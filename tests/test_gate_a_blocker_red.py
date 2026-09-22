# -*- coding: utf-8 -*-
"""RED Test for Gate A Blocker: auto_verify_retrieval self-certifying retriever chunks.

Vulnerability:
When valid_corpus_chunk_ids_by_doc is None, auto_verify_retrieval() dynamically
builds effective_chunk_mapping from self.evidences.
This allows any unconfirmed chunk returned by the retriever to certify itself as
PROVENANCE_VERIFIED, even though no authoritative corpus mapping confirmed it.

Expected:
Retriever returning a chunk does NOT prove it belongs to the corpus document.
Without an authoritative doc-chunk mapping, provenance must remain PROVENANCE_INVALID
and the requirement must NOT become SATISFIED.
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
    EntailmentRelation,
    RequirementStatus,
    EvidenceRequirement,
    StructuredEvidenceState,
)


class TestGateABlockerRED(unittest.TestCase):

    def test_auto_verify_retrieval_must_not_self_certify_chunks_without_authoritative_mapping(self):
        """When valid_corpus_chunk_ids_by_doc is None, retriever chunks must NOT self-certify."""
        state = StructuredEvidenceState(original_query="Kiểm tra thẩm định nguồn tự chứng thực")
        state.expected_requirement_ids = {"REQ_TEST"}
        req = EvidenceRequirement(
            id="REQ_TEST",
            description="Quy định kiểm tra",
            mandatory=True,
            doc_scope="DOC_UNCONFIRMED_CORPUS",
            linked_evidence_ids=["CHUNK_UNCONFIRMED_123"],
        )
        state.add_requirement(req)

        # Retriever returns a chunk claiming to belong to DOC_UNCONFIRMED_CORPUS:
        state.add_raw_retrieval_output(
            task_id="task_1",
            task_result={
                "chunks": [{
                    "chunk_id": "CHUNK_UNCONFIRMED_123",
                    "doc_id": "DOC_UNCONFIRMED_CORPUS",
                    "content": "Nội dung trả về từ retriever chưa qua chứng thực corpus.",
                    "aspects": [],
                }]
            },
            run_id="run_1",
        )

        oracle = {
            ("REQ_TEST", "CHUNK_UNCONFIRMED_123"): EntailmentRelation.ENTAILMENT,
        }

        # Caller provides valid_corpus_doc_ids, but valid_corpus_chunk_ids_by_doc is NONE:
        state.auto_verify_retrieval(
            task_id="task_1",
            run_id="run_1",
            valid_corpus_doc_ids={"DOC_UNCONFIRMED_CORPUS"},
            valid_corpus_chunk_ids_by_doc=None,  # No authoritative chunk mapping provided!
            semantic_oracle=oracle,
        )

        # EXPECTED: Requirement must NOT be SATISFIED because chunk provenance was not
        # confirmed by an authoritative mapping!
        self.assertNotEqual(
            req.status,
            RequirementStatus.SATISFIED,
            "GATE A VULNERABILITY DETECTED: auto_verify_retrieval() self-certified unconfirmed retriever chunk "
            "into effective_chunk_mapping and marked requirement SATISFIED without authoritative doc-chunk mapping!"
        )


if __name__ == "__main__":
    unittest.main()
