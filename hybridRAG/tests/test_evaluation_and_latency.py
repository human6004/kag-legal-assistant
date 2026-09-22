import unittest
import time
from retrieval.metrics.latency_tracker import LatencyTracker
from retrieval.search.bm25_search import BM25Search
from retrieval.search.hybrid_search import HybridSearch
from evaluation.dataset import BENCHMARK_DATASET
from evaluation.ragas_evaluator import RagasEvaluator
from llama_index.core.schema import TextNode, NodeWithScore


class TestLatencyAndEvaluation(unittest.TestCase):

    def test_latency_tracker_basic(self):
        tracker = LatencyTracker()

        with tracker.track("query_rewrite"):
            time.sleep(0.01)

        with tracker.track("vector_search"):
            time.sleep(0.01)

        tracker.stop_total()
        durations = tracker.to_dict(unit="seconds")

        self.assertIn("query_rewrite", durations)
        self.assertIn("vector_search", durations)
        self.assertIn("total", durations)
        self.assertGreaterEqual(durations["query_rewrite"], 0.009)
        self.assertGreaterEqual(durations["total"], 0.02)

        summary_text = tracker.summary()
        self.assertIn("GIAI ĐOẠN", summary_text)
        self.assertIn("Query Rewrite", summary_text)
        self.assertIn("Vector Search", summary_text)

    def test_latency_tracker_ms_conversion(self):
        tracker = LatencyTracker()
        tracker.record("graph_search", 0.05)
        tracker.record("bm25_search", 0.02)
        tracker.record("reranking", 0.03)

        dur_ms = tracker.to_dict(unit="ms")
        self.assertAlmostEqual(dur_ms["graph_search"], 50.0, places=1)
        self.assertAlmostEqual(dur_ms["bm25_search"], 20.0, places=1)
        self.assertAlmostEqual(dur_ms["reranking"], 30.0, places=1)

    def test_benchmark_dataset(self):
        self.assertGreater(len(BENCHMARK_DATASET), 0)
        first_item = BENCHMARK_DATASET[0]
        self.assertIn("user_input", first_item)
        self.assertIn("reference", first_item)
        self.assertIn("reference_contexts", first_item)
        self.assertIsInstance(first_item["reference_contexts"], list)

    def test_bm25_and_rrf_hybrid(self):
        nodes = [
            TextNode(text="Điều 34 xử phạt hành vi dùng AI giả mạo khuôn mặt", id_="node_1"),
            TextNode(text="Điều 11 xử phạt thông tin sai sự thật trên mạng", id_="node_2"),
            TextNode(text="Nghị định 13 bảo vệ dữ liệu cá nhân", id_="node_3")
        ]
        bm25 = BM25Search(nodes=nodes)
        results = bm25.search("xử phạt AI khuôn mặt", top_k=2)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].node.node_id, "node_1")

        hybrid = HybridSearch(k=60)
        vector_res = [NodeWithScore(node=nodes[0], score=0.9)]
        bm25_res = [NodeWithScore(node=nodes[0], score=15.0), NodeWithScore(node=nodes[1], score=5.0)]

        merged = hybrid.merge(vector_results=vector_res, bm25_results=bm25_res)
        self.assertGreater(len(merged), 0)
        self.assertEqual(merged[0].node.node_id, "node_1")

    def test_evaluator_fallback_metrics(self):
        evaluator = RagasEvaluator()
        sample_results = [
            {
                "question": "Dùng AI giả mạo khuôn mặt bị phạt bao nhiêu theo Điều 34?",
                "answer": "Theo Điều 34 Nghị định xử phạt vi phạm hành chính, hành vi dùng AI giả mạo khuôn mặt bị phạt từ 30 đến 50 triệu đồng.",
                "contexts": [
                    "Điều 34 quy định mức phạt từ 30.000.000 đến 50.000.000 đồng đối với hành vi sử dụng AI giả mạo khuôn mặt."
                ],
                "ground_truth": "Mức phạt từ 30.000.000 đến 50.000.000 đồng theo Điều 34."
            }
        ]

        metrics = evaluator.evaluate_fallback(sample_results)
        self.assertIn("faithfulness", metrics)
        self.assertIn("answer_relevancy", metrics)
        self.assertIn("context_precision", metrics)
        self.assertIn("context_recall", metrics)

        self.assertGreater(metrics["faithfulness"], 0.5)
        self.assertGreater(metrics["answer_relevancy"], 0.3)


if __name__ == "__main__":
    unittest.main()
