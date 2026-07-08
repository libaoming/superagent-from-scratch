# 拆解笔记 02 · S1 复刻实录：一个 while 循环里的 agent 本质

> 2026-07-06，S1 切片（F01_agent_loop + F02_real_tools）收口时写。上一篇：notes/01（deer-flow 架构地图）。本篇是「橙研所拆解系列」底稿，也是 PRD Story 9 的交付物：**deer-flow 怎么做 → 我怎么简化 → 为什么 → 拓展练习**。

## 一、deer-flow 怎么做：循环藏在黑盒里

deer-flow 的 lead agent 没有自己写循环。`make_lead_agent` 的本质是一行：

```python
create_agent(model, tools, middleware=[...28 个], system_prompt, state)
```

`create_agent` 是 LangChain 的——真正的 `messages → LLM → tool_calls → 执行 → append` 循环在框架内部，仓库里那 556 行 lead agent 代码全是**外围**：配置 middleware、组装工具、声明状态。你读完这 556 行，仍然没有见过循环本身。

这对产品是合理的：黑盒稳定、免维护、换 provider 不动业务代码。**但对学习者是灾难**——agent 的本质恰恰是那个循环，而它是整个仓库里唯一看不到的东西。

## 二、我怎么简化：187 行，三个文件，循环可见

| 文件 | 行数 | 职责 | deer-flow 对应物 |
|---|---|---|---|
| `src/loop.py` | 49 | State + `run()` 循环本体 | LangChain create_agent 内核（黑盒） |
| `src/llm.py` | 66 | LLMClient 协议 + FakeLLM + AnthropicLLM | ChatModel 抽象 + ModelFactory（389 行） |
| `src/tools.py` | 72 | bash / read_file / write_file | 工具层 + 虚拟路径映射 + sandbox provider |

循环本体去掉注释不到 20 行，值得整段放进笔记：

```python
while True:
    resp = llm.complete(system=system, messages=state.messages, tools=tool_schemas)
    state.messages.append(resp)

    tool_uses = [b for b in resp["content"] if b["type"] == "tool_use"]
    if not tool_uses:
        return state                       # 终止条件 1：自然收口

    results = [{"type": "tool_result", "tool_use_id": b["id"],
                "content": tool_map[b["name"]].run(**b["input"])}
               for b in tool_uses]
    state.messages.append({"role": "user", "content": results})

    state.turn_count += 1
    if state.turn_count >= max_turns:
        return state                       # 终止条件 2：turn 熔断
```

### 终止条件状态图（穷举，没有第四种）

```
                    ┌──────────────────┐
        ┌──────────▶│   llm.complete   │
        │           └────────┬─────────┘
        │                    │ append(resp)
        │                    ▼
        │           ┌──────────────────┐   无 tool_use
        │           │  resp 含 tool_use?├──────────────▶ ① 自然收口 return
        │           └────────┬─────────┘
        │                    │ 有
        │                    ▼
        │           ┌──────────────────┐
        │           │ 执行全部工具，结果 │
        │           │ 并入一条 user 消息 │
        │           └────────┬─────────┘
        │                    │ turn_count += 1
        │                    ▼
        │           ┌──────────────────┐   ≥ max_turns
        └───────────┤ turn_count 检查   ├──────────────▶ ② turn 熔断 return
          < max_turns└──────────────────┘

        （③ 中断信号：S5 的 middleware 在 after_model 返回 Interrupt——
          S1 的循环里还不存在这条边，故意的）
```

## 三、为什么这么简化（决策清单）

**1. 直接用 Anthropic 原生消息形状，不自造中立格式。**
deer-flow 用 LangChain 的 `AIMessage/ToolMessage` 是为了多 provider；我们 out of scope 了多模型，中立格式就只剩成本：读者多学一套没用的抽象，转换层还是 bug 温床。代价诚实交代——绑死 Anthropic 形状。换来的是两个 API 硬事实必须显式面对（也正好显式教）：

- **`tool_result` 以 `user` 角色回填**——工具结果是「用户替工具说话」，新手最容易在这掉坑；
- **同一响应的多个 `tool_use`，结果必须并入紧随其后的同一条 user 消息**，拆开会被 API 拒。

两条都有专门测试钉住（`test_tool_roundtrip` / `test_parallel_tool_results_in_single_user_message`）。

**2. 接缝只有一个：LLMClient 协议（单方法）。**
测试的唯一注入点是 `complete()`。FakeLLM 读录制 fixture 按序弹出，弹尽即抛错——「fixture 覆盖不足属测试 bug，补录制而不是 mock」。除 LLM 外全链路真实执行：测试里的 bash 真开 subprocess、read_file 真读文件。**禁 mock.patch loop 内部**（SPEC 反模式 2）：接缝越窄，测试越难作弊，重构越不碎。

**3. 错误处理分工：bash 回文本，其他工具抛异常。**
bash 的非零退出码和超时是「模型该看到并自纠的正常结果」——stderr 原样回给模型，它下一轮自己改命令。而 read_file 撞上不存在的文件就直接抛 `FileNotFoundError`——错误恢复是横切关注点，归 S2 的 ToolErrorHandling middleware 管，工具不兜。这个分工本身就是 middleware 架构的第一课：**工具只做本职，可靠性外置**。

**4. State 只有两个字段。**
deer-flow 的 ThreadState 有 12+ 字段，每个服务一个产品功能。教学版立了条纪律：**state 每个字段必须被至少一个切片的测试断言用到，否则删**。`todos`/`goal` 等 S5 的测试来要，S5 再进。

**5. `run()` 暂无 middlewares 参数（Deviation D1）。**
SPEC #loop 伪代码里有三条 middleware 链，但 Middleware 协议是 F03 的交付物——S1 加一条空链 = 无消费者的扩展点（反模式 4）。C4 签名冻结从 S2 起算，到时以关键字参数补入，S1 的导入不破坏。

## 四、E2E：第三实现证明缝的质量

S1 收口的真实模型验证不用 SDK，走 `claude -p`（订阅额度，无独立 API key）：`scripts/e2e_s1.py` 里的 `ClaudeCLILLM` 用 subprocess 包 CLI，实现同一个 `complete()` 协议——**loop、tools、测试一行不改**，第三个实现直接插上就跑。一条缝养活三个实现（FakeLLM / AnthropicLLM / ClaudeCLILLM），这就是「接缝质量」的可操作定义。

## 五、产品化拓展练习（取材自 SPEC #product-vs-teaching）

**练习 1 · 缝② 换 provider**：写一个 `OpenAICompatLLM`，实现 `complete()`，内部做 Anthropic 消息形状 ↔ OpenAI tool-calling 形状的互译。
验收：`tests/test_s1_loop.py` 换用它后 7 个测试不改一行仍全绿（fixture 形状不变——互译发生在实现内部，这正是本练习要体会的：**协议冻结时，适配成本全部落在实现侧**）。

**练习 2 · 缝③ 工具执行进沙箱**：把 `BashTool.run()` 的裸 subprocess 换成容器执行（docker run 或任何 sandbox），`name/description/input_schema` 与「超时/非零退出码回文本」契约全部不动。
验收：`tests/test_s1_tools.py` 的 bash 三测原样通过 + 一条新测试证明 `rm -rf /tmp/probe` 之类的命令伤不到宿主机。体会点：deer-flow 的虚拟路径映射为什么必须存在于多租户产品，以及它为什么可以完全不出现在教学版。

## 六、可迁移清单：带走的不是代码，是判断

S1 的 187 行代码本身不值得迁移，值得迁移的是六条决策模式。每条给「是什么 → 如何应用 → 验收信号」，验收信号是关键——迁移一个模式而没有可观察的成功标准，等于没迁移。

**1. 窄接缝：外部依赖收敛成单方法协议。**
- 是什么：整个系统对 LLM 的依赖只有 `complete()` 一个方法，三个实现（Fake/SDK/CLI）随意插拔。
- 如何应用：下次接任何外部服务（支付网关、对象存储、消息队列、别家 API），先写单方法协议再写实现；实现细节（重试、格式互译、鉴权）全部压到协议后面。
- 验收信号：能不改一行调用方代码插入第二个实现（哪怕只是测试用的假实现）。

**2. 录制回放代替 mock：fixture 弹尽即抛错。**
- 是什么：FakeLLM 按序弹出录制好的真实响应，弹尽抛错——「覆盖不足属测试 bug，补录制而不是 mock」。
- 如何应用：任何调外部 API 的测试，录一次真实响应存 JSON，测试离线回放；禁 `mock.patch` 内部函数。
- 验收信号：断网（或 `env -u API_KEY`）跑测试全绿；测试里除被录制的依赖外全链路真实执行。

**3. 错误分两类：模型（或用户）能自纠的回文本，程序性的抛异常。**
- 是什么：bash 非零退出码原样回给模型让它下轮自纠；read_file 缺文件直接抛异常，交横切层兜。
- 如何应用：设计任何工具/接口时先问「这个错误的消费者是谁」——消费者能自纠就把错误做成正常返回值，不能就抛出去让基础设施统一处理，别在每个工具里各写一套 try/except。
- 验收信号：工具代码里没有「吞掉异常转日志」的分支；错误路径有专门测试。

**4. 循环先穷举终止条件，再写循环体。**
- 是什么：S1 循环只有两个出口（自然收口/turn 熔断），状态图穷举画出，第三个出口（Interrupt）明确标注「还不存在，故意的」。
- 如何应用：写任何 while/重试/轮询/agent 循环前，先列全部出口并保证至少一个是无条件递增的熔断器；未来的出口写进注释而不是代码。
- 验收信号：每个出口有一条测试；不存在「理论上可能死循环」的路径。

**5. state 字段准入纪律：没被测试断言用到的字段不进。**
- 是什么：deer-flow 的 ThreadState 有 12+ 字段，教学版只留 2 个——`todos`/`goal` 等 S5 的测试来要时再进。
- 如何应用：任何共享状态（context 对象、Redux store、数据库表）新增字段前，先有一个真实消费者的测试来要它。
- 验收信号：删掉任一字段至少一条测试变红。

**6. 无消费者的扩展点不加（D1 的一般化）。**
- 是什么：SPEC 伪代码里有 middleware 链，但 S1 拒绝预留空链——扩展点在 F03 有真实消费者时才进，且以关键字参数补入保证旧调用不破坏。
- 如何应用：「顺手为将来预留」的参数/hook/配置项一律砍；真到那天，用默认值参数、新方法这类不破坏存量调用的方式补。
- 验收信号：每个扩展点都能指出至少一个当前真实消费者。

### AI PM 视角：同一批事实，另一层判断

工程侧迁移的是决策模式，PM 侧迁移的是「技术事实 → 产品判断」的翻译。S1 每个工程决策的背面都写着一道产品题：

**P1. 黑盒依赖是产品风险，不只是技术选型。**
- 是什么：deer-flow 把循环交给 LangChain——稳定免维护，但 agent 行为不符预期时，没人看得到循环本身。
- 如何应用：评审 AI 产品技术方案时固定问一句「线上出 badcase 时，我们能观察到哪一层」；可观察性差的黑盒，迭代速度会在三个月后还债。
- 验收信号：badcase 归因能落到具体环节（prompt / 工具 / 循环策略），而不是一句「模型抽风」。

**P2. 终止条件是产品参数，不是工程细节。**
- 是什么：max_turns 熔断直接决定单任务成本上限、延迟上限和失败模式（跑飞烧钱 vs 提前放弃惹恼用户）。
- 如何应用：把熔断策略写进 PRD——上限几轮、触发后用户拿到什么（部分结果 / 明确失败 / 转人工），别留给工程师拍默认值。
- 验收信号：PRD 里失败态有明确规格；成本模型里有「p95 轮数」这一项。

**P3. 错误分类直接映射为 UX 分层。**
- 是什么：模型能自纠的错误（bash 失败下轮重试）用户全程无感；不能自纠的才需要暴露和升级路径。
- 如何应用：写 agent 产品 PRD 时按「错误的消费者是谁」给错误态分层：模型自纠（不设计 UI）→ 系统兜底（轻提示）→ 必须问用户（HITL 打断，S5 的 ask_clarification 就是这层）。
- 验收信号：错误态清单里每条都标了消费者；没有「所有错误统一弹窗」的懒设计。

**P4. 接缝质量 = 供应商议价能力。**
- 是什么：一条 `complete()` 缝养活三个实现，换 provider 不动业务代码。
- 如何应用：模型层在商品化，产品的成本结构和谈判筹码取决于「换模型要改多少行」；评估团队架构时问这个问题，答案超过一天就是战略风险。
- 验收信号：能在一个 sprint 内完成主力模型的 A/B 或整体切换。

**P5. 录制 fixture 是 eval set 的最小雏形。**
- 是什么：FakeLLM 的录制回放，把「模型在这个任务上的行为」变成了可回归的资产。
- 如何应用：要求每个线上 badcase 的修复都沉淀一条录制用例——评估集不用专项立项，跟着 bug 流自然生长。
- 验收信号：eval 集条数随版本单调增长；改 prompt 敢上线的底气来自「录制集跑了一遍全绿」，不是「看了几个 case 感觉没问题」。

---
*下一篇：notes/03 —— S2 middleware 管线：横切关注点为什么是现代 harness 的真架构。*
