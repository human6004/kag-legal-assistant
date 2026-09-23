"""Download official congbao document text (.txt via docx/pdf) for located B2.5 docs.

Given a congbao detail URL, pull the .docx download link, unzip it and extract
word/document.xml text.  Saves <name>.txt and <name>.url.
"""
import io
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _b25_tools import SRC, norm  # noqa: E402

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "vi,en;q=0.8",
}


def get(u, timeout=120):
    req = urllib.request.Request(u, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def docx_text(b):
    with zipfile.ZipFile(io.BytesIO(b)) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="replace")
    xml = re.sub(r"(?is)<w:tab[^>]*/>", "\t", xml)
    xml = re.sub(r"(?is)</w:p>", "\n", xml)
    xml = re.sub(r"(?is)<[^>]+>", "", xml)
    for a, b2 in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                  ("&quot;", '"'), ("&apos;", "'")):
        xml = xml.replace(a, b2)
    return norm(xml)


def run(name, detail_url):
    h = get(detail_url).decode("utf-8", errors="replace")
    docx = re.findall(r'href="(https://g7\.cdnchinhphu\.vn/api/download/stream\?[^"]+)"', h)
    pdf = re.findall(r'href="(https://congbaocdn\.chinhphu\.vn/[^"]+\.pdf)"', h)
    docx = [d for d in docx if ".docx" in urllib.parse.unquote(d)]
    url = docx[0].replace("&amp;", "&") if docx else (pdf[0] if pdf else None)
    if url is None:
        print(f"NO-DOWNLOAD {name} ({detail_url})")
        return False
    b = get(url)
    if url.lower().endswith(".pdf") or ".pdf" in urllib.parse.unquote(url):
        from pypdf import PdfReader
        r = PdfReader(io.BytesIO(b))
        t = norm("\n".join((p.extract_text() or "") for p in r.pages))
    else:
        t = docx_text(b)
    out = SRC / f"{name}.txt"
    out.write_text(t, encoding="utf-8")
    (SRC / f"{name}.url").write_text(
        detail_url + "\n" + url + "\n" + (pdf[0] if pdf else ""), encoding="utf-8")
    print(f"OK  {name:<18} chars={len(t):<8} dieu={t.count('Điều'):<5} -> {out.name}")
    return True


import urllib.parse  # noqa: E402

TARGETS = {
    "91-2025-QH15": "https://congbao.chinhphu.vn/van-ban/luat-so-91-2025-qh15-45578.htm",
    "341-2026-ND-CP": "https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-341-2026-nd-cp-470382.htm",
    "1671-QD-TTg": "https://congbao.chinhphu.vn/van-ban/quyet-dinh-so-1671-qd-ttg-470384.htm",
}

if __name__ == "__main__":
    names = sys.argv[1:] or list(TARGETS)
    for n in names:
        try:
            run(n, TARGETS[n])
        except Exception as e:
            print(f"ERR {n}: {type(e).__name__} {e}")
