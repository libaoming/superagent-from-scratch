"""双档阈值 + 延迟注入 + 剥 tool_use 硬停——S10 两件防御（LoopDetection/TokenBudget）的共享基建。

agent 最贵的失败不是崩溃，是打转/烧钱：不抛异常、不触发任何既有熔断（max_turns 要 40 轮才到顶），
每轮烧上下文产出为零。本基建把干预做成两档：
- 警告（≥warn）走**延迟注入**：after_model 只排队，下一轮 before_model 才 append 成 user 消息——
  当场 append 会夹进本轮 tool_use 与未回填的 tool_result 之间（API 配对硬约束第三个引爆点：
  S2 切点避、S7 恢复补、S10 注入绕）。文案本身是修复路径（教自救），同 S8 guard 理念。
- 硬停（≥hard）**剥 tool_use**：留模型已有文本、补停机说明 → loop 见「无工具调用」走终止条件 1
  自然收口——不加终止分支、不抛异常、loop 零改动（deer-flow 同款：剥 tool_calls + 改 finish_reason）。
warn < hard 是延迟注入的硬性推论（构造期断言）：两档重合时硬停当轮就收口，
排队的警告永远等不到「下一轮 before_model」。
计量状态放实例变量、不进 State（2026-07-13 课上拍板 A）：它是防御件的工作内存，不是任务现场——
checkpoint 恢复后计数归零，最坏是检测延迟翻倍（灵敏度暂时降级），不是任务错误。

实例生命周期与挂载次序（对抗审查 2026-07-13 契约化）：
- **一个实例 = 一个任务**：滑窗/花费账本随实例存续——同实例跨任务复用会把甲任务的排队警告
  与计数带进乙任务（per-instance 语义，同 S5 D5）；run_with_goal 续跑属同一任务，共用**有意**
  （打转前科不因续跑清零）。**不得与 subagent 共享实例**：排队中的警告会被 subagent 的
  before_model 消费进隔离栈、在主对话蒸发（S8 审查黄3 姐妹题）。
- **本族注册在 Clarification 等语义件之前**：after_model 逆序执行、后注册者先跑——让 Interrupt
  先行收口（loop 见非 None 即 return，硬停不再执行），否则剥 tool_use 会把 ask_clarification
  块连问题一起删掉、interrupt 静默丢失。双件同挂时先跑者剥、后跑者走「无 tool_use 早退」
  自动跳过已剥轮——先剥者赢，不会双剥。
"""

from src.middleware import Middleware


class TwoTierGuard(Middleware):
    """子类只回答「这一轮的计量值是多少」（_measure）并提供两段文案（_warning/_stop_note）。"""

    def __init__(self, warn_threshold: int, hard_threshold: int):
        assert warn_threshold < hard_threshold, (
            "warn 必须小于 hard：两档重合时硬停当轮收口，排队的警告永远没有「下一轮」可注入"
        )
        self.warn_threshold = warn_threshold
        self.hard_threshold = hard_threshold
        self._pending: str | None = None

    def before_model(self, state) -> None:
        if self._pending is not None:
            state.messages.append({"role": "user", "content": self._pending})
            self._pending = None

    def after_model(self, state):
        resp = state.messages[-1]
        if not any(b.get("type") == "tool_use" for b in resp.get("content", [])):
            return None  # 纯文本响应本来就走终止条件 1，无需计量与干预
        value = self._measure(state)
        if value >= self.hard_threshold:
            self._strip_tool_use(resp, value)
        elif value >= self.warn_threshold:
            self._pending = self._warning(value)
        return None

    def _strip_tool_use(self, resp: dict, value: int) -> None:
        kept = [b for b in resp["content"] if b.get("type") != "tool_use"]  # 留：模型已有文本
        kept.append({"type": "text", "text": self._stop_note(value)})  # 补：停机说明（可观测留痕）
        resp["content"] = kept

    def _measure(self, state) -> int:
        raise NotImplementedError

    def _warning(self, value: int) -> str:
        raise NotImplementedError

    def _stop_note(self, value: int) -> str:
        raise NotImplementedError
