import sys
import os
from pathlib import Path
from typing import List

from core.config import settings
from rag_core.chunker import LegalStructureAwareChunker, LegalChunk
from rag_core.bm25 import BM25OkapiIndex


def get_embedding_function():
    """Khởi tạo OpenAI Embeddings theo cấu hình"""
    api_key = settings.get_embedding_api_key()
    if not api_key:
        raise ValueError(
            "Chưa cấu hình EMBEDDING_API_KEY trong file .env! "
            "Vui lòng mở file .env và điền EMBEDDING_API_KEY (từ OpenAI hoặc Vilao) trước khi đánh chỉ mục."
        )

    # Tự động thêm tiền tố 'sk-' nếu bị thiếu (ví dụ key từ vilao.ai)
    if not api_key.startswith("sk-") and len(api_key) > 20:
        api_key = f"sk-{api_key}"

    from langchain_openai import OpenAIEmbeddings

    # Chuẩn hoá tên model: loại bỏ tiền tố dg/ nếu có (vilao.ai dùng text-embedding-3-large)
    model_name = settings.EMBEDDING_MODEL
    if model_name.startswith("dg/"):
        model_name = model_name.replace("dg/", "")

    kwargs = {
        "model": model_name,
        "api_key": api_key,
    }
    base_url = settings.get_embedding_base_url()
    if base_url:
        kwargs["base_url"] = base_url

    return OpenAIEmbeddings(**kwargs)


def index_knowledge_base():
    """
    Tiến hành nạp toàn bộ văn bản trong knowledge_base/, cắt chunk và đánh chỉ mục
    đồng thời vào ChromaDB (Dense) và BM25 (Sparse).
    """
    kb_dir = Path(settings.KNOWLEDGE_BASE_DIR)
    if not kb_dir.exists():
        raise FileNotFoundError(f"Không tìm thấy thư mục knowledge base tại: {kb_dir}")

    md_files = sorted(list(kb_dir.glob("*.md")))
    if not md_files:
        print(f"Cảnh báo: Không có file markdown nào trong {kb_dir}")
        return

    print(f"--- BẮT ĐẦU ĐÁNH CHỈ MỤC ({len(md_files)} văn bản) ---")
    chunker = LegalStructureAwareChunker(
        max_chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP
    )

    all_chunks: List[LegalChunk] = []
    for f in md_files:
        chunks = chunker.parse_file(f)
        all_chunks.extend(chunks)
        print(f" -> Đã đọc: {f.name} ({len(chunks)} chunks)")

    print(f"\nTổng số chunks đã trích xuất: {len(all_chunks)}")
    if not all_chunks:
        return

    # 1. Lưu BM25 Index (Sparse Search)
    print("\n[1/2] Đang xây dựng chỉ mục từ khóa BM25...")
    bm25_docs = [c.to_dict() for c in all_chunks]
    bm25 = BM25OkapiIndex()
    bm25.fit(bm25_docs)

    bm25_path = Path(settings.BM25_PERSIST_DIR) / "bm25.pkl"
    bm25.save(bm25_path)
    print(f" -> Đã lưu BM25 index tại: {bm25_path}")

    # 2. Lưu ChromaDB (Dense Vector Search)
    print("\n[2/2] Đang khởi tạo embedding và lưu vào ChromaDB...")
    try:
        embeddings = get_embedding_function()
    except ValueError as e:
        print(f"\n[LƯU Ý] {e}")
        print(" -> Chỉ mục BM25 đã được lưu thành công. Khi bạn có API Key, chạy lại script này để nạp Vector DB.")
        return

    import chromadb
    try:
        from langchain_chroma import Chroma
    except ImportError:
        from langchain_community.vectorstores import Chroma
    from langchain_core.documents import Document

    chroma_dir = str(settings.CHROMA_PERSIST_DIR)
    os.makedirs(chroma_dir, exist_ok=True)

    lc_docs = [
        Document(page_content=c.content, metadata=c.metadata)
        for c in all_chunks
    ]

    # Batch insert để tránh giới hạn kích thước request
    batch_size = 50
    total = len(lc_docs)
    
    # Khởi tạo hoặc kết nối DB
    vector_store = Chroma(
        collection_name="legal_ai_vietnam",
        embedding_function=embeddings,
        persist_directory=chroma_dir
    )

    print(f" -> Đang nạp {total} documents vào ChromaDB theo từng batch {batch_size}...")
    for i in range(0, total, batch_size):
        batch = lc_docs[i:i + batch_size]
        vector_store.add_documents(documents=batch)
        print(f"    Đã nạp {min(i + batch_size, total)}/{total} chunks...")

    print(f"\n=== ĐÁNH CHỈ MỤC HOÀN TẤT THÀNH CÔNG ===")
    print(f"ChromaDB đã lưu tại: {chroma_dir}")


if __name__ == "__main__":
    try:
        index_knowledge_base()
    except Exception as ex:
        print(f"Lỗi trong quá trình đánh chỉ mục: {ex}", file=sys.stderr)
        sys.exit(1)
