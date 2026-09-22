# -*- coding: utf-8 -*-
"""Answer-side metrics.

MANDATORY CASE 2 - hit_all is 1.0 for 3 markers out of 3 and 0.0 for 2 out of 3.
                   It is all-or-nothing on purpose: a penalty answer that names
                   two of three sanctions is wrong, not 67% right.
"""
from __future__ import annotations

import pytest

from benchmark.evaluator.answer_metrics import (
    answer_claims,
    evaluate_answer,
    hit_all,
    hit_rate,
    marker_hits,
)
from benchmark.evaluator.judge import JudgeVerdict, NullJudge, RuleBasedJudge, ScriptedJudge

from .helpers import evidence, item, output

THREE_MARKERS = ("30.000.000 đồng", "50.000.000 đồng", "đình chỉ hoạt động")


# -- MANDATORY CASE 2: hit_all is all-or-nothing ----------------------------


def test_hit_all_is_one_when_all_three_markers_are_present() -> None:
    it = item(gold_markers=THREE_MARKERS)
    out = output(
        answer=(
            "Phạt tiền từ 30.000.000 đồng đến 50.000.000 đồng "
            "và đình chỉ hoạt động từ 06 tháng đến 12 tháng."
        )
    )
    m = evaluate_answer(it, out)
    assert m.n_markers_hit == 3
    assert m.hit_rate == 1.0
    assert m.hit_all == 1.0
    assert m.missing_markers == []


def test_hit_all_is_zero_when_only_two_of_three_markers_are_present() -> None:
    it = item(gold_markers=THREE_MARKERS)
    out = output(answer="Phạt tiền từ 30.000.000 đồng đến 50.000.000 đồng.")
    m = evaluate_answer(it, out)
    assert m.n_markers_hit == 2
    assert m.hit_rate == pytest.approx(2 / 3)
    assert m.hit_all == 0.0, "hit_all must not be a partial credit metric"
    assert m.missing_markers == ["đình chỉ hoạt động"]


def test_hit_rate_and_hit_all_are_not_applicable_without_gold_markers() -> None:
    m = evaluate_answer(item(gold_markers=()), output(answer="Bất kỳ câu trả lời nào."))
    assert m.hit_rate is None
    assert m.hit_all is None, "no markers is 'not applicable', not a free 1.0"
    assert m.n_gold_markers == 0


def test_marker_helpers_agree_with_evaluate_answer() -> None:
    answer = "Phạt tiền 30.000.000 đồng."
    assert marker_hits(answer, THREE_MARKERS) == [True, False, False]
    assert hit_rate(answer, THREE_MARKERS) == pytest.approx(1 / 3)
    assert hit_all(answer, THREE_MARKERS) == 0.0
    assert hit_rate(answer, ()) is None
    assert hit_all(answer, ()) is None


def test_number_formatting_does_not_break_a_marker_hit() -> None:
    """Same requirement as MANDATORY CASE 1, seen through the answer metric."""
    it = item(gold_markers=("100.000.000",))
    out = output(answer="Mức phạt tối đa là 100 000 000 đồng.")
    assert evaluate_answer(it, out).hit_all == 1.0


# -- empty answer vs errored answer ----------------------------------------


def test_empty_answer_without_an_error_is_an_honest_zero() -> None:
    m = evaluate_answer(item(gold_markers=THREE_MARKERS), output(answer=""))
    assert m.hit_rate == 0.0
    assert m.hit_all == 0.0


def test_an_errored_run_reports_unavailable_not_zero() -> None:
    m = evaluate_answer(
        item(gold_markers=THREE_MARKERS), output(answer=None, error="HTTP 500")
    )
    assert m.hit_rate is None
    assert m.hit_all is None
    assert m.claim_precision is None
    assert m.claim_recall is None
    assert m.claim_f1 is None
    assert any("error" in note for note in m.notes)


# -- claim precision / recall / f1 -----------------------------------------


def test_claim_metrics_are_unavailable_without_claim_extraction() -> None:
    it = item(gold_claims=("Mức phạt là 30 triệu đồng.",))
    m = evaluate_answer(it, output(answer="Mức phạt là 30 triệu đồng."), judge=NullJudge())
    assert m.n_answer_claims is None
    assert m.claim_precision is None
    assert m.claim_f1 is None
    assert m.claim_recall == 1.0, "recall is deterministic here: gold text is in the answer"


def test_claim_precision_counts_claims_supported_by_gold_material() -> None:
    it = item(
        gold_claims=("Mức phạt tiền là 30.000.000 đồng.",),
        gold_evidence=[evidence(article="53", text="Phạt tiền 30.000.000 đồng.")],
    )
    out = output(
        answer="Mức phạt tiền là 30.000.000 đồng. Ngoài ra bị tịch thu toàn bộ tài sản.",
        answer_claims=[
            "Mức phạt tiền là 30.000.000 đồng.",
            "Bị tịch thu toàn bộ tài sản.",
        ],
    )
    m = evaluate_answer(it, out, judge=RuleBasedJudge(reject_threshold=0.2))
    assert m.n_answer_claims == 2
    assert m.claim_precision == pytest.approx(0.5)
    assert m.claim_recall == 1.0
    assert m.claim_f1 == pytest.approx(2 * 0.5 * 1.0 / 1.5)


def test_claim_f1_is_zero_when_both_sides_are_zero_not_a_zero_division() -> None:
    it = item(
        gold_claims=("Mức phạt là 30.000.000 đồng.",),
        gold_evidence=[evidence(article="53", text="Phạt tiền 30.000.000 đồng.")],
    )
    out = output(answer="Không bị xử phạt.", answer_claims=["Hành vi này được miễn trừ."])
    m = evaluate_answer(it, out, judge=RuleBasedJudge(reject_threshold=0.5))
    assert m.claim_precision == 0.0
    assert m.claim_recall == 0.0
    assert m.claim_f1 == 0.0


def test_undecided_claims_stay_out_of_the_numerator() -> None:
    it = item(
        gold_claims=(),
        gold_evidence=[evidence(article="53", text="Phạt tiền 30.000.000 đồng.")],
    )
    out = output(answer="Có thể bị xử lý.", answer_claims=["Có thể bị xử lý."])
    m = evaluate_answer(it, out, judge=NullJudge())
    assert m.claim_precision == 0.0
    assert m.n_claim_undecided == 1
    assert m.claim_recall is None, "no gold claims -> claim_recall not applicable"


def test_claim_recall_can_fall_back_to_the_judge() -> None:
    gold = "Thời hạn đình chỉ hoạt động là 06 tháng."
    it = item(gold_claims=(gold,))
    out = output(answer="Cơ sở phải tạm dừng nửa năm.")
    judge = ScriptedJudge(hypothesis_verdicts={gold: JudgeVerdict.SUPPORTED})
    assert evaluate_answer(it, out, judge=judge).claim_recall == 1.0


def test_answer_claims_prefers_the_adapter_over_the_judge() -> None:
    out = output(answer="A. B.", answer_claims=["A.", "B."])
    judge = ScriptedJudge(claims={"A. B.": ["something else"]})
    assert answer_claims(out, judge) == ["A.", "B."]


def test_answer_claims_is_none_when_nothing_can_extract_them() -> None:
    assert answer_claims(output(answer="A. B."), None) is None
    assert answer_claims(output(answer="A. B."), NullJudge()) is None
    assert answer_claims(output(answer=None), ScriptedJudge(claims={"": ["x"]})) is None
