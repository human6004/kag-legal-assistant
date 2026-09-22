# -*- coding: utf-8 -*-
"""Adversarial Audit Test Suite: Deep Invariant Verification for M2.

Designed independently to challenge and break the current implementation across 6 critical dimensions:
- ADV-A1: Concurrent queries on same pipeline instance cause state pollution / race conditions.
- ADV-A2: Sequential queries on same pipeline instance leak unconsumed rejection feedback across queries.
- ADV-B1: Keyword heuristic bypass leads to false sufficiency for multi-aspect queries without hardcoded words.
- ADV-C1: Cross-requirement gold label leakage when requirements share an evidence ID.
- ADV-D1: Cross-query receipt replay attack accepted due to global class-level token registry.
- ADV-D2: Public register_issued_token method allows caller to forge and validate arbitrary receipts.
- ADV-E1: ENTAILMENT in run 1 followed by CONTRADICTION in run 2 must transition requirement to CONFLICTING.
- ADV-E2: Evidence failing Stage 2 provenance must NOT trigger an OPEN conflict against genuine evidence.
"""

import sys
import os
import locale
import asyncio
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
from kag.interface.common.prompt import PromptABC
from kag.solver.planner.kag_iterative_planner import KAGIterativePlanner
from kag.solver.evidence_aware.models import (
    Claim,
    ConflictStatus,
    EntailmentRelation,
    Evidence,
    EvidenceRequirement,
    FourStageEvidenceVerifier,
    ModalityType,
    PresenceStatus,
    Provenance,
    ProvenanceValidationStatus,
    RequirementStatus,
    SchemaValidationError,
    Stage1PresenceReceipt,
    Stage2ProvenanceReceipt,
    Stage3EntailmentReceipt,
    Stage4VerificationReceipt,
    StructuredEvidenceState,
)
from kag.solver.evidence_aware.pipeline import KAGEvidenceAwareIterativePipeline


class DummyPrompt(PromptABC):
    template_en = "Query: {query}\nContext: {context}"
    template_zh = "Query: {query}\nContext: {context}"

    @property
    def template_variables(self) -> List[str]:
        return ["query", "context"]


class MockRetrieverExecutor(ExecutorABC):
    def __init__(self, results_map: Dict[str, Any], delay: float = 0.0):
        super().__init__()
        self.results_map = results_map
        self.delay = delay

    def schema(self) -> Dict[str, Any]:
        return {"name": "Retriever", "description": "Mock retrieval", "parameters": {}}

    async def ainvoke(self, query: str, task: Task, context: Context, **kwargs):
        if self.delay > 0:
            await asyncio.sleep(self.delay)
        q = task.arguments.get("query", "")
        task.result = self.results_map.get(q, {"chunks": [], "err_msg": ""})
        task.status = TaskStatus.SUCCESS
        return task.result


class RecordingMockLLM:
    def __init__(self, plan_fn):
        self.plan_fn = plan_fn
        self.call_history: List[Dict[str, Any]] = []

    async def ainvoke(self, payload: Dict[str, Any], prompt: Any, **kwargs) -> List[Task]:
        self.call_history.append({"payload": payload, "kwargs": kwargs})
        num_iter = kwargs.get("num_iteration", len(self.call_history))
        query = payload.get("query", "")
        return self.plan_fn(query, num_iter, payload.get("context", []))


class MockGenerator:
    def __init__(self):
        self.calls: List[Dict[str, Any]] = []

    async def ainvoke(self, query: str, context: Context, **kwargs) -> str:
        self.calls.append({"query": query, "context": context, "kwargs": kwargs})
        return f"ANSWER_FOR_{query}"


class TestM2OvernightAdversarialRED(unittest.IsolatedAsyncioTestCase):

    async def test_ADV_A1_concurrent_queries_pipeline_state_pollution(self):
        """ADV-A1: Two queries running concurrently on the SAME pipeline instance

        must NOT cross-pollute each other's evidence state, rejections, or finish gate.
        """
        def plan_fn(query: str, num_iter: int, ctx: List[Any]) -> List[Task]:
            if "QUERY_A" in query:
                if num_iter == 1:
                    return [Task(executor="Retriever", arguments={"query": "A_RETRIEVE"})]
                else:
                    return [Task(executor="Finish", arguments={})]
            else:
                if num_iter == 1:
                    return [Task(executor="Retriever", arguments={"query": "B_RETRIEVE"})]
                else:
                    return [Task(executor="Finish", arguments={})]

        llm = RecordingMockLLM(plan_fn)
        planner = KAGIterativePlanner(llm=llm, plan_prompt=DummyPrompt())
        # Add slight delay to force interleaving
        retriever = MockRetrieverExecutor({
            "A_RETRIEVE": {"chunks": [{"chunk_id": "C_A", "doc_id": "DOC_A", "content": "Content A"}]},
            "B_RETRIEVE": {"chunks": [{"chunk_id": "C_B", "doc_id": "DOC_B", "content": "Content B"}]},
        }, delay=0.01)
        generator = MockGenerator()

        pipeline = KAGEvidenceAwareIterativePipeline(
            planner=planner,
            executors=[retriever],
            generator=generator,
            max_iteration=3,
            evidence_aware=True,
        )

        state_a = StructuredEvidenceState(original_query="QUERY_A")
        state_a.expected_requirement_ids = {"REQ_A"}
        req_a = EvidenceRequirement(id="REQ_A", description="Req A", mandatory=True, doc_scope="DOC_A", linked_evidence_ids=["C_A"])
        state_a.add_requirement(req_a)

        state_b = StructuredEvidenceState(original_query="QUERY_B")
        state_b.expected_requirement_ids = {"REQ_B"}
        req_b = EvidenceRequirement(id="REQ_B", description="Req B", mandatory=True, doc_scope="DOC_B", linked_evidence_ids=["C_B"])
        state_b.add_requirement(req_b)

        # Run concurrently
        task_a = pipeline.ainvoke(
            "QUERY_A",
            evidence_state=state_a,
            semantic_oracle={("REQ_A", "C_A"): EntailmentRelation.ENTAILMENT},
            valid_corpus_doc_ids={"DOC_A"},
            valid_corpus_chunk_ids_by_doc={"DOC_A": {"C_A"}},
        )
        task_b = pipeline.ainvoke(
            "QUERY_B",
            evidence_state=state_b,
            semantic_oracle={("REQ_B", "C_B"): EntailmentRelation.ENTAILMENT},
            valid_corpus_doc_ids={"DOC_B"},
            valid_corpus_chunk_ids_by_doc={"DOC_B": {"C_B"}},
        )

        res_a, res_b = await asyncio.gather(task_a, task_b)

        self.assertEqual(res_a, "ANSWER_FOR_QUERY_A")
        self.assertEqual(res_b, "ANSWER_FOR_QUERY_B")

        # Invariant: State A must only have C_A; State B must only have C_B
        self.assertIn("C_A", state_a.evidences)
        self.assertNotIn("C_B", state_a.evidences, "VULNERABILITY ADV-A1: Evidence from Query B leaked into State A!")
        self.assertIn("C_B", state_b.evidences)
        self.assertNotIn("C_A", state_b.evidences, "VULNERABILITY ADV-A1: Evidence from Query A leaked into State B!")

    async def test_ADV_A2_sequential_queries_leak_rejection_feedback(self):
        """ADV-A2: When Query 1 has a rejection feedback set on the planner adapter,

        starting Query 2 on the SAME pipeline instance must NOT receive Query 1's feedback.
        """
        def plan_fn(query: str, num_iter: int, ctx: List[Any]) -> List[Task]:
            return [Task(executor="Finish", arguments={})]

        llm = RecordingMockLLM(plan_fn)
        planner = KAGIterativePlanner(llm=llm, plan_prompt=DummyPrompt())
        generator = MockGenerator()
        pipeline = KAGEvidenceAwareIterativePipeline(
            planner=planner,
            executors=[],
            generator=generator,
            max_iteration=2,
            evidence_aware=True,
            fail_closed_mode="ABSTAIN",
        )

        # Query 1: will propose Finish on iter 1 -> rejected with feedback -> reaches max_iteration
        state_1 = StructuredEvidenceState(original_query="Query 1")
        state_1.expected_requirement_ids = {"R1"}
        state_1.add_requirement(EvidenceRequirement(id="R1", description="R1", mandatory=True))

        await pipeline.ainvoke("Query 1", evidence_state=state_1)

        # Query 2 starts fresh on same pipeline instance
        state_2 = StructuredEvidenceState(original_query="Query 2")
        state_2.expected_requirement_ids = {"R2"}
        state_2.add_requirement(EvidenceRequirement(id="R2", description="R2", mandatory=True))

        await pipeline.ainvoke("Query 2", evidence_state=state_2)

        # Check call history for Query 2 iter 1: must NOT contain rejection feedback from Query 1!
        q2_first_call = [c for c in llm.call_history if c["payload"]["query"] == "Query 2"][0]
        q2_context = q2_first_call["payload"]["context"]
        has_stale_feedback = any("[FINISH_GATE_REJECTED]" in str(item) for item in q2_context)
        self.assertFalse(
            has_stale_feedback,
            "VULNERABILITY ADV-A2: Stale rejection feedback from Query 1 leaked into initial prompt of Query 2!"
        )

    def test_ADV_B1_keyword_heuristic_bypass_false_sufficiency(self):
        """ADV-B1: Query requires multiple aspects ('cấm' and 'mức phạt'), but uses phrasing

        without the hardcoded keywords ('kèm mức phạt vi phạm nồng độ cồn').
        State only registers 1 requirement (cấm).
        EXPECTED: Must NOT evaluate to SUFFICIENT.
        """
        # Phrasing uses "kèm mức phạt", does not contain literal " và " or "khung phạt" or "xử phạt"
        query = "Quy định cấm kèm mức phạt vi phạm nồng độ cồn"
        state = StructuredEvidenceState(original_query=query)
        # Omitted expected_requirement_ids
        state.expected_requirement_ids = None

        r1 = EvidenceRequirement(id="R_PROHIBITION", description="Quy định cấm", mandatory=True, status=RequirementStatus.SATISFIED)
        state.add_requirement(r1)

        is_suff, reason = state.is_sufficient()
        # Must detect that query is multi-aspect and fail-closed!
        self.assertFalse(
            is_suff,
            "VULNERABILITY ADV-B1: Keyword heuristic bypassed! Partial state evaluated to SUFFICIENT on query without hardcoded keywords!"
        )

    def test_ADV_C1_cross_requirement_gold_label_leakage(self):
        """ADV-C1: Two requirements REQ_1 and REQ_2 share evidence E_SHARED.

        E_SHARED entails REQ_1, but does NOT entail REQ_2.
        Oracle has exact key: {("REQ_1", "E_SHARED"): ENTAILMENT}.
        EXPECTED: REQ_2 must NOT receive ENTAILMENT via loose / fuzzy oracle lookup!
        """
        state = StructuredEvidenceState(original_query="Shared evidence test")
        state.expected_requirement_ids = {"REQ_1", "REQ_2"}
        req1 = EvidenceRequirement(id="REQ_1", description="Req 1 statement", mandatory=True, linked_evidence_ids=["E_SHARED"])
        req2 = EvidenceRequirement(id="REQ_2", description="Req 2 statement", mandatory=True, linked_evidence_ids=["E_SHARED"])
        state.add_requirement(req1)
        state.add_requirement(req2)

        state.add_raw_retrieval_output(
            task_id="task_shared",
            task_result={"chunks": [{"chunk_id": "E_SHARED", "doc_id": "DOC1", "content": "Shared content"}]},
            run_id="run_1",
        )

        # Oracle ONLY specifies entailment for REQ_1 with E_SHARED:
        strict_oracle = {
            ("REQ_1", "E_SHARED"): EntailmentRelation.ENTAILMENT,
        }

        state.auto_verify_retrieval(
            task_id="task_shared",
            run_id="run_1",
            valid_corpus_doc_ids={"DOC1"},
            valid_corpus_chunk_ids_by_doc={"DOC1": {"E_SHARED"}},
            semantic_oracle=strict_oracle,
        )

        # REQ_1 should be SATISFIED
        self.assertEqual(req1.status, RequirementStatus.SATISFIED)
        # REQ_2 must NOT be SATISFIED (it has no entailment label in oracle!)
        self.assertNotEqual(
            req2.status,
            RequirementStatus.SATISFIED,
            "VULNERABILITY ADV-C1: Gold label for REQ_1 leaked to REQ_2 because of loose oracle key lookup!"
        )

    def test_ADV_D1_cross_query_receipt_replay_attack(self):
        """ADV-D1: Receipt issued in Query A must NOT be accepted in Query B.

        Tokens must be bound to query / state lineage.
        """
        claim_a = Claim(id="C_A", statement="Claim A")
        ev_a = Evidence(id="E_A", content="Content A", provenance=Provenance(doc_id="D1", chunk_id="C1"))
        s1 = FourStageEvidenceVerifier.stage1_verify_presence("E_A", {"E_A"}, run_id="run_A")
        s2 = FourStageEvidenceVerifier.stage2_verify_provenance(ev_a, {"D1"}, run_id="run_A")
        s3 = FourStageEvidenceVerifier.stage3_verify_entailment(
            claim=claim_a, evidence=ev_a, stage1_status=s1, stage2_status=s2,
            ground_truth_relation=EntailmentRelation.ENTAILMENT, run_id="run_A"
        )
        receipt_a = FourStageEvidenceVerifier.create_verification_receipt(
            claim_a, ev_a, s1, s2, s3, run_id="run_A", requirement_id="REQ_A"
        )

        # Now adversary in Query B presents receipt_a for requirement in Query B:
        req_b = EvidenceRequirement(id="REQ_B", description="Req B", mandatory=True)

        # EXPECTED: Stage 4 in Query B must reject receipt_a because it belongs to Query A!
        with self.assertRaises(SchemaValidationError) as ctx:
            FourStageEvidenceVerifier.stage4_evaluate_requirement_coverage(
                requirement=req_b,
                entailment_results=[receipt_a],
            )
        self.assertIn("query", str(ctx.exception).lower())

    def test_ADV_D2_caller_public_token_registration_bypass(self):
        """ADV-D2: Public register_issued_token method must NOT allow untrusted callers

        to register arbitrary fabricated tokens into the verifier registry.
        """
        # Check if caller can call register_issued_token directly:
        fake_token = "FORGED_TOKEN_ABC_123"
        FourStageEvidenceVerifier.register_issued_token(fake_token)

        # If a method exists that allows arbitrary external token registration,
        # an attacker can bypass all stage 1-3 verifications!
        # EXPECTED: Lineage token verification must be bound to HMAC/signing or non-forgeable lineage!
        req = EvidenceRequirement(id="R1", description="Req", mandatory=True)
        claim = Claim(id="C1", statement="Claim")
        ev = Evidence(id="E1", content="Content", provenance=Provenance(doc_id="D1", chunk_id="C1"))
        s1 = Stage1PresenceReceipt("E1", "run_1", PresenceStatus.PRESENCE_CONFIRMED)
        s2 = Stage2ProvenanceReceipt("E1", "run_1", ProvenanceValidationStatus.PROVENANCE_VERIFIED, ModalityType.TEXT)
        s3 = Stage3EntailmentReceipt("C1", "E1", "run_1", EntailmentRelation.ENTAILMENT, "FORGED")

        forged_receipt = Stage4VerificationReceipt(
            run_id="run_1",
            claim_id="C1",
            evidence_id="E1",
            stage1_receipt=s1,
            stage2_receipt=s2,
            stage3_receipt=s3,
            claim=claim,
            evidence=ev,
            relation=EntailmentRelation.ENTAILMENT,
            token=fake_token,
        )

        with self.assertRaises(SchemaValidationError):
            FourStageEvidenceVerifier.stage4_evaluate_requirement_coverage(req, [forged_receipt])

    def test_ADV_E1_entailment_then_contradiction_must_transition_to_conflicting(self):
        """ADV-E1: Run 1 retrieves evidence E1 yielding ENTAILMENT (req becomes SATISFIED).

        Run 2 retrieves evidence E2 yielding CONTRADICTION.
        Requirement MUST transition from SATISFIED to CONFLICTING, and state must NOT evaluate to SUFFICIENT.
        """
        state = StructuredEvidenceState(original_query="Conflict progression test")
        state.expected_requirement_ids = {"REQ_REV"}
        req = EvidenceRequirement(id="REQ_REV", description="Chế tài", mandatory=True)
        state.add_requirement(req)

        # Run 1: ENTAILMENT
        state.add_raw_retrieval_output(
            task_id="task_1",
            task_result={"chunks": [{"chunk_id": "C_OK", "doc_id": "DOC1", "content": "Nội dung chuẩn"}]},
            run_id="run_iter_1",
        )
        oracle = {
            ("REQ_REV", "C_OK"): EntailmentRelation.ENTAILMENT,
            ("REQ_REV", "C_BAD"): EntailmentRelation.CONTRADICTION,
        }
        state.auto_verify_retrieval(
            task_id="task_1",
            run_id="run_iter_1",
            valid_corpus_doc_ids={"DOC1"},
            valid_corpus_chunk_ids_by_doc={"DOC1": {"C_OK", "C_BAD"}},
            semantic_oracle=oracle,
        )
        self.assertEqual(req.status, RequirementStatus.SATISFIED)

        # Run 2: CONTRADICTION
        state.add_raw_retrieval_output(
            task_id="task_2",
            task_result={"chunks": [{"chunk_id": "C_BAD", "doc_id": "DOC1", "content": "Nội dung mâu thuẫn"}]},
            run_id="run_iter_2",
        )
        state.auto_verify_retrieval(
            task_id="task_2",
            run_id="run_iter_2",
            valid_corpus_doc_ids={"DOC1"},
            valid_corpus_chunk_ids_by_doc={"DOC1": {"C_OK", "C_BAD"}},
            semantic_oracle=oracle,
        )

        # Requirement MUST now be CONFLICTING!
        self.assertEqual(
            req.status,
            RequirementStatus.CONFLICTING,
            f"VULNERABILITY ADV-E1: Later contradiction did not transition requirement to CONFLICTING (status={req.status})!"
        )
        is_suff, reason = state.is_sufficient()
        self.assertFalse(is_suff, "VULNERABILITY ADV-E1: State with newly surfaced contradiction evaluated to SUFFICIENT!")

    def test_ADV_E2_unverified_provenance_evidence_must_not_trigger_conflict(self):
        """ADV-E2: Evidence E1 is genuine (ENTAILMENT). Evidence E2 has invalid provenance

        (fabricated chunk not in corpus). Even if E2 claims CONTRADICTION, it must NOT
        trigger an OPEN conflict against genuine evidence.
        """
        state = StructuredEvidenceState(original_query="Fake conflict test")
        state.expected_requirement_ids = {"REQ_LEGAL"}
        req = EvidenceRequirement(id="REQ_LEGAL", description="Luật", mandatory=True)
        state.add_requirement(req)

        # E1: Genuine evidence
        state.add_raw_retrieval_output(
            task_id="task_1",
            task_result={"chunks": [{"chunk_id": "C_REAL", "doc_id": "DOC_CORPUS", "content": "Luật thật"}]},
            run_id="run_1",
        )
        # E2: Fabricated evidence (doc_id NOT in valid_corpus_doc_ids)
        state.add_raw_retrieval_output(
            task_id="task_2",
            task_result={"chunks": [{"chunk_id": "C_FAKE", "doc_id": "DOC_UNKNOWN_FAKE", "content": "Luật bịa"}]},
            run_id="run_2",
        )

        oracle = {
            ("REQ_LEGAL", "C_REAL"): EntailmentRelation.ENTAILMENT,
            ("REQ_LEGAL", "C_FAKE"): EntailmentRelation.CONTRADICTION,
        }

        # Run verification with valid_corpus_doc_ids containing only DOC_CORPUS
        state.auto_verify_retrieval(
            task_id="task_1",
            run_id="run_1",
            valid_corpus_doc_ids={"DOC_CORPUS"},
            valid_corpus_chunk_ids_by_doc={"DOC_CORPUS": {"C_REAL"}},
            semantic_oracle=oracle,
        )
        state.auto_verify_retrieval(
            task_id="task_2",
            run_id="run_2",
            valid_corpus_doc_ids={"DOC_CORPUS"},
            valid_corpus_chunk_ids_by_doc={"DOC_CORPUS": {"C_REAL"}},
            semantic_oracle=oracle,
        )

        # C_FAKE failed Stage 2 provenance -> must NOT generate Stage 4 receipt and must NOT open conflict!
        open_conflicts = [c for c in state.conflicts.values() if c.status == ConflictStatus.OPEN]
        self.assertEqual(
            len(open_conflicts), 0,
            f"VULNERABILITY ADV-E2: Evidence with invalid provenance triggered an OPEN conflict! {open_conflicts}"
        )
        self.assertEqual(req.status, RequirementStatus.SATISFIED)


if __name__ == "__main__":
    unittest.main()
