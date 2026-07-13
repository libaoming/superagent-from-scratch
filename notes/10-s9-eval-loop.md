# 拆解笔记 10 · S9 eval 闭环：把「judge 好不好」变成一个能涨的数

> 前九刀是「怎么造」，这刀是「怎么知道造对了、怎么让它系统性变好」。被评对象选了个最有讽刺性的：`goal.py` 的 `_goal_met`——**它本身就是个 LLM judge（YES/NO），却从没被量化测过**。S5 对抗审查嘴上记过它的 `startswith("YES")` 假阳性（Y1），但「记过」不等于「量过」：没有 eval，坑只是审查报告里的一行字；有了 eval，它是 TSV 里 0.8 → 1.0 的两行账。

## 一、参照系怎么做：连 ★76k 的旗舰都没做 agent quality eval

deer-flow 实况（子 agent 核实 2026-07-09）：**本体几乎没有 agent quality eval**。318 个 pytest + Playwright e2e + 部署冒烟，全是「代码对不对」的软件正确性测试，CI 里没有任何 judge/benchmark job。范式反而藏在它 vendored 的第三方 skill-creator 里：`run_loop.py` = fixture(evals.json) → `claude -p` 跑 → LLM judge（grader.md 逐断言 PASS/FAIL）→ 聚合 pass_rate → 自动改 description → 再跑，带 train/holdout。

这是本项目全部十刀里最特殊的一个参照关系：前九刀是「产品版有、我砍薄」，这刀是「**产品版自己都欠着**」——eval 被忽视到旗舰项目都这样，恰恰说明它最该补、也最能拉开差距。

## 二、我怎么简化：一个 66 行文件 + 两行外科手术

```
src/evals.py（66 行）
  load_cases(dir)          # 按文件名序 glob *.json —— {goal, transcript, expected}
  run_eval(llm, cases)     # 逐案例装 State 喂 _goal_met，比对 ground truth → accuracy + per_case
  append_result(path, ...) # 一行一跑分的 TSV：label / split / n / accuracy

src/goal.py（改 2 处）
  GOAL_JUDGE_PROMPT        # 判定 prompt 从函数体抽成模块常量——「单可变文件」教学版落点
  re.match(r"\s*YES\b")    # startswith("YES") → 整词判定（Y1 假阳性修复）
```

fixture 分两批：`fixtures/eval/train/`（10 个，可见、拿来优化）+ `fixtures/eval/held_out/`（5 个，优化时不可见、只收口跑）。打分不用 LLM-as-judge——案例有 ground truth 标签，**能程序判定就不用 judge**。

## 三、为什么这么设计（决策清单）

1. **被测对象 = _goal_met，而不是 summarization 保真度**（M1 拍板）。后者更贴 autoevolve 原味（judge rubric + 标量分），但引入 judge 档位隔离、±0.5-1.0 噪声、`--runs 3` 去噪三件复杂度。_goal_met 的案例可以带标签，打分器是纯函数——教学切片要的是闭环骨架清晰，不是 judge 工程。
2. **程序化 accuracy 而不是 LLM judge**。这本身是个教学点：judge 是「没有标签时的退路」，不是默认选项。skill-creator 的逐断言 pass_rate 与 autoevolve 的标量分，对应「可程序验证」与「主观质量」两类场景——本切片属于前者。
3. **闭环范围 = 量分 + 记账 + 手动一次一改**（M2 拍板）。agent 自改 prompt、NEVER STOP、固定预算是 autoevolve 产品版形态；教学版只保「分数驱动改动」的最小弧：基线 0.8 → 修**一处** → 1.0，TSV 留痕。改两处就无法归因——「一次一改」是纪律不是懒。
4. **prompt 抽成模块常量而不是独立 .md 文件**（M3 拍板）。autoevolve 的「单可变文件」原味是 prompt 落盘成数据文件，但那要给已 passing 的 S5 代码加文件 IO 和路径依赖；抽常量是 ~2 行外科手术，签名不动、存量测试零改动，「进化改这里」的语义一样成立。
5. **对抗性录制放 train 批、离线量分**。真实模型被「只回 YES 或 NO」的 prompt 约束，很少吐 YESTERDAY 型措辞——假阳性坑在真实 E2E 里几乎不显形。所以 0.8 → 1.0 的教学弧走 FakeLLM 对抗性录制（04/08 两条 YESTERDAY 措辞），真实 E2E 另记一行真准确率。**录制代表「judge 解析必须扛住的自由文本」，不代表「真实模型常这么说」——这一条要诚实地写在这里。**
6. **TSV 路径调用方给**（S7 checkpoint 同款哲学）：库函数不硬编码落盘位置，仓库里的 `evals/results.tsv` 只是本项目的记账处。

## 四、测试怎么钉住

- **红→绿本身就是教学弧**：`test_run_eval_accuracy_over_adversarial_recording` 断言 accuracy == 1.0——修复落地前它是红的（0.8）。测试先写、修复后过，「量分驱动一次一改」在 pytest 层面留了痕。
- **防过度收紧的反向断言**：`goal_verdict_edges.json` 两连发——「YESTERDAY 已完成」→ False（Y1 修复）+「YES！已达成」→ True（`\b` 保住带标点的真阳性）。只钉前者不钉后者，下次有人把判定改成 `verdict == "YES"` 测试照样绿、线上照样坏。
- **残余假阳性面说实（对抗审查 2026-07-12 黄2）**：`\b` 修的是「前缀词粘连」一类（YESTERDAY）；「YES-oriented …未达成」「YES AND NO」这类**复合开头**在整词判定下仍判 True——连字符/空格本身就是词边界。这一面不再打解析补丁：自由文本判定的补丁会无穷追（每修一类措辞冒出下一类），根治路径是**类型化 evaluator**（约束输出结构而非解析自由文本，notes/06 拓展练习 1 的产品版方向）。同理，held_out 批从未经受 YESTERDAY 陷阱（无录制、真实模型不产出该措辞）——它量的是真实分布下的准确率，不是对抗鲁棒性。
- **常量真被使用，走接缝证实**：SpyLLM 包装 FakeLLM 捕获 system 入参，断言 `spy.systems == [GOAL_JUDGE_PROMPT]`——不 patch goal 内部（反模式 2），S8 建立的 SpyLLM 手法第二次复用。
- **存量安全先扫后改**：改判定前先 grep 全部 S5 录制的 verdict 措辞（「YES，目标已达成。」等），确认整词判定下语义不变——85 passed 里那 80 条存量零改动同绿不是运气。

## 五、可迁移清单：带走的不是代码，是判断

1. **「没有 eval 的 judge」是系统里最危险的角色**——它在给别人打分，自己却没被打过分。找到你系统里所有「隐形 judge」（验收器、路由器、审核器），它们都欠一份带标签的案例集。
2. **有 ground truth 就程序判定，没有才上 LLM judge**——judge 引入档位、噪声、抽检三笔成本，别为可断言的事付这笔账。
3. **train/held_out 分批是防自欺的最小结构**——train 涨、held_out 不涨 = 过拟合回退。哪怕只有 15 个案例，这个结构也值得留。
4. **TSV 一行一跑分**：分数不落盘就没有「涨」可言——记账是闭环的地基，不是锦上添花。
5. **一次只改一处**：归因能力比迭代速度值钱。

### AI PM 视角：同一批事实，另一层判断

- eval 是 agent 产品的 CI/质量地基：没有它，改 prompt/换模型都是碰运气；有它，质量可度量、可归因、可积累——demo 到生产的分水岭。
- 写案例集就是 PM 定义质量的过程：15 个 `{goal, transcript, expected}` 里每一个 expected 都是一次产品判断（「staging 部署完 = 目标没达成」是产品语义，不是工程语义）。
- 基线分该进 PRD：「goal 判定准确率 ≥ X%（train n=10 / held_out n=5）」比「支持目标续跑」是硬得多的验收标准。

## 六、拓展练习

1. **给 summarization 建 judge 型 eval**（走 SPEC 对照表升级路径）：无 ground truth 的摘要保真度——写一份 judge rubric（信息保留率 0-10），用更强档位当 judge、`--runs 3` 取均值去噪，TSV 加 judge_model 列。验收：同一批对话，「删一半历史」的摘要分数显著低于全量摘要。
2. **假阴性一侧的对抗案例**：录一条「根据进展判断，目标已达成，YES」（YES 不在句首）——当前整词判定会假阴性。先加案例量出掉分，再决定修法（找整词 in 全文？要求 judge 末行输出结论？），体会「修 A 不引入 B」比「修 A」难在哪。
3. **把 held_out 纪律做成硬闸门**：现在「优化时不许看 held_out」靠自觉；写一个 pre-commit 钩子或 pytest 标记，让 held_out 目录在非收口分支上不可读。体会「纪律代码化」的成本与收益。

## 七、S9 收口结论

- F12 verify：`test_s9_eval` **5 passed**；全量 **85 passed**（存量 80 零改动同绿）；src **1140 行**（预算 1500）。
- 教学弧有账可查：`evals/results.tsv` 四行——baseline 0.8 → fix 1.0 → 真实模型 train 1.0 / held_out 1.0（`scripts/e2e_s9_eval.py`，ClaudeCLILLM）。
- goal.py 两处外科手术（常量 + 整词判定），`run_with_goal` 续跑协议、三缝签名、run() 签名全部不动。
- 十刀全景至此闭环：S1-S5 造骨架、CE 审上下文、S6-S8 记忆/断点/工具治理、**S9 给质量装表**——「怎么造」与「怎么知道造对了」在同一个千行仓库里都有了。
