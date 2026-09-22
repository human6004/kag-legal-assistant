# -*- coding: utf-8 -*-
"""Positive Controls for M2 Provenance (Clause/Point) and Versioned Oracle Replacement.

Exercises:
1. Positive case for clause and point with bound authoritative source records.
2. Valid content replacement / mutation with explicit hash-bound 3-tuple oracle reaching SUFFICIENT.
"""

from __future__ import annotations

import hashlib
import locale
import os
import sys
import unittest

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

try:
    locale.setlocale(locale.LC_ALL, "Chinese_China.936")
except Exception:
    try:
        locale.setlocale(locale.LC_ALL, "Chinese")
    except Exception:
        pass

CANDIDATE_ROOT = os.path.abspath(
    os.environ.get("CANDIDATE_ROOT")
    or os.path.join(os.path.dirname(__file__), "..")
)
VENDOR_KAG = os.path.join(CANDIDATE_ROOT, "vendor", "KAG")
if not os.path.isdir(VENDOR_KAG):
    wt_vendor = os.environ.get("KAG_VENDOR_ROOT") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "vendor", "KAG"))
    if os.path.isdir(wt_vendor):
        VENDOR_KAG = wt_vendor

if VENDOR_KAG not in sys.path:
    sys.path.insert(0, VENDOR_KAG)
if CANDIDATE_ROOT not in sys.path:
    sys.path.insert(0, CANDIDATE_ROOT)

import kag  # noqa: E402
wt_kag = os.path.join(CANDIDATE_ROOT, "kag")
if wt_kag not in kag.__path__:
    kag.__path__.append(wt_kag)

import kag.solver  # noqa: E402
wt_solver = os.path.join(CANDIDATE_ROOT, "kag", "solver")
if wt_solver not in kag.solver.__path__:
    kag.solver.__path__.append(wt_solver)

from kag.solver.evidence_aware.models import (  # noqa: E402
    EntailmentRelation,
    EvaluatorStatus,
    Evidence,
    EvidenceRequirement,
    FourStageEvidenceVerifier,
    ModalityType,
    Provenance,
    ProvenanceValidationStatus,
    RequirementStatus,
    StructuredEvidenceState,
)


class TestM2TwoBlockersPositiveControls(unittest.TestCase):
    def test_positive_clause_and_point_with_bound_authoritative_record(self):
        """Positive Control: Evidence declaring article, clause, point verifies when bound to authoritative record."""
        ev = Evidence(
            id="C1",
            content="Điều 1 Khoản 1 Điểm a quy định chi tiết.",
            provenance=Provenance(
                doc_id="DOC1",
                chunk_id="C1",
                article="Điều 1",
                clause="Khoản 1",
                point="Điểm a",
                page=1,
            ),
            modality=ModalityType.TEXT,
        )
        # Authority provides structured co-occurring tuple binding article, clause, point, page together
        authoritative_records = {("Điều 1", "Khoản 1", "Điểm a", "1")}
        receipt = FourStageEvidenceVerifier.stage2_verify_provenance(
            evidence=ev,
            valid_corpus_doc_ids={"DOC1"},
            valid_corpus_chunk_ids_by_doc={"DOC1": {"C1"}},
            valid_corpus_coords_by_doc={"DOC1": authoritative_records},
        )
        self.assertEqual(receipt.status, ProvenanceValidationStatus.PROVENANCE_VERIFIED)

    def test_positive_clause_and_point_with_chunk_mapped_authority(self):
        """Positive Control: Evidence declaring clause/point verifies via chunk-scoped coordinates."""
        ev = Evidence(
            id="C1",
            content="Điều 1 Khoản 2 Điểm b về xử phạt.",
            provenance=Provenance(
                doc_id="DOC1",
                chunk_id="C1",
                article="Điều 1",
                clause="Khoản 2",
                point="Điểm b",
            ),
            modality=ModalityType.TEXT,
        )
        # Authority provides chunk-specific coordinates mapping
        chunk_coords_map = {
            "C1": {"Điều 1", "Khoản 2", "Điểm b"}
        }
        receipt = FourStageEvidenceVerifier.stage2_verify_provenance(
            evidence=ev,
            valid_corpus_doc_ids={"DOC1"},
            valid_corpus_chunk_ids_by_doc={"DOC1": {"C1"}},
            valid_corpus_coords_by_doc={"DOC1": chunk_coords_map},
        )
        self.assertEqual(receipt.status, ProvenanceValidationStatus.PROVENANCE_VERIFIED)

    def test_positive_content_replacement_with_versioned_oracle_to_sufficient(self):
        """Positive Control: Valid content replacement with explicit new content hash oracle reaches SUFFICIENT."""
        state = StructuredEvidenceState(original_query="Truy vấn kiểm tra thay thế nội dung")
        state.expected_requirement_ids = {"R1"}
        req = EvidenceRequirement(
            id="R1", description="Nội dung điều luật", mandatory=True, linked_evidence_ids=["C1"]
        )
        state.add_requirement(req)

        # 1. Initial retrieval & satisfaction
        initial_content = "Phiên bản cũ của văn bản pháp luật."
        state.add_raw_retrieval_output(
            task_id="t1",
            task_result={"chunks": [{"chunk_id": "C1", "doc_id": "DOC1", "content": initial_content}]},
            run_id="run_1",
        )
        state.auto_verify_retrieval(
            task_id="t1",
            run_id="run_1",
            valid_corpus_doc_ids={"DOC1"},
            valid_corpus_chunk_ids_by_doc={"DOC1": {"C1"}},
            semantic_oracle={("R1", "C1"): EntailmentRelation.ENTAILMENT},
        )
        self.assertEqual(req.status, RequirementStatus.SATISFIED)
        self.assertEqual(state.evaluate_finish_gate().status, EvaluatorStatus.SUFFICIENT)

        # 2. Ingest replacement content (e.g. updated statutory provision)
        new_content = "Phiên bản mới sửa đổi bổ sung năm 2026."
        new_hash = hashlib.sha256(new_content.encode("utf-8")).hexdigest()
        state.add_raw_retrieval_output(
            task_id="t2",
            task_result={"chunks": [{"chunk_id": "C1", "doc_id": "DOC1", "content": new_content}]},
            run_id="run_2",
        )
        # Prior to verification, status must be fail-closed
        self.assertEqual(req.status, RequirementStatus.UNSATISFIED)
        self.assertEqual(state.evaluate_finish_gate().status, EvaluatorStatus.INCOMPLETE)

        # 3. Verify replacement with explicit 3-tuple oracle matching new content hash
        state.auto_verify_retrieval(
            task_id="t2",
            run_id="run_2",
            valid_corpus_doc_ids={"DOC1"},
            valid_corpus_chunk_ids_by_doc={"DOC1": {"C1"}},
            semantic_oracle={("R1", "C1", new_hash): EntailmentRelation.ENTAILMENT},
        )
        self.assertEqual(req.status, RequirementStatus.SATISFIED)
        gate = state.evaluate_finish_gate()
        self.assertEqual(gate.status, EvaluatorStatus.SUFFICIENT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
