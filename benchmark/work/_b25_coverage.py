"""B2.5 coverage report: which evidence documents have official text, and which Qs are blocked."""
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _b25_tools import SRC, WORK, read_text  # noqa: E402

# evidence document_id -> official text basename (None if still missing)
MAP = {
    "116/2025/QH15": "116-2025-QH15",
    "134/2025/QH15": "134-2025-QH15",
    "13/2023/NĐ-CP": "13-2023-ND-CP",
    "330/2026/NĐ-CP": "330-2026-ND-CP",
    "71/2025/QH15": "71-2025-QH15",
    "24/2018/QH14": "24-2018-QH14",
    "142/2026/NĐ-CP": "142-2026-ND-CP",
    "91/2025/QH15": "91-2025-QH15",
    "341/2026/NĐ-CP": "341-2026-ND-CP",
    "367/QĐ-TTg": None,
    "356/2025/NĐ-CP": "356-2025-ND-CP",
    "331/2026/NĐ-CP": "331-2026-ND-CP",
    "332/2026/NĐ-CP": "332-2026-ND-CP",
    "05/2026/TT-BKHCN": "05-2026-TT-BKHCN",
    "86/2015/QH13": None,
    "328/2026/NĐ-CP": "328-2026-ND-CP",
    "53/2022/NĐ-CP": "53-2022-ND-CP",
    "35/2018/QH14": None,
    "333/2026/NĐ-CP": "333-2026-ND-CP",
    "329/2026/NĐ-CP": "329-2026-ND-CP",
    "1671/QĐ-TTg": "1671-QD-TTg",
    "1528/QĐ-TTg": "1528-QD-TTg",
}


def text_for(doc):
    b = MAP.get(doc)
    if not b:
        return None
    p = SRC / f"{b}.txt"
    return read_text(p) if p.exists() else None


def main():
    d = json.loads((WORK / "final_150_candidate.json").read_text(encoding="utf-8"))
    ready, blocked = [], []
    for x in d:
        docs = {e["document_id"] for e in x.get("gold_evidence", [])}
        if not docs:
            ready.append(x["id"])
            continue
        miss = [c for c in docs if not text_for(c)]
        (blocked if miss else ready).append((x["id"], miss) if miss else x["id"])
    print(f"ready={len(ready)}  blocked={len(blocked)}")
    print("\nblocked questions:")
    cnt = collections.Counter()
    for qid, miss in blocked:
        print(f"  {qid}  missing={miss}")
        for m in miss:
            cnt[m] += 1
    print("\nmissing-document frequency:", dict(cnt))
    for doc, b in MAP.items():
        t = text_for(doc)
        print(f"  {'OK ' if t else 'MISS'} {doc:<18} {len(t) if t else 0}")


if __name__ == "__main__":
    main()
