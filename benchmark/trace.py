# -*- coding: utf-8 -*-
"""Execution Trace Module: Records fine-grained pipeline execution events.

Eliminates circular inference by recording runtime events directly:
- Planning proposals per iteration
- Retrieval outputs and timestamps
- Finish proposals and evidence state at the EXACT moment of Finish
- Finish Gate decisions (accepted vs rejected)
- Generator invocation and inputs
- Termination status and rationale
"""

import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class TraceEvent:
    timestamp: float
    iteration: int
    event_type: str  # PLANNING | RETRIEVAL | FINISH_PROPOSED | FINISH_DECISION | GENERATOR_CALL | TERMINATION
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "iteration": self.iteration,
            "event_type": self.event_type,
            "details": self.details,
        }


class ExecutionTraceCollector:
    """Collects runtime execution events during pipeline problem-solving loop."""

    def __init__(self, query_id: str, query: str, pipeline_mode: str):
        self.query_id = query_id
        self.query = query
        self.pipeline_mode = pipeline_mode
        self.start_time = time.time()
        self.events: List[TraceEvent] = []
        self.final_status: str = "UNKNOWN"
        self.final_answer: str = ""
        self.termination_reason: str = ""
        self.elapsed_time: float = 0.0

    def record_planning(self, iteration: int, proposed_task: Dict[str, Any]):
        self.events.append(TraceEvent(
            timestamp=time.time(),
            iteration=iteration,
            event_type="PLANNING",
            details={"proposed_task": proposed_task},
        ))

    def record_retrieval(self, iteration: int, task_id: str, retrieved_chunks: List[Dict[str, Any]]):
        self.events.append(TraceEvent(
            timestamp=time.time(),
            iteration=iteration,
            event_type="RETRIEVAL",
            details={
                "task_id": task_id,
                "chunks": [
                    {
                        "chunk_id": c.get("chunk_id"),
                        "doc_id": c.get("doc_id"),
                        "content": c.get("content", "")[:200],  # excerpt for audit
                        "aspects": c.get("aspects", []),
                    }
                    for c in retrieved_chunks
                ],
            },
        ))

    def record_finish_proposed(self, iteration: int, evidence_pool_at_finish: List[Dict[str, Any]]):
        self.events.append(TraceEvent(
            timestamp=time.time(),
            iteration=iteration,
            event_type="FINISH_PROPOSED",
            details={
                "evidence_pool_at_finish": [
                    {
                        "chunk_id": c.get("chunk_id"),
                        "doc_id": c.get("doc_id"),
                        "content": c.get("content", ""),
                        "aspects": c.get("aspects", []),
                    }
                    for c in evidence_pool_at_finish
                ],
            },
        ))

    def record_finish_decision(
        self,
        iteration: int,
        accepted: bool,
        evaluator_status: str,
        decision: str,
        rationale: str = "",
    ):
        self.events.append(TraceEvent(
            timestamp=time.time(),
            iteration=iteration,
            event_type="FINISH_DECISION",
            details={
                "accepted": accepted,
                "evaluator_status": evaluator_status,
                "decision": decision,
                "rationale": rationale,
            },
        ))

    def record_generator_call(
        self,
        called: bool,
        input_chunks: Optional[List[Dict[str, Any]]] = None,
        answer: str = "",
        reason: str = "",
    ):
        self.events.append(TraceEvent(
            timestamp=time.time(),
            iteration=0,
            event_type="GENERATOR_CALL",
            details={
                "generator_called": called,
                "input_chunks_count": len(input_chunks) if input_chunks else 0,
                "generated_answer": answer,
                "reason": reason,
            },
        ))

    def record_termination(self, final_status: str, answer: str, reason: str, iterations: int):
        self.final_status = final_status
        self.final_answer = answer
        self.termination_reason = reason
        self.elapsed_time = round(time.time() - self.start_time, 4)
        self.events.append(TraceEvent(
            timestamp=time.time(),
            iteration=iterations,
            event_type="TERMINATION",
            details={
                "final_status": final_status,
                "iterations": iterations,
                "reason": reason,
            },
        ))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_id": self.query_id,
            "query": self.query,
            "pipeline_mode": self.pipeline_mode,
            "final_status": self.final_status,
            "final_answer": self.final_answer,
            "termination_reason": self.termination_reason,
            "elapsed_time": self.elapsed_time,
            "events": [e.to_dict() for e in self.events],
        }
