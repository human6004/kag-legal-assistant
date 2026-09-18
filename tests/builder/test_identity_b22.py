# -*- coding: utf-8 -*-
"""B2.2: danh tính ngữ nghĩa theo ngữ cảnh, chạy trên corpus offline thật.

Không LLM, không embedding, không graph write, không DB. Reader + Splitter thật,
entity/triple do test cấp (đứng thay NER) vì NER cần model.

Nguyên tắc kiểm: đủ chứng cứ xác định -> canonical; không đủ -> unresolved.
Một id ``*-unresolved:`` KHÔNG phải bằng chứng rằng chỉ có một occurrence.
"""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kag"))

from builder.canon_id import (  # noqa: E402
    canon_id,
    normalize_source_phrase,
    semantic_identity,
    source_phrase_count,
    unresolved_identity,
)
from builder.extractor import LegalSchemaFreeExtractor  # noqa: E402
from builder.reader import LegalMarkdownReader  # noqa: E402
from builder.splitter import LegalStructuralSplitter  # noqa: E402
from kag.builder.model.chunk import Chunk  # noqa: E402

FINE = "Phạt tiền từ 10.000.000 đồng đến 20.000.000 đồng"
ACT = (
    "Tổ chức, hoạt động, câu kết, xúi giục, mua chuộc, lừa gạt, lôi kéo, đào tạo, "
    "huấn luyện người chống Nhà nước Cộng hòa xã hội chủ nghĩa Việt Nam"
)
OBLIGATION = (
    "Thực hiện nghĩa vụ minh bạch và xử lý sự cố theo quy định tại Điều 11 và "
    "Điều 12 của Luật này"
)
TERM = "An ninh mạng"

_LABELS = (
    "Article", "LegalDocument", "Authority", "Sanction", "Obligation",
    "ProhibitedAct", "LegalTerm", "RegulatedEntity", "Others",
)


def article_chunks(doc_id, article_no):
    """Chunk thật: Reader -> Splitter, giữ nguyên metadata điều/khoản/điểm."""
    path = next((ROOT / "data/processed").rglob(f"{doc_id}_*.md"))
    reader = LegalMarkdownReader(cut_depth=4)
    chunks, _ = reader.solve_content(str(path), path.stem, path.read_text(encoding="utf-8"))
    source = next(c for c in chunks
                  if c.name.split(" / ")[-1].startswith(f"Điều {article_no}."))
    return LegalStructuralSplitter()._invoke(source)


def chunk_with(doc_id, article_no, phrase):
    """Chunk duy nhất của Điều có chứa đúng ``phrase``."""
    hits = [c for c in article_chunks(doc_id, article_no)
            if source_phrase_count(phrase, c.content)]
    assert len(hits) == 1, (doc_id, article_no, len(hits))
    return hits[0]


def fixture_chunk(doc_id, article_no, content, chunk_id=None, heading=None):
    return Chunk(
        id=chunk_id or f"chunk-{doc_id}-{article_no}",
        name=f"{doc_id} / Điều {article_no}. Tiêu đề",
        content=content,
        source_path=next((ROOT / "data/processed").rglob(f"{doc_id}_*.md"))
        .relative_to(ROOT).as_posix(),
        heading_path=[doc_id, heading or f"Điều {article_no}. Tiêu đề"],
        article_no=article_no,
    )


def graph_for(chunk, entities=None, triples=None, official=None):
    extractor = object.__new__(LegalSchemaFreeExtractor)
    extractor.schema = {label: SimpleNamespace(properties={}) for label in _LABELS}
    extractor.external_graph = None
    entities = [dict(item) for item in (entities or [])]
    graph, entities = extractor.assemble_sub_graph_with_spg_records(entities)
    if official:
        extractor.append_official_name(entities, official)
    extractor.assemble_sub_graph(graph, chunk, entities, [list(t) for t in (triples or [])])
    return graph


def ids_of(graph, label):
    return [node.id for node in graph.nodes if node.label == label]


def semantic_edges(graph):
    return [e for e in graph.edges if e.label not in ("source", "OfficialName")]


def sanction_graph(article_no):
    """Một Điều của NĐ 330: Điều -imposes-> Chế tài -forAct-> Hành vi."""
    chunk = chunk_with("330-2026-ND-CP", article_no, FINE)
    act = f"hành vi bị xử phạt tại Điều {article_no}"
    return chunk, graph_for(
        chunk,
        [{"name": f"Điều {article_no}", "category": "Article"},
         {"name": FINE, "category": "Sanction"},
         {"name": act, "category": "ProhibitedAct"}],
        [[f"Điều {article_no}", "imposes", FINE],
         [FINE, "basedOn", f"Điều {article_no}"],
         [FINE, "forAct", act]],
    )


class ATestSanctionOccurrence(unittest.TestCase):
    """A — 3 Điều cùng câu chữ tiền phạt -> 3 id, 0 cặp chéo."""

    def test_three_articles_same_fine_three_ids(self):
        sanctions, pairs = {}, set()
        for article_no in (9, 10, 11):
            _, graph = sanction_graph(article_no)
            ids = ids_of(graph, "Sanction")
            self.assertEqual(len(ids), 1, ids)
            self.assertTrue(ids[0].startswith(f"sanction:330-2026-ND-CP:{article_no}:"))
            sanctions[article_no] = ids[0]
            based = next(e for e in graph.edges if e.label == "basedon")
            pairs.add((based.from_id, based.to_id))
        self.assertEqual(len(set(sanctions.values())), 3, sanctions)
        # 0 cặp chéo: mỗi chế tài chỉ nối về đúng Điều của nó.
        for article_no, sanction_id in sanctions.items():
            self.assertIn((sanction_id, f"article:330-2026-ND-CP:{article_no}"), pairs)
        self.assertEqual(len(pairs), 3)
        cross = {(s, a) for s in sanctions.values() for a in (9, 10, 11)
                 if not s.startswith(f"sanction:330-2026-ND-CP:{a}:")
                 and (s, f"article:330-2026-ND-CP:{a}") in pairs}
        self.assertEqual(cross, set())

    def test_one_sanction_many_acts_stays_one_occurrence(self):
        chunk = chunk_with("330-2026-ND-CP", 9, FINE)
        acts = ["hành vi A tại Điều 9", "hành vi B tại Điều 9"]
        graph = graph_for(
            chunk,
            [{"name": FINE, "category": "Sanction"}]
            + [{"name": a, "category": "ProhibitedAct"} for a in acts],
            [[FINE, "forAct", a] for a in acts],
        )
        self.assertEqual(len(set(ids_of(graph, "Sanction"))), 1)
        self.assertEqual(len([e for e in graph.edges if e.label == "foract"]), 2)

    def test_money_amount_never_normalized_away(self):
        self.assertIn("10.000.000", normalize_source_phrase(f"2. {FINE}"))
        self.assertEqual(normalize_source_phrase(f"2. {FINE}"), normalize_source_phrase(FINE))
        other = FINE.replace("20.000.000", "30.000.000")
        chunk = chunk_with("330-2026-ND-CP", 9, FINE)
        self.assertNotEqual(
            semantic_identity("Sanction", FINE, doc_id="330-2026-ND-CP",
                              article_no=9, content=chunk.content).id,
            semantic_identity("Sanction", other, doc_id="330-2026-ND-CP",
                              article_no=9, content=f"{chunk.content}\n{other}").id,
        )


class BTestObligationAmbiguous(unittest.TestCase):
    """B — Luật AI 134 Điều 14: cùng câu chữ, hai chủ thể -> unresolved."""

    def test_same_wording_two_subjects_one_article_is_unresolved(self):
        chunk = chunk_with("134-2025-QH15", 14, OBLIGATION)
        self.assertEqual(source_phrase_count(OBLIGATION, chunk.content), 2)
        for subject in ("Nhà cung cấp", "Bên triển khai"):
            self.assertIn(subject.casefold(), chunk.content.casefold())
        identity = semantic_identity(
            "Obligation", OBLIGATION, doc_id="134-2025-QH15", article_no=14,
            content=chunk.content, clause_no=chunk.kwargs.get("clause_no"),
            point_no=chunk.kwargs.get("point_no"))
        self.assertIsNone(identity.id, identity)
        graph = graph_for(chunk, [{"name": OBLIGATION, "category": "Obligation"}])
        ids = ids_of(graph, "Obligation")
        self.assertEqual(len(ids), 1)
        self.assertTrue(ids[0].startswith("obligation-unresolved:"), ids[0])
        # Một placeholder KHÔNG chứng minh chỉ có một nghĩa vụ: văn bản có 2 lần.

    def test_same_wording_different_article_different_id(self):
        content = f"1. {OBLIGATION}."
        ids = {
            semantic_identity("Obligation", OBLIGATION, doc_id="134-2025-QH15",
                              article_no=no, content=content).id
            for no in (11, 12)
        }
        self.assertEqual(len(ids), 2, ids)
        self.assertNotIn(None, ids)


class CTestProhibitedActByBasis(unittest.TestCase):
    """C — Luật 24/2018 vs Luật 116/2025: cùng câu chữ, khác căn cứ -> khác id."""

    def test_old_and_new_law_do_not_merge(self):
        ids = []
        for doc_id, article_no in (("24-2018-QH14", 8), ("116-2025-QH15", 7)):
            chunk = chunk_with(doc_id, article_no, ACT)
            graph = graph_for(
                chunk,
                [{"name": f"Điều {article_no}", "category": "Article"},
                 {"name": ACT, "category": "ProhibitedAct"}],
                [[f"Điều {article_no}", "prohibits", ACT]],
            )
            node_ids = ids_of(graph, "ProhibitedAct")
            self.assertEqual(len(node_ids), 1)
            self.assertTrue(node_ids[0].startswith(f"prohibitedact:{doc_id}:{article_no}"),
                            node_ids[0])
            ids.append(node_ids[0])
        self.assertNotEqual(ids[0], ids[1])
        self.assertEqual(normalize_source_phrase(ACT), normalize_source_phrase(ACT))


class DTestAuthorityGlobal(unittest.TestCase):
    """D — Authority là danh tính tổ chức toàn cục, có đối chứng phủ định."""

    def test_same_authority_across_documents(self):
        ids = set()
        for doc_id, article_no in (("24-2018-QH14", 8), ("116-2025-QH15", 7)):
            chunk = article_chunks(doc_id, article_no)[0]
            graph = graph_for(chunk, [{"name": "Bộ Công an", "category": "Authority"}])
            ids.update(ids_of(graph, "Authority"))
        self.assertEqual(ids, {"authority:bộ công an"})

    def test_case_and_spacing_do_not_split_authority(self):
        for variant in ("BỘ CÔNG AN", "bộ  công  an", " Bộ Công An "):
            self.assertEqual(semantic_identity("Authority", variant).id,
                             "authority:bộ công an")

    def test_negative_controls_never_merge_into_authority(self):
        for name in ("Bộ trưởng Bộ Công an", "Cục An ninh mạng thuộc Bộ Công an",
                     "Thanh tra Bộ Công an", "cơ quan có thẩm quyền",
                     "Ủy ban nhân dân", "người có thẩm quyền"):
            identity = semantic_identity("Authority", name)
            self.assertIsNone(identity.id, (name, identity))
            unresolved = unresolved_identity("Authority", "chunk-x", name)
            self.assertTrue(unresolved.startswith("authority-unresolved:"))
            self.assertNotEqual(unresolved, "authority:bộ công an")

    def test_official_name_alone_never_merges_an_alias(self):
        chunk = article_chunks("24-2018-QH14", 8)[0]
        alias = "Cục An ninh mạng thuộc Bộ Công an"
        graph = graph_for(
            chunk,
            [{"name": alias, "category": "Authority"}],
            official=[{"name": alias, "category": "Authority",
                       "official_name": "Bộ Công an"}],
        )
        self.assertNotIn("authority:bộ công an", ids_of(graph, "Authority"))


class ETestLegalTermDefinitionScope(unittest.TestCase):
    """E — LegalTerm gắn vào ngữ cảnh định nghĩa, không toàn cục theo tên."""

    def test_two_definitions_two_identities(self):
        ids = []
        for doc_id in ("24-2018-QH14", "116-2025-QH15"):
            chunk = next(c for c in article_chunks(doc_id, 2)
                         if f"{TERM.casefold()} là" in c.content.casefold())
            graph = graph_for(
                chunk,
                [{"name": "Điều 2", "category": "Article"},
                 {"name": TERM, "category": "LegalTerm"}],
                [["Điều 2", "defines", TERM]],
            )
            node_ids = ids_of(graph, "LegalTerm")
            self.assertEqual(len(node_ids), 1)
            self.assertTrue(node_ids[0].startswith(f"legalterm:{doc_id}:2"), node_ids[0])
            ids.append(node_ids[0])
        self.assertNotEqual(ids[0], ids[1])

    def test_mention_without_definition_is_unresolved(self):
        chunk = article_chunks("24-2018-QH14", 8)[0]
        self.assertIn(TERM.casefold(), chunk.content.casefold())
        graph = graph_for(chunk, [{"name": TERM, "category": "LegalTerm"}])
        ids = ids_of(graph, "LegalTerm")
        self.assertEqual(len(ids), 1)
        self.assertTrue(ids[0].startswith("legalterm-unresolved:"), ids[0])


class FTestRegulatedEntityScope(unittest.TestCase):
    """F — RegulatedEntity là lớp/vai trò có scope, không gộp toàn corpus."""

    def test_generic_name_never_merges_across_documents(self):
        ids = set()
        for doc_id, article_no in (("134-2025-QH15", 2), ("116-2025-QH15", 1)):
            chunk = article_chunks(doc_id, article_no)[0]
            graph = graph_for(chunk, [{"name": "tổ chức, cá nhân",
                                       "category": "RegulatedEntity"}])
            ids.update(ids_of(graph, "RegulatedEntity"))
        self.assertEqual(len(ids), 2, ids)
        self.assertFalse(any(i.startswith("regulatedentity:") for i in ids), ids)

    def test_scope_article_resolves_but_ambiguous_name_does_not(self):
        chunk = article_chunks("134-2025-QH15", 2)[0]
        heading = " / ".join(chunk.kwargs.get("heading_path") or [])
        self.assertIn("đối tượng áp dụng", heading.casefold())
        resolved = semantic_identity(
            "RegulatedEntity", "cơ quan, tổ chức, cá nhân Việt Nam",
            doc_id="134-2025-QH15", article_no=2, heading=heading, content=chunk.content)
        self.assertTrue(str(resolved.id).startswith("regulatedentity:134-2025-QH15:2:"),
                        resolved)
        ambiguous = semantic_identity(
            "RegulatedEntity", "tổ chức, cá nhân", doc_id="134-2025-QH15",
            article_no=2, heading=heading, content=chunk.content)
        self.assertIsNone(ambiguous.id, ambiguous)

    def test_roles_do_not_merge_on_lexical_overlap(self):
        chunk = chunk_with("134-2025-QH15", 14, OBLIGATION)
        ids = {
            name: semantic_identity("RegulatedEntity", name, doc_id="134-2025-QH15",
                                    article_no=14, heading="Điều 14. Quản lý",
                                    content=chunk.content).id
            for name in ("nhà cung cấp", "bên triển khai", "tổ chức, cá nhân")
        }
        self.assertEqual(set(ids.values()), {None}, ids)
        unresolved = {name: unresolved_identity("RegulatedEntity", chunk.id, name)
                      for name in ids}
        self.assertEqual(len(set(unresolved.values())), 3, unresolved)


class GTestNodeEndpointConsistency(unittest.TestCase):
    """G — mọi node B2.2 đã phân giải: node.id == id đầu mút cạnh ngữ nghĩa."""

    def test_every_semantic_endpoint_matches_a_node(self):
        for article_no in (9, 10, 11):
            _, graph = sanction_graph(article_no)
            node_ids = {node.id for node in graph.nodes}
            for edge in semantic_edges(graph):
                self.assertIn(edge.from_id, node_ids, edge.label)
                self.assertIn(edge.to_id, node_ids, edge.label)
            sanction_id = ids_of(graph, "Sanction")[0]
            imposes = next(e for e in graph.edges if e.label == "imposes")
            for_act = next(e for e in graph.edges if e.label == "foract")
            self.assertEqual(imposes.to_id, sanction_id)
            self.assertEqual(for_act.from_id, sanction_id)
            self.assertEqual(imposes.from_id, f"article:330-2026-ND-CP:{article_no}")

    def test_unresolved_endpoint_also_gets_a_node(self):
        chunk = chunk_with("134-2025-QH15", 14, OBLIGATION)
        graph = graph_for(
            chunk,
            [{"name": "Điều 14", "category": "Article"},
             {"name": OBLIGATION, "category": "Obligation"}],
            [["Điều 14", "obliges", OBLIGATION]],
        )
        edge = next(e for e in graph.edges if e.label == "obliges")
        self.assertTrue(edge.to_id.startswith("obligation-unresolved:"), edge.to_id)
        self.assertIn(edge.to_id, ids_of(graph, "Obligation"))

    def test_endpoint_not_listed_as_entity_still_resolves_to_one_node(self):
        chunk = chunk_with("330-2026-ND-CP", 9, FINE)
        graph = graph_for(
            chunk,
            [{"name": FINE, "category": "Sanction"}],
            [[FINE, "basedOn", "Điều 9"]],
        )
        edge = next(e for e in graph.edges if e.label == "basedon")
        self.assertEqual(edge.from_id, ids_of(graph, "Sanction")[0])
        self.assertIn(edge.to_id, {node.id for node in graph.nodes})


class HTestOfficialNameNoCompetingIdentity(unittest.TestCase):
    """H — official_name chỉ để hiển thị/alias, không sinh danh tính cạnh tranh."""

    def test_official_name_creates_no_second_node(self):
        chunk = chunk_with("330-2026-ND-CP", 9, FINE)
        official = [{"name": FINE, "category": "Sanction",
                     "official_name": "Phạt tiền 10-20 triệu đồng"}]
        graph = graph_for(
            chunk,
            [{"name": FINE, "category": "Sanction"}],
            [[FINE, "basedOn", "Điều 9"]],
            official=official,
        )
        ids = ids_of(graph, "Sanction")
        self.assertEqual(len(ids), 1, ids)
        self.assertTrue(ids[0].startswith("sanction:330-2026-ND-CP:9:"))
        self.assertFalse(any(e.label == "OfficialName" for e in graph.edges))
        self.assertNotIn(canon_id("Phạt tiền 10-20 triệu đồng"),
                         {node.id for node in graph.nodes})

    def test_official_name_does_not_change_resolved_id(self):
        chunk = chunk_with("330-2026-ND-CP", 9, FINE)
        plain = graph_for(chunk, [{"name": FINE, "category": "Sanction"}])
        with_official = graph_for(
            chunk, [{"name": FINE, "category": "Sanction"}],
            official=[{"name": FINE, "category": "Sanction",
                       "official_name": "Mức phạt tại khoản 2"}])
        self.assertEqual(ids_of(plain, "Sanction"), ids_of(with_official, "Sanction"))


class ITestStableIdentity(unittest.TestCase):
    """I — chạy lại trên input cố định: id canonical không đổi."""

    def test_rerun_gives_identical_canonical_ids(self):
        first = [ids_of(sanction_graph(no)[1], "Sanction")[0] for no in (9, 10, 11)]
        second = [ids_of(sanction_graph(no)[1], "Sanction")[0] for no in (9, 10, 11)]
        self.assertEqual(first, second)
        self.assertEqual(len(set(first)), 3)

    def test_canonical_id_has_no_chunk_id_and_no_path(self):
        chunk, graph = sanction_graph(9)
        sanction_id = ids_of(graph, "Sanction")[0]
        self.assertNotIn(chunk.id, sanction_id)
        self.assertNotIn("data/processed", sanction_id)
        self.assertNotIn(":\\", sanction_id)
        self.assertNotIn("/", sanction_id)

    def test_identity_material_is_inspectable_and_hash_free(self):
        chunk = chunk_with("330-2026-ND-CP", 9, FINE)
        identity = semantic_identity("Sanction", FINE, doc_id="330-2026-ND-CP",
                                     article_no=9, content=chunk.content)
        self.assertEqual(identity.material[:3], ("Sanction", "330-2026-ND-CP", "9"))
        self.assertEqual(identity.material[-1], normalize_source_phrase(FINE))
        prefix, _, digest = identity.id.rpartition(":")
        self.assertEqual(prefix, "sanction:330-2026-ND-CP:9")
        self.assertEqual(len(digest), 16)
        self.assertTrue(all(ch in "0123456789abcdef" for ch in digest), digest)
        # Chữ liệu tái lập được id: hash không che mất vật liệu để debug.
        self.assertEqual(
            identity.id,
            semantic_identity("Sanction", f"2. {FINE}", doc_id="330-2026-ND-CP",
                              article_no=9, content=chunk.content).id)


class JTestUnresolvedContract(unittest.TestCase):
    """J — unresolved ổn định trong cùng input, không gộp qua chunk khác."""

    def test_same_ambiguous_input_gives_same_unresolved_id(self):
        chunk = chunk_with("134-2025-QH15", 14, OBLIGATION)
        entities = [{"name": OBLIGATION, "category": "Obligation"}]
        first = ids_of(graph_for(chunk, entities), "Obligation")
        second = ids_of(graph_for(chunk, entities), "Obligation")
        self.assertEqual(first, second)
        self.assertTrue(first[0].startswith("obligation-unresolved:"))

    def test_different_chunk_never_merges_unresolved(self):
        content = f"a) {OBLIGATION};\nb) {OBLIGATION};"
        left = fixture_chunk("134-2025-QH15", 14, content, chunk_id="chunk-left")
        right = fixture_chunk("134-2025-QH15", 14, content, chunk_id="chunk-right")
        entities = [{"name": OBLIGATION, "category": "Obligation"}]
        left_id = ids_of(graph_for(left, entities), "Obligation")[0]
        right_id = ids_of(graph_for(right, entities), "Obligation")[0]
        self.assertTrue(left_id.startswith("obligation-unresolved:"))
        self.assertNotEqual(left_id, right_id)

    def test_every_type_has_its_own_unresolved_namespace(self):
        expected = {
            "Sanction": "sanction-unresolved:",
            "Obligation": "obligation-unresolved:",
            "ProhibitedAct": "prohibitedact-unresolved:",
            "LegalTerm": "legalterm-unresolved:",
            "RegulatedEntity": "regulatedentity-unresolved:",
            "Authority": "authority-unresolved:",
        }
        for category, prefix in expected.items():
            self.assertTrue(
                unresolved_identity(category, "chunk-x", "X").startswith(prefix))
        self.assertEqual(len({unresolved_identity(c, "chunk-x", "X")
                              for c in expected}), len(expected))

    def test_no_canonical_id_when_legal_basis_unresolved(self):
        chunk = fixture_chunk("134-2025-QH15", 14, f"1. {OBLIGATION}.")
        chunk.kwargs["article_no"] = None
        graph = graph_for(chunk, [{"name": OBLIGATION, "category": "Obligation"}])
        self.assertTrue(ids_of(graph, "Obligation")[0].startswith("obligation-unresolved:"))


if __name__ == "__main__":
    unittest.main()
