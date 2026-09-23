"""B2.5 shared helpers: official-source text loading + location lookup."""
from pathlib import Path
import importlib
import json
import re
import unicodedata

WORK = Path(__file__).resolve().parent
SRC = WORK / "_b25_src" / "official"


def _try(mods):
    ok = []
    for m in mods:
        try:
            importlib.import_module(m)
            ok.append(m)
        except Exception:
            pass
    return ok


def tools():
    return {
        "pdf": _try(["pypdf", "PyPDF2", "fitz", "pdfminer"]),
        "doc": _try(["docx"]),
        "win": _try(["win32com"]),
    }


def norm(s):
    """Normalize Vietnamese text for comparison (ignore formatting-only diffs)."""
    s = unicodedata.normalize("NFC", s or "")
    s = s.replace("\u00a0", " ").replace("\ufeff", "")
    s = re.sub(r"[\s\u200b]+", " ", s)
    return s.strip()


def fold(s):
    """Aggressive fold: drop everything except letters/digits, lowercase."""
    s = norm(s).lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", s)


def read_text(p):
    """Decode a source file tolerantly (official exports are often mixed encoding)."""
    p = Path(p)
    b = p.read_bytes()
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        pass
    for enc in ("cp1258", "cp1252", "utf-16-le"):
        try:
            t = b.decode(enc)
            if t.count("Điều") >= 3 or "Luật" in t:
                return t
        except Exception:
            continue
    return b.decode("utf-8", errors="replace")


def load_doc(name, exts=(".txt",)):
    for e in exts:
        p = SRC / f"{name}{e}"
        if p.exists():
            return read_text(p)
    return None


def find(text, needle, window=180, limit=5):
    """Return snippets around folded-needle matches (format-insensitive)."""
    hay = text
    fh = fold(hay)
    fn = fold(needle)
    if not fn:
        return []
    out = []
    start = 0
    while len(out) < limit:
        i = fh.find(fn, start)
        if i < 0:
            break
        # map folded index back to original index
        j = k = 0
        while k < i and j < len(hay):
            if fold(hay[j]):
                k += 1
            j += 1
        a = max(0, j - window // 2)
        b = min(len(hay), j + len(needle) + window)
        out.append(norm(hay[a:b]))
        start = i + 1
    return out


def has(text, needle):
    return fold(needle) in fold(text) if needle else False


def article_block(text, article):
    """Extract the text of one Điều (format tolerant), up to next Điều."""
    t = norm(text)
    pat = re.compile(r"Điều\s+" + re.escape(str(article)) + r"\s*\.")
    m = pat.search(t)
    if not m:
        return None
    nxt = re.compile(r"Điều\s+\d+\s*\.").search(t, m.end())
    return t[m.start(): nxt.start() if nxt else len(t)]
