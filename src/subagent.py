"""task 工具 + subagent 委派（SPEC #subagent）——缝③进阶：委派本身也是一个工具。

教学要点：subagent 不是新机制，是 run() 的递归调用 + 全新 State（上下文隔离）。
复用三样现成件：task 是工具（缝③）、跑同一个 run()、结论走同一条 tool_result 回填路。
防无限递归：子工具集 = 全部工具 − task（单层委派，物理摘掉 task）。
Deviation D5（用户已接受）：max_concurrent 实为 **per-instance 生命周期配额**——
`_delegated` 只增不减，无 run 边界复位（loop 已 C4 冻结，无处复位）。单次 run 内它等价于
per-run（每个顶层 run 通常新建 TaskTool）；但同一实例跨多次 run 复用时配额会累计泄漏。
⚠️ S5 `run_with_goal()` 复用同一 tools 列表反复调 run——届时须每 run 重建 TaskTool
或复位 `_delegated`。此行为由 test_delegation_quota_is_per_instance_lifetime 钉住。
教学点（配额 + 超限错误分流 + 防委派炸弹）不受影响。
"""

from src.loop import State, run


def _final_text(state: State) -> str:
    """subagent 的最终结论 = 末条消息的文本块拼接（自然收口时末条是 assistant 文本）。"""
    blocks = state.messages[-1].get("content")
    if isinstance(blocks, list):
        text = "".join(b["text"] for b in blocks if b.get("type") == "text")
        if text:
            return text
    return "[subagent 无文本结论]"


class TaskTool:
    name = "task"
    description = (
        "把一个独立子任务委派给 subagent：它在全新上下文里跑完，只回最终结论。"
        "适合读长文档、多步搜索这类吃上下文的脏活——中间过程不进主对话。"
    )
    input_schema = {
        "type": "object",
        "properties": {
            "description": {"type": "string", "description": "子任务一句话描述"},
            "prompt": {"type": "string", "description": "交给 subagent 的完整指令（它看不到主对话）"},
        },
        "required": ["description", "prompt"],
    }

    def __init__(self, llm, tools, *, middlewares=(), max_concurrent: int = 3, max_turns: int = 40):
        self._llm = llm
        # 单层委派：物理摘掉 task。防递归锚在 name=="task" 约定——教学版只有 general-purpose
        # 一种 subagent、无类型注册表（F05 out_of_scope），故不考虑「别名委派工具」的越界场景。
        self._tools = [t for t in tools if t.name != "task"]
        self._middlewares = middlewares
        self._max_concurrent = max_concurrent
        self._max_turns = max_turns
        self._delegated = 0

    def reset(self) -> None:
        """复位委派计数——拆 D5 埋雷。run_with_goal 每轮 run 前调用，使 per-instance 配额
        在续跑边界归零、不跨 run 泄漏（否则续跑第 max_concurrent+1 次委派起被误拒）。"""
        self._delegated = 0

    def run(self, *, description: str, prompt: str) -> str:
        # description 只供模型自我说明任务，不参与执行；prompt 才是 subagent 的首条 user 消息
        if self._delegated >= self._max_concurrent:
            return f"[task error] 委派配额已用尽（上限 {self._max_concurrent}）：请合并子任务或分批委派。"
        self._delegated += 1
        sub_state = State(messages=[{"role": "user", "content": prompt}])
        final = run(
            sub_state,
            self._llm,
            self._tools,
            middlewares=self._middlewares,
            max_turns=self._max_turns,
        )
        return _final_text(final)
