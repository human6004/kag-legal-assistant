"""Query the official vanban.chinhphu.vn ASP.NET search (POST + VIEWSTATE)."""
import re
import sys
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _b25_tools import norm  # noqa: E402

BASE = "https://vanban.chinhphu.vn/he-thong-van-ban?classid=2&mode=1"
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "vi,en;q=0.8",
}

_jar = CookieJar()
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_jar))


def get(u, timeout=60):
    req = urllib.request.Request(u, headers=UA)
    with _opener.open(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def hidden(h):
    d = {}
    for m in re.finditer(r'<input[^>]*type="hidden"[^>]*>', h):
        tag = m.group(0)
        n = re.search(r'name="([^"]+)"', tag)
        v = re.search(r'value="([^"]*)"', tag)
        if n:
            d[n.group(1)] = v.group(1) if v else ""
    return d


def post(fields, timeout=90):
    body = urllib.parse.urlencode(fields).encode()
    hdr = dict(UA)
    hdr["Content-Type"] = "application/x-www-form-urlencoded"
    hdr["Referer"] = BASE
    req = urllib.request.Request(BASE, data=body, headers=hdr)
    with _opener.open(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def search(kw, per_page=50):
    h = get(BASE)
    f = hidden(h)
    # collect the real control names present in this page build
    names = set(re.findall(r'name="([^"]+)"', h))
    sk = next((n for n in names if n.endswith("$txtSearchKeyword")), None)
    bs = next((n for n in names if n.endswith("$btnSearch")), None)
    rp = next((n for n in names if n.endswith("$drdRecordPerPage")), None)
    hs = next((n for n in names if n.endswith("$hidIsSearch")), None)
    if not sk or not bs:
        raise RuntimeError("search controls not found")
    f[sk] = kw
    f[bs] = "Tìm kiếm"
    if hs:
        f[hs] = "1"
    if rp:
        f[rp] = str(per_page)
    out = post(f)
    (Path(__file__).resolve().parent / "_vb_last.html").write_text(out, encoding="utf-8")
    return out


def parse(h):
    """Pull result rows: docid link + title + document number."""
    rows = []
    for m in re.finditer(r'href="([^"]*docid=(\d+)[^"]*)"[^>]*>(.*?)</a>', h, re.S):
        title = norm(re.sub(r"<[^>]+>", " ", m.group(3)))
        if title and len(title) > 5:
            rows.append({"docid": m.group(2), "href": m.group(1), "title": title})
    seen, uniq = set(), []
    for r in rows:
        if r["docid"] not in seen:
            seen.add(r["docid"])
            uniq.append(r)
    return uniq


if __name__ == "__main__":
    for kw in (sys.argv[1:] or ["Luật an toàn thông tin mạng"]):
        print(f"\n=== {kw!r}")
        try:
            h = search(kw)
        except Exception as e:
            print("  ERR", type(e).__name__, e)
            continue
        rows = parse(h)
        print(f"  rows={len(rows)}")
        for r in rows[:15]:
            print(f"    {r['docid']:<8} {r['title'][:100]}")
