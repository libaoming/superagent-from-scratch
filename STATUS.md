# STATUS — superagent-from-scratch

> 每次 session 第一个读的文件。收尾必更新本文件。

## 一句话状态
2026-07-09 🏁 **全项目完工（8/8 passing）**：S5 收口完成——F07_todo_goal + F08_clarification_hitl 全绿。src/goal.py（run_with_goal 外壳套纯净 run，依赖单向朝内）+ todo.py（计划外置 state.todos）+ clarification.py（中断走 state.interrupt 返回通道）。State 加 todos/goal/interrupt 三字段，run() 零改动（C4 第六次实证）。verify：S5 11 passed（F07 8 + F08 4），全量 **62 passed**（存量 51 零改动同绿），src **666 行**（预算 1500）。**对抗审查 0 红 6 黄全清**（Y5 补整合测试端到端焊死 D5 埋雷 + Y2/Y3/Y4 注释 + Y1 记 verify_notes）+ **收口面试通过**（两复训点 import 方向/loop 丢返回值均补上）+ notes/06 拆解笔记（系列完，含全项目收官表）+ Artifact 留档。tag `sfs-s5` 待提交。S1-S4 已 tag+push（sfs-s1..s4）。仓库公开：https://github.com/libaoming/superagent-from-scratch。五刀全砍完：循环→中间件→委派→技能→长任务。

## 下次入口（所有切片完成，进入收尾/开源打磨）
1. 读本文件 → 读 `M1/PROGRESS.md`（有「增量流水待整理」块累积多日，需合并进正式 Session Log 后清空）
2. push 时机：S5 已 commit+tag（若尚未 push，`git push && git push --tags`）
3. 剩余收尾候选（非切片，按需挑）：
   - README（英文主 + README.zh-CN）切片表更新到 S5 完成 + 五篇 notes 链接
   - CONTEXT.md 补画（LLM 项目第四件，S1-S5 一直欠着；现在回填 7 层上下文构成审计）
   - M1/PROGRESS.md 增量流水整理 + Session Log 收尾
   - features.json 8/8 passing 终检、STATUS 定稿
   - 可选：全项目复盘笔记 / 橙研所成品文（边学边开源的「学」的产物）

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
