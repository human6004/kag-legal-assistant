# -*- coding: utf-8 -*-
"""Test Suite 1: Executable Contract Verification & Counter-Examples (T1 to T6).

Tests against kag.solver.evidence_aware.models to prove:
- T1: SemanticProposal.is_verified=False cannot produce ENTAILMENT or SATISFIED.
- T2: Caller bypassing Stages 1-3 with raw tuples is blocked with SchemaValidationError.
- T3: Graph entity_id arbitrary/fabricated not in run's retrieval fails provenance.
- T4: Caller boolean is_provenance_verified=True without receipt is rejected; conflict remains OPEN.
- T5: Empty state with 0 requirements or 0 mandatory requirements evaluates to INCOMPLETE, never SUFFICIENT.
- T6: Legitimate R1 and R2 verification progression with chained Stage4VerificationReceipt succeeds cleanly.
- Extra: Anti-forgery protections (mismatched run_id, evidence_id, claim_id across stages).
"""

import sys
import os
import locale
import unittest

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

# Ensure vendor KAG is on sys.path first, then extend kag path with research worktree
VENDOR_KAG = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "vendor", "KAG"))
WT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

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
    ConflictResolutionBasis,
    ConflictStatus,
    EntailmentRelation,
    EvaluatorDecision,
    EvaluatorStatus,
    Evidence,
    EvidenceConflict,
    EvidenceRequirement,
    FourStageEvidenceVerifier,
    ModalityType,
    Provenance,
    ProvenanceValidationStatus,
    RequirementStatus,
    SchemaValidationError,
    SemanticProposal,
    StructuredEvidenceState,
)


class TestM2ExecutableContractT1ToT6(unittest.TestCase):

    def test_T1_unverified_proposal_with_quote_match_rejected(self):
        """T1: is_verified=False with quote match yields NEUTRAL and UNSATISFIED."""
        claim = Claim(id="C_UNLAWFUL", statement="Được sa thải lao động mang thai.")
        evidence = Evidence(
            id="E_BLLD_37",
            content="Điều 37 BLLĐ: Không được sa thải lao động vì lý do mang thai.",
            provenance=Provenance(doc_id="DOC_BLLD", chunk_id="C_37"),
            modality=ModalityType.TEXT,
        )
        proposal = SemanticProposal(
            claim_id=claim.id,
            evidence_id=evidence.id,
            predicted_relation=EntailmentRelation.ENTAILMENT,
            confidence=0.99,
            quote="mang thai",
            is_verified=False,
        )

        s1 = FourStageEvidenceVerifier.stage1_verify_presence(evidence.id, {evidence.id})
        s2 = FourStageEvidenceVerifier.stage2_verify_provenance(evidence, {"DOC_BLLD"}, valid_corpus_chunk_ids_by_doc={"DOC_BLLD": {"C_37"}})
        s3 = FourStageEvidenceVerifier.stage3_verify_entailment(
            claim=claim, evidence=evidence, stage1_status=s1, stage2_status=s2, proposal=proposal
        )

        self.assertEqual(s3.relation, EntailmentRelation.NEUTRAL)
        self.assertEqual(s3.source_type, "REJECTED_UNVERIFIED_PROPOSAL")

        v_receipt = FourStageEvidenceVerifier.create_verification_receipt(
            claim=claim, evidence=evidence, stage1_receipt=s1, stage2_receipt=s2, stage3_receipt=s3
        )
        req = EvidenceRequirement(id="REQ_PROHIBITION", description="Quy định cấm", mandatory=True)
        coverage = FourStageEvidenceVerifier.stage4_evaluate_requirement_coverage(req, [v_receipt])
        self.assertEqual(coverage, RequirementStatus.UNSATISFIED)

    def test_T2_caller_bypassing_stages_1_to_3_strictly_blocked(self):
        """T2: Raw unverified tuples supplied directly to Stage 4 raise SchemaValidationError."""
        req = EvidenceRequirement(id="REQ_PENALTY", description="Khung xử phạt", mandatory=True)
        fake_claim = Claim(id="C_FAKE", statement="Phạt 20-40 triệu.")
        fake_evidence = Evidence(
            id="E_FAKE", content="Fake content", provenance=Provenance(doc_id="D", chunk_id="C")
        )
        raw_tuples = [(fake_claim, fake_evidence, EntailmentRelation.ENTAILMENT)]

        with self.assertRaises(SchemaValidationError) as ctx:
            FourStageEvidenceVerifier.stage4_evaluate_requirement_coverage(req, raw_tuples)
        self.assertIn("Stage 1-3 Bypass Attempt Detected", str(ctx.exception))

    def test_T3_fabricated_graph_entity_fails_provenance(self):
        """T3: Fabricated graph entity_id not in run's retrieved graph data returns PROVENANCE_INVALID."""
        retrieved_graph = {"LEGAL_NORM_34", "DECREE_12"}
        fake_graph_evidence = Evidence(
            id="E_GRAPH_FAKE",
            content="Triple: (Doanh nghiệp, bị phạt, 50tr)",
            provenance=Provenance(entity_id="UNKNOWN_FABRICATED_ENTITY_999", relation_id="HAS_PENALTY"),
            modality=ModalityType.GRAPH_TRIPLE,
        )

        s2 = FourStageEvidenceVerifier.stage2_verify_provenance(
            evidence=fake_graph_evidence,
            valid_corpus_doc_ids=set(),
            retrieved_graph_entities_in_run=retrieved_graph,
        )
        self.assertEqual(s2.status, ProvenanceValidationStatus.PROVENANCE_INVALID)

    def test_T4_arbitration_caller_boolean_rejected_conflict_remains_open(self):
        """T4: Caller boolean is_provenance_verified=True rejected; conflict stays OPEN."""
        conflict = EvidenceConflict(
            conflict_id="CONF_001",
            requirement_id="REQ_PENALTY",
            conflicting_evidence_ids=("E1", "E2"),
            status=ConflictStatus.OPEN,
        )
        irrelevant_evidence = Evidence(
            id="E_IRRELEVANT",
            content="Điều 1: Phạm vi áp dụng...",
            provenance=Provenance(doc_id="DOC_GENERAL"),
        )

        with self.assertRaises(SchemaValidationError) as ctx:
            conflict.resolve(
                arbitration_evidence=irrelevant_evidence,
                basis=ConflictResolutionBasis.LEX_POSTERIOR,
                rationale="Caller boolean resolve",
                arbitration_receipt=None,
                is_provenance_verified=True,
            )
        self.assertIn("Untrusted caller boolean rejected", str(ctx.exception))
        self.assertEqual(conflict.status, ConflictStatus.OPEN)

    def test_T5_empty_state_evaluates_to_incomplete_never_sufficient(self):
        """T5: Empty state evaluates to INCOMPLETE / RETRIEVE_MORE."""
        state = StructuredEvidenceState(original_query="Khung xử phạt sa thải lao động mang thai?")
        self.assertEqual(len(state.requirements), 0)

        is_suff, reason = state.is_sufficient()
        self.assertFalse(is_suff)
        self.assertIn("State rỗng", reason)

        eval_out = state.evaluate_finish_gate()
        self.assertEqual(eval_out.status, EvaluatorStatus.INCOMPLETE)
        self.assertEqual(eval_out.next_decision, EvaluatorDecision.RETRIEVE_MORE)

    def test_T6_legitimate_r1_and_r2_progression_succeeds(self):
        """T6: Legitimate R1 and R2 verification progression with full chained receipts."""
        state = StructuredEvidenceState(original_query="Quy định và chế tài sa thải lao động mang thai.")
        r1 = EvidenceRequirement(id="R1", description="Quy định cấm", mandatory=True, required_aspects=["prohibition"])
        r2 = EvidenceRequirement(id="R2", description="Khung xử phạt", mandatory=True, required_aspects=["penalty"])
        state.add_requirement(r1)
        state.add_requirement(r2)

        e1 = Evidence(
            id="E1", content="Cấm sa thải", provenance=Provenance(doc_id="DOC1", chunk_id="C1"), modality=ModalityType.TEXT
        )
        e2 = Evidence(
            id="E2", content="Phạt 10-20tr", provenance=Provenance(doc_id="DOC2", chunk_id="C2"), modality=ModalityType.TEXT
        )
        c1 = Claim(id="C1", statement="Cấm sa thải.")
        c2 = Claim(id="C2", statement="Phạt 10-20tr.")

        valid_chunks = {"DOC1": {"C1"}, "DOC2": {"C2"}}
        # R1 verify
        s1_1 = FourStageEvidenceVerifier.stage1_verify_presence(e1.id, {e1.id, e2.id})
        s2_1 = FourStageEvidenceVerifier.stage2_verify_provenance(e1, {"DOC1", "DOC2"}, valid_corpus_chunk_ids_by_doc=valid_chunks)
        s3_1 = FourStageEvidenceVerifier.stage3_verify_entailment(
            claim=c1, evidence=e1, stage1_status=s1_1, stage2_status=s2_1, ground_truth_relation=EntailmentRelation.ENTAILMENT
        )
        v1 = FourStageEvidenceVerifier.create_verification_receipt(c1, e1, s1_1, s2_1, s3_1)
        r1.covered_aspects = ["prohibition"]
        FourStageEvidenceVerifier.stage4_evaluate_requirement_coverage(r1, [v1])

        # R2 verify
        s1_2 = FourStageEvidenceVerifier.stage1_verify_presence(e2.id, {e1.id, e2.id})
        s2_2 = FourStageEvidenceVerifier.stage2_verify_provenance(e2, {"DOC1", "DOC2"}, valid_corpus_chunk_ids_by_doc=valid_chunks)
        s3_2 = FourStageEvidenceVerifier.stage3_verify_entailment(
            claim=c2, evidence=e2, stage1_status=s1_2, stage2_status=s2_2, ground_truth_relation=EntailmentRelation.ENTAILMENT
        )
        v2 = FourStageEvidenceVerifier.create_verification_receipt(c2, e2, s1_2, s2_2, s3_2)
        r2.covered_aspects = ["penalty"]
        FourStageEvidenceVerifier.stage4_evaluate_requirement_coverage(r2, [v2])

        self.assertEqual(r1.status, RequirementStatus.SATISFIED)
        self.assertEqual(r2.status, RequirementStatus.SATISFIED)

        eval_out = state.evaluate_finish_gate()
        self.assertEqual(eval_out.status, EvaluatorStatus.SUFFICIENT)
        self.assertEqual(eval_out.next_decision, EvaluatorDecision.FINISH)

    def test_extra_receipt_anti_forgery_protections(self):
        """Cross-stage receipt tampering (mismatched run_id, evidence_id, claim_id) is blocked."""
        e1 = Evidence(id="E1", content="Nội dung 1", provenance=Provenance(doc_id="D1", chunk_id="C1"))
        c1 = Claim(id="C1", statement="Claim 1")
        s1 = FourStageEvidenceVerifier.stage1_verify_presence("E1", {"E1"}, run_id="run_100")
        s2 = FourStageEvidenceVerifier.stage2_verify_provenance(e1, {"D1"}, run_id="run_100")
        s3 = FourStageEvidenceVerifier.stage3_verify_entailment(
            claim=c1, evidence=e1, stage1_status=s1, stage2_status=s2,
            ground_truth_relation=EntailmentRelation.ENTAILMENT, run_id="run_100"
        )

        # 1. Tampering with run_id mismatch
        with self.assertRaises(SchemaValidationError) as ctx1:
            FourStageEvidenceVerifier.create_verification_receipt(
                c1, e1, s1, s2, s3, run_id="run_FORGED_DIFFERENT"
            )
        self.assertIn("run_id mismatch", str(ctx1.exception))

        # 2. Tampering with evidence_id mismatch
        s1_wrong = FourStageEvidenceVerifier.stage1_verify_presence("E_OTHER", {"E_OTHER"}, run_id="run_100")
        with self.assertRaises(SchemaValidationError) as ctx2:
            FourStageEvidenceVerifier.create_verification_receipt(
                c1, e1, s1_wrong, s2, s3, run_id="run_100"
            )
        self.assertIn("evidence_id mismatch", str(ctx2.exception))


if __name__ == "__main__":
    unittest.main()
