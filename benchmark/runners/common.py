"""Input isolation, output contract, and batch CLI shared by all systems."""

import argparse
import json
import re
import time
from pathlib import Path

from benchmark.adapters.citation_parser import parse_citation_payloads
from benchmark.evaluator.models import SystemOutput


DOC_CODE = re.compile(r"\b\d{1,4}(?:/\d{4})?/[A-ZĐ][\wĐđ]*(?:-[A-ZĐ][\wĐđ]*)*\b", re.I)
ARTICLE = re.compile(r"\bĐiều\s+(\d+[a-zđ]?)\b", re.I)


def load_questions(path):
    """Project untrusted dataset to exactly the two fields systems may see."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = data if isinstance(data, list) else data.get("items", data.get("questions"))
    if not isinstance(rows, list):
        raise ValueError("dataset must contain a list of questions")
    questions = []
    seen = set()
    for row in rows:
        question_id, question = row["id"], row["question"]
        if not isinstance(question_id, str) or not question_id or question_id in seen:
            raise ValueError(f"invalid or duplicate question id: {question_id!r}")
        if not isinstance(question, str) or not question:
            raise ValueError(f"invalid question: {question_id!r}")
        seen.add(question_id)
        questions.append((question_id, question))
    return questions


def legal_code(value):
    match = DOC_CODE.search(value or "")
    return match.group(0) if match else None


def article_number(value):
    if isinstance(value, int) or (isinstance(value, str) and re.fullmatch(r"\d+[a-zđ]?", value, re.I)):
        return str(value)
    match = ARTICLE.search(str(value or ""))
    return match.group(1) if match else None


def context(rank, text, document_id=None, article=None, clause=None, point=None, score=None):
    return dict(rank=rank, document_id=document_id, article=article, clause=clause,
                point=point, text=text, score=score)


def run_question(question_id, question, system, query):
    start = time.perf_counter()
    answer, contexts, error = None, [], None
    try:
        answer, contexts = query(question)
        if not isinstance(answer, str):
            raise TypeError("system answer must be text")
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        answer = None
    output = dict(
        question_id=question_id, system=system, answer=answer,
        retrieved_contexts=contexts, citations=parse_citation_payloads(answer),
        latency_ms=(time.perf_counter() - start) * 1000, error=error,
    )
    SystemOutput.from_dict(output)
    return output


def main(system, build_query):
    parser = argparse.ArgumentParser(description=f"Run {system} on a benchmark dataset")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    dataset, out = Path(args.dataset).resolve(), Path(args.out).resolve()
    questions = load_questions(dataset)
    query = build_query()  # Startup and index loading are outside latency.
    outputs = [run_question(qid, question, system, query) for qid, question in questions]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(outputs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(outputs)} outputs to {out}")
