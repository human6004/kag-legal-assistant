# -*- coding: utf-8 -*-
"""B3: quan hệ chuẩn và nguồn trích xuất, chạy offline trên corpus thật.

Không LLM, không embedding, không graph write, không DB, không Docker. Reader +
Splitter thật; entity/triple do test cấp (đứng thay NER) vì NER cần model.

Bất biến trung tâm: vị ngữ thô KHÔNG quyết định nhãn quan hệ. Đường đi là
``vị ngữ thô -> map tất định -> quan hệ canonical -> kiểm tuple hợp đồng ->
thêm cạnh``. Trượt bất kỳ bước nào thì KHÔNG có cạnh, và triple bị loại để lại
bằng chứng có cấu trúc trong property ``relationEvidence`` của Chunk.

Hợp đồng kiểm TUPLE ``(kiểu chủ ngữ, quan hệ, kiểu tân ngữ)``, không chỉ kiểm
tên quan hệ: ``basedOn`` hợp lệ cho Sanction và Obligation, không hợp lệ cho
Authority. Hai chiều cùng tồn tại được nếu schema khai cả hai, nhưng KHÔNG bao
giờ tự sinh chiều ngược.

Chạy: rtk proxy .venv/Scripts/python.exe -X utf8 -m unittest tests.builder.test_relation_b3 -v
"""

import json
import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kag"))

from builder.canon_id import canon_id, source_document_id  # noqa: E402
from builder.extractor import (  # noqa: E402
    AMBIGUOUS_BINDING,
    CANONICAL_RELATIONS,
    INVALID_ENDPOINT_TYPES,
    RELATION_ALIASES,
    RELATION_CONTRACT,
    RELATION_MAPPING_VERSION,
    UNKNOWN_PREDICATE,
    UNRESOLVED_ENDPOINT,
    LegalSchemaFreeExtractor,
)
from builder.reader import LegalMarkdownReader  # noqa: E402
from builder.splitter import LegalStructuralSplitter  # noqa: E402
from kag.builder.component.writer.kg_writer import KGWriter  # noqa: E402
from kag.builder.model.sub_graph import SubGraph  # noqa: E402

SCHEMA_FILE = ROOT / "kag" / "schema" / "Legal.schema"
EDGES_FILE = ROOT / "data" / "graph" / "edges.json"

_LABELS = (
    "Article", "LegalDocument", "Authority", "Sanction", "Obligation",
    "ProhibitedAct", "LegalTerm", "RegulatedEntity", "Others",
)

# Một entity cho mỗi kiểu trong hợp đồng: nhãn đầu mút lấy từ NER, nên ca nào
# cũng phải cấp entity, không thì triple bị loại vì thiếu bằng chứng nhãn.
ENTITIES = [
    {"name": "Điều 1", "category": "Article"},
    {"name": "Điều 2", "category": "Article"},
    {"name": "Nghị định 1", "category": "LegalDocument"},
    {"name": "Luật 2", "category": "LegalDocument"},
    {"name": "Hành vi", "category": "ProhibitedAct"},
    {"name": "Phạt tiền", "category": "Sanction"},
    {"name": "Nghĩa vụ", "category": "Obligation"},
    {"name": "Thuật ngữ", "category": "LegalTerm"},
    {"name": "Đối tượng", "category": "RegulatedEntity"},
    {"name": "Bộ Công an", "category": "Authority"},
]

NAME_OF_TYPE = {
    "Article": "Điều 1",
    "LegalDocument": "Nghị định 1",
    "ProhibitedAct": "Hành vi",
    "Sanction": "Phạt tiền",
    "Obligation": "Nghĩa vụ",
    "LegalTerm": "Thuật ngữ",
    "RegulatedEntity": "Đối tượng",
    "Authority": "Bộ Công an",
}


def schema_tuples():
    """(source, relation, target) đọc TRỰC TIẾP từ Legal.schema.

    Nguồn sự thật của hợp đồng là schema. Test này tồn tại để code và schema
    không trôi khỏi nhau: bảng cứng trong extractor chỉ được phép là bản sao.
    """
    text = SCHEMA_FILE.read_text(encoding="utf-8")
    found = set()
    for block in re.split(r"^(?=\S)", text, flags=re.M):
        head = re.match(r"^(\w+)\(", block)
        if not head or "relations:" not in block:
            continue
        tail = block.split("relations:", 1)[1]
        for relation, target in re.findall(r"^\s{8}(\w+)\([^)]*\):\s*(\w+)\s*$", tail, re.M):
            found.add((head.group(1), relation, target))
    return found


def relations(triples, entities=None, endpoint_ids=None, provenance=None):
    """Gọi thẳng đường dựng cạnh. Trả (sub_graph, evidence)."""
    sg = SubGraph(nodes=[], edges=[])
    evidence = []
    LegalSchemaFreeExtractor.assemble_sub_graph_with_triples(
        sg,
        ENTITIES if entities is None else entities,
        [list(t) for t in triples],
        endpoint_ids=endpoint_ids,
        chunk_id="chunk-test",
        provenance=provenance,
        evidence=evidence,
    )
    return sg, evidence


def semantic(sg):
    return [e for e in sg.edges if e.label not in ("source", "OfficialName")]


def labels(sg):
    return [e.label for e in semantic(sg)]


# ---------------------------------------------------------------- pipeline thật


def source_path_of(doc_id):
    """Đường dẫn portable như Reader cấp, KHÔNG phải path tuyệt đối."""
    path = next((ROOT / "data/processed").rglob(f"{doc_id}_*.md"))
    return path.relative_to(ROOT).as_posix()


def article_chunks(doc_id, article_no):
    path = ROOT / source_path_of(doc_id)
    reader = LegalMarkdownReader(cut_depth=4)
    chunks, _ = reader.solve_content(str(path), path.stem, path.read_text(encoding="utf-8"))
    source = next(c for c in chunks
                  if c.name.split(" / ")[-1].startswith(f"Điều {article_no}."))
    return LegalStructuralSplitter()._invoke(source)


def graph_for(chunk, entities=None, triples=None):
    extractor = object.__new__(LegalSchemaFreeExtractor)
    extractor.schema = {label: SimpleNamespace(properties={}) for label in _LABELS}
    extractor.external_graph = None
    entities = [dict(item) for item in (entities or [])]
    graph, entities = extractor.assemble_sub_graph_with_spg_records(entities)
    extractor.assemble_sub_graph(graph, chunk, entities, [list(t) for t in (triples or [])])
    return graph


def chunk_node(graph):
    return next(n for n in graph.nodes if n.label == "Chunk")


FINE = "Phạt tiền từ 10.000.000 đồng đến 20.000.000 đồng"
ACT = "hành vi bị xử phạt tại Điều 9"


def nd330_article_9():
    """Chunk thật của NĐ 330 Điều 9 có chứa câu tiền phạt."""
    hits = [c for c in article_chunks("330-2026-ND-CP", 9) if FINE in c.content]
    assert len(hits) == 1, len(hits)
    return hits[0]


def sanction_case(chunk):
    """Điều -imposes-> Chế tài -basedOn-> Điều, kèm một triple bị loại."""
    entities = [
        {"name": "Điều 9", "category": "Article"},
        {"name": FINE, "category": "Sanction"},
        {"name": ACT, "category": "ProhibitedAct"},
        {"name": "Bộ Công an", "category": "Authority"},
    ]
    triples = [
        ["Điều 9", "quy định chế tài", FINE],
        [FINE, "căn cứ pháp lý", "Điều 9"],
        [FINE, "forAct", ACT],
        # Bị loại: hai đầu mút phân giải được, tên quan hệ map được, nhưng
        # Authority không có basedOn trong hợp đồng -> phải để lại bằng chứng,
        # không drop im lặng, không tự đổi sang quan hệ khác.
        ["Bộ Công an", "căn cứ pháp lý", "Điều 9"],
    ]
    return graph_for(chunk, entities, triples)


# ------------------------------------------------------------------- A: hợp đồng


class ATestContractMatchesSchema(unittest.TestCase):
    """A — bảng cứng trong code == tuple parse từ Legal.schema."""

    def test_eighteen_tuples_seventeen_names(self):
        self.assertEqual(len(RELATION_CONTRACT), 18)
        self.assertEqual(len(CANONICAL_RELATIONS), 17)

    def test_contract_equals_schema(self):
        self.assertEqual(set(RELATION_CONTRACT), schema_tuples())

    def test_no_relation_outside_schema_names(self):
        self.assertEqual(
            CANONICAL_RELATIONS,
            frozenset(relation for _, relation, _ in schema_tuples()),
        )

    def test_basedon_is_the_only_shared_name(self):
        """Tên dùng cho nhiều cặp kiểu -> chứng minh phải kiểm TUPLE."""
        by_name = {}
        for source, relation, target in RELATION_CONTRACT:
            by_name.setdefault(relation, set()).add((source, target))
        shared = {name for name, pairs in by_name.items() if len(pairs) > 1}
        self.assertEqual(shared, {"basedOn"})
        self.assertEqual(
            by_name["basedOn"], {("Sanction", "Article"), ("Obligation", "Article")}
        )


# ----------------------------------------------------- B, C: map vị ngữ thô


class BTestVietnameseAliases(unittest.TestCase):
    """B — 13 vị ngữ prompt từng ưu tiên, map đúng khi kiểu hai đầu đúng."""

    PREFERRED = {
        "thuộc văn bản": ("Article", "belongsTo", "LegalDocument"),
        "nghiêm cấm": ("Article", "prohibits", "ProhibitedAct"),
        "quy định chế tài": ("Article", "imposes", "Sanction"),
        "quy định nghĩa vụ": ("Article", "obliges", "Obligation"),
        "định nghĩa": ("Article", "defines", "LegalTerm"),
        "áp dụng cho": ("Article", "appliesTo", "RegulatedEntity"),
        "áp dụng cho hành vi": ("Sanction", "forAct", "ProhibitedAct"),
        "căn cứ pháp lý": ("Sanction", "basedOn", "Article"),
        "thẩm quyền xử phạt": ("Sanction", "enforcedBy", "Authority"),
        "thay thế": ("LegalDocument", "supersedes", "LegalDocument"),
        "bị thay thế bởi": ("LegalDocument", "supersededBy", "LegalDocument"),
        "sửa đổi bổ sung": ("LegalDocument", "amends", "LegalDocument"),
        "hướng dẫn thi hành": ("LegalDocument", "implementsDoc", "LegalDocument"),
    }

    def test_thirteen_preferred_predicates(self):
        self.assertEqual(len(self.PREFERRED), 13)
        for alias, (source, relation, target) in self.PREFERRED.items():
            with self.subTest(alias=alias):
                subject = NAME_OF_TYPE[source]
                obj = "Luật 2" if source == target == "LegalDocument" else NAME_OF_TYPE[target]
                sg, ev = relations([[subject, alias, obj]])
                self.assertEqual(ev, [])
                self.assertEqual(labels(sg), [relation])

    def test_every_alias_in_the_table_is_canonical(self):
        """17 alias, không alias nào trỏ ra ngoài 17 tên canonical."""
        self.assertEqual(len(RELATION_ALIASES), 17)
        self.assertEqual(set(RELATION_ALIASES.values()), set(CANONICAL_RELATIONS))

    def test_normalization_is_lookup_only(self):
        """Hoa/thường, khoảng trắng thừa vẫn tra được; nhãn ra vẫn canonical."""
        sg, ev = relations([["Điều 1", "  QUY ĐỊNH   Nghĩa Vụ ", "Nghĩa vụ"]])
        self.assertEqual(labels(sg), ["obliges"])
        self.assertEqual(ev, [])

    def test_no_fuzzy_match(self):
        """Gần giống KHÔNG phải giống. Không suy diễn từ đồng nghĩa."""
        for near in ("quy định nghĩa", "quy định các nghĩa vụ", "cấm", "nghiêm cấm hành vi"):
            with self.subTest(near=near):
                sg, ev = relations([["Điều 1", near, "Nghĩa vụ"]])
                self.assertEqual(semantic(sg), [])
                self.assertEqual([e["status"] for e in ev], [UNKNOWN_PREDICATE])


class CTestCanonicalNamesKeepTheirCase(unittest.TestCase):
    """C — LLM nói thẳng tên canonical: giữ đúng chữ hoa, không hạ về lowercase."""

    CASES = [
        ("imposes", "Điều 1", "Phạt tiền"),
        ("belongsTo", "Điều 1", "Nghị định 1"),
        ("basedOn", "Phạt tiền", "Điều 1"),
        ("supersededBy", "Nghị định 1", "Luật 2"),
        ("implementsDoc", "Nghị định 1", "Luật 2"),
        ("prohibitedBy", "Hành vi", "Điều 1"),
        ("sanctionedBy", "Hành vi", "Phạt tiền"),
        ("forAct", "Phạt tiền", "Hành vi"),
        ("enforcedBy", "Phạt tiền", "Bộ Công an"),
        ("boundEntity", "Nghĩa vụ", "Đối tượng"),
        ("definedIn", "Thuật ngữ", "Điều 1"),
    ]

    def test_exact_case_survives(self):
        for relation, subject, obj in self.CASES:
            with self.subTest(relation=relation):
                sg, ev = relations([[subject, relation, obj]])
                self.assertEqual(labels(sg), [relation])
                self.assertEqual(ev, [])

    def test_lowercased_input_still_yields_canonical_case(self):
        """Trước B3, `to_camel_case("basedOn")` ra `basedon` — nhãn sai đó từng
        nằm trong graph. Giờ chuẩn hoá chỉ phục vụ TRA BẢNG (casefold), nên
        `basedon` vẫn tra ra quan hệ, nhưng nhãn ghi xuống là `basedOn`.
        """
        for wrong, relation, subject, obj in (
            ("basedon", "basedOn", "Phạt tiền", "Điều 1"),
            ("belongsto", "belongsTo", "Điều 1", "Nghị định 1"),
            ("impOses", "imposes", "Điều 1", "Phạt tiền"),
            ("foract", "forAct", "Phạt tiền", "Hành vi"),
        ):
            with self.subTest(wrong=wrong):
                sg, ev = relations([[subject, wrong, obj]])
                self.assertEqual(labels(sg), [relation])
                self.assertEqual(ev, [])
                self.assertNotIn(wrong, labels(sg))

    def test_lowercased_form_does_not_bypass_the_tuple_check(self):
        """Viết sai hoa thường KHÔNG nới lỏng hợp đồng: tuple sai vẫn bị loại."""
        sg, ev = relations([["Bộ Công an", "basedon", "Điều 1"]])
        self.assertEqual(semantic(sg), [])
        self.assertEqual(ev[0]["status"], INVALID_ENDPOINT_TYPES)
        self.assertEqual(ev[0]["candidateRelation"], "basedOn")
        self.assertEqual(ev[0]["rawPredicate"], "basedon")

    def test_no_lowercased_label_is_ever_written(self):
        """Không nhãn nào trong hợp đồng ở dạng toàn chữ thường trừ khi vốn vậy."""
        sg, _ = relations([[s, r, o] for r, s, o in self.CASES])
        for label in labels(sg):
            self.assertIn(label, CANONICAL_RELATIONS)
        self.assertNotIn("basedon", labels(sg))
        self.assertNotIn("foract", labels(sg))

    def test_every_canonical_name_is_reachable(self):
        """17 tên canonical đều có ít nhất một ca chấp nhận được."""
        reached = {relation for relation, _, _ in self.CASES}
        reached |= {"prohibits", "obliges", "defines", "appliesTo", "supersedes", "amends"}
        self.assertEqual(reached, set(CANONICAL_RELATIONS))


# -------------------------------------------------- D, E, F, G: loại có bằng chứng


class DTestWrongDirection(unittest.TestCase):
    """D — chiều sai bị loại, KHÔNG tự đảo thành chiều đúng."""

    def test_sanction_imposes_article_is_rejected(self):
        sg, ev = relations([["Phạt tiền", "quy định chế tài", "Điều 1"]])
        self.assertEqual(semantic(sg), [])
        self.assertEqual(len(ev), 1)
        entry = ev[0]
        self.assertEqual(entry["status"], INVALID_ENDPOINT_TYPES)
        self.assertEqual(entry["sourceType"], "Sanction")
        self.assertEqual(entry["targetType"], "Article")
        self.assertEqual(entry["candidateRelation"], "imposes")
        self.assertEqual(entry["rawPredicate"], "quy định chế tài")

    def test_no_reverse_edge_is_invented(self):
        sg, _ = relations([["Phạt tiền", "quy định chế tài", "Điều 1"]])
        self.assertNotIn("imposes", labels(sg))
        self.assertEqual(sg.edges, [])

    def test_reason_says_reverse_exists_but_stays_unused(self):
        _, ev = relations([["Phạt tiền", "quy định chế tài", "Điều 1"]])
        self.assertIn("không tự đảo", ev[0]["reason"])

    def test_both_declared_directions_are_accepted(self):
        """prohibits và prohibitedBy đều có trong schema -> đều hợp lệ."""
        sg, ev = relations([
            ["Điều 1", "nghiêm cấm", "Hành vi"],
            ["Hành vi", "bị cấm theo", "Điều 1"],
        ])
        self.assertEqual(labels(sg), ["prohibits", "prohibitedBy"])
        self.assertEqual(ev, [])

    def test_one_direction_alone_stays_alone(self):
        """Không materialize chiều ngược: LLM nói một chiều thì chỉ một cạnh."""
        sg, _ = relations([["Điều 1", "nghiêm cấm", "Hành vi"]])
        self.assertEqual(labels(sg), ["prohibits"])
        sg, _ = relations([["Phạt tiền", "căn cứ pháp lý", "Điều 1"]])
        self.assertEqual(labels(sg), ["basedOn"])
        self.assertNotIn("imposes", labels(sg))


class ETestWrongEndpointTypes(unittest.TestCase):
    """E — tên quan hệ đúng nhưng kiểu đầu mút sai: loại."""

    def test_authority_obliges_legalterm_is_rejected(self):
        sg, ev = relations([["Bộ Công an", "quy định nghĩa vụ", "Thuật ngữ"]])
        self.assertEqual(semantic(sg), [])
        self.assertEqual(ev[0]["status"], INVALID_ENDPOINT_TYPES)
        self.assertEqual(
            (ev[0]["sourceType"], ev[0]["candidateRelation"], ev[0]["targetType"]),
            ("Authority", "obliges", "LegalTerm"),
        )

    def test_basedon_depends_on_source_type(self):
        """Cùng tên quan hệ, kiểu chủ ngữ quyết định hợp lệ hay không."""
        for subject, valid in (("Phạt tiền", True), ("Nghĩa vụ", True), ("Bộ Công an", False)):
            with self.subTest(subject=subject):
                sg, ev = relations([[subject, "căn cứ pháp lý", "Điều 1"]])
                self.assertEqual(labels(sg), ["basedOn"] if valid else [])
                if not valid:
                    self.assertEqual(ev[0]["status"], INVALID_ENDPOINT_TYPES)
                    self.assertEqual(ev[0]["candidateRelation"], "basedOn")

    def test_mapper_and_validator_are_separate_steps(self):
        """Vị ngữ map được nhưng tuple sai -> candidateRelation vẫn ghi lại."""
        _, ev = relations([["Bộ Công an", "căn cứ pháp lý", "Điều 1"]])
        self.assertEqual(ev[0]["candidateRelation"], "basedOn")
        self.assertNotEqual(ev[0]["status"], UNKNOWN_PREDICATE)

    def test_unresolved_endpoint_is_its_own_status(self):
        sg, ev = relations([["Điều 1", "nghiêm cấm", "Hành vi lạ không qua NER"]])
        self.assertEqual(semantic(sg), [])
        self.assertEqual(ev[0]["status"], UNRESOLVED_ENDPOINT)
        self.assertNotIn("targetType", ev[0])

    def test_ambiguous_binding_is_its_own_status(self):
        """Một tên, hai nhãn NER -> không biết kiểu nào, không đoán."""
        sg, ev = relations(
            [["Điều 1", "nghiêm cấm", "Mơ hồ"]],
            entities=ENTITIES + [
                {"name": "Mơ hồ", "category": "ProhibitedAct"},
                {"name": "mơ  hồ", "category": "LegalTerm"},
            ],
        )
        self.assertEqual(semantic(sg), [])
        self.assertEqual(ev[0]["status"], AMBIGUOUS_BINDING)


class FTestUnknownPredicate(unittest.TestCase):
    """F — vị ngữ lạ: không cạnh, không loại quan hệ tự do, có bằng chứng."""

    def test_gia_mao_creates_no_edge(self):
        sg, ev = relations([["Hành vi", "giả mạo", "Thuật ngữ"]])
        self.assertEqual(sg.edges, [])
        self.assertNotIn("giMO", [e.label for e in sg.edges])
        self.assertEqual(ev[0]["rawPredicate"], "giả mạo")
        self.assertEqual(ev[0]["status"], UNKNOWN_PREDICATE)

    def test_raw_triple_is_kept_whole(self):
        _, ev = relations([["Hành vi", "giả mạo", "Thuật ngữ"]])
        self.assertEqual(
            (ev[0]["rawSubject"], ev[0]["rawPredicate"], ev[0]["rawObject"]),
            ("Hành vi", "giả mạo", "Thuật ngữ"),
        )

    def test_no_free_relation_type_at_all(self):
        """Không `relatedTo`, không `UnknownRelation`, không nhãn camel-case."""
        sg, _ = relations([
            ["Hành vi", "giả mạo", "Thuật ngữ"],
            ["Điều 1", "xử lý", "Hành vi"],
            ["Phạt tiền", "kèm theo", "Bộ Công an"],
        ])
        self.assertEqual(sg.edges, [])

    def test_no_candidate_relation_when_unmappable(self):
        _, ev = relations([["Hành vi", "giả mạo", "Thuật ngữ"]])
        self.assertNotIn("candidateRelation", ev[0])

    def test_types_are_still_recorded_when_known(self):
        _, ev = relations([["Hành vi", "giả mạo", "Thuật ngữ"]])
        self.assertEqual(ev[0]["sourceType"], "ProhibitedAct")
        self.assertEqual(ev[0]["targetType"], "LegalTerm")

    def test_evidence_holds_no_absolute_path(self):
        _, ev = relations([["Hành vi", "giả mạo", "Thuật ngữ"]])
        blob = json.dumps(ev, ensure_ascii=False)
        self.assertNotIn(str(ROOT), blob)
        self.assertNotIn(":\\", blob)

    def test_evidence_never_claims_verification(self):
        _, ev = relations([["Hành vi", "giả mạo", "Thuật ngữ"]])
        blob = json.dumps(ev, ensure_ascii=False)
        for word in ("VERIFIED", "FULL", "human_verified"):
            self.assertNotIn(word, blob)


class GTestCamelCollision(unittest.TestCase):
    """G — `cấm`/`căm` cùng ra `cM`: không gộp thành một quan hệ."""

    def test_both_are_rejected_independently(self):
        sg, ev = relations([
            ["Điều 1", "cấm", "Hành vi"],
            ["Điều 1", "căm", "Hành vi"],
        ])
        self.assertEqual(sg.edges, [])
        self.assertEqual([e["rawPredicate"] for e in ev], ["cấm", "căm"])
        self.assertEqual({e["status"] for e in ev}, {UNKNOWN_PREDICATE})

    def test_no_shared_camel_label_exists(self):
        sg, _ = relations([["Điều 1", "cấm", "Hành vi"], ["Điều 1", "căm", "Hành vi"]])
        self.assertNotIn("cM", [e.label for e in sg.edges])

    def test_diacritic_variants_do_not_collapse(self):
        """`áp dụng cho` map được, `ăp dụng cho` (sai dấu) thì không."""
        sg, ev = relations([["Điều 1", "áp dụng cho", "Đối tượng"]])
        self.assertEqual(labels(sg), ["appliesTo"])
        sg, ev = relations([["Điều 1", "ăp dụng cho", "Đối tượng"]])
        self.assertEqual(semantic(sg), [])
        self.assertEqual(ev[0]["status"], UNKNOWN_PREDICATE)

    def test_one_valid_one_invalid_do_not_shift(self):
        """Triple lạ không đẩy hàng của triple hợp lệ."""
        sg, ev = relations([
            ["Điều 1", "cấm", "Hành vi"],
            ["Điều 1", "nghiêm cấm", "Hành vi"],
        ])
        edges = semantic(sg)
        self.assertEqual([e.label for e in edges], ["prohibits"])
        self.assertEqual(edges[0].properties["originalPredicate"], "nghiêm cấm")
        self.assertEqual([e["rawPredicate"] for e in ev], ["cấm"])


# ------------------------------------------------------- H: danh tính đầu mút


class HTestEndpointIdsComeFromB2(unittest.TestCase):
    """H — id hai đầu cạnh đúng bằng id node sau resolve của B2."""

    def setUp(self):
        self.chunk = nd330_article_9()
        self.graph = sanction_case(self.chunk)

    def test_every_endpoint_matches_a_node(self):
        node_ids = {node.id for node in self.graph.nodes}
        for edge in self.graph.edges:
            self.assertIn(edge.from_id, node_ids, edge.label)
            self.assertIn(edge.to_id, node_ids, edge.label)

    def test_article_endpoint_is_the_canonical_article_id(self):
        imposes = next(e for e in self.graph.edges if e.label == "imposes")
        self.assertEqual(imposes.from_id, "article:330-2026-ND-CP:9")

    def test_sanction_endpoint_is_the_sanction_node_id(self):
        sanction_ids = [n.id for n in self.graph.nodes if n.label == "Sanction"]
        self.assertEqual(len(sanction_ids), 1, sanction_ids)
        imposes = next(e for e in self.graph.edges if e.label == "imposes")
        based = next(e for e in self.graph.edges if e.label == "basedOn")
        self.assertEqual(imposes.to_id, sanction_ids[0])
        self.assertEqual(based.from_id, sanction_ids[0])

    def test_no_second_identity_set_appears(self):
        """Không có đầu mút nào là tên thô chưa qua resolve."""
        for edge in self.graph.edges:
            self.assertNotEqual(edge.from_id, FINE)
            self.assertNotEqual(edge.to_id, FINE)


# ------------------------------------------------- I, J: quan hệ của hệ thống


class ITestSystemRelations(unittest.TestCase):
    """I — cạnh `source` do KAG sinh, không đi qua mapper quan hệ pháp lý."""

    def setUp(self):
        self.chunk = nd330_article_9()
        self.graph = sanction_case(self.chunk)

    def test_source_edges_still_exist(self):
        source_edges = [e for e in self.graph.edges if e.label == "source"]
        self.assertTrue(source_edges)

    def test_source_edges_point_at_the_chunk(self):
        for edge in (e for e in self.graph.edges if e.label == "source"):
            self.assertEqual(edge.to_id, self.chunk.id)

    def test_source_is_not_in_the_relation_contract(self):
        self.assertNotIn("source", CANONICAL_RELATIONS)
        self.assertNotIn("OfficialName", CANONICAL_RELATIONS)

    def test_source_edges_carry_no_legal_provenance(self):
        """Không gắn originalPredicate lên cạnh hệ thống: nó không phải fact LLM."""
        for edge in (e for e in self.graph.edges if e.label == "source"):
            self.assertNotIn("originalPredicate", edge.properties or {})
            self.assertNotIn("relationMappingVersion", edge.properties or {})

    def test_llm_saying_source_is_not_a_system_edge(self):
        sg, ev = relations([["Điều 1", "source", "Hành vi"]])
        self.assertEqual(sg.edges, [])
        self.assertEqual(ev[0]["status"], UNKNOWN_PREDICATE)


class JTestOfficialNameIsNotARelation(unittest.TestCase):
    """J — `OfficialName` không phải quan hệ canonical của LLM."""

    def test_llm_saying_officialname_is_rejected(self):
        sg, ev = relations([["Điều 1", "OfficialName", "Nghị định 1"]])
        self.assertEqual(sg.edges, [])
        self.assertEqual(ev[0]["rawPredicate"], "OfficialName")
        self.assertEqual(ev[0]["status"], UNKNOWN_PREDICATE)

    def test_officialname_keeps_current_behavior_for_unmanaged_types(self):
        """B2 không quản `Others`: cạnh OfficialName vẫn do lớp cha sinh."""
        extractor = object.__new__(LegalSchemaFreeExtractor)
        extractor.schema = {label: SimpleNamespace(properties={}) for label in _LABELS}
        extractor.external_graph = None
        graph, entities = extractor.assemble_sub_graph_with_spg_records(
            [{"name": "ANM", "category": "Others", "official_name": "An ninh mạng"}]
        )
        extractor.append_official_name(entities, "An ninh mạng")
        extractor.assemble_sub_graph_with_entities(graph, entities)
        self.assertIn("OfficialName", [e.label for e in graph.edges])

    def test_mapper_is_not_run_on_officialname_edges(self):
        extractor = object.__new__(LegalSchemaFreeExtractor)
        extractor.schema = {label: SimpleNamespace(properties={}) for label in _LABELS}
        extractor.external_graph = None
        graph, entities = extractor.assemble_sub_graph_with_spg_records(
            [{"name": "ANM", "category": "Others", "official_name": "An ninh mạng"}]
        )
        extractor.append_official_name(entities, "An ninh mạng")
        extractor.assemble_sub_graph_with_entities(graph, entities)
        for edge in (e for e in graph.edges if e.label == "OfficialName"):
            self.assertNotIn("originalPredicate", edge.properties or {})


# ------------------------------------------------------ K, L: nguồn trích xuất


class KTestAcceptedEdgeProvenance(unittest.TestCase):
    """K — cạnh được nhận mang đủ nguồn, và KHÔNG tự nhận đã xác minh."""

    def setUp(self):
        self.chunk = nd330_article_9()
        self.graph = sanction_case(self.chunk)
        self.edge = next(e for e in self.graph.edges if e.label == "imposes")
        self.props = self.edge.properties or {}

    def test_original_predicate_is_the_raw_one(self):
        self.assertEqual(self.props["originalPredicate"], "quy định chế tài")
        self.assertEqual(self.props["originalPredicateStatus"], "RESOLVED")

    def test_mapping_version_describes_the_contract(self):
        self.assertEqual(RELATION_MAPPING_VERSION, "legal_relation_v1")
        self.assertEqual(self.props["relationMappingVersion"], "legal_relation_v1")
        # Field cũ giữ lại cho consumer cũ, giá trị đi cùng version mới.
        self.assertEqual(self.props["predicateMappingVersion"], "legal_relation_v1")
        self.assertNotIn("camel_case", RELATION_MAPPING_VERSION)

    def test_evidence_status_is_unverified(self):
        self.assertEqual(self.props["evidenceStatus"], "UNVERIFIED")

    def test_chunk_and_path_and_document(self):
        self.assertEqual(self.props["sourceChunkId"], self.chunk.id)
        self.assertEqual(self.props["sourcePath"], source_path_of("330-2026-ND-CP"))
        self.assertEqual(
            self.props["sourceDocumentId"], source_document_id(self.props["sourcePath"])
        )
        self.assertEqual(self.props["sourceDocumentId"], "330-2026-ND-CP")

    def test_source_path_is_relative(self):
        self.assertFalse(Path(self.props["sourcePath"]).is_absolute())
        self.assertNotIn(str(ROOT), self.props["sourcePath"])

    def test_article_id_comes_from_the_chunk_not_the_endpoint(self):
        self.assertEqual(self.props["sourceArticleId"], "article:330-2026-ND-CP:9")
        based = next(e for e in self.graph.edges if e.label == "basedOn")
        # Tân ngữ của basedOn cũng là Điều 9, nhưng id nguồn vẫn của CHUNK.
        self.assertEqual(based.properties["sourceArticleId"], "article:330-2026-ND-CP:9")

    def test_document_provenance_is_not_an_endpoint_document(self):
        """LegalDocument làm tân ngữ KHÔNG được thành sourceDocumentId."""
        chunk = self.chunk
        graph = graph_for(
            chunk,
            [{"name": "Điều 9", "category": "Article"},
             {"name": "Luật An ninh mạng", "category": "LegalDocument"}],
            [["Điều 9", "thuộc văn bản", "Luật An ninh mạng"]],
        )
        edge = next(e for e in graph.edges if e.label == "belongsTo")
        self.assertEqual(edge.properties["sourceDocumentId"], "330-2026-ND-CP")
        self.assertNotEqual(edge.properties["sourceDocumentId"], edge.to_id)

    def test_no_verified_claim_anywhere(self):
        for edge in self.graph.edges:
            props = edge.properties or {}
            self.assertNotIn("human_verified", props)
            self.assertNotIn(props.get("evidenceStatus"), ("VERIFIED", "FULL"))

    def test_article_id_absent_when_chunk_article_unresolved(self):
        """Không đoán Điều: Điều nguồn không phân giải -> không có sourceArticleId."""
        from kag.builder.model.chunk import Chunk

        chunk = Chunk(
            id="chunk-khong-phan-giai",
            name="330-2026-ND-CP / Điều 999. Tiêu đề không có trong nguồn",
            content="nội dung",
            source_path=source_path_of("330-2026-ND-CP"),
            heading_path=["330-2026-ND-CP", "Điều 999. Tiêu đề không có trong nguồn"],
            article_no=999,
        )
        graph = graph_for(
            chunk,
            [{"name": "Điều 999", "category": "Article"},
             {"name": "Hành vi lạ", "category": "ProhibitedAct"}],
            [["Điều 999", "nghiêm cấm", "Hành vi lạ"]],
        )
        edge = next(e for e in graph.edges if e.label == "prohibits")
        self.assertNotIn("sourceArticleId", edge.properties)
        self.assertEqual(edge.properties["sourceChunkId"], chunk.id)


class LTestRejectedEvidenceOnChunk(unittest.TestCase):
    """L — triple bị loại để lại bằng chứng trên Chunk của chính nó."""

    def setUp(self):
        self.chunk = nd330_article_9()
        self.graph = sanction_case(self.chunk)
        self.evidence = chunk_node(self.graph).properties["relationEvidence"]

    def test_chunk_carries_relation_evidence(self):
        self.assertEqual(len(self.evidence), 1)

    def test_entry_keeps_the_raw_triple(self):
        entry = self.evidence[0]
        self.assertEqual(entry["rawSubject"], "Bộ Công an")
        self.assertEqual(entry["rawPredicate"], "căn cứ pháp lý")
        self.assertEqual(entry["rawObject"], "Điều 9")

    def test_entry_has_status_and_reason(self):
        entry = self.evidence[0]
        self.assertEqual(entry["status"], INVALID_ENDPOINT_TYPES)
        self.assertTrue(entry["reason"].strip())

    def test_entry_records_types_and_candidate(self):
        entry = self.evidence[0]
        self.assertEqual(entry["sourceType"], "Authority")
        self.assertEqual(entry["targetType"], "Article")
        self.assertEqual(entry["candidateRelation"], "basedOn")

    def test_status_vocabulary_is_fixed(self):
        self.assertEqual(
            {UNKNOWN_PREDICATE, INVALID_ENDPOINT_TYPES, UNRESOLVED_ENDPOINT, AMBIGUOUS_BINDING},
            {"UNKNOWN_PREDICATE", "INVALID_ENDPOINT_TYPES", "UNRESOLVED_ENDPOINT",
             "AMBIGUOUS_BINDING"},
        )

    def test_no_evidence_property_when_nothing_is_rejected(self):
        graph = graph_for(
            self.chunk,
            [{"name": "Điều 9", "category": "Article"},
             {"name": FINE, "category": "Sanction"}],
            [["Điều 9", "quy định chế tài", FINE]],
        )
        self.assertNotIn("relationEvidence", chunk_node(graph).properties)

    def test_evidence_does_not_pretend_the_relation_exists(self):
        """Bằng chứng loại KHÔNG sinh cạnh nào cho quan hệ đó."""
        self.assertFalse(
            any(e.from_id == canon_id("Bộ Công an") for e in self.graph.edges
                if e.label == "basedOn")
        )

    def test_evidence_has_no_absolute_path(self):
        blob = json.dumps(self.evidence, ensure_ascii=False)
        self.assertNotIn(str(ROOT), blob)
        self.assertNotIn(":\\", blob)


# ----------------------------------------------------------- M: nhiều nguồn


class MTestTwoChunksKeepTheirOwnSource(unittest.TestCase):
    """M — cùng quan hệ ở hai chunk: mỗi instance giữ nguồn của chunk mình.

    Chỉ chứng minh TRƯỚC writer. Server upsert/merge nhiều occurrence là việc
    của C, test này không kết luận gì về DB.
    """

    def graphs(self):
        chunks = [c for c in article_chunks("330-2026-ND-CP", 9) if FINE in c.content]
        other = [c for c in article_chunks("330-2026-ND-CP", 10)
                 if "Phạt tiền" in c.content]
        self.assertTrue(chunks and other)
        pairs = []
        for chunk, article_no in ((chunks[0], 9), (other[0], 10)):
            sanction = FINE if article_no == 9 else next(
                line.strip() for line in chunk.content.splitlines() if "Phạt tiền" in line
            )
            graph = graph_for(
                chunk,
                [{"name": f"Điều {article_no}", "category": "Article"},
                 {"name": sanction, "category": "Sanction"}],
                [[f"Điều {article_no}", "quy định chế tài", sanction]],
            )
            pairs.append((chunk, graph))
        return pairs

    def test_each_edge_keeps_its_own_chunk_id(self):
        seen = []
        for chunk, graph in self.graphs():
            edge = next(e for e in graph.edges if e.label == "imposes")
            self.assertEqual(edge.properties["sourceChunkId"], chunk.id)
            seen.append(edge.properties["sourceChunkId"])
        self.assertEqual(len(set(seen)), 2, seen)

    def test_same_canonical_relation_in_both(self):
        for _, graph in self.graphs():
            self.assertIn("imposes", [e.label for e in graph.edges])

    def test_no_in_memory_merge_loses_a_source(self):
        """Hai SubGraph, hai cạnh, hai nguồn — không gộp trong RAM."""
        edges = []
        for _, graph in self.graphs():
            edges += [e for e in graph.edges if e.label == "imposes"]
        self.assertEqual(len(edges), 2)
        self.assertEqual(
            len({e.properties["sourceArticleId"] for e in edges}), 2
        )

    def test_two_occurrences_in_one_chunk_both_survive(self):
        """Cùng vị ngữ, hai tân ngữ: hai cạnh riêng, không dedupe mất một."""
        sg, _ = relations([
            ["Điều 1", "quy định chế tài", "Phạt tiền"],
            ["Điều 2", "quy định chế tài", "Phạt tiền"],
        ])
        self.assertEqual(labels(sg), ["imposes", "imposes"])


# --------------------------------------------------- N: writer offline


class NTestWriterStandardization(unittest.TestCase):
    """N — `standarlize_graph()` offline: nhãn và property sống sót.

    Gọi thẳng `standarlize_graph`, KHÔNG gọi `_invoke()` — không graph write,
    không DB, không client.
    """

    def setUp(self):
        self.chunk = nd330_article_9()
        graph = sanction_case(self.chunk)
        writer = object.__new__(KGWriter)
        # Chỉ cần namespace để format_label chạy; không client, không DB.
        writer.kag_project_config = SimpleNamespace(namespace="Legal")
        self.graph = writer.standarlize_graph(graph)

    def chunk_properties(self):
        node = next(n for n in self.graph.nodes if n.label.split(".")[-1] == "Chunk")
        return node.properties

    def test_canonical_label_survives_namespacing(self):
        labels_out = {e.label for e in self.graph.edges}
        self.assertIn("imposes", labels_out)
        self.assertIn("basedOn", labels_out)
        self.assertNotIn("basedon", labels_out)

    def test_no_camel_case_label_appears(self):
        for edge in self.graph.edges:
            self.assertNotIn("quyNhNghAV", edge.label)
            self.assertNotIn("cM", edge.label.split("."))

    def test_edge_provenance_survives(self):
        edge = next(e for e in self.graph.edges if e.label == "imposes")
        props = edge.properties
        self.assertEqual(props["originalPredicate"], "quy định chế tài")
        self.assertEqual(props["relationMappingVersion"], "legal_relation_v1")
        self.assertEqual(props["evidenceStatus"], "UNVERIFIED")
        self.assertEqual(props["sourceChunkId"], self.chunk.id)

    def test_relation_evidence_survives_as_json(self):
        """Writer `json.dumps` mọi property không phải str: list -> chuỗi JSON."""
        raw = self.chunk_properties()["relationEvidence"]
        self.assertIsInstance(raw, str)
        parsed = json.loads(raw)
        self.assertEqual(parsed[0]["rawPredicate"], "căn cứ pháp lý")
        self.assertEqual(parsed[0]["status"], INVALID_ENDPOINT_TYPES)

    def test_serialized_graph_keeps_everything(self):
        dumped = self.graph.to_dict()
        imposes = [e for e in dumped["resultEdges"] if e["label"] == "imposes"]
        self.assertEqual(len(imposes), 1)
        self.assertEqual(imposes[0]["properties"]["sourceChunkId"], self.chunk.id)
        self.assertTrue(
            any("relationEvidence" in n["properties"] for n in dumped["resultNodes"])
        )


# ------------------------------------------------ O: metadata đã có trong hợp đồng


class OTestMetadataEdgesInsideContract(unittest.TestCase):
    """O — 38 cạnh metadata sẵn có đều là tuple trong hợp đồng B3."""

    @classmethod
    def setUpClass(cls):
        if not EDGES_FILE.exists():
            raise unittest.SkipTest(f"chưa có {EDGES_FILE.name}")
        cls.edges = json.loads(EDGES_FILE.read_text(encoding="utf-8"))

    def test_edge_count_is_the_surveyed_thirty_eight(self):
        self.assertEqual(len(self.edges), 38)

    def test_every_edge_tuple_is_in_the_contract(self):
        for edge in self.edges:
            tuple_ = (edge["fromType"], edge["label"], edge["toType"])
            with self.subTest(tuple_=tuple_):
                self.assertIn(tuple_, RELATION_CONTRACT)

    def test_superseded_by_inverse_is_accepted_too(self):
        """Đường metadata sinh `supersededBy` từ `supersedes` — chiều này hợp lệ."""
        self.assertIn(("LegalDocument", "supersededBy", "LegalDocument"), RELATION_CONTRACT)
        self.assertIn("supersededBy", {e["label"] for e in self.edges})

    def test_metadata_labels_are_a_subset_of_canonical_names(self):
        self.assertTrue({e["label"] for e in self.edges} <= set(CANONICAL_RELATIONS))


class PTestPromptMatchesContract(unittest.TestCase):
    """Prompt và hợp đồng không được trôi khỏi nhau.

    Prompt là đầu vào duy nhất dạy model tên quan hệ. Nếu prompt còn dạy vị ngữ
    tự do, hoặc ví dụ trong prompt sinh ra triple mà chính validator loại, thì
    mọi chunk đều mất quan hệ mà không ai thấy.
    """

    @classmethod
    def setUpClass(cls):
        from string import Template

        from builder.prompt.triple import TEMPLATE

        cls.template = TEMPLATE
        # TEMPLATE là string.Template, không phải JSON: điền chỗ trống rỗng để
        # đọc được phần `example` — phần đó mới là thứ dạy model.
        filled = Template(TEMPLATE).substitute(entity_list="[]", input="")
        cls.example = json.loads(filled)["example"]

    def test_every_canonical_name_is_taught(self):
        for relation in CANONICAL_RELATIONS:
            with self.subTest(relation=relation):
                self.assertIn(f"'{relation}'", self.template)

    def test_free_predicate_escape_hatch_is_gone(self):
        self.assertNotIn("mới đặt vị ngữ tự do", self.template)
        self.assertIn("KHÔNG sinh bộ ba đó", self.template)

    def test_example_triples_all_pass_the_validator(self):
        entities = self.example["entity_list"]
        sg, ev = relations(self.example["output"], entities=entities)
        self.assertEqual(ev, [])
        self.assertEqual(len(semantic(sg)), len(self.example["output"]))
        self.assertTrue(set(labels(sg)) <= set(CANONICAL_RELATIONS))

    def test_example_uses_no_vietnamese_alias_as_relation(self):
        for triple in self.example["output"]:
            self.assertIn(triple[1], CANONICAL_RELATIONS, triple)


if __name__ == "__main__":
    unittest.main(verbosity=2)
