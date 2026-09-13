# -*- coding: utf-8 -*-
"""Kiểm tra đường dẫn tiêu đề trong corpus là duy nhất.

Vì sao cần: markdown_reader.py:663 và 676 lấy
    full_title = " / ".join(current_titles)
    id = generate_hash_id(full_title)
Id không mang gì phân biệt file hay vị trí, nên hai nhánh cùng đường dẫn sinh
cùng id và writer upsert đè mất một chunk.

KHÔNG import kag: môi trường chỉ có Python 3.14 mà gọi kag pin protobuf đòi
3.10. Dựng lại đường dẫn bằng regex và một stack theo cấp heading, đúng cách
markdown_reader.py:489-495 nuôi stack của nó.

Chạy: python kag/builder/check_title_paths.py
"""

import sys
from collections import defaultdict

from clean_corpus import HEADING, title_paths
from fix_h1 import ROOT, all_md
sys.stdout.reconfigure(encoding="utf-8")  # console Windows mặc định cp1252, in chữ có dấu sẽ lỗi


def self_check():
    loi = []
    tong_heading = 0

    for ten, con in [("data/processed", "processed")]:
        paths = defaultdict(list)
        n_heading = 0
        for path in all_md():
            if con not in str(path):
                continue
            text = path.read_text(encoding="utf-8")
            n_heading += len(HEADING.findall(text))
            for p in title_paths(text):
                paths[p].append(f"{path.relative_to(ROOT)}")
        trung = {k: v for k, v in paths.items() if len(v) > 1}
        tong_heading += n_heading
        print(f"{ten:22s} heading: {n_heading:5d} | đường dẫn: {len(paths):5d} | trùng: {len(trung)}")
        for k, v in trung.items():
            loi.append(f"{ten}: trùng {len(v)} lần -> {k[:90]} ({v[0]})")

    # Số heading đếm bằng regex phải bằng số đường dẫn sinh ra: mỗi heading đúng
    # đúng một đường dẫn. Lệch tức là có heading bị bỏ qua hoặc đếm hai lần.
    n_path = sum(len(title_paths(p.read_text(encoding="utf-8"))) for p in all_md())
    print(f"tổng heading: {tong_heading} | tổng đường dẫn sinh ra: {n_path}")
    if n_path != tong_heading:
        loi.append(f"heading {tong_heading} != đường dẫn {n_path}")

    if loi:
        print("[FAIL]")
        for m in loi:
            print("   ", m)
        return 1
    print("[self-check ok] đường dẫn tiêu đề duy nhất trong data/processed")
    return 0


if __name__ == "__main__":
    sys.exit(self_check())
