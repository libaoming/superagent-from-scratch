"""S5 / F08_clarification_hitl：ask_clarification 中断 + 带答案恢复（SPEC #long-task · HITL）。

测试纪律不变：LLM 只从 FakeLLM 接缝进，不 patch loop 内部。
核心断言 = HITL 三件事：①中断先于工具执行（工具没跑）②问题经 state.interrupt 带出（返回通道）
③补 tool_result（用户答案）+ 清 interrupt → 重进同一 run 自然收口。
「录制=全局调用序」：run1 消耗 response[0]（提问）、恢复后的 run2 消耗 response[1]（带答案收口）。
"""

from pathlib import Path

from src.llm import FakeLLM
from src.loop import State, run
from src.middlewares import AskClarification, Clarification

FIXTURES = Path(__file__).parent.parent / "fixtures" / "fake_llm"


def make_state() -> State:
    return State(messages=[{"role": "user", "content": "统计文件数"}])


def tool_results(state: State) -> list[dict]:
    return [
        block
        for msg in state.messages
        if msg["role"] == "user" and isinstance(msg["content"], list)
        for block in msg["content"]
        if block.get("type") == "tool_result"
    ]


def last_tool_use(state: State) -> dict | None:
    blocks = state.messages[-1]["content"]
    if isinstance(blocks, list):
        for b in blocks:
            if b.get("type") == "tool_use":
                return b
    return None


# ---------- 中断：问题经 state.interrupt 带出，工具没跑 ----------


def test_clarification_interrupts_before_tool_runs():
    llm = FakeLLM(FIXTURES / "clarification_flow.json")
    state = run(
        make_state(),
        llm=llm,
        tools=[AskClarification()],
        middlewares=[Clarification()],
    )
    # ② 返回通道：问题挂在 state.interrupt 上（loop 丢弃 after_model 返回值，靠 state 带出）
    assert state.interrupt is not None
    assert state.interrupt.question == "你要统计哪个目录下的文件数？"
    # 末条是悬空的 ask_clarification tool_use（现场已保存，等答案配对）
    tu = last_tool_use(state)
    assert tu is not None and tu["name"] == "ask_clarification"
    # ① 中断先于工具执行：工具没跑（无 tool_result）、turn_count 未自增
    assert tool_results(state) == []
    assert state.turn_count == 0


# ---------- 恢复：补 tool_result（答案）+ 清 interrupt → 重进 run 收口 ----------


def test_resume_with_answer_continues_to_close():
    llm = FakeLLM(FIXTURES / "clarification_flow.json")
    state = run(make_state(), llm=llm, tools=[AskClarification()], middlewares=[Clarification()])

    # 调用方拿到用户答案，补一条 tool_result 配对悬空的 tool_use，清中断，重进同一 run
    tu = last_tool_use(state)
    state.messages.append(
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": tu["id"], "content": "统计 fixtures/workspace"}
        ]}
    )
    state.interrupt = None
    state = run(state, llm=llm, tools=[AskClarification()], middlewares=[Clarification()])

    # ③ 带答案重进 → 自然收口（response[1]），中断已清
    assert state.interrupt is None
    assert state.messages[-1]["role"] == "assistant"
    assert state.messages[-1]["content"][0]["text"] == "好的，fixtures/workspace 下有 1 个文件：data.md。"


# ---------- 无澄清：middleware 在场但模型没调 → 正常收口，interrupt 恒 None ----------


def test_no_clarification_passes_through():
    # natural_close 仅 1 条纯文本录制：Clarification 在场也不该干预
    state = run(
        State(messages=[{"role": "user", "content": "做点事"}]),
        llm=FakeLLM(FIXTURES / "natural_close.json"),
        tools=[AskClarification()],
        middlewares=[Clarification()],
    )
    assert state.interrupt is None
    assert state.messages[-1]["content"][0]["type"] == "text"


# ---------- 工具本身惰性：没挂 middleware 时 run() 只兜底回显，不静默吞 ----------


def test_ask_clarification_tool_is_inert_fallback():
    out = AskClarification().run(question="你要哪个目录？")
    assert "未处理的澄清请求" in out and "你要哪个目录？" in out
