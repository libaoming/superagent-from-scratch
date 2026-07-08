# 拆解笔记 04 · S3 subagent 委派：上下文隔离为什么是长任务的命根

> 2026-07-09，S3（F05_task_subagent passing）收口时写。上一篇：notes/03（S2 middleware 管线）。
> 一句话主张：**subagent 不是「多智能体」这个大词，是 run() 的递归调用 + 一个全新 State**——所有复杂度都在「隔离」二字。

## 一、deer-flow 怎么做：533 行的 task_tool + executor

notes/01 数过：deer-flow 的 `task_tool.py` 有 **533 行**，加 `subagents/executor.py`。机制四步：

1. lead agent 调 `task(description, prompt, subagent_type)`
2. executor 给 subagent 开**全新 ThreadState**（独立 messages，checkpointer=False，一次性不续跑）
3. subagent 用几乎同一条 middleware 链（`build_subagent_runtime_middlewares` 复用共享基座）
4. 跑完只把最终结论作为 ToolMessage 回填主对话；中间过程走**独立事件通道**（`subagent.start/step/end`）供 UI 展开查看，**不进主上下文**

533 行里绝大多数是**并发调度 + SSE 事件流 + subagent 类型工厂**——这些服务前端实时展开（产品需求），不是委派的内核。内核只有一句：**开个空 State，再调一次同一个循环**。

## 二、我怎么简化：60 行一个工具类（代码主体约 40 行 + docstring）

| 文件 | 行数 | 交付物 |
|---|---|---|
| `src/subagent.py` | 60 | `TaskTool`（缝③工具，构造注入 llm/tools）+ `_final_text`（只回结论） |

核心实现（教学版全文骨架）：

```python
class TaskTool:
    name = "task"                                   # 就是一个工具，走缝③
    def __init__(self, llm, tools, *, max_concurrent=3, ...):
        self._tools = [t for t in tools if t.name != "task"]   # 单层委派：物理摘掉 task
        self._delegated = 0
    def run(self, *, description, prompt) -> str:
        if self._delegated >= self._max_concurrent:            # 配额闸门
            return f"[task error] 委派配额已用尽…"             # 超限回错误文本（同款分流）
        self._delegated += 1
        sub_state = State(messages=[{"role": "user", "content": prompt}])  # 全新 State
        final = run(sub_state, self._llm, self._tools, ...)    # 递归调同一个 run()
        return _final_text(final)                              # 只回末条文本结论
```

**三样现成件，零样新机制**——这是「subagent 不是新东西」的精确账：

| 复用了什么 | 证据 |
|---|---|
| task 是**工具**（缝③） | 有 name/description/input_schema/run，和 bash 同一个协议，模型像点普通菜一样点它 |
| 跑**同一个 run()** | `from src.loop import run`，subagent 不是新循环，是递归调用 |
| 结论走**同一条 tool_result 回填路** | task 的返回值和 bash 的返回值一样，被 loop 包成 user 角色 tool_result 回主对话 |

新增的只有**一个动作**：`State(messages=[{prompt}])`——开一个空的会话。上下文隔离的全部物理实现就是这个「空」。

## 三、为什么这么设计（决策清单）

**1. 隔离的是 State，不是能力。**
subagent 拿到同一个 llm、（除 task 外）同一批工具、可挂同一套 middleware——它什么都能干，唯独**在一块干净的白板上干**。主对话看不到它读的 5000 行日志，只看到它写下的那句结论。隔离 ≠ 阉割，这是最容易被误解的一点。

**2. 只回结论，是为了主上下文不被脏活淹没。**
长任务最大的敌人是上下文膨胀。「读长文档、翻日志、多步搜索」这类活会产出大量中间 token，全涌进主对话就把 agent 逼糊涂。委派把这些中间过程关进 subagent 的独立 context，主对话只收一句话——**这正是本项目 CLAUDE.md 的 L4 上下文隔离纪律，也是写这个项目时我一直在用的（脏活派子 agent 只收结论）**。机制（task 工具）与纪律（L4）是同一件事的两侧。

**3. 单层委派，物理摘掉 task。**
`[t for t in tools if t.name != "task"]`——subagent 的工具清单里根本没有 task，它想再委派也无从下手。为什么一刀切：允许递归委派 = 潜在的**委派炸弹**（每个 subagent 再开三个，指数级烧 context 和钱，且难归因）。产品版可做「带深度上限的多层委派」，但那是缝③的拓展，得先有真实需求 + 熔断设计，不是默认打开。

**4. Interrupt 之外的第三种「只回返回值」纪律延续。**
`_final_text` 只取末条消息的文本块——subagent 内部无论转了几轮、调了几个工具，回主对话的永远是一个 str，和普通工具输出无异。委派没有引入任何新的消息类型或控制流，S1「循环出口可穷举」的洁净得以延续。

**5. Deviation D5：max_concurrent 实为 per-instance 生命周期配额（用户已确认，对抗审查据实校正）。**
一开始我写的是「per-run 累计」，对抗审查戳破了：`_delegated` 只增不减、无 run 边界复位，实际语义是**per-instance 生命周期**——单次 run 内它等价于 per-run（每个顶层 run 通常新建 TaskTool），但**同一实例跨多次 run 复用时配额会累计泄漏**。这不是笔误无关紧要：**S5 `run_with_goal()` 正是复用同一 tools 列表反复调 run 的场景**，届时全局第 4 次委派起全被误拒。教训和 S2 的「简单策略不豁免非法序列」同源——**文案和实现必须对齐，估算的语义要被测试钉死**。处置：docstring 据实改 + `test_delegation_quota_is_per_instance_lifetime` 钉住跨 run 泄漏行为 + S5 备忘记「run_with_goal 须每 run 重建 TaskTool」。为什么不直接修成真 per-run：loop 已 C4 冻结，无处复位——保住冻结比消灭这个可控的已知代价更重要。教学点（配额 + 超限错误分流 + 防委派炸弹）一个不少。

## 四、测试怎么钉住「看不见的隔离」

上下文隔离是运行时行为，肉眼 review 不出来。S3 的测试给了两个手法：

- **反向泄漏断言**：`test_task_delegates_and_returns_only_conclusion` 断言主 messages 的 tool_use 只有 `["task"]`，且 subagent 内部的 bash 命令串 `"ls fixtures/workspace"` **不出现在** `str(state.messages)` 里——用「不该在的东西不在」证明隔离，比「该在的在」更难作弊。
- **fixture「录制=全局调用序」第二次咬人 + 正向弹尽确认**：`subagent_flow.json` 的四条响应，`responses[1..2]` 归 subagent 内部循环消耗、`[0]` 和 `[3]` 归主对话。同一 FakeLLM 实例按全局序列弹——这既是坑也是证据。审查提醒隔离只有反向断言，故补了正向确认：测试末尾再 `llm.complete()` 一次断言**弹尽抛错**，反证 subagent 真的跑了那两拍（若被跳过，序列消耗错位、这里就不会弹尽）。
- **边界钉死（对抗审查补）**：`test_final_text_on_subagent_halt` 钉住 subagent 熔断（末条是无 text 的 tool_result）时 `_final_text` 回退占位、不误当结论；`test_delegation_quota_is_per_instance_lifetime` 钉住 D5 的跨 run 泄漏既定行为。

## 五、可迁移清单：带走的不是代码，是判断

**1. 委派 = 递归调用 + 上下文隔离，不是新架构。**
- 是什么：subagent 复用工具协议、同一 run、同一回填路，新增的只有「开空 State」。
- 如何应用：任何系统想加「子任务隔离执行」，先问「能不能用现有的执行器 + 一个干净的上下文实现」，而不是造一套新的子系统；隔离的载体是**状态容器**，不是新引擎。
- 验收信号：委派功能的核心代码能压到几十行，且不改主执行器。

**2. 上下文是稀缺资源，隔离是治理它的架构手段。**
- 是什么：脏活的中间过程关进独立 context，主线只收结论。
- 如何应用：任何「主流程会被大量中间数据淹没」的场景（日志分析、批量爬取、多步检索），把重 context 的子任务外包，主流程只接收压缩后的结论。
- 验收信号：主流程的上下文/内存占用不随子任务的中间数据量增长。

**3. 危险的强能力要有物理边界，不靠约定。**
- 是什么：防递归委派靠「子工具集里没有 task」，不靠「约定别递归」。
- 如何应用：任何有自我调用/放大风险的能力（递归、fork、批量触发），用「能力物理缺席」而非「运行时检查」来兜底——前者不可能被绕过。
- 验收信号：删掉运行时检查，危险行为依然无法发生（因为工具/权限根本不存在）。

### AI PM 视角：同一批事实，另一层判断

**P1. 机制 vs 纪律是两侧，PM 要同时管。**
- 是什么：task 工具 = 平台提供的**机制**，L4 隔离 = 使用者遵守的**纪律**。
- 如何应用：做 agent 平台，问「我给了委派机制吗」；用 agent 做产品，问「我的 agent 把脏活隔离了吗」——两个角色两张检查表。
- 验收信号：平台侧有委派原语的文档与配额；应用侧有「哪些任务必须委派」的设计规范。

**P2. context 治理是产品成本项，该进 PRD。**
- 是什么：长任务跑多远，取决于委派 + 摘要的 context 治理架构，直接决定单任务 token 成本上限与失败率。
- 如何应用：把「上下文预算、委派策略、摘要阈值」当**产品参数**在 PRD 规格化，而不是留给工程拍——它们决定用户体验（能不能跑完）和毛利（烧多少 token）。
- 验收信号：PRD 有「单任务 context 预算」条目，且关联到成本模型。

**P3. 委派清单 = 能力编排面。**
- 是什么：`subagent_type` 注册表（教学版只留 general-purpose）在产品里就是「派什么专家干什么活」。
- 如何应用：规划专业 agent（研究员/审查员/数据分析师）时，每一个都是委派注册表里的一项；路线图上「加一个专家 agent」= 扩展面新增，和改引擎是两种排期。
- 验收信号：能力路线图上每个专业 agent 对应一个可独立开关的注册项。

## 六、拓展练习

**练习 1 · subagent_type 注册表**：把 TaskTool 的单一 general-purpose 扩成「按类型选不同 system prompt + 不同工具子集」的注册表——`task(description, prompt, subagent_type)`。
验收：注册一个 `researcher`（只给 read_file/bash）和一个 `writer`（只给 write_file），各自跑对；未注册类型回错误文本。主 loop 与协议零改动（纯缝③拓展）。

**练习 2 · 真并发 + 事件流（还原 deer-flow 砍掉的部分）**：把同步顺序执行换成 `asyncio.gather` 真并发，max_concurrent 变回严格 per-turn 语义（消解 D5 的简化）。
验收：同一响应的多个 task 并发跑、总耗时接近最慢单个而非求和；配额按「同时活跃数」而非「累计数」限制。体会点：D5 的 per-run 简化省掉了多少东西，以及为什么教学版有资格省。

---

## 七、S3 收口结论

S3 全景 = **一个 TaskTool（代码主体约 40 行）**，复用 S1 的 run、S1 的工具协议、S1 的 tool_result 回填路——新增的只有「开一个空 State」。verify：`test_s3_subagent.py` 6 passed（含对抗审查补的两条边界），全量 44 passed（存量 38 **零改动同绿**，C4 第三次实证）。src 总 402 行（预算 1500）。对抗审查 0 红 5 黄：黄1（配额 per-instance vs 文案 per-run 不一致）据实校正 + 钉测试，黄2/4 补边界测试，黄3 加注释——全清。

一句话带走：**S1 循环可以很小、S2 能力可以不进循环、S3 子任务可以只是递归调用**——三刀砍下来，「多智能体」这个吓人的词落到代码就是「递归 + 隔离」。这就是 deer-flow 敢用一次推倒重写押注这个形态、并成为 2026 年事实标准的原因：它简单到能当标准。tag `sfs-s3` 于收口面试通过后打。

*下一篇：notes/05 —— S4 skills：能力的热插拔（元数据常驻、正文按需）。*
