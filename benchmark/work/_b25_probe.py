"""Probe national DB class variants for the two laws (Luật 86/2015, Luật 35/2018)."""
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _b25_tools import norm  # noqa: E402

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "vi,en;q=0.8",
}


def probe(u):
    try:
        req = urllib.request.Request(u, headers=UA)
        with urllib.request.urlopen(req, timeout=40) as x:
            b = x.read()
            t = b.decode("utf-8", errors="replace")
            m = re.search(r"<title>(.*?)</title>", t, re.S)
            title = norm(m.group(1)) if m else ""
            print(f"OK  {x.status} len={len(b):<8} dieu={t.count('Điều'):<5} {title[:60]:<62} {u[:80]}")
            return t
    except Exception as e:
        print(f"ERR {type(e).__name__:<16} {str(e)[:40]:<42} {u[:80]}")
    return None


if __name__ == "__main__":
    for u in sys.argv[1:]:
        probe(u)
