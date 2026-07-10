# CONTEXT.md — superagent-from-scratch 上下文构成审计

> harness 四件套的第四件（`features.json` + 三件套 + **本文件**）。方法：7 层上下文构成 + 暗物质审计（[context-engineering-kit](https://github.com/libaoming/context-engineering-kit)）。
>
> **纪律**：写第一行 LLM 调用代码前先画本文件；改任何 system prompt / 上下文拼装代码前先读；改动后回填（防文档腐烂）。

## 核心结论（一句话）

**本项目没有「一个上下文」，有五个上下文栈**——同一个 `llm`，被多处 `llm.complete` 调用喂进五套完全不同的 `system + messages + tools`。「context 是 per-call-site 的」：别问「这个 agent 的上下文是什么」，要问「哪一次调用的上下文」。

四处调用点（grep `.complete(` 全项目）：`loop.py:59`（主 agent）、`goal.py:28`（目标评估器）、`summarization.py:38`（摘要压缩器）、`memory.py:140`（**记忆 updater**，S6 新增）；第五个栈是 subagent（`src/subagent.py` 开全新 State 递归调 `run`）。

## 一、五个上下文栈 × 七层构成

| 层 | ① 主 agent 调用<br>`loop.py:59` | ② goal 评估器<br>`goal.py:28` | ③ 摘要压缩器<br>`summarization.py:38` | ④ subagent<br>`src/subagent.py:62` | ⑤ 记忆 updater<br>`memory.py:140`（S6） |
|---|---|---|---|---|---|
| **1 system 指令** | skills 的 `system_block`（可用技能清单，很薄） | `"你是目标验收器：只回 YES 或 NO…"` | `"你是对话压缩器：把历史压成一段摘要…"` | 继承调用方传入（教学版通常 `""`） | `"你是长期记忆更新器，只输出 JSON。"` |
| **2 tools 定义** | bash / read_file / write_file / task / write_todos / ask_clarification | 空 `[]` | 空 `[]` | 全部工具 **− task**（单层委派，物理摘掉） | 空 `[]` |
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

**追加型 vs 替换型**：todo / skill / 续跑 / tool_result 都是**追加**（加东西，透明可查）；Summarization 是**替换/销毁**（模型不自知的失忆）。审计优先盯替换型。

## 三、上下文是稀缺预算 · 五个治理手段（全项目总纲）

S2-S5 砍的五刀，本质是治理「上下文窗口是稀缺预算」这一个问题的五个正交手段：

| 手段 | 切片 | 落点代码 | 治的膨胀 |
|---|---|---|---|
| **压缩** | S2 | `Summarization`（before_model 钩子） | 历史超阈值 → 压成一条摘要 |
| **截断** | S2 | `ToolOutputBudget`（wrap_tool_call 钩子） | 单个工具输出超限 → 截断 + 标注 |
| **隔离** | S3 | `TaskTool` → subagent（独立 State） | 脏活中间过程关进独立栈、只回结论 |
| **外置** | S5 | `WriteTodos` → `state.todos` | 计划移出会被压缩的历史、进结构化字段 |
| **按需注入** | S4 | `discover_skills` / `activate` | 元数据常驻 system、正文激活才进 messages |
| **沉淀**（第二季新增） | S6 | `run_with_memory` + `MemoryQueue` | 跨 session 知识丢失 → 写路径旁路沉淀、下轮 `<memory>` 注回（时间维度：前五个治理 session 内，这个治理 session 之间） |

## 四、已知缺口（暗物质缺口 + 教学简化）

- **few-shot 层全空**：主调用无任何样例注入——教学版不做（任务简单、零样例够用），生产版是一根未拉的杠杆（few-shot 稳定输出格式与边缘行为），按任务类型补。注意：空层是**缺席**（压根没注入），**不是暗物质**——暗物质指「模型收到了、但你没显式设计」的隐藏在场，方向相反；别把二者混为一谈。
- **goal 评估靠 `startswith("YES")`**：对「YESTERDAY 已完成」会假阳性早停（`goal.py`），教学简化；生产版走类型化 evaluator（notes/06 拓展练习 1）。
- ~~无独立记忆层~~ **S6 已落地跨 session 记忆**（`src/memory.py`：6 段摘要 + facts，写路径旁路 + user 角色注回）。存留缺口：6 段只有「非空覆盖」、无主动清空通道（notes/07 拓展练习 2）；全量注入无检索（deer-flow 亦然，教学版不补）。
- **subagent 隔离无返回中间态**：只回 `_final_text`，中间过程对主栈完全不可见（隔离的代价 = 不可观测）。

## 五、维护纪律

- 改 `loop.py` 的 `system`/`messages` 拼装、`goal.py`/`summarization.py` 的 system prompt、或任何 `messages.append`/`messages[:]` 注入点 → **先读本文件对应行、改完回填**。
- 新增一个 `llm.complete` 调用点 = 新增一个上下文栈 → 在第一节表格加一列。
- 新增一处自动注入/改写 → 在第二节暗物质表加一行，标类型（追加/替换）。

---
*建于 2026-07-09（S1-S5 全绿后回填）；2026-07-10 S6 回填（第五栈记忆 updater + `<memory>` 暗物质 + 沉淀手段）。素材：四处 llm.complete + 八个上下文拼装点。对应教学：teach/lessons/0006/0008 + reference/context-eng-exam-points.html + s6-memory-exam-points.html。*
