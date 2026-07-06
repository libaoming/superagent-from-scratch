"""S1 / F02_real_tools：bash / read_file / write_file 三个真实工具。

测试纪律（SPEC C3 / 反模式 2）：工具真实执行（真 subprocess、真文件系统），不 mock；
LLM 侧唯一接缝仍是 FakeLLM（集成测试用 research_task.json 录制序列）。
契约来源 SPEC #tools：run() 永远返回 str；bash 超时/非零退出码作为文本结果返回
（模型需要看到 stderr 学会自纠）；read_file 带行号同 cat -n；其余异常往外抛，middleware 接。
"""

from pathlib import Path

import pytest

from src.llm import FakeLLM
from src.loop import State, run
from src.tools import BashTool, ReadFileTool, WriteFileTool

FIXTURES = Path(__file__).parent.parent / "fixtures" / "fake_llm"


# ---------- 工具 schema 契约（Tool 协议形状，C7 冻结的缝③） ----------


def test_tool_protocol_shape():
    for tool, expected_name, required in [
        (BashTool(), "bash", ["command"]),
        (ReadFileTool(), "read_file", ["path"]),
        (WriteFileTool(), "write_file", ["path", "content"]),
    ]:
        assert tool.name == expected_name
        assert tool.description  # 非空，给模型看的
        schema = tool.input_schema
        assert schema["type"] == "object"
        assert schema["required"] == required
        for prop in required:
            assert prop in schema["properties"]


# ---------- bash ----------


def test_bash_returns_stdout():
    out = BashTool().run(command="echo hello")
    assert isinstance(out, str)
    assert "hello" in out


def test_bash_nonzero_exit_returns_text_with_stderr():
    """非零退出码不抛异常——exit code 与 stderr 都要回给模型，它靠这个自纠。"""
    out = BashTool().run(command="ls /no/such/path/anywhere")
    assert isinstance(out, str)
    assert "exit code" in out
    assert "No such file" in out  # stderr 内容可见


def test_bash_timeout_returns_text():
    """超时同样作为文本结果返回，不抛异常（默认 60s，测试用短闸）。"""
    out = BashTool(timeout_s=1).run(command="sleep 5")
    assert isinstance(out, str)
    assert "timed out" in out
    assert "1" in out  # 超时秒数可见


def test_bash_default_timeout_is_60s():
    assert BashTool().timeout_s == 60  # SPEC #tools 明文契约


# ---------- read_file ----------


def test_read_file_numbers_lines_like_cat_n(tmp_path):
    f = tmp_path / "sample.txt"
    f.write_text("alpha\nbeta\n")
    out = ReadFileTool().run(path=str(f))
    assert out == "     1\talpha\n     2\tbeta\n"  # cat -n：6 宽右对齐 + tab


def test_read_file_missing_raises():
    """文件不存在往外抛——错误恢复是 S2 ToolErrorHandling 的事，工具不兜。"""
    with pytest.raises(FileNotFoundError):
        ReadFileTool().run(path="/no/such/file.md")


# ---------- write_file ----------


def test_write_file_writes_and_confirms(tmp_path):
    target = tmp_path / "out.md"
    result = WriteFileTool().run(path=str(target), content="# hi\n")
    assert target.read_text() == "# hi\n"  # 真的落盘
    assert isinstance(result, str)
    assert str(target) in result  # 确认文本含路径，模型可引用


def test_write_file_overwrites_existing(tmp_path):
    """SPEC #tools「整文件覆盖」语义：已有内容被完整替换，不是追加。"""
    target = tmp_path / "out.md"
    target.write_text("旧内容\n")
    WriteFileTool().run(path=str(target), content="新内容\n")
    assert target.read_text() == "新内容\n"


# ---------- 集成：FakeLLM × 真工具跑通 S1 canonical 研究任务 ----------


def test_research_task_end_to_end():
    """research_task.json：bash 列目录 → read_file 读资料 → 最终结论。
    工具真实执行——断言的 tool_result 内容来自真实 ls 输出与真实文件。"""
    state = run(
        State(messages=[{"role": "user", "content": "研究 deer-flow 的 harness 架构"}]),
        llm=FakeLLM(FIXTURES / "research_task.json"),
        tools=[BashTool(), ReadFileTool(), WriteFileTool()],
        system="你是研究助手",
    )

    # 轮 1：bash ls fixtures/workspace → 真实输出含 data.md
    ls_result = state.messages[2]["content"][0]
    assert ls_result["type"] == "tool_result"
    assert ls_result["tool_use_id"] == "r1"
    assert "data.md" in ls_result["content"]

    # 轮 2：read_file → 真实文件内容 + cat -n 行号
    read_result = state.messages[4]["content"][0]
    assert read_result["tool_use_id"] == "r2"
    assert read_result["content"].startswith("     1\t")
    assert "lead agent" in read_result["content"]

    # 收口：assistant 纯文本结论
    final = state.messages[-1]
    assert final["role"] == "assistant"
    assert final["content"][0]["type"] == "text"
    assert "结论" in final["content"][0]["text"]
    assert state.turn_count == 2
