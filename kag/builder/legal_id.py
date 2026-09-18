# -*- coding: utf-8 -*-
"""Định danh có phạm vi cho LegalDocument / Article / Clause / Point.

Vì sao cần file này. `canon_id.py` gộp thực thể theo TÊN, nên "Điều 2" của Nghị
định 328 và "Điều 2" của Thông tư 05 về cùng một node. Đo trên snapshot
17/09/2026: 102 node tên "Điều N" trần, trung bình ~12 ngữ cảnh văn bản; node
`điều 14` một mình giữ 182 cạnh đi ra từ ít nhất 4 văn bản khác nhau
(NĐ 341, NĐ 328, Luật 86/2015, NĐ 329). Node `điều 2` xuất hiện ở 21 văn bản.

Đây KHÔNG phải lỗi của canon_id: nó chỉ làm đúng việc gộp theo tên. Lỗi là tên
"Điều 2" trần không đủ để định danh. File này bổ sung phần còn thiếu.

Ba tầng định danh:

  doc_key(document)   phạm vi văn bản/phiên bản. Chỉ sinh khi có BẰNG CHỨNG
                      (số hiệu, hoặc tên+ngày). Không đoán từ tên gần giống.
  article_id(doc, so) "dieu:<doc_key>#<so>"  — khóa Điều theo văn bản.
  clause/point_id     "khoan:<article_id>#<so>" / "diem:<clause_id>#<ky tu>"

Nguyên tắc bắt buộc:

1. Không gộp chỉ vì tên canonical trùng. Hai văn bản khác nhau có "Điều 2" là
   hai node khác nhau.
2. Giữ ID cũ để truy ngược: mọi bản ghi mapping đều lưu `legacy_id`.
3. Văn bản chưa đủ bằng chứng định danh thì `doc_key = None` và Article giữ
   trạng thái CHUA_PHAN_GIAI. KHÔNG chọn một văn bản để lấp chỗ trống.
4. Phân biệt "Điều của văn bản đang đọc" với "Điều được dẫn chiếu": chỉ dạng
   thứ nhất mới tạo node Article thuộc văn bản; dạng thứ hai là trích dẫn.

Chạy self-check: python kag/builder/legal_id.py
"""

import re

__all__ = [
    "doc_key_from_number",
    "doc_key_from_catalog_id",
    "doc_key_from_name_and_date",
    "resolve_document_key",
    "article_id",
    "clause_id",
    "point_id",
    "parse_locator",
    "split_article_ref",
    "extract_dates",
    "STATUS_RESOLVED",
    "STATUS_UNRESOLVED",
    "STATUS_NOT_A_DOCUMENT",
    "KEY_AMBIGUOUS_VERSION",
]

STATUS_RESOLVED = "RESOLVED"
STATUS_UNRESOLVED = "UNRESOLVED"
STATUS_NOT_A_DOCUMENT = "NOT_A_SPECIFIC_DOCUMENT"

# Khóa chưa phân giải được phiên bản: CÙNG số hiệu nhưng thiếu năm, nên không
# thể hợp nhất an toàn. Bên gọi PHẢI giữ tách, không được coi là một văn bản.
KEY_AMBIGUOUS_VERSION = "AMBIGUOUS_VERSION"

# Số hiệu văn bản, tìm trên chuỗi gốc (còn dấu "/"): "116/2025/QH15",
# "329/2026/NĐ-CP", "50/NQ-CP" (thiếu năm -> không nhận).
_NUMBER_FULL = re.compile(
    r"\b(\d{1,5})\s*/\s*(\d{4})\s*/\s*([A-Za-zĐđ][A-Za-zĐđ0-9]*(?:-[A-Za-zĐđ0-9]+)*)"
)

# Dạng thiếu năm, có thật trong kho: "1528/QĐ-TTg", "367/QĐ-TTg", "127/QĐ-TTg".
# QĐ-TTg đánh số theo niên độ riêng, số hiệu vẫn định danh được văn bản trong
# phạm vi kho. Nhưng khóa phải ghi rõ KHÔNG có năm để không lặng lẽ đánh đồng
# với một văn bản cùng số nhưng khác năm.
_NUMBER_NO_YEAR = re.compile(
    r"\b(\d{1,5})\s*/\s*([A-Za-zĐđ][A-Za-zĐđ0-9]*(?:-[A-Za-zĐđ0-9]+)*)"
)

# "ngày 12 tháng 6 năm 2018" hoặc "ngày 12/6/2018"
_DATE_LONG = re.compile(
    r"ng[àa]y\s+(\d{1,2})\s+th[áa]ng\s+(\d{1,2})\s+n[ăa]m\s+(\d{4})", re.I
)
_DATE_SHORT = re.compile(r"ng[àa]y\s+(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{4})", re.I)

# "Điều 8", "Điều 121a", "điều 8 luật an ninh mạng", "Điều 4 của Luật ..."
# re.I để "Khoản"/"khoản"/"KHOẢN" đều nhận; tên do LLM sinh không ổn định hoa thường.
_ARTICLE = re.compile(
    r"^\s*[Đđ]i[eề]u\s+(\d+[a-z]?)\b(.*)$", re.U | re.S | re.I
)
_CLAUSE = re.compile(r"^\s*kho[ảa]n\s+(\d+[a-z]?)\b(.*)$", re.U | re.S | re.I)
_POINT = re.compile(r"^\s*đi[ểe]m\s+([a-zđ])\b(.*)$", re.U | re.S | re.I)

# "của" nối mô tả: "Điều 4 của Luật Bảo vệ dữ liệu cá nhân" — phần sau "của" là
# tên văn bản, không phải một Điều khác.
_OF = re.compile(r"^\s*c[ủu]a\s+(.+)$", re.U | re.S)

_SPACES = re.compile(r"\s+")


def _norm(text):
    return _SPACES.sub(" ", str(text)).strip()


def _clean_code(ma):
    """Mã văn bản -> ASCII hoa, giữ gạch nối phân tách. 'NĐ-CP' -> 'ND-CP'."""
    ma = ma.upper().replace("Đ", "D")
    ma = re.sub(r"[^A-Z0-9\-]", "", ma).strip("-")
    return re.sub(r"-{2,}", "-", ma)


def doc_key_from_number(number):
    """`329/2026/NĐ-CP` -> `329-2026-ND-CP`; `1528/QĐ-TTg` -> None.

    Trả None nếu không nhận ra số hiệu **đủ năm**. Dạng thiếu năm CỐ Ý trả
    None: `1528/QĐ-TTg` không nói được là quyết định năm nào, mà QĐ-TTg đánh
    số theo niên độ riêng nên hai quyết định cùng số ở hai năm là chuyện có
    thật. Trước đây hàm này trả `1528-NDQ-QD-TTG`, và hậu quả đã đo được:
    `1528/QĐ-TTg ngày 1/1/2020` và `1528/QĐ-TTg ngày 1/1/2026` ra **cùng một
    khóa** — tức hai văn bản khác nhau bị hợp nhất. Nhãn `NDQ` chỉ nói "thiếu
    năm", nó không phải một phiên bản.

    Muốn định danh văn bản thiếu năm thì phải có thêm bằng chứng (ngày ban
    hành, hoặc doc_id danh mục) — dùng ``resolve_document_key``.
    """
    if not number:
        return None
    m = _NUMBER_FULL.search(str(number))
    if not m:
        return None
    ma = _clean_code(m.group(3))
    return f"{int(m.group(1))}-{m.group(2)}-{ma}" if ma else None


def _number_has_year(number):
    """Số hiệu có năm ngay trong chuỗi không? (để phân biệt với suy từ ngày)"""
    return bool(number) and bool(_NUMBER_FULL.search(str(number)))


def extract_dates(text):
    """Các mốc ngày đọc được trong `text`, dạng `YYYY-MM-DD`, đã sắp xếp.

    Chỉ nhận dạng ghi rõ "ngày ... tháng ... năm ..." hoặc "ngày d/m/yyyy" —
    tức ngày được NÊU TƯỜNG MINH. Ngày trần kiểu "2026" không tính.
    """
    if not text:
        return []
    s = str(text)
    out = set()
    for m in _DATE_LONG.finditer(s):
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            out.add(f"{y:04d}-{mo:02d}-{d:02d}")
    for m in _DATE_SHORT.finditer(s):
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            out.add(f"{y:04d}-{mo:02d}-{d:02d}")
    return sorted(out)


def resolve_document_key(name=None, doc_number=None, date_issued=None,
                         catalog_id=None):
    """Khóa văn bản có PHIÊN BẢN, dùng mọi bằng chứng đáng tin đang có.

    Trả ``(doc_key, status, evidence)``. Thứ tự ưu tiên, mạnh trước yếu:

    1. ``doc_number`` **có năm** -> khóa từ số hiệu. Bằng chứng mạnh nhất, vì
       số hiệu có năm tự nó đã định danh phiên bản.
    2. ``catalog_id`` danh mục (`1528-QD-TTg`) + năm -> số hiệu không có năm
       nhưng danh mục có, và danh mục là khóa do người đặt.
    3. ``doc_number`` thiếu năm + ``date_issued`` -> ghép số hiệu với NĂM ban
       hành. Đây là chỗ sửa lỗi hợp nhất: hai quyết định cùng số khác năm ra
       hai khóa khác nhau.
    4. Chỉ có ngày, không có số hiệu -> khóa theo tên + ngày.
    5. Không đủ bằng chứng -> ``doc_key = None``, status
       ``KEY_AMBIGUOUS_VERSION`` nếu CÓ số hiệu nhưng thiếu năm (nguy hiểm:
       dễ hợp nhất nhầm), ngược lại ``UNRESOLVED``.

    KHÔNG BAO GIỜ trả một khóa đã phân giải cho trường hợp thiếu năm mà không
    có bằng chứng bù. Đó chính là lỗi cũ.
    """
    # 1. Số hiệu đủ năm.
    if doc_number and _number_has_year(doc_number):
        k = doc_key_from_number(doc_number)
        if k:
            return k, STATUS_RESOLVED, f"số hiệu đủ năm {doc_number!r}"

    # 2. Số hiệu thiếu năm + ngày ban hành.
    if doc_number:
        year = _year_of(date_issued)
        if year:
            k = doc_key_from_number(doc_number)
            if k is None:
                # Số hiệu thiếu năm -> tự bóc rồi ghép năm.
                k = _key_with_year(doc_number, year)
                if k:
                    return (
                        k,
                        STATUS_RESOLVED,
                        f"số hiệu thiếu năm {doc_number!r} + ngày ban hành "
                        f"{date_issued!r} -> ghép năm {year}",
                    )
            return (
                None,
                KEY_AMBIGUOUS_VERSION,
                f"số hiệu {doc_number!r} thiếu năm và ngày ban hành "
                f"{date_issued!r} không đọc được năm; KHÔNG hợp nhất",
            )
        # 3. Không có ngày -> thử danh mục.
        k = _key_from_catalog(catalog_id)
        if k:
            return (
                k,
                STATUS_RESOLVED,
                f"số hiệu thiếu năm {doc_number!r} + doc_id danh mục "
                f"{catalog_id!r}",
            )
        return (
            None,
            KEY_AMBIGUOUS_VERSION,
            f"số hiệu {doc_number!r} thiếu năm, không có ngày ban hành hay "
            f"doc_id danh mục; KHÔNG hợp nhất theo số hiệu",
        )

    # 4. Ngày ban hành ghi ngay trong tên.
    k = doc_key_from_name_and_date(name)
    if k:
        return k, STATUS_RESOLVED, "tên kèm ngày ban hành"

    # 5. Danh mục.
    k = _key_from_catalog(catalog_id)
    if k:
        return k, STATUS_RESOLVED, f"doc_id danh mục {catalog_id!r}"

    return None, STATUS_UNRESOLVED, "không đủ bằng chứng định danh"


def _year_of(value):
    """Năm 4 chữ số từ ngày ISO / chuỗi ngày / số năm. None nếu không có."""
    if value is None or value == "":
        return None
    m = re.search(r"(19|20)\d{2}", str(value))
    return m.group(0) if m else None


def _key_with_year(number, year):
    """`1528/QĐ-TTg` + 2020 -> `1528-2020-QD-TTG`.

    Giữ cùng khuôn với dạng đủ năm để hai cách viết về MỘT văn bản ra một khóa.
    """
    m = _NUMBER_NO_YEAR.search(str(number))
    if not m:
        # Số hiệu có thể đã có năm sai định dạng; thử bóc bằng regex đủ.
        m2 = re.match(r"^\s*(\d{1,5})\s*/\s*(.+)$", str(number).strip())
        if not m2:
            return None
        ma = _clean_code(m2.group(2))
        return f"{int(m2.group(1))}-{year}-{ma}" if ma else None
    ma = _clean_code(m.group(2))
    return f"{int(m.group(1))}-{year}-{ma}" if ma else None


def _key_from_catalog(catalog_id):
    """`1528-QD-TTg` -> khóa CHỈ KHI danh mục có năm. Ngược lại None.

    Danh mục đặt mã không năm (`1528-QD-TTg`), và chính vì thế nó KHÔNG đủ để
    định danh phiên bản. Trả None thay vì dựng khóa `NDQ`, để bên gọi giữ
    trạng thái chưa phân giải thay vì hợp nhất hai văn bản cùng số khác năm.
    """
    if not catalog_id:
        return None
    return doc_key_from_catalog_id(catalog_id)


def doc_key_from_catalog_id(doc_id):
    """`05-2026-TT-BKHCN` -> `5-2026-TT-BKHCN`. None nếu không có dạng số-năm-mã.

    `doc_id` trong data/metadata là khóa danh mục do người đặt, đã được dùng làm
    tên file và làm tham chiếu trong `supersedes`/`implements`. Dùng nó làm
    nguồn khi tên văn bản không chứa số hiệu đủ để tự bóc.
    """
    if not doc_id:
        return None
    m = re.match(r"^(\d{1,5})-(\d{4})-([A-Za-z][A-Za-z0-9\-]*)$", str(doc_id).strip())
    if not m:
        return None
    ma = _clean_code(m.group(3))
    return f"{int(m.group(1))}-{m.group(2)}-{ma}" if ma else None


def doc_key_from_name_and_date(name):
    """Tên + ngày ban hành -> khóa phiên bản. None nếu không có ngày.

    Dùng khi văn bản không có số hiệu trong tên nhưng có mốc ngày, ví dụ
    "Luật An ninh mạng ngày 12 tháng 6 năm 2018". Khóa gồm cả tên đã slug và
    ngày, vì chỉ ngày không đủ phân biệt hai văn bản khác nhau cùng ngày.
    """
    if not name:
        return None
    m = _DATE_LONG.search(str(name)) or _DATE_SHORT.search(str(name))
    if not m:
        return None
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return None
    head = str(name)[: m.start()].strip()
    head = re.sub(r"[^\w ]", " ", head.lower(), flags=re.U)
    head = _SPACES.sub(" ", head).strip()
    if not head:
        return None
    return f"{head.replace(' ', '-')}@{y:04d}-{mo:02d}-{d:02d}"


def split_article_ref(text):
    """Tách "Điều 4 của Luật Bảo vệ dữ liệu cá nhân" -> ("4", "Luật Bảo vệ ...").

    Trả (None, None) nếu chuỗi không mở đầu bằng "Điều <số>".

    Phần đuôi được trả về nguyên văn để bên gọi tự quyết định nó là phạm vi
    (văn bản đang đọc) hay trích dẫn (văn bản khác). Hàm này KHÔNG tự gán.
    """
    m = _ARTICLE.match(str(text))
    if not m:
        return None, None
    number, tail = m.group(1), _norm(m.group(2))
    if tail:
        of = _OF.match(tail)
        if of:
            tail = _norm(of.group(1))
    return number, (tail or None)


def parse_locator(text):
    """Bóc vị trí pháp lý từ một chuỗi tên bất kỳ.

    Trả dict {article, clause, point, scope} — giá trị None nghĩa là không có
    bằng chứng cho cấp đó. KHÔNG bịa cấp không xuất hiện trong chuỗi.

    Nhận CẢ HAI thứ tự có thật trong kho:

      "Điều 7", "Khoản 2 Điều 7", "Điểm a Khoản 2 Điều 7"
      "Khoản 2 Điều 7 Thông tư 05/2026/TT-BKHCN"

    Bản cũ chỉ thử Điểm ở đầu chuỗi, nên "Điểm a Khoản 2 Điều 7" mất cả Khoản
    lẫn Điều — đúng loại bỏ sót mà yêu cầu nêu.
    """
    out = {"article": None, "clause": None, "point": None, "scope": None}
    rest = _norm(text)

    # Điểm có thể đứng trước (dạng phổ biến) hoặc không có.
    m_point = _POINT.match(rest)
    if m_point:
        out["point"] = m_point.group(1)
        rest = _norm(m_point.group(2))

    # Điều đứng trước Khoản: "Điều 7 Khoản 2"
    m_art = _ARTICLE.match(rest)
    if m_art:
        out["article"] = m_art.group(1)
        rest = _norm(m_art.group(2))
        m_cl = _CLAUSE.match(rest)
        if m_cl:
            out["clause"] = m_cl.group(1)
            rest = _norm(m_cl.group(2))
        of = _OF.match(rest)
        if of:
            rest = _norm(of.group(1))
        out["scope"] = rest or None
        return out

    # Khoản đứng trước Điều: "Khoản 2 Điều 7"
    m_cl = _CLAUSE.match(rest)
    if m_cl:
        out["clause"] = m_cl.group(1)
        rest = _norm(m_cl.group(2))
        # Điểm có thể nằm giữa Khoản và Điều, hoặc ngay trong phần còn lại.
        m_point2 = _POINT.match(rest)
        if m_point2:
            out["point"] = out["point"] or m_point2.group(1)
            rest = _norm(m_point2.group(2))
        m_art2 = _ARTICLE.match(rest)
        if m_art2:
            out["article"] = m_art2.group(1)
            rest = _norm(m_art2.group(2))
        of = _OF.match(rest)
        if of:
            rest = _norm(of.group(1))
        out["scope"] = rest or None
        return out

    # Không mở đầu bằng Điều/Khoản/Điểm: vẫn thử tìm "Điều N" ở đâu đó trong
    # chuỗi, nhưng chỉ nhận khi thật sự có — không suy diễn.
    m_any = re.search(r"[Đđ]i[eề]u\s+(\d+[a-z]?)\b", rest, re.U | re.I)
    if m_any:
        out["article"] = m_any.group(1)
    return out


def article_id(doc_key, number):
    """ID Điều có phạm vi. doc_key None -> trả None, bên gọi phải giữ chưa phân giải."""
    if not doc_key or not number:
        return None
    return f"dieu:{doc_key}#{number}"


def clause_id(doc_key, article_number, clause_number):
    a = article_id(doc_key, article_number)
    if not a or not clause_number:
        return None
    return f"khoan:{a}#{clause_number}"


def point_id(doc_key, article_number, clause_number, point_letter):
    c = clause_id(doc_key, article_number, clause_number)
    if not c or not point_letter:
        return None
    return f"diem:{c}#{point_letter}"


def _self_check():
    """Ca thật lấy từ snapshot 17/09/2026. Không gọi mạng, không đụng Neo4j."""
    # --- số hiệu -> khóa, nhiều cách viết phải về một khóa ----------------
    same_key = [
        ("329/2026/NĐ-CP", "329-2026-ND-CP"),
        ("329/2026/ND-CP", "329-2026-ND-CP"),
        ("số 329/2026/NĐ-CP", "329-2026-ND-CP"),
        ("116/2025/QH15", "116-2025-QH15"),
        ("05/2026/TT-BKHCN", "5-2026-TT-BKHCN"),
        # Thiếu năm -> KHÔNG tự đặt khóa. Đây là chỗ từng hợp nhất nhầm.
        ("1528/QĐ-TTg", None),
        ("50/NQ-CP", None),
        ("", None),
        (None, None),
    ]
    for raw, want in same_key:
        got = doc_key_from_number(raw)
        assert got == want, f"doc_key_from_number({raw!r}) = {got!r}, chờ {want!r}"
        print(f"  số hiệu        : {str(raw):22s} -> {got!r}")

    # --- PHẢN CHỨNG: cùng số hiệu thiếu năm, KHÁC năm -> KHÁC khóa --------
    a_key, a_st, a_ev = resolve_document_key(
        doc_number="1528/QĐ-TTg", date_issued="2020-01-01")
    c_key, c_st, c_ev = resolve_document_key(
        doc_number="1528/QĐ-TTg", date_issued="2026-01-01")
    assert a_key is not None and c_key is not None, (a_key, c_key)
    assert a_key != c_key, (
        f"HAI văn bản cùng số hiệu khác năm KHÔNG được cùng khóa: "
        f"{a_key!r} == {c_key!r}"
    )
    print(f"  1528/QĐ-TTg 2020 -> {a_key!r}  ({a_st})")
    print(f"  1528/QĐ-TTg 2026 -> {c_key!r}  ({c_st})")

    # thiếu năm VÀ thiếu ngày -> KHÔNG trả khóa đã phân giải
    k, st, ev = resolve_document_key(doc_number="1528/QĐ-TTg")
    assert k is None and st == KEY_AMBIGUOUS_VERSION, (k, st, ev)
    print(f"  thiếu năm+ngày : -> {k!r} status={st} (KHÔNG hợp nhất)")

    # danh mục KHÔNG có năm -> không đủ để định danh phiên bản
    k, st, ev = resolve_document_key(
        doc_number="1528/QĐ-TTg", catalog_id="1528-QD-TTg")
    assert k is None and st == KEY_AMBIGUOUS_VERSION, (k, st, ev)
    print(f"  + doc_id KHÔNG năm: -> {k!r} status={st} (KHÔNG hợp nhất)")

    # danh mục CÓ năm thì dùng được
    k, st, ev = resolve_document_key(catalog_id="05-2026-TT-BKHCN")
    assert k == "5-2026-TT-BKHCN" and st == STATUS_RESOLVED, (k, st, ev)
    print(f"  + doc_id có năm: -> {k!r} status={st}")

    # số hiệu đủ năm thì không cần gì thêm
    k, st, ev = resolve_document_key(doc_number="329/2026/NĐ-CP")
    assert k == "329-2026-ND-CP" and st == STATUS_RESOLVED, (k, st, ev)
    print(f"  đủ năm         : -> {k!r} status={st}")

    # ngày trong tên, và ngày nêu trong nội dung KHÔNG được lẫn
    assert extract_dates("Quyết định số 1671/QĐ-TTg ngày 28 tháng 8 năm 2026") \
        == ["2026-08-28"]
    assert extract_dates("Điều 5. Thời hạn 90 ngày kể từ ngày 01/01/2020") \
        == ["2020-01-01"]
    assert extract_dates("Nghị định 329/2026/NĐ-CP") == []
    print(f"  extract_dates  : chỉ nhận ngày NÊU TƯỜNG MINH, không nhận '2026'")

    # doc_id danh mục -> cùng khóa với số hiệu tương ứng
    pair = [
        ("05-2026-TT-BKHCN", "5-2026-TT-BKHCN"),
        ("1528-QD-TTg", None),  # thiếu năm trong doc_id -> không tự bóc
    ]
    for raw, want in pair:
        got = doc_key_from_catalog_id(raw)
        assert got == want, f"doc_key_from_catalog_id({raw!r}) = {got!r}, chờ {want!r}"
        print(f"  doc_id danh mục: {raw:22s} -> {got!r}")

    # --- parse_locator phải bóc đủ cả Khoản lẫn Điểm ----------------------
    full = parse_locator("Điểm a Khoản 2 Điều 7 Thông tư 05/2026/TT-BKHCN")
    assert full["point"] == "a", full
    assert full["clause"] == "2", full
    assert full["article"] == "7", full
    print(f"  Điểm/Khoản/Điều: {full}")
    kc = parse_locator("Khoản 5 Điều 10")
    assert kc["clause"] == "5" and kc["article"] == "10", kc
    print(f"  Khoản rồi Điều : {kc}")

    # --- ngày -> khóa phiên bản ------------------------------------------
    dated = [
        ("Luật An ninh mạng ngày 12 tháng 6 năm 2018", "luật-an-ninh-mạng@2018-06-12"),
        ("Luật An ninh mạng ngày 12/6/2018", "luật-an-ninh-mạng@2018-06-12"),
        ("Luật An ninh mạng", None),  # không ngày -> không đủ
    ]
    for raw, want in dated:
        got = doc_key_from_name_and_date(raw)
        assert got == want, f"doc_key_from_name_and_date({raw!r}) = {got!r}, chờ {want!r}"
        print(f"  tên + ngày     : {raw[:34]:34s} -> {got!r}")

    # --- hai văn bản cùng "Điều 2" KHÔNG va chạm -------------------------
    a = article_id("328-2026-ND-CP", "2")
    b = article_id("5-2026-TT-BKHCN", "2")
    assert a != b, "Điều 2 của hai văn bản phải khác ID"
    assert a == "dieu:328-2026-ND-CP#2", a
    assert b == "dieu:5-2026-TT-BKHCN#2", b
    print(f"  Điều 2 NĐ 328  : {a}")
    print(f"  Điều 2 TT 05   : {b}   -> khác nhau")

    # cùng văn bản cùng số -> cùng ID (ổn định)
    assert article_id("328-2026-ND-CP", "2") == a

    # không có phạm vi -> None, không được bịa
    assert article_id(None, "2") is None
    assert article_id("328-2026-ND-CP", None) is None
    print("  thiếu phạm vi  : -> None (giữ chưa phân giải, không bịa)")

    # --- khoản / điểm thuộc đúng cấp cha ---------------------------------
    k = clause_id("328-2026-ND-CP", "2", "1")
    d = point_id("328-2026-ND-CP", "2", "1", "a")
    assert k == "khoan:dieu:328-2026-ND-CP#2#1", k
    assert d == "diem:khoan:dieu:328-2026-ND-CP#2#1#a", d
    assert clause_id("5-2026-TT-BKHCN", "2", "1") != k, "Khoản phải theo văn bản"
    print(f"  Khoản 1 Điều 2 : {k}")
    print(f"  Điểm a Khoản 1 : {d}")

    # --- phân biệt Điều đang đọc với Điều được dẫn chiếu -----------------
    own = "Điều 8"
    ref = "Điều 4 của Luật Bảo vệ dữ liệu cá nhân"
    n_own, scope_own = split_article_ref(own)
    n_ref, scope_ref = split_article_ref(ref)
    assert (n_own, scope_own) == ("8", None), (n_own, scope_own)
    assert (n_ref, scope_ref) == ("4", "Luật Bảo vệ dữ liệu cá nhân"), (n_ref, scope_ref)
    print(f"  đang đọc       : {own!r} -> số={n_own!r} phạm vi={scope_own!r}")
    print(f"  dẫn chiếu      : {ref!r}")
    print(f"                   -> số={n_ref!r} phạm vi={scope_ref!r}")

    # --- parse_locator không bịa cấp --------------------------------------
    loc = parse_locator("Khoản 2 Điều 7 Thông tư 05/2026/TT-BKHCN")
    assert loc["clause"] == "2" and loc["article"] == "7", loc
    loc2 = parse_locator("Điều 8")
    assert loc2 == {"article": "8", "clause": None, "point": None, "scope": None}, loc2
    print(f"  locator        : {loc}")
    print(f"  locator        : {loc2}  (không bịa Khoản/Điểm)")

    print("[self-check ok] định danh có phạm vi, không va chạm Điều giữa văn bản")
    return 0


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(_self_check())
