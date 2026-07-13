"""LoopDetection——防打转（SPEC #loop-detection · M1/M2）。

检测信号 = 每轮 tool_use 组归一化 → 排序 → hash → 滑动窗口计数。归一化的不对称设计是精髓：
- 读类**宽进**（防漏报/逃检）：只取 salient 字段（path/command/query 类）、offset 按 200 行分桶——
  「每次换个行号刷读同一文件」归一化后仍是同一调用；
- 写类**严出**（防误报）：名字含 write/edit 等的工具 hash 全参——「对同一文件的多次合法小改」
  content 不同即不同调用，不被误判成打转。
deer-flow 对照：loop_detection_middleware.py 612 行（内核 ~90）——砍频率层（同工具类型计数）、
线程 LRU、per-tool 阈值覆写（部署轮询类合法重复的产品解，走对照表升级路径）、Pydantic 配置。
"""

import hashlib
import json

from src.middlewares.two_tier import TwoTierGuard


class LoopDetection(TwoTierGuard):
    WARN_MARK = "[loop warning]"
    STOP_MARK = "[loop stop]"
    SALIENT_KEYS = frozenset({"path", "file_path", "command", "query", "url"})
    WRITE_HINTS = ("write", "edit", "delete", "create")

    def __init__(
        self,
        warn_threshold: int = 3,
        hard_threshold: int = 5,
        window: int = 20,
        read_bucket_lines: int = 200,
    ):
        super().__init__(warn_threshold, hard_threshold)
        assert window >= 1, "window 必须 ≥1：window=0 的删空切片会让滑窗永不淘汰（无限窗），语义反转"
        self.window = window
        self.read_bucket_lines = read_bucket_lines
        self._recent: list[str] = []  # 滑窗：实例变量不进 State（拍板 A——防御件工作内存非任务现场）

    def _measure(self, state) -> int:
        sig = self._turn_signature(state.messages[-1])
        self._recent.append(sig)
        del self._recent[: -self.window]
        return self._recent.count(sig)

    def _turn_signature(self, resp: dict) -> str:
        keys = sorted(
            self._stable_key(b["name"], b["input"])
            for b in resp["content"]
            if b.get("type") == "tool_use"
        )
        return hashlib.sha1("\n".join(keys).encode()).hexdigest()

    def _stable_key(self, name: str, args: dict) -> str:
        if any(hint in name for hint in self.WRITE_HINTS):
            norm = dict(args)  # 严出：全参入 hash，防把合法的多次小改误判成打转
        else:
            norm = {k: v for k, v in args.items() if k in self.SALIENT_KEYS}
            if "offset" in args:
                norm["offset_bucket"] = int(args["offset"]) // self.read_bucket_lines  # 宽进：防换行号刷读
            if not norm:
                norm = dict(args)  # 未识别 salient 的读工具退回全参：宁在误报侧（有警告档垫底）勿漏报
        return json.dumps([name, norm], sort_keys=True, ensure_ascii=False)

    def _warning(self, count: int) -> str:
        return (
            f"{self.WARN_MARK} 最近 {self.window} 轮内相同的工具调用组合已出现 {count} 次，"
            f"可能在原地打转。请换一种参数或策略推进；重复达到 {self.hard_threshold} 次将被强制停止。"
        )

    def _stop_note(self, count: int) -> str:
        return (
            f"{self.STOP_MARK} 相同的工具调用组合已重复 {count} 次（硬停阈值 {self.hard_threshold}），"
            "本轮工具调用已被移除，请基于已有信息收尾。"
        )
