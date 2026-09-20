# -*- coding: utf-8 -*-
"""B2.2: danh tính ngữ nghĩa theo ngữ cảnh, chạy trên corpus offline thật.

Không LLM, không embedding, không graph write, không DB. Reader + Splitter thật,
entity/triple do test cấp (đứng thay NER) vì NER cần model.

Nguyên tắc kiểm: đủ chứng cứ xác định -> canonical; không đủ -> unresolved.
Một id ``*-unresolved:`` KHÔNG phải bằng chứng rằng chỉ có một occurrence.
"""

import ast
import subprocess
import sys
import unittest
from functools import lru_cache
from pathlib import Path
from types import ModuleType, SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kag"))

from builder.canon_id import (  # noqa: E402
    canon_id,
    normalize_source_phrase,
    semantic_identity,
    source_article_headings,
    source_article_units,
    source_occurrence,
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

# Ca thật cho bất biến câu chữ NER (§E): dòng nguồn NĐ 330 Điều 9 khoản 2 là
# "2. Phạt tiền từ 10.000.000 đồng đến 20.000.000 đồng đối với các hành vi sau
# đây mà chưa đến mức truy cứu trách nhiệm hình sự:". FINE và FINE_LONG là hai
# span dài ngắn khác nhau của CHÍNH dòng đó, không phải văn bản tự bịa.
FINE_LONG = FINE + " đối với các hành vi sau đây"

# Cùng câu chữ nghĩa vụ, hai Điều khác nhau của Luật 116/2025 (Điều 11 và 31).
OBLIGATION_SHARED = (
    "Chủ quản hệ thống thông tin quan trọng về an ninh quốc gia có trách nhiệm "
    "sau đây"
)

# Ca thật cho mơ hồ trùng đơn vị nguồn: hai cụm này nằm trong CÙNG một dòng
# nguồn của Điều 2 Luật 134/2025 (Đối tượng áp dụng).
ENTITY_VN = "cơ quan, tổ chức, cá nhân Việt Nam"
ENTITY_FOREIGN = "tổ chức, cá nhân nước ngoài tham gia vào hoạt động trí tuệ nhân tạo"


def source_path_of(doc_id):
    """Đường dẫn portable như Reader cấp, KHÔNG phải path tuyệt đối."""
    path = next((ROOT / "data/processed").rglob(f"{doc_id}_*.md"))
    return path.relative_to(ROOT).as_posix()


def article_title(doc_id, article_no):
    """Tiêu đề Điều đọc từ file nguồn; B2.1 đòi heading khớp tiêu đề nguồn."""
    titles = [t for n, t in source_article_headings(source_path_of(doc_id))
              if n == article_no]
    assert len(titles) == 1, (doc_id, article_no, titles)
    return titles[0]


# Bản B2.2 core đã review trên GitHub. Hai test bất biến dưới đây phải FAIL với
# bản này, nên nạp thẳng source của nó từ git làm đối chứng phủ định — không
# chép tay lại công thức cũ.
LEGACY_COMMIT = "c159aba"


@lru_cache(maxsize=None)
def legacy_canon_id():
    """`canon_id.py` tại `c159aba`, nạp trong bộ nhớ, không ghi file nào."""
    show = subprocess.run(
        ["git", "show", f"{LEGACY_COMMIT}:kag/builder/canon_id.py"],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
    )
    if show.returncode != 0:
        raise unittest.SkipTest(f"không đọc được {LEGACY_COMMIT}: {show.stderr.strip()}")
    module = ModuleType("canon_id_legacy")
    # __file__ trỏ đúng chỗ cũ vì bản cũ dùng parents[2] để tìm gốc repo.
    module.__file__ = str(ROOT / "kag" / "builder" / "canon_id.py")
    exec(compile(show.stdout, f"{LEGACY_COMMIT}:canon_id.py", "exec"), module.__dict__)
    return module


# Bản đã push lên master, trước khi sửa mơ hồ trùng đơn vị nguồn.
MERGE_COMMIT = "b58e9c0"


@lru_cache(maxsize=None)
def legacy_extractor():
    """`extractor.py` tại `b58e9c0`, nạp trong bộ nhớ, không ghi file nào.

    `canon_id.py` KHÔNG đổi ở lượt này (test dưới đây kiểm lại), nên extractor cũ
    + canon_id hiện tại đúng bằng hành vi của `b58e9c0`. Import tương đối
    `.canon_id` giải theo `__package__ = "builder"` nên trỏ về module thật.
    """
    show = subprocess.run(
        ["git", "show", f"{MERGE_COMMIT}:kag/builder/extractor.py"],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
    )
    if show.returncode != 0:
        raise unittest.SkipTest(f"không đọc được {MERGE_COMMIT}: {show.stderr.strip()}")
    module = ModuleType("builder.extractor_legacy")
    module.__file__ = str(ROOT / "kag" / "builder" / "extractor.py")
    module.__package__ = "builder"
    exec(compile(show.stdout, f"{MERGE_COMMIT}:extractor.py", "exec"), module.__dict__)
    return module


class ZTestNegativeControlIsValid(unittest.TestCase):
    """Đối chứng `b58e9c0` chỉ thật nếu extractor cũ thấy canon_id y như cũ.

    Điều đó KHÔNG đòi canon_id.py không đổi một byte, mà đòi mọi tên top-level
    đã có ở `b58e9c0` còn nguyên từng chữ. Thêm tên MỚI không lọt được vào
    extractor cũ — nó không gọi thứ chưa tồn tại lúc nó được viết — nên phần
    thêm không phá đối chứng. Sửa hay xóa một định nghĩa cũ thì phá, và đó
    đúng là thứ test này chặn.
    """

    def test_definitions_the_legacy_extractor_sees_are_untouched(self):
        show = subprocess.run(
            ["git", "show", f"{MERGE_COMMIT}:kag/builder/canon_id.py"],
            cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(show.returncode, 0, show.stderr)
        current = (ROOT / "kag" / "builder" / "canon_id.py").read_text(encoding="utf-8")

        def top_level_source(source):
            """Tên top-level -> mã nguồn của nó, chuẩn hóa xuống dòng."""
            text = source.replace("\r\n", "\n")
            out = {}
            for node in ast.parse(text).body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    names = [node.name]
                elif isinstance(node, ast.Assign):
                    names = [t.id for t in node.targets if isinstance(t, ast.Name)]
                elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                    names = [node.target.id]
                else:
                    continue
                for name in names:
                    out[name] = ast.get_source_segment(text, node)
            return out

        old, new = top_level_source(show.stdout), top_level_source(current)
        missing = sorted(set(old) - set(new))
        self.assertEqual(missing, [], f"định nghĩa bị xóa: {missing}")
        changed = sorted(name for name, src in old.items() if new[name] != src)
        self.assertEqual(changed, [], f"định nghĩa cũ bị sửa: {changed}")

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
            based = next(e for e in graph.edges if e.label == "basedOn")
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
        self.assertEqual(len([e for e in graph.edges if e.label == "forAct"]), 2)

    def test_money_amount_never_normalized_away(self):
        self.assertIn("10.000.000", normalize_source_phrase(f"2. {FINE}"))
        self.assertEqual(normalize_source_phrase(f"2. {FINE}"), normalize_source_phrase(FINE))
        # Ca thật: NĐ 330 Điều 9 có khoản 1 mức 5-10 triệu và khoản 2 mức 10-20
        # triệu. Hai chế tài khác nhau trong CÙNG một Điều -> hai id.
        source = source_path_of("330-2026-ND-CP")
        lower = "Phạt tiền từ 5.000.000 đồng đến 10.000.000 đồng"
        ids = [
            semantic_identity("Sanction", name, source_path=source, article_no=9)
            for name in (lower, FINE)
        ]
        self.assertTrue(all(i.id for i in ids), ids)
        self.assertNotEqual(ids[0].id, ids[1].id)
        for amount, identity in (("5.000.000", ids[0]), ("20.000.000", ids[1])):
            self.assertIn(amount, identity.material[-1], identity)


class BTestObligationAmbiguous(unittest.TestCase):
    """B — Luật AI 134 Điều 14: cùng câu chữ, hai chủ thể -> unresolved."""

    def test_same_wording_two_subjects_one_article_is_unresolved(self):
        chunk = chunk_with("134-2025-QH15", 14, OBLIGATION)
        self.assertEqual(source_phrase_count(OBLIGATION, chunk.content), 2)
        for subject in ("Nhà cung cấp", "Bên triển khai"):
            self.assertIn(subject.casefold(), chunk.content.casefold())
        identity = semantic_identity(
            "Obligation", OBLIGATION, source_path=source_path_of("134-2025-QH15"),
            article_no=14, clause_no=chunk.kwargs.get("clause_no"),
            point_no=chunk.kwargs.get("point_no"))
        self.assertIsNone(identity.id, identity)
        graph = graph_for(chunk, [{"name": OBLIGATION, "category": "Obligation"}])
        ids = ids_of(graph, "Obligation")
        self.assertEqual(len(ids), 1)
        self.assertTrue(ids[0].startswith("obligation-unresolved:"), ids[0])
        # Một placeholder KHÔNG chứng minh chỉ có một nghĩa vụ: văn bản có 2 lần.

    def test_same_wording_different_article_different_id(self):
        # Ca thật: câu "Chủ quản hệ thống thông tin quan trọng về an ninh quốc
        # gia có trách nhiệm sau đây" nằm ở Điều 11 và Điều 31 Luật 116/2025.
        source = source_path_of("116-2025-QH15")
        ids = {
            no: semantic_identity("Obligation", OBLIGATION_SHARED,
                                  source_path=source, article_no=no).id
            for no in (11, 31)
        }
        self.assertNotIn(None, ids.values(), ids)
        self.assertEqual(len(set(ids.values())), 2, ids)
        for no, identity in ids.items():
            self.assertTrue(identity.startswith(f"obligation:116-2025-QH15:{no}:"), identity)


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
        # Scope đọc từ TIÊU ĐỀ Điều nguồn ("Điều 2. Đối tượng áp dụng"), không
        # lấy heading_path của chunk.
        source = source_path_of("134-2025-QH15")
        resolved = semantic_identity(
            "RegulatedEntity", "cơ quan, tổ chức, cá nhân Việt Nam",
            source_path=source, article_no=2)
        self.assertTrue(str(resolved.id).startswith("regulatedentity:134-2025-QH15:2:"),
                        resolved)
        # "tổ chức, cá nhân" xuất hiện 2 lần trong chính dòng nguồn đó -> mơ hồ.
        ambiguous = semantic_identity(
            "RegulatedEntity", "tổ chức, cá nhân", source_path=source, article_no=2)
        self.assertIsNone(ambiguous.id, ambiguous)

    def test_roles_do_not_merge_on_lexical_overlap(self):
        chunk = chunk_with("134-2025-QH15", 14, OBLIGATION)
        ids = {
            name: semantic_identity("RegulatedEntity", name,
                                    source_path=source_path_of("134-2025-QH15"),
                                    article_no=14).id
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
            for_act = next(e for e in graph.edges if e.label == "forAct")
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

    def test_endpoint_not_listed_as_entity_is_rejected_not_invented(self):
        """B3 đổi hành vi ở đây, có chủ ý.

        Trước B3: đầu mút không có trong entity_list vẫn sinh cạnh, nhãn đầu mút
        đoán bằng ``OTHER_TYPE`` và id dựng tại chỗ. B3 §5 coi đó là thiếu bằng
        chứng nhãn -> KHÔNG sinh cạnh, ghi bằng chứng loại.

        Ý nghĩa regression giữ nguyên: không được dựng bộ danh tính thứ hai, và
        không có đầu mút nào trỏ ra ngoài tập node.
        """
        chunk = chunk_with("330-2026-ND-CP", 9, FINE)
        graph = graph_for(
            chunk,
            [{"name": FINE, "category": "Sanction"}],
            [[FINE, "basedOn", "Điều 9"]],
        )
        self.assertEqual([e for e in graph.edges if e.label == "basedOn"], [])
        node_ids = {node.id for node in graph.nodes}
        for edge in graph.edges:
            self.assertIn(edge.from_id, node_ids, edge.label)
            self.assertIn(edge.to_id, node_ids, edge.label)
        evidence = next(n for n in graph.nodes if n.label == "Chunk").properties["relationEvidence"]
        self.assertEqual([e["rawObject"] for e in evidence], ["Điều 9"])
        self.assertEqual(evidence[0]["status"], "UNRESOLVED_ENDPOINT")


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
        source = source_path_of("330-2026-ND-CP")
        identity = semantic_identity("Sanction", FINE, source_path=source, article_no=9)
        # Material là ĐƠN VỊ NGUỒN, không phải câu chữ NER: dài hơn tên NER.
        self.assertEqual(identity.material[:4], ("Sanction", "330-2026-ND-CP", "9", "k2"))
        unit = identity.material[-1]
        self.assertTrue(unit.startswith(normalize_source_phrase(FINE)), unit)
        self.assertGreater(len(unit), len(normalize_source_phrase(FINE)))
        self.assertEqual(unit, source_occurrence(FINE, source, 9).unit)
        prefix, _, digest = identity.id.rpartition(":")
        self.assertEqual(prefix, "sanction:330-2026-ND-CP:9:k2")
        self.assertEqual(len(digest), 16)
        self.assertTrue(all(ch in "0123456789abcdef" for ch in digest), digest)
        # Dấu đánh mục không phải vật liệu: "2. <tên>" cho cùng id.
        self.assertEqual(
            identity.id,
            semantic_identity("Sanction", f"2. {FINE}", source_path=source,
                              article_no=9).id)


class KTestChunkingInvariance(unittest.TestCase):
    """K — id canonical không đổi khi cấu hình cắt chunk đổi (§A).

    Điểm neo Khoản/Điểm quét từ file nguồn, nên `clause_no`/`point_no` của
    splitter chỉ là hint đối chiếu. Đối chứng: cùng ca này với implementation
    `c159aba` cho HAI id khác nhau.
    """

    def test_clause_metadata_is_a_hint_not_canonical_truth(self):
        source = source_path_of("330-2026-ND-CP")
        loose = semantic_identity("Sanction", FINE, source_path=source, article_no=9,
                                  clause_no=None, point_no=None)
        tight = semantic_identity("Sanction", FINE, source_path=source, article_no=9,
                                  clause_no=2, point_no=None)
        self.assertIsNotNone(loose.id, loose)
        self.assertEqual(loose.id, tight.id)
        # Neo k2 do đọc nguồn, KHÔNG do chunk cấp: splitter để clause_no = None.
        self.assertTrue(loose.id.startswith("sanction:330-2026-ND-CP:9:k2:"), loose.id)
        chunk = chunk_with("330-2026-ND-CP", 9, FINE)
        self.assertIsNone(chunk.kwargs.get("clause_no"), chunk.kwargs)

    def test_hint_mismatch_is_reported_not_baked_into_id(self):
        source = source_path_of("330-2026-ND-CP")
        wrong = semantic_identity("Sanction", FINE, source_path=source, article_no=9,
                                  clause_no=7)
        right = semantic_identity("Sanction", FINE, source_path=source, article_no=9)
        self.assertEqual(wrong.id, right.id)
        self.assertIn("lệch nguồn 2", wrong.reason)

    def test_chunk_content_and_id_do_not_change_canonical_id(self):
        """Chunk hẹp (một khoản) và chunk rộng (cả Điều) cho cùng một id."""
        units = source_article_units(source_path_of("330-2026-ND-CP"), 9)
        narrow = "\n".join(f"2. {u.text}" for u in units if u.clause_no == 2 and not u.point_no)
        wide = "\n".join(u.text for u in units)
        title = article_title("330-2026-ND-CP", 9)
        ids = set()
        for index, content in enumerate((narrow, wide)):
            chunk = fixture_chunk("330-2026-ND-CP", 9, content,
                                  chunk_id=f"chunk-{index}", heading=title)
            chunk.kwargs["clause_no"] = 2 if index == 0 else None
            graph = graph_for(chunk, [{"name": FINE, "category": "Sanction"}])
            ids.update(ids_of(graph, "Sanction"))
        self.assertEqual(len(ids), 1, ids)
        self.assertTrue(next(iter(ids)).startswith("sanction:330-2026-ND-CP:9:k2:"), ids)

    def test_negative_control_legacy_implementation_fails_this(self):
        legacy = legacy_canon_id()
        chunk = chunk_with("330-2026-ND-CP", 9, FINE)
        loose = legacy.semantic_identity("Sanction", FINE, doc_id="330-2026-ND-CP",
                                        article_no=9, content=chunk.content)
        tight = legacy.semantic_identity("Sanction", FINE, doc_id="330-2026-ND-CP",
                                        article_no=9, content=chunk.content, clause_no=2)
        self.assertIsNotNone(loose.id, loose)
        self.assertNotEqual(loose.id, tight.id)


class LTestNerWordingInvariance(unittest.TestCase):
    """L — hai span NER của cùng một đơn vị nguồn cho cùng id (§B).

    Ca thật, không synthetic: dòng nguồn NĐ 330 Điều 9 khoản 2 chứa cả FINE và
    FINE_LONG. Đối chứng: `c159aba` băm câu chữ NER nên cho hai id.
    """

    def test_two_real_spans_of_one_source_unit_share_one_id(self):
        source = source_path_of("330-2026-ND-CP")
        short = semantic_identity("Sanction", FINE, source_path=source, article_no=9)
        long = semantic_identity("Sanction", FINE_LONG, source_path=source, article_no=9)
        self.assertIsNotNone(short.id, short)
        self.assertNotEqual(normalize_source_phrase(FINE), normalize_source_phrase(FINE_LONG))
        self.assertEqual(short.id, long.id)
        self.assertEqual(short.material, long.material)

    def test_both_spans_point_at_the_same_source_unit(self):
        source = source_path_of("330-2026-ND-CP")
        units = {source_occurrence(name, source, 9).unit for name in (FINE, FINE_LONG)}
        self.assertEqual(len(units), 1, units)
        unit = next(iter(units))
        for span in (FINE, FINE_LONG):
            self.assertIn(normalize_source_phrase(span), unit)

    def test_ner_paraphrase_that_is_not_in_source_stays_unresolved(self):
        """Diễn giải lại thì KHÔNG map được: unresolved, không đoán."""
        source = source_path_of("330-2026-ND-CP")
        for paraphrase in ("Phạt tiền 10-20 triệu đồng", "Mức phạt tại khoản 2"):
            identity = semantic_identity("Sanction", paraphrase, source_path=source,
                                         article_no=9)
            self.assertIsNone(identity.id, (paraphrase, identity))
            self.assertIn("cần đúng 1", identity.reason)

    def test_source_occurrence_key_exposes_only_source_facts(self):
        source = source_path_of("330-2026-ND-CP")
        occurrence = source_occurrence(FINE, source, 9)
        self.assertEqual(
            (occurrence.doc_id, occurrence.article_no, occurrence.clause_no,
             occurrence.point_no),
            ("330-2026-ND-CP", 9, 2, None))
        joined = "\x1f".join(str(part) for part in occurrence)
        for leak in ("data/processed", ".md", str(ROOT), "chunk-", "split_index"):
            self.assertNotIn(leak, joined, leak)

    def test_negative_control_legacy_implementation_fails_this(self):
        legacy = legacy_canon_id()
        chunk = chunk_with("330-2026-ND-CP", 9, FINE)
        ids = [
            legacy.semantic_identity("Sanction", name, doc_id="330-2026-ND-CP",
                                     article_no=9, content=chunk.content).id
            for name in (FINE, FINE_LONG)
        ]
        self.assertNotIn(None, ids, ids)
        self.assertNotEqual(ids[0], ids[1])


class MTestSameSourceUnitAmbiguity(unittest.TestCase):
    """M — nhiều tên khác nhau cùng trỏ một đơn vị nguồn -> cả nhóm unresolved.

    Ca thật: Điều 2 Luật 134/2025 (Đối tượng áp dụng) có MỘT dòng nguồn chứa cả
    "cơ quan, tổ chức, cá nhân Việt Nam" và "tổ chức, cá nhân nước ngoài tham
    gia vào hoạt động trí tuệ nhân tạo". Tầng danh tính không có bằng chứng nói
    hai tên này là alias của nhau, cũng không có bằng chứng nói chúng là hai
    nhóm con khác nhau. Đối chứng: `b58e9c` gộp cả hai vào một id canonical.
    """

    def entities(self):
        return [{"name": name, "category": "RegulatedEntity"}
                for name in (ENTITY_VN, ENTITY_FOREIGN)]

    def test_each_name_alone_still_resolves_to_the_same_unit(self):
        """Tiền đề của ca mơ hồ: gọi riêng thì cả hai đều ra CÙNG id canonical."""
        source = source_path_of("134-2025-QH15")
        ids = [semantic_identity("RegulatedEntity", name, source_path=source,
                                 article_no=2)
               for name in (ENTITY_VN, ENTITY_FOREIGN)]
        self.assertTrue(all(i.id for i in ids), ids)
        self.assertEqual(ids[0].id, ids[1].id)
        self.assertTrue(ids[0].id.startswith("regulatedentity:134-2025-QH15:2:"))
        self.assertNotEqual(canon_id(ENTITY_VN), canon_id(ENTITY_FOREIGN))

    def test_two_names_one_unit_are_downgraded_to_unresolved(self):
        chunk = article_chunks("134-2025-QH15", 2)[0]
        graph = graph_for(chunk, self.entities())
        ids = ids_of(graph, "RegulatedEntity")
        self.assertEqual(len(ids), 2, ids)
        self.assertTrue(all(i.startswith("regulatedentity-unresolved:") for i in ids), ids)
        # Hai id unresolved KHÁC nhau vì tên thô khác nhau. Không `_1`/`_2`.
        self.assertEqual(len(set(ids)), 2, ids)
        self.assertEqual(
            set(ids),
            {unresolved_identity("RegulatedEntity", chunk.id, canon_id(name))
             for name in (ENTITY_VN, ENTITY_FOREIGN)})

    def test_canonical_id_disappears_entirely_after_downgrade(self):
        chunk = article_chunks("134-2025-QH15", 2)[0]
        merged = semantic_identity("RegulatedEntity", ENTITY_VN,
                                   source_path=source_path_of("134-2025-QH15"),
                                   article_no=2).id
        graph = graph_for(chunk, self.entities())
        self.assertNotIn(merged, {node.id for node in graph.nodes})

    def test_one_entity_alone_keeps_its_canonical_id(self):
        """Không có tên thứ hai cạnh tranh thì không hạ cấp gì."""
        chunk = article_chunks("134-2025-QH15", 2)[0]
        graph = graph_for(chunk, [{"name": ENTITY_VN, "category": "RegulatedEntity"}])
        ids = ids_of(graph, "RegulatedEntity")
        self.assertEqual(len(ids), 1, ids)
        self.assertTrue(ids[0].startswith("regulatedentity:134-2025-QH15:2:"), ids[0])

    def test_downgrade_flows_into_edge_endpoints(self):
        """§9 — cạnh dùng bản đồ CUỐI, không dùng bản đồ trước khi hạ cấp."""
        chunk = article_chunks("134-2025-QH15", 2)[0]
        graph = graph_for(
            chunk,
            [{"name": "Điều 2", "category": "Article"}] + self.entities(),
            [["Điều 2", "appliesTo", ENTITY_VN],
             ["Điều 2", "appliesTo", ENTITY_FOREIGN]],
        )
        node_ids = {node.id for node in graph.nodes}
        endpoints = set()
        for edge in graph.edges:
            if edge.label != "appliesTo":
                continue
            self.assertIn(edge.from_id, node_ids)
            self.assertIn(edge.to_id, node_ids)
            endpoints.add(edge.to_id)
        self.assertEqual(endpoints, set(ids_of(graph, "RegulatedEntity")))
        self.assertTrue(all(e.startswith("regulatedentity-unresolved:") for e in endpoints),
                        endpoints)

    def test_authority_is_outside_this_rule(self):
        """Authority giữ danh tính tổ chức toàn cục dù chunk có nhóm mơ hồ."""
        chunk = article_chunks("134-2025-QH15", 2)[0]
        graph = graph_for(
            chunk,
            [{"name": "Bộ Công an", "category": "Authority"}] + self.entities(),
        )
        self.assertEqual(ids_of(graph, "Authority"), ["authority:bộ công an"])

    def test_negative_control_legacy_implementation_merges_them(self):
        legacy = legacy_extractor()
        chunk = article_chunks("134-2025-QH15", 2)[0]
        _, _, ids = legacy._endpoint_ids(chunk, self.entities())
        targets = {ids[("RegulatedEntity", canon_id(name))]
                   for name in (ENTITY_VN, ENTITY_FOREIGN)}
        self.assertEqual(len(targets), 1, targets)
        self.assertTrue(next(iter(targets)).startswith("regulatedentity:134-2025-QH15:2:"),
                        targets)


class NTestSimultaneousSpansAreAmbiguous(unittest.TestCase):
    """N — bất biến câu chữ NER không vỡ, nhưng hai span cùng lượt thì mơ hồ.

    `independent resolution != simultaneous ambiguous cardinality`.
    """

    def test_single_span_resolution_is_unchanged(self):
        source = source_path_of("330-2026-ND-CP")
        short = semantic_identity("Sanction", FINE, source_path=source, article_no=9)
        long = semantic_identity("Sanction", FINE_LONG, source_path=source, article_no=9)
        self.assertEqual(short.id, long.id)
        self.assertTrue(short.id.startswith("sanction:330-2026-ND-CP:9:k2:"))

    def test_each_span_alone_in_a_graph_keeps_the_canonical_id(self):
        chunk = chunk_with("330-2026-ND-CP", 9, FINE)
        ids = set()
        for span in (FINE, FINE_LONG):
            graph = graph_for(chunk, [{"name": span, "category": "Sanction"}])
            ids.update(ids_of(graph, "Sanction"))
        self.assertEqual(len(ids), 1, ids)
        self.assertTrue(next(iter(ids)).startswith("sanction:330-2026-ND-CP:9:k2:"), ids)

    def test_both_spans_in_one_extraction_are_unresolved(self):
        chunk = chunk_with("330-2026-ND-CP", 9, FINE)
        graph = graph_for(
            chunk,
            [{"name": FINE, "category": "Sanction"},
             {"name": FINE_LONG, "category": "Sanction"}],
        )
        ids = ids_of(graph, "Sanction")
        self.assertEqual(len(ids), 2, ids)
        self.assertEqual(len(set(ids)), 2, ids)
        self.assertTrue(all(i.startswith("sanction-unresolved:") for i in ids), ids)

    def test_sanction_nine_ten_eleven_unaffected(self):
        """Ca bắt buộc: mỗi Điều một Sanction -> vẫn 3 id canonical."""
        ids = [ids_of(sanction_graph(no)[1], "Sanction")[0] for no in (9, 10, 11)]
        self.assertEqual(len(set(ids)), 3, ids)
        self.assertTrue(all(i.startswith("sanction:330-2026-ND-CP:") for i in ids), ids)


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
