# STATUS — superagent-from-scratch

> 每次 session 第一个读的文件。收尾必更新本文件。

## 一句话状态
2026-07-06 **F03_middleware_protocol passing（3/8，S2 进行中）**：src/middleware.py（三钩子协议 + Interrupt，28 行）+ loop 挂载三条链（before 注册序/after 逆序/wrap 洋葱，终止条件 3 上线），`pytest tests/test_s2_middleware.py -q` 7 passed、全量 26 passed（S1 零改动同绿 = C4 实证）；src 245 行；D1 清账。仓库公开：https://github.com/libaoming/superagent-from-scratch（S1 已 tag sfs-s1）。

## 下次入口
1. 读本文件 → 读 `M1/PROGRESS.md`（含「对抗审查遗留」🟡 清单）
2. 跑 `bash M1/init.sh` 确认环境
3. 当前应做：**F04_core_middlewares**——⚠️ fixture 先行：verify 引用的 `fixtures/fake_llm/oversize_tool_output.json` 不存在，先造（还需 Summarization 场景 fixture，注意「录制=全局调用序」：压缩调用也消耗同一 responses 序列）→ `tests/test_s2_core_mw.py` 先红 → `src/middlewares/`（ToolOutputBudget 截断 / ToolErrorHandling 异常转错误文本 / Summarization 构造注入 llm 压缩旧消息，SPEC #middleware + Q1=A）
4. F04 绿后 = S2 代码侧完成 → notes/03 拆解笔记 → 对抗审查 → `git tag sfs-s2`；顺路考虑清「对抗审查遗留」便宜几条

## 关键技术事实
- 技术栈：Python 3.12 + uv + pytest；**零框架依赖**（不用 LangChain/LangGraph，loop 自己写，直接调 LLM API）
- 参考蓝本：`~/deer-flow`（浅 clone，bytedance/deer-flow）；核心在 `backend/packages/harness/deerflow/`（lead agent 556 行 + 28 middleware + task_tool 533 行）
- 定位：教学向开源（英文主 README + README.zh-CN.md，MIT）+ 面试作品集（WorkBuddy/智谱 Agent PM 方向）
- 切片 S1-S5 = loop → middleware 管线 → subagent 委派 → skills → 长任务（对应 deer-flow 真实架构，非 2025 年的 planner-executor）
- fixture 先行：所有测试用 fake-LLM fixture（录制的 JSON 响应序列）离线跑，真实 API 只做切片收口 E2E
- `notes/` 放 deer-flow 拆解笔记（中文，橙研所底稿）
- 无生产部署，ops 子 agent 的远程只读段不适用

## 文档地图
- 需求：`PRD.md`　方案：`SPEC.md`　架构：`architecture.md`　切片：`features.json`
- 里程碑三件套：`M1/`　fixture：`fixtures/`
- 脏活隔离子 agent：`.claude/agents/superagent-from-scratch-ops.md`

## 未知清单（已清账 · 2026-07-04 拍板 1A 2A 3A 4B，全部回填完毕）
- Q1 middleware 拿 llm = **构造注入**（SPEC #middleware）｜ Q2 goal 续跑 = **外层 run_with_goal()，turn_count 续跑重置**（SPEC #long-task）｜ Q3 skill 注入 = **user 消息前缀块**（SPEC #skills）｜ Q4 E2E = **claude -p 适配器 ClaudeCLILLM**（PRD 验收 4）
- 盲区两条已回填：FakeLLM「录制=全局调用序」（SPEC fixture 节 + fixtures/README）；turn_count 重置语义（随 Q2）

## 踩坑清单
- （随项目积累）
