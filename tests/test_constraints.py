"""SPEC 关键约束的机器闸门（对抗审查 2026-07-06 红色发现 2 的修复）。

C1 行数预算原文「检验方式：CI 脚本 wc -l 断言」——本项目无 CI，pytest 就是每次必跑的闸门。
预算超了测试直接红，比约定俗成的「记得别写多」可靠。
"""

from pathlib import Path

SRC = Path(__file__).parent.parent / "src"


def test_c1_src_total_line_budget():
    total = sum(len(f.read_text().splitlines()) for f in SRC.rglob("*.py"))
    assert total <= 1500, f"C1 违约：src/ 共 {total} 行 > 1500——在复刻产品功能而非教学核心，砍"
