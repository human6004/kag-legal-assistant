import chromadb
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import VectorStoreIndex, Settings
from llama_index.embeddings.openai_like import OpenAILikeEmbedding
import os
from dotenv import load_dotenv

load_dotenv()


class ChromaStore:
    """Dùng cho quá trình build index"""

    def __init__(
        self,
        db_path: str = "./database/chroma_db",
        collection_name: str = "mai_vang"
    ):
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection(name=collection_name)
        self.vector_store = ChromaVectorStore(chroma_collection=self.collection)

    def get_storage_context(self):
        return StorageContext.from_defaults(vector_store=self.vector_store)


def load_vector_index():
    """Load Vector Index từ ChromaDB (dùng cho API)"""
    client = chromadb.PersistentClient(path="./database/chroma_db")
    collection = client.get_or_create_collection(name="mai_vang")   # ← đúng tên collection bạn dùng

    vector_store = ChromaVectorStore(chroma_collection=collection)

    # Khởi tạo lại embedding model (bắt buộc phải làm)
    embed_model = OpenAILikeEmbedding(
        model_name="nvidia/nv-embed-v1",
        api_base="https://integrate.api.nvidia.com/v1",
        api_key=os.getenv("NVIDIA_API_KEY2"),
        embed_batch_size=8,
        additional_kwargs={
            "extra_body": {
                "input_type": "query",
                "truncate": "END",
            }
        },
    )
    Settings.embed_model = embed_model

    # Load vector index
    index = VectorStoreIndex.from_vector_store(vector_store)
    return index