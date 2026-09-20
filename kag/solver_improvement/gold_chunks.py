# -*- coding: utf-8 -*-
"""Sinh tap chunk vang cho tung cau hoi, de do recall cua retriever.

Y tuong: moi marker trong "answers" da duoc kiem chung la chuoi con nguyen van
cua mot file trong data/processed/. Chunk nao chua marker do thi chunk ay la
chunk vang. Khong phai doan lai thuat toan cat cua LengthSplitter: doc thang
chunk da cat tu ckpt cua chinh LengthSplitter (kag/ckpt/LengthSplitter), do la
nguon chan ly - no chinh la thu da nap vao do thi.

Ket qua: kag/solver/data/gold_chunks.json
    { "<nguyen van cau hoi>": ["<chunk_id>", ...], ... }

Chay (dung o kag/solver):
    ..\\..\\.venv\\Scripts\\python.exe gold_chunks.py
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
CKPT = os.path.join(os.path.dirname(HERE), "ckpt", "LengthSplitter")
QUESTIONS = os.path.join(HERE, "data", "questions_mo_rong.json")
OUT = os.path.join(HERE, "data", "gold_chunks.json")


def norm_text(s: str) -> str:
    """Giu dong bo voi kag/solver/eval.py:norm_text. Sua mot ben phai sua ca hai."""
    import unicodedata

    s = unicodedata.normalize("NFC", s)
    for ch in "*`#_|":
        s = s.replace(ch, "")
    return "".join(s.split()).replace(".", "").replace(",", "").lower()


def load_chunks():
    """Doc toan bo chunk da cat tu ckpt cua LengthSplitter."""
    from diskcache import Cache

    if not os.path.isdir(CKPT):
        sys.exit(
            "Khong thay %s.\n"
            "ckpt nay la so nho cua buoc cat chunk; xoa no la mat va phai tra tien "
            "dung lai do thi. Chay gold_chunks.py truoc khi xoa." % CKPT
        )
    cache = Cache(directory=CKPT, shards=8, timeout=60)
    chunks = {}
    for key in cache.iterkeys():
        for ch in cache[key]:
            chunks[ch.id] = ch
    return chunks


# Mot marker chi duoc dung lam gold neu no chua trong it hon nguong nay chunk.
# Ly do: marker nhu "Luat", "Dieu 13", "Chinh phu", "het hieu luc" chua o hang
# tram chunk. Lay het lam gold thi recall@k luon bang 1,0 va chi so tro thanh
# vo nghia. Do lan dau: 8 cau co >100 chunk vang, cao nhat 693.
MAX_CHUNK_MOI_MARKER = 20

# Cau hoi co nhieu chunk chua cung mot cum tu thi "chunk vang" tro nen mo ho.
# Vi du cau 1 co marker 'danh gia su phu hop' xuat hien o 25 chunk, keo theo
# recall va citation recall bi do thap gia tao (mau so phong len).
#
# Nhung cau nhu vay duoc ghi them mot ban gold "hep": chi lay chunk cua marker
# dac trung nhat, tuc marker khop it chunk nhat - do la chunk chua thong tin
# rieng cua cau tra loi. Ghi vao gold_chunks.json duoi khoa "_hep".
MAX_CHUNK_MOI_CAU_HEP = 3

# Duoi do dai nay thi coi la ten muc luc chu khong phai cau van trong luat
# ("Dieu 45", "Giai thich tu ngu"), khong dung lam gold.
#
# De y: do dai KHONG phai thuoc do dung de phan biet marker dac trung hay chung.
# "Dieu 13" ngan nhung dac trung; "Cong thong tin dien tu mot cua ve tri tue
# nhan tao" dai ma van chua o 22 chunk. Nguong nay chi de chan ten muc luc;
# viec loc that su do MAX_CHUNK_MOI_MARKER o duoi lam.
MIN_DAI_MARKER = 8


def main():
    chunks = load_chunks()
    print("So chunk doc tu ckpt LengthSplitter: %d" % len(chunks))

    questions = json.load(open(QUESTIONS, encoding="utf-8"))

    # Dung san ban chuan hoa cua tung chunk, mot lan, cho ca 1121 chunk.
    # Khong lam buoc nay thi 166 cau x 554 marker x 1121 chunk se rat cham.
    haystack = {cid: norm_text(ch.content) for cid, ch in chunks.items()}

    gold = {}
    gold_hep = {}
    thong_ke = {
        "cau": 0,
        "marker": 0,
        "marker_dung": 0,
        "marker_qua_ngan": [],
        "marker_qua_chung": [],
        "marker_mo_coi": [],
        "cau_cuu_bang_marker_chung": 0,
    }

    for q in questions:
        markers = [g for g in q["answers"] if g and not g.startswith("<")]
        if not markers:
            continue

        ids = set()
        du_phong = []  # (so_chunk, khop) cua moi marker, de cuu cau khi bi loc sach
        theo_marker = []  # (so_chunk, khop) cua moi marker dung duoc
        for m in markers:
            thong_ke["marker"] += 1

            if len(m) < MIN_DAI_MARKER:
                thong_ke["marker_qua_ngan"].append(
                    {"nguon": q.get("nguon", "?"), "marker": m}
                )
                continue

            nm = norm_text(m)
            khop = [cid for cid, content in haystack.items() if nm in content]

            if not khop:
                thong_ke["marker_mo_coi"].append(
                    {"nguon": q.get("nguon", "?"), "marker": m}
                )
            elif len(khop) > MAX_CHUNK_MOI_MARKER:
                thong_ke["marker_qua_chung"].append(
                    {"nguon": q.get("nguon", "?"), "marker": m, "so_chunk": len(khop)}
                )
                du_phong.append((len(khop), khop))
            else:
                thong_ke["marker_dung"] += 1
                ids.update(khop)
                theo_marker.append((len(khop), khop))

        # Moi marker cua cau deu bi loc (vi du cau chi toan moc chung nhu
        # "Dieu 13" + "Bo Khoa hoc va Cong nghe"). De trang gold thi cau do
        # khong do duoc recall, ma do lai dung nhung cau quan trong nhat.
        # Lay marker dac trung nhat - tuc marker khop it chunk nhat - lam gold.
        if not ids and du_phong:
            so_chunk, khop = min(du_phong, key=lambda x: x[0])
            ids.update(khop)
            thong_ke["cau_cuu_bang_marker_chung"] += 1

        gold[q["input"]] = sorted(ids)

        # Ban gold hep: gop dan cac marker tu dac trung nhat cho den khi du
        # MAX_CHUNK_MOI_CAU_HEP chunk. Day la tap "chunk phai lay duoc" ro rang
        # nhat, dung de do hit@k va citation cho cong bang.
        nguon = theo_marker or du_phong
        hep = set()
        for _, khop in sorted(nguon, key=lambda x: x[0]):
            hep.update(khop)
            if len(hep) >= MAX_CHUNK_MOI_CAU_HEP:
                break
        gold_hep[q["input"]] = sorted(hep)[:MAX_CHUNK_MOI_CAU_HEP]

        thong_ke["cau"] += 1

    json.dump(gold, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    out_hep = os.path.join(os.path.dirname(OUT), "gold_chunks_hep.json")
    json.dump(gold_hep, open(out_hep, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print("So cau            : %d" % thong_ke["cau"])
    print("So marker         : %d" % thong_ke["marker"])
    print("Marker dung lam gold : %d" % thong_ke["marker_dung"])
    print("  bo vi qua ngan  : %d" % len(thong_ke["marker_qua_ngan"]))
    print("  bo vi qua chung : %d" % len(thong_ke["marker_qua_chung"]))
    print("  khong tra duoc  : %d" % len(thong_ke["marker_mo_coi"]))
    print("Cau cuu bang marker chung : %d" % thong_ke["cau_cuu_bang_marker_chung"])

    print("\n-- marker bi bo vi qua chung (chua o >%d chunk) --" % MAX_CHUNK_MOI_MARKER)
    for x in sorted(thong_ke["marker_qua_chung"], key=lambda z: -z["so_chunk"])[:12]:
        print("   %5d chunk | %s" % (x["so_chunk"], x["marker"][:70]))

    print("\n-- marker khong tra duoc --")
    for x in thong_ke["marker_mo_coi"][:12]:
        print("   [%s] %s" % (x["nguon"], x["marker"][:70]))

    khong_co = [q for q in gold if not gold[q]]
    print("Cau khong co gold chunk: %d" % len(khong_co))
    for q in khong_co[:5]:
        print("   %s..." % q[:80])

    sizes = sorted(len(v) for v in gold.values())
    if sizes:
        print("So chunk vang/cau : min %d, trung vi %d, max %d, tb %.1f" % (
            sizes[0], sizes[len(sizes) // 2], sizes[-1],
            sum(sizes) / len(sizes),
        ))
    print("\nDa ghi %s" % OUT)
    sizes_hep = sorted(len(v) for v in gold_hep.values())
    print("Da ghi %s (gold hep, toi da %d chunk/cau)" % (
        out_hep, MAX_CHUNK_MOI_CAU_HEP))
    if sizes_hep:
        print("Gold hep/cau      : min %d, trung vi %d, max %d, tb %.1f" % (
            sizes_hep[0], sizes_hep[len(sizes_hep) // 2], sizes_hep[-1],
            sum(sizes_hep) / len(sizes_hep),
        ))


if __name__ == "__main__":
    main()
