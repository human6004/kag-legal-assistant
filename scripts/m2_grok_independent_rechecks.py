# -*- coding: utf-8 -*-
"""Independent Grok M2 Recheck Runner.

Executes all independent adversarial checks, master suite tests, and architectural probes
against candidate source without mutating production state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

HERE = os.path.abspath(os.path.dirname(__file__))
DEFAULT_WT = os.path.abspath(os.path.join(HERE, ".."))
LOG_DIR = os.path.join(HERE, "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def run_cmd(label: str, args: List[str], cwd: str, python: str, env_vars: Dict[str, str] = None) -> Dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    if env_vars:
        env.update(env_vars)

    t0 = time.time()
    proc = subprocess.run(
        [python, *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    duration = round(time.time() - t0, 3)
    log_path = os.path.join(LOG_DIR, f"{label}.log")
    with open(log_path, "w", encoding="utf-8") as fh:
        fh.write(f"CMD: {[python, *args]}\nCWD: {cwd}\nEXIT: {proc.returncode}\n\n")
        fh.write("===== STDOUT =====\n")
        fh.write(proc.stdout or "")
        fh.write("\n===== STDERR =====\n")
        fh.write(proc.stderr or "")

    status_str = "PASS" if proc.returncode == 0 else "FAIL"
    print(f"[{label}] {status_str} (exit={proc.returncode}, duration={duration}s)")
    return {
        "label": label,
        "cmd": [python, *args],
        "cwd": cwd,
        "exit_code": proc.returncode,
        "duration_s": duration,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "log_path": log_path,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run independent Grok M2 rechecks.")
    parser.add_argument(
        "--target-dir",
        default=None,
        help="Explicit directory path to run tests against",
    )
    args = parser.parse_args()

    target_root = os.path.abspath(args.target_dir) if args.target_dir else DEFAULT_WT

    venv_py = os.path.join(target_root, ".venv", "Scripts", "python.exe")
    python = venv_py if os.path.isfile(venv_py) else sys.executable

    print("======================================================================")
    print("GROK INDEPENDENT M2 RECHECK RUNNER")
    print(f"Target Root: {target_root}")
    print(f"Python: {python}")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("======================================================================\n")

    vendor_kag = os.path.join(target_root, "vendor", "KAG")
    if not os.path.isdir(vendor_kag):
        vendor_kag = os.path.join(DEFAULT_WT, "vendor", "KAG")

    test_env = {
        "CANDIDATE_ROOT": target_root,
        "PYTHONPATH": f"{target_root};{vendor_kag}",
    }
    results = []

    # 0. Independent Counterexamples Reproducer (Bug A & Bug B)
    counter_script = os.path.join(target_root, "tests", "test_m2_205752_independent_counterexamples.py")
    if not os.path.isfile(counter_script):
        counter_script = os.path.join(HERE, "..", "tests", "test_m2_205752_independent_counterexamples.py")
    if os.path.isfile(counter_script):
        results.append(
            run_cmd(
                "counterexamples_205752",
                [counter_script],
                target_root,
                python,
                env_vars=test_env,
            )
        )

    # 1. Independent Grok Adversarial Suite (10 tests)
    adv_script = os.path.join(target_root, "tests", "test_m2_grok_independent_adversarial.py")
    if os.path.isfile(adv_script):
        results.append(
            run_cmd(
                "independent_adversarial",
                [adv_script],
                target_root,
                python,
                env_vars=test_env,
            )
        )

    # 2. Master Test Suite (56 tests)
    master_script = os.path.join(target_root, "tests", "run_all_m2_tests.py")
    if os.path.isfile(master_script):
        results.append(
            run_cmd(
                "master_suite",
                [master_script],
                target_root,
                python,
                env_vars=test_env,
            )
        )

    # 3. D2 Integration Probe (Option B)
    d2_script = os.path.join(target_root, "tests", "test_d2_integration_probe.py")
    if os.path.isfile(d2_script):
        results.append(
            run_cmd(
                "d2_probe",
                [d2_script],
                target_root,
                python,
                env_vars=test_env,
            )
        )

    # 4. Two defects closure
    two_defects_script = os.path.join(target_root, "tests", "test_m2_two_defects_closure_red.py")
    if os.path.isfile(two_defects_script):
        results.append(
            run_cmd(
                "two_defects_closure",
                [two_defects_script],
                target_root,
                python,
                env_vars=test_env,
            )
        )

    # 5. Bounded closeout
    closeout_script = os.path.join(target_root, "tests", "test_m2_bounded_closeout_red.py")
    if os.path.isfile(closeout_script):
        results.append(
            run_cmd(
                "bounded_closeout",
                [closeout_script],
                target_root,
                python,
                env_vars=test_env,
            )
        )

    all_passed = all(r["exit_code"] == 0 for r in results)
    summary_path = os.path.join(LOG_DIR, "rechecks_summary.json")
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "target_root": target_root,
                "all_passed": all_passed,
                "runs": [
                    {
                        "label": r["label"],
                        "exit_code": r["exit_code"],
                        "duration_s": r["duration_s"],
                        "log_path": r["log_path"],
                    }
                    for r in results
                ],
            },
            fh,
            indent=2,
            ensure_ascii=False,
        )

    print("\n======================================================================")
    print("RECHECK EXECUTION SUMMARY")
    for r in results:
        print(f"  - {r['label']}: {'PASS' if r['exit_code'] == 0 else 'FAIL'} (exit {r['exit_code']})")
    print(f"Overall Verdict: {'ALL PASS (READY_FOR_INDEPENDENT_REVIEW)' if all_passed else 'CONTRACT_FAIL'}")
    print(f"Summary JSON: {summary_path}")
    print("======================================================================")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
