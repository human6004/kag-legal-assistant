# M2 Offline Reproducibility Package: Provenance & Environment Audit Report

**Date**: 2026-09-22  
**Verdict**: REPRODUCIBILITY_READY_FOR_REVIEW  
**Scope**: Offline test execution contract verification and unit regression reproducibility. Network required solely for initial PyPI wheel installation; zero network during test execution.

---

## 1. Candidate Origin & Cryptographic Hashes

- **Original Candidate ZIP**: `evidence-aware-m2-active-evidence-integrity-20260922-083247.zip`
- **Original Candidate SHA-256**: `dec8f1308bc4a8a8b6e2962688ed2f0ecf4ece87375b2da7bf6a06a00b14e661`
- **Grok Audit Verdict**: `CONTRACT_PASS` (offline evidence integrity invariants verified).
- **Astra Reproducibility Audit**: `BLOCKED` on candidate 083247 and 122235 due to packaging/runner/dependency lock issues.
- **Target of this Package**: Remediate packaging, dependency lock, and runner portability; zero changes to M2 production logic (`kag/solver/evidence_aware/{models,pipeline,planner_adapter}.py`).

---

## 2. Upstream OpenSPG / KAG Vendor Provenance

- **Declared Upstream Pin**: `commit fdab15b3929d2ee40dfcdd388f90233096a6afc9` (`fdab15b3`).
- **Git Object Status**: 
  - The local `vendor/KAG/` tree has no `.git` directory (stripped prior to commit in repository history at commit `be0b1a78` to remove 187 MB git history and avoid empty gitlink issues).
  - Git object `fdab15b3` cannot be queried via `git cat-file` locally because the vendor was checked in as a bare source tree.
- **Byte-Level Worktree Verification**:
  - Exactly 1,210 non-pycache source files.
  - Byte-by-byte SHA-256 comparison across 6 worktrees (`kag-legal-assistant`, `wt-evidence-m1`, `wt-handoff`, `wt-acceptance`, `wt-provenance`, `wt-repair`): **100% match (0 differences)**.
- **Vendor Patches Applied**:
  Exactly two lines were modified from upstream `fdab15b3` to ensure UTF-8 compatibility on Windows:
  1. `vendor/KAG/kag/common/conf.py` (line 152): `open(config_file, "r", encoding="utf-8")`
  2. `vendor/KAG/knext/common/env.py` (lines 121, 159): `open(..., encoding="utf-8")`
  Exported patch file available at: `patches/0001-vendor-utf8-encoding.patch`.

---

## 3. Dependencies & Runtime Lock

- **Python Runtime**: Python 3.11.9 (64-bit AMD64, MSC v.1938).
- **NetworkX Alignment**:
  - Upstream `vendor/KAG/requirements.txt` specifies `networkx==3.1`.
  - The verified installation contract enforces `networkx==3.1` (exact vendor alignment).
  - All 10 test suites (including 56 master tests, D2 Option B probe, and 10 Grok adversarial tests) pass 100% on `networkx==3.1`.
- **PyTest Alignment**:
  - Installed and verified runner uses `pytest==7.4.2` as locked in `requirements-lock.txt`.
- **Canonical Installation Contract**:
  - `requirements-lock.txt` is the sole canonical installation contract (all 143 packages locked, transitive constraints resolved without conflicts).
  - Key runtime pins:
    - `networkx==3.1` (aligned with upstream OpenSPG/KAG pin)
    - `pytest==7.4.2`
    - `nltk==3.8.1` (aligned with upstream OpenSPG/KAG pin)
    - `urllib3==1.26.16` (aligned with upstream OpenSPG/KAG pin)
    - `protobuf==3.20.1` (aligned with upstream OpenSPG/KAG pin)
    - `pdfminer.six==20231228` (aligned with upstream OpenSPG/KAG pin)
    - `pyodps==0.12.2` (aligned with upstream OpenSPG/KAG pin)
    - `aliyun-log-python-sdk==0.8.8` (aligned with upstream OpenSPG/KAG pin)
    - `mcp==1.6.0` (aligned with upstream OpenSPG/KAG pin)
    - `tenacity==9.1.4`
    - `pydantic==2.13.5`
    - `pydantic_core==2.46.5`
    - `ruamel.yaml==0.19.1`
    - `numpy==2.4.6`
    - `pandas==3.0.6`
    - `Jinja2==3.1.6`
    - `./vendor/KAG`

---

## 4. Test Suite Execution & Regression Results on networkx==3.1

Master runner `run_repro_suite.py` executed cleanly against `networkx==3.1` and `pytest==7.4.2`:

| Suite # | Test Suite Name | Test Count | Status |
|---|---|---|---|
| 1 | Upstream Regression Smoke | 5 tests | PASS |
| 2 | Grok 10 Adversarial | 10 tests | PASS |
| 3 | Master Suite (56 tests across 9 suites) | 56 tests | PASS |
| 4 | D2 Option B Probe | 2 probe options | PASS |
| 5 | Two Blockers Remediation (Bug 1 & 2) | 4 tests | PASS |
| 6 | Fresh Mutability Probes | 3 tests | PASS |
| 7 | Independent Counterexamples | 5 tests | PASS |
| 8 | Two Blockers Positive Control | 3 tests | PASS |
| 9 | Benchmark Metrics Units | 7 tests | PASS |
| 10 | Benchmark Trace Fidelity | 5 tests | PASS |

- **Zero Leakage**: Passed (0 modules imported from external worktrees).
- **Vendor Hash Binding**: Passed (loaded vendor code hash-matched against `./vendor/KAG`).
- **Master Exit Code**: `0`.

---

## 5. Packaging & Runner Portability Changes

- **Production Logic**: 0 lines changed in `kag/solver/evidence_aware/`.
- **Vendor Inclusion**: Bundled full 1,210 clean source files of `vendor/KAG` into the package so that no external worktree or download is needed.
- **Path Resolution**: Replaced all hardcoded `D:\Dev\Workspaces\KAG\wt-evidence-m1\vendor\KAG` fallbacks with dynamic, relative path discovery (`os.path.join(CANDIDATE_ROOT, "vendor", "KAG")`) and optional `KAG_VENDOR_ROOT` override.
- **Import Isolation Check**: Added automated zero-leakage assertions and byte-level vendor hash binding in `run_repro_suite.py`.
