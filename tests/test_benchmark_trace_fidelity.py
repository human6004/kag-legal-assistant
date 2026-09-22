# -*- coding: utf-8 -*-
"""Test Suite for Benchmark Trace Fidelity & Independent Evaluation.

Tests required under Gate 2:
1. Same query_type but planner NEVER proposed Finish -> attempted_premature_finish is False.
2. Planner proposed Finish but retrieval lacked Aspect R2 -> attempted_pfr is True.
3. Planner proposed Finish when evidence was already complete -> attempted_pfr is False, accepted_pfr is False.
4. Retriever returned chunks differing from expected chunk_store -> evaluated strictly from trace, not hardcoded map.
5. A1 erroneously rejected Finish when evidence was sufficient -> false_rejection recorded accurately.
"""

import sys
import os
import unittest

WT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WT_ROOT not in sys.path:
    sys.path.insert(0, WT_ROOT)

from benchmark.trace import ExecutionTraceCollector
from benchmark.evaluator import evaluate_single_trace, compute_metrics_from_traces


class TestBenchmarkTraceFidelity(unittest.TestCase):

    def setUp(self):
        self.gold_multi = {
            "query_id": "Q_MULTI",
            "query": "Hành vi cấm và mức phạt?",
            "query_category": "multi_aspect",
            "mandatory_requirements": [
                {"requirement_id": "REQ_PROHIBITION", "required_aspects": ["prohibition"], "expected_doc_ids": ["DOC_LAW"]},
                {"requirement_id": "REQ_PENALTY", "required_aspects": ["penalty"], "expected_doc_ids": ["DOC_DECREE"]},
            ],
            "gold_evidence_spans": [
                {"doc_id": "DOC_LAW", "chunk_id": "CHUNK_PROHIB", "target_requirement_id": "REQ_PROHIBITION"},
                {"doc_id": "DOC_DECREE", "chunk_id": "CHUNK_PENALTY", "target_requirement_id": "REQ_PENALTY"},
            ],
            "answerability": "ANSWERABLE",
        }

    def test_case_1_multi_aspect_query_but_planner_never_proposed_finish(self):
        """Case 1: Query is multi_aspect, but planner timed out without ever proposing Finish.

        Trace-based evaluator must record attempted_premature_finish = False (not infer from query_type!).
        """
        collector = ExecutionTraceCollector("Q_MULTI", "Query", "A0")
        collector.record_planning(1, {"executor": "Retriever", "arguments": {"q": "r1"}})
        collector.record_retrieval(1, "task_1", [{"chunk_id": "CHUNK_PROHIB", "doc_id": "DOC_LAW", "aspects": ["prohibition"]}])
        collector.record_planning(2, {"executor": "Retriever", "arguments": {"q": "r2"}})
        collector.record_retrieval(2, "task_2", [])
        # Max iteration reached without any Finish proposal
        collector.record_generator_call(called=False, reason="MAX_ITERATIONS")
        collector.record_termination("MAX_ITERATIONS", "Timed out", "Budget exhausted", 2)

        trace = collector.to_dict()
        res = evaluate_single_trace(trace, self.gold_multi)

        self.assertFalse(res["attempted_premature_finish"], "Must not infer premature finish from query_type when planner never proposed finish!")
        self.assertFalse(res["accepted_premature_finish"])
        self.assertEqual(res["final_status"], "MAX_ITERATIONS")

    def test_case_2_finish_proposed_when_r2_missing(self):
        """Case 2: Planner proposes Finish when only R1 was retrieved and R2 is missing."""
        collector = ExecutionTraceCollector("Q_MULTI", "Query", "A0")
        collector.record_planning(1, {"executor": "Retriever"})
        collector.record_retrieval(1, "t1", [{"chunk_id": "CHUNK_PROHIB", "doc_id": "DOC_LAW", "aspects": ["prohibition"]}])

        # Finish proposed with only prohibition in pool:
        collector.record_planning(2, {"executor": "Finish"})
        collector.record_finish_proposed(2, [{"chunk_id": "CHUNK_PROHIB", "doc_id": "DOC_LAW", "aspects": ["prohibition"]}])
        collector.record_finish_decision(2, accepted=True, evaluator_status="NO_GATE", decision="FINISH")
        collector.record_generator_call(called=True, answer="Căn cứ điều cấm.")
        collector.record_termination("FINISHED", "Căn cứ điều cấm.", "Finish accepted", 2)

        trace = collector.to_dict()
        res = evaluate_single_trace(trace, self.gold_multi)

        self.assertTrue(res["attempted_premature_finish"])
        self.assertTrue(res["accepted_premature_finish"])
        self.assertFalse(res["evidence_genuinely_sufficient"])

    def test_case_3_finish_proposed_when_evidence_already_complete(self):
        """Case 3: Planner proposes Finish after retrieving BOTH R1 and R2."""
        collector = ExecutionTraceCollector("Q_MULTI", "Query", "A0")
        collector.record_planning(1, {"executor": "Retriever"})
        collector.record_retrieval(1, "t1", [
            {"chunk_id": "CHUNK_PROHIB", "doc_id": "DOC_LAW", "aspects": ["prohibition"]},
            {"chunk_id": "CHUNK_PENALTY", "doc_id": "DOC_DECREE", "aspects": ["penalty"]},
        ])

        # Finish proposed with complete evidence pool:
        pool = [
            {"chunk_id": "CHUNK_PROHIB", "doc_id": "DOC_LAW", "aspects": ["prohibition"]},
            {"chunk_id": "CHUNK_PENALTY", "doc_id": "DOC_DECREE", "aspects": ["penalty"]},
        ]
        collector.record_planning(2, {"executor": "Finish"})
        collector.record_finish_proposed(2, pool)
        collector.record_finish_decision(2, accepted=True, evaluator_status="NO_GATE", decision="FINISH")
        collector.record_generator_call(called=True, answer="Căn cứ điều cấm và mức phạt.")
        collector.record_termination("FINISHED", "Căn cứ điều cấm và mức phạt.", "Complete finish", 2)

        trace = collector.to_dict()
        res = evaluate_single_trace(trace, self.gold_multi)

        self.assertFalse(res["attempted_premature_finish"], "Must not mark premature when evidence was complete!")
        self.assertFalse(res["accepted_premature_finish"])
        self.assertTrue(res["evidence_genuinely_sufficient"])
        self.assertEqual(res["unsupported_claims_count"], 0)

    def test_case_4_retriever_returned_unexpected_custom_chunks(self):
        """Case 4: Retriever returns unexpected chunk IDs; evaluator parses real trace chunks."""
        collector = ExecutionTraceCollector("Q_MULTI", "Query", "A1")
        collector.record_planning(1, {"executor": "Retriever"})
        # Custom chunk IDs not present in any static chunk store
        collector.record_retrieval(1, "t1", [
            {"chunk_id": "CHUNK_PROHIB", "doc_id": "DOC_LAW", "aspects": ["prohibition"]},
            {"chunk_id": "CUSTOM_PENALTY_CHUNKS_999", "doc_id": "DOC_DECREE", "aspects": ["penalty"]},
        ])

        pool = [
            {"chunk_id": "CHUNK_PROHIB", "doc_id": "DOC_LAW", "aspects": ["prohibition"]},
            {"chunk_id": "CUSTOM_PENALTY_CHUNKS_999", "doc_id": "DOC_DECREE", "aspects": ["penalty"]},
        ]
        collector.record_planning(2, {"executor": "Finish"})
        collector.record_finish_proposed(2, pool)
        collector.record_finish_decision(2, accepted=True, evaluator_status="SUFFICIENT", decision="FINISH")
        collector.record_generator_call(called=True, answer="Answer with custom penalty chunks")
        collector.record_termination("FINISHED", "Answer with custom penalty chunks", "Finished", 2)

        trace = collector.to_dict()
        res = evaluate_single_trace(trace, self.gold_multi)

        # Evaluator checks actual trace contents: both prohibition and penalty aspects present
        self.assertTrue(res["evidence_genuinely_sufficient"])
        self.assertFalse(res["accepted_premature_finish"])

    def test_case_5_a1_erroneous_false_rejection_on_sufficient_evidence(self):
        """Case 5: Finish gate rejects Finish even though evidence in pool was sufficient."""
        collector = ExecutionTraceCollector("Q_MULTI", "Query", "A1")
        pool = [
            {"chunk_id": "CHUNK_PROHIB", "doc_id": "DOC_LAW", "aspects": ["prohibition"]},
            {"chunk_id": "CHUNK_PENALTY", "doc_id": "DOC_DECREE", "aspects": ["penalty"]},
        ]
        collector.record_planning(1, {"executor": "Finish"})
        collector.record_finish_proposed(1, pool)
        # Erroneously rejected by gate:
        collector.record_finish_decision(1, accepted=False, evaluator_status="INCOMPLETE", decision="RETRIEVE_MORE", rationale="False error")
        collector.record_generator_call(called=False, reason="ABSTAIN")
        collector.record_termination("ABSTAIN", "Abstain", "Gate rejected", 1)

        trace = collector.to_dict()
        res = evaluate_single_trace(trace, self.gold_multi)

        self.assertEqual(res["false_rejections_count"], 1)
        self.assertEqual(res["finish_proposals_on_sufficient_evidence"], 1)


if __name__ == "__main__":
    unittest.main()
