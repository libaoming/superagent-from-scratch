# STATUS — superagent-from-scratch

> 每次 session 第一个读的文件。收尾必更新本文件。

## 一句话状态
2026-07-10 **S7 断点持久化收口完成（10/10 passing, tag sfs-s7）——第二季第 2 刀全闭环，一天两刀（S6+S7）**。src/checkpoint.py（84 行：per-step durability=缝① Checkpointer 在 before_model 每轮存 + 外壳 run_with_checkpoint 收口终存，两件套缺一不可 / load_state 悬空双语义兜底：崩溃悬空补 [interrupted]、待答悬空留调用方，`state.interrupt is None` 单闸 / 恢复与 S5 三步同构）。「节奏定挂载」与 S6 成对：per-run→外壳、per-turn→缝①（缝①第一次收持久化住户，C7/C4 零改动第八次实证）。deer-flow 对照史上最极端：0% 内核+100% 胶水。**教学环反哺开发第一例**：测试套件由理论课上用户先设计（teach/0016）、开发照单实现。收口全清：notes/08 ✅、CONTEXT 回填（[interrupted] 暗物质行，无新调用栈）✅、对抗审查 CLEAR（3 建议落地，含「悬空兜底对自产档不可达」的触发面说实）✅、收口面试 13 问三轮全过（teach/0017）✅。verify：**5 passed** / 全量 **74 passed**，src **968 行**（预算 1500）。eval 切片仍搁置。仓库：https://github.com/libaoming/superagent-from-scratch。

## 下次入口（S8 deferred tools 已开工）
1. 读本文件 → `M1/PROGRESS.md`
2. **第二季第 3 刀已拍板 = S8 deferred tools（F11）**，开工三件套已落：SPEC #deferred-tools（M1=loop 内每轮过滤——run() 零改动 8 连胜光明正大终止、C4 签名仍冻结；M2=双通道晋升）、features.json F11（verify=test_s8_deferred.py，fixture=deferred_tools_flow.json 待造）、考点清单 s8-deferred-tools-exam-points.html。deer-flow 实况：tool_search 四件 397 行（内核 ~250），只 defer MCP 工具，露纯名字清单、缝③元工具、双通道晋升、wrap_tool_call 拦截。**跨切片账：state.promoted 新字段 ⇒ S7 save_state 字段表同步 + roundtrip 断言**
3. **当前应做：上 0010 理论课**（已发布：teach/lessons/0010 + Artifact，含 Claude Code 活教材彩蛋；用户尚未上课/吸收检查/记录 0018）→ 上完开工 F11（C5 顺序）→ notes/09 → 对抗审查 → 收口面试（**「一次一问」串行模式**，对照 S7 批量模式测漏答率）→ tag sfs-s8
   ⚠️ S8 开工三件套改动**未提交**（SPEC #deferred-tools / features.json F11 / STATUS / PROGRESS 表头）——下次收口时随 F11 一并 commit，或开工前先 docs commit
4. 之后可选：eval 切片复活；橙研所成品文；exam-points「暗物质缺口」措辞对齐

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
