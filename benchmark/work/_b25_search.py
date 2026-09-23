"""Search congbao.chinhphu.vn (official Công báo) with the correct keyword param."""
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _b25_tools import SRC, norm  # noqa: E402

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "vi,en;q=0.8",
}


def get(url, timeout=45):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.geturl()


def search(kw):
    url = "https://congbao.chinhphu.vn/tim-kiem?keyword=" + urllib.parse.quote(kw)
    b, final = get(url)
    h = b.decode("utf-8", errors="replace")
    items = []
    for m in re.finditer(r'href="(/van-ban/[^"]+?-\d+\.htm)"[^>]*>(.*?)</a>', h, re.S):
        title = norm(re.sub(r"<[^>]+>", " ", m.group(2)))
        if title and (m.group(1), title) not in items:
            items.append((m.group(1), title))
    return url, final, items


def main():
    queries = {
        "91-2025-QH15": "91/2025/QH15",
        "341-2026-ND-CP": "341/2026/NĐ-CP",
        "367-QD-TTg": "367/QĐ-TTg",
        "86-2015-QH13": "86/2015/QH13",
        "35-2018-QH14": "35/2018/QH14",
        "1671-QD-TTg": "1671/QĐ-TTg",
    }
    out = {}
    for name, kw in queries.items():
        try:
            u, f, items = search(kw)
        except Exception as e:
            print(f"ERR {name}: {type(e).__name__} {e}")
            continue
        print(f"\n=== {name}  kw={kw}  ({len(items)} hits)")
        for href, title in items[:8]:
            print(f"    {href}  {title[:80]}")
        out[name] = {"keyword": kw, "hits": [{"href": h, "title": t} for h, t in items[:8]]}
    (SRC / "_search.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
