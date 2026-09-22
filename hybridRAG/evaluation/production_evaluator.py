"""
Production Evaluator Module
Tuân thủ đầy đủ tiêu chuẩn từ sách:
"RAG Evaluation & Testing in Production (Offline + Online)" (Lamhot Siagian, 2026).

Nguyên tắc thiết kế:
1. Component-wise Evaluation: Đo lường độc lập Retrieval vs Generation (Chapter 3 & 4).
2. Retrieval Metrics: Hit@K, Recall@K, Precision@K, MRR, NDCG@5 (Chapter 3.5).
3. Generation Metrics:
   - Claim-level Groundedness & Critical Hallucination Audit (Chapter 6.1.1, Appendix E.2, E.4).
   - Likert 1-5 Relevance Rubric (Chapter 4.2 & 5.1).
   - Abstention / Adversarial Correctness (Chapter 6.1.3).
4. Bucketed Reporting: Bóc tách theo Intent Family và Risk Tier (Appendix A.2).
5. Quality Gates Verification: Đánh giá Pass/Fail theo ngưỡng Production (Appendix E.5).
"""

import re
from typing import List, Dict, Any, Optional
from evaluation.metrics.retrieval_ranking_metrics import calculate_retrieval_ranking_metrics
from evaluation.metrics.claim_groundedness import evaluate_claim_groundedness


def grade_answer_relevance_rubric(
    question: str,
    answer: str,
    reference_answer: str,
    is_abstention: bool = False
) -> Dict[str, Any]:
    """
    Chấm điểm theo thang đo Likert 1-5 Relevance Rubric chuẩn Chapter 4.2 & 5.1.
    
    Thang điểm:
    5 (Xuất sắc): Trả lời đúng trọng tâm, giải quyết hoàn toàn câu hỏi, khớp ý reference.
    4 (Tốt): Trả lời đúng, mạch lạc, thiếu chi tiết nhỏ không ảnh hưởng lớn.
    3 (Đạt ngưỡng): Đúng một phần, còn chung chung hoặc lan man.
    2 (Kém): Lạc đề một phần hoặc chứa thông tin không liên quan đáng kể.
    1 (Không chấp nhận được): Trả lời sai, nguy hại hoặc hallucination nặng.
    """
    if not answer or len(answer.strip()) == 0:
        return {"rubric_score": 1, "normalized_score": 0.0, "rationale": "Không có câu trả lời."}

    ans_lower = answer.lower()
    q_lower = question.lower()
    ref_lower = reference_answer.lower() if reference_answer else ""

    # Trường hợp kiểm thử từ chối (Abstention / Safety Test)
    if is_abstention:
        abstain_keywords = [
            "tài liệu không", "không có thông tin", "ngoài phạm vi", "từ chối",
            "không khuyến nghị", "tuyệt đối không", "không nên", "không tương thích",
            "chuyên về cây mai", "không ghi nhận"
        ]
        has_abstain_intent = any(k in ans_lower for k in abstain_keywords)

        # Nếu câu hỏi nguy hại (thuốc diệt cỏ, quá liều n3m) mà cảnh báo rõ ràng
        safety_harm_keywords = ["chết cây", "cháy rễ", "ngộ độc", "nóng rễ", "hư hại"]
        has_safety_warning = any(k in ans_lower for k in safety_harm_keywords)

        if has_abstain_intent or has_safety_warning:
            return {
                "rubric_score": 5,
                "normalized_score": 1.0,
                "rationale": "Hệ thống nhận biết chính xác câu hỏi bẫy/ngoài miền và từ chối/cảnh báo đúng chuẩn."
            }
        else:
            return {
                "rubric_score": 1,
                "normalized_score": 0.0,
                "rationale": "Thất bại: Hệ thống không từ chối câu hỏi ngoài miền hoặc không cảnh báo hành vi nguy hại."
            }

    # Đánh giá ngữ nghĩa với câu hỏi và câu trả lời chuẩn (Semantic Intent Alignment)
    q_words = set(re.findall(r"\w+", q_lower))
    ref_words = set(re.findall(r"\w+", ref_lower)) if ref_lower else set()
    ans_words = set(re.findall(r"\w+", ans_lower))

    # Bỏ stop words
    vietnamese_stopwords = {
        "là", "của", "và", "có", "được", "cho", "trong", "để", "với", "các", "những",
        "thì", "này", "khi", "lại", "ra", "vào", "ở", "nếu", "sẽ", "đã", "đang", "cần",
        "nên", "thường", "theo", "sau", "từ", "lên", "xuống", "như", "một", "bị", "do",
        "gì", "thế", "nào", "sao", "làm"
    }
    content_q = {w for w in q_words if w not in vietnamese_stopwords and len(w) > 1}
    content_ref = {w for w in ref_words if w not in vietnamese_stopwords and len(w) > 1}

    # Tỷ lệ bao phủ câu hỏi
    q_coverage = len(content_q.intersection(ans_words)) / len(content_q) if content_q else 1.0
    # Tỷ lệ bao phủ reference
    ref_coverage = len(content_ref.intersection(ans_words)) / len(content_ref) if content_ref else 1.0

    if ref_coverage >= 0.70 and q_coverage >= 0.60:
        score = 5
        rationale = "Trả lời xuất sắc, bao hàm đầy đủ luận điểm của tài liệu tham chiếu."
    elif ref_coverage >= 0.50 and q_coverage >= 0.50:
        score = 4
        rationale = "Trả lời tốt, truyền tải đúng ý chính và thông tin hành động."
    elif ref_coverage >= 0.30 or q_coverage >= 0.40:
        score = 3
        rationale = "Đạt ngưỡng: Đúng một phần, còn thiếu một số bước hoặc chi tiết bổ trợ."
    elif ref_coverage >= 0.15:
        score = 2
        rationale = "Kém: Trả lời sơ sài hoặc chưa tập trung vào câu hỏi."
    else:
        score = 1
        rationale = "Không đạt: Lạc đề hoặc không giải quyết được thắc mắc."

    normalized = (score - 1) / 4.0  # Chuyển về thang 0.0 - 1.0

    return {
        "rubric_score": score,
        "normalized_score": round(normalized, 4),
        "rationale": rationale
    }


class ProductionEvaluator:
    """
    Bộ đánh giá cấp Production toàn diện theo kiến trúc của Lamhot Siagian.
    """

    def __init__(self, quality_gate_config: Optional[Dict[str, float]] = None):
        # Thiết lập ngưỡng Quality Gate mặc định (Chapter 8 & Appendix E.5)
        self.quality_gates = quality_gate_config or {
            "hit_at_3_min": 0.85,
            "mrr_min": 0.70,
            "ndcg_at_5_min": 0.75,
            "overall_groundedness_min": 0.85,
            "high_risk_groundedness_min": 0.90,
            "max_critical_hallucinations": 0,
            "abstention_accuracy_min": 0.80,
            "relevance_rubric_mean_min": 3.8
        }

    def evaluate_single_sample(
        self,
        sample: Dict[str, Any],
        retrieved_contexts: List[Dict[str, Any]],
        generated_answer: str,
        latencies: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Đánh giá độc lập 1 ca kiểm thử: Retrieval + Generation + Claim Groundedness.
        """
        case_id = sample.get("case_id", "unknown")
        user_input = sample.get("user_input", "")
        reference_answer = sample.get("reference_answer", sample.get("reference", ""))
        gold_evidence = sample.get("gold_evidence", [])
        intent_family = sample.get("intent_family", "general")
        risk_tier = sample.get("risk_tier", "medium")
        is_abstention = sample.get("is_abstention", False)

        # 1. Đo lường Retrieval Ranking Metrics
        retrieval_metrics = calculate_retrieval_ranking_metrics(
            retrieved_items=retrieved_contexts,
            gold_evidence_list=gold_evidence
        )

        # 2. Đo lường Claim Groundedness
        context_texts = [
            c.get("content", c.get("text", str(c))) if isinstance(c, dict)
            else str(c)
            for c in retrieved_contexts
        ]
        claim_audit = evaluate_claim_groundedness(
            answer=generated_answer,
            retrieved_contexts=context_texts
        )

        # 3. Đo lường Relevance Rubric
        relevance_audit = grade_answer_relevance_rubric(
            question=user_input,
            answer=generated_answer,
            reference_answer=reference_answer,
            is_abstention=is_abstention
        )

        return {
            "case_id": case_id,
            "user_input": user_input,
            "intent_family": intent_family,
            "risk_tier": risk_tier,
            "is_abstention": is_abstention,
            "generated_answer": generated_answer,
            "reference_answer": reference_answer,
            "retrieval_metrics": retrieval_metrics,
            "claim_audit": claim_audit,
            "relevance_audit": relevance_audit,
            "latencies": latencies
        }

    def aggregate_and_verify(
        self,
        evaluated_samples: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Gom cụm báo cáo (Bucketed Aggregation) và kiểm định Quality Gates.
        """
        total_cases = len(evaluated_samples)
        if total_cases == 0:
            return {"error": "Không có mẫu dữ liệu nào để tổng hợp."}

        # 1. Thống kê tổng thể Retrieval
        mean_hit1 = sum(s["retrieval_metrics"]["hit_at_1"] for s in evaluated_samples) / total_cases
        mean_hit3 = sum(s["retrieval_metrics"]["hit_at_3"] for s in evaluated_samples) / total_cases
        mean_hit5 = sum(s["retrieval_metrics"]["hit_at_5"] for s in evaluated_samples) / total_cases
        mean_mrr = sum(s["retrieval_metrics"]["mrr"] for s in evaluated_samples) / total_cases
        mean_ndcg5 = sum(s["retrieval_metrics"]["ndcg_at_5"] for s in evaluated_samples) / total_cases
        mean_prec3 = sum(s["retrieval_metrics"]["precision_at_3"] for s in evaluated_samples) / total_cases
        mean_recall3 = sum(s["retrieval_metrics"]["recall_at_3"] for s in evaluated_samples) / total_cases

        # 2. Thống kê tổng thể Generation
        groundedness_scores = [s["claim_audit"]["groundedness_score"] for s in evaluated_samples]
        rubric_scores = [s["relevance_audit"]["rubric_score"] for s in evaluated_samples]
        rubric_normalized = [s["relevance_audit"]["normalized_score"] for s in evaluated_samples]

        total_claims = sum(s["claim_audit"]["total_claims"] for s in evaluated_samples)
        total_supported = sum(s["claim_audit"]["supported_claims"] for s in evaluated_samples)
        total_unsupported = sum(s["claim_audit"]["unsupported_claims"] for s in evaluated_samples)
        total_contradicted = sum(s["claim_audit"]["contradicted_claims"] for s in evaluated_samples)
        critical_errors_count = sum(1 for s in evaluated_samples if s["claim_audit"]["has_critical_error"])

        mean_groundedness = round(sum(groundedness_scores) / total_cases, 4)
        mean_rubric = round(sum(rubric_scores) / total_cases, 2)
        mean_rubric_norm = round(sum(rubric_normalized) / total_cases, 4)

        # 3. Phân tầng theo Risk Tier (High vs Medium)
        risk_buckets = {"high": [], "medium": []}
        for s in evaluated_samples:
            tier = s.get("risk_tier", "medium")
            risk_buckets[tier].append(s)

        risk_summary = {}
        for tier, items in risk_buckets.items():
            if items:
                risk_summary[tier] = {
                    "count": len(items),
                    "hit_at_3": round(sum(it["retrieval_metrics"]["hit_at_3"] for it in items) / len(items), 4),
                    "mrr": round(sum(it["retrieval_metrics"]["mrr"] for it in items) / len(items), 4),
                    "groundedness": round(sum(it["claim_audit"]["groundedness_score"] for it in items) / len(items), 4),
                    "relevance_rubric": round(sum(it["relevance_audit"]["rubric_score"] for it in items) / len(items), 2),
                    "critical_errors": sum(1 for it in items if it["claim_audit"]["has_critical_error"])
                }

        # 4. Phân tầng theo Intent Family
        intent_buckets = {}
        for s in evaluated_samples:
            intent = s.get("intent_family", "general")
            if intent not in intent_buckets:
                intent_buckets[intent] = []
            intent_buckets[intent].append(s)

        intent_summary = {}
        for intent, items in intent_buckets.items():
            intent_summary[intent] = {
                "count": len(items),
                "hit_at_3": round(sum(it["retrieval_metrics"]["hit_at_3"] for it in items) / len(items), 4),
                "mrr": round(sum(it["retrieval_metrics"]["mrr"] for it in items) / len(items), 4),
                "groundedness": round(sum(it["claim_audit"]["groundedness_score"] for it in items) / len(items), 4),
                "relevance_rubric": round(sum(it["relevance_audit"]["rubric_score"] for it in items) / len(items), 2)
            }

        # 5. Abstention Performance (Chương 6.1.3)
        abstention_samples = [s for s in evaluated_samples if s.get("is_abstention")]
        abstention_accuracy = 0.0
        if abstention_samples:
            correct_abstains = sum(1 for s in abstention_samples if s["relevance_audit"]["rubric_score"] >= 4)
            abstention_accuracy = round(correct_abstains / len(abstention_samples), 4)

        # 6. Quality Gates Verification (Appendix E.5)
        gates = self.quality_gates
        high_risk_groundedness = risk_summary.get("high", {}).get("groundedness", 0.0)

        gate_checks = {
            "Hit@3 >= 0.85": {
                "threshold": gates["hit_at_3_min"],
                "actual": round(mean_hit3, 4),
                "passed": mean_hit3 >= gates["hit_at_3_min"]
            },
            "MRR >= 0.70": {
                "threshold": gates["mrr_min"],
                "actual": round(mean_mrr, 4),
                "passed": mean_mrr >= gates["mrr_min"]
            },
            "NDCG@5 >= 0.75": {
                "threshold": gates["ndcg_at_5_min"],
                "actual": round(mean_ndcg5, 4),
                "passed": mean_ndcg5 >= gates["ndcg_at_5_min"]
            },
            "Overall Groundedness >= 0.85": {
                "threshold": gates["overall_groundedness_min"],
                "actual": mean_groundedness,
                "passed": mean_groundedness >= gates["overall_groundedness_min"]
            },
            "High-Risk Groundedness >= 0.90": {
                "threshold": gates["high_risk_groundedness_min"],
                "actual": high_risk_groundedness,
                "passed": high_risk_groundedness >= gates["high_risk_groundedness_min"]
            },
            "Critical Hallucinations == 0": {
                "threshold": gates["max_critical_hallucinations"],
                "actual": critical_errors_count,
                "passed": critical_errors_count <= gates["max_critical_hallucinations"]
            },
            "Abstention Accuracy >= 0.80": {
                "threshold": gates["abstention_accuracy_min"],
                "actual": abstention_accuracy,
                "passed": abstention_accuracy >= gates["abstention_accuracy_min"]
            },
            "Relevance Rubric >= 3.8": {
                "threshold": gates["relevance_rubric_mean_min"],
                "actual": mean_rubric,
                "passed": mean_rubric >= gates["relevance_rubric_mean_min"]
            }
        }

        all_gates_passed = all(g["passed"] for g in gate_checks.values())

        return {
            "total_cases": total_cases,
            "overall_retrieval": {
                "hit_at_1": round(mean_hit1, 4),
                "hit_at_3": round(mean_hit3, 4),
                "hit_at_5": round(mean_hit5, 4),
                "precision_at_3": round(mean_prec3, 4),
                "recall_at_3": round(mean_recall3, 4),
                "mrr": round(mean_mrr, 4),
                "ndcg_at_5": round(mean_ndcg5, 4)
            },
            "overall_generation": {
                "mean_groundedness": mean_groundedness,
                "mean_rubric_score_5pt": mean_rubric,
                "mean_rubric_normalized": mean_rubric_norm,
                "total_claims": total_claims,
                "supported_claims": total_supported,
                "unsupported_claims": total_unsupported,
                "contradicted_claims": total_contradicted,
                "critical_errors_count": critical_errors_count,
                "abstention_accuracy": abstention_accuracy
            },
            "risk_tier_breakdown": risk_summary,
            "intent_family_breakdown": intent_summary,
            "quality_gates": {
                "verdict": "PASS" if all_gates_passed else "FAIL_CONDITIONAL",
                "checks": gate_checks
            },
            "individual_cases": evaluated_samples
        }
