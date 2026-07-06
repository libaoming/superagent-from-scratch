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
6. **切片收口 quiz（不满分不打 tag）**：每切片打 `sfs-s{n}` tag 前，Claude 出一份该切片的架构 quiz（why 级别：为什么这么设计 / deer-flow 对照 / 换个做法会怎样）考用户，满分才打 tag——本项目是教学复刻 + 面试作品，「用户真的懂了」和测试绿同为验收物（源自 Thariq《Field Guide to Fable》的 merge 闸门）
7. **对抗审查（quiz 之前）**：派 fresh-context 子 agent 对照 SPEC 锚点 + feature 条目审查实现——「每条需求都实现了吗、边界有测试吗、out_of_scope 的东西没动吗」，只报影响正确性的 gap（Anthropic best-practices adversarial review；实现者不能自评）

## 4. commit 规范
`{feat|fix|refactor|docs}(feature_id): 描述`

## 5. 反模式
过早宣布胜利 / 一次性大包大揽 / 环境不可复现 / 缺端到端验证 → 对应修法见项目 CLAUDE.md L2。
