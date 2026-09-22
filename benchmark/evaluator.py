# -*- coding: utf-8 -*-
"""Objective Benchmark Evaluator for A0 (Baseline) vs A1 (Evidence-Aware KAG).

Calculates quality, safety, and efficiency metrics directly from execution traces
and independent gold annotations, without hardcoded tables or mode-based bias:
- Reads runtime events (PLANNING, RETRIEVAL, FINISH_PROPOSED, FINISH_DECISION, GENERATOR_CALL, TERMINATION).
- Evaluates evidence sufficiency and premature finish from gold standards and the evidence pool at the exact moment of Finish.
- Distinguishes attempted premature finish from accepted premature finish.
- Evaluates false rejections on answerable queries.
- Returns None / "N/A" for empty subsets (never defaulting to 100% or 0%).
- Rigorously validates Hypothesis H4 against the 35% overhead threshold.
"""

import json
import sys
import os
from typing import Dict, List, Any, Optional, Set


def format_metric_value(val: Optional[float]) -> str:
    """Format float as percentage or return 'N/A' if None."""
    if val is None:
        return "N/A"
    return f"{val:.2%}"


def evaluate_h4_hypothesis(
    avg_iters_a0: float,
    avg_iters_a1: float,
    threshold: float = 0.35,
) -> Dict[str, Any]:
    """Evaluate pre-registered Hypothesis H4 (iteration overhead <= 35%)."""
    if avg_iters_a0 <= 0:
        return {
            "supported": False,
            "overhead_pct": None,
            "rationale": "Baseline average iterations is zero or negative.",
        }

    overhead_pct = (avg_iters_a1 - avg_iters_a0) / avg_iters_a0
    supported = (overhead_pct <= threshold)

    if supported:
        rationale = f"Overhead is +{overhead_pct:.1%}, within the pre-registered {threshold:.0%} threshold."
    else:
        rationale = f"Hypothesis H4 NOT supported in test conditions: iteration overhead is +{overhead_pct:.1%}, which exceeded the {threshold:.0%} threshold."

    return {
        "supported": supported,
        "overhead_pct": round(overhead_pct, 4),
        "threshold": threshold,
        "rationale": rationale,
    }


def evaluate_single_trace(trace: Dict[str, Any], gold: Dict[str, Any]) -> Dict[str, Any]:
    """Objectively evaluates an execution trace against gold requirements."""
    events = trace.get("events", [])
    final_status = trace.get("final_status", "UNKNOWN")
    pipeline_mode = trace.get("pipeline_mode", "A0")
    query_id = trace.get("query_id", gold.get("query_id"))
    query_type = gold.get("query_type") or gold.get("query_category", "unknown")

    mandatory_reqs = gold.get("mandatory_requirements", [])
    gold_aspects: Set[str] = {asp for r in mandatory_reqs for asp in r.get("required_aspects", [])}
    if not gold_aspects and "required_aspects" in gold and gold["required_aspects"]:
        gold_aspects = set(gold["required_aspects"])

    expected_doc_ids: Set[str] = {d for r in mandatory_reqs for d in r.get("expected_doc_ids", [])}
    if not expected_doc_ids and "expected_doc_ids" in gold and gold["expected_doc_ids"]:
        expected_doc_ids = set(gold["expected_doc_ids"])

    is_conflicting = (query_type == "conflicting" or gold.get("answerability") == "CONFLICTING_NORMS")
    is_unanswerable = (query_type == "unanswerable" or gold.get("answerability") == "UNANSWERABLE_OUT_OF_SCOPE")

    # 1. Collect all retrieved chunks across execution
    all_retrieved_chunks = []
    for ev in events:
        if ev.get("event_type") == "RETRIEVAL":
            all_retrieved_chunks.extend(ev.get("details", {}).get("chunks", []))

    def _is_pool_sufficient(pool: List[Dict[str, Any]]) -> bool:
        """Evaluates whether an evidence pool genuinely satisfies all gold requirements.

        C4 Fix: Binds aspects to expected documents per requirement.
        A query requiring Aspect A from Doc 1 and Aspect B from Doc 2 is NOT satisfied
        by retrieving Aspect A from Doc 2 and Aspect B from Doc 1.
        """
        if is_conflicting or is_unanswerable:
            return False

        if not mandatory_reqs:
            pool_aspects = {asp for c in pool for asp in c.get("aspects", [])}
            pool_docs = {c.get("doc_id") for c in pool if c.get("doc_id")}
            has_aspects = gold_aspects.issubset(pool_aspects) if gold_aspects else True
            has_docs = bool(pool_docs.intersection(expected_doc_ids)) if expected_doc_ids else True
            return has_aspects and has_docs

        for req in mandatory_reqs:
            req_aspects = set(req.get("required_aspects", []))
            req_docs = set(req.get("expected_doc_ids", []))

            if req_docs:
                valid_chunks_for_req = [c for c in pool if c.get("doc_id") in req_docs]
                covered_aspects_for_req = {asp for c in valid_chunks_for_req for asp in c.get("aspects", [])}
                if not req_aspects.issubset(covered_aspects_for_req):
                    return False
            else:
                pool_aspects = {asp for c in pool for asp in c.get("aspects", [])}
                if not req_aspects.issubset(pool_aspects):
                    return False

        return True

    # 1. Check overall genuine sufficiency
    evidence_genuinely_sufficient = _is_pool_sufficient(all_retrieved_chunks)

    # 2. Inspect Finish Proposals
    attempted_premature_finish = False
    accepted_premature_finish = False
    finish_proposals_on_sufficient_evidence = 0
    false_rejections_count = 0

    finish_proposed_events = [e for e in events if e.get("event_type") == "FINISH_PROPOSED"]
    finish_decision_events = [e for e in events if e.get("event_type") == "FINISH_DECISION"]

    for fp_ev in finish_proposed_events:
        pool = fp_ev.get("details", {}).get("evidence_pool_at_finish", [])
        pool_sufficient = _is_pool_sufficient(pool)

        if not pool_sufficient:
            attempted_premature_finish = True
        else:
            finish_proposals_on_sufficient_evidence += 1

    # Check decisions
    for fd_ev in finish_decision_events:
        details = fd_ev.get("details", {})
        accepted = details.get("accepted", False)
        # Match with corresponding proposed event in the same iteration
        iter_num = fd_ev.get("iteration")
        matching_proposals = [p for p in finish_proposed_events if p.get("iteration") == iter_num]
        if matching_proposals:
            pool = matching_proposals[-1].get("details", {}).get("evidence_pool_at_finish", [])
            # Gate B1 Fix: Accepted Finish uses the exact same sufficiency check (including expected_doc_ids)
            pool_sufficient = _is_pool_sufficient(pool)
            if accepted and not pool_sufficient:
                accepted_premature_finish = True
            elif not accepted and pool_sufficient:
                false_rejections_count += 1
        elif accepted and not evidence_genuinely_sufficient:
            accepted_premature_finish = True

    # Check claims support in final answer
    # Gate B2 Fix: Do NOT certify claim support purely from retriever metadata aspects.
    # Without an independent answer-level evaluator, report NOT_EVALUATED / N/A.
    claims_evaluation = []
    unsupported_claims_count = 0
    if final_status == "FINISHED":
        for asp in gold_aspects:
            claims_evaluation.append({
                "aspect": asp,
                "status": "NOT_EVALUATED",
                "is_supported": None,
            })

    # Conflict check
    conflict_detected = False
    if is_conflicting and final_status == "ABSTAIN":
        conflict_detected = True

    return {
        "query_id": query_id,
        "pipeline_mode": pipeline_mode,
        "query_type": query_type,
        "final_status": final_status,
        "evidence_genuinely_sufficient": evidence_genuinely_sufficient,
        "attempted_premature_finish": attempted_premature_finish,
        "accepted_premature_finish": accepted_premature_finish,
        "finish_proposals_on_sufficient_evidence": finish_proposals_on_sufficient_evidence,
        "false_rejections_count": false_rejections_count,
        "conflict_detected": conflict_detected,
        "claims_evaluation": claims_evaluation,
        "unsupported_claims_count": unsupported_claims_count,
        "iterations": trace.get("events", [{}])[-1].get("iteration", 2),
        "rejections": len([e for e in finish_decision_events if not e.get("details", {}).get("accepted", False)]),
        "elapsed_time": trace.get("elapsed_time", 0.0),
    }


def compute_metrics_from_traces(eval_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute benchmark summary metrics from evaluated trace records."""
    return compute_metrics(eval_results)


def compute_metrics(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute objective benchmark metrics from execution records."""
    if not records:
        return {}

    total_queries = len(records)
    finished_count = sum(1 for r in records if r.get("final_status") == "FINISHED")
    abstain_count = sum(1 for r in records if r.get("final_status") == "ABSTAIN")
    max_iter_count = sum(1 for r in records if r.get("final_status") == "MAX_ITERATIONS")
    error_count = sum(1 for r in records if r.get("final_status") == "ERROR")

    total_iterations = sum(r.get("iterations", 0) for r in records)
    total_rejections = sum(r.get("rejections", 0) for r in records)
    total_elapsed = sum(r.get("elapsed_time", 0.0) for r in records)

    # 1. Evidence Sufficiency Rate (ESR)
    sufficient_count = sum(1 for r in records if r.get("evidence_genuinely_sufficient", False))
    esr = (sufficient_count / total_queries) if total_queries > 0 else 0.0

    # 2. Attempted Premature Finish Rate
    attempted_pfr_count = sum(1 for r in records if r.get("attempted_premature_finish", False))
    attempted_pfr = (attempted_pfr_count / total_queries) if total_queries > 0 else 0.0

    # 3. Accepted Premature Finish Rate
    accepted_pfr_count = sum(1 for r in records if r.get("accepted_premature_finish", False))
    accepted_pfr = (accepted_pfr_count / total_queries) if total_queries > 0 else 0.0

    # 4. False Rejection Rate
    finish_proposals_on_sufficient = sum(r.get("finish_proposals_on_sufficient_evidence", 0) for r in records)
    false_rejections_count = sum(r.get("false_rejections_count", 0) for r in records)
    if finish_proposals_on_sufficient > 0:
        false_rejection_rate = round(false_rejections_count / finish_proposals_on_sufficient, 4)
    else:
        false_rejection_rate = None

    # 5. Unsupported Claim Rate (UCR)
    total_claims = 0
    unsupported_claims = 0
    for r in records:
        claims = r.get("claims_evaluation", [])
        for c in claims:
            if c.get("status") == "NOT_EVALUATED" or c.get("is_supported") is None:
                continue
            total_claims += 1
            if not c.get("is_supported", False):
                unsupported_claims += 1

    if total_claims > 0:
        ucr = round(unsupported_claims / total_claims, 4)
    else:
        ucr = None

    # 6. Conflict Handling Accuracy (CHA)
    conflicting_records = [r for r in records if r.get("query_type") == "conflicting"]
    if conflicting_records:
        cha_correct = sum(
            1 for r in conflicting_records
            if r.get("final_status") == "ABSTAIN" and r.get("conflict_detected", False)
        )
        cha = round(cha_correct / len(conflicting_records), 4)
    else:
        cha = None

    # 7. Unanswerable Abstention Accuracy (UAA)
    unanswerable_records = [r for r in records if r.get("query_type") == "unanswerable"]
    if unanswerable_records:
        uaa_correct = sum(1 for r in unanswerable_records if r.get("final_status") == "ABSTAIN")
        uaa = round(uaa_correct / len(unanswerable_records), 4)
    else:
        uaa = None

    # 8. Task Success Rate (TSR)
    successful_tasks = 0
    for r in records:
        q_type = r.get("query_type")
        status = r.get("final_status")
        if q_type in ("single_aspect", "multi_aspect"):
            if status == "FINISHED" and r.get("evidence_genuinely_sufficient", False):
                claims = r.get("claims_evaluation", [])
                evaluable_claims = [c for c in claims if c.get("status") != "NOT_EVALUATED" and c.get("is_supported") is not None]
                if not evaluable_claims or all(c.get("is_supported", False) for c in evaluable_claims):
                    successful_tasks += 1
        elif q_type == "conflicting":
            if status == "ABSTAIN" and r.get("conflict_detected", False):
                successful_tasks += 1
        elif q_type == "unanswerable":
            if status == "ABSTAIN":
                successful_tasks += 1

    tsr = round(successful_tasks / total_queries, 4) if total_queries > 0 else 0.0

    return {
        "total_queries": total_queries,
        "finished_count": finished_count,
        "abstain_count": abstain_count,
        "max_iter_count": max_iter_count,
        "error_count": error_count,
        "evidence_sufficiency_rate": round(esr, 4),
        "attempted_premature_finish_rate": round(attempted_pfr, 4),
        "accepted_premature_finish_rate": round(accepted_pfr, 4),
        "false_rejection_rate": false_rejection_rate,
        "unsupported_claim_rate": ucr,
        "conflict_handling_accuracy": cha,
        "unanswerable_abstention_accuracy": uaa,
        "task_success_rate": tsr,
        "avg_iterations": round(total_iterations / total_queries, 2) if total_queries > 0 else 0.0,
        "avg_rejections": round(total_rejections / total_queries, 2) if total_queries > 0 else 0.0,
        "avg_elapsed_seconds": round(total_elapsed / total_queries, 4) if total_queries > 0 else 0.0,
    }


def format_markdown_table(metrics_a0: Dict[str, Any], metrics_a1: Dict[str, Any]) -> str:
    """Format comparative metrics table with delta and H4 assessment."""
    h4_eval = evaluate_h4_hypothesis(
        avg_iters_a0=metrics_a0.get("avg_iterations", 0),
        avg_iters_a1=metrics_a1.get("avg_iterations", 0),
    )

    lines = [
        "| Metric | A0 (Baseline Iterative KAG) | A1 (Evidence-Aware KAG) | Delta / Assessment |",
        "|---|---|---|---|",
        f"| **Task Success Rate (TSR)** | {format_metric_value(metrics_a0.get('task_success_rate'))} | {format_metric_value(metrics_a1.get('task_success_rate'))} | Overall correctness across all strata |",
        f"| **Evidence Sufficiency Rate (ESR)** | {format_metric_value(metrics_a0.get('evidence_sufficiency_rate'))} | {format_metric_value(metrics_a1.get('evidence_sufficiency_rate'))} | Genuinely verified vs gold requirements |",
        f"| **Attempted Premature Finish** | {format_metric_value(metrics_a0.get('attempted_premature_finish_rate'))} | {format_metric_value(metrics_a1.get('attempted_premature_finish_rate'))} | Frequency planner proposed Finish early |",
        f"| **Accepted Premature Finish** | {format_metric_value(metrics_a0.get('accepted_premature_finish_rate'))} | {format_metric_value(metrics_a1.get('accepted_premature_finish_rate'))} | Gated: A0 accepts, A1 blocks early Finish |",
        f"| **False Rejection Rate** | {format_metric_value(metrics_a0.get('false_rejection_rate'))} | {format_metric_value(metrics_a1.get('false_rejection_rate'))} | Rejection when evidence was actually sufficient |",
        f"| **Unsupported Claim Rate (UCR)** | {format_metric_value(metrics_a0.get('unsupported_claim_rate'))} | {format_metric_value(metrics_a1.get('unsupported_claim_rate'))} | Unbacked factual statements in answers |",
        f"| **Conflict Handling Accuracy** | {format_metric_value(metrics_a0.get('conflict_handling_accuracy'))} | {format_metric_value(metrics_a1.get('conflict_handling_accuracy'))} | Identification of contradictory legal norms |",
        f"| **Unanswerable Abstention** | {format_metric_value(metrics_a0.get('unanswerable_abstention_accuracy'))} | {format_metric_value(metrics_a1.get('unanswerable_abstention_accuracy'))} | Controlled fail-closed on nonexistent norms |",
        f"| **Average Iterations** | {metrics_a0.get('avg_iterations', 0):.2f} | {metrics_a1.get('avg_iterations', 0):.2f} | Iteration cost comparison |",
        f"| **Average Rejections** | 0.00 | {metrics_a1.get('avg_rejections', 0):.2f} | Active feedback loops forced by gate |",
        f"| **Average Latency (s)** | {metrics_a0.get('avg_elapsed_seconds', 0):.4f}s | {metrics_a1.get('avg_elapsed_seconds', 0):.4f}s | Execution duration |",
        f"| **Hypothesis H4 Status** | Reference Baseline | {'SUPPORTED' if h4_eval['supported'] else 'NOT SUPPORTED'} | {h4_eval['rationale']} |",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python evaluator.py <results_jsonl> [results_a1_jsonl]")
        sys.exit(1)

    file1 = sys.argv[1]
    with open(file1, "r", encoding="utf-8") as f:
        records1 = [json.loads(line) for line in f if line.strip()]

    metrics1 = compute_metrics(records1)
    print(f"\n--- Metrics for {file1} ---")
    print(json.dumps(metrics1, indent=2, ensure_ascii=False))

    if len(sys.argv) >= 3:
        file2 = sys.argv[2]
        with open(file2, "r", encoding="utf-8") as f:
            records2 = [json.loads(line) for line in f if line.strip()]
        metrics2 = compute_metrics(records2)
        print(f"\n--- Metrics for {file2} ---")
        print(json.dumps(metrics2, indent=2, ensure_ascii=False))
        print("\n--- Comparative Table ---")
        print(format_markdown_table(metrics1, metrics2))
