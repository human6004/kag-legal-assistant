# -*- coding: utf-8 -*-
import re
from pathlib import Path
ROOT = Path("data/processed")

def text(glob):
    return next(ROOT.rglob(glob)).read_text(encoding="utf-8")

def chapters_around(t, articles):
    # print chapter heading in force at each article
    heads = [(m.start(), m.group(0)) for m in re.finditer(r"^(#{2,4})\s+(.+)$", t, re.M)]
    arts = {m.group(1): m.start() for m in re.finditer(r"^####\s+Điều\s+(\d+)\.", t, re.M)}
    for n in articles:
        pos = arts[str(n)]
        chap = "?"
        for p, h in heads:
            if p <= pos and h.startswith("## "):
                chap = h
        print(f"Dieu {n} under {chap}")

t = text("71-2025*.md")
chapters_around(t, [12, 28, 43, 44])
# khoản 6 điều 12
m = re.search(r"^#### Điều 12\..+?(?=^#### Điều |\Z)", t, re.S | re.M)
body = m.group(0)
print("--- D12 k6 area ---")
i = body.find("6.")
print(body[i:i+500] if i>=0 else "no k6")
print("--- AI phrase in D12 ---")
for phrase in ["trí tuệ nhân tạo", "ưu đãi"]:
    j = body.lower().find(phrase.lower())
    print(phrase, j, body[max(0,j-80):j+120].replace("\n"," ") if j>=0 else "")

t = text("35-2018*.md")
m = re.search(r"rà soát.{0,80}", t)
print("--- 35 ra soat ---")
print(m.group(0).replace("\n"," ") if m else "none")

t = text("142-2026*.md")
print("--- 142 hieu luc headings ---")
for m in re.finditer(r"^#### Điều \d+\..{0,40}[Hh]iệu lực.*$", t, re.M):
    print(m.group(0))
    start = m.start()
    print(t[start:start+350].replace("\n"," | "))
