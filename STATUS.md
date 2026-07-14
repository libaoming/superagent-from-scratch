# STATUS — superagent-from-scratch

> 每次 session 第一个读的文件。收尾必更新本文件。

## 一句话状态
2026-07-14 **S11 写前版本门收口完成（13/14 passing, tag sfs-s11）——第三季第 2 刀全闭环**。src/middlewares/read_before_write.py（86 行 guard 家族第三员：WRITE_HINTS 判定 + 新文件放行 + fail-open 留痕（课上拍板 A，教学环反哺第四例）+ 反扫 messages 比渲染文本 sha1——读记录寄生 messages=「门的记忆与模型记忆同生共死」（纠错定稿：压缩删记录=拦+逼重读，非放行）；「写不刷新 mark」零实现行）+ tools.py 抽 render_numbered 共用（+4）。对抗审查 1 红 5 黄全清（红1=ToolOutputBudget 截断×版本门永久误拦死循环→检出截断标注 fail-open 留痕+钉测试）。收口面试通过（0023：续考 Q3/Q4/Q5/突袭**全满分级**；两条可迁移命题「fail-closed 前提=拦后有保证可达的自救路」「洞在哪一层补在哪一层」；模板骨架对策连续第二场零漏答）。verify：**7 passed** / 全量 **102 passed** / src **1420 行**（预算余 80）。
（上一里程碑 2026-07-13：S10 防打转+预算闸收口，tag sfs-s10，详见 M1/PROGRESS.md Session Log。）仓库：https://github.com/libaoming/superagent-from-scratch。

## 下次入口（S11 已收口，第三季 2/3；剩 S9 挂账 + S12 预算账）
1. 读本文件 → `M1/PROGRESS.md`
2. **当前应做（二选一）**：
   - **挂账：续 S9 收口面试**（F12 in_progress，最后一个非 passing feature；恢复点=Q1「核心闭环与教学版砍法」3 问已出题未作答——①M2 最小弧 ②0.8→1.0 教学弧实证 ③一次一改为什么是纪律；其后 Q2 程序化 accuracy vs LLM judge → Q3 train/held_out → Q4 作弊防线 → Q5 PM 三条 → 突袭「标量 vs 逐断言」；五考点 Artifact https://claude.ai/code/artifact/8c2879a6-baa2-4e01-a091-36b0cf327bcd ；STEP 0 已满分）。过了才有 F12 passing + tag sfs-s9 → **14/14**
   - **S12 开工前必须先对预算账**：src 余 **80 行**（1420/1500），S12 执行安全三件套规划 ~100 已超——砍面或减法拍板后才准落三件套。另 S12 顺路账两条：bash stderr 审查遗留 + bash 侧信道不设防（S11 未钉面自曝，`echo x > file` 绕过版本门，notes/12 有实锤）
3. 第三季全景（已拍板 D1=A/D2=B/D3=A）：~~S10 防打转+预算闸~~ ✅ → ~~S11 ReadBeforeWrite~~ ✅ → S12 执行安全三件套 → 季末整合理论课+全项目总复习面试。设计稿 `teach/reference/season3-plan.html`（Artifact https://claude.ai/code/artifact/66410217-0fbb-4937-9d87-fba39b447df1 ）

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
