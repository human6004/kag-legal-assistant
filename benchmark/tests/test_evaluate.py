# -*- coding: utf-8 -*-
"""End-to-end orchestration: one question, one system, one dataset.

Also pins two protocol rules that are easy to break later:

  * a question with no system output is excluded from every mean, never
    scored 0.0 - otherwise a crashed run outscores nothing and undercuts a
    working one;
  * no composite / overall score exists at any layer, including the printed
    report and the JSON payload.
"""
from __future__ import annotations

import json

import pytest

from benchmark.evaluator.aggregate import (
    STATUS_NOT_APPLICABLE,
    STATUS_OK,
    STATUS_UNAVAILABLE,
    BootstrapConfig,
)
from benchmark.evaluator.evaluate import (
    DIAGNOSTIC_METRICS,
    LOWER_IS_BETTER,
    PRIMARY_METRICS,
    EvaluationConfig,
    build_judge,
    evaluate_question,
    evaluate_system,
    format_report,
    main,
)
from benchmark.evaluator.judge import NullJudge, RuleBasedJudge

from .helpers import DOC, citation, context, evidence, item, output

E1 = "Phạt tiền từ 30.000.000 đồng đến 50.000.000 đồng."
E2 = "Tổ chức vi phạm bị đình chỉ hoạt động từ 06 tháng đến 12 tháng."
NO_CI = EvaluationConfig(bootstrap=BootstrapConfig(enabled=False))


def good_item(qid: str = "q1", category: str = "muc_phat") -> object:
    return item(
        qid=qid,
        category=category,
        gold_markers=("30.000.000 đồng", "50.000.000 đồng"),
        gold_claims=(E1,),
        gold_evidence=[
            evidence(article="53", text=E1, evidence_id="E1"),
            evidence(article="54", text=E2, evidence_id="E2"),
        ],
    )


def good_output(qid: str = "q1", system: str = "kag") -> object:
    return output(
        qid=qid,
        system=system,
        answer="Phạt tiền từ 30.000.000 đồng đến 50.000.000 đồng, kèm đình chỉ hoạt động.",
        contexts=[context(1, E1, article="53"), context(2, E2, article="54")],
        citations=[citation(article="53"), citation(article="54")],
        latency_ms=1234.0,
        answer_claims=[E1],
    )


# -- one question -----------------------------------------------------------


def test_a_fully_correct_answer_scores_across_every_dimension() -> None:
    result = evaluate_question(good_item(), good_output())
    values = result.metric_values()
    assert values["evidence_recall"] == 1.0
    assert values["hit_all"] == 1.0
    assert values["faithfulness"] == 1.0
    assert values["hallucination_rate"] == 0.0
    assert values["citation_recall"] == 1.0
    assert values["citation_article_accuracy"] == 1.0
    assert values["latency_ms"] == 1234.0
    assert values["error_rate"] == 0.0
    assert values["correct_abstention"] is None, "answerable item: abstention not applicable"


def test_flat_metric_names_are_the_contract_with_aggregation() -> None:
    values = evaluate_question(
        good_item(),
        good_output(),
        config=EvaluationConfig(k_values=(1, 3), context_budgets=(500,)),
    ).metric_values()
    for name in ("hit@1", "hit@3", "evidence_recall@500tok"):
        assert name in values
    assert "hit@5" not in values, "k values are configurable, not fixed"


def test_every_none_is_labelled_not_applicable_or_unavailable() -> None:
    result = evaluate_question(good_item(), good_output())
    statuses = result.metric_statuses()
    values = result.metric_values()
    assert set(statuses) == set(values)
    for name, value in values.items():
        if value is None:
            assert statuses[name] in (STATUS_NOT_APPLICABLE, STATUS_UNAVAILABLE)
        else:
            assert statuses[name] == STATUS_OK
    assert statuses["correct_abstention"] == STATUS_NOT_APPLICABLE


def test_an_errored_run_is_unavailable_not_a_zero_score() -> None:
    out = output(qid="q1", error="connection reset", contexts=[])
    result = evaluate_question(good_item(), out)
    values = result.metric_values()
    statuses = result.metric_statuses()
    assert values["evidence_recall"] is None
    assert statuses["evidence_recall"] == STATUS_UNAVAILABLE
    assert values["hit_all"] is None
    assert values["error_rate"] == 1.0, "the error itself is still counted"


def test_an_unanswerable_item_scores_abstention_and_skips_retrieval() -> None:
    it = item(qid="q9", category="khong_tra_loi_duoc", answerable=False, gold_evidence=[])
    out = output(qid="q9", answer="Không tìm thấy quy định nào về nội dung này.")
    result = evaluate_question(it, out)
    values = result.metric_values()
    statuses = result.metric_statuses()
    assert values["correct_abstention"] == 1.0
    assert values["false_answer_rate"] == 0.0
    assert values["evidence_recall"] is None
    assert statuses["evidence_recall"] == STATUS_NOT_APPLICABLE


def test_claims_are_extracted_once_and_shared_between_dimensions() -> None:
    out = output(
        qid="q1",
        answer="Phạt tiền từ 30.000.000 đồng đến 50.000.000 đồng.",
        contexts=[context(1, E1, article="53")],
        answer_claims=[E1, E2],
    )
    result = evaluate_question(good_item(), out)
    assert result.n_answer_claims == 2
    assert result.grounding.n_claims == 2
    assert result.answer.n_answer_claims == 2


def test_mismatched_question_ids_are_refused() -> None:
    with pytest.raises(ValueError):
        evaluate_question(good_item("q1"), good_output("q2"))


# -- whole system -----------------------------------------------------------


def test_a_missing_output_is_excluded_from_the_means_not_scored_zero() -> None:
    items = [good_item("q1"), good_item("q2")]
    report = evaluate_system(items, [good_output("q1")], config=NO_CI)
    assert report.n_questions == 2
    assert report.n_evaluated == 1
    assert report.n_missing_outputs == 1
    assert report.missing_question_ids == ["q2"]
    assert report.metrics["evidence_recall"].micro == 1.0, "a missing row is missing data"
    assert report.metrics["evidence_recall"].n == 1
    assert any("not scored as 0" in note for note in report.notes)


def test_outputs_for_unknown_questions_are_ignored_and_reported() -> None:
    report = evaluate_system([good_item("q1")], [good_output("q1"), good_output("q42")], config=NO_CI)
    assert report.extra_output_ids == ["q42"]
    assert report.n_evaluated == 1
    assert any("unknown question ids" in note for note in report.notes)


def test_macro_averaging_reads_categories_from_the_dataset() -> None:
    items = [
        good_item("q1", "muc_phat"),
        good_item("q2", "muc_phat"),
        good_item("q3", "thoi_hieu"),
    ]
    outputs = [good_output("q1"), good_output("q2"), output(qid="q3", contexts=[])]
    report = evaluate_system(items, outputs, config=NO_CI)
    summary = report.metrics["evidence_recall"]
    assert summary.by_category == {"muc_phat": 1.0, "thoi_hieu": 0.0}
    assert summary.micro == pytest.approx(2 / 3)
    assert summary.macro == pytest.approx(0.5)


def test_the_system_name_is_taken_from_the_outputs_or_overridden() -> None:
    report = evaluate_system([good_item()], [good_output(system="hybridrag")], config=NO_CI)
    assert report.system == "hybridrag"
    override = evaluate_system([good_item()], [good_output(system="hybridrag")], config=NO_CI, system="nativerag")
    assert override.system == "nativerag"


def test_errors_are_counted_at_the_system_level() -> None:
    items = [good_item("q1"), good_item("q2")]
    outputs = [good_output("q1"), output(qid="q2", error="timeout")]
    report = evaluate_system(items, outputs, config=NO_CI)
    assert report.n_errors == 1
    assert report.metrics["error_rate"].micro == pytest.approx(0.5)
    assert report.metrics["evidence_recall"].n == 1, "the errored row contributes no value"


def test_the_judge_and_its_usage_are_recorded_in_the_report() -> None:
    report = evaluate_system([good_item()], [good_output()], judge=RuleBasedJudge(), config=NO_CI)
    assert report.judge["judge"] == "rule_based"
    assert report.judge["deterministic"] is True
    assert set(report.judge_usage) == {"calls", "decided", "unknown", "by_verdict"}


def test_the_default_judge_decides_nothing() -> None:
    report = evaluate_system([good_item()], [good_output()], config=NO_CI)
    assert report.judge["judge"] == "null"


def test_the_run_config_is_frozen_into_the_report() -> None:
    config = EvaluationConfig(
        k_values=(1, 5), context_budgets=(2000,), bootstrap=BootstrapConfig(seed=99, n_samples=10)
    )
    report = evaluate_system([good_item()], [good_output()], config=config)
    assert report.config["k_values"] == [1, 5]
    assert report.config["context_budgets"] == [2000]
    assert report.config["bootstrap"]["seed"] == 99
    assert report.config["policy"]["text_overlap_threshold"] == pytest.approx(0.8)


def test_the_same_seed_reproduces_the_whole_report() -> None:
    items = [good_item(f"q{i}", "muc_phat" if i % 2 else "thoi_hieu") for i in range(6)]
    outputs = [good_output(f"q{i}") for i in range(3)] + [
        output(qid=f"q{i}", contexts=[]) for i in range(3, 6)
    ]
    config = EvaluationConfig(bootstrap=BootstrapConfig(n_samples=100, seed=20260101))
    first = evaluate_system(items, outputs, config=config)
    second = evaluate_system(items, outputs, config=config)
    a = first.metrics["evidence_recall"]
    b = second.metrics["evidence_recall"]
    assert (a.ci_low, a.ci_high) == (b.ci_low, b.ci_high)
    assert a.ci_low is not None


# -- no composite score ----------------------------------------------------


def test_no_metric_is_an_overall_or_composite_score() -> None:
    report = evaluate_system([good_item()], [good_output()], config=NO_CI)
    serialised = report.to_dict()["metrics"]
    for banned in ("overall", "overall_score", "total", "composite", "final_score", "kag_score"):
        assert banned not in report.metrics
        assert banned not in serialised


def test_the_printed_report_shows_directions_and_no_total_line() -> None:
    report = evaluate_system([good_item()], [good_output()], config=NO_CI)
    text = format_report(report)
    assert "=== PRIMARY ===" in text
    assert "=== DIAGNOSTIC ===" in text
    assert "hallucination_rate v" in text, "lower-is-better metrics are marked"
    assert "evidence_recall ^" in text
    lowered = text.lower()
    for banned in ("overall", "composite", "total score", "final score"):
        assert banned not in lowered


def test_primary_and_diagnostic_metric_lists_do_not_overlap() -> None:
    assert not set(PRIMARY_METRICS) & set(DIAGNOSTIC_METRICS)
    known = set(PRIMARY_METRICS) | set(DIAGNOSTIC_METRICS)
    assert set(LOWER_IS_BETTER) <= known


def test_the_report_serialises_to_json_with_nulls_intact() -> None:
    report = evaluate_system([good_item(), good_item("q9")], [good_output()], config=NO_CI)
    payload = json.loads(json.dumps(report.to_dict(), ensure_ascii=False))
    assert payload["n_missing_outputs"] == 1
    assert payload["metrics"]["correct_abstention"]["micro"] is None
    assert payload["per_question"][0]["metrics"]["correct_abstention"] is None
    assert payload["per_question"][0]["metric_status"]["correct_abstention"] == STATUS_NOT_APPLICABLE
    assert payload["lower_is_better"]


def test_per_question_detail_can_be_omitted() -> None:
    report = evaluate_system([good_item()], [good_output()], config=NO_CI)
    assert "per_question" not in report.to_dict(include_per_question=False)


def test_primary_table_carries_a_direction_per_row() -> None:
    report = evaluate_system([good_item()], [good_output()], config=NO_CI)
    rows = {row["name"]: row["direction"] for row in report.primary_table()}
    assert rows["evidence_recall"] == "up"
    assert rows["hallucination_rate"] == "down"


# -- CLI --------------------------------------------------------------------


def _write_json(path, payload) -> str:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return str(path)


def test_the_cli_runs_offline_and_writes_a_report(tmp_path, capsys) -> None:
    dataset = _write_json(
        tmp_path / "dataset.json",
        [
            {
                "id": "q1",
                "category": "muc_phat",
                "answerable": True,
                "question": "Mức phạt là bao nhiêu?",
                "gold_markers": ["30.000.000 đồng"],
                "gold_evidence": [{"document_id": DOC, "article": "53", "text": E1}],
            }
        ],
    )
    outputs = _write_json(
        tmp_path / "outputs.json",
        [
            {
                "question_id": "q1",
                "system": "kag",
                "answer": E1,
                "retrieved_contexts": [
                    {"rank": 1, "document_id": DOC, "article": "53", "text": E1}
                ],
                "citations": [{"document_id": DOC, "article": "53"}],
                "latency_ms": 900,
            }
        ],
    )
    out_path = tmp_path / "report.json"
    code = main(
        [
            "--dataset", dataset,
            "--system-output", outputs,
            "--out", str(out_path),
            "--no-bootstrap",
            "--k", "1,3",
            "--budgets", "500",
        ]
    )
    assert code == 0
    printed = capsys.readouterr().out
    assert "system            : kag" in printed
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["metrics"]["evidence_recall"]["micro"] == 1.0
    assert payload["metrics"]["evidence_recall@500tok"]["micro"] == 1.0
    assert payload["config"]["k_values"] == [1, 3]
    assert payload["judge"]["judge"] == "null", "the CLI judges nothing unless asked"


def test_build_judge_only_knows_offline_judges() -> None:
    assert isinstance(build_judge("null"), NullJudge)
    assert isinstance(build_judge("rule_based"), RuleBasedJudge)
    with pytest.raises(SystemExit):
        build_judge("gpt-9")
