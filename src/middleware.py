"""middleware 协议（SPEC #middleware）——缝①，一切横切能力的唯一生长面，C7 起签名冻结。

deer-flow 对照：它的 28 个 middleware（摘要/防御/记忆/预算）全部长在同一套钩子上，
loop 主体零改动——「行为扩展面」与「循环引擎」解耦，就是现代 harness 的真架构。
基类默认 no-op：子类只覆写关心的钩子，单一关切（反模式 3：禁止一件 middleware 管两件事）。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Interrupt:
    """after_model 的中断信号：loop 见到即收口（终止条件 3）。question 由 S5 的调用方消费。"""

    question: str


class Middleware:
    def before_model(self, state) -> None:
        """进模型前就地改 state（注册序执行）。"""

    def after_model(self, state) -> Interrupt | None:
        """模型响应后检查/改 state（逆序执行——先注册者最后看到输出，像栈帧）。"""
        return None

    def wrap_tool_call(self, call_next, tool, args) -> str:
        """洋葱模型包裹工具执行（先注册者最外层）。必须调 call_next，除非有意短路。"""
        return call_next(tool, args)
