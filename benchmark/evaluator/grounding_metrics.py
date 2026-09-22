# -*- coding: utf-8 -*-
"""Answer-grounding metrics: does the answer's own content hold up?

This module deliberately keeps two questions apart that are easy to conflate:

  * **Faithfulness** (↑) - # claims `SUPPORTED_BY_CONTEXT` / `n_claims`. This is
    the answer measured against *this system's own retrieved context*, never
    against the whole gold corpus. A system that invents a fact its retriever
    never surfaced is unfaithful even if the fact happens to be true.
  * **Hallucination Rate** (↓) - # claims `UNSUPPORTED` or `CONTRADICTED` /
    `n_claims`. A claim absent from context but *true against gold* is not a
    hallucination; it is a retrieval gap (see below). `UNDECIDED` claims are
    excluded from the numerator and reported separately in `n_undecided`.

**`hallucination_rate != 1 - faithfulness`.** The two metrics are computed
from disjoint claim buckets on purpose:

  * `faithfulness`'s numerator is `SUPPORTED_BY_CONTEXT`.
  * `hallucination_rate`'s numerator is `UNSUPPORTED` + `CONTRADICTED`.
  * `SUPPORTED_BY_GOLD_NOT_CONTEXT` (the retrieval gap) and `UNDECIDED` count
    against neither numerator. A claim can lower faithfulness (it is not in
    context) without raising hallucination (it is true against gold) - that
    is exactly the retrieval-gap case this module exists to keep visible.

Other metrics:

  * `retrieval_gap_rate` (↓, diagnostic) - # `SUPPORTED_BY_GOLD_NOT_CONTEXT` /
    `n_claims`. High values mean the generator is fine but the retriever is
    starving it of material that does exist in the gold corpus.
  * `unsupported_claim_rate` (↓) - same numerator as `hallucination_rate`, but
    the denominator is restricted to claims that had *any* gold material to
    be checked against (`item.gold_evidence` or `item.gold_claims`
    non-empty). When both are empty there is nothing to be unsupported
    against, so the metric is `None`, not a fabricated value.

Claim classification (`classify_claim`) asks two independent support
questions and combines them:

  * context side: `evidence_matching.text_supported_by_contexts` against
    `output.retrieved_contexts` - "did *this system* surface material for
    this claim?"
  * gold side: `evidence_matching.text_supported_by_evidence` against
    `item.gold_evidence` (+ `item.gold_claims`) - "is this claim actually true
    per the authoritative corpus?"

|                  | gold True                        | gold False | gold None  |
|------------------|-----------------------------------|------------|------------|
| context True     | SUPPORTED_BY_CONTEXT               | SUPPORTED_BY_CONTEXT | SUPPORTED_BY_CONTEXT |
| context not True | SUPPORTED_BY_GOLD_NOT_CONTEXT      | UNSUPPORTED (or CONTRADICTED, see below) | UNDECIDED |

Context `True` always wins the row: if the system's own context supports the
claim, that is what faithfulness measures, regardless of what the gold side
says. `CONTRADICTED` is used instead of `UNSUPPORTED` only when the gold-side
`SupportDecision` was produced by the judge route (`SupportMethod.JUDGE`) and
the judge's own verdict was `JudgeVerdict.CONTRADICTED` - `text_supported_by_evidence`
only returns a bare `SupportDecision`, so this module re-asks the judge
directly against `item.gold_evidence` / `item.gold_claims` to recover that
verdict. When no judge is available (or none of them contradicts), plain
non-support is reported as `UNSUPPORTED` and a note records that
contradiction could not be distinguished from absence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence

from .evidence_matching import (
    DEFAULT_POLICY,
    MatchingPolicy,
    SupportMethod,
    text_supported_by_contexts,
    text_supported_by_evidence,
)
from .judge import Judge, JudgeResult, JudgeUsage, JudgeVerdict
from .models import BenchmarkItem, SystemOutput


class ClaimStatus(str, Enum):
    """Where one answer claim landed, context side and gold side combined."""

    SUPPORTED_BY_CONTEXT = "supported_by_context"
    #: Retrieval gap: true against gold, but this system's own context never
    #: surfaced it. Lowers faithfulness; never counted as a hallucination.
    SUPPORTED_BY_GOLD_NOT_CONTEXT = "supported_by_gold_not_context"
    #: Gold side actively said no (or nothing decided it, absent a judge that
    #: could tell contradiction apart from plain non-support).
    UNSUPPORTED = "unsupported"
    #: Gold side said the opposite (judge verdict CONTRADICTED specifically).
    CONTRADICTED = "contradicted"
    #: Neither side could decide.
    UNDECIDED = "undecided"


@dataclass(frozen=True)
class ClaimGrounding:
    """One claim's classification, with enough detail to audit it by hand."""

    claim: str
    status: ClaimStatus
    context_supported: Optional[bool]
    gold_supported: Optional[bool]
    context_detail: str = ""
    gold_detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim": self.claim,
            "status": self.status.value,
            "context_supported": self.context_supported,
            "gold_supported": self.gold_supported,
            "context_detail": self.context_detail,
            "gold_detail": self.gold_detail,
        }


@dataclass(frozen=True)
class GroundingMetrics:
    """Result bundle for one (item, output) pair. See module docstring for formulas."""

    faithfulness: Optional[float]
    hallucination_rate: Optional[float]
    retrieval_gap_rate: Optional[float]
    unsupported_claim_rate: Optional[float]
    n_claims: Optional[int]
    n_undecided: int
    claims: List[ClaimGrounding] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "faithfulness": self.faithfulness,
            "hallucination_rate": self.hallucination_rate,
            "retrieval_gap_rate": self.retrieval_gap_rate,
            "unsupported_claim_rate": self.unsupported_claim_rate,
            "n_claims": self.n_claims,
            "n_undecided": self.n_undecided,
            "claims": [c.to_dict() for c in self.claims],
            "notes": list(self.notes),
        }


def _gold_side_contradicted(
    item: BenchmarkItem,
    claim: str,
    judge: Optional[Judge],
    usage: Optional[JudgeUsage],
) -> bool:
    """Best-effort recovery of a CONTRADICTED verdict on the gold side.

    `text_supported_by_evidence` collapses the judge's verdict into a bare
    `SupportDecision` (True/False/None), so NOT_SUPPORTED and CONTRADICTED are
    indistinguishable from its return value alone. To tell them apart for
    `ClaimStatus`, re-ask the same judge directly against each piece of gold
    material and check for an explicit `JudgeVerdict.CONTRADICTED`. This is a
    best effort: it stops at the first contradiction found, and reports
    nothing when no judge is configured.
    """
    if judge is None:
        return False
    for evidence in item.gold_evidence:
        if not evidence.text:
            continue
        result: JudgeResult = judge.entails(evidence.text, claim)
        if usage is not None:
            usage.record(result)
        if result.verdict is JudgeVerdict.CONTRADICTED:
            return True
    for gold_claim in item.gold_claims:
        result = judge.entails(gold_claim, claim)
        if usage is not None:
            usage.record(result)
        if result.verdict is JudgeVerdict.CONTRADICTED:
            return True
    return False


def classify_claim(
    claim: str,
    item: BenchmarkItem,
    output: SystemOutput,
    judge: Optional[Judge] = None,
    policy: MatchingPolicy = DEFAULT_POLICY,
    usage: Optional[JudgeUsage] = None,
) -> ClaimGrounding:
    """Classify one answer claim against this system's context and gold truth.

    See the module docstring for the full decision table.
    """
    context_decision = text_supported_by_contexts(
        output.retrieved_contexts, claim, judge, policy, usage
    )
    if context_decision.supported is True:
        return ClaimGrounding(
            claim=claim,
            status=ClaimStatus.SUPPORTED_BY_CONTEXT,
            context_supported=True,
            gold_supported=None,
            context_detail=context_decision.detail,
            gold_detail="",
        )

    gold_decision = text_supported_by_evidence(
        item.gold_evidence,
        claim,
        judge,
        policy,
        usage,
        gold_claims=item.gold_claims,
    )

    if gold_decision.supported is True:
        status = ClaimStatus.SUPPORTED_BY_GOLD_NOT_CONTEXT
        gold_detail = gold_decision.detail
    elif gold_decision.supported is False:
        # Try to tell "gold says no" apart from "gold says the opposite".
        # Only the judge route can carry that distinction; the text-containment
        # / overlap routes inside text_supported_by_evidence never return False
        # (see evidence_matching.text_supported_by_evidence), so a False here
        # implies at least one judge call was made.
        if gold_decision.method is SupportMethod.JUDGE and _gold_side_contradicted(
            item, claim, judge, usage
        ):
            status = ClaimStatus.CONTRADICTED
        else:
            status = ClaimStatus.UNSUPPORTED
        gold_detail = gold_decision.detail
    else:
        status = ClaimStatus.UNDECIDED
        gold_detail = gold_decision.detail

    return ClaimGrounding(
        claim=claim,
        status=status,
        context_supported=context_decision.supported,
        gold_supported=gold_decision.supported,
        context_detail=context_decision.detail,
        gold_detail=gold_detail,
    )


def _resolve_claims(
    output: SystemOutput,
    claims: Optional[Sequence[str]],
    judge: Optional[Judge],
) -> Optional[List[str]]:
    """Claim source precedence: explicit argument > output.answer_claims >
    judge.extract_claims(answer) > unavailable (None)."""
    if claims is not None:
        return list(claims)
    if output.answer_claims is not None:
        return list(output.answer_claims)
    if judge is not None and output.answer:
        extracted = judge.extract_claims(output.answer)
        if extracted is not None:
            return list(extracted)
    return None


def evaluate_grounding(
    item: BenchmarkItem,
    output: SystemOutput,
    claims: Optional[Sequence[str]] = None,
    judge: Optional[Judge] = None,
    policy: MatchingPolicy = DEFAULT_POLICY,
    usage: Optional[JudgeUsage] = None,
) -> GroundingMetrics:
    """Compute every grounding metric for one benchmark item / system output pair.

    See the module docstring for the formula and ↑/↓ direction of each field.
    """
    notes: List[str] = []
    resolved_claims = _resolve_claims(output, claims, judge)

    if resolved_claims is None:
        notes.append("answer claims unavailable: grounding metrics need claim extraction")
        return GroundingMetrics(
            faithfulness=None,
            hallucination_rate=None,
            retrieval_gap_rate=None,
            unsupported_claim_rate=None,
            n_claims=None,
            n_undecided=0,
            claims=[],
            notes=notes,
        )

    n_claims = len(resolved_claims)
    if n_claims == 0:
        # An explicit empty claim list is a real "nothing to check", but the
        # rates would need a division by zero to mean anything - report None,
        # not 0.0, and say so rather than implying a perfect (or zero) score.
        notes.append("zero claims to classify: grounding rates not applicable")
        return GroundingMetrics(
            faithfulness=None,
            hallucination_rate=None,
            retrieval_gap_rate=None,
            unsupported_claim_rate=None,
            n_claims=0,
            n_undecided=0,
            claims=[],
            notes=notes,
        )

    gradings = [
        classify_claim(claim, item, output, judge, policy, usage) for claim in resolved_claims
    ]

    n_supported_by_context = sum(
        1 for g in gradings if g.status is ClaimStatus.SUPPORTED_BY_CONTEXT
    )
    n_retrieval_gap = sum(
        1 for g in gradings if g.status is ClaimStatus.SUPPORTED_BY_GOLD_NOT_CONTEXT
    )
    n_unsupported = sum(1 for g in gradings if g.status is ClaimStatus.UNSUPPORTED)
    n_contradicted = sum(1 for g in gradings if g.status is ClaimStatus.CONTRADICTED)
    n_undecided = sum(1 for g in gradings if g.status is ClaimStatus.UNDECIDED)

    if any(g.status is ClaimStatus.UNSUPPORTED for g in gradings) and judge is None:
        notes.append(
            "no judge configured: UNSUPPORTED could not be distinguished from "
            "CONTRADICTED for some claims"
        )

    faithfulness = n_supported_by_context / n_claims
    hallucination_rate = (n_unsupported + n_contradicted) / n_claims
    retrieval_gap_rate = n_retrieval_gap / n_claims

    has_gold_material = bool(item.gold_evidence) or bool(item.gold_claims)
    if not has_gold_material:
        # Nothing on the gold side to be unsupported against - every claim's
        # gold side would be UNDECIDED by construction, so the rate is not
        # applicable rather than a coincidental 0.0.
        unsupported_claim_rate: Optional[float] = None
        notes.append(
            "no gold_evidence or gold_claims: unsupported_claim_rate not applicable"
        )
    else:
        checkable = [g for g in gradings if g.gold_supported is not None or g.status is ClaimStatus.CONTRADICTED]
        n_checkable = len(checkable)
        if n_checkable == 0:
            unsupported_claim_rate = None
            notes.append(
                "no claims had a decidable gold side: unsupported_claim_rate not applicable"
            )
        else:
            n_checkable_bad = sum(
                1
                for g in checkable
                if g.status in (ClaimStatus.UNSUPPORTED, ClaimStatus.CONTRADICTED)
            )
            unsupported_claim_rate = n_checkable_bad / n_checkable

    return GroundingMetrics(
        faithfulness=faithfulness,
        hallucination_rate=hallucination_rate,
        retrieval_gap_rate=retrieval_gap_rate,
        unsupported_claim_rate=unsupported_claim_rate,
        n_claims=n_claims,
        n_undecided=n_undecided,
        claims=gradings,
        notes=notes,
    )
