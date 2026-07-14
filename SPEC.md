# SPEC — superagent-from-scratch

> v1 · 2026-07-04 · 技术规范 + 教学设计。写作原则：记决策不记文件路径；每个决策带「为什么」和「deer-flow 对照」——这是教材的 SPEC，why 和 what 同等重要。
> 章节锚点（#loop #tools #middleware #subagent #skills #long-task）与 features.json 的 `related.specs` 一一对应。

## 数据模型 / Schema

### 消息（Message）

**决策：直接采用 Anthropic Messages API 的原生消息形状，不自造中立格式。**

```python
# 对话历史 = list[dict]，形状与 Anthropic API 一致
{"role": "user" | "assistant", "content": str | list[ContentBlock]}
# ContentBlock 三种：
{"type": "text", "text": str}
{"type": "tool_use", "id": str, "name": str, "input": dict}          # assistant 发出
{"type": "tool_result", "tool_use_id": str, "content": str}          # user 角色回填
```

为什么：教学项目多一层自定义格式 = 读者多学一套没用的抽象，且转换层是 bug 温床。deer-flow 用 LangChain 的 `AIMessage/ToolMessage` 中立格式是为了多 provider，我们 out of scope 了多模型，就该拿掉这层。**代价**（诚实交代）：绑死 Anthropic 形状；tool_result 必须以 user 角色回填是新手最容易踩的 API 事实，正好显式教。

### 会话状态（State）

```python
@dataclass
class State:
    messages: list[dict]          # 唯一事实源
    todos: list[dict] = ...       # S5: [{"content": str, "status": "pending|in_progress|completed"}]
    goal: str | None = None       # S5: 目标闭环
    turn_count: int = 0           # loop 熔断计数
```

为什么这么小：deer-flow 的 ThreadState 有 12+ 字段（sandbox/artifacts/delegations/skill_context/...），每个字段服务一个产品功能。教学版原则——**state 里每个字段必须至少被一个切片的测试断言用到**，否则删。

### fake-LLM fixture（测试接缝的数据格式）

```json
// fixtures/fake_llm/<场景>.json —— 一次对话的录制响应序列
{
  "description": "研究任务：多轮工具调用后收口",
  "responses": [
    {"content": [{"type": "tool_use", "id": "t1", "name": "bash", "input": {"command": "ls fixtures/workspace"}}]},
    {"content": [{"type": "tool_use", "id": "t2", "name": "read_file", "input": {"path": "fixtures/workspace/data.md"}}]},
    {"content": [{"type": "text", "text": "结论：..."}]}
  ]
}
```

约束：`responses` 按序弹出，弹尽后再调用 = 测试失败（fixture 覆盖不足，属测试 bug）。fixture 内路径一律相对仓库根。
**录制 = 全局调用序，不是主对话序**（盲区回填 2026-07-04）：Summarization 的压缩调用、goal 达成判定调用、subagent 的全部调用都消耗同一 `responses` 序列——S2/S3/S5 的 fixture 必须把这些「隐藏调用」也按实际发生顺序录进去，否则测试神秘变红。

### 技能（Skill frontmatter）

```yaml
# skills/<name>/SKILL.md 头部，YAML frontmatter
name: demo-skill        # 必填，= 斜杠激活名
description: 一句话      # 必填，常驻系统提示的唯一内容
```

只留两个必填字段。deer-flow 还有 license/allowed-tools/required-secrets——分别服务分发合规、权限收窄、凭证注入，全是产品关切，教学版砍（见 F06 out_of_scope）。

## 接口 / 协议

### LLM 客户端（唯一测试接缝）{#llm}

```python
class LLMClient(Protocol):
    def complete(self, *, system: str, messages: list[dict], tools: list[dict]) -> dict:
        """返回一条 assistant message（原生形状）。无网络错误处理责任——那是 middleware 的事。"""
```

两个实现：`AnthropicLLM`（薄包 SDK，<40 行）和 `FakeLLM`（读 fixture 按序弹出）。**协议刻意只有一个方法**——接缝越窄，越难在测试里作弊。

### 工具（Tool）{#tools}

```python
class Tool(Protocol):
    name: str
    description: str            # 给模型看的，写「何时用」而非「是什么」
    input_schema: dict          # JSON Schema
    def run(self, **kwargs) -> str: ...   # 永远返回 str；异常往外抛，middleware 接
```

内置三件：`bash`（subprocess，timeout 60s，超时/非零退出码都作为文本结果返回而非异常——模型需要看到 stderr 学会自纠）、`read_file`（带行号，同 cat -n）、`write_file`。
**决策：工具不做沙箱。** deer-flow 的虚拟路径映射（/mnt/user-data → 物理路径）服务多租户隔离；教学版单机自用，加沙箱是把读者拖进无关复杂度。笔记里讲清「生产环境为什么必须有」即可。

### 循环（loop）{#loop}

```
run(state, llm, tools, middlewares, system) -> State
  循环体（每轮 = 一个 turn）：
    1. before_model 链（注册序）
    2. resp = llm.complete(system, messages, tools)
    3. messages.append(resp)
    4. after_model 链（逆序）           ← 中断信号在这里产生（S5 clarification）
    5. 无 tool_use block → return       ← 自然收口
    6. 逐个执行 tool_use：wrap_tool_call 链包裹 tool.run，结果回填 tool_result
    7. turn_count += 1；超 max_turns(默认 40) → 强制收口
```

终止条件穷举（教学要点，必须在笔记里画状态图）：**自然收口**（纯文本响应）/ **turn 熔断** / **中断信号**（middleware 返回 Interrupt）。没有第四种。

### middleware 协议 {#middleware}

```python
class Middleware:
    def before_model(self, state) -> None: ...                    # 改 state 就地
    def after_model(self, state) -> Interrupt | None: ...         # 可发中断信号
    def wrap_tool_call(self, call_next, tool, args) -> str: ...   # 洋葱模型，必须调 call_next
```

执行顺序语义（与 deer-flow/LangChain 一致，刻意保留用于对照教学）：before 按注册序、after 按**逆序**、wrap 按注册序包裹（先注册者最外层）。为什么逆序：保证「先进后出」的对称包裹——先注册的 middleware 最先看到输入、最后看到输出，像栈帧。
内置三件（S2）：`ToolOutputBudget`（wrap，结果超 N 字符截断+标注）、`ToolErrorHandling`（wrap，捕获异常转错误文本回填，run 不死）、`Summarization`（before，messages 超阈值时保留近 K 条 + 用 llm 压缩其余为一条摘要消息）。
**llm 注入方式（2026-07-04 拍板 · Q1=A）**：需要 llm 的 middleware 走**构造注入**（`Summarization(llm=...)`），协议三方法签名不变——接缝最窄，谁需要谁持有；不给协议加参、不挂 state（state 字段必须被测试断言原则）。

### subagent 委派 {#subagent}

```python
# task 也是一个 Tool，从而复用全部工具管线——这是 deer-flow/Claude Code 的同款决策
task(description: str, prompt: str) -> str   # 返回 = subagent 最终文本，即「只回结论」
```

契约：subagent 开**全新 State**（空 messages，prompt 即首条 user 消息）；复用同一 llm + 除 task 外的全部工具（防无限递归，单层委派）；跑同一个 loop 函数（**教学要点：subagent 不是新机制，是循环的递归调用 + 上下文隔离**）；同一 turn 多个 task 调用超过 max_concurrent(3) 的部分直接回错误文本。同步顺序执行——deer-flow 的线程池/SSE 事件流服务前端展示，教学版砍。

### skills {#skills}

发现：启动时递归扫 `skills/**/SKILL.md`（rglob 任意深度），解析 frontmatter；**description 常驻 system prompt，正文一个字不进**。
激活：用户消息以 `/名字 ` 开头 → 该 SKILL.md 全文作为当轮附加上下文注入。
**注入点（2026-07-04 拍板 · Q3=A）**：全文拼为当轮 user 消息的**前缀块**（进 history、可被 Summarization 正常压缩、测试断言直接查 messages）；不动 system。
教学要点（token 经济学）：元数据便宜（常驻）、正文贵（按需）——这就是 Claude Code skills 与 deer-flow SkillActivationMiddleware 的共同设计内核。

### 长任务三件套 {#long-task}

- `write_todos`（Tool）：全量替换 state.todos，渲染进下轮 before_model 注入的提醒——**计划外置**：计划活在 state 不在模型脑子里，摘要压不掉。
- goal 续跑：run 收口后若 state.goal 非空 → 用同一 llm 判定「对话证据是否达成目标」→ 未达成则注入隐藏 user 消息（"目标未完成，继续"）重进 loop；上限 8 次 + 熔断（连续 2 次无新 assistant 文本产出即停）。deer-flow 用独立 evaluator 模型 + 类型化 blocker，教学版同模型简单判定（F07 out_of_scope）。
  **落点（2026-07-04 拍板 · Q2=A）**：外层 `run_with_goal()` 包裹纯净 `run()`——loop 签名不动（C4 不受扰），续跑是 harness 外壳，外置本身即教学点「long-horizon 是 harness 套的目标闭环」。**turn_count 每次续跑重置**（单次 run 上限 40 不变），续跑总量由次数上限 8 独立管控——两个熔断各管一层（盲区回填）。
- `ask_clarification`（Tool + Middleware 配合）：工具本身不执行任何东西；`Clarification` middleware 在 after_model 看到该 tool_use → 返回 Interrupt(question)，loop 收口把问题带出去；调用方拿到用户答案后把 tool_result 补进 messages 重新 run——**中断 = 保存现场的正常收口，恢复 = 带着答案重进循环**，没有魔法。

### 长期记忆 {#memory}（第二季 · S6）

核心 aha：**记忆的「写路径」是一条独立于对话循环的旁路**——对话不因「要更新记忆」而变慢/变脏，记忆异步长在旁边。对照 S2 摘要（session 内压缩）：这是**跨 session 记忆**。deer-flow 用 `after_agent`/`before_agent` 中间件钩子；本项目这两个是 **per-run** 操作，而 middleware 协议只有 per-turn 钩子（C7 冻结）。

**落点（2026-07-09 拍板 · M1=外壳、M2=user role）**：
- **M1 挂载点 = loop 外的 harness 外壳 `run_with_memory()`**——与 S4 skills、S5 goal 同构，`run()` 零改动（C4）。备选「给协议加 before_agent/after_agent 钩子」被否决（破 C7；本项目核心纪律是协议冻结）。「写路径独立于对话循环」的 aha 在外壳形态下最干净——memory 字面就在 loop 外。
- **写路径**：`run()` 收口后 → 过滤消息（只留 human + 无 tool_call 的最终 ai）→ **入队快照**（不是立即更新）→ 去抖（Timer/debounce，同 key 折叠）→ 后台调 llm：把「旧记忆 + 新对话」merge 成新记忆落盘。**去抖 + 后台线程是必留内核**（否则丢了「异步、不阻塞对话」）。测试经 `flush()` 同步排空、不依赖真实 Timer。
- **updater 协议**：llm 出**增量指令** `{user, history, newFacts, factsToRemove}`（user/history 即下方 6 段摘要），代码做**确定性 merge**（6 段非空才覆盖 + facts 过 confidence 门槛 + 内容去重 + max_facts 截断）——**不是全量重写**，防「LLM 手一抖把整个记忆改乱」。
- **M2 读路径 = 注入成 user 角色**（2026-07-09 拍板）：`run()` 前加载记忆，按 confidence 降序拼成 `<memory>…</memory>`，作为 **user 角色**消息注入首条 user 前（**不给 system 权限**）。理由：记忆源自用户、可被污染（OWASP LLM01）——**框架数据 vs 用户数据的信任边界**，是保留的安全教学点。

**三缝协议冻结（C7 延伸）**：① `after run` → queue 的「对话快照入队」；② queue → updater 的 `(messages, old_memory) → update_json`；③ `before run` 的 `<memory>` 注入形态（user 角色）。

教学版数据模型**沿用 deer-flow 结构**：单文件全局 JSON = **6 段结构化摘要**（`user` 按画像侧面切：workContext 工作/personalContext 个人/topOfMind 当前焦点；`history` 按时间远近切：recentMonths/earlierContext/longTermBackground）+ 带类型 `facts` 列表 `[{content, confidence, category}]`。段级更新语义：updater 出非空字符串才覆盖该段（空=不改）。**砍**：per-slot updatedAt、检索/embedding（deer-flow 本就全量注入、无检索）、多租户 per-user/per-agent、tiktoken 精确预算、trace、async 连接池规避、原子写、prefix-cache/ID-swap、上传洗涤、手动 CRUD。

### 断点持久化 {#checkpointer}（第二季 · S7）

核心 aha：**checkpoint = State 的全量快照按轮落盘——「保存现场」从内存升级到磁盘，进程可死、任务不死**。真 checkpointer 语义是 **per-step durability**（每轮都存，崩溃只丢半轮），不是 save-on-close。这里兑现两笔旧账：S5 的「保存现场 = state 在内存」简化（F08 out_of_scope 明写不做断点序列化）+ notes/06 拓展练习 2。

**落点（2026-07-10 拍板 · M1=缝①+外壳、M2=悬空兜底保留）**：
- **M1 挂载点 = 缝① `Checkpointer` middleware（per-turn 存）+ 外壳 `run_with_checkpoint` 收口终存**。middleware 在 `before_model` 每轮落盘（此刻上一轮 tool_result 已 append，快照完整）；外壳收口再终存一次（自然收口后没有下一轮 before_model，最终回复只能靠终存）。**注册序语义**：外壳把 Checkpointer 放 middleware 列表头——快照是本轮其它 middleware（Todo 重注/摘要压缩）**改写前**的轮间态；无害（改写幂等，恢复后重跑即得），但语义要说明。备选「纯外壳收口存」被否决——丢掉 per-step durability，那是 save-on-close 不是 checkpointer。**与 S6 成对照教学点：挂载点由操作节奏决定——per-run 的事走外壳（S6 memory），per-turn 的事走缝①（S7 checkpoint）**；这也是缝①第一次收「持久化」类住户，协议签名零改动（C7）、run() 零改动（C4）。
- **恢复路径**：`load_state(path)` 重建 State →（HITL 场景）补答案 tool_result + 清 interrupt → 重进 `run()`——**与 S5 恢复流程同构**，checkpointer 只是把「State 在内存」换成「可落盘回装」。
- **M2 悬空 tool_use 兜底（保留，~15 行）**：恢复的 State 若末条 assistant 带 tool_use 而无配对 tool_result，下轮请求直接 API 400。`load_state` 检查并补合成 `[interrupted]` tool_result（仅 interrupt 为空时——interrupt 非空是 HITL 待答悬空，答案归调用方补）。这是 deer-flow 用 205 行 DanglingToolCallMiddleware 换来的教训，也是 S2 摘要配对坑的姐妹篇（同一条 API 硬约束的两个引爆点）。**触发面说实（对抗审查 2026-07-10）**：本 checkpointer 自产档不会产生「interrupt 空的悬空」——before_model 快照永远轮间完整、终存悬空必伴 interrupt 非空；该兜底实际是防**外源/手造档**与**第三方 middleware 返回 Interrupt 却不 stash state.interrupt** 的防御层。

**deer-flow 对照（子 agent 核实 2026-07-10）**：它在这个切片上是 **0% 内核 + 100% 胶水**——存/取/恢复全在 LangGraph 官方 saver 库里（InMemory/Sqlite/PostgresSaver），自己的 ~458 行全是工厂/单例/配置胶水；保存节奏是 LangGraph 每 super-step 自动存。**生产代码没用 `interrupt()`/`Command(resume)`**——clarification 走「正常收口 + 同 thread 新消息续跑」，与本项目 S5 设计同构。教学版手写的正是库包办的三件事：存什么（State 全量 JSON）、何时存（每轮）、怎么恢复（载入+补消息+重进）。

**数据模型**：单文件 latest-only JSON（调用方给 path，即最简 thread key）；State 五字段全 JSON 友好，`Interrupt` ⇄ `{"question": ...} | null`。**砍**：checkpoint_id 谱系/time-travel/回滚、多后端工厂与单例锁、pending_writes、多租户/TTL/迁移、并发写锁、`Command(resume)` 兼容层、原子写。

### deferred tools {#deferred-tools}（第二季 · S8）

核心 aha：**tools 定义是上下文第 2 层的常驻成本——deferred tools 把「能力」也做成按需注入：未加载时模型只见名字，搜索命中才晋升出完整 schema**。与 S4 skills 完美对仗：skills 是**知识层**按需注入（元数据常驻 / 正文激活才进），deferred tools 是**能力层**按需注入（名字常驻 / schema 晋升才进）。deer-flow 实况（子 agent 核实 2026-07-10）：`tool_search` 四件 397 行（内核 ~250），只 defer MCP 工具，动机双写在配置注释里——省上下文 + 提工具选择准确率。

**落点（2026-07-10 拍板 · M1=loop 内过滤、M2=双通道）**：
- **露**：deferred 工具（`deferred: bool` 字段标记，教学版不做 MCP 标签）不进 tools 绑定，只在 system 尾部渲染 `<available-deferred-tools>` **纯名字清单**（deer-flow 连摘要都不给——description 藏着但可被搜索命中）。名单静态常驻 = prompt cache 友好；晋升改变 tools 集合、必然破一次前缀缓存，机制固有代价。
- **搜（缝③ 元工具）**：`tool_search(query)` 支持 `select:Name1,Name2` 精确取 + 关键词匹配（搜 name+description）两种，最多回 5 个。**砍** deer-flow 的 `+prefix` 语法与 regex 降级容错。
- **M1 藏 = loop 内每轮过滤（run() 零改动的 8 连胜到此终止，C4 签名仍冻结）**：schema 构建移进循环体，每轮按 `state.promoted`（State 新字段）过滤后提交。为什么必须碰 loop 内部：**治理对象就是「每轮的 tools 提交点」，而提交点在 loop 里**——三钩子只收 state、碰不到 tools 参数（C7 冻结不许改签名）。备选「外壳重进」（借 S5 中断语义，每次晋升多一轮收口/重进往返）与「stub schema 渐进披露」（机制失真：没有真藏/晋升/拦截）被否决。deer-flow 的对应物本就是 middleware 每轮覆写 request.tools——loop 内过滤是它在本架构下的最诚实等价。
- **M2 晋升 = 双通道（deer-flow 同款）**：tool_search 命中后 ① 当轮 tool_result 直接给完整 schema JSON（**当轮可读**，能规划参数）② 名字写进 `state.promoted`，下轮过滤放行、schema 进绑定（**下轮可调**）。
- **拦（缝① guard）**：**藏的是 schema 不是工具本身**——执行层 tool_map 始终持有全部工具。录制/幻觉可能调未晋升工具，`DeferredGuard` 在 wrap_tool_call 拦截、回教学式 error tool result（「工具 X 未加载，先调 tool_search…」）教模型自救而非崩溃。
- **跨切片账（S7 联动）**：`state.promoted` 入列 State ⇒ S7 `save_state`/`load_state` 的字段表必须同步（否则 checkpoint 恢复后晋升丢失、已读 schema 的工具重新隐身）——S8 落地时一并改 + 断言进 roundtrip 测试。set 不可 JSON 化：存 sorted list、载回 set。

**教学骨架一句话**：露（system 名单）— 搜（缝③ tool_search）— 晋升（双通道进 state）— 藏（loop 提交点过滤）— 拦（缝① guard）。三条缝 + loop 提交点各司其职，这是全项目第一个「四个部位协同」的切片。

**砍**（deer-flow 产品化 ~150 行）：catalog_hash 防目录漂移、fail-closed RuntimeError、pydantic 配置开关、`+prefix`/regex 降级、MCP 标签模块、subagent 镜像装配、晋升驱逐/降级。

### eval 闭环 {#eval-loop}（第二季 · S9）

核心 aha：**agent 的输出开放、非确定，eval 不是 `assert equals`，是「量分 + 记账 + 一次一改 + 不涨回退」**。前八刀是「怎么造」，这刀是「怎么知道造对了、怎么让它系统性变好」。第一个被评对象 = `goal.py` 的 `_goal_met`——**它本身就是个 LLM judge（YES/NO），却从没被量化测过**：S5 对抗审查记过 `startswith("YES")` 对「YESTERDAY 开头回复」的假阳性（Y1），正是「没有 eval 的 judge」躲过的那种坑。

**落点（2026-07-12 拍板 · M1=_goal_met+程序化 accuracy、M2=量分+记账+手动一次一改、M3=prompt 抽常量）**：
- **M1 被测对象与打分**：被测 = `_goal_met`；案例带 ground truth 标签（该判达成/不该判达成），打分 = **程序化 accuracy**。教学点：**能程序判定就不用 LLM-as-judge**——judge 留给无标签的主观质量（摘要保真度等，见对照表）；备选「summarization 保真度 + judge 标量分」被否决（引入 judge 档位/噪声/去噪三件复杂度，教学收口难）。
- **fixture 分两批（防过拟合命门）**：`fixtures/eval/train/*.json`（~10，可见、拿来优化）+ `fixtures/eval/held_out/*.json`（~5，优化时不可见、只收口跑）。案例形状 `{goal, transcript, expected}`，覆盖达成/未达成/部分达成/YESTERDAY 型措辞陷阱。判据：**train 涨、held_out 不涨 = 过拟合，回退**。
- **runner + TSV 记账**（`src/evals.py`）：对每案例构造 State → 调 `_goal_met(llm, state, goal)` → 与 expected 比对 → `{accuracy, per_case}`；`append_result` 落一行 TSV（git hash 或标注名 + split + n_cases + accuracy）——分数可回溯、改动可归因。TSV 路径调用方给（S7 checkpoint 同款哲学）。
- **M2 闭环范围 = 手动一次一改**：**离线对抗录制**跑基线分 → 修**一处**（YESTERDAY 假阳性：`startswith` 收紧为整词判定）→ 复跑分数涨 → TSV 留痕；收口 E2E 另记真实模型准确率两行（train/held_out）。基线弧走录制不走 E2E 是诚实选择：真实模型被「只回 YES 或 NO」约束、几乎不吐 YESTERDAY 型措辞，假阳性坑在真实跑分里不显形——录制代表「judge 解析必须扛住的自由文本」（对抗审查 2026-07-12 黄1 说实）。**砍**：agent 自改 prompt、NEVER STOP、固定预算、`--runs 3` 去噪、judge rubric 文件（autoevolve 产品版形态，走对照表升级路径）。
- **M3 缝**：判定 prompt 从 `_goal_met` 函数体抽成 `goal.py` 模块级常量 `GOAL_JUDGE_PROMPT`（~2 行外科手术，签名不动、存量测试零改动）——eval 围着转的「单可变文件」教学版落点，进化改这里、TSV 用 git hash 归因。
- **离线/在线分界（C3 不破）**：eval harness 自身（loader/scorer/TSV/两批分离/YESTERDAY 解析钉死）用 FakeLLM 录制 verdicts 离线单测；**真实跑分是收口 E2E**（ClaudeCLILLM 过 train 批），与 S1 e2e 同位。

**deer-flow 对照（子 agent 核实 2026-07-09）**：**本体（★76k）几无 agent quality eval**——318 个 pytest + Playwright e2e 全是软件正确性测试，CI 无 judge/benchmark job；范式反而在它 vendored 的第三方 skill-creator 里（fixture → `claude -p` → grader.md 逐断言 → pass_rate 聚合 → 自动改 description → 再跑，带 train/holdout）。教学版取 autoevolve 的骨（五要素）+ skill-creator 的打分形态（逐案例可编程断言 → accuracy）。

**砍**（autoevolve/skill-creator 产品化）：agent 自改环与通宵预算、judge 档位隔离与抽检、with-vs-without delta、tokens/时间聚合、best 版本保留器。

### loop detection + token budget {#loop-detection}（第三季 · S10）

核心 aha：**agent 最贵的失败不是崩溃，是打转**——崩溃有 traceback，打转只有账单。防打转 = 把「重复」变成可检测信号（tool_use 归一化 hash + 滑动窗口计数）+ 把干预做成两档（**警告**注入提醒教自救 → **硬停**剥 tool_use 逼自然收口）。加餐 TokenBudget（2026-07-12 拍板 D2=B 进主干）：同一套「双档阈值 + 延迟注入」基建的第二住户——检测对象从「重复」换成「花费」，一份基建教两件。

**落点（2026-07-12 拍板 D1=A / D2=B）**：
- **M1 挂载 = 缝①（LoopDetection middleware，~100 行）**：`after_model` 检测记账（此刻本轮 tool_use 已知）——归一化 hash：取 salient 字段（path/command/query 类），**read_file 按行号 200 行分桶**（防「换行号刷读」逃检）、**write 类反而 hash 全参**（防误报拦住合法的多次小改）——不对称性是考点；排序 → hash → 滑窗（默认 20）计数。**警告延迟到下一轮 `before_model` 注入**（`[loop warning]` user 消息教自救）：为什么不能 after_model 当场插——会夹在 tool_use 与 tool_result 之间，API 配对硬约束直接炸（**S2 配对坑第三次现身**；deer-flow loop_detection_middleware.py:18-38 注释自标全文件最有教学价值段落）。
- **M2 硬停 = 剥 tool_use 不抛异常**：计数 ≥hard 阈值时在 after_model 把本轮 assistant 的 tool_use 块剥掉（留/补文本说明）→ loop 见无工具调用走**终止条件 1 自然收口**——不加终止分支、不抛异常，复用既有终止语义（deer-flow 同款：剥 tool_calls + 改 finish_reason）。
- **加餐 TokenBudget（~60 行）**：同缝①件，`after_model` 累加花费、双档 warn（延迟注入 `[budget warning]`）/hard（剥 tool_use 硬停）——与 LoopDetection 共享延迟注入与硬停两块基建。**计费口径教学版 = 消息字符数近似**（fixture 可控、离线可测）；产品版 = 供应商 `usage_metadata` 差分累加（不用 tokenizer 库，deer-flow 同款），走对照表升级路径。与 S2 Summarization 互补正交：Summarization 管「窗口装不装得下」，Budget 管「这一 run 花了多少」。
- **滑窗计数放哪（开工拍板题）**：middleware 实例变量（重启清零，checkpoint 恢复后计数归零——说实即可）vs State 新字段（跨恢复存活，但触发 S7 字段表第三次联动）。**默认推荐实例变量**，留理论课与用户合议（教学环反哺开发候选）。
- **注册顺序语义（第三季必考）**：缝①住户增至 7+ 件——谁先看到模型输出、谁的警告先注入，顺序表是 S2「顺序语义」的毕业考（deer-flow 对应：Safety 必须后注册先剥 tool_calls 再让 Loop 记账）。

**deer-flow 对照（子 agent 核实 2026-07-12）**：loop_detection_middleware.py **612 行**（内核 ~90）——两层检测（hash 层 + 频率层「同工具类型 30 警/50 停」）、线程级 LRU、pending 警告上限、Pydantic 配置；token_budget_middleware.py **290 行**（内核 ~60）——usage_metadata 差分累加 + input/output/total 三口径取最高占比。

**砍**：频率层、线程 LRU 与并发锁、per-tool 阈值覆写、Pydantic 配置模块、多供应商 finish_reason 兼容、TokenUsageMiddleware 子 agent 用量回写（358 行，账算不全说实即可）。

### read before write {#read-before-write}（第三季 · S11）

核心 aha：**「读过」不存路径集合，存内容 hash**——盲写（没读就写）与读旧版（读过但磁盘已变）是两种事故、一个门拦住；且**状态寄生在 `state.messages` 上**（不开新字段、不用实例变量）——读记录被 Summarization 压掉时门自动失效，**两个 middleware 零协议耦合却语义联动**。deer-flow 对照：read_before_write_middleware.py 265 行（内核 ~70），立项依据是真实事故 issue #3857（同段落盲写追加 5 遍）。

**落点（2026-07-13 理论课 0012 拍板 · fail-open=A 落定）**：拍板判据全文见 learning-records/0022——版本门防「模型犯错」非「能力越权」，漏过最坏=一次可恢复的盲写（退化回没有门），误拦最坏=任务卡死+「死循环指路牌」（门叫模型先 read，门读不了的模型多半也读不了）；被否的 fail-closed 最强论点（读不了=异常信号、环境最可疑时最该拦）被双账压过：写入层有 ToolErrorHandling 兜底（各层各管各的）+ 静默放行可用留痕缓解（放行附警告标注为 C5 实现候选，教学环反哺第四例候选）。
- **M1 挂载 = 缝① `wrap_tool_call` 拦「写已存在文件」**：write 类调用到已存在 path 时，反向扫 `state.messages`（先建 tool_use id→(name,input) 映射再配对 tool_result）找该 path **最近一次 read 的渲染文本**，与「磁盘当前内容的同款渲染」比 hash——没读过 / hash 失配（读的是旧版）→ 拦下回**教学式 error**「先 read_file 再重试」（guard 家族第三员：S7 `[interrupted]` / S8 DeferredGuard / 本件）。**新文件放行**（无旧内容可覆盖，拦了纯误伤——防御面收窄到真实风险）。state 走构造注入（Q1=A 家族，WriteTodos 先例；「一个实例=一个任务」契约同 S10）。
- **比对视图 = 模型看到的同一视图**：`tools.py` 把 cat -n 渲染抽成模块级 `render_numbered(text)`（ReadFileTool 与本件共用，防双份漂移；tools.py 内部重构、协议签名不动）——比「渲染后文本」的 hash，render 对常规文本近似单射——换行符级差异不可辨（尾换行/\r\n/U+2028 被 splitlines 归一化，审查黄2 说实），漏检落在 fail-open 侧、足够本门语义。
- **M2「写不刷新 mark」= 机制的自然推论，零实现行**：写成功后磁盘已变，messages 里最近 read 的 hash 自动失配 → 连续两写之间必须重读。**fail-open 兜底**：门自己读不了文件（权限/IO 异常）→ 放行——防御件不能比被防御的更脆；与 S8 guard 的 fail-closed 相反，判据是「误拦 vs 漏过哪个更贵」（版本门防模型犯错、误拦合法写更贵 → open；能力门防越权、漏过更贵 → closed），S10 误报/漏报权衡的同源延伸。
- **跨切片设计不变量（必须钉成测试；2026-07-13 C5 推演纠错——初稿误写「压缩后放行」）**：Summarization 压缩删掉读记录后，先前的读证明随模型记忆一起失效——**写被拦、逼模型重读**。这是「状态寄生 messages」的语义联动：门的记忆与模型的记忆**同生共死**（模型忘了→门跟着忘→逼重读，恰好正确）；「压缩后还放行」反而是实例变量方案的病（门替模型记得已被遗忘的内容）。fixture 必须钉「压缩后写被拦」场景。对照 S5 todos（把状态**搬出** messages 逃离压缩）：本件把状态**藏进** messages 享受其生命周期——方向相反、各有正当性。

**deer-flow 对照（子 agent 核实 2026-07-12）**：265 行——additional_kwargs 盖章传递读记录、并发锁、async 双轨、多沙箱路径兼容。

**砍**：并发锁、async 双轨、多沙箱兼容、additional_kwargs 盖章（教学版直接反向扫 messages——正因为扫的是 messages，压缩联动语义才成立）。

## 关键约束

| # | 约束 | 检验方式 |
|---|---|---|
| C1 | src/ 总行数 ≤ 1,500（预算：loop 150 / llm 80 / tools 200 / middleware 协议 60 / 三内置件 200 / subagent 100 / skills 120 / goal+todo+clarification 250 / 杂项 240） | `tests/test_constraints.py` pytest 断言（2026-07-06 落地：无 CI，pytest 即每次必跑的闸门） |
| C2 | 运行时依赖仅 `anthropic` + `pyyaml` | pyproject 审查 |
| C3 | pytest 全程无网络：唯一接缝 = LLMClient，工具真实执行 | 测试不设 API key 环境跑通 |
| C4 | S2 起 loop 模块公共签名冻结（middleware 加能力不改 loop） | S2 测试直接复用 S1 的 loop 导入 |
| C5 | 每切片：fixture → 测试红 → 实现绿 → 笔记 → git tag，顺序不可换 | PROGRESS.md 留痕 |
| C6 | 蓝本只读：对 `~/deer-flow` 只允许 Read/grep | 纪律（CLAUDE.md 项目身份段） |
| C7 | **三缝协议冻结**（拓展性承诺）：Middleware / LLMClient / Tool 三个协议的签名 S2 起冻结，变更必须在 CHANGELOG 里给迁移说明 | 三协议的签名断言测试 |

## 反模式（明确禁止 + 为什么）

1. **禁止从 deer-flow 复制代码段**——License 与教学双输；能重写才证明懂了。允许：复述思想 + 笔记引用（标注出处）。
2. **禁止 patch loop 内部做测试**（mock.patch 循环私有函数）——接缝只有 LLMClient 一个；patch 内部 = 测试与实现耦合，重构即碎。
3. **禁止 middleware 里藏业务逻辑**（如在 Summarization 里顺手改 todos）——每个 middleware 单一关切，这是本项目要教的第一架构课，自己先别违反。
4. **禁止无消费者的代码扩展点**（插件注册表/配置系统/抽象工厂）——教材不是框架，YAGNI 是硬约束。**但拓展性不等于预埋代码**：本项目的拓展性走三条既有缝的协议冻结承诺（C7）+「产品版/教学版全景对照」的升级路径 + 每切片笔记末的拓展练习。缝上长东西是读者的作业，不是仓库的主干。
5. **禁止无 why 的注释**——注释只写「为什么这么设计/deer-flow 对照」，不写「下一行干什么」；讲 what 的欲望留给笔记。
6. **禁止 fixture 里写绝对路径 / 依赖执行顺序**——每个测试文件独立可跑，`pytest tests/test_s3_*.py` 单跑必须绿。

## 产品版 / 教学版全景对照 {#product-vs-teaching}

> 「教学版砍」≠「视野外」。每个被砍的产品关切在这里留出**升级路径**——走哪条缝、动多少代码、什么不变。范围外 ≠ 学不到：读者学完教学版，应该能对着这张表说出「长成产品版还差什么、从哪下手」。

**三条缝（唯一合法的拓展面，签名受 C7 冻结保护）**：
- **缝① Middleware 协议** —— 行为扩展面：一切横切能力（防御/记忆/预算）从这里长
- **缝② LLMClient 协议** —— provider 扩展面：换模型 = 一个新类（ClaudeCLILLM 已示范第三实现）
- **缝③ Tool 协议** —— 能力与执行环境扩展面：加工具、换执行后端，schema 契约不动

| 能力域 | deer-flow 产品版 | 教学版（本仓库） | 拓展路径（走哪条缝） |
|---|---|---|---|
| 循环引擎 | LangChain create_agent（黑盒） | 手写 `run()`，~150 行 | **不拓展**——看见循环就是本项目存在的理由 |
| 上下文管理 | Summarization + DurableContext + TokenBudget + 输出限额 | Summarization + ToolOutputBudget 两件 | 缝①：TokenBudget / DurableContext 各是一个新 middleware，loop 零改动 |
| 防御可靠性 | LoopDetection / ReadBeforeWrite / DanglingToolCall / Safety… | ToolErrorHandling 一件 | 缝①：每个防御件 = 一道独立练习（难度递增：Loop 检测→ReadBeforeWrite 版本门） |
| 多模型 | ModelFactory 反射 + vLLM/thinking/vision 适配 | AnthropicLLM + FakeLLM + ClaudeCLILLM | 缝②：OpenAI 兼容端点 = 一个新类实现 `complete()` |
| 工具执行安全 | 虚拟路径映射 + Docker/AIO sandbox provider | 裸 subprocess（60s 超时） | 缝③：bash 的 `run()` 换容器执行，name/schema/契约全不动 |
| subagent 执行器 | 线程池 + SSE 事件流 + 步骤持久化 | 同步递归调同一个 loop | 缝③：task 的 `run()` 内换 asyncio/线程池；「只回结论」契约不变 |
| skills 治理 | allowed-tools 白名单 / required-secrets / .skill 安装 | name + description + 斜杠激活 | frontmatter 加字段 → 激活时过滤 tools 列表（缝③的组合应用） |
| 运行时记忆（含评估闭环） | MemoryMiddleware + debounce 队列 + 事实抽取 | 无 | 缝①：新 middleware，按 agent-memory-kit 四角色接——Doer 留 trace（wrap_tool_call 采集）→ Reflector 评估提炼（critic 评哪里错 + librarian 沉淀长期教训，独立 context = 复用 task 委派即缝③）→ Store（*.md 持久化）→ before_model 检索注入回 Doer；prompt 闭环优化另走 autoevolve（fixture → judge 评分 → TSV 记账，不进主干） |
| goal 闭环 | 独立 evaluator 模型 + 类型化 blocker + 无进展熔断 | 同模型简单判定（run_with_goal 外壳） | 外壳内换 evaluator 实现，`run()` 与续跑协议不动 |
| 持久化 / 断点 | LangGraph checkpointer + threads_meta | State 内存态 | State 是纯 dataclass，天然可 JSON 序列化——(de)serialize 即练习 |
| 产品壳 | gateway / IM channels / 多租户 / tracing / TUI | 无 | **不拓展**（视野外，PRD Out of Scope 第一条） |

**拓展练习纪律**：每切片笔记末附 1–2 道「产品化拓展练习」（给思路与验收标准，不给实现）；练习全部从上表拓展路径列取材。主干代码永远只保教学版——C1 行数预算因此永不放宽。

## 切片关联 — Related Context

| 切片 | Related（读这些就够） | Affected behavior | Out of scope 提醒 |
|---|---|---|---|
| S1 | #loop #tools #llm + notes/01 §三 | 循环终止三条件；工具契约 | 无流式、无 checkpoint、无沙箱 |
| S2 | #middleware + S1 全部 | 三内置件各自的失败→恢复路径 | 不复刻 28 件全家桶；durable context 不做 |
| S3 | #subagent + #loop | 主对话只见结论；并发截断 | 无线程池/事件流；单层委派 |
| S4 | #skills | 元数据常驻 vs 正文按需 | 无 allowed-tools/安装包/secrets |
| S5 | #long-task + #middleware | todo 外置；goal 熔断；中断/恢复对称性 | 无独立 evaluator；无断点落盘 |

> 每切片开工时：新 session / subagent 只需读「Related」列 + 对应 feature 的 JSON 条目，不需要读全 SPEC。

## 端到端验证步骤（收尾 · Anthropic self-contained 三要件之三）

- **离线全量**：`uv run pytest -q` 全绿，全程无网络、无 API key（8 个 feature 的 verify 同源于此）。
- **切片收口序**：`uv run pytest tests/test_s{n}_*.py -q` 全绿 → 对抗审查（fresh 子 agent 对照本 SPEC 锚点）→ 架构 quiz 满分 → `git tag sfs-s{n}`。
- **真实模型 E2E（S1）**：`python scripts/e2e_s1.py`——`ClaudeCLILLM`（claude -p 适配器）驱动一次研究任务，多轮工具调用后产出最终答案（PRD 验收标准 4）。
