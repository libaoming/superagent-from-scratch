# PRD — superagent-from-scratch

> v1 · 2026-07-04 · owner: libaoming
> 定位一句话：**千行级、零框架、中文精讲的 SuperAgent harness 教学复刻**——学的人跑得通，看的人讲得清。

## 背景与动机

### 问题陈述（用户视角）

想真正搞懂「通用 agent 是怎么工作的」的人，2026 年面对的是一个两头够不着的市场：

- **头部开源项目学不动**：deer-flow（★76k）backend 18.5 万行，agent 核心埋在产品壳（gateway/IM 渠道/多租户/持久化）里；OpenManus（★57k）架构停在 2025 年的编排式，学完就过时。想读懂「心脏」，先得在 16 万行产品工程里挖三天。
- **教程又太浅**：市面的 agent 教程停在「调一次 function calling」，不覆盖真正难的部分——上下文管理、防御机制、子 agent 隔离、目标闭环。这些恰恰是生产级 agent 与 demo 的分水岭，也是 deer-flow 用 28 个 middleware 才解决掉的问题。
- **框架遮蔽本质**：主流实现把循环外包给 LangChain/LangGraph，学习者看到的是 `create_agent(...)` 一行黑盒，看不到 messages→LLM→tool→append 的循环本身。

一句话：**没有一个「能在一个下午读完、每行都讲得清为什么」的现代 SuperAgent 参考实现**。

### 方案概述（用户视角）

把 deer-flow 的心脏（约 2,300 行）重写成 ≤1,500 行的零依赖 Python 实现，按「loop → middleware → subagent → skills → 长任务」五个切片线性展开，每个切片配：可离线跑的测试（fake-LLM fixture）+ 一篇中文拆解笔记（学到什么/怎么简化的/为什么）。读者克隆下来 `uv run pytest` 全绿，然后从 S1 开始逐片读代码 + 笔记，读完能独立复述 2026 年通用 agent 的标准架构。

## 目标用户

| 用户 | 场景 | 他要的 |
|---|---|---|
| **P0 学习者**（工程师/转型 AI 的开发者） | 想搞懂 agent 内核，被大项目劝退过 | 小而全的可跑参考实现 + 讲 why 的笔记 |
| **P1 AI PM / 面试官** | 评估候选人或自学 agent 产品力 | 「harness 是产品力」的具象证据：每个 middleware 对应什么事故 |
| **P2 作者本人** | 边学边开源 + Agent PM 面试作品 | 亲手写过一遍的架构体感 + 公开可查的工程纪律证据 |

> 优先级冲突时以 P0 为准：**教学清晰 > 功能完备 > 工程优雅**。

## User Stories

每条 1:1 对应 features.json 的一个 feature，「以便」即验收信号来源。

1. 作为学习者，我想要一个不依赖任何框架的 agent 循环（messages→LLM→tool_calls→执行→append→收口），以便在一个文件里看懂 agent 的本质。（→ F01_agent_loop）
2. 作为学习者，我想要 bash/read_file/write_file 三个真实工具从 schema 声明到结果回填的完整链路，以便理解工具调用的完整契约而不是黑盒。（→ F02_real_tools）
3. 作为学习者，我想要一个 before_model/after_model/wrap_tool_call 的 middleware 协议，以便理解「横切关注点与循环解耦」为什么是现代 harness 的真架构。（→ F03_middleware_protocol）
4. 作为学习者，我想要输出限额/错误恢复/上下文摘要三个内置 middleware 的最小实现，以便看到生产级可靠性问题各自的标准解法。（→ F04_core_middlewares）
5. 作为学习者，我想要 task 工具把子任务派给独立上下文的 subagent 且主对话只收结论，以便理解上下文隔离为什么是长任务的命根。（→ F05_task_subagent）
6. 作为学习者，我想要 SKILL.md 发现→解析→元数据常驻→斜杠激活加载全文的完整技能系统，以便理解「能力热插拔」的 token 经济学。（→ F06_skills）
7. 作为学习者，我想要 write_todos 计划外置 + goal 未达成自动续跑（带熔断），以便理解 long-horizon 是 harness 套的目标闭环而非模型变长。（→ F07_todo_goal）
8. 作为学习者，我想要 ask_clarification 中断循环等用户输入后恢复，以便理解 HITL 在自主循环里的挂载点。（→ F08_clarification_hitl）
9. 作为 P1/P2 读者，我想要每个切片配套的拆解笔记（deer-flow 怎么做→我怎么简化→为什么），以便不读代码也能吸收架构判断。（→ 每切片交付物，验收见下）

## 成功指标

- **北极星**：一个没读过 deer-flow 的工程师，clone 后一个下午内 pytest 全绿 + 能对照笔记复述五层架构。（发布前找 1-2 人实测替代）
- 代理指标（不作承诺，仅观察）：GitHub star/fork、橙研所系列文章阅读、面试中被追问的深度。
- 反指标：src/ 超 1,500 行、任何切片「有代码没笔记」、测试需要真实 API key 才能跑——出现即偏航。

## 技术约束

- Python 3.12 + uv + pytest；运行时第三方依赖**仅 LLM SDK（anthropic）+ pyyaml**（frontmatter 解析）；禁 LangChain/LangGraph/litellm。
- LLM 接口做薄抽象层，fake-LLM 与真实 API 可互换（同一接口）。
- 全部测试离线可跑（fixture 驱动）；真实 API 只做切片收口 E2E（手动触发）。
- 双语开源：README.md 英文主 + README.zh-CN.md；notes/ 笔记中文。MIT License。
- 参考蓝本 `bytenance/deer-flow` 本地浅 clone 只读，理解重写，不复制代码。

## 测试策略 / 验证接缝

**单一接缝：LLM 客户端接口**（唯一注入点）。`FakeLLM` 读取 fixture（录制的响应序列 JSON），按序返回给 loop；除此之外全链路真实执行（真实文件系统、真实 subprocess）。不 patch loop 内部、不 mock 工具——工具行为本身就是被测物。

- 每切片一组 `tests/test_s{n}_*.py`，fixture 放 `fixtures/fake_llm/`（响应序列）+ `fixtures/workspace/`（文件操作沙盘）+ `fixtures/skills/`（示例技能）。
- fixture 先于代码：verify 引用的 fixture 不存在就先造。
- 这一节直接喂 features.json 的 `verify` 字段（8 个 feature 均为 `uv run pytest tests/test_s*.py -q`）。

## 验收标准

1. `uv run pytest -q` 全绿，全程无网络、无 API key。
2. `wc -l src/**/*.py` 总数 ≤ 1,500。
3. 五个切片各有 git tag（sfs-s1..s5）+ notes/ 对应笔记。
4. S1 收口的真实模型 E2E 走 `claude -p` 通道（2026-07-04 拍板 · Q4=B：暂无独立 API key，吃订阅额度）：`scripts/e2e_s1.py` 内置一个薄 `ClaudeCLILLM` 适配器（subprocess 调 claude -p，实现同一 LLMClient 协议——顺带证明接缝可换第三实现），完成一个研究任务（多轮工具调用→最终答案）。脚本放 scripts/ 不占 src 行数预算；`AnthropicLLM` 照常实现并标「需 ANTHROPIC_API_KEY」，拿到 key 后可直跑。
5. README（双语）含：架构图、五切片导读、与 deer-flow 的对照表、每切片的「学到什么」。

## Out of Scope（范围外）

PRD 级全局边界（feature 级 out_of_scope 与此呼应）。**范围外 ≠ 视野外**：每个被砍的产品关切都在 SPEC「产品版/教学版全景对照」（#product-vs-teaching）留有升级路径与拓展练习——不进主干代码，但进文档与练习，读者学完应能说出「长成产品版还差什么、从哪下手」。

- **产品壳一律不做**：Web UI、gateway/REST API、IM 渠道、多租户、鉴权、持久化/checkpoint、Docker sandbox、tracing/可观测、TUI。
- **不追新**：不跟 deer-flow 上游更新，蓝本按 2026-07 快照拆解。
- **不做通用框架**：不发 PyPI 包、不设计扩展点给别人用——这是教材不是框架。
- **不做多模型适配**：只接 Anthropic API（教学重点在 harness 不在 provider 适配）。

## 里程碑

- **M1（本期全部）**：S1–S5 五切片 + 双语 README + 5 篇笔记 + GitHub 公开发布。里程碑内切片线性推进，S1 完成即可先行开源（边学边发）。

## 补充说明

- 笔记同步作为橙研所「Manus 开源复刻众生相」系列底稿；repo 与 harness-kit / agent-memory-kit / agent-design-course 互链。
- **笔记标准结构**（Story 9 的交付定义）：deer-flow 怎么做 → 我怎么简化 → 为什么 → **产品化拓展练习 1–2 道**（思路 + 验收标准，不给实现；取材自 SPEC 全景对照表的拓展路径列）。
- 命名：git tag 前缀 `sfs-`；分支 main 单线。
