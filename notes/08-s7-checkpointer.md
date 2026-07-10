# 拆解笔记 08 · S7 断点持久化：进程可死，任务不死

> 2026-07-10，S7（F10_checkpointer）收口时写。上一篇：notes/07（S6 长期记忆）。第二季第二篇。
> 一句话主张：**checkpointer 的本质是 per-step durability（每轮把 State 全量快照落盘，崩溃只丢半轮），不是 save-on-close；恢复没有魔法——载入 + 补消息 + 重进同一个 `run()`，与 S5 的 HITL 恢复完全同构。** 兑现两笔旧账：S5「保存现场 = state 在内存」的明写简化（F08 out_of_scope）+ notes/06 拓展练习 2。

## 一、deer-flow 怎么做：0% 内核 + 100% 胶水（史上最极端的一次对照）

子 agent 核实（2026-07-10），这刀的对照结论比前七刀都极端：

1. **内核 0 行**：存/取/恢复全部押在 LangGraph 官方 checkpointer 上（InMemory/Sqlite/PostgresSaver 按配置选型）——deer-flow 自己一行存取逻辑都没写。自己的 ~458 行（config 64 + sync provider 192 + async provider 202）**全是工厂/单例/锁/清理胶水**。
2. **保存节奏**：LangGraph 每个 super-step 自动存一个 checkpoint，deer-flow 不干预——**不存在「只在 interrupt 时存」**，per-step durability 是这类系统的默认语义。
3. **意外发现**：生产代码**没有一处调用** LangGraph 的 `interrupt()`/`Command(resume)`——它的 ask_clarification 走「wrap_tool_call 拦截 → 正常收口（goto=END）→ 用户在同一 thread 发新消息 → 从最新 checkpoint 载入续跑」，**与本项目 S5 的设计同构**。框架给的中断原语，生产反而绕开了。
4. **它踩过的坑**：悬空 tool_use 配对（专写 205 行 DanglingToolCallMiddleware）、同 thread 并发写 409、回滚只能追加不能改写历史、subagent 显式 `checkpointer=False` 防污染父 thread。

**教学版要手写的，恰恰是库包办的三件事：存什么 / 何时存 / 怎么恢复。**

## 二、我怎么简化：一个文件、两个存点、一个兜底

| 交付物 | 内容 | 缝 |
|---|---|---|
| `src/checkpoint.py`（84 行，唯一新文件） | `save_state`/`load_state`（JSON 全量 + 悬空兜底）+ `Checkpointer`（缝① middleware）+ `run_with_checkpoint`（外壳终存） | **缝①** + 外壳 |
| `fixtures/fake_llm/checkpoint_crash.json` | 1 条录制：第 2 轮 complete 弹尽 = 中途死 | fixture 先行 |

```python
class Checkpointer(Middleware):          # 缝①住户：per-turn 存
    def before_model(self, state):
        save_state(self._path, state)    # 此刻上一轮 tool_result 已 append，轮间完整态

def run_with_checkpoint(state, llm, tools, *, path, middlewares=(), **kw):
    state = run(state, llm, tools, middlewares=[Checkpointer(path), *middlewares], **kw)
    save_state(path, state)              # 收口终存：最终回复 + interrupt 只有这里兜得住
    return state

def load_state(path) -> State:           # 恢复 = 重建 + 悬空兜底
    ...                                  # 崩溃悬空（interrupt 空）→ 补 [interrupted] tool_result
    ...                                  # 待答悬空（interrupt 非空）→ 留给调用方补答案（S5 流程）
```

**协议签名零改动（C7）、run()/State 零改动（C4 第八次实证）。** checkpoint 是缝①第一次收「持久化」类住户。

## 三、为什么这么设计（决策清单）

**1. per-step durability，不是 save-on-close（核心 aha）。**
只在收口存一次？第 17 轮被 `kill -9` 时磁盘上什么都没有，整个 run 白跑——那是 save-on-close，不配叫 checkpointer。每轮存，崩溃时磁盘上有**最近一轮开始时的完整 State**，只丢半轮。LangGraph 每 super-step 自动存，就是这个语义。

**2. 挂载点 M1：节奏定挂载（与 S6 成对的决策）。**
统一判据：**协议里有对应节奏的钩子就走缝，没有就走外壳。** 记忆读写是 per-run（协议没有 per-run 钩子，加了破 C7）→ 外壳（S6）；checkpoint 的存是 per-turn（协议**恰好有** before_model）→ 缝①（S7）。判据不是轻重、不是数据流向，是**节奏**。否决的备选：纯外壳收口存（= save-on-close，见决策 1）。

**3. 存点选 before_model + 外壳终存，两件套缺一不可。**
before_model 时点 = 上一轮 tool_result 已 append、新一轮未开始——State 处于**轮间完整态**，快照天然不含半轮。但 before_model 只在「还有下一轮」时触发：自然收口后最终 assistant 回复、中断收口后的 interrupt 字段，都没有下一轮 before_model 来存——**只能靠外壳收口终存兜住**。只挂 middleware 丢结尾，只挂外壳丢中途。测试 `test_checkpointer_is_a_plain_middleware` 末尾专门反证了「单挂 middleware 最终回复不在盘上」。

**4. 同步写是语义要求，不是性能妥协（与 S6 旁路的张力）。**
S6 专门做写路径旁路防拖慢，S7 却每轮同步写盘——不矛盾，两层：① 量级不同——S6 旁路防的是**秒级 LLM 调用**，S7 是**毫秒级本地 JSON 写**，轻的同步做、重的旁路做；② 方向相反——checkpoint 若异步写，崩溃瞬间最近一轮可能还没落盘，「只丢半轮」的 durability 承诺就破了。**存完才进模型**：S6 旁路是性能优化，S7 同步是正确性约束。

**5. 悬空 tool_use 兜底 M2——且悬空有两种（实现时的精化）。**
崩溃可能停在「模型要了工具、结果还没回来」的半轮，checkpoint 末条 assistant 带 tool_use 无配对 tool_result——下轮请求直接 API 400（deer-flow 205 行中间件换来的教训；S2 摘要配对坑的姐妹篇：同一条 API 硬约束，S2 在压缩切点引爆、S7 在崩溃恢复引爆）。实现时发现**兜底必须区分两种悬空**：**崩溃悬空**（interrupt 空）→ load 时补合成 `[interrupted]` tool_result；**待答悬空**（interrupt 非空 = S5 HITL 中断收口，ask_clarification 的 tool_use 等的就是用户答案）→ **load 不许抢填**，否则撞坏 S5 恢复流程（调用方再补答案就会出现同 id 双 tool_result）。用 `state.interrupt is None` 一个分支区分，测试把两种都钉死。

**6. 恢复与 S5 同构——checkpointer 没有新恢复机制。**
恢复 = `load_state(path)` 重建 State →（HITL 场景）补答案 tool_result + 清 interrupt → **重进同一个 run()**。S5 定下的「中断 = 保存现场的正常收口，恢复 = 带答案重进循环」原封不动，S7 只是把「现场」从内存搬到磁盘。deer-flow 生产绕开框架中断原语走同构路径，反向印证了这个设计。

## 四、测试怎么钉住「中途死、只丢半轮、真能续」

测试套件是**理论课上用户自己设计的**（教学环反哺开发的第一例，learning-records/0016）：

- **中途死的离线等价物**：没法真 `kill -9`——让**唯一接缝抛异常**（FakeLLM 弹尽 RuntimeError），与 S6 用 `background=False + flush()` 替代真实 Timer 是**同一门手艺：用接缝的确定性行为替代真实环境事件**。fixture 只录 1 条（第 1 轮 tool_use），第 2 轮 complete 弹尽，`pytest.raises` 接住。
- **两次快照夹结论**（`test_checkpoint_survives_mid_run_crash`）：快照一（崩溃后读盘）——`turn_count==1`、messages 恰 3 条（user/tool_use/tool_result 配对完整）、无第 2 轮任何东西 = **只丢半轮**；快照二（换 natural_close 重进 run）——自然收口 = **不只存了，还真能续**。
- **各钉一个决策**：`test_final_save_covers_natural_close` 钉外壳终存（首响应即收口，全程只 1 次 before_model 存的是 `[user]`，盘上有最终回复只能来自终存）；`test_load_state_patches_dangling_tool_use` 手写 JSON 钉双悬空语义（崩溃悬空补 `[interrupted]`、待答悬空原样保留 + Interrupt 对象回装）；`test_save_load_roundtrip_preserves_all_fields` 钉五字段保真；`test_checkpointer_is_a_plain_middleware` 钉缝①独立性（不依赖外壳也工作）+ 反证两件套。

verify：`test_s7_checkpointer.py` **5 passed**，全量 **74 passed**（存量 69 零改动同绿，C4 第八次实证），src 964 行（预算 1500）。

## 五、可迁移清单：带走的不是代码，是判断

**1. durability 语义决定同步/异步，不是「持久化都该异步」。**
- 是什么：checkpoint 同步写（存完才进模型）；异步写则崩溃瞬间最近一步可能未落盘，承诺即破。
- 如何应用：任何「X 之前必须先落盘」的承诺（WAL、事务日志、checkpoint），写盘必须同步挡在 X 前面；只有「衍生数据、丢了可重建」（S6 记忆、索引、统计）才配异步旁路。
- 验收信号：能对每个持久化点回答「崩溃在这之后，承诺还成立吗」。

**2. 节奏定挂载：per-X 的事找 per-X 的钩子，没有就包外壳。**
- 是什么：S6 per-run → 外壳，S7 per-turn → 缝①，同一判据两个方向。
- 如何应用：给系统加横切能力时，先问「这件事的天然节奏是什么」，再看扩展面有没有对应节奏的钩子——有就入住，没有就在外面包一层，**不要为一个新需求改协议**。
- 验收信号：协议签名零改动；能力删掉后主流程行为不变。

**3. 用接缝的确定性行为替代真实环境事件（测试手艺）。**
- 是什么：kill -9 → 接缝抛异常；真实 Timer → background=False + flush()；真实 LLM → fixture 按序弹出。
- 如何应用：任何「真实事件不可控/不可复现」的测试（崩溃、超时、并发、网络抖动），先找系统的确定性接缝，把事件翻译成接缝上的一个可控行为。
- 验收信号：测试离线、确定、毫秒级，且断言的是真实事件会造成的同一可观察结果。

### AI PM 视角：同一批事实，另一层判断

**P1 可靠性底座：**「进程可死、任务不死」是长任务 SLA 的技术前提——部署重启/机器故障/用户关电脑不再等于任务作废。「任务可恢复性」该进 PRD 非功能需求，且要写明恢复点粒度（per-step vs per-run 直接决定用户体感）。

**P2 恢复语义是产品定义，不是工程细节：**丢半轮可不可接受、恢复后工具会不会重放副作用（聊天丢半轮无感，转账半轮重放是事故）、用户从哪继续看到什么——由产品拍板，不同场景答案不同。幂等性要求要写进工具接入规范。

**P3 选型判断：**deer-flow 证明 checkpoint 内核已被框架商品化（0% 自研）——产品价值全在胶水层（多租户/回滚/审计/TTL）。PM 的判断是「内核用库、差异化投胶水」，不为「自研持久化」立项；但要有人**读得懂内核**（本切片 84 行就是为了这个），否则胶水出问题没人会修。

## 六、拓展练习

**练习 1 · checkpoint 谱系与时间回溯（还原 deer-flow 砍掉的回滚）**：把 latest-only 单文件升级为「每轮追加一个带单调 id 的 checkpoint」，实现 `restore(path, checkpoint_id)` 回滚到任意轮。注意 deer-flow 的教训：**回滚不是删除**——恢复旧快照要铸新 id 追加，不能改写历史。
验收：跑 5 轮后回滚到第 3 轮重跑，谱系里新旧两条分支都可查。体会点：latest-only 丢掉了什么（time-travel/审计），以及「只能追加」的事件溯源思想。

**练习 2 · 崩溃注入的模糊测试**：写一个「第 N 轮崩溃」的参数化测试（N=1..5），对每个 N 断言恢复后都能跑完且无 API 配对错误——把「只丢半轮」从单点验证升级为全轮次扫描。
验收：`pytest.mark.parametrize` 全绿；构造一个「工具执行中途崩溃」（工具抛异常且异常穿透）的变体，验证悬空兜底真被触发。体会点：durability 承诺是对**每一轮**的承诺，单点测试只是抽查。

---

## 七、S7 收口结论

S7 全景 = **一个 checkpoint.py：save/load + 悬空双语义兜底 + 缝① Checkpointer + 外壳终存**，84 行，`run()`/协议零改动（C4 第八次实证 / C7 红利）。verify：5 passed，全量 74 passed，src 964 行（预算 1500）。本切片两个第一次：缝①第一次收持久化住户；**测试套件第一次由教学环反哺**——理论课上用户先设计出三测试，开发照单实现（learning-records/0016）。

第二季走到第二刀，「骨架长好后能力怎么长在外面」的图更完整了：S6 记忆（外壳，per-run）→ S7 checkpoint（缝①+外壳，per-turn）——**同是持久化，节奏不同，挂法不同**。一句话带走：**durability 不是把系统改复杂，是在正确的节奏点上、把正确的快照、同步地放到进程外面去。**

*第二季第二篇。前篇：notes/02 循环 · 03 中间件 · 04 委派 · 05 技能 · 06 长任务 · 07 记忆。*
