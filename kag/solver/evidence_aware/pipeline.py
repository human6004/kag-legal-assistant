# -*- coding: utf-8 -*-
"""Evidence-Aware Iterative Pipeline: Subclassing KAGIterativePipeline.

Preserves all 6 upstream OpenSPG behaviors while enforcing Evidence-Aware Finish Gate:
1. @retry on planning()
2. task normalization (task = task[0])
3. atomic executor execution before context.append_task()
4. continuous kwargs propagation
5. FinishExecutor semantics (not invoking finish_executor.ainvoke)
6. fail-closed stopping when max iterations reached without SUFFICIENT
"""

import sys
import os
import logging
from typing import Any, Dict, List, Optional, Union, Tuple
from tenacity import retry, stop_after_attempt

# Ensure vendor KAG is on sys.path
VENDOR_KAG = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "vendor", "KAG"))
if VENDOR_KAG not in sys.path:
    sys.path.insert(0, VENDOR_KAG)

from kag.interface.solver.planner_abc import PlannerABC, Task, TaskStatus
from kag.interface.solver.context import Context
from kag.solver.pipeline.kag_iterative_pipeline import KAGIterativePipeline, MaxIterationsReachedError

from .models import (
    EvaluatorStatus,
    EvaluatorDecision,
    EvaluatorOutput,
    IncompleteAnswerResult,
    StructuredEvidenceState,
)
from .planner_adapter import EvidenceAwarePlannerAdapter

logger = logging.getLogger(__name__)


from kag.interface.solver.planner_abc import PlannerABC, Task, TaskStatus
from kag.interface.solver.context import Context
from kag.interface.solver.executor_abc import ExecutorABC
from kag.interface.solver.generator_abc import GeneratorABC
from kag.solver.pipeline.kag_iterative_pipeline import KAGIterativePipeline, MaxIterationsReachedError

from .models import (
    EvaluatorStatus,
    EvaluatorDecision,
    EvaluatorOutput,
    IncompleteAnswerResult,
    StructuredEvidenceState,
)
from .planner_adapter import EvidenceAwarePlannerAdapter

logger = logging.getLogger(__name__)

INTERNAL_EVAL_KWARGS = {
    "semantic_oracle",
    "valid_corpus_doc_ids",
    "valid_corpus_chunk_ids_by_doc",
    "valid_corpus_coords_by_doc",
    "evidence_state",
    "expected_requirement_ids",
    "fail_closed_mode",
    "semantic_proposals",
    "retrieved_graph_entities",
    "tracer",
}


class KAGEvidenceAwareIterativePipeline(KAGIterativePipeline):
    """Subclass of OpenSPG's KAGIterativePipeline providing evidence sufficiency gating

    and structured evidence tracking.
    """

    def __init__(
        self,
        planner: PlannerABC,
        executors: List[ExecutorABC],
        generator: GeneratorABC,
        max_iteration: int = 5,
        evidence_aware: bool = True,
        fail_closed_mode: str = "EXCEPTION",  # "EXCEPTION" (benchmark/CI) or "ABSTAIN" (production API)
        **kwargs,
    ):
        # Filter finish_executor if passed in kwargs to avoid duplicate / error
        kwargs.pop("finish_executor", None)
        super().__init__(
            planner=planner,
            executors=executors,
            generator=generator,
            max_iteration=max_iteration,
            **kwargs,
        )
        self.evidence_aware = evidence_aware
        self.fail_closed_mode = fail_closed_mode
        self.evidence_state: Optional[StructuredEvidenceState] = None
        self.planner_adapter: Optional[EvidenceAwarePlannerAdapter] = None
        self.rejections_count: int = 0
        self.last_evaluator_output: Optional[EvaluatorOutput] = None

        if self.evidence_aware and self.planner:
            self.planner_adapter = EvidenceAwarePlannerAdapter(self.planner)

    @retry(stop=stop_after_attempt(3), reraise=True)
    async def planning(self, query: str, context: Context, **kwargs) -> Tuple[Task, ExecutorABC]:
        """Perform planning phase with @retry decorator, using planner_adapter if evidence_aware."""
        active_planner = kwargs.get("active_planner") or (self.planner_adapter if (self.evidence_aware and self.planner_adapter) else self.planner)
        # Filter internal evaluation kwargs to prevent leakage to Planner (R10 fix)
        planner_kwargs = {k: v for k, v in kwargs.items() if k not in INTERNAL_EVAL_KWARGS and k != "active_planner"}
        task = await active_planner.ainvoke(
            query,
            context=context,
            executors=[x.schema() for x in self.executors],
            **planner_kwargs,
        )
        if isinstance(task, list):
            task = task[0]
        executor = self.select_executor(task.executor)
        if not executor:
            raise ValueError(f"Executor {task.executor} not in acceptable executors.")
        return task, executor

    async def ainvoke(self, query: str, **kwargs) -> Union[str, IncompleteAnswerResult]:
        """Executes problem-solving loop with evidence awareness.

        When evidence_aware=False: executes upstream baseline with zero overhead.
        When evidence_aware=True: enforces Finish Gate and Structured Evidence State.
        """
        # Baseline equivalence: zero overhead when evidence_aware is False
        if not self.evidence_aware:
            return await super().ainvoke(query, **kwargs)

        # Evidence-aware execution: Request-scoped isolation (ADV-A1 & ADV-A2 fix)
        evidence_state = kwargs.get("evidence_state") or StructuredEvidenceState(original_query=query)
        planner_adapter = EvidenceAwarePlannerAdapter(self.planner) if (self.evidence_aware and self.planner) else None
        rejections_count = 0
        num_iteration = 0
        context: Context = Context()
        finished_by_executor = False

        while num_iteration < self.max_iteration:
            num_iteration += 1
            evidence_state.iteration = num_iteration

            # 1. Behavior 1 & 2: planning with @retry normalization & executor selection
            task, executor = await self.planning(
                query,
                context,
                active_planner=planner_adapter,
                num_iteration=num_iteration,
                **kwargs,
            )

            # 2. Finish Gate Interception
            is_finish = (
                executor == self.finish_executor
                or executor.__class__.__name__ == "FinishExecutor"
                or (hasattr(executor, "schema") and executor.schema().get("name") == "finish_executor")
            )
            if is_finish:
                try:
                    eval_output = evidence_state.evaluate_finish_gate()
                    self.last_evaluator_output = eval_output
                except Exception as eval_err:
                    logger.error(f"Critical error during Finish Gate evaluation: {eval_err}")
                    if self.fail_closed_mode == "ABSTAIN":
                        return IncompleteAnswerResult(
                            status="ABSTAIN",
                            answer=f"Hệ thống từ chối đưa ra kết luận do lỗi nội bộ trong quá trình thẩm định chứng cứ (EVALUATOR_ERROR): {eval_err}.",
                            original_query=query,
                            iterations_executed=num_iteration,
                            max_iterations=self.max_iteration,
                            missing_requirements=[
                                r.to_dict() for r in evidence_state.get_missing_mandatory_requirements()
                            ],
                        )
                    else:
                        raise MaxIterationsReachedError(
                            f"Evaluator failed critically during Finish Gate evaluation: {eval_err}"
                        ) from eval_err

                if eval_output.status == EvaluatorStatus.SUFFICIENT:
                    # Approved: accept Finish and proceed to Generator
                    context.append_task(task)
                    finished_by_executor = True
                    break
                else:
                    # Rejected: deliver feedback to request-scoped Planner for next iteration
                    rejections_count += 1
                    if planner_adapter:
                        planner_adapter.set_rejection_feedback(eval_output.rationale)
                    logger.info(
                        f"Finish Gate rejected iteration {num_iteration}: "
                        f"status={eval_output.status}, decision={eval_output.next_decision}"
                    )
                    continue

            # 3. Behavior 3: Execute operational task BEFORE appending to context
            exec_kwargs = {k: v for k, v in kwargs.items() if k not in INTERNAL_EVAL_KWARGS and k != "active_planner"}
            await executor.ainvoke(query, task, context, **exec_kwargs)

            # Ingest raw retrieval output into structured evidence state
            if hasattr(task, "result") and task.result is not None:
                evidence_state.add_raw_retrieval_output(
                    task_id=task.id,
                    task_result=task.result,
                    run_id=f"run_iter_{num_iteration}",
                )
                # Automatically trigger 4-stage verification chain across ingested evidence
                semantic_oracle = kwargs.get("semantic_oracle")
                semantic_proposals = kwargs.get("semantic_proposals")
                valid_corpus_doc_ids = kwargs.get("valid_corpus_doc_ids") or set()
                valid_corpus_chunk_ids_by_doc = kwargs.get("valid_corpus_chunk_ids_by_doc")
                valid_corpus_coords_by_doc = kwargs.get("valid_corpus_coords_by_doc")
                retrieved_graph_entities = kwargs.get("retrieved_graph_entities")
                evidence_state.auto_verify_retrieval(
                    task_id=task.id,
                    run_id=f"run_iter_{num_iteration}",
                    valid_corpus_doc_ids=valid_corpus_doc_ids,
                    valid_corpus_chunk_ids_by_doc=valid_corpus_chunk_ids_by_doc,
                    valid_corpus_coords_by_doc=valid_corpus_coords_by_doc,
                    retrieved_graph_entities=retrieved_graph_entities,
                    semantic_oracle=semantic_oracle,
                    semantic_proposals=semantic_proposals,
                )

            # Add task to context only after successful execution
            context.append_task(task)

        # Update instance properties for post-run inspection
        self.evidence_state = evidence_state
        self.rejections_count = rejections_count
        self.planner_adapter = planner_adapter

        # 4. Behavior 6: Fail-closed handling when budget exhausts without SUFFICIENT
        if not finished_by_executor:
            if self.fail_closed_mode == "ABSTAIN":
                return IncompleteAnswerResult(
                    status="ABSTAIN",
                    original_query=query,
                    iterations_executed=num_iteration,
                    max_iterations=self.max_iteration,
                    missing_requirements=[
                        r.to_dict() for r in evidence_state.get_missing_mandatory_requirements()
                    ],
                    unresolved_conflicts=[
                        c.conflict_id for c in evidence_state.conflicts.values() if c.status.value == "OPEN"
                    ],
                )
            else:
                raise MaxIterationsReachedError(
                    f"Evidence-Aware Pipeline reached max_iteration ({self.max_iteration}) "
                    f"without satisfying mandatory evidence requirements for query: {query}"
                )

        # 5. Behavior 5 & 6: Generator invocation with internal kwargs filtered (R10 fix)
        gen_kwargs = {k: v for k, v in kwargs.items() if k not in INTERNAL_EVAL_KWARGS and k != "active_planner"}
        answer = await self.generator.ainvoke(query, context, **gen_kwargs)
        return answer
