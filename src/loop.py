"""agent loop 核心：messages→LLM→tool_calls→执行→append→再入模型（SPEC #loop）。

deer-flow 对照：它的 lead agent 循环藏在 LangChain create_agent 黑盒里（556 行外围）；
看见这个循环本身，就是本项目存在的理由。
终止条件穷举（只有三种）：自然收口 / turn 熔断 / 中断信号（S2 挂载，产生者 S5 才有）。
S2 起本模块公共签名冻结（C4）：middleware 加能力不再改 loop。
"""

from dataclasses import dataclass

from src.llm import LLMClient


@dataclass
class State:
    """会话状态。字段纪律：每个字段必须被至少一个切片的测试断言用到，否则删（S5 再加 todos/goal）。"""

    messages: list[dict]
    turn_count: int = 0


def _compose_tool_call(middlewares) -> callable:
    """wrap_tool_call 洋葱：从最内层（真执行）向外包，先注册者最外层。"""

    def base(tool, args) -> str:
        return tool.run(**args)

    call = base
    for mw in reversed(middlewares):
        call = (lambda m, nxt: lambda tool, args: m.wrap_tool_call(nxt, tool, args))(mw, call)
    return call


def run(
    state: State,
    llm: LLMClient,
    tools: list,
    *,
    middlewares: list = (),
    system: str = "",
    max_turns: int = 40,
) -> State:
    tool_map = {t.name: t for t in tools}
    tool_schemas = [
        {"name": t.name, "description": t.description, "input_schema": t.input_schema}
        for t in tools
    ]
    call_tool = _compose_tool_call(middlewares)

    while True:
        for mw in middlewares:
            mw.before_model(state)  # 注册序

        resp = llm.complete(system=system, messages=state.messages, tools=tool_schemas)
        state.messages.append(resp)

        for mw in reversed(middlewares):  # 逆序：先注册者最后看到输出（栈帧对称）
            if mw.after_model(state) is not None:
                return state  # 终止条件 3：中断信号（先于工具执行）

        tool_uses = [b for b in resp["content"] if b["type"] == "tool_use"]
        if not tool_uses:
            return state  # 终止条件 1：纯文本响应，自然收口

        # 同一响应的全部 tool_result 必须并入紧随其后的同一条 user 消息（Anthropic API 硬约束）
        results = [
            {
                "type": "tool_result",
                "tool_use_id": block["id"],
                "content": call_tool(tool_map[block["name"]], block["input"]),
            }
            for block in tool_uses
        ]
        state.messages.append({"role": "user", "content": results})

        state.turn_count += 1
        if state.turn_count >= max_turns:
            return state  # 终止条件 2：turn 熔断，防失控循环烧钱
