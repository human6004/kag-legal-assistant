# -*- coding: utf-8 -*-
from pathlib import Path
root = Path("data/processed")
for p in sorted(root.rglob("*.md")):
    lines = p.read_text(encoding="utf-8").splitlines()
    print(f"{p.name[:40]:40} | {lines[1] if len(lines)>1 else ''}")
