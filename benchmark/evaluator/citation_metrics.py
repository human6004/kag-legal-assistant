# -*- coding: utf-8 -*-
"""Citation-quality metrics: does the answer point at the right legal location?

Every comparison here routes through `evidence_matching.citation_location_match`
/ `citation_matches_evidence`. A citation is never scored against a
system-internal chunk id - only against the declared legal location
(document / article / clause / point) and, where available, text entailment.

Metrics (formula, direction):

  * `document_accuracy` (↑)  - `level_accuracy(citations, gold_evidence, "document")`.
  * `article_accuracy` (↑)   - same, level "article".
  * `clause_accuracy` (↑, diagnostic only) - same, level "clause". Diagnostic
    because most benchmark items do not require clause-level precision; still
    computed so a reviewer can see it.
  * `point_accuracy` (↑, diagnostic only) - same, level "point".
  * `citation_precision` (↑) - fraction of citations that actually support the
    claim they were attached to (see `evaluate_citations` docstring for the
    exact rule and its deterministic fallback).
  * `citation_recall` (↑)    - fraction of `item.required_evidence` that at
    least one citation points at, matched down to the article level (or
    document level when the gold evidence declares no article).

All four accuracies and both precision/recall return `None` when their
denominator is not applicable - "no comparison possible" is never reported as
0.0 or 1.0.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .evidence_matching import (
    DEFAULT_POLICY,
    LEVELS,
    MatchingPolicy,
    citation_location_match,
    citation_matches_evidence,
)
from .judge import Judge, JudgeUsage, JudgeVerdict
from .models import BenchmarkItem, Citation, EvidenceRef, RetrievedContext, SystemOutput


@dataclass(frozen=True)
class CitationMetrics:
    """Result bundle for one (item, output) pair. See module docstring for formulas."""

    document_accuracy: Optional[float]
    article_accuracy: Optional[float]
    clause_accuracy: Optional[float]
    point_accuracy: Optional[float]
    citation_precision: Optional[float]
    citation_recall: Optional[float]
    n_citations: int
    n_gold_required_evidence: int
    n_undecided: int
    details: List[Dict[str, Any]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_accuracy": self.document_accuracy,
            "article_accuracy": self.article_accuracy,
            "clause_accuracy": self.clause_accuracy,
            "point_accuracy": self.point_accuracy,
            "citation_precision": self.citation_precision,
            "citation_recall": self.citation_recall,
            "n_citations": self.n_citations,
            "n_gold_required_evidence": self.n_gold_required_evidence,
            "n_undecided": self.n_undecided,
            "details": [dict(d) for d in self.details],
            "notes": list(self.notes),
        }


def _matches_at_level(citation: Citation, evidence: EvidenceRef, level: str) -> bool:
    """A citation counts as correct at `level` when some single gold evidence
    matches it at `level` AND at every coarser level both declare.

    This stops a citation that agrees with gold document A's article from
    being credited against document B's article: the "correct at this level"
    question is always asked of one evidence entry at a time, coarsest level
    first, using `citation_location_match` for each level in turn.
    """
    order = LEVELS[: LEVELS.index(level) + 1]
    for coarser in order:
        verdict = citation_location_match(citation, evidence, coarser)
        if verdict is False:
            return False
    # The target level itself must have been a *declared, matching* level -
    # citation_location_match already returned True (not None) for it above
    # when both sides declare it. If neither declares it, verdict was None for
    # every level in `order` and the loop never rejected - but that means the
    # match is vacuous (nothing was actually compared at `level`). Guard that.
    return citation_location_match(citation, evidence, level) is True


def level_accuracy(
    citations: Sequence[Citation], evidence: Sequence[EvidenceRef], level: str
) -> Tuple[Optional[float], int]:
    """Accuracy at one location level, over citations where it is applicable.

    Applicable means: the citation declares `level` AND at least one gold
    evidence entry declares `level`. Among applicable citations, the fraction
    that match SOME gold evidence at `level` (and at every coarser level both
    that evidence and the citation declare) is the accuracy. Returns
    `(None, 0)` when nothing is applicable - not 0.0, since "inapplicable" and
    "checked and wrong" are different outcomes.
    """
    if level not in LEVELS:
        raise ValueError(f"unknown level: {level}")
    gold_declares_level = any(
        {
            "document": e.norm_document_id,
            "article": e.norm_article,
            "clause": e.norm_clause,
            "point": e.norm_point,
        }[level]
        is not None
        for e in evidence
    )
    if not gold_declares_level:
        return None, 0

    citation_declares_level = {
        "document": lambda c: c.norm_document_id,
        "article": lambda c: c.norm_article,
        "clause": lambda c: c.norm_clause,
        "point": lambda c: c.norm_point,
    }[level]

    applicable = [c for c in citations if citation_declares_level(c) is not None]
    n_applicable = len(applicable)
    if n_applicable == 0:
        return None, 0

    n_correct = 0
    for citation in applicable:
        if any(_matches_at_level(citation, e, level) for e in evidence):
            n_correct += 1
    return n_correct / n_applicable, n_applicable


def _context_for_citation(
    citation: Citation, contexts: Sequence[RetrievedContext]
) -> Optional[RetrievedContext]:
    """The retrieved context whose declared location matches `citation`, used
    as a text premise when the citation itself carries no text."""
    for context in contexts:
        levels_match = True
        seen_any = False
        for level, citation_val, context_val in (
            ("document", citation.norm_document_id, context.norm_document_id),
            ("article", citation.norm_article, context.norm_article),
            ("clause", citation.norm_clause, context.norm_clause),
            ("point", citation.norm_point, context.norm_point),
        ):
            if citation_val is None or context_val is None:
                continue
            seen_any = True
            if citation_val != context_val:
                levels_match = False
                break
        if seen_any and levels_match:
            return context
    return None


def _citation_precision_one(
    citation: Citation,
    item: BenchmarkItem,
    output: SystemOutput,
    claims: Optional[Sequence[str]],
    judge: Optional[Judge],
    usage: Optional[JudgeUsage],
) -> Tuple[Optional[bool], str]:
    """Is this one citation precise? Returns `(verdict, detail)`.

    Primary route: when the citation carries `claim_index` or `claim`, take
    that as the hypothesis and ask the judge with the citation's own text as
    premise, falling back to the retrieved context whose location matches the
    citation when the citation has no text of its own.

    Deterministic fallback (used whenever no claim is attached, or a claim is
    attached but no judge is available / the judge could not decide): the
    citation counts as precise iff `citation_matches_evidence(citation, e,
    deepest_level="article")` is True for some gold evidence `e`. This treats
    "the citation's declared location matches some gold evidence down to the
    article level" as the operational definition of "precise" when semantic
    entailment against the specific claim cannot be checked.
    """
    hypothesis: Optional[str] = None
    if citation.claim is not None:
        hypothesis = citation.claim
    elif citation.claim_index is not None and claims is not None:
        if 0 <= citation.claim_index < len(claims):
            hypothesis = claims[citation.claim_index]

    if hypothesis is not None and judge is not None:
        premise = citation.text
        if not premise:
            matched_context = _context_for_citation(citation, output.retrieved_contexts)
            premise = matched_context.text if matched_context else None
        if premise:
            result = judge.entails(premise, hypothesis)
            if usage is not None:
                usage.record(result)
            if result.verdict is not JudgeVerdict.UNKNOWN:
                return result.supported, result.rationale or result.verdict.value

    # Deterministic fallback.
    for evidence in item.gold_evidence:
        verdict = citation_matches_evidence(citation, evidence, deepest_level="article")
        if verdict is True:
            return True, f"matches gold evidence {evidence.key()} to article level"
    if item.gold_evidence:
        return False, "no gold evidence matched at document/article level"
    return None, "no gold evidence to compare against"


def evaluate_citations(
    item: BenchmarkItem,
    output: SystemOutput,
    claims: Optional[Sequence[str]] = None,
    judge: Optional[Judge] = None,
    policy: MatchingPolicy = DEFAULT_POLICY,
    usage: Optional[JudgeUsage] = None,
) -> CitationMetrics:
    """Compute every citation metric for one benchmark item / system output pair.

    `claims` (when given) or `output.answer_claims` supplies the hypothesis
    text for citations that carry a `claim_index` but no inline `claim` text;
    when neither is available, `claim_index`-based lookups are skipped and the
    deterministic fallback in `_citation_precision_one` is used instead.
    """
    notes: List[str] = []
    details: List[Dict[str, Any]] = []
    n_undecided = 0

    citations = output.citations
    n_citations = len(citations)
    gold_evidence = item.gold_evidence
    required_evidence = item.required_evidence

    document_accuracy, _ = level_accuracy(citations, gold_evidence, "document")
    article_accuracy, _ = level_accuracy(citations, gold_evidence, "article")
    clause_accuracy, _ = level_accuracy(citations, gold_evidence, "clause")
    point_accuracy, _ = level_accuracy(citations, gold_evidence, "point")

    for level, value in (
        ("document", document_accuracy),
        ("article", article_accuracy),
        ("clause", clause_accuracy),
        ("point", point_accuracy),
    ):
        if value is None:
            notes.append(f"{level}_accuracy: not applicable (no declared {level} on both sides)")

    resolved_claims: Optional[Sequence[str]] = (
        claims if claims is not None else output.answer_claims
    )

    # -- citation precision --------------------------------------------------
    if n_citations == 0:
        citation_precision: Optional[float] = None
        notes.append("no citations: citation_precision not applicable")
    else:
        n_precise = 0
        n_precision_decided = 0
        for citation in citations:
            verdict, detail = _citation_precision_one(
                citation, item, output, resolved_claims, judge, usage
            )
            if verdict is True:
                n_precise += 1
                n_precision_decided += 1
            elif verdict is False:
                n_precision_decided += 1
            else:
                n_undecided += 1
            details.append(
                {
                    "kind": "citation",
                    "citation": citation.label(),
                    "claim_index": citation.claim_index,
                    "precise": verdict,
                    "detail": detail,
                }
            )
        if n_precision_decided == 0:
            citation_precision = None
            notes.append("citation_precision: no citation could be decided -> not applicable")
        else:
            citation_precision = n_precise / n_precision_decided

    # -- citation recall ------------------------------------------------------
    n_gold_required = len(required_evidence)
    if n_gold_required == 0:
        citation_recall: Optional[float] = None
        notes.append("no required gold evidence: citation_recall not applicable")
    else:
        n_hit = 0
        for evidence in required_evidence:
            deepest = "article" if evidence.norm_article is not None else "document"
            hit = False
            matched_citation: Optional[Citation] = None
            for citation in citations:
                verdict = citation_matches_evidence(citation, evidence, deepest_level=deepest)
                if verdict is True:
                    hit = True
                    matched_citation = citation
                    break
            if hit:
                n_hit += 1
            details.append(
                {
                    "kind": "required_evidence",
                    "evidence": evidence.key(),
                    "location": evidence.label(),
                    "cited": hit,
                    "matched_citation": matched_citation.label() if matched_citation else None,
                }
            )
        citation_recall = n_hit / n_gold_required

    return CitationMetrics(
        document_accuracy=document_accuracy,
        article_accuracy=article_accuracy,
        clause_accuracy=clause_accuracy,
        point_accuracy=point_accuracy,
        citation_precision=citation_precision,
        citation_recall=citation_recall,
        n_citations=n_citations,
        n_gold_required_evidence=n_gold_required,
        n_undecided=n_undecided,
        details=details,
        notes=notes,
    )
