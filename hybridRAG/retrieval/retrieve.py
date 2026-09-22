from typing import Optional, Tuple, List, Any
from retrieval.rewrite.query_rewrite import QueryRewrite
from retrieval.rewrite.hyde import HyDE
from retrieval.search.vector_search import VectorSearch
from retrieval.search.graph_search import GraphSearch
from retrieval.search.bm25_search import BM25Search
from retrieval.search.hybrid_search import HybridSearch
from retrieval.reranker.bge_reranker import CrossEncoderReranker
from retrieval.metrics.latency_tracker import LatencyTracker


class Retriever:

    def __init__(
        self,
        llm,
        vector_index=None,
        graph_index=None,
        bm25_search: Optional[BM25Search] = None,
        top_k: int = 5,
        use_hyde: bool = True
    ):
        self.rewriter = QueryRewrite(llm)
        self.use_hyde = use_hyde
        if use_hyde:
            self.hyde = HyDE(llm)

        self.vector_search = (
            VectorSearch(vector_index=vector_index, top_k=top_k)
            if vector_index is not None
            else None
        )

        self.graph_search = (
            GraphSearch(graph_index=graph_index, top_k=top_k)
            if graph_index is not None
            else None
        )

        # Tự động nạp BM25 từ cache nếu chưa truyền vào
        if bm25_search is not None:
            self.bm25_search = bm25_search
        else:
            bm25 = BM25Search(top_k=top_k)
            if bm25.corpus_size > 0:
                self.bm25_search = bm25
            else:
                self.bm25_search = None

        self.hybrid = HybridSearch()
        self.reranker = CrossEncoderReranker(top_k=top_k)
        self.top_k = top_k

    def retrieve(self, question: str, tracker: Optional[LatencyTracker] = None):
        """
        Truy xuất ngữ cảnh lai chuẩn HybridRAG:
        1. Query Rewrite (Chuẩn hóa từ ngữ, viết tắt)
        2. HyDE (Sinh giả định quy phạm pháp luật)
        3. Dense Vector Search (ChromaDB)
        4. Sparse BM25 Search (Từ khóa, số điều, mã luật)
        5. Graph Search (Neo4j Property Graph)
        6. Hybrid RRF Fusion (Reciprocal Rank Fusion 3 kênh)
        7. Cross-Encoder Reranking (BGE Reranker v2 m3)
        """
        # 1. Query Rewrite
        if tracker:
            with tracker.track("query_rewrite"):
                rewritten_question = self.rewriter.rewrite(question)
        else:
            rewritten_question = self.rewriter.rewrite(question)

        # 2. HyDE Generation
        hyde_query = rewritten_question
        if self.use_hyde and hasattr(self, "hyde"):
            if tracker:
                with tracker.track("hyde_generation"):
                    hyde_query = self.hyde.generate(rewritten_question)
            else:
                hyde_query = self.hyde.generate(rewritten_question)

        # 3. Dense Vector Search (Dùng HyDE query cho semantic sâu)
        vector_results = []
        if self.vector_search is not None:
            try:
                if tracker:
                    with tracker.track("vector_search"):
                        vector_results = self.vector_search.search(hyde_query)
                else:
                    vector_results = self.vector_search.search(hyde_query)
            except Exception as e:
                print(f"[CẢNH BÁO] Vector search gặp lỗi ({e}). Bỏ qua kênh vector.")
                vector_results = []

        # 4. Sparse BM25 Search (Dùng rewritten_question và câu hỏi gốc để khớp chính xác từ khóa, số điều)
        bm25_results = []
        if self.bm25_search is not None:
            if tracker:
                with tracker.track("bm25_search"):
                    # Kết hợp tìm kiếm với cả rewritten question và câu hỏi gốc
                    bm25_results = self.bm25_search.search(rewritten_question, top_k=self.top_k)
            else:
                bm25_results = self.bm25_search.search(rewritten_question, top_k=self.top_k)

        # 5. Graph Search (Dùng rewritten_question để tìm kiếm thực thể và quan hệ)
        graph_results = []
        if self.graph_search is not None:
            try:
                if tracker:
                    with tracker.track("graph_search"):
                        graph_results = self.graph_search.search(rewritten_question)
                else:
                    graph_results = self.graph_search.search(rewritten_question)
            except Exception as e:
                print(f"[CẢNH BÁO] Graph search gặp lỗi hoặc graph chưa được lập chỉ mục: {e}")
                graph_results = []

        # 6. Hybrid RRF Fusion (Reciprocal Rank Fusion 3 kênh)
        if tracker:
            with tracker.track("hybrid_merge"):
                merged_results = self.hybrid.merge(
                    vector_results=vector_results,
                    bm25_results=bm25_results,
                    graph_results=graph_results,
                    top_k=self.top_k * 2  # Giữ gấp đôi top_k trước khi đưa vào reranker
                )
        else:
            merged_results = self.hybrid.merge(
                vector_results=vector_results,
                bm25_results=bm25_results,
                graph_results=graph_results,
                top_k=self.top_k * 2
            )

        # 7. Cross-Encoder Reranking
        print("Tái xếp hạng (Cross-Encoder Reranking)...")
        if tracker:
            with tracker.track("reranking"):
                final_results = self.reranker.rerank(rewritten_question, merged_results)
        else:
            final_results = self.reranker.rerank(rewritten_question, merged_results)

        return final_results

    def retrieve_with_latency(self, question: str) -> Tuple[List, LatencyTracker]:
        """Truy xuất kèm trả về tracker chứa thời gian chi tiết của từng bước."""
        tracker = LatencyTracker()
        results = self.retrieve(question, tracker=tracker)
        return results, tracker