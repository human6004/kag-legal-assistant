# -*- coding: utf-8 -*-
"""Kiểm tra ba prompt mà không cần cài kag hay chạy server.

Bắt hai lỗi hay gặp nhất: template không phải JSON hợp lệ (LLM sẽ trả về rác)
và category trong ví dụ không có trong Legal.schema (extractor đẩy về Others).

Chạy: python kag/builder/prompt/check_prompts.py
"""

import json
import re
import sys
from pathlib import Path
from string import Template

sys.stdout.reconfigure(encoding="utf-8")  # console Windows mặc định cp1252, in chữ có dấu sẽ lỗi

HERE = Path(__file__).resolve().parent
SCHEMA_FILE = HERE.parent.parent / "schema" / "Legal.schema"

DUMMY = {
    "schema": '["Article"]',
    "input": "đoạn văn mẫu",
    "named_entities": "[]",
    "entity_list": "[]",
}


def schema_types():
    text = SCHEMA_FILE.read_text(encoding="utf-8")
    return set(re.findall(r"^([a-zA-Z0-9\.]+)\(\w+\):", text, re.M))


def extract_template(path):
    src = path.read_text(encoding="utf-8")
    body = src.split('TEMPLATE = """', 1)[1].split('"""', 1)[0]
    return Template(body).safe_substitute(**DUMMY)


def main():
    types = schema_types()
    assert "Article" in types, f"không đọc được schema tại {SCHEMA_FILE}"
    ok = True
    for name in ("ner.py", "std.py", "triple.py"):
        path = HERE / name
        try:
            data = json.loads(extract_template(path))
        except json.JSONDecodeError as exc:
            print(f"[FAIL] {name}: template không phải JSON hợp lệ -> {exc}")
            ok = False
            continue
        used = set(re.findall(r'"category":\s*"([^"]+)"', json.dumps(data)))
        bad = used - types
        if bad:
            print(f"[FAIL] {name}: category không có trong Legal.schema -> {sorted(bad)}")
            ok = False
        else:
            print(f"[ok]   {name}: JSON hợp lệ, {len(used)} category đều khớp schema")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
