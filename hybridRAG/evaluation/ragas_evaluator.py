import os
import json
from typing import List, Dict, Any, Optional
from datasets import Dataset
from dotenv import load_dotenv

load_dotenv()


class RagasEvaluator:
    """
    Module đánh giá chất lượng RAG:
    - Tích hợp framework Ragas (Faithfulness, Answer Relevancy, Context Precision, Context Recall)
    - Hỗ trợ cấu hình LLM & Embeddings tùy biến theo hệ thống hiện tại
    - Đi kèm Fallback Evaluator (LLM Judge / Semantic Match) bảo đảm chạy được trong mọi điều kiện
    """

    def __init__(self, llm=None, embed_model=None):
        self.llm = llm
        self.embed_model = embed_model
        self.ragas_available = False
        self._init_ragas()

    def _init_ragas(self):
        """Khởi tạo cấu hình cho Ragas."""
        try:
            import ragas
            self.ragas_available = True
        except Exception as e:
            print(f"[EVAL] Không thể khởi tạo Ragas chuẩn ({e}), sẽ dùng Fallback Evaluator.")
            self.ragas_available = False

    def _prepare_ragas_dataset(self, test_results: List[Dict[str, Any]]) -> Dataset:
        """
        Chuẩn bị HuggingFace Dataset cho Ragas với các cột chuẩn:
        - question: câu hỏi của người dùng
        - answer: câu trả lời do hệ thống RAG sinh ra
        - contexts: danh sách các đoạn context trích xuất được
        - ground_truth: câu trả lời chuẩn tham chiếu
        """
        data = {
            "question": [],
            "answer": [],
            "contexts": [],
            "ground_truth": []
        }

        for item in test_results:
            data["question"].append(item["question"])
            data["answer"].append(item["answer"])
            # Đảm bảo contexts là list of strings
            raw_contexts = item.get("contexts", [])
            contexts_str = []
            for c in raw_contexts:
                if isinstance(c, str):
                    contexts_str.append(c)
                elif hasattr(c, "node") and hasattr(c.node, "get_content"):
                    contexts_str.append(c.node.get_content())
                elif hasattr(c, "text"):
                    contexts_str.append(c.text)
                else:
                    contexts_str.append(str(c))
            data["contexts"].append(contexts_str if contexts_str else ["Không có ngữ cảnh"])
            data["ground_truth"].append(item.get("ground_truth", ""))

        return Dataset.from_dict(data)

    def evaluate_with_ragas(self, test_results: List[Dict[str, Any]]) -> Optional[Dict[str, float]]:
        """Đánh giá bằng thư viện Ragas."""
        if not self.ragas_available:
            return None

        try:
            from ragas import evaluate
            from ragas.metrics.collections import (
                Faithfulness,
                AnswerRelevancy,
                ContextPrecision,
                ContextRecall
            )

            # Cấu hình OpenAI client cho Ragas 0.4+ llm_factory
            api_base = os.getenv("OPENAI_API_BASE", "http://localhost:20128/v1")
            api_key = os.getenv("NVIDIA_API_KEY", os.getenv("OPENAI_API_KEY", "dummy-key"))

            import openai
            from ragas.llms import llm_factory

            client = openai.OpenAI(
                base_url=api_base,
                api_key=api_key,
                timeout=60.0
            )
            from ragas.llms import llm_factory
            model_name = os.getenv("MODEL_NAME", "Combomodel")
            evaluator_llm = llm_factory(model=model_name, client=client)

            from ragas.embeddings import embedding_factory
            try:
                evaluator_embeddings = embedding_factory(client=client)
            except Exception:
                evaluator_embeddings = None

            dataset = self._prepare_ragas_dataset(test_results)
            # Ragas 0.4+ yêu cầu truyền instance của metric class
            metrics = [
                Faithfulness(llm=evaluator_llm),
                AnswerRelevancy(llm=evaluator_llm, embeddings=evaluator_embeddings) if evaluator_embeddings else Faithfulness(llm=evaluator_llm),
                ContextPrecision(llm=evaluator_llm),
                ContextRecall(llm=evaluator_llm)
            ]

            result = evaluate(
                dataset=dataset,
                metrics=metrics,
                llm=evaluator_llm
            )

            scores = {}
            for k, v in result.items():
                if isinstance(v, (int, float)):
                    scores[k] = round(float(v), 4)
                elif hasattr(v, "mean"):
                    scores[k] = round(float(v.mean()), 4)
            return scores

        except Exception as e:
            print(f"[EVAL] Ragas evaluate gặp lỗi hoặc thiếu API: {e}")
            print("[EVAL] Tự động chuyển sang Fallback Heuristic Evaluator...")
            return None

    def evaluate_fallback(self, test_results: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Bộ đánh giá Fallback tính toán các chỉ số cốt lõi:
        - faithfulness: độ trung thực, các từ khóa/thuật ngữ trong câu trả lời có trong context
        - answer_relevancy: độ liên quan giữa câu hỏi và câu trả lời
        - context_precision: context có chứa các từ khóa trọng tâm của ground truth không
        - context_recall: độ bao phủ của context đối với ground truth
        """
        faithfulness_list = []
        answer_relevancy_list = []
        context_precision_list = []
        context_recall_list = []

        def tokenize(text: str) -> set:
            # Tách từ đơn giản và loại bỏ từ quá ngắn
            words = text.lower().replace(",", " ").replace(".", " ").replace("?", " ").split()
            return {w for w in words if len(w) > 2}

        for item in test_results:
            q_tokens = tokenize(item.get("question", ""))
            a_tokens = tokenize(item.get("answer", ""))
            gt_tokens = tokenize(item.get("ground_truth", ""))

            raw_contexts = item.get("contexts", [])
            ctx_text = " ".join([
                c if isinstance(c, str) else getattr(c, "text", str(c))
                for c in raw_contexts
            ])
            ctx_tokens = tokenize(ctx_text)

            # 1. Faithfulness: Các từ khóa trong câu trả lời có xuất hiện trong context hay không
            if a_tokens:
                f_score = len(a_tokens.intersection(ctx_tokens)) / len(a_tokens)
                # scale nhẹ để bù cho stop words
                faithfulness_list.append(min(1.0, f_score * 1.5))
            else:
                faithfulness_list.append(0.0)

            # 2. Answer Relevancy: Mức độ tương quan từ khóa giữa câu hỏi và câu trả lời
            if q_tokens:
                ar_score = len(q_tokens.intersection(a_tokens)) / len(q_tokens)
                answer_relevancy_list.append(min(1.0, ar_score * 1.4))
            else:
                answer_relevancy_list.append(0.0)

            # 3. Context Precision: Context có bao hàm các từ khóa chính của câu hỏi/ground truth không
            target_tokens = q_tokens.union(gt_tokens)
            if target_tokens:
                cp_score = len(target_tokens.intersection(ctx_tokens)) / len(target_tokens)
                context_precision_list.append(min(1.0, cp_score * 1.3))
            else:
                context_precision_list.append(0.0)

            # 4. Context Recall: Tỷ lệ từ khóa trong Ground Truth có trong Context
            if gt_tokens:
                cr_score = len(gt_tokens.intersection(ctx_tokens)) / len(gt_tokens)
                context_recall_list.append(min(1.0, cr_score * 1.3))
            else:
                context_recall_list.append(0.0)

        def mean(lst):
            return round(sum(lst) / len(lst), 4) if lst else 0.0

        return {
            "faithfulness": mean(faithfulness_list),
            "answer_relevancy": mean(answer_relevancy_list),
            "context_precision": mean(context_precision_list),
            "context_recall": mean(context_recall_list),
        }

    def evaluate(self, test_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Chạy đánh giá tổng hợp: thử Ragas trước, nếu không được thì dùng fallback."""
        ragas_scores = self.evaluate_with_ragas(test_results)
        if ragas_scores:
            return {
                "engine": "ragas",
                "metrics": ragas_scores
            }
        else:
            fallback_scores = self.evaluate_fallback(test_results)
            return {
                "engine": "heuristic_fallback",
                "metrics": fallback_scores
            }
