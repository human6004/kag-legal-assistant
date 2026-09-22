import os
from pathlib import Path
import chromadb
from dotenv import load_dotenv
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import StorageContext

load_dotenv()

DEFAULT_CHROMA_PATH = os.getenv("CHROMA_DB_PATH", "./database/chroma_db")
DEFAULT_COLLECTION = os.getenv("CHROMA_COLLECTION", "legal_corpus")


class ChromaStore:

    def __init__(
        self,
        db_path: str = DEFAULT_CHROMA_PATH,
        collection_name: str = DEFAULT_COLLECTION,
        recreate: bool = False
    ):
        target_path = Path(db_path)
        target_path.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(target_path))

        if recreate:
            try:
                self.client.delete_collection(name=collection_name)
                print(f"[CHROMA] Đã xóa collection cũ '{collection_name}' để tạo mới theo cấu hình embedding hiện tại.")
            except Exception:
                pass

        self.collection = self.client.get_or_create_collection(
            name=collection_name
        )
        self.vector_store = ChromaVectorStore(
            chroma_collection=self.collection
        )

    def get_storage_context(self):
        return StorageContext.from_defaults(
            vector_store=self.vector_store
        )