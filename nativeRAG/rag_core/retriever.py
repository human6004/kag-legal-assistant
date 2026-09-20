from pathlib import Path
from typing import List, Dict, Any, Tuple

from core.config import settings
from rag_core.bm25 import BM25OkapiIndex


class HybridLegalRetriever:
    """
    Retriever lai ghép (Hybrid Retrieval) kết hợp:
    1. Dense Vector Search (ChromaDB + OpenAI Embeddings)
    2. Sparse Keyword Search (BM25 Okapi)
    Áp dụng thuật toán Reciprocal Rank Fusion (RRF) để xếp hạng tối ưu.
    """

    def __init__(self, top_k: int = 4, rrf_k: int = 60):
        self.top_k = top_k
        self.rrf_k = rrf_k
        self.bm25_index: BM25OkapiIndex | None = None
        self.vector_store = None
        self._load_indices()

    def _load_indices(self):
        # 1. Nạp BM25 index
        bm25_path = Path(settings.BM25_PERSIST_DIR) / "bm25.pkl"
        if bm25_path.exists():
            try:
                self.bm25_index = BM25OkapiIndex.load(bm25_path)
            except Exception as e:
                print(f"Cảnh báo: Không thể nạp BM25 index: {e}")

        # 2. Nạp ChromaDB (nếu có API Key và thư mục đã tồn tại)
        chroma_dir = Path(settings.CHROMA_PERSIST_DIR)
        embedding_key = settings.get_embedding_api_key()
        if chroma_dir.exists() and embedding_key:
            try:
                from langchain_openai import OpenAIEmbeddings
                try:
                    from langchain_chroma import Chroma
                except ImportError:
                    from langchain_community.vectorstores import Chroma

                if not embedding_key.startswith("sk-") and len(embedding_key) > 20:
                    embedding_key = f"sk-{embedding_key}"

                model_name = settings.EMBEDDING_MODEL
                if model_name.startswith("dg/"):
                    model_name = model_name.replace("dg/", "")

                kwargs = {
                    "model": model_name,
                    "api_key": embedding_key,
                }
                base_url = settings.get_embedding_base_url()
                if base_url:
                    kwargs["base_url"] = base_url

                embeddings = OpenAIEmbeddings(**kwargs)
                self.vector_store = Chroma(
                    collection_name="legal_ai_vietnam",
                    embedding_function=embeddings,
                    persist_directory=str(chroma_dir)
                )
            except Exception as e:
                print(f"Cảnh báo: Chưa thể kết nối ChromaDB ({e}). Đang dùng chế độ BM25.")

    def search_sparse(self, query: str, top_n: int = 10) -> List[Dict[str, Any]]:
        """Truy xuất từ khóa bằng BM25"""
        if not self.bm25_index:
            return []
        scored = self.bm25_index.search(query, top_k=top_n)
        return [item[0] for item in scored]

    def search_dense(self, query: str, top_n: int = 10) -> List[Dict[str, Any]]:
        """Truy xuất ngữ nghĩa bằng ChromaDB"""
        if self.vector_store is None:
            return []
        try:
            docs = self.vector_store.similarity_search(query, k=top_n)
            return [{"content": d.page_content, "metadata": d.metadata} for d in docs]
        except Exception as e:
            print(f"Lỗi truy xuất dense vector: {e}")
            return []

    def retrieve(self, query: str, top_k: int | None = None) -> List[Dict[str, Any]]:
        """
        Truy xuất kết hợp (Hybrid Search) bằng RRF:
        RRF_score(d) = sum(1 / (k + rank))
        """
        k = top_k or self.top_k
        fetch_n = max(k * 3, 10)

        sparse_docs = self.search_sparse(query, top_n=fetch_n)
        dense_docs = self.search_dense(query, top_n=fetch_n)

        # Nếu chỉ có 1 trong 2 nguồn hoạt động
        if not dense_docs and sparse_docs:
            return sparse_docs[:k]
        if not sparse_docs and dense_docs:
            return dense_docs[:k]
        if not sparse_docs and not dense_docs:
            return []

        # RRF Fusion
        doc_map: Dict[str, Dict[str, Any]] = {}
        rrf_scores: Dict[str, float] = {}

        def get_doc_key(doc: Dict[str, Any]) -> str:
            meta = doc.get("metadata", {})
            return meta.get("chunk_id") or doc["content"][:100]

        # Tính điểm BM25
        for rank, doc in enumerate(sparse_docs, start=1):
            key = get_doc_key(doc)
            doc_map[key] = doc
            rrf_scores[key] = rrf_scores.get(key, 0.0) + (1.0 / (self.rrf_k + rank))

        # Tính điểm Dense
        for rank, doc in enumerate(dense_docs, start=1):
            key = get_doc_key(doc)
            doc_map[key] = doc
            rrf_scores[key] = rrf_scores.get(key, 0.0) + (1.0 / (self.rrf_k + rank))

        # Sắp xếp theo tổng điểm RRF
        sorted_keys = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
        results = [doc_map[k_id] for k_id in sorted_keys[:k]]
        return results
