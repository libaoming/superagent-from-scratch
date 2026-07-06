# CLAUDE.md — superagent-from-scratch

> 教学向极简 SuperAgent harness —— 千行级复刻 bytedance/deer-flow 核心架构（agent loop → middleware 管线 → subagent 委派 → skills → 长任务），Python 3.12、零框架依赖、fixture 先行，英文主 README 双语开源（MIT）

本项目采用 harness 方法论 + 4 层防御体系（Anthropic "Effective Harnesses for Long-Running Agents" + 得物 Harness 工程实践）。

## 入会顺序（每次新 session）
1. **先读 `STATUS.md`** —— 一句话状态 + 下次入口 + 踩坑清单
2. 再读 `PRD.md` / `SPEC.md` / `architecture.md` / `features.json`（三件套覆盖需求/方案/切片）
3. 开工前跑 `bash M1/init.sh` 确认环境全绿

> 🤖 **增量流水合并（每次启动先做）**：若 `M1/PROGRESS.md` 有「🤖 增量流水（待整理）」块（Stop hook 每轮自动追加的原始请求），**先合并进正式 Session Log、清空该块，再开工**。

> 🧹 **本文件当代码对待（Anthropic best-practices）**：Claude 做错一次的事就写进来；定期 prune——每行自问「删掉会让 Claude 犯错吗」，不会就删（规则被噪声淹没=没有规则）；每条约束都是对模型当前能力的临时假设，模型升级后主动做减法。

## 仓库结构
```
superagent-from-scratch/
  CLAUDE.md              本文件（L1 持久化 + L4 隔离纪律）
  STATUS.md              新 session 入口（L1）
  PRD.md / SPEC.md / architecture.md   文档先行三件套（L2 输入源）
  features.json          原子 feature 单一事实源（L2）
  CONTEXT.md             上下文构成审计（CE 产物，LLM 项目才有 → context-engineering-kit）
  M1/         里程碑三件套（init.sh / AGENTS.md / PROGRESS.md）
  fixtures/              fixture（先于代码，含 README 索引；fake-LLM 录制响应放 fixtures/fake_llm/）
  src/                   实现（loop.py / llm.py / tools.py / middleware.py / middlewares/ / subagent.py / skills.py）
  tests/                 每切片一组 pytest（test_s1_*.py ... test_s5_*.py），离线可跑
  notes/                 deer-flow 拆解笔记（中文，橙研所底稿）
  .claude/agents/        项目专属子 agent（L4 脏活隔离）
```

## 项目身份（教学复刻的特殊纪律）
- 参考蓝本 `~/deer-flow` 是**只读教材**：只 Read/grep，绝不修改；复刻时理解思想重写，不复制代码（License 干净）
- **千行级预算**：src/ 总行数目标 ≤ 1500 行——超了说明在复刻产品功能而非教学核心，砍
- 每个切片完成后，`notes/` 必须有对应拆解笔记（学到什么 → 我怎么简化 → 为什么 → 产品化拓展练习 1-2 道）——笔记和代码同等重要，这是「边学边开源」的学的部分
- **拓展性纪律（三缝一表一练习）**：拓展性只允许三个载体——三条缝的协议冻结承诺（SPEC C7）、SPEC「产品版/教学版全景对照」表（#product-vs-teaching）、笔记末拓展练习。**主干代码永远只保教学版**，任何「顺手为产品版预留」的代码 = 违反 SPEC 反模式 4，砍

---

## 4 层防御体系（本项目的工程底座）

### L1 持久化层
业务语义 / 规则 / 进度从不可靠的 LLM 记忆迁到确定性文件：`CLAUDE.md`（规则）+ `STATUS.md`（进度，每次 session 收尾必更新）+ Auto Memory（跨会话）。

### L2 方法论层（开发纪律）
- `features.json` 是**单一事实源**：status ∈ {pending, in_progress, failing, passing}，**verify 真跑通才能改 passing**
- 🚦 **verifier 硬闸门**：feature 的 `verify` 字段为空 = **不准开工**（不能离开 pending）。每个目标必须带可衡量的成功信号——"没有验证机制的目标只是许愿"
- 🧭 **三段式关联**：每个 feature 必须填 `related`/`affected`/`out_of_scope`，让 subagent 秒判"读哪些、不读哪些"，对治 context 膨胀（OpenSpec Related Context 实践）。`out_of_scope` 同时防 AI 联调复刻隐性功能
- **线性切片**推进：每切片有 exit_criteria + git_tag，完成才进下一个
- **fixture 先于代码**：verify 引用的 fixture 不存在就先造，不许 mock、不许"等真数据"
- 三件套放 `M1/` 子目录，不放根目录

### L3 自动化钩子层
确定性自动化放项目级 `.claude/settings.local.json`（local 不入 git）。**已内置一对 Stop hook**：
- `stop-progress-append.sh`（异步）——每轮把用户请求增量追加到 `M1/PROGRESS.md` 的「增量流水」区，扛关电脑、不调 LLM。
- `stop-verify-claims.py`（同步）——**防造假收口闸**：末轮出现「已写/已落盘/File created + 文件名」或交付表 `path`（N 行）时逐一 `test -f`，有声称却磁盘不存在的文件就 exit 2 拒绝收口、把缺失清单喂回强制真核验。把 CLAUDE.md 的软规则「完成声明前先回读」在 Stop 边界机器化（缺 python3 自动降级 no-op，fail-open）。

其它按需加（session 启动注入 / 产物同步 / 提交前校验）。

### L4 上下文隔离层 ⭐
把"吃大量 context 的脏活"派给子 agent（**Agent 工具, `subagent_type=general-purpose`** 或下方项目专属子 agent）在独立 context 跑完，**只回结论**；主 context 保持干净，专注改代码决策 + 跟用户对话。

**必须隔离的脏活（派子 agent，prompt 自包含）**
- 大文档检索：PRD/SPEC/大 features.json/长日志 → 子 agent 读完只回「相关切片 / 答案」，主 context 绝不整文件 Read
- 远程/生产状态核查：ssh 日志、systemctl、容器日志（动辄上千行）→ 子 agent 只回结论
- 大数据/transcript 分析 → 子 agent 只回诊断结论

**留主线（不外包）**：改代码、架构决策、跟用户对话、verify 判定

**🚨 子 agent 铁律**
1. prompt **完全自包含**：写死路径、命令、远程 alias（子 agent 冷启动看不到对话）
2. **远程/生产只读**：对线上只允许 `systemctl is-active` / `journalctl` / `docker logs` / `grep` / `cat` 这类只读命令
3. **改动只在本地**：不擅自 `git push` / `pull` / 重启线上 / 改生产配置；部署是用户显式触发的独立动作

---

## 上下文工程纪律（LLM 项目）

若本项目调用 LLM（agent / chat / 工作流），`CONTEXT.md` 是 harness 四件套的第四件（`features.json` + 三件套 + **CONTEXT.md**）：
- **开工前**：写第一行 LLM 调用代码前先画 `CONTEXT.md`（7 层上下文构成 + 暗物质审计）
- **改动前**：改任何 system prompt / 上下文拼装代码前先读 CONTEXT.md
- **改动后**：回填 CONTEXT.md，防文档腐烂
- 模板与方法 → [context-engineering-kit](https://github.com/libaoming/context-engineering-kit)

## verify 纪律
- **开工闸门**：`verify` 字段为空的 feature 不准动（停在 pending），先定义可衡量的成功信号再开工
- `features.json` status：单测通过只到 `in_progress`；**真实端到端 verify 通过才能改 `passing`**
- verify 通过的细节写进 feature 的 `verify_notes`

## 命名约定
（按需补：git branch / docker tag / 代码注释 vs 用户可见文案）
