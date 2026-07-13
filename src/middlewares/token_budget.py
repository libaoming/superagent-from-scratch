"""TokenBudget——预算闸（SPEC #loop-detection · 加餐，D2=B）。

同一套双档基建的第二住户：检测对象从「重复」换成「花费」。与 S2 Summarization 互补正交——
Summarization 管「窗口装不装得下」（空间轴），本件管「这一 run 花了多少」（成本轴）：
压缩省窗口但不省已花的钱，两者谁也替代不了谁。
计费口径（教学版）：每个工具轮把当前 messages 总字符数计入累计花费——近似「每轮全量重提交
历史」的真实成本结构（历史越长每轮越贵）。产品版 = 供应商 usage_metadata 差分累加、
input/output/total 三口径取最高占比（deer-flow 同款，不用 tokenizer 库——本地猜得再准
不如供应商账单），升级只动本类内部，缝①签名不变（对照表升级路径）。
"""

from src.middlewares.two_tier import TwoTierGuard


class TokenBudget(TwoTierGuard):
    WARN_MARK = "[budget warning]"
    STOP_MARK = "[budget stop]"

    def __init__(self, warn_chars: int, hard_chars: int):
        super().__init__(warn_chars, hard_chars)
        self._spent = 0  # 花费账本同滑窗：实例变量不进 State（拍板 A 同款）

    def _measure(self, state) -> int:
        self._spent += sum(len(str(m.get("content", ""))) for m in state.messages)
        return self._spent

    def _warning(self, spent: int) -> str:
        return (
            f"{self.WARN_MARK} 本次运行累计花费约 {spent} 字符（警告线 {self.warn_threshold}），"
            "请收敛探索、尽快给出结论。"
        )

    def _stop_note(self, spent: int) -> str:
        return (
            f"{self.STOP_MARK} 累计花费约 {spent} 字符已达硬停线 {self.hard_threshold}，"
            "本轮工具调用已被移除，请基于已有信息收尾。"
        )
