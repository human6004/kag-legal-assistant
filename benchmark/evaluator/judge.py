# -*- coding: utf-8 -*-
"""Semantic judging abstraction.

The evaluator core never talks to a model vendor. Metrics that need semantic
entailment (Evidence Recall on paraphrase, Context Precision, Claim
Precision/Recall, Faithfulness, Hallucination, citation entailment, abstention
in unclear phrasing) call a `Judge` object. Deterministic metrics never do.

Three judges ship here, all offline:

  * `NullJudge`      - answers UNKNOWN to everything. This is the default, and
    it makes judge-dependent metrics report `None` ("unavailable") instead of a
    fabricated 0. Useful for a deterministic-only run.
  * `RuleBasedJudge` - lexical containment / token coverage. Deterministic and
    reproducible; it never claims NOT_SUPPORTED unless a reject threshold is
    configured, because "I could not match the words" is not evidence of
    contradiction.
  * `ScriptedJudge`  - fixed answers for tests and for replaying a frozen judge
    run.

A real LLM judge is an adapter written *outside* this module (it only has to
subclass `Judge`), so that the core stays importable with no network, no API
key and no SDK. `JudgeConfig` exists to freeze such a judge for the paper:
model name, model version, temperature 0, prompt version, seed. Its
`fingerprint()` goes into the report so a reviewer can tell two runs apart.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from .normalization import normalize_for_match, token_coverage


class JudgeVerdict(str, Enum):
    """Outcome of one entailment question.

    NOT_SUPPORTED and CONTRADICTED are kept apart on purpose: "the evidence does
    not mention this" and "the evidence says the opposite" have different
    consequences for Hallucination Rate.
    """

    SUPPORTED = "supported"
    NOT_SUPPORTED = "not_supported"
    CONTRADICTED = "contradicted"
    UNKNOWN = "unknown"

    @property
    def decided(self) -> bool:
        return self is not JudgeVerdict.UNKNOWN


@dataclass(frozen=True)
class JudgeResult:
    verdict: JudgeVerdict
    score: Optional[float] = None
    rationale: str = ""
    judge: str = ""

    @property
    def supported(self) -> Optional[bool]:
        """True / False / None(unknown). CONTRADICTED is False."""
        if self.verdict is JudgeVerdict.SUPPORTED:
            return True
        if self.verdict in (JudgeVerdict.NOT_SUPPORTED, JudgeVerdict.CONTRADICTED):
            return False
        return None


UNKNOWN_RESULT = JudgeResult(JudgeVerdict.UNKNOWN)


@dataclass(frozen=True)
class JudgeConfig:
    """Everything needed to reproduce a judge run. Freeze this for the paper."""

    model: str
    model_version: str = ""
    temperature: float = 0.0
    prompt_version: str = ""
    seed: Optional[int] = None
    max_output_tokens: Optional[int] = None
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "JudgeConfig":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in payload.items() if k in known})

    def fingerprint(self) -> str:
        """Short stable hash of the config, for the report header."""
        blob = json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


class Judge:
    """Interface every judge implements.

    Subclasses override `entails`; `extract_claims` and `is_abstention` are
    optional and return `None` when the judge cannot decide, which the metrics
    translate into "unavailable" rather than a default value.
    """

    name: str = "judge"
    config: Optional[JudgeConfig] = None
    #: True when this judge produces the same answer for the same input forever.
    deterministic: bool = True

    def entails(self, premise: str, hypothesis: str) -> JudgeResult:
        """Does `premise` support `hypothesis`?"""
        raise NotImplementedError

    def extract_claims(self, answer: str) -> Optional[List[str]]:
        """Split an answer into atomic factual claims, or `None` if unsupported."""
        return None

    def is_abstention(self, answer: str) -> Optional[bool]:
        """Is this answer a refusal to answer, or `None` if undecided?"""
        return None

    def describe(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"judge": self.name, "deterministic": self.deterministic}
        if self.config is not None:
            out["config"] = self.config.to_dict()
            out["config_fingerprint"] = self.config.fingerprint()
        return out


class NullJudge(Judge):
    """Decides nothing. Default judge, so nothing silently becomes 0."""

    name = "null"

    def entails(self, premise: str, hypothesis: str) -> JudgeResult:
        return JudgeResult(JudgeVerdict.UNKNOWN, judge=self.name)


class RuleBasedJudge(Judge):
    """Lexical stand-in for an entailment model.

    SUPPORTED when the hypothesis is contained in the premise after marker
    normalization, or when token coverage reaches `support_threshold`.
    NOT_SUPPORTED only when `reject_threshold` is set and coverage falls to or
    below it; otherwise UNKNOWN. It never returns CONTRADICTED - detecting
    negation reliably needs a real model, and guessing here would turn a
    retrieval gap into a fake hallucination.
    """

    name = "rule_based"

    def __init__(
        self,
        support_threshold: float = 0.8,
        reject_threshold: Optional[float] = None,
    ) -> None:
        if not 0.0 < support_threshold <= 1.0:
            raise ValueError("support_threshold must be in (0, 1]")
        if reject_threshold is not None and not 0.0 <= reject_threshold < support_threshold:
            raise ValueError("reject_threshold must be in [0, support_threshold)")
        self.support_threshold = support_threshold
        self.reject_threshold = reject_threshold

    def entails(self, premise: str, hypothesis: str) -> JudgeResult:
        hyp = normalize_for_match(hypothesis)
        if not hyp:
            return JudgeResult(JudgeVerdict.UNKNOWN, judge=self.name, rationale="empty hypothesis")
        if hyp in normalize_for_match(premise):
            return JudgeResult(
                JudgeVerdict.SUPPORTED, score=1.0, rationale="containment", judge=self.name
            )
        coverage = token_coverage(hypothesis, premise)
        if coverage is None:
            return JudgeResult(JudgeVerdict.UNKNOWN, judge=self.name, rationale="no tokens")
        if coverage >= self.support_threshold:
            return JudgeResult(
                JudgeVerdict.SUPPORTED,
                score=coverage,
                rationale=f"token coverage {coverage:.2f}",
                judge=self.name,
            )
        if self.reject_threshold is not None and coverage <= self.reject_threshold:
            return JudgeResult(
                JudgeVerdict.NOT_SUPPORTED,
                score=coverage,
                rationale=f"token coverage {coverage:.2f}",
                judge=self.name,
            )
        return JudgeResult(
            JudgeVerdict.UNKNOWN,
            score=coverage,
            rationale=f"token coverage {coverage:.2f} is inconclusive",
            judge=self.name,
        )


def _key(premise: str, hypothesis: str) -> Tuple[str, str]:
    return (normalize_for_match(premise), normalize_for_match(hypothesis))


class ScriptedJudge(Judge):
    """Judge with pre-recorded answers. For tests and frozen-judge replays.

    `verdicts` maps `(premise, hypothesis)` to a verdict; keys are matched after
    marker normalization so test fixtures can be written naturally. `default`
    applies to anything not scripted - keep it UNKNOWN unless a test needs a
    closed world.
    """

    name = "scripted"

    def __init__(
        self,
        verdicts: Optional[Mapping[Tuple[str, str], JudgeVerdict]] = None,
        default: JudgeVerdict = JudgeVerdict.UNKNOWN,
        claims: Optional[Mapping[str, List[str]]] = None,
        abstentions: Optional[Mapping[str, bool]] = None,
        hypothesis_verdicts: Optional[Mapping[str, JudgeVerdict]] = None,
    ) -> None:
        self._verdicts = {_key(p, h): v for (p, h), v in (verdicts or {}).items()}
        self._by_hypothesis = {
            normalize_for_match(h): v for h, v in (hypothesis_verdicts or {}).items()
        }
        self._default = default
        self._claims = {normalize_for_match(k): v for k, v in (claims or {}).items()}
        self._abstentions = {
            normalize_for_match(k): v for k, v in (abstentions or {}).items()
        }
        self.calls: List[Tuple[str, str]] = []

    def entails(self, premise: str, hypothesis: str) -> JudgeResult:
        self.calls.append((premise, hypothesis))
        k = _key(premise, hypothesis)
        if k in self._verdicts:
            return JudgeResult(self._verdicts[k], judge=self.name, rationale="scripted")
        hk = normalize_for_match(hypothesis)
        if hk in self._by_hypothesis:
            return JudgeResult(
                self._by_hypothesis[hk], judge=self.name, rationale="scripted by hypothesis"
            )
        return JudgeResult(self._default, judge=self.name, rationale="scripted default")

    def extract_claims(self, answer: str) -> Optional[List[str]]:
        return self._claims.get(normalize_for_match(answer))

    def is_abstention(self, answer: str) -> Optional[bool]:
        return self._abstentions.get(normalize_for_match(answer))


class CallableJudge(Judge):
    """Wrap a plain function as a judge. Handy for ad-hoc experiments."""

    name = "callable"

    def __init__(
        self,
        fn: Callable[[str, str], JudgeResult],
        name: str = "callable",
        config: Optional[JudgeConfig] = None,
        deterministic: bool = True,
    ) -> None:
        self._fn = fn
        self.name = name
        self.config = config
        self.deterministic = deterministic

    def entails(self, premise: str, hypothesis: str) -> JudgeResult:
        return self._fn(premise, hypothesis)


class CachingJudge(Judge):
    """Memoize another judge. An LLM judge is slow and billed per call."""

    def __init__(self, inner: Judge) -> None:
        self.inner = inner
        self.name = f"cached({inner.name})"
        self.config = inner.config
        self.deterministic = inner.deterministic
        self._cache: Dict[Tuple[str, str], JudgeResult] = {}
        self.hits = 0
        self.misses = 0

    def entails(self, premise: str, hypothesis: str) -> JudgeResult:
        k = _key(premise, hypothesis)
        if k in self._cache:
            self.hits += 1
            return self._cache[k]
        self.misses += 1
        result = self.inner.entails(premise, hypothesis)
        self._cache[k] = result
        return result

    def extract_claims(self, answer: str) -> Optional[List[str]]:
        return self.inner.extract_claims(answer)

    def is_abstention(self, answer: str) -> Optional[bool]:
        return self.inner.is_abstention(answer)


@dataclass
class JudgeUsage:
    """Bookkeeping so a report can state how much of it rested on the judge."""

    calls: int = 0
    decided: int = 0
    unknown: int = 0
    by_verdict: Dict[str, int] = field(default_factory=dict)

    def record(self, result: JudgeResult) -> JudgeResult:
        self.calls += 1
        if result.verdict.decided:
            self.decided += 1
        else:
            self.unknown += 1
        self.by_verdict[result.verdict.value] = self.by_verdict.get(result.verdict.value, 0) + 1
        return result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "calls": self.calls,
            "decided": self.decided,
            "unknown": self.unknown,
            "by_verdict": dict(self.by_verdict),
        }


def default_judge() -> Judge:
    """The judge used when a caller passes none: decides nothing, invents nothing."""
    return NullJudge()
