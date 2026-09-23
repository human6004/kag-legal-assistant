# -*- coding: utf-8 -*-
import json
from pathlib import Path
rep = json.loads(Path("benchmark/work/_match_report.json").read_text(encoding="utf-8"))
for it in rep["items"]:
    print(f"{it['legacy_id']}\t{it['nhom']}\t{','.join(it['flags']) or 'CLEAN'}\t{it['question'][:110]}")
print("N", len(rep["items"]))
