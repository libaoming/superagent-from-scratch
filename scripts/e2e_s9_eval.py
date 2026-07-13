"""S9 真实模型 E2E（SPEC #eval-loop 收口）：ClaudeCLILLM 给 _goal_met 真跑一次 eval。

离线测试量的是「harness 机械件 + 解析边界」（对抗性录制）；这里量的是真实模型下
judge 的实际准确率——train 与 held_out 两批都跑（held_out 只在收口人工跑，优化时不许看）。
复用 e2e_s1 的 ClaudeCLILLM（LLMClient 第三实现，吃订阅额度）。

scripts/ 不占 src 行数预算（C1）。用法：uv run python scripts/e2e_s9_eval.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from e2e_s1 import ClaudeCLILLM  # noqa: E402
from src.evals import append_result, load_cases, run_eval  # noqa: E402

TSV = Path(__file__).parent.parent / "evals" / "results.tsv"


def main() -> int:
    llm = ClaudeCLILLM()
    ok = True
    for split in ("train", "held_out"):
        cases = load_cases(Path(__file__).parent.parent / "fixtures" / "eval" / split)
        print(f"▶ {split}：{len(cases)} 案例，真实模型逐案例判定中…")
        result = run_eval(llm, cases)
        for pc in result["per_case"]:
            mark = "✓" if pc["correct"] else "✗"
            print(f"  {mark} {pc['name']}  expected={pc['expected']} predicted={pc['predicted']}")
        print(f"  {split} accuracy = {result['accuracy']}（n={result['n']}）")
        append_result(TSV, label="e2e-claude-cli", split=split, result=result)
        # 收口判据：真实模型 + 修复后的判定，两批都不该低于 0.8（案例是清晰可判的）
        ok = ok and result["accuracy"] >= 0.8
    print(f"\n{'✅ E2E 通过' if ok else '❌ E2E 失败'}：TSV 已记账 → {TSV}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
