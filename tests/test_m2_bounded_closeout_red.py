# -*- coding: utf-8 -*-
"""RED Tests for M2 Bounded Final Closeout: C1, C2, C3, C4.

Reproduces:
C1 - PROVENANCE:
     Without authoritative doc-chunk mapping (valid_corpus_chunk_ids_by_doc=None),
     DEFAULT_FIXTURE_DOC_CHUNKS must NOT verify chunk provenance in runtime.
     EXPECTED: ProvenanceValidationStatus.PROVENANCE_INVALID.

C2 - PRESENCE LINEAGE:
     Task 1 retrieves C1. Task 2 returns empty retrieval.
     Task 2 must NOT issue a presence receipt for C1 with run_id of Task 2.
     EXPECTED: Zero receipts issued for C1 under run_id of Task 2.

C3 - SEMANTIC ORACLE:
     R1 and R2 share evidence C1, but have different requirement statements.
     Oracle only certifies claim of R1.
     R2 must NOT become SATISFIED via evidence-only alias (e.g. 'C1' or 'C1_CLAIM').
     EXPECTED: R2 status != RequirementStatus.SATISFIED.

C4 - BENCHMARK EVALUATOR:
     Gold: R1 requires aspect A from D1; R2 requires aspect B from D2.
     Retrieval: Chunk with A from D2; chunk with B from D1 (crossed/mismatched).
     EXPECTED: evidence_genuinely_sufficient=False, accepted_premature_finish=True.
"""

import sys
import os
import unittest
import locale

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

try:
    locale.setlocale(locale.LC_ALL, 'Chinese_China.936')
except Exception:
    try:
        locale.setlocale(locale.LC_ALL, 'Chinese')
    except Exception:
        pass

WT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WT_ROOT not in sys.path:
    sys.path.insert(0, WT_ROOT)
VENDOR_KAG = os.path.join(WT_ROOT, "vendor", "KAG")
if VENDOR_KAG not in sys.path:
    sys.path.insert(0, VENDOR_KAG)

import kag
wt_kag = os.path.join(WT_ROOT, "kag")
if wt_kag not in kag.__path__:
    kag.__path__.append(wt_kag)

import kag.solver
wt_solver = os.path.join(WT_ROOT, "kag", "solver")
if wt_solver not in kag.solver.__path__:
    kag.solver.__path__.append(wt_solver)

from kag.solver.evidence_aware.models import (
    Evidence,
    Provenance,
    ModalityType,
    ProvenanceValidationStatus,
    EntailmentRelation,
    RequirementStatus,
    FourStageEvidenceVerifier,
    EvidenceRequirement,
    StructuredEvidenceState,
)
from benchmark.trace import ExecutionTraceCollector
from benchmark.evaluator import evaluate_single_trace


class TestM2BoundedCloseoutRED(unittest.TestCase):

    def test_C1_provenance_without_authoritative_mapping_must_be_invalid(self):
        """C1: Without authoritative doc-chunk mapping, DEFAULT_FIXTURE_DOC_CHUNKS must NOT verify chunk."""
        ev = Evidence(
            id="C1",
            content="Nội dung điều khoản C1",
            provenance=Provenance(doc_id="DOC1", chunk_id="C1"),
            modality=ModalityType.TEXT,
        )

        receipt = FourStageEvidenceVerifier.stage2_verify_provenance(
            evidence=ev,
            valid_corpus_doc_ids={"DOC1"},
            valid_corpus_chunk_ids_by_doc=None,  # No authoritative mapping provided
        )

        self.assertNotEqual(
            receipt.status,
            ProvenanceValidationStatus.PROVENANCE_VERIFIED,
            "C1 DEFECT DETECTED: Chunk was verified simply because doc_id/chunk_id was in DEFAULT_FIXTURE_DOC_CHUNKS, "
            "without authoritative doc-chunk mapping!"
        )
        self.assertEqual(
            receipt.status,
            ProvenanceValidationStatus.PROVENANCE_INVALID,
            "C1 EXPECTATION: Chunk without authoritative mapping must be PROVENANCE_INVALID."
        )

    def test_C2_presence_lineage_empty_retrieval_must_not_issue_receipt_for_past_chunks(self):
        """C2: Task2 with empty retrieval must NOT issue a presence receipt for C1 with Task2 run_id."""
        state = StructuredEvidenceState(original_query="Lineage test C2")
        state.expected_requirement_ids = {"R1"}
        r1 = EvidenceRequirement(id="R1", description="Cấm sa thải", mandatory=True, linked_evidence_ids=["C1"])
        state.add_requirement(r1)

        # Task 1: returns C1
        state.add_raw_retrieval_output(
            task_id="task_1",
            task_result={"chunks": [{"chunk_id": "C1", "doc_id": "DOC1", "content": "Nội dung C1"}]},
            run_id="run_iter_1",
        )
        state.auto_verify_retrieval(
            task_id="task_1",
            run_id="run_iter_1",
            valid_corpus_doc_ids={"DOC1"},
            valid_corpus_chunk_ids_by_doc={"DOC1": {"C1"}},
            semantic_oracle={("R1", "C1"): EntailmentRelation.ENTAILMENT},
        )

        # Task 2: returns empty retrieval
        state.add_raw_retrieval_output(
            task_id="task_2",
            task_result={"chunks": []},
            run_id="run_iter_2",
        )
        receipts_task2 = state.auto_verify_retrieval(
            task_id="task_2",
            run_id="run_iter_2",
            valid_corpus_doc_ids={"DOC1"},
            valid_corpus_chunk_ids_by_doc={"DOC1": {"C1"}},
            semantic_oracle={("R1", "C1"): EntailmentRelation.ENTAILMENT},
        )

        # EXPECTED: Zero receipts issued for C1 under run_iter_2
        task2_c1_receipts = [r for r in receipts_task2 if r.evidence_id == "C1" and r.run_id == "run_iter_2"]
        self.assertEqual(
            len(task2_c1_receipts),
            0,
            f"C2 DEFECT DETECTED: Task 2 with empty retrieval issued {len(task2_c1_receipts)} receipts for C1 with run_id='run_iter_2'!"
        )

    def test_C3_semantic_oracle_evidence_only_alias_must_not_satisfy_different_requirement(self):
        """C3: R1 and R2 share evidence C1 but have different statements.

        Oracle only certifies claim of R1. R2 must NOT become SATISFIED via evidence-only alias.
        """
        state = StructuredEvidenceState(original_query="Oracle isolation test C3")
        state.expected_requirement_ids = {"R1", "R2"}
        r1 = EvidenceRequirement(id="R1", description="Cấm sa thải lao động", mandatory=True, linked_evidence_ids=["C1"])
        r2 = EvidenceRequirement(id="R2", description="Khung xử phạt vi phạm 100 triệu", mandatory=True, linked_evidence_ids=["C1"])
        state.add_requirement(r1)
        state.add_requirement(r2)

        state.add_raw_retrieval_output(
            task_id="task_1",
            task_result={"chunks": [{"chunk_id": "C1", "doc_id": "DOC1", "content": "Điều 37 cấm sa thải."}]},
            run_id="run_1",
        )

        # Oracle only certifies R1 claim via bound pair, but evidence-only alias 'C1' is also provided:
        oracle = {
            ("R1", "C1"): EntailmentRelation.ENTAILMENT,
            "C1": EntailmentRelation.ENTAILMENT,  # Evidence-only alias
        }

        state.auto_verify_retrieval(
            task_id="task_1",
            run_id="run_1",
            valid_corpus_doc_ids={"DOC1"},
            valid_corpus_chunk_ids_by_doc={"DOC1": {"C1"}},
            semantic_oracle=oracle,
        )

        self.assertEqual(r1.status, RequirementStatus.SATISFIED)
        self.assertNotEqual(
            r2.status,
            RequirementStatus.SATISFIED,
            "C3 DEFECT DETECTED: R2 became SATISFIED via evidence-only alias 'C1' even though oracle only certified R1!"
        )

    def test_C4_benchmark_evaluator_aspect_doc_cross_mismatch_must_be_insufficient(self):
        """C4: Aspect A from D2 and Aspect B from D1 (crossed/swapped) must NOT be evaluated as sufficient."""
        gold = {
            "query_id": "Q_C4",
            "query": "Query C4 cross mismatch",
            "query_category": "multi_aspect",
            "mandatory_requirements": [
                {"requirement_id": "R1", "required_aspects": ["aspect_A"], "expected_doc_ids": ["DOC_1"]},
                {"requirement_id": "R2", "required_aspects": ["aspect_B"], "expected_doc_ids": ["DOC_2"]},
            ],
            "answerability": "ANSWERABLE",
        }

        collector = ExecutionTraceCollector("Q_C4", "Query C4", "A0")
        # Retrieval has aspect_A from DOC_2 (wrong doc!) and aspect_B from DOC_1 (wrong doc!):
        pool = [
            {"chunk_id": "C_A_WRONG", "doc_id": "DOC_2", "aspects": ["aspect_A"]},
            {"chunk_id": "C_B_WRONG", "doc_id": "DOC_1", "aspects": ["aspect_B"]},
        ]
        collector.record_planning(1, {"executor": "Retriever"})
        collector.record_retrieval(1, "task_1", pool)
        collector.record_planning(2, {"executor": "Finish"})
        collector.record_finish_proposed(2, pool)
        collector.record_finish_decision(2, accepted=True, evaluator_status="NO_GATE", decision="FINISH")
        collector.record_generator_call(called=True, answer="Answer")
        collector.record_termination("FINISHED", "Answer", "Finish accepted", 2)

        trace = collector.to_dict()
        res = evaluate_single_trace(trace, gold)

        self.assertFalse(
            res["evidence_genuinely_sufficient"],
            "C4 DEFECT DETECTED: evidence_genuinely_sufficient was True despite crossed/mismatched document scopes!"
        )
        self.assertTrue(
            res["accepted_premature_finish"],
            "C4 DEFECT DETECTED: accepted_premature_finish was False despite evidence coming from wrong documents for both requirements!"
        )


if __name__ == "__main__":
    unittest.main()
