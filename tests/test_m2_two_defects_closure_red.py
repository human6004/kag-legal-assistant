# -*- coding: utf-8 -*-
"""RED Tests for M2 Two-Defect Closure.

Reproduces:
1. Semantic Oracle Defect:
   Evidence-only fallback in semantic_oracle (e.g. {'C1': ENTAILMENT}) allows requirements
   to be satisfied without binding entailment to the exact (requirement/claim, evidence) pair.
   EXPECTED: Evidence-only keys must NOT grant entailment. Entailment must strictly require
   the exact (requirement/claim, evidence) pair.

2. Article/Span Provenance Defect:
   Caller-supplied article, span, or page coordinates under a valid doc_id currently default
   to PROVENANCE_VERIFIED without checking against an authoritative coordinates source.
   EXPECTED: Caller self-attestation of article/span coordinates under a valid doc_id must NOT
   default to PROVENANCE_VERIFIED. Without authoritative coordinates confirmation, provenance
   must remain unverified (PROVENANCE_INVALID).
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


class TestM2TwoDefectsClosureRED(unittest.TestCase):

    def test_defect_1_evidence_only_fallback_must_be_completely_eliminated(self):
        """Defect 1: Evidence-only key {'C1': ENTAILMENT} must NOT satisfy requirement.

        Entailment must be bound to the exact requirement/claim and evidence pair.
        """
        state = StructuredEvidenceState(original_query="Truy vấn kiểm tra oracle evidence-only")
        state.expected_requirement_ids = {"REQ_1"}
        req = EvidenceRequirement(
            id="REQ_1",
            description="Quy định cấm sa thải",
            mandatory=True,
            linked_evidence_ids=["C1"],
        )
        state.add_requirement(req)

        state.add_raw_retrieval_output(
            task_id="task_1",
            task_result={"chunks": [{"chunk_id": "C1", "doc_id": "DOC1", "content": "Nội dung C1"}]},
            run_id="run_1",
        )

        # Oracle ONLY provides evidence-only key 'C1', with NO requirement/claim binding:
        evidence_only_oracle = {
            "C1": EntailmentRelation.ENTAILMENT,
        }

        state.auto_verify_retrieval(
            task_id="task_1",
            run_id="run_1",
            valid_corpus_doc_ids={"DOC1"},
            valid_corpus_chunk_ids_by_doc={"DOC1": {"C1"}},
            semantic_oracle=evidence_only_oracle,
        )

        # EXPECTED: Requirement must NOT be satisfied via evidence-only key!
        self.assertNotEqual(
            req.status,
            RequirementStatus.SATISFIED,
            "DEFECT 1 VULNERABILITY: Requirement was satisfied via evidence-only oracle key 'C1' "
            "without binding to the requirement/claim!"
        )

    def test_defect_1_bound_pair_satisfies_only_matching_requirement(self):
        """Defect 1b: Exact pair ('REQ_1', 'C1') satisfies REQ_1, but must NOT satisfy REQ_2."""
        state = StructuredEvidenceState(original_query="Truy vấn kiểm tra oracle cặp (req, ev)")
        state.expected_requirement_ids = {"REQ_1", "REQ_2"}
        req1 = EvidenceRequirement(id="REQ_1", description="Cấm sa thải", mandatory=True, linked_evidence_ids=["C1"])
        req2 = EvidenceRequirement(id="REQ_2", description="Khung phạt 50 triệu", mandatory=True, linked_evidence_ids=["C1"])
        state.add_requirement(req1)
        state.add_requirement(req2)

        state.add_raw_retrieval_output(
            task_id="task_1",
            task_result={"chunks": [{"chunk_id": "C1", "doc_id": "DOC1", "content": "Nội dung C1"}]},
            run_id="run_1",
        )

        # Oracle strictly specifies ('REQ_1', 'C1'):
        pair_oracle = {
            ("REQ_1", "C1"): EntailmentRelation.ENTAILMENT,
        }

        state.auto_verify_retrieval(
            task_id="task_1",
            run_id="run_1",
            valid_corpus_doc_ids={"DOC1"},
            valid_corpus_chunk_ids_by_doc={"DOC1": {"C1"}},
            semantic_oracle=pair_oracle,
        )

        self.assertEqual(req1.status, RequirementStatus.SATISFIED)
        self.assertNotEqual(
            req2.status,
            RequirementStatus.SATISFIED,
            "DEFECT 1 VULNERABILITY: REQ_2 was satisfied even though oracle only bound ('REQ_1', 'C1')!"
        )

    def test_defect_2_caller_self_declared_article_must_not_default_to_verified(self):
        """Defect 2a: Caller self-declaring article under valid doc_id must NOT default to PROVENANCE_VERIFIED."""
        ev = Evidence(
            id="E_FAKE_ARTICLE",
            content="Nội dung điều luật bịa đặt.",
            provenance=Provenance(
                doc_id="DOC_REAL_CORPUS",
                article="Điều 999_BỊA_ĐẶT_KHÔNG_TỒN_TẠI",
            ),
            modality=ModalityType.TEXT,
        )

        # Caller provides valid_corpus_doc_ids containing DOC_REAL_CORPUS, but no coords verification
        receipt = FourStageEvidenceVerifier.stage2_verify_provenance(
            evidence=ev,
            valid_corpus_doc_ids={"DOC_REAL_CORPUS"},
        )

        self.assertNotEqual(
            receipt.status,
            ProvenanceValidationStatus.PROVENANCE_VERIFIED,
            "DEFECT 2 VULNERABILITY: Fabricated article was marked PROVENANCE_VERIFIED simply because "
            "doc_id was valid and caller populated the article field!"
        )
        self.assertEqual(
            receipt.status,
            ProvenanceValidationStatus.PROVENANCE_INVALID,
            "DEFECT 2 EXPECTATION: Coordinates without authoritative verification must remain PROVENANCE_INVALID."
        )

    def test_defect_2_caller_self_declared_span_must_not_default_to_verified(self):
        """Defect 2b: Caller self-declaring span/page under valid doc_id must NOT default to PROVENANCE_VERIFIED."""
        ev = Evidence(
            id="E_FAKE_SPAN",
            content="Nội dung span bịa đặt.",
            provenance=Provenance(
                doc_id="DOC_REAL_CORPUS",
                span="char_9999_to_10000",
                page=999,
            ),
            modality=ModalityType.TEXT,
        )

        receipt = FourStageEvidenceVerifier.stage2_verify_provenance(
            evidence=ev,
            valid_corpus_doc_ids={"DOC_REAL_CORPUS"},
        )

        self.assertNotEqual(
            receipt.status,
            ProvenanceValidationStatus.PROVENANCE_VERIFIED,
            "DEFECT 2 VULNERABILITY: Fabricated span/page was marked PROVENANCE_VERIFIED simply because "
            "doc_id was valid and caller populated the span/page fields!"
        )
        self.assertEqual(
            receipt.status,
            ProvenanceValidationStatus.PROVENANCE_INVALID,
            "DEFECT 2 EXPECTATION: Span/page coordinates without authoritative verification must remain PROVENANCE_INVALID."
        )


if __name__ == "__main__":
    unittest.main()
