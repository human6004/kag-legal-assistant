# Evidence-Aware KAG-Solver (M2 Offline Reproducible Package): Reproduction Guide

This guide provides step-by-step instructions to verify and reproduce the full test suite, architectural probes, and offline contract verification from this self-contained candidate package in a clean environment.

---

## 1. Prerequisites

- **Python**: 3.10+ (tested and verified on Python 3.11.9, 64-bit Windows AMD64).
- **Virtual Environment**: Clean isolated `venv` (no external site-packages or worktrees).
- **Network Scope**: 
  - **Initial Installation**: Internet access to PyPI is required to download binary dependency wheels.
  - **Test Execution**: 100% offline test execution after installation. All KAG vendor library code is bundled locally in `./vendor/KAG`. No external network, live LLM API, Neo4j, or external search engine calls occur during test runs.

---

## 2. Setup Clean Environment

Extract the reproducibility candidate package to any clean directory of your choice (e.g. `C:\repro_clean\candidate` or `D:\test\candidate`):

```bash
cd candidate

# Create fresh virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

# CANONICAL INSTALLATION CONTRACT:
# Install exact mutually-resolved dependencies from requirements-lock.txt.
# (Do NOT use unpinned requirements.txt; requirements-lock.txt is the sole canonical contract).
pip install -r requirements-lock.txt
```

---

## 3. One-Command Master Verification

Run the master verification script from the root of the candidate directory:

```bash
python run_repro_suite.py
```

This single command:
1. Validates strict import provenance and hash-binds loaded vendor code against the local `./vendor/KAG` bundle.
2. Asserts zero module leakage from any external worktree or legacy site-packages.
3. Executes all 10 M2 test suites sequentially with subprocess isolation, capturing stdout/stderr to `logs/`.
4. Extracts and displays individual test counts and durations, exiting with code `0` on 100% success.

---

## 4. Running Individual Test Suites

You can also run any suite directly using the virtual environment's Python:

```bash
# 1. Upstream Regression Smoke (5 tests)
python tests/test_m2_upstream_regression.py

# 2. Grok Independent Adversarial Suite (10 tests)
python tests/test_m2_grok_independent_adversarial.py

# 3. Master Test Suite (56 tests across 9 suites)
python tests/run_all_m2_tests.py

# 4. D2 Option B Probe (Architectural Feedback without Context DAG Pollution)
python tests/test_d2_integration_probe.py

# 5. Two Blockers Probe (Bug 1 & Bug 2)
python tests/test_m2_grok_20260922_two_blockers.py

# 6. Fresh Mutability Probes (3 tests)
python tests/test_m2_013544_fresh_mutability_probes.py

# 7. Independent Counterexamples (5 tests)
python tests/test_m2_205752_independent_counterexamples.py

# 8. Two Blockers Positive Controls
python tests/test_m2_two_blockers_positive.py

# 9. Benchmark Metric & Trace Units
python tests/test_benchmark_metrics.py
python tests/test_benchmark_trace_fidelity.py
```

---

## 5. Provenance and Scope

- **Contract Pass**: Grok `CONTRACT_PASS` for M2 offline integrity is preserved verbatim.
- **Offline Test Boundary**: This package guarantees offline evidence integrity, contract verification, and unit regression. Execution operates with zero network traffic once pip dependencies are installed.
- **Vendor Code**: Bundled in `vendor/KAG/` (1,210 files, verified clean source tree, commit `fdab15b3929d2ee40dfcdd388f90233096a6afc9`). See `docs/provenance_report.md` for SHA-256 digests and patch details.
