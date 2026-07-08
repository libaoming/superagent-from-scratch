# M1 Session Kickoff（开新会话先读这份）

> 接班说明：不靠任何人讲背景，10 分钟内选到正确的下一件事干。
> 依据：Anthropic "Effective Harnesses for Long-Running Agents"。

## 0. 一句话定位
教学向极简 SuperAgent harness —— 千行级复刻 bytedance/deer-flow 核心架构（agent loop → middleware 管线 → subagent 委派 → skills → 长任务），Python 3.12、零框架依赖、fixture 先行，英文主 README 双语开源（MIT）

## 1. Session 启动 5 步
1. `cat M1/PROGRESS.md` → 看 active_feature / blockers / next_candidates
2. 读 `../STATUS.md` → 一句话状态 + 踩坑
3. `bash M1/init.sh` → 环境全绿才开工
4. 按"选 feature 算法"挑下一件事
5. 动手 → 收尾更新 PROGRESS.md + STATUS.md

## 1.5 切片教学环（整个切片 = 准备一场面试）
每个切片按「准备一场面试」的完整弧设计，四步：

1. **提炼考点**（切片开始）：Claude 从 SPEC 该切片锚点 + deer-flow 对照 + Agent PM 面试常问，提炼该切片的**考点清单**（3-5 条 why 级考点：为什么这么设计 / 换个做法会怎样 / 产品视角怎么讲），写进 `teach/` 工作区（随该切片课程材料）
2. **讲解**（理论课）：**提醒用户跑 `/teach`** 上本切片理论课，按考点清单讲——目标不是「听懂」而是「学完能对面试官脱稿讲清」，含常见追问怎么接。`/teach` 只能用户显式触发，Claude 的职责 = 到点提醒 + 把知识源备好（notes/、SPEC 锚点、deer-flow 路径喂给 `teach/RESOURCES.md`）。用户上完课再动代码
3. **检查**（收口面试模拟）：切片代码收口时按**同一份考点清单**模拟面试（规矩 6）——课上讲什么，收口就考什么
4. **复盘**（补弱）：漏答的要点 + 评估记录落 `teach/learning-records/`，下切片课程开头复测（spacing）

检查 `teach/NOTES.md` 课程进度判断当前切片走到哪一步。

## 2. 选 feature 算法
1. 优先 `status=failing` 且 `blocking=[]` 的最低编号 feature
2. 没有则取 `pending` 且依赖已 passing 的
3. 同一 slice 内做完再进下一 slice（线性切片）

## 3. 6 条硬规矩
1. **fixture 先于代码**：verify 引用的 fixture 不存在就先造，不许 mock
2. **verify 真跑通才改 passing**：单测过只到 in_progress
3. **不跳 slice**：当前 slice 的 exit_criteria 没达成不开下一个
4. **收尾必更新 PROGRESS.md + STATUS.md**
5. **偏差协议（Deviations）**：撞上边缘情况不得不偏离 SPEC/计划时——选保守选项 → 记进 PROGRESS.md 的「Deviations」栏 → 继续；收尾把 Deviations 逐条向用户核对，不静默改道
6. **切片收口面试模拟（不过关不打 tag）**：每切片打 `sfs-s{n}` tag 前，Claude 以 Agent PM 面试官身份，按该切片**考点清单**（1.5 节第 1 步提炼的那份）出 3-5 道面试题（why 级 + 追问一层），**每题预设要点清单**；用户作答后逐题评估：命中要点即过，全过才打 tag。漏掉的要点 + 评估记录写进 `teach/learning-records/`（编号递增）当复训材料——本项目是教学复刻 + 面试作品，「用户真的懂了」和测试绿同为验收物（源自 Thariq《Field Guide to Fable》的 merge 闸门，是 1.5 节教学环的第 3-4 步）
7. **对抗审查（面试模拟之前）**：派 fresh-context 子 agent 对照 SPEC 锚点 + feature 条目审查实现——「每条需求都实现了吗、边界有测试吗、out_of_scope 的东西没动吗」，只报影响正确性的 gap（Anthropic best-practices adversarial review；实现者不能自评）

## 4. commit 规范
`{feat|fix|refactor|docs}(feature_id): 描述`

## 5. 反模式
过早宣布胜利 / 一次性大包大揽 / 环境不可复现 / 缺端到端验证 → 对应修法见项目 CLAUDE.md L2。
