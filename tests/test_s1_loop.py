"""S1 / F01_agent_loop：核心循环 + FakeLLM 接缝。

测试纪律（SPEC C3 / 反模式 2）：唯一接缝是 LLMClient（FakeLLM 读 fixture 按序弹出），
不 patch loop 内部；工具用测试内定义的极小真实工具（真执行，非 mock）。
终止条件穷举见 SPEC #loop：自然收口 / turn 熔断 / 中断信号（S5 才有，此处不测）。
"""

from pathlib import Path

import pytest

from src.llm import FakeLLM
from src.loop import State, run

FIXTURES = Path(__file__).parent.parent / "fixtures" / "fake_llm"


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


def make_state(prompt: str = "做点事") -> State:
    return State(messages=[{"role": "user", "content": prompt}])


# ---------- FakeLLM 契约 ----------


def test_fake_llm_pops_in_order():
    llm = FakeLLM(FIXTURES / "echo_roundtrip.json")
    r1 = llm.complete(system="", messages=[], tools=[])
    r2 = llm.complete(system="", messages=[], tools=[])
    assert r1["role"] == "assistant"
    assert r1["content"][0]["type"] == "tool_use"
    assert r1["content"][0]["input"] == {"text": "hello"}
    assert r2["content"][0]["input"] == {"text": "world"}


def test_fake_llm_exhausted_raises():
    llm = FakeLLM(FIXTURES / "natural_close.json")
    llm.complete(system="", messages=[], tools=[])
    with pytest.raises(RuntimeError, match="fixture"):
        llm.complete(system="", messages=[], tools=[])


# ---------- 终止条件 1：自然收口 ----------


def test_natural_close():
    state = run(
        make_state("42 是什么"),
        llm=FakeLLM(FIXTURES / "natural_close.json"),
        tools=[EchoTool()],
        system="你是测试助手",
    )
    assert len(state.messages) == 2  # user + assistant 纯文本，立即收口
    assert state.messages[-1]["role"] == "assistant"
    assert state.messages[-1]["content"][0]["type"] == "text"
    assert state.turn_count == 0  # 没执行过工具轮


# ---------- 工具往返：回填形状 + 计数 ----------


def test_tool_roundtrip():
    state = run(
        make_state(),
        llm=FakeLLM(FIXTURES / "echo_roundtrip.json"),
        tools=[EchoTool()],
        system="",
    )
    # 消息序：user / assistant(tool_use) / user(tool_result) / assistant(tool_use) / user(tool_result) / assistant(text)
    roles = [m["role"] for m in state.messages]
    assert roles == ["user", "assistant", "user", "assistant", "user", "assistant"]

    first_result = state.messages[2]["content"][0]
    assert first_result["type"] == "tool_result"
    assert first_result["tool_use_id"] == "t1"  # id 必须对上 tool_use
    assert first_result["content"] == "echo: hello"  # 工具真实执行的输出

    second_result = state.messages[4]["content"][0]
    assert second_result["tool_use_id"] == "t2"
    assert second_result["content"] == "echo: world"

    assert state.messages[-1]["content"][0]["type"] == "text"
    assert state.turn_count == 2


def test_parallel_tool_results_in_single_user_message():
    """同一响应的多个 tool_use，结果必须全部并入紧随其后的同一条 user 消息（API 硬约束）。"""
    state = run(
        make_state(),
        llm=FakeLLM(FIXTURES / "parallel_tools.json"),
        tools=[EchoTool()],
        system="",
    )
    result_msg = state.messages[2]
    assert result_msg["role"] == "user"
    assert [b["tool_use_id"] for b in result_msg["content"]] == ["p1", "p2"]
    assert [b["content"] for b in result_msg["content"]] == ["echo: alpha", "echo: beta"]
    assert state.turn_count == 1  # 一轮并行工具 = 一个 turn


# ---------- 终止条件 2：turn 熔断 ----------


def test_max_turns_fuse():
    state = run(
        make_state(),
        llm=FakeLLM(FIXTURES / "endless_tool_calls.json"),
        tools=[EchoTool()],
        system="",
        max_turns=2,
    )
    assert state.turn_count == 2  # 到上限强制收口，不再进模型
    # 最后一条是回填的 tool_result（熔断收口），不是 assistant 文本
    assert state.messages[-1]["role"] == "user"
    assert state.messages[-1]["content"][0]["type"] == "tool_result"


# ---------- loop 把工具 schema 递给 llm ----------


def test_loop_passes_tool_schemas_to_llm():
    class RecordingFake(FakeLLM):
        def complete(self, *, system, messages, tools):
            self.seen_tools = tools
            self.seen_system = system
            return super().complete(system=system, messages=messages, tools=tools)

    llm = RecordingFake(FIXTURES / "natural_close.json")
    run(make_state(), llm=llm, tools=[EchoTool()], system="系统提示词")
    assert llm.seen_system == "系统提示词"
    assert llm.seen_tools == [
        {
            "name": "echo",
            "description": "回显输入文本，测试用",
            "input_schema": EchoTool.input_schema,
        }
    ]
