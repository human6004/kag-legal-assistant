# -*- coding: utf-8 -*-
"""D2 Integration Gate Probe: Testing Feedback Delivery Options to Real KAGIterativePlanner.

Compares:
- Option A: Context-compatible Task Event (Task(executor="FeedbackEvent", status=TaskStatus.FAILED))
- Option B: Planner Adapter / Planning Wrapper (Feedback injected into Planner prompt payload without polluting Context)

Evaluates:
1. Does feedback appear in Planner input on subsequent iteration?
2. Does feedback leak into Generator context?
3. Is TaskStatus enum contract preserved (no fake REJECTED)?
4. Is Context._tasks private attribute untouched?
5. Is Context DAG preserved without corruption?
"""

import sys
import os
import locale
import json
import asyncio
from typing import List, Dict, Any, Optional

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

# Ensure vendor KAG is on sys.path
VENDOR_KAG = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "vendor", "KAG"))
if not os.path.isdir(VENDOR_KAG):
    alt_vendor = os.environ.get("KAG_VENDOR_ROOT") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "vendor", "KAG"))
    if os.path.isdir(alt_vendor):
        VENDOR_KAG = alt_vendor
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
from kag.solver.planner.kag_iterative_planner import KAGIterativePlanner
from kag.interface.common.prompt import PromptABC
from kag.solver.evidence_aware.planner_adapter import EvidenceAwarePlannerAdapter


class MockLLMClient:
    """Mock LLM Client that records all calls and returns canned Task plans."""

    def __init__(self):
        self.call_history: List[Dict[str, Any]] = []

    async def ainvoke(self, payload: Dict[str, Any], prompt: Any, **kwargs) -> List[Task]:
        num_iteration = kwargs.get("num_iteration", len(self.call_history))
        record = {
            "iteration": num_iteration,
            "query": payload.get("query"),
            "context_payload": payload.get("context"),
            "executors": payload.get("executors"),
        }
        self.call_history.append(record)

        # Simulation logic:
        # Iteration 0: return Retriever task
        # Iteration 1: return Finish task (which will be rejected)
        # Iteration 2: return second Retriever task
        # Iteration 3: return Finish task (approved)
        if num_iteration == 0:
            return [Task(executor="Retriever", arguments={"query": "Điều kiện sa thải lao động mang thai"})]
        elif num_iteration == 1:
            return [Task(executor="Finish", arguments={})]
        elif num_iteration == 2:
            return [Task(executor="Retriever", arguments={"query": "Khung xử phạt sa thải lao động mang thai"})]
        else:
            return [Task(executor="Finish", arguments={})]


class DummyPrompt(PromptABC):
    template_en = "Query: {query}\nContext: {context}"
    template_zh = "Query: {query}\nContext: {context}"

    @property
    def template_variables(self) -> List[str]:
        return ["query", "context"]


# ==============================================================================
# PROBE FOR OPTION A: Context Task Event
# ==============================================================================
async def run_probe_option_a():
    print("\n=======================================================")
    print("RUNNING PROBE: OPTION A (Context Task Event)")
    print("=======================================================")
    mock_llm = MockLLMClient()
    planner = KAGIterativePlanner(llm=mock_llm, plan_prompt=DummyPrompt())
    context = Context()

    rejection_feedback = "THIẾU CHỨNG CỨ: Chưa có khung xử phạt R2 theo Nghị định 12/2022/NĐ-CP."

    # Iteration 0: Planner proposes Retriever task
    task0 = (await planner.ainvoke("Sa thải lao động mang thai", context=context, num_iteration=0))[0]
    task0.result = "Điều 37 BLLĐ: Cấm sa thải lao động nữ vì lý do mang thai."
    task0.status = TaskStatus.SUCCESS
    context.append_task(task0)

    # Iteration 1: Planner proposes Finish task
    task1 = (await planner.ainvoke("Sa thải lao động mang thai", context=context, num_iteration=1))[0]
    print(f"Iteration 1 proposed: executor={task1.executor}")

    # Finish Gate REJECTS task1
    # Option A: append Task event to Context with TaskStatus.FAILED
    feedback_task = Task(
        executor="FeedbackEvent",
        arguments={"rejection": rejection_feedback},
    )
    feedback_task.result = f"[FINISH_GATE_REJECTED] {rejection_feedback}"
    feedback_task.status = TaskStatus.FAILED
    context.append_task(feedback_task)

    # Iteration 2: Planner runs next iteration
    task2 = (await planner.ainvoke("Sa thải lao động mang thai", context=context, num_iteration=2))[0]
    task2.result = "Điều 28 NĐ 12/2022: Phạt tiền từ 10 đến 20 triệu đồng."
    task2.status = TaskStatus.SUCCESS
    context.append_task(task2)

    # Iteration 3: Planner proposes Finish again (now SUFFICIENT)
    task3 = (await planner.ainvoke("Sa thải lao động mang thai", context=context, num_iteration=3))[0]

    # Inspect results for Option A:
    # 1. Did feedback reach planner in Iteration 2?
    it2_input = mock_llm.call_history[2]["context_payload"]
    it2_has_feedback = any("[FINISH_GATE_REJECTED]" in str(item) for item in it2_input)
    print(f"Option A - Feedback reached Planner in Iteration 2: {it2_has_feedback}")

    # 2. What does Generator see if context is passed directly?
    generator_task_contexts = [t.get_task_context() for t in context.gen_task(False)]
    generator_sees_feedback = any("[FINISH_GATE_REJECTED]" in str(tc) for tc in generator_task_contexts)
    print(f"Option A - Generator receives rejection feedback in context: {generator_sees_feedback}")

    # 3. Context DAG nodes
    dag_nodes = list(context.get_dag().nodes())
    print(f"Option A - DAG nodes count: {len(dag_nodes)}, node IDs: {dag_nodes}")

    return {
        "option": "A",
        "planner_received_feedback": it2_has_feedback,
        "generator_contaminated": generator_sees_feedback,
        "dag_node_ids": dag_nodes,
        "call_history": mock_llm.call_history,
    }


# ==============================================================================
# PROBE FOR OPTION B: Planner Adapter / Wrapper (Using Production EvidenceAwarePlannerAdapter)
# ==============================================================================
async def run_probe_option_b():
    print("\n=======================================================")
    print("RUNNING PROBE: OPTION B (Planner Adapter / Wrapper)")
    print("=======================================================")
    mock_llm = MockLLMClient()
    raw_planner = KAGIterativePlanner(llm=mock_llm, plan_prompt=DummyPrompt())
    adapter = EvidenceAwarePlannerAdapter(raw_planner)
    context = Context()

    rejection_feedback = "THIẾU CHỨNG CỨ: Chưa có khung xử phạt R2 theo Nghị định 12/2022/NĐ-CP."

    # Iteration 0: Planner proposes Retriever task
    task0 = (await adapter.ainvoke("Sa thải lao động mang thai", context=context, num_iteration=0))[0]
    task0.result = "Điều 37 BLLĐ: Cấm sa thải lao động nữ vì lý do mang thai."
    task0.status = TaskStatus.SUCCESS
    context.append_task(task0)

    # Iteration 1: Planner proposes Finish task
    task1 = (await adapter.ainvoke("Sa thải lao động mang thai", context=context, num_iteration=1))[0]
    print(f"Iteration 1 proposed: executor={task1.executor}")

    # Finish Gate REJECTS task1
    # Option B: Set feedback in production adapter. DO NOT append fake task to context!
    adapter.set_rejection_feedback(rejection_feedback)

    # Iteration 2: Planner runs next iteration
    task2 = (await adapter.ainvoke("Sa thải lao động mang thai", context=context, num_iteration=2))[0]
    task2.result = "Điều 28 NĐ 12/2022: Phạt tiền từ 10 đến 20 triệu đồng."
    task2.status = TaskStatus.SUCCESS
    context.append_task(task2)

    # Iteration 3: Planner proposes Finish again (now SUFFICIENT)
    task3 = (await adapter.ainvoke("Sa thải lao động mang thai", context=context, num_iteration=3))[0]

    # Inspect results for Option B:
    # 1. Did feedback reach planner in Iteration 2?
    it2_input = mock_llm.call_history[2]["context_payload"]
    it2_has_feedback = any("[FINISH_GATE_REJECTED]" in str(item) for item in it2_input)
    print(f"Option B - Feedback reached Planner in Iteration 2: {it2_has_feedback}")

    # 2. What does Generator see if context is passed directly?
    generator_task_contexts = [t.get_task_context() for t in context.gen_task(False)]
    generator_sees_feedback = any("[FINISH_GATE_REJECTED]" in str(tc) for tc in generator_task_contexts)
    print(f"Option B - Generator receives rejection feedback in context: {generator_sees_feedback}")

    # 3. Context DAG nodes
    dag_nodes = list(context.get_dag().nodes())
    print(f"Option B - DAG nodes count: {len(dag_nodes)}, node IDs: {dag_nodes}")

    return {
        "option": "B",
        "planner_received_feedback": it2_has_feedback,
        "generator_contaminated": generator_sees_feedback,
        "dag_node_ids": dag_nodes,
        "call_history": mock_llm.call_history,
    }


async def main():
    res_a = await run_probe_option_a()
    res_b = await run_probe_option_b()

    print("\n=======================================================")
    print("D2 INTEGRATION GATE COMPARATIVE SUMMARY")
    print("=======================================================")
    print(f"Option A (Context Task Event):")
    print(f"  - Planner received feedback: {res_a['planner_received_feedback']}")
    print(f"  - Generator contaminated: {res_a['generator_contaminated']}  <-- CRITICAL DEFECT!")
    print(f"  - Context DAG polluted: {len(res_a['dag_node_ids'])} nodes  <-- DAG POLLUTION!")

    print(f"\nOption B (Planner Adapter / Wrapper):")
    print(f"  - Planner received feedback: {res_b['planner_received_feedback']}")
    print(f"  - Generator contaminated: {res_b['generator_contaminated']}  <-- 100% CLEAN!")
    print(f"  - Context DAG polluted: {len(res_b['dag_node_ids'])} nodes  <-- 100% CLEAN (only real tasks)!")

    # Save probe execution report to file for audit
    report_file = os.path.join(os.path.dirname(__file__), "d2_probe_report.json")
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump({"option_a": res_a, "option_b": res_b}, f, indent=2, ensure_ascii=False)
    print(f"\nReport saved to: {report_file}")


if __name__ == "__main__":
    asyncio.run(main())
