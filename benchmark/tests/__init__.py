# -*- coding: utf-8 -*-
"""Offline unit tests for the common benchmark evaluator.

Every test here runs on tiny synthetic data, with no network, no API key and no
real judge. Semantic decisions are made by `ScriptedJudge` / `RuleBasedJudge`
from `benchmark.evaluator.judge`. Nothing in this package imports `kag`,
`hybridRAG` or `nativeRAG` (see `test_isolation.py`, which asserts it).
"""
