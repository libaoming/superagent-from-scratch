# superagent-from-scratch

**两千行内、零框架、教学优先的现代 SuperAgent harness 复刻**——从 [bytedance/deer-flow](https://github.com/bytedance/deer-flow)（★76k）的心脏蒸馏而来，一个下午能读完。

[English README](README.md) · 拆解笔记见 [`notes/`](notes/)

> ✅ **第一季五刀完工（tag `sfs-s1` … `sfs-s5`），续刀已至 S11**（tag `sfs-s11`）——13/17 feature passing，**122 条离线测试全绿**，`src/` **约 1,650 行**（预算 ≤1,900）。每个切片交付时都带可离线跑的测试 + 一篇 why 先行的拆解笔记。

## 为什么做这个

2026 年想真正搞懂「通用 agent 是怎么工作的」，市场两头都够不着：

- **头部开源项目学不动**：deer-flow 的 backend 18.5 万行，agent 核心（约 2,300 行）埋在产品壳里——gateway、IM 渠道、多租户、持久化。想读懂心脏，先在 16 万行产品工程里挖三天。
- **教程又太浅**：大多停在「调一次 function calling」，够不着真正难的部分——上下文管理、防御 middleware、子 agent 隔离、目标闭环。这些恰恰是生产级 agent 与 demo 的分水岭。
- **框架遮蔽本质**：主流实现把循环外包给 LangChain/LangGraph，你看到的是 `create_agent(...)` 一行黑盒，看不到 `messages → LLM → tools → append` 的循环本身。

本仓库把 deer-flow 约 2,300 行的心脏重写成 **≤1,900 行零依赖 Python**（运行时依赖仅 `anthropic` + `pyyaml`），按切片线性展开，每片配离线测试 + 一篇讲 why 的拆解笔记。第一季五刀搭出骨架，之后继续往 harness 深水区切：记忆、持久化、deferred tools、eval 闭环、防御件家族。

## 架构

2026 年通用 agent 的共识形态——与 Claude Code 同构，deer-flow 为此推倒重写了自己：

```
                ┌─────────────────────────────────────────────┐
                │             lead agent loop（S1）           │
                │  messages → LLM → tool_calls → 执行 → append │
                │  终止：自然收口 / turn 熔断 / 中断信号        │
                └──────┬──────────────────┬───────────────────┘
                       │                  │
        ┌──────────────┴───────┐   ┌──────┴──────────────────────┐
        │ middleware 管线      │   │ 工具                        │
        │（S2）                │   │  bash / read_file /         │
        │  before_model        │   │  write_file（S1）           │
        │  after_model         │   │  task → subagent 独立上下文  │
        │  wrap_tool_call      │   │  只回结论（S3）             │
        │  · 输出限额          │   │  write_todos（S5）          │
        │  · 错误恢复          │   │  ask_clarification（S5）    │
        │  · 上下文摘要        │   │                             │
        └──────────────────────┘   └─────────────────────────────┘
                       │
        ┌──────────────┴──────────────────────────────┐
        │ skills（S4）：SKILL.md 发现 →               │
        │ 元数据常驻、正文 /斜杠 激活按需加载          │
        ├─────────────────────────────────────────────┤
        │ 长任务（S5）：计划外置到 todos +            │
        │ goal 续跑闭环（带熔断）+ HITL 中断/恢复      │
        └─────────────────────────────────────────────┘
```

## 第一季 · 五个切片

线性推进——每个切片都是一课，自带测试与笔记：

| 切片 | 构建什么 | 学到什么 | 状态 |
|---|---|---|---|
| **S1** | agent 循环 + LLM 接缝 + 3 个真实工具 | agent 就是一个 while 循环。终止条件只有三种。为什么 `tool_result` 要以 `user` 角色回填。 | ✅ 完成（[笔记](notes/02-s1-agent-loop.md)，tag `sfs-s1`）|
| **S2** | middleware 协议（`before_model` / `after_model` / `wrap_tool_call`）+ 3 个内置件 | 横切关注点与循环解耦——现代 harness 的真架构。输出限额、错误恢复、上下文摘要。 | ✅ 完成（[笔记](notes/03-s2-middleware.md)，tag `sfs-s2`）|
| **S3** | `task` 工具 + subagent 委派 | 上下文隔离是长任务的命根。subagent 不是新机制——是同一个循环的递归调用 + 全新上下文，只回结论。 | ✅ 完成（[笔记](notes/04-s3-subagent.md)，tag `sfs-s3`）|
| **S4** | skills 系统（SKILL.md + 斜杠激活） | 能力热插拔的 token 经济学：元数据便宜（常驻）、正文贵（按需）。 | ✅ 完成（[笔记](notes/05-s4-skills.md)，tag `sfs-s4`）|
| **S5** | `write_todos` + goal 续跑 + `ask_clarification` HITL | 「long-horizon」不是模型变长——是 harness 在模型外面套的目标闭环，带熔断。中断 = 保存现场的正常收口。 | ✅ 完成（[笔记](notes/06-s5-long-task.md)，tag `sfs-s5`）|

## 续刀 · 深水区（S6 起，持续构建中）

五刀骨架收官后，继续切 harness 真正难的部分——每刀仍是「测试 + 笔记 + tag」三件套：

| 切片 | 主题与一句话主张 | 状态 |
|---|---|---|
| **S6** | 长期记忆——写路径是对话循环外的旁路，跨 session 沉淀，读回来只是一条 user 消息 | ✅ 完成（[笔记](notes/07-s6-memory.md)，tag `sfs-s6`）|
| **S7** | 断点持久化——per-step durability，进程可死、任务不死；恢复 = 载入 + 补消息 + 重进同一个 `run()` | ✅ 完成（[笔记](notes/08-s7-checkpointer.md)，tag `sfs-s7`）|
| **S8** | deferred tools——能力也按需注入：未加载只见名字，搜索命中才晋升出完整 schema | ✅ 完成（[笔记](notes/09-s8-deferred-tools.md)，tag `sfs-s8`）|
| **S9** | eval 闭环——把「judge 好不好」变成一个能涨的数 | 🚧 收口中（[笔记](notes/10-s9-eval-loop.md)已出）|
| **S10** | 防打转 + 预算闸——agent 最贵的失败不是崩溃，是打转 | ✅ 完成（[笔记](notes/11-s10-loop-detection.md)，tag `sfs-s10`）|
| **S11** | 写前版本门——状态寄生在 messages 上的确定性防御 | ✅ 完成（[笔记](notes/12-s11-read-before-write.md)，tag `sfs-s11`）|
| **S12–S13** | 执行安全三道门 + 安全截断（非空 tool_calls ≠ 完整意图） | 🚧 进行中 |

## deer-flow 对照

每一处砍削都留有升级路径（见 `SPEC.md` 的「产品版/教学版全景对照」）。**砍什么本身就是课程**：

| 能力域 | deer-flow（产品版） | 本仓库（教学版） |
|---|---|---|
| 循环引擎 | LangChain `create_agent`（黑盒） | 手写 `run()`，~50 行，完全可见 |
| 上下文管理 | Summarization + DurableContext + TokenBudget + 输出限额 | Summarization + ToolOutputBudget + TokenBudget |
| 防御 middleware | LoopDetection / ReadBeforeWrite / DanglingToolCall / Safety… | ToolErrorHandling + LoopDetection + TwoTierGuard + ReadBeforeWrite（逐刀补齐中，Safety 收口中） |
| 多模型 | ModelFactory + vLLM/thinking/vision 适配 | `LLMClient` 协议：Anthropic + FakeLLM + CLI 适配器 |
| 工具沙箱 | 虚拟路径映射 + Docker sandbox | 裸 subprocess，60s 超时 |
| subagent 执行器 | 线程池 + SSE 事件流 | 同步递归调同一个循环 |
| 产品壳 | gateway / IM 渠道 / 多租户 / tracing / TUI | 无——那是 18.5 万行里的 16 万行，且不是 agent 本身 |

## 快速开始

```bash
git clone https://github.com/libaoming/superagent-from-scratch.git
cd superagent-from-scratch
uv sync
uv run pytest -q   # 全程离线——无需 API key、无需网络
```

所有测试跑在**录制的 LLM fixture**（`fixtures/fake_llm/*.json`）上：唯一测试接缝是 `LLMClient` 协议，其余一切——文件系统、subprocess——真实执行。永不 `mock.patch`。

## 仓库地图

```
src/            实现（预算：总计 ≤1,900 行）
tests/          每切片一组测试，全部离线
fixtures/       录制的 LLM 响应序列 + 文件操作沙盘
notes/          拆解笔记（中文）：deer-flow 怎么做 →
                本仓库怎么简化 → 为什么 → 拓展练习
PRD.md          项目为什么存在、为谁存在
SPEC.md         每个设计决策的 why 与 deer-flow 对照
features.json   切片/feature 状态的单一事实源
```

## 教学纪律（硬约束，不是愿景）

- **src/ ≤ 1,900 行**——超了说明在复刻产品功能而非教学核心，`wc -l` 可查。
- **测试全离线**——缺 API key 永远不阻塞 `pytest`。
- **fixture 先行**——fixture 是入库可 review 的数据，不是 mock。
- **不复制代码**——deer-flow 是只读教材，全部理解后重写（License 干净的 MIT）。
- **每切片必有笔记**——只有代码没有拆解笔记不算完成。

## License

[MIT](LICENSE)
