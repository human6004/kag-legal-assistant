# -*- coding: utf-8 -*-
"""Evidence-Aware Planner Adapter: Option B Implementation.

Injects Finish Gate feedback into the Planner prompt context payload without
contaminating the Context DAG or Generator context.
"""

from typing import Any, Dict, List, Optional
import os
import sys

# Ensure vendor KAG is on sys.path
VENDOR_KAG = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "vendor", "KAG"))
if VENDOR_KAG not in sys.path:
    sys.path.insert(0, VENDOR_KAG)

from kag.interface.solver.planner_abc import PlannerABC, Task
from kag.interface.solver.context import Context


class EvidenceAwarePlannerAdapter:
    """Wraps an upstream Planner to inject Finish Gate rejection feedback into

    the planning prompt payload without appending fake tasks to Context.
    """

    def __init__(self, planner: PlannerABC):
        self.planner = planner
        self.last_rejection_feedback: Optional[str] = None

    def set_rejection_feedback(self, feedback: Optional[str]) -> None:
        """Sets the rejection feedback to be delivered on the next planning iteration."""
        self.last_rejection_feedback = feedback

    def clear_rejection_feedback(self) -> None:
        """Clears pending rejection feedback."""
        self.last_rejection_feedback = None

    async def ainvoke(self, query: str, context: Context, **kwargs) -> List[Task]:
        """Asynchronously executes planning, injecting feedback into the LLM context

        payload if present, while preserving the purity of the Context DAG.
        """
        # Format context using upstream planner format_context
        if hasattr(self.planner, "format_context"):
            formatted_context = self.planner.format_context(context)
        else:
            formatted_context = []
            for task in context.gen_task():
                formatted_context.append({
                    "action": {"name": task.executor, "argument": task.arguments},
                    "result": task.result.to_string() if hasattr(task.result, "to_string") else str(task.result),
                })

        # Inject rejection feedback into formatted prompt payload if present
        feedback_str: Optional[str] = None
        if self.last_rejection_feedback:
            feedback_str = f"[FINISH_GATE_REJECTED]: {self.last_rejection_feedback}"
            formatted_context.append({
                "action": {"name": "FinishGateFeedback", "argument": {"decision": "REPLAN"}},
                "result": feedback_str,
            })
            # Clear after injecting so it is consumed exactly once per rejection
            self.last_rejection_feedback = None

        num_iteration = kwargs.get("num_iteration", 0)

        # If planner has an llm and plan_prompt (like KAGIterativePlanner)
        if hasattr(self.planner, "llm") and hasattr(self.planner, "plan_prompt"):
            return await self.planner.llm.ainvoke(
                {
                    "query": query,
                    "context": formatted_context,
                    "executors": kwargs.get("executors", []),
                },
                self.planner.plan_prompt,
                segment_name="thinker",
                tag_name=f"Iterative planning {num_iteration}",
                **kwargs,
            )

        # Fallback to direct ainvoke for PlannerABC: deliver rejection feedback via kwargs
        if feedback_str:
            kwargs["rejection_feedback"] = feedback_str
            if hasattr(self.planner, "set_rejection_feedback"):
                getattr(self.planner, "set_rejection_feedback")(feedback_str)

        return await self.planner.ainvoke(query, context=context, **kwargs)
