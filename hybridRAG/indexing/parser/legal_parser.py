# indexing/parser/legal_parser.py
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from llama_index.core.schema import Document, BaseNode, TextNode


class LegalStructureAwareParser:
    """
    Bộ phân tích cú pháp chuyên biệt cho văn bản quy phạm pháp luật Việt Nam.
    Bóc tách cấu trúc: Tiêu đề văn bản, Số hiệu văn bản, Trạng thái hiệu lực, Chương, Mục, Điều.
    Gắn Context Header vào từng Node để đảm bảo trọn vẹn ngữ cảnh khi truy xuất.
    """

    def __init__(self, max_chunk_size: int = 1200, chunk_overlap: int = 150):
        self.max_chunk_size = max_chunk_size
        self.chunk_overlap = chunk_overlap

    def parse_documents(self, documents: List[Document]) -> List[BaseNode]:
        """Phân tích danh sách LlamaIndex Document thành danh sách LlamaIndex TextNode giàu metadata."""
        all_nodes: List[BaseNode] = []

        for doc in documents:
            source_name = doc.metadata.get("file_name") or doc.metadata.get("source") or ""
            nodes = self.parse_text(doc.text, source_filename=source_name)
            all_nodes.extend(nodes)

        return all_nodes

    def parse_text(self, text: str, source_filename: str = "") -> List[TextNode]:
        lines = text.splitlines()
        if not lines:
            return []

        # 1. Trích xuất thông tin chung từ đầu tài liệu
        doc_title = ""
        doc_code = ""
        doc_status = "còn hiệu lực"

        # Regex tìm H1 (# Tiêu đề)
        h1_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        if h1_match:
            doc_title = h1_match.group(1).strip()
            # Tìm số hiệu (ví dụ 13/2023/NĐ-CP, 116/2025/QH15, 127/QĐ-TTg, 05/2026/TT-BKHCN)
            code_match = re.search(r"(\d+/\d+/[\wĐđ-]+|\d+/[\wĐđ-]+/[\wĐđ-]+|\d+/[\wĐđ-]+)", doc_title)
            if not code_match:
                code_match = re.search(r"(\d+-\d+-[\wĐđ-]+|\d+-[\wĐđ-]+-[\wĐđ-]+|\d+-[\wĐđ-]+)", doc_title)
            if code_match:
                raw_code = code_match.group(1)
                parts = raw_code.split("-")
                if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
                    doc_code = f"{parts[0]}/{parts[1]}/{'-'.join(parts[2:])}"
                else:
                    doc_code = raw_code

        # Regex tìm trạng thái hiệu lực
        status_match = re.search(r"(còn hiệu lực|hết hiệu lực|chưa có hiệu lực)", text, re.IGNORECASE)
        if status_match:
            doc_status = status_match.group(1).lower()

        if not doc_code and source_filename:
            code_from_file = source_filename.split("_")[0]
            doc_code = code_from_file.replace("-", "/")

        if not doc_title:
            doc_title = source_filename.replace(".md", "").replace("_", " ")

        # 2. Gom nhóm theo cấu trúc Chương / Mục / Điều
        current_chapter = "Mở đầu / Căn cứ ban hành"
        current_article = "Thông tin chung"
        current_content_lines: List[str] = []
        raw_sections: List[Dict[str, Any]] = []

        def save_current_section():
            content = "\n".join(current_content_lines).strip()
            if content:
                raw_sections.append({
                    "chapter": current_chapter,
                    "article": current_article,
                    "content": content
                })

        for line in lines:
            stripped = line.strip()

            if stripped.startswith("# ") and not stripped.startswith("## "):
                continue

            # Tiêu đề Chương (## Chương ...)
            if re.match(r"^##\s+(Chương\s+[IVXLCDM\d]+.*)", stripped, re.IGNORECASE):
                save_current_section()
                current_chapter = stripped.lstrip("#").strip()
                current_article = "Quy định chung chương"
                current_content_lines = []
                continue

            # Tiêu đề Mục (### Mục ...)
            if re.match(r"^###\s+(Mục\s+\d+.*)", stripped, re.IGNORECASE):
                save_current_section()
                current_chapter = f"{current_chapter} - {stripped.lstrip('#').strip()}"
                current_content_lines = []
                continue

            # Tiêu đề Điều (#### Điều ... hoặc ## Điều ...)
            if re.match(r"^#{2,4}\s+(Điều\s+\d+.*)", stripped, re.IGNORECASE) or re.match(r"^(Điều\s+\d+\..*)", stripped, re.IGNORECASE):
                save_current_section()
                current_article = stripped.lstrip("#").strip()
                current_content_lines = []
                continue

            current_content_lines.append(line)

        save_current_section()

        # 3. Tạo TextNode kèm Context Header
        nodes: List[TextNode] = []
        chunk_idx = 0

        for sec in raw_sections:
            content = sec["content"]
            chapter = sec["chapter"]
            article = sec["article"]

            header_prefix = (
                f"[Văn bản: {doc_title}]\n"
                f"[Số hiệu: {doc_code} | Hiệu lực: {doc_status}]\n"
                f"[Phần: {chapter}]\n"
                f"[{article}]\n\n"
            )

            # Nếu section vừa với max_chunk_size, giữ trọn vẹn Điều đó
            if len(header_prefix) + len(content) <= self.max_chunk_size:
                full_text = f"{header_prefix}{content}"
                chunk_id = f"{source_filename}_c{chunk_idx}" if source_filename else f"chunk_{chunk_idx}"
                metadata = {
                    "source": source_filename,
                    "doc_title": doc_title,
                    "doc_code": doc_code,
                    "status": doc_status,
                    "chapter": chapter,
                    "article": article,
                    "chunk_id": chunk_id,
                    "part": 1,
                    "total_parts": 1
                }
                nodes.append(TextNode(text=full_text, id_=chunk_id, metadata=metadata))
                chunk_idx += 1
            else:
                # Nếu section quá dài, chia nhỏ nhưng vẫn đính kèm Header Prefix
                sub_chunks = self._split_long_text(content, max_length=self.max_chunk_size - len(header_prefix))
                total_parts = len(sub_chunks)
                for part_no, sub_c in enumerate(sub_chunks, start=1):
                    full_text = f"{header_prefix}{sub_c}"
                    chunk_id = f"{source_filename}_c{chunk_idx}" if source_filename else f"chunk_{chunk_idx}"
                    metadata = {
                        "source": source_filename,
                        "doc_title": doc_title,
                        "doc_code": doc_code,
                        "status": doc_status,
                        "chapter": chapter,
                        "article": article,
                        "chunk_id": chunk_id,
                        "part": part_no,
                        "total_parts": total_parts
                    }
                    nodes.append(TextNode(text=full_text, id_=chunk_id, metadata=metadata))
                    chunk_idx += 1

        return nodes

    def _split_long_text(self, text: str, max_length: int) -> List[str]:
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        result: List[str] = []
        current = ""

        for p in paragraphs:
            if not current:
                current = p
            elif len(current) + len(p) + 2 <= max_length:
                current += "\n\n" + p
            else:
                result.append(current)
                current = p

        if current:
            result.append(current)

        final_splits = []
        for item in result:
            if len(item) > max_length:
                for i in range(0, len(item), max_length - self.chunk_overlap):
                    final_splits.append(item[i:i + max_length])
            else:
                final_splits.append(item)

        return final_splits or [text]
