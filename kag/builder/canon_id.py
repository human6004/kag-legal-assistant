# -*- coding: utf-8 -*-
"""id node chuẩn cho mọi thực thể, dùng chung cho cả hai đường nạp đồ thị.

Một thực thể chỉ được có MỘT id, và id đó phải giống nhau ở cả hai đường:
OpenIE (schema_free_extractor.py) và metadata (metadata_to_graph.py).

Vì sao cần. schema_free_extractor ghi mỗi thực thể HAI lần vào cùng một
subgraph: một lần bằng tên thô (schema_free_extractor.py:302 và :312) và một
lần bằng processing_phrases(name) (:424). Hai id khác nhau nên thành hai node,
mà node thô mới giữ quan hệ — node kia chỉ có cạnh source trỏ về chunk. Đo trên
đồ thị thử 4 văn bản: Obligation 419 node = 169 id thô + 250 vỏ rỗng, và 514
cạnh `similar` phần lớn là để nối hai nửa của cùng một thực thể.

Tên văn bản còn nở ra 3-4 biến thể quanh cùng một số hiệu: "Nghị định
329/2026/NĐ-CP" (metadata), "nghị định 329 2026 nđ cp", "Nghị định số
329/2026/NĐ-CP", "nghị định số 329 2026 nđ cp". Bốn node cho một văn bản, nên
status / sourceUrl / supersedes nằm một node còn cạnh về chunk nằm node khác,
không truy vấn nào đi từ bên này sang bên kia.

Phép chuẩn hóa, hai bước:
  1. slug: bỏ dấu câu, viết thường, GIỮ chữ có dấu tiếng Việt; rồi gộp khoảng
     trắng (slug biến mỗi dấu câu thành một dấu cách).
  2. nếu chuỗi MỞ ĐẦU bằng một loại văn bản và có số hiệu <số> <năm> <mã> thì
     quy về "<loại> <số> <năm> <mã>", bỏ chữ "số" và mọi tên riêng chen giữa.
     "Luật An ninh mạng số 116/2025/QH15" và "Luật 116/2025/QH15" về cùng một id.

Bước 2 chạy trên chuỗi ĐÃ slug chứ không phải chuỗi gốc, vì schema_free_extractor
gọi processing_phrases(name) trước rồi mới đưa id vào (:424), lúc đó dấu "/" đã
thành dấu cách. Tìm số hiệu trên chuỗi gốc thì dạng "nghị định số 329 2026 nđ cp"
không khớp gì cả và vẫn thành node riêng.

Bước 2 chỉ chạy khi loại văn bản đứng ĐẦU chuỗi. Không có điều kiện đó thì
"Điều 5 Nghị định 329/2026/NĐ-CP" sẽ bị quy về id của chính nghị định 329.

Chỉ áp cho thực thể. Chunk / Table / Summary / Outline giữ nguyên id do tầng
reader sinh ra (băm sha256 kèm hậu tố #4950#table#0#LEN) — xem KEEP_ID.

Chạy self-check: python builder/canon_id.py
"""

import hashlib
import re
import json
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple, Optional, Tuple

__all__ = [
    "slug",
    "canon_id",
    "source_document_id",
    "article_identity",
    "KEEP_ID",
    "Identity",
    "CONTEXTUAL_CATEGORIES",
    "SEMANTIC_CATEGORIES",
    "IDENTITY_PREFIXES",
    "semantic_identity",
    "unresolved_identity",
    "is_semantic_identity",
    "normalize_source_phrase",
    "source_phrase_count",
]

# Nhãn giữ nguyên id gốc. Đây là các node do tầng reader/splitter sinh ra, id là
# băm chứ không phải tên, đổi đi là mất liên hệ với chunk và với chỉ mục vector.
KEEP_ID = {
    "Chunk",
    "Table",
    "Summary",
    "Outline",
    "KnowledgeUnit",
    "AtomicQuery",
    "Doc",
}

# Loại văn bản. Xếp dài trước để "bộ luật" không bị "luật" chen ngang.
_DOC_KINDS = (
    "bộ luật",
    "luật",
    "nghị định",
    "nghị quyết",
    "thông tư",
    "quyết định",
    "pháp lệnh",
    "hiến pháp",
    "sắc lệnh",
    "chỉ thị",
)

# Mã văn bản đứng sau năm ban hành. Hai dạng có thật:
#   QH15, QH14  — chữ rồi số, một token
#   NĐ-CP, TT-BKHCN, QĐ-TTg — hai token ngắn, sau slug thành "nđ cp", "tt bkhcn"
# Token đầu phải bắt đầu bằng CHỮ để "329 2026 15" không bị nhận nhầm là văn bản.
_DOC_CODE = r"(?:[a-zđ]{1,3}\d{1,3}|[a-zđ]{1,4} [a-zđ]{2,6})"

# Số hiệu, tìm trên chuỗi ĐÃ slug: "116/2025/QH15" -> "116 2025 qh15".
_DOC_NUMBER = re.compile(rf"\b(\d{{1,5}}) (\d{{4}}) ({_DOC_CODE})")
_NO_YEAR_DECISION = re.compile(r"^quyết định (?:số )?(\d{1,5}) qđ ttg(?:$| )")

_SPACES = re.compile(r"\s+")


def slug(phrase):
    r"""Bỏ dấu câu, viết thường, giữ chữ có dấu: \w ở chế độ Unicode.

    Đây là bản vá của kag.common.utils.processing_phrases (bản gốc chỉ giữ
    [A-Za-z0-9 CJK] nên "Luật" thành "lu t"). kag/builder/__init__.py gắn đè
    hàm này vào schema_free_extractor.
    """
    return re.sub(r"[^\w ]", " ", str(phrase).lower(), flags=re.U).strip()


def canon_id(phrase):
    """id chuẩn của một thực thể. Không đổi gì nếu không nhận ra số hiệu văn bản."""
    s = _SPACES.sub(" ", slug(phrase))

    # Quyết định dạng <số>/QĐ-TTg trong corpus không chứa năm. Chỉ nhận
    # mã QĐ-TTg đủ cụ thể, không rút gọn câu thường có chữ "quyết định".
    no_year = _NO_YEAR_DECISION.match(s)
    if no_year:
        return f"quyết định {no_year.group(1)} qđ ttg"

    m = _DOC_NUMBER.search(s)
    if not m:
        return s

    head = s[: m.start()].strip()
    kind = next(
        (k for k in _DOC_KINDS if head == k or head.startswith(k + " ")), None
    )
    if not kind:
        return s

    return f"{kind} {m.group(1)} {m.group(2)} {m.group(3)}"


@lru_cache(maxsize=None)
def source_document_id(source_path):
    """Map đường dẫn Reader portable vào doc_id; chỉ nhận file đã có metadata."""
    path = Path(str(source_path).replace("\\", "/"))
    parts = str(source_path).replace("\\", "/").split("/")
    if len(parts) != 4 or parts[:2] != ["data", "processed"] or path.suffix != ".md":
        return None
    doc_id, sep, _ = path.stem.partition("_")
    if not sep or not re.fullmatch(r"[A-Za-z0-9-]+", doc_id):
        return None
    meta_path = Path(__file__).resolve().parents[2] / "data" / "metadata" / f"{doc_id}.json"
    if not meta_path.is_file():
        return None
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    raw_paths = [meta.get("raw_file", ""), *(meta.get("raw_files") or [])]
    if meta.get("doc_id") != doc_id or not any(
        Path(raw).stem == path.stem and Path(raw).parent.name == parts[2]
        for raw in raw_paths if raw
    ):
        return None
    return doc_id


def document_node_name(meta):
    """Tên node LegalDocument, phải trùng cách LLM gọi văn bản (xem prompt legal_std).

    Là tên HIỂN THỊ, không phải id: `canon_id()` mới quy nó về id. Hai đường nạp
    dùng chung hàm này (`metadata_to_graph.py` và extractor) để không có đường
    nào tự đặt tên khác rồi nở ra node thứ hai cho cùng một văn bản.
    """
    number = (meta.get("doc_number") or "").strip()
    if not number:
        return (meta.get("title") or "").strip()
    doc_type = (meta.get("doc_type") or "").strip()
    if meta.get("jurisdiction") == "VN" and doc_type:
        return f"{doc_type} {number}"
    return number


@lru_cache(maxsize=None)
def source_document_name(doc_id):
    """doc_id -> tên node LegalDocument của nó, hoặc None nếu không có metadata.

    Chỉ đọc `data/metadata`, không suy từ tên file và không hỏi LLM: đây là
    đường tất định để một Điều NGUỒN biết mình thuộc văn bản nào.
    """
    if not isinstance(doc_id, str) or not re.fullmatch(r"[A-Za-z0-9-]+", doc_id):
        return None
    meta_path = Path(__file__).resolve().parents[2] / "data" / "metadata" / f"{doc_id}.json"
    if not meta_path.is_file():
        return None
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("doc_id") != doc_id:
        return None
    return document_node_name(meta) or None


def article_identity(doc_id, article_no):
    """Danh tính Điều đã được xác định nguồn; độc lập tên hiển thị/chunk."""
    if not isinstance(doc_id, str) or not re.fullmatch(r"[A-Za-z0-9-]+", doc_id) or not str(article_no).isdigit():
        raise ValueError("Article cần doc_id và article_no hợp lệ")
    number = int(article_no)
    if number < 1:
        raise ValueError("article_no phải dương")
    return f"article:{doc_id}:{number}"


@lru_cache(maxsize=None)
def source_article_headings(source_path):
    """Điều nguồn theo dãy số liên tiếp; heading chen ngang là trích dẫn chưa rõ đích."""
    # ponytail: 23 văn bản hiện có đánh số Điều nguồn 1..N; tài liệu nhảy số
    # sẽ để unresolved. Chỉ mở rộng parser khi có case thật cần phân giải.
    if not source_document_id(source_path):
        return frozenset()
    path = Path(__file__).resolve().parents[2] / source_path
    headings = {}
    source, next_number = set(), 1
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^(#{1,6})\s+(.+)", line)
        if not match:
            continue
        level, title = len(match.group(1)), match.group(2).strip()
        headings = {k: v for k, v in headings.items() if k < level}
        if not any(re.match(r"^(?:Phụ lục|Mẫu|Biểu mẫu)\b", h, re.I) for h in headings.values()):
            article = re.match(r"^Điều\s+(\d{1,3})\b", title)
            if article:
                number = int(article.group(1))
                if number == next_number:
                    source.add((number, title))
                    next_number += 1
        headings[level] = title
    return frozenset(source)


#  B2.2 — danh tính ngữ nghĩa cho thực thể phụ thuộc ngữ cảnh
# ---------------------------------------------------------------------------
# Bài toán: `canon_id()` chuẩn hóa TÊN, nên mọi thực thể trùng tên về một node.
# Với tên văn bản đó là đúng (một văn bản một id), với chế tài/nghĩa vụ/hành vi
# thì sai: "Phạt tiền từ 10.000.000 đồng đến 20.000.000 đồng" xuất hiện ở Điều
# 9, 10 và 11 của cùng một nghị định là BA chế tài khác nhau, gộp lại thì Điều 9
# thừa hưởng hành vi của Điều 11.
#
# Quy tắc chung, không có ngoại lệ:
#
#     đủ bằng chứng deterministic  -> danh tính canonical
#     không đủ                     -> danh tính unresolved
#
# Không đoán. Không gộp vì trùng tên. Không tách vì khác chunk.
#
# Hai họ danh tính:
#
# * Authority — danh tính TOÀN CỤC theo tổ chức. "Bộ Công an" ở mọi văn bản là
#   một cơ quan. Không dùng văn bản/Điều làm material, nếu không thì mỗi lần
#   nhắc lại là một cơ quan mới.
# * Sanction / Obligation / ProhibitedAct / LegalTerm / RegulatedEntity —
#   danh tính THEO CĂN CỨ (legal occurrence). Material là căn cứ pháp lý đã
#   phân giải cộng với đoạn văn nguồn, không phải tên hiển thị.
#
# Bằng chứng nào được tính. Pipeline hiện KHÔNG có character offset / mention
# span: triple chỉ mang tên hai đầu mút. Nên bằng chứng duy nhất kiểm được bằng
# code là "tên thực thể khớp DUY NHẤT MỘT lần vào VĂN BẢN NGUỒN của Điều". Khớp
# 0 lần nghĩa là LLM diễn giải lại, khớp nhiều lần nghĩa là không biết lần nào —
# cả hai đều ra unresolved. Đây là chỗ cố tình không dùng fuzzy match: một phép
# khớp gần đúng sẽ sinh id canonical cho thứ không chứng minh được.
#
# Hai tính bất biến BẮT BUỘC của id canonical:
#
# 1. Bất biến với cấu hình chunk. Điểm neo Khoản/Điểm được quét TỪ FILE NGUỒN
#    (`source_article_units`), không lấy `chunk.kwargs["clause_no"]`. Đổi
#    cut_depth/ngưỡng của splitter không đổi id. `chunk.id`, `split_index`,
#    đường dẫn tuyệt đối không bao giờ vào material canonical.
# 2. Bất biến với cách LLM cắt chữ. Tên NER chỉ dùng để ĐỊNH VỊ duy nhất một
#    đơn vị văn bản nguồn; material canonical là chính đơn vị nguồn đó. Hai span
#    dài ngắn khác nhau của cùng một dòng nguồn cho cùng một id.
#
# Giá của (2): hai occurrence cùng nhãn nằm cùng một dòng nguồn sẽ gộp về một
# id. Không phân biệt được với "hai span của một occurrence" khi thiếu mention
# span, nên chọn gộp — xem Hạn chế trong report.
#
# Chuẩn hóa được phép mất: hoa/thường, khoảng trắng, dấu nháy, dấu đánh mục đầu
# dòng ("1. ", "a) ") — hợp đồng NER đã bỏ các dấu này. KHÔNG được mất: số tiền,
# phủ định, điều kiện, thời hạn, tỷ lệ, chủ thể. Vì vậy `_STRUCTURAL_MARKER`
# đòi khoảng trắng sau dấu chấm: "10.000.000 đồng" không bị cắt thành "000.000".

# Thực thể phụ thuộc căn cứ pháp lý. Authority đứng ngoài: nó toàn cục.
CONTEXTUAL_CATEGORIES = (
    "Sanction",
    "Obligation",
    "ProhibitedAct",
    "LegalTerm",
    "RegulatedEntity",
)

# Mọi nhãn do resolver này cấp id. Article do B2.1 cấp, giữ nguyên.
SEMANTIC_CATEGORIES = ("Authority",) + CONTEXTUAL_CATEGORIES

# namespace id theo nhãn. Dạng "<ns>:..." là canonical, "<ns>-unresolved:..."
# là chưa phân giải. `builder/__init__.py` dựa vào đây để KHÔNG slug hóa id đã
# mang namespace; tên thô chưa phân giải thì vẫn phải đi qua canon_id().
IDENTITY_PREFIXES = {
    "Article": "article",
    "Authority": "authority",
    "Sanction": "sanction",
    "Obligation": "obligation",
    "ProhibitedAct": "prohibitedact",
    "LegalTerm": "legalterm",
    "RegulatedEntity": "regulatedentity",
}

_QUOTES = dict.fromkeys(map(ord, "\"'“”‘’«»"), None)

# Dấu đánh mục đầu dòng. PHẢI có khoảng trắng sau dấu chấm, nếu không thì
# "10.000.000 đồng đến 20.000.000 đồng" bị cắt mất chữ số hàng triệu.
_STRUCTURAL_MARKER = re.compile(r"^(?:\d{1,3}\.|[a-zđ]\)|[-–•])\s+")

# Dấu Khoản/Điểm đọc từ file nguồn. Cùng ràng buộc khoảng trắng như trên.
_SOURCE_CLAUSE = re.compile(r"^(\d{1,3})\.\s+")
_SOURCE_POINT = re.compile(r"^([a-zđ])\)\s+")

# Chức danh: người/vai, không phải tổ chức. Phải xét TRƯỚC loại tổ chức vì
# "bộ trưởng bộ công an" cũng mở đầu bằng "bộ ".
_PERSON_TITLES = (
    "bộ trưởng", "thứ trưởng", "thủ tướng", "phó thủ tướng", "chủ tịch",
    "phó chủ tịch", "cục trưởng", "tổng cục trưởng", "vụ trưởng", "giám đốc",
    "chánh án", "phó chánh án", "viện trưởng", "phó viện trưởng",
    "chánh thanh tra", "trưởng ban", "trưởng đoàn", "người đứng đầu",
    "thủ trưởng", "tổng giám đốc", "tổng thanh tra",
)

# Tổ chức đầu mối. Chuỗi phải MỞ ĐẦU bằng một trong các loại này, nên
# "Thanh tra Bộ Công an" và "Cục An ninh mạng ... Bộ Công an" không lọt vào.
_ORG_KINDS = (
    "bộ", "chính phủ", "quốc hội", "ủy ban thường vụ quốc hội",
    "ủy ban nhân dân", "hội đồng nhân dân", "tòa án nhân dân",
    "viện kiểm sát nhân dân", "ngân hàng nhà nước", "kiểm toán nhà nước",
    "văn phòng chính phủ", "thanh tra chính phủ", "chủ tịch nước",
)

# Tổ chức nói chung, không rõ là cơ quan nào. Gộp các chuỗi này lại là gộp
# UBND của mọi tỉnh vào một node.
_AMBIGUOUS_ORG = frozenset({
    "bộ", "cơ quan", "cơ quan nhà nước", "cơ quan có thẩm quyền",
    "cơ quan quản lý", "cơ quan quản lý nhà nước", "nhà nước", "chính quyền",
    "ủy ban", "ủy ban nhân dân", "hội đồng nhân dân", "tòa án nhân dân",
    "viện kiểm sát nhân dân", "tòa án", "viện kiểm sát", "thanh tra",
    "người có thẩm quyền", "cấp có thẩm quyền",
})

# Điều xác định phạm vi/đối tượng. Chỉ ở đây mới coi là đã chứng minh scope của
# một RegulatedEntity; ở Điều khác thì "tổ chức, cá nhân" chỉ là lần nhắc.
_SCOPE_HEADINGS = ("đối tượng áp dụng", "phạm vi điều chỉnh", "phạm vi áp dụng")


class Identity(NamedTuple):
    """Kết quả phân giải. `material` để test/debug xem được TRƯỚC khi băm."""

    id: Optional[str]
    material: Tuple[str, ...]
    reason: str


def _norm_text(text):
    """Chuẩn hóa để SO KHỚP. Mất hoa/thường, khoảng trắng, dấu nháy."""
    normalized = unicodedata.normalize("NFC", str(text)).translate(_QUOTES)
    return _SPACES.sub(" ", normalized).strip().casefold()


def normalize_source_phrase(text):
    """Như `_norm_text` nhưng bỏ thêm dấu đánh mục đầu chuỗi."""
    return _STRUCTURAL_MARKER.sub("", _norm_text(text), count=1).strip()


def source_phrase_count(name, content):
    """Số lần tên thực thể khớp vào văn bản nguồn. 1 = phân giải được."""
    needle = normalize_source_phrase(name)
    if not needle:
        return 0
    return _norm_text(content).count(needle)


class SourceUnit(NamedTuple):
    """Một đơn vị văn bản trong Điều nguồn, kèm điểm neo pháp lý của nó."""

    clause_no: Optional[int]
    point_no: Optional[str]
    text: str


@lru_cache(maxsize=None)
def source_article_units(source_path, article_no):
    """Các đơn vị văn bản của một Điều, đọc TRỰC TIẾP từ file nguồn.

    Khoản/Điểm suy ra từ dấu đánh mục trong chính file nguồn, nên không phụ
    thuộc splitter đang cắt tới cấp nào. Trả `()` khi không chứng minh được
    thân Điều: chưa có metadata, Điều không nằm trong dãy số liên tiếp, hoặc
    tài liệu có nhiều heading cùng số Điều (trích dẫn sửa đổi) — lúc đó không
    biết thân nào là thân thật nên để tầng trên ra unresolved.
    """
    if not source_document_id(source_path) or not str(article_no or "").isdigit():
        return ()
    titles = [t for n, t in source_article_headings(source_path) if n == int(article_no)]
    if len(titles) != 1:
        return ()
    path = Path(__file__).resolve().parents[2] / source_path
    blocks, body = [], None
    for line in path.read_text(encoding="utf-8").splitlines():
        heading = re.match(r"^#{1,6}\s+(.+)", line)
        if heading:
            if body is not None:
                blocks.append(body)
            body = [] if heading.group(1).strip() == titles[0] else None
            continue
        if body is not None:
            body.append(line)
    if body is not None:
        blocks.append(body)
    if len(blocks) != 1:
        return ()

    body_lines = blocks[0]
    if not any(_norm_text(line) for line in body_lines):
        # 6 Điều trong corpus có toàn văn nằm ngay trên dòng heading (QĐ-TTg
        # một Điều, Luật 71/2025 Điều 46). Lấy chính phần sau "Điều N." làm
        # đơn vị duy nhất: vẫn là văn bản nguồn, không đoán chỗ cắt tiêu đề.
        body_lines = [re.sub(r"^Điều\s+\d{1,3}\.\s*", "", titles[0])]

    units, clause, point = [], None, None
    for line in body_lines:
        text = normalize_source_phrase(line)
        if not text:
            continue
        marker = _norm_text(line)
        clause_mark = _SOURCE_CLAUSE.match(marker)
        if clause_mark:
            # Sang Khoản mới thì Điểm của Khoản cũ hết hiệu lực.
            clause, point = int(clause_mark.group(1)), None
        else:
            point_mark = _SOURCE_POINT.match(marker)
            if point_mark:
                point = point_mark.group(1)
        units.append(SourceUnit(clause, point, text))
    return tuple(units)


class SourceOccurrence(NamedTuple):
    """Khóa occurrence nguồn. Soi được bằng mắt TRƯỚC khi băm.

    Chỉ chứa thứ suy được từ văn bản nguồn: `doc_id`, số Điều, điểm neo
    Khoản/Điểm nếu chứng minh được, và đơn vị văn bản nguồn. KHÔNG chứa
    `chunk.id`, `split_index`, đường dẫn tuyệt đối, `official_name` của LLM,
    hay cách diễn giải lại của NER. `unit` rỗng nghĩa là chưa phân giải.
    """

    doc_id: Optional[str]
    article_no: Optional[int]
    clause_no: Optional[int]
    point_no: Optional[str]
    unit: str
    reason: str


def source_occurrence(name, source_path, article_no, *, definition=False):
    """Tên NER -> đúng MỘT đơn vị văn bản nguồn, hoặc không gì cả.

    Tên chỉ để định vị. Không fuzzy match: khớp 0 lần, khớp nhiều dòng, hay
    khớp nhiều lần trong cùng một dòng đều trả `unit` rỗng. Thất bại bảo toàn
    được chấp nhận — đoán thì sinh id canonical cho thứ không chứng minh được.
    """
    doc_id = source_document_id(source_path)
    empty = SourceOccurrence(doc_id, None, None, None, "", "")
    if not doc_id or not str(article_no or "").isdigit():
        return empty._replace(reason="chưa phân giải được căn cứ pháp lý")
    number = int(article_no)
    units = source_article_units(source_path, number)
    if not units:
        return empty._replace(article_no=number, reason="không xác định được thân Điều nguồn")
    needle = normalize_source_phrase(name)
    if not needle:
        return empty._replace(article_no=number, reason="tên rỗng")

    if definition:
        # Dòng ĐỊNH NGHĨA, không phải lần nhắc. Không dùng `"<term> là" in text`:
        # câu "bảo vệ an ninh mạng là trách nhiệm của..." cũng chứa "an ninh
        # mạng là" mà không định nghĩa gì.
        hits = [u for u in units if u.text.startswith(needle + " là ")]
        total, label = len(hits), "dòng định nghĩa nguồn"
    else:
        hits = [u for u in units if needle in u.text]
        total = sum(u.text.count(needle) for u in units)
        label = "khớp văn bản nguồn"
    if total != 1 or len(hits) != 1:
        return empty._replace(
            article_no=number, reason=f"{label} {total} lần, cần đúng 1"
        )
    unit = hits[0]
    return SourceOccurrence(
        doc_id, number, unit.clause_no, unit.point_no, unit.text, "phân giải theo đơn vị nguồn"
    )


def _scope_article(source_path, article_no):
    """Điều nguồn có tiêu đề xác định phạm vi/đối tượng áp dụng hay không."""
    titles = [
        t for n, t in source_article_headings(source_path)
        if str(article_no or "").isdigit() and n == int(article_no)
    ]
    return len(titles) == 1 and any(
        key in _norm_text(titles[0]) for key in _SCOPE_HEADINGS
    )


def _digest(*parts):
    """Băm ổn định cross-process. KHÔNG dùng hash() built-in (có PYTHONHASHSEED)."""
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:16]


def _authority_identity(name):
    """Danh tính tổ chức toàn cục, hoặc None khi không chứng minh được."""
    text = _SPACES.sub(" ", slug(name))
    if not text:
        return Identity(None, (), "authority:tên rỗng")
    if any(text == title or text.startswith(title + " ") for title in _PERSON_TITLES):
        # Chức danh không phải tổ chức. "Bộ trưởng Bộ Công an" KHÁC "Bộ Công an".
        return Identity(None, (), "authority:chức danh, không phải tổ chức")
    if " thuộc " in f" {text} ":
        # Đơn vị trực thuộc. Không có bảng mapping deterministic thì không gộp
        # vào cơ quan chủ quản, cũng không tự cấp danh tính toàn cục.
        return Identity(None, (), "authority:đơn vị trực thuộc, chưa có mapping")
    if text in _AMBIGUOUS_ORG:
        return Identity(None, (), "authority:tổ chức nói chung, không rõ cơ quan")
    kind = next(
        (k for k in _ORG_KINDS if text == k or text.startswith(k + " ")), None
    )
    if not kind:
        return Identity(None, (), "authority:không mở đầu bằng loại cơ quan")
    return Identity(f"authority:{text}", ("Authority", text), "authority:tổ chức")


def semantic_identity(
    category,
    name,
    *,
    source_path="",
    article_no=None,
    clause_no=None,
    point_no=None,
):
    """Một resolver dùng chung cho node và cả hai đầu mút cạnh.

    Trả về `Identity`. `id is None` nghĩa là bằng chứng không đủ; tầng gọi phải
    dùng `unresolved_identity()`, KHÔNG được tự bịa số thứ tự occurrence.

    Material canonical lấy từ VĂN BẢN NGUỒN (`source_occurrence`), không lấy tên
    NER và không lấy metadata của splitter. `clause_no`/`point_no` của B1 chỉ là
    hint để đối chiếu, ghi vào `reason`; chúng KHÔNG vào material nên đổi cấu
    hình cắt chunk không đổi id.
    """
    if category == "Authority":
        return _authority_identity(name)
    if category not in CONTEXTUAL_CATEGORIES:
        return Identity(None, (), "nhãn không do resolver này cấp id")

    occurrence = source_occurrence(
        name, source_path, article_no, definition=(category == "LegalTerm")
    )
    if not occurrence.unit:
        return Identity(None, (), occurrence.reason)
    if category == "RegulatedEntity" and not _scope_article(source_path, article_no):
        # Ở Điều khác, "tổ chức, cá nhân" chỉ là lần nhắc, chưa chứng minh scope.
        return Identity(None, (), "chưa chứng minh được scope của đối tượng")

    anchor = [occurrence.doc_id, str(occurrence.article_no)]
    if occurrence.clause_no is not None:
        anchor.append(f"k{occurrence.clause_no}")
    if occurrence.point_no is not None:
        anchor.append(f"p{occurrence.point_no}")
    material = (category, *anchor, occurrence.unit)
    head = ":".join([IDENTITY_PREFIXES[category], *anchor])

    reason = occurrence.reason
    hints = (("khoản", clause_no, occurrence.clause_no), ("điểm", point_no, occurrence.point_no))
    lech = [
        f"{ten} B1 {b1} lệch nguồn {nguon}"
        for ten, b1, nguon in hints
        if b1 is not None and str(b1) != str(nguon)
    ]
    if lech:
        # Không để hint quyết định id, chỉ báo để soi lại splitter.
        reason = f"{reason}; {', '.join(lech)}"
    return Identity(f"{head}:{_digest(*material)}", material, reason)


def unresolved_identity(category, chunk_id, name):
    """Danh tính CHƯA phân giải. KHÔNG phải danh tính pháp lý canonical.

    Chỉ nói "trong chunk này có một thực thể tên như vậy mà chưa chứng minh
    được nó là occurrence nào". Có `chunk_id` để hai chunk khác nhau không bị
    gộp khi bằng chứng mơ hồ — và vì thế nó KHÔNG chứng minh cardinality: một
    placeholder không có nghĩa trong chunk chỉ có một occurrence.
    """
    namespace = IDENTITY_PREFIXES.get(category)
    if not namespace:
        raise ValueError(f"nhãn {category!r} không có namespace danh tính")
    return f"{namespace}-unresolved:{_digest(str(chunk_id), canon_id(name))}"


def is_semantic_identity(node_id, label):
    """id đã mang namespace của resolver thì giữ nguyên, không slug hóa nữa."""
    namespace = IDENTITY_PREFIXES.get(str(label).split(".")[-1])
    if not namespace:
        return False
    return str(node_id).startswith((f"{namespace}:", f"{namespace}-unresolved:"))


def _self_check():
    """Ca thật lấy từ đồ thị thử 121 chunk. Không gọi mạng, không đụng Neo4j."""
    same = [
        # (tên LLM viết, tên metadata, id chờ đợi)
        ("Nghị định 329/2026/NĐ-CP", "Nghị định 329/2026/NĐ-CP", "nghị định 329 2026 nđ cp"),
        ("Nghị định số 329/2026/NĐ-CP", "Nghị định 329/2026/NĐ-CP", "nghị định 329 2026 nđ cp"),
        ("Luật An ninh mạng số 116/2025/QH15", "Luật 116/2025/QH15", "luật 116 2025 qh15"),
        ("Luật 116/2025/QH15", "Luật 116/2025/QH15", "luật 116 2025 qh15"),
        ("Thông tư số 05/2026/TT-BKHCN", "Thông tư 05/2026/TT-BKHCN", "thông tư 05 2026 tt bkhcn"),
        ("Bộ luật Hình sự số 100/2015/QH13", "Bộ luật 100/2015/QH13", "bộ luật 100 2015 qh13"),
        (
            "Luật Sửa đổi, bổ sung một số điều của Luật Dầu khí số 10/2008/QH12",
            "Luật 10/2008/QH12",
            "luật 10 2008 qh12",
        ),
        # schema_free_extractor.py:424 đưa vào id ĐÃ slug, mất dấu "/" — dạng này
        # cũng phải gộp, nếu không thì mỗi tên văn bản còn hai node.
        ("nghị định số 329 2026 nđ cp", "nghị định 329 2026 nđ cp", "nghị định 329 2026 nđ cp"),
        ("luật an ninh mạng số 116 2025 qh15", "luật 116 2025 qh15", "luật 116 2025 qh15"),
        # Tên văn bản bị LLM viết thêm vế mô tả phía sau.
        ("Luật 116/2025/QH15 quy định về an ninh mạng", "Luật 116/2025/QH15", "luật 116 2025 qh15"),
    ]
    for llm, meta, want in same:
        got_llm, got_meta = canon_id(llm), canon_id(meta)
        assert got_llm == want, f"canon_id({llm!r}) = {got_llm!r}, chờ đợi {want!r}"
        assert got_meta == want, f"canon_id({meta!r}) = {got_meta!r}, chờ đợi {want!r}"
        print(f"  hai đường gặp nhau: {llm!r} -> {got_llm!r}")

    # Thô và slug của cùng một thực thể phải về một id.
    for name in [
        "Bảo vệ dữ liệu cá nhân, bí mật đời tư, thông tin mật và bí mật kinh doanh",
        "Điều 3. Giải thích (từ ngữ)",
    ]:
        assert canon_id(name) == canon_id(f" {name} "), name
        print(f"  thô = slug        : {name!r} -> {canon_id(name)!r}")

    # Bài học từ vụ "Điều 5 Nghị định 329": số hiệu không đứng sau loại văn bản
    # thì KHÔNG được quy về văn bản.
    di_doi = [
        ("Điều 5 Nghị định 329/2026/NĐ-CP", "điều 5 nghị định 329 2026 nđ cp"),
        ("Khoản 2 Điều 7 Thông tư 05/2026/TT-BKHCN", "khoản 2 điều 7 thông tư 05 2026 tt bkhcn"),
        ("19/2023/QH15", "19 2023 qh15"),
        ("Hiến pháp", "hiến pháp"),
    ]
    for goc, want in di_doi:
        got = canon_id(goc)
        assert got == want, f"canon_id({goc!r}) = {got!r}, chờ đợi {want!r}"
        print(f"  không gộp bừa      : {goc!r} -> {got!r}")

    # B2.2 — thực thể phụ thuộc căn cứ. Cùng câu chữ, khác Điều -> khác id.
    # Đọc TRỰC TIẾP file nguồn trong corpus, không dựng content giả.
    nd330 = next(
        (Path(__file__).resolve().parents[2] / "data" / "processed").rglob("330-2026-ND-CP_*.md")
    )
    nguon = "data/processed/" + nd330.parent.name + "/" + nd330.name
    fine = "Phạt tiền từ 10.000.000 đồng đến 20.000.000 đồng"
    occurrences = [
        semantic_identity("Sanction", fine, source_path=nguon, article_no=number)
        for number in (9, 10, 11)
    ]
    assert all(o.id for o in occurrences), occurrences
    assert len({o.id for o in occurrences}) == 3, [o.id for o in occurrences]
    print(f"  chế tài theo căn cứ : 3 Điều cùng câu chữ -> {len({o.id for o in occurrences})} id")

    # Số tiền KHÔNG được chuẩn hóa mất. "10.000.000" cũng không bị dấu đánh mục
    # ăn mất chữ số: marker chỉ khớp khi có khoảng trắng sau dấu chấm.
    assert normalize_source_phrase(f"2. {fine}") == normalize_source_phrase(fine)
    assert "10.000.000" in normalize_source_phrase(fine)
    khac = semantic_identity("Sanction", "Phạt tiền từ 5.000.000 đồng đến 10.000.000 đồng",
                             source_path=nguon, article_no=9)
    assert khac.id and khac.id != occurrences[0].id
    print("  số tiền giữ nguyên  : khoản 1 (5-10tr) và khoản 2 (10-20tr) khác id")

    # Bất biến cấu hình chunk: hint khoản của splitter không vào material.
    assert semantic_identity("Sanction", fine, source_path=nguon, article_no=9,
                             clause_no=2).id == occurrences[0].id
    assert occurrences[0].id.startswith("sanction:330-2026-ND-CP:9:k2:"), occurrences[0]
    print("  bất biến chunk      : clause_no None/2 -> cùng id, neo k2 đọc từ nguồn")

    # Bất biến câu chữ NER: hai span của cùng một dòng nguồn -> cùng id.
    dai = semantic_identity("Sanction", fine + " đối với các hành vi sau đây",
                            source_path=nguon, article_no=9)
    assert dai.id == occurrences[0].id, (dai, occurrences[0])
    print("  bất biến câu chữ NER: span dài/ngắn cùng dòng nguồn -> cùng id")

    # Diễn giải lại (khớp 0 lần) và tên mơ hồ (khớp nhiều lần) đều KHÔNG được
    # cấp id canonical.
    for ten, ten_goi in (("Phạt tiền 10-20 triệu đồng", "khớp 0 lần"),
                         ("Phạt tiền từ", "khớp nhiều lần")):
        mo_ho = semantic_identity("Sanction", ten, source_path=nguon, article_no=9)
        assert mo_ho.id is None, (ten_goi, mo_ho)
        print(f"  {ten_goi:<20}: {mo_ho.reason}")

    # Authority toàn cục, nhưng chức danh và đơn vị trực thuộc thì KHÔNG gộp.
    bca = semantic_identity("Authority", "Bộ Công an")
    assert bca.id == "authority:bộ công an", bca
    assert semantic_identity("Authority", "BỘ CÔNG AN").id == bca.id
    for am in ("Bộ trưởng Bộ Công an", "Cục An ninh mạng thuộc Bộ Công an",
               "Thanh tra Bộ Công an", "Ủy ban nhân dân", "cơ quan có thẩm quyền"):
        got = semantic_identity("Authority", am)
        assert got.id != bca.id, (am, got)
        assert got.id is None, (am, got)
    print(f"  cơ quan toàn cục    : {bca.id!r}; chức danh/đơn vị trực thuộc -> unresolved")

    # unresolved ổn định trong cùng chunk, không gộp xuyên chunk.
    a = unresolved_identity("Sanction", "chunk-1", fine)
    assert a == unresolved_identity("Sanction", "chunk-1", fine)
    assert a != unresolved_identity("Sanction", "chunk-2", fine)
    assert a.startswith("sanction-unresolved:")
    assert is_semantic_identity(a, "Sanction") and not is_semantic_identity(fine, "Sanction")
    print(f"  unresolved ổn định  : {a!r}")

    print("[self-check ok] một thực thể một id, hai đường nạp gặp nhau")
    return 0


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")  # console Windows mặc định cp1252
    sys.exit(_self_check())
