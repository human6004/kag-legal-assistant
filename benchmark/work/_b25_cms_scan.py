"""Locate congbao detail pages for the 6 B2.5 documents still missing official text.

congbao detail URLs look like /van-ban/<slug>-<cmsid>.htm where cmsid is a
monotonic integer.  Given a known-good neighbour id we can scan a window and
match the page <title> against the document number.
"""
import json
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _b25_tools import SRC, norm  # noqa: E402

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "vi,en;q=0.8",
}

# number string -> regex that must appear in the page title
WANT = {
    "91/2025/QH15": r"91\s*/\s*2025\s*/\s*QH15",
    "341/2026/NĐ-CP": r"341\s*/\s*2026\s*/\s*NĐ-CP",
    "367/QĐ-TTg": r"367\s*/\s*QĐ-TTg",
    "86/2015/QH13": r"86\s*/\s*2015\s*/\s*QH13",
    "35/2018/QH14": r"35\s*/\s*2018\s*/\s*QH14",
    "1671/QĐ-TTg": r"1671\s*/\s*QĐ-TTg",
}


def fetch(cmsid):
    url = f"https://congbao.chinhphu.vn/van-ban/x-{cmsid}.htm"
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            if r.status != 200:
                return cmsid, None, None
            h = r.read().decode("utf-8", errors="replace")
    except Exception:
        return cmsid, None, None
    m = re.search(r"<title>(.*?)</title>", h, re.S)
    title = norm(re.sub(r"\s+", " ", m.group(1))) if m else ""
    m2 = re.search(r'<link rel="canonical" href="([^"]+)"', h)
    canon = m2.group(1) if m2 else None
    return cmsid, title, canon


def scan(lo, hi, workers=16):
    found = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for cmsid, title, canon in ex.map(fetch, range(lo, hi)):
            if not title:
                continue
            for doc, pat in WANT.items():
                if re.search(pat, title):
                    found.append({"doc": doc, "cmsid": cmsid, "title": title, "url": canon})
    return found


if __name__ == "__main__":
    lo, hi = int(sys.argv[1]), int(sys.argv[2])
    res = scan(lo, hi)
    for r in sorted(res, key=lambda x: x["doc"]):
        print(f"{r['doc']:<16} {r['cmsid']:<8} {r['url']}")
        print(f"                 {r['title'][:100]}")
    out = SRC / "_cms_scan.json"
    prev = json.loads(out.read_text(encoding="utf-8")) if out.exists() else []
    prev.extend(res)
    out.write_text(json.dumps(prev, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nscanned {lo}-{hi}; hits={len(res)}; total saved={len(prev)}")
