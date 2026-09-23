"""Crawl congbao issuing-agency/type listings to locate the remaining B2.5 docs."""
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _b25_tools import SRC  # noqa: E402

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "vi,en;q=0.8",
}

WANT = {
    "341/2026/NĐ-CP": r"nghi-dinh-so-341-2026-nd-cp",
    "367/QĐ-TTg": r"quyet-dinh-so-367-qd-ttg",
    "86/2015/QH13": r"luat-so-86-2015-qh13",
    "35/2018/QH14": r"luat-so-35-2018-qh14",
}

LISTINGS = [
    "https://congbao.chinhphu.vn/van-ban-dang-cong-bao/luat-l13.htm",
    "https://congbao.chinhphu.vn/van-ban-dang-cong-bao/quyet-dinh-l2.htm",
    "https://congbao.chinhphu.vn/van-ban-dang-cong-bao/nghi-dinh-l1.htm",
]


def get(u):
    req = urllib.request.Request(u, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", errors="replace")


def page_urls(base, n):
    out = []
    for i in range(1, n + 1):
        out.append(base if i == 1 else f"{base}?page={i}")
    return out


def main():
    urls = []
    for base in LISTINGS:
        urls += page_urls(base, 40)
    hits = {}
    with ThreadPoolExecutor(max_workers=12) as ex:
        for u, h in zip(urls, ex.map(lambda x: (get(x) if True else ""), urls)):
            pass
    print("done")


if __name__ == "__main__":
    main()
