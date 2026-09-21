# -*- coding: utf-8 -*-
"""Common benchmark for comparing KAG / HybridRAG / NativeRAG.

This package is deliberately independent of the three systems: it never imports
`kag`, `hybridRAG` or `nativeRAG`, and it never treats any system's internal
chunk identifiers as ground truth. See `benchmark/README.md`.

Status: B1 (evaluator) only. The 150-question dataset is NOT built yet.
"""

__all__ = ["evaluator"]
