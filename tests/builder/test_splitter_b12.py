# -*- coding: utf-8 -*-
"""B1.2: khóa hành vi chia chunk theo cấu trúc pháp luật.

Chạy:  .venv/Scripts/python.exe -X utf8 tests/builder/test_splitter_b12.py

Không LLM, không embedding, không graph, không DB, không ghi gì. Mọi ca chạy
trên ĐƯỜNG THẬT: ``LegalMarkdownReader.solve_content`` (hàm indexer.py gọi) rồi
``LegalStructuralSplitter._invoke``. Gọi ``_invoke`` thay vì ``invoke`` để đi
vòng qua checkpoint ``ckpt/`` — không xoá, không reset state nào.

Mọi ca dùng văn bản thật trong ``data/processed``, không có fixture tổng hợp.

Passage kiểm theo đúng hợp đồng của extractor thật
(``schema_free_extractor.py:506``)::

    passage = chunk.name + "\\n" + chunk.content

nên mọi kiểm tra về "LLM đọc thấy gì" chạy trên ``passage``, không chỉ trên
``content``.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kag"))

import builder.reader as legal_reader  # noqa: E402
import builder.splitter as legal_splitter  # noqa: E402

THRESHOLD = 4950
READER = legal_reader.LegalMarkdownReader(cut_depth=4)
SPLITTER = legal_splitter.LegalStructuralSplitter(split_length=THRESHOLD)

ND142 = ROOT / "data/processed/vn_ai/142-2026-ND-CP_quy-dinh-chi-tiet-luat-tri-tue-nhan-tao.md"
QD1528 = ROOT / "data/processed/vn_ai/1528-QD-TTg_chuong-trinh-quoc-gia-phat-trien-nhan-luc-ai.md"
QD1671 = ROOT / "data/processed/vn_ai/1671-QD-TTg_chien-luoc-quoc-gia-tri-tue-nhan-tao-2030-tam-nhin-2045.md"
ND356 = (
    ROOT
    / "data/processed/vn_an_ninh_mang/356-2025-ND-CP_quy-dinh-chi-tiet-luat-bao-ve-du-lieu-ca-nhan.md"
)

PASS, FAIL = [], []


def check(name, got, want):
    if got == want:
        PASS.append(name)
        print(f"  OK   {name}")
    else:
        FAIL.append((name, got, want))
        print(f"  FAIL {name}\n       got  = {got}\n       want = {want}")


def read(path):
    outs, _ = READER.solve_content(
        id=str(path), title=path.stem, content=path.read_text(encoding="utf-8")
    )
    return outs


def leaf(chunk):
    return (chunk.name or "").split(" / ")[-1]


def pick(chunks, pattern, on_leaf=True):
    hit = [c for c in chunks if re.search(pattern, leaf(c) if on_leaf else (c.name or ""))]
    return hit


def split(chunk):
    return SPLITTER._invoke(chunk)


def passage(chunk):
    """Đúng chuỗi extractor thật gửi cho LLM."""
    return (chunk.name or "") + "\n" + (chunk.content or "")


def body_lines(text):
    return [line.strip() for line in text.split("\n") if line.strip()]


print("\n1) Điều ngắn (<= 4950 ký tự) giữ nguyên một chunk")
r142 = read(ND142)
short = [
    c
    for c in r142
    if (c.content or "").strip()
    and len(c.content) <= THRESHOLD
    and re.match(r"Điều \d+\.", leaf(c))
    and "Mẫu" not in (c.name or "")
]
check("có Điều ngắn thật trong 142-2026-ND-CP", len(short) > 0, True)
for c in short:
    outs = split(c)
    if len(outs) != 1 or outs[0].content != c.content or outs[0].id != c.id:
        check(f"Điều ngắn giữ nguyên: {leaf(c)[:40]}", (len(outs), outs[0].content == c.content), (1, True))
        break
else:
    check(f"cả {len(short)} Điều ngắn -> 1 chunk, nội dung và id không đổi", True, True)

print("\n2) source_path sống từ Reader sang Splitter")
REL142 = "data/processed/vn_ai/142-2026-ND-CP_quy-dinh-chi-tiet-luat-tri-tue-nhan-tao.md"
check("mọi chunk Reader có source_path", [c.name for c in r142 if not c.kwargs.get("source_path")], [])
check("source_path là đường dẫn tương đối gốc repo", {c.kwargs.get("source_path") for c in r142}, {REL142})
check(
    "source_path trỏ đúng file thật",
    (ROOT / next(iter({c.kwargs.get("source_path") for c in r142}))).is_file(),
    True,
)
check(
    "cả chunk TEXT và TABLE đều có source_path",
    sorted({c.type.name for c in r142 if c.kwargs.get("source_path")}),
    ["Table", "Text"],
)
# Không ghi absolute path máy người dùng vào metadata.
check(
    "source_path không chứa absolute path",
    [c.name for c in r142 if re.match(r"^[A-Za-z]:|^/", str(c.kwargs.get("source_path")))],
    [],
)
src13 = pick(r142, r"^Điều 13\.")
check("reader trả đúng 1 chunk cho Điều 13", len(src13) == 1, True)
src13 = src13[0]
out13 = split(src13)
check("chunk con giữ source_path của cha", {c.kwargs.get("source_path") for c in out13}, {REL142})
check(
    "source_path không rò vào text LLM",
    [c.name for c in out13 if REL142 in passage(c)],
    [],
)

print("\n3) Điều dài (142-2026-ND-CP / Điều 13, 5018 ký tự) chia theo Khoản")
check("Điều 13 vượt ngưỡng", len(src13.content) > THRESHOLD, True)
check("Điều 13 -> 6 chunk (mỗi Khoản một chunk)", len(out13) == 6, True)
check(
    "clause_no theo đúng thứ tự Khoản 1..6",
    [c.kwargs.get("clause_no") for c in out13],
    ["1", "2", "3", "4", "5", "6"],
)
check("mọi chunk con của Điều 13 <= 4950", max(len(c.content) for c in out13) <= THRESHOLD, True)
# đuôi mồ côi 144 ký tự của LengthSplitter cũ không được tái xuất
check("không còn chunk đuôi < 200 ký tự", min(len(c.content) for c in out13) >= 200, True)
check(
    "mỗi chunk con mở đầu bằng số Khoản của nó",
    [c.content.split(".", 1)[0].strip() for c in out13],
    ["1", "2", "3", "4", "5", "6"],
)
check("tên chunk con mang Khoản N", [leaf(c) for c in out13], [f"Khoản {n}" for n in range(1, 7)])

print("\n4) Passage thật không lặp heading")
# content chỉ mang thân; ngữ cảnh nằm ở name, extractor ghép lại một lần.
doc_title = (src13.name or "").split(" / ")[0]
check("content không chứa tiêu đề văn bản", [leaf(c) for c in out13 if doc_title in c.content], [])
check(
    "content không chứa nguyên heading path của cha",
    [leaf(c) for c in out13 if src13.name in c.content],
    [],
)
check(
    "tên Điều xuất hiện đúng một lần trong passage",
    [leaf(c) for c in out13 if passage(c).count("Điều 13.") != 1],
    [],
)

print("\n5) Không mất nội dung, không trùng nội dung, overlap = 0")
orig = body_lines(src13.content)
merged = "\n".join(c.content for c in out13)
check("không mất dòng thân nào của Điều 13", [l for l in orig if l not in merged], [])
dup = [(l[:48], sum(1 for c in out13 if l in c.content)) for l in orig]
check("không dòng thân nào nằm trong >1 chunk", [d for d in dup if d[1] != 1], [])
check("window_length mặc định = 0 (không overlap)", SPLITTER.window_length, 0)

print("\n6) Khoản dài chia theo Điểm (1671-QD-TTg / III. CÁC TRỤ CỘT CHIẾN LƯỢC)")
r1671 = read(QD1671)
pillar = pick(r1671, r"^III\. CÁC TRỤ CỘT CHIẾN LƯỢC")
check("tìm được node trụ cột chiến lược", len(pillar) == 1, True)
outs = split(pillar[0])
check("node 29782 ký tự -> 24 chunk", len(outs), 24)
heads = [c.content.splitlines()[0] for c in outs]
# mục 6 (mang câu dẫn) rồi các Điểm b..q: descent xuống cấp Điểm vẫn chạy
points = [h[0] for h in heads if re.match(r"^[a-zđ]\) ", h)]
check(
    "Khoản/mục 6 được chia tiếp theo Điểm b..q",
    points,
    ["b", "c", "d", "đ", "e", "g", "h", "i", "k", "l", "m", "n", "o", "p", "q"],
)
check(
    "các mục đánh số 1..9 giữ nguyên thứ tự",
    [h.split(".", 1)[0] for h in heads if re.match(r"^\d+\. ", h)],
    ["1", "2", "3", "4", "5", "6", "7", "8", "9"],
)
check("mọi chunk <= 4950", max(len(c.content) for c in outs) <= THRESHOLD, True)
src_p = body_lines(pillar[0].content)
merged_p = "\n".join(c.content for c in outs)
check("không mất dòng nào", [l for l in src_p if l not in merged_p], [])
check(
    "không dòng nào nằm trong >1 chunk",
    [l[:40] for l in src_p if sum(1 for c in outs if l in c.content) > 1],
    [],
)

print("\n7) Mục đánh số ngoài Điều thật KHÔNG được gọi là Khoản")
# Quyết định 1671 dùng mục La Mã + mục đánh số, không có Điều -> không đủ bằng
# chứng gọi "1." là Khoản.
check("node không phải Điều -> article_no = None", {c.kwargs.get("article_no") for c in outs}, {None})
check("không gắn clause_no giả", {c.kwargs.get("clause_no") for c in outs}, {None})
check("không gắn point_no giả", {c.kwargs.get("point_no") for c in outs}, {None})
check("tên không chứa 'Khoản'", [c.name[-40:] for c in outs if "Khoản" in c.name], [])
check("tên không chứa 'Điểm'", [c.name[-40:] for c in outs if "Điểm" in c.name], [])
check(
    "thứ tự giữ bằng split_index",
    [c.kwargs.get("split_index") for c in outs],
    list(range(1, 25)),
)
check("split_total đúng", {c.kwargs.get("split_total") for c in outs}, {24})
forms = [c for c in r142 if "Mẫu AI09" in (c.name or "")]
check("có nhánh Mẫu AI09a/AI09b", len(forms) > 0, True)
fo = [o for c in forms for o in split(c)]
check("Mẫu AI09*: article_no = None", {c.kwargs.get("article_no") for c in fo}, {None})
check("Mẫu AI09*: không clause_no giả", {c.kwargs.get("clause_no") for c in fo}, {None})
check("Mẫu AI09*: tên không có 'Khoản'", [c.name[-40:] for c in fo if "Khoản" in c.name], [])
real3 = [c for c in r142 if re.match(r"Điều 3\.", leaf(c)) and "Mẫu" not in (c.name or "")]
check("Điều 3 thật vẫn có article_no = 3", [split(c)[0].kwargs.get("article_no") for c in real3], [3])

print("\n8) Khối vượt ngưỡng không có ranh giới cấu trúc: fallback theo dòng")
r356 = read(ND356)
form9 = pick(r356, r"^Mẫu 09")
check("tìm được Mẫu 09 của 356-2025-ND-CP", len(form9) == 1, True)
outs9 = split(form9[0])
check("Mẫu 09 -> nhiều phần", len(outs9) >= 2, True)
check("mọi phần <= 4950", max(len(c.content) for c in outs9) <= THRESHOLD, True)
check(
    "phần đánh số (phần i/N), không gọi là Khoản",
    all(re.search(r"\(phần \d+/\d+\)$", c.name) for c in outs9),
    True,
)
check("Mẫu 09: không clause_no giả", {c.kwargs.get("clause_no") for c in outs9}, {None})
src_lines = body_lines(form9[0].content)
merged9 = "\n".join(c.content for c in outs9)
check("fallback không mất dòng nào", [l for l in src_lines if l not in merged9], [])
# ranh giới rơi vào cuối dòng nguồn -> không có mảnh nào cắt giữa từ
cut_mid_word = []
for c in outs9:
    first = body_lines(c.content)[0] if body_lines(c.content) else ""
    if first and not any(l.startswith(first[:30]) for l in src_lines):
        cut_mid_word.append(first[:40])
check("mảnh fallback mở đầu đúng một dòng nguồn", cut_mid_word, [])

print("\n9) Heading rỗng thân: Điều mang quy định thì giữ, nhãn cấu trúc thì không")
r1528 = read(QD1528)
empty = [c for c in r1528 if not (c.content or "").strip()]
check("1528-QD-TTg có heading rỗng thân", len(empty) > 0, True)
art2 = pick(r1528, r"^Điều 2\.")
check("Điều 2 của 1528 là heading rỗng thân", len(art2) == 1 and not (art2[0].content or "").strip(), True)
o2 = split(art2[0])
check("Điều 2 không bị mất", len(o2), 1)
# quy định nằm ở name; content rỗng để passage không đọc hai lần cùng một câu
check("Điều 2: content rỗng", o2[0].content, "")
check("Điều 2: quy định nằm trong name", "có hiệu lực thi hành" in o2[0].name, True)
check(
    "passage thật của Điều 2 chứa quy định đúng một lần",
    passage(o2[0]).count("có hiệu lực thi hành"),
    1,
)
check("Điều 2 giữ article_no = 2", o2[0].kwargs.get("article_no"), 2)
check("Điều 2 giữ source_path", bool(o2[0].kwargs.get("source_path")), True)
labels = [c for c in r142 if not (c.content or "").strip() and not re.match(r"Điều \d+\.", leaf(c))]
check("nhãn cấu trúc rỗng không sinh chunk rỗng", [c.name for c in labels if split(c)], [])

print("\n10) Bảng: không mất dòng, không đổi thứ tự, không hồi quy giá trị lexical")
tables = [c for c in r1528 if c.type.name == "Table"]
check("1528-QD-TTg có bảng", len(tables) > 0, True)
lost_rows, changed = [], []
for c in tables:
    outs_t = split(c)
    rows_in = [l for l in c.content.split("\n") if l.lstrip().startswith("|")]
    rows_out = []
    for o in outs_t:
        rows_out.extend(l for l in o.content.split("\n") if l.lstrip().startswith("|"))
    lost_rows.extend(r[:40] for r in rows_in if r not in rows_out)
    joined = "\n".join(o.content for o in outs_t)
    for token in ("5.000", "1.100"):
        if c.content.count(token) != joined.count(token):
            changed.append((leaf(c), token))
check("không mất dòng bảng nào", lost_rows, [])
check("số lần xuất hiện giá trị dấu nghìn không đổi", changed, [])
check(
    "không ô nào bị ép về số thực kiểu '5.0'",
    [leaf(c) for c in tables for o in split(c) if "| 5.0 " in o.content or "| 1.1 " in o.content],
    [],
)

print("\n11) Text cho LLM không chứa dấu vết kỹ thuật")
sample = out13 + outs + outs9 + o2
check("không chunk nào chứa '_split_'", [c.name for c in sample if "_split_" in passage(c)], [])
check(
    "không chunk nào chứa đường dẫn nguồn",
    [c.name for c in sample if "data/processed" in passage(c)],
    [],
)
check(
    "không chunk nào chứa id băm của chính nó",
    [c.name for c in sample if c.id in passage(c)],
    [],
)

print(f"\n{len(PASS)} OK, {len(FAIL)} FAIL")
sys.exit(1 if FAIL else 0)
