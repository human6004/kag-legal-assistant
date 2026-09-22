# -*- coding: utf-8 -*-
"""Master Test Runner: Executes all M2 Test Suites and generates audit reports."""

import sys
import os
import locale
import unittest
import time

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

try:
    locale.setlocale(locale.LC_ALL, 'Chinese_China.936')
except Exception:
    try:
        locale.setlocale(locale.LC_ALL, 'Chinese')
    except Exception:
        pass

# Ensure paths
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)
WT_ROOT = os.path.dirname(TESTS_DIR)
VENDOR_KAG = os.path.join(WT_ROOT, "vendor", "KAG")
if not os.path.isdir(VENDOR_KAG):
    alt_vendor = os.environ.get("KAG_VENDOR_ROOT") or os.path.abspath(os.path.join(WT_ROOT, "vendor", "KAG"))
    if os.path.isdir(alt_vendor):
        VENDOR_KAG = alt_vendor

if VENDOR_KAG not in sys.path:
    sys.path.insert(0, VENDOR_KAG)

import kag
wt_kag = os.path.join(WT_ROOT, "kag")
if wt_kag not in kag.__path__:
    kag.__path__.append(wt_kag)

import kag.solver
wt_solver = os.path.join(WT_ROOT, "kag", "solver")
if wt_solver not in kag.solver.__path__:
    kag.solver.__path__.append(wt_solver)

from test_m2_executable_contract_t1_t6 import TestM2ExecutableContractT1ToT6
from test_m2_pipeline_e2e_and_adversarial import TestM2PipelineE2EAndAdversarial
from test_m2_upstream_regression import TestM2UpstreamRegression
from test_tc_m2_01_to_12_acceptance import TestTCM2AcceptanceSuite
from test_m2_closure_defects_red import TestM2ClosureDefectsRED
from test_m2_final_integrity_red import TestM2FinalIntegrityRED
from test_m2_overnight_adversarial_red import TestM2OvernightAdversarialRED
from test_m2_validity_verifier_red import TestM2VerifierIntegrityRED
from test_m2_closeout_red import TestM2CloseoutDefectsRED


def run_all():
    print("======================================================================")
    print("M2 EVIDENCE-AWARE KAG-SOLVER: MASTER TEST SUITE EXECUTION")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("Environment: Isolated Virtualenv (.venv)")
    print("Note: D2 Integration Probe runs as an independent architectural gate")
    print("      via `tests/test_d2_integration_probe.py`.")
    print("======================================================================\n")

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Suite 1: Contract & Anti-forgery (T1 to T6) (7 tests)
    suite.addTests(loader.loadTestsFromTestCase(TestM2ExecutableContractT1ToT6))
    # Suite 2: Pipeline E2E & Adversarial (4 tests)
    suite.addTests(loader.loadTestsFromTestCase(TestM2PipelineE2EAndAdversarial))
    # Suite 3: Upstream OpenSPG Regression (5 tests)
    suite.addTests(loader.loadTestsFromTestCase(TestM2UpstreamRegression))
    # Suite 4: Dedicated TC-M2-01 to TC-M2-12 Acceptance Tests (12 tests)
    suite.addTests(loader.loadTestsFromTestCase(TestTCM2AcceptanceSuite))
    # Suite 5: Defect A to F Verification Suite (6 tests)
    suite.addTests(loader.loadTestsFromTestCase(TestM2ClosureDefectsRED))
    # Suite 6: Final Integrity R1 to R10 Suite (10 tests)
    suite.addTests(loader.loadTestsFromTestCase(TestM2FinalIntegrityRED))
    # Suite 7: Overnight Deep Adversarial Suite (8 tests)
    suite.addTests(loader.loadTestsFromTestCase(TestM2OvernightAdversarialRED))
    # Suite 8: Validity Verifier Integrity V1 & V2 Suite (2 tests)
    suite.addTests(loader.loadTestsFromTestCase(TestM2VerifierIntegrityRED))
    # Suite 9: Closeout Gate RED-1 & RED-2 Suite (2 tests)
    suite.addTests(loader.loadTestsFromTestCase(TestM2CloseoutDefectsRED))

    runner = unittest.TextTestRunner(verbosity=2)
    start_time = time.time()
    result = runner.run(suite)
    duration = time.time() - start_time

    print("\n======================================================================")
    print("EXECUTION SUMMARY")
    print(f"Total Tests Run: {result.testsRun}")
    print(f"Passed: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Duration: {duration:.3f}s")
    print(f"Final Status: {'ALL PASS (GREEN)' if result.wasSuccessful() else 'FAILED'}")
    print("======================================================================")

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_all())
