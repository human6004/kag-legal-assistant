# -*- coding: utf-8 -*-
"""Test gắn `originalPredicate` — chống gán sai khi triple bị loại.

Lỗi gốc từng có: gắn vị ngữ gốc bằng `zip(new_edges, triples)` theo thứ tự. Khi
một triple bị loại (subject rỗng, object rỗng, vị ngữ rỗng), mọi cạnh sau đó
lệch một hàng và nhận vị ngữ của triple khác.

B3 đổi CÁCH chống lỗi này, không đổi ý nghĩa test. Trước B3 phải khớp cạnh với
triple SAU khi lớp cha đã dựng cạnh (vì lớp cha vứt vị ngữ thô đi), nên mới có
chuyện lệch hàng. Từ B3, cạnh do chính extractor dựng trong cùng vòng lặp với
triple, nên `originalPredicate` lấy thẳng từ triple đang xử lý — không còn khe
nào để lệch. Test dưới đây giữ nguyên các ca cũ và kiểm cùng bất biến:

  * triple bị loại ở đầu/giữa/cuối KHÔNG làm cạnh khác nhận vị ngữ sai;
  * hai vị ngữ khác nhau mà cùng camel-case (`cấm`/`căm` -> `cM`) KHÔNG bị gộp;
  * triple không hợp lệ KHÔNG đẩy hàng của triple hợp lệ.

Điểm CỐ Ý khác bản trước B3: `edge.label` giờ là tên quan hệ canonical trong
Legal.schema, không còn là camel-case của vị ngữ thô (`quyNhNghAV`), và vị ngữ
không map được thì KHÔNG sinh cạnh nào cả — nó vào bằng chứng loại.

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

# Nhãn đầu mút LẤY TỪ NER, nên mọi ca phải cấp entity. Đây không phải chi tiết
# test: B3 coi đầu mút không có nhãn là thiếu bằng chứng và loại triple.
ENTITIES = [
    {"name": "Điều 1", "category": "Article"},
    {"name": "Nghị định 1", "category": "LegalDocument"},
    {"name": "Hành vi", "category": "ProhibitedAct"},
    {"name": "Phạt tiền", "category": "Sanction"},
    {"name": "Nghĩa vụ", "category": "Obligation"},
    {"name": "Thuật ngữ", "category": "LegalTerm"},
    {"name": "Đối tượng", "category": "RegulatedEntity"},
    {"name": "Bộ Công an", "category": "Authority"},
]


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    if not cond and detail:
        print(f"         {detail}")


def build(triples, entities=None):
    """(sub_graph, evidence) — evidence là danh sách triple bị loại."""
    sg = SubGraph(nodes=[], edges=[])
    evidence = []
    LegalSchemaFreeExtractor.assemble_sub_graph_with_triples(
        sg,
        ENTITIES if entities is None else entities,
        [list(t) for t in triples] if triples else triples,
        evidence=evidence,
    )
    return sg, evidence


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
    print("GẮN originalPredicate — chống lệch hàng khi triple bị loại")
    print("=" * 78)

    # --- 1. Ca của phản chứng: triple đầu bị loại vì subject rỗng ----------
    print("\nT1 — Triple đầu bị loại (subject rỗng), cạnh sau không nhận vị ngữ của nó")
    sg, ev = build([
        ["", "quy định nghĩa vụ", "Nghĩa vụ"],
        ["Điều 1", "nghiêm cấm", "Hành vi"],
    ])
    p = preds(sg)
    check("chỉ còn 1 cạnh nội dung", len(p) == 1, p)
    check("cạnh còn lại là prohibits", p and p[0][0] == "prohibits", p)
    check(
        "originalPredicate phải là 'nghiêm cấm' (KHÔNG được là 'quy định nghĩa vụ')",
        p and p[0][1] == "nghiêm cấm",
        f"thực tế: {p[0][1]!r} — đây chính là lỗi zip lệch hàng" if p else "không có cạnh",
    )
    check("triple bị loại có bằng chứng, không drop im lặng",
          [e["rawPredicate"] for e in ev] == ["quy định nghĩa vụ"], ev)

    # --- 2. Triple bị loại ở GIỮA -----------------------------------------
    print("\nT2 — Triple bị loại ở giữa (subject rỗng)")
    sg, ev = build([
        ["Điều 1", "quy định nghĩa vụ", "Nghĩa vụ"],
        ["", "nghiêm cấm", "Hành vi"],
        ["Điều 1", "áp dụng cho", "Đối tượng"],
    ])
    p = dict(preds(sg))
    check("giữ đủ 2 cạnh nội dung", len(p) == 2, p)
    check("cạnh obliges giữ 'quy định nghĩa vụ'",
          p.get("obliges") == "quy định nghĩa vụ", p)
    check("cạnh appliesTo giữ 'áp dụng cho', KHÔNG nhận 'nghiêm cấm'",
          p.get("appliesTo") == "áp dụng cho", p)
    check("đúng 1 bằng chứng loại", len(ev) == 1, ev)

    # --- 3. Triple bị loại ở CUỐI -----------------------------------------
    print("\nT3 — Triple cuối bị loại")
    sg, ev = build([["Điều 1", "nghiêm cấm", "Hành vi"], ["", "quy định nghĩa vụ", "Nghĩa vụ"]])
    p = preds(sg)
    check("1 cạnh, vị ngữ 'nghiêm cấm'",
          len(p) == 1 and p[0][1] == "nghiêm cấm", p)

    # --- 4. Object rỗng: B3 KHÔNG sinh cạnh tới node rỗng -----------------
    # Trước B3 lớp cha vẫn thêm cạnh ('cM','a','') vì phép kiểm `if o_name == ""`
    # của KAG so với tên đã phân giải entity, không so với tri[2]. Cạnh đó không
    # chứng minh được tương ứng với triple nào nên phải để trống vị ngữ.
    # B3 xử thẳng ở đầu vào: đầu mút rỗng là thiếu bằng chứng -> không có cạnh.
    print("\nT4 — Object rỗng: không sinh cạnh, ghi bằng chứng loại")
    sg, ev = build([["Điều 1", "nghiêm cấm", ""], ["Điều 1", "quy định nghĩa vụ", "Nghĩa vụ"]])
    p = dict(preds(sg))
    check("chỉ 1 cạnh nội dung, không có cạnh tới node rỗng", len(p) == 1, p)
    check("cạnh obliges giữ 'quy định nghĩa vụ'",
          p.get("obliges") == "quy định nghĩa vụ", p)
    check("không cạnh nào có đầu mút rỗng",
          all(e.from_id and e.to_id for e in sg.edges),
          [(e.from_id, e.label, e.to_id) for e in sg.edges])
    check("object rỗng vào bằng chứng với UNRESOLVED_ENDPOINT",
          [e["status"] for e in ev] == ["UNRESOLVED_ENDPOINT"], ev)

    # --- 5. Vị ngữ rỗng -> không map được -> không sinh cạnh --------------
    print("\nT5 — Vị ngữ rỗng không sinh cạnh, không tiêu thụ hàng của triple khác")
    sg, ev = build([
        ["Điều 1", "nghiêm cấm", "Hành vi"],
        ["Điều 1", "", "Nghĩa vụ"],
        ["Phạt tiền", "căn cứ pháp lý", "Điều 1"],
    ])
    p = dict(preds(sg))
    check("2 cạnh nội dung", len(p) == 2, p)
    check("cạnh prohibits giữ 'nghiêm cấm'", p.get("prohibits") == "nghiêm cấm", p)
    check("cạnh basedOn giữ 'căn cứ pháp lý', KHÔNG bị triple vị ngữ rỗng cướp",
          p.get("basedOn") == "căn cứ pháp lý", p)
    check("vị ngữ rỗng vào bằng chứng với UNKNOWN_PREDICATE",
          [e["status"] for e in ev] == ["UNKNOWN_PREDICATE"], ev)

    # --- 6. Hai vị ngữ khác nhau nhưng CÙNG camel-case -------------------
    print("\nT6 — 'cấm'/'căm' cùng ra `cM`: cả hai bị loại RIÊNG, không gộp")
    sg, ev = build([["Điều 1", "cấm", "Hành vi"], ["Điều 1", "căm", "Hành vi"]])
    check("không sinh cạnh nào (không có nhãn `cM`)", preds(sg) == [], preds(sg))
    check("hai bằng chứng riêng biệt, giữ nguyên vị ngữ thô",
          [e["rawPredicate"] for e in ev] == ["cấm", "căm"], ev)
    check("không bằng chứng nào mang candidateRelation",
          all("candidateRelation" not in e for e in ev), ev)

    # --- 7. Cạnh trùng: hai triple y hệt nhau ----------------------------
    print("\nT7 — Hai triple y hệt nhau")
    sg, ev = build([["Điều 1", "nghiêm cấm", "Hành vi"]] * 2)
    p = preds(sg)
    check("mỗi triple một cạnh, không tự gộp mất nguồn", len(p) == 2, p)
    check("cả hai cạnh đều là prohibits/'nghiêm cấm'",
          all(x == ("prohibits", "nghiêm cấm") for x in p), p)

    # --- 8. Mọi cạnh nội dung đều RESOLVED, không còn nhánh UNRESOLVED ---
    print("\nT8 — Vị ngữ gốc lấy thẳng từ triple: luôn RESOLVED")
    sg, ev = build([
        ["Điều 1", "nghiêm cấm", "Hành vi"],
        ["Phạt tiền", "áp dụng cho hành vi", "Hành vi"],
    ])
    states = [(e.properties or {}).get("originalPredicateStatus") for e in sg.edges
              if e.label not in ("source", "OfficialName")]
    check("mọi cạnh nội dung RESOLVED", states == ["RESOLVED", "RESOLVED"], states)

    # --- 9. Vị ngữ `source` do LLM nói ra KHÔNG phải cạnh hệ thống -------
    print("\nT9 — LLM nói vị ngữ 'source'/'OfficialName' -> loại, không sinh cạnh hệ thống")
    sg, ev = build([
        ["Điều 1", "source", "Hành vi"],
        ["Điều 1", "OfficialName", "Hành vi"],
    ])
    check("không sinh cạnh nào", sg.edges == [], [e.label for e in sg.edges])
    check("cả hai vào bằng chứng UNKNOWN_PREDICATE",
          [(e["rawPredicate"], e["status"]) for e in ev]
          == [("source", "UNKNOWN_PREDICATE"), ("OfficialName", "UNKNOWN_PREDICATE")],
          ev)

    # --- 10. Edge type là quan hệ canonical, KHÔNG phải camel-case -------
    print("\nT10 — edge.label là tên quan hệ trong Legal.schema")
    sg, ev = build([["Điều 1", "quy định nghĩa vụ", "Nghĩa vụ"]])
    labels = [e.label for e in sg.edges]
    check("edge.label == 'obliges'", labels == ["obliges"], labels)
    check("KHÔNG còn nhãn camel-case 'quyNhNghAV'", "quyNhNghAV" not in labels, labels)

    # --- 11. Mọi cạnh mới đều UNVERIFIED, không tự VERIFIED --------------
    print("\nT11 — Không tự gắn VERIFIED/FULL")
    sg, ev = build([
        ["Điều 1", "nghiêm cấm", "Hành vi"],
        ["Phạt tiền", "thẩm quyền xử phạt", "Bộ Công an"],
    ])
    vals = [(e.properties or {}).get("evidenceStatus") for e in sg.edges
            if e.label not in ("source", "OfficialName")]
    check("mọi cạnh là UNVERIFIED", vals and all(v == "UNVERIFIED" for v in vals),
          vals)
    check("không có cạnh nào mang human_verified/VERIFIED/FULL",
          not any((e.properties or {}).get("human_verified")
                  or (e.properties or {}).get("evidenceStatus") in ("VERIFIED", "FULL")
                  for e in sg.edges))

    # --- 12. Danh sách rỗng / None không làm nổ --------------------------
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
