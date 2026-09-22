# -*- coding: utf-8 -*-
"""Master Reproducibility Suite Runner for M2 Candidate.

Verifies strict import provenance, asserts hash binding against the bundled vendor,
and executes all 10 M2 test suites with individual child logging and test count extraction.
"""

from __future__ import annotations

import hashlib
import locale
import os
import re
import subprocess
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

try:
    locale.setlocale(locale.LC_ALL, "Chinese_China.936")
except Exception:
    try:
        locale.setlocale(locale.LC_ALL, "Chinese")
    except Exception:
        pass

CANDIDATE_ROOT = os.path.abspath(os.path.dirname(__file__))
VENDOR_DIR = os.path.join(CANDIDATE_ROOT, "vendor", "KAG")
TESTS_DIR = os.path.join(CANDIDATE_ROOT, "tests")
LOGS_DIR = os.path.join(CANDIDATE_ROOT, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

# Prepend vendor and candidate root to sys.path
if VENDOR_DIR not in sys.path:
    sys.path.insert(0, VENDOR_DIR)
if CANDIDATE_ROOT not in sys.path:
    sys.path.insert(0, CANDIDATE_ROOT)

print("=" * 78)
print("EVIDENCE-AWARE M2 MASTER REPRODUCIBILITY SUITE RUNNER")
print(f"Candidate Root: {CANDIDATE_ROOT}")
print(f"Vendor Root:    {VENDOR_DIR}")
print(f"Python Exec:    {sys.executable} ({sys.version.split()[0]})")
print("=" * 78)


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


# ----------------------------------------------------------------------
# PHASE 1: Rigorous Import Provenance and Hash Binding Check
# ----------------------------------------------------------------------
print("\n[PHASE 1] Verifying Import Provenance & Cryptographic Binding...")

import kag
wt_kag = os.path.join(CANDIDATE_ROOT, "kag")
if wt_kag not in kag.__path__:
    kag.__path__.append(wt_kag)

import kag.solver
wt_solver = os.path.join(CANDIDATE_ROOT, "kag", "solver")
if wt_solver not in kag.solver.__path__:
    kag.solver.__path__.append(wt_solver)

import knext
import kag.solver.evidence_aware.models as ea_models
import kag.solver.evidence_aware.pipeline as ea_pipeline
import kag.solver.evidence_aware.planner_adapter as ea_adapter
import kag.solver.planner.kag_iterative_planner as up_planner
import kag.solver.pipeline.kag_iterative_pipeline as up_pipeline
import kag.interface.solver.context as if_context
import kag.interface.solver.planner_abc as if_planner_abc
import kag.interface.solver.executor_abc as if_executor_abc
import kag.interface.solver.generator_abc as if_generator_abc

modules_to_audit = [
    ("kag", kag, "kag/__init__.py", True),
    ("knext", knext, "knext/__init__.py", True),
    ("kag.interface.solver.context", if_context, "kag/interface/solver/context.py", True),
    ("kag.interface.solver.planner_abc", if_planner_abc, "kag/interface/solver/planner_abc.py", True),
    ("kag.interface.solver.executor_abc", if_executor_abc, "kag/interface/solver/executor_abc.py", True),
    ("kag.interface.solver.generator_abc", if_generator_abc, "kag/interface/solver/generator_abc.py", True),
    ("kag.solver.planner.kag_iterative_planner", up_planner, "kag/solver/planner/kag_iterative_planner.py", True),
    ("kag.solver.pipeline.kag_iterative_pipeline", up_pipeline, "kag/solver/pipeline/kag_iterative_pipeline.py", True),
    ("kag.solver.evidence_aware.models", ea_models, "kag/solver/evidence_aware/models.py", False),
    ("kag.solver.evidence_aware.pipeline", ea_pipeline, "kag/solver/evidence_aware/pipeline.py", False),
    ("kag.solver.evidence_aware.planner_adapter", ea_adapter, "kag/solver/evidence_aware/planner_adapter.py", False),
]

for name, mod, rel_path, is_vendor in modules_to_audit:
    mod_file = os.path.abspath(mod.__file__)
    # Assert zero external worktree leakage
    assert "wt-evidence-m1" not in mod_file, f"LEAKAGE DETECTED in {name}: {mod_file}"

    if is_vendor:
        bundled_ref = os.path.abspath(os.path.join(VENDOR_DIR, rel_path.replace("/", os.sep)))
        if mod_file.lower().startswith(VENDOR_DIR.lower()):
            provenance = "BUNDLED_VENDOR_TREE"
        elif "site-packages" in mod_file.lower():
            # If loaded from site-packages (via pip install ./vendor/KAG), verify byte-level SHA-256 match!
            site_sha = file_sha256(mod_file)
            bundled_sha = file_sha256(bundled_ref)
            assert site_sha == bundled_sha, (
                f"HASH MISMATCH for installed vendor module {name}:\n"
                f"  Installed ({mod_file}): {site_sha}\n"
                f"  Bundled ({bundled_ref}): {bundled_sha}"
            )
            provenance = f"SITE_PACKAGES (HASH-VERIFIED against bundled vendor: {site_sha[:12]}...)"
        else:
            raise AssertionError(f"Vendor module {name} loaded from unexpected location: {mod_file}")
    else:
        # Custom M2 module must be loaded directly from CANDIDATE_ROOT
        expected_dir = os.path.abspath(os.path.join(CANDIDATE_ROOT, "kag", "solver", "evidence_aware"))
        assert mod_file.lower().startswith(expected_dir.lower()), (
            f"Custom M2 module {name} loaded from unexpected path: {mod_file}"
        )
        provenance = "CANDIDATE_M2_ROOT"

    print(f"  {name:<44} -> [{provenance}]")

print("  --> PROVENANCE & HASH BINDING: 100% VERIFIED (Zero leakage, 100% verified against bundle)")


# ----------------------------------------------------------------------
# PHASE 2: Test Suite Execution with Subprocess Isolation & Logging
# ----------------------------------------------------------------------
print("\n[PHASE 2] Executing Complete 10 M2 Test Suites with Subprocess Logging...")

env = os.environ.copy()
env["CANDIDATE_ROOT"] = CANDIDATE_ROOT
env["KAG_VENDOR_ROOT"] = VENDOR_DIR
env["PYTHONPATH"] = f"{TESTS_DIR}{os.pathsep}{VENDOR_DIR}{os.pathsep}{CANDIDATE_ROOT}"
env["PYTHONIOENCODING"] = "utf-8"
env["PYTHONUTF8"] = "1"

suites = [
    ("1. Upstream Regression Smoke", "test_m2_upstream_regression.py"),
    ("2. Grok 10 Adversarial", "test_m2_grok_independent_adversarial.py"),
    ("3. Master Suite (56 Tests)", "run_all_m2_tests.py"),
    ("4. D2 Option B Probe", "test_d2_integration_probe.py"),
    ("5. Two Blockers Remediation", "test_m2_grok_20260922_two_blockers.py"),
    ("6. Fresh Mutability Probes", "test_m2_013544_fresh_mutability_probes.py"),
    ("7. Independent Counterexamples", "test_m2_205752_independent_counterexamples.py"),
    ("8. Two Blockers Positive Control", "test_m2_two_blockers_positive.py"),
    ("9. Benchmark Metrics Units", "test_benchmark_metrics.py"),
    ("10. Benchmark Trace Fidelity", "test_benchmark_trace_fidelity.py"),
]

suite_results = []
start_time = time.time()

for idx, (label, filename) in enumerate(suites, start=1):
    script_path = os.path.join(TESTS_DIR, filename)
    log_base = os.path.join(LOGS_DIR, f"suite_{idx:02d}_{os.path.splitext(filename)[0]}")
    t0 = time.time()

    res = subprocess.run(
        [sys.executable, "-I", script_path],
        cwd=TESTS_DIR,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    dt = time.time() - t0

    # Save stdout and stderr to dedicated log files
    with open(f"{log_base}.stdout.log", "w", encoding="utf-8") as f:
        f.write(res.stdout)
    with open(f"{log_base}.stderr.log", "w", encoding="utf-8") as f:
        f.write(res.stderr)

    # Extract test count from stdout or stderr
    combined = res.stdout + "\n" + res.stderr
    test_count_str = "N/A"
    ran_match = re.search(r"Ran\s+(\d+)\s+tests?", combined)
    if ran_match:
        test_count_str = f"{ran_match.group(1)} tests"
    elif "test_T1_" in combined or "Final Status: ALL PASS" in combined:
        m = re.findall(r"test_\w+\s+\([^)]+\)\s+\.\.\.\s+ok", combined)
        if m:
            test_count_str = f"{len(m)} tests"
    elif "Option B" in combined:
        test_count_str = "2 probe options"

    status = "PASS" if res.returncode == 0 else "FAIL"
    print(f"  [{status}] {label:<35} | {test_count_str:<15} | {dt:.2f}s | exit {res.returncode}")
    suite_results.append({
        "label": label,
        "filename": filename,
        "status": status,
        "test_count": test_count_str,
        "duration": dt,
        "exit_code": res.returncode,
        "combined_output": combined,
    })

total_time = time.time() - start_time
failed_suites = [s for s in suite_results if s["status"] != "PASS"]

print("\n" + "=" * 78)
print("TEST EXECUTION BREAKDOWN SUMMARY")
print("=" * 78)
for s in suite_results:
    print(f"  {s['label']:<36} | {s['test_count']:<16} | {s['duration']:5.2f}s | {s['status']}")
print("-" * 78)
print(f"Total Suites: {len(suite_results)} | Passed: {len(suite_results) - len(failed_suites)} | Failed: {len(failed_suites)} | Total Time: {total_time:.2f}s")
print("=" * 78)

if not failed_suites:
    print("\nALL 10 M2 TEST SUITES PASSED WITH ZERO LEAKAGE!")
    print("REPRODUCIBILITY CONTRACT: SATISFIED")
    print(f"Log files preserved in: {LOGS_DIR}")
    sys.exit(0)
else:
    print(f"\nFAILED SUITES ({len(failed_suites)}):")
    for s in failed_suites:
        print(f"\n--- Output of {s['label']} ({s['filename']}) ---")
        print(s["combined_output"])
    sys.exit(1)
