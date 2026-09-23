"""Extract text from the B2.5 official PDFs/DOCs into .txt (no overwrite of good text)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _b25_tools import SRC, norm  # noqa: E402

from pypdf import PdfReader  # noqa: E402


def pdf_text(p):
    r = PdfReader(str(p))
    return "\n".join((pg.extract_text() or "") for pg in r.pages), len(r.pages)


def main():
    for p in sorted(SRC.glob("*.pdf")):
        out = SRC / (p.stem + ".pdf.txt")
        try:
            t, n = pdf_text(p)
        except Exception as e:
            print(f"ERR  {p.name}: {type(e).__name__} {e}")
            continue
        t = norm(t)
        out.write_text(t, encoding="utf-8")
        dieu = t.count("Điều")
        print(f"OK   {p.name:<24} pages={n:<4} chars={len(t):<8} dieu={dieu:<5} -> {out.name}")


if __name__ == "__main__":
    main()
