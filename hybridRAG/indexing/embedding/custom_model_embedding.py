import os
from dotenv import load_dotenv
from llama_index.core import Settings
from llama_index.embeddings.openai import OpenAIEmbedding

load_dotenv()


class CustomModelEmbedding:
    """
    Wrapper mô hình Embedding dùng OpenAI chính hãng hoặc OpenAI-compatible proxy (vilao).
    Cấu hình linh hoạt qua:
    - EMBEDDING_MODEL: tên model (vd: text-embedding-3-large, text-embedding-3-small)
    - EMBEDDING_API_KEY: API key
    - EMBEDDING_BASE_URL: Base URL của endpoint
    - EMBED_BATCH_SIZE: số lượng chunk gửi mỗi lần (mặc định: 50)
    """

    def __init__(
        self,
        model_name: str | None = None,
        api_key: str | None = None,
        api_base: str | None = None,
        embed_batch_size: int = 50,
    ):
        model = model_name or os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
        key = api_key or os.getenv("EMBEDDING_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
        base = api_base or os.getenv("EMBEDDING_BASE_URL") or os.getenv("OPENAI_BASE_URL")
        batch_size = int(os.getenv("EMBED_BATCH_SIZE", str(embed_batch_size)))

        kwargs = {
            "model_name": model,
            "api_key": key,
            "embed_batch_size": batch_size,
            "timeout": 60.0,
        }
        if base:
            kwargs["api_base"] = base

        self.embed_model = OpenAIEmbedding(**kwargs)
        Settings.embed_model = self.embed_model

    def get_model(self):
        Settings.embed_model = self.embed_model
        return self.embed_model


# Alias tương thích ngược
NVIDIAEmbeddingWrapper = CustomModelEmbedding
OpenAIEmbeddingWrapper = CustomModelEmbedding