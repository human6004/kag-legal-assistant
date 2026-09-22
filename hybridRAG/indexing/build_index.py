import os
from pathlib import Path
from ingestion.loader.load_markdown import MarkdownLoader
from ingestion.processes.clean_text import TextCleaner
from ingestion.processes.normalize import TextNormalizer

from indexing.parser.legal_parser import LegalStructureAwareParser
from indexing.embedding.custom_model_embedding import CustomModelEmbedding
from indexing.graph.graph_builder import GraphBuilder
from indexing.vector.chroma import ChromaStore
from indexing.graph.graph_store import GraphStore
from retrieval.search.bm25_search import BM25Search

from llama_index.core import Settings, VectorStoreIndex
from llm.config import get_default_llm


class BuildIndex:
    """
    Quy trình xây dựng toàn diện bộ chỉ mục đa kênh cho Legal HybridRAG:
    1. Tiền xử lý & làm sạch văn bản luật
    2. Phân tích cú pháp chuyên sâu (LegalStructureAwareParser)
    3. Xây dựng BM25 Sparse Index (BM25Search)
    4. Xây dựng Dense Vector Index (ChromaDB)
    5. Xây dựng Knowledge Graph Index (Neo4j)
    """

    def __init__(
        self,
        data_dir: str = "knowledge/markdown",
        build_graph: bool = True,
        recreate_vector_store: bool = True
    ):
        self.loader = MarkdownLoader(data_dir)
        self.cleaner = TextCleaner()
        self.normalizer = TextNormalizer()
        self.parser = LegalStructureAwareParser(max_chunk_size=1200, chunk_overlap=150)

        self.build_graph = build_graph
        try:
            self.llm = get_default_llm()
        except Exception:
            self.llm = None

        self.embed_model = CustomModelEmbedding().get_model()
        self.chroma_store = ChromaStore(recreate=recreate_vector_store)

        if self.build_graph and self.llm is not None:
            try:
                self.graph_store = GraphStore().get_store()
                self.graph_builder = GraphBuilder(
                    llm=self.llm,
                    embed_model=self.embed_model,
                    graph_store=self.graph_store
                )
            except Exception as e:
                print(f"[CẢNH BÁO] Không thể kết nối Neo4j GraphStore: {e}. Sẽ bỏ qua nhánh Graph.")
                self.graph_builder = None
        else:
            self.graph_builder = None

    def run(self):
        print("\n" + "=" * 60)
        print("1. LOAD VÀ TIỀN XỬ LÝ VĂN BẢN QUY PHẠM PHÁP LUẬT")
        print("=" * 60)
        documents = self.loader.load()
        print(f"-> Đã load thành công {len(documents)} văn bản.")

        for doc in documents:
            cleaned = self.cleaner.clean(doc.text)
            normalized = self.normalizer.normalize(cleaned)
            doc.set_content(normalized)

        print("\n" + "=" * 60)
        print("2. PHÂN TÍCH CẤU TRÚC PHÁP LUẬT & TẠO CHUNKS GIÀU METADATA")
        print("=" * 60)
        nodes = self.parser.parse_documents(documents)
        print(f"-> Tổng số Legal Nodes được tạo: {len(nodes)}")
        if nodes:
            print(f"-> Metadata mẫu node đầu tiên: {nodes[0].metadata}")

        print("\n" + "=" * 60)
        print("3. XÂY DỰNG CHỈ MỤC TỪ KHÓA BM25 (SPARSE RETRIEVAL)")
        print("=" * 60)
        bm25_search = BM25Search(nodes=nodes, cache_path="./database/bm25_index.pkl")
        print(f"-> Đã huấn luyện và lưu BM25 index ({bm25_search.corpus_size} chunks) thành công!")

        print("\n" + "=" * 60)
        print("4. XÂY DỰNG CHỈ MỤC VECTOR (DENSE RETRIEVAL - CHROMADB)")
        print("=" * 60)
        storage_context = self.chroma_store.get_storage_context()
        vector_index = VectorStoreIndex(
            nodes=nodes,
            storage_context=storage_context,
            embed_model=self.embed_model,
            show_progress=True
        )
        print("-> Đã nạp nodes vào ChromaDB thành công!")

        graph_index = None
        if self.graph_builder is not None:
            print("\n" + "=" * 60)
            print("5. XÂY DỰNG KNOWLEDGE GRAPH (NEO4J)")
            print("=" * 60)
            try:
                graph_index = self.graph_builder.build(nodes)
                print("-> Đã xây dựng Knowledge Graph thành công!")
            except Exception as e:
                print(f"[CẢNH BÁO] Lỗi khi dựng graph: {e}")
        else:
            print("\n[INFO] Bỏ qua nhánh Graph vì chưa cấu hình Neo4j hoặc LLM.")

        print("\n" + "=" * 60)
        print("HOÀN THÀNH TOÀN BỘ TIẾN TRÌNH INDEXING HYBRIDRAG PHÁP LÝ!")
        print("=" * 60)

        return vector_index, bm25_search, graph_index