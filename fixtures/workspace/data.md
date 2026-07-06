# deer-flow harness 速览（研究任务语料）

- lead agent 主循环：`backend/packages/harness/deerflow/` 下约 556 行
- middleware：28 个，覆盖上下文管理 / 防御可靠性 / 记忆 / 预算
- task_tool 委派：约 533 行，subagent 独立 context 只回结论
- 本仓库目标：≤1500 行复刻以上教学核心（loop → middleware → subagent → skills → 长任务）
