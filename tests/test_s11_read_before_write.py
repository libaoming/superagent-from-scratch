"""S11 / F14_read_before_write：写前版本门（SPEC #read-before-write）。

测试纪律不变（C3 / 反模式 2）：FakeLLM 唯一接缝、工具真实执行——真文件放 fixtures/workspace/
下由 pytest fixture setup/teardown（录制里的 path 是相对仓库根的固定字符串，tmp_path 用不了）。
读记录寄生 messages（F14 out_of_scope 禁令：不开 State 字段）；设计不变量「压缩后写被拦、
逼重读」（2026-07-13 纠错版）由 test_gate_decays_with_summarization 钉住。
fail-open = 课上拍板 A（记录 0022），[version-gate bypassed] 留痕 = 教学环反哺第四例。
"""

from pathlib import Path

import pytest

from src.llm import FakeLLM
from src.loop import State, run
from src.middlewares import ReadBeforeWrite, Summarization, ToolOutputBudget
from src.tools import ReadFileTool, WriteFileTool, render_numbered

FIXTURES = Path(__file__).parent.parent / "fixtures" / "fake_llm"
SCRATCH = Path("fixtures/workspace/gate_scratch.md")  # 相对仓库根（pytest 从根跑，反模式 6 既有约束）


@pytest.fixture
def scratch_file():
    SCRATCH.write_text("v1：原始笔记")
    yield SCRATCH
    SCRATCH.unlink(missing_ok=True)


def make_state(task: str = "改写工作区笔记") -> State:
    return State(messages=[{"role": "user", "content": task}])


def gated_run(state: State, llm) -> State:
    return run(
        state,
        llm=llm,
        tools=[ReadFileTool(), WriteFileTool()],
        middlewares=[ReadBeforeWrite(state=state)],
    )


def tool_results(state: State) -> list[str]:
    return [
        block["content"]
        for msg in state.messages
        if msg["role"] == "user" and isinstance(msg["content"], list)
        for block in msg["content"]
        if block.get("type") == "tool_result"
    ]


# ---------- 主流程：盲写被拦 → 读 → 重试放行（自救弧） ----------


def test_blind_write_blocked_then_rescue(scratch_file):
    state = gated_run(make_state(), FakeLLM(FIXTURES / "gate_blind_write_rescue.json"))
    results = tool_results(state)
    # 首写被拦：教学式 error 给修复路径（guard 家族方言），未真执行
    assert "版本门" in results[0] and "read_file" in results[0]
    # 读后重试放行，磁盘终态 = 读后版本（盲写版从未落盘）
    assert "已写入" in results[2]
    assert scratch_file.read_text() == "v2：读后改写"
    assert state.turn_count == 3


def test_write_after_write_requires_reread(scratch_file):
    """「写不刷新 mark」零实现行：首写后磁盘已变，旧 read hash 自动失配——连续两写必须重读。"""
    state = gated_run(make_state(), FakeLLM(FIXTURES / "gate_write_write.json"))
    results = tool_results(state)
    assert "已写入" in results[1]
    assert "版本门" in results[2]  # 第二写被拦
    assert scratch_file.read_text() == "第二版"  # 第三版从未落盘


def test_stale_read_blocked_after_external_change(scratch_file):
    """读旧版被拦：跨两次 run 的外部改档（同 llm 实例，「录制=全局调用序」）。"""
    llm = FakeLLM(FIXTURES / "gate_stale_read.json")
    state = make_state()
    gated_run(state, llm)  # run1：读 + 收口
    scratch_file.write_text("外部修改的内容")  # 两次 run 之间，磁盘被别人改了
    state.messages.append({"role": "user", "content": "现在改写它"})
    gated_run(state, llm)  # run2：写被拦（读过，但读的是旧版）
    assert "版本门" in tool_results(state)[-1]
    assert scratch_file.read_text() == "外部修改的内容"  # 基于旧知识的写没生效


# ---------- 设计不变量：压缩删读记录 → 写被拦、逼重读（门与模型记忆同生共死） ----------


def test_gate_decays_with_summarization(scratch_file):
    """2026-07-13 纠错版不变量：hash 本匹配（磁盘未变），只因 read 记录被压缩删掉才拦——
    模型不记得内容了，门跟着忘、逼它重读。「压缩后还放行」才是 bug（绕门漏洞）。"""
    msgs = [{"role": "user", "content": "任务开始"}]
    msgs.append({"role": "assistant", "content": [
        {"type": "tool_use", "id": "old1", "name": "read_file", "input": {"path": str(SCRATCH)}}]})
    msgs.append({"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "old1",
         "content": render_numbered(SCRATCH.read_text())}]})  # 真实渲染：不压缩的话本可放行
    for i in range(8):  # 垫长历史，把 read 配对推进「将被压缩」的 old 段
        msgs.append({"role": "assistant", "content": [{"type": "text", "text": f"步骤{i}答复"}]})
        msgs.append({"role": "user", "content": f"步骤{i}"})
    msgs.append({"role": "user", "content": "继续改写这份笔记"})
    state = State(messages=msgs)
    llm = FakeLLM(FIXTURES / "gate_summarization_decay.json")
    run(
        state,
        llm=llm,
        tools=[ReadFileTool(), WriteFileTool()],
        # max_messages=12：初始 20 条触发压缩；压缩后最多涨到 11 条，第二次压缩不会偷跑吃掉收口录制
        middlewares=[Summarization(llm=llm, max_messages=12, keep_last=4), ReadBeforeWrite(state=state)],
    )
    # 压缩真发生（反证链前提：read 记录确实被压掉了）
    assert any("早前对话摘要" in str(m.get("content")) for m in state.messages)
    results = tool_results(state)
    assert "版本门" in results[0]  # 压缩后的首写被拦——设计不变量
    assert scratch_file.read_text() == "重读后的改写"  # 重读 → 再写放行


# ---------- fail-open（拍板 A）与新文件放行 ----------


def test_fail_open_with_bypass_note():
    """门读不了（二进制 UnicodeDecodeError）→ 放行 + 留痕标注（P3 可观测），写真执行成功。"""
    bin_path = Path("fixtures/workspace/gate_binary.bin")
    bin_path.write_bytes(b"\xff\xfe\x00binary")
    try:
        state = gated_run(make_state("清理二进制文件"), FakeLLM(FIXTURES / "gate_fail_open.json"))
        (result,) = tool_results(state)
        assert "version-gate bypassed" in result  # 静默放行的缓解：留痕
        assert "已写入" in result  # 放行后 write 真执行
        assert bin_path.read_text() == "清理为文本内容"
    finally:
        bin_path.unlink(missing_ok=True)


def test_truncated_read_bypasses_gate_not_deadlock(scratch_file):
    """审查红1（2026-07-13）：ToolOutputBudget 截断读记录后，与磁盘全文永不可比——
    硬拦会让「重读→再写」也被拦（死循环指路牌真实现形）。修复语义：检出截断标注 →
    fail-open 留痕放行，而非教学式 error。"""
    scratch_file.write_text("大文件内容行\n" * 200)  # 渲染后远超预算，读结果必被截断
    state = make_state("精简这个大文件")
    run(
        state,
        llm=FakeLLM(FIXTURES / "gate_truncated_read.json"),
        tools=[ReadFileTool(), WriteFileTool()],
        # Budget 注册在前（洋葱外层）：截断的是「门透传后的真实读结果」，截断文本进 messages
        middlewares=[ToolOutputBudget(max_chars=200), ReadBeforeWrite(state=state)],
    )
    results = tool_results(state)
    assert "已截断" in results[0]  # 前提成立：读记录确实被截断
    assert "version-gate bypassed" in results[1]  # 放行留痕，而非拦截
    assert "版本门拦下" not in results[1]  # 不是死循环的那条 error
    assert scratch_file.read_text() == "精简后的内容"  # 写真执行


def test_new_file_write_passes():
    """新文件直接放行且不留 bypass 痕：没有旧内容可覆盖，这不是 fail-open，是防御面收窄。"""
    new_path = Path("fixtures/workspace/gate_new_note.md")
    new_path.unlink(missing_ok=True)
    try:
        state = gated_run(make_state("建个新笔记"), FakeLLM(FIXTURES / "gate_new_file.json"))
        (result,) = tool_results(state)
        assert result.startswith("已写入")  # 干净放行：无拦截、无 bypass 前缀
        assert new_path.read_text() == "全新文件，无需先读"
    finally:
        new_path.unlink(missing_ok=True)
