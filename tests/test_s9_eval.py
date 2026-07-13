"""S9 eval 闭环（SPEC #eval-loop · F12）——把「judge 好不好」变成一个能涨的数。

被评对象 = goal.py 的 _goal_met（它本身是个 LLM judge，却从没被量化测过）。
离线钉住的是 harness 机械件 + 解析边界：loader 两批分离 / runner 程序化 accuracy /
TSV 记账 / YESTERDAY 前缀词假阳性（S5 审查 Y1）修复且不过度收紧。
真实模型跑分是收口 E2E（C3：离线测试全程无网络）。
观察 judge prompt 走唯一接缝（SpyLLM 包装 FakeLLM），不 patch goal 内部（反模式 2）。
"""

from pathlib import Path

from src.evals import append_result, load_cases, run_eval
from src.goal import GOAL_JUDGE_PROMPT, _goal_met
from src.llm import FakeLLM
from src.loop import State

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _state_with(transcript: str) -> State:
    return State(messages=[{"role": "assistant", "content": [{"type": "text", "text": transcript}]}])


def test_load_cases_two_splits_sorted_and_shaped():
    train = load_cases(FIXTURES / "eval" / "train")
    held_out = load_cases(FIXTURES / "eval" / "held_out")
    assert len(train) == 10 and len(held_out) == 5
    # 按文件名序加载——录制=全局调用序的前提，顺序不定测试就神秘变红
    assert train[0]["goal"] == "写一份 README 草稿"
    assert train[3]["expected"] is False  # 04_deploy_staging_only：陷阱案例的 ground truth
    for case in train + held_out:
        assert set(case) >= {"goal", "transcript", "expected"}
        assert isinstance(case["expected"], bool)


def test_run_eval_accuracy_over_adversarial_recording():
    """对抗性录制含 2 条 YESTERDAY 前缀词措辞——整词判定修复后应满分。

    这条测试在修复落地前是红的（accuracy 0.8）：红→绿本身就是「量分驱动一次一改」的实证。
    """
    llm = FakeLLM(FIXTURES / "fake_llm" / "eval_verdicts.json")
    cases = load_cases(FIXTURES / "eval" / "train")
    result = run_eval(llm, cases)
    assert result["n"] == 10
    assert result["accuracy"] == 1.0
    assert all(pc["correct"] for pc in result["per_case"])


def test_goal_met_word_boundary_edges():
    """Y1 修复钉死：YESTERDAY 前缀词 → False；带标点整词 YES → True（防过度收紧）。"""
    llm = FakeLLM(FIXTURES / "fake_llm" / "goal_verdict_edges.json")
    assert _goal_met(llm, _state_with("staging 部署完成"), "部署到生产") is False
    assert _goal_met(llm, _state_with("用例全部通过"), "补单元测试") is True


def test_goal_judge_prompt_is_the_single_mutable_constant():
    """判定 prompt 抽成模块常量（单可变文件教学版落点）——接缝处证实 _goal_met 真用它。"""
    assert isinstance(GOAL_JUDGE_PROMPT, str) and GOAL_JUDGE_PROMPT

    class SpyLLM:
        def __init__(self, inner):
            self._inner = inner
            self.systems: list[str] = []

        def complete(self, *, system: str, messages: list[dict], tools: list[dict]) -> dict:
            self.systems.append(system)
            return self._inner.complete(system=system, messages=messages, tools=tools)

    spy = SpyLLM(FakeLLM(FIXTURES / "fake_llm" / "goal_verdict_edges.json"))
    _goal_met(spy, _state_with("staging 部署完成"), "部署到生产")
    assert spy.systems == [GOAL_JUDGE_PROMPT]


def test_load_cases_refuses_silent_boundaries(tmp_path):
    """审查黄3 钉死：空目录/错路径不许静默回空（下游会安静记 0 分账）；expected 非布尔装载时就炸。"""
    import json

    import pytest

    with pytest.raises(ValueError, match="为空或不存在"):
        load_cases(tmp_path / "no_such_dir")
    bad = tmp_path / "cases"
    bad.mkdir()
    (bad / "01_str_expected.json").write_text(
        json.dumps({"goal": "g", "transcript": "t", "expected": "true"})
    )
    with pytest.raises(ValueError, match="必须是布尔"):
        load_cases(bad)


def test_append_result_tsv_accountable(tmp_path):
    """TSV 记账：首写带表头，追加不重复表头——每行一次跑分，分数可回溯。"""
    tsv = tmp_path / "results.tsv"
    append_result(tsv, label="baseline", split="train", result={"n": 10, "accuracy": 0.8})
    append_result(tsv, label="fix-yes-word-boundary", split="train", result={"n": 10, "accuracy": 1.0})
    lines = tsv.read_text().strip().split("\n")
    assert lines[0] == "label\tsplit\tn\taccuracy"
    assert lines[1] == "baseline\ttrain\t10\t0.8"
    assert lines[2] == "fix-yes-word-boundary\ttrain\t10\t1.0"
    assert len(lines) == 3
