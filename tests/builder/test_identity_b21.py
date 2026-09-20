# -*- coding: utf-8 -*-
"""B2.1 identity checks on the real offline Reader/Splitter and graph assembly."""

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kag"))

from builder.canon_id import article_identity, canon_id, source_document_id  # noqa: E402
from builder.extractor import LegalSchemaFreeExtractor  # noqa: E402
from builder.reader import LegalMarkdownReader  # noqa: E402
from builder.splitter import LegalStructuralSplitter  # noqa: E402
from kag.builder.model.chunk import Chunk  # noqa: E402

ND142 = ROOT / "data/processed/vn_ai/142-2026-ND-CP_quy-dinh-chi-tiet-luat-tri-tue-nhan-tao.md"


def fixture_chunk(doc_id="134-2025-QH15", article_no=1, content="Nội dung Điều này."):
    source = next((ROOT / "data/processed").rglob(f"{doc_id}_*.md"))
    path = source.relative_to(ROOT).as_posix()
    return Chunk(
        id=f"chunk-{doc_id}-{article_no}",
        name=f"{doc_id} / Điều {article_no}. Phạm vi điều chỉnh",
        content=content,
        source_path=path,
        heading_path=[doc_id, f"Điều {article_no}. Phạm vi điều chỉnh"],
        article_no=article_no,
    )


def graph_for(chunk, entities=None, triples=None, official=None):
    extractor = object.__new__(LegalSchemaFreeExtractor)
    extractor.schema = {
        label: SimpleNamespace(properties={})
        for label in ("Article", "LegalDocument", "Sanction", "LegalTerm", "Others")
    }
    extractor.external_graph = None
    entities = [dict(item) for item in (entities or [])]
    graph, entities = extractor.assemble_sub_graph_with_spg_records(entities)
    if official:
        extractor.append_official_name(entities, official)
    extractor.assemble_sub_graph(graph, chunk, entities, [list(t) for t in (triples or [])])
    return graph


class B21IdentityTests(unittest.TestCase):
    def test_document_mapping_entire_corpus(self):
        files = sorted((ROOT / "data/processed").rglob("*.md"))
        self.assertEqual(len(files), 23)
        for path in files:
            doc_id = source_document_id(path.relative_to(ROOT).as_posix())
            self.assertTrue(doc_id, path)
            meta = json.loads((ROOT / "data/metadata" / f"{doc_id}.json").read_text(encoding="utf-8"))
            self.assertEqual(doc_id, meta["doc_id"])
        self.assertIsNone(source_document_id("C:/private/142-2026-ND-CP_x.md"))
        self.assertIsNone(source_document_id("data/processed/vn_ai/unknown_x.md"))

    def test_two_article_ones_do_not_collide(self):
        ids = []
        for doc in ("134-2025-QH15", "24-2018-QH14"):
            graph = graph_for(fixture_chunk(doc), [{"name": "Điều 1", "category": "Article"}])
            articles = [node for node in graph.nodes if node.label == "Article"]
            self.assertEqual(len(articles), 1)
            self.assertEqual(articles[0].properties["articleNumber"], "1")
            self.assertNotEqual(articles[0].name, articles[0].id)
            ids.append(articles[0].id)
        self.assertEqual(ids, ["article:134-2025-QH15:1", "article:24-2018-QH14:1"])

    def test_six_chunks_share_article_but_not_chunk_identity(self):
        reader = LegalMarkdownReader(cut_depth=4)
        chunks, _ = reader.solve_content(str(ND142), ND142.stem, ND142.read_text(encoding="utf-8"))
        source = next(c for c in chunks if c.name.split(" / ")[-1].startswith("Điều 13."))
        children = LegalStructuralSplitter()._invoke(source)
        self.assertEqual(len(children), 6)
        self.assertEqual(len({c.id for c in children}), 6)
        article_ids = {
            node.id
            for chunk in children
            for node in graph_for(chunk, [{"name": "Điều 13", "category": "Article"}]).nodes
            if node.label == "Article" and node.id.startswith("article:")
        }
        self.assertEqual(article_ids, {"article:142-2026-ND-CP:13"})
        self.assertEqual(article_ids, {
            node.id
            for chunk in LegalStructuralSplitter()._invoke(source)
            for node in graph_for(chunk, [{"name": "Điều 13", "category": "Article"}]).nodes
            if node.label == "Article" and node.id.startswith("article:")
        })

    def test_quoted_amendment_articles_do_not_merge_with_source_article(self):
        path = next((ROOT / "data/processed").rglob("35-2018-QH14_*.md"))
        reader = LegalMarkdownReader(cut_depth=4)
        chunks, _ = reader.solve_content(str(path), path.stem, path.read_text(encoding="utf-8"))
        for number in (22, 23):
            distinct = [c for c in chunks if c.name.split(" / ")[-1].startswith(f"Điều {number}.")]
            self.assertEqual(len(distinct), 2)
            ids = []
            for chunk in distinct:
                split_chunk = LegalStructuralSplitter()._invoke(chunk)[0]
                self.assertEqual(split_chunk.kwargs["article_no"], number)
                graph = graph_for(split_chunk, [{"name": f"Điều {number}", "category": "Article"}])
                ids.append(next(n.id for n in graph.nodes if n.label == "Article"))
            self.assertEqual(len(set(ids)), 2)
            self.assertEqual(ids[0], f"article:35-2018-QH14:{number}")
            self.assertTrue(ids[1].startswith("article-unresolved:"))
        quoted_35 = next(c for c in chunks if c.name.split(" / ")[-1].startswith("Điều 35."))
        quoted = LegalStructuralSplitter()._invoke(quoted_35)[0]
        graph = graph_for(quoted, [{"name": "Điều 35", "category": "Article"}])
        self.assertTrue(next(n.id for n in graph.nodes if n.label == "Article").startswith("article-unresolved:"))

    def test_node_and_both_semantic_endpoints_use_one_article_id(self):
        article = "Điều 1"
        sanction = "Phạt tiền từ 10.000.000 đồng đến 20.000.000 đồng"
        chunk = fixture_chunk()
        graph = graph_for(
            chunk,
            [{"name": article, "category": "Article"}, {"name": sanction, "category": "Sanction"}],
            [[article, "imposes", sanction], [sanction, "basedOn", article]],
            [{"name": article, "category": "Article", "official_name": "Điều 1 Luật 134/2025/QH15"}],
        )
        articles = [n for n in graph.nodes if n.label == "Article"]
        self.assertEqual([n.id for n in articles], ["article:134-2025-QH15:1"])
        self.assertEqual(articles[0].properties["articleNumber"], "1")
        # Cạnh do LLM khai mang `originalPredicate`; cạnh hệ thống thì không.
        # Lọc theo dấu đó, không liệt kê tên cạnh hệ thống: danh sách tên phải
        # sửa lại mỗi lần thêm một cạnh cấu trúc, còn dấu này thì đúng mãi.
        semantic = [e for e in graph.edges if "originalPredicate" in (e.properties or {})]
        self.assertEqual(len(semantic), 2)
        self.assertEqual(semantic[0].from_id, articles[0].id)
        self.assertEqual(semantic[1].to_id, articles[0].id)
        self.assertFalse(any(e.label == "OfficialName" and e.from_type == "Article" for e in graph.edges))
        # Điều nguồn biết mình thuộc văn bản nào kể cả khi LLM không khai gì:
        # cạnh cấu trúc, nên KHÔNG mang `originalPredicate` (xem lọc ở trên).
        structural = [e for e in graph.edges if e.label == "belongsTo"]
        self.assertEqual(len(structural), 1)
        self.assertEqual(structural[0].from_id, articles[0].id)
        self.assertEqual(structural[0].to_id, canon_id("Luật 134/2025/QH15"))
        self.assertNotIn("originalPredicate", structural[0].properties or {})

    def test_raw_article_with_source_document_number_resolves(self):
        path = next((ROOT / "data/processed").rglob("330-2026-ND-CP_*.md"))
        reader = LegalMarkdownReader(cut_depth=4)
        chunks, _ = reader.solve_content(str(path), path.stem, path.read_text(encoding="utf-8"))
        source = next(c for c in chunks if c.name.split(" / ")[-1].startswith("Điều 34."))
        chunk = LegalStructuralSplitter()._invoke(source)[0]
        name = "Điều 34 Nghị định số 330/2026/NĐ-CP"
        graph = graph_for(chunk, [{"name": name, "category": "Article"}])
        self.assertEqual([n.id for n in graph.nodes if n.label == "Article"],
                         ["article:330-2026-ND-CP:34"])

    def test_external_same_number_stays_unresolved(self):
        reader = LegalMarkdownReader(cut_depth=4)
        chunks, _ = reader.solve_content(str(ND142), ND142.stem, ND142.read_text(encoding="utf-8"))
        source = next(c for c in chunks if c.name.split(" / ")[-1].startswith("Điều 13."))
        chunk = next(c for c in LegalStructuralSplitter()._invoke(source)
                     if "Điều 13 của Luật Trí tuệ nhân tạo" in c.content)
        graph = graph_for(
            chunk,
            [{"name": "Điều 13", "category": "Article"}, {"name": "X", "category": "Sanction"}],
            [["X", "basedOn", "Điều 13"]],
        )
        canonical = "article:142-2026-ND-CP:13"
        self.assertIn(canonical, [n.id for n in graph.nodes])
        edge = next(e for e in graph.edges if e.label == "basedOn")
        self.assertTrue(edge.to_id.startswith("article-unresolved:"), edge.to_id)
        self.assertNotEqual(edge.to_id, canonical)
        self.assertIn(edge.to_id, [n.id for n in graph.nodes])
        self.assertEqual(edge.to_id, next(e for e in graph_for(
            chunk, [{"name": "Điều 13", "category": "Article"}, {"name": "X", "category": "Sanction"}],
            [["X", "basedOn", "Điều 13"]],
        ).edges if e.label == "basedOn").to_id)
        other = fixture_chunk("24-2018-QH14", 13, chunk.content)
        other_graph = graph_for(other, [{"name": "Điều 13", "category": "Article"}])
        self.assertNotIn(edge.to_id, [n.id for n in other_graph.nodes])

    def test_qualified_other_law_name_never_becomes_source_article(self):
        reader = LegalMarkdownReader(cut_depth=4)
        chunks, _ = reader.solve_content(str(ND142), ND142.stem, ND142.read_text(encoding="utf-8"))
        source = next(c for c in chunks if c.name.split(" / ")[-1].startswith("Điều 13."))
        chunk = next(c for c in LegalStructuralSplitter()._invoke(source)
                     if "Điều 13 của Luật Trí tuệ nhân tạo" not in c.content)
        name = "Điều 13 của Luật Trí tuệ nhân tạo"
        graph = graph_for(chunk, [{"name": name, "category": "Article"},
                                  {"name": "X", "category": "Sanction"}],
                          [["X", "basedOn", name]])
        edge = next(e for e in graph.edges if e.label == "basedOn")
        self.assertTrue(edge.to_id.startswith("article-unresolved:"))
        self.assertNotEqual(edge.to_id, "article:142-2026-ND-CP:13")
        self.assertIn("article:142-2026-ND-CP:13", [n.id for n in graph.nodes])

    def test_unqualified_repeat_in_body_is_not_assumed_to_be_source(self):
        reader = LegalMarkdownReader(cut_depth=4)
        chunks, _ = reader.solve_content(str(ND142), ND142.stem, ND142.read_text(encoding="utf-8"))
        source = next(c for c in chunks if c.name.split(" / ")[-1].startswith("Điều 13."))
        chunk = LegalStructuralSplitter()._invoke(source)[0]
        chunk.content = "Theo Điều 13 nêu trên."
        graph = graph_for(chunk, [{"name": "Điều 13", "category": "Article"},
                                  {"name": "X", "category": "Sanction"}],
                          [["X", "basedOn", "Điều 13"]])
        edge = next(e for e in graph.edges if e.label == "basedOn")
        self.assertTrue(edge.to_id.startswith("article-unresolved:"))

    def test_ner_keeps_same_name_with_different_labels(self):
        extractor = object.__new__(LegalSchemaFreeExtractor)
        extractor.external_graph = None
        extractor.schema = {label: object() for label in ("Article", "LegalTerm", "Others")}
        result = extractor._named_entity_recognition_process("", [
            {"name": "X", "category": "Article"},
            {"name": "X", "category": "LegalTerm"},
            {"name": "X", "category": "Article"},
            {"name": "Y", "category": ["Article"]},
            {"name": "Y", "category": "Invalid"},
        ])
        self.assertEqual([(x["name"], x["category"]) for x in result],
                         [("X", "Article"), ("X", "LegalTerm"), ("Y", "Others")])

    def test_document_variants_and_negative_controls(self):
        self.assertEqual(canon_id("Nghị định số 142/2026/NĐ-CP"),
                         canon_id("Nghị định 142/2026/NĐ-CP"))
        for number in (127, 1528, 1671, 367):
            self.assertEqual(canon_id(f"Quyết định số {number}/QĐ-TTg"),
                             canon_id(f"Quyết định {number}/QĐ-TTg"))
        self.assertNotEqual(canon_id("quyết định số 127 dự án"), canon_id("quyết định 127 qđ ttg"))
        self.assertNotEqual(canon_id("Điều 1 Quyết định số 127/QĐ-TTg"),
                            canon_id("Quyết định 127/QĐ-TTg"))


if __name__ == "__main__":
    unittest.main()
