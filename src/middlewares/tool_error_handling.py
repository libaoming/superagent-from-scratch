"""ToolErrorHandling——程序性异常转错误文本回填，run 不死（wrap_tool_call）。

S1 的分工在此闭环（SPEC #tools 异常处理分工）：工具只做本职、异常外抛，
「错误恢复是 middleware 的单一关切」——本件就是那个值班的横切层。
转成文本后错误的消费者变回模型：它看到 [tool error] 可下轮自纠或换路。
"""

from src.middleware import Middleware


class ToolErrorHandling(Middleware):
    def wrap_tool_call(self, call_next, tool, args) -> str:
        try:
            return call_next(tool, args)
        except Exception as e:  # noqa: BLE001——横切兜底层，宽接是本职
            return f"[tool error] {type(e).__name__}: {e}"
