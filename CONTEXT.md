# CONTEXT.md — superagent-from-scratch 上下文构成审计

> harness 四件套的第四件（`features.json` + 三件套 + **本文件**）。方法：7 层上下文构成 + 暗物质审计（[context-engineering-kit](https://github.com/libaoming/context-engineering-kit)）。
>
> **纪律**：写第一行 LLM 调用代码前先画本文件；改任何 system prompt / 上下文拼装代码前先读；改动后回填（防文档腐烂）。

## 核心结论（一句话）

**本项目没有「一个上下文」，有五个上下文栈**——同一个 `llm`，被多处 `llm.complete` 调用喂进五套完全不同的 `system + messages + tools`。「context 是 per-call-site 的」：别问「这个 agent 的上下文是什么」，要问「哪一次调用的上下文」。

四处调用点（grep `.complete(` 全项目）：`loop.py:63`（主 agent）、`goal.py:34`（目标评估器）、`summarization.py:38`（摘要压缩器）、`memory.py:140`（**记忆 updater**，S6 新增）；第五个栈是 subagent（`src/subagent.py` 开全新 State 递归调 `run`）。S9 的 `evals.py` **不是新调用点**——eval runner 驱动的就是栈②本身（给它喂带标签案例、量它的准确率），五栈不变。

## 一、五个上下文栈 × 七层构成

| 层 | ① 主 agent 调用<br>`loop.py:63` | ② goal 评估器<br>`goal.py:34` | ③ 摘要压缩器<br>`summarization.py:38` | ④ subagent<br>`src/subagent.py:62` | ⑤ 记忆 updater<br>`memory.py:140`（S6） |
|---|---|---|---|---|---|
| **1 system 指令** | skills 的 `system_block` + **S8 `<available-deferred-tools>` 纯名字清单**（两块都很薄——都是「目录常驻」） | `GOAL_JUDGE_PROMPT` 常量（S9 抽出——eval「单可变文件」，进化改这里、TSV 归因） | `"你是对话压缩器：把历史压成一段摘要…"` | 继承调用方传入（教学版通常 `""`） | `"你是长期记忆更新器，只输出 JSON。"` |
| **2 tools 定义** | bash / read_file / write_file / task / write_todos / ask_clarification + tool_search；**S8 起本层动态化**：每轮按 `state.promoted` 过滤，deferred 工具未晋升不提交 schema（晋升改变集合 = 破一次前缀缓存） | 空 `[]` | 空 `[]` | 全部工具 **− task**（单层委派，物理摘掉） | 空 `[]` |
| **3 few-shot 示例** | **空 ⚠️** | 空 | 空 | 空 | 空 |
| **4 消息历史** | `state.messages` 全量（含下方所有注入） | 单次拼装：目标 + 最新进展 | 待压的 `old` messages（切点避开 tool 配对） | 全新 State，仅 `prompt` 一条（隔离） | 单次拼装：旧记忆 JSON + **过滤后**对话（human + 最终 ai，`<memory>` 注入已剔） |
| **5 检索知识** | skill 正文（`/斜杠` 激活时进 user 前缀块） | 无 | 无 | 无 | 无 |
| **6 状态/记忆** | `state.todos`（渲染进历史）/ `state.goal`；**`<memory>` 注入块（S6，user 角色）** | 无 | 无 | 无（独立 State，主栈记忆不进） | 旧记忆全量（它是记忆的**生产者**） |
| **7 用户输入** | 原始 user 消息（+ skill 前缀块） | `goal` 字符串 | —（不含用户输入） | `prompt`（主对话看不到，它也看不到主对话） | —（对话是素材不是指令） |

**读法**：一列 = 一次 LLM 调用真正收到的东西。评估器/压缩器/记忆 updater 是「窄栈」（无工具、单一职责）；subagent 是「隔离栈」（全新记忆）；只有主调用是「宽栈」。记忆 updater 跑在**后台线程**（去抖后），是五栈里唯一不在对话线程上的。

## 二、暗物质审计（模型实收 ≠ 你显式写的）

模型这一轮真正收到的字节里，有一部分是自动注入 / 自动改写混进去的——不在任何一处显式 prompt 里。审计上下文必须看这些，只看 system prompt 查不出问题。

| 暗物质 | 位置 | 类型 | 模型看到什么 | 风险 / 备注 |
|---|---|---|---|---|
| 隐藏续跑消息 | `goal.py:72` | 追加 | `[目标未完成] 请继续推进…` | 模型不知这是外壳自动加的；续跑轮才有 |
| todo 提醒重注 | `todo.py:65` | 追加（每轮） | `[当前计划]\n- [status] …` | 每轮先撤旧提醒再重注，只保留一条 |
| **摘要替换真实历史** | `summarization.py:44` | **替换 ⚠️ 最危险** | `[早前对话摘要] …` + 近 K 条 | **失忆型**：模型以为读原话、实为有损压缩件，关键细节可能被压丢且不自知——线上「模型突然忘了前面说的」高发点 |
| skill 正文前缀 | `skills.py:57` | 追加 | skill 全文 + 原请求 | 含 frontmatter（description 与 system 重复注入，有意为之） |
| tool_result 回填 | `loop.py:79` | 追加 | user 角色的工具结果 | 同一响应的多个结果并入同一条 user 消息（API 硬约束） |
| **`<memory>` 记忆注入** | `memory.py:211` | 追加（run 前一次） | `<memory>\n[工作] …\n- [preference \| 0.9] …\n</memory>`（user 角色） | **跨 session 暗物质**：模型收到上轮沉淀、用户没显式写。两道防线：user 角色不升格为指令（OWASP LLM01）；`filter_messages_for_memory` 把它从喂 updater 的对话里剔掉（防自我强化） |
| **`[interrupted]` 悬空补丁** | `checkpoint.py`（load_state 兜底） | 追加（崩溃恢复时一次） | 合成的 tool_result：`[interrupted]`（配对崩溃时悬空的 tool_use） | **恢复场景专属暗物质**：模型以为工具真跑过并返回了 `[interrupted]`，实际结果从未产生。不兜会 API 400（S2 配对坑姐妹篇）；只兜崩溃悬空（interrupt 空），HITL 待答悬空留给调用方补真答案 |
| **guard 拦截合成 error**（S8） | `deferred.py`（DeferredGuard.wrap_tool_call） | 追加（未晋升直调时） | 合成的 tool_result：`[tool error] 工具 X 尚未加载…先调 tool_search` | 与 `[interrupted]` 同族（**工具从未执行**，模型以为执行了返回了 error）；差别在意图：这条是**教学式**暗物质——文案就是给模型的下一步指令（自救路径），错误设计成「教」而非「拒」 |
| **`[loop warning]` / `[budget warning]` 延迟注入**（S10） | `two_tier.py`（before_model，排队自上轮 after_model） | 追加（≥warn 时**每件**每轮至多一条；双件同挂=连续两条 user 消息，API 合法、同 todo 先例） | user 角色：`[loop warning] 最近 20 轮内相同的工具调用组合已出现 N 次…请换一种参数或策略` | 教学式暗物质第三员（同 S8 guard / `[interrupted]` 族）：文案即修复路径。**必须隔一轮注入**——after_model 当场 append 会夹进 tool_use/tool_result 配对之间（API 400，配对约束第三引爆点） |
| **`[loop stop]` / `[budget stop]` 剥 tool_use + 停机说明**（S10） | `two_tier.py`（_strip_tool_use，after_model 就地改写） | **替换（输出侧）⚠️ 新类型** | assistant 自己的消息被改写：tool_use 块被删、补一段它没说过的停机说明文本 | 此前唯一的替换型（Summarization）改的是**历史**；这条改的是**模型本轮刚说的话**——「被代言」型暗物质。转录里那段 `[loop stop]` 文本不是模型说的，是防御件替它说的；留痕的意义正在于此（可观测：用户问「为什么停了」答得上来） |
| **版本门拦截 error**（S11） | `read_before_write.py`（wrap_tool_call 拦截） | 追加（盲写/读旧版时） | 合成的 tool_result：`[tool error] 版本门拦下对 X 的写入…先用 read_file 读取当前内容再重试` | guard 家族教学式暗物质第三员（S7 `[interrupted]` / S8 DeferredGuard / 本条）：**工具从未执行**、文案即修复路径。与 S8 差异：S8 fail-closed，本件 fail-open（判据=误拦 vs 漏过哪个更贵，拍板 A） |
| **`[version-gate bypassed]` 留痕前缀**（S11） | `read_before_write.py`（fail-open 分支） | **前缀改写**（门读不了文件 / 读记录被 Budget 截断不可比时——审查红1 修复新增触发面） | 真实工具结果前被加注：`[version-gate bypassed: 门读取 X 失败（…），本次放行] ` + 真结果 | 第三种形态：不是合成整个结果（追加型）也不是替换内容（替换型），是**在真实结果上加注**——静默放行的缓解（P3 可观测），教学环反哺第四例。注意 call_next 抛异常时前缀丢失（异常穿透，ToolErrorHandling 接管——各层各管各的） |

**追加型 vs 替换型**：todo / skill / 续跑 / tool_result 都是**追加**（加东西，透明可查）；Summarization 是**替换/销毁**（模型不自知的失忆）。审计优先盯替换型。

## 三、上下文是稀缺预算 · 五个治理手段（全项目总纲）

S2-S5 砍的五刀，本质是治理「上下文窗口是稀缺预算」这一个问题的五个正交手段：

| 手段 | 切片 | 落点代码 | 治的膨胀 |
|---|---|---|---|
| **压缩** | S2 | `Summarization`（before_model 钩子） | 历史超阈值 → 压成一条摘要 |
| **截断** | S2 | `ToolOutputBudget`（wrap_tool_call 钩子） | 单个工具输出超限 → 截断 + 标注 |
| **隔离** | S3 | `TaskTool` → subagent（独立 State） | 脏活中间过程关进独立栈、只回结论 |
| **外置** | S5 | `WriteTodos` → `state.todos` | 计划移出会被压缩的历史、进结构化字段 |
| **按需注入（知识层）** | S4 | `discover_skills` / `activate` | 元数据常驻 system、正文激活才进 messages |
| **沉淀**（第二季新增） | S6 | `run_with_memory` + `MemoryQueue` | 跨 session 知识丢失 → 写路径旁路沉淀、下轮 `<memory>` 注回（时间维度：前五个治理 session 内，这个治理 session 之间） |
| **按需注入（能力层）**（第二季新增） | S8 | `deferred.py` + loop 提交点过滤 | 工具 schema 常驻成本（第 2 层）→ 名字常驻、搜索晋升才进绑定——与 S4 同范式，注入对象从知识换成能力 |
| **止损**（第三季新增） | S10 | `two_tier.py` + `loop_detection.py` / `token_budget.py` | 打转/超支的**无产出轮次**白烧窗口与钱（前七个手段治「装不下」，这个治「烧得值不值」）→ 归一化 hash/字符计费双信号，警告教自救、硬停剥 tool_use 走终止条件 1 |

## 四、已知缺口（暗物质缺口 + 教学简化）

- **few-shot 层全空**：主调用无任何样例注入——教学版不做（任务简单、零样例够用），生产版是一根未拉的杠杆（few-shot 稳定输出格式与边缘行为），按任务类型补。注意：空层是**缺席**（压根没注入），**不是暗物质**——暗物质指「模型收到了、但你没显式设计」的隐藏在场，方向相反；别把二者混为一谈。
- ~~goal 评估靠 `startswith("YES")`~~ **S9 已修**：整词判定 `\s*YES\b`（假阳性由 eval 量化实锤后修复，`evals/results.tsv` 0.8→1.0）。存留缺口：「YES 不在句首」的假阴性一侧未治（notes/10 拓展练习 2）；类型化 evaluator 仍是生产版路径（notes/06 拓展练习 1）。
- ~~无独立记忆层~~ **S6 已落地跨 session 记忆**（`src/memory.py`：6 段摘要 + facts，写路径旁路 + user 角色注回）。存留缺口：6 段只有「非空覆盖」、无主动清空通道（notes/07 拓展练习 2）；全量注入无检索（deer-flow 亦然，教学版不补）。
- **subagent 隔离无返回中间态**：只回 `_final_text`，中间过程对主栈完全不可见（隔离的代价 = 不可观测）。

## 五、维护纪律

- 改 `loop.py` 的 `system`/`messages` 拼装、`goal.py`/`summarization.py` 的 system prompt、或任何 `messages.append`/`messages[:]` 注入点 → **先读本文件对应行、改完回填**。
- 新增一个 `llm.complete` 调用点 = 新增一个上下文栈 → 在第一节表格加一列。
- 新增一处自动注入/改写 → 在第二节暗物质表加一行，标类型（追加/替换）。

---
*建于 2026-07-09（S1-S5 全绿后回填）；2026-07-10 S6 回填（第五栈记忆 updater + `<memory>` 暗物质 + 沉淀手段）；2026-07-10 S7 回填（`[interrupted]` 悬空补丁暗物质——S7 无新 llm.complete 调用点，五栈不变）；2026-07-11 S8 回填（主栈第 1 层加 deferred 名单、**第 2 层 tools 首次动态化** + guard 合成 error 暗物质 + 按需注入·能力层手段——S8 亦无新调用点，五栈不变）；2026-07-12 S9 回填（栈② system 抽成 `GOAL_JUDGE_PROMPT` 常量 + 整词判定修复入账、行号校准 loop.py:63/goal.py:34——S9 无新调用点、无新暗物质，eval runner 只是给栈②装了量表）；2026-07-13 S10 回填（警告延迟注入 + **首个输出侧替换型暗物质**「剥 tool_use 被代言」两行 + 「止损」手段行——S10 无新调用点，五栈不变）；2026-07-13 S11 回填（版本门拦截 error=guard 教学式第三员 + `[version-gate bypassed]` **前缀改写**=第三种暗物质形态——S11 无新调用点，五栈不变；注意版本门是 messages 的**消费者**而非注入者：反向扫读记录，这是暗物质表之外第一个「靠读 messages 工作」的防御件）。素材：四处 llm.complete + 十四个上下文拼装点。对应教学：teach/lessons/0006/0008/0009/0010 + reference/context-eng-exam-points.html + s6/s7/s8/eval exam-points。*
