"""Regenerate B2_5_OFFICIAL_VERIFICATION_REPORT.md from the audit JSON (checkpoint-safe)."""
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _b25_tools import WORK  # noqa: E402
from _b25_verify import AUDIT, CAND, OFFICIAL  # noqa: E402

REPORT = WORK / "B2_5_OFFICIAL_VERIFICATION_REPORT.md"

CATS = ("definition", "obligation", "sanction_numeric", "effectiveness_metadata",
        "inter_document", "multi_hop", "unanswerable")


def main():
    cand = json.loads(CAND.read_text(encoding="utf-8"))
    aud = json.loads(AUDIT.read_text(encoding="utf-8")) if AUDIT.exists() else {"records": []}
    recs = {r["id"]: r for r in aud["records"]}
    all_ids = [c["id"] for c in cand]
    cand_by = {c["id"]: c for c in cand}
    done = [i for i in all_ids if i in recs]
    notdone = [i for i in all_ids if i not in recs]
    st = collections.Counter(recs[i]["status"] for i in done)

    hosts = collections.Counter()
    for i in done:
        for s in recs[i].get("official_sources", []):
            u = s.get("url", "")
            if "congbao" in u:
                hosts["congbao.chinhphu.vn (Công báo)"] += 1
            elif "vanban.chinhphu" in u:
                hosts["vanban.chinhphu.vn (HTVB Chính phủ)"] += 1
            elif "vbpl" in u:
                hosts["vbpl.vn"] += 1
            elif u:
                hosts["khác"] += 1

    cat_done = collections.Counter(recs[i]["category"] for i in done)
    cat_all = collections.Counter(c["category"] for c in cand)
    issues = [i for i in done if recs[i]["status"] != "OFFICIAL_VERIFIED"]
    una = [i for i in done if recs[i]["category"] == "unanswerable"]

    L = []
    L.append("# B2.5 OFFICIAL VERIFICATION REPORT")
    L.append("")
    L.append("## Progress")
    L.append(f"- checked {len(done)}/150")
    L.append(f"- last completed {done[-1] if done else 'none'}")
    L.append(f"- next {notdone[0] if notdone else 'none (all records present)'}")
    L.append("")
    L.append("## Status counts")
    for k in ("OFFICIAL_VERIFIED", "MINOR_REPAIR", "REPLACE_REQUIRED", "BLOCKER"):
        L.append(f"- {k}: {st.get(k, 0)}")
    L.append(f"- NOT_YET_CHECKED: {len(notdone)}")
    L.append("")
    L.append("## Source counts (official hosts cited)")
    for k, v in hosts.most_common():
        L.append(f"- {k}: {v}")
    L.append("")
    L.append("## Category progress")
    L.append("")
    L.append("| category | checked | total |")
    L.append("|---|---|---|")
    for c in CATS:
        L.append(f"| {c} | {cat_done.get(c, 0)} | {cat_all.get(c, 0)} |")
    L.append("")
    L.append("## Issues found")
    for i in issues:
        r = recs[i]
        L.append("")
        L.append(f"### {i} — {r['status']} ({r['category']})")
        L.append(f"- source_id: {r['source_id']}")
        L.append(f"- notes: {r['notes']}")
        if r.get("proposed_fix"):
            pf = r["proposed_fix"]
            L.append(f"- proposed fix: {pf.get('issue', '')}")
            L.append(f"  - before: `{pf.get('before', '')}`")
            L.append(f"  - after: `{pf.get('after', '')}`")
            L.append(f"  - applied to final_150_candidate.json: {not pf.get('not_applied', False)}")
    L.append("")
    L.append("## Unanswerable audit (Q136-Q150, corpus-unanswerable)")
    L.append("")
    L.append("All 15 keep `answerable=false` (benchmark is fixed to the 23-document corpus).")
    L.append("For each: the nearest in-corpus premise was verified against the official text,")
    L.append("and `outside_corpus_answer_exists` records whether an official document outside")
    L.append("the corpus answers it.")
    L.append("")
    L.append("| id | outside_corpus_answer_exists |")
    L.append("|---|---|")
    for i in una:
        v = recs[i]["outside_corpus_answer_exists"]
        L.append(f"| {i} | {v} |")
    L.append("")
    L.append("## Blocked source documents")
    L.append("")
    L.append("| document | affected items | reason |")
    L.append("|---|---|---|")
    b86 = [i for i in issues if "86/2015/QH13" in json.dumps(recs[i], ensure_ascii=False)]
    b35 = [i for i in issues if "35/2018/QH14" in json.dumps(recs[i], ensure_ascii=False)]
    b367 = [i for i in issues if "367/QĐ-TTg" in json.dumps(recs[i], ensure_ascii=False)]
    if b86:
        L.append(f"| 86/2015/QH13 | {', '.join(b86)} | Official signed PDF is a scanned "
                 "image (no text layer); no OCR available. |")
    if b35:
        L.append(f"| 35/2018/QH14 | {', '.join(b35)} | Official signed PDF is a scanned "
                 "image (no text layer); no OCR available. |")
    if b367:
        L.append(f"| 367/QĐ-TTg | {', '.join(b367)} | Official signed PDF is a scanned "
                 "image (no text layer); no OCR available. |")
    L.append("")
    L.append("## Checkpoint instructions for next session")
    L.append("- Audit file: `benchmark/work/B2_5_OFFICIAL_VERIFICATION.json` (append-only; do not wipe).")
    L.append("- Official texts: `benchmark/work/_b25_src/official/*.txt` (each has a `.url` pointer).")
    L.append("- Validate: `.venv\\Scripts\\python.exe -X utf8 benchmark/work/_b25_validate.py`")
    L.append("- Regenerate this report: `.venv\\Scripts\\python.exe -X utf8 benchmark/work/_b25_report.py`")
    L.append("- Packet for a question: `.venv\\Scripts\\python.exe -X utf8 benchmark/work/_b25_verify.py report Qxxx`")
    L.append(f"- Resume: resolve the {len(issues)} non-OFFICIAL_VERIFIED records above.")
    L.append("")

    REPORT.write_text("\n".join(L), encoding="utf-8")
    print(f"report written: checked={len(done)} issues={len(issues)}")


if __name__ == "__main__":
    main()
