"""
Retrieval Ranking Metrics Module
Tuân thủ các công thức toán học và chuẩn mực đánh giá tại Chapter 3.5
trong sách "RAG Evaluation & Testing in Production" (Lamhot Siagian, 2026).

Hỗ trợ đánh giá:
- Hit@K (Binary success at cut-off K)
- Recall@K (Coverage of gold standard context)
- Precision@K (Purity of retrieved window)
- MRR (Mean Reciprocal Rank - Rank of first relevant item)
- NDCG@K (Normalized Discounted Cumulative Gain with position penalty)
"""

import math
from typing import List, Dict, Any, Set, Optional


def compute_binary_relevance(
    retrieved_chunk: Dict[str, Any],
    gold_evidence_list: List[Dict[str, Any]],
    text_overlap_threshold: float = 0.65
) -> int:
    """
    Xác định một chunk truy xuất được có liên quan (relevant = 1) hay không (0).
    So khớp theo 2 tầng:
    1. Chunk ID / Source matching (nếu có định danh)
    2. Exact substring hoặc Jaccard character-trigram containment matching
    """
    retrieved_id = retrieved_chunk.get("chunk_id") or retrieved_chunk.get("id") or ""
    retrieved_text = (
        retrieved_chunk.get("content")
        or retrieved_chunk.get("text")
        or ""
    ).strip().lower()

    if not retrieved_text and not retrieved_id:
        return 0

    for gold in gold_evidence_list:
        gold_id = gold.get("chunk_id") or gold.get("id") or ""
        # 1. Khớp ID
        if retrieved_id and gold_id and retrieved_id == gold_id:
            return 1

        gold_text = (
            gold.get("content")
            or gold.get("text")
            or ""
        ).strip().lower()

        if not gold_text:
            continue

        # 2. Containment match (một bên chứa bên kia đáng kể)
        if gold_text in retrieved_text or retrieved_text in gold_text:
            return 1

        # 3. Trigram Jaccard similarity (bảo vệ chống biến đổi nhẹ về định dạng markdown)
        def get_trigrams(s: str) -> Set[str]:
            words = s.split()
            if len(words) < 3:
                return set(words)
            return {" ".join(words[i:i+3]) for i in range(len(words)-2)}

        gold_trigrams = get_trigrams(gold_text)
        retrieved_trigrams = get_trigrams(retrieved_text)

        if gold_trigrams and retrieved_trigrams:
            intersection = len(gold_trigrams.intersection(retrieved_trigrams))
            min_len = min(len(gold_trigrams), len(retrieved_trigrams))
            overlap_ratio = intersection / min_len if min_len > 0 else 0.0
            if overlap_ratio >= text_overlap_threshold:
                return 1

    return 0


def calculate_retrieval_ranking_metrics(
    retrieved_items: List[Dict[str, Any]],
    gold_evidence_list: List[Dict[str, Any]],
    k_list: List[int] = [1, 3, 5]
) -> Dict[str, float]:
    """
    Tính toán chi tiết các metric xếp hạng cho một query đơn lẻ.
    
    Args:
        retrieved_items: Danh sách các chunk/node được hệ thống trả về theo thứ tự rank.
        gold_evidence_list: Danh sách các chunk chuẩn (gold context) thực tế.
        k_list: Các ngưỡng cắt K để tính metric.
    
    Returns:
        Dict chứa Hit@K, Recall@K, Precision@K, MRR, NDCG@K
    """
    num_gold = len(gold_evidence_list)
    if num_gold == 0:
        # Trường hợp Out-of-domain / Negative Query: nếu hệ thống không retrieve rác thì tốt
        return {
            "hit_at_1": 1.0 if len(retrieved_items) == 0 else 0.0,
            "hit_at_3": 1.0 if len(retrieved_items) == 0 else 0.0,
            "hit_at_5": 1.0 if len(retrieved_items) == 0 else 0.0,
            "recall_at_1": 1.0 if len(retrieved_items) == 0 else 0.0,
            "recall_at_3": 1.0 if len(retrieved_items) == 0 else 0.0,
            "recall_at_5": 1.0 if len(retrieved_items) == 0 else 0.0,
            "precision_at_1": 1.0 if len(retrieved_items) == 0 else 0.0,
            "precision_at_3": 1.0 if len(retrieved_items) == 0 else 0.0,
            "precision_at_5": 1.0 if len(retrieved_items) == 0 else 0.0,
            "mrr": 1.0 if len(retrieved_items) == 0 else 0.0,
            "ndcg_at_5": 1.0 if len(retrieved_items) == 0 else 0.0,
        }

    # Đánh giá binary relevance cho từng vị trí rank (1-indexed)
    relevance_scores = []
    for item in retrieved_items:
        rel = compute_binary_relevance(item, gold_evidence_list)
        relevance_scores.append(rel)

    results = {}

    # 1. MRR (Mean Reciprocal Rank)
    reciprocal_rank = 0.0
    for idx, rel in enumerate(relevance_scores):
        if rel == 1:
            reciprocal_rank = 1.0 / (idx + 1)
            break
    results["mrr"] = round(reciprocal_rank, 4)

    # 2. Hit@K, Precision@K, Recall@K
    for k in k_list:
        sub_rel = relevance_scores[:k]
        hits = sum(sub_rel)

        # Hit@K: Có ít nhất 1 chunk liên quan trong top K
        results[f"hit_at_{k}"] = 1.0 if hits > 0 else 0.0

        # Precision@K: Tỷ lệ chunk liên quan trên tổng số K chunk trả về
        actual_k = len(sub_rel) if len(sub_rel) > 0 else k
        results[f"precision_at_{k}"] = round(hits / actual_k, 4) if actual_k > 0 else 0.0

        # Recall@K: Tỷ lệ chunk liên quan tìm được trên tổng số gold evidence
        results[f"recall_at_{k}"] = round(min(hits, num_gold) / num_gold, 4)

    # 3. NDCG@K (Discounted Cumulative Gain)
    for k in [3, 5]:
        sub_rel = relevance_scores[:k]
        dcg = 0.0
        for i, rel in enumerate(sub_rel):
            if rel > 0:
                dcg += (2**rel - 1) / math.log2(i + 2)  # log2(rank + 1), vì i bắt đầu từ 0 nên log2(i+2)

        # Ideal DCG (tất cả các gold chunk đều đứng ở đầu bảng)
        ideal_hits = min(k, num_gold)
        idcg = 0.0
        for i in range(ideal_hits):
            idcg += 1.0 / math.log2(i + 2)

        ndcg = (dcg / idcg) if idcg > 0 else 0.0
        results[f"ndcg_at_{k}"] = round(min(1.0, ndcg), 4)

    return results
