# -*- coding: utf-8 -*-
"""Extractor vá bốn lỗi của SchemaFreeExtractor trong KAG 0.8.0.

Ba lỗi đầu từng làm 11 trên 23 văn bản không dựng được đồ thị. Trước đây chúng
được sửa thẳng trong mã nguồn KAG, nghĩa là dự án chỉ chạy đúng trên đúng một
máy có bản KAG đã sửa. Chuyển vào đây thì KAG trở lại là thư viện pip bình
thường, ai clone repo về cũng chạy được.

Lỗi thứ tư (giai đoạn 6, đã thay bằng B3): edge type sinh từ `to_camel_case`.

`schema_free_extractor.py:358` gọi `to_camel_case(tri[1])` rồi dùng kết quả làm
edge type. `to_camel_case` đi qua `processing_phrases`, hàm này thay MỌI ký tự
ngoài ``[A-Za-z0-9 CJK]`` bằng dấu cách — nên dấu tiếng Việt biến mất:

    "quy định nghĩa vụ" -> "quyNhNghAV"
    "thuộc văn bản"     -> "thuCVNBN"
    "nghiêm cấm"        -> "nghiMCM"

Phép này KHÔNG khả nghịch. Chạy thử trong .venv: ``to_camel_case("cấm")`` và
``to_camel_case("căm")`` đều ra ``"cM"``; ``"áp dụng cho"`` và ``"ăp dụng cho"``
đều ra ``"pDNgCho"``. Vì vậy không được suy ngược vị ngữ gốc từ edge type.

Hậu quả đã đo trên snapshot 17/09/2026: 554 loại quan hệ, 342 loại chỉ xuất
hiện một lần, và 51 loại là mảnh vụn <= 4 ký tự (``l``, ``ngh``, ``c``, ``k``)
— không thể biết nghĩa gốc. Checkpoint cũ chỉ giữ tên ĐÃ biến đổi.

Giai đoạn 6 chỉ ghi THÊM vị ngữ gốc vào properties cạnh và giữ edge type camel.
B3 bỏ hẳn đường đó: `to_camel_case` KHÔNG còn quyết định nhãn quan hệ ngữ nghĩa.

B3 — quan hệ canonical (xem `RELATION_CONTRACT` bên dưới)
----------------------------------------------------------
Triple của LLM đi đúng năm bước, tất cả tất định, không đoán:

    làm sạch triple thô
    -> bind hai đầu về entity/nhãn của NER
    -> ánh xạ vị ngữ thô sang quan hệ canonical trong Legal.schema
    -> kiểm tuple (nhãn nguồn, quan hệ, nhãn đích) theo contract
    -> lấy id cuối của B2 rồi add_edge trực tiếp

Vì vậy KHÔNG còn gọi `SchemaFreeExtractor.assemble_sub_graph_with_triples`: lớp
cha sinh nhãn bằng `to_camel_case` và không kiểm chiều/nhãn hai đầu. `edge.label`
bây giờ luôn là một trong 17 tên quan hệ của schema.

Không map được, sai chiều, sai nhãn hoặc không định vị được đầu mút thì KHÔNG
sinh cạnh nào — không `relatedTo`, không `UnknownRelation`, không tự đảo chiều.
Nhưng cũng không im lặng bỏ: triple bị từ chối được ghi vào
`relationEvidence` của chính node Chunk đang xử lý.

Không gắn FULL/VERIFIED khi LLM trả triple: cạnh mới chỉ có
`evidenceStatus=UNVERIFIED`, provenance thật do tầng gọi bổ sung.

Không chép lại thân hàm của lớp cha: cả bốn chỗ đều làm sạch dữ liệu trước hoặc
sau khi gọi super(), nên bản KAG mới ra vẫn dùng được mà không phải so lại từng
dòng.
"""

import logging
import re
import unicodedata
from typing import Dict, List

from kag.interface import ExtractorABC
from kag.builder.component.extractor.schema_free_extractor import SchemaFreeExtractor
from kag.builder.model.sub_graph import SubGraph
from kag.common.utils import generate_hash_id
from knext.schema.client import CHUNK_TYPE, OTHER_TYPE

# Import tuyệt đối, KHÔNG dùng `from .canon_id`: loader production
# (kag/common/registry/utils.py:31, gọi từ indexer.py và injection.py) import mọi
# module con của kag/builder dưới tên TOP-LEVEL ("extractor"), nên module này khi
# đó không có parent package và relative import nổ ImportError ngay lúc bootstrap.
# Loader đã chèn kag/ vào sys.path và đã import package `builder` trước khi đệ quy,
# nên `builder.canon_id` giải được ở cả hai đường: production loader và
# `import builder.extractor` (đường của tests).
from builder.canon_id import (
    CONTEXTUAL_CATEGORIES,
    SEMANTIC_CATEGORIES,
    article_identity,
    canon_id,
    semantic_identity,
    source_article_headings,
    source_document_id,
    unresolved_identity,
)

logger = logging.getLogger(__name__)

# Phiên bản quy tắc ánh xạ vị ngữ thô -> quan hệ canonical. KHÔNG còn là
# "camel_case_v1": nhãn quan hệ không sinh từ camel-case của vị ngữ nữa.
RELATION_MAPPING_VERSION = "legal_relation_v1"

# Tên field cũ giữ nguyên để consumer đang đọc `predicateMappingVersion` không
# vỡ; giá trị thì theo quy tắc mới. Cạnh mới mang CẢ HAI field, cùng giá trị.
PREDICATE_MAPPING_VERSION = RELATION_MAPPING_VERSION

# Contract quan hệ: CHÍNH XÁC các tuple đang khai báo trong kag/schema/Legal.schema.
# 18 tuple, 17 tên quan hệ (`basedOn` xuất hiện ở hai nhãn nguồn).
#
# Đây là bảng explicit, không parse schema lúc chạy — nhưng
# tests/builder/test_relation_b3.py khóa parity với Legal.schema để hai bên không
# lệch âm thầm. Thêm/bớt quan hệ là đổi schema, không phải đổi riêng bảng này.
RELATION_CONTRACT = frozenset({
    ("LegalDocument", "supersedes", "LegalDocument"),
    ("LegalDocument", "supersededBy", "LegalDocument"),
    ("LegalDocument", "amends", "LegalDocument"),
    ("LegalDocument", "implementsDoc", "LegalDocument"),
    ("Article", "belongsTo", "LegalDocument"),
    ("Article", "prohibits", "ProhibitedAct"),
    ("Article", "imposes", "Sanction"),
    ("Article", "obliges", "Obligation"),
    ("Article", "defines", "LegalTerm"),
    ("Article", "appliesTo", "RegulatedEntity"),
    ("ProhibitedAct", "prohibitedBy", "Article"),
    ("ProhibitedAct", "sanctionedBy", "Sanction"),
    ("Sanction", "forAct", "ProhibitedAct"),
    ("Sanction", "basedOn", "Article"),
    ("Sanction", "enforcedBy", "Authority"),
    ("Obligation", "boundEntity", "RegulatedEntity"),
    ("Obligation", "basedOn", "Article"),
    ("LegalTerm", "definedIn", "Article"),
})

# 17 tên. Chiều nào có mặt trong schema thì chiều đó hợp lệ — `prohibits` và
# `prohibitedBy` đều là quan hệ thật. Nhưng KHÔNG suy một chiều từ chiều kia:
# OpenIE không tự materialize inverse (xem `_map_relation`).
CANONICAL_RELATIONS = frozenset(relation for _, relation, _ in RELATION_CONTRACT)

# Vị ngữ tiếng Việt explicit -> quan hệ canonical. Bảng đóng: không fuzzy match,
# không tự thêm từ đồng nghĩa. Prompt (prompt/triple.py) yêu cầu model dùng đúng
# tên canonical; bảng alias là đường vào tất định cho output tiếng Việt.
RELATION_ALIASES = {
    "thay thế": "supersedes",
    "bị thay thế bởi": "supersededBy",
    "sửa đổi bổ sung": "amends",
    "hướng dẫn thi hành": "implementsDoc",
    "thuộc văn bản": "belongsTo",
    "nghiêm cấm": "prohibits",
    "quy định chế tài": "imposes",
    "quy định nghĩa vụ": "obliges",
    "định nghĩa": "defines",
    "áp dụng cho": "appliesTo",
    "bị cấm theo": "prohibitedBy",
    "bị xử phạt theo": "sanctionedBy",
    "áp dụng cho hành vi": "forAct",
    "căn cứ pháp lý": "basedOn",
    "thẩm quyền xử phạt": "enforcedBy",
    "ràng buộc đối tượng": "boundEntity",
    "định nghĩa tại": "definedIn",
}

# Trạng thái từ chối. Tập nhỏ, tất định, được test khóa. Không thêm trạng thái
# mới chỉ để mô tả sắc thái — `reason` là chỗ ghi chi tiết.
UNKNOWN_PREDICATE = "UNKNOWN_PREDICATE"
INVALID_ENDPOINT_TYPES = "INVALID_ENDPOINT_TYPES"
UNRESOLVED_ENDPOINT = "UNRESOLVED_ENDPOINT"
AMBIGUOUS_BINDING = "AMBIGUOUS_BINDING"

# Quan hệ do hệ thống sinh, không phải fact LLM. `source` do
# `assemble_sub_graph_with_chunk` tạo, `OfficialName` do
# `assemble_sub_graph_with_entities` tạo — cả hai KHÔNG đi qua mapper quan hệ
# pháp lý. Nếu LLM trả đúng hai chữ này làm vị ngữ thì đó không phải cạnh hệ
# thống hợp lệ: nó bị từ chối như mọi vị ngữ ngoài contract.
_SYSTEM_PREDICATES = {"source", "OfficialName"}


def _normalize_predicate(raw):
    """Chuẩn hóa CHỈ để tra bảng. Không dùng để sinh nhãn, không fuzzy match."""
    if not isinstance(raw, str):
        return ""
    text = unicodedata.normalize("NFC", raw).casefold()
    return re.sub(r"\s+", " ", text).strip()


# Tra cứu: tên canonical (mọi cách viết hoa/thường) + alias tiếng Việt. Giá trị
# luôn là tên canonical ĐÚNG CASE của schema, nên "imposes"/"IMPOSES"/"Imposes"
# đều ra "imposes" và "basedon" ra "basedOn" — không bị lowercase thành sai tên.
_RELATION_LOOKUP = {
    **{_normalize_predicate(name): name for name in CANONICAL_RELATIONS},
    **{_normalize_predicate(alias): name for alias, name in RELATION_ALIASES.items()},
}


def _map_relation(raw):
    """Vị ngữ thô -> tên quan hệ canonical, hoặc None nếu không map được.

    Tất định và không đối xứng: `prohibits` KHÔNG sinh thêm `prohibitedBy`, và
    một triple sai chiều KHÔNG được đảo lại thành chiều hợp schema. Ánh xạ tên
    và kiểm tuple là hai bước tách biệt — cùng một alias (`"căn cứ pháp lý"` ->
    `basedOn`) hợp lệ với `Sanction`/`Obligation` nhưng sai với `Authority`.
    """
    if not isinstance(raw, str) or raw.strip() in _SYSTEM_PREDICATES:
        return None
    return _RELATION_LOOKUP.get(_normalize_predicate(raw))


def _bind_endpoint(raw, entity_labels):
    """Đầu mút thô -> nhãn NER của nó. Trả `(label, (status, reason))`.

    Chỉ nhận đầu mút khớp một thực thể NER: không có entity thì không có bằng
    chứng nhãn, mà không biết nhãn thì không kiểm được tuple. Khóa khớp là
    `canon_id()` — cùng khóa mà `_endpoint_ids` dùng, nên bind và tra id không
    lệch nhau.
    """
    key = canon_id(raw) if isinstance(raw, str) else ""
    if not key:
        return None, (UNRESOLVED_ENDPOINT, "đầu mút rỗng sau chuẩn hóa")
    labels = entity_labels.get(key)
    if not labels:
        return None, (UNRESOLVED_ENDPOINT, f"{raw!r} không khớp thực thể NER nào")
    if len(labels) > 1:
        return None, (
            AMBIGUOUS_BINDING,
            f"{raw!r} khớp nhiều nhãn: {sorted(labels)}",
        )
    return next(iter(labels)), None


def _final_endpoint_id(label, raw, endpoint_ids):
    """Id THẬT trên cạnh, phải trùng id mà node mang.

    Nhãn resolver quản lý thì lấy đúng id cuối của B2; nhãn khác (LegalDocument,
    …) dùng `canon_id()` — cùng phép mà `add_node` của vendor đã đi qua sau khi
    `builder/__init__.py` gắn đè. Không được dựng một bộ danh tính thứ hai ở đây.
    """
    key = canon_id(raw)
    if label not in _MANAGED or endpoint_ids is None:
        # `endpoint_ids is None` chỉ xảy ra khi gọi trực tiếp ngoài pipeline
        # (unit test). Đường pipeline luôn truyền bản đồ B2.
        return key
    return endpoint_ids.get((label, key))


_ARTICLE_NO = re.compile(r"^Điều\s+(\d{1,3})\b", re.IGNORECASE)

# Nhãn mà resolver cấp id. Vendor KHÔNG được dựng node cho các nhãn này: nó dùng
# tên thô làm id, tức một danh tính cạnh tranh với danh tính đã phân giải.
_MANAGED = frozenset(("Article",) + SEMANTIC_CATEGORIES)


def _unresolved_article(chunk_id, name):
    # Runtime-scoped: không gộp tên mơ hồ xuyên chunk/document.
    return "article-unresolved:" + generate_hash_id(f"{chunk_id}|{canon_id(name)}")


def _article_ids(chunk, entities):
    """Một map duy nhất cho Article node và hai đầu semantic edge."""
    meta = chunk.kwargs
    doc_id = source_document_id(meta.get("source_path", ""))
    number = meta.get("article_no")
    heading = (meta.get("heading_path") or [chunk.name])[-1]
    source_id = (
        article_identity(doc_id, number)
        if doc_id and number and (int(number), heading) in source_article_headings(meta["source_path"])
        else None
    )
    ids = {}
    for entity in entities:
        if entity.get("category") != "Article":
            continue
        name = entity["name"]
        match = _ARTICLE_NO.match(name)
        same_number = source_id and match and int(match.group(1)) == int(number)
        qualifier = re.search(
            r"\b(?:Bộ luật|Luật|Nghị định|Thông tư|Quyết định)\s+.+$",
            name, re.IGNORECASE,
        )
        source_doc_name = (meta.get("heading_path") or [""])[0].split(" — ", 1)[0]
        qualified_source = bool(
            qualifier and source_doc_name
            and canon_id(qualifier.group()) == canon_id(source_doc_name)
        )
        # Nếu thân nhắc lại cùng số Điều, raw "Điều N" có thể là nguồn hoặc
        # dẫn chiếu. Triple không có vị trí mention nên giữ unresolved.
        cross_reference = bool(
            same_number and (
                re.search(rf"\bĐiều\s+{number}\b", chunk.content or "", re.IGNORECASE)
                or (qualifier and not qualified_source)
            )
        )
        source_heading = name.strip() == heading.strip()
        target = source_id if same_number and (source_heading or qualified_source or not cross_reference) else _unresolved_article(chunk.id, name)
        key = canon_id(name)
        # Hai tên chuẩn hóa như nhau nhưng suy ra hai đích khác nhau: giữ mơ hồ.
        if key in ids and ids[key] != target:
            target = _unresolved_article(chunk.id, key)
        ids[key] = target
    return source_id, heading, ids


def _same_unit_ambiguity(resolved, chunk_id, ids):
    """Nhiều tên khác nhau cùng rơi vào một occurrence nguồn -> cả nhóm mơ hồ.

    `semantic_identity()` chỉ trả lời "tên này định vị vào đơn vị nguồn nào"; nó
    không biết trong cùng lượt trích xuất còn tên nào khác cũng trỏ đúng đơn vị
    đó. Vì vậy phải quyết ở đây, SAU khi từng thực thể đã phân giải riêng.

    Khi hai tên chuẩn hóa KHÁC nhau cùng ra một id canonical, tầng danh tính
    không có bằng chứng nào phân biệt được hai khả năng:

        (1) hai cách gọi của cùng một occurrence — alias;
        (2) hai occurrence/nhóm con khác nhau trên cùng dòng nguồn.

    Không có alias tất định thì không được chọn (1) rồi gộp. `official_name` của
    LLM KHÔNG phải bằng chứng; thứ tự xuất hiện cũng không. Hạ cả nhóm về
    unresolved theo contract sẵn có: mỗi tên một id riêng, không `_1`/`_2`.

    Bất biến câu chữ NER không vỡ: phân giải RIÊNG từng tên vẫn cho cùng id
    canonical. Chỉ khi hai tên cùng có mặt một lượt mới thành mơ hồ cardinality.

    Authority nằm ngoài rule này (§4): danh tính của nó là tổ chức toàn cục, hai
    tên khác nhau về cùng một tổ chức là hợp nhất đúng, không phải mơ hồ.
    """
    groups = {}
    for key, target in resolved.items():
        groups.setdefault((key[0], target), []).append(key)
    downgraded = {}
    for (category, target), keys in groups.items():
        if len(keys) < 2:
            continue
        for key in keys:
            ids[key] = unresolved_identity(category, chunk_id, key[1])
            downgraded[key] = (
                f"{len(keys)} tên khác nhau cùng trỏ một đơn vị nguồn "
                f"({target}), không có bằng chứng alias tất định"
            )
    if downgraded:
        logger.warning(
            "hạ %d thực thể về unresolved vì trùng đơn vị nguồn ở chunk %s",
            len(downgraded), chunk_id,
        )
    return downgraded


def _endpoint_ids(chunk, entities):
    """MỘT bản đồ danh tính cho node và cho cả hai đầu mút cạnh.

    Khóa là ``(nhãn, canon_id(tên))`` vì id trên cạnh đã đi qua ``canon_id()``
    (``SubGraph.add_edge`` bị ``builder/__init__.py`` gắn đè). Article giữ nguyên
    đường B2.1; các nhãn B2.2 đi qua ``semantic_identity()``.

    Không có bản đồ dùng chung thì node và đầu mút cạnh tách thành hai danh tính
    cạnh tranh — đúng lỗi mà B2.1 đã sửa cho Article.
    """
    source_id, heading, article_ids = _article_ids(chunk, entities)
    ids = {("Article", key): target for key, target in article_ids.items()}
    meta = chunk.kwargs
    # Chỉ cấp occurrence khi Điều nguồn của chunk ĐÃ phân giải. Không có căn cứ
    # thì mọi thực thể phụ thuộc ngữ cảnh trong chunk đều unresolved.
    #
    # `clause_no`/`point_no` của splitter chỉ đi kèm làm hint đối chiếu. Resolver
    # tự quét Khoản/Điểm từ file nguồn, nên id canonical không đổi khi cấu hình
    # cắt chunk đổi. `chunk.id` chỉ dùng cho nhánh unresolved.
    anchor = {
        "source_path": meta.get("source_path", "") if source_id else "",
        "article_no": meta.get("article_no") if source_id else None,
        "clause_no": meta.get("clause_no"),
        "point_no": meta.get("point_no"),
    }
    reasons, resolved = {}, {}
    for entity in entities:
        category = entity.get("category")
        if category not in SEMANTIC_CATEGORIES:
            continue
        name = entity["name"]
        identity = semantic_identity(category, name, **anchor)
        target = identity.id or unresolved_identity(category, chunk.id, name)
        key = (category, canon_id(name))
        # Hai tên chuẩn hóa như nhau mà suy ra hai đích khác nhau: giữ mơ hồ.
        if key in ids and ids[key] != target:
            target = unresolved_identity(category, chunk.id, key[1])
        elif identity.id and category in CONTEXTUAL_CATEGORIES:
            resolved[key] = identity.id
        ids[key] = target
        reasons[key] = identity.reason
    for key, reason in _same_unit_ambiguity(resolved, chunk.id, ids).items():
        reasons[key] = reason
    if reasons:
        logger.debug("danh tính B2.2 của chunk %s: %s", chunk.id, reasons)
    return source_id, heading, ids


@ExtractorABC.register("legal_schema_free_extractor")
class LegalSchemaFreeExtractor(SchemaFreeExtractor):
    def _named_entity_recognition_process(self, passage, ner_result):
        """Lọc kết quả NER trước khi đưa cho lớp cha.

        ner_result đến thẳng từ LLM nên không tin được hình dạng của nó:

        - ``None``: ``llm_client.invoke(with_except=False)`` nuốt exception rồi
          rơi khỏi hàm. Hay gặp nhất khi output bị cắt cụt ("response is not
          intact, please set max_tokens") làm ``json.loads`` hỏng. Ném ra để
          ``@retry`` của tenacity trên ``named_entity_recognition`` gọi lại.
        - ``dict``: LLM bọc mảng trong một object, ví dụ ``{"entities": [...]}``.
        - phần tử thiếu ``category``: ``assemble_sub_graph_with_entities`` ném
          ``KeyError``, mà hàm đó KHÔNG nằm trong ``@retry`` nên chết cả file.
        """
        if ner_result is None:
            raise ValueError("NER trả về None (LLM lỗi hoặc JSON hỏng), thử lại")
        if isinstance(ner_result, dict):
            ner_result = next(
                (v for v in ner_result.values() if isinstance(v, list)), []
            )
        cleaned = []
        for item in ner_result:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            item["category"] = item.get("category") or "Others"
            cleaned.append(item)

        def category(value):
            return value if isinstance(value, str) and self.schema.get(value) is not None else "Others"

        output, seen = [], set()
        external = self.external_graph.ner(passage) if self.external_graph else []
        for node in external:
            label = category(node.label)
            key = (node.name, label)
            if key not in seen:
                seen.add(key)
                output.append({
                    "name": node.name,
                    "category": label,
                    "type": node.properties.get("semanticType", label),
                    "description": node.properties.get("desc", ""),
                })
        for item in cleaned:
            label = category(item["category"])
            key = (item["name"], label)
            if key not in seen:
                seen.add(key)
                item["category"] = label
                output.append(item)
        return output

    def assemble_sub_graph_with_spg_records(self, entities):
        # Vendor dựng node bằng TÊN THÔ, trước khi ngữ cảnh chunk được dùng. Với
        # các nhãn resolver quản lý thì đó là một danh tính cạnh tranh, phải bỏ.
        graph, _ = super().assemble_sub_graph_with_spg_records(
            [entity for entity in entities if entity.get("category") not in _MANAGED]
        )
        return graph, entities

    def assemble_sub_graph(self, sub_graph, chunk, entities, triples):
        source_id, heading, endpoint_ids = _endpoint_ids(chunk, entities)
        # Vendor cũng sinh node `official_name` cạnh node chính. Với nhãn resolver
        # quản lý, official_name chỉ là tên hiển thị/alias, không được thành một
        # danh tính thứ hai — nên các nhãn đó không đi qua đường này.
        self.assemble_sub_graph_with_entities(
            sub_graph, [entity for entity in entities if entity.get("category") not in _MANAGED]
        )
        for entity in entities:
            category = entity.get("category")
            if category not in _MANAGED:
                continue
            node_id = endpoint_ids[(category, canon_id(entity["name"]))]
            properties = {
                "desc": entity.get("description", ""),
                "semanticType": entity.get("type", ""),
            }
            if node_id == source_id:
                properties["articleNumber"] = str(chunk.kwargs["article_no"])
            sub_graph.add_node(node_id, entity["name"], category, properties)
        if source_id:
            sub_graph.add_node(source_id, heading, "Article", {
                "articleNumber": str(chunk.kwargs["article_no"]),
            })
        source_path = chunk.kwargs.get("source_path", "")
        # Provenance của CHUNK đang xử lý, không phải của đầu mút quan hệ.
        # `sourceArticleId` chỉ điền khi Điều nguồn của chunk đã phân giải tất
        # định; không suy Article từ endpoint của cạnh. `sourceDocumentId` suy từ
        # `source_path` (portable, B1.2), không lấy LegalDocument làm tân ngữ.
        provenance = {
            "sourceChunkId": chunk.id,
            "sourcePath": source_path,
            "sourceDocumentId": source_document_id(source_path),
            "sourceArticleId": source_id or "",
        }
        evidence = []
        self.assemble_sub_graph_with_triples(
            sub_graph, entities, triples, endpoint_ids, chunk.id,
            provenance=provenance, evidence=evidence,
        )
        self.assemble_sub_graph_with_chunk(sub_graph, chunk)
        if evidence:
            # Chunk node tự nó LÀ source occurrence của bằng chứng này, nên
            # không cần artifact ngoài và không lưu path tuyệt đối. Gắn sau khi
            # chunk node đã tồn tại: `add_node` ưu tiên properties đã có, ghi
            # trước sẽ bị chính nó bỏ qua.
            node = sub_graph.get_node_by_id(chunk.id, CHUNK_TYPE)
            if node is not None:
                node.properties["relationEvidence"] = evidence
            else:  # pragma: no cover - vendor luôn tạo node chunk
                logger.warning("không thấy node Chunk %s để ghi relationEvidence", chunk.id)
        return sub_graph

    @staticmethod
    def assemble_sub_graph_with_triples(
        sub_graph: SubGraph, entities: List[Dict], triples: List[list],
        endpoint_ids=None, chunk_id=None, provenance=None, evidence=None,
    ):
        """Dựng cạnh ngữ nghĩa theo hợp đồng quan hệ, KHÔNG qua lớp cha.

        Vì sao không gọi ``SchemaFreeExtractor.assemble_sub_graph_with_triples``
        nữa: lớp cha đặt ``edge_type = to_camel_case(tri[1])``, nghĩa là vị ngữ
        thô QUYẾT ĐỊNH nhãn quan hệ. Phép đó không khả nghịch (``cấm`` và ``căm``
        cùng ra ``cM``) và sinh nhãn ngoài schema (``quyNhNghAV``). Vá nhãn sau
        khi lớp cha đã tạo cạnh cũng không cứu được: vị ngữ không map được vẫn
        đã thành một cạnh rồi, mà hợp đồng B3 yêu cầu KHÔNG có cạnh nào cả.

        Đường tất định, đúng thứ tự:

        1. làm sạch triple thô (giữ hai bản sửa cũ, xem dưới);
        2. bind hai đầu mút -> nhãn NER;
        3. map vị ngữ thô -> tên quan hệ canonical (bảng tường minh);
        4. kiểm tuple ``(sourceType, relation, targetType)`` trong hợp đồng;
        5. phân giải id cuối theo bản đồ B2;
        6. thêm cạnh canonical trực tiếp.

        Trượt bất kỳ bước nào: KHÔNG sinh cạnh, không loại quan hệ tự do, không
        ``relatedTo``, không tự đảo chiều. Triple bị loại ghi vào ``evidence``
        (kết thúc ở property ``relationEvidence`` của Chunk) — loại có bằng
        chứng, không phải drop im lặng.

        Hai bản sửa cũ vẫn giữ vì vẫn là lỗi đầu vào:

        1. ``_invoke`` của KAG 0.8.0 viết
           ``triples = (self.triples_extraction(...),)`` — dấu phẩy thừa biến
           danh sách triple thành tuple một phần tử, chỉ lặp đúng một vòng rồi
           bỏ sạch quan hệ. Đường ``_ainvoke`` viết đúng nên không dính.
        2. Triple do LLM sinh có thể là ``None`` hoặc phần tử không phải bộ ba
           chuỗi.
        """
        if isinstance(triples, tuple) and len(triples) == 1:
            triples = triples[0]
        cleaned = [
            tri
            for tri in (triples or [])
            if isinstance(tri, list)
            and len(tri) == 3
            and all(isinstance(x, str) for x in tri)
        ]
        # Nhãn đầu mút LẤY TỪ NER, không suy từ tên. Không có entity thì không
        # có bằng chứng nhãn -> không kiểm được tuple -> loại.
        entity_labels = {}
        for entity in entities or []:
            if not isinstance(entity, dict) or not entity.get("name"):
                continue
            key = canon_id(entity["name"])
            if key:
                entity_labels.setdefault(key, set()).add(
                    entity.get("category") or OTHER_TYPE
                )

        meta = provenance or {}
        sink = evidence if evidence is not None else []
        for raw_s, raw_p, raw_o in cleaned:
            relation = _map_relation(raw_p)
            s_label, s_err = _bind_endpoint(raw_s, entity_labels)
            o_label, o_err = _bind_endpoint(raw_o, entity_labels)

            def reject(status, reason):
                entry = {
                    "rawSubject": raw_s,
                    "rawPredicate": raw_p,
                    "rawObject": raw_o,
                    "status": status,
                    "reason": reason,
                }
                # "nếu biết" theo đúng nghĩa: không bịa nhãn, không bịa quan hệ.
                if s_label:
                    entry["sourceType"] = s_label
                if o_label:
                    entry["targetType"] = o_label
                if relation:
                    entry["candidateRelation"] = relation
                sink.append(entry)

            if relation is None:
                # Gồm cả trường hợp vị ngữ thô là "source"/"OfficialName": quan
                # hệ hệ thống do KAG sinh, LLM nói ra thì KHÔNG phải quan hệ hợp lệ.
                reject(UNKNOWN_PREDICATE, f"{raw_p!r} không có trong bảng map tất định")
                continue
            if s_err or o_err:
                status, reason = s_err or o_err
                reject(status, reason)
                continue
            if (s_label, relation, o_label) not in RELATION_CONTRACT:
                reason = (
                    f"({s_label}, {relation}, {o_label}) không có trong hợp đồng"
                )
                if (o_label, relation, s_label) in RELATION_CONTRACT:
                    # Chiều ngược hợp lệ trong schema NHƯNG không tự đảo: chiều
                    # là một phần của fact, đảo hộ là bịa fact.
                    reason += "; chiều ngược tồn tại trong schema, không tự đảo"
                reject(INVALID_ENDPOINT_TYPES, reason)
                continue

            from_id = _final_endpoint_id(s_label, raw_s, endpoint_ids)
            to_id = _final_endpoint_id(o_label, raw_o, endpoint_ids)
            if not from_id or not to_id:
                missing = raw_s if not from_id else raw_o
                reject(
                    UNRESOLVED_ENDPOINT,
                    f"{missing!r} không có id cuối trong bản đồ danh tính B2",
                )
                continue

            properties = {
                # Vị ngữ GỐC của triple đang xử lý, không suy ngược từ nhãn cạnh.
                "originalPredicate": raw_p,
                "originalPredicateStatus": "RESOLVED",
                "relationMappingVersion": RELATION_MAPPING_VERSION,
                "predicateMappingVersion": PREDICATE_MAPPING_VERSION,
                # Cạnh mới CHƯA xác minh. Không bao giờ VERIFIED/FULL/human_verified.
                "evidenceStatus": "UNVERIFIED",
            }
            for field in ("sourceChunkId", "sourcePath", "sourceDocumentId"):
                if meta.get(field):
                    properties[field] = meta[field]
            # Chỉ điền khi Điều nguồn của CHUNK đã phân giải tất định. Không đoán
            # Article từ đầu mút cạnh.
            if meta.get("sourceArticleId"):
                properties["sourceArticleId"] = meta["sourceArticleId"]
            sub_graph.add_edge(from_id, s_label, relation, to_id, o_label, properties)

        if sink:
            logger.debug(
                "chunk %s: loại %d/%d triple, có bằng chứng trong relationEvidence",
                chunk_id, len(sink), len(cleaned),
            )
        return sub_graph
