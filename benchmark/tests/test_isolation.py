# -*- coding: utf-8 -*-
"""The evaluator must stay independent of the three systems it scores.

If `benchmark.evaluator` ever imported `kag`, `hybridRAG` or `nativeRAG`, the
shared benchmark would inherit one architecture's assumptions - most
dangerously its chunk ids - and stop being a fair common ground. These tests
are structural, so the coupling cannot creep back in unnoticed.
"""
from __future__ import annotations

import ast
import importlib
import pkgutil
import sys
from pathlib import Path
from typing import List, Set

import pytest

import benchmark.evaluator as evaluator_pkg

SYSTEM_PACKAGES = ("kag", "hybridRAG", "nativeRAG", "hybridrag", "nativerag")
EVALUATOR_DIR = Path(evaluator_pkg.__file__).parent
BENCHMARK_DIR = EVALUATOR_DIR.parent
#: Adapter helpers are shared by all three systems, so they are held to the
#: same rule as the evaluator: no system package, no third-party dependency.
ADAPTERS_DIR = BENCHMARK_DIR / "adapters"
SHARED_DIRS = (EVALUATOR_DIR, ADAPTERS_DIR)


def python_files(root: Path) -> List[Path]:
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def imported_roots(path: Path) -> Set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import, stays inside the package
                continue
            if node.module:
                roots.add(node.module.split(".")[0])
    return roots


@pytest.mark.parametrize("path", python_files(EVALUATOR_DIR), ids=lambda p: p.name)
def test_no_evaluator_module_imports_a_system_package(path: Path) -> None:
    offenders = imported_roots(path) & set(SYSTEM_PACKAGES)
    assert not offenders, f"{path.name} imports {sorted(offenders)}"


@pytest.mark.parametrize("path", python_files(BENCHMARK_DIR), ids=lambda p: p.name)
def test_no_benchmark_file_imports_a_system_package(path: Path) -> None:
    offenders = imported_roots(path) & set(SYSTEM_PACKAGES)
    assert not offenders, f"{path.name} imports {sorted(offenders)}"


def test_the_evaluator_uses_only_the_standard_library() -> None:
    """No third-party dependency: the evaluator must run in a bare interpreter."""
    allowed = {"benchmark", "__future__"}
    stdlib = set(sys.stdlib_module_names)
    for root_dir in SHARED_DIRS:
        for path in python_files(root_dir):
            for root in imported_roots(path):
                assert root in stdlib or root in allowed, f"{path.name} imports {root!r}"


def test_the_adapter_helpers_are_shared_and_system_free() -> None:
    """A rule implemented once per system is a rule applied three ways."""
    assert (ADAPTERS_DIR / "citation_parser.py").is_file()
    for path in python_files(ADAPTERS_DIR):
        assert not imported_roots(path) & set(SYSTEM_PACKAGES), path.name


def test_importing_every_evaluator_module_pulls_in_no_system_package() -> None:
    before = {name.split(".")[0] for name in sys.modules}
    for module in pkgutil.iter_modules([str(EVALUATOR_DIR)]):
        importlib.import_module(f"benchmark.evaluator.{module.name}")
    after = {name.split(".")[0] for name in sys.modules}
    assert not (after - before) & set(SYSTEM_PACKAGES)


def test_the_evaluator_lives_outside_the_kag_package() -> None:
    parts = EVALUATOR_DIR.parts
    assert "kag" not in parts
    assert parts[-2:] == ("benchmark", "evaluator")
    assert (BENCHMARK_DIR / "benchmark_schema.json").is_file()
    assert (BENCHMARK_DIR / "system_output_schema.json").is_file()


def test_no_evaluator_source_mentions_a_system_chunk_id() -> None:
    """Chunk ids are the one thing the common gold truth may never rest on."""
    banned = ("gold_chunks", "chunk_id", "kag_chunk", "vector_id", "node_id")
    for path in python_files(EVALUATOR_DIR):
        text = path.read_text(encoding="utf-8")
        for token in banned:
            if token not in text:
                continue
            # models.py names them to REJECT them; nothing may consume them.
            assert path.name == "models.py", f"{path.name} mentions {token!r}"
            assert "FORBIDDEN" in text


def test_no_vendor_or_model_name_is_hard_coded_in_the_judge_layer() -> None:
    text = (EVALUATOR_DIR / "judge.py").read_text(encoding="utf-8").lower()
    for vendor in ("openai", "anthropic", "gemini", "qwen", "deepseek", "api_key", "http"):
        assert vendor not in text, f"judge.py mentions {vendor!r}"


def test_no_evaluator_module_hard_codes_the_dataset_size_or_categories() -> None:
    for path in python_files(EVALUATOR_DIR):
        text = path.read_text(encoding="utf-8")
        assert "150" not in text, f"{path.name} hard-codes a dataset size"
        assert "questions_mo_rong" not in text
