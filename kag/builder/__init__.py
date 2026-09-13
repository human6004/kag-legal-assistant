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
"""

# --- Vá lỗi: KAG băm nát tên thực thể tiếng Việt ---------------------------
#
# kag/common/utils.py:196 processing_phrases() thay MỌI ký tự ngoài
# [A-Za-z0-9 CJK] bằng dấu cách. schema_free_extractor.py:424 dùng kết quả làm
# CẢ id LẪN name của node, nên "Luật 116/2025/QH15" thành "lu t 116 2025 qh15".
# Phía solver không gọi hàm này (câu hỏi giữ dấu) và node nạp qua
# external_graph cũng không, nên hai bên không bao giờ gộp được với nhau.
#
# Vì sao gắn đè ở CẤP MODULE chứ không sửa kag.common.utils: to_camel_case()
# gọi bản gốc qua kag.common.utils và được dùng ở schema_free_extractor.py:358
# để sinh edge_type. Edge type phải thuần ASCII cho server nuốt được. Gắn đè
# cấp module giữ nguyên đường đó.
#
# File này CÓ chạy: indexer.py và injection.py gọi
# import_modules_from_path(kag/builder), hàm đó (kag/common/registry/utils.py:31)
# chèn kag/ vào sys.path rồi import_module("builder"), tức chính file này,
# dưới tên gọi `builder`. Thân hàm resolve biến global lúc gọi nên thứ tự
# import không quan trọng.
#
# Ghi chú: schema_constraint_extractor và knowledge_unit_extractor cũng dùng
# processing_phrases, nhưng kag_config.yaml đang chạy schema_free_extractor
# nên không va chạm ở đây.
import re as _re

from kag.builder.component.extractor import schema_free_extractor as _sfe


def _processing_phrases_giu_dau(phrase):
    r"""Như bản gốc nhưng giữ chữ có dấu: \w trong chế độ Unicode."""
    return _re.sub(r"[^\w ]", " ", str(phrase).lower(), flags=_re.U).strip()


_sfe.processing_phrases = _processing_phrases_giu_dau
