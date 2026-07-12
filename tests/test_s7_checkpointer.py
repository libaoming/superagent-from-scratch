"""S7 / F10_checkpointer：断点持久化（SPEC #checkpointer）。

测试纪律不变：LLM 只从 FakeLLM 接缝进，不 patch 内部。「中途死」= 接缝抛异常
（FakeLLM 弹尽 RuntimeError），与 S6 不依赖真实 Timer 是同一门手艺——用接缝的
确定性行为替代真实环境事件（kill -9）。核心断言：①per-step durability（崩溃后磁盘
有上一轮完整快照，两次快照一崩一续）②外壳收口终存（只靠 before_model 会丢最终回复）
③悬空 tool_use 兜底（崩溃悬空补 [interrupted]；待答悬空 interrupt 非空则留给调用方）。
"""

import json
from pathlib import Path

import pytest

from src.checkpoint import Checkpointer, load_state, run_with_checkpoint, save_state
from src.llm import FakeLLM
from src.loop import State, run

FIX = Path(__file__).parent.parent / "fixtures" / "fake_llm"


class EchoTool:
    """极小真实工具：真的执行 run()，只为喂 loop 的工具管线。"""

    name = "echo"
    description = "回显输入文本，测试用"
    input_schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    def run(self, *, text: str) -> str:
        return f"echo: {text}"


# ---------- per-step durability：两次快照，一崩一续（核心断言） ----------


def test_checkpoint_survives_mid_run_crash(tmp_path):
    path = tmp_path / "ckpt.json"
    llm = FakeLLM(FIX / "checkpoint_crash.json")  # 1 条录制：第 2 轮 complete 弹尽 = 中途死
    with pytest.raises(RuntimeError):
        run_with_checkpoint(
            State(messages=[{"role": "user", "content": "回显 step-one 然后继续"}]),
            llm,
            tools=[EchoTool()],
            path=path,
        )
    # 快照一（崩溃后读盘）：停在第 2 轮 before_model 时刻——第 1 轮完整落账，无第 2 轮任何东西
    st = load_state(path)
    assert st.turn_count == 1
    assert len(st.messages) == 3  # user / assistant tool_use / user tool_result
    assert st.messages[1]["content"][0]["type"] == "tool_use"
    assert st.messages[2]["content"][0]["tool_use_id"] == "t1"  # 第 1 轮往返完整（无悬空）
    assert "echo: step-one" in st.messages[2]["content"][0]["content"]
    # 快照二（恢复续跑）：checkpoint 不只是存了，还真能载回来跑完
    llm2 = FakeLLM(FIX / "natural_close.json")
    st2 = run_with_checkpoint(st, llm2, tools=[EchoTool()], path=path)
    assert "42" in st2.messages[-1]["content"][0]["text"]  # 自然收口


# ---------- 外壳收口终存：只靠 before_model 会丢结尾 ----------


def test_final_save_covers_natural_close(tmp_path):
    path = tmp_path / "ckpt.json"
    llm = FakeLLM(FIX / "natural_close.json")  # 首条响应即纯文本收口——全程只有 1 次 before_model
    run_with_checkpoint(
        State(messages=[{"role": "user", "content": "直接回答"}]),
        llm,
        tools=[],
        path=path,
    )
    loaded = load_state(path)
    # 最终 assistant 回复在盘上：before_model 那次存的还是 [user]，只有收口终存能写进回复
    assert loaded.messages[-1]["role"] == "assistant"
    assert "42" in loaded.messages[-1]["content"][0]["text"]


# ---------- 悬空 tool_use 兜底：崩溃悬空补 [interrupted]，待答悬空留给调用方 ----------


def test_load_state_patches_dangling_tool_use(tmp_path):
    dangling_msgs = [
        {"role": "user", "content": "数一下文件"},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "t9", "name": "bash", "input": {}}]},
    ]
    # 崩溃悬空（interrupt 空）：末条 tool_use 无配对 → load 时补 [interrupted]，否则下轮 API 400
    crash = tmp_path / "crash.json"
    crash.write_text(json.dumps(
        {"messages": dangling_msgs, "turn_count": 0, "todos": [], "goal": "", "interrupt": None},
        ensure_ascii=False,
    ))
    st = load_state(crash)
    patched = st.messages[-1]
    assert patched["role"] == "user"
    assert patched["content"][0]["tool_use_id"] == "t9"
    assert "[interrupted]" in patched["content"][0]["content"]
    # 待答悬空（interrupt 非空 = HITL 中断收口）：答案归调用方补，load 不许抢着填
    hitl = tmp_path / "hitl.json"
    hitl.write_text(json.dumps(
        {"messages": dangling_msgs, "turn_count": 0, "todos": [], "goal": "",
         "interrupt": {"question": "要数哪个目录？"}},
        ensure_ascii=False,
    ))
    st2 = load_state(hitl)
    assert st2.interrupt.question == "要数哪个目录？"  # Interrupt 对象回装
    assert st2.messages[-1]["role"] == "assistant"  # 未被兜底篡改，悬空留给调用方补答案


# ---------- save/load 往返：State 字段全量保真（S8 起六字段；promoted 的 roundtrip 由 test_s8 钉） ----------


def test_save_load_roundtrip_preserves_all_fields(tmp_path):
    path = tmp_path / "ckpt.json"
    state = State(
        messages=[{"role": "user", "content": "hi"},
                  {"role": "assistant", "content": [{"type": "text", "text": "ok"}]}],
        turn_count=3,
        todos=[{"task": "写测试", "status": "done"}],
        goal="全绿",
    )
    save_state(path, state)
    loaded = load_state(path)
    assert loaded.messages == state.messages
    assert loaded.turn_count == 3
    assert loaded.todos == state.todos
    assert loaded.goal == "全绿"
    assert loaded.interrupt is None


# ---------- Checkpointer 是缝①住户：单挂 middleware 也工作（不依赖外壳） ----------


def test_checkpointer_is_a_plain_middleware(tmp_path):
    path = tmp_path / "ckpt.json"
    llm = FakeLLM(FIX / "natural_close.json")
    run(
        State(messages=[{"role": "user", "content": "直接回答"}]),
        llm,
        tools=[],
        middlewares=[Checkpointer(path)],
    )
    loaded = load_state(path)  # before_model 存过：至少有进模型前的快照
    assert loaded.messages[0]["content"] == "直接回答"
    assert loaded.messages[-1]["role"] == "user"  # 无终存（没套外壳）——最终回复不在盘上，反证两件套缺一不可
