"""ToolOutputBudget——工具输出超预算即截断加标注（wrap_tool_call，包副作用时机）。

deer-flow 对照：它有 TokenBudget/输出限额一族；教学版只留字符预算一件（SPEC #product-vs-teaching）。
截断标注要让模型看得懂发生了什么（原长/保留量），它下轮可自行决定换策略（如分页读取）。
"""

from src.middleware import Middleware


class ToolOutputBudget(Middleware):
    def __init__(self, max_chars: int = 4000):
        self.max_chars = max_chars

    def wrap_tool_call(self, call_next, tool, args) -> str:
        result = call_next(tool, args)
        if len(result) <= self.max_chars:
            return result
        return (
            result[: self.max_chars]
            + f"\n[输出超预算已截断：原 {len(result)} 字符，保留前 {self.max_chars}]"
        )
