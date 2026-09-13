# -*- coding: utf-8 -*-
"""Kiem tra ban va processing_phrases trong kag/builder/__init__.py.

KHONG import kag: moi truong chi co Python 3.14 ma goi kag pin protobuf doi
3.10. Nen chep nguyen ban regex cu (kag/common/utils.py:196) va ban moi vao
day roi so tren du lieu that trong data/graph/nodes.json.

Do "hong" bang CHU CAI CON LAI, khong bang chuoi bang nhau. Ca hai ban deu
thay "/" va "-" bang dau cach nen khong ban nao tra ve dung chinh ten goc;
cai dang do la co mat chu cai co dau hay khong.

Chay: python kag/builder/check_processing_phrases.py
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NODES = ROOT / "data" / "graph" / "nodes.json"

# ban goc, chep nguyen van tu kag/common/utils.py:196
CU = lambda p: re.sub("[^A-Za-z0-9一-龥 ]", " ", str(p).lower()).strip()

# ban va, chep nguyen van tu kag/builder/__init__.py
MOI = lambda p: re.sub(r"[^\w ]", " ", str(p).lower(), flags=re.U).strip()


def chu(s):
    """Day chu cai/chu so con lai, bo qua cach cat bang dau cach."""
    return re.findall(r"\w+", s, flags=re.U)


def to_camel_case(phrase, fn):
    """Chep nguyen van tu kag/common/utils.py:201, cho phep doi ham ben trong."""
    s = fn(phrase).replace(" ", "_")
    return "".join(
        word.capitalize() if i != 0 else word for i, word in enumerate(s.split("_"))
    )


def self_check():
    names = [n["name"] for n in json.loads(NODES.read_text(encoding="utf-8"))]
    assert names, f"khong doc duoc ten node nao tu {NODES}"
    co_dau = [n for n in names if not n.isascii()]

    hong_cu = [n for n in names if chu(CU(n)) != chu(n.lower())]
    hong_moi = [n for n in names if chu(MOI(n)) != chu(n.lower())]

    print(f"ten node doc tu {NODES.relative_to(ROOT)}: {len(names)} ({len(co_dau)} co dau)")
    print(f"  ban cu  lam mat chu: {len(hong_cu)}/{len(names)}")
    print(f"  ban moi lam mat chu: {len(hong_moi)}/{len(names)}")
    print(f"  vi du ban cu : {names[0]!r} -> {CU(names[0])!r}")
    print(f"  vi du ban moi: {names[0]!r} -> {MOI(names[0])!r}")

    loi = []
    # moi ten co dau phai bi ban cu lam mat chu, khong con it hon
    if len(hong_cu) != len(co_dau):
        loi.append(
            f"cho doi ban cu lam mat chu het {len(co_dau)} ten co dau, thuc te {len(hong_cu)}"
        )
    if hong_moi:
        loi.append(f"ban moi van lam mat chu {len(hong_moi)} ten: {hong_moi[:3]}")

    # ban moi van phai xoa ky tu khong phai chu, khong duoc thanh ham rong
    for goc, cho_doi in [
        ("Điều 3. Giải thích (từ ngữ)", "điều 3  giải thích  từ ngữ"),
        ("Luật 116/2025/QH15", "luật 116 2025 qh15"),
        ("Thông tư 05/2026/TT-BKHCN", "thông tư 05 2026 tt bkhcn"),
    ]:
        that = MOI(goc)
        print(f"  xoa ky tu: {goc!r} -> {that!r}")
        if that != cho_doi:
            loi.append(f"MOI({goc!r}) = {that!r}, cho doi {cho_doi!r}")

    # to_camel_case phai giu nguyen duong kag.common.utils, tuc van thuan ASCII
    for goc in ["thay thế", "được ban hành bởi", "Điều chỉnh"]:
        camel = to_camel_case(goc, CU)
        print(f"  to_camel_case(ban goc): {goc!r} -> {camel!r}")
        if not camel.isascii():
            loi.append(f"to_camel_case({goc!r}) = {camel!r} khong thuan ASCII")

    if loi:
        print("[FAIL]")
        for m in loi:
            print("   ", m)
        return 1
    print("[self-check ok] ban moi giu dau, van xoa ky tu la, edge_type van ASCII")
    return 0


if __name__ == "__main__":
    sys.exit(self_check())
