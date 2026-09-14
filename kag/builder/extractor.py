# -*- coding: utf-8 -*-
"""Extractor vá ba lỗi của SchemaFreeExtractor trong KAG 0.8.0.

Ba lỗi này từng làm 11 trên 23 văn bản không dựng được đồ thị. Trước đây chúng
được sửa thẳng trong mã nguồn KAG, nghĩa là dự án chỉ chạy đúng trên đúng một
máy có bản KAG đã sửa. Chuyển vào đây thì KAG trở lại là thư viện pip bình
thường, ai clone repo về cũng chạy được.

Không chép lại thân hàm của lớp cha: cả ba chỗ đều làm sạch dữ liệu trước hoặc
sau khi gọi super(), nên bản KAG mới ra vẫn dùng được mà không phải so lại từng
dòng.
"""

import logging
from typing import Dict, List

from kag.interface import ExtractorABC
from kag.builder.component.extractor.schema_free_extractor import SchemaFreeExtractor
from kag.builder.model.sub_graph import SubGraph

logger = logging.getLogger(__name__)


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
        return SchemaFreeExtractor.assemble_sub_graph_with_triples(
            sub_graph, entities, cleaned
        )
