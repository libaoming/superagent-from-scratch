"""eval 闭环（SPEC #eval-loop）——量分 + 记账 + 一次一改 + 不涨回退。

第一个被评对象是 goal.py 的 _goal_met：它本身就是个 LLM judge（YES/NO），却从没被
量化测过——「没有 eval 的 judge」最容易藏坑（S5 审查 Y1 的 YESTERDAY 假阳性实锤）。
案例带 ground truth 标签，打分是程序化 accuracy：**能程序判定就不用 LLM-as-judge**，
judge 留给无标签的主观质量（SPEC 对照表升级路径）。
fixture 分 train/held_out 两批是防过拟合命门：train 涨、held_out 不涨 = 过拟合，回退。
TSV 路径由调用方给（S7 checkpoint 同款哲学）；真实模型跑分走收口 E2E（C3 离线纪律）。
"""

import json
from pathlib import Path

from src.goal import _goal_met
from src.loop import State


def load_cases(dir_path: str | Path) -> list[dict]:
    """按文件名序加载一批案例 `{goal, transcript, expected}`——顺序即录制序（fixtures/README 全局调用序约定）。"""
    cases = []
    for p in sorted(Path(dir_path).glob("*.json")):
        case = json.loads(p.read_text())
        missing = {"goal", "transcript", "expected"} - set(case)
        if missing:
            raise ValueError(f"案例缺字段 {missing}：{p}")
        if not isinstance(case["expected"], bool):
            # "true"（字符串）会被静默判错、1 会因 True==1 静默通过——类型错在装载时炸，不进跑分
            raise ValueError(f"expected 必须是布尔：{p} 给的是 {type(case['expected']).__name__}")
        case["name"] = p.stem
        cases.append(case)
    if not cases:
        # 空目录/写错路径 glob 静默回空 → 下游安静记一行 0 分账，比报错更危险
        raise ValueError(f"案例目录为空或不存在：{dir_path}")
    return cases


def run_eval(llm, cases: list[dict]) -> dict:
    """逐案例把 transcript 装进 State 喂 _goal_met，与 ground truth 比对出 accuracy。"""
    per_case = []
    for case in cases:
        state = State(
            messages=[{"role": "assistant", "content": [{"type": "text", "text": case["transcript"]}]}]
        )
        predicted = _goal_met(llm, state, case["goal"])
        per_case.append(
            {
                "name": case["name"],
                "expected": case["expected"],
                "predicted": predicted,
                "correct": predicted == case["expected"],
            }
        )
    n = len(per_case)
    return {
        "n": n,
        "accuracy": sum(pc["correct"] for pc in per_case) / n if n else 0.0,
        "per_case": per_case,
    }


def append_result(path: str | Path, *, label: str, split: str, result: dict) -> None:
    """一行一跑分的 TSV 记账：分数可回溯、改动可归因（label 记「改了哪一处」，配 commit hash 用）。"""
    path = Path(path)
    line = f"{label}\t{split}\t{result['n']}\t{result['accuracy']}\n"
    if not path.exists():
        path.write_text("label\tsplit\tn\taccuracy\n" + line)
    else:
        with path.open("a") as f:
            f.write(line)
