# -*- coding: utf-8 -*-
"""Retrieval-side metrics: how well a system's retrieved contexts cover gold evidence.

All metrics are architecture-neutral: they compare against `item.gold_evidence`
(document/article/clause/point/text), never against a system-internal chunk id.
Every metric that has no well-defined value for a given item reports `None`
("not applicable" / "unavailable") rather than a fabricated `0.0`; see each
docstring below for the exact rule and read `n_gold_evidence`, `n_undecided`
and `notes` on the result before trusting a number.

Metrics (formula, direction):

  * `evidence_recall` (↑)          - # gold evidence supported by *some*
    retrieved context / # gold evidence. Undecided evidence is excluded from
    the numerator but does not shrink the denominator.
  * `evidence_recall_required` (↑) - same, restricted to `item.required_evidence`.
  * `context_precision` (↑)        - # retrieved contexts that support at least
    one gold evidence or gold claim / # retrieved contexts.
  * `hit_at_k[k]` (↑)              - 1.0 iff some context ranked <= k supports
    any required gold evidence (all gold evidence when none is required), else
    0.0. `None` when there is no gold evidence or the system errored.
  * `mrr` (↑)                      - 1 / rank of the first context that
    supports required gold evidence; 0.0 when nothing relevant was found (but
    the search was decided); `None` when there is no gold evidence or the
    system errored.
  * `first_relevant_rank`          - the raw rank behind `mrr`, or `None`.
  * `topk_evidence_recall[k]` (↑)  - `evidence_recall` recomputed over the top
    `k` contexts only. This is the headline retrieval number: full-list recall
    rewards a system for returning more, and `hit@k` collapses several pieces
    of evidence into one bit, whereas recall at a fixed cut-off asks all three
    systems the same question at the same list length.
  * `budget_evidence_recall[b]` (↑) - `evidence_recall` recomputed after
    truncating contexts to a `b`-token budget (`contexts_within_budget`), so
    systems that pack more/less per chunk are compared on equal context size.

Everything here is deterministic except for judge-backed support decisions,
which are delegated to `evidence_matching.support_map` /
`context_supports_any` and reused where cheap.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from .evidence_matching import (
    DEFAULT_POLICY,
    EvidenceSupport,
    MatchingPolicy,
    context_supports_any,
    contexts_within_budget,
    default_token_counter,
    support_map,
)
from .judge import Judge, JudgeUsage
from .models import BenchmarkItem, EvidenceRef, RetrievedContext, SystemOutput

DEFAULT_K_VALUES = (1, 3, 5, 10)


@dataclass(frozen=True)
class RetrievalMetrics:
    """Result bundle for one (item, output) pair. See module docstring for formulas."""

    evidence_recall: Optional[float]
    evidence_recall_required: Optional[float]
    context_precision: Optional[float]
    hit_at_k: Dict[int, Optional[float]]
    mrr: Optional[float]
    first_relevant_rank: Optional[int]
    topk_evidence_recall: Dict[int, Optional[float]]
    budget_evidence_recall: Dict[int, Optional[float]]
    n_gold_evidence: int
    n_required_evidence: int
    n_supported: int
    n_undecided: int
    n_contexts: int
    supports: List[EvidenceSupport]
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_recall": self.evidence_recall,
            "evidence_recall_required": self.evidence_recall_required,
            "context_precision": self.context_precision,
            "hit_at_k": {int(k): v for k, v in self.hit_at_k.items()},
            "mrr": self.mrr,
            "first_relevant_rank": self.first_relevant_rank,
            "topk_evidence_recall": {int(k): v for k, v in self.topk_evidence_recall.items()},
            "budget_evidence_recall": {int(b): v for b, v in self.budget_evidence_recall.items()},
            "n_gold_evidence": self.n_gold_evidence,
            "n_required_evidence": self.n_required_evidence,
            "n_supported": self.n_supported,
            "n_undecided": self.n_undecided,
            "n_contexts": self.n_contexts,
            "supports": [s.to_dict() for s in self.supports],
            "notes": list(self.notes),
        }


def _recall_over(
    evidence_list: Sequence[EvidenceRef],
    contexts: Sequence[RetrievedContext],
    judge: Optional[Judge],
    policy: MatchingPolicy,
    usage: Optional[JudgeUsage],
    output: SystemOutput,
    notes: List[str],
    *,
    label: str,
) -> Optional[float]:
    """Shared evidence-recall computation, reused for required/budgeted variants."""
    n_gold = len(evidence_list)
    if n_gold == 0:
        # Denominator would be 0 - "recall over nothing" is not applicable.
        return None
    if not contexts:
        if output.error is not None:
            notes.append(f"{label}: system errored and returned no contexts -> unavailable")
            return None
        # An empty context list with no error is a real, honest zero.
        notes.append(f"{label}: no retrieved contexts (no error) -> recall is 0.0")
        return 0.0
    supports = support_map(contexts, evidence_list, judge, policy, usage)
    n_supported_true = sum(1 for s in supports if s.supported is True)
    return n_supported_true / n_gold


def _hit_at_k_and_mrr(
    output: SystemOutput,
    required_or_all: Sequence[EvidenceRef],
    judge: Optional[Judge],
    policy: MatchingPolicy,
    usage: Optional[JudgeUsage],
    k_values: Sequence[int],
    notes: List[str],
) -> tuple:
    """Compute hit@k for each k, plus mrr / first_relevant_rank.

    Both derive from the same notion of "first rank at which any relevant
    context appears", computed via `output.top_k(k)` so ranking/truncation is
    never re-derived by hand here.
    """
    hit_at_k: Dict[int, Optional[float]] = {}
    if not required_or_all:
        for k in k_values:
            hit_at_k[k] = None
        notes.append("hit@k: no gold evidence to target -> unavailable")
        return hit_at_k, None, None

    if output.error is not None:
        for k in k_values:
            hit_at_k[k] = None
        notes.append("hit@k/mrr: system errored -> unavailable")
        return hit_at_k, None, None

    for k in k_values:
        truncated = output.top_k(k)
        if not truncated:
            hit_at_k[k] = 0.0
            continue
        hit = False
        for context in truncated:
            decision = context_supports_any(context, required_or_all, judge, policy, usage)
            if decision.supported is True:
                hit = True
                break
        hit_at_k[k] = 1.0 if hit else 0.0

    # first_relevant_rank / mrr walk the full ranked list once, independent of
    # k_values, so a caller passing an empty k_values sequence still gets mrr.
    first_relevant_rank: Optional[int] = None
    for context in output.top_k(None):
        decision = context_supports_any(context, required_or_all, judge, policy, usage)
        if decision.supported is True:
            first_relevant_rank = context.rank
            break

    mrr = 1.0 / first_relevant_rank if first_relevant_rank else 0.0
    return hit_at_k, mrr, first_relevant_rank


def evaluate_retrieval(
    item: BenchmarkItem,
    output: SystemOutput,
    judge: Optional[Judge] = None,
    policy: MatchingPolicy = DEFAULT_POLICY,
    k_values: Sequence[int] = DEFAULT_K_VALUES,
    budgets: Sequence[int] = (),
    token_counter: Callable[[Optional[str]], int] = default_token_counter,
    usage: Optional[JudgeUsage] = None,
) -> RetrievalMetrics:
    """Compute every retrieval metric for one benchmark item / system output pair.

    See the module docstring for the formula and ↑/↓ direction of each field.
    """
    notes: List[str] = []
    gold_evidence = item.gold_evidence
    n_gold = len(gold_evidence)
    contexts = output.top_k(None)
    n_contexts = len(contexts)

    if n_gold == 0:
        notes.append("no gold evidence: retrieval metrics not applicable")
        empty_hit_at_k: Dict[int, Optional[float]] = {k: None for k in k_values}
        empty_budget: Dict[int, Optional[float]] = {b: None for b in budgets}
        return RetrievalMetrics(
            evidence_recall=None,
            evidence_recall_required=None,
            context_precision=None,
            hit_at_k=empty_hit_at_k,
            mrr=None,
            first_relevant_rank=None,
            topk_evidence_recall={k: None for k in k_values},
            budget_evidence_recall=empty_budget,
            n_gold_evidence=0,
            n_required_evidence=0,
            n_supported=0,
            n_undecided=0,
            n_contexts=n_contexts,
            supports=[],
            notes=notes,
        )

    required_evidence = item.required_evidence

    # -- evidence recall (all gold, and required-only) ---------------------
    supports = support_map(contexts, gold_evidence, judge, policy, usage) if contexts else []
    if not contexts:
        evidence_recall = _recall_over(
            gold_evidence, contexts, judge, policy, usage, output, notes, label="evidence_recall"
        )
    else:
        n_supported_true = sum(1 for s in supports if s.supported is True)
        evidence_recall = n_supported_true / n_gold

    n_supported = sum(1 for s in supports if s.supported is True)
    n_undecided = sum(1 for s in supports if s.supported is None)

    if not required_evidence:
        evidence_recall_required = None
        notes.append("no required evidence: evidence_recall_required not applicable")
    else:
        evidence_recall_required = _recall_over(
            required_evidence,
            contexts,
            judge,
            policy,
            usage,
            output,
            notes,
            label="evidence_recall_required",
        )

    # -- context precision --------------------------------------------------
    if not contexts:
        context_precision = None
        notes.append("no retrieved contexts: context_precision not applicable")
    else:
        n_precise = 0
        n_precision_undecided = 0
        for context in contexts:
            decision = context_supports_any(
                context, gold_evidence, judge, policy, usage, gold_claims=item.gold_claims
            )
            if decision.supported is True:
                n_precise += 1
            elif decision.supported is None:
                n_precision_undecided += 1
        context_precision = n_precise / n_contexts
        n_undecided += n_precision_undecided

    # -- hit@k / mrr (required evidence, falling back to all gold) ---------
    target_evidence = required_evidence if required_evidence else gold_evidence
    hit_at_k, mrr, first_relevant_rank = _hit_at_k_and_mrr(
        output, target_evidence, judge, policy, usage, k_values, notes
    )

    # -- evidence recall at a fixed list length ------------------------------
    # Recomputed per k rather than derived from `supports`, because a support
    # decision carries the rank of the *best* context that supported it and a
    # cheaper rank filter would quietly assume that rank is the only one.
    topk_evidence_recall: Dict[int, Optional[float]] = {}
    for k in k_values:
        topk_evidence_recall[k] = _recall_over(
            gold_evidence,
            output.top_k(k),
            judge,
            policy,
            usage,
            output,
            notes,
            label=f"evidence_recall@{k}",
        )

    # -- budgeted evidence recall --------------------------------------------
    budget_evidence_recall: Dict[int, Optional[float]] = {}
    for budget in budgets:
        budgeted_contexts = contexts_within_budget(contexts, budget, token_counter)
        budget_evidence_recall[budget] = _recall_over(
            gold_evidence,
            budgeted_contexts,
            judge,
            policy,
            usage,
            output,
            notes,
            label=f"budget_evidence_recall[{budget}]",
        )

    return RetrievalMetrics(
        evidence_recall=evidence_recall,
        evidence_recall_required=evidence_recall_required,
        context_precision=context_precision,
        hit_at_k=hit_at_k,
        mrr=mrr,
        first_relevant_rank=first_relevant_rank,
        topk_evidence_recall=topk_evidence_recall,
        budget_evidence_recall=budget_evidence_recall,
        n_gold_evidence=n_gold,
        n_required_evidence=len(required_evidence),
        n_supported=n_supported,
        n_undecided=n_undecided,
        n_contexts=n_contexts,
        supports=supports,
        notes=notes,
    )
