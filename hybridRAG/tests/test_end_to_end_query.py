import sys
import io
from pathlib import Path

# Đảm bảo root thư mục được đưa vào sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from database.chroma_store import load_vector_index
from retrieval.search.bm25_search import BM25Search
from retrieval.retrieve import Retriever
from llm.answer_generator import AnswerGenerator
from llm.config import get_default_llm


def main():
    print("Khởi tạo hệ thống kiểm thử End-to-End với LLM tự động...")
    llm = get_default_llm()
    print(f"LLM đã chọn: {type(llm).__name__}")

    vector_index = load_vector_index()
    bm25 = BM25Search(cache_path=str(PROJECT_ROOT / "database" / "bm25_index.pkl"))

    retriever = Retriever(
        llm=llm,
        vector_index=vector_index,
        bm25_search=bm25,
        top_k=3,
        use_hyde=True
    )
    generator = AnswerGenerator(llm=llm)

    query = "Doanh nghiệp mua bán trái phép dữ liệu cá nhân nhạy cảm của 300 người thì bị phạt bao nhiêu tiền và quy định tại điều nào?"
    print(f"\n[QUERY] {query}")

    contexts, tracker = retriever.retrieve_with_latency(query)
    print("\n--- THỜI GIAN TRUY XUẤT ---")
    print(tracker.summary())

    print("\n--- DANH SÁCH NGUỒN CĂN CỨ TRUY XUẤT ---")
    sources = generator.extract_sources(contexts)
    for s in sources:
        print(f"[{s['index']}] Văn bản: {s['doc_title']}")
        print(f"    Điều/Khoản: {s['article']} | Score: {s['score']}")
        print(f"    Trích đoạn: {s['snippet'][:150]}...\n")

    print("--- SINH CÂU TRẢ LỜI PHÁP LÝ ---")
    answer = generator.generate(question=query, contexts=contexts)
    print(answer)


if __name__ == "__main__":
    main()
