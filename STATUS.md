# STATUS — superagent-from-scratch

> 每次 session 第一个读的文件。收尾必更新本文件。

## 一句话状态
2026-07-09 **S4 收口完成（6/8 passing）**：F06_skills 全绿——src/skills.py（发现 discover_skills + 激活 activate 两纯函数，skills 不占缝、全在 loop 外，run 零改动），verify 6 passed、全量 **50 passed**（存量 44 零改动同绿 = C4 第四次实证），src 454 行。**对抗审查 0 红 5 黄全清**（Y1/Y3/Y5 注释、Y2 补断言焊死注入边界、Y4 SPEC skills/**/消歧）+ **收口面试通过**（5 考点，4 题源码级）+ notes/05 拆解笔记落盘 + Artifact 留档。tag `sfs-s4` 待提交。S1-S3 已收口打 tag（sfs-s1/s2/s3，已 push）。仓库公开：https://github.com/libaoming/superagent-from-scratch。

## 下次入口
1. 读本文件 → 读 `M1/PROGRESS.md`
2. 跑 `bash M1/init.sh` 确认环境
3. 当前应做：**S5（最后一个切片，两 feature）**——F07_todo_goal + F08_clarification_hitl。两条 S5 备忘务必记：① Interrupt.question 返回通道；② run_with_goal 复用 TaskTool 须每 run 重建/复位 `_delegated`（S3 D5 已埋雷：`_delegated` per-instance 累计，跨 run 会误拒委派）。先补 CONTEXT.md？（S5 涉 goal 续跑的上下文拼装，改前先读）
4. push 时机：S4 已 commit+tag（若尚未 push，`git push && git push --tags`）；S5 收口同法

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
