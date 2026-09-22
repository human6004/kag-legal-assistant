import os
from pathlib import Path
import chromadb
from dotenv import load_dotenv
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import VectorStoreIndex, StorageContext, Settings
from indexing.embedding.custom_model_embedding import CustomModelEmbedding

load_dotenv()

DEFAULT_CHROMA_PATH = os.getenv("CHROMA_DB_PATH", "./database/chroma_db")
DEFAULT_COLLECTION = os.getenv("CHROMA_COLLECTION", "legal_corpus")


class ChromaStore:
    """Dùng cho quá trình build index"""

    def __init__(
        self,
        db_path: str = DEFAULT_CHROMA_PATH,
        collection_name: str = DEFAULT_COLLECTION
    ):
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection(name=collection_name)
        self.vector_store = ChromaVectorStore(chroma_collection=self.collection)

    def get_storage_context(self):
        return StorageContext.from_defaults(vector_store=self.vector_store)


def load_vector_index(
    db_path: str = DEFAULT_CHROMA_PATH,
    collection_name: str = DEFAULT_COLLECTION
):
    """
    Load Vector Index từ ChromaDB.
    Tự động nhận diện collection có số chiều phù hợp với Embedding Model hiện tại (OpenAI 3072 dims).
    """
    embed_model = CustomModelEmbedding().get_model()
    Settings.embed_model = embed_model

    # Kiểm tra kho dữ liệu 3150 chunks chuẩn 3072 chiều tại nativeRAG
    native_chroma = Path("../nativeRAG/data/chroma_db")
    local_chroma = Path(db_path)

    chosen_client = None
    chosen_col_name = None
    chosen_path = None

    # 1. Ưu tiên kiểm tra kho 3150 chunks nếu tồn tại
    if native_chroma.exists():
        try:
            n_client = chromadb.PersistentClient(path=str(native_chroma))
            n_cols = [c.name for c in n_client.list_collections()]
            if "legal_ai_vietnam" in n_cols:
                col = n_client.get_collection("legal_ai_vietnam")
                if col.count() > 0:
                    chosen_client = n_client
                    chosen_col_name = "legal_ai_vietnam"
                    chosen_path = str(native_chroma)
        except Exception:
            pass

    # 2. Nếu không, dùng local
    if chosen_client is None:
        local_chroma.mkdir(parents=True, exist_ok=True)
        chosen_client = chromadb.PersistentClient(path=str(local_chroma))
        existing = [c.name for c in chosen_client.list_collections()]
        chosen_col_name = collection_name if collection_name in existing else (existing[0] if existing else collection_name)
        chosen_path = str(local_chroma)

    col = chosen_client.get_or_create_collection(name=chosen_col_name)
    print(f"[CHROMA] Đã nạp thành công collection '{chosen_col_name}' ({col.count()} bản ghi) tại {chosen_path}")

    vector_store = ChromaVectorStore(chroma_collection=col)
    index = VectorStoreIndex.from_vector_store(
        vector_store=vector_store,
        embed_model=embed_model
    )
    return index