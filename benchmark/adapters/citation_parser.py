# -*- coding: utf-8 -*-
"""One citation parser, used by all three adapters.

Why this exists. The `citations` field means three different things in the
three systems, and taking each system's word for it would not compare like
with like:

  * KAG emits prose citations *and* `<reference id="chunk:1_2">` tags, whose id
    indexes its own trace log rather than a legal location;
  * HybridRAG emits prose citations plus a trailing "Căn cứ:" list;
  * NativeRAG emits prose citations, but the `citations` field its engine
    returns is a copy of the documents it retrieved. Copying that field into
    the benchmark would make its Citation Recall equal to its retrieval recall,
    for free, without the answer ever pointing at anything.

What all three prompts do require is an inline Vietnamese prose citation. That
is the only common ground, so it is the only thing parsed here: the input is
the answer text and nothing else.

The contract, which adapters may not work around:

  * `citations[]` is whatever this parser extracts from `answer`;
  * it is never built from `retrieved_contexts`, from chunk metadata, or from
    any other channel;
  * `<reference>` tags are ignored - they point at a trace log, not at a law.

Recognised forms, deepest first, with the document optional on each:

    điểm b khoản 2 Điều 8 Nghị định 13/2023/NĐ-CP
    khoản 2 Điều 8 Nghị định 13/2023/NĐ-CP
    Điều 8 khoản 2 của Nghị định 13/2023/NĐ-CP
    Điều 8 Nghị định 13/2023/NĐ-CP
    Luật 59/2020/QH14

A citation that names no document inherits the nearest document mentioned
before it in the same answer - the same rule for every system.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from ..evaluator.models import Citation

# "13/2023/NĐ-CP", "59/2020/QH14", "27/2024/QĐ-TTg".
_DOC_CODE = r"\d{1,4}/\d{4}/[A-ZĐ][A-Za-zĐđ0-9]{0,5}(?:-[A-ZĐ][A-Za-zĐđ0-9]{0,5})*"
# The document type is part of the match so that "Điều 8 Nghị định 13/2023/..."
# reads as one citation: the words between the article and the number must not
# look like a gap, or the two halves would be grouped apart.
_DOC_KIND = (
    r"(?:nghị\s*định|nghi\s*dinh|thông\s*tư|thong\s*tu|quyết\s*định|quyet\s*dinh"
    r"|nghị\s*quyết|nghi\s*quyet|pháp\s*lệnh|phap\s*lenh|bộ\s*luật|bo\s*luat"
    r"|luật|luat|văn\s*bản|van\s*ban)\s*(?:số|so)?\s*"
)

_MARKERS = re.compile(
    r"(?P<document>(?:" + _DOC_KIND + r")?(?P<code>" + _DOC_CODE + r"))"
    r"|(?P<point>đi[ểe]m\s+(?P<point_value>[a-zđ]{1,2})(?![\w]))"
    r"|(?P<article>[đd]i[ềe]u\s+(?P<article_value>\d{1,4}[a-zđ]?)(?![\w]))"
    r"|(?P<clause>kho[ảa]n\s+(?P<clause_value>\d{1,3}[a-zđ]?)(?![\w]))",
    re.IGNORECASE | re.UNICODE,
)

#: KAG's reference tags index its own trace log, so they are removed before
#: parsing rather than parsed: keeping them would also break the adjacency rule
#: below by inserting markup between two halves of one citation.
_REFERENCE_TAG = re.compile(r"</?reference[^>]*>", re.IGNORECASE)

#: Text allowed to sit between two markers of the same citation. Anything else
#: (a verb, a number, a new sentence) ends the citation.
_FILLER = re.compile(
    r"^(?:[\s,;:.()\[\]\-–\"'“”]|của|cua|tại|tai|theo|và|va|quy\s*định|quy\s*dinh"
    r"|căn\s*cứ|can\s*cu|thuộc|thuoc|ở|o)*$",
    re.IGNORECASE | re.UNICODE,
)

def _markers(text: str) -> List[Tuple[str, str, int, int]]:
    """(level, value, start, end) for every legal marker, in reading order."""
    found: List[Tuple[str, str, int, int]] = []
    for m in _MARKERS.finditer(text):
        for level, value_group in (
            ("document", "code"),
            ("point", "point_value"),
            ("article", "article_value"),
            ("clause", "clause_value"),
        ):
            if m.group(level) is not None:
                found.append((level, m.group(value_group), m.start(), m.end()))
                break
    return found


def _group(text: str, markers: List[Tuple[str, str, int, int]]) -> List[Dict[str, str]]:
    """Fold adjacent markers into one citation each.

    Two markers belong together when only filler separates them and they speak
    about different levels. A repeated level ("Điều 8 và Điều 9") starts a new
    citation, which is what keeps a list of articles from collapsing into one.
    """
    groups: List[Dict[str, str]] = []
    current: Dict[str, str] = {}
    previous_end: Optional[int] = None
    for level, value, start, end in markers:
        gap = text[previous_end:start] if previous_end is not None else ""
        if current and (level in current or not _FILLER.match(gap)):
            groups.append(current)
            current = {}
        current[level] = value
        previous_end = end
    if current:
        groups.append(current)
    return groups


def parse_citations(answer: Optional[str]) -> List[Citation]:
    """Extract the citations an answer makes, in order of first appearance.

    Duplicates are collapsed on the normalized `(document, article, clause,
    point)` tuple, so repeating a citation neither helps nor hurts precision.
    """
    if not answer:
        return []
    text = _REFERENCE_TAG.sub(" ", answer)
    groups = _group(text, _markers(text))

    out: List[Citation] = []
    seen = set()
    document: Optional[str] = None
    for group in groups:
        document = group.get("document", document)
        if "article" not in group and document is None:
            # A bare "khoản 2" before any document has been named points
            # nowhere; dropping it is better than inventing a location.
            continue
        citation = Citation(
            document_id=document,
            article=group.get("article"),
            clause=group.get("clause"),
            point=group.get("point"),
        )
        key = citation_key(citation)
        if key in seen:
            continue
        seen.add(key)
        out.append(citation)
    return out


def parse_citation_payloads(answer: Optional[str]) -> List[Dict[str, Any]]:
    """`parse_citations` as plain dicts, ready for `system_output.json`."""
    payloads: List[Dict[str, Any]] = []
    for c in parse_citations(answer):
        payload: Dict[str, Any] = {}
        for key, value in (
            ("document_id", c.document_id),
            ("article", c.article),
            ("clause", c.clause),
            ("point", c.point),
        ):
            if value is not None:
                payload[key] = value
        payloads.append(payload)
    return payloads


def citation_key(citation: Citation) -> Tuple[Optional[str], ...]:
    """Normalized location tuple, for de-duplication and for comparing systems."""
    return (
        citation.norm_document_id,
        citation.norm_article,
        citation.norm_clause,
        citation.norm_point,
    )
