"""B2.5 verification engine.

Two modes:
  report <Qxxx> ...   -> dump a compact verification packet for the given ids
  check               -> mechanical self-check of the audit file

The actual legal judgement is made by the agent reading the packet; this module
only assembles the official text so verification is grounded in real evidence.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _b25_tools import SRC, WORK, norm, fold, read_text  # noqa: E402
from _b25_coverage import MAP, text_for  # noqa: E402

AUDIT = WORK / "B2_5_OFFICIAL_VERIFICATION.json"
CAND = WORK / "final_150_candidate.json"

# Official source metadata per evidence document (verified during discovery)
OFFICIAL = {
    "116/2025/QH15": ("Luật số 116/2025/QH15 - Luật An ninh mạng",
                      "https://congbao.chinhphu.vn/van-ban/luat-so-116-2025-qh15-468678.htm", "congbao.chinhphu.vn"),
    "134/2025/QH15": ("Luật số 134/2025/QH15 - Luật Trí tuệ nhân tạo",
                      "https://congbao.chinhphu.vn/van-ban/luat-so-134-2025-qh15-468694.htm", "congbao.chinhphu.vn"),
    "13/2023/NĐ-CP": ("Nghị định số 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân",
                      "https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-13-2023-nd-cp-39228.htm", "congbao.chinhphu.vn"),
    "330/2026/NĐ-CP": ("Nghị định số 330/2026/NĐ-CP quy định xử phạt vi phạm hành chính lĩnh vực an ninh mạng",
                       "https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-330-2026-nd-cp-470339.htm", "congbao.chinhphu.vn"),
    "71/2025/QH15": ("Luật số 71/2025/QH15 - Luật Công nghiệp công nghệ số",
                     "https://congbao.chinhphu.vn/van-ban/luat-so-71-2025-qh15-45555.htm", "congbao.chinhphu.vn"),
    "24/2018/QH14": ("Luật số 24/2018/QH14 - Luật An ninh mạng",
                     "https://congbao.chinhphu.vn/van-ban/luat-so-24-2018-qh14-39318.htm", "congbao.chinhphu.vn"),
    "142/2026/NĐ-CP": ("Nghị định số 142/2026/NĐ-CP quy định chi tiết Luật Trí tuệ nhân tạo",
                       "https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-142-2026-nd-cp-469480.htm", "congbao.chinhphu.vn"),
    "91/2025/QH15": ("Luật số 91/2025/QH15 - Luật Bảo vệ dữ liệu cá nhân",
                     "https://congbao.chinhphu.vn/van-ban/luat-so-91-2025-qh15-45578.htm", "congbao.chinhphu.vn"),
    "341/2026/NĐ-CP": ("Nghị định số 341/2026/NĐ-CP quy định chi tiết Luật An ninh mạng về mật mã dân sự",
                       "https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-341-2026-nd-cp-470382.htm", "congbao.chinhphu.vn"),
    "367/QĐ-TTg": ("Quyết định số 367/QĐ-TTg ban hành Kế hoạch triển khai thi hành Luật Trí tuệ nhân tạo",
                   "https://vanban.chinhphu.vn/?pageid=27160&docid=210020&classid=2", "vanban.chinhphu.vn"),
    "356/2025/NĐ-CP": ("Nghị định số 356/2025/NĐ-CP quy định chi tiết Luật Bảo vệ dữ liệu cá nhân",
                       "https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-356-2025-nd-cp-468371.htm", "congbao.chinhphu.vn"),
    "331/2026/NĐ-CP": ("Nghị định số 331/2026/NĐ-CP về bảo vệ an ninh mạng đối với hệ thống thông tin",
                       "https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-331-2026-nd-cp-470334.htm", "congbao.chinhphu.vn"),
    "332/2026/NĐ-CP": ("Nghị định số 332/2026/NĐ-CP về kinh doanh sản phẩm, dịch vụ an ninh mạng",
                       "https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-332-2026-nd-cp-470329.htm", "congbao.chinhphu.vn"),
    "05/2026/TT-BKHCN": ("Thông tư số 05/2026/TT-BKHCN - Khung đạo đức trí tuệ nhân tạo quốc gia",
                         "https://congbao.chinhphu.vn/van-ban/thong-tu-so-05-2026-tt-bkhcn-469079.htm", "congbao.chinhphu.vn"),
    "86/2015/QH13": ("Luật số 86/2015/QH13 - Luật An toàn thông tin mạng",
                     "https://vanban.chinhphu.vn/", "vanban.chinhphu.vn"),
    "328/2026/NĐ-CP": ("Nghị định số 328/2026/NĐ-CP về phòng, chống tin giả, tin sai sự thật",
                       "https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-328-2026-nd-cp-470333.htm", "congbao.chinhphu.vn"),
    "53/2022/NĐ-CP": ("Nghị định số 53/2022/NĐ-CP quy định chi tiết Luật An ninh mạng",
                      "https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-53-2022-nd-cp-39253.htm", "congbao.chinhphu.vn"),
    "35/2018/QH14": ("Luật số 35/2018/QH14 sửa đổi, bổ sung một số điều của 37 luật có liên quan đến quy hoạch",
                     "https://vanban.chinhphu.vn/", "vanban.chinhphu.vn"),
    "333/2026/NĐ-CP": ("Nghị định số 333/2026/NĐ-CP quy định chi tiết biện pháp thi hành Luật An ninh mạng",
                       "https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-333-2026-nd-cp-470335.htm", "congbao.chinhphu.vn"),
    "329/2026/NĐ-CP": ("Nghị định số 329/2026/NĐ-CP về lực lượng bảo vệ an ninh mạng",
                       "https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-329-2026-nd-cp-470328.htm", "congbao.chinhphu.vn"),
    "1671/QĐ-TTg": ("Quyết định số 1671/QĐ-TTg phê duyệt Chiến lược quốc gia về trí tuệ nhân tạo đến năm 2030",
                    "https://congbao.chinhphu.vn/van-ban/quyet-dinh-so-1671-qd-ttg-470384.htm", "congbao.chinhphu.vn"),
    "1528/QĐ-TTg": ("Quyết định số 1528/QĐ-TTg về Chương trình quốc gia phát triển nhân lực AI",
                    "https://congbao.chinhphu.vn/van-ban/quyet-dinh-so-1528-qd-ttg-470264.htm", "congbao.chinhphu.vn"),
}


def load_cand():
    return json.loads(CAND.read_text(encoding="utf-8"))


def load_audit():
    if AUDIT.exists():
        return json.loads(AUDIT.read_text(encoding="utf-8"))
    return {"records": []}


def packet(qid, rec):
    """Build a verification packet: question + evidence + official location excerpts."""
    out = [f"### {qid} [{rec['category']}] answerable={rec['answerable']} source={rec['source_id']}"]
    out.append(f"Q: {rec['question']}")
    if rec.get("gold_markers"):
        out.append("MARKERS:")
        for m in rec["gold_markers"]:
            out.append(f"  - {m}")
    evs = rec.get("gold_evidence", [])
    out.append(f"EVIDENCE ({len(evs)}):")
    for e in evs:
        loc = f"Điều {e['article']}" + (f" khoản {e['clause']}" if e.get("clause") else "") + \
              (f" điểm {e['point']}" if e.get("point") else "")
        out.append(f"  [{e['document_id']} | {loc}]")
        out.append(f"    gold: {e.get('text', '')[:600]}")
        text = text_for(e["document_id"])
        if not text:
            out.append("    OFFICIAL: <SOURCE NOT AVAILABLE>")
            continue
        needles = [e.get("text", "")]
        # also try the salient clause head for locating
        head = re.split(r"[.;]", e.get("text", ""))[0]
        if head and head != needles[0]:
            needles.append(head)
        shown = False
        for nd in needles:
            nd = nd.strip()
            if len(nd) < 15:
                continue
            fh, fn = fold(text), fold(nd)
            i = fh.find(fn[:180])
            if i < 0:
                i = fh.find(fn[:90])
            if i >= 0:
                j = k = 0
                while k < i and j < len(text):
                    if fold(text[j]):
                        k += 1
                    j += 1
                a = max(0, j - 120)
                b = min(len(text), j + len(nd) + 120)
                out.append(f"    OFFICIAL: ...{norm(text[a:b])}...")
                shown = True
                break
        if not shown:
            out.append("    OFFICIAL: <text not located verbatim>")
    return "\n".join(out)


def cmd_report(ids):
    cand = {r["id"]: r for r in load_cand()}
    for qid in ids:
        r = cand.get(qid)
        if not r:
            print(f"!! {qid} not found")
            continue
        print(packet(qid, r))
        print()


def cmd_check():
    aud = load_audit()
    recs = {r["id"]: r for r in aud.get("records", [])}
    cand = load_cand()
    missing = [r["id"] for r in cand if r["id"] not in recs]
    print(f"records={len(recs)} missing={len(missing)}")
    if missing:
        print("missing ids:", missing[:20])
    dupes = len(aud.get("records", [])) - len(recs)
    print("duplicates:", dupes)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "report":
        cmd_report(sys.argv[2:])
    else:
        cmd_check()
