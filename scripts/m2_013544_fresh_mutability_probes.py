# -*- coding: utf-8 -*-
"""Independent Fresh Mutability Probes for M2 candidate (013544).

Targeted reproduction of 2 counterexamples:
1. PROVENANCE MUTATION: Evidence provenance mutated in-place on active evidence.
   Finish Gate must compare both content AND provenance against verified snapshot.
2. MISSING ACTIVE TEXT EVIDENCE: When text evidence is deleted/removed from active state,
   prior receipt must NOT be accepted in fallback branch to declare SUFFICIENT.
3. POSITIVE CONTROL: Valid active evidence with matching content and provenance reaches SUFFICIENT.

Baseline on candidate ZIP 013544: 2 FAIL / 1 PASS.
Target after fix: 3/3 PASS.
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
    ModalityType,
    Provenance,
    RequirementStatus,
    StructuredEvidenceState,
)


class TestM2FreshMutabilityProbes(unittest.TestCase):
    def _create_satisfied_state(self):
        state = StructuredEvidenceState(original_query="Truy vấn kiểm tra tính bất biến của bằng chứng")
        state.expected_requirement_ids = {"R1"}
        req = EvidenceRequirement(
            id="R1", description="Cấm sa thải lao động", mandatory=True, linked_evidence_ids=["C1"]
        )
        state.add_requirement(req)

        content = "Điều 37: Người sử dụng lao động không được sa thải lao động mang thai."
        state.add_raw_retrieval_output(
            task_id="t1",
            task_result={"chunks": [{"chunk_id": "C1", "doc_id": "DOC1", "content": content}]},
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
        return state, req

    # =========================================================================
    # COUNTEREXAMPLE 1: IN-PLACE PROVENANCE MUTATION
    # =========================================================================
    def test_01_provenance_mutation_must_be_rejected_at_finish_gate(self):
        """COUNTEREXAMPLE 1: Mutating evidence provenance in-place must invalidate sufficiency at Finish Gate."""
        state, req = self._create_satisfied_state()

        # In-place provenance mutation: change article from verified coordinate to fabricated coordinate
        state.evidences["C1"].provenance = Provenance(
            doc_id="DOC1",
            chunk_id="C1",
            article="Điều 999_BỊA_ĐẶT",
            page=999,
        )

        # Finish Gate MUST detect that live evidence provenance diverges from verified receipt snapshot
        gate = state.evaluate_finish_gate()
        self.assertNotEqual(
            req.status,
            RequirementStatus.SATISFIED,
            "COUNTEREXAMPLE 1 DETECTED: Requirement remained SATISFIED despite in-place provenance mutation!",
        )
        self.assertNotEqual(
            gate.status,
            EvaluatorStatus.SUFFICIENT,
            "COUNTEREXAMPLE 1 DETECTED: Finish Gate returned SUFFICIENT despite in-place provenance mutation!",
        )

    # =========================================================================
    # COUNTEREXAMPLE 2: MISSING ACTIVE TEXT EVIDENCE
    # =========================================================================
    def test_02_missing_active_text_evidence_must_not_be_sufficient(self):
        """COUNTEREXAMPLE 2: When text evidence is removed from active state, receipt cannot yield SUFFICIENT."""
        state, req = self._create_satisfied_state()

        # Remove text evidence from active state (e.g. evicted, unretrieved, or deleted)
        del state.evidences["C1"]

        # Finish Gate MUST NOT accept a stale receipt for a missing text evidence via fallback branch
        gate = state.evaluate_finish_gate()
        self.assertNotEqual(
            req.status,
            RequirementStatus.SATISFIED,
            "COUNTEREXAMPLE 2 DETECTED: Requirement remained SATISFIED when text evidence was missing from active state!",
        )
        self.assertNotEqual(
            gate.status,
            EvaluatorStatus.SUFFICIENT,
            "COUNTEREXAMPLE 2 DETECTED: Finish Gate returned SUFFICIENT when text evidence was missing from active state!",
        )

    # =========================================================================
    # POSITIVE CONTROL
    # =========================================================================
    def test_03_positive_control_active_evidence_with_matching_content_and_provenance(self):
        """POSITIVE CONTROL: Active evidence with matching content AND provenance verifies to SUFFICIENT."""
        state, req = self._create_satisfied_state()
        gate = state.evaluate_finish_gate()
        self.assertEqual(req.status, RequirementStatus.SATISFIED)
        self.assertEqual(gate.status, EvaluatorStatus.SUFFICIENT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
