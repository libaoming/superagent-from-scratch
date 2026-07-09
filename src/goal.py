"""goal 续跑（SPEC #long-task · 目标闭环，Q2=A 拍板）。

long-horizon 的本质：**不是把 loop 改大，而是用 harness 外壳把纯净的 run() 套进目标闭环**。
run_with_goal() 在 run() 收口后用同一个 llm 判「对话证据是否达成 goal」，未达成就注入一条
隐藏续跑消息重进 run——loop 签名一个字不改（C4）。依赖单向朝内：本模块 import loop，loop 不 import 本模块。

两个熔断各管一层（盲区回填）：
- 单次 run 内 turn_count≤max_turns（每续跑重置——否则第二轮直接顶格）；
- 续跑总量 max_continuations 次 + 无进展熔断（连续 2 次续跑无新 assistant 文本即停）。
无进展熔断尤其关键：光有次数上限，模型可能空转到顶；「连续 2 次没产出新文本」才是真「卡住了」。

deer-flow 用独立 evaluator 模型 + 类型化 blocker；教学版同模型简单 YES/NO 判定（F07 out_of_scope）。
"""

from src.loop import run


def _last_assistant_text(state) -> str:
    """末条 assistant 消息的文本块拼接——用于无进展判定与 goal 评估证据。"""
    for msg in reversed(state.messages):
        if msg.get("role") == "assistant" and isinstance(msg.get("content"), list):
            return "".join(b.get("text", "") for b in msg["content"] if b.get("type") == "text")
    return ""


def _goal_met(llm, state, goal: str) -> bool:
    """用同一 llm 判「对话证据是否达成目标」，只认 YES/NO（简单判定，F07 out_of_scope）。"""
    resp = llm.complete(
        system="你是目标验收器：只回 YES 或 NO。判断给定对话是否已达成用户目标。",
        messages=[{"role": "user", "content": f"目标：{goal}\n\n最新进展：{_last_assistant_text(state)}\n\n达成了吗？只回 YES 或 NO。"}],
        tools=[],
    )
    verdict = "".join(b.get("text", "") for b in resp["content"] if b.get("type") == "text")
    return verdict.strip().upper().startswith("YES")


def run_with_goal(state, llm, tools, *, max_continuations: int = 8, **run_kwargs):
    """外壳：反复调纯净 run() 逼近 state.goal，直到达成 / 中断 / 触发任一熔断。

    goal 为空 → 退化为单次 run（无续跑、无评估）。中断（state.interrupt）优先于续跑：
    立即把控制权交回调用方，不替用户续跑（HITL 与 goal 续跑的边界）。
    """
    prev_text = None
    stale = 0
    continuations = 0
    while True:
        state.turn_count = 0  # 单轮熔断每轮复位（续跑总量另由 continuations 管）
        for t in tools:
            reset = getattr(t, "reset", None)  # 拆 D5 埋雷：TaskTool 等有状态工具每轮复位，防跨 run 泄漏
            if callable(reset):
                reset()
        state = run(state, llm, tools, **run_kwargs)

        if state.interrupt is not None:
            return state  # 中断优先：交回调用方，不续跑
        if not state.goal or _goal_met(llm, state, state.goal):
            return state  # 无目标 或 已达成 → 收工
        if continuations >= max_continuations:
            return state  # 熔断①：续跑次数上限

        # 熔断锚在 assistant 文本：若某轮进展全在工具调用里、没吐文本（_last_assistant_text 返回 ""），
        # 连续两轮 ""=="" 会被误判无进展而早停——方向保守（停而非空转烧钱），教学版接受。
        cur = _last_assistant_text(state)
        if cur == prev_text:
            stale += 1
            if stale >= 2:
                return state  # 熔断②：连续 2 次续跑无新文本 = 卡住了
        else:
            stale = 0
        prev_text = cur

        state.messages.append({"role": "user", "content": "[目标未完成] 请继续推进，直到达成目标。"})
        continuations += 1
