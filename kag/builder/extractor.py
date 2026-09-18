# -*- coding: utf-8 -*-
"""Extractor vá bốn lỗi của SchemaFreeExtractor trong KAG 0.8.0.

Ba lỗi đầu từng làm 11 trên 23 văn bản không dựng được đồ thị. Trước đây chúng
được sửa thẳng trong mã nguồn KAG, nghĩa là dự án chỉ chạy đúng trên đúng một
máy có bản KAG đã sửa. Chuyển vào đây thì KAG trở lại là thư viện pip bình
thường, ai clone repo về cũng chạy được.

Lỗi thứ tư (mới, giai đoạn 6): vị ngữ gốc do LLM trả bị mất.

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

Cách sửa: giữ nguyên `to_camel_case` cho edge type (đường đó đang chạy được,
đổi đi là phá 554 loại hiện có), nhưng ghi THÊM vị ngữ gốc vào properties của
cạnh: `original_predicate` và `predicate_mapping_version`. Writer đã ghi
properties cấp cạnh, nên không cần đổi schema hay tầng ghi.

Không gắn FULL/VERIFIED khi LLM trả triple: cạnh mới chỉ có
`evidence_status=UNVERIFIED`, provenance thật do tầng gọi bổ sung.

Không chép lại thân hàm của lớp cha: cả bốn chỗ đều làm sạch dữ liệu trước hoặc
sau khi gọi super(), nên bản KAG mới ra vẫn dùng được mà không phải so lại từng
dòng.
"""

import logging
from typing import Dict, List

from kag.interface import ExtractorABC
from kag.builder.component.extractor.schema_free_extractor import SchemaFreeExtractor
from kag.builder.model.sub_graph import SubGraph

logger = logging.getLogger(__name__)

# Phiên bản quy tắc ánh xạ vị ngữ -> edge type. Tăng khi đổi cách sinh type,
# để dữ liệu cũ biết nó thuộc quy tắc nào.
PREDICATE_MAPPING_VERSION = "camel_case_v1"

# Quan hệ do hệ thống sinh, không phải LLM trả. Không gắn original_predicate.
_SYSTEM_PREDICATES = {"source", "OfficialName"}


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
            item.setdefault("category", "Others")
            cleaned.append(item)
        return super()._named_entity_recognition_process(passage, cleaned)

    @staticmethod
    def assemble_sub_graph_with_triples(
        sub_graph: SubGraph, entities: List[Dict], triples: List[list]
    ):
        """Lọc triple trước khi lớp cha dựng cạnh.

        Hai lỗi khác nhau gộp vào một chỗ vì cùng sửa được ở đầu vào:

        1. ``_invoke`` của KAG 0.8.0 viết
           ``triples = (self.triples_extraction(...),)`` — dấu phẩy thừa biến
           danh sách triple thành tuple một phần tử, lớp cha lặp đúng một vòng
           rồi bỏ sạch quan hệ. Đường ``_ainvoke`` viết đúng nên không dính.
           Đây là lý do đồ thị từng chỉ có 38 quan hệ thay vì hơn 10.000.
        2. Triple do LLM sinh có thể là ``None`` hoặc phần tử không phải bộ ba
           chuỗi, lớp cha gọi ``processing_phrases`` lên đó là nổ.
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
        before = len(sub_graph.edges)
        # Lớp cha SỬA TẠI CHỖ `tri[0] = processing_phrases(tri[0])`
        # (schema_free_extractor.py:344), nên sau lời gọi đó vị ngữ gốc vẫn còn
        # nhưng ĐẦU MÚT đã mất dấu tiếng Việt. Phải chụp lại bản gốc TRƯỚC khi
        # gọi, nếu không thì không còn gì để đối chiếu hai đầu cạnh.
        snapshot = [list(tri) for tri in cleaned]
        result = SchemaFreeExtractor.assemble_sub_graph_with_triples(
            sub_graph, entities, cleaned
        )
        _attach_original_predicates(sub_graph, before, snapshot, entities)
        return result


def _attach_original_predicates(sub_graph, first_new_edge, cleaned_triples,
                                entities=None):
    """Ghi vị ngữ gốc của LLM vào properties cạnh.

    Vì sao phải làm ở đây: lớp cha gọi ``to_camel_case(tri[1])`` rồi vứt
    ``tri[1]`` đi. Sau lời gọi đó không còn chỗ nào lấy lại được vị ngữ gốc, mà
    phép biến đổi thì không khả nghịch (``cấm`` và ``căm`` cùng ra ``cM``).

    CÁCH KHỚP — đây là chỗ từng sai. Lớp cha bỏ một số triple (subject rỗng
    chẳng hạn), nên **không được zip theo vị trí**: chỉ cần mất một hàng ở đầu
    là mọi cạnh sau đó nhận vị ngữ của triple khác. Cũng **không được chọn ứng
    viên khớp đầu tiên** theo thứ tự, vì triple bị bỏ vẫn nằm trong danh sách
    ứng viên (nó chỉ không sinh cạnh) và sẽ cướp mất cạnh của triple thật.

    Bằng chứng dùng để khớp là **hai đầu cạnh thật**:

        cạnh.label        == to_camel_case(tri[1])
        cạnh.from_id      == processing_phrases(tri[0])
        cạnh.to_id        == processing_phrases(tri[2])

    Đầu nào không suy ra được id (triple có subject/object rỗng) thì KHÔNG
    tính là khớp: bỏ ứng viên đó. Đây là điểm mấu chốt — triple `['', 'cấm',
    'B']` có head rỗng nên id của nó không thể là `a`, vì vậy nó không được
    phép nhận cạnh `a -> b`. Chỉ nhận khi **mọi** đầu suy ra được đều trùng.

    Ứng viên được tiêu thụ theo thứ tự để hai triple giống nhau không dùng
    chung một cạnh. Cạnh không chứng minh được tương ứng thì **để trống** vị
    ngữ gốc và ghi ``originalPredicateStatus = UNRESOLVED`` — không đoán bừa,
    không lấy đại ứng viên còn lại.

    Vị ngữ gốc KHÔNG BAO GIỜ thay ``edge.label``. Edge type giữ nguyên.
    """
    from kag.common.utils import to_camel_case

    new_edges = sub_graph.edges[first_new_edge:]
    if not new_edges:
        return

    def _phrase(text):
        """Cùng phép biến đổi lớp cha dùng để sinh id nút."""
        from kag.common.utils import processing_phrases

        return processing_phrases(text) if isinstance(text, str) and text else None

    def _category_and_name(entity_name):
        """Bản sao của `get_category_and_name` trong lớp cha.

        Phải sao lại ĐÚNG logic này, vì id đầu cạnh không phải lúc nào cũng là
        `processing_phrases(tri[i])`:
          - nếu khớp một entity -> id là TÊN GỐC của entity (`s_name`);
          - nếu không khớp -> id là `processing_phrases(tri[0])`.
        Hai cách này cho hai id khác nhau, nên dùng sai là không chứng minh được.
        """
        from kag.common.utils import processing_phrases

        for ent in entities or []:
            if not isinstance(ent, dict) or not ent.get("name"):
                continue
            if processing_phrases(ent["name"]) == processing_phrases(entity_name):
                return ent["name"]
        return None

    def _final_id(raw_name):
        """Id THẬT SỰ xuất hiện trên cạnh, sau mọi tầng biến đổi.

        Quan trọng: `SubGraph.add_edge` bị `kag/builder/__init__.py` gắn đè để
        chạy `canon_id()` lên mọi id (trừ nhãn trong KEEP_ID). Nghĩa là id trên
        cạnh KHÔNG phải `s_name` thô mà là dạng đã chuẩn hoá, ví dụ
        'Điều 34 Nghị định 330/2026/NĐ-CP' -> 'điều 34 nghị định 330 2026 nđ cp'.
        Không áp đúng phép chuẩn hoá này thì không bao giờ khớp được hai đầu.
        """
        try:
            from builder.canon_id import canon_id, KEEP_ID
        except ImportError:
            return raw_name
        return raw_name if raw_name is None else canon_id(raw_name)

    # Ứng viên: mọi triple sinh được cạnh, kèm hai đầu ĐÃ biến đổi.
    candidates = []
    for tri in cleaned_triples:
        edge_type = to_camel_case(tri[1])
        if not edge_type:
            # Lớp cha bỏ triple có vị ngữ rỗng -> không sinh cạnh, không ứng viên.
            continue
        s_name = _category_and_name(tri[0]) or _phrase(tri[0])
        o_name = _category_and_name(tri[2]) or _phrase(tri[2])
        candidates.append({
            "edge_type": edge_type,
            "raw": tri[1],
            "head": _final_id(s_name),
            "tail": _final_id(o_name),
        })

    used = set()
    unresolved = 0
    for edge in new_edges:
        pick = None
        for i, c in enumerate(candidates):
            if i in used or c["edge_type"] != edge.label:
                continue
            # Cả hai đầu phải CHỨNG MINH được. Đầu rỗng ở triple nghĩa là
            # triple đó không thể sinh cạnh có id tương ứng -> loại.
            if not c["head"] or not c["tail"]:
                continue
            if c["head"] != edge.from_id or c["tail"] != edge.to_id:
                continue
            pick = i
            break

        props = dict(edge.properties or {})
        if pick is None:
            unresolved += 1
            # Không chứng minh được tương ứng -> KHÔNG gán vị ngữ nào cả.
            props.setdefault("originalPredicateStatus", "UNRESOLVED")
            props.setdefault("predicateMappingVersion", PREDICATE_MAPPING_VERSION)
            props.setdefault("evidenceStatus", "UNVERIFIED")
            edge.properties = props
            continue

        used.add(pick)
        if edge.label in _SYSTEM_PREDICATES:
            # Cạnh do hệ thống sinh, không phải fact của LLM.
            props.setdefault("originalPredicateStatus", "NOT_APPLICABLE")
            props.setdefault("predicateMappingVersion", PREDICATE_MAPPING_VERSION)
            props.setdefault("evidenceStatus", "UNVERIFIED")
            edge.properties = props
            continue
        # Không ghi đè nếu tầng trên đã đặt: tầng trên biết nhiều hơn.
        props.setdefault("originalPredicate", candidates[pick]["raw"])
        props.setdefault("originalPredicateStatus", "RESOLVED")
        props.setdefault("predicateMappingVersion", PREDICATE_MAPPING_VERSION)
        # Cạnh mới CHƯA được xác minh. Không gắn FULL/VERIFIED ở đây.
        props.setdefault("evidenceStatus", "UNVERIFIED")
        edge.properties = props

    if unresolved:
        logger.warning(
            "không chứng minh được vị ngữ gốc cho %d/%d cạnh mới; "
            "để trống originalPredicate thay vì gán theo thứ tự",
            unresolved,
            len(new_edges),
        )

