"""Summarization——messages 超阈值时保留近 K 条，其余交 llm 压缩为一条摘要消息（before_model）。

llm 走构造注入（Q1=A 拍板）：谁需要谁持有，协议签名不动。
简单策略（feature out_of_scope）：不做 deer-flow 的 durable context 通道。
切点纪律（S2 对抗审查红色发现）：tool_result 不许与它的 tool_use 拆开——
这是 loop.py 回填处同款的 Anthropic API 硬约束，切点落在配对中间时向前让位。
⚠️ 测试录制注意「录制=全局调用序」：压缩调用与主循环调用消耗同一 FakeLLM responses 序列。
"""

from src.middleware import Middleware


def _starts_with_tool_result(msg: dict) -> bool:
    blocks = msg.get("content")
    return (
        msg["role"] == "user"
        and isinstance(blocks, list)
        and any(b.get("type") == "tool_result" for b in blocks)
    )


class Summarization(Middleware):
    def __init__(self, llm, max_messages: int = 20, keep_last: int = 4):
        assert keep_last < max_messages, "keep_last 必须小于 max_messages（否则每轮净增摘要消息，越压越长）"
        self._llm = llm
        self.max_messages = max_messages
        self.keep_last = keep_last

    def before_model(self, state) -> None:
        if len(state.messages) <= self.max_messages:
            return
        old, recent = state.messages[: -self.keep_last], state.messages[-self.keep_last :]
        # 切点不许落在 tool_use/tool_result 配对中间：把配对的 assistant(tool_use) 挪回 recent
        while old and _starts_with_tool_result(recent[0]):
            recent.insert(0, old.pop())
        if not old:
            return  # 让位后无可压缩内容，本轮放行
        resp = self._llm.complete(
            system="你是对话压缩器：把给你的历史压成一段摘要，保留关键事实、决定与结论。",
            messages=[{"role": "user", "content": "压缩以下对话历史：\n" + "\n".join(map(str, old))}],
            tools=[],
        )
        summary = "".join(b["text"] for b in resp["content"] if b["type"] == "text")
        state.messages[:] = [{"role": "user", "content": f"[早前对话摘要] {summary}"}, *recent]
