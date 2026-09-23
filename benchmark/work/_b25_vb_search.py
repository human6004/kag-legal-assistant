"""Official vanban.chinhphu.vn search client + detail/document fetch.

Results expose: so ky hieu, ngay ban hanh, trich yeu, and a datafiles.chinhphu.vn
signed PDF link (the official published attachment).
"""
import re
import sys
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _b25_tools import SRC, norm  # noqa: E402

BASE = "https://vanban.chinhphu.vn/he-thong-van-ban?classid=2&mode=1"
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "vi,en;q=0.8",
}
_jar = CookieJar()
_op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_jar))


def get(u, timeout=90):
    req = urllib.request.Request(u, headers=UA)
    with _op.open(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def _hidden(h):
    d = {}
    for m in re.finditer(r'<input[^>]*type="hidden"[^>]*>', h):
        tag = m.group(0)
        n = re.search(r'name="([^"]+)"', tag)
        v = re.search(r'value="([^"]*)"', tag)
        if n:
            d[n.group(1)] = v.group(1) if v else ""
    return d


def search(kw, per_page=500):
    h = get(BASE)
    f = _hidden(h)
    names = set(re.findall(r'name="([^"]+)"', h))
    sk = next((n for n in names if n.endswith("$txtSearchKeyword")), None)
    bs = next((n for n in names if n.endswith("$btnSearch")), None)
    rp = next((n for n in names if n.endswith("$drdRecordPerPage")), None)
    hs = next((n for n in names if n.endswith("$hidIsSearch")), None)
    f[sk] = kw
    f[bs] = "Tìm kiếm"
    if hs:
        f[hs] = "1"
    if rp:
        f[rp] = str(per_page)
    hdr = dict(UA)
    hdr["Content-Type"] = "application/x-www-form-urlencoded"
    hdr["Referer"] = BASE
    req = urllib.request.Request(BASE, data=urllib.parse.urlencode(f).encode(), headers=hdr)
    with _op.open(req, timeout=120) as r:
        return r.read().decode("utf-8", errors="replace")


ROW = re.compile(
    r"docid=(\d+)[^>]*>\s*<span class=\"code\">(.*?)</span>.*?"
    r"<span class=\"substract\">(.*?)</span>.*?"
    r'(?:<div class="bl-doc-file"><a href="([^"]+)"[^>]*>)?',
    re.S)


def parse(h):
    rows = []
    blocks = re.split(r"</tr>\s*<tr>", h)
    for b in blocks:
        m = re.search(r"docid=(\d+)", b)
        if not m:
            continue
        code = re.search(r'<span class="code">(.*?)</span>', b, re.S)
        abst = re.search(r'<span class="substract">(.*?)</span>', b, re.S)
        date = re.search(r'<span class="issued-date">(.*?)</span>', b, re.S)
        files = re.findall(r'href="(https://datafiles\.chinhphu\.vn/[^"]+)"', b)
        rows.append({
            "docid": m.group(1),
            "code": norm(re.sub(r"<[^>]+>", " ", code.group(1))) if code else "",
            "date": norm(date.group(1)) if date else "",
            "abstract": norm(re.sub(r"<[^>]+>", " ", abst.group(1))) if abst else "",
            "files": files,
            "url": f"https://vanban.chinhphu.vn/?pageid=27160&docid={m.group(1)}&classid=2",
        })
    seen, out = set(), []
    for r in rows:
        if r["docid"] not in seen:
            seen.add(r["docid"])
            out.append(r)
    return out


if __name__ == "__main__":
    kws = sys.argv[1:] or ["Luật an toàn thông tin mạng"]
    for kw in kws:
        print(f"\n=== {kw!r}")
        try:
            rows = parse(search(kw))
        except Exception as e:
            print("  ERR", type(e).__name__, e)
            continue
        print(f"  rows={len(rows)}")
        for r in rows[:20]:
            print(f"    {r['code']:<22} {r['date']:<12} {r['abstract'][:70]}")
            if r["files"]:
                print(f"        FILE {r['files'][0][:110]}")
