# -*- coding: utf-8 -*-
"""Don cac loi dinh dang trong corpus markdown.

1. Bieu mau trong phu luc bi viet thanh heading "#### Điều ..." nen reader coi
   chung la dieu luat that. Vi du "Điều 1. Cho phép ……………. (3) được kinh doanh".
   Chung sinh ra thuc the Dieu gia toan dau cham lung. Ha xuong thanh van ban
   thuong, giu nguyen chu.

2. Moc phu luc ("Phụ lục I - Mẫu số 01", "Mẫu số 03", "Mẫu AI08a: Báo cáo...")
   dang la van ban thuong nen ca phan phu luc dinh vao Dieu cuoi cung truoc no.
   O 332/2026/ND-CP dieu nay tao ra mot khoi 49.630 ky tu. Nang chung len
   heading h3 de moi bieu mau la mot chunk rieng, ten ro rang, VA de cac heading
   "#### Điều N" ben trong bieu mau nam duoi no thay vi thanh anh em.

3. Heading gia do bo chuyen doi docx -> md sinh ra. File .docx goc khong co bat
   ky pStyle nao (kiem bang zipfile: Counter() rong), nen bo chuyen doi doan
   heading bang tu khoa dau dong. No khop ca nhung o bang bat dau bang
   "Chương trình" hay "Mục tiêu", tuc tu khoa KHONG di kem so. Cung loi do o
   ban tieng Anh: ANNEX III cua NIS 2 la CORRELATION TABLE, moi o bang ghi dung
   chu "Article N" thanh heading. Ha tat ca xuong van ban thuong, giu nguyen chu.

4. Ky tu vo hinh: BOM (U+FEFF), NBSP (U+00A0), zero-width space (U+200B),
   soft hyphen (U+00AD). NBSP trong heading lam ten chunk khong khop chuoi voi
   ban viet dau cach thuong, vi du "## Chương<U+00A0>I".

Muc dich chung cua (2) va (3): duong dan tieu de phai duy nhat. MarkDownReader
(markdown_reader.py:663, 676) lay id chunk = generate_hash_id(" / ".join(
current_titles)), khong mang gi phan biet file hay vi tri, nen hai nhanh cung
duong dan se de mat nhau khi writer upsert.

Chay thu:  python kag/builder/clean_corpus.py
Ghi that:  python kag/builder/clean_corpus.py --write
"""

import re
import sys
from collections import defaultdict

from fix_h1 import all_md

# heading Dieu cua bieu mau: co dau cham lung hoac chuoi dau cham dai
FORM_HEADING = re.compile(r"^(#{1,6}\s*)(Điều\b.*(?:…|\.{4,}).*)$", re.M)

# Tu khoa cau truc phai di kem so (a rap hoac La Ma). Khong kem so la o bang
# bi bo chuyen doi nham thanh heading: "Chương trình", "Mục tiêu thử nghiệm".
# Viet hoa toan bo ("ĐIỀU KHOẢN THI HÀNH") la tieu de phu luc that, khong khop
# vi regex phan biet chu hoa chu thuong.
PSEUDO_HEADING = re.compile(
    # [^\S\n]* la dau cach ngang ke ca NBSP, de khong ket luan sai khi buoc don
    # ky tu vo hinh chua chay ("## Chương<U+00A0>I" van la heading that).
    r"^#{1,6}[ \t]+((?:Chương|Mục|Điều|Phần)\b(?![^\S\n]*(?:\d|[IVXLC]+\b))[^\n]*)$",
    re.M,
)

# Ten moc phu luc, dung chung cho ca ban van ban thuong va ban da la heading.
# Duoi ":" la ten bieu mau, 142/2026 viet "Mẫu AI08a: Báo cáo tổng kết...";
# phan duoi phai chay het dong nen mot cau van thuong khong khop.
ANNEX_NAME = (
    r"(?:Phụ lục\s+[IVXLC]+\s*[-–]\s*)?Mẫu\s+(?:số\s+)?\S+(?:[ \t]*:[^\n]*)?"
    r"|Phụ lục\s+[IVXLC]+"
)

# dong chi la moc phu luc, dung mot minh tren dong
ANNEX_MARK = re.compile(rf"^[ \t]*({ANNEX_NAME})[ \t]*$", re.M)

# cung ten do nhung da la heading roi, chi can dua ve dung cap
ANNEX_HEADING = re.compile(rf"^(#{{1,6}})[ \t]+({ANNEX_NAME})[ \t]*$", re.M)

# Cap heading cho moc phu luc. h3 chu khong h4: bieu mau nao cung co the chua
# "#### Điều N" ben trong (xem 331/2026 Mẫu số 06 va 07), h4 se thanh anh em
# cua chung nen duong dan tieu de khong phan biet duoc hai bieu mau.
ANNEX_LEVEL = "###"

# Moc nam sat nhau la muc luc phu luc, khong phai than bieu mau. Do that tren
# corpus: muc luc cach moc sau 24-148 ky tu, than bieu mau cach 618-3080.
MIN_BODY = 300

# ten -> (ky tu vo hinh, thay bang gi)
INVISIBLE = {
    "BOM": ("﻿", ""),
    "NBSP": (" ", " "),
    "ZWSP": ("​", ""),
    "SHY": ("­", ""),
}

HEADING = re.compile(r"^#{1,6} ", re.M)
HEADING_LINE = re.compile(r"^(#{1,6}) (.*)$", re.M)


def strip_invisible(text):
    counts = {}
    for ten, (ch, thay) in INVISIBLE.items():
        counts[ten] = text.count(ch)
        if counts[ten]:
            text = text.replace(ch, thay)
    return text, counts


def demote_form_headings(text):
    return FORM_HEADING.subn(lambda m: m.group(2), text)


def demote_pseudo_headings(text):
    return PSEUDO_HEADING.subn(lambda m: m.group(1), text)


def relevel_annex_headings(text):
    n = sum(1 for m in ANNEX_HEADING.finditer(text) if m.group(1) != ANNEX_LEVEL)
    return ANNEX_HEADING.sub(lambda m: f"{ANNEX_LEVEL} {m.group(2)}", text), n


def promote_annex_marks(text):
    marks = [(m.start(), m.end(), m.group(1)) for m in ANNEX_MARK.finditer(text)]
    # Ranh gioi la heading HOAC moc phu luc. Tinh ca heading thi sau khi nang,
    # moc vua nang van con la ranh gioi, nen chay lai cho ket qua y het.
    bounds = sorted([m.start() for m in HEADING.finditer(text)] + [m[0] for m in marks])
    keep = []
    for start, end, name in marks:
        nxt = next((b for b in bounds if b > start), len(text))
        if nxt - start > MIN_BODY:
            keep.append((start, end, name))
    for start, end, name in reversed(keep):
        text = text[:start] + f"{ANNEX_LEVEL} {name}" + text[end:]
    return text, len(keep)


def clean(text):
    text, n = strip_invisible(text)
    text, n["form"] = demote_form_headings(text)
    text, n["pseudo"] = demote_pseudo_headings(text)
    text, n["mark"] = promote_annex_marks(text)
    text, n["level"] = relevel_annex_headings(text)
    return text, n


def title_paths(text):
    """Dung lai duong dan tieu de dung cach MarkDownReader noi current_titles.

    markdown_reader.py:489-495 nuoi mot stack, pop khi stack[-1].level >= level;
    markdown_reader.py:620 lay current_titles = parent_titles + [node.title];
    markdown_reader.py:663 noi lai bang " / " thanh ten VA id cua chunk.
    """
    stack, out = [], []
    for m in HEADING_LINE.finditer(text):
        lvl, title = len(m.group(1)), m.group(2).strip()
        while stack and stack[-1][0] >= lvl:
            stack.pop()
        stack.append((lvl, title))
        out.append(" / ".join(t for _, t in stack))
    return out


def main():
    write = "--write" in sys.argv
    total = defaultdict(int)
    touched = 0
    h_before = h_after = 0

    for path in all_md():
        old = path.read_text(encoding="utf-8")
        new, n = clean(old)
        h_before += len(HEADING.findall(old))
        h_after += len(HEADING.findall(new))
        if new == old:
            continue
        touched += 1
        for k, v in n.items():
            total[k] += v
        print(
            "%-44s BOM=%d NBSP=%d ZWSP=%d SHY=%d"
            " | ha: bieu mau=%d gia=%d | moc nang=%d cap sua=%d"
            % (
                path.name[:44],
                n["BOM"],
                n["NBSP"],
                n["ZWSP"],
                n["SHY"],
                n["form"],
                n["pseudo"],
                n["mark"],
                n["level"],
            )
        )
        # Ke toan heading: chi duoc mat dung so heading da co y ha xuong, va chu
        # cua heading bi ha phai con nguyen trong file.
        cho_doi = (
            len(HEADING.findall(old)) - n["form"] - n["pseudo"] + n["mark"]
        )
        that = len(HEADING.findall(new))
        assert that == cho_doi, f"{path.name}: heading {that} != cho doi {cho_doi}"
        for txt in (m.group(1) for m in PSEUDO_HEADING.finditer(old)):
            assert txt in new, f"{path.name}: mat chu khi ha heading: {txt[:40]}"

    print(
        "\nfile sua: %d | BOM: %d | NBSP: %d | ZWSP: %d | SHY: %d"
        % (touched, total["BOM"], total["NBSP"], total["ZWSP"], total["SHY"])
    )
    print(
        "heading ha: bieu mau %d, gia %d"
        " | moc phu luc nang: %d | cap moc sua: %d"
        % (
            total["form"],
            total["pseudo"],
            total["mark"],
            total["level"],
        )
    )
    print(
        "heading toan corpus: %d -> %d (= %d - %d - %d + %d)"
        % (
            h_before,
            h_after,
            h_before,
            total["form"],
            total["pseudo"],
            total["mark"],
        )
    )

    if not write:
        print("Chay thu. Them --write de ghi that.")
        return 0

    for path in all_md():
        old = path.read_text(encoding="utf-8")
        new, _ = clean(old)
        if new != old:
            path.write_text(new, encoding="utf-8")
    return self_check()


def self_check():
    """Sach ky tu vo hinh, khong con heading gia, duong dan tieu de duy nhat,
    va chay lai khong sinh thay doi nao."""
    bad = []
    paths = defaultdict(list)
    n_heading = 0

    for path in all_md():
        text = path.read_text(encoding="utf-8")
        for ten, (ch, _) in INVISIBLE.items():
            if ch in text:
                bad.append((path.name, f"con {ten} ({text.count(ch)} cho)"))
        if FORM_HEADING.search(text):
            bad.append((path.name, "con heading Dieu bieu mau"))
        if PSEUDO_HEADING.search(text):
            bad.append((path.name, "con heading gia (tu khoa khong kem so)"))
        again, _ = clean(text)
        if again != text:
            bad.append((path.name, "chay lai van con doi -> khong on dinh"))
        for p in title_paths(text):
            paths[p].append(path.name)
            n_heading += 1

    trung = {k: v for k, v in paths.items() if len(v) > 1}
    for k, v in trung.items():
        bad.append((v[0], f"duong dan tieu de trung {len(v)} lan: {k[:70]}"))

    print(f"heading dem lai: {n_heading} | duong dan tieu de trung: {len(trung)}")
    if bad:
        print("[FAIL]")
        for n, why in bad:
            print("   ", n, "->", why)
        return 1
    print(
        "[self-check ok] sach ky tu vo hinh, khong con heading gia,"
        " duong dan tieu de duy nhat, chay lai khong doi"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
