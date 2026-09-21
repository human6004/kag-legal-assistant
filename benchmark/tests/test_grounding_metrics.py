# -*- coding: utf-8 -*-
"""Grounding metrics: faithfulness vs hallucination, kept strictly apart.

MANDATORY CASE 6 - a claim that is true per gold but absent from this system's
                   retrieved context lowers `faithfulness` while
                   `hallucination_rate` stays 0.0. If the two were computed as
                   `1 - faithfulness`, a retrieval gap would be reported as a
                   fabrication, which is the single easiest way to make a RAG
                   comparison say the wrong thing.
"""
from __future__ import annotations

import pytest

from benchmark.evaluator.grounding_metrics import (
    ClaimStatus,
    classify_claim,
    evaluate_grounding,
)
from benchmark.evaluator.judge import (
    JudgeUsage,
    JudgeVerdict,
    NullJudge,
    RuleBasedJudge,
    ScriptedJudge,
)

from .helpers import context, evidence, item, output

E1 = "Phạt tiền từ 30.000.000 đồng đến 50.000.000 đồng."
E2 = "Tổ chức vi phạm bị đình chỉ hoạt động từ 06 tháng đến 12 tháng."
FABRICATION = "Người vi phạm bị phạt tù 03 năm."


def gold_item() -> object:
    return item(
        gold_evidence=[
            evidence(article="53", text=E1, evidence_id="E1"),
            evidence(article="54", text=E2, evidence_id="E2"),
        ]
    )


# -- MANDATORY CASE 6 -------------------------------------------------------


def test_a_gold_true_claim_missing_from_context_costs_faithfulness_only() -> None:
    it = gold_item()
    out = output(
        answer=E1 + " " + E2,
        contexts=[context(1, E1, article="53")],  # E2 was never retrieved
        answer_claims=[E1, E2],
    )
    m = evaluate_grounding(it, out)

    assert m.n_claims == 2
    assert m.faithfulness == pytest.approx(0.5), "only one claim is backed by own context"
    assert m.hallucination_rate == 0.0, "the other claim is true per gold, not invented"
    assert m.retrieval_gap_rate == pytest.approx(0.5)
    assert [c.status for c in m.claims] == [
        ClaimStatus.SUPPORTED_BY_CONTEXT,
        ClaimStatus.SUPPORTED_BY_GOLD_NOT_CONTEXT,
    ]


def test_hallucination_rate_is_not_one_minus_faithfulness() -> None:
    """Same run, stated as the invariant the paper depends on."""
    it = gold_item()
    out = output(
        answer=E1 + " " + E2,
        contexts=[context(1, E1, article="53")],
        answer_claims=[E1, E2],
    )
    m = evaluate_grounding(it, out)
    assert m.hallucination_rate != 1 - m.faithfulness
    assert m.faithfulness + m.hallucination_rate + m.retrieval_gap_rate == pytest.approx(1.0)


def test_a_fabricated_claim_does_raise_the_hallucination_rate() -> None:
    it = gold_item()
    out = output(
        answer=E1 + " " + FABRICATION,
        contexts=[context(1, E1, article="53")],
        answer_claims=[E1, FABRICATION],
    )
    # A judge that can actually say "no" is required: RuleBasedJudge leaves a
    # partial lexical overlap UNKNOWN rather than guessing, which is why the
    # same run below lands in the undecided bucket instead.
    m = evaluate_grounding(it, out, judge=ScriptedJudge(
        hypothesis_verdicts={FABRICATION: JudgeVerdict.NOT_SUPPORTED}
    ))
    assert m.faithfulness == pytest.approx(0.5)
    assert m.hallucination_rate == pytest.approx(0.5)
    assert m.retrieval_gap_rate == 0.0
    assert m.claims[1].status is ClaimStatus.UNSUPPORTED


def test_the_three_buckets_partition_every_claim() -> None:
    it = gold_item()
    out = output(
        answer="all three",
        contexts=[context(1, E1, article="53")],
        answer_claims=[E1, E2, FABRICATION],
    )
    m = evaluate_grounding(it, out, judge=RuleBasedJudge(reject_threshold=0.3))
    total = (
        m.faithfulness * m.n_claims
        + m.retrieval_gap_rate * m.n_claims
        + m.hallucination_rate * m.n_claims
        + m.n_undecided
    )
    assert total == pytest.approx(m.n_claims)


# -- contradiction vs plain absence ----------------------------------------


def test_contradiction_is_reported_separately_when_a_judge_can_see_it() -> None:
    it = gold_item()
    claim = "Hành vi này không bị xử phạt."
    out = output(answer=claim, contexts=[context(1, E1, article="53")], answer_claims=[claim])
    judge = ScriptedJudge(hypothesis_verdicts={claim: JudgeVerdict.CONTRADICTED})
    m = evaluate_grounding(it, out, judge=judge)
    assert m.claims[0].status is ClaimStatus.CONTRADICTED
    assert m.hallucination_rate == 1.0
    assert m.faithfulness == 0.0


def test_without_a_judge_contradiction_and_absence_are_not_separated() -> None:
    it = gold_item()
    out = output(
        answer=FABRICATION, contexts=[context(1, E1, article="53")], answer_claims=[FABRICATION]
    )
    m = evaluate_grounding(it, out)
    assert m.claims[0].status is ClaimStatus.UNDECIDED
    assert m.hallucination_rate == 0.0, "undecided must not be counted as a hallucination"
    assert m.n_undecided == 1


def test_undecided_claims_are_excluded_from_every_numerator() -> None:
    it = gold_item()
    vague = "Có thể phát sinh nghĩa vụ khác."
    out = output(
        answer=vague,
        contexts=[context(1, E1, article="53")],
        answer_claims=[E1, vague],
    )
    m = evaluate_grounding(it, out, judge=NullJudge())
    assert m.n_undecided == 1
    assert m.faithfulness == pytest.approx(0.5)
    assert m.hallucination_rate == 0.0
    assert m.retrieval_gap_rate == 0.0


# -- faithfulness is measured against the system's OWN context -------------


def test_faithfulness_never_borrows_another_systems_context() -> None:
    it = gold_item()
    rich = output(qid=it.id, system="a", contexts=[context(1, E1), context(2, E2)], answer_claims=[E1, E2])
    poor = output(qid=it.id, system="b", contexts=[context(1, E1)], answer_claims=[E1, E2])
    assert evaluate_grounding(it, rich).faithfulness == 1.0
    assert evaluate_grounding(it, poor).faithfulness == pytest.approx(0.5)


def test_a_claim_in_context_is_faithful_even_when_gold_disagrees() -> None:
    """Faithfulness asks 'did your retriever surface this', nothing more."""
    it = gold_item()
    claim = "Mức phạt là 999.000.000 đồng."
    out = output(contexts=[context(1, claim, article="53")], answer_claims=[claim])
    m = evaluate_grounding(it, out, judge=RuleBasedJudge(reject_threshold=0.3))
    assert m.faithfulness == 1.0
    assert m.claims[0].status is ClaimStatus.SUPPORTED_BY_CONTEXT


# -- not applicable / unavailable -------------------------------------------


def test_grounding_is_unavailable_when_claims_cannot_be_extracted() -> None:
    m = evaluate_grounding(gold_item(), output(answer="Một câu trả lời."), judge=NullJudge())
    assert m.n_claims is None
    assert m.faithfulness is None
    assert m.hallucination_rate is None
    assert m.unsupported_claim_rate is None


def test_zero_claims_is_not_applicable_rather_than_a_perfect_score() -> None:
    m = evaluate_grounding(gold_item(), output(answer_claims=[]))
    assert m.n_claims == 0
    assert m.faithfulness is None
    assert m.hallucination_rate is None


def test_unsupported_claim_rate_needs_gold_material() -> None:
    it = item(qid="q9", answerable=False, gold_evidence=[], gold_claims=())
    out = output(qid="q9", answer=FABRICATION, answer_claims=[FABRICATION])
    m = evaluate_grounding(it, out, judge=RuleBasedJudge(reject_threshold=0.3))
    assert m.unsupported_claim_rate is None
    assert any("not applicable" in note for note in m.notes)


def test_unsupported_claim_rate_uses_only_claims_with_a_decidable_gold_side() -> None:
    it = gold_item()
    out = output(
        contexts=[context(1, E1, article="53")],
        answer_claims=[E1, FABRICATION],
    )
    m = evaluate_grounding(it, out, judge=ScriptedJudge(
        hypothesis_verdicts={FABRICATION: JudgeVerdict.NOT_SUPPORTED}
    ))
    assert m.unsupported_claim_rate == 1.0, "only the fabrication had a decidable gold side"
    assert m.hallucination_rate == pytest.approx(0.5)


# -- plumbing ---------------------------------------------------------------


def test_explicit_claims_argument_wins_over_the_output() -> None:
    it = gold_item()
    out = output(contexts=[context(1, E1)], answer_claims=[FABRICATION])
    m = evaluate_grounding(it, out, claims=[E1])
    assert m.faithfulness == 1.0


def test_classify_claim_is_usable_on_its_own() -> None:
    g = classify_claim(E1, gold_item(), output(contexts=[context(1, E1, article="53")]))
    assert g.status is ClaimStatus.SUPPORTED_BY_CONTEXT
    assert g.context_supported is True
    assert g.to_dict()["status"] == "supported_by_context"


def test_judge_usage_is_recorded_when_a_usage_object_is_passed() -> None:
    usage = JudgeUsage()
    out = output(contexts=[context(1, "Nội dung khác.")], answer_claims=[FABRICATION])
    evaluate_grounding(gold_item(), out, judge=RuleBasedJudge(), usage=usage)
    assert usage.calls > 0
    assert usage.calls == usage.decided + usage.unknown
