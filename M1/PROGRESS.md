# M1 PROGRESS

| 字段 | 值 |
|---|---|
| active_feature | （无——F01 已收口，下一个 F02_real_tools） |
| slice | S1 |
| 更新 | 2026-07-04 |

## Next Candidates
- F02_real_tools（S1）—— bash/read_file/write_file 三真实工具 + research_task.json 集成

## Blockers
- （无）

## Deviations（偏离 SPEC/计划的决定 · 逐条向用户核对后清账）
- **D1（F01）**：S1 的 `run()` 签名暂不含 `middlewares` 参数（SPEC #loop 伪代码含三条 middleware 链）。理由：Middleware 协议是 F03 交付物，S1 加空链 = 无消费者的扩展点（反模式 4）；C4 签名冻结从 S2 起算，S2 以关键字参数补入不破坏 S1 导入。
- **D2（F01）**：State 只含 `messages` + `turn_count`，SPEC 数据模型里标注 "S5:" 的 `todos`/`goal` 字段推迟到 S5 落地（字段纪律：必须被切片测试断言用到）。
- **D3（F01）**：AnthropicLLM 默认 `model="claude-opus-4-8"`、`max_tokens=16000`、不传 thinking/采样参数（claude-api skill 当前指引；SPEC 未规定默认值）。

## Session Log（倒序）
### 2026-07-04
- （晚间）F01 学习手册 artifact 发布（含循环步进器/自测6题/30min动手路径），已按下午 SPEC 页模版对齐（ivory+clay/宋体标题/16px/800px），模版偏好存入 Auto Memory：https://claude.ai/code/artifact/72f95524-2b11-4668-8d52-0b27ff26e2aa
- （晚间）**F01_agent_loop 完成 → passing**：C5 顺序走完——fixture 5 个（natural_close/echo_roundtrip/parallel_tools/endless_tool_calls/research_task + workspace/data.md）→ test_s1_loop.py 先红（ModuleNotFoundError）→ src/llm.py + src/loop.py 实现 → 7 passed（无 API key 环境复跑同绿）。pyproject.toml 落地（uv，C2 依赖仅 anthropic+pyyaml）。src 共 115 行。产生 Deviations D1-D3 待用户核对。
- （晚间）harness 进度速查（0/8 pending，F01 应做）→ 用户下令开工 F01。
- （下午→傍晚）打开 SPEC review；artifacts 页面链接确认；对齐 memory-kit 理解；四决策拍板（1A 2A 3A 4B）+ 拓展性规则落地进 SPEC/PRD/CLAUDE.md。
- 项目脚手架完成（4 层骨架）。下一步：文档先行填 PRD/SPEC/architecture。

## 如果…就…
- 如果不知道做什么 → 按 AGENTS.md「选 feature 算法」
- 如果 fixture 缺 → 先造 fixture，不许 mock
- 如果要核查线上/读大文件 → 派 `.claude/agents/superagent-from-scratch-ops.md` 子 agent，别在主 context 拉原始输出

## 🤖 增量流水（待整理）
- [2026-07-04 18:51] 当前项目进展 把spec 文件打开
- [2026-07-04 18:53] 下午 artifacts 的页面不是有链接吗
- [2026-07-04 18:56] 发一个新的
- [2026-07-04 19:41] 匹配我的 memory-kit 更好的理解
- [2026-07-04 19:58] 输出一张紧凑的进度表 + 一句「下一步」。如果当前目录没有 features.json，直接说这不是 harness 项目，并提示可用 `/harness-kit:harness-init` 初始化。
- [2026-07-04 20:02] 6点后的版本 我不喜欢  你排查下
- [2026-07-04 20:07] - **WIF auth: unset `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, and `ANTHROPIC_PROFILE`.** `ANTHROP
- [2026-07-04 20:12] - Spend your boldness in one place; keep everything around it quiet. If the accent fights the ground
- [2026-07-04 20:13] plan-推理 -code vs loop
- [2026-07-04 20:19] 按下午的模版即可 不用新建模版
- [2026-07-04 20:23] 关机 回家
- [2026-07-06 09:22] 输出一张紧凑的进度表 + 一句「下一步」。如果当前目录没有 features.json，直接说这不是 harness 项目，并提示可用 `/harness-kit:harness-init` 初始化。
- [2026-07-06 09:26] - Spend your boldness in one place; keep everything around it quiet. If the accent fights the ground
