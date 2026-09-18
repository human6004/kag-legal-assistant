# -*- coding: utf-8 -*-
"""B1.2: khóa hành vi chia chunk theo cấu trúc pháp luật.

Chạy:  .venv/Scripts/python.exe -X utf8 tests/builder/test_splitter_b12.py

Không LLM, không embedding, không graph, không DB, không ghi gì. Mọi ca chạy
trên ĐƯỜNG THẬT: ``LegalMarkdownReader.solve_content`` (hàm indexer.py gọi) rồi
``LegalStructuralSplitter._invoke``. Gọi ``_invoke`` thay vì ``invoke`` để đi
vòng qua checkpoint ``ckpt/`` — không xoá, không reset state nào.

Mọi ca dùng văn bản thật trong ``data/processed``, không có fixture tổng hợp.
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

print("\n2) Điều dài (142-2026-ND-CP / Điều 13, 5018 ký tự) chia theo Khoản")
src13 = pick(r142, r"^Điều 13\.")
check("reader trả đúng 1 chunk cho Điều 13", len(src13) == 1, True)
src13 = src13[0]
check("Điều 13 vượt ngưỡng", len(src13.content) > THRESHOLD, True)
out13 = split(src13)
check("Điều 13 -> 6 chunk (mỗi Khoản một chunk)", len(out13) == 6, True)
check(
    "clause_no theo đúng thứ tự Khoản 1..6",
    [c.kwargs.get("clause_no") for c in out13],
    ["1", "2", "3", "4", "5", "6"],
)
check("mọi chunk con của Điều 13 <= 4950", max(len(c.content) for c in out13) <= THRESHOLD, True)
# đuôi mồ côi 144 ký tự của LengthSplitter cũ không được tái xuất
check("không còn chunk đuôi < 200 ký tự", min(len(c.content) for c in out13) >= 200, True)
# mỗi chunk con phải mở đầu đúng bằng số Khoản của nó
starts = []
for c in out13:
    tail = c.content.split("\n\n", 1)[1] if "\n\n" in c.content else c.content
    starts.append(tail.split(".", 1)[0].strip())
check("mỗi chunk con mở đầu bằng số Khoản của nó", starts, ["1", "2", "3", "4", "5", "6"])

print("\n3) Không mất nội dung, không trùng nội dung, overlap = 0")
orig = body_lines(src13.content)
merged = "\n".join(c.content for c in out13)
check("không mất dòng thân nào của Điều 13", [l for l in orig if l not in merged], [])
dup = [(l[:48], sum(1 for c in out13 if l in c.content)) for l in orig]
check("không dòng thân nào nằm trong >1 chunk", [d for d in dup if d[1] != 1], [])
check("window_length mặc định = 0 (không overlap)", SPLITTER.window_length, 0)

print("\n4) Khoản dài chia theo Điểm (1671-QD-TTg / III. CÁC TRỤ CỘT CHIẾN LƯỢC)")
r1671 = read(QD1671)
pillar = pick(r1671, r"^III\. CÁC TRỤ CỘT CHIẾN LƯỢC")
check("tìm được node trụ cột chiến lược", len(pillar) == 1, True)
outs = split(pillar[0])
points = [c for c in outs if c.kwargs.get("point_no") is not None]
check("có chunk cấp Điểm", len(points) > 0, True)
check("mọi Điểm đều thuộc Khoản 6", sorted({c.kwargs.get("clause_no") for c in points}), ["6"])
check(
    "thứ tự Điểm a..q giữ nguyên",
    [c.kwargs.get("point_no") for c in points],
    ["a", "b", "c", "d", "đ", "e", "g", "h", "i", "k", "l", "m", "n", "o", "p", "q"],
)
check("mọi chunk cấp Điểm <= 4950", max(len(c.content) for c in points) <= THRESHOLD, True)
# Điểm đầu nhận câu dẫn thật của Khoản; các Điểm sau chỉ nhận dấu "Khoản 6."
# làm ngữ cảnh, không nhận lại thân Khoản cha.
first_body = points[0].content.split("\n\n", 1)[1]
check("Điểm đầu giữ câu dẫn thật của Khoản 6", first_body.startswith("6. "), True)
check(
    "mọi Điểm sau đều mang dấu 'Khoản 6.' làm ngữ cảnh",
    [c.kwargs.get("point_no") for c in points[1:] if "Khoản 6." not in c.content],
    [],
)
check(
    "Điểm sau không lặp lại câu dẫn của Khoản 6",
    [c.kwargs.get("point_no") for c in points[1:] if first_body.split("\n")[0] in c.content],
    [],
)
print("\n5) Điểm/khối vượt ngưỡng: fallback theo dòng, không cắt giữa từ")
r356 = read(ND356)
form9 = pick(r356, r"^Mẫu 09")
check("tìm được Mẫu 09 của 356-2025-ND-CP", len(form9) == 1, True)
outs9 = split(form9[0])
parts = [c for c in outs9 if " / Phần " in (c.name or "")]
check("có chunk fallback theo độ dài", len(parts) >= 2, True)
check("mọi phần fallback <= 4950", max(len(c.content) for c in parts) <= THRESHOLD, True)
src_lines = body_lines(form9[0].content)
merged9 = "\n".join(c.content for c in outs9)
check("fallback không mất dòng nào", [l for l in src_lines if l not in merged9], [])
# ranh giới rơi vào cuối dòng nguồn -> không có mảnh nào cắt giữa từ
cut_mid_word = []
for c in parts:
    tail = c.content.split("\n\n", 1)[1] if "\n\n" in c.content else c.content
    first = body_lines(tail)[0] if body_lines(tail) else ""
    if first and not any(l.startswith(first[:30]) for l in src_lines):
        cut_mid_word.append(first[:40])
check("mảnh fallback mở đầu đúng một dòng nguồn", cut_mid_word, [])

print("\n6) Heading rỗng thân: Điều mang quy định thì giữ, nhãn cấu trúc thì không")
r1528 = read(QD1528)
empty = [c for c in r1528 if not (c.content or "").strip()]
check("1528-QD-TTg có heading rỗng thân", len(empty) > 0, True)
art2 = pick(r1528, r"^Điều 2\.")
check("Điều 2 của 1528 là heading rỗng thân", len(art2) == 1 and not (art2[0].content or "").strip(), True)
o2 = split(art2[0])
check("Điều 2 không bị mất", len(o2), 1)
check("câu quy định của Điều 2 xuất hiện đúng một lần", o2[0].content.count("có hiệu lực thi hành"), 1)
check("Điều 2 giữ article_no = 2", o2[0].kwargs.get("article_no"), 2)
labels = [c for c in read(ND142) if not (c.content or "").strip() and not re.match(r"Điều \d+\.", leaf(c))]
check("nhãn cấu trúc rỗng không sinh chunk rỗng", [c.name for c in labels if split(c)], [])

print("\n7) Điều trong Mẫu/Phụ lục không được gán article_no")
forms = [c for c in r142 if "Mẫu AI09" in (c.name or "")]
check("có nhánh Mẫu AI09a/AI09b", len(forms) > 0, True)
bad = [o.name for c in forms for o in split(c) if o.kwargs.get("article_no") is not None]
check("mọi chunk trong Mẫu AI09* có article_no = None", bad, [])
real3 = [c for c in r142 if re.match(r"Điều 3\.", leaf(c)) and "Mẫu" not in (c.name or "")]
check("Điều 3 thật vẫn có article_no = 3", [split(c)[0].kwargs.get("article_no") for c in real3], [3])

print("\n8) Bảng: không mất dòng, không đổi thứ tự, không hồi quy giá trị lexical")
tables = [c for c in r1528 if c.type.name == "Table"]
check("1528-QD-TTg có bảng", len(tables) > 0, True)
lost_rows, changed = [], []
for c in tables:
    outs = split(c)
    rows_in = [l for l in c.content.split("\n") if l.lstrip().startswith("|")]
    rows_out = []
    for o in outs:
        rows_out.extend(l for l in o.content.split("\n") if l.lstrip().startswith("|"))
    lost_rows.extend(r[:40] for r in rows_in if r not in rows_out)
    joined = "\n".join(o.content for o in outs)
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

print("\n9) Text cho LLM không chứa dấu vết kỹ thuật")
sample = out13 + points + parts + o2
check("không chunk nào chứa '_split_'", [c.name for c in sample if "_split_" in c.content], [])
check("không chunk nào chứa đường dẫn nguồn", [c.name for c in sample if "data/processed" in c.content], [])
check(
    "không chunk nào chứa id băm của chính nó",
    [c.name for c in sample if c.id in c.content],
    [],
)

print(f"\n{len(PASS)} OK, {len(FAIL)} FAIL")
sys.exit(1 if FAIL else 0)
