"""ReadBeforeWrite——写前版本门（SPEC #read-before-write）。guard 家族第三员。

「读过」不存路径集合、存内容 hash：盲写（没读就写）与读旧版（读过但磁盘已被外部改）
两种事故走同一条拦截路径（deer-flow 立项依据=真实事故 issue #3857）。
读记录寄生在 state.messages 上（不开 State 字段、不用实例变量）：messages 是唯一同时具备
「随 Summarization 压缩失效 + 随 checkpoint 存活」两性质的介质——它就是模型记忆本身。
设计不变量（2026-07-13 纠错定稿）：压缩删掉读记录后写被拦、逼模型重读——门的记忆与模型的
记忆同生共死；「压缩后还放行」反而是实例变量方案的病（门替模型记得已被遗忘的内容）。
「写不刷新 mark」零实现行：写成功后磁盘已变，旧 read 的 hash 自动失配。
边界说实：同一响应里「先 read 后 write」的并行调用，write 在 wrap 时扫不到同轮 read 的
结果（results 尚未回填 messages）——会被拦、下一轮重试即过；教学版接受此保守语义。
fail-open（2026-07-13 课上拍板 A，记录 0022）：门自己读不了文件 → 放行 + bypass 留痕
（静默放行的缓解，教学环反哺第四例）——防御件不能比被防御的更脆，写真有问题让工具层
自己炸（各层各管各的）；对照 S8 guard fail-closed，判据=「误拦 vs 漏过哪个更贵」。
读记录被 ToolOutputBudget 截断过时同走 fail-open 留痕（对抗审查 2026-07-13 红1）：
截断记录与磁盘全文永不可比，硬拦会让「重读→再写」也被拦——教学式指引变成死循环指路牌。
挂载指引：欲保 bypass 留痕，把 ToolErrorHandling 注册在本件**之后**（洋葱内层先转文本、
本件再加前缀）；注册在本件之前则 call_next 异常穿透、前缀丢失（审查黄5）。
实例生命周期契约同 S10 TwoTierGuard：一个实例 = 一个任务，不得与 subagent 共享。
"""

import hashlib
from pathlib import Path

from src.middleware import Middleware
from src.tools import render_numbered


def _digest(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()


class ReadBeforeWrite(Middleware):
    WRITE_HINTS = ("write", "edit")

    def __init__(self, state):
        self._state = state  # 构造注入（Q1=A 家族）：wrap 钩子签名里没有 state（C7 冻结）

    def wrap_tool_call(self, call_next, tool, args) -> str:
        if not any(h in tool.name for h in self.WRITE_HINTS) or "path" not in args:
            return call_next(tool, args)
        path = Path(args["path"])
        if not path.exists():
            return call_next(tool, args)  # 新文件放行：无旧内容可覆盖，拦了纯误伤
        try:
            current = _digest(render_numbered(path.read_text()))
        except (OSError, UnicodeDecodeError) as exc:
            return (
                f"[version-gate bypassed: 门读取 {path} 失败（{type(exc).__name__}），本次放行] "
                + call_next(tool, args)
            )
        record = self._last_read_text(args["path"])
        if record is not None and "已截断" in record:
            # 截断记录不可比（审查红1）：硬拦=死循环指路牌，按 fail-open 留痕放行。
            # 说实：正文恰含「已截断」字样的文件会误走此分支（漏防侧，教学版接受）
            return (
                f"[version-gate bypassed: {args['path']} 的读记录被截断、无法比对版本，本次放行] "
                + call_next(tool, args)
            )
        if record is None or _digest(record) != current:
            return (
                f"[tool error] 版本门拦下对 {args['path']} 的写入：没有读过该文件，"
                "或磁盘内容已变化（读到的是旧版）。请先用 read_file 读取当前内容，再重试写入。"
            )
        return call_next(tool, args)

    def _last_read_text(self, path: str) -> str | None:
        """反向扫 messages：先建 id→tool_use 映射（tool_result 里只有 id），再找该 path 最近一次 read 的渲染文本。路径经 resolve 归一化（审查黄3：防相对/绝对别名误拦）。"""
        calls = {
            b["id"]: (b["name"], b.get("input", {}))
            for m in self._state.messages
            if m["role"] == "assistant" and isinstance(m.get("content"), list)
            for b in m["content"]
            if b.get("type") == "tool_use"
        }
        target = Path(path).resolve()
        for m in reversed(self._state.messages):
            if m["role"] != "user" or not isinstance(m.get("content"), list):
                continue
            for b in m["content"]:
                if b.get("type") != "tool_result":
                    continue
                name, inp = calls.get(b["tool_use_id"], ("", {}))
                if "read" in name and inp.get("path") and Path(inp["path"]).resolve() == target:
                    return b["content"]
        return None
