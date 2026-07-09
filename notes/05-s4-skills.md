# 拆解笔记 05 · S4 skills：能力的热插拔（元数据常驻、正文按需）

> 2026-07-09，S4（F06_skills passing）收口时写。上一篇：notes/04（S3 subagent 委派）。
> 一句话主张：**skill 不是第四条缝，是「往 messages/system 里塞知识」这件事本身**——发现与激活全在 loop 外，run() 一个字没改（C4 第四次实证）。它的全部技术含量就一句话：**元数据便宜所以常驻，正文贵所以按需**。

## 零、先把三类扩展摆清楚：skill 到底是第几种东西

前三个切片砍出了三条缝，S4 要证明的恰恰是**第四类扩展根本不占缝**：

| 扩展类型 | 走哪 | 谁触发 | 给 agent 的是 |
|---|---|---|---|
| **工具 / subagent**（缝③） | `tools` 列表 + tool_use | **模型主动**点 | 一个**能力**（做事的手） |
| **middleware**（缝①） | before/after 钩子 | 框架在 loop 里**自动**跑 | 一段**横切行为**（重试/预算/摘要） |
| **skill**（不占缝） | messages 内容 + system 文本 | 用户 `/斜杠` **确定性**触发 | 一份**知识**（怎么做的说明书） |

这张表是 S4 的定位锚。工具是「手」、middleware 是「反射弧」、skill 是「随身带的操作手册」——**手册不改变身体构造，只在需要时翻到那一页**。所以 skills 不需要新缝：发现只是往 system prompt 拼字符串，激活只是往 user 消息拼字符串，两个纯函数在 harness 外壳里被调用，`run()` 全程无感。

## 一、deer-flow 怎么做：SkillActivationMiddleware

deer-flow 把技能激活做成一条 **middleware**（`SkillActivationMiddleware`，与 Claude Code skills 同一设计内核）。机制：

1. 启动扫 `skills/*/SKILL.md`，解析 frontmatter（name/description/**license/allowed-tools/required-secrets**）
2. description 常驻 system prompt；正文不进
3. before_model 钩子里检测激活条件 → 把该 skill 正文注入上下文，**并按 `allowed-tools` 收窄本轮工具白名单、按 `required-secrets` 注入凭证**

产品版的重量全在那三个多出来的 frontmatter 字段上：`license` 服务分发合规、`allowed-tools` 服务权限收窄（激活某 skill 时把 tools 列表过滤一遍）、`required-secrets` 服务凭证注入。**这三样都是「治理」，不是「技能」本身**——技能的内核只有「一句话描述常驻 + 正文按需注入」。

## 二、我怎么简化：53 行两个纯函数，连 middleware 都不做

| 文件 | 行数 | 交付物 |
|---|---|---|
| `src/skills.py` | 53 | `discover_skills`（发现）+ `activate`（激活）+ `_parse_frontmatter`（拆 YAML） |

**比 S3 更进一步的简化：deer-flow 用 middleware（缝①）做的事，我连缝都不占。** 两个函数在 loop 外被 harness 调用：

```python
def discover_skills(skills_dir) -> tuple[dict, str]:
    registry = {}
    for skill_md in sorted(Path(skills_dir).rglob("SKILL.md")):   # 递归发现
        meta, _body = _parse_frontmatter(skill_md.read_text())
        name, desc = meta.get("name"), meta.get("description")
        if name and desc:                                          # 两必填字段齐才注册
            registry[name] = {"description": desc, "path": skill_md}  # path 留给激活，不进 system
    lines = [f"/{n}：{s['description']}" for n, s in registry.items()]
    return registry, "可用技能（斜杠激活）：\n" + "\n".join(lines)   # system_block 只含元数据

def activate(user_text: str, registry: dict) -> str:
    if not user_text.startswith("/"):
        return user_text                                          # 无斜杠：原样放行
    name, _, rest = user_text[1:].partition(" ")
    skill = registry.get(name)
    if skill is None:
        return user_text                                          # 未注册：当普通文本，不报错
    full = Path(skill["path"]).read_text().strip()                # 激活才读全文（贵）
    return f"{full}\n\n{rest}" if rest else full                  # 全文作 user 前缀块
```

**只留两个必填字段 name/description**（SPEC 技能节）——deer-flow 的 license/allowed-tools/required-secrets 全砍（F06 out_of_scope）。发现阶段 `registry` 里存 `path` 而非正文：**正文的读取被推迟到激活那一刻**，这就是「按需」的物理实现——不激活，正文永远躺在磁盘上，一个 token 都不烧。

## 三、为什么这么设计（决策清单）

**1. token 经济学 = 元数据常驻、正文按需，这是整个 skill 系统的存在理由。**
假设有 100 个 skill，每个正文 2000 token。若全量常驻 system = 20 万 token 每轮都烧，且大部分与当前任务无关（噪声淹没信号）。渐进披露把它拆成两层：**便宜的一句话 description 常驻**（100 句 × 20 字 ≈ 几千 token，模型据此知道「有哪些手册可翻」），**贵的正文只在斜杠激活时进当轮上下文**（一次一本）。发现存 `path` 不存正文，就是把「贵」这一层锁在磁盘上。这不是省钱小技巧——它决定了「能挂多少 skill」的量级上限。

**2. 注入点 = user 消息前缀块，不是 system（Q3=A，2026-07-04 拍板）。**
激活后的正文可以塞三个地方，为什么选 user 前缀块：
- **进 history → 可被 Summarization 正常压缩**：skill 正文是一次性指导，用完就该能被摘要吃掉；塞进 system 它会永久占着预算，和 S2 摘要 middleware 打架。
- **可测**：测试直接 `assert BODY_MARK in str(state.messages[0])` 就能验证注入，不用刨 system 拼装逻辑。
- **语义正确**：skill 是「对这条用户请求的补充说明」，本就属于这一轮 user turn，拼在用户原话前面天经地义。
取舍：user 前缀块会让这一轮 user 消息变长（正文在前、原请求在后），但这正是我们要的——它跟着这轮请求走、随摘要走。

**3. 激活是确定性的斜杠触发，不是模型自己决定。**
和工具（模型主动 tool_use）的关键区别：skill 激活由**用户显式 `/名字`** 触发，是确定性的、发生在进 loop 之前。为什么不让模型「按需自己加载」：那会变成又一次 tool_use round-trip（模型先调 load_skill 工具、拿回正文、再干活），多烧一轮且不可控。斜杠激活把「翻哪本手册」的决定权交给用户，一次注入到位——**确定性优于智能，能不进循环就不进**。

**4. 未注册的斜杠名原样放行，不报错（教学版容错）。**
`/nonexistent 做点事` → 当普通文本原样返回。为什么不抛异常：斜杠可能只是用户正常输入（比如路径 `/usr/bin`、或就想打个斜杠），skill 系统对「不是我的菜」的输入应当**无副作用透明放行**，而非劫持所有以 `/` 开头的消息。产品版可做「未知 skill 提示 + 相似名建议」，但那是体验优化，不是内核。

**5. frontmatter 解析对「没有 frontmatter」宽容。**
`_parse_frontmatter` 见到不以 `---` 开头的文件 → 元数据空、全文当正文；发现阶段因 `name and desc` 缺失而**跳过注册**，不炸整个发现流程。一个坏 SKILL.md 不该拖垮其余技能的发现——这是 rglob 批量扫描的健壮性底线。

## 四、测试怎么钉住「看不见的经济学」

token 经济学是**分布行为**（谁进 system、谁进 messages），肉眼 review 不出来。S4 的 6 条测试用「标记词在哪／不在哪」把它钉死：

- **两个标记词对撞**：`DESC_MARK="统计目录文件"`（description）、`BODY_MARK="按这个步骤做"`（正文）。
  - `test_system_block_carries_description_not_body`：`DESC_MARK in system_block`（元数据常驻）**且** `BODY_MARK not in system_block`（正文一字不进 system）——「贵的不在便宜区」是核心断言。
  - `test_slash_activates_full_text`：斜杠激活后 `BODY_MARK in injected`（正文按需进），且原请求保留在前缀块之后。
- **端到端钉注入点（Q3=A）**：`test_skill_body_enters_messages_not_system` 真跑 `run()`，断言 `BODY_MARK in str(state.messages[0]["content"])` 且 `role == "user"`——正文进的是 user 消息 history，不是 system 常驻。
- **放行两条**：无斜杠原样返回、未注册斜杠名原样返回——证明 skill 系统对「不是激活」的输入零副作用。
- **多技能递归发现**：fixture 放 `demo-skill` + `note-taker` 两个（不同子目录），`test_discover_registers_all_skills` 断言 `set(registry) == {"demo-skill", "note-taker"}`——证明 rglob 真的递归、不是只扫一层。

verify：`test_s4_skills.py` **6 passed**，全量 **50 passed**（存量 44 **零改动同绿**，C4 第四次实证）。

## 五、可迁移清单：带走的不是代码，是判断

**1. 上下文是分层预算，用「访问频率 × 单价」决定谁常驻。**
- 是什么：元数据（高频命中、低单价）常驻，正文（低频命中、高单价）按需加载。
- 如何应用：任何「候选项很多、每次只用少数」的上下文（工具库、文档库、few-shot 示例库、记忆库），都拆成「便宜的索引常驻 + 贵的正文按需」两层，别全量灌。
- 验收信号：常驻上下文的大小随候选**数量**线性增长（每项一句话），而非随候选**总体积**增长。

**2. 确定性触发优于让模型自己决定——能不进循环就不进。**
- 是什么：skill 用斜杠一次注入，而非让模型多转一轮 tool_use 去加载。
- 如何应用：凡是「加载什么」的决定用户/规则能确定给出的，就在进 loop 前确定性注入，别设计成模型的一次工具往返——省 round-trip、去不确定性。
- 验收信号：常见路径下完成任务的 LLM 往返次数不因「加载资源」而增加。

**3. 批量发现要对单个坏样本宽容。**
- 是什么：一个缺字段/无 frontmatter 的 SKILL.md 被跳过，不炸掉整个发现。
- 如何应用：任何「扫目录批量注册」的机制（插件、skill、配置片段），单个坏样本 skip + 可选告警，而非 fail-fast 拖垮全体。
- 验收信号：注入一个损坏样本，其余样本照常发现可用。

### AI PM 视角：同一批事实，另一层判断

**P1. skill 是「能力的内容化」——把 workflow 沉淀成可分发的资产，而非写死进代码。**
- 是什么：一段「怎么做某类任务」的知识，不是新代码、不是新工具，是一个 Markdown 文件。
- 如何应用：产品里大量「最佳实践/SOP/领域知识」不必都做成功能，可沉淀成 skill 库让 agent 按需翻阅；「加一个 skill」= 写一篇文档，排期成本远低于「加一个功能」。这是 agent 产品**能力扩张的最便宜的一条路**。
- 验收信号：非工程角色（运营/领域专家）能独立新增一个 skill 并生效。

**P2. token 经济学是可量化的产品成本项，直接进容量模型。**
- 是什么：常驻元数据的总量 = 每轮固定成本；激活正文的均值 = 每次任务边际成本。
- 如何应用：把「能挂多少 skill / 每轮常驻预算 / 激活正文上限」当产品参数在 PRD 里定死，它决定 skill 库的规模天花板和单任务毛利——和 S3 的 context 治理是同一张成本表的两行。
- 验收信号：PRD 有「skill 库规模上限」条目，且关联到每轮 system 预算。

**P3. 治理字段（allowed-tools/secrets/license）才是 skill 从「教学玩具」到「企业级」的分水岭。**
- 是什么：教学版砍掉的三个字段，恰是产品化时最先要补的——权限收窄、凭证注入、分发合规。
- 如何应用：评估/设计 skill 平台时，别只看「能不能注入知识」，要看治理面：一个 skill 激活时能不能限制它只用某几个工具？能不能安全注入它需要的密钥？能不能管分发授权？没有治理面的 skill 系统上不了企业。
- 验收信号：skill 激活能改变本轮可用工具集；密钥不落进 skill 正文明文。

## 六、拓展练习

**练习 1 · allowed-tools 白名单（缝③的组合应用）**：给 frontmatter 加 `allowed-tools: [bash]` 字段，激活某 skill 时把传给 `run()` 的 tools 列表过滤成白名单交集。
验收：激活 demo-skill（allowed-tools=[bash]）后，即使 harness 挂了 write_file，本轮模型也只拿得到 bash；未声明 allowed-tools 的 skill 不收窄。体会点：skill 治理 = 用**发现出的元数据**去配置**缝③的工具列表**——第四类扩展借前三条缝落地。

**练习 2 · 模型自主激活（对比确定性斜杠）**：加一个 `load_skill(name)` 工具，让模型能在对话中自己决定加载某 skill 正文，对比斜杠激活。
验收：跑通「模型先 load_skill 拿回正文、再据此干活」的两轮往返；然后测量它比斜杠激活多烧了几轮、几多 token。体会点：**为什么教学版选确定性斜杠**——把决策 3 的「能不进循环就不进」用数字量出来。

---

## 七、S4 收口结论

S4 全景 = **一个 53 行的 `skills.py`，两个纯函数**，连 middleware 都不做——deer-flow 用缝①（SkillActivationMiddleware）做的事，教学版发现结论：**skill 根本不占缝**，它只是「往 system 拼元数据、往 user 消息拼正文」这两个字符串操作，`run()` 零改动（C4 第四次实证）。verify：`test_s4_skills.py` 6 passed，全量 50 passed（存量 44 零改动同绿）。src 总 454 行（预算 1500）。

一句话带走：**S1 循环可以很小、S2 能力可以不进循环、S3 子任务只是递归调用、S4 知识只是按需拼的字符串**——四刀砍下来，一个「能挂工具、有横切治理、能委派子任务、能热插拔技能」的 agent harness，主体就四百多行。skill 这一刀最轻，却点破了一个最容易被产品复杂度掩盖的真相：**很多「能力」的本质，只是在对的时机把对的文字放进上下文**。token 经济学不是优化，是这类能力的定义本身。tag `sfs-s4` 于收口面试通过后打。

*下一篇：notes/06 —— S5 长任务：todo 外置 + goal 续跑 + clarification 中断（最后一个切片，harness 套住 long-horizon 的目标闭环）。*
