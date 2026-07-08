"""SPEC 关键约束的机器闸门（S1 对抗审查红 2 落 C1；S2 对抗审查黄 4 补齐 C7/C4）。

C1 行数预算原文「检验方式：CI 脚本 wc -l 断言」——本项目无 CI，pytest 就是每次必跑的闸门。
C7 三协议（Middleware / LLMClient / Tool）签名 S2 起冻结——Middleware 钉在
test_s2_middleware.py，另两个钉在这里；C4 补钉 run() 完整参数表。
兼容性承诺写成测试不写成文档：想改协议先让这里红，变更被迫显式化。
"""

import inspect
from pathlib import Path

from src.llm import LLMClient
from src.loop import run
from src.tools import BashTool, ReadFileTool, WriteFileTool

SRC = Path(__file__).parent.parent / "src"


def test_c1_src_total_line_budget():
    total = sum(len(f.read_text().splitlines()) for f in SRC.rglob("*.py"))
    assert total <= 1500, f"C1 违约：src/ 共 {total} 行 > 1500——在复刻产品功能而非教学核心，砍"


def test_c7_llmclient_signature_frozen():
    assert list(inspect.signature(LLMClient.complete).parameters) == [
        "self", "system", "messages", "tools",
    ]


def test_c7_tool_protocol_shape_frozen():
    """Tool 协议是鸭子类型无基类，冻结的是形状：name/description/input_schema/run 四件套。"""
    for tool_cls in (BashTool, ReadFileTool, WriteFileTool):
        for attr in ("name", "description", "input_schema", "run"):
            assert hasattr(tool_cls, attr), f"{tool_cls.__name__} 缺 {attr}"
        assert isinstance(tool_cls.name, str) and isinstance(tool_cls.input_schema, dict)


def test_c4_run_signature_frozen():
    assert list(inspect.signature(run).parameters) == [
        "state", "llm", "tools", "middlewares", "system", "max_turns",
    ]
