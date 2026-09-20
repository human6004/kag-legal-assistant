import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


# Đường dẫn gốc của project
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # =========================================================================
    # 1. CẤU HÌNH LLM CHAT (DÙNG GEMINI QUA 9ROUTER THEO CHUẨN OPENAI)
    # =========================================================================
    LLM_API_KEY: str = Field(default="", description="API Key của 9router cho Gemini LLM")
    LLM_BASE_URL: str | None = Field(default=None, description="Base URL của 9router (vd: https://api.9router.../v1)")
    LLM_MODEL: str = Field(default="gemini-2.5-flash", description="Tên model Gemini trên 9router")

    # =========================================================================
    # 2. CẤU HÌNH EMBEDDING (DÙNG OPENAI CHÍNH HÃNG HOẶC CUSTOM THEO CHUẨN OPENAI)
    # =========================================================================
    EMBEDDING_API_KEY: str = Field(default="", description="API Key của OpenAI cho Embedding")
    EMBEDDING_BASE_URL: str | None = Field(default=None, description="Base URL của OpenAI (để trống nếu dùng OpenAI mặc định)")
    EMBEDDING_MODEL: str = Field(default="text-embedding-3-small", description="Tên model embedding OpenAI")

    # Hỗ trợ tương thích ngược nếu người dùng điền tên OPENAI_API_KEY cũ
    OPENAI_API_KEY: str | None = None
    OPENAI_BASE_URL: str | None = None

    # Cấu hình đường dẫn dữ liệu & Vector DB
    KNOWLEDGE_BASE_DIR: Path = Field(default=BASE_DIR / "knowledge_base", description="Thư mục chứa văn bản Markdown")
    CHROMA_PERSIST_DIR: Path = Field(default=BASE_DIR / "data" / "chroma_db", description="Thư mục lưu trữ ChromaDB")
    BM25_PERSIST_DIR: Path = Field(default=BASE_DIR / "data" / "bm25_index", description="Thư mục lưu BM25 index")

    # Tham số RAG
    CHUNK_SIZE: int = Field(default=1000, description="Kích thước tối đa của một chunk (ký tự)")
    CHUNK_OVERLAP: int = Field(default=150, description="Độ gối đầu giữa các chunk con")
    TOP_K: int = Field(default=4, description="Số lượng context trả về cho LLM")
    TEMPERATURE: float = Field(default=0.1, description="Độ sáng tạo của LLM (thấp để chống ảo giác)")

    def get_llm_api_key(self) -> str:
        return self.LLM_API_KEY or self.OPENAI_API_KEY or ""

    def get_llm_base_url(self) -> str | None:
        return self.LLM_BASE_URL

    def get_embedding_api_key(self) -> str:
        return self.EMBEDDING_API_KEY or self.OPENAI_API_KEY or ""

    def get_embedding_base_url(self) -> str | None:
        return self.EMBEDDING_BASE_URL or self.OPENAI_BASE_URL

    class Config:
        env_file = BASE_DIR / ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
