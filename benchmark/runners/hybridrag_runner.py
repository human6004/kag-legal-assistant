"""Adapter for the same Retriever/AnswerGenerator pair used by HybridRAG API."""

import os
import sys
from pathlib import Path

from .common import article_number, context, legal_code, main


def adapt_contexts(nodes):
    out = []
    for rank, item in enumerate(nodes, 1):
        node = getattr(item, "node", item)
        meta = getattr(node, "metadata", {}) or {}
        text = node.get_content() if hasattr(node, "get_content") else getattr(node, "text", None)
        out.append(context(rank, text, legal_code(meta.get("doc_code")),
                           article_number(meta.get("article")), score=getattr(item, "score", None)))
    return out


def build_query():
    root = Path(__file__).resolve().parents[2] / "hybridRAG"
    sys.path.insert(0, str(root))
    previous = Path.cwd()
    try:
        os.chdir(root)  # Existing API resolves BM25/Chroma paths against cwd.
        from api.main import generator, retriever
    finally:
        os.chdir(previous)

    def query(question):
        nodes = retriever.retrieve(question)
        return generator.generate(question=question, contexts=nodes), adapt_contexts(nodes)

    return query


if __name__ == "__main__":
    main("hybridrag", build_query)
