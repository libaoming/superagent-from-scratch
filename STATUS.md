# STATUS — superagent-from-scratch

> 每次 session 第一个读的文件。收尾必更新本文件。

## 一句话状态
2026-07-10 **S6 长期记忆收口完成（9/9 passing, tag sfs-s6）——第二季第 1 刀全闭环**。src/memory.py（写路径旁路=入队去抖后台 merge / loop 外外壳 run_with_memory，run() 零改动 C4 第七次实证 / updater 增量 merge「LLM 提议、代码定夺」/ 读注入 user 角色权限隔离 M2 / 6 段摘要 + facts）。收口五件全清：notes/07 拆解笔记 ✅、CONTEXT.md 回填（第五栈 + `<memory>` 暗物质 + 沉淀手段）✅、对抗审查 CLEAR（3 建议落地：SPEC:147 口径对齐 / updater 渲染抽 text 块 / 补 3 边界断言）✅、收口面试五考点全过（teach 记录 0013/0015，MISSION 已更新为全栈）✅、F09 passing + tag ✅。verify：test_s6_memory **7 passed**，全量 **69 passed**，src **880 行**（预算 1500）。eval 切片仍搁置（考点+lesson 0007 留档）。仓库：https://github.com/libaoming/superagent-from-scratch。

## 下次入口
1. 读本文件 → `M1/PROGRESS.md`（「增量流水待整理」块累积多日，需合并进正式 Session Log 后清空——上次收口未做）
2. **当前应做：第二季下一刀选型**（三候选，先跟用户拍板再提炼考点开课）：
   - C2 checkpointer（断点持久化，接 notes/06 拓展练习 2）
   - C3 deferred tools（工具延迟加载）
   - eval 切片复活（考点 + lesson 0007 已留档，接 _goal_met 的 eval 闭环）
3. 之后可选：M1 增量流水整理；exam-points「暗物质缺口」措辞对齐；橙研所成品文（7 笔记 + 7 面试记录是底稿）
4. 教学侧下切片注意（记录 0015）：面试加「只问证据/只问备选」单点题练审题——用户新暴露模式是「答偏子问题」

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
