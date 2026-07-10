# fixtures 索引

verify 引用的 fixture 都在此。**fixture 先于代码**：feature 的 verify 指向的 fixture 不存在 → 先造，不许 mock、不许"等真数据"。优先设计"一段 fixture 养活多条 feature"的复用结构。

⚠️ **fake_llm 录制 = 全局调用序，不是主对话序**：Summarization 压缩调用、goal 达成判定调用、subagent 的全部调用，都从同一 `responses` 序列按序弹出——录制时必须把这些「隐藏调用」按实际发生顺序编进去（S2/S3/S5 尤其），否则测试神秘变红。

| fixture | 状态 | 用途 / 喂哪些 feature |
|---|---|---|
| `fake_llm/natural_close.json` | ✅ | F01：终止条件 1（纯文本自然收口） |
| `fake_llm/echo_roundtrip.json` | ✅ | F01：两轮工具往返 + tool_result user 角色回填 + turn 计数 |
| `fake_llm/parallel_tools.json` | ✅ | F01：同响应多 tool_use → 结果并入同一条 user 消息（API 硬约束） |
| `fake_llm/endless_tool_calls.json` | ✅ | F01：max_turns 熔断（终止条件 2） |
| `fake_llm/research_task.json` | ✅ | F02 集成 + S1 收口 E2E 对照（bash→read_file→结论） |
| `fake_llm/oversize_tool_output.json` | ✅ | F04：ToolOutputBudget 截断场景（超长输出的 spew 工具由测试注入） |
| `fake_llm/summarize_history.json` | ✅ | F04：Summarization 压缩场景，「录制=全局调用序」教学样本（responses[0] 归压缩调用消耗） |
| `fake_llm/subagent_flow.json` | ✅ | F05：主→task→subagent 跑 bash→结论回填→主收口（responses[1..2] 归 subagent 内部循环） |
| `fake_llm/subagent_concurrency.json` | ✅ | F05：4 个 task 撞 max_concurrent=3，第 4 个回错误文本 |
| `fake_llm/subagent_quota_across_runs.json` | ✅ | F05 审查黄1：同实例跨两次 run，配额泄漏（per-instance 生命周期语义） |
| `fake_llm/subagent_halt.json` | ✅ | F05 审查黄2：subagent max_turns 熔断，_final_text 回退占位 |
| `skills/demo-skill/SKILL.md` | ✅ | F06：技能发现+斜杠激活主 fixture（frontmatter 两字段 + 正文） |
| `skills/note-taker/SKILL.md` | ✅ | F06：第二个技能，验证多技能递归发现 |
| `fake_llm/goal_continuation.json` | ✅ | F07：goal 续跑达成场景（工作/NO/工作/YES 交错，run 与评估共用序列） |
| `fake_llm/goal_stale.json` | ✅ | F07：无进展熔断（连续相同文本→stale 累计到 2 停） |
| `fake_llm/goal_cap.json` | ✅ | F07：次数熔断（不同文本始终 NO，靠 max_continuations 兜底） |
| `fake_llm/goal_with_delegation.json` | ✅ | F07 审查 Y5：真 TaskTool 穿过续跑各委派一次，端到端证 _delegated 每轮复位（拆 D5） |
| `fake_llm/clarification_flow.json` | ✅ | F08：ask_clarification 中断→state.interrupt 带出→补答案重进收口 |
| `fake_llm/checkpoint_crash.json` | ✅ | F10：中途崩溃场景——第 2 轮 complete 弹尽抛错 = kill -9 离线等价物（接缝确定性行为替代真实环境事件）；natural_close 复用做恢复续跑/终存场景 |
| `workspace/data.md` | ✅ | F02：read_file/bash 真实执行语料 |
