"""三个真实工具：bash / read_file / write_file（SPEC #tools）。

Tool 协议（缝③，C7 冻结）：name / description / input_schema / run(**kwargs) -> str。
异常处理分工：bash 的超时与非零退出码是「模型该看到并自纠的正常结果」，作为文本返回；
其余异常（文件不存在等）往外抛——错误恢复是 middleware 的单一关切（S2 ToolErrorHandling），工具不兜。
deer-flow 对照：它的工具走虚拟路径映射 + Docker sandbox（多租户隔离）；教学版裸执行，
升级路径在缝③——run() 内换容器执行，name/schema/契约全不动。
"""

import subprocess
from pathlib import Path


class BashTool:
    name = "bash"
    description = "在仓库根目录执行 shell 命令。查看目录、搜索文件、运行脚本时用。"
    input_schema = {
        "type": "object",
        "properties": {"command": {"type": "string", "description": "要执行的 shell 命令"}},
        "required": ["command"],
    }

    def __init__(self, timeout_s: int = 60):
        self.timeout_s = timeout_s

    def run(self, *, command: str) -> str:
        try:
            proc = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=self.timeout_s
            )
        except subprocess.TimeoutExpired:
            return f"command timed out after {self.timeout_s}s: {command}"
        if proc.returncode != 0:
            return (
                f"exit code {proc.returncode}\n"
                f"stdout:\n{proc.stdout}\n"
                f"stderr:\n{proc.stderr}"
            )
        return proc.stdout


class ReadFileTool:
    name = "read_file"
    description = "读取文件内容，带行号（同 cat -n）。查看资料或代码时用。"
    input_schema = {
        "type": "object",
        "properties": {"path": {"type": "string", "description": "文件路径"}},
        "required": ["path"],
    }

    def run(self, *, path: str) -> str:
        text = Path(path).read_text()
        return "".join(
            f"{i:>6}\t{line}\n" for i, line in enumerate(text.splitlines(), start=1)
        )


class WriteFileTool:
    name = "write_file"
    description = "把内容写入文件（整文件覆盖）。产出结论、保存结果时用。"
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "目标文件路径"},
            "content": {"type": "string", "description": "要写入的完整内容"},
        },
        "required": ["path", "content"],
    }

    def run(self, *, path: str, content: str) -> str:
        Path(path).write_text(content)
        return f"已写入 {path}（{len(content)} 字符）"
