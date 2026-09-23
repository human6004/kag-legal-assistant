import os
from typing import Dict, Any, List, Generator
from core.config import settings
from rag_core.retriever import HybridLegalRetriever


SYSTEM_PROMPT = """Bạn là Cố vấn Pháp lý cao cấp chuyên sâu về Pháp luật Công nghệ số, Trí tuệ nhân tạo (AI) và An ninh mạng Việt Nam.
Nhiệm vụ của bạn là giải đáp câu hỏi của người dùng một cách chính xác, minh bạch và có căn cứ pháp lý rõ ràng.

HƯỚNG DẪN QUAN TRỌNG:
1. NGUỒN THÔNG TIN: Chỉ trả lời dựa trên ngữ cảnh (CONTEXT) được cung cấp dưới đây. Không được suy diễn hoặc đưa thông tin không có căn cứ từ bên ngoài tài liệu.
2. TRÍCH DẪN NGUỒN (CITATIONS): Luôn nêu rõ tên văn bản, số hiệu văn bản và Điều/Khoản cụ thể làm căn cứ cho từng ý (Ví dụ: Theo Điều 2 Nghị định 13/2023/NĐ-CP...).
3. HIỆU LỰC PHÁP LÝ: Nếu văn bản được trích dẫn có trạng thái "hết hiệu lực", bạn PHẢI cảnh báo rõ ràng cho người dùng biết để lưu ý áp dụng.
4. TÍNH TRUNG THỰC & CHỐNG ẢO GIÁC: Nếu thông tin trong CONTEXT không đề cập hoặc không đủ để trả lời, hãy thông báo thẳng thắn: "Tài liệu hiện có không chứa thông tin để trả lời câu hỏi này", tuyệt đối không tự bịa đặt câu trả lời.
5. ĐỊNH DẠNG: Trình bày mạch lạc bằng Markdown, dùng gạch đầu dòng rõ ràng, dễ hiểu.
"""


def format_context(retrieved_docs: List[Dict[str, Any]]) -> str:
    """Format danh sách context documents thành chuỗi văn bản có cấu trúc rõ ràng"""
    context_blocks = []
    for idx, doc in enumerate(retrieved_docs, start=1):
        content = doc.get("content", "").strip()
        meta = doc.get("metadata", {})
        doc_title = meta.get("doc_title", "Không rõ")
        doc_code = meta.get("doc_code", "Không rõ")
        status = meta.get("status", "Không rõ")
        article = meta.get("article", "")

        block = (
            f"--- TÀI LIỆU THAM KHẢO #{idx} ---\n"
            f"Văn bản: {doc_title} (Số hiệu: {doc_code})\n"
            f"Tình trạng hiệu lực: {status}\n"
            f"Điều khoản: {article}\n"
            f"Nội dung:\n{content}\n"
        )
        context_blocks.append(block)

    return "\n".join(context_blocks)


class LegalRAGEngine:
    """
    RAG Engine:
    - LLM: Gọi Gemini thông qua 9router (chuẩn OpenAI: LLM_API_KEY & LLM_BASE_URL)
    - Retrieval: Hybrid (ChromaDB với OpenAI Embedding: EMBEDDING_API_KEY + BM25 Okapi)
    """

    def __init__(self):
        self.retriever = HybridLegalRetriever(top_k=settings.TOP_K)
        self.llm = None
        self._init_llm()

    def _init_llm(self):
        api_key = settings.get_llm_api_key()
        if not api_key:
            return

        try:
            from langchain_openai import ChatOpenAI

            kwargs = {
                "model": settings.LLM_MODEL,
                "api_key": api_key,
                "temperature": settings.TEMPERATURE,
            }
            base_url = settings.get_llm_base_url()
            if base_url:
                kwargs["base_url"] = base_url

            self.llm = ChatOpenAI(**kwargs)
        except Exception as e:
            print(f"Cảnh báo: Không thể khởi tạo ChatOpenAI cho model Gemini trên 9router: {e}")

    def generate(self, question: str, include_retrieved: bool = False) -> Dict[str, Any]:
        """Trả lời câu hỏi và trả về câu trả lời kèm citations"""
        docs = self.retriever.retrieve(question)

        citations = []
        for d in docs:
            meta = d.get("metadata", {})
            citations.append({
                "doc_title": meta.get("doc_title", ""),
                "doc_code": meta.get("doc_code", ""),
                "status": meta.get("status", ""),
                "chapter": meta.get("chapter", ""),
                "article": meta.get("article", ""),
                "source": meta.get("source", ""),
                "preview": d.get("content", "")[:200]
            })

        if not self.llm:
            return {
                "question": question,
                "answer": (
                    "Hệ thống chưa được cấu hình LLM_API_KEY (dành cho 9router). "
                    "Vui lòng điền LLM_API_KEY và LLM_BASE_URL vào file .env."
                ),
                "citations": citations,
                "context_found": len(docs) > 0
            }

        context_text = format_context(docs)
        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"CONTEXT:\n{context_text}\n\n"
            f"CÂU HỎI:\n{question}\n\n"
            f"TRẢ LỜI:"
        )

        response = self.llm.invoke(prompt)
        answer_text = response.content if hasattr(response, "content") else str(response)

        result = {
            "question": question,
            "answer": answer_text,
            "citations": citations,
            "context_found": len(docs) > 0
        }
        if include_retrieved:
            result["retrieved_contexts"] = docs
        return result

    def generate_stream(self, question: str) -> Generator[str, None, None]:
        """Streaming câu trả lời qua token generator từ 9router (chuẩn OpenAI)"""
        docs = self.retriever.retrieve(question)
        if not self.llm:
            yield "Chưa cấu hình LLM_API_KEY (9router) trong file .env."
            return

        context_text = format_context(docs)
        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"CONTEXT:\n{context_text}\n\n"
            f"CÂU HỎI:\n{question}\n\n"
            f"TRẢ LỜI:"
        )

        for chunk in self.llm.stream(prompt):
            content = chunk.content if hasattr(chunk, "content") else str(chunk)
            yield content
