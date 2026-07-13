"""内置三件 middleware（SPEC #middleware 内置三件）——缝①上的第一批住户。

每件单一关切（SPEC 反模式 3）：Budget 只管截断、ErrorHandling 只管接异常、
Summarization 只管压历史；loop 与工具零改动（C4）。
"""

from src.middlewares.clarification import AskClarification, Clarification
from src.middlewares.loop_detection import LoopDetection
from src.middlewares.summarization import Summarization
from src.middlewares.todo import TodoMiddleware, WriteTodos
from src.middlewares.token_budget import TokenBudget
from src.middlewares.tool_error_handling import ToolErrorHandling
from src.middlewares.tool_output_budget import ToolOutputBudget

__all__ = [
    "AskClarification",
    "Clarification",
    "LoopDetection",
    "Summarization",
    "TodoMiddleware",
    "TokenBudget",
    "ToolErrorHandling",
    "ToolOutputBudget",
    "WriteTodos",
]
