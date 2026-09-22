# -*- coding: utf-8 -*-
"""Test Suite 2: Evidence-Aware Pipeline E2E & Adversarial Counter-Examples.

Covers:
1. Full Iterative Loop:
   R1 present, R2 missing -> Rejection 1 -> Feedback to Planner -> Retrieval of R2 -> Approval -> Generator called once.
2. Generator Isolation:
   Generator receives clean context; zero rejection strings or fake tasks leak into generation.
3. Repeated Finish proposals:
   Planner repeatedly proposes Finish without new evidence -> repeatedly rejected; no gate fatigue.
4. Budget Exhaustion Fail-Closed:
   Max iterations reached without SUFFICIENT -> raises MaxIterationsReachedError or returns IncompleteAnswerResult(status="ABSTAIN"); Generator NEVER called.
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
    EntailmentRelation,
    EvidenceRequirement,
    IncompleteAnswerResult,
    RequirementStatus,
    StructuredEvidenceState,
)
from kag.solver.evidence_aware.pipeline import KAGEvidenceAwareIterativePipeline


class DynamicMockPlanner:
    """Mock Planner that generates fresh Task objects on each planning invocation."""

    def __init__(self, plan_factory: Callable[[int, Context], List[Task]]):
        self.plan_factory = plan_factory
        self.call_count = 0
        self.received_contexts: List[Context] = []

    async def ainvoke(self, query: str, context: Context = None, **kwargs) -> List[Task]:
        num_iteration = kwargs.get("num_iteration", self.call_count)
        self.received_contexts.append(context)
        tasks = self.plan_factory(num_iteration, context)
        self.call_count += 1
        return tasks


class MockRetrieverExecutor(ExecutorABC):
    """Mock Retriever returning controlled chunks."""

    def __init__(self, results_map: Dict[str, Any]):
        super().__init__()
        self.results_map = results_map
        self.invocations: List[Dict[str, Any]] = []

    def schema(self) -> Dict[str, Any]:
        return {"name": "Retriever", "description": "Mock retrieval", "parameters": {}}

    async def ainvoke(self, query: str, task: Task, context: Context, **kwargs):
        self.invocations.append({"query": query, "task": task})
        q = task.arguments.get("query", "")
        task.result = self.results_map.get(q, {"chunks": [], "err_msg": ""})
        task.status = TaskStatus.SUCCESS
        return task.result


class MockGenerator:
    """Mock Generator recording calls and context."""

    def __init__(self):
        self.calls: List[Dict[str, Any]] = []

    async def ainvoke(self, query: str, context: Context, **kwargs) -> str:
        self.calls.append({"query": query, "context": context, "kwargs": kwargs})
        return "GENERATED_FINAL_LEGAL_ANSWER"


class TestM2PipelineE2EAndAdversarial(unittest.IsolatedAsyncioTestCase):

    async def test_full_iterative_loop_r1_missing_r2_feedback_to_approval(self):
        """TC-M2-11: Full loop.

        Iteration 1: Planner retrieves R1, then proposes Finish -> Rejected (R2 missing).
        Iteration 2: Planner receives rejection feedback, retrieves R2 -> Approved -> Generator called once.
        """
        def plan_factory(num_iter: int, ctx: Context) -> List[Task]:
            # Step 1: retrieve R1
            if num_iter == 1:
                return [Task(executor="Retriever", arguments={"query": "R1_PROHIBITION"})]
            # Step 2: attempt Finish early (before R2 is collected)
            elif num_iter == 2:
                return [Task(executor="Finish", arguments={})]
            # Step 3: retrieve R2
            elif num_iter == 3:
                return [Task(executor="Retriever", arguments={"query": "R2_PENALTY"})]
            # Step 4: Finish when both ready
            else:
                return [Task(executor="Finish", arguments={})]

        planner = DynamicMockPlanner(plan_factory)

        retriever = MockRetrieverExecutor({
            "R1_PROHIBITION": {
                "chunks": [{
                    "chunk_id": "C_R1",
                    "doc_id": "DOC_BLLD",
                    "content": "Điều 37: Cấm đơn phương sa thải lao động mang thai.",
                }]
            },
            "R2_PENALTY": {
                "chunks": [{
                    "chunk_id": "C_R2",
                    "doc_id": "DOC_ND12",
                    "content": "Điều 28: Phạt tiền từ 10 đến 20 triệu đồng.",
                }]
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

        state = StructuredEvidenceState(original_query="Sa thải lao động mang thai")
        r1 = EvidenceRequirement(id="REQ_R1", description="Cấm sa thải", mandatory=True, doc_scope="DOC_BLLD", linked_evidence_ids=["C_R1"])
        r2 = EvidenceRequirement(id="REQ_R2", description="Khung xử phạt", mandatory=True, doc_scope="DOC_ND12", linked_evidence_ids=["C_R2"])
        state.add_requirement(r1)
        state.add_requirement(r2)

        # Automated verification via semantic oracle (no manual status mutation!):
        semantic_oracle = {
            ("REQ_R1", "C_R1"): EntailmentRelation.ENTAILMENT,
            ("REQ_R2", "C_R2"): EntailmentRelation.ENTAILMENT,
        }
        valid_corpus_doc_ids = {"DOC_BLLD", "DOC_ND12"}

        answer = await pipeline.ainvoke(
            "Sa thải lao động mang thai",
            evidence_state=state,
            semantic_oracle=semantic_oracle,
            valid_corpus_doc_ids=valid_corpus_doc_ids,
            valid_corpus_chunk_ids_by_doc={"DOC_BLLD": {"C_R1"}, "DOC_ND12": {"C_R2"}},
        )

        self.assertEqual(answer, "GENERATED_FINAL_LEGAL_ANSWER")
        self.assertEqual(pipeline.rejections_count, 1)
        self.assertEqual(len(generator.calls), 1)

        self.assertIsNotNone(pipeline.last_evaluator_output)
        self.assertEqual(state.requirements["REQ_R1"].status, RequirementStatus.SATISFIED)
        self.assertEqual(state.requirements["REQ_R2"].status, RequirementStatus.SATISFIED)

    async def test_generator_isolation_zero_rejection_leakage(self):
        """Adversarial: Prove that Generator context contains ZERO rejection strings or fake tasks."""
        def plan_factory(num_iter: int, ctx: Context) -> List[Task]:
            if num_iter == 1:
                return [Task(executor="Finish", arguments={})]
            elif num_iter == 2:
                return [Task(executor="Retriever", arguments={"query": "R1_QUERY"})]
            else:
                return [Task(executor="Finish", arguments={})]

        planner = DynamicMockPlanner(plan_factory)
        retriever = MockRetrieverExecutor({
            "R1_QUERY": {
                "chunks": [{
                    "chunk_id": "C_R1",
                    "doc_id": "DOC1",
                    "content": "Content for R1",
                }]
            }
        })
        generator = MockGenerator()

        pipeline = KAGEvidenceAwareIterativePipeline(
            planner=planner,
            executors=[retriever],
            generator=generator,
            max_iteration=4,
            evidence_aware=True,
        )

        state = StructuredEvidenceState(original_query="Test isolation")
        r = EvidenceRequirement(id="R1", description="Req 1", mandatory=True, doc_scope="DOC1", linked_evidence_ids=["C_R1"])
        state.add_requirement(r)

        semantic_oracle = {("R1", "C_R1"): EntailmentRelation.ENTAILMENT}
        valid_corpus_doc_ids = {"DOC1"}

        await pipeline.ainvoke(
            "Test isolation",
            evidence_state=state,
            semantic_oracle=semantic_oracle,
            valid_corpus_doc_ids=valid_corpus_doc_ids,
            valid_corpus_chunk_ids_by_doc={"DOC1": {"C_R1"}},
        )

        # Check generator context
        gen_context: Context = generator.calls[0]["context"]
        gen_task_contexts = [t.get_task_context() for t in gen_context.gen_task(False)]

        for tc in gen_task_contexts:
            self.assertNotIn("[FINISH_GATE_REJECTED]", str(tc))
            self.assertNotIn("FinishGateFeedback", str(tc))

        # Check DAG nodes in generator context: only legitimate retriever and finish task
        dag_nodes = list(gen_context.get_dag().nodes())
        self.assertEqual(len(dag_nodes), 2)  # Retriever task + Finish task

    async def test_repeated_finish_proposals_consistently_rejected(self):
        """TC-M2-07: Planner repeatedly proposes Finish without new evidence -> repeatedly rejected."""
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
        r = EvidenceRequirement(id="R1", description="Unsatisfied requirement", mandatory=True)
        state.add_requirement(r)

        result = await pipeline.ainvoke("Repeated finish", evidence_state=state)

        self.assertEqual(pipeline.rejections_count, 3)
        self.assertEqual(len(generator.calls), 0)
        self.assertIsInstance(result, IncompleteAnswerResult)
        self.assertEqual(result.status, "ABSTAIN")

    async def test_budget_exhaustion_fail_closed_modes(self):
        """TC-M2-10: Budget exhaustion when requirements missing triggers fail-closed."""
        def plan_factory(num_iter: int, ctx: Context) -> List[Task]:
            return [Task(executor="Retriever", arguments={"query": f"q_{num_iter}"})]

        retriever = MockRetrieverExecutor({})
        generator = MockGenerator()

        # Mode A: EXCEPTION (benchmark / CI)
        planner_exc = DynamicMockPlanner(plan_factory)
        pipeline_exc = KAGEvidenceAwareIterativePipeline(
            planner=planner_exc,
            executors=[retriever],
            generator=generator,
            max_iteration=2,
            evidence_aware=True,
            fail_closed_mode="EXCEPTION",
        )
        state_exc = StructuredEvidenceState(original_query="Budget test")
        state_exc.add_requirement(EvidenceRequirement(id="R1", description="R1", mandatory=True))

        with self.assertRaises(MaxIterationsReachedError):
            await pipeline_exc.ainvoke("Budget test", evidence_state=state_exc)

        # Mode B: ABSTAIN (production API)
        planner_abs = DynamicMockPlanner(plan_factory)
        pipeline_abs = KAGEvidenceAwareIterativePipeline(
            planner=planner_abs,
            executors=[retriever],
            generator=generator,
            max_iteration=2,
            evidence_aware=True,
            fail_closed_mode="ABSTAIN",
        )
        state_abs = StructuredEvidenceState(original_query="Budget test")
        state_abs.add_requirement(EvidenceRequirement(id="R1", description="R1", mandatory=True))

        res_abs = await pipeline_abs.ainvoke("Budget test", evidence_state=state_abs)
        self.assertIsInstance(res_abs, IncompleteAnswerResult)
        self.assertEqual(res_abs.status, "ABSTAIN")
        self.assertEqual(len(generator.calls), 0)


if __name__ == "__main__":
    unittest.main()
