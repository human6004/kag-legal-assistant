"""Pick the best available official text per evidence document (B2.5)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _b25_tools import SRC  # noqa: E402

# evidence document_id -> candidate basenames in priority order
CAND = {
    "116/2025/QH15": ["116-2025-QH15"],
    "134/2025/QH15": ["134-2025-QH15"],
    "13/2023/NĐ-CP": ["13-2023-ND-CP"],
    "330/2026/NĐ-CP": ["330-2026-ND-CP"],
    "71/2025/QH15": ["71-2025-QH15"],
    "24/2018/QH14": ["24-2018-QH14"],
    "142/2026/NĐ-CP": ["142-2026-ND-CP"],
    "91/2025/QH15": ["91-2025-QH15"],
    "341/2026/NĐ-CP": ["341-2026-ND-CP"],
    "367/QĐ-TTg": ["367-QD-TTg"],
    "356/2025/NĐ-CP": ["356-2025-ND-CP"],
    "331/2026/NĐ-CP": ["331-2026-ND-CP"],
    "332/2026/NĐ-CP": ["332-2026-ND-CP"],
    "05/2026/TT-BKHCN": ["05-2026-TT-BKHCN"],
    "86/2015/QH13": ["86-2015-QH13"],
    "328/2026/NĐ-CP": ["328-2026-ND-CP"],
    "53/2022/NĐ-CP": ["53-2022-ND-CP"],
    "35/2018/QH14": ["35-2018-QH14"],
    "333/2026/NĐ-CP": ["333-2026-ND-CP"],
    "329/2026/NĐ-CP": ["329-2026-ND-CP"],
    "1671/QĐ-TTg": ["1671-QD-TTg"],
    "1528/QĐ-TTg": ["1528-QD-TTg"],
}

EXT_ORDER = [".txt", ".doc.txt", ".pdf.txt"]


def best(doc):
    for base in CAND.get(doc, []):
        for ext in EXT_ORDER:
            p = SRC / (base + ext)
            if p.exists():
                t = p.read_bytes().decode("utf-8", errors="replace")
                if t.count("Điều") >= 3:
                    return p, t
    return None, ""


def main():
    ok = bad = 0
    for doc in CAND:
        p, t = best(doc)
        if p is None:
            print(f"NO-SRC  {doc}")
            bad += 1
        else:
            print(f"OK      {doc:<18} {p.name:<26} chars={len(t):<8} dieu={t.count('Điều')}")
            ok += 1
    print(f"\nusable={ok}  unusable={bad}")


if __name__ == "__main__":
    main()
