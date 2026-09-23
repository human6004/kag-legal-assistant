"""Fetch an official signed document from datafiles.chinhphu.vn and save text."""
import io
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _b25_tools import SRC, norm  # noqa: E402

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
}


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def pdf_text(b):
    from pypdf import PdfReader
    r = PdfReader(io.BytesIO(b))
    return norm("\n".join((p.extract_text() or "") for p in r.pages))


def main():
    name, url = sys.argv[1], sys.argv[2]
    b = fetch(url)
    t = pdf_text(b) if ".pdf" in url.lower() else ""
    if t.strip():
        (SRC / f"{name}.txt").write_text(t, encoding="utf-8")
    (SRC / f"{name}.url").write_text(url, encoding="utf-8")
    print(f"{name}: bytes={len(b)} chars={len(t)} dieu={t.count('Điều')}")
    if t:
        print("HEAD:", t[:400].replace("\n", " | "))


if __name__ == "__main__":
    main()
