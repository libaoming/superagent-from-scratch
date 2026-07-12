"""S8 deferred tools（SPEC #deferred-tools · F11）——能力层按需注入。

五动作各有断言：露（system 纯名字清单）/ 搜（select: + 关键词，max 5）/
晋升（双通道：当轮 tool_result 给 schema JSON + state.promoted 记名）/
藏（loop 每轮按 promoted 过滤 schema 提交，tool_map 仍持全部）/
拦（缝① DeferredGuard 回教学式 error 教自救）。
观察「每轮提交了哪些 schema」走唯一接缝 LLMClient（SpyLLM 包装 FakeLLM），不 patch loop 内部（反模式 2）。
"""

import json
from pathlib import Path

from src.checkpoint import load_state, save_state
from src.deferred import DeferredGuard, ToolSearchTool, deferred_system_block
from src.llm import FakeLLM
from src.loop import State, run

FIXTURES = Path(__file__).parent.parent / "fixtures" / "fake_llm"


class SpyLLM:
    """接缝处记录每轮提交的 tools 名单——验证「藏」只能在这里看，别处都是 patch 内部。"""

    def __init__(self, inner):
        self._inner = inner
        self.tools_per_call: list[list[str]] = []

    def complete(self, *, system: str, messages: list[dict], tools: list[dict]) -> dict:
        self.tools_per_call.append([t["name"] for t in tools])
        return self._inner.complete(system=system, messages=messages, tools=tools)


class SendEmailTool:
    name = "send_email"
    description = "发送邮件给指定收件人"
    input_schema = {
        "type": "object",
        "properties": {"to": {"type": "string"}, "subject": {"type": "string"}},
        "required": ["to"],
    }
    deferred = True

    def __init__(self):
        self.calls: list[dict] = []

    def run(self, **kwargs) -> str:
        self.calls.append(kwargs)
        return "sent"


class EchoTool:
    name = "echo"
    description = "回显文本"
    input_schema = {"type": "object", "properties": {"text": {"type": "string"}}}

    def run(self, *, text: str = "") -> str:
        return text


def _make_run(fixture: str):
    """标准装配：echo 常驻 + send_email deferred + tool_search 元工具 + guard。"""
    state = State(messages=[{"role": "user", "content": "给 bob 发封邮件"}])
    email = SendEmailTool()
    tools = [EchoTool(), email]
    catalog = [*tools, ToolSearchTool(tools, state)]
    llm = SpyLLM(FakeLLM(f"{FIXTURES}/{fixture}"))
    out = run(state, llm, catalog, middlewares=[DeferredGuard(state)],
              system="test" + deferred_system_block(tools))
    return out, llm, email


def test_deferred_hidden_until_promoted_then_visible():
    """藏+晋升通道②：第 1 轮提交不含 deferred schema；tool_search 后下轮包含且真执行。"""
    state, llm, email = _make_run("deferred_tools_flow.json")
    assert "send_email" not in llm.tools_per_call[0]  # 未晋升：只见名字不见 schema
    assert "tool_search" in llm.tools_per_call[0]  # 元工具自身常驻绑定
    assert "echo" in llm.tools_per_call[0]  # 非 deferred 工具不受影响
    assert "send_email" in llm.tools_per_call[1]  # 晋升后下轮放行
    assert state.promoted == {"send_email"}
    assert email.calls == [{"to": "bob@example.com", "subject": "hi"}]  # 真执行了


def test_promotion_returns_schema_json_same_turn():
    """晋升通道①：tool_search 的 tool_result 当轮就给完整 schema JSON（当轮可读，能规划参数）。"""
    state, _, _ = _make_run("deferred_tools_flow.json")
    result_msg = state.messages[2]  # user 消息：tool_search 的 tool_result
    block = result_msg["content"][0]
    assert block["tool_use_id"] == "s1"
    schemas = json.loads(block["content"])
    assert schemas[0]["name"] == "send_email"
    assert schemas[0]["input_schema"]["required"] == ["to"]


def test_guard_blocks_unpromoted_call_and_model_self_rescues():
    """拦：未晋升直调被缝① guard 拦下（不真执行）、error 文本教调 tool_search；关键词搜索命中 description。"""
    state, _, email = _make_run("deferred_guard_block.json")
    blocked = state.messages[2]["content"][0]["content"]  # 第 1 轮 tool_result
    assert "tool_search" in blocked  # 教学式 error：教自救，不是崩溃
    assert email.calls == [{"to": "bob@example.com", "subject": "hi"}]  # 只有晋升后那次真执行
    assert state.promoted == {"send_email"}  # 关键词「邮件」匹配 description 完成晋升
    assert state.messages[-1]["content"][0]["text"].startswith("补救完成")


def test_tool_search_select_keyword_and_cap():
    """搜：select: 精确取多名 / 关键词匹配 name+description / 最多回 5 个 / 未命中回提示。"""
    state = State(messages=[])

    class T:
        input_schema = {"type": "object", "properties": {}}
        deferred = True

        def __init__(self, name, description):
            self.name, self.description = name, description

    catalog = [T(f"tool_{i}", "批量处理数据") for i in range(7)] + [T("send_email", "发送邮件")]
    ts = ToolSearchTool(catalog, state)
    hits = json.loads(ts.run(query="select:send_email,tool_0"))
    assert {s["name"] for s in hits} == {"send_email", "tool_0"}
    assert len(json.loads(ts.run(query="数据"))) == 5  # 7 个命中截到 max 5
    assert "未找到" in ts.run(query="不存在的能力")
    promoted_before = set(state.promoted)
    assert "为空" in ts.run(query="   ")  # 空 query 回提示，不静默群晋升（对抗审查黄2）
    assert state.promoted == promoted_before


def test_system_block_lists_names_only():
    """露：system 尾部清单只含 deferred 工具的纯名字——description 藏着（可被搜索命中但不占常驻）。"""
    block = deferred_system_block([EchoTool(), SendEmailTool()])
    assert "send_email" in block
    assert "echo" not in block  # 非 deferred 不进名单（它有完整 schema 在绑定里）
    assert "发送邮件" not in block  # 纯名字：description 不露


def test_promoted_survives_checkpoint_roundtrip(tmp_path):
    """S7 联动账：promoted 进 save_state 字段表（sorted list ⇄ set），恢复后晋升不丢失。"""
    path = tmp_path / "ckpt.json"
    state = State(messages=[{"role": "user", "content": "hi"}], promoted={"send_email", "bash2"})
    save_state(path, state)
    on_disk = json.loads(path.read_text())
    assert on_disk["promoted"] == ["bash2", "send_email"]  # sorted list：JSON 可序列化 + diff 稳定
    restored = load_state(path)
    assert restored.promoted == {"send_email", "bash2"}
    assert isinstance(restored.promoted, set)
