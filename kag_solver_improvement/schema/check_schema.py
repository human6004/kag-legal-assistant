"""Kiểm tra cú pháp Legal.schema mà không cần dựng server.

`knext schema commit` chỉ báo lỗi khi cụm Docker đã chạy và đã đăng ký dự án,
nên một lỗi dấu ngoặc cũng bắt ta đi hết vòng đó. Script này áp dụng đúng các
biểu thức chính quy của knext/schema/marklang/schema_ml.py ngay tại chỗ.

    python check_schema.py
"""

import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")  # console Windows mặc định cp1252, in chữ có dấu sẽ lỗi

NAMESPACE = re.compile(r"^namespace\s+([a-zA-Z0-9]+)$")
TYPE = re.compile(r"^([a-zA-Z0-9\.]+)\((\w+)\):\s*?([a-zA-Z0-9,]+)$")
META = re.compile(
    r"^(desc|properties|relations|hypernymPredicate|regular|spreadable|autoRelate):\s*?(.*)$"
)
PROPERTY = re.compile(r"^([a-zA-Z0-9#]+)\(([\w\.]+)\):\s*?([a-zA-Z0-9,\.]+)$")
SUB = re.compile(r"^(desc|properties|constraint|rule|index):\s*?(.*)$")

VALID_KINDS = {"EntityType", "ConceptType", "EventType", "StandardType"}
BASIC_TYPES = {"Text", "Integer", "Float"}
# mức thụt dòng: 0 kiểu, 5 properties/relations, 8 thuộc tính, 12 index/constraint
LEVELS = {0: TYPE, 5: META, 8: PROPERTY, 12: SUB}


def check(path):
    types, refs, errors = {}, [], []

    for num, raw in enumerate(io.open(path, encoding="utf-8"), 1):
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        body = line.strip()

        if indent not in LEVELS:
            errors.append("dòng %d: thụt dòng %d là không hợp lệ" % (num, indent))
            continue
        if indent == 0 and NAMESPACE.match(body):
            continue

        match = LEVELS[indent].match(body)
        if not match:
            errors.append("dòng %d: sai cú pháp -> %s" % (num, body))
            continue
        if indent == 0:
            types[match.group(1)] = match.group(3)
        elif indent == 8:
            refs.append((num, match.group(3)))

    for name, kind in types.items():
        if kind not in VALID_KINDS:
            errors.append("kiểu %s khai là %s, không hợp lệ" % (name, kind))
    for num, target in refs:
        if target not in BASIC_TYPES and target not in types:
            errors.append("dòng %d: trỏ tới kiểu %s chưa được định nghĩa" % (num, target))

    return types, errors


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    schema = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "Legal.schema")

    types, errors = check(schema)
    print("%s: %d kiểu" % (os.path.basename(schema), len(types)))
    for error in errors:
        print("  LỖI:", error)
    if errors:
        sys.exit(1)
    print("  cú pháp hợp lệ")
