# -*- coding: utf-8 -*-
"""Trích quan hệ ba ngôi cho văn bản pháp luật Việt Nam.

Extractor dựng cạnh đồ thị từ [chủ ngữ, vị ngữ, tân ngữ]. Vị ngữ để tự do thì
mỗi chunk sinh một cách gọi khác nhau và đồ thị vỡ vụn, nên prompt ép dùng ĐÚNG
tên quan hệ canonical trong Legal.schema.

B3: bỏ lối thoát "quan hệ ngoài danh sách thì đặt vị ngữ tự do". Extractor không
còn sinh nhãn từ vị ngữ thô; vị ngữ nào không nằm trong hợp đồng quan hệ là bị
loại kèm bằng chứng, nên vị ngữ tự do chỉ tạo rác chứ không tạo cạnh. Prompt
liệt kê luôn cả kiểu hai đầu mút vì hợp đồng kiểm tuple
``(kiểu chủ ngữ, quan hệ, kiểu tân ngữ)``, không chỉ kiểm tên quan hệ.

Prompt cũng phải đòi CẢ HAI đầu mút nằm trong ``entity_list``: extractor bind cả
chủ ngữ lẫn tân ngữ vào thực thể NER, đầu nào không bind được thì cả bộ ba bị
loại. Luật cũ "ít nhất một thực thể" dạy model sinh đúng thứ validator loại.
Ví dụ trong prompt chỉ được chứa quan hệ mà chính đoạn input nói ra — ví dụ
schema-valid nhưng không có trong text dạy model bịa fact.
"""

import json
from typing import List

from kag.interface import PromptABC


TEMPLATE = """
{
    "instruction": "Bạn là chuyên gia trích xuất quan hệ từ văn bản pháp luật Việt Nam. Từ đoạn văn trong trường input, hãy liệt kê mọi quan hệ có thể rút ra dưới dạng bộ ba [chủ ngữ, quan hệ, tân ngữ] và trả về theo đúng định dạng của trường output trong ví dụ. Yêu cầu: (1) CẢ chủ ngữ VÀ tân ngữ phải là thực thể có tên trong entity_list. Phải viết tên y hệt trong entity_list. Nếu một trong hai đầu không có trong entity_list thì KHÔNG sinh bộ ba đó. (2) Thay mọi đại từ và cách gọi trỏ ngược như 'Điều này', 'Nghị định này' bằng tên cụ thể. (3) Vị trí quan hệ CHỈ được nhận đúng một trong các tên sau, viết y hệt từng chữ và từng chữ hoa, không dịch, không thêm dấu, không đặt từ đồng nghĩa. Mỗi tên chỉ dùng được đúng cặp kiểu thực thể ghi kèm, lấy kiểu từ trường category trong entity_list: 'supersedes' LegalDocument thay thế LegalDocument; 'supersededBy' LegalDocument bị thay thế bởi LegalDocument; 'amends' LegalDocument sửa đổi bổ sung LegalDocument; 'implementsDoc' LegalDocument hướng dẫn thi hành LegalDocument; 'belongsTo' Article thuộc LegalDocument; 'prohibits' Article nghiêm cấm ProhibitedAct; 'imposes' Article quy định chế tài Sanction; 'obliges' Article quy định nghĩa vụ Obligation; 'defines' Article định nghĩa LegalTerm; 'appliesTo' Article áp dụng cho RegulatedEntity; 'prohibitedBy' ProhibitedAct bị cấm theo Article; 'sanctionedBy' ProhibitedAct bị xử phạt theo Sanction; 'forAct' Sanction áp dụng cho hành vi ProhibitedAct; 'basedOn' Sanction hoặc Obligation có căn cứ pháp lý là Article; 'enforcedBy' Sanction do Authority có thẩm quyền xử phạt; 'boundEntity' Obligation ràng buộc RegulatedEntity; 'definedIn' LegalTerm được định nghĩa tại Article. (4) Chỉ dùng quan hệ trong danh sách trên; nếu không có quan hệ nào phù hợp, hoặc kiểu hai đầu không đúng cặp kiểu ghi kèm, thì KHÔNG sinh bộ ba đó. Không đặt vị ngữ tự do, không tự đảo chiều quan hệ. (5) Không suy diễn quan hệ mà đoạn văn không nói. Nếu không có quan hệ nào thì trả về danh sách rỗng. Chỉ trả về một chuỗi JSON, không giải thích thêm.",
    "entity_list": $entity_list,
    "input": "$input",
    "example": {
        "input": "Điều 34. Vi phạm quy định về xác thực, định danh, bảo mật tài khoản số\\n2. Phạt tiền từ 30.000.000 đồng đến 50.000.000 đồng đối với một trong các hành vi sau đây: c) Sử dụng công nghệ trí tuệ nhân tạo (AI), Deepfake hoặc các biện pháp kỹ thuật công nghệ cao để giả mạo dữ liệu sinh trắc học (khuôn mặt, giọng nói) nhằm xác thực tài khoản trái phép.\\n3. Biện pháp khắc phục hậu quả: Buộc khôi phục lại tình trạng ban đầu đối với hành vi vi phạm quy định tại khoản 1, 2 Điều này. Việc xử phạt do lực lượng chuyên trách bảo vệ an ninh mạng thực hiện. Nghị định 330/2026/NĐ-CP quy định chi tiết thi hành Luật An ninh mạng.",
        "entity_list": [
            {"name": "Điều 34 Nghị định 330/2026/NĐ-CP", "category": "Article"},
            {"name": "Nghị định 330/2026/NĐ-CP", "category": "LegalDocument"},
            {"name": "Luật An ninh mạng", "category": "LegalDocument"},
            {"name": "Sử dụng công nghệ trí tuệ nhân tạo (AI), Deepfake để giả mạo dữ liệu sinh trắc học nhằm xác thực tài khoản trái phép", "category": "ProhibitedAct"},
            {"name": "Phạt tiền từ 30.000.000 đồng đến 50.000.000 đồng", "category": "Sanction"},
            {"name": "Buộc khôi phục lại tình trạng ban đầu", "category": "Sanction"},
            {"name": "dữ liệu sinh trắc học", "category": "LegalTerm"},
            {"name": "lực lượng chuyên trách bảo vệ an ninh mạng", "category": "Authority"}
        ],
        "output": [
            ["Điều 34 Nghị định 330/2026/NĐ-CP", "belongsTo", "Nghị định 330/2026/NĐ-CP"],
            ["Điều 34 Nghị định 330/2026/NĐ-CP", "prohibits", "Sử dụng công nghệ trí tuệ nhân tạo (AI), Deepfake để giả mạo dữ liệu sinh trắc học nhằm xác thực tài khoản trái phép"],
            ["Điều 34 Nghị định 330/2026/NĐ-CP", "imposes", "Phạt tiền từ 30.000.000 đồng đến 50.000.000 đồng"],
            ["Điều 34 Nghị định 330/2026/NĐ-CP", "imposes", "Buộc khôi phục lại tình trạng ban đầu"],
            ["Phạt tiền từ 30.000.000 đồng đến 50.000.000 đồng", "forAct", "Sử dụng công nghệ trí tuệ nhân tạo (AI), Deepfake để giả mạo dữ liệu sinh trắc học nhằm xác thực tài khoản trái phép"],
            ["Phạt tiền từ 30.000.000 đồng đến 50.000.000 đồng", "basedOn", "Điều 34 Nghị định 330/2026/NĐ-CP"],
            ["Phạt tiền từ 30.000.000 đồng đến 50.000.000 đồng", "enforcedBy", "lực lượng chuyên trách bảo vệ an ninh mạng"],
            ["Buộc khôi phục lại tình trạng ban đầu", "forAct", "Sử dụng công nghệ trí tuệ nhân tạo (AI), Deepfake để giả mạo dữ liệu sinh trắc học nhằm xác thực tài khoản trái phép"],
            ["Nghị định 330/2026/NĐ-CP", "implementsDoc", "Luật An ninh mạng"]
        ]
    }
}
"""


@PromptABC.register("legal_triple")
class LegalTriplePrompt(PromptABC):
    template_en = TEMPLATE
    template_zh = TEMPLATE

    @property
    def template_variables(self) -> List[str]:
        return ["entity_list", "input"]

    def parse_response(self, response: str, **kwargs):
        rsp = response
        if isinstance(rsp, str):
            rsp = json.loads(rsp)
        if isinstance(rsp, dict) and "output" in rsp:
            rsp = rsp["output"]
        if isinstance(rsp, dict) and "triples" in rsp:
            triples = rsp["triples"]
        else:
            triples = rsp

        standardized_triples = []
        for triple in triples:
            if isinstance(triple, list):
                standardized_triples.append(triple)
            elif isinstance(triple, dict):
                s = triple.get("subject")
                p = triple.get("predicate")
                o = triple.get("object")
                if s and p and o:
                    standardized_triples.append([s, p, o])

        return standardized_triples
