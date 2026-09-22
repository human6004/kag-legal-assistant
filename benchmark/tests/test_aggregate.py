# -*- coding: utf-8 -*-
"""Aggregation and bootstrap confidence intervals.

MANDATORY CASE 9  - categories of unequal size: micro and macro must differ,
                    and macro must not let the big category swamp the small one.
MANDATORY CASE 10 - the same seed must produce the same CI bounds, every run.
"""
from __future__ import annotations

import pytest

from benchmark.evaluator.aggregate import (
    STATUS_NOT_APPLICABLE,
    STATUS_OK,
    STATUS_UNAVAILABLE,
    BootstrapConfig,
    QuestionMetrics,
    aggregate,
    bootstrap_ci,
    summaries_to_dict,
)

NO_CI = BootstrapConfig(enabled=False)


def record(qid: str, category: str, value=None, status=None, metric: str = "evidence_recall"):
    statuses = {metric: status} if status is not None else {}
    return QuestionMetrics(question_id=qid, category=category, values={metric: value}, statuses=statuses)


# -- MANDATORY CASE 9: unequal category sizes ------------------------------


def test_micro_and_macro_differ_when_categories_have_unequal_sizes() -> None:
    records = [
        # big category, 4 questions, all wrong
        *[record(f"b{i}", "muc_phat", 0.0) for i in range(4)],
        # small category, 1 question, right
        record("s1", "thoi_hieu", 1.0),
    ]
    summary = aggregate(records, bootstrap=NO_CI)["evidence_recall"]
    assert summary.micro == pytest.approx(0.2), "1 of 5 questions scored"
    assert summary.macro == pytest.approx(0.5), "1 of 2 categories scored"
    assert summary.micro != summary.macro
    assert summary.by_category == {"muc_phat": 0.0, "thoi_hieu": 1.0}
    assert summary.category_counts == {"muc_phat": 4, "thoi_hieu": 1}


def test_macro_weights_each_category_once_regardless_of_size() -> None:
    records = [
        *[record(f"b{i}", "muc_phat", 1.0) for i in range(9)],
        record("s1", "thoi_hieu", 0.0),
    ]
    summary = aggregate(records, bootstrap=NO_CI)["evidence_recall"]
    assert summary.micro == pytest.approx(0.9)
    assert summary.macro == pytest.approx(0.5)


def test_categories_are_read_from_the_data_not_hard_coded() -> None:
    records = [record("q1", "mot_hang_muc_moi", 1.0), record("q2", "khac_hoan_toan", 0.0)]
    summary = aggregate(records, bootstrap=NO_CI)["evidence_recall"]
    assert sorted(summary.by_category) == ["khac_hoan_toan", "mot_hang_muc_moi"]


def test_dataset_size_is_whatever_was_passed_in() -> None:
    """No expectation of 150 questions, or of any particular count."""
    for n in (1, 3, 17):
        records = [record(f"q{i}", "muc_phat", 1.0) for i in range(n)]
        assert aggregate(records, bootstrap=NO_CI)["evidence_recall"].n == n


def test_metric_names_are_discovered_automatically() -> None:
    records = [
        QuestionMetrics("q1", "muc_phat", {"evidence_recall": 1.0, "mrr": 0.5}),
        QuestionMetrics("q2", "muc_phat", {"evidence_recall": 0.0, "faithfulness": 1.0}),
    ]
    summaries = aggregate(records, bootstrap=NO_CI)
    assert sorted(summaries) == ["evidence_recall", "faithfulness", "mrr"]
    assert summaries["mrr"].n == 1, "a metric only one question reported still aggregates"


def test_explicit_metric_names_restrict_the_output() -> None:
    records = [QuestionMetrics("q1", "muc_phat", {"evidence_recall": 1.0, "mrr": 0.5})]
    summaries = aggregate(records, metric_names=["mrr"], bootstrap=NO_CI)
    assert list(summaries) == ["mrr"]


# -- None is never a zero ---------------------------------------------------


def test_none_values_are_excluded_from_the_mean_and_counted_by_reason() -> None:
    records = [
        record("q1", "muc_phat", 1.0, STATUS_OK),
        record("q2", "muc_phat", None, STATUS_NOT_APPLICABLE),
        record("q3", "muc_phat", None, STATUS_UNAVAILABLE),
    ]
    summary = aggregate(records, bootstrap=NO_CI)["evidence_recall"]
    assert summary.micro == 1.0, "a None must not drag the mean down like a 0.0 would"
    assert summary.n == 1
    assert summary.n_not_applicable == 1
    assert summary.n_unavailable == 1


def test_an_unlabelled_none_is_treated_as_unavailable_not_not_applicable() -> None:
    summary = aggregate([record("q1", "muc_phat", None)], bootstrap=NO_CI)["evidence_recall"]
    assert summary.n_unavailable == 1
    assert summary.n_not_applicable == 0


def test_a_metric_with_no_real_values_reports_none_not_zero() -> None:
    records = [record("q1", "muc_phat", None, STATUS_NOT_APPLICABLE)]
    summary = aggregate(records, bootstrap=NO_CI)["evidence_recall"]
    assert summary.micro is None
    assert summary.macro is None
    assert summary.ci_low is None and summary.ci_high is None


def test_a_category_that_contributed_nothing_shows_as_none_not_zero() -> None:
    records = [
        record("q1", "muc_phat", 1.0),
        record("q2", "thoi_hieu", None, STATUS_NOT_APPLICABLE),
    ]
    summary = aggregate(records, bootstrap=NO_CI)["evidence_recall"]
    assert summary.by_category == {"muc_phat": 1.0, "thoi_hieu": None}
    assert summary.macro == 1.0, "an empty category is skipped, not counted as 0"


def test_an_explicit_zero_is_kept_as_a_zero() -> None:
    summary = aggregate([record("q1", "muc_phat", 0.0, STATUS_OK)], bootstrap=NO_CI)["evidence_recall"]
    assert summary.micro == 0.0
    assert summary.n == 1
    assert summary.n_unavailable == 0


# -- MANDATORY CASE 10: reproducible bootstrap ------------------------------


def test_the_same_seed_gives_the_same_ci_bounds() -> None:
    values = [0.0, 0.25, 0.5, 0.5, 0.75, 1.0, 1.0, 0.5, 0.25, 0.0]
    config = BootstrapConfig(n_samples=200, seed=20260101)
    first = bootstrap_ci(values, config)
    second = bootstrap_ci(values, config)
    assert first == second
    assert first[0] is not None and first[1] is not None
    assert first[0] <= sum(values) / len(values) <= first[1]


def test_a_different_seed_gives_different_bounds() -> None:
    values = [0.0, 0.25, 0.5, 0.75, 1.0, 0.5, 0.25, 0.0, 1.0, 0.5]
    a = bootstrap_ci(values, BootstrapConfig(n_samples=200, seed=1))
    b = bootstrap_ci(values, BootstrapConfig(n_samples=200, seed=2))
    assert a != b


def test_the_bootstrap_does_not_depend_on_global_random_state() -> None:
    import random as _random

    values = [0.0, 0.5, 1.0, 0.5, 0.25]
    config = BootstrapConfig(n_samples=100, seed=7)
    baseline = bootstrap_ci(values, config)
    _random.seed(999)
    _random.random()
    assert bootstrap_ci(values, config) == baseline


def test_aggregate_is_reproducible_end_to_end_with_a_fixed_seed() -> None:
    records = [record(f"q{i}", "muc_phat" if i % 2 else "thoi_hieu", i / 10.0) for i in range(10)]
    config = BootstrapConfig(n_samples=150, seed=20260101)
    first = aggregate(records, bootstrap=config)["evidence_recall"]
    second = aggregate(records, bootstrap=config)["evidence_recall"]
    assert (first.ci_low, first.ci_high) == (second.ci_low, second.ci_high)


def test_sample_count_is_configurable() -> None:
    values = [0.0, 0.5, 1.0, 0.5]
    few = bootstrap_ci(values, BootstrapConfig(n_samples=10, seed=3))
    many = bootstrap_ci(values, BootstrapConfig(n_samples=1000, seed=3))
    assert few != many, "more resamples must actually change the estimate"


def test_a_single_value_gets_no_interval() -> None:
    assert bootstrap_ci([0.5]) == (None, None)
    assert bootstrap_ci([]) == (None, None)


def test_the_bootstrap_can_be_switched_off() -> None:
    assert bootstrap_ci([0.0, 1.0], BootstrapConfig(enabled=False)) == (None, None)


def test_a_constant_sample_gives_a_degenerate_but_honest_interval() -> None:
    lo, hi = bootstrap_ci([1.0, 1.0, 1.0], BootstrapConfig(n_samples=50, seed=5))
    assert lo == 1.0 and hi == 1.0


def test_confidence_level_widens_the_interval() -> None:
    values = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    narrow = bootstrap_ci(values, BootstrapConfig(n_samples=500, seed=11, confidence=0.5))
    wide = bootstrap_ci(values, BootstrapConfig(n_samples=500, seed=11, confidence=0.95))
    assert wide[0] <= narrow[0] and wide[1] >= narrow[1]


# -- no composite score ----------------------------------------------------


def test_aggregate_never_invents_an_overall_score() -> None:
    records = [
        QuestionMetrics("q1", "muc_phat", {"evidence_recall": 1.0, "faithfulness": 0.0}),
    ]
    summaries = aggregate(records, bootstrap=NO_CI)
    assert sorted(summaries) == ["evidence_recall", "faithfulness"]
    for banned in ("overall", "overall_score", "total", "score", "composite", "kag_score"):
        assert banned not in summaries


def test_summaries_to_dict_is_json_shaped_and_keeps_nulls() -> None:
    import json

    records = [record("q1", "muc_phat", 1.0), record("q2", "thoi_hieu", None, STATUS_NOT_APPLICABLE)]
    payload = summaries_to_dict(aggregate(records, bootstrap=NO_CI))
    round_tripped = json.loads(json.dumps(payload))
    entry = round_tripped["evidence_recall"]
    assert entry["micro"] == 1.0
    assert entry["ci_low"] is None
    assert entry["by_category"]["thoi_hieu"] is None
    assert entry["n_not_applicable"] == 1
