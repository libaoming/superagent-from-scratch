"""内置三件 middleware（SPEC #middleware 内置三件）——缝①上的第一批住户。

每件单一关切（SPEC 反模式 3）：Budget 只管截断、ErrorHandling 只管接异常、
Summarization 只管压历史；loop 与工具零改动（C4）。
"""

from src.middlewares.summarization import Summarization
from src.middlewares.tool_error_handling import ToolErrorHandling
from src.middlewares.tool_output_budget import ToolOutputBudget

__all__ = ["Summarization", "ToolErrorHandling", "ToolOutputBudget"]
