# -*- coding: utf-8 -*-
"""RED Tests for Gate B: Benchmark Measurement Fidelity Deficiencies.

Reproduces:
B1: Accepted Finish criteria diverges from Proposed Finish:
    When chunks in pool have required aspects but belong to the WRONG document,
    accepted_premature_finish is falsely evaluated as False because evaluate_single_trace()
    omitted expected_doc_ids in the finish_decision check.
    EXPECTED: accepted_premature_finish must be True (same sufficiency criteria).

B2: Claims support falsely certified as SUPPORTED purely from retriever metadata aspects:
    Currently, evaluate_single_trace() marks is_supported=True solely because
    chunk dict has matching aspect in its metadata.
    EXPECTED: Without an independent answer-level evaluator, claim support must be
    reported as NOT_EVALUATED / N/A, not blindly certified as SUPPORTED.
"""

import sys
import os
import unittest

WT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WT_ROOT not in sys.path:
    sys.path.insert(0, WT_ROOT)

from benchmark.trace import ExecutionTraceCollector
from benchmark.evaluator import evaluate_single_trace


class TestGateBMeasurementRED(unittest.TestCase):

    def test_B1_accepted_finish_must_enforce_document_scope(self):
        """B1: Accepted Finish must enforce document scope identically to proposed Finish.

        Trace has chunks with aspect 'penalty', but from DOC_WRONG instead of DOC_LAW.
        """
        gold = {
            "query_id": "Q_DOC_SCOPE",
            "query": "Quy định mức phạt theo luật chuyên ngành",
            "query_category": "single_aspect",
            "mandatory_requirements": [
                {
                    "requirement_id": "REQ_PENALTY",
                    "required_aspects": ["penalty"],
                    "expected_doc_ids": ["DOC_LAW_CORRECT"],
                }
            ],
            "answerability": "ANSWERABLE",
        }

        collector = ExecutionTraceCollector("Q_DOC_SCOPE", "Query", "A0")
        # Pool has aspect 'penalty', but doc_id is DOC_WRONG:
        wrong_pool = [{"chunk_id": "C_WRONG", "doc_id": "DOC_WRONG", "aspects": ["penalty"]}]
        collector.record_planning(1, {"executor": "Finish"})
        collector.record_finish_proposed(1, wrong_pool)
        collector.record_finish_decision(1, accepted=True, evaluator_status="NO_GATE", decision="FINISH")
        collector.record_generator_call(called=True, answer="Phạt tiền theo doc wrong.")
        collector.record_termination("FINISHED", "Answer", "Finish accepted", 1)

        trace = collector.to_dict()
        res = evaluate_single_trace(trace, gold)

        # EXPECTED: accepted_premature_finish must be TRUE because doc_scope was violated!
        self.assertTrue(
            res["accepted_premature_finish"],
            "GATE B1 DEFECT: accepted_premature_finish was False despite evidence coming from the WRONG document!"
        )

    def test_B2_claim_support_must_not_blindly_certify_from_retriever_aspects(self):
        """B2: Claims support must NOT be certified as SUPPORTED without an independent claim evaluator.

        Must return 'NOT_EVALUATED' or 'N/A', not is_supported=True.
        """
        gold = {
            "query_id": "Q_CLAIM_EVAL",
            "query": "Hành vi vi phạm và mức phạt",
            "query_category": "single_aspect",
            "mandatory_requirements": [
                {
                    "requirement_id": "REQ_1",
                    "required_aspects": ["prohibition"],
                    "expected_doc_ids": ["DOC_LAW"],
                }
            ],
            "answerability": "ANSWERABLE",
        }

        collector = ExecutionTraceCollector("Q_CLAIM_EVAL", "Query", "A1")
        pool = [{"chunk_id": "C1", "doc_id": "DOC_LAW", "aspects": ["prohibition"]}]
        collector.record_planning(1, {"executor": "Finish"})
        collector.record_finish_proposed(1, pool)
        collector.record_finish_decision(1, accepted=True, evaluator_status="SUFFICIENT", decision="FINISH")
        collector.record_generator_call(called=True, answer="Câu trả lời pháp lý.")
        collector.record_termination("FINISHED", "Answer", "Finish accepted", 1)

        trace = collector.to_dict()
        res = evaluate_single_trace(trace, gold)

        claims_eval = res.get("claims_evaluation", [])
        self.assertTrue(len(claims_eval) > 0)
        # Verify that claim support is NOT blindly marked as True/SUPPORTED:
        for c in claims_eval:
            self.assertNotEqual(
                c.get("status"),
                "SUPPORTED",
                "GATE B2 DEFECT: Claim was blindly certified as 'SUPPORTED' purely from retriever metadata aspects!"
            )
            self.assertEqual(
                c.get("status"),
                "NOT_EVALUATED",
                "GATE B2 EXPECTATION: Claim evaluation without independent answer-level evaluator must be 'NOT_EVALUATED'."
            )


if __name__ == "__main__":
    unittest.main()
