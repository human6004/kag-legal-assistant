"""Fetch official sources for the B2.5 documents still missing usable text.

Uses congbao.chinhphu.vn (official Công báo) search + vbpl.vn as fallback.
Writes <name>.url (source pointers) and <name>.web.txt (page text).
Never overwrites an already-good .txt.
"""
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

TARGETS = {
    "91-2025-QH15": "luật bảo vệ dữ liệu cá nhân 91/2025/QH15",
    "341-2026-ND-CP": "nghị định 341/2026/NĐ-CP mật mã dân sự",
    "367-QD-TTg": "quyết định 367/QĐ-TTg kế hoạch triển khai luật trí tuệ nhân tạo",
    "86-2015-QH13": "luật an toàn thông tin mạng 86/2015/QH13",
    "35-2018-QH14": "luật 35/2018/QH14 sửa đổi bổ sung một số điều của 37 luật",
    "1671-QD-TTg": "quyết định 1671/QĐ-TTg chiến lược quốc gia trí tuệ nhân tạo",
}


def get(url, timeout=45):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.geturl()


def strip_html(b):
    t = b.decode("utf-8", errors="replace")
    t = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", t)
    t = re.sub(r"(?is)<br\s*/?>", "\n", t)
    t = re.sub(r"(?is)</(p|div|tr|li|h[1-6])>", "\n", t)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    t = (t.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"')
          .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
    return norm(t)


def congbao_search(q):
    url = "https://congbao.chinhphu.vn/tim-kiem?q=" + urllib.parse.quote(q)
    try:
        b, _ = get(url)
    except Exception as e:
        return []
    h = b.decode("utf-8", errors="replace")
    return sorted(set(re.findall(r"/van-ban/[a-z0-9\-]+-\d+\.htm", h)))


def main():
    report = {}
    for name, q in TARGETS.items():
        hits = congbao_search(q)
        print(f"\n=== {name}  q={q!r}\n    hits={hits[:6]}")
        report[name] = {"query": q, "hits": hits[:10]}
    (SRC / "_fetch_probe.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
