# -*- coding: utf-8 -*-
"""The scoring depth of the comparison, pinned from both sides.

KAG, HybridRAG and NativeRAG report legal metadata at different depths: KAG can
label a chunk down to the clause, HybridRAG often knows only the document. The
comparison is therefore scored at the article, and these tests pin what that
means in both directions:

  * a wrong article is a hard negative nothing can rescue (right content, wrong
    address);
  * a wrong - or absent - clause costs nothing, so declaring more metadata can
    never score worse than declaring less.
"""
from __future__ import annotations

import pytest

from benchmark.evaluator.evidence_matching import (
    HARD_NEGATIVE_LEVELS,
    DEFAULT_POLICY,
    MatchingPolicy,
    SupportMethod,
    context_supports_evidence,
    structural_decision,
)
from benchmark.evaluator.judge import JudgeVerdict, ScriptedJudge
from benchmark.evaluator.models import EvidenceRef, RetrievedContext
from benchmark.evaluator.retrieval_metrics import evaluate_retrieval

from .helpers import context, evidence, item, output

E1 = "Phạt tiền từ 30.000.000 đồng đến 50.000.000 đồng đối với hành vi kinh doanh không phép."


def always_supports() -> ScriptedJudge:
    """A judge that would rescue anything, used to prove what it cannot rescue."""
    return ScriptedJudge(default=JudgeVerdict.SUPPORTED)


def gold(**kwargs) -> EvidenceRef:
    return EvidenceRef.from_dict(evidence(**kwargs))


def ctx(**kwargs) -> RetrievedContext:
    return RetrievedContext.from_dict(context(**kwargs), 1, "test context")


# -- the scoring depth itself ----------------------------------------------


def test_the_default_scoring_depth_is_document_and_article() -> None:
    assert DEFAULT_POLICY.hard_negative_levels == ("document", "article")
    assert HARD_NEGATIVE_LEVELS == ("document", "article")


def test_structural_decision_reports_soft_mismatches_instead_of_deciding() -> None:
    verdict, missing, mismatch, soft = structural_decision(
        {"document": "d", "article": "53", "clause": "2", "point": None},
        {"document": "d", "article": "53", "clause": "3", "point": None},
    )
    assert verdict is None, "a clause mismatch must not decide anything"
    assert mismatch is None
    assert soft == ["clause"]
    assert missing == []


# -- clause / point are diagnostic ------------------------------------------


def test_clause_mismatch_falls_through_to_text() -> None:
    """KAG labelling a multi-clause chunk by its first clause must still score."""
    decision = context_supports_evidence(
        ctx(rank=1, text=E1, article="53", clause="2"),
        gold(article="53", clause="3", text=E1),
    )
    assert decision.supported is True
    assert decision.method is not SupportMethod.LOCATION_MISMATCH
    assert decision.soft_mismatch == ("clause",), "still visible for error analysis"


def test_point_mismatch_falls_through_to_text() -> None:
    decision = context_supports_evidence(
        ctx(rank=1, text=E1, article="53", clause="3", point="a"),
        gold(article="53", clause="3", point="b", text=E1),
    )
    assert decision.supported is True
    assert decision.soft_mismatch == ("point",)


def test_clause_metadata_does_not_change_the_score() -> None:
    """Three depths of metadata for one and the same passage, one score."""
    it = item(gold_evidence=[evidence(article="53", clause="3", text=E1)])
    exact = output(contexts=[context(1, E1, article="53", clause="3")])
    wrong_clause = output(contexts=[context(1, E1, article="53", clause="2")])
    no_clause = output(contexts=[context(1, E1, article="53")])

    recalls = [
        evaluate_retrieval(it, out).evidence_recall
        for out in (exact, wrong_clause, no_clause)
    ]
    assert recalls == [1.0, 1.0, 1.0]


def test_a_soft_mismatch_never_turns_into_a_location_mismatch() -> None:
    """Without text to arbitrate, a clause mismatch is undecided, not false."""
    decision = context_supports_evidence(
        ctx(rank=1, article="53", clause="2"),
        gold(article="53", clause="3", text=E1),
    )
    assert decision.supported is None
    assert decision.method is SupportMethod.UNDECIDED
    assert decision.soft_mismatch == ("clause",)


def test_a_soft_mismatch_is_not_rescued_by_coarse_metadata() -> None:
    """The lenient opt-in accepts silence about a clause, not a wrong clause."""
    lenient = MatchingPolicy(coarse_metadata_counts=True)
    silent = context_supports_evidence(
        ctx(rank=1, article="53"), gold(article="53", clause="3", text=E1), policy=lenient
    )
    wrong = context_supports_evidence(
        ctx(rank=1, article="53", clause="2"),
        gold(article="53", clause="3", text=E1),
        policy=lenient,
    )
    assert silent.supported is True
    assert wrong.supported is None


def test_the_soft_mismatch_survives_into_the_per_question_detail() -> None:
    it = item(gold_evidence=[evidence(article="53", clause="3", text=E1)])
    out = output(contexts=[context(1, E1, article="53", clause="2")])
    payload = evaluate_retrieval(it, out).to_dict()
    assert payload["supports"][0]["soft_mismatch"] == ["clause"]


# -- document / article stay hard --------------------------------------------


def test_article_mismatch_is_still_a_hard_negative() -> None:
    """Right content at the wrong address is wrong, judge or no judge."""
    for judge in (None, always_supports()):
        decision = context_supports_evidence(
            ctx(rank=1, text=E1, article="52"),
            gold(article="53", text=E1),
            judge=judge,
        )
        assert decision.supported is False
        assert decision.method is SupportMethod.LOCATION_MISMATCH


def test_document_mismatch_is_still_a_hard_negative() -> None:
    decision = context_supports_evidence(
        ctx(rank=1, text=E1, article="53", document_id="331/2026/NĐ-CP"),
        gold(article="53", text=E1),
        judge=always_supports(),
    )
    assert decision.supported is False
    assert decision.method is SupportMethod.LOCATION_MISMATCH


def test_an_article_mismatch_beats_a_clause_mismatch_to_the_verdict() -> None:
    """Both levels differ: the hard one decides, and it decides False."""
    verdict, _, mismatch, _ = structural_decision(
        {"document": "d", "article": "52", "clause": "2", "point": None},
        {"document": "d", "article": "53", "clause": "3", "point": None},
    )
    assert verdict is False
    assert mismatch == "article"


# -- the property the whole comparison rests on ------------------------------


def test_richer_metadata_never_scores_worse_than_poorer_metadata() -> None:
    it = item(gold_evidence=[evidence(article="53", clause="3", text=E1)])
    kag_like = output(contexts=[context(1, E1, article="53", clause="2")])
    hybrid_like = output(contexts=[context(1, E1)])
    assert evaluate_retrieval(it, kag_like).evidence_recall == pytest.approx(
        evaluate_retrieval(it, hybrid_like).evidence_recall
    )
