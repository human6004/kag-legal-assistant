from typing import Optional, Union, List, Dict, Any
from llm.nvidia import NvidiaNimLLM
from llm.prompts import PROMPT, build_prompt
from retrieval.metrics.latency_tracker import LatencyTracker


class AnswerGenerator:

    def __init__(self, llm=None):
        self.llm = llm if llm is not None else NvidiaNimLLM().get_llm()

    def _format_context(self, contexts: Union[str, List]) -> str:
        """
        Chuẩn hóa ngữ cảnh đầu vào thành dạng chuỗi giàu thông tin metadata
        giúp LLM dễ dàng nhận diện và trích dẫn chính xác nguồn gốc điều luật.
        """
        if isinstance(contexts, str):
            return contexts

        formatted_chunks = []
        for i, item in enumerate(contexts, 1):
            meta = {}
            if hasattr(item, "node"):
                node = item.node
                text = node.get_content().strip() if hasattr(node, "get_content") else str(node)
                meta = getattr(node, "metadata", {}) or {}
            elif hasattr(item, "text"):
                text = item.text.strip()
                meta = getattr(item, "metadata", {}) or {}
            else:
                text = str(item).strip()

            header_parts = [f"--- [Nguồn tham khảo {i}] ---"]
            if meta:
                doc_title = meta.get("doc_title") or meta.get("title") or meta.get("source")
                doc_code = meta.get("doc_code")
                article = meta.get("article")
                chapter = meta.get("chapter")

                if doc_title:
                    header_parts.append(f"Văn bản: {doc_title}")
                if doc_code:
                    header_parts.append(f"Số hiệu: {doc_code}")
                if article:
                    header_parts.append(f"Điều khoản: {article}")
                if chapter and chapter != "Mở đầu / Căn cứ ban hành":
                    header_parts.append(f"Chương/Mục: {chapter}")

            header_str = "\n".join(header_parts)
            formatted_chunks.append(f"{header_str}\nNội dung:\n{text}")

        return "\n\n".join(formatted_chunks)

    def extract_sources(self, contexts: Union[str, List]) -> List[Dict[str, Any]]:
        """Trích xuất danh sách nguồn tham khảo (citations) từ danh sách node."""
        if isinstance(contexts, str):
            return []

        sources = []
        seen_chunks = set()

        for i, item in enumerate(contexts, 1):
            meta = {}
            text_snippet = ""
            score = None

            if hasattr(item, "score"):
                score = round(float(item.score), 4)

            if hasattr(item, "node"):
                node = item.node
                text = node.get_content() if hasattr(node, "get_content") else str(node)
                text_snippet = text[:200] + "..." if len(text) > 200 else text
                meta = getattr(node, "metadata", {}) or {}
                chunk_id = getattr(node, "node_id", f"chunk_{i}")
            else:
                text = str(item)
                text_snippet = text[:200] + "..." if len(text) > 200 else text
                chunk_id = f"chunk_{i}"

            if chunk_id in seen_chunks:
                continue
            seen_chunks.add(chunk_id)

            sources.append({
                "index": i,
                "chunk_id": chunk_id,
                "doc_title": meta.get("doc_title") or meta.get("title") or meta.get("source", "Không rõ"),
                "doc_code": meta.get("doc_code", "Không rõ"),
                "article": meta.get("article", "Quy định liên quan"),
                "chapter": meta.get("chapter", ""),
                "score": score,
                "snippet": text_snippet
            })

        return sources

    def generate(
        self,
        question: str,
        contexts: Union[str, List],
        tracker: Optional[LatencyTracker] = None
    ) -> str:
        context_str = self._format_context(contexts)

        user_content = build_prompt(
            context=context_str,
            question=question,
        )

        full_prompt = (
            PROMPT
            + "\n\n"
            + user_content
        )

        if tracker:
            with tracker.track("answer_generation"):
                response = self.llm.complete(full_prompt)
        else:
            response = self.llm.complete(full_prompt)

        return response.text