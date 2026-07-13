"""S10 / F13_loop_detection：LoopDetection + TokenBudget 加餐（SPEC #loop-detection）。

测试纪律不变（C3 / 反模式 2）：LLM 只从 FakeLLM 接缝进、不 patch loop 内部——
警告注入、剥 tool_use 硬停全部通过 state.messages 的可观察形状断言。
滑窗计数是 middleware 实例变量（2026-07-13 课上拍板 A）：不进 State、不触 S7 字段表。
"""

from pathlib import Path

import pytest

from src.llm import FakeLLM
from src.loop import State, run
from src.middlewares import AskClarification, Clarification, LoopDetection, TokenBudget

FIXTURES = Path(__file__).parent.parent / "fixtures" / "fake_llm"


class SearchTool:
    name = "search"
    description = "检索资料，测试用"
    input_schema = {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    }

    def run(self, *, query: str) -> str:
        return f"结果：关于「{query}」的资料若干"


class ReadDocTool:
    """带 offset 的读类工具——喂分桶归一化（真实 read_file 无行号参数，逃检场景需要它）。"""

    name = "read_doc"
    description = "从指定行号起读文档，测试用"
    input_schema = {
        "type": "object",
        "properties": {"path": {"type": "string"}, "offset": {"type": "integer"}},
        "required": ["path", "offset"],
    }

    def run(self, *, path: str, offset: int) -> str:
        return f"{path} 第 {offset} 行起的内容……"


class WriteNoteTool:
    """名字含 write → 归一化走全参（严出）。不落真实文件，只回执。"""

    name = "write_note"
    description = "记笔记，测试用"
    input_schema = {
        "type": "object",
        "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
        "required": ["path", "content"],
    }

    def run(self, *, path: str, content: str) -> str:
        return f"已记 {len(content)} 字符"


def make_state(task: str = "查部署失败原因") -> State:
    return State(messages=[{"role": "user", "content": task}])


def injected(state: State, mark: str) -> list[str]:
    """收集以 mark 开头的注入 user 消息（警告走 before_model append，形态同 TodoMiddleware）。"""
    return [
        m["content"]
        for m in state.messages
        if m["role"] == "user" and isinstance(m["content"], str) and m["content"].startswith(mark)
    ]


def last_text(state: State) -> str:
    return "".join(b["text"] for b in state.messages[-1]["content"] if b["type"] == "text")


def assert_pairing_intact(state: State) -> None:
    """任何注入都不许把 tool_result 与它的 tool_use 拆开（API 硬约束第三个引爆点）。"""
    for i, msg in enumerate(state.messages):
        if msg["role"] == "user" and isinstance(msg["content"], list) and any(
            b.get("type") == "tool_result" for b in msg["content"]
        ):
            prev = state.messages[i - 1]
            assert prev["role"] == "assistant"
            assert any(b.get("type") == "tool_use" for b in prev["content"])


# ---------- LoopDetection：警告延迟注入 → 硬停剥 tool_use ----------


def test_repeat_calls_warn_then_hard_stop():
    state = run(
        make_state(),
        llm=FakeLLM(FIXTURES / "loop_repeat_calls.json"),
        tools=[SearchTool()],
        middlewares=[LoopDetection(warn_threshold=2, hard_threshold=3)],
    )
    # 警告：第 2 次重复排队、下一轮 before_model 注入，且不落在配对中间
    assert len(injected(state, LoopDetection.WARN_MARK)) == 1
    assert_pairing_intact(state)
    # 硬停：末条 assistant 的 tool_use 被剥掉（终止条件 1 自然收口，不抛异常）
    last = state.messages[-1]
    assert last["role"] == "assistant"
    assert all(b["type"] != "tool_use" for b in last["content"])
    # 「留/补」双断言：模型已有文本存活 + 停机说明补入（可观测留痕）
    assert "再查一次应该就有了。" in last_text(state)
    assert LoopDetection.STOP_MARK in last_text(state)
    assert state.turn_count == 2  # 第 3 轮工具未执行


def test_warning_enables_self_rescue():
    state = run(
        make_state(),
        llm=FakeLLM(FIXTURES / "loop_self_rescue.json"),
        tools=[SearchTool()],
        middlewares=[LoopDetection(warn_threshold=2, hard_threshold=3)],
    )
    # 恰好一次警告；换 query 后计数归 1，run 继续到自然收口——警告档教自救、不惩罚
    assert len(injected(state, LoopDetection.WARN_MARK)) == 1
    assert LoopDetection.STOP_MARK not in str(state.messages)
    assert "换角度查到了" in last_text(state)
    assert state.turn_count == 3


# ---------- 归一化不对称：读类宽进（分桶防逃检） vs 写类严出（全参防误报） ----------


def test_read_offsets_bucket_together():
    """换行号刷读逃不了检：offset 0/100/199 同落 200 行桶 → 视为相同调用 → 硬停。"""
    state = run(
        make_state("读一下文档"),
        llm=FakeLLM(FIXTURES / "loop_offset_bucket.json"),
        tools=[ReadDocTool()],
        middlewares=[LoopDetection(warn_threshold=2, hard_threshold=3)],
    )
    assert len(injected(state, LoopDetection.WARN_MARK)) == 1
    assert LoopDetection.STOP_MARK in last_text(state)
    assert all(b["type"] != "tool_use" for b in state.messages[-1]["content"])


def test_write_full_args_never_flags_legit_edits():
    """对同一文件的多次合法小改不被误杀：写类 hash 全参，content 不同即不同调用。"""
    state = run(
        make_state("迭代这份笔记"),
        llm=FakeLLM(FIXTURES / "loop_write_full_args.json"),
        tools=[WriteNoteTool()],
        middlewares=[LoopDetection(warn_threshold=2, hard_threshold=3)],
    )
    assert injected(state, LoopDetection.WARN_MARK) == []
    assert LoopDetection.STOP_MARK not in str(state.messages)
    assert "笔记已迭代三版完成。" in last_text(state)
    assert state.turn_count == 3


# ---------- TokenBudget 加餐：同基建第二住户，检测对象=花费 ----------


def test_budget_warns_on_spend():
    state = run(
        make_state("查两份资料"),
        llm=FakeLLM(FIXTURES / "token_budget_overflow.json"),
        tools=[SearchTool()],
        middlewares=[TokenBudget(warn_chars=1, hard_chars=10**9)],
    )
    # 每个工具轮排队一条（单槽），两个工具轮 → 注入 2 条；不硬停、自然收口
    assert len(injected(state, TokenBudget.WARN_MARK)) == 2
    assert TokenBudget.STOP_MARK not in str(state.messages)
    assert "花费可控，任务完成。" in last_text(state)
    assert_pairing_intact(state)


def test_budget_hard_stops():
    """复用 endless_tool_calls（4 条录制）：hard=2 首轮即剥，多余录制不该被消费。"""
    state = run(
        make_state(),
        llm=FakeLLM(FIXTURES / "endless_tool_calls.json"),
        tools=[SearchTool()],
        middlewares=[TokenBudget(warn_chars=1, hard_chars=2)],
    )
    assert TokenBudget.STOP_MARK in last_text(state)
    assert all(b["type"] != "tool_use" for b in state.messages[-1]["content"])
    assert state.turn_count == 0  # 首轮工具未执行即收口


# ---------- 挂载次序契约（对抗审查 2026-07-13 黄3）：同挂不双剥、Interrupt 先行 ----------


def test_co_mounted_guards_strip_once_and_survive():
    """双件同挂（真实场景必然）：注册 [TokenBudget, LoopDetection]，after 逆序 LoopDetection 先跑、
    轮 3 它剥；TokenBudget 后跑走「无 tool_use 早退」跳过已剥轮——先剥者赢，不双剥不炸。"""
    state = run(
        make_state(),
        llm=FakeLLM(FIXTURES / "loop_repeat_calls.json"),
        tools=[SearchTool()],
        middlewares=[
            TokenBudget(warn_chars=1, hard_chars=10**9),
            LoopDetection(warn_threshold=2, hard_threshold=3),
        ],
    )
    assert LoopDetection.STOP_MARK in last_text(state)
    assert TokenBudget.STOP_MARK not in str(state.messages)  # 早退免疫：没有第二段停机说明
    assert all(b["type"] != "tool_use" for b in state.messages[-1]["content"])
    # 两件的警告各自独立注入（每件每轮至多一条；连续两条 user 消息合法，同 todo 先例）
    assert len(injected(state, LoopDetection.WARN_MARK)) == 1
    assert len(injected(state, TokenBudget.WARN_MARK)) == 2
    assert_pairing_intact(state)


def test_interrupt_wins_when_guard_registered_before_clarification():
    """挂载次序契约：防御件注册在 Clarification 之前（after 逆序 → Clarification 先跑）——
    Interrupt 先行收口，防御件的 after 根本不跑：tool_use 完好不被剥、问题不丢。"""
    state = run(
        State(messages=[{"role": "user", "content": "盯一下部署"}]),
        llm=FakeLLM(FIXTURES / "loop_hardstop_vs_clarification.json"),
        tools=[SearchTool(), AskClarification()],
        middlewares=[LoopDetection(warn_threshold=1, hard_threshold=2), Clarification()],
    )
    assert state.interrupt is not None
    assert state.interrupt.question == "要盯 staging 还是 prod？"
    assert any(b["type"] == "tool_use" for b in state.messages[-1]["content"])  # 未被剥
    assert LoopDetection.STOP_MARK not in str(state.messages)


# ---------- 共享基建的构造闸门：warn < hard 是延迟注入的硬性推论 ----------


def test_two_tier_rejects_warn_not_below_hard():
    """两档重合时硬停当轮收口，排队的警告永远等不到「下一轮 before_model」——构造期直接拒绝。"""
    with pytest.raises(AssertionError):
        LoopDetection(warn_threshold=3, hard_threshold=3)
    with pytest.raises(AssertionError):
        TokenBudget(warn_chars=5, hard_chars=4)
