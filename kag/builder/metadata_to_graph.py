# -*- coding: utf-8 -*-
"""Sinh nodes.json / edges.json cho do thi tu cac file metadata trong data/metadata.

Ly do: scanner cua KAG chi nhan .md nen moi thu trong metadata (ngay hieu luc,
trang thai, chuoi thay the) khong bao gio vao do thi. Script nay nap thang
chung vao graph qua co che external graph co san cua KAG.

Chay trong thu muc kag/: python builder/metadata_to_graph.py
Ket qua: data/graph/nodes.json, data/graph/edges.json
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
META_DIR = ROOT / "data" / "metadata"
OUT_DIR = ROOT / "data" / "graph"
SCHEMA_FILE = ROOT / "kag" / "schema" / "Legal.schema"

LABEL = "LegalDocument"


def _norm_id(phrase):
    """Chuan hoa id node cho trung voi id ma OpenIE sinh ra.

    schema_free_extractor.py:424 chay processing_phrases(name) roi lay ket qua
    lam CA id LAN name cua node. kag/builder/__init__.py da va ham do de giu
    dau tieng Viet. Ham nay lap lai dung quy tac ay.

    Chi ap cho id. Truong `name` van giu nguyen van vi no la thu duoc hien thi
    va duoc vector hoa de entity linking bam vao.

    Khong dung thi "Luat 116/2025/QH15" cua injection va "luat 116 2025 qh15"
    cua OpenIE thanh hai node roi nhau: mot node giu status va chuoi thay the,
    mot node giu canh ve chunk, khong truy van nao di duoc tu ben nay sang ben kia.
    """
    return re.sub(r"[^\w ]", " ", str(phrase).lower(), flags=re.U).strip()


# metadata field -> ten thuoc tinh trong Legal.schema
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

# field danh sach trong metadata -> (ten quan he, co dao chieu khong)
REL_MAP = {
    "supersedes": ("supersedes", False),
    "superseded_by": ("supersedes", True),
    "amends": ("amends", False),
    "amended_by": ("amends", True),
    "implements": ("implementsDoc", False),
    "implemented_by": ("implementsDoc", True),
}

# quan he nguoc, sinh them de truy van mot buoc chay duoc ca hai chieu
INVERSE = {"supersedes": "supersededBy"}


def schema_props(label):
    """Doc truc tiep Legal.schema, khong can server, de bat sai ten thuoc tinh."""
    text = SCHEMA_FILE.read_text(encoding="utf-8")
    blocks = re.split(r"^(?=\S)", text, flags=re.M)
    for block in blocks:
        if block.startswith(f"{label}("):
            return set(re.findall(r"^\s{8}(\w+)\(", block, re.M))
    raise SystemExit(f"khong tim thay type {label} trong {SCHEMA_FILE}")


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
    """Ten node phai trung cach LLM goi van ban, xem prompt std (legal_std)."""
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
            print(f"[bo qua] trung doc_id {key}: {path.name} (da co {seen[key]})")
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
            raise SystemExit(f"thuoc tinh khong co trong schema: {sorted(bad)}")

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

    # van ban duoc dan chieu nhung chua cao ve: tao node rong de khong dut chuoi
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
                raise SystemExit(f"quan he {label} khong co trong schema {LABEL}")
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
                "desc": f"{ref}. Van ban duoc dan chieu, chua co ban day du trong kho.",
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
    print(f"nodes: {len(nodes)} ({full} co metadata day du, {len(stubs)} chi duoc dan chieu)")
    print(f"edges: {len(edges)}")
    if stubs:
        print("dan chieu chua co trong kho:", ", ".join(sorted(stubs)))

    self_check(nodes, edges)


def self_check(nodes, edges):
    """Truong hop that: Luat 116/2025 thay the Luat 24/2018 tu 01/7/2026.

    Day dung la cho ma bo du lieu cu bi sai, hai luat nam canh nhau ma khong
    co gi phan biet con hieu luc hay khong.
    """
    old = nodes.get("Luật 24/2018/QH14")
    new = nodes.get("Luật 116/2025/QH15")
    if not old or not new:
        print("[bo qua self-check] khong thay hai luat an ninh mang trong metadata")
        return
    assert old["properties"]["status"] == "hết hiệu lực", old["properties"]
    assert old["properties"]["dateExpired"] == "2026-07-01", old["properties"]
    assert "Luật 116/2025/QH15-supersedes-Luật 24/2018/QH14" in edges
    assert "Luật 24/2018/QH14-supersededBy-Luật 116/2025/QH15" in edges
    assert "Luật 24/2018/QH14-supersedes-Luật 116/2025/QH15" not in edges
    print("[self-check ok] chuoi thay the 24/2018 -> 116/2025 dung chieu")

    # id phai trung cai schema_free_extractor sinh ra, neu khong thi hai duong
    # nap (metadata va OpenIE) tao ra hai node roi nhau cho cung mot van ban.
    key = "Luật 116/2025/QH15-supersedes-Luật 24/2018/QH14"
    assert new["id"] == "luật 116 2025 qh15", new["id"]
    assert old["id"] == "luật 24 2018 qh14", old["id"]
    assert new["name"] == "Luật 116/2025/QH15", new["name"]
    assert edges[key]["from"] == new["id"], edges[key]
    assert edges[key]["to"] == old["id"], edges[key]
    print("[self-check ok] id node trung quy tac processing_phrases, name giu nguyen")


if __name__ == "__main__":
    sys.exit(main())
