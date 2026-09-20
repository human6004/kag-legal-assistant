# -*- coding: utf-8 -*-
"""Loader đồ thị ngoài cho metadata văn bản.

Vì sao không dùng thẳng DefaultExternalGraphLoader: hàm __init__ của nó kiểm
tra thuộc tính bằng `k not in self.schema[node.label]`, mà BaseSpgType không
định nghĩa __contains__ / __iter__ nên dòng đó ném TypeError ngay khi node có
bất kỳ thuộc tính nào. Ví dụ domain_kg của KAG không dính lỗi này vì mọi
node của nó đều có properties rỗng.

Cách xử lý: tạm gỡ properties ra trước khi gọi super(), rồi tự kiểm tra lại
bằng spg_type.properties (cái này có thật) và gán trả về.

Lỗi thứ hai: ner() bản gốc tách từ bằng jieba, xem override bên dưới.
"""

from typing import List

from kag.interface import ExternalGraphLoaderABC, MatchConfig
from kag.builder.component.external_graph.external_graph import (
    DefaultExternalGraphLoader,
)
from kag.builder.model.sub_graph import Node, Edge


@ExternalGraphLoaderABC.register("legal_external_graph", constructor="from_json_file")
class LegalExternalGraphLoader(DefaultExternalGraphLoader):
    def __init__(
        self, nodes: List[Node], edges: List[Edge], match_config: MatchConfig, **kwargs
    ):
        saved = [node.properties for node in nodes]
        for node in nodes:
            node.properties = {}

        super().__init__(
            nodes=nodes, edges=edges, match_config=match_config, **kwargs
        )

        for node, properties in zip(self.nodes, saved):
            spg_type = self.schema[node.label]
            unknown = set(properties) - set(spg_type.properties)
            if unknown:
                raise ValueError(
                    f"Node {node.name} có thuộc tính ngoài schema: {sorted(unknown)}"
                )
            node.properties = properties

    def ner(self, content: str):
        """Bản gốc tách từ bằng jieba, mà jieba băm tiếng Việt ra từng ký tự.

        Do đó:
            jieba.cut("Nghị định 330/2026/NĐ-CP")
            -> ['Ngh', 'ị', ' ', 'đ', 'ị', 'nh', ' ', '330', '/', ...]
        nên không tên văn bản nào khớp được với vocabulary và ner() luôn trả về
        rỗng, bất kể __init__ đã jieba.add_word từng tên. Tên văn bản là chuỗi
        cố định nên quét chuỗi con là đủ, và không phụ thuộc bộ tách từ nào.

        30 node x ~1100 chunk. Chậm thì mới đổi sang Aho-Corasick.
        """
        return [node for name, node in self.vocabulary.items() if name in content]
