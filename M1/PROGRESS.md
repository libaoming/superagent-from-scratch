# M1 PROGRESS

| 字段 | 值 |
|---|---|
| active_feature | S2 收口中（F04 已 passing） |
| slice | S2 |
| 更新 | 2026-07-08 |

## Next Candidates
- S2 收口序列：notes/03 回填（三件实战 + fixture 坑）→ 对抗审查（子 agent）→ 第 3 课（teach 实战课）→ 收口面试模拟（考点清单五条，规矩 6）→ `git tag sfs-s2`
- 顺路可清「对抗审查遗留」便宜几条

## S5 备忘（S2 审查 2026-07-08 顺手发现，非本切片账）
- Interrupt.question 目前被 loop 丢弃（loop.py 只 return state，question 无返回通道）——S5 的 ask_clarification 需靠 middleware 自持状态取回（可行、不破 C4），落地时别忘

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
- ~~**D4（教学环流程）**~~ ✅ 2026-07-07 已确认：落地「切片教学环」时两处按 Claude 推荐拍板——①面试问题环节与规矩 6 收口 quiz **合并升级**（不并存两个 quiz）②过关标准从「满分」改「**面试官 rubric**（命中要点即过）」。用户批准含此两点的 plan + 补充指示「用一场面试准备的思路来讲解和检查」，视为确认。

## Session Log（倒序）
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
<!-- Stop hook 自动追加区。2026-07-08 已整理 49 条：07-07 全天教学批次（0001 课问答/S1 面试模拟/补考清账/0002 课预习）归并为 07-07「S1 教学环补跑完整一轮」条，教学细节在 teach/learning-records/0002；07-08 批次（0002 课问答/F04 理论确认/开工）归并进 07-08 两条既有 Session Log + learning-records/0003；噪声丢弃（10:28 路径片段、15:44 设计 skill 文本、11:50 图片占位）。 -->
- [2026-07-08 14:10] 继续收口
- [2026-07-08 14:15] 总评：实现干净、测试纪律好，唯一必须处理的是 Summarization 与工具历史组合时的消息配对破坏——修它或显式豁免它，不能悬着。</result>
- [2026-07-08 14:24] [Image: source: /Users/baomingli/.claude/image-cache/2a54404f-7972-4181-86fa-fd69fdd81932/2.png]
- [2026-07-08 14:34] 这个是在哪生效定义的
- [2026-07-08 14:36] 这个 run 函数有什么作用
- [2026-07-08 14:39] 考我S2
- [2026-07-08 14:53] 5. middelware 架构对产品商业化分层、增加新能力都有很好的架构便捷
- [2026-07-08 15:04] 3. raise interrupt 是设计
- [2026-07-08 15:11] 问题 after_model 现在看来 主要是 raise interrupt  ask_clarifaction
- [2026-07-08 15:15] 预算为啥不挂在 after_model 钩子上 挂在这个钩子上 超限额了 后面的 tool_use 就不会继续浪费tokens
- [2026-07-08 15:18] 当前学习进展
- [2026-07-08 15:34] middleware 对PM设计有什么帮助
- [2026-07-08 16:36] 重考 S2
- [2026-07-08 16:46] 5. 产品规划和 middlewave 同构, 颗粒度一致。可以在评估竞品能力、商业化能力分层设计，按数量、按开关来设计
- [2026-07-08 16:52]       对象，让三个出口在 run() 里排队站好。
- [2026-07-08 16:55]       "system", "max_turns"]；连同三条缝的协议签名（LLMClient.complete、Tool 四件套）一并冻结。谁想改引擎签名（删参、改名、调序），这条断言先红，变更
- [2026-07-08 17:00] 保证 保留区 不存在 tools_result 孤儿
