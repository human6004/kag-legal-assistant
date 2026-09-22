# -*- coding: utf-8 -*-
"""Independent Counterexamples Reproducer entrypoint in scripts."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
runner = os.path.join(HERE, "..", "tests", "test_m2_205752_independent_counterexamples.py")
with open(runner, "rb") as f:
    code = compile(f.read(), runner, "exec")
exec(code)
