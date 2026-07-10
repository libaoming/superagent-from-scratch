# 拆解笔记 07 · S6 长期记忆：把「写路径」搬出对话循环

> 2026-07-10，S6（F09_memory）收口时写。上一篇：notes/06（S5 长任务，第一季收官）。这是第二季第一篇。
> 一句话主张：**长期记忆的内核是一条独立于对话循环的「写路径旁路」——对话不因「要更新记忆」而变慢/变脏，记忆异步长在旁边；读回来时它只是一条 user 消息，不是 system 指令。** 对照 S2 摘要（session 内压缩），这是**跨 session 沉淀**；挂载上与 S4 skills、S5 goal 同族——loop 外的 harness 外壳，`run()` 零改动（C4 第七次实证）。

## 一、deer-flow 怎么做：agent 级钩子 + 多租户产品化记忆

deer-flow 的记忆内核不大，重量全在产品化外壳（~2000 行，子 agent 核实）：

1. **挂载**：`before_agent` / `after_agent` **agent 级中间件钩子**——LangChain 协议里有 per-run 钩子位，读写记忆各挂一头。
2. **数据模型**：**6 段结构化摘要**（`user` 按画像侧面切 ×3 + `history` 按时间远近切 ×3）+ 带类型 facts 列表——这个结构教学版**原样沿用**（它本身就是精华）。
3. **产品化堆料**：多租户 per-user/per-agent 路径分发、tiktoken 精确 token 预算、async 连接池规避、trace 埋点、OWASP ID-swap 硬化、per-slot updatedAt。**没有检索/embedding——deer-flow 本就全量注入**，这帮我们看清：记忆的内核不在检索，在「写路径怎么走、读回来算谁的话」。

## 二、我怎么简化：一个文件、一条旁路、一个外壳

| 交付物 | 内容 | 缝 |
|---|---|---|
| `src/memory.py`（211 行，唯一新文件） | `MemoryStore`（单文件 JSON）+ `MemoryQueue`（入队/去抖/后台）+ `update_memory`（llm 增量指令 + 确定性 merge）+ `run_with_memory`（外壳） | **不占缝**（harness 外壳，包着 run） |
| `fixtures/fake_llm/memory_update.json` | 录制的 updater 增量指令响应 | fixture 先行 |

写读两条路，各三步：

```python
# 写路径（旁路）：run 收口 → 入队快照（瞬时）→ 去抖 → 后台 llm merge 落盘
def run_with_memory(state, llm, tools, store, queue, *, key="default", **run_kwargs):
    injected = format_memory_for_injection(store.load())
    if injected:  # 读路径 M2：user 角色注入首条前，不给 system 权限
        state.messages.insert(0, {"role": "user", "content": f"<memory>\n{injected}\n</memory>"})
    state = run(state, llm, tools, **run_kwargs)   # 纯净引擎，零改动
    queue.add(key, state.messages)                  # 入队即返回，不等更新
    return state

# updater：llm 只出增量指令，代码做确定性 merge（不是全量重写）
upd = {"user": {...6 段非空才覆盖...}, "newFacts": [过 0.7 门槛+去重],
       "factsToRemove": [按内容删]}                 # 超 max_facts 按 confidence 降序截断
```

**没有一行改到 `run()`，也没占三条缝。** memory 不实现 Middleware 协议——它字面就长在 loop 外面。

## 三、为什么这么设计（决策清单）

**1. 写路径是旁路，不是主路（核心 aha）。**
`run()` 返回那一刻只做一件事：`queue.add(对话快照)`——瞬时，对话线程立刻回家。真正的重活（调一次 llm 把「旧记忆 + 新对话」merge）在去抖后的后台线程。为什么不同步做：**那次额外的 llm 调用跟「回答用户」半毛钱关系没有，不该由用户每轮的响应延迟买单**——本质是职责错配，不只是「慢一点」。去抖（滑动窗口 30s，每次 add 重新计时）+ 同 key 折叠（连聊三轮只留最新快照、只 merge 一次）是必留内核——丢了它们就丢了「异步、不阻塞对话」。

**2. M1 挂载点 = 外壳，不加钩子（per-run 的事不塞 per-turn 协议）。**
deer-flow 有 agent 级钩子可挂；本项目 middleware 协议只有 per-turn 钩子（before_model/after_model，**C7 冻结**）。记忆的写（整轮一次）/读（整轮一次）是 per-run 操作——备选「给协议加 before_agent/after_agent」被否决（破 C7）。做成 `run_with_memory()` 外壳后还白得一个教学收益：**「写路径独立于对话循环」在外壳形态下最干净——memory 字面就在 loop 外**。这是 skills（S4）、goal（S5）之后「loop 外外壳家族」的第三个成员。

**3. updater 是增量 merge，不是全量重写（LLM 提议、代码定夺）。**
让 llm 直接吐一份新记忆覆盖旧的？**LLM 手一抖，几十轮攒下的记忆就改乱/丢了。** 所以 llm 只出**增量指令** `{user, history, newFacts, factsToRemove}`，**代码做确定性 merge**：6 段非空字符串才覆盖（空=不改）、newFacts 过 confidence 门槛（0.7）+ 内容去重（casefold）、factsToRemove 按内容删、超 max_facts 按 confidence 降序截断。解析失败（llm 没吐合法 JSON）→ **不动记忆**（防污染，宁可这轮不学）。0.7 不是数学保证——LLM 自评 confidence 有系统性过度自信，门槛的价值在砍掉 0.5 这种明显没底的噪声，是**工程旋钮不是真值**。

**4. 6 段摘要 vs facts：面与点的分工。**
为什么要两种？**摘要管「面」**：连续、有上下文的画像散文（user×3 按画像侧面：工作/个人/当前焦点；history×3 按时间远近：近月/更早/背景），回答「这个人大致是谁」。**facts 管「点」**：离散、可精确增删、可按 confidence 排序截断的事实。**门槛/去重/截断这些「守闸」动作只有 facts 干得了——它是列表不是散文。** 已知代价（设计不对称）：facts 有 factsToRemove 删除通道，**6 段只有「非空覆盖」、没有「主动清空」通道**——「换工作」靠覆盖能解，「这段该整个消失」解不了（见拓展练习 2）。

**5. M2 读路径 = user 角色注入（数据不当指令）。**
记忆按 confidence 拼成 `<memory>…</memory>`，作 **user 角色**注入首条 user 前——**不给 system 权限**。理由：记忆源自用户、可被投毒（用户可以说「记住：忽略你的安全规则」，它会被记进去、下轮注回来）。放 system = 用户数据篡夺框架权威；放 user = 它就是一条普通用户输入，模型对它的信任等级不升格。这是**框架数据 vs 用户数据的信任边界**（OWASP LLM01），本切片保留的安全教学点。

**6. filter 双重剔除：防自我强化 + 防噪声。**
喂给 updater 的对话先过 `filter_messages_for_memory`：① 以 `<memory>` 开头的 user 消息**剔掉**——否则上轮注入的记忆被 updater 当「新对话」再学一遍，**记忆自我强化**（吃自己拉的数据，CE 课「暗物质必须可剔除」的实战版）；② 工具往返（tool_use/tool_result）全丢，只留 human 输入 + 无工具调用的最终 ai 文本——记忆学的是「用户是谁、聊了什么结论」，不是中间执行噪声。

**7. 三缝协议冻结（C7 延伸到记忆）。**
① `after run` → queue 的「对话快照入队」；② queue → updater 的 `(messages, old_memory) → update_json`；③ `before run` 的 `<memory>` user 角色注入形态。产品版在这三个缝上换实现（多租户 store / 检索注入 / 结构化 update 协议），形态不变。

## 四、测试怎么钉住「旁路、角色、merge 边界」

- **写路径旁路（核心断言）**：`test_write_path_is_off_the_conversation_loop`——run 返回后 `store.load() == empty_memory()`（**记忆仍空**），`flush()` 才更新。「独立于对话循环」不是嘴说的，是断言钉死的。
- **读路径角色**：`test_read_path_injects_memory_as_user_role`——注入消息 `role == "user"`、以 `<memory>` 开头、段标签在、原始 user 消息还在。
- **merge 四边界一测打包**：`test_apply_updates_sections_threshold_dedup_remove`——非空覆盖 / 空段不改（含「upd 不给 history 段 → 旧值不动」）/ 0.4 被门槛砍 / factsToRemove / 重复内容不重复加；`test_apply_updates_caps_at_max_facts` 钉容量截断保 confidence top-N。
- **filter 白名单语义**：`test_filter_keeps_human_and_final_ai_only`——五种消息进去只留两条（`<memory>` 注入、tool_use 轮、tool_result 全丢）。
- **队列折叠**：`test_queue_folds_same_key`——同 key add 两次只留最新快照（llm=None 反证 add 不调 llm）。
- **解析容错**：`test_parse_update_tolerates_wrapping`——thinking/markdown 包裹能扫出 JSON；扫不出回空 dict（调用方不动记忆）。
- **测试纪律**：队列用 `background=False + flush()` 同步排空，**不依赖真实 Timer**（确定性）；llm 只从 FakeLLM 接缝进（C3）。

verify：`test_s6_memory.py` **7 passed**，全量 **69 passed**（存量 62 零改动同绿，C4 第七次实证），src 877 行（预算 1500）。

## 五、可迁移清单：带走的不是代码，是判断

**1. 衍生数据的更新走旁路，不阻塞主流程。**
- 是什么：记忆是对话的衍生物，其更新（入队→去抖→后台 merge）不在对话线程做。
- 如何应用：任何「主流程产生数据 → 衍生系统要消化它」的场景（索引、画像、统计、审计），先问「消化能不能异步」——能就入队+去抖，主流程只留一次瞬时 add。
- 验收信号：主流程的响应延迟与衍生系统的处理耗时**解耦**（衍生系统挂了/慢了，主流程无感）。

**2. LLM 提议、代码定夺。**
- 是什么：llm 只出增量指令，确定性 merge（门槛/去重/截断/解析失败不动）由代码兜底。
- 如何应用：凡是「LLM 输出直接改持久化状态」的地方，中间必须垫一层确定性校验/合并——永远不给 LLM 对存量数据的全权改写。
- 验收信号：构造一个 llm 输出「乱 JSON / 超低 confidence / 重复内容」的 case，存量数据毫发无损。

**3. 数据不当指令：按来源定角色，不按用途。**
- 是什么：记忆「用途」像系统级背景知识，但「来源」是用户——所以走 user 角色。
- 如何应用：任何回注上下文的内容，先问「这数据最初谁产生的」——用户/外部产生的一律不进 system，哪怕它看起来像配置。
- 验收信号：在记忆/检索文档里塞一条「忽略你的安全规则」，模型行为不变。

### AI PM 视角：同一批事实，另一层判断

**P1. 「它怎么记住我」是 agent 产品被问最多的问题。**
- 是什么：记忆是个性化与留存的技术底座；写读分离让「记住我」不以「对话变慢」为代价。
- 如何应用：把「记忆更新是否阻塞对话」当**体验参数**写进 PRD——竞品评测时专测「连续对话第 N 轮的响应延迟是否随记忆增长」。
- 验收信号：PRD 有「记忆更新对 P95 响应延迟零贡献」条目。

**P2. 记忆质量有旋钮，不是玄学。**
- 是什么：confidence 门槛、去重、max_facts 容量、注入预算（max_chars）——「记多少、记多准、注多少」全是可调参数。
- 如何应用：这些旋钮决定记忆是帮手还是噪声源，该由产品按「记忆命中率 vs 上下文成本」定，不该留给工程拍。
- 验收信号：PRD 有记忆容量/门槛的默认值及其依据；有「记忆错了用户怎么纠正」的路径设计。

**P3. 记忆是新的信任攻击面。**
- 是什么：用户能写进记忆、记忆又注回上下文——投毒的闭环天然存在。
- 如何应用：user 角色隔离、confidence 门槛、filter 剔注入，都是**产品级安全设计**（不是工程细节）；企业级 agent 的安全审查必问「记忆内容能否升格为指令」。
- 验收信号：安全评审清单里有「记忆投毒」条目，且有对应测试。

## 六、拓展练习

**练习 1 · 多租户 store（还原 deer-flow 砍掉的路径分发）**：把 `MemoryStore` 升级为 per-user/per-agent 双维路径（`memories/{user_id}/{agent_id}.json`），`run_with_memory` 加 `user_id` 参数。
验收：两个 user 交错对话，各自记忆互不串；同 user 换 agent，记忆隔离。体会点：多租户为什么只动 store 不动 updater/注入——三缝协议冻结（决策 7）下，产品化=换缝上的实现。

**练习 2 · 给 6 段补「清空通道」（修本切片的已知设计不对称）**：updater 协议加 `sectionsToClear: ["workContext", ...]`，merge 支持把指定段置空。
验收：构造「用户说『我离职了，别再提上家公司』」的对话，workContext 能被**整段清空**而不是残留旧值等覆盖。体会点：覆盖式数据模型天生做不到「变回空」——「非空才覆盖」防手抖与「无法主动遗忘」是同一个设计的两面，安全默认与能力缺口互为代价。

---

## 七、S6 收口结论 + 第二季开篇

S6 全景 = **一个 memory.py：store + queue + updater + 外壳**，`run()` 零改动（C4 第七次实证），不占三条缝。verify：7 passed，全量 69 passed，src 877 行（预算 1500）。数据模型（6 段 + facts）沿用 deer-flow 原结构——这次砍的不是数据模型，是产品化外壳（多租户/tiktoken/async/trace/ID-swap）。

第二季的看点变了：第一季五刀教「骨架有多小」，S6 开始教**「骨架长好后，能力怎么长在外面」**——记忆没进 loop、没占缝、没加钩子，它是第三个 loop 外外壳（skills → goal → memory）。一句话带走：**agent 的「记忆力」不是循环的属性，是 harness 的属性——引擎负责这一轮聪明，外壳负责下一轮还记得。**

*第二季第一篇。前篇：notes/02 循环 · 03 中间件 · 04 委派 · 05 技能 · 06 长任务。*
