# -*- coding: utf-8 -*-
"""Answer-side metrics: does the generated answer say the right thing.

Metrics (formula, direction):

  * `hit_rate` (↑)      - # gold markers found in the answer (via
    `normalization.contains_marker`) / # gold markers. `None` when there are
    no gold markers (not applicable) - never `0.0` in that case.
  * `hit_all` (↑)       - 1.0 iff every gold marker was found, else 0.0.
    `None` when there are no gold markers.
  * `claim_precision` (↑) - of the answer's own claims, the fraction that are
    supported by gold evidence/claims. Undecided claims are excluded from the
    numerator but still counted (`n_claim_undecided`). `None` when the
    answer's claims are unavailable or there are none.
  * `claim_recall` (↑)    - of the gold claims, the fraction the answer
    expresses (deterministic containment/coverage first, judge second).
    `None` when `item.gold_claims` is empty.
  * `claim_f1` (↑)        - harmonic mean of `claim_precision`/`claim_recall`;
    `None` when either input is `None`; `0.0` when both are `0.0`.

Error / empty-answer handling (see `evaluate_answer` docstring for the exact
rule): a system error always yields `None` for every judge/marker metric that
depends on the (possibly missing) answer text, with a note explaining why. An
answer that is merely empty text with *no* error is scored as a genuine miss
(`0.0`) against any gold markers that exist, because "the system answered
nothing" really does hit nothing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from .evidence_matching import DEFAULT_POLICY, MatchingPolicy, text_supported_by_evidence
from .judge import Judge, JudgeUsage
from .models import BenchmarkItem, SystemOutput
from .normalization import contains_marker, token_coverage


@dataclass(frozen=True)
class AnswerMetrics:
    """Result bundle for one (item, output) pair. See module docstring for formulas."""

    hit_rate: Optional[float]
    hit_all: Optional[float]
    n_gold_markers: int
    n_markers_hit: int
    missing_markers: List[str]
    claim_precision: Optional[float]
    claim_recall: Optional[float]
    claim_f1: Optional[float]
    n_answer_claims: Optional[int]
    n_gold_claims: int
    n_claim_undecided: int
    claim_details: List[Dict[str, Any]]
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hit_rate": self.hit_rate,
            "hit_all": self.hit_all,
            "n_gold_markers": self.n_gold_markers,
            "n_markers_hit": self.n_markers_hit,
            "missing_markers": list(self.missing_markers),
            "claim_precision": self.claim_precision,
            "claim_recall": self.claim_recall,
            "claim_f1": self.claim_f1,
            "n_answer_claims": self.n_answer_claims,
            "n_gold_claims": self.n_gold_claims,
            "n_claim_undecided": self.n_claim_undecided,
            "claim_details": [dict(d) for d in self.claim_details],
            "notes": list(self.notes),
        }


def marker_hits(answer: Optional[str], gold_markers: Sequence[str]) -> List[bool]:
    """Per-marker containment result, in `gold_markers` order."""
    return [contains_marker(answer, marker) for marker in gold_markers]


def hit_rate(answer: Optional[str], gold_markers: Sequence[str]) -> Optional[float]:
    """Fraction of `gold_markers` found in `answer`. `None` when there are none."""
    n = len(gold_markers)
    if n == 0:
        # Denominator would be 0 - "hit rate over no markers" is not applicable.
        return None
    hits = marker_hits(answer, gold_markers)
    return sum(1 for h in hits if h) / n


def hit_all(answer: Optional[str], gold_markers: Sequence[str]) -> Optional[float]:
    """1.0 iff every gold marker was found, else 0.0. `None` when there are none."""
    if len(gold_markers) == 0:
        # Nothing to require -> not applicable, not a free pass of 1.0.
        return None
    hits = marker_hits(answer, gold_markers)
    return 1.0 if all(hits) else 0.0


def answer_claims(output: SystemOutput, judge: Optional[Judge] = None) -> Optional[List[str]]:
    """The answer's atomic claims: adapter-provided, else judge-extracted, else `None`.

    `None` means "claim metrics unavailable" and must propagate as `None`
    through every claim metric, never silently become `0.0`.
    """
    if output.answer_claims is not None:
        return output.answer_claims
    if judge is not None and output.answer:
        extracted = judge.extract_claims(output.answer)
        if isinstance(extracted, list):
            return extracted
    return None


def _claim_recall_decision(
    answer: Optional[str],
    gold_claim: str,
    judge: Optional[Judge],
    policy: MatchingPolicy,
) -> Dict[str, Any]:
    """Decide whether `answer` expresses `gold_claim`. Deterministic first, judge second."""
    if contains_marker(answer, gold_claim):
        return {
            "side": "gold",
            "claim": gold_claim,
            "supported": True,
            "method": "text_containment",
            "detail": "gold claim contained in answer",
        }
    coverage = token_coverage(gold_claim, answer)
    if coverage is not None and coverage >= policy.text_overlap_threshold:
        return {
            "side": "gold",
            "claim": gold_claim,
            "supported": True,
            "method": "text_overlap",
            "detail": f"token coverage {coverage:.2f}",
        }
    if judge is not None and answer:
        result = judge.entails(premise=answer, hypothesis=gold_claim)
        return {
            "side": "gold",
            "claim": gold_claim,
            "supported": result.supported,
            "method": "judge",
            "detail": result.rationale or result.verdict.value,
        }
    detail = "no route decided"
    if coverage is not None:
        detail = f"token coverage {coverage:.2f} below threshold"
    return {
        "side": "gold",
        "claim": gold_claim,
        "supported": None,
        "method": "undecided",
        "detail": detail,
    }


def evaluate_answer(
    item: BenchmarkItem,
    output: SystemOutput,
    judge: Optional[Judge] = None,
    policy: MatchingPolicy = DEFAULT_POLICY,
    usage: Optional[JudgeUsage] = None,
) -> AnswerMetrics:
    """Compute every answer metric for one benchmark item / system output pair.

    Error / empty-answer rule: when `output.error` is set, `hit_rate`,
    `hit_all`, and every claim metric report `None` ("unavailable") with a
    note - a system that errored did not "fail to say the marker", it never
    got the chance. When there is no error but `output.answer` is empty/None,
    `hit_rate`/`hit_all` are computed normally against an empty string, which
    is `0.0` whenever gold markers exist (a real, honest miss), and claim
    metrics fall back on `answer_claims()` (typically `None`, since there is
    no text to extract claims from).
    """
    notes: List[str] = []
    gold_markers = item.gold_markers
    gold_claims = item.gold_claims
    n_gold_markers = len(gold_markers)
    n_gold_claims = len(gold_claims)

    if output.error is not None:
        notes.append(f"system error '{output.error}': answer metrics unavailable")
        return AnswerMetrics(
            hit_rate=None,
            hit_all=None,
            n_gold_markers=n_gold_markers,
            n_markers_hit=0,
            missing_markers=list(gold_markers),
            claim_precision=None,
            claim_recall=None,
            claim_f1=None,
            n_answer_claims=None,
            n_gold_claims=n_gold_claims,
            n_claim_undecided=0,
            claim_details=[],
            notes=notes,
        )

    answer = output.answer

    # -- marker metrics ------------------------------------------------------
    hits = marker_hits(answer, gold_markers)
    n_markers_hit = sum(1 for h in hits if h)
    missing_markers = [m for m, h in zip(gold_markers, hits) if not h]
    hr = hit_rate(answer, gold_markers)
    ha = hit_all(answer, gold_markers)
    if n_gold_markers == 0:
        notes.append("no gold markers: hit_rate/hit_all not applicable")
    elif not answer:
        notes.append("empty answer (no error): marker metrics scored as a genuine miss")

    # -- claim metrics ---------------------------------------------------------
    claims = answer_claims(output, judge)
    n_answer_claims = len(claims) if claims is not None else None
    claim_details: List[Dict[str, Any]] = []
    n_claim_undecided = 0

    # claim_precision: for each answer claim, is it supported by gold material?
    if claims is None:
        claim_precision: Optional[float] = None
        notes.append("answer claims unavailable: claim_precision not applicable")
    elif len(claims) == 0:
        claim_precision = None
        notes.append("answer produced no claims: claim_precision not applicable")
    else:
        n_precision_supported = 0
        for claim in claims:
            decision = text_supported_by_evidence(
                item.gold_evidence, claim, judge, policy, usage, gold_claims=gold_claims
            )
            claim_details.append(
                {
                    "side": "answer",
                    "claim": claim,
                    "supported": decision.supported,
                    "method": decision.method.value,
                    "detail": decision.detail,
                }
            )
            if decision.supported is True:
                n_precision_supported += 1
            elif decision.supported is None:
                n_claim_undecided += 1
        claim_precision = n_precision_supported / len(claims)

    # claim_recall: for each gold claim, does the answer express it?
    if n_gold_claims == 0:
        claim_recall: Optional[float] = None
        notes.append("no gold claims: claim_recall not applicable")
    else:
        n_expressed = 0
        for gold_claim in gold_claims:
            decision = _claim_recall_decision(answer, gold_claim, judge, policy)
            claim_details.append(decision)
            if decision["supported"] is True:
                n_expressed += 1
            elif decision["supported"] is None:
                n_claim_undecided += 1
        claim_recall = n_expressed / n_gold_claims

    # claim_f1: harmonic mean, undefined when either side is unavailable.
    if claim_precision is None or claim_recall is None:
        claim_f1: Optional[float] = None
    elif claim_precision + claim_recall == 0:
        # Both zero -> harmonic mean would divide by zero; the honest score is 0.
        claim_f1 = 0.0
    else:
        claim_f1 = 2 * claim_precision * claim_recall / (claim_precision + claim_recall)

    return AnswerMetrics(
        hit_rate=hr,
        hit_all=ha,
        n_gold_markers=n_gold_markers,
        n_markers_hit=n_markers_hit,
        missing_markers=missing_markers,
        claim_precision=claim_precision,
        claim_recall=claim_recall,
        claim_f1=claim_f1,
        n_answer_claims=n_answer_claims,
        n_gold_claims=n_gold_claims,
        n_claim_undecided=n_claim_undecided,
        claim_details=claim_details,
        notes=notes,
    )
