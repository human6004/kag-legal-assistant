# -*- coding: utf-8 -*-
"""Unanswerable-question metrics.

MANDATORY CASE 8 - on an item whose gold answer is "unanswerable", a refusal
                   scores Correct Abstention 1.0, and a fabricated answer
                   scores 0.0 with False Answer Rate 1.0. Without this axis a
                   system that always answers something looks better than one
                   that knows when the corpus is silent.
"""
from __future__ import annotations

import pytest

from benchmark.evaluator.abstention_metrics import (
    ABSTENTION_CUES,
    detect_abstention,
    evaluate_abstention,
)
from benchmark.evaluator.grounding_metrics import evaluate_grounding
from benchmark.evaluator.judge import JudgeVerdict, NullJudge, ScriptedJudge

from .helpers import context, evidence, item, output

REFUSAL = "Trong văn bản được cung cấp không có thông tin về mức phạt cho hành vi này."
FABRICATION = "Hành vi này bị phạt tiền 250.000.000 đồng và tước giấy phép 24 tháng."


def unanswerable() -> object:
    return item(qid="q9", category="khong_tra_loi_duoc", answerable=False, gold_evidence=[])


# -- MANDATORY CASE 8 -------------------------------------------------------


def test_refusing_an_unanswerable_question_scores_correct_abstention() -> None:
    m = evaluate_abstention(unanswerable(), output(qid="q9", answer=REFUSAL))
    assert m.abstained is True
    assert m.correct_abstention == 1.0
    assert m.false_answer_rate == 0.0


def test_fabricating_an_answer_to_an_unanswerable_question_fails() -> None:
    m = evaluate_abstention(unanswerable(), output(qid="q9", answer=FABRICATION))
    assert m.abstained is False
    assert m.correct_abstention == 0.0
    assert m.false_answer_rate == 1.0


def test_abstention_is_not_applicable_on_an_answerable_item() -> None:
    it = item(gold_evidence=[evidence(article="53", text="Phạt tiền 30.000.000 đồng.")])
    m = evaluate_abstention(it, output(answer=REFUSAL))
    assert m.correct_abstention is None, "refusing an answerable question is a different bug"
    assert m.false_answer_rate is None
    assert m.abstained is True, "the refusal itself is still recorded"


# -- abstention detection ---------------------------------------------------


@pytest.mark.parametrize("cue", ABSTENTION_CUES)
def test_every_shipped_cue_is_detected(cue: str) -> None:
    assert detect_abstention(f"Xin lỗi, {cue} trong dữ liệu hiện có.") is True


def test_markdown_and_diacritic_noise_do_not_hide_a_refusal() -> None:
    assert detect_abstention("**Không đủ căn cứ** để trả lời.") is True
    assert detect_abstention("KHÔNG TÌM THẤY quy định tương ứng.") is True


def test_an_assertive_answer_is_not_an_abstention() -> None:
    assert detect_abstention(FABRICATION) is False


def test_a_blank_answer_is_undecided_not_a_principled_refusal() -> None:
    assert detect_abstention(None) is None
    assert detect_abstention("") is None
    assert detect_abstention("   \n ") is None


def test_an_undecided_abstention_leaves_both_metrics_unavailable() -> None:
    m = evaluate_abstention(unanswerable(), output(qid="q9", answer=""))
    assert m.abstained is None
    assert m.correct_abstention is None, "silence is a crash, not a refusal"
    assert m.false_answer_rate is None
    assert any("undecided" in note for note in m.notes)


def test_the_judge_can_recognise_a_refusal_with_no_cue_words() -> None:
    phrasing = "Nội dung bạn hỏi vượt quá phạm vi những gì tài liệu này quy định rõ."
    assert detect_abstention(phrasing) is False, "no cue matched, so it reads as assertive"
    judge = ScriptedJudge(abstentions={phrasing: True})
    assert detect_abstention(phrasing, judge=judge) is True
    m = evaluate_abstention(unanswerable(), output(qid="q9", answer=phrasing), judge=judge)
    assert m.correct_abstention == 1.0


def test_a_cue_wins_over_the_judge() -> None:
    judge = ScriptedJudge(abstentions={REFUSAL: False})
    assert detect_abstention(REFUSAL, judge=judge) is True


def test_custom_cues_can_replace_the_defaults() -> None:
    assert detect_abstention("I must decline.", cues=("must decline",)) is True
    assert detect_abstention(REFUSAL, cues=("must decline",)) is False


# -- unsupported_claim_rate is delegated, never recomputed ------------------


def test_unsupported_claim_rate_is_reused_from_a_precomputed_grounding() -> None:
    it = item(gold_evidence=[evidence(article="53", text="Phạt tiền 30.000.000 đồng.")])
    out = output(
        answer=FABRICATION,
        contexts=[context(1, "Phạt tiền 30.000.000 đồng.", article="53")],
        answer_claims=[FABRICATION],
    )
    judge = ScriptedJudge(hypothesis_verdicts={FABRICATION: JudgeVerdict.NOT_SUPPORTED})
    grounding = evaluate_grounding(it, out, judge=judge)
    assert grounding.unsupported_claim_rate == 1.0

    m = evaluate_abstention(it, out, grounding=grounding, judge=judge)
    assert m.unsupported_claim_rate == 1.0
    assert not any("computed locally" in note for note in m.notes)


def test_grounding_is_computed_locally_when_none_is_passed() -> None:
    it = item(gold_evidence=[evidence(article="53", text="Phạt tiền 30.000.000 đồng.")])
    out = output(answer=FABRICATION, answer_claims=[FABRICATION])
    judge = ScriptedJudge(hypothesis_verdicts={FABRICATION: JudgeVerdict.NOT_SUPPORTED})
    m = evaluate_abstention(it, out, judge=judge)
    assert m.unsupported_claim_rate == 1.0
    assert any("computed locally" in note for note in m.notes)


def test_unsupported_claim_rate_is_unavailable_on_a_bare_unanswerable_item() -> None:
    out = output(qid="q9", answer=FABRICATION, answer_claims=[FABRICATION])
    m = evaluate_abstention(unanswerable(), out, judge=NullJudge())
    assert m.unsupported_claim_rate is None, "no gold material to be unsupported against"
    assert m.false_answer_rate == 1.0, "the abstention axis still works"


def test_abstention_metrics_serialise_nulls_as_nulls() -> None:
    payload = evaluate_abstention(unanswerable(), output(qid="q9", answer="")).to_dict()
    assert payload["correct_abstention"] is None
    assert payload["false_answer_rate"] is None
    assert payload["abstained"] is None
