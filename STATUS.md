# STATUS — superagent-from-scratch

> 每次 session 第一个读的文件。收尾必更新本文件。

## 一句话状态
2026-07-09 **F05 passing + 对抗审查全清（5/8，S3 只差面试收口）**：src/subagent.py（TaskTool 缝③工具 + 递归调 run + 单层委派 + 只回结论）；对抗审查 0 红 5 黄全清（黄1=max_concurrent 据实校正为 per-instance 生命周期配额 + 钉跨 run 泄漏测试；边界/防递归补齐）；notes/04 回填闭合。verify 6 passed、全量 **44 passed**（存量零改动同绿 = C4 再实证），src 402 行。S2 已 tag sfs-s2。S3 教学环 1-2 步完成。仓库公开：https://github.com/libaoming/superagent-from-scratch（tag: sfs-s1, sfs-s2）。

## 下次入口
1. 读本文件 → 读 `M1/PROGRESS.md`（含「对抗审查遗留」🟡 清单）
2. 跑 `bash M1/init.sh` 确认环境
3. 当前应做：**S3 收口面试模拟**（规矩 6：用户说「考我 S3」触发；S3 考点清单五条 + 三样现成 + 交叉复习三旧考点，全过才打 tag）→ `git tag sfs-s3` + 提交 S3 全批改动（含 teach/ 已 gitignore）
4. 收口后 S4：F06_skills 开教学环（提炼考点 → /teach S4 → 开工）
5. 未 push：本地 commit/tag 都在，远程未动——用户要 push 再 `git push && git push --tags`

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
