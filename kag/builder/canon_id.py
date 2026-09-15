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

import re

__all__ = ["slug", "canon_id", "KEEP_ID"]

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

    print("[self-check ok] một thực thể một id, hai đường nạp gặp nhau")
    return 0


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")  # console Windows mặc định cp1252
    sys.exit(_self_check())
