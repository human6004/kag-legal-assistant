# -*- coding: utf-8 -*-
"""Text and legal-label normalization shared by every metric.

Design rule: normalization may only erase *presentational* differences
(encoding form, markdown emphasis, thousand separators, spacing). It must never
erase differences that carry legal meaning:

  * digit order         "Điều 13" != "Điều 31"
  * document numbers    "330/2026/NĐ-CP" != "331/2026/NĐ-CP"
  * negation            "không được phép" != "được phép"
  * units / rates       "30 triệu đồng" != "30 triệu", "30,5%" != "305%"

This is why the module does NOT strip "." and "," globally the way the legacy
KAG evaluator does (`kag/solver/eval.py:norm_text`): there, a decimal comma and
a thousand separator are deleted by the same rule, so "30,5%" becomes "305%".
Here separators are removed only *inside digit groups* (see `_THOUSANDS`), so
"100.000.000" == "100 000 000" == "100,000,000" while "30,5%" is preserved.

Two profiles exist:

  * `TEXT_PROFILE`   - whitespace collapsed to single spaces. Use for tokenized
    work (token overlap, judge prompts) where word boundaries matter.
  * `MARKER_PROFILE` - whitespace removed entirely. Use for gold-marker
    substring matching, where a model may write "**100.000.000**đồng" with the
    markdown boundary landing in the middle of the marker. Removing spaces is
    safe for that job because it cannot merge two different numbers or drop a
    negation; it only makes containment less brittle.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable, List, Optional, Set

# Markdown emphasis / table characters a generator may wrap around a marker.
MARKDOWN_CHARS = "*`#_|~"

# A digit group using ".", "," , NBSP or space as *thousand* separator:
# "1.000", "100 000 000", "12,345,678". The lookarounds keep the rule away from
# 4+ digit runs (years: "2026.01") and the {3} requirement keeps decimals
# ("30,5") intact.
_THOUSANDS = re.compile(r"(?<!\d)(\d{1,3})((?:[ .,\u00a0\u202f]\d{3})+)(?!\d)")
_SEPARATORS = re.compile(r"[ .,\u00a0\u202f]")
_WHITESPACE = re.compile(r"\s+")
_WORD = re.compile(r"[0-9a-zA-ZÀ-ỹà-ỹĐđ]+", re.UNICODE)


@dataclass(frozen=True)
class NormalizationProfile:
    """Switches for `normalize`. Every switch is presentational only."""

    nfc: bool = True
    strip_markdown: bool = True
    lowercase: bool = True
    unify_number_separators: bool = True
    collapse_whitespace: bool = True
    strip_whitespace: bool = False


TEXT_PROFILE = NormalizationProfile()
MARKER_PROFILE = NormalizationProfile(strip_whitespace=True)


def _strip_thousands(s: str) -> str:
    def repl(m: "re.Match[str]") -> str:
        return m.group(1) + _SEPARATORS.sub("", m.group(2))

    return _THOUSANDS.sub(repl, s)


def normalize(s: Optional[str], profile: NormalizationProfile = TEXT_PROFILE) -> str:
    """Normalize `s` under `profile`. `None` normalizes to the empty string."""
    if not s:
        return ""
    if profile.nfc:
        s = unicodedata.normalize("NFC", s)
    if profile.strip_markdown:
        for ch in MARKDOWN_CHARS:
            s = s.replace(ch, "")
    if profile.unify_number_separators:
        # Before whitespace handling: "100 000 000" needs its spaces visible.
        s = _strip_thousands(s)
    if profile.lowercase:
        s = s.lower()
    if profile.strip_whitespace:
        s = "".join(s.split())
    elif profile.collapse_whitespace:
        s = _WHITESPACE.sub(" ", s).strip()
    return s


def normalize_text(s: Optional[str]) -> str:
    """Shorthand for `normalize(s, TEXT_PROFILE)`."""
    return normalize(s, TEXT_PROFILE)


def normalize_for_match(s: Optional[str]) -> str:
    """Shorthand for `normalize(s, MARKER_PROFILE)` (substring matching)."""
    return normalize(s, MARKER_PROFILE)


def contains_marker(haystack: Optional[str], marker: Optional[str]) -> bool:
    """True when `marker` appears in `haystack` after marker normalization.

    An empty marker never matches: an empty gold marker is a dataset bug, and
    counting it as a hit would inflate Hit Rate.
    """
    needle = normalize_for_match(marker)
    if not needle:
        return False
    return needle in normalize_for_match(haystack)


def tokenize(s: Optional[str]) -> List[str]:
    """Word tokens of the normalized text. Punctuation is dropped, digits kept."""
    return _WORD.findall(normalize_text(s))


def token_set(s: Optional[str]) -> Set[str]:
    return set(tokenize(s))


def token_coverage(needle: Optional[str], haystack: Optional[str]) -> Optional[float]:
    """Fraction of `needle`'s distinct tokens that also occur in `haystack`.

    Returns `None` when `needle` has no tokens - the question "how much of
    nothing is covered" has no answer, and returning 0.0 or 1.0 would both be a
    silent lie. Callers must handle `None` explicitly.
    """
    a = token_set(needle)
    if not a:
        return None
    b = token_set(haystack)
    return len(a & b) / len(a)


# --------------------------------------------------------------------------
# Legal label normalization
# --------------------------------------------------------------------------

# "Nghị định số 330/2026/NĐ-CP" -> "330/2026/nd-cp"; "330-2026-ND-CP" -> same.
_DOC_PREFIX = re.compile(
    r"^(nghi\s*dinh|nghị\s*định|thong\s*tu|thông\s*tư|quyet\s*dinh|quyết\s*định"
    r"|luat|luật|van\s*ban|văn\s*bản|decree|law|circular|document)?"
    r"\s*(so|số|no\.?|number)?\s*",
    re.IGNORECASE,
)
_DOC_SEPARATORS = re.compile(r"[\\/\-_.\s]+")
_ARTICLE_PREFIX = re.compile(r"^(dieu|điều|article|art\.?)\s*", re.IGNORECASE)
_CLAUSE_PREFIX = re.compile(r"^(khoan|khoản|clause|para\.?|paragraph)\s*", re.IGNORECASE)
_POINT_PREFIX = re.compile(r"^(diem|điểm|point|litera|let\.?)\s*", re.IGNORECASE)
_LABEL_JUNK = re.compile(r"[)\].,;:]+$")


def _fold_diacritics(s: str) -> str:
    """Drop Vietnamese diacritics. Only used on structural labels.

    Safe there because labels are digits plus a latin letter ("53", "3", "b"),
    and document codes are ASCII ("NĐ-CP" -> "nd-cp"). Never call this on
    evidence or answer text: folding tone marks in Vietnamese prose changes
    words ("nghĩa" / "nghía") and can erase meaning.
    """
    s = s.replace("Đ", "D").replace("đ", "d")
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c)
    )


def normalize_document_id(value: Optional[str]) -> Optional[str]:
    """Normalize a legal document identifier, or `None` when absent.

    "330/2026/NĐ-CP", "330-2026-ND-CP" and "Nghị định số 330/2026/NĐ-CP" all
    normalize to "330/2026/nd/cp": every separator becomes "/", so the same
    document written three ways compares equal. Different numbers stay
    different ("331/2026/NĐ-CP" -> "331/2026/nd/cp").
    """
    if value is None:
        return None
    s = unicodedata.normalize("NFC", str(value)).strip()
    if not s:
        return None
    s = _DOC_PREFIX.sub("", s, count=1)
    s = _fold_diacritics(s).lower().strip()
    s = _DOC_SEPARATORS.sub("/", s).strip("/")
    return s or None


def _normalize_label(value: Optional[str], prefix: "re.Pattern[str]") -> Optional[str]:
    if value is None:
        return None
    s = unicodedata.normalize("NFC", str(value)).strip()
    if not s:
        return None
    s = prefix.sub("", s, count=1)
    s = _LABEL_JUNK.sub("", s.strip())
    s = _fold_diacritics(s).lower()
    s = re.sub(r"\s+", "", s)
    return s or None


def normalize_article(value: Optional[str]) -> Optional[str]:
    """"Điều 53" / "53" / "Article 53." -> "53". Keeps suffixes: "53a" -> "53a"."""
    return _normalize_label(value, _ARTICLE_PREFIX)


def normalize_clause(value: Optional[str]) -> Optional[str]:
    """"khoản 3" / "3" / "3)" -> "3"."""
    return _normalize_label(value, _CLAUSE_PREFIX)


def normalize_point(value: Optional[str]) -> Optional[str]:
    """"điểm b" / "b" / "b)" -> "b"."""
    return _normalize_label(value, _POINT_PREFIX)


def unique_preserving_order(items: Iterable[str]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out
