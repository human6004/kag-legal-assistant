# -*- coding: utf-8 -*-
"""Independent Grok adversarial suite for M2 candidate.

These cases are intentionally different from Gemini closeout / two-defect /
overnight tests. They exercise the ZIP candidate source only.
"""

from __future__ import annotations

import hashlib
import locale
import os
import sys
import unittest
from typing import Any, Dict, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

try:
    locale.setlocale(locale.LC_ALL, "Chinese_China.936")
except Exception:
    try:
        locale.setlocale(locale.LC_ALL, "Chinese")
    except Exception:
        pass

CANDIDATE_ROOT = os.path.abspath(
    os.environ.get("CANDIDATE_ROOT")
    or (
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if os.path.basename(os.path.dirname(os.path.abspath(__file__))) == "tests"
        else os.path.join(os.path.dirname(os.path.abspath(__file__)), "candidate")
    )
)
VENDOR_KAG = os.path.join(CANDIDATE_ROOT, "vendor", "KAG")
if not os.path.isdir(VENDOR_KAG):
    alt_vendor = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "vendor", "KAG"))
    if os.path.isdir(alt_vendor):
        VENDOR_KAG = alt_vendor
    else:
        wt_vendor = os.environ.get("KAG_VENDOR_ROOT") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "vendor", "KAG"))
        if os.path.isdir(wt_vendor):
            VENDOR_KAG = wt_vendor
if VENDOR_KAG not in sys.path:
    sys.path.insert(0, VENDOR_KAG)
if CANDIDATE_ROOT not in sys.path:
    sys.path.insert(0, CANDIDATE_ROOT)

import kag  # noqa: E402

wt_kag = os.path.join(CANDIDATE_ROOT, "kag")
if wt_kag not in kag.__path__:
    kag.__path__.append(wt_kag)

import kag.solver  # noqa: E402

wt_solver = os.path.join(CANDIDATE_ROOT, "kag", "solver")
if wt_solver not in kag.solver.__path__:
    kag.solver.__path__.append(wt_solver)

from kag.interface.solver.context import Context  # noqa: E402
from kag.interface.solver.executor_abc import ExecutorABC  # noqa: E402
from kag.interface.solver.planner_abc import Task, TaskStatus  # noqa: E402
from kag.solver.evidence_aware.models import (  # noqa: E402
    EntailmentRelation,
    EvaluatorStatus,
    Evidence,
    EvidenceRequirement,
    FourStageEvidenceVerifier,
    ModalityType,
    Provenance,
    ProvenanceValidationStatus,
    RequirementStatus,
    SchemaValidationError,
    StructuredEvidenceState,
)
from kag.solver.evidence_aware.pipeline import (  # noqa: E402
    KAGEvidenceAwareIterativePipeline,
)
from kag.solver.evidence_aware.planner_adapter import (  # noqa: E402
    EvidenceAwarePlannerAdapter,
)


def _models_path() -> str:
    return os.path.join(
        CANDIDATE_ROOT, "kag", "solver", "evidence_aware", "models.py"
    )


class PlannerABCOnly:
    """PlannerABC-shaped object: ainvoke only, no llm / plan_prompt."""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    async def ainvoke(self, query: str, context: Context = None, **kwargs):
        self.calls.append(
            {
                "query": query,
                "context": context,
                "kwargs": dict(kwargs),
                "context_tasks": list(context.gen_task()) if context else [],
            }
        )
        return [Task(executor="Finish", arguments={})]


class RecordingPlanner:
    def __init__(self, plan_by_iter: Dict[int, List[Task]]) -> None:
        self.plan_by_iter = plan_by_iter
        self.calls: List[Dict[str, Any]] = []
        self.call_count = 0

    async def ainvoke(self, query: str, context: Context = None, **kwargs):
        self.call_count += 1
        self.calls.append(
            {
                "query": query,
                "context": context,
                "kwargs": dict(kwargs),
                "num_iteration": kwargs.get("num_iteration"),
            }
        )
        return self.plan_by_iter.get(
            self.call_count, [Task(executor="Finish", arguments={})]
        )


class MockRetriever(ExecutorABC):
    def __init__(self, results_map: Dict[str, Any]) -> None:
        super().__init__()
        self.results_map = results_map

    def schema(self) -> Dict[str, Any]:
        return {"name": "Retriever", "description": "mock", "parameters": {}}

    async def ainvoke(self, query: str, task: Task, context: Context, **kwargs):
        q = task.arguments.get("query", "")
        task.result = self.results_map.get(q, {"chunks": [], "err_msg": ""})
        task.status = TaskStatus.SUCCESS
        return task.result


class MockGenerator:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    async def ainvoke(self, query: str, context: Context, **kwargs) -> str:
        dumped = []
        for t in context.gen_task():
            dumped.append(
                {
                    "executor": t.executor,
                    "arguments": t.arguments,
                    "result": str(t.result),
                }
            )
        self.calls.append(
            {"query": query, "tasks": dumped, "kwargs": dict(kwargs)}
        )
        return f"ANSWER:{query}"


class TestGrokIndependentAdversarial(unittest.IsolatedAsyncioTestCase):
    def test_I1_fake_article_must_not_verify_via_unrelated_real_page(self):
        """NEW vs Defect 2: authoritative coords ARE provided.

        Gemini only tested the no-mapping case. Here DOC1's real page '1'
        is in the coord set, but the evidence cites a fabricated article.
        Matching any one coordinate must not verify a false article.
        """
        ev = Evidence(
            id="E_FAKE_ART",
            content="Nội dung gắn điều luật bịa.",
            provenance=Provenance(
                doc_id="DOC1",
                article="Điều 999_KHÔNG_TỒN_TẠI",
                page=1,
            ),
            modality=ModalityType.TEXT,
        )
        receipt = FourStageEvidenceVerifier.stage2_verify_provenance(
            evidence=ev,
            valid_corpus_doc_ids={"DOC1"},
            valid_corpus_coords_by_doc={
                "DOC1": {"Điều 1", "1"},
            },
        )
        self.assertEqual(
            receipt.status,
            ProvenanceValidationStatus.PROVENANCE_INVALID,
            "I1: fake article became PROVENANCE_VERIFIED because a real page "
            f"token matched. actual={receipt.status}",
        )

    def test_I1b_fake_article_plus_real_page_must_not_satisfy_requirement(self):
        """Same hole through auto_verify → Finish Gate."""
        state = StructuredEvidenceState(original_query="I1b query")
        state.expected_requirement_ids = {"R1"}
        req = EvidenceRequirement(
            id="R1",
            description="Điều 999 bịa đặt",
            mandatory=True,
        )
        state.add_requirement(req)
        ev = Evidence(
            id="E1",
            content="Nội dung không thuộc Điều 999.",
            provenance=Provenance(
                doc_id="DOC1",
                article="Điều 999_FAKE",
                page=1,
            ),
            modality=ModalityType.TEXT,
        )
        state.evidences["E1"] = ev
        state.auto_verify_retrieval(
            task_id=None,
            run_id="run_i1b",
            retrieved_chunk_ids_in_current_run={"E1"},
            valid_corpus_doc_ids={"DOC1"},
            valid_corpus_coords_by_doc={"DOC1": {"Điều 1", "1"}},
            semantic_oracle={("R1", "E1"): EntailmentRelation.ENTAILMENT},
        )
        gate = state.evaluate_finish_gate()
        self.assertNotEqual(req.status, RequirementStatus.SATISFIED)
        self.assertNotEqual(gate.status, EvaluatorStatus.SUFFICIENT)

    def test_I2_identical_description_must_not_share_oracle_label(self):
        """NEW vs C3/ADV-C1: those used distinct descriptions and pair keys.

        Oracle is keyed only by shared natural-language description.
        R2 must not inherit R1's entailment label.
        """
        shared = "Cấm sa thải lao động mang thai"
        state = StructuredEvidenceState(original_query="I2 shared desc")
        state.expected_requirement_ids = {"R1", "R2"}
        r1 = EvidenceRequirement(
            id="R1", description=shared, mandatory=True, linked_evidence_ids=["C1"]
        )
        r2 = EvidenceRequirement(
            id="R2", description=shared, mandatory=True, linked_evidence_ids=["C1"]
        )
        state.add_requirement(r1)
        state.add_requirement(r2)
        state.add_raw_retrieval_output(
            task_id="t1",
            task_result={
                "chunks": [
                    {"chunk_id": "C1", "doc_id": "DOC1", "content": "Điều 37 cấm sa thải."}
                ]
            },
            run_id="run_i2",
        )
        state.auto_verify_retrieval(
            task_id="t1",
            run_id="run_i2",
            valid_corpus_doc_ids={"DOC1"},
            valid_corpus_chunk_ids_by_doc={"DOC1": {"C1"}},
            semantic_oracle={(shared, "C1"): EntailmentRelation.ENTAILMENT},
        )
        self.assertEqual(r1.status, RequirementStatus.SATISFIED)
        self.assertNotEqual(
            r2.status,
            RequirementStatus.SATISFIED,
            "I2: R2 became SATISFIED via R1's description-keyed oracle label",
        )

    def test_I3_open_conflict_must_not_be_sufficient(self):
        """Conflict then extra entailment must stay closed."""
        state = StructuredEvidenceState(original_query="I3 conflict")
        state.expected_requirement_ids = {"R1"}
        req = EvidenceRequirement(
            id="R1", description="Quy định", mandatory=True, linked_evidence_ids=["C1", "C2"]
        )
        state.add_requirement(req)
        state.add_raw_retrieval_output(
            task_id="t1",
            task_result={
                "chunks": [
                    {"chunk_id": "C1", "doc_id": "DOC1", "content": "Cấm"},
                    {"chunk_id": "C2", "doc_id": "DOC1", "content": "Cho phép"},
                ]
            },
            run_id="run_i3",
        )
        state.auto_verify_retrieval(
            task_id="t1",
            run_id="run_i3",
            valid_corpus_doc_ids={"DOC1"},
            valid_corpus_chunk_ids_by_doc={"DOC1": {"C1", "C2"}},
            semantic_oracle={
                ("R1", "C1"): EntailmentRelation.ENTAILMENT,
                ("R1", "C2"): EntailmentRelation.CONTRADICTION,
            },
        )
        gate = state.evaluate_finish_gate()
        self.assertEqual(req.status, RequirementStatus.CONFLICTING)
        self.assertNotEqual(gate.status, EvaluatorStatus.SUFFICIENT)

    def test_I4_poisoned_chunk_overwrite_must_not_keep_sufficient(self):
        """NEW: same chunk_id overwritten with different content after SATISFIED.

        Finish Gate must not remain SUFFICIENT for poisoned content.
        """
        state = StructuredEvidenceState(original_query="I4 overwrite")
        state.expected_requirement_ids = {"R1"}
        req = EvidenceRequirement(
            id="R1", description="Cấm sa thải", mandatory=True, linked_evidence_ids=["C1"]
        )
        state.add_requirement(req)
        state.add_raw_retrieval_output(
            task_id="t1",
            task_result={
                "chunks": [
                    {
                        "chunk_id": "C1",
                        "doc_id": "DOC1",
                        "content": "Điều 37: Cấm sa thải lao động mang thai.",
                    }
                ]
            },
            run_id="run_1",
        )
        state.auto_verify_retrieval(
            task_id="t1",
            run_id="run_1",
            valid_corpus_doc_ids={"DOC1"},
            valid_corpus_chunk_ids_by_doc={"DOC1": {"C1"}},
            semantic_oracle={("R1", "C1"): EntailmentRelation.ENTAILMENT},
        )
        self.assertEqual(req.status, RequirementStatus.SATISFIED)

        state.add_raw_retrieval_output(
            task_id="t2",
            task_result={
                "chunks": [
                    {
                        "chunk_id": "C1",
                        "doc_id": "DOC1",
                        "content": "POISON: không có lệnh cấm nào cả.",
                    }
                ]
            },
            run_id="run_2",
        )
        state.auto_verify_retrieval(
            task_id="t2",
            run_id="run_2",
            valid_corpus_doc_ids={"DOC1"},
            valid_corpus_chunk_ids_by_doc={"DOC1": {"C1"}},
            semantic_oracle={("R1", "C1"): EntailmentRelation.NEUTRAL},
        )
        self.assertEqual(state.evidences["C1"].content, "POISON: không có lệnh cấm nào cả.")
        gate = state.evaluate_finish_gate()
        self.assertNotEqual(
            gate.status,
            EvaluatorStatus.SUFFICIENT,
            "I4: Finish Gate stayed SUFFICIENT after chunk_id C1 was overwritten "
            f"with poisoned content. status={gate.status} req={req.status}",
        )

    def test_I4b_receipt_from_other_query_same_req_id_must_be_rejected(self):
        """NEW vs ADV-D1: ADV-D1 used different requirement ids (REQ_A vs REQ_B).

        Same requirement id, different query_hash, must still fail.
        """
        q_a = hashlib.sha256(b"query A unique").hexdigest()
        q_b = hashlib.sha256(b"query B unique").hexdigest()
        self.assertNotEqual(q_a, q_b)

        from kag.solver.evidence_aware.models import Claim, PresenceStatus

        ev = Evidence(
            id="E1",
            content="Content A",
            provenance=Provenance(doc_id="DOC1", chunk_id="C1"),
            modality=ModalityType.TEXT,
        )
        claim = Claim(id="CLAIM_R1_E1", statement="Claim A")
        s1 = FourStageEvidenceVerifier.stage1_verify_presence(
            "E1", {"E1"}, run_id="run_A"
        )
        s2 = FourStageEvidenceVerifier.stage2_verify_provenance(
            ev,
            {"DOC1"},
            valid_corpus_chunk_ids_by_doc={"DOC1": {"C1"}},
            run_id="run_A",
        )
        self.assertEqual(s1.status, PresenceStatus.PRESENCE_CONFIRMED)
        self.assertEqual(s2.status, ProvenanceValidationStatus.PROVENANCE_VERIFIED)
        s3 = FourStageEvidenceVerifier.stage3_verify_entailment(
            claim=claim,
            evidence=ev,
            stage1_status=s1,
            stage2_status=s2,
            ground_truth_relation=EntailmentRelation.ENTAILMENT,
            run_id="run_A",
        )
        receipt_a = FourStageEvidenceVerifier.create_verification_receipt(
            claim,
            ev,
            s1,
            s2,
            s3,
            run_id="run_A",
            requirement_id="R1",
            query_hash=q_a,
        )

        req_b = EvidenceRequirement(id="R1", description="Req in query B", mandatory=True)
        try:
            status = FourStageEvidenceVerifier.stage4_evaluate_requirement_coverage(
                requirement=req_b,
                entailment_results=[receipt_a],
            )
        except SchemaValidationError:
            return
        self.assertNotEqual(
            status,
            RequirementStatus.SATISFIED,
            "I4b: receipt issued for query A was accepted for query B because "
            "requirement_id matched and query_hash was not rebound",
        )

    def test_I6_legitimate_complete_evidence_still_reaches_sufficient(self):
        """Invariant 6 control: valid path must still exist."""
        state = StructuredEvidenceState(original_query="I6 happy path")
        state.expected_requirement_ids = {"R1", "R2"}
        r1 = EvidenceRequirement(
            id="R1",
            description="Cấm sa thải",
            mandatory=True,
            doc_scope="DOC_A",
            linked_evidence_ids=["C_A"],
        )
        r2 = EvidenceRequirement(
            id="R2",
            description="Khung phạt",
            mandatory=True,
            doc_scope="DOC_B",
            linked_evidence_ids=["C_B"],
        )
        state.add_requirement(r1)
        state.add_requirement(r2)
        state.add_raw_retrieval_output(
            task_id="t1",
            task_result={
                "chunks": [
                    {
                        "chunk_id": "C_A",
                        "doc_id": "DOC_A",
                        "content": "Cấm sa thải.",
                    }
                ]
            },
            run_id="run_1",
        )
        state.add_raw_retrieval_output(
            task_id="t2",
            task_result={
                "chunks": [
                    {
                        "chunk_id": "C_B",
                        "doc_id": "DOC_B",
                        "content": "Phạt 20 triệu.",
                    }
                ]
            },
            run_id="run_2",
        )
        oracle = {
            ("R1", "C_A"): EntailmentRelation.ENTAILMENT,
            ("R2", "C_B"): EntailmentRelation.ENTAILMENT,
        }
        mapping = {"DOC_A": {"C_A"}, "DOC_B": {"C_B"}}
        docs = {"DOC_A", "DOC_B"}
        state.auto_verify_retrieval(
            task_id="t1",
            run_id="run_1",
            valid_corpus_doc_ids=docs,
            valid_corpus_chunk_ids_by_doc=mapping,
            semantic_oracle=oracle,
        )
        state.auto_verify_retrieval(
            task_id="t2",
            run_id="run_2",
            valid_corpus_doc_ids=docs,
            valid_corpus_chunk_ids_by_doc=mapping,
            semantic_oracle=oracle,
        )
        gate = state.evaluate_finish_gate()
        self.assertEqual(r1.status, RequirementStatus.SATISFIED)
        self.assertEqual(r2.status, RequirementStatus.SATISFIED)
        self.assertEqual(gate.status, EvaluatorStatus.SUFFICIENT)

    async def test_I7_plannerabc_fallback_must_deliver_rejection_feedback(self):
        """NEW: adapter fallback path (no llm/plan_prompt) used by official e2e mocks.

        Rejection feedback must actually reach planner.ainvoke.
        """
        planner = PlannerABCOnly()
        adapter = EvidenceAwarePlannerAdapter(planner)
        adapter.set_rejection_feedback("Thiếu R2 khung phạt")
        ctx = Context()
        await adapter.ainvoke("query I7", context=ctx, executors=[])
        self.assertTrue(planner.calls, "planner.ainvoke was never called")
        blob = str(planner.calls[0])
        self.assertIn(
            "FINISH_GATE_REJECTED",
            blob,
            "I7: PlannerABC fallback never received rejection feedback; "
            "adapter cleared it after writing formatted_context that was discarded",
        )
        self.assertIsNone(adapter.last_rejection_feedback)

    async def test_I5_two_requests_same_pipeline_must_not_mix_state(self):
        """Invariant 5 with identical requirement ids (Gemini used REQ_A vs REQ_B)."""

        def plan_factory(num_iter: int, ctx: Context) -> List[Task]:
            if num_iter == 1:
                return [Task(executor="Retriever", arguments={"query": "GET"})]
            return [Task(executor="Finish", arguments={})]

        class IterPlanner:
            def __init__(self) -> None:
                self.n = 0
                self.queries: List[str] = []

            async def ainvoke(self, query: str, context: Context = None, **kwargs):
                self.n += 1
                self.queries.append(query)
                n = kwargs.get("num_iteration") or self.n
                return plan_factory(n, context)

        planner = IterPlanner()
        retriever = MockRetriever(
            {
                "GET": {
                    "chunks": [
                        {"chunk_id": "C_SHARED", "doc_id": "DOC1", "content": "x"}
                    ]
                }
            }
        )
        generator = MockGenerator()
        pipeline = KAGEvidenceAwareIterativePipeline(
            planner=planner,
            executors=[retriever],
            generator=generator,
            max_iteration=3,
            evidence_aware=True,
        )

        state1 = StructuredEvidenceState(original_query="Q1")
        state1.expected_requirement_ids = {"R1"}
        state1.add_requirement(
            EvidenceRequirement(
                id="R1",
                description="Q1 claim",
                mandatory=True,
                linked_evidence_ids=["C_SHARED"],
            )
        )
        state2 = StructuredEvidenceState(original_query="Q2")
        state2.expected_requirement_ids = {"R1"}
        state2.add_requirement(
            EvidenceRequirement(
                id="R1",
                description="Q2 claim",
                mandatory=True,
                linked_evidence_ids=["C_SHARED"],
            )
        )

        from kag.solver.pipeline.kag_iterative_pipeline import MaxIterationsReachedError

        a1 = await pipeline.ainvoke(
            "Q1",
            evidence_state=state1,
            semantic_oracle={("R1", "C_SHARED"): EntailmentRelation.ENTAILMENT},
            valid_corpus_doc_ids={"DOC1"},
            valid_corpus_chunk_ids_by_doc={"DOC1": {"C_SHARED"}},
        )
        with self.assertRaises(MaxIterationsReachedError):
            await pipeline.ainvoke(
                "Q2",
                evidence_state=state2,
                semantic_oracle={("R1", "C_SHARED"): EntailmentRelation.NEUTRAL},
                valid_corpus_doc_ids={"DOC1"},
                valid_corpus_chunk_ids_by_doc={"DOC1": {"C_SHARED"}},
            )
        self.assertTrue(str(a1).startswith("ANSWER:"))
        self.assertEqual(state1.requirements["R1"].status, RequirementStatus.SATISFIED)
        self.assertNotEqual(
            state2.requirements["R1"].status,
            RequirementStatus.SATISFIED,
            "I5: Q2 inherited SATISFIED from Q1 because both used id R1",
        )

    async def test_I7b_rejection_feedback_must_not_appear_in_generator_tasks(self):
        planner = RecordingPlanner(
            {
                1: [Task(executor="Finish", arguments={})],
                2: [Task(executor="Retriever", arguments={"query": "GET"})],
                3: [Task(executor="Finish", arguments={})],
            }
        )
        retriever = MockRetriever(
            {
                "GET": {
                    "chunks": [
                        {
                            "chunk_id": "C1",
                            "doc_id": "DOC1",
                            "content": "Cấm sa thải",
                        }
                    ]
                }
            }
        )
        generator = MockGenerator()
        pipeline = KAGEvidenceAwareIterativePipeline(
            planner=planner,
            executors=[retriever],
            generator=generator,
            max_iteration=4,
            evidence_aware=True,
        )
        state = StructuredEvidenceState(original_query="I7b")
        state.expected_requirement_ids = {"R1"}
        state.add_requirement(
            EvidenceRequirement(
                id="R1",
                description="Cấm sa thải",
                mandatory=True,
                linked_evidence_ids=["C1"],
            )
        )
        answer = await pipeline.ainvoke(
            "I7b",
            evidence_state=state,
            semantic_oracle={("R1", "C1"): EntailmentRelation.ENTAILMENT},
            valid_corpus_doc_ids={"DOC1"},
            valid_corpus_chunk_ids_by_doc={"DOC1": {"C1"}},
        )
        self.assertEqual(answer, "ANSWER:I7b")
        self.assertEqual(len(generator.calls), 1)
        blob = str(generator.calls[0]["tasks"])
        self.assertNotIn("FINISH_GATE_REJECTED", blob)
        self.assertNotIn("FinishGateFeedback", blob)
        self.assertGreaterEqual(pipeline.rejections_count, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
