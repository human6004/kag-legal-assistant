# -*- coding: utf-8 -*-
import re
from pathlib import Path
ROOT = Path("data/processed")

def load(glob):
    p = next(ROOT.rglob(glob))
    return p.read_text(encoding="utf-8")

def art(text, n):
    marks = list(re.finditer(r"^####\s+Điều\s+(\d+)\.", text, re.M))
    for i, m in enumerate(marks):
        if m.group(1) == str(n):
            end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
            return text[m.start():end]
    return "MISSING"

t = load("142-2026*.md")
body = art(t, 19)
# khoản 1 only: up to "\n2."
print("===== 142 D19 k1 =====")
print(body[:2200])
print("===== 142 chapters =====")
for m in re.finditer(r"^##\s+Chương.+$", t, re.M):
    print(m.group(0))
print("===== 142 form doi chieu (context) =====")
i = t.find("Mô-đun, thành phần hoặc phiên bản hệ thống được triển khai trong thử nghiệm")
print(t[i - 1500:i + 900])

t = load("86-2015*.md")
b = art(t, 45)
j = b.find("3. Doanh nghiệp không vi phạm")
print("===== 86 D45 k3 =====")
print(b[j:j + 900])
b = art(t, 40)
print("===== 86 D40 k2 =====")
k = b.find("Thời hạn của Giấy phép")
print(b[max(0, k - 200):k + 250])

t = load("333-2026*.md")
print("===== 333 D31 =====")
print(art(t, 31)[:1800])
print("===== 333 D1 full first 2000 =====")
print(art(t, 1)[:2000])

t = load("116-2025*.md")
b = art(t, 25)
k = b.lower().find("lưu trữ")
print("===== 116 D25 luu tru =====")
print("idx", k)
print(b[max(0, k - 300):k + 500] if k >= 0 else "NO luu tru")

t = load("24-2018*.md")
b = art(t, 26)
k = b.lower().find("lưu trữ")
print("===== 24 D26 luu tru =====")
print(b[max(0, k - 200):k + 400] if k >= 0 else "NO")

t = load("53-2022*.md")
b = art(t, 26)
print("===== 53 D26 k6 area =====")
k = b.find("12 tháng")
print(b[max(0, k - 250):k + 350] if k >= 0 else b[:400])
b = art(t, 27)
print("===== 53 D27 =====")
print(b[:1500])
