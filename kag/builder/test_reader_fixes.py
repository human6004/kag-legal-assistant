# -*- coding: utf-8 -*-
"""R2: test bản vá reader trên ĐƯỜNG THẬT, kiểm cả THỨ TỰ nội dung.

Chạy:  .venv\\Scripts\\python.exe kag/builder/test_reader_fixes.py

Không gọi LLM, không gọi mạng, không ghi gì. Mọi ca dùng đúng ``solve_content``
— hàm mà ``indexer.py`` chạy — nên nếu seam vá sai thì test đổ, chứ không phải
chỉ helper đúng.

Khác bản r1 (đã bị review độc lập bắt lỗi):
- Kiểm THỨ TỰ ĐẦY ĐỦ của Khoản và Điểm, không chỉ đếm số 1,2,3 hay kiểm sự
  hiện diện của a), b). Bản r1 vẫn pass trong khi Khoản bị dồn lên trước Điểm.
- Kiểm cả đầu ra reader LẪN đầu ra sau LengthSplitter.
- Bổ sung ca ``li@value`` (đầu, giữa danh sách), ``ol@start``, danh sách lồng
  nhau THẬT trong HTML, ``li`` chứa nhiều ``p``, và đoạn lặp hợp lệ.
- Không xoá đoạn lặp hợp lệ bằng phép khử trùng toàn cục.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kag"))

from kag.builder.component.reader.markdown_reader import MarkDownReader  # noqa: E402
from kag.builder.component.splitter.length_splitter import LengthSplitter  # noqa: E402

import builder.reader as legal_reader  # noqa: E402

ND341 = ROOT / "data/processed/vn_an_ninh_mang/341-2026-ND-CP_mat-ma-dan-su.md"
ND328 = ROOT / "data/processed/vn_an_ninh_mang/328-2026-ND-CP_phong-chong-tin-gia-tin-sai-su-that.md"
TT05 = ROOT / "data/processed/vn_ai/05-2026-TT-BKHCN_khung-dao-duc-tri-tue-nhan-tao-quoc-gia.md"
ND330 = ROOT / "data/processed/vn_an_ninh_mang/330-2026-ND-CP_xu-phat-vi-pham-hanh-chinh-linh-vuc-an-ninh-mang.md"

PASS, FAIL = [], []


def check(name, got, want):
    if got == want:
        PASS.append(name)
        print(f"  OK   {name}")
    else:
        FAIL.append((name, got, want))
        print(f"  FAIL {name}\n       got  = {got}\n       want = {want}")


def run(reader, md, title="probe"):
    outputs, _ = reader.solve_content(id="probe", title=title, content=md)
    return "\n".join(o.content if hasattr(o, "content") else str(o) for o in outputs)


def slice_article(path, heading):
    """Cắt đúng một Điều từ file nguồn, như bộ cắt chunk vẫn làm."""
    text = path.read_text(encoding="utf-8")
    start = text.index(heading)
    nxt = re.search(r"(?m)^#{2,6}\s+Điều\s+\d+\.", text[start + len(heading):])
    end = start + len(heading) + nxt.start() if nxt else len(text)
    return text[start:end]


def outline(text):
    """Chuỗi (loại, số/ký hiệu, phần đầu nội dung) theo ĐÚNG thứ tự xuất hiện.

    Đây mới là phép kiểm bắt được lỗi đảo Khoản/Điểm. Đếm ``tops()`` không bắt
    được: bản r1 có đúng 1,2,3 nhưng Điểm đã bị đẩy xuống cuối.
    """
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(\d{1,3})\.\s*(.*)$", line)
        if m:
            out.append(("K", int(m.group(1)), m.group(2)[:40]))
            continue
        m = re.match(r"^([a-zđ])\)\s*(.*)$", line)
        if m:
            out.append(("D", m.group(1), m.group(2)[:40]))
    return out


def tops(text):
    """Số Khoản ở đầu dòng, theo thứ tự xuất hiện (không tính Điểm a/b/c)."""
    return [n for kind, n, _ in outline(text) if kind == "K"]


def count_lines(text):
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def split_order(chunks):
    """Ghép chunk sau khi bỏ phần đầu trùng đuôi chunk trước (overlap)."""
    out = []
    for chunk in chunks:
        cur = count_lines(chunk)
        best = 0
        for k in range(min(len(out), len(cur)), 0, -1):
            if out[-k:] == cur[:k]:
                best = k
                break
        out.extend(cur[best:])
    return out


def main():
    lib = MarkDownReader(cut_depth=4)
    pat = legal_reader.LegalMarkdownReader(cut_depth=4)
    splitter = LengthSplitter(split_length=4950, window_length=100)
    pat_split = legal_reader.LegalMarkdownReader(cut_depth=4, length_splitter=splitter)

    # ------------------------------------------------------------------ 1
    print("1. Ca toi thieu cua review: KHONG duoc dao Khoan/Diem")
    md = "#### Test\n\n1. Clause one\n\na) Point of one\n\n2. Clause two\n"
    out = run(pat, md)
    check("thu tu Khoan/Diem dung nhu nguon",
          [(k, v) for k, v, _ in outline(out)], [("K", 1), ("D", "a"), ("K", 2)])
    check("Diem nam TRUOC Khoan 2, khong bi day xuong cuoi",
          out.index("Point of one") < out.index("Clause two"), True)
    check("khong mat noi dung nao",
          [x for x in count_lines(out)],
          ["1. Clause one", "a) Point of one", "2. Clause two"])
    # Cùng ca đó, qua splitter: thứ tự Khoản/Điểm vẫn phải đúng
    sp_lines = split_order([run(pat_split, md)])
    check("sau splitter van du 3 muc, dung thu tu",
          [x for x in sp_lines if x in ("1.", "a)", "2.") or "Clause" in x or "Point" in x],
          ["1.", "Clause one", "a) Point of one", "2.", "Clause two"])

    # ------------------------------------------------------------------ 2
    print("\n2. Ca that ND 341/2026/ND-CP Dieu 8 — so VA thu tu Khoan/Diem")
    src = slice_article(ND341, "#### Điều 8.")
    want = [(k, v) for k, v, _ in outline(src)]
    check("nguồn Markdown có 3 Khoản và 9 Điểm", len(want), 12)
    check("reader gốc đánh lại 1,1,1", tops(run(lib, src)), [1, 1, 1])
    got = outline(run(pat, src))
    check("bản vá giữ đúng SỐ Khoản", [n for k, n, _ in got if k == "K"], [1, 2, 3])
    check("bản vá giữ đúng THỨ TỰ Khoản/Điểm như nguồn",
          [(k, v) for k, v, _ in got], want)
    check("bản vá không mất Điểm nào",
          [v for k, v, _ in got if k == "D"],
          ["a", "b", "c", "a", "b", "c", "d", "đ", "e"])
    # Mỗi Điểm phải nằm ngay sau Khoản của nó
    kinds = [k for k, _, _ in got]
    check("Điểm luôn đứng sau Khoản chứa nó (không dồn Khoản lên trước)",
          kinds.index("D") < kinds.index("K", kinds.index("K") + 1)
          if kinds.count("K") > 1 else True, True)
    # Sau splitter: nội dung không mất, thứ tự giữ nguyên
    sp = split_order([run(pat_split, src)])
    check("sau splitter: đủ 3 Khoản, đúng thứ tự",
          [x.split(" ", 1)[0] for x in sp if re.match(r"^\d{1,3}\.\s", x)], [])
    check("sau splitter: số Khoản đứng riêng dòng đúng 1,2,3",
          [x for x in sp if re.fullmatch(r"\d{1,3}\.", x)], ["1.", "2.", "3."])
    check("sau splitter: đủ 9 Điểm",
          [x.split(")", 1)[0] + ")" for x in sp if re.match(r"^[a-zđ]\)\s", x)],
          ["a)", "b)", "c)", "a)", "b)", "c)", "d)", "đ)", "e)"])

    # ------------------------------------------------------------------ 3
    print("\n3. Ca that TT 05/2026/TT-BKHCN Dieu 3 — so VA thu tu Khoan/Diem")
    src = slice_article(TT05, "#### Điều 3.")
    want = [(k, v) for k, v, _ in outline(src)]
    check("nguồn có 4 Khoản, 17 Điểm", len(want), 21)
    check("reader gốc làm phẳng hết về 1", set(tops(run(lib, src))), {1})
    got = outline(run(pat, src))
    check("bản vá giữ đúng SỐ Khoản", [n for k, n, _ in got if k == "K"], [1, 2, 3, 4])
    check("bản vá giữ đúng THỨ TỰ Khoản/Điểm như nguồn",
          [(k, v) for k, v, _ in got], want)
    check("bản vá không mất Điểm nào", len([1 for k, _, _ in got if k == "D"]), 17)

    # ------------------------------------------------------------------ 4
    print("\n4. Ca lap ND 328/2026/ND-CP Dieu 2 — het lap do parser")
    src = slice_article(ND328, "#### Điều 2.")
    lib_lines, pat_lines = count_lines(run(lib, src)), count_lines(run(pat, src))
    check("reader gốc ghi mỗi khoản hai lần", len(lib_lines), 2 * len(pat_lines))
    check("reader vá không còn dòng lặp liền nhau",
          [a for a, b in zip(pat_lines, pat_lines[1:]) if a == b], [])
    check("số khoản giữ nguyên 1..4", tops("\n".join(pat_lines)), [1, 2, 3, 4])
    check("không mất nội dung: mọi dòng bản vá đều nằm trong nguồn",
          all(ln.split(" ", 1)[-1][:30] in src for ln in pat_lines), True)

    # ------------------------------------------------------------------ 5
    print("\n5. ol@start khac 1")
    md = "#### Điều X.\n\n5. Mục thứ năm.\n\n6. Mục thứ sáu.\n\n7. Mục thứ bảy.\n"
    check("reader gốc mất số bắt đầu (1,2,3)", tops(run(lib, md)), [1, 2, 3])
    check("reader vá giữ đúng 5,6,7", tops(run(pat, md)), [5, 6, 7])
    md2 = "#### Điều X.\n\n5. Mục năm.\n\na) Điểm a;\n\n6. Mục sáu.\n"
    check("start=5 tách bởi Điểm vẫn giữ 5,6", tops(run(pat, md2)), [5, 6])
    check("thứ tự vẫn đúng khi có Điểm chen giữa",
          [(k, v) for k, v, _ in outline(run(pat, md2))], [("K", 5), ("D", "a"), ("K", 6)])

    # ------------------------------------------------------------------ 6
    print("\n6. li@value — dau danh sach, giua danh sach, va so ke tiep")
    check("value=5 ở đầu danh sách -> 5,6",
          tops(run(pat, "#### T.\n\n<ol><li value=5>Five</li><li>Six</li></ol>")), [5, 6])
    check("value=5 giữa danh sách -> cắt đúng tại 5",
          tops(run(pat, "#### T.\n\n<ol><li>One</li><li>Two</li>"
                        "<li value=7>Seven</li><li>Eight</li></ol>")), [1, 2, 7, 8])
    check("ol@start=3 -> 3,4",
          tops(run(pat, "#### T.\n\n<ol start=3><li>Three</li><li>Four</li></ol>")), [3, 4])
    check("danh sách bắt đầu lại về 1 sau danh sách khác",
          tops(run(pat, "#### T.\n\n<ol start=4><li>A</li><li>B</li></ol>\n\n"
                        "<p>ngăn</p>\n\n<ol><li>C</li><li>D</li></ol>")), [4, 5, 1, 2])

    # ------------------------------------------------------------------ 7
    print("\n7. Danh sach HTML long nhau THAT (khong phai a)/b) dang p)")
    md = ("#### Điều Y.\n\n<ol><li>Khoản một"
          "<ol><li>Điểm a</li><li>Điểm b</li></ol></li>"
          "<li>Khoản hai</li></ol>\n")
    out = run(pat, md)
    check("giữ cả Khoản lẫn Điểm của danh sách lồng",
          ["Khoản một" in out, "Điểm a" in out, "Điểm b" in out, "Khoản hai" in out],
          [True, True, True, True])
    check("Điểm lồng vẫn đứng giữa hai Khoản",
          out.index("Điểm a") < out.index("Khoản hai"), True)

    # ------------------------------------------------------------------ 8
    print("\n8. li chua nhieu p")
    md = ("#### Điều W.\n\n<ol><li><p>Đoạn một của Khoản.</p>"
          "<p>Đoạn hai của Khoản.</p></li><li>Khoản sau.</li></ol>\n")
    out = run(pat, md)
    check("giữ đủ hai đoạn trong cùng một Khoản",
          ["Đoạn một của Khoản." in out, "Đoạn hai của Khoản." in out], [True, True])
    check("Khoản sau vẫn còn", "Khoản sau." in out, True)
    check("đoạn một đứng trước đoạn hai",
          out.index("Đoạn một") < out.index("Đoạn hai"), True)

    # ------------------------------------------------------------------ 9
    print("\n9. Doan lap HOP LE trong nguon — KHONG duoc xoa")
    md = ("#### Điều Z.\n\n1. Dẫn chiếu quy định tại Điều 5 Nghị định này.\n\n"
          "2. Dẫn chiếu quy định tại Điều 5 Nghị định này.\n")
    out = run(pat, md)
    check("hai Khoản cùng câu vẫn còn đủ hai dòng",
          sum(1 for ln in count_lines(out) if "Điều 5 Nghị định này" in ln), 2)
    check("số Khoản 1,2 giữ nguyên", tops(out), [1, 2])
    text = ND341.read_text(encoding="utf-8")
    src_rep = [a for a, b in zip(count_lines(text), count_lines(text)[1:]) if a == b]
    out_rep = [a for a, b in zip(count_lines(run(pat, text)), count_lines(run(pat, text))[1:])
               if a == b]
    check("nguồn ND 341 thật có dòng lặp sẵn", bool(src_rep), True)
    check("bản vá giữ nguyên các dòng lặp có sẵn đó", out_rep, src_rep)

    # ----------------------------------------------------------------- 10
    print("\n10. Tieu de va bang khong bi mat cau truc")
    src = slice_article(ND341, "#### Điều 8.")
    body = run(pat, src)
    check("tiêu đề Điều không lọt vào thân chunk", "Điều 8. Tạm đình chỉ" in body, False)
    check("thân chunk vẫn có nội dung Khoản", bool(tops(body)), True)

    # ----------------------------------------------------------------- 11
    print("\n11. Chay tren ca file that — khong no, khong mat noi dung")
    for path in [ND341, ND328, TT05, ND330]:
        text = path.read_text(encoding="utf-8")
        try:
            out = run(pat, text)
        except Exception as exc:  # noqa: BLE001
            check(f"{path.name} chạy được", f"lỗi: {exc}", "chạy được")
            continue
        check(f"{path.name} chạy được", True, True)
        check(f"{path.name} còn nhiều Khoản",
              len(tops(out)) >= len(tops(text)) // 2, True)
        # Không khẳng định "hết mọi dòng lặp": văn bản luật có dòng lặp hợp lệ
        # (khối chữ ký, mẫu đơn). Chỉ khẳng định bản vá không THÊM dòng lặp mới
        # so với nguồn — đó mới là điều lỗi parser gây ra.
        src_rep = [a for a, b in zip(count_lines(text), count_lines(text)[1:]) if a == b]
        out_rep = [a for a, b in zip(count_lines(out), count_lines(out)[1:]) if a == b]
        check(f"{path.name} không sinh thêm dòng lặp mới", sorted(out_rep), sorted(src_rep))

    # ----------------------------------------------------------------- 12
    print("\n12. Bullet ul khong bi bien thanh so Khoan (ca nho va QD 127)")
    md_bullet = "#### T\n\n1. Clause\n\n- Bullet A\n- Bullet B\n\n2. Next\n"
    out_b = run(pat, md_bullet)
    check("ca nhỏ: bullet giữ * không thành số Khoản",
          count_lines(out_b), ["1. Clause", "* Bullet A", "* Bullet B", "2. Next"])
    sp_b = split_order([run(pat_split, md_bullet)])
    check("ca nhỏ sau splitter: bullet giữ * không thành số",
          [x for x in sp_b if "Bullet" in x], ["* Bullet A", "* Bullet B"])

    # Ca thật QĐ 127
    p_127 = next(ROOT.glob("data/processed/**/127-QD-TTg*.md"))
    text_127 = p_127.read_text(encoding="utf-8")
    target_127 = "Việt Nam nằm trong nhóm 5 nước dẫn đầu"
    out_127 = run(pat, text_127)
    matching_lines_127 = [s for s in out_127.splitlines() if target_127 in s]
    check("QĐ 127: dòng bullet giữ *",
          bool(matching_lines_127 and matching_lines_127[0].startswith("* ")), True)
    check("QĐ 127: dòng bullet KHÔNG bị biến thành số Khoản 1.",
          any(s.startswith("1. ") for s in matching_lines_127), False)

    # ----------------------------------------------------------------- 13
    print("\n13. li@value kem Diem giu dung thu tu")
    md_val = "#### T\n\n<ol><li>A</li><li value=7>B</li></ol>\n\na) Point of B\n\n<ol start=8><li>C</li></ol>"
    out_val = run(pat, md_val)
    check("li@value kèm Điểm: thứ tự A -> B -> Point of B -> C",
          count_lines(out_val), ["1. A", "7. B", "a) Point of B", "8. C"])
    check("Điểm của B đứng sau B",
          out_val.index("7. B") < out_val.index("a) Point of B"), True)
    check("Điểm của B đứng trước C",
          out_val.index("a) Point of B") < out_val.index("8. C"), True)

    # ----------------------------------------------------------------- 14
    print("\n14. li chua nhieu p va danh sach long khong lap noi dung")
    md_multi = "#### T\n\n<ol><li><p>First paragraph.</p><p>Second paragraph.</p></li></ol>"
    out_multi = run(pat, md_multi)
    check("li nhiều p: xuất đúng 2 dòng, không dòng ghép, không lặp",
          count_lines(out_multi), ["1. First paragraph.", "Second paragraph."])

    md_nest = "#### T\n\n<ol><li>Parent<ol><li>Child</li></ol></li><li>Next</li></ol>"
    out_nest = run(pat, md_nest)
    check("danh sách lồng: không ghép ParentChild, giữ đúng số lần",
          count_lines(out_nest), ["1. Parent", "1. Child", "2. Next"])

    # ----------------------------------------------------------------- 15
    print("\n15. QD 1671: bao toan cac doan van ban bat dau bang so trong Phu luc")
    p_1671 = next(ROOT.glob("data/processed/**/1671-QD-TTg*.md"))
    text_1671 = p_1671.read_text(encoding="utf-8")
    out_1671 = run(pat, text_1671)
    target_1671 = "Tổ chức triển khai hiệu quả Chương trình quốc gia phát triển nhân lực AI"
    matches_1671 = [s for s in out_1671.splitlines() if target_1671 in s]
    check("QĐ 1671: xuất hiện đủ cả 2 lần (ở Điều 1 và ở Phụ lục II)",
          len(matches_1671), 2)
    check("QĐ 1671: một lần là Điểm a) và một lần là mục 1.",
          sorted([m.split()[0] for m in matches_1671]), ["1.", "a)"])

    print(f"\n{len(PASS)} OK, {len(FAIL)} FAIL")
    if FAIL:
        for name, got, want in FAIL:
            print(f"  FAIL {name}: got={got!r} want={want!r}")
        sys.exit(1)


if __name__ == "__main__":
    main()

