"""Input isolation, output contract, and batch CLI shared by all systems."""

import argparse
import json
import os
import re
import tempfile
import time
from pathlib import Path

from benchmark.adapters.citation_parser import parse_citation_payloads
from benchmark.evaluator.models import SystemOutput, parse_system_outputs


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


def _atomic_write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as temp:
            temp_path = Path(temp.name)
            json.dump(payload, temp, ensure_ascii=False, indent=2)
            temp.write("\n")
            temp.flush()
            os.fsync(temp.fileno())
        os.replace(temp_path, path)
        temp_path = None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _load_resume_outputs(path, system, question_ids):
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("resume output must be a JSON list")
    records = parse_system_outputs(payload)
    seen = set()
    for record in records:
        if record.question_id in seen:
            raise ValueError(f"duplicate question_id in resume output: {record.question_id}")
        seen.add(record.question_id)
        if record.system != system:
            raise ValueError(
                f"resume system mismatch for {record.question_id}: "
                f"expected {system}, got {record.system}"
            )
        if record.question_id not in question_ids:
            raise ValueError(f"resume question_id not in dataset: {record.question_id}")
    return {row["question_id"]: row for row in payload}


def main(system, build_query):
    parser = argparse.ArgumentParser(description=f"Run {system} on a benchmark dataset")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--resume", action="store_true", help="resume from valid outputs in --out")
    args = parser.parse_args()
    dataset, out = Path(args.dataset).resolve(), Path(args.out).resolve()
    questions = load_questions(dataset)
    question_ids = {qid for qid, _ in questions}
    outputs_by_id = (
        _load_resume_outputs(out, system, question_ids)
        if args.resume and out.exists()
        else {}
    )
    query = build_query()  # Startup and index loading are outside latency.
    try:
        for qid, question in questions:
            if qid in outputs_by_id:
                continue
            outputs_by_id[qid] = run_question(qid, question, system, query)
            _atomic_write_json(
                out,
                [outputs_by_id[question_id] for question_id, _ in questions
                 if question_id in outputs_by_id],
            )
    finally:
        close_query = getattr(query, "close", None)
        if callable(close_query):
            close_query()
    outputs = [outputs_by_id[qid] for qid, _ in questions if qid in outputs_by_id]
    _atomic_write_json(out, outputs)
    print(f"wrote {len(outputs)} outputs to {out}")
