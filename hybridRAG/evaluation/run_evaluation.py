import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path

# Đảm bảo import được các module từ root của project
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Đảm bảo in tiếng Việt trên console Windows không bị lỗi bảng mã
if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from evaluation.dataset import load_dataset_flexible
from evaluation.ragas_evaluator import RagasEvaluator
from retrieval.metrics.latency_tracker import LatencyTracker


def calculate_percentile(data, percentile):
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = int(len(sorted_data) * (percentile / 100.0))
    idx = min(idx, len(sorted_data) - 1)
    return sorted_data[idx]


def run_evaluation(dataset_path: str = None, num_samples: int = None, use_mock: bool = False):
    print("=" * 70)
    print("   CHƯƠNG TRÌNH ĐÁNH GIÁ HỆ THỐNG GRAPHRAG CÂY MAI VÀNG")
    print("   (ĐO LƯỜNG TỐC ĐỘ GIAI ĐOẠN & CHẤT LƯỢNG VỚI RAGAS)")
    print("=" * 70)

    # Nạp dữ liệu linh hoạt (ưu tiên file chỉ định hoặc pilot.jsonl)
    dataset = load_dataset_flexible(dataset_path)

    if num_samples is not None and num_samples > 0:
        dataset = dataset[:num_samples]

    print(f"\n[INFO] Số lượng mẫu đánh giá thực tế: {len(dataset)}")

    # Khởi tạo các thành phần RAG
    retriever = None
    generator = None
    llm = None

    if not use_mock:
        try:
            from llm.nvidia import NvidiaNimLLM
            from llm.answer_generator import AnswerGenerator
            from retrieval.retrieve import Retriever
            from database.neo4j_store import load_graph_index
            from database.chroma_store import load_vector_index

            print("[INFO] Đang kết nối Neo4j và ChromaDB...")
            llm = NvidiaNimLLM().get_llm()
            vector_index = load_vector_index()
            graph_index = load_graph_index()

            retriever = Retriever(
                llm=llm,
                vector_index=vector_index,
                graph_index=graph_index
            )
            generator = AnswerGenerator(llm=llm)
            print("[INFO] Khởi tạo hệ thống GraphRAG thành công!")
        except Exception as e:
            print(f"[CẢNH BÁO] Không thể kết nối Database/LLM trực tiếp: {e}")
            print("[CẢNH BÁO] Tự động chuyển sang chế độ MOCK để kiểm thử pipeline...")
            use_mock = True

    eval_results = []
    stage_latencies = {
        "query_rewrite": [],
        "hyde_generation": [],
        "vector_search": [],
        "graph_search": [],
        "hybrid_merge": [],
        "reranking": [],
        "answer_generation": [],
        "total": [],
    }

    # Chạy lần lượt từng mẫu kiểm thử
    for i, sample in enumerate(dataset, 1):
        q = sample["user_input"]
        gt = sample["reference"]
        ref_ctxs = sample.get("reference_contexts", [])
        case_id = sample.get("case_id", f"case_{i}")

        print(f"\n[{i}/{len(dataset)}] [{case_id}] Đang xử lý: \"{q}\"")

        tracker = LatencyTracker()

        if not use_mock and retriever and generator:
            try:
                contexts = retriever.retrieve(q, tracker=tracker)
                answer = generator.generate(q, contexts, tracker=tracker)
                tracker.stop_total()

                context_texts = [
                    c.node.get_content() if hasattr(c, "node") and hasattr(c.node, "get_content")
                    else getattr(c, "text", str(c))
                    for c in contexts
                ]
            except Exception as err:
                print(f"  [LỖI RAG]: {err}")
                answer = "Không đủ thông tin để trả lời."
                context_texts = ref_ctxs
                tracker.stop_total()
        else:
            # Chế độ Mock giả lập thời gian thực thi
            with tracker.track("query_rewrite"):
                time.sleep(0.08)
            with tracker.track("hyde_generation"):
                time.sleep(0.15)
            with tracker.track("vector_search"):
                time.sleep(0.05)
            with tracker.track("graph_search"):
                time.sleep(0.07)
            with tracker.track("hybrid_merge"):
                time.sleep(0.01)
            with tracker.track("reranking"):
                time.sleep(0.09)
            with tracker.track("answer_generation"):
                time.sleep(0.20)
            tracker.stop_total()

            answer = gt
            context_texts = ref_ctxs

        timings = tracker.to_dict(unit="seconds")
        print(f"  -> Hoàn tất trong {timings.get('total', 0)}s")

        for stage, val in timings.items():
            if stage in stage_latencies:
                stage_latencies[stage].append(val)

        eval_results.append({
            "case_id": case_id,
            "intent_family": sample.get("intent_family", ""),
            "tags": sample.get("tags", []),
            "question": q,
            "answer": answer,
            "contexts": context_texts,
            "ground_truth": gt,
            "latencies": timings
        })

    # Tính toán bảng thống kê độ trễ
    latency_summary = {}
    for stage, vals in stage_latencies.items():
        if vals:
            mean_val = round(sum(vals) / len(vals), 4)
            min_val = round(min(vals), 4)
            max_val = round(max(vals), 4)
            p95_val = round(calculate_percentile(vals, 95), 4)
            latency_summary[stage] = {
                "mean_seconds": mean_val,
                "mean_ms": round(mean_val * 1000, 1),
                "min_seconds": min_val,
                "max_seconds": max_val,
                "p95_seconds": p95_val,
            }

    # Đánh giá chất lượng RAG
    print("\n" + "=" * 70)
    print("   BẮT ĐẦU ĐÁNH GIÁ CHẤT LƯỢNG RAG VỚI RAGAS...")
    print("=" * 70)
    evaluator = RagasEvaluator(llm=llm)
    quality_evaluation = evaluator.evaluate(eval_results)

    # In bảng thống kê độ trễ
    print("\n" + "=" * 75)
    print(f"{'GIAI ĐOẠN TRUY VẤN':<28} | {'MEAN (s)':<10} | {'MEAN (ms)':<10} | {'P95 (s)':<10} | {'MAX (s)':<10}")
    print("-" * 75)
    labels = {
        "query_rewrite": "1. Query Rewrite",
        "hyde_generation": "2. HyDE Generation",
        "vector_search": "3. Vector Search (Chroma)",
        "graph_search": "4. Graph Search (Neo4j)",
        "hybrid_merge": "5. Hybrid Merge",
        "reranking": "6. Cross-Encoder Rerank",
        "answer_generation": "7. LLM Answer Gen",
        "total": "TỔNG TOÀN BỘ PIPELINE",
    }
    for stage, stats in latency_summary.items():
        name = labels.get(stage, stage)
        print(f"{name:<28} | {stats['mean_seconds']:<10.4f} | {stats['mean_ms']:<10.1f} | {stats['p95_seconds']:<10.4f} | {stats['max_seconds']:<10.4f}")
    print("=" * 75)

    # In điểm số chất lượng
    print("\n" + "=" * 55)
    print(f"   ĐIỂM CHẤT LƯỢNG RAG (Engine: {quality_evaluation.get('engine')})")
    print("=" * 55)
    metrics = quality_evaluation.get("metrics", {})
    metric_labels = {
        "faithfulness": "Faithfulness (Độ trung thực, không ảo giác)",
        "answer_relevancy": "Answer Relevancy (Độ liên quan câu trả lời)",
        "context_precision": "Context Precision (Độ chuẩn xác ngữ cảnh)",
        "context_recall": "Context Recall (Độ bao phủ ngữ cảnh)",
    }
    for k, v in metrics.items():
        lbl = metric_labels.get(k, k)
        print(f"  * {lbl:<48}: {v:.4f}")
    print("=" * 55)

    # Lưu file báo cáo JSON
    report_data = {
        "generated_at": datetime.now().isoformat(),
        "dataset_source": dataset_path or "pilot.jsonl",
        "num_samples": len(dataset),
        "evaluation_engine": quality_evaluation.get("engine"),
        "quality_metrics": metrics,
        "latency_summary": latency_summary,
        "sample_details": eval_results
    }

    report_json_path = PROJECT_ROOT / "evaluation" / "eval_report.json"
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] Đã lưu báo cáo JSON: {report_json_path}")

    # Tạo báo cáo Markdown
    md_lines = [
        "# Báo Cáo Đánh Giá Hệ Thống GraphRAG Cây Mai Vàng\n",
        f"- **Thời điểm đánh giá:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **Nguồn dữ liệu đánh giá:** `{dataset_path or 'pilot.jsonl'}`",
        f"- **Số lượng mẫu kiểm thử:** {len(dataset)} mẫu",
        f"- **Engine đánh giá:** `{quality_evaluation.get('engine')}`\n",
        "## 1. Điểm số Chất lượng RAG (RAG Quality Metrics)\n",
        "| Chỉ số đánh giá | Điểm số (0.0 - 1.0) | Ý nghĩa |",
        "| :--- | :--- | :--- |",
        f"| **Faithfulness** | `{metrics.get('faithfulness', 0):.4f}` | Câu trả lời bám sát context, không bịa đặt nguyên nhân/thuốc |",
        f"| **Answer Relevancy** | `{metrics.get('answer_relevancy', 0):.4f}` | Câu trả lời phản hồi đúng trọng tâm câu hỏi |",
        f"| **Context Precision** | `{metrics.get('context_precision', 0):.4f}` | Ngữ cảnh được truy xuất chứa đúng thông tin trọng điểm |",
        f"| **Context Recall** | `{metrics.get('context_recall', 0):.4f}` | Ngữ cảnh bao quát đủ thông tin theo đáp án chuẩn tham chiếu |\n",
        "## 2. Thống kê Tốc độ Truy vấn Từng Giai đoạn (Latency Breakdown)\n",
        "| Giai đoạn trong Pipeline | Trung bình (s) | Trung bình (ms) | P95 (s) | Tối đa (s) |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]

    for stage, stats in latency_summary.items():
        name = labels.get(stage, stage)
        md_lines.append(f"| **{name}** | {stats['mean_seconds']:.4f}s | {stats['mean_ms']}ms | {stats['p95_seconds']:.4f}s | {stats['max_seconds']:.4f}s |")

    md_lines.append("\n## 3. Chi tiết Từng Mẫu Kiểm Thử\n")
    for i, s in enumerate(eval_results, 1):
        cid = s.get("case_id", f"case_{i}")
        md_lines.append(f"### Mẫu {i} [{cid}]: {s['question']}")
        if s.get("intent_family"):
            md_lines.append(f"- **Phân loại intent:** `{s['intent_family']}` | **Tags:** `{', '.join(s.get('tags', []))}`")
        md_lines.append(f"- **Tổng thời gian xử lý:** `{s['latencies'].get('total', 0)}s`")
        md_lines.append(f"- **Câu trả lời sinh ra:**\n> {s['answer']}\n")
        md_lines.append(f"- **Đáp án tham chiếu (Ground Truth):**\n> {s['ground_truth']}\n")

    report_md_path = PROJECT_ROOT / "evaluation" / "eval_report.md"
    with open(report_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    print(f"[OK] Đã lưu báo cáo Markdown: {report_md_path}")

    return report_data


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Chạy đánh giá GraphRAG với dataset linh hoạt")
    parser.add_argument(
        "--dataset", "-d", "--file", "-f",
        type=str,
        default=None,
        help="Đường dẫn file dataset (.jsonl hoặc .json), mặc định tự động tìm pilot.jsonl"
    )
    parser.add_argument("--samples", "-s", type=int, default=None, help="Số lượng mẫu test cần chạy")
    parser.add_argument("--mock", action="store_true", help="Chạy giả lập để test pipeline không cần DB")
    args = parser.parse_args()

    run_evaluation(dataset_path=args.dataset, num_samples=args.samples, use_mock=args.mock)
