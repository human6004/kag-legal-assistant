# -*- coding: utf-8 -*-
"""Data contracts for the common benchmark.

Two contracts live here, both architecture-neutral:

  * `BenchmarkItem`  - one benchmark question plus its ground truth. Ground
    truth is expressed as `document -> article -> clause -> point -> text`.
    Any system-internal identifier (chunk id, vector id, node id) is rejected
    by the validator: whoever writes the dataset must not be able to smuggle
    one system's indexing decisions into the gold standard.
  * `SystemOutput`   - what one system answered for one question, after its
    adapter mapped the native output onto the common shape.

JSON Schema files next to this package (`benchmark/benchmark_schema.json`,
`benchmark/system_output_schema.json`) describe the same contracts for
non-Python consumers. This module is the executable version; it does not
require the `jsonschema` package.
"""
from __future__ import annotations

import io
import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .normalization import (
    normalize_article,
    normalize_clause,
    normalize_document_id,
    normalize_point,
)


class SchemaError(ValueError):
    """Raised when input does not satisfy the benchmark data contract."""


# Keys that would tie the gold standard to one system's internals. The common
# benchmark must stay comparable across KAG / HybridRAG / NativeRAG, so these
# are refused in the dataset rather than silently ignored.
FORBIDDEN_DATASET_KEYS = frozenset(
    {
        "chunk_id",
        "chunk_ids",
        "gold_chunks",
        "gold_chunk_ids",
        "vector_id",
        "vector_ids",
        "embedding_id",
        "node_id",
        "kag_chunk_id",
        "hybridrag_chunk_id",
        "nativerag_chunk_id",
    }
)


def _as_opt_str(value: Any, ctx: str, key: str) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, bool):
        raise SchemaError(f"{ctx}: '{key}' must be a string, got bool")
    if isinstance(value, (int, float)):
        # "article": 53 is a common authoring slip; accept it as "53".
        return str(value)
    if isinstance(value, str):
        return value if value.strip() else None
    raise SchemaError(f"{ctx}: '{key}' must be a string, got {type(value).__name__}")


def _as_req_str(value: Any, ctx: str, key: str) -> str:
    out = _as_opt_str(value, ctx, key)
    if not out:
        raise SchemaError(f"{ctx}: '{key}' is required and must be non-empty")
    return out


def _as_str_list(value: Any, ctx: str, key: str) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raise SchemaError(f"{ctx}: '{key}' must be a list of strings, got a string")
    if not isinstance(value, Sequence):
        raise SchemaError(f"{ctx}: '{key}' must be a list of strings")
    out: List[str] = []
    for i, v in enumerate(value):
        if not isinstance(v, str):
            raise SchemaError(f"{ctx}: '{key}[{i}]' must be a string")
        if v.strip():
            out.append(v)
    return out


def _check_forbidden(payload: Mapping[str, Any], ctx: str) -> None:
    bad = sorted(set(payload) & FORBIDDEN_DATASET_KEYS)
    if bad:
        raise SchemaError(
            f"{ctx}: system-internal identifiers are not allowed in the common "
            f"benchmark ground truth: {bad}. Express evidence as "
            f"document/article/clause/point/text instead."
        )


# --------------------------------------------------------------------------
# Ground truth
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceRef:
    """One piece of authoritative evidence a correct answer must rest on.

    `required=False` marks evidence that is acceptable but not necessary (for
    example a second document stating the same rule). Hit@k and MRR consider
    required evidence only; Evidence Recall reports both.
    """

    document_id: str
    evidence_id: Optional[str] = None
    article: Optional[str] = None
    clause: Optional[str] = None
    point: Optional[str] = None
    text: Optional[str] = None
    required: bool = True

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any], ctx: str = "gold_evidence") -> "EvidenceRef":
        if not isinstance(payload, Mapping):
            raise SchemaError(f"{ctx}: each evidence entry must be an object")
        _check_forbidden(payload, ctx)
        required = payload.get("required", True)
        if not isinstance(required, bool):
            raise SchemaError(f"{ctx}: 'required' must be a boolean")
        return cls(
            document_id=_as_req_str(payload.get("document_id"), ctx, "document_id"),
            evidence_id=_as_opt_str(payload.get("evidence_id"), ctx, "evidence_id"),
            article=_as_opt_str(payload.get("article"), ctx, "article"),
            clause=_as_opt_str(payload.get("clause"), ctx, "clause"),
            point=_as_opt_str(payload.get("point"), ctx, "point"),
            text=_as_opt_str(payload.get("text"), ctx, "text"),
            required=required,
        )

    # -- normalized views used by every matcher ---------------------------
    @property
    def norm_document_id(self) -> Optional[str]:
        return normalize_document_id(self.document_id)

    @property
    def norm_article(self) -> Optional[str]:
        return normalize_article(self.article)

    @property
    def norm_clause(self) -> Optional[str]:
        return normalize_clause(self.clause)

    @property
    def norm_point(self) -> Optional[str]:
        return normalize_point(self.point)

    def location_key(self) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        return (
            self.norm_document_id,
            self.norm_article,
            self.norm_clause,
            self.norm_point,
        )

    def label(self) -> str:
        parts = [self.document_id]
        if self.article:
            parts.append(f"Điều {normalize_article(self.article)}")
        if self.clause:
            parts.append(f"khoản {normalize_clause(self.clause)}")
        if self.point:
            parts.append(f"điểm {normalize_point(self.point)}")
        return " ".join(parts)

    def key(self) -> str:
        """Stable identity for reporting: the declared id, else the location."""
        return self.evidence_id or self.label()


@dataclass(frozen=True)
class BenchmarkItem:
    """One benchmark question with its architecture-neutral ground truth."""

    id: str
    category: str
    answerable: bool
    question: str
    gold_markers: List[str] = field(default_factory=list)
    gold_claims: List[str] = field(default_factory=list)
    gold_evidence: List[EvidenceRef] = field(default_factory=list)
    source_url: Optional[str] = None
    source_name: Optional[str] = None
    notes: Optional[str] = None
    verification_status: Optional[str] = None
    extra: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "BenchmarkItem":
        if not isinstance(payload, Mapping):
            raise SchemaError("benchmark item must be an object")
        qid = _as_req_str(payload.get("id"), "benchmark item", "id")
        ctx = f"question {qid}"
        _check_forbidden(payload, ctx)
        answerable = payload.get("answerable")
        if not isinstance(answerable, bool):
            raise SchemaError(f"{ctx}: 'answerable' is required and must be a boolean")

        markers = _as_str_list(payload.get("gold_markers"), ctx, "gold_markers")
        # Placeholders such as "<fill in the correct answer>" were used by the
        # legacy KAG question file; they must never count as a gold marker.
        markers = [m for m in markers if not m.strip().startswith("<")]

        evidence_raw = payload.get("gold_evidence") or []
        if isinstance(evidence_raw, Mapping) or isinstance(evidence_raw, str):
            raise SchemaError(f"{ctx}: 'gold_evidence' must be a list")
        evidence = [
            EvidenceRef.from_dict(e, f"{ctx} gold_evidence[{i}]")
            for i, e in enumerate(evidence_raw)
        ]

        known = {
            "id",
            "category",
            "answerable",
            "question",
            "gold_markers",
            "gold_claims",
            "gold_evidence",
            "source_url",
            "source_name",
            "notes",
            "verification_status",
        }
        return cls(
            id=qid,
            category=_as_req_str(payload.get("category"), ctx, "category"),
            answerable=answerable,
            question=_as_req_str(payload.get("question"), ctx, "question"),
            gold_markers=markers,
            gold_claims=_as_str_list(payload.get("gold_claims"), ctx, "gold_claims"),
            gold_evidence=evidence,
            source_url=_as_opt_str(payload.get("source_url"), ctx, "source_url"),
            source_name=_as_opt_str(payload.get("source_name"), ctx, "source_name"),
            notes=_as_opt_str(payload.get("notes"), ctx, "notes"),
            verification_status=_as_opt_str(
                payload.get("verification_status"), ctx, "verification_status"
            ),
            extra={k: v for k, v in payload.items() if k not in known},
        )

    @property
    def required_evidence(self) -> List[EvidenceRef]:
        return [e for e in self.gold_evidence if e.required]


# --------------------------------------------------------------------------
# System output
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class RetrievedContext:
    """One retrieved passage, as reported by a system's adapter.

    `score` is deliberately optional and never compared across systems: a KAG
    graph score, a Chroma distance and a BM25 score are not on one scale. Only
    `rank`, `text` and the legal metadata are used by the evaluator.
    """

    rank: int
    text: Optional[str] = None
    document_id: Optional[str] = None
    article: Optional[str] = None
    clause: Optional[str] = None
    point: Optional[str] = None
    score: Optional[float] = None
    token_count: Optional[int] = None

    @classmethod
    def from_dict(
        cls, payload: Mapping[str, Any], fallback_rank: int, ctx: str
    ) -> "RetrievedContext":
        if not isinstance(payload, Mapping):
            raise SchemaError(f"{ctx}: each retrieved context must be an object")
        rank = payload.get("rank", fallback_rank)
        if isinstance(rank, bool) or not isinstance(rank, int):
            raise SchemaError(f"{ctx}: 'rank' must be an integer")
        if rank < 1:
            raise SchemaError(f"{ctx}: 'rank' is 1-based, got {rank}")
        score = payload.get("score")
        if score is not None and (isinstance(score, bool) or not isinstance(score, (int, float))):
            raise SchemaError(f"{ctx}: 'score' must be a number or null")
        tokens = payload.get("token_count")
        if tokens is not None and (isinstance(tokens, bool) or not isinstance(tokens, int)):
            raise SchemaError(f"{ctx}: 'token_count' must be an integer or null")
        return cls(
            rank=rank,
            text=_as_opt_str(payload.get("text"), ctx, "text"),
            document_id=_as_opt_str(payload.get("document_id"), ctx, "document_id"),
            article=_as_opt_str(payload.get("article"), ctx, "article"),
            clause=_as_opt_str(payload.get("clause"), ctx, "clause"),
            point=_as_opt_str(payload.get("point"), ctx, "point"),
            score=float(score) if score is not None else None,
            token_count=tokens,
        )

    @property
    def norm_document_id(self) -> Optional[str]:
        return normalize_document_id(self.document_id)

    @property
    def norm_article(self) -> Optional[str]:
        return normalize_article(self.article)

    @property
    def norm_clause(self) -> Optional[str]:
        return normalize_clause(self.clause)

    @property
    def norm_point(self) -> Optional[str]:
        return normalize_point(self.point)

    def label(self) -> str:
        loc = " ".join(
            p
            for p in (
                self.document_id or "",
                f"Điều {normalize_article(self.article)}" if self.article else "",
                f"khoản {normalize_clause(self.clause)}" if self.clause else "",
                f"điểm {normalize_point(self.point)}" if self.point else "",
            )
            if p
        )
        return loc or f"rank {self.rank}"


@dataclass(frozen=True)
class Citation:
    """A source the answer points at.

    `claim_index` is optional: when an adapter can tell which answer claim a
    citation was attached to, citation precision can be scored claim-wise;
    otherwise it falls back to location correctness.
    """

    document_id: Optional[str] = None
    article: Optional[str] = None
    clause: Optional[str] = None
    point: Optional[str] = None
    text: Optional[str] = None
    claim_index: Optional[int] = None
    claim: Optional[str] = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any], ctx: str) -> "Citation":
        if not isinstance(payload, Mapping):
            raise SchemaError(f"{ctx}: each citation must be an object")
        claim_index = payload.get("claim_index")
        if claim_index is not None and (
            isinstance(claim_index, bool) or not isinstance(claim_index, int)
        ):
            raise SchemaError(f"{ctx}: 'claim_index' must be an integer or null")
        return cls(
            document_id=_as_opt_str(payload.get("document_id"), ctx, "document_id"),
            article=_as_opt_str(payload.get("article"), ctx, "article"),
            clause=_as_opt_str(payload.get("clause"), ctx, "clause"),
            point=_as_opt_str(payload.get("point"), ctx, "point"),
            text=_as_opt_str(payload.get("text"), ctx, "text"),
            claim_index=claim_index,
            claim=_as_opt_str(payload.get("claim"), ctx, "claim"),
        )

    @property
    def norm_document_id(self) -> Optional[str]:
        return normalize_document_id(self.document_id)

    @property
    def norm_article(self) -> Optional[str]:
        return normalize_article(self.article)

    @property
    def norm_clause(self) -> Optional[str]:
        return normalize_clause(self.clause)

    @property
    def norm_point(self) -> Optional[str]:
        return normalize_point(self.point)

    def label(self) -> str:
        parts = [self.document_id or "?"]
        if self.article:
            parts.append(f"Điều {normalize_article(self.article)}")
        if self.clause:
            parts.append(f"khoản {normalize_clause(self.clause)}")
        if self.point:
            parts.append(f"điểm {normalize_point(self.point)}")
        return " ".join(parts)


@dataclass(frozen=True)
class SystemOutput:
    """One system's answer to one question, in the common shape."""

    question_id: str
    system: str
    answer: Optional[str] = None
    retrieved_contexts: List[RetrievedContext] = field(default_factory=list)
    citations: List[Citation] = field(default_factory=list)
    latency_ms: Optional[float] = None
    error: Optional[str] = None
    answer_claims: Optional[List[str]] = None
    extra: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SystemOutput":
        if not isinstance(payload, Mapping):
            raise SchemaError("system output must be an object")
        qid = _as_req_str(payload.get("question_id"), "system output", "question_id")
        ctx = f"output for {qid}"
        contexts_raw = payload.get("retrieved_contexts") or []
        if isinstance(contexts_raw, (Mapping, str)):
            raise SchemaError(f"{ctx}: 'retrieved_contexts' must be a list")
        contexts = [
            RetrievedContext.from_dict(c, i + 1, f"{ctx} retrieved_contexts[{i}]")
            for i, c in enumerate(contexts_raw)
        ]
        contexts.sort(key=lambda c: c.rank)

        citations_raw = payload.get("citations") or []
        if isinstance(citations_raw, (Mapping, str)):
            raise SchemaError(f"{ctx}: 'citations' must be a list")
        citations = [
            Citation.from_dict(c, f"{ctx} citations[{i}]")
            for i, c in enumerate(citations_raw)
        ]

        latency = payload.get("latency_ms")
        if latency is not None and (
            isinstance(latency, bool) or not isinstance(latency, (int, float))
        ):
            raise SchemaError(f"{ctx}: 'latency_ms' must be a number or null")

        claims = payload.get("answer_claims")
        if claims is not None:
            claims = _as_str_list(claims, ctx, "answer_claims")

        known = {
            "question_id",
            "system",
            "answer",
            "retrieved_contexts",
            "citations",
            "latency_ms",
            "error",
            "answer_claims",
        }
        return cls(
            question_id=qid,
            system=_as_req_str(payload.get("system"), ctx, "system"),
            answer=_as_opt_str(payload.get("answer"), ctx, "answer"),
            retrieved_contexts=contexts,
            citations=citations,
            latency_ms=float(latency) if latency is not None else None,
            error=_as_opt_str(payload.get("error"), ctx, "error"),
            answer_claims=claims,
            extra={k: v for k, v in payload.items() if k not in known},
        )

    def top_k(self, k: Optional[int] = None) -> List[RetrievedContext]:
        """Contexts in rank order, truncated to `k` (all of them when `k` is None)."""
        ordered = sorted(self.retrieved_contexts, key=lambda c: c.rank)
        return ordered if k is None else ordered[:k]

    @property
    def failed(self) -> bool:
        return bool(self.error)


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------


def _unwrap(payload: Any, keys: Sequence[str], what: str) -> List[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, Mapping):
        for key in keys:
            if key in payload:
                inner = payload[key]
                if not isinstance(inner, list):
                    raise SchemaError(f"{what}: '{key}' must be a list")
                return inner
    raise SchemaError(
        f"{what}: expected a JSON list, or an object with one of {list(keys)}"
    )


def parse_benchmark(payload: Any) -> List[BenchmarkItem]:
    items = [BenchmarkItem.from_dict(p) for p in _unwrap(payload, ("items", "questions"), "benchmark")]
    seen: Dict[str, int] = {}
    for i, item in enumerate(items):
        if item.id in seen:
            raise SchemaError(
                f"duplicate question id '{item.id}' at positions {seen[item.id]} and {i}"
            )
        seen[item.id] = i
    return items


def parse_system_outputs(payload: Any) -> List[SystemOutput]:
    return [
        SystemOutput.from_dict(p)
        for p in _unwrap(payload, ("outputs", "results"), "system output file")
    ]


def _read_json(path: str) -> Any:
    with io.open(path, "r", encoding="utf-8") as fin:
        return json.load(fin)


def load_benchmark(path: str) -> List[BenchmarkItem]:
    return parse_benchmark(_read_json(path))


def load_system_outputs(path: str) -> List[SystemOutput]:
    return parse_system_outputs(_read_json(path))


def index_benchmark(items: Iterable[BenchmarkItem]) -> Dict[str, BenchmarkItem]:
    return {item.id: item for item in items}


def index_outputs(outputs: Iterable[SystemOutput]) -> Dict[str, SystemOutput]:
    """Index outputs by question id, rejecting duplicates for the same question."""
    out: Dict[str, SystemOutput] = {}
    for o in outputs:
        if o.question_id in out:
            raise SchemaError(f"duplicate output for question '{o.question_id}'")
        out[o.question_id] = o
    return out
