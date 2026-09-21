# -*- coding: utf-8 -*-
"""Top-level evaluation: one question at a time, then aggregation.

This module wires the metric dimensions together and nothing else. It holds no
metric formula of its own, and it deliberately produces **no composite score**:
retrieval, answer correctness, grounding, citation and abstention are reported
side by side because they trade off against each other, and averaging them
would hide exactly the behaviour the paper is about.

Metric naming is flat and stable, because the aggregation layer and the paper
tables key on these strings:

    retrieval   evidence_recall, evidence_recall_required, context_precision,
                mrr, hit@1, hit@3, hit@5, hit@10, evidence_recall@<N>tok
    answer      hit_rate, hit_all, claim_precision, claim_recall, claim_f1
    grounding   faithfulness, hallucination_rate, retrieval_gap_rate,
                unsupported_claim_rate
    citation    citation_document_accuracy, citation_article_accuracy,
                citation_clause_accuracy, citation_point_accuracy,
                citation_precision, citation_recall
    abstention  correct_abstention, false_answer_rate
    operational latency_ms, error_rate

Every metric may be `None`, and `None` is not zero. Each `None` is labelled
either `not_applicable` (the ground truth does not pose that question - an
answerable item has no abstention score, an item with empty gold evidence has
no Evidence Recall) or `unavailable` (the question applies but could not be
decided - the system errored, or a judge-dependent metric ran with a judge that
decides nothing). The aggregation layer counts both separately.

CLI:

    python -m benchmark.evaluator.evaluate \
        --dataset benchmark/data/dev.json \
        --system-output runs/kag_dev.json \
        --out runs/kag_dev_report.json
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .abstention_metrics import AbstentionMetrics, evaluate_abstention
from .aggregate import (
    STATUS_NOT_APPLICABLE,
    STATUS_OK,
    STATUS_UNAVAILABLE,
    BootstrapConfig,
    MetricSummary,
    QuestionMetrics,
    aggregate,
    summaries_to_dict,
)
from .answer_metrics import AnswerMetrics, answer_claims, evaluate_answer
from .citation_metrics import CitationMetrics, evaluate_citations
from .evidence_matching import DEFAULT_POLICY, MatchingPolicy, default_token_counter
from .grounding_metrics import GroundingMetrics, evaluate_grounding
from .judge import Judge, JudgeUsage, NullJudge, RuleBasedJudge
from .models import (
    BenchmarkItem,
    SystemOutput,
    index_outputs,
    load_benchmark,
    load_system_outputs,
)
from .retrieval_metrics import (
    DEFAULT_K_VALUES,
    RetrievalMetrics,
    evaluate_retrieval,
)

# Metrics that go into the paper's main table. Diagnostics are still computed
# and reported; this list only says which rows are headline rows.
PRIMARY_METRICS: Tuple[str, ...] = (
    "evidence_recall",
    "context_precision",
    "mrr",
    "claim_f1",
    "hit_all",
    "faithfulness",
    "hallucination_rate",
    "citation_precision",
    "citation_recall",
    "correct_abstention",
)

DIAGNOSTIC_METRICS: Tuple[str, ...] = (
    "hit@1",
    "hit@3",
    "hit@5",
    "hit@10",
    "hit_rate",
    "claim_precision",
    "claim_recall",
    "evidence_recall_required",
    "retrieval_gap_rate",
    "unsupported_claim_rate",
    "citation_document_accuracy",
    "citation_article_accuracy",
    "citation_clause_accuracy",
    "citation_point_accuracy",
    "false_answer_rate",
    "latency_ms",
    "error_rate",
)

#: Metrics where a lower number is better. Kept here so report readers and
#: table generators do not have to guess.
LOWER_IS_BETTER: Tuple[str, ...] = (
    "hallucination_rate",
    "retrieval_gap_rate",
    "unsupported_claim_rate",
    "false_answer_rate",
    "latency_ms",
    "error_rate",
)


@dataclass(frozen=True)
class EvaluationConfig:
    """Run configuration. Freeze this next to the results."""

    k_values: Tuple[int, ...] = tuple(DEFAULT_K_VALUES)
    #: Context-token budgets for the equal-budget recall comparison. Empty by
    #: default: no single budget is privileged, the caller chooses (e.g. 2000,
    #: 4000) and the same budgets are used for every system in a comparison.
    context_budgets: Tuple[int, ...] = ()
    policy: MatchingPolicy = DEFAULT_POLICY
    bootstrap: BootstrapConfig = BootstrapConfig()
    token_counter: Callable[[Optional[str]], int] = default_token_counter

    def to_dict(self) -> Dict[str, Any]:
        return {
            "k_values": list(self.k_values),
            "context_budgets": list(self.context_budgets),
            "policy": {
                "text_overlap_threshold": self.policy.text_overlap_threshold,
                "use_structural": self.policy.use_structural,
                "use_text": self.policy.use_text,
                "use_judge": self.policy.use_judge,
                "undecided_counts_as": self.policy.undecided_counts_as,
                "coarse_metadata_counts": self.policy.coarse_metadata_counts,
                "verify_text_when_available": self.policy.verify_text_when_available,
            },
            "bootstrap": self.bootstrap.to_dict(),
            "token_counter": getattr(self.token_counter, "__name__", str(self.token_counter)),
        }


@dataclass(frozen=True)
class QuestionResult:
    """Everything measured for one (question, system) pair."""

    question_id: str
    category: str
    answerable: bool
    system: str
    error: Optional[str]
    latency_ms: Optional[float]
    n_answer_claims: Optional[int]
    retrieval: RetrievalMetrics
    answer: AnswerMetrics
    grounding: GroundingMetrics
    citation: CitationMetrics
    abstention: AbstentionMetrics

    # -- flat metric view ------------------------------------------------
    def metric_values(self) -> Dict[str, Optional[float]]:
        values: Dict[str, Optional[float]] = {
            "evidence_recall": self.retrieval.evidence_recall,
            "evidence_recall_required": self.retrieval.evidence_recall_required,
            "context_precision": self.retrieval.context_precision,
            "mrr": self.retrieval.mrr,
            "hit_rate": self.answer.hit_rate,
            "hit_all": self.answer.hit_all,
            "claim_precision": self.answer.claim_precision,
            "claim_recall": self.answer.claim_recall,
            "claim_f1": self.answer.claim_f1,
            "faithfulness": self.grounding.faithfulness,
            "hallucination_rate": self.grounding.hallucination_rate,
            "retrieval_gap_rate": self.grounding.retrieval_gap_rate,
            "unsupported_claim_rate": self.grounding.unsupported_claim_rate,
            "citation_document_accuracy": self.citation.document_accuracy,
            "citation_article_accuracy": self.citation.article_accuracy,
            "citation_clause_accuracy": self.citation.clause_accuracy,
            "citation_point_accuracy": self.citation.point_accuracy,
            "citation_precision": self.citation.citation_precision,
            "citation_recall": self.citation.citation_recall,
            "correct_abstention": self.abstention.correct_abstention,
            "false_answer_rate": self.abstention.false_answer_rate,
            "latency_ms": self.latency_ms,
            "error_rate": 1.0 if self.error else 0.0,
        }
        for k, v in sorted(self.retrieval.hit_at_k.items()):
            values[f"hit@{k}"] = v
        for budget, v in sorted(self.retrieval.budget_evidence_recall.items()):
            values[f"evidence_recall@{budget}tok"] = v
        return values

    def metric_statuses(self) -> Dict[str, str]:
        """Label every `None` as not_applicable or unavailable.

        `not_applicable` means the ground truth does not pose the question.
        `unavailable` means it does, but the run could not answer it.
        """
        has_gold_evidence = self.retrieval.n_gold_evidence > 0
        has_required_evidence = self.retrieval.n_required_evidence > 0
        has_markers = self.answer.n_gold_markers > 0
        has_gold_claims = self.answer.n_gold_claims > 0
        has_gold_material = has_gold_evidence or has_gold_claims
        has_citations = self.citation.n_citations > 0
        errored = bool(self.error)

        applicable: Dict[str, bool] = {
            "evidence_recall": has_gold_evidence,
            "evidence_recall_required": has_required_evidence,
            "context_precision": has_gold_material,
            "mrr": has_gold_evidence,
            "hit_rate": has_markers,
            "hit_all": has_markers,
            "claim_precision": has_gold_material,
            "claim_recall": has_gold_claims,
            "claim_f1": has_gold_material and has_gold_claims,
            "faithfulness": True,
            "hallucination_rate": has_gold_material,
            "retrieval_gap_rate": has_gold_material,
            "unsupported_claim_rate": has_gold_material,
            "citation_document_accuracy": has_citations,
            "citation_article_accuracy": has_citations,
            "citation_clause_accuracy": has_citations,
            "citation_point_accuracy": has_citations,
            "citation_precision": has_citations,
            "citation_recall": has_required_evidence,
            "correct_abstention": not self.answerable,
            "false_answer_rate": not self.answerable,
            "latency_ms": True,
            "error_rate": True,
        }
        for k in self.retrieval.hit_at_k:
            applicable[f"hit@{k}"] = has_gold_evidence
        for budget in self.retrieval.budget_evidence_recall:
            applicable[f"evidence_recall@{budget}tok"] = has_gold_evidence

        statuses: Dict[str, str] = {}
        for name, value in self.metric_values().items():
            if value is not None:
                statuses[name] = STATUS_OK
            elif not applicable.get(name, True):
                statuses[name] = STATUS_NOT_APPLICABLE
            elif errored:
                statuses[name] = STATUS_UNAVAILABLE
            else:
                statuses[name] = STATUS_UNAVAILABLE
        return statuses

    def as_question_metrics(self) -> QuestionMetrics:
        return QuestionMetrics(
            question_id=self.question_id,
            category=self.category,
            values=self.metric_values(),
            statuses=self.metric_statuses(),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question_id": self.question_id,
            "category": self.category,
            "answerable": self.answerable,
            "system": self.system,
            "error": self.error,
            "latency_ms": self.latency_ms,
            "n_answer_claims": self.n_answer_claims,
            "metrics": self.metric_values(),
            "metric_status": self.metric_statuses(),
            "retrieval": self.retrieval.to_dict(),
            "answer": self.answer.to_dict(),
            "grounding": self.grounding.to_dict(),
            "citation": self.citation.to_dict(),
            "abstention": self.abstention.to_dict(),
        }


def evaluate_question(
    item: BenchmarkItem,
    output: SystemOutput,
    judge: Optional[Judge] = None,
    config: EvaluationConfig = EvaluationConfig(),
    usage: Optional[JudgeUsage] = None,
) -> QuestionResult:
    """Run every dimension for one question.

    Claims are extracted once and shared, so the grounding and citation
    dimensions judge the same claim list the answer dimension scored.
    """
    if item.id != output.question_id:
        raise ValueError(
            f"output is for question {output.question_id!r}, not {item.id!r}"
        )
    judge = judge if judge is not None else NullJudge()
    claims = answer_claims(output, judge)

    retrieval = evaluate_retrieval(
        item,
        output,
        judge=judge,
        policy=config.policy,
        k_values=config.k_values,
        budgets=config.context_budgets,
        token_counter=config.token_counter,
        usage=usage,
    )
    answer = evaluate_answer(item, output, judge=judge, policy=config.policy, usage=usage)
    grounding = evaluate_grounding(
        item, output, claims=claims, judge=judge, policy=config.policy, usage=usage
    )
    citation = evaluate_citations(
        item, output, claims=claims, judge=judge, policy=config.policy, usage=usage
    )
    abstention = evaluate_abstention(
        item,
        output,
        grounding=grounding,
        judge=judge,
        policy=config.policy,
        usage=usage,
    )
    return QuestionResult(
        question_id=item.id,
        category=item.category,
        answerable=item.answerable,
        system=output.system,
        error=output.error,
        latency_ms=output.latency_ms,
        n_answer_claims=len(claims) if claims is not None else None,
        retrieval=retrieval,
        answer=answer,
        grounding=grounding,
        citation=citation,
        abstention=abstention,
    )


@dataclass(frozen=True)
class SystemReport:
    """Aggregated result for one system over one dataset."""

    system: str
    n_questions: int
    n_evaluated: int
    n_missing_outputs: int
    n_errors: int
    missing_question_ids: List[str] = field(default_factory=list)
    extra_output_ids: List[str] = field(default_factory=list)
    metrics: Dict[str, MetricSummary] = field(default_factory=dict)
    per_question: List[QuestionResult] = field(default_factory=list)
    judge: Dict[str, Any] = field(default_factory=dict)
    judge_usage: Dict[str, Any] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def primary_table(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for name in PRIMARY_METRICS:
            summary = self.metrics.get(name)
            if summary is None:
                continue
            row = summary.to_dict()
            row["direction"] = "down" if name in LOWER_IS_BETTER else "up"
            rows.append(row)
        return rows

    def to_dict(self, include_per_question: bool = True) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "system": self.system,
            "n_questions": self.n_questions,
            "n_evaluated": self.n_evaluated,
            "n_missing_outputs": self.n_missing_outputs,
            "n_errors": self.n_errors,
            "missing_question_ids": list(self.missing_question_ids),
            "extra_output_ids": list(self.extra_output_ids),
            "primary_metrics": list(PRIMARY_METRICS),
            "diagnostic_metrics": list(DIAGNOSTIC_METRICS),
            "lower_is_better": list(LOWER_IS_BETTER),
            "metrics": summaries_to_dict(self.metrics),
            "judge": self.judge,
            "judge_usage": self.judge_usage,
            "config": self.config,
            "notes": list(self.notes),
        }
        if include_per_question:
            out["per_question"] = [q.to_dict() for q in self.per_question]
        return out


def evaluate_system(
    items: Sequence[BenchmarkItem],
    outputs: Sequence[SystemOutput],
    judge: Optional[Judge] = None,
    config: EvaluationConfig = EvaluationConfig(),
    system: Optional[str] = None,
) -> SystemReport:
    """Evaluate one system over a dataset and aggregate.

    Questions with no output are counted in `n_missing_outputs` and left out of
    every mean: a missing row is missing data, and silently scoring it 0 would
    make a crashed run look like a wrong answer. Rows whose `error` is set stay
    in the report (error_rate counts them) but their judge-dependent metrics are
    `unavailable`.
    """
    judge = judge if judge is not None else NullJudge()
    usage = JudgeUsage()
    by_id = index_outputs(outputs)
    item_ids = {item.id for item in items}

    results: List[QuestionResult] = []
    missing: List[str] = []
    systems: Dict[str, int] = {}
    for item in items:
        output = by_id.get(item.id)
        if output is None:
            missing.append(item.id)
            continue
        systems[output.system] = systems.get(output.system, 0) + 1
        results.append(evaluate_question(item, output, judge=judge, config=config, usage=usage))

    notes: List[str] = []
    if missing:
        notes.append(
            f"{len(missing)} question(s) had no system output and were excluded "
            f"from every mean (not scored as 0)"
        )
    extra = sorted(set(by_id) - item_ids)
    if extra:
        notes.append(f"{len(extra)} output(s) referenced unknown question ids and were ignored")
    if len(systems) > 1:
        notes.append(f"outputs mix several system names: {sorted(systems)}")

    name = system or (max(systems, key=lambda s: systems[s]) if systems else "unknown")
    summaries = aggregate(
        [r.as_question_metrics() for r in results], bootstrap=config.bootstrap
    )
    return SystemReport(
        system=name,
        n_questions=len(items),
        n_evaluated=len(results),
        n_missing_outputs=len(missing),
        n_errors=sum(1 for r in results if r.error),
        missing_question_ids=missing,
        extra_output_ids=extra,
        metrics=summaries,
        per_question=results,
        judge=judge.describe(),
        judge_usage=usage.to_dict(),
        config=config.to_dict(),
        notes=notes,
    )


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

JUDGE_FACTORIES: Dict[str, Callable[[], Judge]] = {
    "null": NullJudge,
    "rule_based": RuleBasedJudge,
}


def build_judge(name: str) -> Judge:
    """Build one of the offline judges by name.

    A real LLM judge is an adapter outside this package; point at it from your
    own script and pass the instance to `evaluate_system`. Keeping vendors out
    of here is what lets the evaluator be imported with no API key.
    """
    try:
        return JUDGE_FACTORIES[name]()
    except KeyError:
        raise SystemExit(
            f"unknown judge {name!r}; available: {sorted(JUDGE_FACTORIES)}"
        ) from None


def _int_list(raw: Optional[str]) -> Tuple[int, ...]:
    if not raw:
        return ()
    return tuple(int(x) for x in raw.replace(" ", "").split(",") if x)


def format_report(report: SystemReport) -> str:
    """Plain-text summary. No composite score is printed, by design."""
    lines: List[str] = []
    lines.append(f"system            : {report.system}")
    lines.append(
        f"questions         : {report.n_questions} "
        f"(evaluated {report.n_evaluated}, missing output {report.n_missing_outputs}, "
        f"errored {report.n_errors})"
    )
    lines.append(f"judge             : {report.judge.get('judge')}")
    usage = report.judge_usage or {}
    if usage.get("calls"):
        lines.append(
            f"judge calls       : {usage['calls']} "
            f"(decided {usage.get('decided')}, unknown {usage.get('unknown')})"
        )
    for note in report.notes:
        lines.append(f"note              : {note}")
    lines.append("")
    header = f"{'metric':<32}{'micro':>9}{'macro':>9}{'95% CI':>21}{'n':>6}{'n/a':>6}{'unav':>6}"
    for title, names in (("PRIMARY", PRIMARY_METRICS), ("DIAGNOSTIC", DIAGNOSTIC_METRICS)):
        lines.append(f"=== {title} ===")
        lines.append(header)
        for name in names:
            s = report.metrics.get(name)
            if s is None:
                continue
            arrow = "v" if name in LOWER_IS_BETTER else "^"
            micro = "-" if s.micro is None else f"{s.micro:.3f}"
            macro = "-" if s.macro is None else f"{s.macro:.3f}"
            if s.ci_low is None or s.ci_high is None:
                ci = "-"
            else:
                ci = f"[{s.ci_low:.3f}, {s.ci_high:.3f}]"
            lines.append(
                f"{name + ' ' + arrow:<32}{micro:>9}{macro:>9}{ci:>21}"
                f"{s.n:>6}{s.n_not_applicable:>6}{s.n_unavailable:>6}"
            )
        lines.append("")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="benchmark.evaluator.evaluate",
        description="Evaluate one system's outputs against the common benchmark.",
    )
    parser.add_argument("--dataset", required=True, help="benchmark JSON (see benchmark_schema.json)")
    parser.add_argument(
        "--system-output", required=True, help="system output JSON (see system_output_schema.json)"
    )
    parser.add_argument("--out", help="write the full JSON report here")
    parser.add_argument("--system", help="override the system name in the report")
    parser.add_argument("--k", default=",".join(str(k) for k in DEFAULT_K_VALUES), help="Hit@k values")
    parser.add_argument(
        "--budgets",
        default="",
        help="context-token budgets for equal-budget Evidence Recall, e.g. 2000,4000",
    )
    parser.add_argument("--judge", default="null", choices=sorted(JUDGE_FACTORIES))
    parser.add_argument("--bootstrap-samples", type=int, default=BootstrapConfig().n_samples)
    parser.add_argument("--seed", type=int, default=BootstrapConfig().seed)
    parser.add_argument("--no-bootstrap", action="store_true")
    parser.add_argument(
        "--no-per-question", action="store_true", help="omit per-question detail from --out"
    )
    args = parser.parse_args(argv)

    items = load_benchmark(args.dataset)
    outputs = load_system_outputs(args.system_output)
    config = EvaluationConfig(
        k_values=_int_list(args.k) or tuple(DEFAULT_K_VALUES),
        context_budgets=_int_list(args.budgets),
        bootstrap=BootstrapConfig(
            n_samples=args.bootstrap_samples,
            seed=args.seed,
            enabled=not args.no_bootstrap,
        ),
    )
    report = evaluate_system(
        items, outputs, judge=build_judge(args.judge), config=config, system=args.system
    )
    print(format_report(report))
    if args.out:
        with io.open(args.out, "w", encoding="utf-8", newline="\n") as fout:
            json.dump(
                report.to_dict(include_per_question=not args.no_per_question),
                fout,
                ensure_ascii=False,
                indent=1,
            )
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
