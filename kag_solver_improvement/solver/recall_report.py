# -*- coding: utf-8 -*-
"""Do chat luong truy xuat va trich dan tren file ket qua cua eval.py.

Doc legal_res_<ts>.json trong runs/, doi chieu voi gold_chunks.json (sinh boi
gold_chunks.py), roi in ra:

  - hit@1 / hit@3 / hit@5 / hit@10 / hit@20  : chunk vang co nam trong top-k
    chunk ma retriever lay ve khong. Day chinh la y nghia cua hit3/hit5/hitall
    trong benchmark.txt - truoc day luon bang 0 vi lop cha tra {"recall": None}.
  - recall  : ty le chunk vang duoc lay ve (khong quan tam thu hang)
  - MRR     : 1/hang cua chunk vang dau tien tim thay
  - nDCG@10 : nhu MRR nhung cong don theo vi tri

  - citation precision : trong cac chunk ma cau tra loi dan ra, bao nhieu
    thuc su nam trong tap chunk vang
  - citation recall    : trong cac chunk vang, bao nhieu duoc cau tra loi dan ra

Khong goi LLM, khong ton tien. Chay lai duoc bao nhieu lan cung duoc.

Chay (dung o kag/solver):
    ..\\..\\.venv\\Scripts\\python.exe recall_report.py
    ..\\..\\.venv\\Scripts\\python.exe recall_report.py <duong dan res.json>
"""
import glob
import json
import math
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, "runs")
GOLD = os.path.join(HERE, "data", "gold_chunks.json")
GOLD_HEP = os.path.join(HERE, "data", "gold_chunks_hep.json")

# Cau tra loi dan nguon bang the <reference id="chunk:0_7"></reference>.
# So 0_7 la chi so chunk trong danh sach reference cua traceLog, khong phai
# chunk_id. Xem traceLog.info.reference[i]["chunk_id"] de doi ra id that.
RE_REF = re.compile(r'<reference\s+id="chunk:(\d+)_(\d+)"')


def norm_text(s: str) -> str:
    """Giu dong bo voi kag/solver/eval.py:norm_text."""
    import unicodedata

    s = unicodedata.normalize("NFC", s)
    for ch in "*`#_|":
        s = s.replace(ch, "")
    return "".join(s.split()).replace(".", "").replace(",", "").lower()


def tim_file():
    if len(sys.argv) > 1:
        return sys.argv[1]
    ds = sorted(glob.glob(os.path.join(RUNS, "legal_res_*.json")))
    if not ds:
        sys.exit("Khong thay legal_res_*.json trong %s. Chay eval.py truoc." % RUNS)
    return ds[-1]


def danh_sach_chunk_lay_ve(trace):
    """Tra ve list chunk_id theo DUNG thu tu retriever tra ve.

    Chunk trong traceLog.info.decompose[].chunks dung khoa "chunk_id" (KHONG
    phai "id" - da dinh bay nay mot lan, doc sai khoa thi lay_ve = 0 va moi chi
    so truy xuat deu bang 0 ma khong bao loi).

    Uu tien decompose[] vi do la thu tu tung buoc, reference[] la ban gop da
    sap theo diem. Tinh MRR/nDCG phai dung ban theo buoc moi co y nghia.
    """
    info = (trace or {}).get("info") or {}
    ra = []
    for buoc in info.get("decompose") or []:
        for c in buoc.get("chunks") or []:
            if isinstance(c, dict):
                cid = c.get("chunk_id") or c.get("id")
                if cid:
                    ra.append(cid)
    if not ra:
        for ref in info.get("reference") or []:
            if ref.get("chunk_id"):
                ra.append(ref["chunk_id"])
    return ra


def main():
    path = tim_file()
    res = json.load(open(path, encoding="utf-8"))
    gold = json.load(open(GOLD, encoding="utf-8"))
    gold_hep = json.load(open(GOLD_HEP, encoding="utf-8")) if os.path.exists(GOLD_HEP) else {}
    print("File ket qua : %s" % os.path.basename(path))
    print("So cau       : %d" % len(res))
    print()

    K = (1, 3, 5, 10, 20)
    hit = {k: 0 for k in K}
    hit_hep = {k: 0 for k in K}
    tong_recall = 0.0
    tong_recall_hep = 0.0
    tong_mrr = 0.0
    tong_mrr_hep = 0.0
    tong_ndcg = 0.0
    tong_cp = 0.0
    tong_cr = 0.0
    tong_cp_hep = 0.0
    tong_cr_hep = 0.0
    n = 0
    n_hep = 0
    n_co_gold = 0
    n_co_dan = 0
    chi_tiet = []

    for s in res:
        q = s["input"]
        g = set(gold.get(q) or [])
        gh = set(gold_hep.get(q) or [])
        if not g:
            continue
        n_co_gold += 1

        lay = danh_sach_chunk_lay_ve(s.get("traceLog"))
        # bo trung nhung giu thu tu
        seen = set()
        lay = [c for c in lay if not (c in seen or seen.add(c))]
        if not lay:
            continue
        n += 1

        for k in K:
            if g & set(lay[:k]):
                hit[k] += 1
            if gh and (gh & set(lay[:k])):
                hit_hep[k] += 1

        tong_recall += len(g & set(lay)) / len(g)

        hang = next((i + 1 for i, c in enumerate(lay) if c in g), None)
        if hang:
            tong_mrr += 1.0 / hang

        if gh:
            n_hep += 1
            tong_recall_hep += len(gh & set(lay)) / len(gh)
            hang_hep = next((i + 1 for i, c in enumerate(lay) if c in gh), None)
            if hang_hep:
                tong_mrr_hep += 1.0 / hang_hep

        dcg = sum(
            1.0 / math.log2(i + 2) for i, c in enumerate(lay[:10]) if c in g
        )
        idcg = sum(1.0 / math.log2(i + 2) for i in range(min(len(g), 10)))
        tong_ndcg += (dcg / idcg) if idcg else 0.0

        # --- trich dan ---
        info = (s.get("traceLog") or {}).get("info") or {}
        refs = info.get("reference") or []
        dan = set()
        for m in RE_REF.finditer(s.get("prediction") or ""):
            i = int(m.group(2))
            if 0 <= i < len(refs) and refs[i].get("chunk_id"):
                dan.add(refs[i]["chunk_id"])
        if dan:
            n_co_dan += 1
            tong_cp += len(dan & g) / len(dan)
            tong_cr += len(dan & g) / len(g)
            if gh:
                tong_cp_hep += len(dan & gh) / len(dan)
                tong_cr_hep += len(dan & gh) / len(gh)

        chi_tiet.append(
            {
                "hoi": q,
                "nhom": s.get("nhom", "?"),
                "so_gold": len(g),
                "so_gold_hep": len(gh),
                "lay_ve": len(lay),
                "hang": hang,
                "dan": len(dan),
                "dan_dung": len(dan & g),
                "dan_dung_hep": len(dan & gh),
            }
        )

    if not n:
        sys.exit("Khong co cau nao vua co gold vua co chunk lay ve.")

    print("=== TRUY XUAT (%d cau) ===" % n)
    print("  %-9s %-10s %s" % ("", "gold day du", "gold hep (<=3 chunk)"))
    for k in K:
        print("  hit@%-6d %.3f      %.3f" % (
            k, hit[k] / n, (hit_hep[k] / n_hep) if n_hep else 0.0))
    print("  %-9s %-10.3f %.3f" % ("recall", tong_recall / n,
                                    (tong_recall_hep / n_hep) if n_hep else 0.0))
    print("  %-9s %-10.3f %.3f" % ("MRR", tong_mrr / n,
                                    (tong_mrr_hep / n_hep) if n_hep else 0.0))
    print("  %-9s %-10.3f %s" % ("nDCG@10", tong_ndcg / n, "-"))
    print()
    print("=== TRICH DAN (%d cau co dan nguon) ===" % n_co_dan)
    if n_co_dan:
        print("  %-19s %-10s %s" % ("", "gold day du", "gold hep"))
        print("  %-19s %-10.3f %.3f" % ("citation precision", tong_cp / n_co_dan,
                                        (tong_cp_hep / n_hep) if n_hep else 0.0))
        print("  %-19s %-10.3f %.3f" % ("citation recall", tong_cr / n_co_dan,
                                        (tong_cr_hep / n_hep) if n_hep else 0.0))
    else:
        print("  khong cau nao dan nguon")
    print()

    print("=== 12 cau kho nhat (chunk vang khong duoc lay ve) ===")
    kho = [c for c in chi_tiet if c["hang"] is None]
    for c in kho[:12]:
        print("  [%s] gold %d | lay %d | dan %d (%d dung) | %s..." % (
            c["nhom"], c["so_gold"], c["lay_ve"], c["dan"], c["dan_dung"],
            c["hoi"][:62]))

    print()
    print("=== 12 cau dan sai nhieu nhat ===")
    for c in sorted(chi_tiet, key=lambda z: (z["dan_dung"] - z["dan"]))[:12]:
        if c["dan"] == 0:
            continue
        print("  [%s] dan %d, chi %d dung | gold %d | %s..." % (
            c["nhom"], c["dan"], c["dan_dung"], c["so_gold"], c["hoi"][:62]))

    if len(sys.argv) > 2 and sys.argv[2] == "--json":
        out = os.path.join(RUNS, "recall_chi_tiet.json")
        json.dump(chi_tiet, open(out, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("\nDa ghi %s" % out)


if __name__ == "__main__":
    main()
