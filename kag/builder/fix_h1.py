# -*- coding: utf-8 -*-
"""Đưa số hiệu văn bản lên dòng h1 của từng file trong data/processed.

Vì sao cần: extractor ghép passage = chunk.name + "\\n" + chunk.content, mà
chunk.name là đường dẫn tiêu đề (h1 / Chương / Điều). Số hiệu hiện nằm ở dòng
2, tức thân của node h1, nên không chunk Điều nào nhìn thấy nó. LLM sẽ gọi văn
bản là "Nghị định này" và node đó không bao giờ gộp được với node metadata tên
"Nghị định 330/2026/NĐ-CP".

Tên đặt vào h1 lấy từ đúng hàm node_name của metadata_to_graph, để hai bên
không thể lệch nhau.

Chạy thử:  python kag/builder/fix_h1.py
Ghi thật:  python kag/builder/fix_h1.py --write
Chạy lại nhiều lần được, file đã đúng định dạng thì bỏ qua.
"""

import sys
from pathlib import Path

from metadata_to_graph import ROOT, load_metadata, node_name
sys.stdout.reconfigure(encoding="utf-8")  # console Windows mặc định cp1252, in chữ có dấu sẽ lỗi

# Chỉ còn corpus tiếng Việt. Kho tiếng Anh đã xóa vì đề tài chỉ làm luật VN.
MD_DIRS = [ROOT / "data" / "processed"]
SEP = " — "


def all_md():
    return sorted(q for d in MD_DIRS if d.is_dir() for q in d.rglob("*.md"))


def new_h1(name, title):
    return f"# {name}{SEP}{title}"


def plan():
    metas = {m["doc_id"]: m for m in load_metadata()}
    todo, skipped, orphan = [], [], []

    for path in all_md():
        doc_id = path.name.split("_")[0]
        meta = metas.get(doc_id)
        if not meta:
            orphan.append(path)
            continue
        name = node_name(meta)
        lines = path.read_text(encoding="utf-8").splitlines()
        if not lines or not lines[0].startswith("# "):
            orphan.append(path)
            continue
        old = lines[0]
        title = old[2:].strip()
        if title.startswith(name):
            # đã có số hiệu ở đầu, chỉ cần chắc chắn đúng dấu phân cách
            skipped.append((path, old))
            continue
        todo.append((path, old, new_h1(name, title)))

    return todo, skipped, orphan


def apply(todo):
    for path, _, new in todo:
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        ending = "\n" if lines[0].endswith("\n") else ""
        lines[0] = new + ending
        path.write_text("".join(lines), encoding="utf-8")


def self_check():
    """Mọi h1 phải bắt đầu bằng đúng tên node mà metadata_to_graph sinh ra."""
    metas = {m["doc_id"]: m for m in load_metadata()}
    bad = []
    for path in all_md():
        meta = metas.get(path.name.split("_")[0])
        if not meta:
            continue
        name = node_name(meta)
        first = path.read_text(encoding="utf-8").splitlines()[0]
        if not first.startswith(f"# {name}"):
            bad.append((path.name, first[:60]))
    if bad:
        print("[FAIL] h1 không khớp tên node:")
        for n, f in bad:
            print("   ", n, "->", f)
        return 1
    print("[self-check ok] mọi h1 đều bắt đầu bằng tên node trong nodes.json")
    return 0


def main():
    write = "--write" in sys.argv
    todo, skipped, orphan = plan()

    for path, old, new in todo:
        print(f"{path.relative_to(ROOT)}")
        print(f"  - {old[:100]}")
        print(f"  + {new[:100]}")
    print(f"\nsửa: {len(todo)} | đã đúng sẵn: {len(skipped)} | bỏ qua: {len(orphan)}")
    for path in orphan:
        print("   bỏ qua:", path.name)

    if not write:
        print("\nChạy thử. Thêm --write để ghi thật.")
        return 0

    apply(todo)
    print(f"\nĐã ghi {len(todo)} file.")
    return self_check()


if __name__ == "__main__":
    sys.exit(main())
