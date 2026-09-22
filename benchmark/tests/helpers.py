# -*- coding: utf-8 -*-
"""Tiny fixture builders shared by the test modules.

Everything is synthetic. The recurring scenario is a made-up decree
"330/2026/NĐ-CP" with two articles, chosen so no real legal text is asserted
against and so the document number cannot collide with anything in the repo.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from benchmark.evaluator.models import BenchmarkItem, SystemOutput

DOC = "330/2026/NĐ-CP"


def evidence(
    article: Optional[str] = None,
    text: Optional[str] = None,
    clause: Optional[str] = None,
    point: Optional[str] = None,
    document_id: str = DOC,
    required: bool = True,
    evidence_id: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"document_id": document_id, "required": required}
    if evidence_id is not None:
        payload["evidence_id"] = evidence_id
    if article is not None:
        payload["article"] = article
    if clause is not None:
        payload["clause"] = clause
    if point is not None:
        payload["point"] = point
    if text is not None:
        payload["text"] = text
    return payload


def item(
    qid: str = "q1",
    category: str = "muc_phat",
    answerable: bool = True,
    question: str = "Mức phạt là bao nhiêu?",
    gold_markers: Sequence[str] = (),
    gold_claims: Sequence[str] = (),
    gold_evidence: Sequence[Dict[str, Any]] = (),
    **extra: Any,
) -> BenchmarkItem:
    payload: Dict[str, Any] = {
        "id": qid,
        "category": category,
        "answerable": answerable,
        "question": question,
        "gold_markers": list(gold_markers),
        "gold_claims": list(gold_claims),
        "gold_evidence": list(gold_evidence),
    }
    payload.update(extra)
    return BenchmarkItem.from_dict(payload)


def context(
    rank: int,
    text: Optional[str] = None,
    article: Optional[str] = None,
    clause: Optional[str] = None,
    point: Optional[str] = None,
    document_id: Optional[str] = DOC,
    score: Optional[float] = None,
    token_count: Optional[int] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"rank": rank}
    if text is not None:
        payload["text"] = text
    if document_id is not None:
        payload["document_id"] = document_id
    if article is not None:
        payload["article"] = article
    if clause is not None:
        payload["clause"] = clause
    if point is not None:
        payload["point"] = point
    if score is not None:
        payload["score"] = score
    if token_count is not None:
        payload["token_count"] = token_count
    return payload


def citation(
    article: Optional[str] = None,
    document_id: Optional[str] = DOC,
    clause: Optional[str] = None,
    point: Optional[str] = None,
    text: Optional[str] = None,
    claim_index: Optional[int] = None,
    claim: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    if document_id is not None:
        payload["document_id"] = document_id
    if article is not None:
        payload["article"] = article
    if clause is not None:
        payload["clause"] = clause
    if point is not None:
        payload["point"] = point
    if text is not None:
        payload["text"] = text
    if claim_index is not None:
        payload["claim_index"] = claim_index
    if claim is not None:
        payload["claim"] = claim
    return payload


def output(
    qid: str = "q1",
    system: str = "kag",
    answer: Optional[str] = None,
    contexts: Sequence[Dict[str, Any]] = (),
    citations: Sequence[Dict[str, Any]] = (),
    latency_ms: Optional[float] = None,
    error: Optional[str] = None,
    answer_claims: Optional[List[str]] = None,
) -> SystemOutput:
    payload: Dict[str, Any] = {
        "question_id": qid,
        "system": system,
        "answer": answer,
        "retrieved_contexts": list(contexts),
        "citations": list(citations),
        "latency_ms": latency_ms,
        "error": error,
    }
    if answer_claims is not None:
        payload["answer_claims"] = answer_claims
    return SystemOutput.from_dict(payload)
