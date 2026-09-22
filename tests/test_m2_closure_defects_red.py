# -*- coding: utf-8 -*-
"""RED Test Suite: Reproducing M2 Implementation Closure Defects (A through F).

These tests reproduce the exact defects identified in the current M2 implementation:
- Defect A: Pipeline does not automatically verify raw retrieval outputs; requires manual status assignment in tests.
- Defect B: Stage 4 accepts (Claim, Evidence, Stage3EntailmentReceipt) without verifying Stage 1 and Stage 2 validity.
- Defect C: Graph provenance defaults to PROVENANCE_VERIFIED when no comparison set is provided.
- Defect D: Incomplete requirement set for query (only R1 registered when R1+R2 required) evaluates to SUFFICIENT.
- Defect E: Evaluator exception in ABSTAIN mode is unhandled instead of returning fail-closed IncompleteAnswerResult.
- Defect F: evidence_aware=True bypasses planning @retry and crashes on transient planner failures.
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
from kag.solver.evidence_aware.models import (
    Claim,
    EntailmentRelation,
    Evidence,
    EvidenceRequirement,
    EvaluatorStatus,
    FourStageEvidenceVerifier,
    IncompleteAnswerResult,
    ModalityType,
    PresenceStatus,
    Provenance,
    ProvenanceValidationStatus,
    RequirementStatus,
    SchemaValidationError,
    Stage3EntailmentReceipt,
    StructuredEvidenceState,
)
from kag.solver.evidence_aware.pipeline import KAGEvidenceAwareIterativePipeline


class DynamicMockPlanner:
    def __init__(self, plan_factory):
        self.plan_factory = plan_factory
        self.call_count = 0

    async def ainvoke(self, query: str, context: Context = None, **kwargs) -> List[Task]:
        num_iteration = kwargs.get("num_iteration", self.call_count)
        tasks = self.plan_factory(num_iteration, context)
        self.call_count += 1
        return tasks


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


class MockGenerator:
    def __init__(self):
        self.calls = []

    async def ainvoke(self, query: str, context: Context, **kwargs) -> str:
        self.calls.append({"query": query, "context": context})
        return "GENERATED_FINAL_ANSWER"


class FlakyEvidenceAwarePlanner:
    """Simulates planner that fails 2 times and succeeds on 3rd attempt."""
    def __init__(self):
        self.attempts = 0

    async def ainvoke(self, query: str, context: Context = None, **kwargs) -> List[Task]:
        self.attempts += 1
        if self.attempts < 3:
            raise ConnectionError(f"Transient connection error attempt {self.attempts}")
        return [Task(executor="Finish", arguments={})]


class TestM2ClosureDefectsRED(unittest.IsolatedAsyncioTestCase):

    async def test_A_pipeline_must_auto_verify_without_manual_status_assignment(self):
        """DEFECT A: Pipeline must automatically run verification on raw retrieval outputs

        using an injected semantic oracle, WITHOUT any test code manually setting requirement.status.
        """
        def plan_factory(num_iter: int, ctx: Context) -> List[Task]:
            if num_iter == 1:
                return [Task(executor="Retriever", arguments={"query": "R1_QUERY"})]
            elif num_iter == 2:
                return [Task(executor="Finish", arguments={})]
            elif num_iter == 3:
                return [Task(executor="Retriever", arguments={"query": "R2_QUERY"})]
            else:
                return [Task(executor="Finish", arguments={})]

        planner = DynamicMockPlanner(plan_factory)
        retriever = MockRetrieverExecutor({
            "R1_QUERY": {
                "chunks": [{"chunk_id": "C_R1", "doc_id": "DOC1", "content": "Điều 37: Cấm sa thải"}]
            },
            "R2_QUERY": {
                "chunks": [{"chunk_id": "C_R2", "doc_id": "DOC2", "content": "Điều 28: Phạt 10-20tr"}]
            },
        })
        generator = MockGenerator()

        # Define semantic oracle for this fixture
        semantic_oracle = {
            ("R1", "C_R1"): EntailmentRelation.ENTAILMENT,
            ("R2", "C_R2"): EntailmentRelation.ENTAILMENT,
        }

        pipeline = KAGEvidenceAwareIterativePipeline(
            planner=planner,
            executors=[retriever],
            generator=generator,
            max_iteration=5,
            evidence_aware=True,
        )

        state = StructuredEvidenceState(original_query="Sa thải và xử phạt lao động mang thai")
        r1 = EvidenceRequirement(id="R1", description="Cấm sa thải", doc_scope="DOC1", mandatory=True, linked_evidence_ids=["C_R1"])
        r2 = EvidenceRequirement(id="R2", description="Khung xử phạt", doc_scope="DOC2", mandatory=True, linked_evidence_ids=["C_R2"])
        state.add_requirement(r1)
        state.add_requirement(r2)

        # In current pipeline: NO automatic verification exists.
        # Notice: We DO NOT hook or assign r1.status = SATISFIED anywhere!
        # If the pipeline does not have automatic verifier integration, Finish will be rejected forever,
        # reaching max_iteration and raising MaxIterationsReachedError!
        # We assert that the pipeline should complete successfully and return answer:
        answer = await pipeline.ainvoke(
            "Sa thải và xử phạt lao động mang thai",
            evidence_state=state,
            semantic_oracle=semantic_oracle,
            valid_corpus_doc_ids={"DOC1", "DOC2"},
            valid_corpus_chunk_ids_by_doc={"DOC1": {"C_R1"}, "DOC2": {"C_R2"}},
        )
        self.assertEqual(answer, "GENERATED_FINAL_ANSWER")
        self.assertEqual(r1.status, RequirementStatus.SATISFIED)
        self.assertEqual(r2.status, RequirementStatus.SATISFIED)

    def test_B_stage4_must_reject_unverified_stages_1_and_2(self):
        """DEFECT B: Stage 4 must reject (Claim, Evidence, Stage3EntailmentReceipt) if

        Stage 1 was not PRESENCE_CONFIRMED or Stage 2 was not PROVENANCE_VERIFIED.
        """
        req = EvidenceRequirement(id="R1", description="Test req", mandatory=True)
        claim = Claim(id="C1", statement="Claim 1")
        evidence = Evidence(id="E1", content="Evidence 1", provenance=Provenance(doc_id="UNKNOWN"))

        # Caller creates a Stage 3 receipt directly without valid Stage 1 and Stage 2:
        stage3_receipt = Stage3EntailmentReceipt(
            claim_id=claim.id,
            evidence_id=evidence.id,
            run_id="run_1",
            relation=EntailmentRelation.ENTAILMENT,
            source_type="FORGED_WITHOUT_STAGES_1_2",
        )

        # If Stage 4 accepts this tuple, it will mark req as SATISFIED!
        # Expected: Stage 4 must strictly reject unchained/unverified tuples!
        with self.assertRaises(SchemaValidationError) as ctx:
            FourStageEvidenceVerifier.stage4_evaluate_requirement_coverage(
                requirement=req,
                entailment_results=[(claim, evidence, stage3_receipt)],
            )
        self.assertIn("must be verified via Stage4VerificationReceipt", str(ctx.exception))

    def test_C_graph_entity_without_comparison_set_must_not_be_verified(self):
        """DEFECT C: Graph entity_id must NOT default to PROVENANCE_VERIFIED when

        retrieved_graph_entities_in_run is None (missing comparison set).
        """
        fake_graph_evidence = Evidence(
            id="E_GRAPH_FAKE",
            content="Triple: (A, B, C)",
            provenance=Provenance(entity_id="FABRICATED_UNGROUNDED_ENTITY_999", relation_id="REL"),
            modality=ModalityType.GRAPH_TRIPLE,
        )

        # Currently: When retrieved_graph_entities_in_run is None, it defaults to PROVENANCE_VERIFIED!
        receipt = FourStageEvidenceVerifier.stage2_verify_provenance(
            evidence=fake_graph_evidence,
            valid_corpus_doc_ids=set(),
            retrieved_graph_entities_in_run=None,
        )

        # Expected: Missing ground truth comparison set must NOT grant PROVENANCE_VERIFIED!
        self.assertEqual(
            receipt.status,
            ProvenanceValidationStatus.PROVENANCE_INVALID,
            f"VULNERABILITY DETECTED in Defect C: Graph evidence defaulted to PROVENANCE_VERIFIED without comparison set! status={receipt.status}",
        )

    def test_D_incomplete_requirements_for_query_must_not_be_sufficient(self):
        """DEFECT D: When query requires {R1, R2} but state only registered {R1},

        state must NOT conclude SUFFICIENT even if R1 is SATISFIED.
        """
        state = StructuredEvidenceState(
            original_query="Quy định cấm và khung phạt đối với deepfake ngân hàng"
        )
        # Expected mandatory requirements for this query: R1 and R2
        state.expected_requirement_ids = {"REQ_PROHIBITION", "REQ_PENALTY"}

        # State only registers R1:
        r1 = EvidenceRequirement(id="REQ_PROHIBITION", description="Cấm", mandatory=True, status=RequirementStatus.SATISFIED)
        state.add_requirement(r1)

        is_suff, reason = state.is_sufficient()
        print(f"Defect D: is_sufficient={is_suff}, reason={reason}")

        # Expected: Must detect that REQ_PENALTY is missing from registered requirements!
        self.assertFalse(
            is_suff,
            "VULNERABILITY DETECTED in Defect D: Incomplete requirement set (missing R2) evaluated to SUFFICIENT!",
        )
        self.assertIn("REQ_PENALTY", reason)

    async def test_E_evaluator_exception_in_abstain_mode_must_return_abstain(self):
        """DEFECT E: Evaluator raising an unexpected Exception in ABSTAIN mode

        must return IncompleteAnswerResult(status='ABSTAIN') without calling Generator.
        """
        def plan_factory(num_iter: int, ctx: Context) -> List[Task]:
            return [Task(executor="Finish", arguments={})]

        planner = DynamicMockPlanner(plan_factory)
        retriever = MockRetrieverExecutor({})
        generator = MockGenerator()

        pipeline = KAGEvidenceAwareIterativePipeline(
            planner=planner,
            executors=[retriever],
            generator=generator,
            max_iteration=3,
            evidence_aware=True,
            fail_closed_mode="ABSTAIN",
        )

        state = StructuredEvidenceState(original_query="Query test exception")
        state.add_requirement(EvidenceRequirement(id="R1", description="R1", mandatory=True))

        # Force evaluator to crash with an unexpected exception
        def crashing_evaluator():
            raise RuntimeError("CRITICAL EVALUATOR CRASH!")
        state.evaluate_finish_gate = crashing_evaluator

        # In current pipeline: unhandled RuntimeError crashes pipeline!
        # Expected: pipeline handles error safely and returns IncompleteAnswerResult(status="ABSTAIN")
        result = await pipeline.ainvoke("Query test exception", evidence_state=state)
        self.assertIsInstance(result, IncompleteAnswerResult)
        self.assertEqual(result.status, "ABSTAIN")
        self.assertIn("EVALUATOR_ERROR", result.answer)
        self.assertEqual(len(generator.calls), 0)

    async def test_F_planning_retry_must_operate_when_evidence_aware_is_true(self):
        """DEFECT F: When evidence_aware=True, planning retry (@retry) must function

        and recover from transient planner failures instead of crashing immediately.
        """
        flaky_planner = FlakyEvidenceAwarePlanner()
        retriever = MockRetrieverExecutor({})
        generator = MockGenerator()

        pipeline = KAGEvidenceAwareIterativePipeline(
            planner=flaky_planner,
            executors=[retriever],
            generator=generator,
            max_iteration=3,
            evidence_aware=True,
        )

        state = StructuredEvidenceState(original_query="Retry test")
        state.add_requirement(EvidenceRequirement(id="R1", description="R1", mandatory=False, status=RequirementStatus.SATISFIED))

        # In current pipeline: ainvoke calls active_planner.ainvoke directly without @retry,
        # so attempt 1 crashes with ConnectionError!
        # Expected: @retry retries up to 3 times, succeeds on attempt 3!
        answer = await pipeline.ainvoke("Retry test", evidence_state=state, trace_id="TRACE_XYZ")
        self.assertEqual(answer, "GENERATED_FINAL_ANSWER")
        self.assertEqual(flaky_planner.attempts, 3)


if __name__ == "__main__":
    unittest.main()
