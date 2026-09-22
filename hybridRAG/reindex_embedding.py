import os
import sys
import pickle
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# Đảm bảo hiển thị tiếng Việt trên Windows
if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import chromadb
from dotenv import load_dotenv
from neo4j import GraphDatabase
from llama_index.vector_stores.chroma import ChromaVectorStore
from indexing.embedding.custom_model_embedding import CustomModelEmbedding

load_dotenv()

CACHE_PKL_FILE = PROJECT_ROOT / "metadata_nodes_final.pkl"
CHROMA_DB_PATH = PROJECT_ROOT / "database" / "chroma_db"
COLLECTION_NAME = "mai_vang"
CHECKPOINT_FILE = PROJECT_ROOT / "reindex_progress.pkl"


def embed_with_retry(embed_model, text, is_query=False, max_retries=5):
    """Tính embedding với cơ chế tự động chờ nếu gặp Rate Limit (429 ResourceExhausted)."""
    backoff = 10
    for attempt in range(max_retries):
        try:
            if is_query:
                return embed_model.get_query_embedding(text)
            else:
                return embed_model.get_text_embedding(text)
        except Exception as e:
            err_str = str(e).lower()
            if "resource_exhausted" in err_str or "429" in err_str or "quota" in err_str:
                print(f"\n[RATE-LIMIT] Gặp giới hạn quota Gemini, tự động chờ {backoff}s rồi thử lại (Lần {attempt+1}/{max_retries})...")
                time.sleep(backoff)
                backoff *= 1.5
            else:
                raise e
    raise RuntimeError(f"Vượt quá {max_retries} lần thử lại do rate limit.")


def reindex_chroma(nodes, embed_model, batch_size=10):
    print("\n" + "=" * 60)
    print("1. BẮT ĐẦU RE-INDEX CHROMADB VỚI GEMINI EMBEDDING")
    print("=" * 60)

    client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))

    # Kiểm tra tiến trình cũ
    done_ids = set()
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, "rb") as f:
            done_ids = pickle.load(f)
        print(f"[RESUME] Tìm thấy tiến trình cũ, đã nhúng xong {len(done_ids)}/{len(nodes)} nodes.")
        collection = client.get_or_create_collection(name=COLLECTION_NAME)
    else:
        try:
            client.delete_collection(name=COLLECTION_NAME)
            print(f"[CHROMA] Đã xóa collection cũ '{COLLECTION_NAME}' (để reset số chiều).")
        except Exception:
            pass
        collection = client.create_collection(name=COLLECTION_NAME)

    remaining_nodes = [n for n in nodes if n.node_id not in done_ids]
    print(f"[CHROMA] Còn lại {len(remaining_nodes)} nodes cần tính vector...")

    for i in range(0, len(remaining_nodes), batch_size):
        batch = remaining_nodes[i:i + batch_size]
        batch_ids = [n.node_id for n in batch]
        batch_texts = [n.get_content() for n in batch]
        batch_metadatas = [n.metadata for n in batch]

        # Tính embeddings từng node kèm retry backoff
        batch_embeddings = []
        for text in batch_texts:
            vec = embed_with_retry(embed_model, text, is_query=False)
            batch_embeddings.append(vec)
            time.sleep(0.3)  # Delay nhẹ để giữ dưới ngưỡng RPM

        collection.upsert(
            ids=batch_ids,
            embeddings=batch_embeddings,
            documents=batch_texts,
            metadatas=batch_metadatas
        )

        done_ids.update(batch_ids)
        with open(CHECKPOINT_FILE, "wb") as f:
            pickle.dump(done_ids, f)

        total_done = len(done_ids)
        pct = round(total_done / len(nodes) * 100, 1)
        print(f"  [CHROMA] Đã lưu {total_done}/{len(nodes)} nodes ({pct}%)...")

    if CHECKPOINT_FILE.exists():
        os.remove(CHECKPOINT_FILE)

    print(f"[CHROMA] Hoàn tất re-index ChromaDB! Tổng bản ghi trong collection: {collection.count()}")


def reindex_neo4j_entities(embed_model):
    print("\n" + "=" * 60)
    print("2. BẮT ĐẦU CẬP NHẬT EMBEDDING CHO CÁC THỰC THỂ TRONG NEO4J")
    print("=" * 60)

    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USERNAME")
    pwd = os.getenv("NEO4J_PASSWORD")

    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    with driver.session() as session:
        # Xóa vector index cũ nếu có
        try:
            session.run("DROP INDEX entity IF EXISTS")
            print("[NEO4J] Đã drop vector index 'entity' cũ (4096 chiều).")
        except Exception:
            pass

        # Lấy tất cả các Entity hiện có trong Neo4j
        res = session.run("MATCH (e:`__Entity__`) RETURN id(e) AS node_id, e.id AS name, e.name AS alt_name")
        entities = list(res)
        print(f"[NEO4J] Tìm thấy {len(entities)} thực thể cần cập nhật embedding...")

        for i, ent in enumerate(entities, 1):
            n_id = ent["node_id"]
            name = ent["name"] or ent["alt_name"] or ""
            if not name:
                continue

            # Tính vector embedding mới bằng Gemini kèm retry
            vec = embed_with_retry(embed_model, name, is_query=True)

            session.run(
                "MATCH (e) WHERE id(e) = $id SET e.embedding = $vec",
                id=n_id,
                vec=vec
            )
            time.sleep(0.2)

            if i % 20 == 0 or i == len(entities):
                print(f"  [NEO4J] Đã cập nhật {i}/{len(entities)} thực thể...")

        # Tạo lại vector index mới trên Neo4j theo số chiều của Gemini (3072)
        sample_vec = embed_with_retry(embed_model, "test", is_query=True)
        dim = len(sample_vec)
        print(f"[NEO4J] Đang tạo lại vector index 'entity' với dimension={dim}...")
        create_index_query = f"""
        CREATE VECTOR INDEX entity IF NOT EXISTS
        FOR (e:`__Entity__`)
        ON (e.embedding)
        OPTIONS {{
          indexConfig: {{
            `vector.dimensions`: {dim},
            `vector.similarity_function`: 'cosine'
          }}
        }}
        """
        session.run(create_index_query)
        print(f"[NEO4J] Hoàn tất cập nhật thực thể Neo4j!")

    driver.close()


def main():
    print("=" * 60)
    print("   SCRIPT CHUYỂN ĐỔI TOÀN BỘ HỆ THỐNG SANG GEMINI EMBEDDING")
    print("   (Có cơ chế Auto-Resume Checkpoint & Retry Rate Limit)")
    print("=" * 60)

    if not CACHE_PKL_FILE.exists():
        print(f"[LỖI] Không tìm thấy file cache: {CACHE_PKL_FILE}")
        return

    with open(CACHE_PKL_FILE, "rb") as f:
        nodes = pickle.load(f)
    print(f"[INFO] Đã load {len(nodes)} nodes từ file cache {CACHE_PKL_FILE.name} thành công.")

    embed_model = CustomModelEmbedding().get_model()
    print(f"[INFO] Khởi tạo CustomModelEmbedding (Gemini) thành công.")

    # 1. Re-index ChromaDB
    reindex_chroma(nodes, embed_model)

    # 2. Re-index Neo4j Entities
    reindex_neo4j_entities(embed_model)

    print("\n" + "=" * 60)
    print("   TẤT CẢ ĐÃ HOÀN TẤT! HỆ THỐNG ĐÃ SẴN SÀNG CHẠY API /CHAT")
    print("=" * 60)


if __name__ == "__main__":
    main()
