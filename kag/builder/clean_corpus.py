# -*- coding: utf-8 -*-
"""Dọn các lỗi định dạng trong corpus markdown.

1. Biểu mẫu trong phụ lục bị viết thành heading "#### Điều ..." nên reader coi
   chúng là điều luật thật. Ví dụ "Điều 1. Cho phép ……………. (3) được kinh doanh".
   Chúng sinh ra thực thể Điều giả toàn dấu chấm lửng. Hạ xuống thành văn bản
   thường, giữ nguyên chữ.

2. Mốc phụ lục ("Phụ lục I - Mẫu số 01", "Mẫu số 03", "Mẫu AI08a: Báo cáo...")
   đang là văn bản thường nên cả phần phụ lục dính vào Điều cuối cùng trước nó.
   Ớ 332/2026/NĐ-CP điều này tạo ra một khối 49.630 ký tự. Nâng chúng lên
   heading h3 để mỗi biểu mẫu là một chunk riêng, tên rõ ràng, VÀ để các heading
   "#### Điều N" bên trong biểu mẫu nằm dưới nó thay vì thành anh em.

3. Heading giả do bộ chuyển đổi docx -> md sinh ra. File .docx gốc không có bất
   kỳ pStyle nào (kiểm bằng zipfile: Counter() rỗng), nên bộ chuyển đổi đoán
   heading bằng từ khóa đầu dòng. Nó khớp cả những ô bảng bắt đầu bằng
   "Chương trình" hay "Mục tiêu", tức từ khóa KHÔNG đi kèm số. Cùng lỗi đó ở
   bản tiếng Anh: ANNEX III của NIS 2 là CORRELATION TABLE, mọi ô bảng ghi đúng
   chữ "Article N" thành heading. Hạ tất cả xuống văn bản thường, giữ nguyên chữ.

4. Ký tự vô hình: BOM (U+FEFF), NBSP (U+00A0), zero-width space (U+200B),
   soft hyphen (U+00AD). NBSP trong heading làm tên chunk không khớp chuỗi với
   bản viết dấu cách thường, ví dụ "## Chương<U+00A0>I".

Mục đích chung của (2) và (3): đường dẫn tiêu đề phải duy nhất. MarkDownReader
(markdown_reader.py:663, 676) lấy id chunk = generate_hash_id(" / ".join(
current_titles)), không mang gì phân biệt file hay vị trí, nên hai nhánh cùng
đường dẫn sẽ dễ mất nhau khi writer upsert.

Chạy thử:  python kag/builder/clean_corpus.py
Ghi thật:  python kag/builder/clean_corpus.py --write
"""

import re
import sys
from collections import defaultdict

from fix_h1 import all_md
sys.stdout.reconfigure(encoding="utf-8")  # console Windows mặc định cp1252, in chữ có dấu sẽ lỗi

# heading Điều của biểu mẫu: có dấu chấm lửng hoặc chuỗi dấu chấm dài
FORM_HEADING = re.compile(r"^(#{1,6}\s*)(Điều\b.*(?:…|\.{4,}).*)$", re.M)

# Từ khóa cấu trúc phải đi kèm số (ả rập hoặc La Mã). Không kèm số là ô bảng
# bị bộ chuyển đổi nhầm thành heading: "Chương trình", "Mục tiêu thử nghiệm".
# Viết hoa toàn bộ ("ĐIỀU KHOẢN THI HÀNH") là tiêu đề phụ lục thật, không khớp
# vì regex phân biệt chữ hoa chữ thường.
PSEUDO_HEADING = re.compile(
    # [^\S\n]* là dấu cách ngang kể cả NBSP, để không kết luận sai khi bước dồn
    # ký tự vô hình chưa chạy ("## Chương<U+00A0>I" vẫn là heading thật).
    r"^#{1,6}[ \t]+((?:Chương|Mục|Điều|Phần)\b(?![^\S\n]*(?:\d|[IVXLC]+\b))[^\n]*)$",
    re.M,
)

# Tên mốc phụ lục, dùng chung cho cả bản văn bản thường và bản đã là heading.
# Dưới ":" là tên biểu mẫu, 142/2026 viết "Mẫu AI08a: Báo cáo tổng kết...";
# phần dưới phải chạy hết dòng nên một câu văn thường không khớp.
ANNEX_NAME = (
    r"(?:Phụ lục\s+[IVXLC]+\s*[-–]\s*)?Mẫu\s+(?:số\s+)?\S+(?:[ \t]*:[^\n]*)?"
    r"|Phụ lục\s+[IVXLC]+"
)

# dòng chỉ là mốc phụ lục, đứng một mình trên dòng
ANNEX_MARK = re.compile(rf"^[ \t]*({ANNEX_NAME})[ \t]*$", re.M)

# cùng tên đó nhưng đã là heading rồi, chỉ cần đưa về đúng cấp
ANNEX_HEADING = re.compile(rf"^(#{{1,6}})[ \t]+({ANNEX_NAME})[ \t]*$", re.M)

# Cấp heading cho mốc phụ lục. h3 chứ không h4: biểu mẫu nào cũng có thể chứa
# "#### Điều N" bên trong (xem 331/2026 Mẫu số 06 và 07), h4 sẽ thành anh em
# của chúng nên đường dẫn tiêu đề không phân biệt được hai biểu mẫu.
ANNEX_LEVEL = "###"

# Mốc nằm sát nhau là mục lục phụ lục, không phải thân biểu mẫu. Đo thật trên
# corpus: mục lục cách mốc sau 24-148 ký tự, thân biểu mẫu cách 618-3080.
MIN_BODY = 300

# tên -> (ký tự vô hình, thay bằng gì)
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
    # Ranh giới là heading HOẶC mốc phụ lục. Tính cả heading thì sau khi nâng,
    # mốc vừa nâng vẫn còn là ranh giới, nên chạy lại cho kết quả y hệt.
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
    """Dựng lại đường dẫn tiêu đề đúng cách MarkDownReader nối current_titles.

    markdown_reader.py:489-495 nuôi một stack, pop khi stack[-1].level >= level;
    markdown_reader.py:620 lấy current_titles = parent_titles + [node.title];
    markdown_reader.py:663 nối lại bằng " / " thành tên VÀ id của chunk.
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
            " | hạ: biểu mẫu=%d giả=%d | mốc nâng=%d cấp sửa=%d"
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
        # Kế toán heading: chỉ được mất đúng số heading đã cố ý hạ xuống, và chữ
        # của heading bị hạ phải còn nguyên trong file.
        cho_doi = (
            len(HEADING.findall(old)) - n["form"] - n["pseudo"] + n["mark"]
        )
        that = len(HEADING.findall(new))
        assert that == cho_doi, f"{path.name}: heading {that} != chờ đợi {cho_doi}"
        for txt in (m.group(1) for m in PSEUDO_HEADING.finditer(old)):
            assert txt in new, f"{path.name}: mất chữ khi hạ heading: {txt[:40]}"

    print(
        "\nfile sửa: %d | BOM: %d | NBSP: %d | ZWSP: %d | SHY: %d"
        % (touched, total["BOM"], total["NBSP"], total["ZWSP"], total["SHY"])
    )
    print(
        "heading hạ: biểu mẫu %d, giả %d"
        " | mốc phụ lục nâng: %d | cấp mốc sửa: %d"
        % (
            total["form"],
            total["pseudo"],
            total["mark"],
            total["level"],
        )
    )
    print(
        "heading toàn corpus: %d -> %d (= %d - %d - %d + %d)"
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
        print("Chạy thử. Thêm --write để ghi thật.")
        return 0

    for path in all_md():
        old = path.read_text(encoding="utf-8")
        new, _ = clean(old)
        if new != old:
            path.write_text(new, encoding="utf-8")
    return self_check()


def self_check():
    """Sạch ký tự vô hình, không còn heading giả, đường dẫn tiêu đề duy nhất,
    và chạy lại không sinh thay đổi nào."""
    bad = []
    paths = defaultdict(list)
    n_heading = 0

    for path in all_md():
        text = path.read_text(encoding="utf-8")
        for ten, (ch, _) in INVISIBLE.items():
            if ch in text:
                bad.append((path.name, f"còn {ten} ({text.count(ch)} chỗ)"))
        if FORM_HEADING.search(text):
            bad.append((path.name, "còn heading Điều biểu mẫu"))
        if PSEUDO_HEADING.search(text):
            bad.append((path.name, "còn heading giả (từ khóa không kèm số)"))
        again, _ = clean(text)
        if again != text:
            bad.append((path.name, "chạy lại vẫn còn đổi -> không ổn định"))
        for p in title_paths(text):
            paths[p].append(path.name)
            n_heading += 1

    trung = {k: v for k, v in paths.items() if len(v) > 1}
    for k, v in trung.items():
        bad.append((v[0], f"đường dẫn tiêu đề trùng {len(v)} lần: {k[:70]}"))

    print(f"heading đếm lại: {n_heading} | đường dẫn tiêu đề trùng: {len(trung)}")
    if bad:
        print("[FAIL]")
        for n, why in bad:
            print("   ", n, "->", why)
        return 1
    print(
        "[self-check ok] sạch ký tự vô hình, không còn heading giả,"
        " đường dẫn tiêu đề duy nhất, chạy lại không đổi"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
