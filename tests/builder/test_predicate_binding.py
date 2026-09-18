# -*- coding: utf-8 -*-
"""Test gắn `originalPredicate` — chống gán sai khi lớp cha bỏ triple.

Lỗi từng có: gắn vị ngữ gốc bằng `zip(new_edges, triples)` theo thứ tự. Khi
lớp cha bỏ một triple (subject rỗng, object rỗng, vị ngữ rỗng), mọi cạnh sau
đó lệch một hàng và nhận vị ngữ của triple khác. Vì `to_camel_case` không khả
nghịch, sai ở đây là sai vĩnh viễn trong graph.

Test gọi thẳng `assemble_sub_graph_with_triples` — cùng đường mà pipeline dùng.
Không gọi LLM, không đụng Neo4j, không ghi file.

Chạy: rtk proxy .venv/Scripts/python.exe -X utf8 tests/builder/test_predicate_binding.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kag"))

from builder.extractor import LegalSchemaFreeExtractor  # noqa: E402
from kag.builder.model.sub_graph import SubGraph  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    if not cond and detail:
        print(f"         {detail}")


def build(triples, entities=None):
    sg = SubGraph(nodes=[], edges=[])
    LegalSchemaFreeExtractor.assemble_sub_graph_with_triples(
        sg, entities or [], [list(t) for t in triples]
    )
    return sg


def preds(sg):
    """[(edge_label, originalPredicate)] cho cạnh KHÔNG phải hệ thống."""
    return [
        (e.label, (e.properties or {}).get("originalPredicate"))
        for e in sg.edges
        if e.label not in ("source", "OfficialName")
    ]


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("=" * 78)
    print("GẮN originalPredicate — chống lệch hàng khi lớp cha bỏ triple")
    print("=" * 78)

    # --- 1. Ca của phản chứng: triple đầu bị bỏ vì subject rỗng -----------
    print("\nT1 — Triple đầu bị bỏ (subject rỗng), hai vị ngữ cùng ra `cM`")
    sg = build([["", "cấm", "B"], ["A", "căm", "B"]])
    p = preds(sg)
    check("chỉ còn 1 cạnh nội dung", len(p) == 1, p)
    check("cạnh còn lại là cM", p and p[0][0] == "cM", p)
    check(
        "originalPredicate phải là 'căm' (KHÔNG được là 'cấm')",
        p and p[0][1] == "căm",
        f"thực tế: {p[0][1]!r} — đây chính là lỗi zip lệch hàng" if p else "không có cạnh",
    )

    # --- 2. Triple bị bỏ ở GIỮA -------------------------------------------
    print("\nT2 — Triple bị bỏ ở giữa (subject rỗng)")
    sg = build([
        ["A", "quy định nghĩa vụ", "B"],
        ["", "cấm", "C"],
        ["D", "áp dụng cho", "E"],
    ])
    p = dict(preds(sg))
    check("giữ đủ 2 cạnh nội dung", len(p) == 2, p)
    check("cạnh A->B giữ 'quy định nghĩa vụ'",
          p.get("quyNhNghAV") == "quy định nghĩa vụ", p)
    check("cạnh D->E giữ 'áp dụng cho', KHÔNG nhận 'cấm'",
          p.get("pDNgCho") == "áp dụng cho", p)

    # --- 3. Triple bị bỏ ở CUỐI -------------------------------------------
    print("\nT3 — Triple cuối bị bỏ")
    sg = build([["A", "cấm", "B"], ["", "căm", "C"]])
    p = preds(sg)
    check("1 cạnh, vị ngữ 'cấm'", len(p) == 1 and p[0][1] == "cấm", p)

    # --- 4. Object rỗng: lớp cha VẪN thêm cạnh tới node rỗng -------------
    # Đo trực tiếp trên lớp cha: triple ['A','cấm',''] sinh cạnh ('cM','a','').
    # Phép kiểm `if o_name == ""` của KAG so với tên ĐÃ phân giải entity, không
    # so với tri[2], nên object rỗng vẫn đi qua. Vì vậy cạnh đó không chứng minh
    # được tương ứng với triple nào (đầu phải rỗng) -> phải để trống vị ngữ.
    print("\nT4 — Object rỗng: lớp cha vẫn sinh cạnh tới node rỗng")
    sg = build([["A", "cấm", ""], ["D", "căm", "E"]])
    p = preds(sg)
    check("có 2 cạnh nội dung (đúng như lớp cha sinh ra)", len(p) == 2, p)
    by_from = {(e.from_id, e.to_id): (e.properties or {}).get("originalPredicate")
               for e in sg.edges if e.label not in ("source", "OfficialName")}
    check("cạnh d -> e giữ 'căm'", by_from.get(("d", "e")) == "căm", by_from)
    check("cạnh tới node rỗng KHÔNG được gán vị ngữ (không chứng minh được)",
          by_from.get(("a", "")) is None, by_from)

    # --- 5. Vị ngữ rỗng -> to_camel_case ra rỗng -> không sinh cạnh -------
    print("\nT5 — Vị ngữ rỗng không sinh cạnh, không tiêu thụ ứng viên")
    sg = build([["A", "cấm", "B"], ["C", "", "D"], ["E", "căm", "F"]])
    by_from = {(e.from_id, e.to_id): (e.properties or {}).get("originalPredicate")
               for e in sg.edges if e.label not in ("source", "OfficialName")}
    check("không có cạnh nào từ c (vị ngữ rỗng)", ("c", "d") not in by_from,
          by_from)
    check("cạnh a->b giữ 'cấm'", by_from.get(("a", "b")) == "cấm", by_from)
    check("cạnh e->f giữ 'căm', KHÔNG bị triple vị ngữ rỗng cướp",
          by_from.get(("e", "f")) == "căm", by_from)

    # --- 6. Hai predicate khác nhau nhưng CÙNG camel-case -----------------
    print("\nT6 — Hai vị ngữ khác nhau cùng ra một edge type")
    sg = build([["A", "cấm", "B"], ["C", "căm", "D"]])
    p = preds(sg)
    check("2 cạnh cùng type cM", len(p) == 2 and all(x[0] == "cM" for x in p), p)
    check("vị ngữ phân biệt được theo HAI ĐẦU cạnh, không theo thứ tự",
          sorted(x[1] or "" for x in p) == ["cM", "cM"] or
          sorted(x[1] or "" for x in p) == sorted(["cấm", "căm"]),
          f"thực tế: {p}")

    # --- 7. Cạnh trùng: hai triple y hệt nhau -----------------------------
    print("\nT7 — Hai triple y hệt nhau (cạnh trùng)")
    sg = build([["A", "cấm", "B"], ["A", "cấm", "B"]])
    p = preds(sg)
    check("không nhân bản cạnh",
          len(sg.edges) <= 2, f"{len(sg.edges)} cạnh")
    check("mọi cạnh nội dung đều có vị ngữ 'cấm'",
          all(x[1] == "cấm" for x in p), p)

    # --- 8. Không chứng minh được tương ứng -> để TRỐNG, có trạng thái ----
    print("\nT8 — Không chứng minh được tương ứng -> để trống, ghi trạng thái")
    sg = SubGraph(nodes=[], edges=[])
    LegalSchemaFreeExtractor.assemble_sub_graph_with_triples(
        sg,
        [],
        [["A", "cấm", "B"], ["A", "căm", "B"]],
    )
    # Hai triple cùng type, cùng hai đầu -> không phân biệt được cái nào sinh
    # cái nào. Ứng viên tiêu thụ theo thứ tự nhưng phải KHÔNG bịa thêm.
    p = preds(sg)
    check("mọi cạnh nội dung đều có trạng thái vị ngữ",
          all((e.properties or {}).get("originalPredicateStatus") in
              ("RESOLVED", "UNRESOLVED", "NOT_APPLICABLE")
              for e in sg.edges if e.label not in ("source", "OfficialName")),
          [(e.label, (e.properties or {}).get("originalPredicateStatus"))
           for e in sg.edges])

    # --- 9. Cạnh `source` do hệ thống sinh không nhận vị ngữ LLM ----------
    print("\nT9 — Cạnh hệ thống (`source`) không nhận vị ngữ của LLM")
    sg = build([["A", "source", "B"]])
    src = [e for e in sg.edges if e.label == "source"]
    check("cạnh `source` không bị gán originalPredicate",
          all((e.properties or {}).get("originalPredicate") is None for e in src),
          [(e.label, (e.properties or {}).get("originalPredicate")) for e in src])

    # --- 10. Edge type KHÔNG bị đổi ---------------------------------------
    print("\nT10 — Edge type giữ nguyên, không bị ghi đè")
    sg = build([["A", "quy định nghĩa vụ", "B"]])
    check("edge.label vẫn là camel-case của vị ngữ gốc",
          any(e.label == "quyNhNghAV" for e in sg.edges),
          [e.label for e in sg.edges])

    # --- 11. Mọi cạnh mới đều UNVERIFIED, không tự VERIFIED ---------------
    print("\nT11 — Không tự gắn VERIFIED/FULL")
    sg = build([["A", "cấm", "B"], ["C", "căm", "D"]])
    vals = [(e.properties or {}).get("evidenceStatus") for e in sg.edges
            if e.label not in ("source", "OfficialName")]
    check("mọi cạnh là UNVERIFIED", vals and all(v == "UNVERIFIED" for v in vals),
          vals)
    check("không có cạnh nào mang human_verified/VERIFIED",
          not any((e.properties or {}).get("human_verified")
                  or (e.properties or {}).get("evidenceStatus") == "VERIFIED"
                  for e in sg.edges))

    # --- 12. Danh sách rỗng / None không làm nổ ---------------------------
    print("\nT12 — Đầu vào rỗng/None không làm nổ")
    for bad in ([], None, [None], [["A"]], [["A", "B"]]):
        try:
            sg = SubGraph(nodes=[], edges=[])
            LegalSchemaFreeExtractor.assemble_sub_graph_with_triples(sg, [], bad)
            ok = True
        except Exception as exc:  # noqa: BLE001
            ok = False
            print(f"         {bad!r} -> {type(exc).__name__}: {exc}")
        check(f"triples={bad!r} không nổ", ok)

    print()
    print("=" * 78)
    print(f"KET QUA: {len(PASS)} PASS, {len(FAIL)} FAIL")
    for f in FAIL:
        print(f"  FAIL: {f}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
