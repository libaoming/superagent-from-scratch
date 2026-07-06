"""S1 真实模型 E2E（PRD 验收 4）：ClaudeCLILLM 驱动一次研究任务。

ClaudeCLILLM = LLMClient 协议的第三个实现（前两个：FakeLLM / AnthropicLLM），
用 subprocess 包 `claude -p`（吃订阅额度，无需 ANTHROPIC_API_KEY——2026-07-04 拍板 Q4=B）。
loop / tools / 测试一行不改，第三实现直接插上就跑——这正是接缝质量的验收。

scripts/ 不占 src 行数预算（C1）。用法：uv run python scripts/e2e_s1.py
"""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm import LLMClient  # noqa: E402  （仅类型示意，协议是结构性的）
from src.loop import State, run  # noqa: E402
from src.tools import BashTool, ReadFileTool, WriteFileTool  # noqa: E402

PROMPT_TEMPLATE = """你是一个 agent 循环里的 LLM。根据系统提示与对话历史，决定下一步：调用一个工具，或给出最终答案。

系统提示：{system}

可用工具（JSON Schema）：
{tools}

对话历史（Anthropic 消息格式；tool_result 是此前工具调用的真实输出）：
{messages}

只输出一个 JSON 对象，禁止任何其它文字、解释或 markdown 围栏。形状二选一：
- 调用工具：{{"content": [{{"type": "tool_use", "id": "e1", "name": "<工具名>", "input": {{...}}}}]}}
- 最终答案：{{"content": [{{"type": "text", "text": "<答案>"}}]}}
id 请自造且不重复（e1、e2…）。"""


class ClaudeCLILLM:
    """薄包 claude -p：把 complete() 的入参编排成 prompt，要求模型回严格 JSON。"""

    def __init__(self, timeout_s: int = 300):
        self._timeout_s = timeout_s

    def complete(self, *, system: str, messages: list[dict], tools: list[dict]) -> dict:
        prompt = PROMPT_TEMPLATE.format(
            system=system,
            tools=json.dumps(tools, ensure_ascii=False, indent=1),
            messages=json.dumps(messages, ensure_ascii=False, indent=1),
        )
        proc = subprocess.run(
            ["claude", "-p", "--output-format", "text"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=self._timeout_s,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"claude -p 失败（exit {proc.returncode}）：{proc.stderr[:500]}")
        raw = proc.stdout.strip()
        # 容错：剥 markdown 围栏 / 前后杂文字，取首尾花括号之间
        if "{" in raw:
            raw = raw[raw.index("{"): raw.rindex("}") + 1]
        data = json.loads(raw)
        return {"role": "assistant", "content": data["content"]}


def main() -> int:
    task = (
        "研究 fixtures/workspace 目录里的资料，总结 deer-flow 的 harness 核心架构"
        "由哪几部分构成、各自规模多大。先看目录里有什么，再读文件，最后给出结论。"
    )
    print(f"▶ 任务：{task}\n▶ LLM：ClaudeCLILLM（claude -p）\n")

    state = run(
        State(messages=[{"role": "user", "content": task}]),
        llm=ClaudeCLILLM(),
        tools=[BashTool(), ReadFileTool(), WriteFileTool()],
        system="你是研究助手。用提供的工具完成研究任务，得到足够信息后给出最终结论。",
        max_turns=8,
    )

    # 轨迹回放
    for msg in state.messages:
        content = msg["content"]
        if isinstance(content, str):
            print(f"[user] {content[:120]}")
            continue
        for block in content:
            if block["type"] == "text":
                print(f"[{msg['role']}] {block['text'][:300]}")
            elif block["type"] == "tool_use":
                print(f"[assistant→tool] {block['name']} {json.dumps(block['input'], ensure_ascii=False)[:200]}")
            elif block["type"] == "tool_result":
                print(f"[tool_result] {str(block['content'])[:150].replace(chr(10), ' ⏎ ')}")

    final = state.messages[-1]
    ok = (
        final["role"] == "assistant"
        and isinstance(final["content"], list)
        and final["content"][-1]["type"] == "text"
        and state.turn_count >= 1  # 至少真调过一轮工具才算研究任务
    )
    print(f"\n{'✅ E2E 通过' if ok else '❌ E2E 失败'}：turn_count={state.turn_count}，"
          f"消息数={len(state.messages)}，自然收口={'是' if ok else '否'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
