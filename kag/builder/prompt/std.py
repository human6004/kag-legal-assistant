# -*- coding: utf-8 -*-
"""Chuẩn hoá tên thực thể trong văn bản pháp luật Việt Nam.

Việc chính: quy các cách gọi tắt trong luật ("Nghị định này", "Điều này",
"Luật An ninh mạng", "Bộ Công an") về một tên chính thức duy nhất, để hai
chunk khác nhau nói về cùng một thứ thì nối được vào cùng một node.

parse_response giữ nguyên logic gốc: entity nào LLM bỏ sót thì lấy chính
name làm official_name rồi ghép trở lại.

official_name của văn bản BẮT BUỘC kèm số hiệu, để trùng đúng node_name() trong
kag/builder/metadata_to_graph.py. Trùng thì node OpenIE và node metadata gộp làm
một, node đó mang cả nội dung điều luật lẫn trạng thái hiệu lực. Tên gọi thường
("Luật An ninh mạng") không mất đi: schema_free_extractor.py:449 tự tạo node phụ
và cạnh OfficialName trỏ sang node chính, nên người dùng hỏi bằng tên thường vẫn
tra được.
"""

import json
from typing import List

from kag.interface import PromptABC


TEMPLATE = """
{
    "instruction": "Trường input chứa một đoạn văn bản pháp luật Việt Nam. Trường named_entities chứa các thực thể đã trích ra từ đoạn đó, trong đó nhiều tên là cách gọi tắt, đại từ chỉ định hoặc viết tắt. Nhiệm vụ của bạn là trả về tên chính thức của từng thực thể dựa vào ngữ cảnh đoạn văn và kiến thức pháp luật của bạn. Quy tắc: (1) Các cách gọi trỏ ngược như 'Nghị định này', 'Luật này', 'Thông tư này' phải thay bằng tên đầy đủ kèm số hiệu nếu đoạn văn hoặc tiêu đề có nêu, ví dụ 'Nghị định 330/2026/NĐ-CP'. (2) 'Điều này', 'Điều nêu trên' phải thay bằng số điều cụ thể. (3) Tên viết tắt của cơ quan phải viết đầy đủ, ví dụ 'Bộ TT&TT' thành 'Bộ Thông tin và Truyền thông'. (4) Tên viết tắt kỹ thuật giữ cả dạng đầy đủ, ví dụ 'AI' thành 'trí tuệ nhân tạo'. (5) Hành vi vi phạm và chế tài giữ nguyên câu chữ của luật, chỉ bỏ phần đánh số điểm khoản ở đầu như 'a)' hoặc 'điểm c khoản 2'. (6) Hai thực thể cùng nghĩa chỉ được có MỘT official_name giống hệt nhau. (7) Nếu không xác định được tên chính thức thì đặt official_name bằng đúng name ban đầu, không bỏ trống và không loại thực thể ra khỏi kết quả. (8) official_name của Luật, Nghị định, Thông tư, Quyết định BẮT BUỘC viết dạng '<loại văn bản> <số hiệu>', ví dụ 'Luật 116/2025/QH15', 'Nghị định 330/2026/NĐ-CP'. Số hiệu phải lấy từ chính đoạn văn hoặc từ tiêu đề văn bản, TUYỆT ĐỐI không tự bịa; không có căn cứ thì giữ nguyên tên gọi ban đầu. Giữ nguyên trường category của từng thực thể. Chỉ trả về một chuỗi JSONArray theo đúng định dạng trường output trong ví dụ, không giải thích thêm.",
    "example": {
        "input": "Điều 34. Vi phạm quy định về xác thực, định danh, bảo mật tài khoản số. 2. Phạt tiền từ 30.000.000 đồng đến 50.000.000 đồng đối với một trong các hành vi sau đây: c) Sử dụng công nghệ trí tuệ nhân tạo (AI), Deepfake hoặc các biện pháp kỹ thuật công nghệ cao để giả mạo dữ liệu sinh trắc học nhằm xác thực tài khoản trái phép. 3. Biện pháp khắc phục hậu quả: Buộc khôi phục lại tình trạng ban đầu đối với hành vi vi phạm quy định tại khoản 1, 2 Điều này. Việc xử phạt thực hiện theo Nghị định này và Luật An ninh mạng số 116/2025/QH15; Bộ Công an chịu trách nhiệm hướng dẫn thi hành.",
        "named_entities": [
            {"name": "Điều 34", "category": "Article"},
            {"name": "Điều này", "category": "Article"},
            {"name": "Nghị định này", "category": "LegalDocument"},
            {"name": "Luật An ninh mạng", "category": "LegalDocument"},
            {"name": "Bộ Công an", "category": "Authority"},
            {"name": "AI", "category": "LegalTerm"},
            {"name": "dữ liệu sinh trắc học", "category": "LegalTerm"},
            {"name": "c) Sử dụng công nghệ trí tuệ nhân tạo (AI), Deepfake để giả mạo dữ liệu sinh trắc học", "category": "ProhibitedAct"},
            {"name": "Phạt tiền từ 30.000.000 đồng đến 50.000.000 đồng", "category": "Sanction"},
            {"name": "Buộc khôi phục lại tình trạng ban đầu", "category": "Sanction"}
        ],
        "output": [
            {
                "name": "Điều 34",
                "category": "Article",
                "official_name": "Điều 34 Nghị định 330/2026/NĐ-CP"
            },
            {
                "name": "Điều này",
                "category": "Article",
                "official_name": "Điều 34 Nghị định 330/2026/NĐ-CP"
            },
            {
                "name": "Nghị định này",
                "category": "LegalDocument",
                "official_name": "Nghị định 330/2026/NĐ-CP"
            },
            {
                "name": "Luật An ninh mạng",
                "category": "LegalDocument",
                "official_name": "Luật 116/2025/QH15"
            },
            {
                "name": "Bộ Công an",
                "category": "Authority",
                "official_name": "Bộ Công an"
            },
            {
                "name": "AI",
                "category": "LegalTerm",
                "official_name": "trí tuệ nhân tạo"
            },
            {
                "name": "dữ liệu sinh trắc học",
                "category": "LegalTerm",
                "official_name": "dữ liệu sinh trắc học"
            },
            {
                "name": "c) Sử dụng công nghệ trí tuệ nhân tạo (AI), Deepfake để giả mạo dữ liệu sinh trắc học",
                "category": "ProhibitedAct",
                "official_name": "Sử dụng công nghệ trí tuệ nhân tạo (AI), Deepfake để giả mạo dữ liệu sinh trắc học nhằm xác thực tài khoản trái phép"
            },
            {
                "name": "Phạt tiền từ 30.000.000 đồng đến 50.000.000 đồng",
                "category": "Sanction",
                "official_name": "Phạt tiền từ 30.000.000 đồng đến 50.000.000 đồng"
            },
            {
                "name": "Buộc khôi phục lại tình trạng ban đầu",
                "category": "Sanction",
                "official_name": "Buộc khôi phục lại tình trạng ban đầu"
            }
        ]
    },
    "input": "$input",
    "named_entities": $named_entities
}
"""


@PromptABC.register("legal_std")
class LegalEntityStandardizationPrompt(PromptABC):
    template_en = TEMPLATE
    template_zh = TEMPLATE

    @property
    def template_variables(self) -> List[str]:
        return ["input", "named_entities"]

    def parse_response(self, response: str, **kwargs):
        rsp = response
        if isinstance(rsp, str):
            rsp = json.loads(rsp)
        if isinstance(rsp, dict) and "output" in rsp:
            rsp = rsp["output"]
        if isinstance(rsp, dict) and "named_entities" in rsp:
            standardized_entity = rsp["named_entities"]
        else:
            standardized_entity = rsp
        entities_with_offical_name = set()
        merged = []
        entities = kwargs.get("named_entities", [])

        # dau vao khong thong nhat cau truc, xu ly ca hai dang
        if "entities" in entities:
            entities = entities["entities"]
        if isinstance(entities, dict):
            _entities = []
            for category in entities:
                _e = entities[category]
                if isinstance(_e, list):
                    for _e2 in _e:
                        _entities.append({"name": _e2, "category": category})
                elif isinstance(_e, str):
                    _entities.append({"name": _e, "category": category})
                else:
                    pass

        for entity in standardized_entity:
            merged.append(entity)
            entities_with_offical_name.add(entity["name"])
        # phong khi llm bo sot thuc the
        for entity in entities:
            if "name" in entity and entity["name"] not in entities_with_offical_name:
                entity["official_name"] = entity["name"]
                merged.append(entity)
        return merged
