# -*- coding: utf-8 -*-
"""Executable Acceptance Test Suite: TC-M2-01 to TC-M2-12.

Each acceptance criterion from TC-M2-01 to TC-M2-12 is implemented as a dedicated
test method with concrete assertions.
"""

import sys
import os
import locale
import unittest
from typing import List, Dict, Any, Callable

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
from kag.solver.pipeline.kag_iterative_pipeline import MaxIterationsReachedError
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
    IncompleteAnswerResult,
    ModalityType,
    PresenceStatus,
    Provenance,
    ProvenanceValidationStatus,
    RequirementStatus,
    RetrievalStatus,
    SchemaValidationError,
    SemanticProposal,
    Stage3EntailmentReceipt,
    StructuredEvidenceState,
)
from kag.solver.evidence_aware.pipeline import KAGEvidenceAwareIterativePipeline


class DynamicMockPlanner:
    def __init__(self, plan_factory: Callable[[int, Context], List[Task]]):
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
        self.calls: List[Dict[str, Any]] = []

    async def ainvoke(self, query: str, context: Context, **kwargs) -> str:
        self.calls.append({"query": query, "context": context})
        return "FINAL_VERIFIED_ANSWER"


class TestTCM2AcceptanceSuite(unittest.IsolatedAsyncioTestCase):

    def test_TC_M2_01_chunk_id_real_but_irrelevant_rejected(self):
        """TC-M2-01: Real chunk with valid provenance but irrelevant content rejected."""
        evidence = Evidence(
            id="E_REAL_PROV",
            content="Nội dung về an toàn giao thông đường bộ không liên quan.",
            provenance=Provenance(doc_id="DOC_GTDB", chunk_id="C_101"),
            modality=ModalityType.TEXT,
        )
        claim = Claim(id="CLAIM_LABOR", statement="Cấm sa thải lao động mang thai.")
        s1 = FourStageEvidenceVerifier.stage1_verify_presence(evidence.id, {evidence.id})
        s2 = FourStageEvidenceVerifier.stage2_verify_provenance(evidence, {"DOC_GTDB"}, valid_corpus_chunk_ids_by_doc={"DOC_GTDB": {"C_101"}})

        # Proposal fails semantic match (irrelevant quote or low confidence or unverified)
        unverified_proposal = SemanticProposal(
            claim_id=claim.id,
            evidence_id=evidence.id,
            predicted_relation=EntailmentRelation.ENTAILMENT,
            confidence=0.50,  # Below threshold
            is_verified=False,
            quote="an toàn giao thông",
        )
        s3 = FourStageEvidenceVerifier.stage3_verify_entailment(
            claim=claim,
            evidence=evidence,
            stage1_status=s1,
            stage2_status=s2,
            proposal=unverified_proposal,
        )
        self.assertEqual(s3.relation, EntailmentRelation.NEUTRAL)
        self.assertEqual(s3.source_type, "REJECTED_UNVERIFIED_PROPOSAL")

        # Stage 4 coverage must not satisfy requirement
        receipt = FourStageEvidenceVerifier.create_verification_receipt(claim, evidence, s1, s2, s3)
        req = EvidenceRequirement(id="R1", description="Cấm sa thải", mandatory=True)
        cov = FourStageEvidenceVerifier.stage4_evaluate_requirement_coverage(req, [receipt])
        self.assertEqual(cov, RequirementStatus.UNSATISFIED)
        self.assertEqual(req.status, RequirementStatus.UNSATISFIED)

    def test_TC_M2_02_contradiction_triggers_conflict(self):
        """TC-M2-02: Evidence has real provenance but contradicts claim -> triggers CONFLICTING."""
        evidence = Evidence(
            id="E_CONTRADICT",
            content="Người sử dụng lao động ĐƯỢC QUYỀN sa thải lao động mang thai trong trường hợp bất khả kháng.",
            provenance=Provenance(doc_id="DOC_OLD", chunk_id="C_OLD"),
            modality=ModalityType.TEXT,
        )
        claim = Claim(id="CLAIM_PROHIBIT", statement="Người sử dụng lao động tuyệt đối không được sa thải.")
        s1 = FourStageEvidenceVerifier.stage1_verify_presence(evidence.id, {evidence.id})
        s2 = FourStageEvidenceVerifier.stage2_verify_provenance(evidence, {"DOC_OLD"}, valid_corpus_chunk_ids_by_doc={"DOC_OLD": {"C_OLD"}})
        s3 = FourStageEvidenceVerifier.stage3_verify_entailment(
            claim=claim,
            evidence=evidence,
            stage1_status=s1,
            stage2_status=s2,
            ground_truth_relation=EntailmentRelation.CONTRADICTION,
        )
        receipt = FourStageEvidenceVerifier.create_verification_receipt(claim, evidence, s1, s2, s3)
        req = EvidenceRequirement(id="R1", description="Cấm sa thải", mandatory=True)
        cov = FourStageEvidenceVerifier.stage4_evaluate_requirement_coverage(req, [receipt])
        self.assertEqual(cov, RequirementStatus.CONFLICTING)
        self.assertEqual(req.status, RequirementStatus.CONFLICTING)

    def test_TC_M2_03_missing_requirement_at_init_blocked(self):
        """TC-M2-03: Missing requirement from initiation blocks sufficiency."""
        state = StructuredEvidenceState(original_query="Quy định cấm và khung phạt đối với vi phạm hợp đồng")
        state.expected_requirement_ids = {"REQ_PROHIBITION", "REQ_PENALTY"}
        state.add_requirement(
            EvidenceRequirement(id="REQ_PROHIBITION", description="Cấm", mandatory=True, status=RequirementStatus.SATISFIED)
        )
        is_suff, reason = state.is_sufficient()
        self.assertFalse(is_suff)
        self.assertIn("REQ_PENALTY", reason)

        eval_out = state.evaluate_finish_gate()
        self.assertEqual(eval_out.status, EvaluatorStatus.INCOMPLETE)
        self.assertEqual(eval_out.next_decision, EvaluatorDecision.RETRIEVE_MORE)

    def test_TC_M2_04_duplicate_requirement_id_different_scope_rejected(self):
        """TC-M2-04: Duplicate requirement ID with conflicting scope/aspects rejected with SchemaValidationError."""
        state = StructuredEvidenceState(original_query="Query test collision")
        r1 = EvidenceRequirement(id="REQ_SAME", description="Quy định A", doc_scope="DOC_A", mandatory=True)
        state.add_requirement(r1)

        r2_conflicting = EvidenceRequirement(id="REQ_SAME", description="Quy định B khác", doc_scope="DOC_B", mandatory=True)
        with self.assertRaises(SchemaValidationError) as ctx:
            state.add_requirement(r2_conflicting)
        self.assertIn("Duplicate requirement ID collision", str(ctx.exception))
        self.assertEqual(len(state.requirements), 1)

    def test_TC_M2_05_valid_graph_evidence_without_chunk_id_accepted(self):
        """TC-M2-05: Valid graph evidence without chunk_id is accepted in Stage 2 provenance."""
        graph_evidence = Evidence(
            id="E_GRAPH_1",
            content="Triple: (Thủ_tướng, ký_ban_hành, Nghị_định_12)",
            provenance=Provenance(entity_id="ENT_TTCP", relation_id="REL_KY_BAN_HANH", chunk_id=None),
            modality=ModalityType.GRAPH_TRIPLE,
        )
        # Graph entity and relation exist in run's retrieved graph data
        s2 = FourStageEvidenceVerifier.stage2_verify_provenance(
            evidence=graph_evidence,
            valid_corpus_doc_ids=set(),
            retrieved_graph_entities_in_run={"ENT_TTCP"},
            retrieved_graph_relations_in_run={"REL_KY_BAN_HANH"},
        )
        self.assertEqual(s2.status, ProvenanceValidationStatus.PROVENANCE_VERIFIED)
        self.assertIsNone(graph_evidence.provenance.chunk_id)

    def test_TC_M2_06_retrieval_distinguishes_no_result_vs_error(self):
        """TC-M2-06: add_raw_retrieval_output clearly distinguishes NO_RESULT vs RETRIEVAL_ERROR vs FOUND."""
        state = StructuredEvidenceState(original_query="Test retrieval status")

        # 1. Error
        st_err = state.add_raw_retrieval_output("task_err", {"err_msg": "Timeout connecting to VectorDB"})
        self.assertEqual(st_err, RetrievalStatus.RETRIEVAL_ERROR)

        # 2. No result
        st_none = state.add_raw_retrieval_output("task_none", {"chunks": [], "graphs": []})
        self.assertEqual(st_none, RetrievalStatus.NO_RESULT)

        # 3. Found
        st_found = state.add_raw_retrieval_output("task_ok", {
            "chunks": [{"chunk_id": "C1", "doc_id": "D1", "content": "Content"}]
        })
        self.assertEqual(st_found, RetrievalStatus.FOUND)
        self.assertIn("C1", state.evidences)

    async def test_TC_M2_07_repeated_finish_proposals_consistently_rejected(self):
        """TC-M2-07: Planner repeatedly proposes Finish without satisfying requirements -> rejected consistently."""
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
        state = StructuredEvidenceState(original_query="Repeated finish")
        state.add_requirement(EvidenceRequirement(id="R1", description="Req", mandatory=True))

        res = await pipeline.ainvoke("Repeated finish", evidence_state=state)
        self.assertEqual(pipeline.rejections_count, 3)
        self.assertEqual(len(generator.calls), 0)
        self.assertIsInstance(res, IncompleteAnswerResult)
        self.assertEqual(res.status, "ABSTAIN")

    async def test_TC_M2_08_evaluator_exception_fail_closed(self):
        """TC-M2-08: Evaluator exception stops fail-closed in both ABSTAIN and EXCEPTION modes."""
        def plan_factory(num_iter: int, ctx: Context) -> List[Task]:
            return [Task(executor="Finish", arguments={})]

        retriever = MockRetrieverExecutor({})
        generator = MockGenerator()

        # ABSTAIN mode
        pipe_abstain = KAGEvidenceAwareIterativePipeline(
            planner=DynamicMockPlanner(plan_factory),
            executors=[retriever],
            generator=generator,
            max_iteration=2,
            evidence_aware=True,
            fail_closed_mode="ABSTAIN",
        )
        state_abs = StructuredEvidenceState(original_query="Crash test")
        state_abs.add_requirement(EvidenceRequirement(id="R1", description="R1", mandatory=True))
        state_abs.evaluate_finish_gate = lambda: (_ for _ in ()).throw(RuntimeError("Evaluator crash!"))

        res_abs = await pipe_abstain.ainvoke("Crash test", evidence_state=state_abs)
        self.assertIsInstance(res_abs, IncompleteAnswerResult)
        self.assertEqual(res_abs.status, "ABSTAIN")
        self.assertIn("EVALUATOR_ERROR", res_abs.answer)
        self.assertEqual(len(generator.calls), 0)

        # EXCEPTION mode
        pipe_exc = KAGEvidenceAwareIterativePipeline(
            planner=DynamicMockPlanner(plan_factory),
            executors=[retriever],
            generator=generator,
            max_iteration=2,
            evidence_aware=True,
            fail_closed_mode="EXCEPTION",
        )
        state_exc = StructuredEvidenceState(original_query="Crash test")
        state_exc.add_requirement(EvidenceRequirement(id="R1", description="R1", mandatory=True))
        state_exc.evaluate_finish_gate = lambda: (_ for _ in ()).throw(RuntimeError("Evaluator crash!"))

        with self.assertRaises(MaxIterationsReachedError):
            await pipe_exc.ainvoke("Crash test", evidence_state=state_exc)

    def test_TC_M2_09_unresolved_conflict_remains_open(self):
        """TC-M2-09: Unresolved conflict cannot be resolved by untrusted caller boolean; remains OPEN."""
        conflict = EvidenceConflict(
            conflict_id="CONF_01",
            requirement_id="REQ_1",
            conflicting_evidence_ids=("E_OLD", "E_NEW"),
            status=ConflictStatus.OPEN,
        )
        irrelevant_ev = Evidence(id="E_IRRELEVANT", content="Không liên quan", provenance=Provenance())

        with self.assertRaises(SchemaValidationError):
            conflict.resolve(
                arbitration_evidence=irrelevant_ev,
                basis=ConflictResolutionBasis.LEX_POSTERIOR,
                rationale="Caller claim",
                arbitration_receipt=None,
                is_provenance_verified=True,
            )
        self.assertEqual(conflict.status, ConflictStatus.OPEN)

        state = StructuredEvidenceState(original_query="Conflict state test")
        r = EvidenceRequirement(id="R1", description="Req 1", mandatory=True, status=RequirementStatus.SATISFIED)
        state.add_requirement(r)
        state.conflicts[conflict.conflict_id] = conflict

        is_suff, reason = state.is_sufficient()
        self.assertFalse(is_suff)
        self.assertIn("xung đột chứng cứ chưa giải quyết", reason)

    async def test_TC_M2_10_budget_exhaustion_fail_closed(self):
        """TC-M2-10: Budget exhaustion when requirements missing triggers fail-closed."""
        def plan_factory(num_iter: int, ctx: Context) -> List[Task]:
            return [Task(executor="Retriever", arguments={"query": "R_QUERY"})]

        retriever = MockRetrieverExecutor({})
        generator = MockGenerator()

        pipeline = KAGEvidenceAwareIterativePipeline(
            planner=DynamicMockPlanner(plan_factory),
            executors=[retriever],
            generator=generator,
            max_iteration=2,
            evidence_aware=True,
            fail_closed_mode="EXCEPTION",
        )
        state = StructuredEvidenceState(original_query="Budget test")
        state.add_requirement(EvidenceRequirement(id="R1", description="R1", mandatory=True))

        with self.assertRaises(MaxIterationsReachedError):
            await pipeline.ainvoke("Budget test", evidence_state=state)
        self.assertEqual(len(generator.calls), 0)

    async def test_TC_M2_11_full_iterative_loop_r1_missing_r2_feedback_to_approval(self):
        """TC-M2-11: Full loop with automated verifier (no manual status assignment)."""
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

        pipeline = KAGEvidenceAwareIterativePipeline(
            planner=planner,
            executors=[retriever],
            generator=generator,
            max_iteration=5,
            evidence_aware=True,
        )

        state = StructuredEvidenceState(original_query="Sa thải và xử phạt lao động mang thai")
        r1 = EvidenceRequirement(id="REQ_R1", description="Cấm sa thải", mandatory=True, doc_scope="DOC1", linked_evidence_ids=["C_R1"])
        r2 = EvidenceRequirement(id="REQ_R2", description="Khung xử phạt", mandatory=True, doc_scope="DOC2", linked_evidence_ids=["C_R2"])
        state.add_requirement(r1)
        state.add_requirement(r2)

        semantic_oracle = {
            ("REQ_R1", "C_R1"): EntailmentRelation.ENTAILMENT,
            ("REQ_R2", "C_R2"): EntailmentRelation.ENTAILMENT,
        }
        valid_corpus_doc_ids = {"DOC1", "DOC2"}

        answer = await pipeline.ainvoke(
            "Sa thải và xử phạt lao động mang thai",
            evidence_state=state,
            semantic_oracle=semantic_oracle,
            valid_corpus_doc_ids=valid_corpus_doc_ids,
            valid_corpus_chunk_ids_by_doc={"DOC1": {"C_R1"}, "DOC2": {"C_R2"}},
        )

        self.assertEqual(answer, "FINAL_VERIFIED_ANSWER")
        self.assertEqual(pipeline.rejections_count, 1)
        self.assertEqual(len(generator.calls), 1)
        self.assertEqual(r1.status, RequirementStatus.SATISFIED)
        self.assertEqual(r2.status, RequirementStatus.SATISFIED)

    async def test_TC_M2_12_baseline_equivalence_evidence_aware_false(self):
        """TC-M2-12: Baseline equivalence: when evidence_aware=False, bypasses evidence gate."""
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
            evidence_aware=False,
        )
        answer = await pipeline.ainvoke("Query without evidence awareness")
        self.assertEqual(answer, "FINAL_VERIFIED_ANSWER")
        self.assertEqual(len(generator.calls), 1)
        self.assertEqual(pipeline.rejections_count, 0)
        self.assertIsNone(pipeline.evidence_state)


if __name__ == "__main__":
    unittest.main()
