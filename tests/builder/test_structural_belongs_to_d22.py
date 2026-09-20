# -*- coding: utf-8 -*-
"""D2.2: Điều NGUỒN phải biết mình thuộc văn bản nào, không nhờ LLM.

Chạy offline trên corpus thật: Reader + Splitter thật, không LLM, không
embedding, không DB, không Docker. Entity/triple do test cấp khi cần đứng thay
NER.

Defect: 8 Điều canonical không có cạnh ``belongsTo`` nào, dù chunk nguồn của
chúng còn đủ. Nguyên nhân KHÔNG phải mất dữ liệu mà là không có đường code nào
sinh cạnh này — nó chỉ xuất hiện khi HAI điều kiện độc lập cùng xảy ra: LLM
tình cờ khai một triple map về ``belongsTo``, VÀ chủ ngữ của triple đó phân
giải đúng về id Điều nguồn. Điều kiện thứ hai gần như luôn trượt, vì chủ ngữ
trần "Điều N" gặp chính tiêu đề Điều trong thân chunk nên bị coi là dẫn chiếu
và rẽ về bản ``article-unresolved:``.

"Điều này thuộc văn bản nào" là fact CẤU TRÚC: suy từ đường dẫn nguồn +
metadata, không cần suy luận. Nên sinh nó tất định.

Chạy: rtk proxy .venv/Scripts/python.exe -X utf8 -m unittest tests.builder.test_structural_belongs_to_d22 -v
"""

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kag"))

from builder.canon_id import (  # noqa: E402
    canon_id,
    document_node_name,
    source_document_id,
    source_document_name,
)
from builder.extractor import LegalSchemaFreeExtractor  # noqa: E402
from builder.reader import LegalMarkdownReader  # noqa: E402
from builder.splitter import LegalStructuralSplitter  # noqa: E402
from kag.builder.model.chunk import Chunk  # noqa: E402

META_DIR = ROOT / "data" / "metadata"
NODES_FILE = ROOT / "data" / "graph" / "nodes.json"

_LABELS = (
    "Article", "LegalDocument", "Authority", "Sanction", "Obligation",
    "ProhibitedAct", "LegalTerm", "RegulatedEntity", "Others",
)

# 8 Điều canonical thiếu belongsTo trong đồ thị candidate, liệt kê nguyên văn.
MISSING = (
    ("142-2026-ND-CP", 9),
    ("142-2026-ND-CP", 10),
    ("142-2026-ND-CP", 21),
    ("331-2026-ND-CP", 30),
    ("35-2018-QH14", 4),
    ("35-2018-QH14", 10),
    ("35-2018-QH14", 15),
    ("53-2022-ND-CP", 26),
)

# Đối chứng: Điều canonical vốn ĐÃ có belongsTo. Fix không được đụng tới chúng.
ALREADY_FINE = (
    ("330-2026-ND-CP", 9),
    ("116-2025-QH15", 25),
    ("134-2025-QH15", 1),
)


def source_path_of(doc_id):
    path = next((ROOT / "data/processed").rglob(f"{doc_id}_*.md"))
    return path.relative_to(ROOT).as_posix()


def article_chunks(doc_id, article_no):
    """Chunk thật của Điều: Reader -> Splitter, giữ nguyên metadata điều/khoản."""
    path = ROOT / source_path_of(doc_id)
    reader = LegalMarkdownReader(cut_depth=4)
    chunks, _ = reader.solve_content(str(path), path.stem, path.read_text(encoding="utf-8"))
    heads = [c for c in chunks
             if c.name.split(" / ")[-1].startswith(f"Điều {article_no}.")]
    assert heads, (doc_id, article_no)
    # 35-2018-QH14 có Điều được TRÍCH lại trong nội dung sửa đổi nên tiêu đề
    # trùng; Điều nguồn là cái đầu tiên, đúng thứ tự văn bản.
    return LegalStructuralSplitter()._invoke(heads[0])


def graph_for(chunk, entities=None, triples=None):
    extractor = object.__new__(LegalSchemaFreeExtractor)
    extractor.schema = {label: SimpleNamespace(properties={}) for label in _LABELS}
    extractor.external_graph = None
    entities = [dict(item) for item in (entities or [])]
    graph, entities = extractor.assemble_sub_graph_with_spg_records(entities)
    extractor.assemble_sub_graph(graph, chunk, entities, [list(t) for t in (triples or [])])
    return graph


def belongs_to(graph):
    return [e for e in graph.edges if e.label == "belongsTo"]


class DocumentNameIsOneRule(unittest.TestCase):
    """Một văn bản chỉ được có MỘT tên node, dù đi đường nạp nào.

    Nếu extractor tự đặt tên khác với đường metadata thì cùng một văn bản nở ra
    hai node: một node giữ status/ngày hiệu lực, một node giữ cạnh belongsTo,
    không truy vấn nào đi được từ bên này sang bên kia. Đây là chế độ hỏng đắt
    nhất của fix này, nên kiểm trước.
    """

    def test_metadata_path_and_extractor_path_agree_on_every_document(self):
        # Bỏ `_*.json` y như metadata_to_graph.py: `_index.json` là mục lục,
        # không phải metadata của một văn bản.
        metas = [p for p in sorted(META_DIR.glob("*.json"))
                 if not p.name.startswith("_")]
        self.assertGreaterEqual(len(metas), 23)
        for path in metas:
            meta = json.loads(path.read_text(encoding="utf-8"))
            doc_id = meta["doc_id"]
            self.assertEqual(
                source_document_name(doc_id), document_node_name(meta), doc_id
            )

    def test_name_resolves_to_an_id_that_already_exists_in_the_graph(self):
        """id suy ra phải TRÙNG id node LegalDocument đã nạp, không tạo id mới."""
        known = {node["id"] for node in json.loads(NODES_FILE.read_text(encoding="utf-8"))
                 if node["label"] == "LegalDocument"}
        self.assertTrue(known)
        for doc_id, _ in MISSING + ALREADY_FINE:
            name = source_document_name(doc_id)
            self.assertTrue(name, doc_id)
            self.assertIn(canon_id(name), known, doc_id)

    def test_no_metadata_means_no_name(self):
        """Không suy từ tên file, không đoán: không metadata -> None."""
        self.assertIsNone(source_document_name("999-2099-ND-CP"))
        self.assertIsNone(source_document_name(None))
        self.assertIsNone(source_document_name(""))
        self.assertIsNone(source_document_name("../../etc/passwd"))


class EightMissingArticlesAreRestored(unittest.TestCase):
    """8/8 Điều thiếu phải có belongsTo kể cả khi LLM không khai gì."""

    def test_each_missing_article_gets_exactly_one_edge_with_no_llm_triple(self):
        for doc_id, article_no in MISSING:
            expected_article = f"article:{doc_id}:{article_no}"
            expected_doc = canon_id(source_document_name(doc_id))
            with self.subTest(article=expected_article):
                chunks = article_chunks(doc_id, article_no)
                self.assertTrue(chunks)
                for chunk in chunks:
                    graph = graph_for(chunk)  # KHÔNG entity, KHÔNG triple
                    edges = belongs_to(graph)
                    self.assertEqual(len(edges), 1)
                    self.assertEqual(edges[0].from_id, expected_article)
                    self.assertEqual(edges[0].to_id, expected_doc)

    def test_both_endpoints_are_real_nodes_in_the_same_subgraph(self):
        """Đầu mút treo thì writer ghi ra cạnh trỏ vào chỗ không có gì."""
        for doc_id, article_no in MISSING:
            with self.subTest(doc=doc_id, article=article_no):
                graph = graph_for(article_chunks(doc_id, article_no)[0])
                ids = {node.id for node in graph.nodes}
                edge = belongs_to(graph)[0]
                self.assertIn(edge.from_id, ids)
                self.assertIn(edge.to_id, ids)
                doc_node = next(n for n in graph.nodes if n.id == edge.to_id)
                self.assertEqual(doc_node.label, "LegalDocument")
                self.assertEqual(doc_node.name, source_document_name(doc_id))

    def test_edge_is_structural_not_a_model_claim(self):
        """Cạnh cấu trúc: không mang originalPredicate, không tự nhận đã xác minh."""
        for doc_id, article_no in MISSING:
            with self.subTest(doc=doc_id, article=article_no):
                edge = belongs_to(graph_for(article_chunks(doc_id, article_no)[0]))[0]
                props = edge.properties or {}
                self.assertNotIn("originalPredicate", props)
                self.assertNotIn("human_verified", props)
                self.assertEqual(props.get("evidenceStatus"), "STRUCTURAL")
                self.assertNotIn(props.get("evidenceStatus"), ("VERIFIED", "FULL"))

    def test_provenance_points_at_the_source_chunk(self):
        for doc_id, article_no in MISSING:
            with self.subTest(doc=doc_id, article=article_no):
                chunk = article_chunks(doc_id, article_no)[0]
                edge = belongs_to(graph_for(chunk))[0]
                props = edge.properties
                self.assertEqual(props["sourceChunkId"], chunk.id)
                self.assertEqual(props["sourcePath"], source_path_of(doc_id))
                self.assertEqual(props["sourceDocumentId"], doc_id)
                self.assertEqual(props["sourceDocumentId"],
                                 source_document_id(props["sourcePath"]))
                # Tân ngữ là TÊN văn bản, provenance là doc_id — hai thứ khác nhau.
                self.assertNotEqual(props["sourceDocumentId"], edge.to_id)


class ExistingEdgesAreNotDisturbed(unittest.TestCase):
    """Không nhân đôi, không tranh chấp với cạnh LLM đã đúng."""

    def test_llm_edge_on_the_source_article_is_not_duplicated(self):
        """LLM đã khai đúng Điều nguồn -> giữ cạnh của LLM, không thêm cạnh thứ hai."""
        doc_id, article_no = "330-2026-ND-CP", 9
        chunk = article_chunks(doc_id, article_no)[0]
        name = source_document_name(doc_id)
        graph = graph_for(
            chunk,
            [{"name": f"Điều {article_no} Nghị định số 330/2026/NĐ-CP", "category": "Article"},
             {"name": name, "category": "LegalDocument"}],
            [[f"Điều {article_no} Nghị định số 330/2026/NĐ-CP", "thuộc văn bản", name]],
        )
        edges = belongs_to(graph)
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].from_id, f"article:{doc_id}:{article_no}")
        # Cạnh còn lại là của LLM, nên PHẢI mang dấu fact của LLM.
        self.assertIn("originalPredicate", edges[0].properties or {})

    def test_articles_that_already_had_an_edge_still_have_exactly_one(self):
        for doc_id, article_no in ALREADY_FINE:
            with self.subTest(doc=doc_id, article=article_no):
                for chunk in article_chunks(doc_id, article_no):
                    edges = belongs_to(graph_for(chunk))
                    self.assertEqual(len(edges), 1)
                    self.assertEqual(edges[0].from_id, f"article:{doc_id}:{article_no}")

    def test_llm_edge_from_another_subject_does_not_block_the_source_article(self):
        """Cạnh LLM của một Điều KHÁC không được coi là Điều nguồn đã có cạnh."""
        doc_id, article_no = "142-2026-ND-CP", 9
        chunk = article_chunks(doc_id, article_no)[0]
        name = source_document_name(doc_id)
        graph = graph_for(
            chunk,
            [{"name": "Điều 2 Luật 134/2025/QH15", "category": "Article"},
             {"name": name, "category": "LegalDocument"}],
            [["Điều 2 Luật 134/2025/QH15", "thuộc văn bản", name]],
        )
        froms = {e.from_id for e in belongs_to(graph)}
        self.assertIn(f"article:{doc_id}:{article_no}", froms)


class DoesNotGuess(unittest.TestCase):
    """Thiếu căn cứ thì KHÔNG có cạnh, không suy bừa."""

    def test_unresolved_source_article_gets_no_edge(self):
        doc_id = "330-2026-ND-CP"
        chunk = Chunk(
            id="chunk-dieu-khong-co-trong-nguon",
            name=f"{doc_id} / Điều 999. Tiêu đề không có trong nguồn",
            content="nội dung",
            source_path=source_path_of(doc_id),
            heading_path=[doc_id, "Điều 999. Tiêu đề không có trong nguồn"],
            article_no=999,
        )
        self.assertEqual(belongs_to(graph_for(chunk)), [])

    def test_chunk_without_article_number_gets_no_edge(self):
        doc_id = "330-2026-ND-CP"
        chunk = Chunk(
            id="chunk-khong-co-so-dieu",
            name=f"{doc_id} / Phần mở đầu",
            content="Căn cứ Luật Tổ chức Chính phủ;",
            source_path=source_path_of(doc_id),
            heading_path=[doc_id, "Phần mở đầu"],
        )
        self.assertEqual(belongs_to(graph_for(chunk)), [])

    def test_document_outside_the_corpus_gets_no_edge(self):
        """Đường dẫn đúng hình dạng nhưng không có metadata -> không có cạnh."""
        chunk = Chunk(
            id="chunk-ngoai-kho",
            name="unknown / Điều 1. Tiêu đề",
            content="nội dung",
            source_path="data/processed/vn_ai/unknown_van-ban-khong-co-trong-kho.md",
            heading_path=["unknown", "Điều 1. Tiêu đề"],
            article_no=1,
        )
        self.assertIsNone(source_document_id(chunk.kwargs["source_path"]))
        self.assertEqual(belongs_to(graph_for(chunk)), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
