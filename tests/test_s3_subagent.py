"""S3 / F05_task_subagent：task 工具 + subagent 委派（SPEC #subagent）。

测试纪律不变：LLM 只从 FakeLLM 接缝进——主 agent 与 subagent 共享同一实例，
按「录制=全局调用序」消耗；工具真执行，不 patch。
核心断言：subagent 的中间过程不进主对话（上下文隔离），主对话只见最终结论。
"""

from pathlib import Path

import pytest

from src.llm import FakeLLM
from src.loop import State, run
from src.subagent import TaskTool
from src.tools import BashTool, ReadFileTool, WriteFileTool

FIXTURES = Path(__file__).parent.parent / "fixtures" / "fake_llm"


def tool_results(state) -> list[str]:
    return [
        b["content"]
        for m in state.messages
        if m["role"] == "user" and isinstance(m["content"], list)
        for b in m["content"]
        if b.get("type") == "tool_result"
    ]


def main_tool_use_names(state) -> list[str]:
    return [
        b["name"]
        for m in state.messages
        if isinstance(m["content"], list)
        for b in m["content"]
        if b.get("type") == "tool_use"
    ]


# ---------- 主线：委派 → 只回结论 → 上下文隔离 ----------


def test_task_delegates_and_returns_only_conclusion():
    llm = FakeLLM(FIXTURES / "subagent_flow.json")
    real = [BashTool(), ReadFileTool(), WriteFileTool()]
    task = TaskTool(llm=llm, tools=real)
    state = run(State(messages=[{"role": "user", "content": "统计文件"}]), llm, [*real, task])

    # 主对话只收到 subagent 的最终文本结论
    assert tool_results(state) == ["workspace 下有 1 个文件：data.md。"]
    # 上下文隔离：subagent 内部那步 bash 既不在主对话的 tool_use 里，命令串也没泄进主 messages
    assert main_tool_use_names(state) == ["task"]
    assert "ls fixtures/workspace" not in str(state.messages)
    # 正向确认 subagent 真跑了（不是被跳过）：4 条录制已全消耗，再调即弹尽抛错
    with pytest.raises(RuntimeError):
        llm.complete(system="", messages=[], tools=[])


def test_task_result_is_user_role_tool_result():
    llm = FakeLLM(FIXTURES / "subagent_flow.json")
    real = [BashTool(), ReadFileTool(), WriteFileTool()]
    task = TaskTool(llm=llm, tools=real)
    state = run(State(messages=[{"role": "user", "content": "x"}]), llm, [*real, task])

    tr_msg = next(
        m for m in state.messages if m["role"] == "user" and isinstance(m["content"], list)
    )
    assert tr_msg["content"][0]["type"] == "tool_result"  # 结论走同一条 tool_result 回填路


# ---------- 单层委派：子工具集物理摘掉 task ----------


def test_subagent_toolset_excludes_task():
    llm = FakeLLM(FIXTURES / "subagent_flow.json")
    real = [BashTool()]
    inner = TaskTool(llm=llm, tools=real)
    # 把含 task 的完整清单传进去，构造期应把 task 滤掉（防无限递归）
    outer = TaskTool(llm=llm, tools=[*real, inner])
    assert [t.name for t in outer._tools] == ["bash"]
    assert all(t.name != "task" for t in outer._tools)


# ---------- max_concurrent 截断（Deviation D5：per-run 配额语义） ----------


def test_max_concurrent_truncates():
    llm = FakeLLM(FIXTURES / "subagent_concurrency.json")
    task = TaskTool(llm=llm, tools=[], max_concurrent=3)
    state = run(State(messages=[{"role": "user", "content": "派 4 个"}]), llm, [task])

    results = tool_results(state)
    assert len(results) == 4
    assert results[:3] == ["子任务1完成", "子任务2完成", "子任务3完成"]
    assert "配额" in results[3] or "上限" in results[3]  # 第 4 个被配额拦下，回错误文本


def test_delegation_quota_is_per_instance_lifetime():
    """审查黄1：_delegated 只增不减 = per-instance 生命周期配额，跨 run 泄漏（Deviation D5 的据实语义）。
    钉住既定行为——生产复用同实例（如 S5 run_with_goal）须每 run 重建 TaskTool 或复位计数。"""
    llm = FakeLLM(FIXTURES / "subagent_quota_across_runs.json")
    task = TaskTool(llm=llm, tools=[], max_concurrent=1)  # 同一实例跨两次 run
    s1 = run(State(messages=[{"role": "user", "content": "第一次"}]), llm, [task])
    assert tool_results(s1) == ["子任务完成"]  # run1 配额内，正常委派
    s2 = run(State(messages=[{"role": "user", "content": "第二次"}]), llm, [task])
    quota_msg = tool_results(s2)[0]
    assert "配额" in quota_msg or "上限" in quota_msg  # run2 同实例配额已耗尽 → 跨 run 泄漏


# ---------- _final_text 边界：subagent 熔断收口无文本结论 ----------


def test_final_text_on_subagent_halt():
    """审查黄2：subagent 因 max_turns 熔断、末条是 tool_result（无 text）时，回退到占位而非误当结论。"""
    llm = FakeLLM(FIXTURES / "subagent_halt.json")
    task = TaskTool(llm=llm, tools=[BashTool()], max_turns=1)  # subagent 一拍即熔断
    state = run(State(messages=[{"role": "user", "content": "派个会熔断的"}]), llm, [task])
    assert tool_results(state) == ["[subagent 无文本结论]"]
