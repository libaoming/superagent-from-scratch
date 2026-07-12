# 拆解笔记 09 · S8 deferred tools：能力也按需注入

> 2026-07-11，S8（F11_deferred_tools）收口时写。上一篇：notes/08（S7 断点持久化）。第二季第三篇。
> 一句话主张：**tools 定义是上下文第 2 层的常驻成本——deferred tools 把「能力」做成按需注入：未加载只见名字，搜索命中才晋升出完整 schema。它与 S4 skills 是同一渐进披露范式的两个实例（知识层 vs 能力层），而「藏在视图层」必然推出「拦在执行层」。** 本刀终止了「run() 零改动」的 8 连胜——光明正大地：C4 冻结的是签名，不是内部实现。

## 一、deer-flow 怎么做：内核不小、砍的是产品化

子 agent 核实（2026-07-10），`tool_search` 四件共 397 行、**内核占比过半（~250 行）**——与 S7「0% 内核+100% 胶水」正相反，这刀的内核必须手写：

1. **只 defer MCP 工具**：内置工具全量绑定，第三方 MCP 工具默认延迟——「谁被 defer」本身就是一个产品决策（教学版用 `deferred: bool` 字段代替 MCP 标签模块）。
2. **双动机明写在配置注释里**：reduces context usage + **improves tool selection accuracy**——第二条常被忽略：工具太多不只是贵，是模型选不准，这是产品质量问题。
3. **露纯名字**：system 里只列 deferred 工具的名字，**连摘要都不给**——description 藏着但可被搜索命中，这是「名字看不出功能」仍然 work 的原因。
4. **缝③元工具 + 双通道晋升**：`tool_search` 支持 `select:` 精确取与关键词匹配；命中后当轮 tool_result 给完整 schema、名字进晋升集合，下轮起进绑定。
5. **wrap_tool_call 拦截**：未晋升调用被拦、回「先调 tool_search」的教学式 error。
6. **产品化 ~150 行被我砍掉**：catalog_hash 防目录漂移、fail-closed RuntimeError、pydantic 配置开关、`+prefix`/regex 降级、subagent 镜像装配、晋升驱逐。

**活教材**：你正在用的 Claude Code 就在跑同一套——system 里有「The following deferred tools are available via ToolSearch」的纯名字清单，`ToolSearch` 元工具的 `select:Name1,Name2` 语法与 deer-flow 几乎逐字相同，直调未加载工具报 InputValidationError 被教育「先 ToolSearch」。两个独立 harness 收敛到同一设计——这不是巧合，是范式。

## 二、我怎么简化：一个新文件 + 提交点三行过滤

| 交付物 | 内容 | 缝 |
|---|---|---|
| `src/deferred.py`（唯一新文件） | `deferred_system_block`（露）+ `ToolSearchTool`（搜+双通道晋升）+ `DeferredGuard`（拦） | 缝③ + 缝① |
| `src/loop.py`（内部 3 处） | `State.promoted` 新字段 + schema 构建移进循环体按 promoted 过滤 | loop 提交点（非缝） |
| `src/checkpoint.py`（2 行） | save/load 字段表同步 promoted（sorted list ⇄ set） | S7 联动 |
| fixtures 两个 | `deferred_tools_flow`（主流程）+ `deferred_guard_block`（拦截自救，兼测关键词搜） | fixture 先行 |

```python
# loop.py 循环体内（每轮重算——治理对象是提交点，提交点只在这里）
tool_schemas = [
    {...} for t in tools
    if not getattr(t, "deferred", False) or t.name in state.promoted
]

class ToolSearchTool:                    # 缝③元工具：catalog+state 构造注入（Q1 先例）
    def run(self, *, query):
        hits = ...                       # select: 精确取 / 关键词匹配 name+description，max 5
        self._state.promoted.update(t.name for t in hits)   # 通道②：下轮可调
        return json.dumps([schema...])                       # 通道①：当轮可读

class DeferredGuard(Middleware):         # 缝①：未晋升直调 → 教学式 error，不真执行
    def wrap_tool_call(self, call_next, tool, args):
        if getattr(tool, "deferred", False) and tool.name not in self._state.promoted:
            return "[tool error] 工具 X 尚未加载：先调 tool_search..."
        return call_next(tool, args)
```

**全项目第一个「四个部位协同」的切片**：露（system）— 搜（缝③）— 晋升（state）— 藏（loop 提交点）— 拦（缝①）。协议签名零改动（C7）；run() 签名零改动，但内部动了——见决策 2。

## 三、为什么这么设计（决策清单）

**1. 本质：与 S4 的完美对仗（核心 aha）。**
skills 是**知识层**按需注入（元数据常驻 / 正文激活才进 user history）；deferred tools 是**能力层**按需注入（名字常驻 / schema 晋升才进绑定）。共同骨架 = **目录常驻、内容按需**——渐进披露。区别只在注入的东西：知识（怎么做某事的文本）vs 能力（可发出的 tool_use）。MCP 时代「接一百个工具」是常态，这刀回答的就是「工具多了怎么办」。

**2. M1：过滤放 loop 内部——8 连胜光明正大终止。**
S4-S7 四刀 run() 零改动，S8 绕不开：**治理对象是「每轮的 tools 提交点」，而提交点在 loop 里**。三钩子只收 state、碰不到 tools 参数（tools 是 run() 的参数不是 state 字段）——给钩子加参数 = 改协议签名 = 真破 C7。两害相权：动 loop 内部实现（C4 冻结的是**公共签名**，内部移几行不在范围），保 C7 协议不动。**「零改动 N 连胜」是荣誉不是约束**——把荣誉当约束守，就会做出「外壳重进」（每次晋升多一轮收口/重进往返）或「stub schema」（没有真藏/晋升/拦截，机制失真）这种为守假约束而失真的设计。deer-flow 的对应物本就是 middleware 每轮覆写 request.tools——loop 内过滤是它在本架构下最诚实的等价。

**3. M2：晋升双通道，缺一不可。**
通道①（当轮 tool_result 给完整 schema JSON）管**当轮可读**——模型立刻看到参数长什么样、能规划下一步；通道②（名字进 `state.promoted`）管**下轮可调**——过滤放行、schema 进绑定，tool_use 才发得出去。砍①：模型知道加载成功却要白等一轮才见到参数；砍②：读得到文档、永远调不了。**读和调走两条物理通道**（消息流 vs 绑定列表），所以必须双写。

**4. 藏的是视图，不是工具——所以必须拦。**
`tool_map` 始终持有全部工具（执行层不动，晋升无需重建任何东西——晋升是「放行视图」不是「装载能力」）。必然推论：录制/幻觉直调未晋升工具，**不拦会静默执行成功**，「藏」就成了假的。缝① `DeferredGuard` 在执行前拦下、回教学式 error 指路 tool_search——教模型自救，不是崩溃。这条链（藏在视图层 ⇒ 拦在执行层）是本刀最容易漏的因果。

**5. 缓存账：低频一次性代价换高频复利收益。**
名字清单静态常驻 system = 不晋升时 prompt cache 完全友好；晋升改变 tools 集合、必破一次前缀缓存——但全量绑定是**每轮都贵**（100 schema × N turn 复利），晋升是**低频一次性**。总账：省（每轮少提交 N-k 个 schema）+ 准（选项少了选得准），覆盖固有代价。

**6. S7 联动：State 加字段从来不是一行的事。**
`state.promoted` 入列 ⇒ S7 `save_state` 硬编码字段表必须同步，否则 checkpoint 恢复后晋升丢失——模型读过 schema 的工具突然重新隐身。set 不可 JSON 化：存 sorted list（diff 稳定）、载回 set；老档缺字段兜空集（向后兼容）。**有持久层的系统里，数据模型变更自带一笔持久化账**——S8 落地时一并结清并钉进 roundtrip 测试。

**实现陷阱三则（对抗审查 2026-07-11，0 红 4 黄）：**
① **构造注入绑定的是「这一个 State」**——ToolSearchTool/DeferredGuard 构造时绑 state，而 subagent 开全新 State、`load_state` 返回新 State：这两个场景必须用对应 State **重建**二者。把绑定父 state 的 tool_search 下放给子 agent，晋升会写进**父** state（污染父 run 的 tools 集合）、子 agent 自己却永远等不到放行——「不继承晋升」符合 out_of_scope（不做 subagent 镜像装配），但「写进别人的 state」是要文档防住的坑（本刀选文档化不改 TaskTool，保 S3 代码不动）。
② **空 query 静默群晋升（已修）**——`"" in anything` 恒真，空串走关键词分支会命中全部 deferred 工具并晋升前 5 个（白破一次缓存）。修法与「拦」同哲学：退化输入回提示教自救，不静默扩权。
③ **两个不设防的边界**：`select:` 前缀大小写敏感（`Select:` 静默降级为关键词搜）；给 ToolSearchTool 自己标 `deferred=True` 会死锁（loop 藏它 + guard 拦它，鸡生蛋）——默认实现不会触发，但接产品版前要知道。

## 四、测试怎么钉住「藏得真、晋升得全、拦得住」

- **观察「每轮提交了哪些 schema」只能在唯一接缝**：`SpyLLM` 包装 FakeLLM、记录每次 `complete()` 收到的 tools 名单——第 1 轮不含 `send_email`、tool_search 后第 2 轮包含（反模式 2：不 patch loop 内部，重构不碎）。
- **主流程 fixture**（`deferred_tools_flow`）：`select:` 精确取 → 双通道断言（tool_result 里 parse 出 schema JSON = 通道①；`state.promoted=={"send_email"}` + 下轮真执行 = 通道②）。
- **拦截 fixture**（`deferred_guard_block`）一段录制钉三件事：直调被拦（`email.calls` 只有晋升后那一次 = 没真执行）、error 文本含 tool_search（教自救）、关键词「邮件」命中 description（搜索的第二种形态）。
- **单元侧**：select 多名精确取 / 7 命中截到 max 5 / 未命中回提示；system_block 纯名字（description 不露、非 deferred 不进名单）。
- **S7 联动**：roundtrip 断言盘上是 sorted list、载回是 set、集合保真。

verify：`test_s8_deferred.py` **6 passed**，全量 **80 passed**（存量 74 零改动同绿，C4 第九次实证——loop 内部动了、签名没动、老测试一行没改），src 1064 行（预算 1500）。

## 五、可迁移清单：带走的不是代码，是判断

**1. 目录常驻、内容按需（渐进披露）是治「常驻成本」的通用范式。**
- 是什么：skills（知识）与 deferred tools（能力）共用同一骨架——便宜的索引常驻，贵的本体按需加载。
- 如何应用：任何「全量注入撑爆上下文」的资源（工具/文档/记忆/示例库），先问「它的最便宜索引是什么」（名字/标题/一行摘要），索引常驻 + 元操作按需取本体。
- 验收信号：不使用该资源时其上下文占用接近零；使用路径不多于一次额外往返。

**2. 「荣誉指标」与「真约束」要分开守。**
- 是什么：「run() 零改动 8 连胜」是荣誉，C4 签名冻结才是约束——把荣誉当约束守会逼出失真设计（外壳重进/stub schema）。
- 如何应用：连胜类指标（零回归、零改动、100% 覆盖）被打破前，先问「它背后的真约束是什么、破的是哪个」——只为真约束设防。
- 验收信号：能一句话说出每条「不许动」背后保护的契约是谁、谁在依赖它。

**3. 隐藏类机制必配拦截：视图与执行分层时，权限要在执行层再查一次。**
- 是什么：藏 schema 不藏工具 ⇒ 视图过滤形同虚设的路径（幻觉/录制/注入直调）必然存在 ⇒ 执行层 guard 兜底。
- 如何应用：任何「前端不展示 = 用户不能用」的假设都要在服务端复查（UI 隐藏按钮 ≠ API 鉴权）；error 设计成「教下一步」而非「拒绝」——agent 系统里模型是要自救的。
- 验收信号：绕过视图直接打执行层的测试存在且被拦。

### AI PM 视角：同一批事实，另一层判断

**P1 工具规模化的上下文经济学——「选择准确率」进 PRD**：接入工具数是增长指标，但**工具选择准确率随工具数下降**是质量指标——两条要放在一张图上看（工具数 vs 选对率基线曲线），扩目录前看拐点。全量绑定的成本模型是「每轮复利」，deferred 化把它改写成「索引常驻 + 按需一次性」。

**P2 可发现性是旋钮不是开关**：露多少（纯名字/加一行摘要/完整 description）、一次回几个（max_results）、谁被 defer（全部第三方 or 按调用频次）——都是产品参数。千级工具市场的运营化方案（0010 课上用户给出的分层设计）：**预算上限 + 三层准入**——L0 长尾不占 system 纯靠搜索、L1 平台级热门露名字、L2 用户个人高频常驻 name+description（按使用频次取 topN）；用「工具选择准确率 + 使用频次」周期性重算分层，harness 层观测计算。**度量不是为了汇报，是为了驱动参数。**

**P3 渐进披露是平台范式**：插件市场/工具市场类的平台型 agent 产品，扩展生态入口该统一按「目录常驻、内容按需」设计——Claude Code（deferred 名单+ToolSearch）与 deer-flow 独立收敛到同一形态，是这个范式成立的最强证据。

## 六、拓展练习

**练习 1 · 「露多少」旋钮实装（还原 deer-flow 砍掉的摘要档）**：给 `deferred_system_block` 加 `verbosity` 参数（`names` | `names+summary`），summary 取 description 首句；再实现 L1/L2 分层——`ToolSearchTool` 记调用计数，提供 `top_n(k)` 让外壳把高频工具直接预晋升（开 run 时注入 promoted）。
验收：两档 system 长度可测差异；预晋升工具第 1 轮即在绑定里且无需 tool_search。体会点：可发现性 vs 常驻成本是连续谱，产品参数就长在这根轴上。

**练习 2 · 晋升驱逐（LRU 降级，deer-flow 砍掉的方向反操作）**：promoted 加容量上限 K，超限时驱逐最久未调用的工具名（回到只见名字状态）。注意与 S7 的联动：驱逐后 checkpoint 恢复不得复活已驱逐工具。
验收：第 K+1 个晋升触发驱逐、被驱逐工具再调用被 guard 拦、save/load roundtrip 后 LRU 序保持。体会点：上下文预算是运行时资源，「加载」就要考虑「卸载」——和内存管理是同一门学问。

---

## 七、S8 收口结论

S8 全景 = **一个 deferred.py（露/搜+双通道晋升/拦）+ loop 提交点三行过滤 + checkpoint 字段表两行联动**，`run()` 签名与三协议零改动（C4/C7），但内部实现动了——8 连胜光明正大终止。verify：6 passed，全量 80 passed，src 1064 行（预算 1500）。本切片两个第一次：第一个「四个部位协同」的切片（缝①③ + system + loop 提交点）；第一次「荣誉与约束分离」的实战辩护。

第二季走到第三刀，「骨架长好后能力怎么长在外面」再添一格：S6 记忆（外壳，per-run）→ S7 checkpoint（缝①+外壳，per-turn）→ S8 deferred tools（缝①③+提交点，per-turn 过滤 + per-search 晋升）。一句话带走：**上下文里最贵的不是说过的话，是每轮重复携带的「可能用得上」——把「可能」变成「按需」，就是这一刀的全部。**

*第二季第三篇。前篇：notes/02 循环 · 03 中间件 · 04 委派 · 05 技能 · 06 长任务 · 07 记忆 · 08 断点。*
