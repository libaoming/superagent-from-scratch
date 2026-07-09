"""S5 / F07_todo_goal：计划外置 + goal 续跑（SPEC #long-task）。

测试纪律不变：LLM 只从 FakeLLM 接缝进，不 patch 内部。「录制=全局调用序」：run 与 goal 评估
共用同一 responses 序列，交错排对（工作文本 / YES-NO 评估）。
核心断言：①续跑到达成 ②两个熔断各管一层（无进展 / 次数）③turn_count 每续跑重置 + _delegated 每轮复位
（拆 S3 D5 埋雷）④计划外置到 state.todos、摘要压不掉 ⑤中断优先于续跑。
"""

from pathlib import Path

from src.goal import run_with_goal
from src.llm import FakeLLM
from src.loop import State
from src.middlewares import AskClarification, Clarification, TodoMiddleware, WriteTodos
from src.subagent import TaskTool

FIX = Path(__file__).parent.parent / "fixtures" / "fake_llm"


class Resettable:
    """有 reset() 的桩工具——验证 run_with_goal 每轮复位（拆 D5 埋雷）。fixture 全文本，永不被调。"""

    name = "noop"
    description = "test stub"
    input_schema = {"type": "object", "properties": {}, "required": []}

    def __init__(self):
        self.reset_count = 0

    def reset(self) -> None:
        self.reset_count += 1

    def run(self) -> str:
        return ""


def assistant_texts(state: State) -> list[str]:
    return [
        b["text"]
        for m in state.messages
        if m["role"] == "assistant" and isinstance(m["content"], list)
        for b in m["content"]
        if b.get("type") == "text"
    ]


def has_continuation(state: State) -> bool:
    return any(
        isinstance(m["content"], str) and "[目标未完成]" in m["content"] for m in state.messages
    )


# ---------- 续跑闭环：未达成→注入续跑→达成收工 ----------


def test_goal_continues_until_met():
    llm = FakeLLM(FIX / "goal_continuation.json")
    tool = Resettable()
    state = State(
        messages=[{"role": "user", "content": "统计 workspace 文件数"}],
        goal="统计出 fixtures/workspace 的文件数",
    )
    state = run_with_goal(state, llm, tools=[tool])

    assert state.interrupt is None
    assert has_continuation(state)  # 发生了续跑（隐藏续跑消息在 messages）
    texts = assistant_texts(state)
    assert any("第一步完成" in t for t in texts) and any("目标已达成" in t for t in texts)
    # _delegated 每轮复位：2 轮 run → reset 2 次（拆 D5 埋雷）
    assert tool.reset_count == 2
    # turn_count 每续跑重置：末轮自然收口无工具，停在 0
    assert state.turn_count == 0


def test_delegation_quota_resets_across_continuations():
    # Y5 整合：真 TaskTool（max_concurrent=1）穿过 run_with_goal 两轮续跑、每轮各委派一次。
    # 若 _delegated 不每轮复位，第 2 轮委派撞满配额回 [task error]——端到端证「拆了 D5 埋雷」。
    llm = FakeLLM(FIX / "goal_with_delegation.json")
    task = TaskTool(llm, tools=[], max_concurrent=1)
    state = State(messages=[{"role": "user", "content": "统计文件"}], goal="统计出文件数")
    state = run_with_goal(state, llm, tools=[task])

    results = [
        b["content"]
        for m in state.messages
        if m["role"] == "user" and isinstance(m["content"], list)
        for b in m["content"]
        if b.get("type") == "tool_result"
    ]
    # 两轮委派都真正跑到 subagent（拿回子任务结论），第 2 轮没被配额拒（无 [task error]）
    assert any("子任务1完成" in r for r in results)
    assert any("子任务2完成" in r for r in results)
    assert not any(r.startswith("[task error]") for r in results)


def test_no_goal_is_single_run():
    # goal 空 → 退化单次 run、不评估（natural_close 仅 1 条，评估若偷跑必弹尽抛错）
    state = run_with_goal(
        State(messages=[{"role": "user", "content": "做点事"}]),
        FakeLLM(FIX / "natural_close.json"),
        tools=[],
    )
    assert state.messages[-1]["content"][0]["text"] == "你好，这个问题不需要用工具，直接回答：42。"
    assert not has_continuation(state)


# ---------- 两个熔断各管一层 ----------


def test_stale_circuit_breaker():
    # 连续 2 次续跑产出相同文本 → 无进展熔断，跑 3 轮即停（不是 8 轮），目标未达成
    state = State(messages=[{"role": "user", "content": "处理"}], goal="完成任务")
    state = run_with_goal(state, FakeLLM(FIX / "goal_stale.json"), tools=[])
    assert assistant_texts(state) == ["我还在处理中。"] * 3
    assert state.interrupt is None


def test_continuation_count_cap():
    # 每轮文本不同（不触发无进展）、始终 NO → 靠次数上限兜底。max_continuations=2 → 跑 3 轮即停
    state = State(messages=[{"role": "user", "content": "推进"}], goal="完成任务")
    state = run_with_goal(state, FakeLLM(FIX / "goal_cap.json"), tools=[], max_continuations=2)
    texts = assistant_texts(state)
    assert len(texts) == 3
    assert texts[-1] == "进展 C：完成了统计。"


# ---------- 计划外置：write_todos → state.todos → before_model 注入 ----------


def test_write_todos_externalizes_plan():
    state = State(messages=[{"role": "user", "content": "开始"}])
    out = WriteTodos(state).run(
        todos=[
            {"content": "列目录", "status": "completed"},
            {"content": "数文件", "status": "pending"},
        ]
    )
    assert state.todos[1]["content"] == "数文件"  # 全量写进 state
    assert "2 项" in out and "已完成 1" in out
    TodoMiddleware().before_model(state)
    reminder = state.messages[-1]
    assert reminder["role"] == "user" and reminder["content"].startswith("[当前计划]")
    assert "数文件" in reminder["content"] and "completed" in reminder["content"]


def test_todo_reminder_survives_history_reset():
    # 模拟 Summarization 把历史压没：计划仍在 state.todos → 提醒从 state 重生（摘要压不掉）
    state = State(
        messages=[{"role": "user", "content": "开始"}],
        todos=[{"content": "关键步骤", "status": "in_progress"}],
    )
    mw = TodoMiddleware()
    mw.before_model(state)  # 注入一次
    state.messages[:] = [{"role": "user", "content": "[早前对话摘要] 略"}]  # 历史被压缩、旧提醒也没了
    mw.before_model(state)  # 再进一轮 before_model → 从 state.todos 重注
    reminders = [
        m for m in state.messages if isinstance(m["content"], str) and m["content"].startswith("[当前计划]")
    ]
    assert len(reminders) == 1  # 只保留一条、不累积
    assert "关键步骤" in reminders[0]["content"]


# ---------- 中断优先于续跑（与 F08 的边界） ----------


def test_interrupt_preempts_continuation():
    # goal 非空但 run 内触发 clarification 中断 → 立即交回调用方，不续跑、不评估
    state = State(messages=[{"role": "user", "content": "统计文件"}], goal="统计出文件数")
    state = run_with_goal(
        state,
        FakeLLM(FIX / "clarification_flow.json"),
        tools=[AskClarification()],
        middlewares=[Clarification()],
    )
    assert state.interrupt is not None
    assert state.interrupt.question == "你要统计哪个目录下的文件数？"
    assert not has_continuation(state)  # 没续跑（没消耗 response[1]、没注入续跑消息）
