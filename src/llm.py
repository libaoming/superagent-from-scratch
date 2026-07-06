"""LLM 客户端 —— 本项目唯一的测试接缝（SPEC #llm）。

协议刻意只有 complete() 一个方法：接缝越窄，测试越难作弊。
deer-flow 对照：它用 LangChain 的 ChatModel 抽象换多 provider 能力，
我们 out of scope 了多模型，直接采用 Anthropic 原生消息形状（SPEC 数据模型决策）。
"""

import json
from pathlib import Path
from typing import Protocol


class LLMClient(Protocol):
    def complete(self, *, system: str, messages: list[dict], tools: list[dict]) -> dict:
        """返回一条 assistant message（原生形状）。无网络错误处理责任——那是 middleware 的事。"""
        ...


class FakeLLM:
    """读 fixture 按序弹出（fixtures/fake_llm/*.json）。

    录制 = 全局调用序：所有经由本实例的调用（含未来切片的摘要/goal 判定/subagent 调用）
    消耗同一 responses 序列。弹尽再调 = fixture 覆盖不足，属测试 bug，直接抛错。
    """

    def __init__(self, fixture_path: str | Path):
        data = json.loads(Path(fixture_path).read_text())
        self._responses: list[dict] = list(data["responses"])
        self._fixture = str(fixture_path)

    def complete(self, *, system: str, messages: list[dict], tools: list[dict]) -> dict:
        if not self._responses:
            raise RuntimeError(
                f"FakeLLM fixture 已弹尽：{self._fixture}（fixture 覆盖不足，补录制而不是 mock）"
            )
        resp = self._responses.pop(0)
        return {"role": "assistant", "content": resp["content"]}


class AnthropicLLM:
    """薄包 Anthropic SDK。不设 thinking/采样参数——保持 SPEC 三种 ContentBlock 的教学数据模型。"""

    def __init__(self, model: str = "claude-opus-4-8", max_tokens: int = 16000):
        import anthropic  # 惰性导入：离线测试（C3）不依赖 SDK 可用

        self._client = anthropic.Anthropic()
        self._model = model
        self._max_tokens = max_tokens

    def complete(self, *, system: str, messages: list[dict], tools: list[dict]) -> dict:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            messages=messages,
            tools=tools,
        )
        content = []
        for block in resp.content:
            if block.type == "text":
                content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                content.append(
                    {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
                )
        return {"role": "assistant", "content": content}
