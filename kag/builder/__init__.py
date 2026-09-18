# Copyright 2023 OpenSPG Authors
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except
# in compliance with the License. You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License
# is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
# or implied.

"""
Builder Dir.

Vá hai lỗi của KAG 0.8.0 làm đồ thị pháp luật không dùng được. Cả hai đều gắn
đè ở cấp module chứ không sửa vendor/KAG, để KAG vẫn là thư viện pip bình thường.

File này CÓ chạy: indexer.py và injection.py gọi
import_modules_from_path(kag/builder), hàm đó (kag/common/registry/utils.py:31)
chèn kag/ vào sys.path rồi import_module("builder"), tức chính file này, dưới
tên gọi `builder`. Thân hàm resolve biến global lúc gọi nên thứ tự import không
quan trọng.

1. processing_phrases băm nát tên tiếng Việt
--------------------------------------------
kag/common/utils.py:196 thay MỌI ký tự ngoài [A-Za-z0-9 CJK] bằng dấu cách, nên
"Luật 116/2025/QH15" thành "lu t 116 2025 qh15". Phía solver không gọi hàm này
(câu hỏi giữ dấu) và node nạp qua external_graph cũng không, nên hai bên không
bao giờ gộp được với nhau.

Vì sao gắn đè ở CẤP MODULE chứ không sửa kag.common.utils: to_camel_case() gọi
bản gốc qua kag.common.utils và được dùng ở schema_free_extractor.py:358 để sinh
edge_type. Edge type phải thuần ASCII cho server nuốt được. Gắn đè cấp module
giữ nguyên đường đó.

Ghi chú: schema_constraint_extractor và knowledge_unit_extractor cũng dùng
processing_phrases, nhưng kag_config.yaml đang chạy schema_free_extractor nên
không va chạm ở đây.

2. Mỗi thực thể bị ghi thành hai node
-------------------------------------
schema_free_extractor ghi mỗi thực thể hai lần vào cùng một subgraph, một lần
bằng tên thô (:302, :312) và một lần bằng processing_phrases(name) (:424). Hai
id khác nhau nên SubGraph.add_node không gộp, và node thô mới là node giữ quan
hệ. Đo trên đồ thị thử 121 chunk: Obligation 419 node = 169 thô + 250 vỏ rỗng;
LegalDocument 92 node cho 30 văn bản. Sửa ở add_node/add_edge chứ không sửa
từng chỗ gọi: mọi đường ghi đều đi qua hai hàm đó.

Quy tắc id nằm ở kag/builder/canon_id.py, dùng chung với metadata_to_graph.py.
"""

from kag.builder.component.extractor import schema_free_extractor as _sfe
from kag.builder.model.sub_graph import SubGraph as _SubGraph

from .canon_id import KEEP_ID as _KEEP_ID
from .canon_id import canon_id as _canon_id
from .canon_id import slug as _slug


def _processing_phrases_giu_dau(phrase):
    r"""Như bản gốc nhưng giữ chữ có dấu: \w trong chế độ Unicode."""
    return _slug(phrase)


_sfe.processing_phrases = _processing_phrases_giu_dau


def _id_chuan(node_id, label):
    """id do tầng reader sinh ra (băm) thì giữ nguyên, còn lại quy về id chuẩn."""
    label = str(label).split(".")[-1]
    if label in _KEEP_ID or (label == "Article" and str(node_id).startswith(("article:", "article-unresolved:"))):
        return node_id
    return _canon_id(node_id)


_add_node = _SubGraph.add_node
_add_edge = _SubGraph.add_edge


def _add_node_chuan(self, id, name, label, properties=None):
    return _add_node(self, _id_chuan(id, label), name, label, properties)


def _add_edge_chuan(self, s_id, s_label, p, o_id, o_label, properties=None):
    return _add_edge(
        self,
        _id_chuan(s_id, s_label),
        s_label,
        p,
        _id_chuan(o_id, o_label),
        o_label,
        properties,
    )


_SubGraph.add_node = _add_node_chuan
_SubGraph.add_edge = _add_edge_chuan
