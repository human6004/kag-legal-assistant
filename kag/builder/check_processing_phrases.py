# -*- coding: utf-8 -*-
"""Kiểm tra bản vá processing_phrases trong kag/builder/__init__.py.

KHÔNG import kag: môi trường chỉ có Python 3.14 mà gọi kag pin protobuf đòi
3.10. Nên chép nguyên bản regex cũ (kag/common/utils.py:196) và bản mới vào
đây rồi so trên dữ liệu thật trong data/graph/nodes.json.

Đo "hỏng" bằng CHỮ CÁI CÒN LẠI, không bằng chuỗi bằng nhau. Cả hai bản đều
thay "/" và "-" bằng dấu cách nên không bản nào trả về đúng chính tên gốc;
cái đáng đo là có mất chữ cái có dấu hay không.

Chạy: python kag/builder/check_processing_phrases.py
"""

import json
import re
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")  # console Windows mặc định cp1252, in chữ có dấu sẽ lỗi

ROOT = Path(__file__).resolve().parents[2]
NODES = ROOT / "data" / "graph" / "nodes.json"

# bản gốc, chép nguyên văn từ kag/common/utils.py:196
CU = lambda p: re.sub("[^A-Za-z0-9一-龥 ]", " ", str(p).lower()).strip()

# bản vá, chép nguyên văn từ kag/builder/__init__.py
MOI = lambda p: re.sub(r"[^\w ]", " ", str(p).lower(), flags=re.U).strip()


def chu(s):
    """Đẩy chữ cái/chữ số còn lại, bỏ qua cách cắt bằng dấu cách."""
    return re.findall(r"\w+", s, flags=re.U)


def to_camel_case(phrase, fn):
    """Chép nguyên văn từ kag/common/utils.py:201, cho phép đổi hàm bên trong."""
    s = fn(phrase).replace(" ", "_")
    return "".join(
        word.capitalize() if i != 0 else word for i, word in enumerate(s.split("_"))
    )


def self_check():
    names = [n["name"] for n in json.loads(NODES.read_text(encoding="utf-8"))]
    assert names, f"không đọc được tên node nào từ {NODES}"
    co_dau = [n for n in names if not n.isascii()]

    hong_cu = [n for n in names if chu(CU(n)) != chu(n.lower())]
    hong_moi = [n for n in names if chu(MOI(n)) != chu(n.lower())]

    print(f"tên node đọc từ {NODES.relative_to(ROOT)}: {len(names)} ({len(co_dau)} có dấu)")
    print(f"  bản cũ  làm mất chữ: {len(hong_cu)}/{len(names)}")
    print(f"  bản mới làm mất chữ: {len(hong_moi)}/{len(names)}")
    print(f"  ví dụ bản cũ : {names[0]!r} -> {CU(names[0])!r}")
    print(f"  ví dụ bản mới: {names[0]!r} -> {MOI(names[0])!r}")

    loi = []
    # mọi tên có dấu phải bị bản cũ làm mất chữ, không còn ít hơn
    if len(hong_cu) != len(co_dau):
        loi.append(
            f"chờ đợi bản cũ làm mất chữ hết {len(co_dau)} tên có dấu, thực tế {len(hong_cu)}"
        )
    if hong_moi:
        loi.append(f"bản mới vẫn làm mất chữ {len(hong_moi)} tên: {hong_moi[:3]}")

    # bản mới vẫn phải xóa ký tự không phải chữ, không được thành hàm rỗng
    for goc, cho_doi in [
        ("Điều 3. Giải thích (từ ngữ)", "điều 3  giải thích  từ ngữ"),
        ("Luật 116/2025/QH15", "luật 116 2025 qh15"),
        ("Thông tư 05/2026/TT-BKHCN", "thông tư 05 2026 tt bkhcn"),
    ]:
        that = MOI(goc)
        print(f"  xóa ký tự: {goc!r} -> {that!r}")
        if that != cho_doi:
            loi.append(f"MOI({goc!r}) = {that!r}, chờ đợi {cho_doi!r}")

    # to_camel_case phải giữ nguyên đường kag.common.utils, tức vẫn thuần ASCII
    for goc in ["thay thế", "được ban hành bởi", "Điều chỉnh"]:
        camel = to_camel_case(goc, CU)
        print(f"  to_camel_case(bản gốc): {goc!r} -> {camel!r}")
        if not camel.isascii():
            loi.append(f"to_camel_case({goc!r}) = {camel!r} không thuần ASCII")

    if loi:
        print("[FAIL]")
        for m in loi:
            print("   ", m)
        return 1
    print("[self-check ok] bản mới giữ dấu, vẫn xóa ký tự lạ, edge_type vẫn ASCII")
    return 0


if __name__ == "__main__":
    sys.exit(self_check())
