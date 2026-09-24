"""Adapter for the configured KAG solver and its retrieval trace."""

import asyncio
import importlib
import importlib.util
import json
import os
import sys
from pathlib import Path

from .common import article_number, context, legal_code, main


def adapt_contexts(reporter):
    out = []
    seen = set()
    for report_id in dict.fromkeys(reporter.report_record):
        event = reporter.report_stream_data[report_id]
        if event["segment"] != "reference":
            continue
        response = event["content"]
        for chunk in getattr(response, "chunk_datas", getattr(response, "chunks", [])):
            raw = str(chunk.content)
            if raw.startswith('"') and raw.endswith('"'):
                try:
                    raw = json.loads(raw)
                except ValueError:
                    pass
            key = getattr(chunk, "chunk_id", None) or raw
            if not raw or key in seen:
                continue
            seen.add(key)
            props = getattr(chunk, "properties", {}) or {}
            document_id = legal_code(props.get("sourceDocumentId") or props.get("doc_code"))
            document_id = document_id or legal_code(getattr(chunk, "title", ""))
            article = props.get("article_no") or article_number(getattr(chunk, "title", ""))
            out.append(context(len(out) + 1, raw, document_id, str(article) if article else None,
                               str(props["clause_no"]) if props.get("clause_no") else None,
                               str(props["point_no"]) if props.get("point_no") else None,
                               getattr(chunk, "score", None)))
    return out


class KAGQuery:
    def __init__(self, pipeline, reporter_factory):
        self.pipeline = pipeline
        self.reporter_factory = reporter_factory
        self.loop = asyncio.new_event_loop()

    def __call__(self, question):
        reporter = self.reporter_factory()
        answer = self.loop.run_until_complete(
            self.pipeline.ainvoke(question, reporter=reporter)
        )
        return answer, adapt_contexts(reporter)

    def close(self):
        if self.loop.is_closed():
            return
        try:
            self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            self.loop.run_until_complete(self.loop.shutdown_default_executor())
        finally:
            self.loop.close()


def build_query():
    root = Path(__file__).resolve().parents[2]
    kag_root = root / "kag"
    sys.path.insert(0, str(root / "vendor" / "KAG"))
    sys.path.insert(0, str(kag_root))
    os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
    previous = Path.cwd()
    try:
        os.chdir(kag_root)  # KAG_CONFIG discovers kag_config.yaml from cwd.
        KAG_CONFIG = importlib.import_module("kag.common.conf").KAG_CONFIG
        project = KAG_CONFIG.all_config["project"]
        if str(project["id"]) != "4" or project["namespace"] != "LegalFinalCand":
            raise ValueError("KAG benchmark requires project 4 / LegalFinalCand")
        import_modules_from_path = importlib.import_module("kag.common.registry").import_modules_from_path
        SolverPipelineABC = importlib.import_module("kag.interface").SolverPipelineABC
        TraceLogReporter = importlib.import_module("kag.solver.reporter.trace_log_reporter").TraceLogReporter

        import_modules_from_path(str(kag_root / "solver"))
        spec = importlib.util.spec_from_file_location("_legal_eval_for_prompts", kag_root / "solver" / "eval.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module._nap_prompt_theo_duong_dan(str(kag_root / "builder" / "prompt"))
        pipeline = SolverPipelineABC.from_config(KAG_CONFIG.all_config["kag_solver_pipeline"])
    finally:
        os.chdir(previous)

    return KAGQuery(pipeline, TraceLogReporter)


if __name__ == "__main__":
    main("kag", build_query)
