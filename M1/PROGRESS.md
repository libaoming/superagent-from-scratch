# M1 PROGRESS

| 字段 | 值 |
|---|---|
| active_feature | 第二季下一刀选型（9/9 passing，S6 已收口 tag sfs-s6） |
| slice | S6 完成 |
| 更新 | 2026-07-10 |

## Next Candidates
- 第二季下一刀选型（先跟用户拍板再提炼考点开课）：C2 checkpointer（接 notes/06 拓展练习 2）/ C3 deferred tools / eval 切片复活（考点+lesson 0007 已留档）
- 顺路可清「对抗审查遗留」便宜几条；exam-points「暗物质缺口」措辞对齐；橙研所成品文（7 笔记 + 7 面试记录是底稿）

## ~~S5 备忘~~（✅ 2026-07-09 两颗雷均在 S5 落地时拆除并钉测试，见 notes/06 决策 7）
- ~~Interrupt.question 返回通道~~ ✅ S5 走 state.interrupt 字段带出（test_clarification_interrupts_before_tool_runs）
- ~~run_with_goal() 复用 TaskTool 的 `_delegated` 泄漏~~ ✅ S5 加 TaskTool.reset() + 每续跑复位（test_goal_continues_until_met 断言 reset_count）

## 对抗审查遗留（S1 审查 2026-07-06 · 🟡 契约存在但未钉测试，后续切片顺路补）
- bash 成功时 stderr 被静默丢弃（SPEC「模型要看 stderr」只覆盖了失败路径）
- read_file 与 cat -n 边缘差异：空文件/无结尾换行/splitlines 的 Unicode 分隔符
- read_file 「其余异常外抛」只钉了 FileNotFoundError（目录/无权限未钉）
- AnthropicLLM 的 block 映射（text/tool_use 之外静默丢弃）是纯函数可离线测而未测
- fixture「相对仓库根」约束无护栏（靠 pytest 从仓库根跑保证）

## Blockers
- （无）

## Deviations（偏离 SPEC/计划的决定 · 逐条向用户核对后清账）
- ~~**D1（F01）**~~ ✅ 2026-07-06 随 F03 清账：`run()` 已以关键字参数补入 `middlewares`，S1 测试零改动同绿。
- **D2（F01）**：State 只含 `messages` + `turn_count`，SPEC 数据模型里标注 "S5:" 的 `todos`/`goal` 字段推迟到 S5 落地（字段纪律：必须被切片测试断言用到）。
- **D3（F01）**：AnthropicLLM 默认 `model="claude-opus-4-8"`、`max_tokens=16000`、不传 thinking/采样参数（claude-api skill 当前指引；SPEC 未规定默认值）。
- ~~**D5（F05）**~~ ✅ 2026-07-09 用户确认接受，对抗审查据实校正：`max_concurrent` 实为 **per-instance 生命周期配额**（`_delegated` 只增不减，无 run 边界复位）——单次 run 内等价 per-run，跨 run 复用会累计泄漏。原文案误写「per-run」，审查黄1 戳破后据实改 docstring/notes + 钉 test_delegation_quota_is_per_instance_lifetime。为何不修成真 per-run：loop C4 冻结无处复位，保冻结优先。教学点（配额+超限错误分流+防委派炸弹）不变。
- ~~**D4（教学环流程）**~~ ✅ 2026-07-07 已确认：落地「切片教学环」时两处按 Claude 推荐拍板——①面试问题环节与规矩 6 收口 quiz **合并升级**（不并存两个 quiz）②过关标准从「满分」改「**面试官 rubric**（命中要点即过）」。用户批准含此两点的 plan + 补充指示「用一场面试准备的思路来讲解和检查」，视为确认。

## Session Log（倒序）
### 2026-07-10（续：S7 全切片一日闭环）
- **S7 断点持久化开工→收口 → F10 passing + tag sfs-s7（第二季第 2 刀）**：开工序列（deer-flow 实况子 agent 调研：0% 内核+100% 胶水 458 行、生产没用 interrupt()/Command(resume)→ 拍板 M1=缝① per-turn+外壳终存 / M2=悬空兜底保留 → SPEC #checkpointer + F10 + 考点清单）→ 理论课 0009（quiz 8/8；**教学环反哺开发第一例**：用户课上先设计出测试套件，记录 0016）→ C5 开发（fixture checkpoint_crash.json → 测试红 → src/checkpoint.py 84 行绿，5+74 passed，C4 第八次实证）→ 收口（notes/08 + CONTEXT [interrupted] 暗物质行 + 对抗审查 CLEAR 3 建议落地含「悬空兜底对自产档不可达」触发面说实 + 收口面试 13 问三轮全过含一次跳关被闸门拦回，记录 0017）。实现层精化：悬空分崩溃/待答两种语义（`state.interrupt is None` 单闸），防撞坏 S5 恢复。
### 2026-07-10
- **S6 收口完成 → F09 passing + tag sfs-s6（第二季第 1 刀全闭环）**：理论课 0008 完课（quiz 8/8，白板写路径「入队快照」满分，记录 0013）→ notes/07 拆解笔记 → CONTEXT.md 回填（第五栈 memory updater + `<memory>` 暗物质行 + 「沉淀」治理手段行）→ 对抗审查（fresh 子 agent）**CLEAR 无 FAIL**，3 建议落地：SPEC:147 updater 协议口径对齐 6 段 / update_memory 渲染抽 text 块（防 block list 的 Python repr 喂 updater）/ 补 3 边界断言（confidence=0.7 恰好进、空记忆不注入、casefold 去重）→ 收口面试五考点全过（Q3 一次过，Q1/Q2/Q4/Q5 补答收口；新暴露模式「答偏子问题」，记录 0015）→ verify：test_s6_memory 7 passed / 全量 69 passed / src 880 行 → commit 193e963 + tag sfs-s6 + push（`git ls-remote` 核实远端）。teach/MISSION.md 经用户确认正式更新为「全栈脱稿」（记录 0014）。
### 2026-07-09（下半日补记：S5 收口→CE 加课→第二季开季，当日未及入正式流水）
- **S5 收口完成 → F07+F08 passing + tag sfs-s5，第一季全项目完工**：notes/06 拆解笔记 → 对抗审查全清 → S5 收口面试通过（记录 0010，两复训点补上）→ 全量 61 passed、src 661 行 → commit bcf8ceb + push；随后 README 中英切片表更新到 S5 完成（commit 58e630c）。两颗跨切片雷（Interrupt 返回通道 / _delegated 复位）在引爆点拆除并钉测试。
- **CE 收尾加课 + CONTEXT.md 落地**：CE 考点清单 + 0006 总复习课（五刀缝成「上下文治理」一张图：四栈×七层 + 暗物质 + 五治理手段）→ CE 收口面试通过（记录 0012，Q4 学生追倒老师材料「暗物质=隐藏在场 vs 空层=缺席」→ 据实修 CONTEXT.md 措辞）→ CONTEXT.md 上下文构成审计 commit 28604b3 + push。
- **第二季开季：eval 上课后搁置 → S6 记忆 build**：eval 闭环理论课 0007 完课后切片搁置（考点 + lesson 留档，接 _goal_met eval 闭环的开工点保留）；转 S6 长期记忆——用户参与拍板 M1（loop 外外壳，不加钩子破 C7）/ M2（读注入走 user 角色）+ 追问 summary vs facts 分工 + **6 段结构化摘要模型增加到教学版**；src/memory.py + fixtures/memory_update.json + test_s6_memory **7 passed 代码绿**（收口序列留次日）；S6 考点清单提炼（reference/s6-memory-exam-points.html）。
### 2026-07-09
- **F06_skills 完成 → passing**：C5 顺序——fixture 先造（skills/demo-skill + note-taker，两 SKILL.md 验证多技能递归发现）→ test_s4_skills.py 先红（ModuleNotFoundError）→ src/skills.py 实现（discover_skills：rglob+yaml frontmatter→registry+system_block 只含元数据 / activate：斜杠+已注册→全文作 user 前缀块，否则原样）→ 6 passed；全量 50 passed（存量 44 零改动同绿 = C4 第四次实证），src 454 行。skills 不占缝、全在 loop 外。pyyaml C2 早预留。无新 Deviations。**S4 代码侧完成**。
- **S4 教学环第 1-2 步完成**：考点清单提炼（reference/s4-exam-points.html 五条 + 交叉复习四旧考点）→ 0004 课发布并吸收合格（learning-records/0008，三题过；注入点「压缩」理由一度说反已当场纠——skill 正文放「压得掉的地方」user history，system 压不掉）。核心洞察：skills 注入知识不是能力、token 经济学元数据常驻正文按需。
- **S3 收口推进（notes/04 + 对抗审查 0 红 5 黄全清）**：① notes/04 拆解笔记（deer-flow 533 行对照→60 行简化→决策 why→隔离测试手法→可迁移 6 条→拓展练习 2→收口结论；行数经 wc 校正）② 对抗审查（fresh 子 agent）报 **0 红 5 黄**——黄1（真问题）：max_concurrent 文案「per-run」与实现「per-instance 生命周期」（_delegated 只增不减）不符，S5 run_with_goal 复用会泄漏 → 据实改 docstring/notes/D5 + 钉 test_delegation_quota_is_per_instance_lifetime + S5 备忘；黄2 熔断边界测试（_final_text 回退占位）；黄3 防递归 name 约定注释；黄4 隔离正向弹尽确认；黄5 归 D5。③ 全量 **44 passed**，src 402 行。剩：收口面试 → tag sfs-s3。
- **F05_task_subagent 完成 → passing**：C5 顺序——fixture 先造（subagent_flow + subagent_concurrency，均带「录制=全局调用序」注释）→ test_s3_subagent.py 先红（ModuleNotFoundError）→ src/subagent.py 实现（TaskTool 缝③工具 + 递归调 run + 单层委派滤 task + _final_text 只回结论）→ 4 passed；全量 42 passed（存量 38 零改动同绿 = C4 再实证）。产生 Deviation D5 待核对。**S3 代码侧完成**。
- **S3 教学环第 1-2 步完成**：考点清单提炼（reference/s3-exam-points.html 五条 + 交叉复习三旧考点）→ 0003 课发布并吸收合格（learning-records/0006，三题脱稿全过）。核心洞察 subagent=递归+隔离在 07-07 晚用户已自行摸到，本课收敛成型。
- **S2 收口完成 → tag sfs-s2**：收口面试第二次通过（learning-records/0005，追问 A/B/C 全满分 + 压力测试顶住）→ commit 9e7a17a（F04 三件 + 对抗审查全清）+ tag sfs-s2。teach/ 判个人学习记录不入公开仓库 → 加进 .gitignore（check-ignore 确认）。S2 收口面试第一次未通过（0004，标签级答案+疲劳）是闸门首次真拦截。
### 2026-07-08
- **S2 收口推进（notes 回填 + 对抗审查全清）**：① notes/03 回填完成（新四节「内置三件实战」+ fixture 坑实录 + 八节收口结论，行数经 wc 实测校正）② 对抗审查（fresh 子 agent）报 **1 红 4 黄**——红：Summarization 按条数切可断 tool_use/tool_result 配对（API 硬约束，「简单策略」不豁免非法序列）→ 当场修复（切点对配对让位 + keep_last<max_messages 构造断言）+ 钉配对测试；黄全清：近 K 条方向断言、预算边界测试、C7 补齐 LLMClient/Tool/run 签名闸门（test_constraints.py，S1 遗留的 C7 账一并结清）③ 全量 **38 passed**，src 337 行。S5 备忘一条（Interrupt.question 返回通道）记入上方。剩：收口面试模拟 → tag sfs-s2。
- **F04_core_middlewares 完成 → passing**：C5 顺序——fixture 先造（oversize_tool_output.json + summarize_history.json，后者是「录制=全局调用序」教学样本；错误场景复用 echo_roundtrip、未超阈值场景用 natural_close 单条录制反向证明压缩未偷跑）→ test_s2_core_mw.py 先红（ModuleNotFoundError）→ src/middlewares/ 三件实现（budget 截断标注 / error 异常转 [tool error] 文本 / summarization 保近 K 条 + llm 构造注入压缩，Q1=A）→ 6 passed；全量 32 passed（26 条存量零改动同绿 = C4 再实证），src 320 行。无新 Deviations。**S2 代码侧完成**。
- **S2 教学环第 1-2 步完成**：0002 课（三钩子 + 顺序语义）发布并完课（学习记录 0003 + artifact 留档），S2 考点清单五条在课内收尾节；课中纠偏两处（钩子触发≠干活、三条缝非两层）+ 确立教学铁律「具体先行抽象殿后」。F04 开工前完成理论课 = 教学环按设计运转的第一个完整案例。
### 2026-07-07
- （下午→晚间）**S1 教学环补跑完整一轮**：0001 课完课（白板 + quiz 7/8）→ 首次收口面试模拟（主 5 题 4 过 1 半过，追问一度被反问岔开）→ 当晚用户主动清账补考通过（学习记录 0002 + artifact 留档）。行为层沉淀两条复训点（改对答案 / 反问回避追问）+ 新用户规矩「生成 md/html 一律发 Artifact 留档」（入 Auto Memory）。晚间续 0002 课预习问答（顺序语义大楼模型的由来）。
- （上午）**切片教学环流程落地**：用户需求「每个 S 开始 `/teach` 理论课、每个 S 结束设计面试问题并评估，以面试准备为纲——开始讲解、结束检查」。评估后与既有规矩 6 收口 quiz 合并（见 Deviations D4）。按用户补充指示「用准备一场面试来设计」定为四步弧（提炼考点→讲解→检查→复盘）。改动：`M1/AGENTS.md` 新增 1.5「切片教学环（整个切片 = 准备一场面试）」+ 规矩 6 升级为「收口面试模拟（不过关不打 tag，rubric 过关，记录落 `teach/learning-records/`）」；`CLAUDE.md` 项目身份补「切片教学环」一行；`STATUS.md` 下次入口插 S2 补课步骤（0002/0003 后再开工 F04）+ 收口序列补面试模拟；`teach/NOTES.md` 记流程约定。features.json 不动（教学仪式是 tag 闸门不进 verify）；S1 不回溯。
### 2026-07-06
- （下午→傍晚）**S2 开工配套教学动作**：S2 内容 artifact 讲解；notes/03 增补「可迁移清单 + AI PM 视角」并随 F03 更新；《The AI Agents Stack, 2026 Edition》（O'Reilly）artifact 讲解；傍晚用户跑 `/teach S1 和 S2` 建立教学工作区 `teach/`（MISSION=面向 Agent PM 面试脱稿讲清 S1+S2，0001 课已发布，0002/0003 规划中）。
- （中午）**S1 收口 → tag sfs-s1**：① notes/02 拆解笔记（含终止条件状态图 + 2 道拓展练习）② scripts/e2e_s1.py 真跑通过（ClaudeCLILLM 走 claude -p，bash→read_file→结论，turn_count=2，PRD 验收 4）③ 对抗审查（fresh 子 agent）：3 红全修——BashTool description 不再谎称仓库根 / C1 落成 pytest 机器闸门 tests/test_constraints.py / features.json F02+F05 清除 LangChain 残留词 ToolMessage；🟡 补钉 max_turns 默认 40 + write_file 覆盖语义，其余记「对抗审查遗留」节 ④ 全量 19 passed 无 key 同绿。
- （上午）**F02_real_tools 完成 → passing**：C5 顺序——fixture 复用（research_task.json + workspace/data.md，无需新造）→ test_s1_tools.py 先红（ModuleNotFoundError）→ src/tools.py 实现（72 行）→ 9 passed；全量 16 passed，无 API key 复跑同绿。无新 Deviations。S1 代码侧完成。
- （上午）**开源落地**：`git init` + 首 commit（26 文件/1795 行）→ `gh repo create` 私有建仓推送 → 用户下令转 **public** → 补 MIT LICENSE + 双语 README（含架构图/五切片导读/deer-flow 对照表，PRD 验收 5 部分交付；GitHub License API 确认识别 MIT）。`.gitignore` 排除 .venv/缓存/settings.local.json。STATUS.md 建仓待办清账。
- （上午）S1 学习手册 artifact 发布（按 SPEC v1 模版重建——原 f01 页面文件随 tmp 清理丢失，token 取自 Auto Memory）：https://claude.ai/code/artifact/14533136-5bf1-4224-88eb-d100052bfee9
- （上午）harness 进度速查（1/8 passing，F02 应做）；定下一步 = F02_real_tools（先清本流水）。
### 2026-07-04
- （晚间）F01 学习手册 artifact 发布（含循环步进器/自测6题/30min动手路径），已按下午 SPEC 页模版对齐（ivory+clay/宋体标题/16px/800px），模版偏好存入 Auto Memory：https://claude.ai/code/artifact/72f95524-2b11-4668-8d52-0b27ff26e2aa
- （晚间）**F01_agent_loop 完成 → passing**：C5 顺序走完——fixture 5 个（natural_close/echo_roundtrip/parallel_tools/endless_tool_calls/research_task + workspace/data.md）→ test_s1_loop.py 先红（ModuleNotFoundError）→ src/llm.py + src/loop.py 实现 → 7 passed（无 API key 环境复跑同绿）。pyproject.toml 落地（uv，C2 依赖仅 anthropic+pyyaml）。src 共 115 行。产生 Deviations D1-D3 待用户核对。
- （晚间）harness 进度速查（0/8 pending，F01 应做）→ 用户下令开工 F01。
- （下午→傍晚）打开 SPEC review；artifacts 页面链接确认；对齐 memory-kit 理解；四决策拍板（1A 2A 3A 4B）+ 拓展性规则落地进 SPEC/PRD/CLAUDE.md。
- （晚间收尾散记，自流水归并）F01 手册 20:02 版被用户否掉（「6点后的版本我不喜欢」）→ 排查出与下午 SPEC 页字号/版式不一致 → 按「按下午的模版即可」重发对齐（即上条 artifact 模版偏好的由来）；期间还聊了「plan-推理-code vs loop」话题（未形成决定）；20:23 关机收工。
- 项目脚手架完成（4 层骨架）。下一步：文档先行填 PRD/SPEC/architecture。

## 如果…就…
- 如果不知道做什么 → 按 AGENTS.md「选 feature 算法」
- 如果 fixture 缺 → 先造 fixture，不许 mock
- 如果要核查线上/读大文件 → 派 `.claude/agents/superagent-from-scratch-ops.md` 子 agent，别在主 context 拉原始输出

## 🤖 增量流水（待整理）
<!-- Stop hook 自动追加区。2026-07-10 已整理 84 条（2026-07-08 14:10 → 2026-07-10 14:22）：07-08 下午批次（S2 面试两场/S3 考点+理论课/F05 开工审查/S3 面试/S4 考点+理论课/F06 开工）已被既有 07-08/07-09 Session Log 覆盖，教学细节在 learning-records/0004-0008；07-09 批次（S4 收口面试/进 S5/S5 全程/CE 加课/eval 理论课/S6 build）归并为新增「2026-07-09（下半日补记）」三条；07-10 批次（S6 收口/面试答题）归并为「2026-07-10」一条，面试细节在 learning-records/0015；噪声丢弃（图片占位、代码片段回显、harness 系统提示、答题原文碎片）。 -->

- [2026-07-10 14:27] - M1/PROGRESS.md 增量流水块累积多日合并
- [2026-07-10 14:31] commit
- [2026-07-10 14:34] C2 checkpointer
- [2026-07-10 14:49] 教学版预估 50-80 行可完成整个切片内核。</result>
- [2026-07-10 16:47] 开工 F10
- [2026-07-10 16:55] S7 收口
- [2026-07-10 17:02] 无阻塞级代码缺陷。随手应修（非阻塞）：① features.json F10 `verify.fixture` 改为 `fixtures/fake_llm/checkpoint_crash.json`
- [2026-07-10 17:29]  5. 落进产品的sla 质量保证. 恢复语义是产品定义不是工程细节, 哪些场景可以丢半轮 哪些场景不能丢半轮, 恢复后的重放副作用 哪些操作需要人工确认(无幂等)
- [2026-07-10 17:31]     ① deer-flow 实况：0% 内核 + 100% 胶水——存/取/恢复内核 0 行自研，全在 LangGraph 官方 saver 库里（InMemory/Sqlite/Postgres
- [2026-07-10 17:33] S7 收口
