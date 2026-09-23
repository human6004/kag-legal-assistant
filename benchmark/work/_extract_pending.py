# -*- coding: utf-8 -*-
"""Pull specific articles / phrase hits from the processed corpus. Mechanical only."""
import re
from pathlib import Path

ROOT = Path("data/processed")

def load(glob):
    hits = list(ROOT.rglob(glob))
    if not hits:
        raise SystemExit("missing " + glob)
    return hits[0], hits[0].read_text(encoding="utf-8")

ART = re.compile(r"^####\s+Điều\s+(\d+)\.", re.M)

def articles(text):
    marks = [(m.start(), m.group(1)) for m in ART.finditer(text)]
    out = {}
    for i, (pos, num) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        out[num] = text[pos:end]
    return out

def show(label, body, limit=1800):
    print("\n" + "=" * 70)
    print(label, "chars", len(body))
    print(body[:limit].replace("\n", " | "))
    if len(body) > limit:
        print(" ...[truncated]...")

def find_phrase(text, phrase, window=180):
    low = text.lower()
    p = phrase.lower()
    i = 0
    n = 0
    while True:
        j = low.find(p, i)
        if j < 0:
            break
        n += 1
        # which article
        art = "?"
        for m in ART.finditer(text):
            if m.start() <= j:
                art = m.group(1)
            else:
                break
        snippet = text[max(0, j - 80): j + len(phrase) + window].replace("\n", " ")
        print(f"  HIT Dieu {art}: ...{snippet}...")
        i = j + len(p)
        if n >= 6:
            print("  (more hits omitted)")
            break
    if n == 0:
        print("  NO HIT:", phrase)

# --- files ---
jobs = []

p, t = load("328-2026*.md")
A = articles(t)
print("FILE", p.name, "line2:", t.splitlines()[1])
# last 3 article numbers
nums = sorted(A, key=lambda x: int(x))
for n in nums[-3:]:
    show(f"328 Dieu {n}", A[n], 900)
find_phrase(t, "chưa có hiệu lực")
find_phrase(t, "có hiệu lực")

p, t = load("333-2026*.md")
A = articles(t)
print("\nFILE", p.name)
find_phrase(t, "53/2022")
find_phrase(t, "hết hiệu lực")
nums = sorted(A, key=lambda x: int(x))
show("333 last article " + nums[-1], A[nums[-1]], 700)
# hieu luc article by heading
for n, body in A.items():
    if "Hiệu lực" in body[:120]:
        show(f"333 Dieu {n} HIEU LUC", body, 1200)

p, t = load("71-2025*.md")
print("\nFILE", p.name, "line2:", t.splitlines()[1])
find_phrase(t, "một phần hết hiệu lực")
find_phrase(t, "2026-01-01")
A = articles(t)
for n, body in A.items():
    if "Hiệu lực" in body[:80] or "chuyển tiếp" in body[:80].lower():
        show(f"71 Dieu {n}", body, 700)

p, t = load("1671*.md")
print("\nFILE", p.name, "line2:", t.splitlines()[1])
# promulgation near top
print("HEAD:\n", " | ".join(t.splitlines()[:25]))
find_phrase(t, "127/QĐ-TTg")
find_phrase(t, "ngày ký")

p, t = load("127-QD*.md")
print("\nFILE", p.name, "line2:", t.splitlines()[1])
print("HEAD:\n", " | ".join(t.splitlines()[:12]))

p, t = load("134-2025*.md")
print("\nFILE", p.name)
find_phrase(t, "71/2025")
find_phrase(t, "Công nghiệp công nghệ số")
A = articles(t)
for n, body in A.items():
    head = body[:100]
    if "sửa đổi" in head.lower() or "Hiệu lực" in head or "hiệu lực" in head.lower()[:60]:
        show(f"134 Dieu {n}", body, 900)

p, t = load("13-2023*.md")
A = articles(t)
show("13 Dieu 22", A.get("22", "MISSING"), 1500)
show("13 Dieu 9 head", A.get("9", "MISSING")[:600], 600)

p, t = load("86-2015*.md")
A = articles(t)
show("86 Dieu 45", A.get("45", "MISSING"), 1600)
show("86 Dieu 32 head+k4", A.get("32", "MISSING")[:1200], 1200)
find_phrase(t, "Giấy phép kinh doanh sản phẩm, dịch vụ an toàn thông tin mạng")

p, t = load("331-2026*.md")
A = articles(t)
# clause 2 intro of dieu 12: print until diem
body = A.get("12", "MISSING")
show("331 Dieu 12", body, 2200)
show("331 Dieu 13 k2 area", A.get("13", "")[:800], 800)
show("331 Dieu 38", A.get("38", "MISSING"), 500)
show("331 Dieu 39", A.get("39", "MISSING"), 2200)

p, t = load("341-2026*.md")
find_phrase(t, "Hệ điều hành, trình duyệt")
find_phrase(t, "Điện thoại di động không có khả năng mã hóa")
find_phrase(t, "Danh mục sản phẩm mật mã dân sự")
A = articles(t)
# where does dieu 19 start relative to the phrase
idx = t.lower().find("hệ điều hành, trình duyệt")
print("341 phrase index", idx, "dieu19 start", A["19"][:40] if "19" in A else None)
# heading immediately before phrase
pre = t[:idx]
heads = list(re.finditer(r"^#{1,4} .+$", pre, re.M))
print("341 headings before phrase (last 6):")
for h in heads[-6:]:
    print("  ", h.group(0)[:110])

p, t = load("24-2018*.md")
A = articles(t)
show("24 Dieu 24", A.get("24", "MISSING"), 2000)

p, t = load("142-2026*.md")
for phrase in [
    "Mô-đun, thành phần hoặc phiên bản hệ thống được triển khai trong thử nghiệm",
    "Quy mô triển khai tối đa của hệ thống trí tuệ nhân tạo",
    "Giá trị chịu rủi ro tối đa",
    "Điều kiện kỹ thuật và quản trị rủi ro",
]:
    print("\n142 PHRASE", phrase[:50])
    find_phrase(t, phrase, 60)

p, t = load("91-2025*.md")
A = articles(t)
for n, body in A.items():
    if "Hiệu lực" in body[:90] or "chuyển tiếp" in body[:90].lower():
        show(f"91 Dieu {n}", body, 1400)
find_phrase(t, "13/2023")

p, t = load("53-2022*.md")
print("\n53 line2", t.splitlines()[1])
find_phrase(t, "hết hiệu lực")

p, t = load("116-2025*.md")
A = articles(t)
show("116 Dieu 25", A.get("25", "MISSING"), 1600)
show("116 Dieu 44", A.get("44", "MISSING"), 800)
