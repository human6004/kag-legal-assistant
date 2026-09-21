# -*- coding: utf-8 -*-
"""Architecture-neutral matching between gold evidence and retrieved context.

Every retrieval, grounding and citation metric routes through this module, so
the fairness rule lives in exactly one place: a system is credited for finding
*the evidence*, never for producing a particular chunk. Nothing here knows how
any system splits documents, and no system-internal identifier participates.

Three routes decide support, in this order:

1. **structural** - the context's declared legal location matches every level
   the gold evidence declares (document, and article/clause/point when given).
   A declared mismatch is a hard negative: citing Điều 52 for Điều 53 evidence
   cannot be rescued by a judge.
2. **text** - the gold evidence text is contained in the context text after
   marker normalization, or covers enough of its tokens. This is what makes
   different chunkings comparable: one 2000-token chunk holding E1 and E2
   supports both, and two 200-token chunks holding one each also support both.
3. **judge** - semantic entailment, for paraphrase and for coarse contexts that
   declare less metadata than the gold evidence.

When no route decides, the decision is `supported=None` ("undecided"), not
False. Callers choose what to do with it; `MatchingPolicy.undecided_counts_as`
makes that choice explicit and reportable instead of hidden.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from .judge import Judge, JudgeUsage, JudgeVerdict
from .models import Citation, EvidenceRef, RetrievedContext
from .normalization import normalize_for_match, token_coverage, tokenize


class SupportMethod(str, Enum):
    STRUCTURAL = "structural"
    TEXT_CONTAINMENT = "text_containment"
    TEXT_OVERLAP = "text_overlap"
    JUDGE = "judge"
    LOCATION_MISMATCH = "location_mismatch"
    UNDECIDED = "undecided"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class SupportDecision:
    """Outcome of one support question, with the route that produced it."""

    supported: Optional[bool]
    method: SupportMethod
    score: Optional[float] = None
    detail: str = ""

    @property
    def decided(self) -> bool:
        return self.supported is not None

    def resolve(self, undecided_counts_as: Optional[bool]) -> Optional[bool]:
        if self.supported is not None:
            return self.supported
        return undecided_counts_as


UNDECIDED = SupportDecision(None, SupportMethod.UNDECIDED)


@dataclass(frozen=True)
class MatchingPolicy:
    """Knobs for evidence matching. Defaults are the ones used for the paper."""

    #: Minimum fraction of gold-evidence tokens present in the context text.
    text_overlap_threshold: float = 0.8
    use_structural: bool = True
    use_text: bool = True
    use_judge: bool = True
    #: How an undecided decision is counted by metrics. `None` keeps it out of
    #: the numerator *and* records it, so a reader can see how much was unknown.
    undecided_counts_as: Optional[bool] = None
    #: Count a structural match that stops above the gold granularity (context
    #: declares the article, gold declares a point, no text to check) as support.
    #: Off by default: it would reward coarse metadata.
    coarse_metadata_counts: bool = False
    #: Even when structure matches, require the text route to agree if both
    #: sides carry text. Off by default (structure is the cheaper, harder signal).
    verify_text_when_available: bool = False


DEFAULT_POLICY = MatchingPolicy()

LEVELS = ("document", "article", "clause", "point")


def _levels(evidence: EvidenceRef) -> Dict[str, Optional[str]]:
    return {
        "document": evidence.norm_document_id,
        "article": evidence.norm_article,
        "clause": evidence.norm_clause,
        "point": evidence.norm_point,
    }


def _context_levels(context: RetrievedContext) -> Dict[str, Optional[str]]:
    return {
        "document": context.norm_document_id,
        "article": context.norm_article,
        "clause": context.norm_clause,
        "point": context.norm_point,
    }


def _citation_levels(citation: Citation) -> Dict[str, Optional[str]]:
    return {
        "document": citation.norm_document_id,
        "article": citation.norm_article,
        "clause": citation.norm_clause,
        "point": citation.norm_point,
    }


def structural_decision(
    context_levels: Dict[str, Optional[str]],
    gold_levels: Dict[str, Optional[str]],
) -> Tuple[Optional[bool], List[str], Optional[str]]:
    """Compare declared legal locations.

    Returns `(verdict, missing_levels, mismatch_level)`:

      * `(False, [], level)`  - both sides declare `level` and they differ.
      * `(True, [], None)`    - every level the gold declares is matched.
      * `(None, missing, None)` - no mismatch, but the context stays silent on
        `missing` levels, so structure alone cannot decide.
    """
    missing: List[str] = []
    for level in LEVELS:
        gold = gold_levels.get(level)
        if gold is None:
            continue
        got = context_levels.get(level)
        if got is None:
            missing.append(level)
        elif got != gold:
            return False, [], level
    if missing:
        return None, missing, None
    return True, [], None


def _text_decision(
    gold_text: Optional[str], context_text: Optional[str], policy: MatchingPolicy
) -> SupportDecision:
    if not gold_text or not context_text:
        return SupportDecision(None, SupportMethod.NOT_APPLICABLE, detail="no text to compare")
    if normalize_for_match(gold_text) in normalize_for_match(context_text):
        return SupportDecision(True, SupportMethod.TEXT_CONTAINMENT, 1.0, "evidence text contained")
    coverage = token_coverage(gold_text, context_text)
    if coverage is None:
        return SupportDecision(None, SupportMethod.NOT_APPLICABLE, detail="no tokens")
    if coverage >= policy.text_overlap_threshold:
        return SupportDecision(
            True, SupportMethod.TEXT_OVERLAP, coverage, f"token coverage {coverage:.2f}"
        )
    return SupportDecision(
        None, SupportMethod.TEXT_OVERLAP, coverage, f"token coverage {coverage:.2f} below threshold"
    )


def _judge_decision(
    judge: Optional[Judge],
    premise: Optional[str],
    hypothesis: Optional[str],
    usage: Optional[JudgeUsage] = None,
) -> SupportDecision:
    if judge is None or not premise or not hypothesis:
        return SupportDecision(None, SupportMethod.UNDECIDED, detail="judge unavailable")
    result = judge.entails(premise, hypothesis)
    if usage is not None:
        usage.record(result)
    if result.verdict is JudgeVerdict.SUPPORTED:
        return SupportDecision(True, SupportMethod.JUDGE, result.score, result.rationale)
    if result.verdict in (JudgeVerdict.NOT_SUPPORTED, JudgeVerdict.CONTRADICTED):
        return SupportDecision(
            False, SupportMethod.JUDGE, result.score, result.rationale or result.verdict.value
        )
    return SupportDecision(None, SupportMethod.UNDECIDED, result.score, result.rationale)


def context_supports_evidence(
    context: RetrievedContext,
    evidence: EvidenceRef,
    judge: Optional[Judge] = None,
    policy: MatchingPolicy = DEFAULT_POLICY,
    usage: Optional[JudgeUsage] = None,
) -> SupportDecision:
    """Does this retrieved context support this gold evidence?"""
    gold_levels = _levels(evidence)
    if policy.use_structural:
        verdict, missing, mismatch = structural_decision(_context_levels(context), gold_levels)
        if verdict is False:
            return SupportDecision(
                False,
                SupportMethod.LOCATION_MISMATCH,
                detail=f"{mismatch} mismatch: context {_context_levels(context).get(mismatch)!r} "
                f"vs gold {gold_levels.get(mismatch)!r}",
            )
        if verdict is True:
            if not (policy.verify_text_when_available and evidence.text and context.text):
                return SupportDecision(
                    True, SupportMethod.STRUCTURAL, 1.0, "declared location matches gold"
                )
    else:
        missing = [lvl for lvl in LEVELS if gold_levels.get(lvl)]

    if policy.use_text:
        text_decision = _text_decision(evidence.text, context.text, policy)
        if text_decision.supported is True:
            return text_decision
    else:
        text_decision = UNDECIDED

    if policy.use_judge:
        judged = _judge_decision(judge, context.text, evidence.text, usage)
        if judged.decided:
            return judged

    if policy.coarse_metadata_counts:
        # No level mismatched; the context is merely coarser than the gold
        # (declares the article, gold declares a point). Opt-in only.
        return SupportDecision(
            True,
            SupportMethod.STRUCTURAL,
            None,
            f"coarse metadata accepted (context silent on {missing})" if missing else "coarse metadata accepted",
        )
    detail = text_decision.detail or "no route decided"
    return SupportDecision(None, SupportMethod.UNDECIDED, text_decision.score, detail)


@dataclass(frozen=True)
class EvidenceSupport:
    """Per-evidence retrieval outcome for one system's context list."""

    evidence: EvidenceRef
    supported: Optional[bool]
    rank: Optional[int]
    decision: SupportDecision

    def to_dict(self) -> Dict[str, object]:
        return {
            "evidence": self.evidence.key(),
            "location": self.evidence.label(),
            "required": self.evidence.required,
            "supported": self.supported,
            "rank": self.rank,
            "method": self.decision.method.value,
            "detail": self.decision.detail,
        }


def support_for_evidence(
    contexts: Sequence[RetrievedContext],
    evidence: EvidenceRef,
    judge: Optional[Judge] = None,
    policy: MatchingPolicy = DEFAULT_POLICY,
    usage: Optional[JudgeUsage] = None,
) -> EvidenceSupport:
    """Find the best-ranked context supporting `evidence`.

    A single undecided context does not make the evidence undecided: the search
    continues, and undecided is only reported when no context supported it and
    at least one could not be decided.
    """
    best: Optional[SupportDecision] = None
    saw_undecided = False
    for context in sorted(contexts, key=lambda c: c.rank):
        decision = context_supports_evidence(context, evidence, judge, policy, usage)
        if decision.supported is True:
            return EvidenceSupport(evidence, True, context.rank, decision)
        if decision.supported is None:
            saw_undecided = True
            if best is None or best.supported is not None:
                best = decision
        elif best is None:
            best = decision
    supported: Optional[bool] = None if saw_undecided else False
    return EvidenceSupport(
        evidence,
        supported,
        None,  # no context supported it, so there is no supporting rank
        best or SupportDecision(supported, SupportMethod.UNDECIDED, detail="no contexts"),
    )


def support_map(
    contexts: Sequence[RetrievedContext],
    evidence_list: Sequence[EvidenceRef],
    judge: Optional[Judge] = None,
    policy: MatchingPolicy = DEFAULT_POLICY,
    usage: Optional[JudgeUsage] = None,
) -> List[EvidenceSupport]:
    return [
        support_for_evidence(contexts, e, judge, policy, usage) for e in evidence_list
    ]


def context_supports_any(
    context: RetrievedContext,
    evidence_list: Sequence[EvidenceRef],
    judge: Optional[Judge] = None,
    policy: MatchingPolicy = DEFAULT_POLICY,
    usage: Optional[JudgeUsage] = None,
    gold_claims: Sequence[str] = (),
) -> SupportDecision:
    """Is this context relevant at all - does it support any gold evidence/claim?

    Used by Context Precision. Gold claims participate because a context can be
    on-topic support for a claim whose evidence text was not transcribed.
    """
    best: Optional[SupportDecision] = None
    for evidence in evidence_list:
        decision = context_supports_evidence(context, evidence, judge, policy, usage)
        if decision.supported is True:
            return decision
        if best is None or (best.supported is False and decision.supported is None):
            best = decision
    for claim in gold_claims:
        decision = text_supported_by_context(context, claim, judge, policy, usage)
        if decision.supported is True:
            return decision
        if best is None or (best.supported is False and decision.supported is None):
            best = decision
    return best or SupportDecision(None, SupportMethod.UNDECIDED, detail="no gold to compare")


def text_supported_by_context(
    context: RetrievedContext,
    hypothesis: str,
    judge: Optional[Judge] = None,
    policy: MatchingPolicy = DEFAULT_POLICY,
    usage: Optional[JudgeUsage] = None,
) -> SupportDecision:
    """Does one context's text support a free-text hypothesis (a claim)?"""
    if policy.use_text:
        decision = _text_decision(hypothesis, context.text, policy)
        if decision.supported is True:
            return decision
    if policy.use_judge:
        judged = _judge_decision(judge, context.text, hypothesis, usage)
        if judged.decided:
            return judged
    return SupportDecision(None, SupportMethod.UNDECIDED, detail="no route decided")


def text_supported_by_contexts(
    contexts: Sequence[RetrievedContext],
    hypothesis: str,
    judge: Optional[Judge] = None,
    policy: MatchingPolicy = DEFAULT_POLICY,
    usage: Optional[JudgeUsage] = None,
) -> SupportDecision:
    """Best decision across all contexts for one hypothesis.

    A False from one context never outweighs an undecided from another: absence
    of the claim in context #1 says nothing about context #2.
    """
    best: Optional[SupportDecision] = None
    saw_undecided = False
    for context in sorted(contexts, key=lambda c: c.rank):
        decision = text_supported_by_context(context, hypothesis, judge, policy, usage)
        if decision.supported is True:
            return decision
        if decision.supported is None:
            saw_undecided = True
        if best is None:
            best = decision
    if saw_undecided:
        return SupportDecision(None, SupportMethod.UNDECIDED, detail="no context decided support")
    return best or SupportDecision(None, SupportMethod.UNDECIDED, detail="no contexts")


def text_supported_by_evidence(
    evidence_list: Sequence[EvidenceRef],
    hypothesis: str,
    judge: Optional[Judge] = None,
    policy: MatchingPolicy = DEFAULT_POLICY,
    usage: Optional[JudgeUsage] = None,
    gold_claims: Sequence[str] = (),
) -> SupportDecision:
    """Is a hypothesis supported by the authoritative gold material?

    This is the corpus-side question used to tell a retrieval gap apart from a
    hallucination: a claim can be true against gold evidence while absent from
    what the system actually retrieved.
    """
    best: Optional[SupportDecision] = None
    saw_undecided = False
    for claim in gold_claims:
        if normalize_for_match(claim) and normalize_for_match(hypothesis) in normalize_for_match(claim):
            return SupportDecision(True, SupportMethod.TEXT_CONTAINMENT, 1.0, "gold claim contains hypothesis")
        coverage = token_coverage(hypothesis, claim)
        if coverage is not None and coverage >= policy.text_overlap_threshold:
            return SupportDecision(
                True, SupportMethod.TEXT_OVERLAP, coverage, "gold claim covers hypothesis"
            )
    for evidence in evidence_list:
        if policy.use_text and evidence.text:
            if normalize_for_match(hypothesis) in normalize_for_match(evidence.text):
                return SupportDecision(
                    True, SupportMethod.TEXT_CONTAINMENT, 1.0, "gold evidence text contains hypothesis"
                )
            coverage = token_coverage(hypothesis, evidence.text)
            if coverage is not None and coverage >= policy.text_overlap_threshold:
                return SupportDecision(
                    True, SupportMethod.TEXT_OVERLAP, coverage, "gold evidence covers hypothesis"
                )
        if policy.use_judge:
            judged = _judge_decision(judge, evidence.text, hypothesis, usage)
            if judged.supported is True:
                return judged
            if judged.supported is None:
                saw_undecided = True
            elif best is None:
                best = judged
    for claim in gold_claims:
        if policy.use_judge:
            judged = _judge_decision(judge, claim, hypothesis, usage)
            if judged.supported is True:
                return judged
            if judged.supported is None:
                saw_undecided = True
            elif best is None:
                best = judged
    if saw_undecided:
        return SupportDecision(None, SupportMethod.UNDECIDED, detail="gold side undecided")
    return best or SupportDecision(None, SupportMethod.UNDECIDED, detail="no gold material")


# --------------------------------------------------------------------------
# Citation location matching
# --------------------------------------------------------------------------


def citation_location_match(
    citation: Citation, evidence: EvidenceRef, level: str
) -> Optional[bool]:
    """Compare a citation with gold evidence at one level.

    Returns `None` when the comparison is not applicable - either the gold does
    not declare that level, or the citation does not. That keeps Article
    Accuracy from being punished for a level the dataset never specified, and
    from being credited for a level the system never stated.
    """
    if level not in LEVELS:
        raise ValueError(f"unknown level: {level}")
    gold = _levels(evidence).get(level)
    got = _citation_levels(citation).get(level)
    if gold is None or got is None:
        return None
    return got == gold


def citation_matches_evidence(
    citation: Citation,
    evidence: EvidenceRef,
    deepest_level: str = "article",
) -> Optional[bool]:
    """True when the citation agrees with the evidence down to `deepest_level`.

    A level neither side declares is skipped. `None` means undecidable (for
    instance a citation carrying no document id at all).
    """
    order = LEVELS[: LEVELS.index(deepest_level) + 1]
    seen_any = False
    for level in order:
        verdict = citation_location_match(citation, evidence, level)
        if verdict is False:
            return False
        if verdict is True:
            seen_any = True
    return True if seen_any else None


# --------------------------------------------------------------------------
# Context-token budget
# --------------------------------------------------------------------------

TokenCounter = Callable[[str], int]


def default_token_counter(text: Optional[str]) -> int:
    """Rough, model-free token estimate.

    Two signals, take the larger: whitespace words, and characters / 4. It
    intentionally does not load a tokenizer - the budget comparison has to be
    identical for all three systems and reproducible years later, and the point
    is a *shared* budget, not an exact count for one vendor's tokenizer. Pass a
    real tokenizer as `token_counter` if a run needs one; use the same one for
    every system.
    """
    if not text:
        return 0
    words = len(tokenize(text))
    chars = math.ceil(len(text) / 4)
    return max(words, chars)


def contexts_within_budget(
    contexts: Sequence[RetrievedContext],
    budget_tokens: int,
    token_counter: TokenCounter = default_token_counter,
) -> List[RetrievedContext]:
    """Rank-ordered prefix of `contexts` whose total token count fits the budget.

    A context whose own size already exceeds the remaining budget is skipped and
    the walk continues, mirroring what a generator would do when packing a
    prompt. `token_count` from the adapter wins over the estimate when present.
    """
    if budget_tokens <= 0:
        return []
    used = 0
    kept: List[RetrievedContext] = []
    for context in sorted(contexts, key=lambda c: c.rank):
        size = context.token_count
        if size is None:
            size = token_counter(context.text or "")
        if used + size > budget_tokens:
            continue
        used += size
        kept.append(context)
    return kept


def iter_ranks(contexts: Iterable[RetrievedContext]) -> List[int]:
    return [c.rank for c in sorted(contexts, key=lambda c: c.rank)]
