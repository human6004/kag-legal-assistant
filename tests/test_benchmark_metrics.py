# -*- coding: utf-8 -*-
"""Unit Tests for Benchmark Evaluator Metric Calculations.

Covers:
1. A0 Finish with sufficient evidence -> PFR=0, ESR=1.0, TSR=1.0
2. A0 Finish missing R2 -> attempted_PFR=1.0, accepted_PFR=1.0, ESR=0.0
3. A1 False Rejection on sufficient evidence -> false_rejection_rate > 0
4. A1 Correct Abstention on conflicting / unanswerable -> CHA=1.0, UAA=1.0, TSR=1.0
5. A1 Unsupported Claim -> UCR > 0, TSR=0.0
6. Empty sample subsets -> return None / N/A, never defaulting to 100% or 0%
7. H4 hypothesis validation: checks overhead threshold (<= 35%).
"""

import unittest
import sys
import os

WT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WT_ROOT not in sys.path:
    sys.path.insert(0, WT_ROOT)

from benchmark.evaluator import compute_metrics, format_metric_value


class TestBenchmarkEvaluatorMetrics(unittest.TestCase):

    def test_case_1_a0_finish_with_sufficient_evidence(self):
        """Case 1: A0 finishes with genuinely sufficient evidence.

        Must NOT be penalized as premature finish simply for being A0.
        """
        records = [{
            "query_id": "Q1",
            "query_type": "single_aspect",
            "final_status": "FINISHED",
            "evidence_genuinely_sufficient": True,
            "attempted_premature_finish": False,
            "accepted_premature_finish": False,
            "claims_evaluation": [{"claim": "C1", "is_supported": True}],
            "iterations": 2,
            "rejections": 0,
            "elapsed_time": 0.05,
        }]

        metrics = compute_metrics(records)
        self.assertEqual(metrics["evidence_sufficiency_rate"], 1.0)
        self.assertEqual(metrics["accepted_premature_finish_rate"], 0.0)
        self.assertEqual(metrics["attempted_premature_finish_rate"], 0.0)
        self.assertEqual(metrics["unsupported_claim_rate"], 0.0)
        self.assertEqual(metrics["task_success_rate"], 1.0)

    def test_case_2_a0_finish_missing_r2(self):
        """Case 2: A0 finishes prematurely while missing mandatory aspect R2.

        Both attempted and accepted premature finish must be 1.0.
        """
        records = [{
            "query_id": "Q3",
            "query_type": "multi_aspect",
            "final_status": "FINISHED",
            "evidence_genuinely_sufficient": False,
            "attempted_premature_finish": True,
            "accepted_premature_finish": True,
            "claims_evaluation": [
                {"claim": "Prohibition", "is_supported": True},
                {"claim": "Penalty", "is_supported": False},
            ],
            "iterations": 2,
            "rejections": 0,
            "elapsed_time": 0.05,
        }]

        metrics = compute_metrics(records)
        self.assertEqual(metrics["evidence_sufficiency_rate"], 0.0)
        self.assertEqual(metrics["attempted_premature_finish_rate"], 1.0)
        self.assertEqual(metrics["accepted_premature_finish_rate"], 1.0)
        self.assertEqual(metrics["unsupported_claim_rate"], 0.5)
        self.assertEqual(metrics["task_success_rate"], 0.0)

    def test_case_3_a1_false_rejection_on_sufficient_evidence(self):
        """Case 3: Finish gate erroneously rejects an answerable query with sufficient evidence."""
        records = [{
            "query_id": "Q1",
            "query_type": "single_aspect",
            "final_status": "ABSTAIN",
            "evidence_genuinely_sufficient": True,
            "finish_proposals_on_sufficient_evidence": 1,
            "false_rejections_count": 1,
            "attempted_premature_finish": False,
            "accepted_premature_finish": False,
            "claims_evaluation": [],
            "iterations": 5,
            "rejections": 1,
            "elapsed_time": 0.1,
        }]

        metrics = compute_metrics(records)
        self.assertEqual(metrics["false_rejection_rate"], 1.0)
        self.assertEqual(metrics["task_success_rate"], 0.0)

    def test_case_4_a1_correct_abstention_on_conflicting_and_unanswerable(self):
        """Case 4: A1 correctly abstains on conflicting and unanswerable queries."""
        records = [
            {
                "query_id": "Q_CONF",
                "query_type": "conflicting",
                "final_status": "ABSTAIN",
                "conflict_detected": True,
                "evidence_genuinely_sufficient": False,
                "attempted_premature_finish": True,
                "accepted_premature_finish": False,
                "claims_evaluation": [],
                "iterations": 5,
                "rejections": 3,
                "elapsed_time": 0.1,
            },
            {
                "query_id": "Q_UNANS",
                "query_type": "unanswerable",
                "final_status": "ABSTAIN",
                "conflict_detected": False,
                "evidence_genuinely_sufficient": False,
                "attempted_premature_finish": True,
                "accepted_premature_finish": False,
                "claims_evaluation": [],
                "iterations": 5,
                "rejections": 4,
                "elapsed_time": 0.1,
            },
        ]

        metrics = compute_metrics(records)
        self.assertEqual(metrics["conflict_handling_accuracy"], 1.0)
        self.assertEqual(metrics["unanswerable_abstention_accuracy"], 1.0)
        self.assertEqual(metrics["accepted_premature_finish_rate"], 0.0)
        self.assertEqual(metrics["task_success_rate"], 1.0)

    def test_case_5_a1_unsupported_claim_leads_to_failure(self):
        """Case 5: A1 generated an answer containing ungrounded claim -> penalized."""
        records = [{
            "query_id": "Q1",
            "query_type": "single_aspect",
            "final_status": "FINISHED",
            "evidence_genuinely_sufficient": False,
            "attempted_premature_finish": True,
            "accepted_premature_finish": True,
            "claims_evaluation": [{"claim": "Hallucinated rule", "is_supported": False}],
            "iterations": 3,
            "rejections": 0,
            "elapsed_time": 0.05,
        }]

        metrics = compute_metrics(records)
        self.assertEqual(metrics["unsupported_claim_rate"], 1.0)
        self.assertEqual(metrics["task_success_rate"], 0.0)

    def test_case_6_empty_sample_subsets_return_none_not_default_100(self):
        """Case 6: Subsets with 0 samples must yield None / N/A, NOT 1.0 (100%)."""
        records = [{
            "query_id": "Q1",
            "query_type": "single_aspect",
            "final_status": "FINISHED",
            "evidence_genuinely_sufficient": True,
            "attempted_premature_finish": False,
            "accepted_premature_finish": False,
            "claims_evaluation": [{"claim": "C1", "is_supported": True}],
            "iterations": 2,
            "rejections": 0,
            "elapsed_time": 0.05,
        }]

        metrics = compute_metrics(records)
        # Conflicting subset has 0 records -> must be None
        self.assertIsNone(metrics["conflict_handling_accuracy"])
        self.assertEqual(format_metric_value(metrics["conflict_handling_accuracy"]), "N/A")

        # Unanswerable subset has 0 records -> must be None
        self.assertIsNone(metrics["unanswerable_abstention_accuracy"])
        self.assertEqual(format_metric_value(metrics["unanswerable_abstention_accuracy"]), "N/A")

        # False rejection on sufficient evidence has 0 proposals -> must be None
        self.assertIsNone(metrics["false_rejection_rate"])
        self.assertEqual(format_metric_value(metrics["false_rejection_rate"]), "N/A")

    def test_case_7_h4_overhead_evaluation(self):
        """Case 7: Evaluates H4 hypothesis check: overhead <= 35%."""
        from benchmark.evaluator import evaluate_h4_hypothesis

        # Test case: 2.0 vs 2.5 iters (+25% -> Supported)
        res_supp = evaluate_h4_hypothesis(avg_iters_a0=2.0, avg_iters_a1=2.5)
        self.assertTrue(res_supp["supported"])

        # Test case: 2.0 vs 4.0 iters (+100% -> NOT Supported)
        res_unsupp = evaluate_h4_hypothesis(avg_iters_a0=2.0, avg_iters_a1=4.0)
        self.assertFalse(res_unsupp["supported"])
        self.assertIn("exceeded", res_unsupp["rationale"].lower())


if __name__ == "__main__":
    unittest.main()
