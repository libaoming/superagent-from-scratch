"""S2 / F03_middleware_protocol：三钩子协议 + 挂载进 loop。

测试纪律不变（SPEC C3 / 反模式 2）：LLM 只从 FakeLLM 接缝进（复用 S1 fixture），
middleware 用测试内极小实现真执行，不 patch loop 内部。
顺序语义（SPEC #middleware）：before 注册序 / after 逆序 / wrap 洋葱（先注册者最外层）——
像栈帧：先注册的最先看到输入、最后看到输出。
"""

import inspect
from pathlib import Path

from src.llm import FakeLLM
from src.loop import State, run
from src.middleware import Interrupt, Middleware

FIXTURES = Path(__file__).parent.parent / "fixtures" / "fake_llm"


class EchoTool:
    name = "echo"
    description = "回显输入文本，测试用"
    input_schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    def run(self, *, text: str) -> str:
        return f"echo: {text}"


class Probe(Middleware):
    """记录钩子触发顺序的探针——只观察不改动。"""

    def __init__(self, tag: str, log: list):
        self._tag, self._log = tag, log

    def before_model(self, state) -> None:
        self._log.append(f"{self._tag}.before")

    def after_model(self, state):
        self._log.append(f"{self._tag}.after")
        return None

    def wrap_tool_call(self, call_next, tool, args) -> str:
        self._log.append(f"{self._tag}.wrap_in")
        result = call_next(tool, args)
        self._log.append(f"{self._tag}.wrap_out")
        return result


def make_state() -> State:
    return State(messages=[{"role": "user", "content": "做点事"}])


# ---------- 协议基类：默认全 no-op，子类只覆写关心的钩子 ----------


def test_middleware_defaults_are_noops():
    mw = Middleware()
    state = make_state()
    assert mw.before_model(state) is None
    assert mw.after_model(state) is None
    # wrap 默认直通 call_next
    called = []
    result = mw.wrap_tool_call(lambda tool, args: called.append(1) or "ok", EchoTool(), {})
    assert result == "ok" and called == [1]


def test_c7_protocol_signatures_frozen():
    """C7：Middleware 协议签名断言（S2 起冻结，变更须走 CHANGELOG）。"""
    assert list(inspect.signature(Middleware.before_model).parameters) == ["self", "state"]
    assert list(inspect.signature(Middleware.after_model).parameters) == ["self", "state"]
    assert list(inspect.signature(Middleware.wrap_tool_call).parameters) == [
        "self", "call_next", "tool", "args",
    ]


# ---------- 顺序语义 ----------


def test_before_registration_order_after_reverse_order():
    log: list = []
    run(
        make_state(),
        llm=FakeLLM(FIXTURES / "natural_close.json"),
        tools=[EchoTool()],
        middlewares=[Probe("a", log), Probe("b", log)],
    )
    assert log == ["a.before", "b.before", "b.after", "a.after"]  # 栈帧对称


def test_wrap_onion_first_registered_outermost():
    log: list = []
    run(
        make_state(),
        llm=FakeLLM(FIXTURES / "echo_roundtrip.json"),
        tools=[EchoTool()],
        middlewares=[Probe("a", log), Probe("b", log)],
    )
    wraps = [e for e in log if ".wrap" in e]
    # 两轮工具调用，每轮：a 在最外层包 b
    assert wraps == ["a.wrap_in", "b.wrap_in", "b.wrap_out", "a.wrap_out"] * 2


# ---------- wrap 有真实力量：可改写工具结果 ----------


def test_wrap_can_transform_tool_result():
    class Tagger(Middleware):
        def wrap_tool_call(self, call_next, tool, args) -> str:
            return f"[tagged] {call_next(tool, args)}"

    state = run(
        make_state(),
        llm=FakeLLM(FIXTURES / "echo_roundtrip.json"),
        tools=[EchoTool()],
        middlewares=[Tagger()],
    )
    assert state.messages[2]["content"][0]["content"] == "[tagged] echo: hello"


# ---------- 终止条件 3：after_model 返回 Interrupt → 立即收口 ----------


def test_after_model_interrupt_closes_loop():
    class Halter(Middleware):
        def after_model(self, state):
            return Interrupt(question="需要用户拍板")

    llm = FakeLLM(FIXTURES / "echo_roundtrip.json")
    state = run(
        make_state(),
        llm=llm,
        tools=[EchoTool()],
        middlewares=[Halter()],
    )
    # 首响应是 tool_use，但中断先于工具执行：无 tool_result，模型只被调一次
    assert len(state.messages) == 2  # user + assistant(tool_use)
    assert state.turn_count == 0
    # fixture 还剩一条未弹出 = 循环没有再进模型
    llm.complete(system="", messages=[], tools=[])  # 不抛错，证明剩余 1 条


# ---------- C4 回归：不传 middlewares，S1 行为原样 ----------


def test_run_without_middlewares_is_s1_behavior():
    state = run(
        make_state(),
        llm=FakeLLM(FIXTURES / "echo_roundtrip.json"),
        tools=[EchoTool()],
    )
    assert state.turn_count == 2
    assert state.messages[-1]["content"][0]["type"] == "text"
