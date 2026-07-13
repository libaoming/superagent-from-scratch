# STATUS — superagent-from-scratch

> 每次 session 第一个读的文件。收尾必更新本文件。

## 一句话状态
2026-07-13 **S10 防打转+预算闸收口完成（12/13 passing, tag sfs-s10）——第三季第 1 刀全闭环，一日完成「理论课→拍板→C5→审查→面试」全弧**。src/middlewares/two_tier.py（68 行共享基建 TwoTierGuard：双档阈值构造断言 warn<hard + 延迟注入「after_model 排队/before_model 注入」绕配对 + 剥 tool_use 走终止条件 1）+ loop_detection.py（72 行：归一化不对称——读类 salient+offset 200 行分桶宽进防逃检 / 写类全参严出防误报；sha1 滑窗 20 计数，**滑窗=实例变量，课上拍板 A**）+ token_budget.py（37 行：字符数近似累加=「每轮全量重提交」成本结构，产品版 usage_metadata 升级只动 _measure）。对抗审查 0 红 6 黄全清（实例生命周期契约「一个实例=一个任务、不与 subagent 共享」+ 挂载次序「防御件在语义件之前」2 行为钉 + checkpoint 幂等注释例外）。收口面试通过（0021：「只问证据」第五验满分=条件反射一日闭环；「多问漏答」5 次现形→下场对策=多问题附作答模板骨架）。verify：**9 passed** / 全量 **95 passed** / src **1330 行**（预算 1500）。CONTEXT 新增**首个输出侧替换型暗物质**（[loop stop] 被代言）+「止损」治理手段行。
（上一里程碑 2026-07-12：S8 deferred tools 收口，第二季三刀全部闭环。）src/deferred.py（92 行：deferred_system_block 露纯名字 / ToolSearchTool 搜+双通道晋升「当轮可读 tool_result 回 schema、下轮可调 state.promoted 放行」/ DeferredGuard 缝①拦未晋升回教学式 error）+ loop.py（State.promoted、schema 构建移进循环体按 promoted 过滤——**「run() 零改动」8 连胜光明正大终止，C4 签名仍冻结**，存量 74 零改动同绿=第九次实证）+ checkpoint.py（字段表同步 promoted，set ⇄ sorted list，S7 联动账结清）。与 S4 对仗：skills 治知识层、deferred tools 治能力层，同一渐进披露范式；deer-flow 对照新样本「内核不小（397 行中 ~250）、砍产品化」。收口全清：notes/09 ✅、CONTEXT 回填 ✅、对抗审查 0 红 4 黄全清 ✅、收口面试五考点+突袭全过（teach/0019；复述对策三连败→下场改验证「逐问小标题作答」）✅。verify：**6 passed** / 全量 **80 passed**，src **1064 行**（预算 1500）。eval 切片仍搁置。仓库：https://github.com/libaoming/superagent-from-scratch。

## 下次入口（S10 已收口，第三季 1/3）
1. 读本文件 → `M1/PROGRESS.md`
2. **当前应做（二选一，建议先清挂账）**：① **S9 收口面试**（F12 只差它；恢复点=STEP 0 复测两问 + 五考点 Artifact https://claude.ai/code/artifact/8c2879a6-baa2-4e01-a091-36b0cf327bcd ；面试新对策=多问题末尾附作答模板骨架「1.___ 2.___」）→ F12 passing + tag sfs-s9；② 或直接开 **S11 ReadBeforeWrite 开工三件套**（SPEC 节 + F14 + 考点清单，蓝本 deer-flow read_before_write 265 行）
3. S11 理论课 0012 前置素材：`teach/reference/season3-plan.html`；**预算纪律：季末余量已被 S10 黄修吃进 ~14 行（1330/1500，S11+S12 规划 ~150 行），黄修继续文档/断言优先**
4. **挂账：S9 收口面试**（F12 in_progress、改动未 commit；恢复点=STEP 0 复测两问 + 五考点 Artifact https://claude.ai/code/artifact/8c2879a6-baa2-4e01-a091-36b0cf327bcd ；新规则=逐问小标题作答）。过了才有 tag sfs-s9
5. 第三季全景（已拍板 D1=A/D2=B/D3=A）：S10 防打转+预算闸 → S11 ReadBeforeWrite → S12 执行安全三件套 → 季末整合理论课+全项目总复习面试。设计稿 `teach/reference/season3-plan.html`（Artifact https://claude.ai/code/artifact/66410217-0fbb-4937-9d87-fba39b447df1 ）

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
