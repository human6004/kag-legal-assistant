"""Adapter for NativeRAG's single retrieval-and-generation call."""

import sys
from pathlib import Path

from .common import article_number, context, legal_code, main


def adapt_contexts(docs):
    out = []
    for rank, doc in enumerate(docs, 1):
        meta = doc.get("metadata") or {}
        out.append(context(rank, doc.get("content"), legal_code(meta.get("doc_code")),
                           article_number(meta.get("article"))))
    return out


def build_query():
    root = Path(__file__).resolve().parents[2] / "nativeRAG"
    sys.path.insert(0, str(root))
    from rag_core.engine import LegalRAGEngine

    engine = LegalRAGEngine()
    if engine.llm is None:
        raise RuntimeError("NativeRAG LLM is not configured")

    def query(question):
        result = engine.generate(question, include_retrieved=True)
        return result["answer"], adapt_contexts(result["retrieved_contexts"])

    return query


if __name__ == "__main__":
    main("nativerag", build_query)
