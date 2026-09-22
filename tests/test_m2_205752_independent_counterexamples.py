# -*- coding: utf-8 -*-
"""Independent Counterexamples Reproducer for M2 candidate (205752).

Reproduces:
BUG A: PROVENANCE COORDINATE BYPASS
Evidence with valid doc_id/chunk_id but declaring invalid article/page/span
must NOT be PROVENANCE_VERIFIED. Valid chunk_id must not excuse invalid coordinates.

BUG B: STALE SEMANTIC ORACLE AFTER CONTENT MUTATION
When C1 content is mutated/poisoned, a subsequent verification pass with
stale oracle label (R1, C1) must NOT re-satisfy R1 on the mutated content.
Oracle labels must bind to evidence content version.
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
    or (
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if os.path.basename(os.path.dirname(os.path.abspath(__file__))) in ("tests", "scripts")
        else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
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


class TestM2IndependentCounterexamples(unittest.TestCase):
    # =========================================================================
    # BUG A: PROVENANCE COORDINATE BYPASS
    # =========================================================================
    def test_bug_a_valid_chunk_with_fake_coords_must_be_invalid(self):
        """BUG A: chunk_id is valid, but cited article/page are fabricated.

        chunk_id validity must NOT excuse invalid coordinates.
        """
        ev = Evidence(
            id="E_BYPASS",
            content="Nội dung gắn điều luật bịa đặt.",
            provenance=Provenance(
                doc_id="DOC1",
                chunk_id="C1",
                article="Điều 999_BỊA_ĐẶT",
                page=999,
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
            f"BUG A DETECTED: Valid chunk_id excused fabricated article/page! status={receipt.status}",
        )

    def test_bug_a_valid_chunk_with_fake_coords_in_auto_verify(self):
        """BUG A in auto_verify: fake coords must not reach SATISFIED/SUFFICIENT."""
        state = StructuredEvidenceState(original_query="Bug A query")
        state.expected_requirement_ids = {"R1"}
        req = EvidenceRequirement(id="R1", description="Yêu cầu kiểm tra", mandatory=True)
        state.add_requirement(req)

        ev = Evidence(
            id="C1",
            content="Nội dung điều luật.",
            provenance=Provenance(
                doc_id="DOC1",
                chunk_id="C1",
                article="Điều 999_BỊA_ĐẶT",
                page=999,
            ),
            modality=ModalityType.TEXT,
        )
        state.evidences["C1"] = ev
        state.auto_verify_retrieval(
            task_id=None,
            run_id="run_a",
            retrieved_chunk_ids_in_current_run={"C1"},
            valid_corpus_doc_ids={"DOC1"},
            valid_corpus_chunk_ids_by_doc={"DOC1": {"C1"}},
            valid_corpus_coords_by_doc={"DOC1": {"Điều 1", "1"}},
            semantic_oracle={("R1", "C1"): EntailmentRelation.ENTAILMENT},
        )
        gate = state.evaluate_finish_gate()
        self.assertNotEqual(
            req.status,
            RequirementStatus.SATISFIED,
            "BUG A DETECTED: Requirement became SATISFIED despite fabricated coordinates on chunk!",
        )
        self.assertNotEqual(gate.status, EvaluatorStatus.SUFFICIENT)

    # =========================================================================
    # BUG B: STALE SEMANTIC ORACLE AFTER CONTENT MUTATION
    # =========================================================================
    def test_bug_b_stale_semantic_oracle_after_content_mutation(self):
        """BUG B: R1 is SATISFIED by C1 in Iteration 1.

        In Iteration 2, C1 is overwritten with non-supporting/poisoned content.
        A subsequent verification pass with stale oracle label (R1, C1) must NOT
        re-satisfy R1 on the mutated content without content version binding.
        """
        state = StructuredEvidenceState(original_query="Bug B query")
        state.expected_requirement_ids = {"R1"}
        req = EvidenceRequirement(
            id="R1", description="Cấm sa thải lao động", mandatory=True, linked_evidence_ids=["C1"]
        )
        state.add_requirement(req)

        # Iteration 1: Valid retrieval
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

        # Iteration 2: Content mutation / poisoning on chunk C1
        state.add_raw_retrieval_output(
            task_id="t2",
            task_result={
                "chunks": [
                    {
                        "chunk_id": "C1",
                        "doc_id": "DOC1",
                        "content": "POISON: Cho phép doanh nghiệp sa thải tự do không bị phạt.",
                    }
                ]
            },
            run_id="run_2",
        )

        # Verification pass runs with stale oracle {('R1', 'C1'): ENTAILMENT} that was meant for old content
        state.auto_verify_retrieval(
            task_id="t2",
            run_id="run_2",
            valid_corpus_doc_ids={"DOC1"},
            valid_corpus_chunk_ids_by_doc={"DOC1": {"C1"}},
            semantic_oracle={("R1", "C1"): EntailmentRelation.ENTAILMENT},
        )

        gate = state.evaluate_finish_gate()
        self.assertNotEqual(
            req.status,
            RequirementStatus.SATISFIED,
            "BUG B DETECTED: Stale oracle label (R1, C1) re-satisfied requirement after content mutation!",
        )
        self.assertNotEqual(
            gate.status,
            EvaluatorStatus.SUFFICIENT,
            "BUG B DETECTED: Finish Gate evaluated to SUFFICIENT on poisoned content via stale oracle!",
        )

    # =========================================================================
    # POSITIVE CONTROLS (Must stay green)
    # =========================================================================
    def test_positive_valid_chunk_with_all_matching_coords(self):
        """Positive Control: Real chunk with real matching article/page is verified."""
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

    def test_positive_content_mutation_with_explicit_versioned_oracle(self):
        """Positive Control: After mutation, if oracle explicitly binds new content hash, it satisfies."""
        state = StructuredEvidenceState(original_query="Bug B positive query")
        state.expected_requirement_ids = {"R1"}
        req = EvidenceRequirement(
            id="R1", description="Cấm sa thải", mandatory=True, linked_evidence_ids=["C1"]
        )
        state.add_requirement(req)

        # Mutated content
        new_content = "Văn bản sửa đổi: Cấm sa thải người mang thai và nuôi con nhỏ."
        new_hash = hashlib.sha256(new_content.encode("utf-8")).hexdigest()

        state.add_raw_retrieval_output(
            task_id="t1",
            task_result={
                "chunks": [
                    {
                        "chunk_id": "C1",
                        "doc_id": "DOC1",
                        "content": new_content,
                    }
                ]
            },
            run_id="run_pos",
        )

        # Explicitly versioned oracle key: (requirement_id, chunk_id, content_hash)
        versioned_oracle = {
            ("R1", "C1", new_hash): EntailmentRelation.ENTAILMENT,
        }
        state.auto_verify_retrieval(
            task_id="t1",
            run_id="run_pos",
            valid_corpus_doc_ids={"DOC1"},
            valid_corpus_chunk_ids_by_doc={"DOC1": {"C1"}},
            semantic_oracle=versioned_oracle,
        )
        gate = state.evaluate_finish_gate()
        self.assertEqual(req.status, RequirementStatus.SATISFIED)
        self.assertEqual(gate.status, EvaluatorStatus.SUFFICIENT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
