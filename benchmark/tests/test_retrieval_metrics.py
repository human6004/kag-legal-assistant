# -*- coding: utf-8 -*-
"""Retrieval metrics, including the two fairness properties that matter most.

MANDATORY CASE 3  - Hit@3 = 1 when a top-3 context supports gold Điều 53.
MANDATORY CASE 4  - the only relevant context sits at rank 4 -> MRR = 0.25.
MANDATORY CASE 5  - one chunk holding E1+E2 and two chunks holding one each
                    must produce the same Evidence Recall. This is the property
                    that lets KAG, HybridRAG and NativeRAG be compared at all.
"""
from __future__ import annotations

import pytest

from benchmark.evaluator.evidence_matching import (
    MatchingPolicy,
    contexts_within_budget,
    default_token_counter,
)
from benchmark.evaluator.judge import NullJudge, RuleBasedJudge
from benchmark.evaluator.retrieval_metrics import evaluate_retrieval

from .helpers import context, evidence, item, output

E1_TEXT = "Phạt tiền từ 30.000.000 đồng đến 50.000.000 đồng đối với hành vi kinh doanh không phép."
E2_TEXT = "Ngoài phạt tiền, tổ chức vi phạm bị đình chỉ hoạt động từ 06 tháng đến 12 tháng."


def two_evidence_item() -> "object":
    return item(
        gold_evidence=[
            evidence(article="53", text=E1_TEXT, evidence_id="E1"),
            evidence(article="54", text=E2_TEXT, evidence_id="E2"),
        ]
    )


# -- MANDATORY CASE 3: Hit@3 ------------------------------------------------


def test_hit_at_3_is_one_when_a_top_3_context_supports_dieu_53() -> None:
    it = item(gold_evidence=[evidence(article="53", text=E1_TEXT)])
    out = output(
        contexts=[
            context(1, "Nội dung không liên quan về thủ tục đăng ký.", article="10"),
            context(2, "Nội dung không liên quan về hồ sơ.", article="11"),
            context(3, E1_TEXT, article="53"),
            context(4, "Nội dung khác.", article="70"),
        ]
    )
    m = evaluate_retrieval(it, out)
    assert m.hit_at_k[1] == 0.0
    assert m.hit_at_k[3] == 1.0
    assert m.hit_at_k[5] == 1.0
    assert m.evidence_recall == 1.0
    assert m.first_relevant_rank == 3


def test_hit_at_k_is_zero_when_nothing_relevant_is_retrieved() -> None:
    it = item(gold_evidence=[evidence(article="53", text=E1_TEXT)])
    out = output(contexts=[context(1, "Chuyện khác hoàn toàn.", article="10")])
    m = evaluate_retrieval(it, out)
    assert m.hit_at_k[1] == 0.0
    assert m.hit_at_k[3] == 0.0
    assert m.mrr == 0.0
    assert m.first_relevant_rank is None


# -- MANDATORY CASE 4: MRR = 0.25 ------------------------------------------


def test_mrr_is_one_quarter_when_the_only_relevant_context_is_at_rank_4() -> None:
    it = item(gold_evidence=[evidence(article="53", text=E1_TEXT)])
    out = output(
        contexts=[
            context(1, "Không liên quan.", article="10"),
            context(2, "Không liên quan.", article="11"),
            context(3, "Không liên quan.", article="12"),
            context(4, E1_TEXT, article="53"),
        ]
    )
    m = evaluate_retrieval(it, out)
    assert m.first_relevant_rank == 4
    assert m.mrr == pytest.approx(0.25)
    assert m.hit_at_k[3] == 0.0
    assert m.hit_at_k[5] == 1.0


@pytest.mark.parametrize("rank, expected", [(1, 1.0), (2, 0.5), (4, 0.25), (5, 0.2)])
def test_mrr_is_the_reciprocal_of_the_first_relevant_rank(rank: int, expected: float) -> None:
    it = item(gold_evidence=[evidence(article="53", text=E1_TEXT)])
    contexts = [
        context(r, "Không liên quan.", article=str(20 + r)) for r in range(1, rank)
    ] + [context(rank, E1_TEXT, article="53")]
    m = evaluate_retrieval(it, output(contexts=contexts))
    assert m.mrr == pytest.approx(expected)


# -- MANDATORY CASE 5: chunking-invariant Evidence Recall -------------------


def test_evidence_recall_is_the_same_for_one_big_chunk_and_two_small_ones() -> None:
    it = two_evidence_item()

    one_chunk = output(
        qid=it.id,
        system="system_a",
        contexts=[context(1, E1_TEXT + " " + E2_TEXT)],
    )
    two_chunks = output(
        qid=it.id,
        system="system_b",
        contexts=[context(1, E1_TEXT), context(2, E2_TEXT)],
    )

    a = evaluate_retrieval(it, one_chunk)
    b = evaluate_retrieval(it, two_chunks)
    assert a.evidence_recall == 1.0
    assert b.evidence_recall == 1.0
    assert a.evidence_recall == b.evidence_recall


def test_partial_coverage_scores_the_same_fraction_either_way() -> None:
    it = two_evidence_item()
    big = output(contexts=[context(1, "Mở đầu. " + E1_TEXT + " Kết thúc.")])
    small = output(contexts=[context(1, E1_TEXT), context(2, "Nội dung khác.")])
    assert evaluate_retrieval(it, big).evidence_recall == pytest.approx(0.5)
    assert evaluate_retrieval(it, small).evidence_recall == pytest.approx(0.5)


def test_context_without_article_still_recalls_via_text() -> None:
    """A system that reports no article must not lose to one that does.

    HybridRAG's adapter can often name only the document, KAG can name the
    clause. Both retrieved the same passage, so both must score it: gold text
    is the route every system can reach, which is why it is mandatory.
    """
    it = item(gold_evidence=[evidence(article="53", clause="3", text=E1_TEXT)])
    kag_like = output(system="kag", contexts=[context(1, E1_TEXT, article="53", clause="3")])
    hybrid_like = output(system="hybridrag", contexts=[context(1, E1_TEXT)])

    assert evaluate_retrieval(it, kag_like).evidence_recall == 1.0
    assert evaluate_retrieval(it, hybrid_like).evidence_recall == 1.0


def test_metadata_only_matching_also_survives_different_chunking() -> None:
    """A system that reports locations but no text is scored structurally."""
    it = two_evidence_item()
    merged = output(contexts=[context(1, None, article="53"), context(2, None, article="54")])
    m = evaluate_retrieval(it, merged)
    assert m.evidence_recall == 1.0


# -- evidence recall at a fixed list length ---------------------------------


def test_recall_at_k_truncates_by_rank() -> None:
    """The headline retrieval metric asks all systems for the same list length."""
    it = item(gold_evidence=[evidence(article="53", text=E1_TEXT)])
    contexts = [
        context(r, "Không liên quan.", article=str(20 + r)) for r in range(1, 7)
    ] + [context(7, E1_TEXT, article="53")]
    m = evaluate_retrieval(it, output(contexts=contexts), k_values=(5, 10))
    assert m.topk_evidence_recall[5] == 0.0
    assert m.topk_evidence_recall[10] == 1.0
    assert m.evidence_recall == 1.0, "the full-list number is unchanged"


def test_recall_at_k_counts_partial_coverage_like_full_recall() -> None:
    it = two_evidence_item()
    out = output(contexts=[context(1, E1_TEXT), context(2, "Nội dung khác."), context(3, E2_TEXT)])
    m = evaluate_retrieval(it, out, k_values=(2, 5))
    assert m.topk_evidence_recall[2] == pytest.approx(0.5)
    assert m.topk_evidence_recall[5] == 1.0


def test_recall_at_k_is_not_applicable_without_gold_evidence() -> None:
    it = item(qid="q9", answerable=False, gold_evidence=[])
    m = evaluate_retrieval(it, output(qid="q9", contexts=[context(1, "Bất kỳ.")]))
    assert all(v is None for v in m.topk_evidence_recall.values())


def test_recall_at_k_is_zero_not_none_when_a_healthy_system_returns_nothing() -> None:
    it = item(gold_evidence=[evidence(article="53", text=E1_TEXT)])
    assert evaluate_retrieval(it, output(contexts=[])).topk_evidence_recall[5] == 0.0
    errored = evaluate_retrieval(it, output(error="timeout", contexts=[]))
    assert errored.topk_evidence_recall[5] is None, "an errored run is unavailable, not 0"


# -- context precision ------------------------------------------------------


def test_context_precision_counts_relevant_contexts_over_all_contexts() -> None:
    it = item(gold_evidence=[evidence(article="53", text=E1_TEXT)])
    out = output(
        contexts=[
            context(1, E1_TEXT, article="53"),
            context(2, "Nội dung không liên quan.", article="10"),
            context(3, "Nội dung không liên quan.", article="11"),
            context(4, "Nội dung không liên quan.", article="12"),
        ]
    )
    m = evaluate_retrieval(it, out)
    assert m.context_precision == pytest.approx(0.25)
    assert m.n_contexts == 4


def test_context_precision_is_none_without_contexts() -> None:
    it = item(gold_evidence=[evidence(article="53", text=E1_TEXT)])
    m = evaluate_retrieval(it, output(contexts=[]))
    assert m.context_precision is None
    assert m.evidence_recall == 0.0, "no contexts and no error is an honest zero"


# -- hard negatives ---------------------------------------------------------


def test_a_declared_article_mismatch_is_not_support() -> None:
    """Điều 52 text cannot stand in for Điều 53 evidence, even with a judge."""
    it = item(gold_evidence=[evidence(article="53", text=E1_TEXT)])
    out = output(contexts=[context(1, E1_TEXT, article="52")])
    m = evaluate_retrieval(it, out, judge=RuleBasedJudge())
    assert m.evidence_recall == 0.0
    assert m.hit_at_k[1] == 0.0
    assert m.supports[0].decision.method.value == "location_mismatch"


def test_a_different_document_is_not_support() -> None:
    it = item(gold_evidence=[evidence(article="53", text=E1_TEXT)])
    out = output(contexts=[context(1, E1_TEXT, article="53", document_id="331/2026/NĐ-CP")])
    assert evaluate_retrieval(it, out).evidence_recall == 0.0


# -- null / not-applicable handling ----------------------------------------


def test_unanswerable_item_has_no_retrieval_recall() -> None:
    it = item(qid="q9", answerable=False, gold_evidence=[])
    out = output(qid="q9", contexts=[context(1, "Bất kỳ nội dung nào.")])
    m = evaluate_retrieval(it, out)
    assert m.evidence_recall is None
    assert m.evidence_recall_required is None
    assert m.mrr is None
    assert all(v is None for v in m.hit_at_k.values())
    assert m.n_gold_evidence == 0


def test_error_makes_metrics_unavailable_not_zero() -> None:
    it = item(gold_evidence=[evidence(article="53", text=E1_TEXT)])
    out = output(error="LLM timeout", contexts=[])
    m = evaluate_retrieval(it, out)
    assert m.evidence_recall is None, "an errored run did not 'fail to retrieve'"
    assert m.mrr is None
    assert all(v is None for v in m.hit_at_k.values())


def test_undecided_stays_out_of_the_numerator_with_a_null_judge() -> None:
    """Gold declares a point; the context declares only the article, no text.

    Gold always carries text, but a context that carries none leaves the text
    route nothing to arbitrate with, so nothing decides.
    """
    it = item(gold_evidence=[evidence(article="53", clause="3", point="b", text=E1_TEXT)])
    out = output(contexts=[context(1, None, article="53")])
    m = evaluate_retrieval(it, out, judge=NullJudge())
    assert m.evidence_recall == 0.0
    assert m.n_undecided >= 1
    assert m.supports[0].supported is None


def test_coarse_metadata_can_be_opted_into() -> None:
    it = item(gold_evidence=[evidence(article="53", clause="3", point="b", text=E1_TEXT)])
    out = output(contexts=[context(1, None, article="53")])
    lenient = MatchingPolicy(coarse_metadata_counts=True)
    assert evaluate_retrieval(it, out, policy=lenient).evidence_recall == 1.0


# -- required vs optional evidence ----------------------------------------


def test_required_recall_ignores_optional_evidence() -> None:
    it = item(
        gold_evidence=[
            evidence(article="53", text=E1_TEXT, evidence_id="E1"),
            evidence(article="54", text=E2_TEXT, evidence_id="E2", required=False),
        ]
    )
    out = output(contexts=[context(1, E1_TEXT, article="53")])
    m = evaluate_retrieval(it, out)
    assert m.evidence_recall == pytest.approx(0.5)
    assert m.evidence_recall_required == 1.0


# -- equal context-token budget -------------------------------------------


def test_budgeted_recall_penalises_a_system_that_needs_more_context() -> None:
    it = two_evidence_item()
    padding = "Văn bản đệm không liên quan. " * 40
    verbose = output(
        contexts=[
            context(1, padding, token_count=400),
            context(2, E1_TEXT, token_count=30),
            context(3, E2_TEXT, token_count=30),
        ]
    )
    compact = output(
        contexts=[
            context(1, E1_TEXT, token_count=30),
            context(2, E2_TEXT, token_count=30),
        ]
    )
    m_verbose = evaluate_retrieval(it, verbose, budgets=(100,))
    m_compact = evaluate_retrieval(it, compact, budgets=(100,))
    assert m_verbose.evidence_recall == 1.0, "unbudgeted, both systems find everything"
    assert m_compact.evidence_recall == 1.0
    assert m_verbose.budget_evidence_recall[100] == 1.0, "the 400-token chunk is skipped"
    assert m_compact.budget_evidence_recall[100] == 1.0


def test_budget_is_configurable_and_not_hard_coded() -> None:
    it = two_evidence_item()
    out = output(
        contexts=[context(1, E1_TEXT, token_count=30), context(2, E2_TEXT, token_count=30)]
    )
    m = evaluate_retrieval(it, out, budgets=(20, 40, 100))
    assert sorted(m.budget_evidence_recall) == [20, 40, 100]
    assert m.budget_evidence_recall[20] == 0.0, "no context fits a 20-token budget"
    assert m.budget_evidence_recall[40] == pytest.approx(0.5)
    assert m.budget_evidence_recall[100] == 1.0


def test_no_budget_is_applied_by_default() -> None:
    it = two_evidence_item()
    out = output(contexts=[context(1, E1_TEXT)])
    assert evaluate_retrieval(it, out).budget_evidence_recall == {}


def test_contexts_within_budget_keeps_rank_order_and_skips_oversized() -> None:
    contexts = output(
        contexts=[
            context(1, "a", token_count=10),
            context(2, "b", token_count=500),
            context(3, "c", token_count=10),
        ]
    ).retrieved_contexts
    kept = contexts_within_budget(contexts, 100)
    assert [c.rank for c in kept] == [1, 3]
    assert contexts_within_budget(contexts, 0) == []


def test_default_token_counter_is_tokenizer_free_and_monotonic() -> None:
    assert default_token_counter("") == 0
    assert default_token_counter(None) == 0
    short = default_token_counter("Phạt tiền 30 triệu đồng.")
    long = default_token_counter("Phạt tiền 30 triệu đồng. " * 10)
    assert 0 < short < long


def test_injected_token_counter_is_used() -> None:
    it = two_evidence_item()
    out = output(contexts=[context(1, E1_TEXT), context(2, E2_TEXT)])
    m = evaluate_retrieval(
        it, out, budgets=(3,), token_counter=lambda text: 1 if text else 0
    )
    assert m.budget_evidence_recall[3] == 1.0
