# -*- coding: utf-8 -*-
"""Abstention metrics: did the system correctly refuse an unanswerable question?

Metrics (formula, direction):

  * `correct_abstention` (↑) - 1.0 when the system abstained on an item whose
    gold answer is "unanswerable" (`item.answerable is False`), else 0.0.
    `None` when `item.answerable is True` (not applicable - abstention is not
    the right behavior there) or when abstention itself could not be decided.
  * `false_answer_rate` (↓)  - the complement view of the same case: 1.0 when
    the system asserted an answer on an unanswerable item, else 0.0. Also
    `None` when `item.answerable is True` or abstention is undecided.
  * `unsupported_claim_rate` (↓) - delegated to `grounding_metrics`, never
    recomputed here (see below).

`correct_abstention` and `false_answer_rate` are two different views of the
same coin flip (abstained vs. answered) on unanswerable items, not
complementary in general: both are `None` together, or `1.0`/`0.0` together in
a way that always sums to 1.0 when decided at all. They are kept as separate
fields because "the metric that goes up when the system behaves well" and
"the metric that goes down" read differently in a report table.

Retrieval metrics are **not** computed in this module. An unanswerable item
with an intentionally empty `gold_evidence` list has nothing to retrieve
against, and `retrieval_metrics.evaluate_retrieval` already reports every
retrieval metric as `None` for `n_gold_evidence == 0` - that is the existing,
correct behavior and this module does not duplicate or override it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .grounding_metrics import GroundingMetrics, evaluate_grounding
from .judge import Judge, JudgeUsage
from .models import BenchmarkItem, SystemOutput
from .normalization import contains_marker
from .evidence_matching import DEFAULT_POLICY, MatchingPolicy

# Vietnamese + English refusal cues for a legal-assistant answer. Overridable
# per call via `detect_abstention(..., cues=...)`. Matched with
# `normalization.contains_marker`, so diacritics and markdown wrapping
# ("**không đủ căn cứ**") do not break a match.
ABSTENTION_CUES: Tuple[str, ...] = (
    # Vietnamese
    "không đủ căn cứ",
    "không tìm thấy",
    "không có thông tin",
    "không xác định được",
    "chưa có quy định",
    "không thể trả lời",
    "ngoài phạm vi",
    # English
    "cannot answer",
    "not enough information",
    "no information",
    "unable to determine",
    "insufficient",
)


@dataclass(frozen=True)
class AbstentionMetrics:
    """Result bundle for one (item, output) pair. See module docstring for formulas."""

    correct_abstention: Optional[float]
    false_answer_rate: Optional[float]
    unsupported_claim_rate: Optional[float]
    abstained: Optional[bool]
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "correct_abstention": self.correct_abstention,
            "false_answer_rate": self.false_answer_rate,
            "unsupported_claim_rate": self.unsupported_claim_rate,
            "abstained": self.abstained,
            "notes": list(self.notes),
        }


def detect_abstention(
    answer: Optional[str],
    judge: Optional[Judge] = None,
    cues: Sequence[str] = ABSTENTION_CUES,
) -> Optional[bool]:
    """Did this answer refuse to answer?

    Precedence:

      1. Any cue in `cues` found in `answer` (via `contains_marker`) -> `True`.
      2. No cue hit, but `judge.is_abstention(answer)` returns a bool -> that
         bool.
      3. No cue hit, no judge verdict, and `answer` has real (non-whitespace)
         content -> `False` (an assertive answer).
      4. `answer` is `None` or blank -> `None` (unavailable). An empty answer
         is a failure to respond, not a principled refusal, so it must not be
         reported as either `True` or `False`.
    """
    if answer is not None and any(contains_marker(answer, cue) for cue in cues):
        return True
    if judge is not None:
        judged = judge.is_abstention(answer or "")
        if judged is not None:
            return judged
    if answer is not None and answer.strip():
        return False
    return None


def evaluate_abstention(
    item: BenchmarkItem,
    output: SystemOutput,
    grounding: Optional[GroundingMetrics] = None,
    judge: Optional[Judge] = None,
    policy: MatchingPolicy = DEFAULT_POLICY,
    usage: Optional[JudgeUsage] = None,
) -> AbstentionMetrics:
    """Compute abstention metrics for one benchmark item / system output pair.

    `unsupported_claim_rate` is read from `grounding` when the caller already
    computed it (no recomputation); otherwise this calls
    `grounding_metrics.evaluate_grounding` itself. It is `None` when grounding
    metrics are unavailable (see `grounding_metrics` for why that happens).
    """
    notes: List[str] = []

    abstained = detect_abstention(output.answer, judge, ABSTENTION_CUES)
    if abstained is None:
        notes.append(
            "abstention undecided: answer is empty/whitespace, no cue matched, "
            "and no judge verdict was available"
        )

    if item.answerable:
        correct_abstention: Optional[float] = None
        false_answer_rate: Optional[float] = None
        notes.append("item.answerable is True: correct_abstention/false_answer_rate not applicable")
    elif abstained is None:
        correct_abstention = None
        false_answer_rate = None
    else:
        correct_abstention = 1.0 if abstained else 0.0
        false_answer_rate = 0.0 if abstained else 1.0

    if grounding is not None:
        resolved_grounding = grounding
    else:
        resolved_grounding = evaluate_grounding(item, output, judge=judge, policy=policy, usage=usage)
        notes.append("grounding metrics computed locally (no precomputed GroundingMetrics passed)")

    unsupported_claim_rate = resolved_grounding.unsupported_claim_rate
    if unsupported_claim_rate is None:
        notes.extend(
            n for n in resolved_grounding.notes if "unsupported_claim_rate" in n
        )

    return AbstentionMetrics(
        correct_abstention=correct_abstention,
        false_answer_rate=false_answer_rate,
        unsupported_claim_rate=unsupported_claim_rate,
        abstained=abstained,
        notes=notes,
    )
