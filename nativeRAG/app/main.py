from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import json

from core.config import settings
from rag_core.engine import LegalRAGEngine
from rag_core.retriever import HybridLegalRetriever


app = FastAPI(
    title="Vietnam AI & Cyber Law RAG API",
    description="Hệ thống Trợ lý Tra cứu Pháp luật AI & An ninh mạng Việt Nam (OpenAI Compatible)",
    version="2.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Khởi tạo RAG Engine
rag_engine = LegalRAGEngine()


# Schemas
class ChatRequest(BaseModel):
    question: str = Field(..., description="Câu hỏi hoặc yêu cầu tra cứu pháp luật", example="Dữ liệu cá nhân nhạy cảm gồm những gì?")
    top_k: Optional[int] = Field(default=None, description="Số lượng context trả về")


class CitationItem(BaseModel):
    doc_title: str
    doc_code: str
    status: str
    chapter: str
    article: str
    source: str
    preview: str


class ChatResponse(BaseModel):
    question: str
    answer: str
    citations: List[CitationItem]
    context_found: bool


class SearchRequest(BaseModel):
    query: str = Field(..., description="Từ khóa hoặc câu hỏi cần tìm kiếm")
    top_k: int = Field(default=4, description="Số lượng kết quả cần lấy")


@app.get("/")
def root():
    return {
        "service": "Vietnam AI & Cyber Law RAG API",
        "status": "running",
        "docs_url": "/docs",
        "health_url": "/api/v1/health"
    }


@app.get("/api/v1/health")
def health_check():
    """Kiểm tra trạng thái cấu hình và cơ sở dữ liệu"""
    bm25_ready = rag_engine.retriever.bm25_index is not None
    bm25_count = rag_engine.retriever.bm25_index.corpus_size if bm25_ready else 0
    chroma_ready = rag_engine.retriever.vector_store is not None

    return {
        "status": "healthy",
        "configuration": {
            "llm": {
                "role": "Chat & Generation",
                "provider": "9router (Gemini via OpenAI format)",
                "base_url": settings.get_llm_base_url() or "Chưa cấu hình LLM_BASE_URL",
                "model": settings.LLM_MODEL,
                "api_key_configured": bool(settings.get_llm_api_key())
            },
            "embedding": {
                "role": "Vector Store & Indexing",
                "provider": "OpenAI (via OpenAI format)",
                "base_url": settings.get_embedding_base_url() or "default (https://api.openai.com/v1)",
                "model": settings.EMBEDDING_MODEL,
                "api_key_configured": bool(settings.get_embedding_api_key())
            }
        },
        "indices": {
            "bm25_ready": bm25_ready,
            "bm25_chunks_count": bm25_count,
            "chromadb_ready": chroma_ready,
        }
    }


@app.post("/api/v1/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """Truy vấn câu hỏi pháp luật (Non-streaming)"""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Câu hỏi không được để trống")

    result = rag_engine.generate(request.question)
    return result


@app.post("/api/v1/chat/stream")
def chat_stream(request: ChatRequest):
    """Truy vấn câu hỏi pháp luật theo dạng Streaming (Server-Sent Events)"""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Câu hỏi không được để trống")

    def event_stream():
        for chunk in rag_engine.generate_stream(request.question):
            # Định dạng SSE
            yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/v1/search")
def search(request: SearchRequest):
    """Endpoint tra cứu context thuần túy để đánh giá chất lượng retrieval"""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Từ khóa không được để trống")

    results = rag_engine.retriever.retrieve(request.query, top_k=request.top_k)
    return {
        "query": request.query,
        "total_results": len(results),
        "results": results
    }
