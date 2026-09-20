import sys
from core.config import settings
from rag_core.engine import LegalRAGEngine


def main():
    print("=" * 60)
    print("   HỆ THỐNG TRỢ LÝ PHÁP LUẬT AI & AN NINH MẠNG VIỆT NAM   ")
    print("=" * 60)
    print("1. LLM (Chat): 9router -> Gemini")
    print(f"   - Model: {settings.LLM_MODEL}")
    print(f"   - Base URL: {settings.get_llm_base_url() or 'Chưa điền LLM_BASE_URL'}")
    print(f"   - API Key: {'Đã cấu hình' if settings.get_llm_api_key() else 'CHƯA CẤU HÌNH LLM_API_KEY'}")
    print("2. Embedding: OpenAI")
    print(f"   - Model: {settings.EMBEDDING_MODEL}")
    print(f"   - Base URL: {settings.get_embedding_base_url() or 'Default (https://api.openai.com/v1)'}")
    print(f"   - API Key: {'Đã cấu hình' if settings.get_embedding_api_key() else 'CHƯA CẤU HÌNH EMBEDDING_API_KEY'}")
    print("-" * 60)

    engine = LegalRAGEngine()

    query = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "Dữ liệu cá nhân nhạy cảm gồm những gì theo Nghị định 13/2023/NĐ-CP?"
    )

    print(f"\n[CÂU HỎI]: {query}\n")
    print("Đang tìm kiếm tài liệu và sinh câu trả lời...\n")

    result = engine.generate(query)

    print("-" * 60)
    print("[CÂU TRẢ LỜI]:\n")
    print(result["answer"])
    print("\n" + "-" * 60)
    print(f"[TRÍCH DẪN NGUỒN ({len(result['citations'])} tài liệu)]:")
    for i, cite in enumerate(result["citations"], start=1):
        print(f"\n{i}. Văn bản: {cite['doc_title']}")
        print(f"   Số hiệu: {cite['doc_code']} | Tình trạng: {cite['status']}")
        print(f"   Điều khoản: {cite['article']}")
        print(f"   Nội dung trích đoạn: {cite['preview']}...")
    print("=" * 60)


if __name__ == "__main__":
    main()
