"""S2 / F04_core_middlewares：三个内置 middleware（SPEC #middleware 内置三件）。

测试纪律不变（SPEC C3 / 反模式 2）：LLM 只从 FakeLLM 接缝进，工具真执行，不 patch loop 内部。
每件单一关切（SPEC 反模式 3）：Budget 只截断、ErrorHandling 只接异常、Summarization 只压历史。
fixture 复用：错误场景复用 echo_roundtrip（录制只管模型侧，工具实现由测试注入）；
「未超阈值不压缩」用 natural_close 反向证明——只有 1 条录制，压缩若偷跑必弹尽抛错。
"""

from pathlib import Path

import pytest

from src.llm import FakeLLM
from src.loop import State, run
from src.middlewares import Summarization, ToolErrorHandling, ToolOutputBudget

FIXTURES = Path(__file__).parent.parent / "fixtures" / "fake_llm"


class SpewTool:
    """产出超长文本的工具——喂 ToolOutputBudget。"""

    name = "spew"
    description = "输出一大段文本，测试用"
    input_schema = {"type": "object", "properties": {}, "required": []}

    def run(self) -> str:
        return "x" * 10_000


class BoomTool:
    """一调就抛程序性异常的工具——喂 ToolErrorHandling。名字叫 echo 以复用 echo_roundtrip 录制。"""

    name = "echo"
    description = "回显输入文本，测试用"
    input_schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    def run(self, *, text: str) -> str:
        raise FileNotFoundError(f"no such file: {text}")


def make_state() -> State:
    return State(messages=[{"role": "user", "content": "做点事"}])


def tool_results(state: State) -> list[str]:
    """取全部 tool_result 的文本内容。"""
    return [
        block["content"]
        for msg in state.messages
        if msg["role"] == "user" and isinstance(msg["content"], list)
        for block in msg["content"]
        if block.get("type") == "tool_result"
    ]


# ---------- ToolOutputBudget：超预算截断 + 标注 ----------


def test_budget_truncates_oversize_output():
    state = run(
        make_state(),
        llm=FakeLLM(FIXTURES / "oversize_tool_output.json"),
        tools=[SpewTool()],
        middlewares=[ToolOutputBudget(max_chars=200)],
    )
    (result,) = tool_results(state)
    assert result.startswith("x" * 200)
    assert "已截断" in result and "10000" in result
    assert len(result) < 10_000


def test_budget_keeps_small_output_intact():
    state = run(
        make_state(),
        llm=FakeLLM(FIXTURES / "oversize_tool_output.json"),
        tools=[SpewTool()],
        middlewares=[ToolOutputBudget(max_chars=99_999)],
    )
    (result,) = tool_results(state)
    assert result == "x" * 10_000  # 预算内一字不动


def test_budget_exact_boundary_passes():
    """len == max_chars 是「预算内」（<= 放行），边界不截断。"""
    state = run(
        make_state(),
        llm=FakeLLM(FIXTURES / "oversize_tool_output.json"),
        tools=[SpewTool()],
        middlewares=[ToolOutputBudget(max_chars=10_000)],
    )
    (result,) = tool_results(state)
    assert result == "x" * 10_000


# ---------- ToolErrorHandling：异常转错误文本，run 不死 ----------


def test_error_becomes_text_and_run_survives():
    state = run(
        make_state(),
        llm=FakeLLM(FIXTURES / "echo_roundtrip.json"),
        tools=[BoomTool()],
        middlewares=[ToolErrorHandling()],
    )
    # 两轮工具都炸了，但 run 走完全程并自然收口
    assert state.turn_count == 2
    assert state.messages[-1]["content"][0]["type"] == "text"
    results = tool_results(state)
    assert len(results) == 2
    assert all("FileNotFoundError" in r and "no such file" in r for r in results)


def test_error_propagates_without_middleware():
    """对照组 = S1 行为：程序性异常外抛（错误的消费者是代码侧）。"""
    with pytest.raises(FileNotFoundError):
        run(
            make_state(),
            llm=FakeLLM(FIXTURES / "echo_roundtrip.json"),
            tools=[BoomTool()],
        )


# ---------- Summarization：超阈值压缩旧消息（llm 构造注入，Q1=A） ----------


def long_history_state(n: int = 12) -> State:
    msgs = []
    for i in range(n - 1):
        role = "user" if i % 2 == 0 else "assistant"
        content = f"第{i}轮内容" if role == "user" else [{"type": "text", "text": f"第{i}轮答复"}]
        msgs.append({"role": role, "content": content})
    msgs.append({"role": "user", "content": "继续最后一步"})
    return State(messages=msgs)


def test_summarization_compresses_old_messages():
    llm = FakeLLM(FIXTURES / "summarize_history.json")
    state = run(
        long_history_state(12),
        llm=llm,
        tools=[],
        middlewares=[Summarization(llm=llm, max_messages=10, keep_last=4)],
    )
    # 结构 = [摘要消息] + 近 4 条 + 本轮 assistant 收口响应
    assert len(state.messages) == 1 + 4 + 1
    summary = state.messages[0]
    assert summary["role"] == "user"
    assert "早前对话摘要" in summary["content"] and "结论 X" in summary["content"]
    # 「近 K 条」钉的是「后」4 条不是「前」4 条
    assert state.messages[-2]["content"] == "继续最后一步"
    # 「录制=全局调用序」：responses[0] 已被压缩调用消耗，主循环拿到的是 responses[1]
    assert state.messages[-1]["content"][0]["text"] == "基于摘要继续：任务完成。"


def test_summarization_never_splits_tool_pairing():
    """S2 对抗审查红色发现：切点落在 tool_use/tool_result 配对中间时必须让位（API 硬约束）。"""
    msgs = [{"role": "user", "content": "任务开始"}]
    for i in range(3):
        msgs.append({"role": "assistant", "content": [{"type": "text", "text": f"答复{i}"}]})
        msgs.append({"role": "user", "content": f"步骤{i}"})
    msgs.append({"role": "assistant", "content": [
        {"type": "tool_use", "id": "p1", "name": "echo", "input": {"text": "hi"}}]})
    msgs.append({"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "p1", "content": "echo: hi"}]})
    msgs.append({"role": "assistant", "content": [{"type": "text", "text": "工具结果收到"}]})
    msgs.append({"role": "user", "content": "继续最后一步"})
    # 共 11 条；keep_last=3 的切点恰好落在 tool_result 上 → 应向前让位把 tool_use 一并保留
    llm = FakeLLM(FIXTURES / "summarize_history.json")
    state = run(
        State(messages=msgs),
        llm=llm,
        tools=[],
        middlewares=[Summarization(llm=llm, max_messages=10, keep_last=3)],
    )
    assert len(state.messages) == 1 + 4 + 1  # 摘要 + 让位后的近 4 条 + 收口响应
    for i, msg in enumerate(state.messages):
        if msg["role"] == "user" and isinstance(msg["content"], list) and any(
            b.get("type") == "tool_result" for b in msg["content"]
        ):
            prev = state.messages[i - 1]
            assert prev["role"] == "assistant"
            assert any(b.get("type") == "tool_use" for b in prev["content"])


def test_summarization_rejects_self_defeating_config():
    """keep_last >= max_messages = 每轮净增摘要消息、越压越长——构造期直接拒绝。"""
    with pytest.raises(AssertionError):
        Summarization(llm=None, max_messages=4, keep_last=4)


def test_summarization_noop_under_threshold():
    llm = FakeLLM(FIXTURES / "natural_close.json")  # 仅 1 条录制：压缩若偷跑必弹尽
    state = run(
        make_state(),
        llm=llm,
        tools=[],
        middlewares=[Summarization(llm=llm, max_messages=10, keep_last=4)],
    )
    assert len(state.messages) == 2  # 原 user + 收口响应，历史未被动过
    assert state.messages[0] == {"role": "user", "content": "做点事"}
