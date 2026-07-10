"""断点持久化（SPEC #checkpointer · S7）——per-step durability，进程可死、任务不死。

核心 aha：checkpoint = State 的**全量快照按轮落盘**——「保存现场」从内存（S5 的简化）
升级到磁盘。真 checkpointer 语义是 **per-step durability**（每轮都存，崩溃只丢半轮），
不是 save-on-close（只在收口存 = 中途崩溃白跑整个 run）。

挂载点（M1 拍板）：与 S6 成对的决策——**节奏定挂载**。记忆读写是 per-run（协议没有
per-run 钩子）→ 外壳；checkpoint 的存是 per-turn（协议恰好有 before_model）→ 缝①。
这是缝①第一次收「持久化」类住户，C7 协议零改动、run() 零改动（C4）。
deer-flow 对照：它 0% 内核 + 100% 胶水（存取恢复全在 LangGraph 官方 saver 库里，
自己 458 行全是工厂/单例）——本模块手写的正是库包办的三件事：存什么/何时存/怎么恢复。
"""

import json
from pathlib import Path

from src.loop import State, run
from src.middleware import Interrupt, Middleware


def save_state(path, state: State) -> None:
    """State 五字段全量 JSON 落盘（单文件 latest-only，教学版砍 checkpoint_id 谱系/原子写）。"""
    data = {
        "messages": state.messages,
        "turn_count": state.turn_count,
        "todos": state.todos,
        "goal": state.goal,
        "interrupt": {"question": state.interrupt.question} if state.interrupt else None,
    }
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_state(path) -> State:
    """重建 State + 悬空 tool_use 兜底（deer-flow 用 205 行 middleware 换来的教训，这里 ~15 行）。

    悬空有两种，只兜第一种：**interrupt 空的悬空**——末条 assistant 带 tool_use 而无配对
    tool_result，下轮请求直接 API 400（S2 摘要配对坑的姐妹篇），补合成 [interrupted]；
    **待答悬空**（interrupt 非空 = HITL 中断收口）——答案归调用方补（S5 恢复流程），不许抢填。
    触发面说实：本 checkpointer 自产档不会走到第一种（before_model 快照永远轮间完整、
    终存悬空必伴 interrupt）——它防的是外源/手造档与「第三方 middleware 中断却不 stash」。
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    itr = data.get("interrupt")
    state = State(
        messages=data["messages"],
        turn_count=data.get("turn_count", 0),
        interrupt=Interrupt(itr["question"]) if itr else None,
        todos=data.get("todos", []),
        goal=data.get("goal", ""),
    )
    if state.interrupt is None and state.messages:
        last = state.messages[-1]
        if last.get("role") == "assistant" and isinstance(last.get("content"), list):
            dangling = [b for b in last["content"] if b.get("type") == "tool_use"]
            if dangling:
                state.messages.append({"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": b["id"], "content": "[interrupted]"}
                    for b in dangling
                ]})
    return state


class Checkpointer(Middleware):
    """缝①住户：before_model 每轮落盘——此刻上一轮 tool_result 已 append，State 处于轮间完整态。

    同步写是语义要求不是性能妥协：存完才进模型，异步写则崩溃瞬间最近一轮可能没落盘，
    「只丢半轮」的 durability 承诺就破了（对照 S6：旁路防的是秒级 LLM 调用，这里是毫秒级本地写）。
    注册序语义：外壳把本件放列表头——快照是本轮其它 middleware（Todo 重注/摘要）改写前的
    轮间态；无害（改写幂等，恢复后重跑即得），但语义要说清（对抗审查 2026-07-10）。
    """

    def __init__(self, path):
        self._path = path

    def before_model(self, state) -> None:
        save_state(self._path, state)


def run_with_checkpoint(state: State, llm, tools, *, path, middlewares=(), **run_kwargs) -> State:
    """harness 外壳：middleware 每轮存 + 收口终存，两件套缺一不可。

    只挂 middleware 会丢结尾（自然收口后没有下一轮 before_model，最终回复/interrupt 不落盘）；
    只靠外壳收口存 = save-on-close（中途崩溃白跑）。恢复与 S5 同构：load_state → 补答案/清
    interrupt → 重进同一个 run()。
    """
    state = run(state, llm, tools, middlewares=[Checkpointer(path), *middlewares], **run_kwargs)
    save_state(path, state)  # 收口终存：最终 assistant 回复 + interrupt 字段只有这里能兜住
    return state
