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
