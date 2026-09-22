# -*- coding: utf-8 -*-
"""Helpers an adapter needs to map a system's native output onto the contract.

An adapter turns what KAG / HybridRAG / NativeRAG actually return into the
shape of `benchmark/system_output_schema.json`. The rules that must be the same
for all three live here rather than in each adapter, because a rule that is
implemented three times is a rule that is applied three ways.

Like `benchmark.evaluator`, nothing here imports a system package.
"""
from __future__ import annotations

from .citation_parser import (
    citation_key,
    parse_citation_payloads,
    parse_citations,
)

__all__ = ["parse_citations", "parse_citation_payloads", "citation_key"]
