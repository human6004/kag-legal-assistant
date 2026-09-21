# -*- coding: utf-8 -*-
"""Architecture-neutral benchmark evaluator for KAG / HybridRAG / NativeRAG.

Nothing in this package imports `kag`, `hybridRAG` or `nativeRAG`, and nothing
here treats a system-internal chunk id, node id or vector id as ground truth.
Gold evidence is always a legal location plus its text
(`document -> article -> clause -> point -> text`), so the same dataset scores
three different retrieval architectures without favouring any of their chunking
schemes.

Layers, bottom to top:

  * `normalization`      - presentational-only text normalization (NFC,
    markdown, thousand separators) plus structural label parsing.
  * `models`             - the executable input/output contract.
  * `judge`              - vendor-free semantic-judging abstraction.
  * `evidence_matching`  - the single place that decides "does this context
    support this gold evidence?" (structural -> text -> judge).
  * `retrieval_metrics`, `answer_metrics`, `grounding_metrics`,
    `citation_metrics`, `abstention_metrics` - metric families.
  * `aggregate`          - micro/macro means and bootstrap CIs.
  * `evaluate`           - per-question orchestration, reporting and CLI.

No composite/overall score exists at any layer, by design.
"""
from __future__ import annotations

from .abstention_metrics import (
    ABSTENTION_CUES,
    AbstentionMetrics,
    detect_abstention,
    evaluate_abstention,
)
from .aggregate import (
    STATUS_NOT_APPLICABLE,
    STATUS_OK,
    STATUS_UNAVAILABLE,
    BootstrapConfig,
    MetricSummary,
    QuestionMetrics,
    aggregate,
    bootstrap_ci,
    summaries_to_dict,
)
from .answer_metrics import (
    AnswerMetrics,
    answer_claims,
    evaluate_answer,
    hit_all,
    hit_rate,
    marker_hits,
)
from .citation_metrics import CitationMetrics, evaluate_citations, level_accuracy
from .evaluate import (
    DIAGNOSTIC_METRICS,
    LOWER_IS_BETTER,
    PRIMARY_METRICS,
    EvaluationConfig,
    QuestionResult,
    SystemReport,
    evaluate_question,
    evaluate_system,
    format_report,
)
from .evidence_matching import (
    DEFAULT_POLICY,
    LEVELS,
    EvidenceSupport,
    MatchingPolicy,
    SupportDecision,
    SupportMethod,
    citation_matches_evidence,
    context_supports_any,
    context_supports_evidence,
    contexts_within_budget,
    default_token_counter,
    support_for_evidence,
    support_map,
    text_supported_by_contexts,
    text_supported_by_evidence,
)
from .grounding_metrics import (
    ClaimGrounding,
    ClaimStatus,
    GroundingMetrics,
    classify_claim,
    evaluate_grounding,
)
from .judge import (
    CachingJudge,
    CallableJudge,
    Judge,
    JudgeConfig,
    JudgeResult,
    JudgeUsage,
    JudgeVerdict,
    NullJudge,
    RuleBasedJudge,
    ScriptedJudge,
    default_judge,
)
from .models import (
    FORBIDDEN_DATASET_KEYS,
    BenchmarkItem,
    Citation,
    EvidenceRef,
    RetrievedContext,
    SchemaError,
    SystemOutput,
    index_benchmark,
    index_outputs,
    load_benchmark,
    load_system_outputs,
    parse_benchmark,
    parse_system_outputs,
)
from .normalization import (
    MARKER_PROFILE,
    TEXT_PROFILE,
    NormalizationProfile,
    contains_marker,
    normalize,
    normalize_article,
    normalize_clause,
    normalize_document_id,
    normalize_for_match,
    normalize_point,
    normalize_text,
    token_coverage,
    token_set,
    tokenize,
)
from .retrieval_metrics import DEFAULT_K_VALUES, RetrievalMetrics, evaluate_retrieval

__all__ = [
    # normalization
    "NormalizationProfile",
    "TEXT_PROFILE",
    "MARKER_PROFILE",
    "normalize",
    "normalize_text",
    "normalize_for_match",
    "contains_marker",
    "tokenize",
    "token_set",
    "token_coverage",
    "normalize_document_id",
    "normalize_article",
    "normalize_clause",
    "normalize_point",
    # contract
    "SchemaError",
    "FORBIDDEN_DATASET_KEYS",
    "EvidenceRef",
    "BenchmarkItem",
    "RetrievedContext",
    "Citation",
    "SystemOutput",
    "parse_benchmark",
    "parse_system_outputs",
    "load_benchmark",
    "load_system_outputs",
    "index_benchmark",
    "index_outputs",
    # judge
    "JudgeVerdict",
    "JudgeResult",
    "JudgeConfig",
    "Judge",
    "NullJudge",
    "RuleBasedJudge",
    "ScriptedJudge",
    "CallableJudge",
    "CachingJudge",
    "JudgeUsage",
    "default_judge",
    # matching
    "SupportMethod",
    "SupportDecision",
    "MatchingPolicy",
    "DEFAULT_POLICY",
    "LEVELS",
    "EvidenceSupport",
    "context_supports_evidence",
    "context_supports_any",
    "support_for_evidence",
    "support_map",
    "text_supported_by_contexts",
    "text_supported_by_evidence",
    "citation_matches_evidence",
    "contexts_within_budget",
    "default_token_counter",
    # metrics
    "DEFAULT_K_VALUES",
    "RetrievalMetrics",
    "evaluate_retrieval",
    "AnswerMetrics",
    "evaluate_answer",
    "marker_hits",
    "hit_rate",
    "hit_all",
    "answer_claims",
    "ClaimStatus",
    "ClaimGrounding",
    "GroundingMetrics",
    "classify_claim",
    "evaluate_grounding",
    "CitationMetrics",
    "level_accuracy",
    "evaluate_citations",
    "ABSTENTION_CUES",
    "AbstentionMetrics",
    "detect_abstention",
    "evaluate_abstention",
    # aggregation
    "STATUS_OK",
    "STATUS_NOT_APPLICABLE",
    "STATUS_UNAVAILABLE",
    "QuestionMetrics",
    "BootstrapConfig",
    "MetricSummary",
    "bootstrap_ci",
    "aggregate",
    "summaries_to_dict",
    # orchestration
    "EvaluationConfig",
    "QuestionResult",
    "SystemReport",
    "PRIMARY_METRICS",
    "DIAGNOSTIC_METRICS",
    "LOWER_IS_BETTER",
    "evaluate_question",
    "evaluate_system",
    "format_report",
]
