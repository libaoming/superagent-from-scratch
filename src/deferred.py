"""deferred tools（SPEC #deferred-tools · S8）——能力层按需注入：未加载只见名字，搜索命中才晋升出 schema。

与 S4 skills 完美对仗（同一渐进披露范式）：skills 元数据常驻/正文激活（知识层），
这里名字常驻/schema 晋升（能力层）。deer-flow 对照：tool_search 四件 397 行只 defer MCP 工具，
双动机写在配置注释——省上下文 + 提工具选择准确率；教学版砍 catalog_hash/fail-closed/+prefix/MCP 标签。
藏的是 schema 不是工具本身：执行层 tool_map 始终持全部，所以「拦」是「藏」的必然推论。
state/catalog 走构造注入（Q1 先例）——Tool/Middleware 协议签名不动（C7）。
构造注入绑定的是「这一个 State」：subagent（全新 State）与 checkpoint 恢复（load_state 返回新
State）场景必须用对应 State **重建** ToolSearchTool/DeferredGuard——把绑定父 state 的实例下放给
子 agent，晋升会写进父 state（子 agent 自己永远等不到放行），对抗审查 2026-07-11 黄3。
"""

import json

from src.middleware import Middleware


def deferred_system_block(tools) -> str:
    """露：system 尾部纯名字清单（deer-flow 连摘要都不给——description 藏着但可被搜索命中）。

    静态常驻 = prompt cache 友好；露多少是产品旋钮（纯名字/加摘要），教学版取最省档。
    """
    names = [t.name for t in tools if getattr(t, "deferred", False)]
    if not names:
        return ""
    return "\n<available-deferred-tools>\n" + "\n".join(names) + "\n</available-deferred-tools>"


class ToolSearchTool:
    """搜 + 晋升（缝③元工具）：select: 精确取 / 关键词匹配 name+description，最多回 max_results 个。

    晋升双通道缺一不可：① 返回值（当轮 tool_result）给完整 schema JSON——当轮可读，能规划参数；
    ② 命中名字写进 state.promoted——下轮 loop 过滤放行进绑定，才发得出 tool_use。
    晋升改变 tools 集合必破一次前缀缓存：低频一次性代价，换每轮少提交 N-k 个 schema。
    """

    name = "tool_search"
    description = (
        "搜索并加载 deferred 工具的完整定义。query 支持两种："
        "select:Name1,Name2 按名字精确取；或用关键词匹配工具的名字与说明。"
    )
    input_schema = {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "select:名字列表 或 关键词"}},
        "required": ["query"],
    }

    def __init__(self, catalog, state, max_results: int = 5):
        self._catalog = [t for t in catalog if getattr(t, "deferred", False)]
        self._state = state
        self._max = max_results

    def run(self, *, query: str) -> str:
        q = query.strip()
        if not q:  # 空串对关键词分支恒真匹配 = 静默群晋升（还白破一次缓存）——退化输入回提示教自救，不扩权
            return "query 为空：用 select:名字 精确取，或给一个能匹配工具名字/说明的关键词。"
        if q.startswith("select:"):
            wanted = {n.strip() for n in q[len("select:"):].split(",") if n.strip()}
            hits = [t for t in self._catalog if t.name in wanted]
        else:
            ql = q.lower()
            hits = [
                t for t in self._catalog
                if ql in t.name.lower() or ql in t.description.lower()
            ]
        hits = hits[: self._max]
        if not hits:
            return f"未找到匹配 {query!r} 的 deferred 工具。可用名单见 system 的 <available-deferred-tools>。"
        self._state.promoted.update(t.name for t in hits)  # 通道②：下轮可调
        return json.dumps(  # 通道①：当轮可读
            [{"name": t.name, "description": t.description, "input_schema": t.input_schema} for t in hits],
            ensure_ascii=False,
        )


class DeferredGuard(Middleware):
    """拦（缝①）：未晋升的 deferred 调用拦在执行前，回教学式 error 教模型自救。

    必须拦的原因：tool_map 持全部工具，录制/幻觉直调未晋升工具会静默执行成功——
    「藏在视图层」若不配「拦在执行层」，藏就是假的。error 文案指路 tool_search（deer-flow 同款思路）。
    """

    def __init__(self, state):
        self._state = state

    def wrap_tool_call(self, call_next, tool, args) -> str:
        if getattr(tool, "deferred", False) and tool.name not in self._state.promoted:
            return (
                f"[tool error] 工具 {tool.name} 尚未加载（deferred）："
                f"先调 tool_search（如 select:{tool.name}）获取其定义，晋升后再重试。"
            )
        return call_next(tool, args)
