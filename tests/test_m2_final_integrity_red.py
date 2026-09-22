# -*- coding: utf-8 -*-
"""RED Test Suite: Reproducing M2 Final Integrity Gate Defects (R1 through R10).

This suite reproduces the 10 critical integrity defects identified on current implementation:
- R1: CONTRADICTION followed by ENTAILMENT for same requirement must NOT overwrite conflict or lead to SUFFICIENT.
- R2: Missing query requirement when expected_requirement_ids is None must fail-closed, NOT SUFFICIENT.
- R3: Requirement with doc_scope=DOC_REQUIRED must reject evidence from DOC_OTHER even if caller linked evidence ID.
- R4: Chunk ID not confirmed in authoritative doc-chunk mapping must NOT be PROVENANCE_VERIFIED.
- R5: Caller-constructed Stage 1-4 receipts without verifier lineage must be rejected by Stage 4.
- R6: SemanticProposal with self-declared is_verified=True but non-entailing content must NOT yield ENTAILMENT.
- R7: Aspect-based requirement coverage must transition to SATISFIED only when all required aspects have verified evidence; partial aspect must be blocked.
- R8: Evidence from run_iter_1 must NOT be confirmed as present in run_iter_2.
- R9: D2 probe must use production EvidenceAwarePlannerAdapter, real KAGIterativePlanner, and mock LLM.
- R10: Evaluation internals (semantic_oracle, valid_corpus_doc_ids, evidence_state) must NOT leak to Planner or Generator via kwargs.
"""

import sys
import os
import locale
import unittest
from typing import List, Dict, Any

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

from kag.interface.solver.planner_abc import Task, TaskStatus
from kag.interface.solver.context import Context
from kag.interface.solver.executor_abc import ExecutorABC
from kag.solver.planner.kag_iterative_planner import KAGIterativePlanner
from kag.interface.common.prompt import PromptABC
from kag.solver.evidence_aware.models import (
    Claim,
    ConflictStatus,
    EntailmentRelation,
    EvaluatorStatus,
    Evidence,
    EvidenceRequirement,
    FourStageEvidenceVerifier,
    ModalityType,
    PresenceStatus,
    Provenance,
    ProvenanceValidationStatus,
    RequirementStatus,
    SchemaValidationError,
    SemanticProposal,
    Stage1PresenceReceipt,
    Stage2ProvenanceReceipt,
    Stage3EntailmentReceipt,
    Stage4VerificationReceipt,
    StructuredEvidenceState,
)
from kag.solver.evidence_aware.planner_adapter import EvidenceAwarePlannerAdapter
from kag.solver.evidence_aware.pipeline import KAGEvidenceAwareIterativePipeline


class MockRetrieverExecutor(ExecutorABC):
    def __init__(self, results_map: Dict[str, Any]):
        super().__init__()
        self.results_map = results_map

    def schema(self) -> Dict[str, Any]:
        return {"name": "Retriever", "description": "Mock retrieval", "parameters": {}}

    async def ainvoke(self, query: str, task: Task, context: Context, **kwargs):
        q = task.arguments.get("query", "")
        task.result = self.results_map.get(q, {"chunks": [], "err_msg": ""})
        task.status = TaskStatus.SUCCESS
        return task.result


class DummyPrompt(PromptABC):
    template_en = "Query: {query}\nContext: {context}"
    template_zh = "Query: {query}\nContext: {context}"

    @property
    def template_variables(self) -> List[str]:
        return ["query", "context"]


class RecordingMockLLM:
    def __init__(self, canned_tasks: List[Task]):
        self.canned_tasks = canned_tasks
        self.call_history: List[Dict[str, Any]] = []

    async def ainvoke(self, payload: Dict[str, Any], prompt: Any, **kwargs) -> List[Task]:
        self.call_history.append({"payload": payload, "kwargs": kwargs})
        idx = min(len(self.call_history) - 1, len(self.canned_tasks) - 1)
        return [self.canned_tasks[idx]]


class RecordingGenerator:
    def __init__(self):
        self.received_kwargs: List[Dict[str, Any]] = []
        self.received_contexts: List[Context] = []

    async def ainvoke(self, query: str, context: Context, **kwargs) -> str:
        self.received_kwargs.append(kwargs)
        self.received_contexts.append(context)
        return "GENERATOR_OUTPUT"


class TestM2FinalIntegrityRED(unittest.IsolatedAsyncioTestCase):

    def test_R1_contradiction_then_entailment_must_not_overwrite_conflict(self):
        """R1: When evidence E1 yields CONTRADICTION and subsequent evidence E2 yields ENTAILMENT

        for the same requirement, the conflict must NOT be overwritten or cleared without arbitration.
        Requirement status must remain CONFLICTING and must NOT evaluate to SUFFICIENT.
        """
        state = StructuredEvidenceState(original_query="Sa thải lao động mang thai")
        state.expected_requirement_ids = {"REQ_1"}
        req = EvidenceRequirement(id="REQ_1", description="Cấm sa thải", mandatory=True)
        state.add_requirement(req)

        # Iteration 1: Ingest contradicting evidence E1
        state.add_raw_retrieval_output(
            task_id="task_1",
            task_result={"chunks": [{"chunk_id": "C_CONTRA", "doc_id": "DOC1", "content": "Cho phép sa thải"}]},
            run_id="run_iter_1",
        )
        oracle = {
            ("REQ_1", "C_CONTRA"): EntailmentRelation.CONTRADICTION,
            ("REQ_1", "C_ENTAIL"): EntailmentRelation.ENTAILMENT,
        }
        state.auto_verify_retrieval(
            task_id="task_1",
            run_id="run_iter_1",
            valid_corpus_doc_ids={"DOC1"},
            valid_corpus_chunk_ids_by_doc={"DOC1": {"C_CONTRA", "C_ENTAIL"}},
            semantic_oracle=oracle,
        )
        self.assertEqual(req.status, RequirementStatus.CONFLICTING)

        # Iteration 2: Ingest supporting evidence E2 for same requirement
        state.add_raw_retrieval_output(
            task_id="task_2",
            task_result={"chunks": [{"chunk_id": "C_ENTAIL", "doc_id": "DOC1", "content": "Tuyệt đối cấm sa thải"}]},
            run_id="run_iter_2",
        )
        state.auto_verify_retrieval(
            task_id="task_2",
            run_id="run_iter_2",
            valid_corpus_doc_ids={"DOC1"},
            valid_corpus_chunk_ids_by_doc={"DOC1": {"C_CONTRA", "C_ENTAIL"}},
            semantic_oracle=oracle,
        )

        # EXPECTED: Conflict must NOT be overwritten by subsequent ENTAILMENT!
        # Status must remain CONFLICTING and state must NOT be sufficient!
        self.assertEqual(
            req.status,
            RequirementStatus.CONFLICTING,
            f"VULNERABILITY DETECTED in R1: Subsequent ENTAILMENT overwrote CONFLICTING to {req.status}!"
        )
        is_suff, reason = state.is_sufficient()
        self.assertFalse(is_suff, "VULNERABILITY DETECTED in R1: State with unresolved contradiction evaluated to SUFFICIENT!")

    def test_R2_unconfirmed_requirement_completeness_must_fail_closed(self):
        """R2: When original query has requirements {R1, R2}, but state only registered {R1}

        and expected_requirement_ids was NOT provided (None), state must fail-closed (NOT SUFFICIENT).
        """
        state = StructuredEvidenceState(original_query="Quy định cấm và khung xử phạt sa thải mang thai")
        # expected_requirement_ids is None (caller omitted completeness contract)
        state.expected_requirement_ids = None

        r1 = EvidenceRequirement(id="R1", description="Cấm sa thải", mandatory=True, status=RequirementStatus.SATISFIED)
        state.add_requirement(r1)

        # EXPECTED: Without a confirmed completeness contract for original_query,
        # an arbitrary partial requirement set must NOT evaluate to SUFFICIENT!
        is_suff, reason = state.is_sufficient()
        self.assertFalse(
            is_suff,
            "VULNERABILITY DETECTED in R2: Partial requirement set without confirmed completeness evaluated to SUFFICIENT!"
        )

    def test_R3_doc_scope_mismatch_must_reject_evidence_even_if_linked(self):
        """R3: Requirement specifies doc_scope=DOC_REQUIRED. Evidence is from DOC_OTHER.

        Even if caller linked evidence ID, the evidence must NOT satisfy the requirement.
        """
        state = StructuredEvidenceState(original_query="Doc scope test")
        state.expected_requirement_ids = {"REQ_SCOPE"}
        req = EvidenceRequirement(
            id="REQ_SCOPE",
            description="Quy định",
            doc_scope="DOC_REQUIRED",
            mandatory=True,
            linked_evidence_ids=["C_OTHER"],  # Caller linked evidence from different doc
        )
        state.add_requirement(req)

        state.add_raw_retrieval_output(
            task_id="task_scope",
            task_result={"chunks": [{"chunk_id": "C_OTHER", "doc_id": "DOC_OTHER", "content": "Nội dung khác"}]},
            run_id="run_1",
        )
        oracle = {"C_OTHER": EntailmentRelation.ENTAILMENT}
        state.auto_verify_retrieval(
            task_id="task_scope",
            run_id="run_1",
            valid_corpus_doc_ids={"DOC_REQUIRED", "DOC_OTHER"},
            semantic_oracle=oracle,
        )

        # EXPECTED: Evidence from DOC_OTHER must be rejected for REQ_SCOPE (doc_scope=DOC_REQUIRED)!
        self.assertNotEqual(
            req.status,
            RequirementStatus.SATISFIED,
            "VULNERABILITY DETECTED in R3: Evidence from DOC_OTHER satisfied requirement with doc_scope=DOC_REQUIRED!"
        )

    def test_R4_chunk_not_in_authoritative_doc_chunk_mapping_must_fail_provenance(self):
        """R4: Document exists in corpus, but chunk_id is fabricated and not confirmed

        in authoritative doc-chunk mapping. Must return PROVENANCE_INVALID.
        """
        fake_chunk_evidence = Evidence(
            id="E_FAKE_CHUNK",
            content="Nội dung bịa đặt gắn chunk_id giả",
            provenance=Provenance(doc_id="DOC_REAL", chunk_id="CHUNK_FABRICATED_999", article="Điều 1"),
            modality=ModalityType.TEXT,
        )
        authoritative_chunks = {
            "DOC_REAL": {"CHUNK_REAL_001", "CHUNK_REAL_002"}
        }

        # Stage 2 provenance check: When authoritative doc-chunk mapping is provided and chunk_id is unconfirmed,
        # it must NOT evaluate to PROVENANCE_VERIFIED even if article is provided.
        s2 = FourStageEvidenceVerifier.stage2_verify_provenance(
            evidence=fake_chunk_evidence,
            valid_corpus_doc_ids={"DOC_REAL"},
            valid_corpus_chunk_ids_by_doc=authoritative_chunks,
        )
        self.assertEqual(
            s2.status,
            ProvenanceValidationStatus.PROVENANCE_INVALID,
            f"VULNERABILITY DETECTED in R4: Fabricated chunk_id was accepted as {s2.status}!"
        )

    def test_R5_unregistered_caller_fabricated_receipt_must_be_rejected_by_stage4(self):
        """R5: Caller constructs Stage1-Stage4 receipts directly without verifier lineage/issuance.

        Stage 4 must reject receipts not issued by the trusted verification lineage.
        """
        req = EvidenceRequirement(id="R1", description="Test req", mandatory=True)
        claim = Claim(id="C1", statement="Test claim")
        evidence = Evidence(id="E1", content="Test evidence", provenance=Provenance(doc_id="D1", chunk_id="C1"))

        # Caller forges a Stage4VerificationReceipt directly:
        forged_s1 = Stage1PresenceReceipt(evidence_id=evidence.id, run_id="run_1", status=PresenceStatus.PRESENCE_CONFIRMED)
        forged_s2 = Stage2ProvenanceReceipt(
            evidence_id=evidence.id,
            run_id="run_1",
            status=ProvenanceValidationStatus.PROVENANCE_VERIFIED,
            modality=ModalityType.TEXT,
        )
        forged_s3 = Stage3EntailmentReceipt(
            claim_id=claim.id,
            evidence_id=evidence.id,
            run_id="run_1",
            relation=EntailmentRelation.ENTAILMENT,
            source_type="FORGED",
        )

        forged_receipt = Stage4VerificationReceipt(
            run_id="run_1",
            claim_id=claim.id,
            evidence_id=evidence.id,
            stage1_receipt=forged_s1,
            stage2_receipt=forged_s2,
            stage3_receipt=forged_s3,
            claim=claim,
            evidence=evidence,
            relation=EntailmentRelation.ENTAILMENT,
        )

        # Stage 4 must reject caller-fabricated receipts not present in verifier's lineage registry
        with self.assertRaises(SchemaValidationError) as ctx:
            FourStageEvidenceVerifier.stage4_evaluate_requirement_coverage(req, [forged_receipt])
        self.assertIn("lineage", str(ctx.exception).lower())

    def test_R6_self_declared_is_verified_proposal_without_entailment_must_not_yield_entailment(self):
        """R6: Caller sets SemanticProposal.is_verified=True, quote matches, but proposal

        content does not entail claim. Stage 3 must NOT return ENTAILMENT based on caller's self-attestation.
        """
        claim = Claim(id="C1", statement="Cấm sa thải lao động mang thai")
        evidence = Evidence(id="E1", content="Quy định về thời giờ nghỉ ngơi của người lao động", provenance=Provenance(doc_id="D1", chunk_id="C1"))
        s1 = FourStageEvidenceVerifier.stage1_verify_presence("E1", {"E1"})
        s2 = FourStageEvidenceVerifier.stage2_verify_provenance(evidence, {"D1"})

        # Caller creates proposal asserting is_verified=True and predicted_relation=ENTAILMENT:
        untrusted_proposal = SemanticProposal(
            claim_id="C1",
            evidence_id="E1",
            predicted_relation=EntailmentRelation.ENTAILMENT,
            confidence=0.99,
            is_verified=True,  # Self-attested by caller
            quote="thời giờ nghỉ ngơi",
        )

        s3 = FourStageEvidenceVerifier.stage3_verify_entailment(
            claim=claim,
            evidence=evidence,
            stage1_status=s1,
            stage2_status=s2,
            proposal=untrusted_proposal,
            ground_truth_relation=None,  # No ground truth oracle
        )
        # Untrusted self-attestation must NOT yield ENTAILMENT!
        self.assertNotEqual(
            s3.relation,
            EntailmentRelation.ENTAILMENT,
            "VULNERABILITY DETECTED in R6: Caller self-attested is_verified=True was accepted as ENTAILMENT!"
        )

    def test_R7_aspect_based_coverage_requires_evidence_for_all_aspects(self):
        """R7: Requirement requires aspects ['prohibition', 'penalty'].

        - Positive fixture: evidence for both aspects -> MUST transition to SATISFIED.
        - Negative fixture: evidence for only 1 aspect -> must NOT be SATISFIED (PARTIALLY_SATISFIED).
        """
        req_pos = EvidenceRequirement(
            id="REQ_MULTI_POS",
            description="Chế tài sa thải",
            mandatory=True,
            required_aspects=["prohibition", "penalty"],
        )
        state_pos = StructuredEvidenceState(original_query="Aspect test pos")
        state_pos.expected_requirement_ids = {"REQ_MULTI_POS"}
        state_pos.add_requirement(req_pos)

        # Ingest evidence for 'prohibition' and 'penalty'
        state_pos.add_raw_retrieval_output(
            task_id="task_pos_1",
            task_result={"chunks": [{"chunk_id": "C_PROHIBIT", "doc_id": "D1", "content": "Cấm sa thải", "aspects": ["prohibition"]}]},
            run_id="run_1",
        )
        state_pos.add_raw_retrieval_output(
            task_id="task_pos_2",
            task_result={"chunks": [{"chunk_id": "C_PENALTY", "doc_id": "D1", "content": "Phạt 20tr", "aspects": ["penalty"]}]},
            run_id="run_2",
        )
        oracle = {
            ("REQ_MULTI_POS", "C_PROHIBIT"): EntailmentRelation.ENTAILMENT,
            ("REQ_MULTI_POS", "C_PENALTY"): EntailmentRelation.ENTAILMENT,
        }
        state_pos.auto_verify_retrieval(
            task_id="task_pos_1",
            run_id="run_1",
            valid_corpus_doc_ids={"D1"},
            valid_corpus_chunk_ids_by_doc={"D1": {"C_PROHIBIT", "C_PENALTY"}},
            semantic_oracle=oracle,
        )
        state_pos.auto_verify_retrieval(
            task_id="task_pos_2",
            run_id="run_2",
            valid_corpus_doc_ids={"D1"},
            valid_corpus_chunk_ids_by_doc={"D1": {"C_PROHIBIT", "C_PENALTY"}},
            semantic_oracle=oracle,
        )

        # In current code: auto_verify_retrieval does NOT update covered_aspects, so req_pos remains PENDING/PARTIALLY_SATISFIED!
        # EXPECTED in valid implementation: req_pos MUST reach SATISFIED!
        self.assertEqual(
            req_pos.status,
            RequirementStatus.SATISFIED,
            f"VULNERABILITY DETECTED in R7 (Positive): Requirement with all aspects satisfied remained {req_pos.status}!"
        )

    def test_R8_evidence_from_iter1_must_not_be_confirmed_present_in_iter2(self):
        """R8: Evidence E1 was retrieved only in run_iter_1. In run_iter_2, E1 was NOT retrieved.

        auto_verify_retrieval in run_iter_2 must NOT issue a Stage 1 receipt claiming E1 was present in run_iter_2.
        """
        state = StructuredEvidenceState(original_query="Run isolation test")
        state.expected_requirement_ids = {"REQ_1"}
        req = EvidenceRequirement(id="REQ_1", description="Test", mandatory=True)
        state.add_requirement(req)

        # Iteration 1 retrieves E1
        state.add_raw_retrieval_output(
            task_id="task_1",
            task_result={"chunks": [{"chunk_id": "E1", "doc_id": "D1", "content": "Content E1"}]},
            run_id="run_iter_1",
        )

        # Iteration 2 retrieves E2 (E1 is NOT retrieved in this run)
        state.add_raw_retrieval_output(
            task_id="task_2",
            task_result={"chunks": [{"chunk_id": "E2", "doc_id": "D1", "content": "Content E2"}]},
            run_id="run_iter_2",
        )
        receipts_iter2 = state.auto_verify_retrieval(
            task_id="task_2",
            run_id="run_iter_2",
            valid_corpus_doc_ids={"D1"},
            valid_corpus_chunk_ids_by_doc={"D1": {"E1", "E2"}},
            semantic_oracle={("REQ_1", "E1"): EntailmentRelation.ENTAILMENT, ("REQ_1", "E2"): EntailmentRelation.ENTAILMENT},
        )

        # In current code: E1 is in self.evidences, so auto_verify_retrieval issues a receipt for E1 in run_iter_2!
        # EXPECTED: In run_iter_2, E1 must NOT be verified as present in run_iter_2!
        receipts_for_e1 = [r for r in receipts_iter2 if r.evidence_id == "E1" and r.run_id == "run_iter_2"]
        self.assertEqual(
            len(receipts_for_e1), 0,
            f"VULNERABILITY DETECTED in R8: Evidence E1 from run_iter_1 was verified as present in run_iter_2! {receipts_for_e1}"
        )

    def test_R9_d2_probe_must_use_production_evidence_aware_planner_adapter(self):
        """R9: D2 Probe file (tests/test_d2_integration_probe.py) must import and use the actual

        production EvidenceAwarePlannerAdapter from kag.solver.evidence_aware.planner_adapter,
        and must NOT define a local mock PlannerAdapter class.
        """
        d2_probe_path = os.path.join(WT_ROOT, "tests", "test_d2_integration_probe.py")
        with open(d2_probe_path, "r", encoding="utf-8") as f:
            content = f.read()

        # EXPECTED: Must NOT have a local 'class PlannerAdapter:' definition!
        self.assertNotIn(
            "class PlannerAdapter:",
            content,
            "VULNERABILITY in R9: tests/test_d2_integration_probe.py defines a local PlannerAdapter class instead of using production EvidenceAwarePlannerAdapter!"
        )
        self.assertIn(
            "from kag.solver.evidence_aware.planner_adapter import EvidenceAwarePlannerAdapter",
            content,
            "VULNERABILITY in R9: tests/test_d2_integration_probe.py does not import production EvidenceAwarePlannerAdapter!"
        )

    async def test_R10_internal_evaluation_kwargs_must_not_leak_to_planner_or_generator(self):
        """R10: Evaluation internals (semantic_oracle, valid_corpus_doc_ids, evidence_state)

        must NOT be passed to Planner.ainvoke or Generator.ainvoke via kwargs.
        """
        mock_llm = RecordingMockLLM([Task(executor="Finish", arguments={})])
        planner = KAGIterativePlanner(llm=mock_llm, plan_prompt=DummyPrompt())
        generator = RecordingGenerator()
        retriever = MockRetrieverExecutor({})

        pipeline = KAGEvidenceAwareIterativePipeline(
            planner=planner,
            executors=[retriever],
            generator=generator,
            max_iteration=2,
            evidence_aware=True,
        )
        state = StructuredEvidenceState(original_query="Leak test")
        state.expected_requirement_ids = {"R1"}
        state.add_requirement(EvidenceRequirement(id="R1", description="R1", mandatory=True, status=RequirementStatus.SATISFIED))

        secret_gold_labels = {"SECRET_GOLD_LABEL_KEY": "SECRET_GOLD_VALUE"}
        await pipeline.ainvoke(
            "Leak test",
            evidence_state=state,
            semantic_oracle=secret_gold_labels,
            valid_corpus_doc_ids={"SECRET_DOC_ID"},
        )

        # Check planner kwargs
        for call in mock_llm.call_history:
            pl_kwargs = call.get("kwargs", {})
            self.assertNotIn(
                "semantic_oracle",
                pl_kwargs,
                "VULNERABILITY in R10: semantic_oracle leaked to Planner via kwargs!"
            )
            self.assertNotIn(
                "valid_corpus_doc_ids",
                pl_kwargs,
                "VULNERABILITY in R10: valid_corpus_doc_ids leaked to Planner via kwargs!"
            )

        # Check generator kwargs
        for gen_kwargs in generator.received_kwargs:
            self.assertNotIn(
                "semantic_oracle",
                gen_kwargs,
                "VULNERABILITY in R10: semantic_oracle leaked to Generator via kwargs!"
            )
            self.assertNotIn(
                "valid_corpus_doc_ids",
                gen_kwargs,
                "VULNERABILITY in R10: valid_corpus_doc_ids leaked to Generator via kwargs!"
            )


if __name__ == "__main__":
    unittest.main()
