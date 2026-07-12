# STATUS — superagent-from-scratch

> 每次 session 第一个读的文件。收尾必更新本文件。

## 一句话状态
2026-07-12 **S8 deferred tools 收口完成（11/11 passing, tag sfs-s8）——第二季三刀（S6 记忆/S7 断点/S8 deferred tools）全部闭环**。src/deferred.py（92 行：deferred_system_block 露纯名字 / ToolSearchTool 搜+双通道晋升「当轮可读 tool_result 回 schema、下轮可调 state.promoted 放行」/ DeferredGuard 缝①拦未晋升回教学式 error）+ loop.py（State.promoted、schema 构建移进循环体按 promoted 过滤——**「run() 零改动」8 连胜光明正大终止，C4 签名仍冻结**，存量 74 零改动同绿=第九次实证）+ checkpoint.py（字段表同步 promoted，set ⇄ sorted list，S7 联动账结清）。与 S4 对仗：skills 治知识层、deferred tools 治能力层，同一渐进披露范式；deer-flow 对照新样本「内核不小（397 行中 ~250）、砍产品化」。收口全清：notes/09 ✅、CONTEXT 回填 ✅、对抗审查 0 红 4 黄全清 ✅、收口面试五考点+突袭全过（teach/0019；复述对策三连败→下场改验证「逐问小标题作答」）✅。verify：**6 passed** / 全量 **80 passed**，src **1064 行**（预算 1500）。eval 切片仍搁置。仓库：https://github.com/libaoming/superagent-from-scratch。

## 下次入口（S8 已收口，下一刀待拍板）
1. 读本文件 → `M1/PROGRESS.md`
2. **下一刀候选（用户拍板）**：① eval 切片复活（考点 + lesson 0007 已留档，接 _goal_met eval 闭环的开工点保留）② 橙研所成品文（9 篇 notes + 9 场面试记录是底稿，「教学环反哺开发」是新亮点）③ 顺路清「对抗审查遗留」便宜几条 / exam-points「暗物质缺口」措辞对齐
3. 复训点（下切片课前复测）：skills 正文注入时机=激活时非启动时；否决备选提取（外壳重进/stub schema）
4. 面试格式规则更新提案待验证：「动笔前复述」→「逐问小标题作答」（0019 新假设：管用的是输出格式不是前置动作）

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
