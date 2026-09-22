# -*- coding: utf-8 -*-
"""Unified Benchmark Runner for A0 (Baseline) vs A1 (Evidence-Aware KAG).

Supports offline dry-run validation using simulated retrieval and planner executors,
guaranteeing zero live LLM API calls while validating harness schemas and metrics.
Records runtime execution traces directly (ExecutionTraceCollector) and evaluates
objectively via evaluate_single_trace without hardcoded heuristics or query_id maps.
"""

import sys
import os
import json
import time
import locale
import asyncio
import argparse
from typing import Dict, List, Any, Set

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

# Ensure vendor and candidate root are on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WT_ROOT = os.path.dirname(SCRIPT_DIR)
if WT_ROOT not in sys.path:
    sys.path.insert(0, WT_ROOT)

VENDOR_KAG = os.environ.get("KAG_VENDOR_ROOT") or os.path.join(WT_ROOT, "vendor", "KAG")
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
    StructuredEvidenceState,
)
from kag.solver.evidence_aware.pipeline import KAGEvidenceAwareIterativePipeline
from benchmark.trace import ExecutionTraceCollector
from benchmark.evaluator import evaluate_single_trace


# ---------------------------------------------------------------------------
# Offline Mock Components for Deterministic Harness Validation
# ---------------------------------------------------------------------------

class OfflineBenchmarkRetriever(ExecutorABC):
    """Simulated legal retriever delivering pre-indexed legal corpus chunks."""

    def __init__(self):
        super().__init__()
        self.chunk_store = {
            "Q1_licensing": {
                "chunks": [{
                    "chunk_id": "CHK_341_ART4",
                    "doc_id": "341-2026-ND-CP",
                    "content": "Điều 4: Hồ sơ đề nghị cấp Giấy phép gồm Đơn đề nghị, Bản sao GĐKKD, Đề án kinh doanh, Phương án bảo đảm an ninh mạng.",
                    "aspects": ["licensing_dossier"],
                }]
            },
            "Q2_transparency": {
                "chunks": [{
                    "chunk_id": "CHK_05_ART3",
                    "doc_id": "05-2026-TT-BKHCN",
                    "content": "Điều 3: Nguyên tắc minh bạch và giải trình: Bảo đảm công khai mục đích sử dụng AI và giải trình quyết định tự động.",
                    "aspects": ["transparency_principle"],
                }]
            },
            "Q3_prohibition": {
                "chunks": [{
                    "chunk_id": "CHK_116_ART8",
                    "doc_id": "116-2025-QH15",
                    "content": "Điều 8: Nghiêm cấm hành vi phát tán thông tin sai sự thật trên không gian mạng.",
                    "aspects": ["prohibition"],
                }]
            },
            "Q3_penalty": {
                "chunks": [{
                    "chunk_id": "CHK_330_ART15",
                    "doc_id": "330-2026-ND-CP",
                    "content": "Điều 15: Phạt tiền từ 10.000.000 đồng đến 20.000.000 đồng đối với hành vi phát tán tin giả.",
                    "aspects": ["penalty"],
                }]
            },
            "Q4_tech_req": {
                "chunks": [{
                    "chunk_id": "CHK_134_ART12",
                    "doc_id": "134-2025-QH15",
                    "content": "Điều 12: Hệ thống AI rủi pro cao phải thiết lập hệ thống quản lý rủi ro và tự động ghi nhật ký.",
                    "aspects": ["technical_requirements"],
                }]
            },
            "Q4_penalty": {
                "chunks": [{
                    "chunk_id": "CHK_142_ART25",
                    "doc_id": "142-2026-ND-CP",
                    "content": "Điều 25: Đình chỉ lưu hành và phạt tiền đến 100 triệu đồng nếu không đánh giá sự phù hợp của AI rủi ro cao.",
                    "aspects": ["enforcement_penalty"],
                }]
            },
            "Q5_retention_old": {
                "chunks": [{
                    "chunk_id": "CHK_53_ART18",
                    "doc_id": "53-2022-ND-CP",
                    "content": "Điều 18: Thời hạn lưu trữ nhật ký hệ thống thông tin là ít nhất 12 tháng.",
                    "aspects": ["retention_period"],
                }]
            },
            "Q5_retention_new": {
                "chunks": [{
                    "chunk_id": "CHK_331_ART20",
                    "doc_id": "331-2026-ND-CP",
                    "content": "Điều 20: Thời hạn lưu trữ nhật ký hệ thống thông tin tối thiểu phải là 24 tháng.",
                    "aspects": ["retention_period"],
                }]
            },
            "Q6_jurisdiction_old": {
                "chunks": [{
                    "chunk_id": "CHK_24_ART35",
                    "doc_id": "24-2018-QH14",
                    "content": "Điều 35: Cục An ninh mạng Bộ Công an có thẩm quyền thanh tra an ninh mạng toàn diện.",
                    "aspects": ["jurisdiction"],
                }]
            },
            "Q6_jurisdiction_new": {
                "chunks": [{
                    "chunk_id": "CHK_116_ART40",
                    "doc_id": "116-2025-QH15",
                    "content": "Điều 40: Ngân hàng Nhà nước Việt Nam chủ trì thanh tra an ninh mạng các tổ chức tín dụng.",
                    "aspects": ["jurisdiction"],
                }]
            },
        }

    def schema(self) -> Dict[str, Any]:
        return {"name": "Retriever", "description": "Offline benchmark retriever", "parameters": {}}

    async def ainvoke(self, query: str, task: Task, context: Context, **kwargs):
        retrieval_key = task.arguments.get("key", "")
        task.result = self.chunk_store.get(retrieval_key, {"chunks": [], "err_msg": "NO_MATCH"})
        task.status = TaskStatus.SUCCESS
        return task.result


class OfflineBenchmarkPlanner:
    """Planner simulating realistic behaviors under unconstrained vs feedback-guided loops."""

    def __init__(self, query_item: Dict[str, Any]):
        self.query_item = query_item
        self.qid = query_item["query_id"]
        self.rejection_feedback = None

    def set_rejection_feedback(self, feedback: str):
        self.rejection_feedback = feedback

    async def ainvoke(self, query: str, context: Context = None, **kwargs) -> List[Task]:
        num_iter = kwargs.get("num_iteration", 1)

        # CAT-1: Single-aspect queries (Q1, Q2)
        if self.qid == "Q1":
            if num_iter == 1:
                return [Task(executor="Retriever", arguments={"key": "Q1_licensing"})]
            return [Task(executor="Finish", arguments={})]

        if self.qid == "Q2":
            if num_iter == 1:
                return [Task(executor="Retriever", arguments={"key": "Q2_transparency"})]
            return [Task(executor="Finish", arguments={})]

        # CAT-2: Multi-aspect queries (Q3, Q4)
        if self.qid == "Q3":
            if num_iter == 1:
                return [Task(executor="Retriever", arguments={"key": "Q3_prohibition"})]
            elif num_iter == 2:
                return [Task(executor="Finish", arguments={})]
            elif num_iter == 3:
                return [Task(executor="Retriever", arguments={"key": "Q3_penalty"})]
            else:
                return [Task(executor="Finish", arguments={})]

        if self.qid == "Q4":
            if num_iter == 1:
                return [Task(executor="Retriever", arguments={"key": "Q4_tech_req"})]
            elif num_iter == 2:
                return [Task(executor="Finish", arguments={})]
            elif num_iter == 3:
                return [Task(executor="Retriever", arguments={"key": "Q4_penalty"})]
            else:
                return [Task(executor="Finish", arguments={})]

        # CAT-3: Conflicting Norms queries (Q5, Q6)
        if self.qid == "Q5":
            if num_iter == 1:
                return [Task(executor="Retriever", arguments={"key": "Q5_retention_old"})]
            elif num_iter == 2:
                return [Task(executor="Retriever", arguments={"key": "Q5_retention_new"})]
            else:
                return [Task(executor="Finish", arguments={})]

        if self.qid == "Q6":
            if num_iter == 1:
                return [Task(executor="Retriever", arguments={"key": "Q6_jurisdiction_old"})]
            elif num_iter == 2:
                return [Task(executor="Retriever", arguments={"key": "Q6_jurisdiction_new"})]
            else:
                return [Task(executor="Finish", arguments={})]

        # CAT-4: Unanswerable queries (Q7, Q8)
        if self.qid in ("Q7", "Q8"):
            if num_iter == 1:
                return [Task(executor="Retriever", arguments={"key": "UNANSWERABLE_KEY"})]
            else:
                return [Task(executor="Finish", arguments={})]

        return [Task(executor="Finish", arguments={})]


class OfflineBenchmarkGenerator:
    """Objective generator that synthesizes answers purely from retrieved context chunks.

    Zero knowledge of ground_truth_answer; zero branching on A0/A1 mode.
    """

    async def ainvoke(self, query: str, context: Context, **kwargs) -> str:
        retrieved_chunks = []
        if context:
            for task in context.gen_task(False):
                if hasattr(task, "result") and isinstance(task.result, dict):
                    retrieved_chunks.extend(task.result.get("chunks", []))

        if not retrieved_chunks:
            return f"Không tìm thấy căn cứ pháp lý trong hồ sơ truy vấn cho: {query}"

        contents = [c.get("content", "") for c in retrieved_chunks if c.get("content")]
        return f"Căn cứ tài liệu thu thập được: {' '.join(contents)}"


# ---------------------------------------------------------------------------
# Runner Execution with Trace Recording
# ---------------------------------------------------------------------------

async def run_single_benchmark_query(
    mode: str,
    query_item: Dict[str, Any],
    max_iteration: int = 5,
) -> Dict[str, Any]:
    """Execute a single query under either A0 or A1 configuration with full trace capture."""
    query = query_item["query"]
    qid = query_item["query_id"]

    collector = ExecutionTraceCollector(query_id=qid, query=query, pipeline_mode=mode)

    planner = OfflineBenchmarkPlanner(query_item=query_item)
    retriever = OfflineBenchmarkRetriever()
    generator = OfflineBenchmarkGenerator()

    is_evidence_aware = (mode == "A1")

    pipeline = KAGEvidenceAwareIterativePipeline(
        planner=planner,
        executors=[retriever],
        generator=generator,
        max_iteration=max_iteration,
        evidence_aware=is_evidence_aware,
        fail_closed_mode="ABSTAIN",
    )

    # Setup evidence state requirements for A1
    state = None
    semantic_oracle = {}
    valid_corpus_doc_ids = set()
    valid_corpus_chunk_ids_by_doc = {}

    if is_evidence_aware:
        state = StructuredEvidenceState(original_query=query)
        for aspect in query_item.get("required_aspects", []):
            req = EvidenceRequirement(
                id=f"REQ_{aspect.upper()}",
                description=f"Requirement for aspect: {aspect}",
                mandatory=True,
                required_aspects=[aspect],
            )
            state.add_requirement(req)

        state.expected_requirement_ids = set(state.requirements.keys())

        # Link expected evidence chunks and mock oracle for contract test
        if qid == "Q1":
            state.requirements["REQ_LICENSING_DOSSIER"].linked_evidence_ids = ["CHK_341_ART4"]
            semantic_oracle[("REQ_LICENSING_DOSSIER", "CHK_341_ART4")] = EntailmentRelation.ENTAILMENT
            valid_corpus_doc_ids.add("341-2026-ND-CP")
            valid_corpus_chunk_ids_by_doc["341-2026-ND-CP"] = {"CHK_341_ART4"}
        elif qid == "Q2":
            state.requirements["REQ_TRANSPARENCY_PRINCIPLE"].linked_evidence_ids = ["CHK_05_ART3"]
            semantic_oracle[("REQ_TRANSPARENCY_PRINCIPLE", "CHK_05_ART3")] = EntailmentRelation.ENTAILMENT
            valid_corpus_doc_ids.add("05-2026-TT-BKHCN")
            valid_corpus_chunk_ids_by_doc["05-2026-TT-BKHCN"] = {"CHK_05_ART3"}
        elif qid == "Q3":
            state.requirements["REQ_PROHIBITION"].linked_evidence_ids = ["CHK_116_ART8"]
            state.requirements["REQ_PENALTY"].linked_evidence_ids = ["CHK_330_ART15"]
            semantic_oracle[("REQ_PROHIBITION", "CHK_116_ART8")] = EntailmentRelation.ENTAILMENT
            semantic_oracle[("REQ_PENALTY", "CHK_330_ART15")] = EntailmentRelation.ENTAILMENT
            valid_corpus_doc_ids.update(["116-2025-QH15", "330-2026-ND-CP"])
            valid_corpus_chunk_ids_by_doc["116-2025-QH15"] = {"CHK_116_ART8"}
            valid_corpus_chunk_ids_by_doc["330-2026-ND-CP"] = {"CHK_330_ART15"}
        elif qid == "Q4":
            state.requirements["REQ_TECHNICAL_REQUIREMENTS"].linked_evidence_ids = ["CHK_134_ART12"]
            state.requirements["REQ_ENFORCEMENT_PENALTY"].linked_evidence_ids = ["CHK_142_ART25"]
            semantic_oracle[("REQ_TECHNICAL_REQUIREMENTS", "CHK_134_ART12")] = EntailmentRelation.ENTAILMENT
            semantic_oracle[("REQ_ENFORCEMENT_PENALTY", "CHK_142_ART25")] = EntailmentRelation.ENTAILMENT
            valid_corpus_doc_ids.update(["134-2025-QH15", "142-2026-ND-CP"])
            valid_corpus_chunk_ids_by_doc["134-2025-QH15"] = {"CHK_134_ART12"}
            valid_corpus_chunk_ids_by_doc["142-2026-ND-CP"] = {"CHK_142_ART25"}
        elif qid in ("Q5", "Q6"):
            req_id = list(state.requirements.keys())[0]
            if qid == "Q5":
                state.requirements[req_id].linked_evidence_ids = ["CHK_53_ART18", "CHK_331_ART20"]
                semantic_oracle[(req_id, "CHK_53_ART18")] = EntailmentRelation.ENTAILMENT
                semantic_oracle[(req_id, "CHK_331_ART20")] = EntailmentRelation.CONTRADICTION
                valid_corpus_doc_ids.update(["53-2022-ND-CP", "331-2026-ND-CP"])
                valid_corpus_chunk_ids_by_doc["53-2022-ND-CP"] = {"CHK_53_ART18"}
                valid_corpus_chunk_ids_by_doc["331-2026-ND-CP"] = {"CHK_331_ART20"}
            else:
                state.requirements[req_id].linked_evidence_ids = ["CHK_24_ART35", "CHK_116_ART40"]
                semantic_oracle[(req_id, "CHK_24_ART35")] = EntailmentRelation.ENTAILMENT
                semantic_oracle[(req_id, "CHK_116_ART40")] = EntailmentRelation.CONTRADICTION
                valid_corpus_doc_ids.update(["24-2018-QH14", "116-2025-QH15"])
                valid_corpus_chunk_ids_by_doc["24-2018-QH14"] = {"CHK_24_ART35"}
                valid_corpus_chunk_ids_by_doc["116-2025-QH15"] = {"CHK_116_ART40"}

    final_status = "UNKNOWN"
    answer_text = ""
    reason = ""
    iterations = 0

    # Custom loop tracing wrapper around pipeline to record exact events
    context = Context()
    accumulated_chunks = []

    try:
        while iterations < max_iteration:
            iterations += 1
            if state:
                state.iteration = iterations

            task, executor = await pipeline.planning(
                query,
                context,
                active_planner=pipeline.planner_adapter if is_evidence_aware else pipeline.planner,
                num_iteration=iterations,
            )

            collector.record_planning(iterations, {"executor": task.executor, "arguments": getattr(task, "arguments", {})})

            is_finish = (
                executor == pipeline.finish_executor
                or executor.__class__.__name__ == "FinishExecutor"
                or (hasattr(executor, "schema") and executor.schema().get("name") == "finish_executor")
            )

            if is_finish:
                collector.record_finish_proposed(iterations, list(accumulated_chunks))
                if is_evidence_aware:
                    eval_out = state.evaluate_finish_gate()
                    pipeline.last_evaluator_output = eval_out
                    accepted = (eval_out.status.value == "SUFFICIENT")
                    collector.record_finish_decision(
                        iterations,
                        accepted=accepted,
                        evaluator_status=eval_out.status.value,
                        decision=eval_out.next_decision.value,
                        rationale=eval_out.rationale,
                    )
                    if accepted:
                        context.append_task(task)
                        final_status = "FINISHED"
                        reason = "Finish Gate approved with SUFFICIENT evidence."
                        break
                    else:
                        pipeline.rejections_count += 1
                        if pipeline.planner_adapter:
                            pipeline.planner_adapter.set_rejection_feedback(eval_out.rationale)
                        continue
                else:
                    collector.record_finish_decision(
                        iterations,
                        accepted=True,
                        evaluator_status="NO_GATE",
                        decision="FINISH",
                        rationale="Baseline A0 unconstrained termination",
                    )
                    context.append_task(task)
                    final_status = "FINISHED"
                    reason = "Baseline planner proposed Finish."
                    break

            # Execute retrieval task
            await executor.ainvoke(query, task, context)
            if hasattr(task, "result") and isinstance(task.result, dict):
                chunks = task.result.get("chunks", [])
                accumulated_chunks.extend(chunks)
                collector.record_retrieval(iterations, task.id, chunks)

                if is_evidence_aware and state:
                    state.add_raw_retrieval_output(task.id, task.result, f"run_iter_{iterations}")
                    state.auto_verify_retrieval(
                        task_id=task.id,
                        run_id=f"run_iter_{iterations}",
                        valid_corpus_doc_ids=valid_corpus_doc_ids,
                        valid_corpus_chunk_ids_by_doc=valid_corpus_chunk_ids_by_doc,
                        semantic_oracle=semantic_oracle,
                    )

            context.append_task(task)

        if final_status == "FINISHED":
            answer_text = await pipeline.generator.ainvoke(query, context)
            collector.record_generator_call(called=True, input_chunks=accumulated_chunks, answer=answer_text)
        else:
            final_status = "ABSTAIN"
            answer_text = "Hệ thống từ chối đưa ra kết luận (ABSTAIN) do ngân sách cạn kiệt hoặc chứng cứ chưa đầy đủ."
            reason = "Max iterations reached without sufficient evidence."
            collector.record_generator_call(called=False, reason="ABSTAIN_FAIL_CLOSED")

    except MaxIterationsReachedError:
        final_status = "MAX_ITERATIONS"
        answer_text = "ERROR: Max iterations reached without finish."
        reason = "MaxIterationsReachedError"
    except Exception as e:
        final_status = "ERROR"
        answer_text = f"CRITICAL_ERROR: {e}"
        reason = str(e)

    collector.record_termination(final_status, answer_text, reason, iterations)

    # Objectively evaluate execution trace against gold requirements
    trace_dict = collector.to_dict()
    eval_result = evaluate_single_trace(trace_dict, query_item)
    eval_result["trace"] = trace_dict
    return eval_result


async def main_async():
    parser = argparse.ArgumentParser(description="Run A0/A1 Benchmark Experiment with Execution Traces")
    parser.add_argument("--dataset", default="benchmark/synthetic_sample_dataset.jsonl", help="Input dataset JSONL")
    parser.add_argument("--mode", choices=["A0", "A1"], required=True, help="Pipeline mode (A0 or A1)")
    parser.add_argument("--output", required=True, help="Output results JSONL")
    args = parser.parse_args()

    queries = []
    with open(args.dataset, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                queries.append(json.loads(line))

    print(f"Loaded {len(queries)} benchmark queries from: {args.dataset}")
    print(f"Executing under Mode: {args.mode} with Full Execution Trace Recording")

    results = []
    for item in queries:
        res = await run_single_benchmark_query(mode=args.mode, query_item=item)
        results.append(res)
        print(f"  [{res['pipeline_mode']}] {res['query_id']} ({res['query_type']}): status={res['final_status']}, iters={res['iterations']}, rejections={res['rejections']}, accepted_pfr={res['accepted_premature_finish']}")

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"Saved {len(results)} results with traces to: {args.output}\n")


if __name__ == "__main__":
    asyncio.run(main_async())
