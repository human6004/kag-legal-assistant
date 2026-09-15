# -*- coding: utf-8 -*-
"""Sinh nodes.json / edges.json cho đồ thị từ các file metadata trong data/metadata.

Lý do: scanner của KAG chỉ nhận .md nên mọi thứ trong metadata (ngày hiệu lực,
trạng thái, chuỗi thay thế) không bao giờ vào đồ thị. Script này nạp thẳng
chúng vào graph qua cơ chế external graph có sẵn của KAG.

Chạy trong thư mục kag/: python builder/metadata_to_graph.py
Kết quả: data/graph/nodes.json, data/graph/edges.json
"""

import json
import re
import sys
from pathlib import Path

import canon_id  # cùng thư mục; kag/builder nằm trên sys.path khi chạy file này

sys.stdout.reconfigure(encoding="utf-8")  # console Windows mặc định cp1252, in chữ có dấu sẽ lỗi

ROOT = Path(__file__).resolve().parents[2]
META_DIR = ROOT / "data" / "metadata"
OUT_DIR = ROOT / "data" / "graph"
SCHEMA_FILE = ROOT / "kag" / "schema" / "Legal.schema"

LABEL = "LegalDocument"


def _norm_id(phrase):
    """Chuẩn hóa id node cho trùng với id mà OpenIE sinh ra.

    Quy tắc nằm ở kag/builder/canon_id.py, dùng chung với bản vá
    SubGraph.add_node trong kag/builder/__init__.py. Trước đây hai bên chép tay
    cùng một regex nên lệch nhau: metadata sinh "nghị định 329 2026 nđ cp" còn
    OpenIE sinh "luật an ninh mạng số 116 2025 qh15", thành hai node rời nhau —
    một node giữ status và chuỗi thay thế, một node giữ cạnh về chunk, không
    truy vấn nào đi được từ bên này sang bên kia.

    Chỉ áp cho id. Trường `name` vẫn giữ nguyên văn vì nó là thứ được hiển thị
    và được vector hóa để entity linking bám vào.
    """
    return canon_id.canon_id(phrase)


# metadata field -> tên thuộc tính trong Legal.schema
PROP_MAP = {
    "doc_number": "docNumber",
    "doc_type": "docType",
    "issuing_body": "issuingBody",
    "date_effective": "dateEffective",
    "date_issued": "dateIssued",
    "date_expired": "dateExpired",
    "status": "status",
    "source_url": "sourceUrl",
}

# field danh sách trong metadata -> (tên quan hệ, có đảo chiều không)
REL_MAP = {
    "supersedes": ("supersedes", False),
    "superseded_by": ("supersedes", True),
    "amends": ("amends", False),
    "amended_by": ("amends", True),
    "implements": ("implementsDoc", False),
    "implemented_by": ("implementsDoc", True),
}

# quan hệ ngược, sinh thêm để truy vấn một bước chạy được cả hai chiều
INVERSE = {"supersedes": "supersededBy"}


def schema_props(label):
    """Đọc trực tiếp Legal.schema, không cần server, để bắt sai tên thuộc tính."""
    text = SCHEMA_FILE.read_text(encoding="utf-8")
    blocks = re.split(r"^(?=\S)", text, flags=re.M)
    for block in blocks:
        if block.startswith(f"{label}("):
            return set(re.findall(r"^\s{8}(\w+)\(", block, re.M))
    raise SystemExit(f"không tìm thấy type {label} trong {SCHEMA_FILE}")


def schema_rels(label):
    text = SCHEMA_FILE.read_text(encoding="utf-8")
    blocks = re.split(r"^(?=\S)", text, flags=re.M)
    for block in blocks:
        if block.startswith(f"{label}("):
            tail = block.split("relations:", 1)
            if len(tail) == 1:
                return set()
            return set(re.findall(r"^\s{8}(\w+)\(", tail[1], re.M))
    return set()


def node_name(meta):
    """Tên node phải trùng cách LLM gọi văn bản, xem prompt std (legal_std)."""
    number = (meta.get("doc_number") or "").strip()
    if not number:
        return meta["title"].strip()
    doc_type = (meta.get("doc_type") or "").strip()
    if meta.get("jurisdiction") == "VN" and doc_type:
        return f"{doc_type} {number}"
    return number


def load_metadata():
    metas = []
    seen = {}
    for path in sorted(META_DIR.glob("*.json")):
        if path.name.startswith("_"):
            continue
        meta = json.loads(path.read_text(encoding="utf-8"))
        if not meta.get("doc_id"):
            continue
        key = meta["doc_id"]
        if key in seen:
            print(f"[bỏ qua] trùng doc_id {key}: {path.name} (đã có {seen[key]})")
            continue
        seen[key] = path.name
        metas.append(meta)
    return metas


def main():
    props_allowed = schema_props(LABEL)
    rels_allowed = schema_rels(LABEL)
    metas = load_metadata()

    nodes = {}
    number_to_name = {}
    for meta in metas:
        name = node_name(meta)
        props = {}
        for src, dst in PROP_MAP.items():
            value = (meta.get(src) or "").strip()
            if value:
                props[dst] = value
        desc = meta.get("title", "").strip()
        basis = (meta.get("status_basis") or "").strip()
        if basis:
            desc = f"{desc}. {basis}"
        props["desc"] = desc
        props["semanticType"] = (meta.get("doc_type") or LABEL).strip()

        bad = set(props) - props_allowed
        if bad:
            raise SystemExit(f"thuộc tính không có trong schema: {sorted(bad)}")

        nodes[name] = {
            "id": _norm_id(name),
            "name": name,
            "label": LABEL,
            "properties": props,
        }
        number = (meta.get("doc_number") or "").strip()
        if number:
            number_to_name[number] = name
        number_to_name[meta["doc_id"]] = name

    # văn bản được dẫn chiếu nhưng chưa cào về: tạo node rỗng để không đứt chuỗi
    stubs = set()

    def resolve(ref):
        ref = ref.strip()
        if not ref:
            return None
        if ref in number_to_name:
            return number_to_name[ref]
        stubs.add(ref)
        return ref

    edges = {}

    def add_edge(src, dst, label):
        if src == dst:
            return
        key = f"{src}-{label}-{dst}"
        edges[key] = {
            "id": key,
            "from": _norm_id(src),
            "fromType": LABEL,
            "to": _norm_id(dst),
            "toType": LABEL,
            "label": label,
            "properties": {},
        }

    for meta in metas:
        name = node_name(meta)
        for field, (label, reverse) in REL_MAP.items():
            if label not in rels_allowed:
                raise SystemExit(f"quan hệ {label} không có trong schema {LABEL}")
            for ref in meta.get(field) or []:
                other = resolve(ref)
                if not other:
                    continue
                src, dst = (other, name) if reverse else (name, other)
                add_edge(src, dst, label)
                if label in INVERSE:
                    add_edge(dst, src, INVERSE[label])

    for ref in sorted(stubs):
        if ref in nodes:
            continue
        nodes[ref] = {
            "id": _norm_id(ref),
            "name": ref,
            "label": LABEL,
            "properties": {
                "docNumber": ref,
                "desc": f"{ref}. Văn bản được dẫn chiếu, chưa có bản đầy đủ trong kho.",
                "semanticType": LABEL,
            },
        }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "nodes.json").write_text(
        json.dumps(list(nodes.values()), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT_DIR / "edges.json").write_text(
        json.dumps(list(edges.values()), ensure_ascii=False, indent=2), encoding="utf-8"
    )

    full = len(nodes) - len(stubs)
    print(f"metadata doc: {len(metas)}")
    print(f"nodes: {len(nodes)} ({full} có metadata đầy đủ, {len(stubs)} chỉ được dẫn chiếu)")
    print(f"edges: {len(edges)}")
    if stubs:
        print("dẫn chiếu chưa có trong kho:", ", ".join(sorted(stubs)))

    self_check(nodes, edges)


def self_check(nodes, edges):
    """Trường hợp thật: Luật 116/2025 thay thế Luật 24/2018 từ 01/7/2026.

    Đây đúng là chỗ mà bộ dữ liệu cũ bị sai, hai luật nằm cạnh nhau mà không
    có gì phân biệt còn hiệu lực hay không.
    """
    old = nodes.get("Luật 24/2018/QH14")
    new = nodes.get("Luật 116/2025/QH15")
    if not old or not new:
        print("[bỏ qua self-check] không thấy hai luật an ninh mạng trong metadata")
        return
    assert old["properties"]["status"] == "hết hiệu lực", old["properties"]
    assert old["properties"]["dateExpired"] == "2026-07-01", old["properties"]
    assert "Luật 116/2025/QH15-supersedes-Luật 24/2018/QH14" in edges
    assert "Luật 24/2018/QH14-supersededBy-Luật 116/2025/QH15" in edges
    assert "Luật 24/2018/QH14-supersedes-Luật 116/2025/QH15" not in edges
    print("[self-check ok] chuỗi thay thế 24/2018 -> 116/2025 đúng chiều")

    # id phải trùng cái schema_free_extractor sinh ra, nếu không thì hai đường
    # nạp (metadata và OpenIE) tạo ra hai node rời nhau cho cùng một văn bản.
    key = "Luật 116/2025/QH15-supersedes-Luật 24/2018/QH14"
    assert new["id"] == "luật 116 2025 qh15", new["id"]
    assert old["id"] == "luật 24 2018 qh14", old["id"]
    assert new["name"] == "Luật 116/2025/QH15", new["name"]
    assert edges[key]["from"] == new["id"], edges[key]
    assert edges[key]["to"] == old["id"], edges[key]
    print("[self-check ok] id node trùng quy tắc processing_phrases, name giữ nguyên")


if __name__ == "__main__":
    sys.exit(main())
