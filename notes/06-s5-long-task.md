# 拆解笔记 06 · S5 长任务三件套：把纯净的 run() 套进目标闭环

> 2026-07-09，S5（F07_todo_goal + F08_clarification_hitl passing）收口时写。上一篇：notes/05（S4 skills）。这是最后一篇。
> 一句话主张：**long-horizon 不是把 loop 改大，而是用 harness 外壳把一个纯净的 run() 套进「目标闭环」，再给人留一个中断口。** 三件套治三个长任务痛点——计划被摘要压掉、一轮到不了目标、信息不全还硬猜——全部长在 loop 外或缝①，`run()` 签名一个字没改（C4 第六次实证）。

## 一、deer-flow 怎么做：checkpointer + interrupt + evaluator

deer-flow 的长任务能力散在三处，都比教学版重：

1. **todo**：`PlanningMiddleware` 把计划写进持久化 state，配合前端渲染成任务卡片流。
2. **goal 续跑**：独立的 **evaluator 模型** + 类型化 `blocker`（结构化诊断「为什么没达成、缺什么」），驱动 orchestrator 决定是否再跑一轮。
3. **HITL**：LangGraph 的 `checkpointer` + `interrupt()` —— 把整个图的执行状态**序列化到磁盘**，中断后可跨进程、跨天恢复；`Command(resume=...)` 带答案回灌。

重量全在「生产级持久化 + 独立评估模型 + 类型化诊断」上。**长任务的内核不在这些——内核是「跑完一轮，问一句达成没，没达成就接着跑；缺信息就停下问人」。**

## 二、我怎么简化：一个外壳 + 一对工具/中间件 + 一个返回字段

| 文件 | 交付物 | 缝 |
|---|---|---|
| `src/goal.py` | `run_with_goal` 外壳 + `_goal_met` 评估 + 双熔断 | **不占缝**（harness 外壳，包着 run） |
| `src/middlewares/todo.py` | `WriteTodos`（工具）+ `TodoMiddleware`（before_model 注入） | 缝③ + 缝① |
| `src/middlewares/clarification.py` | `AskClarification`（工具）+ `Clarification`（after_model 拦截） | 缝③ + 缝① |
| `src/loop.py` | State 加 `todos` / `goal` / `interrupt` 三字段 | 数据模型（非签名，C4 不受扰） |

三件套各自的骨架：

```python
# goal 续跑——外壳包纯净 run()，loop 零改动（C4）
def run_with_goal(state, llm, tools, *, max_continuations=8, **run_kwargs):
    prev_text, stale, continuations = None, 0, 0
    while True:
        state.turn_count = 0                          # 单轮熔断每轮复位
        for t in tools:                               # 拆 D5 埋雷：有状态工具每轮复位
            if callable(getattr(t, "reset", None)): t.reset()
        state = run(state, llm, tools, **run_kwargs)  # 调同一个纯净引擎
        if state.interrupt is not None: return state  # 中断优先于续跑
        if not state.goal or _goal_met(llm, state, state.goal): return state
        if continuations >= max_continuations: return state          # 熔断①：次数
        cur = _last_assistant_text(state)
        if cur == prev_text:
            stale += 1
            if stale >= 2: return state               # 熔断②：连续 2 次无新文本
        else: stale = 0
        prev_text = cur
        state.messages.append({"role": "user", "content": "[目标未完成] 请继续推进…"})
        continuations += 1

# clarification——问题走 state 字段，不走返回值
class Clarification(Middleware):
    def after_model(self, state):
        for block in state.messages[-1].get("content", []):
            if block.get("type") == "tool_use" and block["name"] == "ask_clarification":
                state.interrupt = Interrupt(block["input"]["question"])  # stash = 返回通道
                return state.interrupt                                    # 非 None → loop 收口
        return None

# todo——计划外置到 state，每轮 before_model 重注一条提醒
class TodoMiddleware(Middleware):
    def before_model(self, state):
        state.messages[:] = [m for m in state.messages if not self._is_reminder(m)]  # 撤旧
        if state.todos:
            state.messages.append({"role": "user", "content": 渲染(state.todos)})    # 重注
```

**没有一行改到 `run()`。** 续跑是 run() 外面的外壳、todo/clarification 是缝①上的住户、三个新字段只是 State 的数据模型——三件套全部长在既有骨架的缝上。

## 三、为什么这么设计（决策清单）

**1. 计划外置到 state，是为了摘要压不掉（todo）。**
长任务里计划若只活在对话历史里，一触发 S2 的 Summarization 就可能被压没。把计划外置成 `state.todos` 结构化字段（摘要逻辑只碰 messages 不碰它），每轮 `before_model` 再渲染成一条提醒重注入——**计划活在 state、不活在模型脑子里**。全量替换（不做增量 diff）是教学简化：模型每次给全量清单，覆盖即真相。这是三件套里和 S2 咬合最紧的一件：**正是「计划会被摘要压掉」这个威胁逼出了外置**。

**2. goal 续跑走外层 run_with_goal()，不改 loop（Q2=A）。**
续跑是**目标闭环**，属于比「单轮循环」更外面的一层。做成外壳包纯净 `run()`，loop 签名一个字不改（C4）。依赖单向朝内：`goal.py` import `loop`，`loop` 不 import `goal`——**引擎压根不知道有续跑这回事**，这才是「外壳」的硬证据。外置本身即教学点：**long-horizon 是 harness 套的目标闭环，不是把引擎改复杂**。

**3. 两个熔断各管一层（盲区回填）。**
`turn_count≤40` 管**单次 run 内**一轮转不停（且**每续跑重置**，否则第二轮直接顶格）；`续跑次数≤8 + 连续 2 次无新 assistant 文本即停` 管**续跑总量**（目标永远判不达成会无限烧钱）。前者防「一轮转不停」，后者防「轮次转不完」，正交。**无进展熔断尤其关键**：光有次数上限，模型可能空转 8 次；「连续 2 次没产出新文本」才是真「卡住了」的信号。

**4. Interrupt 走 state 字段，不走返回值——因为 loop 丢弃返回值（F08）。**
`Clarification.after_model` 看到 ask_clarification 的 tool_use → 把问题 stash 进 `state.interrupt` 并返回 Interrupt → loop 收口（**先于工具执行**）。为什么走 state：**loop 见 after_model 非 None 只 `return state`、把返回的 Interrupt 当纯真值信号用、对象本身丢弃**；加上 C4 冻结 run 返回 State、不能改成返回 Interrupt。两条一夹，问题**只能**挂 state 上带出。这也印证了 S2 的伏笔——**Interrupt 做成返回值而非异常**，正是为了让「中断」是收口的一种、现场（state）完整保存。

**5. 中断 = 收口不是崩溃，恢复 = 带答案重进循环。**
HITL 全部机制一句话，没有魔法。中断是和「纯文本自然收口」「turn 熔断」并列的**终止条件 3**——loop 干净 `return state`，现场完整。恢复就是往 messages 补一条 tool_result（用户答案）配对悬空的 tool_use、清 interrupt、重进同一个 run。教学版不把断点序列化到磁盘（F08 out_of_scope）——「保存现场」就是 state 本身。

**6. 中断优先于续跑（F07×F08 的边界）。**
`run_with_goal` 每轮 run 后**先查 `state.interrupt`**：非空就立即交回调用方、不续跑、不评估。语义正确——agent 主动说「我缺信息要问人」时，不该被 goal 续跑逻辑无视着硬推。两个长任务机制的优先级在这一行定死。

**7. 两处埋雷在引爆点前拆掉（跨切片的账）。**
S5 引爆了前面埋的两颗雷，都在此拆除并测试钉死：① **Interrupt 返回通道**——S2 的 `Interrupt` 类早定义好（docstring 写「question 由 S5 调用方消费」），S5 补上 state.interrupt 字段接住；② **`_delegated` 跨 run 泄漏**——S3 D5 明确记「run_with_goal 复用同一 TaskTool 会泄漏，须每轮复位」，S5 加 `TaskTool.reset()` + run_with_goal 每轮调。**简化留下的已知代价，要在引爆点前主动拆，不能让它静默炸。**

## 四、测试怎么钉住「跑了几轮 / 停在哪 / 计划还在不在」

长任务的行为（续跑几次、哪个熔断先响、中断有没有优先）都是运行时的，S5 用 fixture 的「全局调用序」+ 结构断言钉死：

- **续跑闭环 + 两处复位**：`test_goal_continues_until_met` 用 4 条交错录制（工作/NO/工作/YES），断言发生了续跑（`[目标未完成]` 在 messages）、达成后收工，且 `tool.reset_count == 2`（**_delegated 每轮复位 = 拆 D5 埋雷**）、`turn_count == 0`（每续跑重置）。
- **两个熔断各测一条**：`test_stale_circuit_breaker`（相同文本 → 连续 2 次无进展，跑 3 轮即停不是 8 轮）；`test_continuation_count_cap`（不同文本、始终 NO、`max_continuations=2` → 靠次数上限停在 3 轮）。两个熔断走不同的响应模式，分别钉死。
- **计划外置抗压缩**：`test_todo_reminder_survives_history_reset` 模拟 Summarization 把 messages 压没，断言提醒**从 state.todos 重生**、且只保留一条不累积——证明「计划外置、摘要压不掉」。
- **中断三件事**：`test_clarification_interrupts_before_tool_runs` 钉「问题在 state.interrupt / 工具没跑（无 tool_result）/ turn_count 未自增」；`test_resume_with_answer_continues_to_close` 钉带答案重进收口。
- **无目标退化 + 中断优先**：`test_no_goal_is_single_run`（goal 空 → 单次 run 不评估，用 1 条录制反证评估没偷跑）；`test_interrupt_preempts_continuation`（goal 非空但触发中断 → 不续跑不评估）。

verify：`test_s5_todo_goal.py` 7 passed + `test_s5_hitl.py` 4 passed，全量 **61 passed**（存量 54 零改动同绿，C4 第六次实证）。

## 五、可迁移清单：带走的不是代码，是判断

**1. 长任务 = 外壳套引擎的目标闭环，不是把引擎改复杂。**
- 是什么：run_with_goal 包纯净 run，引擎不知道有续跑。
- 如何应用：任何「跑一次不够、要逼近一个目标」的系统，先问「能不能用现有的单次执行器 + 一个外层循环 + 一个达成判定实现」，而不是把目标逻辑塞进执行器。
- 验收信号：执行器代码不 import 目标/续跑模块（依赖单向朝内）。

**2. 关键状态外置到结构化字段，别留在会被治理的地方。**
- 是什么：计划放 state.todos，不放会被摘要压掉的 messages。
- 如何应用：任何「必须活到任务结束」的状态（计划、目标、预算、进度），放在不被上下文治理（摘要/截断/淘汰）碰到的结构化字段里，每轮从它重新渲染。
- 验收信号：把对话历史整段清空后，关键状态仍能从字段重建。

**3. 每个自动循环都要有正交的多层熔断。**
- 是什么：单轮 turn 熔断 + 续跑次数熔断 + 无进展熔断，各防一种失控。
- 如何应用：凡是「模型驱动的自动循环」，至少配「单步上限」+「总量上限」+「无进展检测」三层——只有次数上限挡不住「空转到顶」。
- 验收信号：构造一个「永远判不完成」的输入，系统在有限步内因无进展而停，不是耗到次数顶格。

### AI PM 视角：同一批事实，另一层判断

**P1. 目标闭环 = 产品的「能跑完吗 + 烧多少」。**
- 是什么：续跑次数、双熔断阈值直接决定任务完成率与单任务成本上限。
- 如何应用：把「续跑上限 / 熔断阈值 / 目标判定策略」当**产品参数**在 PRD 定死——它们是「任务完成率」和「单任务毛利」两个指标的旋钮，不该留给工程拍。
- 验收信号：PRD 有「单任务续跑预算」条目，关联到完成率与成本模型。

**P2. HITL 是信任与安全闸，不是「功能没做完的补丁」。**
- 是什么：ask_clarification 让 agent「不确定就停下来问」，是高风险动作前的确认位。
- 如何应用：产品的「人工介入点」设计 = 往缝①挂拦截 middleware；转账/删库/发布这类不可逆动作前，强制一个 clarification/confirmation 中断。这是可编排的能力面，也是企业级信任的基础。
- 验收信号：高风险工具调用前有强制中断；中断能被审计（谁问了什么、谁答的）。

**P3. 计划外置 = 长任务的进度可观测性。**
- 是什么：state.todos 让计划成为结构化、可渲染、可给用户看的进度条。
- 如何应用：长任务产品的「agent 现在做到哪一步」UI，数据源就是外置的 todo 状态——外置不只喂模型，也喂前端。
- 验收信号：产品能实时展示 agent 的当前计划与每项状态，且与 agent 内部状态一致。

## 六、拓展练习

**练习 1 · 类型化 blocker（还原 deer-flow 砍掉的评估层）**：把 `_goal_met` 的 YES/NO 判定升级成结构化诊断——返回 `{met: bool, blocker: str, next_hint: str}`，续跑时把 `next_hint` 注入而非笼统的「继续」。
验收：目标未达成时，续跑消息带上具体缺口（「还差统计文件数」）而非「[目标未完成] 请继续」；跑通一个「诊断驱动续跑」的 case。体会点：教学版的 YES/NO 简单判定丢了什么，以及独立 evaluator 的价值在哪。

**练习 2 · 断点持久化（还原 checkpointer）**：把 clarification 中断时的 state 序列化到磁盘（JSON），实现「关掉进程、明天带答案恢复」。
验收：run 中断后进程退出，重启后从磁盘反序列化 state + 补 tool_result → 继续跑完。体会点：教学版「保存现场 = state 在内存」的简化省掉了什么，以及跨进程 HITL 为什么需要 checkpointer。

---

## 七、S5 收口结论 + 全项目收官

S5 全景 = **一个 `run_with_goal` 外壳 + 一对 todo 工具/中间件 + 一对 clarification 工具/中间件 + State 三个新字段**，`run()` 零改动（C4 第六次实证）。verify：11 passed（F07 7 + F08 4），全量 61 passed，src 661 行（预算 1500）。两处跨切片埋雷（Interrupt 返回通道、_delegated 复位）在引爆点拆除并钉死。

**五刀砍完，回望整个项目**——一个「能循环、能挂工具、有横切治理、能委派子任务、能热插拔技能、能跑长任务」的 agent harness，主体 661 行：

| 切片 | 一句话 | 新增的本质 |
|---|---|---|
| S1 循环 | messages→LLM→tools→append→再入模型 | 一个可穷举出口的 while |
| S2 中间件 | 横切能力长在三钩子上，loop 零改动 | 一个行为扩展面（缝①） |
| S3 委派 | subagent = 递归调用 + 全新 State | 一个「开空 State」的隔离 |
| S4 技能 | 注入知识不是能力，元数据常驻正文按需 | 往 messages 拼字符串（不占缝） |
| S5 长任务 | 外壳套引擎的目标闭环 + 人在环中 | 一个外层循环 + 三个 state 字段 |

一句话带走：**deer-flow 那套让人望而生畏的「多智能体长任务框架」，落到教学版就是——一个小循环、一个扩展面、一次递归、几次字符串拼接、一个外层闭环。** 复杂的从来不是 agent 的骨架，是骨架之上为了产品化堆的持久化、并发、多模型、类型化诊断、事件流。看清骨架有多小，就看清了「从零手写一个 agent」根本不需要框架——这正是本项目存在的理由。tag `sfs-s5` 于收口面试通过后打，全项目完工。

*系列完。五篇拆解笔记对应五刀：notes/02 循环 · 03 中间件 · 04 委派 · 05 技能 · 06 长任务。*
