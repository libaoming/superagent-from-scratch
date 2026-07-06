# 拆解笔记 01 · deer-flow 的 harness 长什么样

> 侦察日期 2026-07-04，基于 bytedance/deer-flow 浅 clone（★76,028）。本篇是复刻项目的架构地图，也是橙研所拆解系列的底稿。

## 一、先纠正一个过时印象

搜「deer-flow 架构」，中文互联网上的资料大多还停留在 2025 年初的版本：planner → researcher → coder → reporter 的**静态编排图**（LangGraph 节点图，前身 langmanus）。

2026 年的 deer-flow 已经完全不是这个形状。它收敛成了 **Claude Code 同构**：

- 没有固定的 planner-executor 图了。取而代之的是**一个 lead agent + 一条 middleware 流水线**，规划能力退化成一个 `write_todos` 工具（TodoMiddleware，plan mode 下挂载）
- 多 agent 不再是静态图上的节点，而是 **`task` 工具动态委派**——lead agent 觉得需要就派一个 subagent 出去，跑完只回结论（并发上限 3，默认超时 30 分钟，max_turns 150）
- **Skills 系统**：`SKILL.md` + YAML frontmatter + `/skill-name` 斜杠激活——就是 Claude Code skills 的开源同构
- 记忆、沙箱、上下文摘要、澄清中断，全部以 middleware 形式挂在同一条链上

这个转变本身就是最大的行业信号：**通用 agent 的架构共识已经收敛**。2025 年大家还在争论「工作流编排 vs 自主循环」，2026 年字节用行动投了票——把自家 4.6 万 star 的编排式架构推倒，重写成 Claude Code 形态，并直接把核心包命名为 `deerflow-harness`。

## 二、规模分层：产品的壳很大，心脏很小

实测（cloc 级粗统计，find + wc）：

| 层 | 规模 | 内容 |
|---|---|---|
| backend 全部 | 692 个 py 文件 / 18.5 万行 | 含 gateway、IM channels（飞书/Slack/Telegram/钉钉/Discord/微信）、持久化、鉴权、TUI |
| harness 核心包 | 284 个文件 / 5.2 万行 | `packages/harness/deerflow/`，可独立发布的 agent 框架 |
| 真正的心脏 | ~2,300 行 | lead_agent/agent.py 556 + prompt.py 836 + factory.py 389 + task_tool.py 533 |

对复刻者的启示：**18.5 万行里有 16 万行是产品工程（多租户、多渠道、可观测、迁移），不是 agent 本身**。教学复刻只需要抄心脏——这就是本项目「千行级预算」的依据。

## 三、真正的架构：middleware 流水线

`make_lead_agent` 做的事一句话能说完：`create_agent(model, tools, middleware=[...28 个], system_prompt, state)`。**所有复杂度都在那 28 个 middleware 里**。挑最有含金量的几个：

### 上下文管理三件套（防 context 爆炸）
- **SummarizationMiddleware**：接近 token 上限时压缩旧消息
- **DurableContextMiddleware**：在摘要压掉历史**之前**，把「task 委派记录 + 已加载的 skill 引用」抢救进 ThreadState 的独立通道，再逐请求投影回模型——保证压缩后 agent 仍知道「我派过什么活、开了什么技能」
- **ToolOutputBudgetMiddleware**：工具输出进上下文前先限额截断

### 防御三件套（防 agent 自伤）
- **LoopDetectionMiddleware**：检测重复工具调用循环，硬停时连结构化 tool_calls 带原始 provider 元数据一起清掉，强制出文字答案
- **ReadBeforeWriteMiddleware**：文件写入的版本门——`read_file` 时在 ToolMessage 上盖内容 hash 章，`write_file`/`str_replace` 必须持有匹配当前文件 hash 的最新章才放行；摘要把读取记录压掉后章自动失效，逼 agent 重读再写（防并发写、防基于过期内容的覆盖）
- **DanglingToolCallMiddleware**：用户打断导致 tool_call 没有对应 ToolMessage 时补占位，防下一轮模型看到断链历史直接报错

### 工程细节（prefix cache 意识）
- **DynamicContextMiddleware**：当前日期/记忆不进 system prompt，而是作为 `<system-reminder>` 注进第一条用户消息——**保持 system prompt 完全静态，吃 prefix cache**
- **SystemMessageCoalescingMiddleware**：把散落的 SystemMessage 合并成开头一条，兼容 vLLM/Qwen/Anthropic 等严格后端

这个清单本身就是一份「生产级 agent 你会踩的坑」目录——每个 middleware 都对应一次真实事故。

## 四、subagent：上下文隔离的标准解

`task_tool.py`（533 行）+ `subagents/executor.py`。机制：

1. lead agent 调 `task(description, prompt, subagent_type)`
2. executor 给 subagent 开**全新的 ThreadState**（独立 messages，checkpointer=False，一次性不续跑）
3. subagent 用几乎同一条 middleware 链（`build_subagent_runtime_middlewares` 复用共享基座）
4. 跑完只把最终结论作为 ToolMessage 回填主对话；中间过程走独立事件通道（`subagent.start/step/end`）供 UI 展开查看，**不进主上下文**

主 agent 的上下文洁净靠这个机制保证。这和我在 Claude Code 里被要求遵守的「L4 上下文隔离纪律」是同一件事的两侧：平台提供机制（task 工具），使用者遵守纪律（脏活外包）。

## 五、还有一个别处没有的：goal 续跑

Gateway 层（不在 harness 包里）有个 goal 机制：给 thread 设一个目标，每轮可见回合结束后用一个 evaluator 判定「目标达成没有」——没达成且可继续，就注入**隐藏的续跑消息**让 agent 接着干，上限 8 次，带「连续 2 次无新可见产出」的熔断器。

这是「long-horizon」三个字的实际落地：不是模型自己变长了，而是 harness 在外面套了一层**目标闭环**。复刻切片 S5 的核心就是它。

## 六、复刻映射：S1-S5 怎么来的

| 切片 | 对应 deer-flow 模块 | 教学要点 |
|---|---|---|
| S1 loop | create_agent 的内核循环 | messages→LLM→tool_calls→执行→append，一个 while 循环讲清 agent 本质 |
| S2 middleware | 28 条链中抽 3 条（输出限额/错误恢复/摘要） | 横切关注点与 loop 解耦，架构的灵魂 |
| S3 subagent | task_tool + executor | 上下文隔离为什么是长任务的命根 |
| S4 skills | skills/ + SkillActivationMiddleware | 能力的热插拔：元数据常驻、正文按需 |
| S5 长任务 | TodoMiddleware + goal 续跑 + ClarificationMiddleware | 计划外置、目标闭环、人机中断 |

砍掉的（out of scope，防复刻产品功能）：gateway/channels/持久化/多租户/sandbox 容器化/tracing/TUI——全是产品壳，不是 harness 心脏。

## 七、给面试叙事的三句话

1. **架构收敛**：2026 年通用 agent 的事实标准是「lead agent + middleware 管线 + task 委派 + skills」，deer-flow 用一次推倒重写为此背书——聊 WorkBuddy（同形态）和智谱 GLM-5「Agentic Engineering」都从这里切入
2. **harness 是产品力**：模型之上、产品之下的这一层（上下文管理/防御/目标闭环）才是 agent 产品的差异化所在，18.5w:0.23w 的壳心比说明工程量在哪
3. **每个 middleware = 一次事故复盘**：ReadBeforeWrite、LoopDetection、DanglingToolCall……这份清单是 PM 理解「agent 可靠性」的最好教材

---
*下一篇：notes/02 —— S1 复刻实录：一个 while 循环里的 agent 本质*
