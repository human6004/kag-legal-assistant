# -*- coding: utf-8 -*-
"""Kiểm hai đường nạp module của kag/builder, mỗi đường một process sạch.

Chạy (đứng ở thư mục gốc repo):
    .venv/Scripts/python.exe -X utf8 tests/builder/test_bootstrap_loader.py

Vì sao phải có test này: loader production
``kag/common/registry/utils.py:31`` (gọi từ ``kag/builder/indexer.py:127`` và
``kag/builder/injection.py``) import mọi module con của ``kag/builder`` dưới tên
TOP-LEVEL, nên module con KHÔNG có parent package. Một ``from .canon_id import``
trong ``extractor.py`` làm cả bootstrap production nổ ``ImportError`` trước khi
chạy được chunk nào. Lỗi chỉ hiện ra theo tên module lúc import, nên phải chạy
process riêng: ``sys.modules`` của process đã import kiểu dotted sẽ che mất lỗi.

Không LLM, không embedding, không ghi graph, không cần OpenSPG: chỉ nạp module,
kiểm registry và kiểm hai bản vá của ``builder/__init__.py``.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KAGDIR = ROOT / "kag"
BUILDER = KAGDIR / "builder"

EXPECT = {
    "kag.interface:ExtractorABC": ["legal_schema_free_extractor"],
    "kag.interface:ReaderABC": ["legal_md_reader"],
    "kag.interface:SplitterABC": ["legal_structural_splitter"],
    "kag.interface:ExternalGraphLoaderABC": ["legal_external_graph"],
    "kag.interface:PromptABC": ["legal_ner", "legal_triple", "legal_std"],
    "kag.interface:KAGBuilderChain": ["legal_unstructured_builder_chain"],
}


def _check_registry():
    import importlib

    for path, names in EXPECT.items():
        mod, cls_name = path.split(":")
        cls = getattr(importlib.import_module(mod), cls_name)
        available = cls.list_available()
        for name in names:
            assert name in available, (name, cls_name, sorted(available))
        print("  registry %-22s : %s" % (cls_name, ", ".join(names)))


def _check_init_patches():
    """Hai bản vá cấp module của builder/__init__.py còn sống sau khi nạp."""
    from kag.builder.model.sub_graph import SubGraph

    assert SubGraph.add_node.__name__ == "_add_node_chuan", SubGraph.add_node
    assert SubGraph.add_edge.__name__ == "_add_edge_chuan", SubGraph.add_edge
    print("  SubGraph.add_node/add_edge   : wrapper của project")

    g = SubGraph([], [])
    for ten in ("Nghị định 329/2026/NĐ-CP", "Nghị định số 329/2026/NĐ-CP"):
        g.add_node(ten, ten, "LegalDocument")
    assert len(g.nodes) == 1, [n.id for n in g.nodes]
    assert g.nodes[0].id == "nghị định 329 2026 nđ cp", g.nodes[0].id
    print("  hai cách viết số hiệu        : một node canonical")

    cid = "b2c8d28bd04779084f49c52e10e635dd2a3c1586de6fa234a9a3fc8a6e2218ba#4950#table#0#LEN"
    g2 = SubGraph([], [])
    g2.add_node(cid, "tên chunk", "Chunk")
    assert g2.nodes[0].id == cid, g2.nodes[0].id
    print("  chunk giữ nguyên id băm      : OK")


def child_production_loader():
    """Đúng lời gọi của indexer.py: loader tự lo sys.path, không chèn tay."""
    os.chdir(KAGDIR)
    from kag.common.registry import import_modules_from_path

    import_modules_from_path(str(BUILDER))
    print("  import_modules_from_path()   : không ném")
    _check_registry()
    _check_init_patches()


def child_dotted_import():
    """Đường của tests và của script khảo sát: kag/ trên sys.path."""
    os.chdir(KAGDIR)
    sys.path.insert(0, str(KAGDIR))
    import builder  # noqa: F401
    import builder.extractor  # noqa: F401
    import builder.chain  # noqa: F401
    import builder.reader  # noqa: F401
    import builder.splitter  # noqa: F401
    import builder.external_graph  # noqa: F401
    import builder.prompt.ner  # noqa: F401
    import builder.prompt.triple  # noqa: F401
    import builder.prompt.std  # noqa: F401

    print("  import builder.extractor     : không ném")
    _check_registry()
    _check_init_patches()


def child_injection_imports():
    """injection.py dùng cùng loader; nạp module + registry, KHÔNG gọi inject()."""
    os.chdir(KAGDIR)
    sys.path.insert(0, str(KAGDIR))
    import builder.injection as inj

    assert hasattr(inj, "inject"), dir(inj)
    from kag.common.registry import import_modules_from_path

    import_modules_from_path(str(BUILDER))
    print("  injection: import + loader   : không ném, inject() KHÔNG gọi")
    _check_registry()


CHILDREN = {
    "--child-production-loader": child_production_loader,
    "--child-dotted-import": child_dotted_import,
    "--child-injection-imports": child_injection_imports,
}


def main():
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    failed = []
    for flag in CHILDREN:
        print("\n== %s (process riêng) ==" % flag.replace("--child-", ""))
        proc = subprocess.run(
            [sys.executable, "-X", "utf8", str(Path(__file__).resolve()), flag],
            capture_output=True, text=True, encoding="utf-8", env=env, cwd=str(ROOT),
        )
        out = [ln for ln in (proc.stdout or "").splitlines() if not ln.startswith("20")]
        print("\n".join(out))
        if proc.returncode != 0:
            failed.append(flag)
            print("  exit=%d\n%s" % (proc.returncode, (proc.stderr or "")[-2000:]))
        else:
            print("  exit=0")
    if failed:
        raise AssertionError("bootstrap fail: %s" % failed)
    print("\nHai đường nạp module đều chạy, registry và bản vá đều còn.")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    if arg in CHILDREN:
        CHILDREN[arg]()
    else:
        main()
