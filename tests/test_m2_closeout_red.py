# -*- coding: utf-8 -*-
"""RED Tests for M2 Closeout Gate: RED-1 and RED-2.

Reproduces:
RED-1: Requirement R1, evidence C1. Oracle only contains ('R10', 'C1') = ENTAILMENT.
       Currently, R1 matches 'R10' due to subsequence check ('R1' in 'R10') and becomes SATISFIED.
       EXPECTED: R1 must NOT receive R10's label and must NOT become SATISFIED.

RED-2: Document ID is real, chunk ID is unconfirmed in authoritative doc-chunk mapping,
       and mapping is not provided (None).
       Currently, chunk defaults to PROVENANCE_VERIFIED simply because doc_id exists.
       EXPECTED: Chunk must be PROVENANCE_INVALID.
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
    Claim,
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


class TestM2CloseoutDefectsRED(unittest.TestCase):

    def test_RED_1_semantic_oracle_fuzzy_subsequence_leakage(self):
        """RED-1: Requirement R1, evidence C1.

        Oracle ONLY has key ('R10', 'C1') = ENTAILMENT.
        R1 must NOT match ('R10', 'C1') via fuzzy subsequence matching.
        EXPECTED: R1 must NOT become SATISFIED.
        """
        state = StructuredEvidenceState(original_query="Test fuzzy oracle leakage")
        state.expected_requirement_ids = {"R1"}
        r1 = EvidenceRequirement(
            id="R1",
            description="Quy định cấm",
            mandatory=True,
            doc_scope="DOC1",
            linked_evidence_ids=["C1"],
        )
        state.add_requirement(r1)

        # Ingest retrieval for C1
        state.add_raw_retrieval_output(
            task_id="task_1",
            task_result={
                "chunks": [{
                    "chunk_id": "C1",
                    "doc_id": "DOC1",
                    "content": "Nội dung điều khoản C1.",
                    "aspects": [],
                }]
            },
            run_id="run_1",
        )

        # Oracle contains label for R10, NOT R1:
        semantic_oracle = {
            ("R10", "C1"): EntailmentRelation.ENTAILMENT,
        }

        state.auto_verify_retrieval(
            task_id="task_1",
            run_id="run_1",
            valid_corpus_doc_ids={"DOC1"},
            valid_corpus_chunk_ids_by_doc={"DOC1": {"C1"}},
            semantic_oracle=semantic_oracle,
        )

        # ASSERTION: R1 must NOT be SATISFIED!
        self.assertNotEqual(
            r1.status,
            RequirementStatus.SATISFIED,
            "RED-1 DEFECT DETECTED: Requirement 'R1' matched oracle key 'R10' via substring/subsequence fallback and became SATISFIED!"
        )

    def test_RED_2_unmapped_chunk_with_real_doc_must_not_be_provenance_verified(self):
        """RED-2: Document ID is real, chunk ID is arbitrary/unmapped, mapping not provided.

        EXPECTED: Chunk must NOT be PROVENANCE_VERIFIED simply because doc_id exists.
        """
        ev = Evidence(
            id="CHUNK_ARBITRARY_999",
            content="Nội dung tùy ý do caller hoặc retriever bịa đặt.",
            provenance=Provenance(
                doc_id="DOC_REAL_EXISTS",
                chunk_id="CHUNK_ARBITRARY_999",
            ),
            modality=ModalityType.TEXT,
        )

        valid_docs = {"DOC_REAL_EXISTS"}
        # Mapping is NOT provided:
        receipt = FourStageEvidenceVerifier.stage2_verify_provenance(
            evidence=ev,
            valid_corpus_doc_ids=valid_docs,
            valid_corpus_chunk_ids_by_doc=None,
        )

        # ASSERTION: Must NOT be PROVENANCE_VERIFIED!
        self.assertNotEqual(
            receipt.status,
            ProvenanceValidationStatus.PROVENANCE_VERIFIED,
            "RED-2 DEFECT DETECTED: Arbitrary chunk was marked PROVENANCE_VERIFIED simply because DOC_REAL_EXISTS exists, without authoritative chunk mapping!"
        )


if __name__ == "__main__":
    unittest.main()
