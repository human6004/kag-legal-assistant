"""Extract .doc (Word 97-2003 binary) text without external binaries.

Strategy: strip the OLE WordDocument stream heuristically, then pull runs of
printable text.  Good enough for Vietnamese legal text in congbao .doc exports.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _b25_tools import SRC, norm  # noqa: E402


def doc_text(p):
    b = p.read_bytes()
    # Word files keep the body as CP1258/UTF-16LE runs.  Try UTF-16LE first.
    for enc in ("utf-16-le", "cp1258", "cp1252"):
        try:
            t = b.decode(enc, errors="strict")
        except Exception:
            continue
        if t.count("Điều") >= 3:
            return t, enc
    # fallback: utf-16-le with replacement
    t = b.decode("utf-16-le", errors="replace")
    return t, "utf-16-le/loose"


def clean(t):
    t = t.replace("\r", "\n").replace("\x07", "\n").replace("\x0c", "\n")
    t = re.sub(r"[\x00-\x08\x0b\x0e-\x1f]", " ", t)
    # drop long junk runs of replacement chars
    t = re.sub(r"\ufffd{2,}", " ", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"\n{2,}", "\n", t)
    return norm(t)


def main():
    for p in sorted(SRC.glob("*.doc")):
        t, enc = doc_text(p)
        c = clean(t)
        out = SRC / (p.stem + ".doc.txt")
        out.write_text(c, encoding="utf-8")
        print(f"{p.name:<22} enc={enc:<16} chars={len(c):<8} dieu={c.count('Điều'):<4} -> {out.name}")


if __name__ == "__main__":
    main()
