import os
from dotenv import load_dotenv
from llama_index.llms.openai_like import OpenAILike
from llama_index.core import Settings
from llama_index.core.types import PydanticProgramMode

load_dotenv()

# =====================================================================
# 1. CẤU HÌNH LLM (GEMINI QUA 9ROUTER / OPENAI-COMPATIBLE)
# =====================================================================
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-3.8-flash-high")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://127.0.0.1:8317/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")

# =====================================================================
# 2. CẤU HÌNH EMBEDDING (OPENAI / CUSTOM PROXY VILAO)
# =====================================================================
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "https://api.vilao.ai/v1")
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "")


def get_default_llm():
    """
    Khởi tạo mô hình LLM tương thích OpenAI (Gemini chạy qua 9router custom).
    """
    llm = OpenAILike(
        model=LLM_MODEL,
        api_base=LLM_BASE_URL,
        api_key=LLM_API_KEY,
        is_chat_model=True,
        is_function_calling_model=False,
        pydantic_program_mode=PydanticProgramMode.LLM,
        context_window=32768,
        timeout=60.0,
        max_retries=3,
    )
    Settings.llm = llm
    return llm
