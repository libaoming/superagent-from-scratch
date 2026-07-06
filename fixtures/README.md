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
| `workspace/data.md` | ✅ | F02：read_file/bash 真实执行语料 |
