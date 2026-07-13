# M1 PROGRESS

| 字段 | 值 |
|---|---|
| active_feature | **S10 全闭环（F13 passing + tag sfs-s10，12/13 passing）**。下一步二选一：清 S9 挂账（F12 只差收口面试）或开 S11 ReadBeforeWrite 三件套 |
| slice | S10 收口完成（第三季第 1 刀 ✅）｜ S9 收口暂停（挂账） |
| 更新 | 2026-07-13 |

## Next Candidates
- **进行中：S10 LoopDetection + TokenBudget 加餐（2026-07-12 开季拍板 D1=A/D2=B/D3=A）**——三件套 ✅ → 理论课 0011（待上）→ C5 开发 → 收口。第三季全景：S11 ReadBeforeWrite → S12 执行安全三件套 → 季末整合理论课+总复习面试（设计稿 teach/reference/season3-plan.html）
- **挂账：S9 收口面试**（F12 in_progress，恢复点=STEP 0 复测两问；改动未 commit，与 S10 文件面基本不相交）
- 备选：橙研所成品文；「对抗审查遗留」的 bash stderr 一条留 S12 顺路清

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
### 2026-07-13
- **S10 收口面试通过 → F13 passing + tag sfs-s10（第三季第 1 刀全闭环，12/13 passing）**：面试（串行+漏答不判过+逐问小标题+「只问证据」现挂）五考点+突袭全过——Q1 三轮收口（「发现延迟乘在账单上」到根 / salient 归位 / 「归一化在回答什么算同一件事」全场最佳段落之一）；Q2 消息序列摆写满分 + quiz 错题池家谱清账（避/补/绕）；Q3 方言归位 +**「只问证据」第五验满分**（git diff 0 行 + 存量同绿 + 三断言「行为指纹」解读，0011 复测错→当晚现挂满分=条件反射一日闭环，宣布成型）；Q4 一次过零追问（两个自产论证超标准答案：「打转 run 被 Summarization 服务得很好却在成本轴无限烧钱」「Loop 抓检测得到的重复、Budget 兜检测不到的一切浪费」）；Q5 三轮收口（P1 划线权衡「回家」）；突袭警告蒸发机制链五步满分级（「共享实例=把主循环的信箱挂在 subagent 门口」）。**「多问漏答」5 次现形且小标题格式全场未被自发使用**——0019 假设修正（实际有效=面试官单发一问），下场对策=多问题附作答模板骨架；新确诊「万能权衡」模式（误报率vs止损速度错放两次第三次回家）。记录 0021。→ verify 真跑 **9 passed / 全量 95 passed** → F13 passing（verify_notes 回填）→ commit + tag sfs-s10。**12/13 passing，教学环反哺开发本切片三例。**
- **S10 收口推进（notes/11 + CONTEXT 回填 + 对抗审查 0 红 6 黄全清）**：① notes/11 拆解笔记（七节全：deer-flow 902 行对照内核 ~150 → 177 行三文件 / 7 条决策清单含拍板 A 与「教学环反哺开发第三例」/ 未钉面说实 / 可迁移 5 条 + PM 4 条 / 拓展练习 2 道含「警告自救成功率 eval」接 S9 量表）② CONTEXT.md 回填（S10 无新调用点五栈不变；暗物质 +2 行——`[loop warning]` 延迟注入=教学式第三员、`[loop stop]` 剥 tool_use=**首个输出侧替换型「被代言」**；治理手段 +「止损」行）③ 对抗审查（fresh 子 agent）**0 红 6 黄**——黄1 实例状态跨 run 泄漏（甲任务警告注入乙对话，实跑复现）+ 黄2 与 subagent 共享实例警告被劫走（S8 黄3 姐妹题）→ **契约化 docstring**「一个实例=一个任务、不与 subagent 共享」（续跑共用=有意语义：前科不因续跑清零，同 D5 处理）；黄3 挂载次序缺位（双件同挂脏账 + 硬停剥掉 ask_clarification 丢 interrupt）→ docstring 次序原则「防御件注册在语义件之前」+ **补 2 个行为钉**（同挂先剥者赢/后跑者早退免疫、Interrupt 先行收口不被剥，新 fixture loop_hardstop_vs_clarification）+ CONTEXT「每件每轮至多一条」措辞校正；黄4 notes 未钉面清单补全（含「多余录制不被消费已被 turn_count==0 间接钉死」反向澄清）；黄5 checkpoint「改写幂等」注释被警告注入证伪 → 补非幂等例外；黄6 window≥1 断言（window=0 删空切片=无限窗语义反转）+ features.json 行数 165→177 据实改正（期间自犯「先写后测」一次，当场按核验纪律改正）。④ 修后复验 **test_s10 9 passed / 全量 95 passed / src 1330 行**。剩：收口面试（串行+漏答不判过+逐问小标题+「只问证据」第五验现挂）→ F13 passing + tag sfs-s10。
- **F13_loop_detection 代码侧完成 → in_progress**：C5 顺序——fixture 先造（5 个：loop_repeat_calls 主流程「留/补」双断言 / loop_self_rescue 警告教自救 / loop_offset_bucket 宽进防逃检 / loop_write_full_args 严出防误报 / token_budget_overflow 警告线，预算硬停复用 endless_tool_calls）→ test_s10_loop_detection.py 先红（ImportError）→ 实现绿：src/middlewares/two_tier.py（共享基建 TwoTierGuard：双档阈值构造断言 warn<hard「排队警告永远等不到下一轮」+ 延迟注入（after_model 排队/before_model append，形态同 TodoMiddleware）+ 剥 tool_use（原地改 messages[-1].content，loop 走终止条件 1））+ loop_detection.py（归一化不对称：读类 salient 字段+offset 200 行分桶宽进 / 名字含 write/edit 等全参严出；排序→sha1→滑窗 20 计数，**滑窗=实例变量（拍板 A 落地，零 S7 联动）**）+ token_budget.py（字符数近似累加，每工具轮计整个 messages——近似「每轮全量重提交」成本结构）→ **7 passed；全量 93 passed（存量 86 零改动同绿 = C4 第十次实证），src 1316 行**（三文件 165 行，预算内）。配对完整性断言（assert_pairing_intact）钉住「注入不拆配对」。无新 Deviations。剩：notes/11 → CONTEXT 回填 → 对抗审查 → 收口面试 → tag sfs-s10。
- **增量流水 36 条归并清空（全部已被既有条目覆盖）+ 0011 理论课发布并完课 → S10 拍板 A，进入 C5**：0011 课发布（`teach/lessons/0011-s10-loop-detection-off-script.html` + Artifact https://claude.ai/code/artifact/68f1ce72-3f77-4121-8869-440d74981896 ，沿用十课格式 + 新增「课上合议·开工拍板题」节）→ 完课：复测 2/3（**Q1「只问证据」回退**——连续第四课、0010 对本课错，教形状判别法「证据不以『因为』开头，长着『跑了什么看到什么』的形状」）、quiz 7/8（Q4 配对坑家谱错——干扰项「同切片真决策错约束」，判别法「配对坑资格=不这么做 API 就 400」+ 避/补/绕三动词口诀）、吸收检查 3/3（检查 2 自救窗口一次过 + 补「**warn<hard 是延迟注入的硬性推论**」——硬停当轮收口、排队警告永远等不到下一轮；检查 3 轮询误杀场景两问全中、对策命中被砍的 per-tool 覆写，收束「**豁免的安全网=TokenBudget**」正交防御产品理由）→ **拍板题（本课交付物）：案 A middleware 实例变量**——判据「丢了不影响 loop 任务的恢复」（灵敏度降级≠任务错误），替 B 公平陈述跨恢复存活，代价（恢复后计数归零、检测延迟翻倍）说实知情接受，**零 S7 联动、省季末预算**。「逐问小标题作答」题内首验有效（拍板 3 问齐答），「多问漏答」新形态=漏**题外前置项**两例。记录 0020。剩：C5 开发 → notes/11 → 对抗审查 → 收口面试（含「只问证据」第五验现挂形态）→ tag sfs-s10。
### 2026-07-12（晚：第三季开季拍板 + S10 开工三件套）
- **第三季设计→拍板→S10 三件套落盘**：deer-flow 实况子 agent 调研（28 件 middleware 8040 行全盘点 + LoopDetection 612/ReadBeforeWrite 265/sandbox 全家 ~4000 精读，全部 wc -l 实测）→ 设计稿 season3-plan.html（Artifact https://claude.ai/code/artifact/66410217-0fbb-4937-9d87-fba39b447df1 ）→ 用户拍板 **D1=A**（三刀照 TOP 3：S10 防打转/S11 写前版本门/S12 执行安全三件套）**D2=B**（TokenBudget +60 行进主干作 S10 加餐，季末余量 ~19 行的预算风险知情接受）**D3=A**（季末 0 行代码整合理论课+全项目总复习面试）**顺序=B**（直接开 S10，S9 面试挂账后补）→ S10 开工三件套：SPEC #loop-detection（M1=缝① after_model 检测+before_model 延迟注入——S2 配对坑第三现身；M2=剥 tool_use 硬停复用终止条件 1；加餐共享双档+延迟注入基建，字符数近似计费；滑窗计数放哪留理论课合议）+ features.json F13（verify=test_s10_loop_detection.py，fixture 待造）+ 考点清单 s10-loop-detection-exam-points.html（Artifact https://claude.ai/code/artifact/0e6b25d5-a513-4b1e-95bf-61e09c9b2d04 ）+ RESOURCES.md 喂 S10 知识源。**剩：/teach 0011 理论课（用户上完才动代码）→ C5 → 收口**。
### 2026-07-12（续：S9 eval 闭环开工→代码侧+审查全清）
- **S9 开工三件套 + C5 开发 + E2E + 对抗审查 0 红 3 黄全清（收口面试待走）**：用户拍板 M1=_goal_met+程序化 accuracy / M2=量分+记账+手动一次一改 / M3=prompt 抽模块常量（全 A）→ SPEC #eval-loop + features.json F12（考点清单/理论课 0007 复用 07-09 留档）→ C5 顺序：fixture 先造（train 10 / held_out 5 案例 `{goal, transcript, expected}` + eval_verdicts 对抗录制 04/08 藏 YESTERDAY 措辞 + goal_verdict_edges 解析边界两连发）→ test_s9_eval 先红（ModuleNotFoundError）→ src/evals.py 实现（load_cases 按文件名序 / run_eval 程序化 accuracy / append_result TSV 记账）→ **基线真跑 0.8**（04/08 假阳性把 S5 审查 Y1 量化实锤）→ 修一处（goal.py：GOAL_JUDGE_PROMPT 抽常量 +「\s*YES\b」整词判定；改前先 grep 存量 S5 录制措辞确认语义不变）→ **1.0**，红→绿即「量分驱动一次一改」实证 → 真实模型 E2E（scripts/e2e_s9_eval.py 复用 ClaudeCLILLM）**train 1.0 / held_out 1.0**，evals/results.tsv 四行账齐。notes/10 ✅ + CONTEXT 回填 ✅（栈② system 抽常量、startswith 缺口清账、行号校准；无新调用点/暗物质）。对抗审查（fresh 子 agent）**0 红 3 黄**——黄1 SPEC M2「E2E 真跑基线」与实际（离线对抗录制跑基线）不符→SPEC 措辞据实改+写明为何是诚实选择；黄2 整词判定对「YES-oriented/YES AND NO」复合开头残余假阳性→notes/10 说实（不打解析补丁，根治=类型化 evaluator）+ held_out 未经受陷阱也说实；黄3 load_cases 空目录静默回空/expected 非布尔静默判错→装载时 raise 两道 + 钉 test_load_cases_refuses_silent_boundaries。修后复验 **test_s9 6 passed / 全量 86 passed / src 1146 行**。剩：收口面试（新规则「逐问小标题作答」首验）→ F12 passing + tag sfs-s9。
### 2026-07-12
- **S8 收口面试通过 → F11 passing + tag sfs-s8（第二季第 3 刀全闭环）**：增量流水 15 条归并清空（全部已被既有条目覆盖）→ 收口面试（串行+漏答不判过+动笔前复述三件套）五考点+突袭全过：Q1 追问补「知识层 vs 能力层」点睛句 + 纠偏「skills 正文注入=激活时非启动时」；Q2 三轮收口（③否决备选同题连漏两轮——多问漏答新形态）；Q3/Q4/Q5/突袭连续满分级，Q5 PM 三条（质量基线/分层旋钮带反馈回路/平台范式）绕开「问产品答机制」坑为全场最佳，突袭砍法双面论证引「不可能的分支不兜错」。**短板对策三连败确认**（明示 N 问→串行→复述均失效，8 答仅 1 复述），但 Q4 起用户自发「逐问小标题作答」后三题零漏答——新假设：有效的是输出格式不是前置动作，下场面试改验证「逐问小标题」。记录 0019。→ verify 真跑：test_s8_deferred **6 passed** / 全量 **80 passed** → F11 改 passing（verify_notes 回填）→ commit + tag sfs-s8 + push。**11/11 passing，第二季三刀（S6 记忆/S7 断点/S8 deferred tools)全部收口**。
### 2026-07-11
- **S8 收口推进（notes/09 + CONTEXT 回填 + 对抗审查 0 红 4 黄全清）**：① notes/09 拆解笔记（七节全 + 实现陷阱三则；Artifact 留档 https://claude.ai/code/artifact/1be7d0bd-8998-4bba-8e81-9ec65d94a86f）② CONTEXT.md S8 回填（主栈第 2 层 tools 首次动态化 / guard 合成 error 暗物质与 [interrupted] 同族但教学式 / 按需注入·能力层手段行；五栈不变）③ 对抗审查（fresh 子 agent）**0 红 4 黄**——黄1 test_s8 fixture 路径 cwd 依赖偏离兄弟文件约定→改 `Path(__file__)` 式（修前 cd tests 单跑 3 failed，修后 6 passed 实证）；黄2 空 query 走关键词分支恒真匹配→静默群晋升 5 个并白破缓存→回提示教自救不扩权 + 钉断言；黄3 构造注入跨上下文语义（绑定父 state 的 tool_search 下放子 agent 会晋升写进父 state、子 agent 永远等不到放行；load_state 新 State 须重建）→选**文档化**不改 TaskTool（保 S3 代码不动），docstring + notes/09 陷阱①；黄4 select: 大小写敏感与 tool_search 自标 deferred 死锁入陷阱③ + test_s7 「五字段」过期注释改「六字段」。④ 复验全量 **80 passed**。剩：收口面试（串行+漏答不判过+动笔前复述题目）→ tag sfs-s8。
- **0010 理论课完课（教学环第 3 步）**：复测 3/3、quiz 8/8（连续第二课满分）、吸收检查串行补答全过；分层旋钮方案为十课最佳 PM 输出；「多问漏答」四次现形且串行模式拦不住（确诊审题习惯），新确诊「问产品答机制」；收口面试对策升级三件套（串行+漏答不判过+动笔前复述题目）。记录 0018。用户新教学偏好入 NOTES：每课至少一道场景化产品题。
- **F11_deferred_tools 代码侧完成 → in_progress**：C5 顺序——fixture 先造（deferred_tools_flow 主流程 + deferred_guard_block 拦截自救兼测关键词搜）→ test_s8_deferred.py 先红（ModuleNotFoundError）→ 实现绿：src/deferred.py（deferred_system_block 露纯名字 / ToolSearchTool 搜+双通道晋升，catalog+state 构造注入 / DeferredGuard 缝①拦未晋升回教学式 error）+ loop.py（State.promoted 新字段、schema 构建移进循环体按 promoted 过滤——**「run() 零改动」8 连胜光明正大终止，C4 签名仍冻结**）+ checkpoint.py（save/load 字段表同步 promoted，sorted list ⇄ set，S7 联动账结清）→ **6 passed；全量 80 passed（存量 74 零改动同绿 = C4 第九次实证），src 1064 行**。测试观察「每轮提交哪些 schema」走唯一接缝（SpyLLM 包装 FakeLLM），不 patch loop 内部。无新 Deviations。剩：notes/09 → 对抗审查 → 收口面试 → tag sfs-s8。
### 2026-07-10（晚：S8 deferred tools 开工三件套）
- **S8 开工序列前半完成 → commit e3ddf25**：C3 deferred tools 调研（deer-flow 实况：tool_search 四件 397 行、内核 ~250——只 defer MCP 工具、露纯名字清单、缝③元工具、双通道晋升、wrap_tool_call 拦截）→ 拍板 M1=loop 内每轮过滤（run() 零改动、C4 冻结）/ M2=双通道晋升 → SPEC #deferred-tools + features.json F11 + 考点清单 s8-deferred-tools-exam-points.html 落盘。该砍清单定案：catalog_hash 防漂移 / fail-closed RuntimeError / pydantic 配置模块 / regex 降级容错。跨切片账：state.promoted 新字段 ⇒ S7 save_state 字段表同步 + roundtrip 断言。剩：0010 理论课（已发布未上）→ C5 开发 → 收口。
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
<!-- Stop hook 自动追加区。2026-07-13 已整理 36 条（2026-07-12 10:04 → 2026-07-13 08:47）：S8 收口面试批次（10:04-12:19）已被「2026-07-12 · S8 收口面试通过 → tag sfs-s8」覆盖；S9 fixture 造案例与实跑批次（13:43-13:55，含重复指令 15 条）已被「2026-07-12（续）· S9 开工三件套 + C5 开发」覆盖；第三季设计批次（14:16-14:44）已被「2026-07-12（晚）· 第三季开季拍板 + S10 开工三件套」覆盖；07-13 08:47 为本 session 启动请求，无新信息，全部丢弃。 -->
- [2026-07-13 09:15] - Spend your boldness in one place; keep everything around it quiet. If the accent fights the ground
- [2026-07-13 15:00] 上完了
- [2026-07-13 15:04] 3. B 方案跨恢复存活——恢复后接着上次的计数继续,不必重新打转计数
- [2026-07-13 15:06] [Image: source: /Users/baomingli/.claude/image-cache/631ea0e5-f177-4d22-b0e9-8e32db676dcf/1.png] [Im
- [2026-07-13 15:07] [Image: source: /Users/baomingli/.claude/image-cache/631ea0e5-f177-4d22-b0e9-8e32db676dcf/3.png]
- [2026-07-13 15:07] [Image: source: /Users/baomingli/.claude/image-cache/631ea0e5-f177-4d22-b0e9-8e32db676dcf/4.png]
- [2026-07-13 15:11] 丢了滑窗计数, 不影响loop任务的恢复. 是agent的防御监测计数
- [2026-07-13 15:15] 间隔2, 是提醒大模型 给模型自救的轮次和空间. 如果调成0, 会杀死模型打转自救机制
- [2026-07-13 15:30] 配置白名单
- [2026-07-13 15:38] 继续
- [2026-07-13 15:57] **全量 pytest**：`uv run pytest -q` → **93 passed**（1.10s；新增 7 + 存量 86，与 notes/11 §7 声称一致）。</result>
- [2026-07-13 16:03] S10 收口面试
- [2026-07-13 16:15] 3. 不对称设计共同说明, 防打转是 误报率 vs 止损速度的权衡
- [2026-07-13 16:22] 1. 打转每次调用都是重复无产出, 最贵的账是 tokens账单和 会话上下文
- [2026-07-13 16:28] 不自知」决定了打转的发现延迟——发现延迟直接乘在账单上。模型不会发现 系统不会发现
- [2026-07-13 16:34]       ▎ ）。read 场景怕逃检所以宽进，write 场景怕误伤所以严出——两个方向相反的设计共存于同一个归一化函数，恰好证明这是逐工具的误报/漏报权衡，不是越严越好。
- [2026-07-13 16:42] 1. 当场注入, 会破坏API的 tool_call和 tool_result配对的硬约束
- [2026-07-13 16:47]       ]}
- [2026-07-13 16:48] S2 摘要切点避开配对 / S7 恢复补 [interrupted] / S10 警告排队绕配对
- [2026-07-13 16:55] 警告/硬停的分工, 是止损速度和误报率的权衡
- [2026-07-13 16:59] 同一个设计方言：错误信息即修复路径, 惩罚是最后的手段
- [2026-07-13 17:04]       正常返回」断言组合——不是「因为剥掉后 loop 见无工具调用就会收口」那句机制解释。
- [2026-07-13 17:09]     - 产品版的正解不是 tokenizer，是供应商的 usage_metadata 差分累加（deer-flow 同款：input/output/total 三口径取最高占比）。为什么恰恰不用
- [2026-07-13 17:13] 1. 产品参数： warn/hard  指标 打转率 硬停率 固定时间review 打转率和硬停率指标, 评估打转的高发场合和高发任务
- [2026-07-13 17:14] 1. warn/hard 划线依据 = 误报率 vs 止损速度：太低误伤合法重试（用户体感 agent 动不动放弃），太高止损太慢（老板体感账单爆炸）
- [2026-07-13 17:15] 产品层面保证 防御层可观测可解释
- [2026-07-13 17:16] 1. 不违约——续跑属同一任务，打转前科不因续跑清零
