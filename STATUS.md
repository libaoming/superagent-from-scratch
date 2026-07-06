# STATUS — superagent-from-scratch

> 每次 session 第一个读的文件。收尾必更新本文件。

## 一句话状态
2026-07-04 **F01_agent_loop passing（1/8）**：fixture 先行 → 测试先红 → src/llm.py（LLMClient 协议 + FakeLLM + AnthropicLLM）+ src/loop.py（run 循环，终止条件 1/2）实现绿，`pytest tests/test_s1_loop.py -q` 7 passed（无 API key 复跑同绿）；pyproject（uv）落地；src 115 行。Deviations D1-D3 见 M1/PROGRESS.md 待核对。

## 下次入口
1. 读本文件 → 读 `M1/PROGRESS.md`
2. 跑 `bash M1/init.sh` 确认环境
3. 当前应做：**F02_real_tools**——写 `tests/test_s1_tools.py`（先红：bash/read_file/write_file 三真实工具契约 + research_task.json 驱动的 FakeLLM×真工具集成）→ 实现 `src/tools.py`（读 SPEC #tools：bash 超时 60s、非零退出码回文本不抛异常；read_file 带行号同 cat -n）
4. F02 绿后 = S1 代码侧完成 → 补 `notes/` S1 拆解笔记 + `scripts/e2e_s1.py`（ClaudeCLILLM 真实 E2E，PRD 验收 4）→ 对抗审查 → `git tag sfs-s1`（tag 前需先 `git init`，待用户指令）
5. 待用户指令：`git init` + GitHub 建仓（用户要开源，未明确让动 git）

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
