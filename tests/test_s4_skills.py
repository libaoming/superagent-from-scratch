"""S4 / F06_skills：技能发现 + 斜杠激活（SPEC #skills）。

测试纪律不变：LLM 只从 FakeLLM 接缝进，真实 SKILL.md fixture，不 mock。
核心断言 = token 经济学：description 常驻 system（便宜），正文只在斜杠激活时进 messages（贵）。
skills 不占缝——发现/激活都在 loop 外，run() 零改动（C4）。
"""

from pathlib import Path

from src.llm import FakeLLM
from src.loop import State, run
from src.skills import activate, discover_skills

ROOT = Path(__file__).parent.parent
SKILLS = ROOT / "fixtures" / "skills"
FIX_LLM = ROOT / "fixtures" / "fake_llm"

BODY_MARK = "按这个步骤做"  # demo-skill 正文里的关键句
DESC_MARK = "统计目录文件"  # demo-skill 的 description


# ---------- 发现：递归扫 SKILL.md，只把元数据进 system ----------


def test_discover_registers_all_skills():
    registry, _ = discover_skills(SKILLS)
    assert set(registry) == {"demo-skill", "note-taker"}  # 两个都被递归发现
    assert registry["demo-skill"]["description"].startswith("统计目录文件")


def test_system_block_carries_description_not_body():
    _, system_block = discover_skills(SKILLS)
    assert DESC_MARK in system_block  # 元数据常驻 system（便宜）
    assert BODY_MARK not in system_block  # 正文一个字不进 system（贵，按需）
    assert "/demo-skill" in system_block  # 斜杠激活名可见


# ---------- 激活：斜杠触发才注入全文，进 user 前缀块 ----------


def test_slash_activates_full_text():
    registry, _ = discover_skills(SKILLS)
    injected = activate("/demo-skill 统计 workspace 有几个文件", registry)
    assert BODY_MARK in injected  # 正文按需注入
    assert DESC_MARK in injected  # 焊死注入边界=SPEC「全文」含 frontmatter（description 也在其中）
    assert "统计 workspace 有几个文件" in injected  # 原请求保留在前缀块之后


def test_no_slash_passes_through():
    registry, _ = discover_skills(SKILLS)
    assert activate("统计 workspace 有几个文件", registry) == "统计 workspace 有几个文件"


def test_unknown_skill_passes_through():
    registry, _ = discover_skills(SKILLS)
    # 未注册的斜杠名当普通文本原样放行（教学版不报错）
    assert activate("/nonexistent 做点事", registry) == "/nonexistent 做点事"


# ---------- 端到端：description 进 system、正文进 messages history ----------


def test_skill_body_enters_messages_not_system():
    registry, system_block = discover_skills(SKILLS)
    injected = activate("/demo-skill 统计 workspace", registry)
    state = run(
        State(messages=[{"role": "user", "content": injected}]),
        FakeLLM(FIX_LLM / "natural_close.json"),
        tools=[],
        system=system_block,
    )
    # 正文进了 messages（可被 Summarization 压缩、可测），不靠 system 常驻
    assert BODY_MARK in str(state.messages[0]["content"])
    assert state.messages[0]["role"] == "user"  # 走 user 角色前缀块（Q3=A）
