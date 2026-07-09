"""ask_clarification 工具 + Clarification middleware（SPEC #long-task · HITL）。

human-in-the-loop 的全部机制就一句话：**中断 = 保存现场的正常收口，恢复 = 带答案重进循环，没有魔法。**
- 工具本身不执行任何东西（run 只兜底回显）；真正的拦截在 middleware。
- Clarification.after_model 看到 ask_clarification 的 tool_use → 把问题 stash 进 state.interrupt
  并返回 Interrupt → loop 收口（终止条件 3，**先于工具执行**，见 loop.py 注释）。
- 调用方读 state.interrupt.question 问用户，拿到答案后补一条 tool_result 进 messages、清 interrupt、重进 run。

返回通道为什么走 state.interrupt：loop 见 after_model 非 None 只 `return state`、丢弃返回值（C4 冻结
签名不能改成返回 Interrupt），故问题必须挂到 state 上带出去。

教学版简化（F08 out_of_scope）：假设 ask_clarification 单独出现（模型缺信息时通常如此）；不做多问题
队列，也不把断点序列化到磁盘——「保存现场」就是 state 本身，恢复就是接着 run 同一个 state。
"""

from src.middleware import Interrupt, Middleware


class AskClarification:
    name = "ask_clarification"
    description = (
        "当任务缺少关键信息、无法继续时，用它向用户提问。"
        "调用会中断执行、把问题交还给用户；拿到回答后自动继续。"
    )
    input_schema = {
        "type": "object",
        "properties": {"question": {"type": "string", "description": "要问用户的问题"}},
        "required": ["question"],
    }

    def run(self, *, question: str) -> str:
        # 正常流程里不会被调到——middleware 在工具执行前就中断了 loop。
        # 仅作兜底：万一没挂 Clarification middleware，至少把问题回显、不静默吞掉。
        return f"[未处理的澄清请求] {question}"


class Clarification(Middleware):
    def after_model(self, state) -> Interrupt | None:
        resp = state.messages[-1]
        for block in resp.get("content", []):
            if block.get("type") == "tool_use" and block["name"] == AskClarification.name:
                state.interrupt = Interrupt(block["input"]["question"])  # stash = 返回通道
                return state.interrupt  # 非 None → loop 收口（先于工具执行）
        return None
