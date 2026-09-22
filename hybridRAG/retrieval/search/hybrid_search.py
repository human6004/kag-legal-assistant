from typing import List, Dict, Any, Optional
from llama_index.core.schema import NodeWithScore


class HybridSearch:
    """
    Module kết hợp đa nguồn tìm kiếm (Dense Vector, Sparse BM25, Knowledge Graph)
    sử dụng thuật toán chuẩn công nghiệp Reciprocal Rank Fusion (RRF).
    """

    def __init__(self, k: int = 60):
        """
        :param k: Hằng số làm mượt RRF (thông thường là 60 theo chuẩn IR).
        """
        self.k = k

    @staticmethod
    def _extract_node_id(item: Any) -> str:
        """Trích xuất ID duy nhất của node."""
        if hasattr(item, "node") and hasattr(item.node, "node_id"):
            return str(item.node.node_id)
        if hasattr(item, "node_id"):
            return str(item.node_id)
        if hasattr(item, "id"):
            return str(item.id)
        # Fallback theo hash nội dung
        if hasattr(item, "node") and hasattr(item.node, "get_content"):
            return str(hash(item.node.get_content()))
        if hasattr(item, "text"):
            return str(hash(item.text))
        return str(hash(str(item)))

    def rrf_fuse(
        self,
        ranked_lists: Dict[str, List[Any]],
        weights: Optional[Dict[str, float]] = None,
        top_k: Optional[int] = None
    ) -> List[NodeWithScore]:
        """
        Hợp nhất nhiều danh sách kết quả theo giải thuật Reciprocal Rank Fusion.

        :param ranked_lists: Dict các danh sách kết quả, ví dụ:
                             {"vector": vector_results, "bm25": bm25_results, "graph": graph_results}
        :param weights: Trọng số tương ứng cho mỗi nguồn (mặc định 1.0 cho tất cả).
        :param top_k: Số lượng kết quả cao nhất cần lấy.
        :return: Danh sách NodeWithScore đã sắp xếp giảm dần theo điểm RRF.
        """
        if weights is None:
            weights = {source: 1.0 for source in ranked_lists.keys()}

        rrf_scores: Dict[str, float] = {}
        node_map: Dict[str, Any] = {}

        for source_name, results in ranked_lists.items():
            if not results:
                continue

            weight = weights.get(source_name, 1.0)

            for rank_idx, item in enumerate(results, start=1):
                node_id = self._extract_node_id(item)

                if node_id not in node_map:
                    node_map[node_id] = item

                # Công thức RRF: w / (k + rank)
                contribution = weight * (1.0 / (self.k + rank_idx))
                rrf_scores[node_id] = rrf_scores.get(node_id, 0.0) + contribution

        # Sắp xếp các node theo điểm RRF giảm dần
        sorted_nodes = sorted(
            rrf_scores.keys(),
            key=lambda nid: rrf_scores[nid],
            reverse=True
        )

        final_results: List[NodeWithScore] = []
        for nid in sorted_nodes:
            raw_item = node_map[nid]
            score = float(rrf_scores[nid])

            if isinstance(raw_item, NodeWithScore):
                final_results.append(
                    NodeWithScore(node=raw_item.node, score=score)
                )
            elif hasattr(raw_item, "node"):
                final_results.append(
                    NodeWithScore(node=raw_item.node, score=score)
                )
            else:
                final_results.append(
                    NodeWithScore(node=raw_item, score=score)
                )

        if top_k is not None:
            final_results = final_results[:top_k]

        return final_results

    def merge(
        self,
        vector_results: List[Any],
        graph_results: Optional[List[Any]] = None,
        bm25_results: Optional[List[Any]] = None,
        weights: Optional[Dict[str, float]] = None,
        top_k: Optional[int] = None
    ) -> List[NodeWithScore]:
        """
        Hàm merge tương thích ngược và mở rộng hỗ trợ 3 kênh (Vector, BM25, Graph).
        Áp dụng thuật toán Reciprocal Rank Fusion (RRF).
        """
        ranked_lists: Dict[str, List[Any]] = {}

        if vector_results:
            ranked_lists["vector"] = vector_results
        if bm25_results:
            ranked_lists["bm25"] = bm25_results
        if graph_results:
            ranked_lists["graph"] = graph_results

        if not ranked_lists:
            return []

        # Trọng số mặc định tối ưu cho Legal RAG:
        # BM25 cực kỳ quan trọng cho số hiệu/điều luật, Vector tốt cho ngữ nghĩa
        if weights is None:
            weights = {
                "bm25": 1.2,
                "vector": 1.0,
                "graph": 0.8
            }

        return self.rrf_fuse(ranked_lists, weights=weights, top_k=top_k)