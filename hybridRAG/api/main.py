import io
import os
import sys
from typing import Optional, Dict, List, Any

if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from llm.config import get_default_llm
from llm.answer_generator import AnswerGenerator
from retrieval.retrieve import Retriever
from retrieval.metrics.latency_tracker import LatencyTracker
from retrieval.search.bm25_search import BM25Search
from database.neo4j_store import load_graph_index
from database.chroma_store import load_vector_index


# 1. Khởi tạo LLM (Gemini qua 9router OpenAI-compatible)
llm = get_default_llm()

# 2. Khởi tạo Vector Index (ChromaDB)
try:
    vector_index = load_vector_index()
    print("[INIT] Nạp Vector Index từ ChromaDB thành công.")
except Exception as e:
    print(f"[CẢNH BÁO] Không thể nạp Vector Index: {e}")
    vector_index = None

# 3. Khởi tạo Graph Index (Neo4j) với cơ chế bảo vệ (fallback an toàn nếu Neo4j offline)
try:
    graph_index = load_graph_index()
    print("[INIT] Nạp Graph Index từ Neo4j thành công.")
except Exception as e:
    print(f"[CẢNH BÁO] Neo4j chưa khởi động hoặc gặp lỗi ({e}). Bỏ qua kênh Graph, chuyển sang Vector + BM25.")
    graph_index = None

# 4. Khởi tạo BM25 Search
bm25_search = BM25Search(cache_path="./database/bm25_index.pkl")
if bm25_search.corpus_size > 0:
    print(f"[INIT] Nạp BM25 Index thành công ({bm25_search.corpus_size} chunks).")
else:
    print("[CẢNH BÁO] Chưa tìm thấy file BM25 cache. BM25 Search sẽ được xây dựng tự động khi chạy offline phase.")

# 5. Khởi tạo Retriever đa kênh
retriever = Retriever(
    llm=llm,
    vector_index=vector_index,
    graph_index=graph_index,
    bm25_search=bm25_search if bm25_search.corpus_size > 0 else None,
    top_k=5
)

# 6. Khởi tạo Answer Generator
generator = AnswerGenerator(llm=llm)


app = FastAPI(
    title="Vietnam Legal HybridRAG API",
    description="API hỏi đáp & tra cứu quy phạm pháp luật Việt Nam (An ninh mạng, Trí tuệ nhân tạo, Dữ liệu cá nhân) theo kiến trúc chuẩn HybridRAG (Dense Vector + Sparse BM25 + Knowledge Graph) tích hợp đo độ trễ và trích dẫn căn cứ pháp lý.",
    version="2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    question: str


class CitationItem(BaseModel):
    index: int
    doc_title: str
    doc_code: str
    article: str
    chapter: Optional[str] = ""
    score: Optional[float] = None
    snippet: str


class ChatResponse(BaseModel):
    answer: str
    latencies: Optional[Dict[str, float]] = None
    citations: Optional[List[CitationItem]] = None
    retrieved_contexts: Optional[List[str]] = None


@app.get("/")
def root():
    return {
        "status": "online",
        "system": "Vietnam Legal HybridRAG Assistant",
        "version": "2.0",
        "channels": {
            "dense_vector": vector_index is not None,
            "sparse_bm25": bm25_search.corpus_size > 0,
            "knowledge_graph": graph_index is not None,
        }
    }


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    tracker = LatencyTracker()

    # 1. Truy xuất ngữ cảnh đa kênh chuẩn HybridRAG
    contexts = retriever.retrieve(request.question, tracker=tracker)

    # 2. Sinh câu trả lời kèm căn cứ pháp lý
    answer = generator.generate(
        question=request.question,
        contexts=contexts,
        tracker=tracker
    )

    tracker.stop_total()
    print(tracker.summary())

    # 3. Trích xuất citations và text phục vụ frontend / kiểm tra
    raw_citations = generator.extract_sources(contexts)
    citation_items = [CitationItem(**c) for c in raw_citations]

    retrieved_texts = []
    for c in contexts:
        if hasattr(c, "node") and hasattr(c.node, "get_content"):
            retrieved_texts.append(c.node.get_content())
        elif hasattr(c, "text"):
            retrieved_texts.append(c.text)
        else:
            retrieved_texts.append(str(c))

    return ChatResponse(
        answer=answer,
        latencies=tracker.to_dict(unit="seconds"),
        citations=citation_items,
        retrieved_contexts=retrieved_texts
    )