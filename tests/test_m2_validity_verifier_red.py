# -*- coding: utf-8 -*-
"""RED Tests for Gate 1: Verifier Integrity Deficiencies (V1 & V2).

Reproduces:
V1: Stage 3 yields NEUTRAL, Stage 4 receipt has relation mutated to ENTAILMENT
    while keeping the token intact. Currently accepted as SATISFIED because
    the token hash does not bind the semantic relation.
V2: Caller crafts Stage 1-4 receipts without passing through verifier issuance,
    computes the matching token payload, and calls register_issued_token().
    Currently accepted as SATISFIED because token registration is an open public set.
"""

import sys
import os
import unittest
import hashlib
import time
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
    PresenceStatus,
    ProvenanceValidationStatus,
    EntailmentRelation,
    RequirementStatus,
    Stage1PresenceReceipt,
    Stage2ProvenanceReceipt,
    Stage3EntailmentReceipt,
    Stage4VerificationReceipt,
    FourStageEvidenceVerifier,
    EvidenceRequirement,
    StructuredEvidenceState,
    SchemaValidationError,
)


class TestM2VerifierIntegrityRED(unittest.TestCase):

    def test_V1_relation_mutation_on_neutral_receipt_must_be_rejected(self):
        """V1: Stage 3 = NEUTRAL. Stage 4 receipt relation mutated to ENTAILMENT.

        Expected: Stage 4 must reject the receipt and NOT satisfy requirement.
        """
        claim = Claim(id="CLM_1", statement="Tổ chức vi phạm bị xử phạt")
        evidence = Evidence(
            id="EV_1",
            content="Quy định chung về an ninh mạng.",
            provenance=Provenance(doc_id="DOC_1", chunk_id="EV_1"),
            modality=ModalityType.TEXT,
            aspects=["penalty"],
        )

        r1 = Stage1PresenceReceipt(evidence_id="EV_1", run_id="run_1", status=PresenceStatus.PRESENCE_CONFIRMED)
        r2 = Stage2ProvenanceReceipt(
            evidence_id="EV_1",
            run_id="run_1",
            status=ProvenanceValidationStatus.PROVENANCE_VERIFIED,
            modality=ModalityType.TEXT,
            verified_corpus_doc_id="DOC_1",
            verified_chunk_id="EV_1",
        )
        # Stage 3 is genuinely NEUTRAL:
        r3 = Stage3EntailmentReceipt(
            claim_id="CLM_1",
            evidence_id="EV_1",
            run_id="run_1",
            relation=EntailmentRelation.NEUTRAL,
            source_type="FIXTURE_GROUND_TRUTH",
        )

        query_hash = hashlib.sha256("câu hỏi kiểm tra".encode("utf-8")).hexdigest()
        receipt = FourStageEvidenceVerifier.create_verification_receipt(
            claim=claim,
            evidence=evidence,
            stage1_receipt=r1,
            stage2_receipt=r2,
            stage3_receipt=r3,
            run_id="run_1",
            requirement_id="REQ_1",
            query_hash=query_hash,
        )

        # Adversarial tamper: caller mutates Stage 4 relation to ENTAILMENT while keeping token
        # In python dataclass, if frozen, object.__setattr__ mutates it
        object.__setattr__(receipt, "relation", EntailmentRelation.ENTAILMENT)

        req = EvidenceRequirement(id="REQ_1", description="Phải có chế tài", mandatory=True, required_aspects=["penalty"])

        # Stage 4 evaluation MUST reject this tampered receipt!
        with self.assertRaises(SchemaValidationError, msg="V1 DEFECT: Stage 4 accepted tampered relation=ENTAILMENT on NEUTRAL Stage 3 receipt!"):
            FourStageEvidenceVerifier.stage4_evaluate_requirement_coverage(
                requirement=req,
                entailment_results=[receipt],
            )

    def test_V2_caller_forged_receipt_via_register_issued_token_must_be_rejected(self):
        """V2: Caller crafts Stage 1-4 receipts without verifier issuance and registers token.

        Expected: Stage 4 must reject because receipt was not issued by trusted verifier ledger.
        """
        claim = Claim(id="CLM_FORGED", statement="Khung phạt 100 triệu")
        evidence = Evidence(
            id="EV_FORGED",
            content="Phạt tiền 100 triệu.",
            provenance=Provenance(doc_id="DOC_1", chunk_id="EV_FORGED"),
            modality=ModalityType.TEXT,
            aspects=["penalty"],
        )

        t1 = time.time()
        r1 = Stage1PresenceReceipt(evidence_id="EV_FORGED", run_id="run_forged", status=PresenceStatus.PRESENCE_CONFIRMED, timestamp=t1)
        r2 = Stage2ProvenanceReceipt(
            evidence_id="EV_FORGED",
            run_id="run_forged",
            status=ProvenanceValidationStatus.PROVENANCE_VERIFIED,
            modality=ModalityType.TEXT,
            verified_corpus_doc_id="DOC_1",
            verified_chunk_id="EV_FORGED",
            timestamp=t1,
        )
        r3 = Stage3EntailmentReceipt(
            claim_id="CLM_FORGED",
            evidence_id="EV_FORGED",
            run_id="run_forged",
            relation=EntailmentRelation.ENTAILMENT,
            source_type="FIXTURE_GROUND_TRUTH",
            timestamp=t1,
        )

        query_hash = hashlib.sha256("query forged".encode("utf-8")).hexdigest()

        # Forge token using known formula:
        token_payload = f"{query_hash}:REQ_FORGED:run_forged:CLM_FORGED:EV_FORGED:{t1}:{t1}:{t1}"
        forged_token = hashlib.sha256(token_payload.encode("utf-8")).hexdigest()

        # Caller registers forged token via public method:
        FourStageEvidenceVerifier.register_issued_token(forged_token)

        forged_receipt = Stage4VerificationReceipt(
            run_id="run_forged",
            claim_id="CLM_FORGED",
            evidence_id="EV_FORGED",
            stage1_receipt=r1,
            stage2_receipt=r2,
            stage3_receipt=r3,
            claim=claim,
            evidence=evidence,
            relation=EntailmentRelation.ENTAILMENT,
            token=forged_token,
            requirement_id="REQ_FORGED",
            query_hash=query_hash,
        )

        req = EvidenceRequirement(id="REQ_FORGED", description="Forged requirement", mandatory=True, required_aspects=["penalty"])

        # Stage 4 MUST reject this unissued forged receipt!
        with self.assertRaises(SchemaValidationError, msg="V2 DEFECT: Stage 4 accepted forged receipt registered via register_issued_token()!"):
            FourStageEvidenceVerifier.stage4_evaluate_requirement_coverage(
                requirement=req,
                entailment_results=[forged_receipt],
            )


if __name__ == "__main__":
    unittest.main()
