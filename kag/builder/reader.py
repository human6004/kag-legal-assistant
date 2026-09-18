# -*- coding: utf-8 -*-
"""Reader cho pipeline văn bản pháp luật (R3).

Kế thừa ``MarkDownReader`` và triển khai trực tiếp ``_build_document_tree``
để bảo toàn cấu trúc văn bản pháp luật mà không cần các thao tác đột biến soup phức tạp.

Các vấn đề đã giải quyết:
1. Số Khoản và Điểm:
   - Đọc thuộc tính ``start`` của ``<ol>`` và ``value`` của ``<li>`` để đánh số chính xác.
   - Bảo toàn đúng thứ tự tài liệu: Điểm (dạng <p>) nằm ngay sau Khoản tương ứng.
2. Danh sách không thứ tự (bullet / ul):
   - Phân biệt rõ danh sách thứ tự (ol) và không thứ tự (ul) theo đúng cấp cha trực tiếp.
   - Không biến bullet thành số Khoản (sửa hồi quy R2 trên QĐ 127 và các văn bản tương tự).
3. Đảo thứ tự khi có li@value và Điểm xen kẽ:
   - Xử lý theo đúng thứ tự xuất hiện của các phần tử trong cây tài liệu.
4. Trùng lặp nội dung phức tạp:
   - Xử lý các ``<p>`` bên trong ``<li>`` thành từng dòng riêng biệt, không ghép xâu rồi lặp lại.
   - Danh sách lồng nhau (nested list) không bị ghép nội dung con vào cha.
5. Không làm mất nội dung hợp lệ:
   - Giữ lại các đoạn văn bản bắt đầu bằng số (khắc phục việc mất 285 dòng trong QĐ 1671 do
     chốt chặn `re.match(r'^\\d+\\. ', text)` cũ của thư viện gốc).
"""

import io
import logging
import os
import re
from pathlib import Path
from typing import List, Optional

from bs4 import BeautifulSoup, Tag
import markdown
from markdown.extensions import Extension
from markdown.extensions.sane_lists import SaneOListProcessor
from kag.builder.component.reader.markdown_reader import MarkdownNode, MarkDownReader, convert_to_subgraph
from kag.interface import ReaderABC
import pandas as pd

logger = logging.getLogger(__name__)

_HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_BLOCK_TAGS = {"p", "ol", "ul", "table", "pre", "blockquote", *_HEADINGS}

#: Gốc repo, để quy đường dẫn nguồn về dạng tương đối portable.
_REPO_ROOT = Path(__file__).resolve().parents[2]


class _LexicalTable(pd.DataFrame):
    """DataFrame bảng: chặn tabulate parse lại chuỗi số khi render markdown.

    ``to_markdown`` mặc định để tabulate tự suy kiểu; cột toàn chuỗi số sẽ bị đọc
    thành float nên "1.100" in ra "1.1". Giá trị ô đã đúng ở tầng đọc, chỉ cần giữ
    nguyên lúc render, nên bật ``disable_numparse``.
    """

    @property
    def _constructor(self):
        return _LexicalTable

    def to_markdown(self, *args, **kwargs):
        kwargs.setdefault("disable_numparse", True)
        return super().to_markdown(*args, **kwargs)


class _SourceNumberList(SaneOListProcessor):
    """Retain each source ordinal before Markdown discards it (including resets)."""

    def run(self, parent, blocks):
        numbers = [m.group(2).rstrip('.') for line in blocks[0].splitlines()
                   if (m := self.CHILD_RE.match(line))]
        before = set(parent.iter('li'))
        super().run(parent, blocks)
        # Nested ordered lists run this same processor first and already have value.
        items = [li for ol in parent.iter('ol') for li in ol
                 if li.tag == 'li' and li not in before and 'value' not in li.attrib]
        if len(items) != len(numbers):
            raise ValueError('Cannot preserve source list ordinals')
        for li, number in zip(items, numbers):
            li.set('value', number)


class _SourceNumbers(Extension):
    def extendMarkdown(self, md):
        md.parser.blockprocessors.register(_SourceNumberList(md.parser), 'olist', 40)


@ReaderABC.register("legal_md_reader")
class LegalMarkdownReader(MarkDownReader):
    """``MarkDownReader`` bảo toàn cấu trúc pháp lý, thứ tự và nội dung không lặp."""

    @staticmethod
    def _source_path(id) -> str:
        """Đường dẫn nguồn ổn định của file đang đọc.

        ``MarkDownReader._parse_input`` đã có đường dẫn file ở tham số ``id``,
        nhưng chỉ chunk BẢNG được gắn ``file_name``; chunk TEXT không giữ gì. Ở
        đây quy về đường dẫn TƯƠNG ĐỐI so với gốc repo, dấu ``/``, để không ghi
        absolute path của máy người dùng vào graph. File ngoài repo chỉ giữ tên
        file; input không phải path thì trả nguyên chuỗi.

        Đây là provenance để truy nguồn, KHÔNG phải canonical legal identity.
        """
        raw = str(id or "").strip()
        if not raw:
            return ""
        path = Path(raw)
        if not (raw.lower().endswith(".md") or os.path.isfile(raw)):
            return raw
        try:
            resolved = path.resolve()
        except OSError:
            return path.name
        try:
            return resolved.relative_to(_REPO_ROOT).as_posix()
        except ValueError:
            return resolved.name

    @staticmethod
    def _stamp(chunks, source_path: str):
        """Gắn ``source_path`` vào ``chunk.kwargs`` (kênh metadata, không vào text)."""
        if not source_path:
            return chunks
        for chunk in chunks:
            chunk.kwargs["source_path"] = source_path
            chunk.source_path = source_path
        return chunks

    def solve_content(self, id, title, content, **kwargs):
        # Same orchestration as KAG; add the ordinal-preserving block processor.
        html = markdown.markdown(self._preprocess_markdown_content(content),
                                 extensions=['tables', 'nl2br', 'sane_lists',
                                             'fenced_code', _SourceNumbers()])
        root = self._build_document_tree(BeautifulSoup(html, 'html.parser'))
        outputs, mapping = self._convert_to_outputs(root, id)
        if self.length_splitter:
            outputs, mapping = self._apply_length_splitting(outputs, mapping)
        # Gắn sau khi chia để mọi chunk (TEXT và TABLE) đều có cùng một
        # source identifier trước khi đi vào splitter.
        self._stamp(outputs, self._source_path(id))
        graph, _ = convert_to_subgraph(root, outputs, self._flatten_node_chunk_map(mapping))
        return outputs, graph

    def _apply_length_splitting(self, outputs, node_chunk_map):
        """Honor configured lengths and retain heading-only chunks in the reader seam."""
        result, mapping = [], {}
        by_id = {}
        for output in outputs:
            split = (self.length_splitter.slide_window_chunk(
                output, self.length_splitter.split_length, self.length_splitter.window_length)
                if output.content else [output])
            for chunk in split:
                chunk.parent_id = output.parent_id
            result.extend(split)
            by_id[output.id] = split
        for node, chunk in node_chunk_map.items():
            mapping[node] = by_id[chunk.id]
        return result, mapping

    def _process_text_with_links(self, element: Tag) -> str:
        """Trích xuất văn bản có link markdown, bỏ qua các thẻ khối con."""
        result = []
        current_text = ""

        for child in element.children:
            if isinstance(child, Tag):
                if child.name in _BLOCK_TAGS:
                    # Các thẻ khối con được xử lý riêng, không ghép vào dòng cha
                    continue
                if child.name == "a":
                    if current_text:
                        result.append(current_text.strip())
                        current_text = ""
                    link_text = child.get_text().strip()
                    href = child.get("href", "")
                    title = child.get("title", "")
                    if title:
                        result.append(f'[{link_text}]({href} "{title}")')
                    else:
                        result.append(f"[{link_text}]({href})")
                elif child.name == "br":
                    if current_text:
                        result.append(current_text.strip())
                        current_text = ""
                    result.append("\n")
                else:
                    # Các thẻ inline khác (em, strong, span, code...)
                    current_text += child.get_text()
            else:
                current_text += str(child)

        if current_text:
            result.append(current_text.strip())

        out = ""
        for piece in result:
            if piece == "\n":
                out = out.rstrip() + "\n"
            else:
                if out and not out.endswith("\n"):
                    out += " " + piece
                else:
                    out += piece
        return out.strip()

    def _build_document_tree(self, soup: BeautifulSoup) -> MarkdownNode:
        """Dựng cây tài liệu phân cấp trực tiếp từ soup theo thứ tự khối."""
        root = MarkdownNode("root", 0)
        stack: List[MarkdownNode] = [root]
        current_content: List[str] = []

        def _process_table(element: Tag) -> Optional[dict]:
            """Chuyển thẻ table thành dữ liệu bảng có cấu trúc."""
            try:
                # pandas suy dtype trước khi ép sang str: dấu nghìn tiếng Việt bị
                # đọc là dấu thập phân ("5.000" -> 5.0), số nguyên thành 10.0, và
                # NA inference biến literal "NA"/"N/A" thành missing. Lượt đọc đầu
                # chỉ để lấy số cột, rồi đọc lại với converters=str giữ nguyên text.
                probe = pd.read_html(io.StringIO(str(element)), header=0)[0]
                df = pd.read_html(
                    io.StringIO(str(element)),
                    header=0,
                    converters={idx: str for idx in range(probe.shape[1])},
                    keep_default_na=False,
                )[0]
                for col in df.columns:
                    df[col] = df[col].map(
                        lambda x: str(x).strip('"\\"') if isinstance(x, str) else x
                    )
                df.columns = [
                    "" if "Unnamed" in str(col) else str(col).strip('"\\"')
                    for col in df.columns
                ]
                headers = df.columns.tolist()
                df = _LexicalTable(df)
                context = self._extract_table_context(
                    element, self._process_text_with_links
                )
                return {"headers": headers, "data": df, "context": context}
            except Exception as exc:
                raise ValueError('Cannot parse source table without losing content') from exc

        def _process_li(li_tag: Tag, prefix: str, depth: int):
            """Xử lý từng mục li, bảo đảm không ghép lồng và không nhân bản p."""
            first = True
            inline_buf = []

            def flush_inline():
                nonlocal first
                text = " ".join(inline_buf).strip()
                inline_buf.clear()
                if text:
                    for line in text.splitlines():
                        line = line.strip()
                        if line:
                            if first:
                                current_content.append(f"{prefix}{line}")
                                first = False
                            else:
                                current_content.append('    ' * (depth + 1) + line)

            for child in li_tag.children:
                if isinstance(child, Tag) and child.name in (
                    "p",
                    "ol",
                    "ul",
                    "table",
                    "pre",
                ):
                    flush_inline()
                    if child.name == "p":
                        p_text = self._process_text_with_links(child)
                        if p_text:
                            for line in p_text.splitlines():
                                line = line.strip()
                                if line:
                                    if first:
                                        current_content.append(f"{prefix}{line}")
                                        first = False
                                    else:
                                        current_content.append('    ' * (depth + 1) + line)
                    elif child.name == "ol":
                        _process_ol(child, depth + 1)
                    elif child.name == "ul":
                        _process_ul(child, depth + 1)
                    elif child.name == "pre":
                        current_content.append(child.get_text())
                    elif child.name == "table":
                        t = _process_table(child)
                        if t and stack[-1].title != "root":
                            stack[-1].tables.append(t)
                else:
                    part = (
                        self._process_text_with_links(child)
                        if isinstance(child, Tag)
                        else str(child).strip()
                    )
                    if part:
                        inline_buf.append(part)
            flush_inline()

        def _process_ol(ol_tag: Tag, depth=0):
            """Xử lý danh sách có thứ tự (ol), đọc start và value."""
            start = 1
            raw_start = ol_tag.get("start")
            if raw_start is not None and str(raw_start).strip().isdigit():
                start = int(str(raw_start).strip())

            for child in ol_tag.children:
                if not isinstance(child, Tag):
                    continue
                if child.name == "li":
                    val = child.get("value")
                    if val is not None and str(val).strip().isdigit():
                        start = int(str(val).strip())
                    _process_li(child, '    ' * depth + f"{start}. ", depth)
                    start += 1
                elif child.name == "ol":
                    _process_ol(child)
                elif child.name == "ul":
                    _process_ul(child)
                elif child.name == "table":
                    t = _process_table(child)
                    if t and stack[-1].title != "root":
                        stack[-1].tables.append(t)
                elif child.name == "p":
                    txt = self._process_text_with_links(child)
                    if txt:
                        for line in txt.splitlines():
                            if line.strip():
                                current_content.append(line.strip())

        def _process_ul(ul_tag: Tag, depth=0):
            """Xử lý danh sách không thứ tự (ul), luôn dùng bullet *."""
            for child in ul_tag.children:
                if not isinstance(child, Tag):
                    continue
                if child.name == "li":
                    _process_li(child, '    ' * depth + "* ", depth)
                elif child.name == "ol":
                    _process_ol(child)
                elif child.name == "ul":
                    _process_ul(child)
                elif child.name == "table":
                    t = _process_table(child)
                    if t and stack[-1].title != "root":
                        stack[-1].tables.append(t)
                elif child.name == "p":
                    txt = self._process_text_with_links(child)
                    if txt:
                        for line in txt.splitlines():
                            if line.strip():
                                current_content.append(line.strip())

        def _process_element(element: Tag):
            """Xử lý từng phần tử khối theo thứ tự xuất hiện."""
            if element.name in _HEADINGS:
                if current_content and stack[-1].title != "root":
                    stack[-1].content = "\n".join(current_content)
                current_content.clear()
                level = int(element.name[1])
                title_text = self._process_text_with_links(element)
                new_node = MarkdownNode(title_text, level)
                while stack and stack[-1].level >= level:
                    stack.pop()
                if stack:
                    stack[-1].children.append(new_node)
                stack.append(new_node)
            elif element.name == "ol":
                _process_ol(element)
            elif element.name == "ul":
                _process_ul(element)
            elif element.name == "table":
                t = _process_table(element)
                if t and stack[-1].title != "root":
                    stack[-1].tables.append(t)
            elif element.name in ("pre", "code"):
                txt = element.get_text()
                if txt:
                    current_content.append(txt)
            elif element.name == "p":
                txt = self._process_text_with_links(element)
                if txt:
                    for line in txt.splitlines():
                        if line.strip():
                            current_content.append(line.strip())
            elif element.name in ("div", "section", "article", "blockquote"):
                for child in element.children:
                    if isinstance(child, Tag):
                        _process_element(child)

        for child in soup.children:
            if isinstance(child, Tag):
                _process_element(child)

        if current_content and stack[-1].title != "root":
            stack[-1].content = "\n".join(current_content)

        return root
