# -*- coding: utf-8 -*-
"""Splitter chia chunk theo ranh giới cấu trúc pháp luật (B1.2).

Thay việc cắt theo text phẳng + độ dài bằng thang cấu trúc đã chốt ở B1:

    Điều <= ngưỡng            -> giữ nguyên một chunk
    Điều > ngưỡng             -> chia theo Khoản
    một Khoản > ngưỡng        -> chia theo Điểm
    một Điểm > ngưỡng         -> fallback theo độ dài (ranh giới dòng/câu)

Ngưỡng mặc định 4950 **ký tự Unicode** (không phải token), overlap = 0 cho mọi
lần chia theo cấu trúc; ngữ cảnh được giữ bằng heading prefix, không bằng cách
sao lại phần thân của chunk trước.

Ranh giới Khoản/Điểm lấy ở đâu
------------------------------
``MarkdownNode`` của reader chỉ dựng node cho heading (``#``..``######``). Khoản
và Điểm nằm trong cùng một node dưới dạng ``<ol>/<li>`` và được
``reader._process_ol``/``_process_li`` phát ra thành dòng text với tiền tố xác
định: Khoản/mục đánh số là ``"{số}. "``, danh sách lồng thụt thêm 4 space mỗi
cấp, Điểm giữ nguyên chữ cái đầu dòng (``"a) "``). Vì vậy ranh giới cấu trúc mà
splitter có thể dùng chính là các tiền tố đó ở **cột 0** — không phải regex đoán
trên text bất kỳ. Neo ở cột 0 khiến danh sách lồng (đã thụt lề) tự động nằm
trong đơn vị cha, không bị tách ra.

``heading_path`` lấy từ ``chunk.name`` (reader đã ghép ``" / "``.join các heading
từ gốc tới node), nên Điều thật (``... / Chương II / Điều 13. ...``) phân biệt
được với Điều trong mẫu biểu (``... / Mẫu AI09a: / Điều 3. ...``) bằng tổ tiên,
không phải bằng regex số Điều.

Hai kênh tách biệt
------------------
* text cho LLM: ``name`` mang heading/ngữ cảnh pháp lý, ``content`` mang THÂN
  ngữ nghĩa. Extractor thật dựng passage bằng
  ``passage = input.name + "\\n" + input.content``
  (``schema_free_extractor.py:506``), nên nếu prepend lại ``heading_path`` vào
  ``content`` thì heading lặp hai lần trong passage — không làm vậy. Không chứa
  hash, đường dẫn, offset hay hậu tố kỹ thuật kiểu ``_split_1``.
* metadata truy nguồn: ``source_path`` (reader gắn), ``heading_path``,
  ``article_no``, ``clause_no``, ``point_no``, ``split_index``, ``split_total``
  trong ``chunk.kwargs``.

Chỉ gọi là Khoản/Điểm khi biết chắc là Điều
-------------------------------------------
``1.``/``2.`` ở cột 0 vẫn dùng làm ranh giới chia ở mọi nhánh, nhưng nhãn pháp
lý (``clause_no``, ``point_no``, tên ``... / Khoản N``) chỉ gắn khi
``article_no`` xác định được. Trong Mẫu/Phụ lục/nhánh không phải Điều, ``1.``
chỉ là mục đánh số — không đủ bằng chứng gọi là Khoản, nên ở đó chỉ giữ thứ tự
bằng ``split_index`` và hậu tố ``(phần i/N)``.

ID của chunk ở đây chỉ là **runtime chunk id**, không phải canonical legal
identity; danh tính Điều/Khoản/Điểm là việc của B2.
"""

import logging
import re
from typing import Dict, List, Optional, Tuple

from kag.builder.component.splitter.length_splitter import LengthSplitter
from kag.builder.model.chunk import Chunk, ChunkTypeEnum
from kag.common.utils import generate_hash_id
from kag.interface import SplitterABC
from knext.common.base.runnable import Output

logger = logging.getLogger(__name__)

#: Khoản (hoặc mục đánh số) do reader phát ra ở cột 0: "1. ", "12. ".
_CLAUSE_RE = re.compile(r"^(\d{1,3})\.[ \t]+(?=\S)")
#: Điểm do reader giữ nguyên ở cột 0: "a) ", "đ) ". Chữ cái tiếng Việt có dấu
#: vẫn xuất hiện trong văn bản (đ, ă, â, ê, ô, ơ, ư) nên phải liệt kê.
_POINT_RE = re.compile(r"^([a-zđăâêôơư])\)[ \t]+(?=\S)", re.IGNORECASE)
#: Heading là một Điều được đánh số.
_ARTICLE_RE = re.compile(r"^Điều\s+(\d{1,3})\b")
#: Heading chỉ là nhãn cấu trúc, không mang quy định tự thân.
_LABEL_RE = re.compile(r"^(Chương|Mục|Phần|Phụ lục|Mẫu|Biểu|Bảng)\b", re.IGNORECASE)
#: Tổ tiên cho biết nhánh này là mẫu biểu/phụ lục, không phải thân văn bản.
_FORM_ANCESTOR_RE = re.compile(r"^(Phụ lục|Mẫu|Biểu mẫu)\b", re.IGNORECASE)


class _Unit:
    """Một đơn vị cấu trúc sẽ thành một chunk."""

    def __init__(
        self,
        body: str,
        clause_no: Optional[str] = None,
        point_no: Optional[str] = None,
        part_no: Optional[int] = None,
    ):
        self.body = body
        self.clause_no = clause_no
        self.point_no = point_no
        self.part_no = part_no

    def legal_suffix(self) -> str:
        """Hậu tố pháp lý — chỉ dùng khi đã xác định được Điều."""
        parts = []
        if self.clause_no is not None:
            parts.append(f"Khoản {self.clause_no}")
        if self.point_no is not None:
            parts.append(f"Điểm {self.point_no}")
        return " / ".join(parts)


@SplitterABC.register("legal_structural_splitter")
class LegalStructuralSplitter(LengthSplitter):
    """Chia chunk theo Điều → Khoản → Điểm, fallback độ dài là bước cuối.

    Kế thừa ``LengthSplitter`` để dùng lại đường chia bảng của
    ``BaseTableSplitter``; không sửa code vendor.
    """

    def __init__(
        self,
        split_length: int = 4950,
        window_length: int = 0,
        **kwargs,
    ):
        super().__init__(
            split_length=split_length, window_length=window_length, **kwargs
        )

    # ------------------------------------------------------------------ #
    # phân tích cấu trúc
    # ------------------------------------------------------------------ #
    @staticmethod
    def _blocks(text: str, marker: re.Pattern) -> Tuple[str, List[Tuple[str, str]]]:
        """Tách text thành (phần dẫn, [(số/chữ đánh dấu, thân đơn vị)]).

        Chỉ dòng khớp ``marker`` ở cột 0 mới mở đơn vị mới, nên danh sách lồng
        (reader thụt 4 space mỗi cấp) nằm trong đơn vị cha.
        """
        lead: List[str] = []
        blocks: List[Tuple[str, List[str]]] = []
        for line in text.split("\n"):
            hit = marker.match(line)
            if hit:
                blocks.append((hit.group(1), [line]))
            elif blocks:
                blocks[-1][1].append(line)
            else:
                lead.append(line)
        return "\n".join(lead).strip("\n"), [
            (key, "\n".join(lines).strip("\n")) for key, lines in blocks
        ]

    @staticmethod
    def _split_by_length(text: str, budget: int) -> List[str]:
        """Fallback cuối: cắt theo ranh giới dòng, rồi câu, rồi khoảng trắng.

        Không cắt giữa từ nếu còn chỗ cắt an toàn, không đảo thứ tự, không bỏ
        ký tự nào ngoài khoảng trắng ở hai đầu mảnh. Overlap = 0.
        """
        budget = max(budget, 1)
        pieces: List[str] = []
        current: List[str] = []
        current_len = 0

        def flush():
            nonlocal current, current_len
            if current:
                pieces.append("\n".join(current).strip("\n"))
                current = []
                current_len = 0

        for line in text.split("\n"):
            for fragment in LegalStructuralSplitter._fragment_line(line, budget):
                extra = len(fragment) + (1 if current else 0)
                if current and current_len + extra > budget:
                    flush()
                current.append(fragment)
                current_len += len(fragment) + (1 if len(current) > 1 else 0)
        flush()
        return [piece for piece in pieces if piece.strip()]

    @staticmethod
    def _fragment_line(line: str, budget: int) -> List[str]:
        """Cắt một dòng quá dài: ưu tiên hết câu, sau đó khoảng trắng."""
        if len(line) <= budget:
            return [line]
        out: List[str] = []
        rest = line
        while len(rest) > budget:
            window = rest[:budget]
            cut = max(window.rfind(". "), window.rfind("; "), window.rfind(": "))
            if cut > 0:
                cut += 1
            else:
                cut = window.rfind(" ")
            if cut <= 0:
                cut = budget  # một "từ" dài hơn cả ngưỡng: buộc phải cắt cứng
            out.append(rest[:cut].rstrip())
            rest = rest[cut:].lstrip()
        if rest:
            out.append(rest)
        return out

    def _units(self, content: str, budget: int) -> List[_Unit]:
        """Đi thang Khoản → Điểm → độ dài cho một chunk vượt ngưỡng."""
        lead, clauses = self._blocks(content, _CLAUSE_RE)
        if not clauses:
            # Không có Khoản: thử Điểm ngay, nếu cũng không có thì fallback.
            return self._units_without_clause(content, budget, clause_no=None)

        units: List[_Unit] = []
        for idx, (clause_no, body) in enumerate(clauses):
            text = f"{lead}\n{body}" if idx == 0 and lead else body
            if len(text) <= budget:
                units.append(_Unit(text, clause_no=clause_no))
                continue
            units.extend(self._units_without_clause(text, budget, clause_no=clause_no))
        return units

    def _units_without_clause(
        self, text: str, budget: int, clause_no: Optional[str]
    ) -> List[_Unit]:
        """Một Khoản (hoặc khối không có Khoản) vượt ngưỡng: xuống Điểm."""
        lead, points = self._blocks(text, _POINT_RE)
        if not points:
            parts = self._split_by_length(text, budget)
            if len(parts) == 1:
                return [_Unit(parts[0], clause_no=clause_no)]
            return [
                _Unit(part, clause_no=clause_no, part_no=number)
                for number, part in enumerate(parts, start=1)
            ]

        units: List[_Unit] = []
        for idx, (point_no, body) in enumerate(points):
            # Câu dẫn của Khoản đi cùng Điểm đầu (nó là đầu câu của Khoản);
            # các Điểm sau lấy ngữ cảnh từ ``name`` (".../ Khoản n / Điểm x"),
            # không nhận lại phần thân của Khoản cha.
            point_text = f"{lead}\n{body}" if idx == 0 and lead else body
            if len(point_text) <= budget:
                units.append(
                    _Unit(point_text, clause_no=clause_no, point_no=point_no)
                )
                continue
            for number, part in enumerate(
                self._split_by_length(point_text, budget), start=1
            ):
                units.append(
                    _Unit(
                        part,
                        clause_no=clause_no,
                        point_no=point_no,
                        part_no=number,
                    )
                )
        return units

    # ------------------------------------------------------------------ #
    # metadata
    # ------------------------------------------------------------------ #
    @staticmethod
    def _heading_path(chunk: Chunk) -> List[str]:
        return [seg.strip() for seg in (chunk.name or "").split(" / ") if seg.strip()]

    @classmethod
    def _article_no(cls, heading_path: List[str]) -> Optional[int]:
        """Số Điều của văn bản, hoặc None nếu heading không phải Điều thật.

        Điều trong ``Phụ lục``/``Mẫu`` là điều khoản của biểu mẫu kèm theo, không
        phải Điều của văn bản, nên không được gán số — dựa vào tổ tiên trong
        heading path, không dựa riêng vào regex ``Điều N``.
        """
        if not heading_path:
            return None
        if any(_FORM_ANCESTOR_RE.match(seg) for seg in heading_path[:-1]):
            return None
        hit = _ARTICLE_RE.match(heading_path[-1])
        return int(hit.group(1)) if hit else None

    def _metadata(
        self,
        chunk: Chunk,
        unit: Optional[_Unit],
        split_index: int,
        split_total: int,
    ) -> Dict:
        heading_path = self._heading_path(chunk)
        article_no = self._article_no(heading_path)
        # chunk.kwargs mang sẵn ``source_path`` reader đã gắn -> đi tiếp xuống
        # chunk con, không dựng lại ở đây.
        meta = dict(chunk.kwargs)
        meta.update(
            {
                "heading_path": heading_path,
                "article_no": article_no,
                "split_index": split_index,
                "split_total": split_total,
            }
        )
        # Ngoài Điều thật thì "1."/"a)" chỉ là mục đánh số: không gắn nhãn
        # pháp lý cho chúng.
        if unit is not None and article_no is not None:
            if unit.clause_no is not None:
                meta["clause_no"] = unit.clause_no
            if unit.point_no is not None:
                meta["point_no"] = unit.point_no
        return meta

    # ------------------------------------------------------------------ #
    # dựng chunk
    # ------------------------------------------------------------------ #
    def _unit_name(
        self,
        base: str,
        unit: _Unit,
        legal: bool,
        index: int,
        total: int,
        occurrence: Dict[str, int],
    ) -> str:
        """Tên chunk con = ngữ cảnh pháp lý; đây cũng là title LLM nhận.

        Ngoài Điều thật thì không đặt tên "... / Khoản N" — chỉ đánh
        ``(phần i/N)`` để giữ thứ tự và tránh tên trùng.
        """
        suffix = unit.legal_suffix() if legal else ""
        if not suffix:
            return f"{base} (phần {index}/{total})"
        name = f"{base} / {suffix}"
        if unit.part_no is not None:
            name = f"{name} (phần {unit.part_no})"
        # Biểu mẫu/đoạn đánh số lại từ 1 nhiều lần trong cùng một node nên
        # "Khoản 1" có thể xuất hiện lại. Trùng tên thì thêm số lần lặp.
        seen = occurrence.get(name, 0) + 1
        occurrence[name] = seen
        return name if seen == 1 else f"{name} (lần {seen})"

    def _emit(self, chunk: Chunk, units: List[_Unit]) -> List[Chunk]:
        legal = self._article_no(self._heading_path(chunk)) is not None
        total = len(units)
        output = []
        occurrence: Dict[str, int] = {}
        for index, unit in enumerate(units, start=1):
            output.append(
                Chunk(
                    # split_index là vị trí trong chuỗi đơn vị của chunk cha nên
                    # id luôn phân biệt; đây là runtime chunk id, KHÔNG phải
                    # canonical legal identity (việc của B2).
                    id=generate_hash_id(f"{chunk.id}#{index}"),
                    name=self._unit_name(
                        chunk.name, unit, legal, index, total, occurrence
                    ),
                    # Chỉ thân ngữ nghĩa: heading đã nằm trong name, extractor
                    # ghép lại bằng name + "\n" + content.
                    content=unit.body,
                    type=chunk.type,
                    **self._metadata(chunk, unit, index, total),
                )
            )
        return output

    def _keep(self, chunk: Chunk, content: Optional[str] = None) -> Chunk:
        """Giữ nguyên chunk (id/name/nội dung), chỉ gắn metadata B1."""
        return Chunk(
            id=chunk.id,
            name=chunk.name,
            content=chunk.content if content is None else content,
            type=chunk.type,
            **self._metadata(chunk, None, 1, 1),
        )

    def _heading_only(self, chunk: Chunk) -> List[Chunk]:
        """Heading rỗng thân: phân biệt đơn vị pháp lý với nhãn cấu trúc.

        ``#### Điều 2. Quyết định này có hiệu lực...`` mang chính quy định trong
        heading, nên phải giữ lại đúng một lần. ``Phụ lục I``/``Chương III`` chỉ
        là nhãn: nội dung thật nằm ở các chunk con, nhãn đã có trong heading path
        của chúng, nên không sinh chunk thân rỗng.

        Quy định nằm ở ``name`` (extractor dựng passage từ ``name`` +
        ``content``), nên ``content`` để rỗng: viết lại heading vào ``content``
        là để LLM đọc chính câu đó hai lần.
        """
        heading_path = self._heading_path(chunk)
        leaf = heading_path[-1] if heading_path else ""
        if _ARTICLE_RE.match(leaf) and not _LABEL_RE.match(leaf):
            return [self._keep(chunk, content="")]
        logger.debug("Bo heading nhan cau truc khong co than: %s", chunk.name)
        return []

    @staticmethod
    def _table_parts(content: str, budget: int) -> Optional[List[str]]:
        """Chia bảng markdown theo RANH GIỚI DÒNG, lặp lại header mỗi phần.

        Không dùng ``BaseTableSplitter._split_table`` của vendor: hàm đó cộng
        ``cur_len`` chỉ bằng độ dài các dòng thân, bỏ qua prefix + header lặp
        lại, và kiểm ngưỡng TRƯỚC khi thêm dòng, nên phần sinh ra vượt
        ``chunk_size`` (đo được 11553 ký tự với ngưỡng 4950). Nó còn nhét
        ``#0``/``#LEN`` vào name/id. Ở đây tính đúng phần overhead, giữ nguyên
        văn bản từng dòng (nên giá trị lexical B1.1 như ``5.000`` không đổi) và
        giữ nguyên thứ tự dòng/cột.
        """
        start = content.find("|")
        end = content.rfind("|") + 1
        if start < 0 or start >= end:
            return None
        prefix = content[:start].strip("\n ")
        rows = content[start:end].split("\n")
        suffix = content[end:].strip("\n ")
        if len(rows) < 3:
            return None
        fixed = [line for line in (prefix, rows[0], rows[1]) if line]
        tail = [suffix] if suffix else []
        overhead = sum(len(line) + 1 for line in fixed + tail)

        groups: List[List[str]] = []
        current: List[str] = []
        current_len = overhead
        for row in rows[2:]:
            need = len(row) + 1
            if current and current_len + need > budget:
                groups.append(current)
                current = []
                current_len = overhead
            current.append(row)
            current_len += need
        if current:
            groups.append(current)
        return ["\n".join(fixed + group + tail) for group in groups]

    def _split_oversize_table(self, chunk: Chunk, budget: int) -> List[Chunk]:
        parts = self._table_parts(chunk.content or "", budget)
        if not parts:
            # Không nhận ra là bảng markdown: quay về cắt theo dòng.
            parts = self._split_by_length(chunk.content or "", budget)
        if len(parts) == 1:
            return [self._keep(chunk)]
        return self._emit(
            chunk,
            [_Unit(part, part_no=number) for number, part in enumerate(parts, start=1)],
        )

    def split_structural(self, chunk: Chunk) -> List[Output]:
        """Chia một chunk theo thang cấu trúc."""
        content = chunk.content or ""
        if not content.strip():
            return self._heading_only(chunk)
        if len(content) <= self.split_length:
            return [self._keep(chunk)]

        # Ngưỡng đo trên ``content``: heading không còn nằm trong content nên
        # không phải trừ trước phần prefix nữa. Cùng một thước với nhánh giữ
        # nguyên ở trên (``len(content) <= split_length``).
        budget = self.split_length

        if chunk.type == ChunkTypeEnum.Table:
            return self._split_oversize_table(chunk, budget)

        units = self._units(content, budget)
        if not units:
            return [self._keep(chunk)]
        return self._emit(chunk, units)

    def _invoke(self, input: Chunk, **kwargs) -> List[Output]:
        chunks = input if isinstance(input, list) else [input]
        output: List[Output] = []
        for chunk in chunks:
            output.extend(self.split_structural(chunk))
        return output
