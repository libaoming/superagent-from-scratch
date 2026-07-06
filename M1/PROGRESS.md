# M1 PROGRESS

| 字段 | 值 |
|---|---|
| active_feature | F03_middleware_protocol |
| slice | S2 |
| 更新 | 2026-07-06 |

## Next Candidates
- F03_middleware_protocol（S2）—— before_model/after_model/wrap_tool_call 协议 + 挂载进 loop（D1 清账时机：run() 以关键字参数补 middlewares）

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

## Session Log（倒序）
### 2026-07-06
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
<!-- Stop hook 自动追加区。2026-07-06 已整理 16 条：07-04/07-06 各批次归并进上方 Session Log；skill prompt 片段（进度表指令×2、设计 skill 文本×2、WIF auth 行）判为 hook 误抓噪声丢弃。 -->
- [2026-07-06 11:01] 先清流水
- [2026-07-06 11:05] 开工 F02
- [2026-07-06 11:25] id 请自造且不重复（e1、e2…）。
- [2026-07-06 11:25] id 请自造且不重复（e1、e2…）。
- [2026-07-06 11:25] id 请自造且不重复（e1、e2…）。
- [2026-07-06 11:26] 继续
- [2026-07-06 11:32] 一句话结论：代码主体对 SPEC 忠实度高、测试纪律好；三个真发现集中在「说了但没做」——BashTool 的 cwd 承诺、C1 的机器闸门、features.json 的 LangChain 残留
- [2026-07-06 14:22] - **Exploring alternative interfaces** — see [DESIGN-IT-TWICE.md](DESIGN-IT-TWICE.md): spin up paral
