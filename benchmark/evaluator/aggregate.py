# -*- coding: utf-8 -*-
"""Aggregation of per-question metric values into reportable summaries.

This module takes the per-question metric values produced elsewhere in the
evaluator (retrieval metrics, evidence matching, judge scores, ...) and turns
them into `MetricSummary` objects: micro/macro means, per-category breakdowns,
and bootstrap confidence intervals.

Two averaging modes are computed for every metric:

  * micro - the plain mean over every question that has a real (non-None)
    value for that metric. A question whose value is `None` is excluded from
    the mean; it is instead counted as `n_not_applicable` or `n_unavailable`,
    read from that question's `statuses` mapping (a `None` value with no
    corresponding status entry is treated as `STATUS_UNAVAILABLE`, since the
    absence of a status is itself missing information, not a deliberate
    "not applicable" judgement).
  * macro - the mean, over categories, of each category's micro mean. A
    category that contributed no real value to a metric is skipped entirely
    (it does not count as a zero and does not appear in the denominator).
    This keeps a category with many questions from swamping a category with
    few. Categories are read from the `QuestionMetrics` records themselves;
    this module never hard-codes a category list or an expected dataset size.

There is deliberately NO composite/overall score anywhere in this module. Do
not add one: the benchmark protocol forbids averaging across metrics (e.g.
averaging a retrieval metric with a judge score) because they are not on a
comparable scale and doing so would hide which capability is actually weak.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

STATUS_OK = "ok"
STATUS_NOT_APPLICABLE = "not_applicable"
STATUS_UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class QuestionMetrics:
    """One question's metric values, ready for aggregation.

    `values` maps metric name -> value (or None if the metric could not be
    computed for this question). `statuses` maps metric name -> one of
    `STATUS_OK` / `STATUS_NOT_APPLICABLE` / `STATUS_UNAVAILABLE`, explaining a
    `None` value (a metric that legitimately does not apply to this question,
    e.g. an evidence metric on an unanswerable question, versus one that
    could not be computed, e.g. a judge call that errored). A metric name
    present in `values` with a real value need not appear in `statuses`.
    """

    question_id: str
    category: str
    values: Mapping[str, Optional[float]]
    statuses: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class BootstrapConfig:
    """Configuration for the percentile bootstrap used by `bootstrap_ci`."""

    n_samples: int = 1000
    confidence: float = 0.95
    seed: int = 20260101
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n_samples": self.n_samples,
            "confidence": self.confidence,
            "seed": self.seed,
            "enabled": self.enabled,
        }


@dataclass(frozen=True)
class MetricSummary:
    """The reportable summary for one metric across all questions."""

    name: str
    micro: Optional[float]
    macro: Optional[float]
    n: int
    n_not_applicable: int
    n_unavailable: int
    ci_low: Optional[float]
    ci_high: Optional[float]
    by_category: Dict[str, Optional[float]]
    category_counts: Dict[str, int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "micro": self.micro,
            "macro": self.macro,
            "n": self.n,
            "n_not_applicable": self.n_not_applicable,
            "n_unavailable": self.n_unavailable,
            "ci_low": self.ci_low,
            "ci_high": self.ci_high,
            "by_category": dict(self.by_category),
            "category_counts": dict(self.category_counts),
        }


def _percentile(sorted_values: Sequence[float], pct: float) -> float:
    """Linear-interpolation percentile, matching numpy's default method.

    `sorted_values` must already be sorted ascending. `pct` is in [0, 100].
    """
    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]
    rank = (pct / 100.0) * (n - 1)
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return sorted_values[int(rank)]
    frac = rank - lo
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * frac


def bootstrap_ci(
    values: Sequence[float], config: BootstrapConfig = BootstrapConfig()
) -> Tuple[Optional[float], Optional[float]]:
    """Percentile bootstrap confidence interval over pooled per-question values.

    Resamples `len(values)` values with replacement, `config.n_samples`
    times, takes the mean of each resample, then reports the
    `(1-confidence)/2` and `(1+confidence)/2` percentiles of those resample
    means.

    Reproducible by construction: a fresh `random.Random(config.seed)` is
    created inside this call and used for every draw. The global `random`
    module state is never touched, so two calls with the same seed and the
    same `values` (in the same order) return byte-identical bounds,
    regardless of what else in the process has consumed randomness.

    Returns `(None, None)` when `config.enabled` is False, when `values` is
    empty, or when `len(values) < 2` - a confidence interval computed from a
    single point is meaningless (every resample would just be that one value
    repeated), so this case is refused rather than silently returning a
    degenerate (x, x) interval.
    """
    if not config.enabled:
        return (None, None)
    n = len(values)
    if n < 2:
        return (None, None)

    rng = random.Random(config.seed)
    pool = list(values)
    means: List[float] = []
    for _ in range(config.n_samples):
        resample = [pool[rng.randrange(n)] for _ in range(n)]
        means.append(sum(resample) / n)

    means.sort()
    alpha = (1.0 - config.confidence) / 2.0
    lo = _percentile(means, alpha * 100.0)
    hi = _percentile(means, (1.0 - alpha) * 100.0)
    return (lo, hi)


def _status_for(record: QuestionMetrics, metric: str) -> str:
    status = record.statuses.get(metric)
    if status:
        return status
    return STATUS_UNAVAILABLE


def aggregate(
    records: Sequence[QuestionMetrics],
    metric_names: Optional[Sequence[str]] = None,
    bootstrap: BootstrapConfig = BootstrapConfig(),
) -> Dict[str, MetricSummary]:
    """Aggregate per-question metric values into one `MetricSummary` per metric.

    `metric_names` defaults to the union of keys across every record's
    `values`, sorted, so a new metric is picked up automatically and never
    needs registration here.

    The confidence interval attached to each summary is computed by
    `bootstrap_ci` over the same pooled per-question values used for micro.
    The macro mean is never bootstrapped: resampling fairly across unequal
    category sizes needs a stratified resampling design (resample within
    each category, then average), which this function does not implement.
    Reporting a plain bootstrap CI next to macro would misrepresent its
    uncertainty, so `MetricSummary.ci_low`/`ci_high` should be read as
    belonging to micro only.
    """
    if metric_names is None:
        names: List[str] = sorted({name for r in records for name in r.values})
    else:
        names = list(metric_names)

    summaries: Dict[str, MetricSummary] = {}
    for name in names:
        micro_values: List[float] = []
        n_not_applicable = 0
        n_unavailable = 0

        # category -> list of values contributed by that category
        by_category_values: Dict[str, List[float]] = {}
        category_counts: Dict[str, int] = {}

        for record in records:
            category_counts.setdefault(record.category, 0)
            if name not in record.values:
                continue
            value = record.values[name]
            if value is None:
                status = _status_for(record, name)
                if status == STATUS_NOT_APPLICABLE:
                    n_not_applicable += 1
                else:
                    n_unavailable += 1
                continue
            micro_values.append(value)
            category_counts[record.category] += 1
            by_category_values.setdefault(record.category, []).append(value)

        micro = sum(micro_values) / len(micro_values) if micro_values else None

        by_category: Dict[str, Optional[float]] = {}
        category_micros: List[float] = []
        for category, values in by_category_values.items():
            cat_mean = sum(values) / len(values)
            by_category[category] = cat_mean
            category_micros.append(cat_mean)
        # Categories that contributed nothing still get an entry (None) so
        # every category present in the input is visible in the report.
        for record in records:
            by_category.setdefault(record.category, None)

        macro = sum(category_micros) / len(category_micros) if category_micros else None

        ci_low, ci_high = bootstrap_ci(micro_values, bootstrap)

        summaries[name] = MetricSummary(
            name=name,
            micro=micro,
            macro=macro,
            n=len(micro_values),
            n_not_applicable=n_not_applicable,
            n_unavailable=n_unavailable,
            ci_low=ci_low,
            ci_high=ci_high,
            by_category=by_category,
            category_counts=category_counts,
        )

    return summaries


def summaries_to_dict(summaries: Mapping[str, MetricSummary]) -> Dict[str, Any]:
    """Convert a name -> `MetricSummary` mapping into a plain JSON-able dict."""
    return {name: summary.to_dict() for name, summary in summaries.items()}
