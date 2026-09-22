# -*- coding: utf-8 -*-
"""Citation metrics: the answer may be right while the pointer is wrong.

MANDATORY CASE 7 - gold evidence is Điều 53 but the answer cites Điều 52.
                   Article Accuracy must fail while Document Accuracy passes,
                   and answer correctness (hit_all) may still be 1.0. A legal
                   assistant that states the right penalty under the wrong
                   article is a different failure from one that states the
                   wrong penalty, and the report has to show both.
"""
from __future__ import annotations

import pytest

from benchmark.evaluator.answer_metrics import evaluate_answer
from benchmark.evaluator.citation_metrics import evaluate_citations, level_accuracy
from benchmark.evaluator.judge import JudgeVerdict, NullJudge, ScriptedJudge

from .helpers import DOC, citation, context, evidence, item, output

E1 = "Phạt tiền từ 30.000.000 đồng đến 50.000.000 đồng."
E2 = "Tổ chức vi phạm bị đình chỉ hoạt động từ 06 tháng đến 12 tháng."


# -- MANDATORY CASE 7 -------------------------------------------------------


def test_citing_dieu_52_for_dieu_53_fails_article_accuracy_only() -> None:
    it = item(
        gold_markers=("30.000.000 đồng", "50.000.000 đồng"),
        gold_evidence=[evidence(article="53", text=E1)],
    )
    out = output(
        answer="Phạt tiền từ 30.000.000 đồng đến 50.000.000 đồng theo Điều 52.",
        contexts=[context(1, E1, article="53")],
        citations=[citation(article="52")],
    )

    cit = evaluate_citations(it, out)
    assert cit.document_accuracy == 1.0, "the decree is right"
    assert cit.article_accuracy == 0.0, "the article is not"
    assert cit.citation_recall == 0.0, "gold Điều 53 was never pointed at"
    assert cit.citation_precision == 0.0

    ans = evaluate_answer(it, out)
    assert ans.hit_all == 1.0, "answer correctness is a separate axis and can still pass"


def test_citing_the_right_article_passes_every_level_that_applies() -> None:
    it = item(gold_evidence=[evidence(article="53", text=E1)])
    out = output(citations=[citation(article="53")], contexts=[context(1, E1, article="53")])
    cit = evaluate_citations(it, out)
    assert cit.document_accuracy == 1.0
    assert cit.article_accuracy == 1.0
    assert cit.citation_precision == 1.0
    assert cit.citation_recall == 1.0
    assert cit.clause_accuracy is None, "gold declares no clause -> not applicable"
    assert cit.point_accuracy is None


def test_citing_the_wrong_document_fails_at_the_document_level() -> None:
    it = item(gold_evidence=[evidence(article="53", text=E1)])
    out = output(citations=[citation(article="53", document_id="331/2026/NĐ-CP")])
    cit = evaluate_citations(it, out)
    assert cit.document_accuracy == 0.0
    assert cit.article_accuracy == 0.0, "a right article in the wrong decree is not right"
    assert cit.citation_recall == 0.0


def test_an_article_cannot_borrow_credit_from_another_document() -> None:
    """Gold has doc A/Điều 53 and doc B/Điều 70; a citation of A/Điều 70 is wrong."""
    it = item(
        gold_evidence=[
            evidence(article="53", text=E1),
            evidence(article="70", text=E2, document_id="331/2026/NĐ-CP"),
        ]
    )
    out = output(citations=[citation(article="70", document_id=DOC)])
    cit = evaluate_citations(it, out)
    assert cit.document_accuracy == 1.0
    assert cit.article_accuracy == 0.0


# -- clause / point diagnostics --------------------------------------------


def test_clause_and_point_are_diagnostic_but_really_computed() -> None:
    it = item(gold_evidence=[evidence(article="53", clause="3", point="b", text=E1)])
    out = output(citations=[citation(article="53", clause="3", point="a")])
    cit = evaluate_citations(it, out)
    assert cit.article_accuracy == 1.0
    assert cit.clause_accuracy == 1.0
    assert cit.point_accuracy == 0.0


def test_a_coarser_citation_is_not_penalised_at_a_level_it_never_claimed() -> None:
    it = item(gold_evidence=[evidence(article="53", clause="3", text=E1)])
    out = output(citations=[citation(article="53")])
    cit = evaluate_citations(it, out)
    assert cit.article_accuracy == 1.0
    assert cit.clause_accuracy is None, "the citation declared no clause to be wrong about"


def test_level_accuracy_reports_not_applicable_instead_of_zero() -> None:
    gold = item(gold_evidence=[evidence(article="53", text=E1)]).gold_evidence
    value, n = level_accuracy([], gold, "article")
    assert value is None and n == 0
    value, n = level_accuracy(
        output(citations=[citation(article="53")]).citations, gold, "point"
    )
    assert value is None and n == 0


def test_level_accuracy_rejects_an_unknown_level() -> None:
    with pytest.raises(ValueError):
        level_accuracy([], [], "paragraph")


# -- precision vs recall ---------------------------------------------------


def test_citation_precision_and_recall_move_independently() -> None:
    it = item(
        gold_evidence=[
            evidence(article="53", text=E1, evidence_id="E1"),
            evidence(article="54", text=E2, evidence_id="E2"),
        ]
    )
    # One right citation plus one invented one: precision 0.5, recall 0.5.
    out = output(citations=[citation(article="53"), citation(article="99")])
    cit = evaluate_citations(it, out)
    assert cit.citation_precision == pytest.approx(0.5)
    assert cit.citation_recall == pytest.approx(0.5)
    assert cit.n_citations == 2
    assert cit.n_gold_required_evidence == 2


def test_citation_recall_ignores_optional_gold_evidence() -> None:
    it = item(
        gold_evidence=[
            evidence(article="53", text=E1),
            evidence(article="54", text=E2, required=False),
        ]
    )
    out = output(citations=[citation(article="53")])
    cit = evaluate_citations(it, out)
    assert cit.citation_recall == 1.0
    assert cit.n_gold_required_evidence == 1


def test_duplicate_citations_do_not_inflate_recall_past_one() -> None:
    it = item(gold_evidence=[evidence(article="53", text=E1)])
    out = output(citations=[citation(article="53"), citation(article="53")])
    cit = evaluate_citations(it, out)
    assert cit.citation_recall == 1.0
    assert cit.citation_precision == 1.0


# -- claim-attached citations ----------------------------------------------


def test_a_claim_attached_citation_is_checked_by_entailment() -> None:
    it = item(gold_evidence=[evidence(article="53", text=E1)])
    claim = "Mức phạt tối đa là 50.000.000 đồng."
    out = output(
        contexts=[context(1, E1, article="53")],
        citations=[citation(article="53", claim=claim)],
    )
    judge = ScriptedJudge(verdicts={(E1, claim): JudgeVerdict.SUPPORTED})
    assert evaluate_citations(it, out, judge=judge).citation_precision == 1.0

    rejecting = ScriptedJudge(verdicts={(E1, claim): JudgeVerdict.NOT_SUPPORTED})
    assert evaluate_citations(it, out, judge=rejecting).citation_precision == 0.0


def test_claim_index_resolves_against_the_answer_claims() -> None:
    it = item(gold_evidence=[evidence(article="53", text=E1)])
    claims = ["Mức phạt tiền là 30.000.000 đồng.", "Bị đình chỉ hoạt động."]
    out = output(
        contexts=[context(1, E1, article="53")],
        citations=[citation(article="53", claim_index=1)],
        answer_claims=claims,
    )
    judge = ScriptedJudge(verdicts={(E1, claims[1]): JudgeVerdict.NOT_SUPPORTED})
    cit = evaluate_citations(it, out, judge=judge)
    assert cit.citation_precision == 0.0, "citation 0 was attached to claim 1, which E1 denies"


def test_precision_falls_back_to_location_matching_without_a_judge() -> None:
    it = item(gold_evidence=[evidence(article="53", text=E1)])
    out = output(
        citations=[citation(article="53", claim="whatever")],
        contexts=[context(1, E1, article="53")],
    )
    assert evaluate_citations(it, out, judge=NullJudge()).citation_precision == 1.0


# -- not applicable --------------------------------------------------------


def test_no_citations_is_not_applicable_for_precision_but_zero_for_recall() -> None:
    it = item(gold_evidence=[evidence(article="53", text=E1)])
    cit = evaluate_citations(it, output(citations=[]))
    assert cit.citation_precision is None
    assert cit.citation_recall == 0.0, "gold evidence exists and nothing cited it"
    assert cit.document_accuracy is None
    assert cit.article_accuracy is None


def test_no_gold_evidence_makes_recall_not_applicable() -> None:
    it = item(qid="q9", answerable=False, gold_evidence=[])
    out = output(qid="q9", citations=[citation(article="53")])
    cit = evaluate_citations(it, out)
    assert cit.citation_recall is None
    assert cit.citation_precision is None, "nothing to be precise against"
    assert cit.n_undecided == 1


def test_metrics_serialise_with_their_null_values_intact() -> None:
    it = item(gold_evidence=[evidence(article="53", text=E1)])
    payload = evaluate_citations(it, output(citations=[])).to_dict()
    assert payload["citation_precision"] is None
    assert payload["citation_recall"] == 0.0
    assert isinstance(payload["notes"], list) and payload["notes"]
