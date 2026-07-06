# architecture — superagent-from-scratch

> v1 · 2026-07-04。只放拓扑与职责划分；接口契约、schema、约束全在 SPEC.md（单一事实源，此处不重复）。

## 运行时拓扑（一次 run 的完整调用链）

```
用户输入（str，可含 /skill 前缀）
  │
  ▼
skills 激活检查 ──── 命中 → SKILL.md 全文注入当轮上下文
  │
  ▼
┌─────────────────────── loop.run() ───────────────────────┐
│                                                           │
│   ┌→ ① before_model 链（注册序）                          │
│   │     Summarization / todo 提醒注入                     │
│   │                                                       │
│   │  ② llm.complete(system, messages, tools)              │
│   │     ├─ AnthropicLLM（生产）                            │
│   │     └─ FakeLLM（测试，读 fixtures/fake_llm/*.json）    │
│   │                                                       │
│   │  ③ after_model 链（逆序）                              │
│   │     Clarification 拦截 → Interrupt 收口 ──────────┐    │
│   │                                                  │    │
│   │  ④ 无 tool_use → 自然收口 ────────────────────────┤    │
│   │                                                  │    │
│   │  ⑤ 执行 tool_use（wrap_tool_call 洋葱包裹）        │    │
│   │     ToolErrorHandling ▸ ToolOutputBudget ▸ run()  │    │
│   │       ├─ bash / read_file / write_file            │    │
│   │       ├─ write_todos（改 state.todos）             │    │
│   │       └─ task ──→ 新 State + 递归调 loop.run() ──┐ │    │
│   │                    （subagent，只回最终文本）      │ │    │
│   │  ⑥ tool_result 回填 messages                    │ │    │
│   └──⑦ turn_count++，超 max_turns 熔断收口 ──────────┼─┤    │
│                                                    ▼ ▼    │
└───────────────────────────────────────────── State 返回 ──┘
  │
  ▼
goal 闭环（若 state.goal 非空）：达成判定 → 未达成注入续跑消息重进 loop
（上限 8 次 + 连续 2 次无新产出熔断）
  │
  ▼
最终答案 / Clarification 问题（带答案回填后可恢复）
```

## 模块职责表（谁负责什么，谁不准碰什么）

| 模块 | 职责 | 明确不负责 | 切片 |
|---|---|---|---|
| loop | 循环骨架 + 三种终止条件 | 任何业务逻辑、错误处理 | S1 |
| llm | LLMClient 协议 + Anthropic/Fake 两实现 | 重试、限流（middleware 的事） | S1 |
| tools | Tool 协议 + bash/read/write | 沙箱、路径虚拟化 | S1 |
| middleware | 协议 + 挂载点语义（序/逆序/洋葱） | 具体能力 | S2 |
| middlewares/* | 三内置件，每件单一关切 | 相互调用 | S2 |
| subagent | task 工具 = 新 State + 递归 loop | 线程池、事件流 | S3 |
| skills | 发现/解析/激活 | 权限过滤、安装 | S4 |
| goal + todo + clarification | 长任务三件套 | 断点持久化 | S5 |

## 三个拓扑级决策（why 见 SPEC 对应节）

1. **单循环递归，无第二引擎**：subagent 不是新执行器，是 loop 的递归调用——整个系统只有一个循环实现（SPEC #subagent）。
2. **middleware 是唯一扩展面**：loop 从 S2 起签名冻结，一切能力增量走 middleware（SPEC C4）。
3. **测试接缝只在 LLM 边界**：FakeLLM 之下全真实执行，架构图里只有 ② 一处虚实分叉（SPEC #llm）。

## 与 deer-flow 的拓扑对照（教学锚点）

| deer-flow | 本项目 | 砍掉的理由 |
|---|---|---|
| create_agent（LangChain 黑盒循环） | 手写 loop | 教学要看见循环本身 |
| 28 个 middleware | 协议 + 3 个内置件 | 每件教一类问题，全家桶是产品需求 |
| SubagentExecutor（线程池+SSE） | task = 递归 loop | 异步是前端展示需求 |
| Gateway/channels/持久化（16 万行壳） | 无 | PRD Out of Scope |
