# -*- coding: utf-8 -*-
"""Mechanical evidence check of the 166-question legacy pool against data/processed.

This does not assign PASS/FIX/DROP. It only reports where each legacy marker
actually sits in the corpus, under the B1 normalization (punctuation kept).
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "data" / "processed"
QUESTIONS = ROOT / "kag" / "solver" / "data" / "questions_mo_rong.json"
OUT = Path(__file__).resolve().parent / "_match_report.json"

HEADING = re.compile(r"^####\s+Điều\s+(\d+)\b[.\s:]*(.*)$", re.M)
ARTICLE_ANS = re.compile(r"^điều\s+(\d+)$", re.I)
DOC_ANS = re.compile(
    r"^\d+\s*/\s*(?:\d{4}\s*/\s*)?[A-Za-zĐđ][A-Za-zĐđ0-9\-]*$",
    re.I,
)
EMBEDDED_ARTICLE = re.compile(r"Điều\s+(\d+)", re.I)
KHOAN_LINE = re.compile(r"^(\d+[a-zA-Z]?)\.\s")
POINT_LINE = re.compile(r"^([a-zđ])\)\s", re.I)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s).replace(" ", " ")
    for ch in "*`#_|":
        s = s.replace(ch, "")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\s*\n\s*", " ", s)
    return s.strip().lower()


def loose(s: str) -> str:
    """Legacy kag/solver/eval.py norm: strips '.' and ',' as well. Diagnostic only."""
    return "".join(norm(s).replace(".", "").replace(",", "").split())


def kind_of(answer: str) -> str:
    n = norm(answer)
    if ARTICLE_ANS.match(n):
        return "article"
    if DOC_ANS.match(answer.strip()):
        return "doc_id"
    return "substantive"


def load_corpus():
    docs = []
    for path in sorted(CORPUS.rglob("*.md")):
        raw = path.read_text(encoding="utf-8")
        lines = raw.splitlines()
        title = lines[0].lstrip("#").strip() if lines else ""
        status = lines[1].strip() if len(lines) > 1 else ""
        doc_id = status.split("—")[0].strip() if "—" in status else ""
        header = "\n".join(lines[:3])
        matches = list(HEADING.finditer(raw))
        articles = []
        for i, m in enumerate(matches):
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
            body = raw[start:end]
            articles.append(
                {
                    "number": m.group(1),
                    "heading": m.group(2).strip(),
                    "text": body,
                    "norm": norm(body),
                    "loose": loose(body),
                    "chars": len(body),
                }
            )
        numbers = [a["number"] for a in articles]
        docs.append(
            {
                "stem": path.stem,
                "rel": str(path.relative_to(ROOT)).replace("\\", "/"),
                "title": title,
                "doc_id": doc_id,
                "status": status,
                "header_norm": norm(header),
                "articles": articles,
                "dup_articles": sorted({n for n in numbers if numbers.count(n) > 1}),
            }
        )
    return docs


def index_docs(docs):
    by_stem = {d["stem"]: d for d in docs}
    by_doc_id = {}
    for d in docs:
        by_doc_id[d["doc_id"]] = d
        hyphen = d["doc_id"].replace("/", "-")
        by_doc_id[hyphen] = d
    return by_stem, by_doc_id


def resolve_sources(nguon: str, by_stem, by_doc_id):
    parts = [p.strip() for p in nguon.split("+")]
    found, missing = [], []
    for part in parts:
        key = part[len("metadata/") :] if part.startswith("metadata/") else part
        doc = by_stem.get(key) or by_doc_id.get(key)
        if doc is None:
            missing.append(part)
        else:
            found.append(doc)
    return found, missing


def articles_containing(doc, needle_norm: str, needle_loose: str):
    verbatim, loose_only = [], []
    for art in doc["articles"]:
        if needle_norm and needle_norm in art["norm"]:
            verbatim.append(art["number"])
        elif needle_loose and needle_loose in art["loose"]:
            loose_only.append(art["number"])
    return verbatim, loose_only


def window(art_text: str, marker: str, radius: int = 180) -> str:
    n_art = norm(art_text)
    n_mark = norm(marker)
    idx = n_art.find(n_mark)
    if idx < 0:
        return ""
    # norm() collapses whitespace, so the index is not a raw offset.
    # Fall back to a case-insensitive raw search, then to the heading.
    raw_idx = art_text.lower().find(marker.strip().lower())
    if raw_idx < 0:
        # try first 40 chars of marker
        probe = marker.strip()[:40].lower()
        raw_idx = art_text.lower().find(probe)
    if raw_idx < 0:
        return art_text[: radius * 2].replace("\n", " ")
    a = max(0, raw_idx - radius)
    b = min(len(art_text), raw_idx + len(marker) + radius)
    return art_text[a:b].replace("\n", " ")


def clause_point(art_text: str, marker: str):
    raw_idx = art_text.lower().find(marker.strip().lower()[:40])
    if raw_idx < 0:
        return None, None
    pre = art_text[:raw_idx]
    clause = point = None
    for line in pre.splitlines():
        km = KHOAN_LINE.match(line.strip())
        pm = POINT_LINE.match(line.strip())
        if km:
            clause = km.group(1)
            point = None
        elif pm:
            point = pm.group(1)
    return clause, point


def main():
    docs = load_corpus()
    by_stem, by_doc_id = index_docs(docs)
    questions = json.loads(QUESTIONS.read_text(encoding="utf-8"))

    # corpus-wide verbatim posting list for specificity
    postings = []  # list of (doc_stem, article_number, norm_text) — searched linearly; 765 is fine

    items = []
    for i, q in enumerate(questions):
        sources, missing = resolve_sources(q["nguon"], by_stem, by_doc_id)
        cited = []
        for ans in q["answers"]:
            if kind_of(ans) == "article":
                cited.append(ARTICLE_ANS.match(norm(ans)).group(1))
            else:
                cited.extend(EMBEDDED_ARTICLE.findall(ans))
        # unique, keep order
        seen = set()
        cited_u = []
        for c in cited:
            if c not in seen:
                seen.add(c)
                cited_u.append(c)

        marker_rows = []
        flags = []
        if missing:
            flags.append("UNMAPPED_SOURCE")
        if q["nguon"] == "cau-hoi-goc":
            flags.append("SOURCE_UNSTATED")
        if q["nguon"].startswith("metadata/"):
            flags.append("METADATA_SOURCE")
        if len(sources) > 1:
            flags.append("MULTI_SOURCE")

        cited_found = {}
        for c in cited_u:
            present = [d["stem"] for d in sources if any(a["number"] == c for a in d["articles"])]
            cited_found[c] = present
            if sources and not present:
                flags.append("CITED_ARTICLE_ABSENT")

        substantive = [a for a in q["answers"] if kind_of(a) == "substantive"]
        if not substantive:
            flags.append("NO_SUBSTANTIVE_MARKER")

        search_docs = sources if sources else docs
        for ans in q["answers"]:
            k = kind_of(ans)
            row = {"text": ans, "kind": k}
            if k != "substantive":
                marker_rows.append(row)
                continue
            n_ans, l_ans = norm(ans), loose(ans)
            in_source = []
            loose_source = []
            header_hit = False
            for d in sources:
                v, lo = articles_containing(d, n_ans, l_ans)
                for num in v:
                    in_source.append(f"{d['doc_id']}#{num}")
                for num in lo:
                    loose_source.append(f"{d['doc_id']}#{num}")
                if n_ans in d["header_norm"]:
                    header_hit = True
            corpus_hits = []
            loose_corpus = []
            if not in_source:
                for d in docs:
                    v, lo = articles_containing(d, n_ans, l_ans)
                    for num in v:
                        corpus_hits.append(f"{d['doc_id']}#{num}")
                    for num in lo:
                        loose_corpus.append(f"{d['doc_id']}#{num}")
            row.update(
                {
                    "in_source_articles": in_source,
                    "loose_only_in_source": loose_source,
                    "header_hit": header_hit,
                    "corpus_hits_if_absent": corpus_hits[:12],
                    "n_corpus_verbatim": len(in_source) if in_source else len(corpus_hits),
                    "loose_only_corpus": loose_corpus[:8],
                }
            )
            if not in_source and not corpus_hits:
                if loose_source or loose_corpus:
                    flags.append("MARKER_LOOSE_ONLY")
                elif header_hit:
                    flags.append("HEADER_ONLY")
                else:
                    flags.append("MARKER_MISSING")
            elif not in_source and corpus_hits:
                flags.append("MARKER_OTHER_DOC")
            else:
                cited_ids = {f"{d['doc_id']}#{c}" for d in sources for c in cited_u}
                if cited_u and not any(h in cited_ids for h in in_source):
                    flags.append("MARKER_OUTSIDE_CITED_ARTICLE")
                if len(in_source) > 3 or (not in_source and len(corpus_hits) > 3):
                    flags.append("GENERIC_MARKER")
                if len(n_ans) < 12:
                    flags.append("SHORT_MARKER")
            # evidence window from the best article: cited if possible, else first hit
            window_from = None
            chosen = None
            for d in sources:
                for art in d["articles"]:
                    label = f"{d['doc_id']}#{art['number']}"
                    if label in in_source and (not cited_u or art["number"] in cited_u or chosen is None):
                        if art["number"] in cited_u or chosen is None:
                            chosen = (d, art)
                            if art["number"] in cited_u:
                                break
                if chosen and chosen[1]["number"] in cited_u:
                    break
            if chosen is None:
                # first corpus hit
                for d in docs:
                    for art in d["articles"]:
                        if f"{d['doc_id']}#{art['number']}" in (in_source or corpus_hits):
                            chosen = (d, art)
                            break
                    if chosen:
                        break
            if chosen:
                d, art = chosen
                clause, point = clause_point(art["text"], ans)
                row["window"] = {
                    "doc_id": d["doc_id"],
                    "file": d["stem"],
                    "article": art["number"],
                    "heading": art["heading"][:140],
                    "clause": clause,
                    "point": point,
                    "article_chars": art["chars"],
                    "snippet": window(art["text"], ans)[:420],
                }
            marker_rows.append(row)

        # does one article inside the stated source contain every substantive marker?
        if sources and substantive:
            per_doc = []
            for d in sources:
                sets = []
                for ans in substantive:
                    v, _ = articles_containing(d, norm(ans), loose(ans))
                    sets.append(set(v))
                common = set.intersection(*sets) if sets else set()
                per_doc.append({"doc_id": d["doc_id"], "common_articles": sorted(common, key=int)})
            row_common = per_doc
        else:
            row_common = []
        if sources and substantive and not any(r["common_articles"] for r in row_common):
            if "MARKER_MISSING" not in flags and "MARKER_OTHER_DOC" not in flags and "MARKER_LOOSE_ONLY" not in flags:
                flags.append("NO_SINGLE_ARTICLE")

        # dedupe flags, stable order
        order = []
        for f in flags:
            if f not in order:
                order.append(f)

        items.append(
            {
                "legacy_id": f"L{i + 1:03d}",
                "nhom": q["nhom"],
                "nguon": q["nguon"],
                "source_doc_ids": [d["doc_id"] for d in sources],
                "source_files": [d["rel"] for d in sources],
                "unmapped": missing,
                "question": q["input"],
                "answers": q["answers"],
                "cited_articles": cited_u,
                "cited_articles_found_in": cited_found,
                "common_articles": row_common,
                "flags": order,
                "markers": marker_rows,
            }
        )

    flag_tally = {}
    for it in items:
        key = ",".join(it["flags"]) if it["flags"] else "CLEAN"
        flag_tally[key] = flag_tally.get(key, 0) + 1
    clean = [it["legacy_id"] for it in items if not it["flags"]]
    summary = {
        "n_questions": len(items),
        "n_docs": len(docs),
        "docs": [
            {
                "doc_id": d["doc_id"],
                "stem": d["stem"],
                "n_articles": len(d["articles"]),
                "dup_articles": d["dup_articles"],
                "status": d["status"],
            }
            for d in docs
        ],
        "n_clean": len(clean),
        "clean_ids": clean,
        "flag_tally": dict(sorted(flag_tally.items(), key=lambda kv: -kv[1])),
    }
    OUT.write_text(
        json.dumps({"summary": summary, "items": items}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"questions={len(items)} clean={len(clean)} docs={len(docs)}")
    print("flag tally:")
    for k, v in summary["flag_tally"].items():
        print(f"  {v:3d}  {k}")


if __name__ == "__main__":
    main()
