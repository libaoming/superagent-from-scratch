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

---
*下一篇：notes/03 —— S2 middleware 管线：横切关注点为什么是现代 harness 的真架构。*
