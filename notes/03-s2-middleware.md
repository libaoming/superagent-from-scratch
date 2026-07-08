# 拆解笔记 03 · S2 middleware 管线：横切关注点为什么是现代 harness 的真架构

> 2026-07-06 写上半场（F03 passing 时），2026-07-08 F04 绿后回填下半场（第四节 + 收口结论）。上一篇：notes/02（S1 复刻实录）。
> 先写上半场再回填，是因为协议设计的决策记忆最容易在实现细节里被冲掉——事实证明有效：回填时协议层一字未改。

## 一、deer-flow 怎么做：28 个 middleware，一套钩子

notes/01 数过：deer-flow 的 lead agent 本体 556 行全是外围，真正的产品能力在 **28 个 middleware** 里——摘要、防御、记忆、预算、todo……全部长在同一套钩子协议上，loop 主体零改动。

这才是现代 harness 的真架构：**「循环引擎」和「行为扩展面」解耦**。引擎（S1 那 20 行循环）一旦写对就冻结；所有横切关注点——「每轮都要发生、但不属于任何单个工具」的事——从唯一的一个协议面生长出来。deer-flow 加一个产品功能 ≈ 加一个 middleware 文件，这是它能堆到 28 个而不烂掉的原因。

## 二、我怎么简化：28 行协议 + 3 条链挂载

| 文件 | 行数 | 交付物 |
|---|---|---|
| `src/middleware.py` | 28 | `Middleware` 三钩子基类（默认全 no-op）+ `Interrupt` 中断信号 |
| `src/loop.py` | 78（S1 的 49 + 挂载 29） | `run()` 补 `middlewares` 关键字参数，三条链挂进循环 |

协议全文只有三个方法：

```python
class Middleware:
    def before_model(self, state) -> None:
        """进模型前就地改 state（注册序执行）。"""

    def after_model(self, state) -> Interrupt | None:
        """模型响应后检查/改 state（逆序执行）。"""
        return None

    def wrap_tool_call(self, call_next, tool, args) -> str:
        """洋葱模型包裹工具执行。必须调 call_next，除非有意短路。"""
        return call_next(tool, args)
```

### 顺序语义：一个心智模型记住三条链

注册序 `[A, B]` 时，单轮循环里钩子这样触发：

```
   before_model:   A → B                （注册序）
        │
        ▼
   llm.complete()
        │
        ▼
   after_model:    B → A                （逆序，栈帧对称）
        │                 ├─ 返回 Interrupt → 终止条件 ③，先于工具执行
        ▼
   wrap_tool_call: A( B( tool.run() ) ) （洋葱，先注册者最外层）
```

三条链一句话记住：**先注册者最先看到输入、最后看到输出、包在最外层**——和函数调用栈同构。S1 状态图里「故意不存在」的第三条终止边（Interrupt），本切片正式上线。

## 三、为什么这么设计（决策清单）

**1. 钩子只有三个，因为横切时机只有三个。**
每轮循环里能横切的位置穷举：进模型前（改输入）、出模型后（审输出）、工具执行时（包副作用）。F04 的三个内置 middleware 会各自认领钩子——Summarization 用 before_model 压缩旧消息，ToolOutputBudget / ToolErrorHandling 用 wrap_tool_call 管输出和异常。钩子数量由时机穷举推出，不是拍的。

**2. 顺序语义显式规定并用测试钉死，不留给实现顺序碰运气。**
before 注册序 / after 逆序 / wrap 洋葱——`test_before_registration_order_after_reverse_order` 用 Probe 探针断言精确序列 `["a.before", "b.before", "b.after", "a.after"]`。插件系统最阴的 bug 全是顺序 bug：两个 middleware 各自正确、组合起来错。顺序是协议的一部分，就必须是测试的一部分。

**3. Interrupt 是返回值，不是异常。**
after_model 返回 `Interrupt(question=...)` 即收口——用数据流而不是 raise 表达控制流，S1「终止条件穷举可见」的纪律得以延续：三个 return 全在 `run()` 里排队站好，没有藏在异常栈里的第四出口。且中断**先于工具执行**生效：已经决定打断，就不再烧工具副作用。协议在 S2 进场、消费者（ask_clarification）S5 才来——不违反「无消费者扩展点不加」，因为 F03 的测试就是它的第一个消费者（Halter 用 fixture 余量证明模型未被再调）。

**4. `middlewares` 以关键字参数补入，S1 测试零改动同绿。**
这就是 D1 清账的方式：C4 签名冻结从 S2 起算，`run(state, llm, tools)` 的旧调用原样工作，全量 26 passed（S1 的 19 条一行没改）是「加能力不改引擎」的回归实证，不是口头承诺。C7 再用 `inspect.signature` 断言把协议签名钉进测试——想改协议先让测试红，变更被迫显式化。

**5. 基类默认 no-op，子类只覆写关心的钩子。**
一件 middleware 只管一件事（SPEC 反模式 3）。默认 no-op 的另一面是组合安全：挂 0 个 middleware 时 `run()` 退化为 S1 行为，有专门测试（`test_run_without_middlewares_is_s1_behavior`）。

## 四、内置三件实战（F04 回填）：各认领哪个钩子、为什么

| middleware | 钩子 | 一句话 | 实现行数 |
|---|---|---|---|
| `ToolOutputBudget` | wrap | 输出超 N 字符 → 截断 + 标注原长/保留量 | 21 |
| `ToolErrorHandling` | wrap | 程序性异常 → `[tool error] 类名: 详情` 文本，run 不死 | 16 |
| `Summarization` | before | messages 超阈值 → 保近 K 条 + llm 压缩其余为一条 user 摘要消息 | 44 |

**钩子认领不是分配，是推导**：压缩改的是模型的输入 → 只能在进模型前（before）；预算和异常管的是工具执行的副作用 → 只能在包副作用处（wrap）。三个时机恰好用满，反过来验证了「钩子只有三个」的穷举论证。

三个实现级取舍：

**1. 截断标注要让模型看得懂。** `[输出超预算已截断：原 N 字符，保留前 M]`——不是给人看的日志，是给模型的信号：它下轮可自行换策略（分页读、加过滤条件）。和 ToolErrorHandling 的 `[tool error]` 同一思想：**横切层的产出物，消费者永远是模型**。

**2. ToolErrorHandling 宽接 `Exception` 是本职，不是坏味道。** 工具层的纪律是「程序性异常外抛、不兜」（S1），值班的兜底层就必须宽接——分工各守一边。S1 埋的那半句「错误恢复是 middleware 的单一关切」在此闭环，且有**对照组测试**：不挂它时异常照旧外抛（`test_error_propagates_without_middleware`）——「消费者分流」从口头原则变成可跑断言。

**3. Summarization 的 llm 从构造函数进（Q1=A 落地）。** `Summarization(llm=...)`——谁需要谁持有，协议三方法签名一字不动（C7 无感）。替换用 `state.messages[:] = ...` 就地写回，与 before_model「就地改 state」的协议语义一致。

**4. 切点必须对配对让位（S2 对抗审查红色发现的修复）。** 按条数切 `[-K:]` 可能把 tool_use/tool_result 配对从中间切断——真实 API 直接 400。修法 3 行：recent 若以 tool_result 开头，把配对的 assistant(tool_use) 从 old 挪回来再压。教训一句话：**「简单策略」豁免的是算法简单，不豁免产出非法消息序列**——out_of_scope 的边界要抠字眼。配套守护：`keep_last < max_messages` 构造期断言（否则每轮净增摘要消息，越压越长）。

### fixture 坑实录：「录制 = 全局调用序」第一次真咬人

`summarize_history.json` 的两条录制，**顺序即语义**：`responses[0]` 会被 before_model 里的压缩调用先消耗，`responses[1]` 才轮到主循环——两条对调，测试神秘变红（模型把摘要文案当成了最终答案）。fixtures/README 预警过的坑，F04 是第一个实际踩线的切片。

反向技巧再+1：「未超阈值不压缩」的测试用 `natural_close.json`（**仅 1 条录制**）——压缩若偷跑必弹尽抛错。这是「弹尽即抛错」契约第二次反向当证据用（第一次是 F03 的 Halter），不用任何 mock 计数器。

## 五、测试怎么钉住「看不见的顺序」

顺序和中断都是运行时行为，肉眼 review 不出来，S2 的测试给了两个可复用的手法：

- **Probe 探针**：一个只记日志不改行为的 middleware，把钩子触发序列变成可断言的列表——测顺序语义的通用工具；
- **fixture 余量证明**：Interrupt 测试收口后再手动 `llm.complete()` 一次，不抛错 = 录制序列还剩一条 = 循环确实没再进模型。用 FakeLLM「弹尽即抛错」的契约反向做证据，不用 mock 计数器。

## 六、可迁移清单：带走的不是代码，是判断

**1. 横切关注点收敛到唯一协议面，引擎冻结。**
- 是什么：新能力 = 新 middleware 文件，`loop.py` 从 S2 起签名冻结，deer-flow 靠这个堆到 28 个能力不烂。
- 如何应用：任何有「每次请求都要发生的事」的系统（HTTP 服务、数据管线、消息消费者），把日志/鉴权/限流/重试收敛到一个拦截器协议，业务引擎不再为横切改动。
- 验收信号：加一个横切能力的 PR，diff 里引擎文件零改动。

**2. 顺序语义是协议的一部分，必须有契约测试。**
- 是什么：before 注册序 / after 逆序 / wrap 洋葱，Probe 探针断言精确序列。
- 如何应用：接手任何插件/拦截器/hook 系统，第一件事写顺序契约测试；没有它，重构等于赌博。
- 验收信号：调换任意两个插件的注册顺序，至少一条测试变红（顺序无关则应显式声明无关）。

**3. 控制流信号用返回值表达，不用异常。**
- 是什么：`Interrupt` 是 frozen dataclass 返回值，loop 的三个出口全部平铺可见。
- 如何应用：工作流引擎的暂停/HITL/降级信号做成一等返回值类型；异常只留给真正的意外。
- 验收信号：终止条件能在引擎单一函数里穷举数出来，无隐藏出口。

**4. 兼容性承诺写成测试，不写成文档。**
- 是什么：C7 用 `inspect.signature` 断言钉住协议签名；C4 用「S1 测试零改动同绿」证明扩展未破坏存量。
- 如何应用：内部协议要冻结时，给签名/行为各写一条守护测试——文档会过期，红灯不会。
- 验收信号：任何破坏性变更必然先弄红一条测试，逼出显式决策。

### AI PM 视角：同一批事实，另一层判断

**P1. middleware 清单就是产品能力清单。**
- 是什么：deer-flow 的 28 个 middleware 直接对应摘要/防御/记忆/预算等产品能力——扩展面的单位就是能力交付的单位。
- 如何应用：评估一个 agent 产品（或竞品 harness）的成熟度，去数它的 middleware/拦截器清单，比读宣传页准；规划路线图时，「能不能做成一个 middleware」是功能成本估算的第一问。
- 验收信号：路线图上每个 agent 能力项都能标注「引擎改动 or 扩展面新增」，两者的排期和风险完全不同。

**P2. HITL 是否一等公民，在协议层就决定了。**
- 是什么：Interrupt 进协议的成本是一个返回值类型（S2，5 行）；如果等产品上线后再从 UI 层往循环里凿打断点，成本是重构引擎。
- 如何应用：做 agent 产品规划时，把「人在哪些点位能打断/接管」当架构需求在第一版就提给工程，哪怕 UI 晚两个版本才做——预留协议位便宜，事后凿洞昂贵。
- 验收信号：PRD 的 HITL 章节能指出协议层的挂载点，而不是一句「后续支持人工介入」。

**P3. 能力可组合 = 发布与商业化的粒度。**
- 是什么：middleware 按注册列表逐个挂载，天然支持独立开关。
- 如何应用：功能开关、灰度、分层套餐（企业版 = 多挂审计/预算/合规三个 middleware）的技术前提就是这个扩展面；商业化包装的颗粒度受架构颗粒度约束，PM 要在架构评审时替商业模式占位。
- 验收信号：任一能力可以对单个租户/单次会话独立开关，不需要发版。

## 七、拓展练习

**练习 1 · 用 wrap_tool_call 写 RetryMiddleware**：对返回值含 "timeout" 的工具调用自动重试至多 2 次，loop 与工具零改动。
验收：注入一个「先超时一次、再成功」的假工具，挂 RetryMiddleware 后任务全绿；不挂则拿到超时文本——同一套测试翻转断言即可。

**练习 2 · 顺序契约实战**：写 CacheMiddleware（命中缓存直接短路，不调 call_next）和 LoggingMiddleware，回答：谁注册在前？（提示：缓存命中时这次调用要不要出现在日志里？两种答案对应两种注册序，都合法——但必须用 Probe 式测试把你选的语义钉住。）
验收：一条测试断言命中缓存时的日志行为，调换注册序测试变红。

**练习 3（F04 版）· 给 Summarization 加 pinned 消息**：带 `"pinned": True` 标记的消息（如任务目标、用户硬约束）永不进压缩区——deer-flow durable context 的 20 行简化版。
验收：构造含 pinned 消息的超阈值历史，压缩后 pinned 原文仍在 messages 里且顺序合法；无 pinned 时行为与现版完全一致（原测试同绿）。

---
## 八、S2 收口结论

S2 全景 = **28 行协议 + 三条链挂载（29 行）+ 三件内置（81 行 + 11 行导出）**。verify：`test_s2_middleware.py` 7 passed + `test_s2_core_mw.py` 9 passed，全量 38 passed——其中存量测试**零改动同绿**，「加能力不改引擎」（C4）在 F03、F04 两次拿到回归实证。src 总 337 行（预算 1500）。对抗审查（fresh 子 agent）报 1 红 4 黄：红（切点破坏工具配对）当场修复并钉测试；黄全清——「近 K 条」方向断言、配置守护、预算边界、C7 三协议签名闸门补齐（LLMClient/Tool 形状/run 参数表进 test_constraints.py）。

一句话带走：**S1 证明循环可以很小，S2 证明能力可以不进循环**——引擎冻结 + 唯一扩展面，这就是 deer-flow 堆到 28 件不烂的全部秘密。tag `sfs-s2` 于收口面试通过后打。

*下一篇：notes/04 —— S3 task 工具 + subagent 委派：上下文隔离为什么是 harness 的第二支柱。*
