# -*- coding: utf-8 -*-
"""Independent Blocker Probe for M2 Grok Review (2026-09-22).

Targeted reproduction of 2 contract defects:
BUG 1: FALSE PROVENANCE
  - Provenance has article, clause, point, page, span.
  - Stage 2 must check ALL declared coordinates (including clause and point).
  - Valid chunk_id must NOT excuse invalid coordinates.
  - Missing authoritative records must fail-closed.
  - Valid coordinates must stay verified.

BUG 2: IN-PLACE MUTATION / STALE RECEIPT
  - In-place mutation of Evidence content bypassing add_raw_retrieval_output
    must NOT retain SATISFIED status or allow EvaluatorStatus.SUFFICIENT at Finish Gate.
  - Finish Gate must compare active evidence content hash against immutable verifier ledger.

Test suite contract: 4 tests total.
Baseline on unpatched candidate: 3 FAIL, 1 PASS.
Target after fix: 4 PASS (4/4).
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
    or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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


class TestM2TwoBlockers(unittest.TestCase):
    # =========================================================================
    # BUG 1: FALSE PROVENANCE (Clause and Point validation)
    # =========================================================================
    def test_01_bug1_fake_clause_on_valid_chunk(self):
        """BUG 1: Stage 2 must check clause coordinate. Valid chunk_id must not excuse fake clause."""
        ev = Evidence(
            id="C1",
            content="Nội dung điều luật.",
            provenance=Provenance(
                doc_id="DOC1",
                chunk_id="C1",
                clause="Khoản 999_BỊA",
            ),
            modality=ModalityType.TEXT,
        )
        receipt = FourStageEvidenceVerifier.stage2_verify_provenance(
            evidence=ev,
            valid_corpus_doc_ids={"DOC1"},
            valid_corpus_chunk_ids_by_doc={"DOC1": {"C1"}},
            valid_corpus_coords_by_doc={"DOC1": {"Điều 1", "1"}},
        )
        self.assertEqual(
            receipt.status,
            ProvenanceValidationStatus.PROVENANCE_INVALID,
            f"BUG 1 DETECTED: Stage 2 ignored fabricated clause! status={receipt.status}",
        )

    def test_02_bug1_fake_point_beside_valid_article(self):
        """BUG 1: Stage 2 must check point coordinate beside real article/page."""
        ev = Evidence(
            id="C1",
            content="Nội dung điều luật.",
            provenance=Provenance(
                doc_id="DOC1",
                chunk_id="C1",
                article="Điều 1",
                page=1,
                point="Điểm 999_BỊA",
            ),
            modality=ModalityType.TEXT,
        )
        receipt = FourStageEvidenceVerifier.stage2_verify_provenance(
            evidence=ev,
            valid_corpus_doc_ids={"DOC1"},
            valid_corpus_chunk_ids_by_doc={"DOC1": {"C1"}},
            valid_corpus_coords_by_doc={"DOC1": {"Điều 1", "1"}},
        )
        self.assertEqual(
            receipt.status,
            ProvenanceValidationStatus.PROVENANCE_INVALID,
            f"BUG 1 DETECTED: Stage 2 ignored fabricated point! status={receipt.status}",
        )

    # =========================================================================
    # BUG 2: IN-PLACE MUTATION / STALE RECEIPT AT FINISH GATE
    # =========================================================================
    def test_03_bug2_inplace_mutation_finish_gate(self):
        """BUG 2: In-place mutation of Evidence object must be caught at Finish Gate via ledger hash."""
        state = StructuredEvidenceState(original_query="Bug 2 query")
        state.expected_requirement_ids = {"R1"}
        req = EvidenceRequirement(
            id="R1", description="Cấm sa thải lao động", mandatory=True, linked_evidence_ids=["C1"]
        )
        state.add_requirement(req)

        # Ingest and satisfy R1
        state.add_raw_retrieval_output(
            task_id="t1",
            task_result={
                "chunks": [
                    {
                        "chunk_id": "C1",
                        "doc_id": "DOC1",
                        "content": "Điều 37: Cấm sa thải lao động mang thai.",
                    }
                ]
            },
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

        # In-place mutation of Evidence object without calling add_raw_retrieval_output
        state.evidences["C1"].content = "POISON: Cho phép doanh nghiệp sa thải tự do."

        # Finish Gate MUST detect content mutation against trusted verifier ledger hash
        gate = state.evaluate_finish_gate()
        self.assertNotEqual(
            req.status,
            RequirementStatus.SATISFIED,
            "BUG 2 DETECTED: Requirement remained SATISFIED despite in-place evidence mutation!",
        )
        self.assertNotEqual(
            gate.status,
            EvaluatorStatus.SUFFICIENT,
            "BUG 2 DETECTED: Finish Gate returned SUFFICIENT despite in-place evidence mutation!",
        )

    # =========================================================================
    # POSITIVE CONTROL
    # =========================================================================
    def test_04_positive_control_valid_coords_and_oracle(self):
        """Positive Control: Valid chunk with all matching valid coordinates verifies cleanly."""
        ev = Evidence(
            id="C1",
            content="Điều 1 quy định chung.",
            provenance=Provenance(
                doc_id="DOC1",
                chunk_id="C1",
                article="Điều 1",
                page=1,
            ),
            modality=ModalityType.TEXT,
        )
        receipt = FourStageEvidenceVerifier.stage2_verify_provenance(
            evidence=ev,
            valid_corpus_doc_ids={"DOC1"},
            valid_corpus_chunk_ids_by_doc={"DOC1": {"C1"}},
            valid_corpus_coords_by_doc={"DOC1": {"Điều 1", "1"}},
        )
        self.assertEqual(receipt.status, ProvenanceValidationStatus.PROVENANCE_VERIFIED)


if __name__ == "__main__":
    unittest.main(verbosity=2)
