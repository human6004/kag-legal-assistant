# -*- coding: utf-8 -*-
"""Nhận diện thực thể cho văn bản pháp luật Việt Nam.

SchemaFreeExtractor đọc đúng 4 trường của mỗi thực thể:
  name        -> id + name của node
  category    -> nhãn node, PHẢI trùng một kiểu trong schema, sai thì bị đẩy về Others
  type        -> thuộc tính semanticType (tự do)
  description -> thuộc tính desc (được vector hoá để tìm kiếm)
"""

import json
from string import Template
from typing import List

from kag.interface import PromptABC
from knext.schema.client import SchemaClient
from knext.schema.model.base import SpgTypeEnum


TEMPLATE = """
{
    "instruction": "Bạn là chuyên gia trích xuất thực thể từ văn bản pháp luật Việt Nam về an ninh mạng, bảo vệ dữ liệu cá nhân, báo chí và truyền thông. Đọc đoạn văn trong trường input và liệt kê mọi thực thể quan trọng. Mỗi thực thể trả về 4 trường: name là tên gọi giữ nguyên chữ của văn bản, type là loại chi tiết dạng tự do ví dụ Nghị định hoặc Điều luật hoặc Phạt tiền, category BẮT BUỘC chọn đúng một tên có trong danh sách schema bên dưới và không được bịa tên mới, description là mô tả ngắn gọn dựa trên chính đoạn văn. Quy tắc riêng cho văn bản luật: (1) Mỗi hành vi bị cấm hoặc bị xử phạt là một thực thể riêng với category ProhibitedAct, đặt name là cụm động từ mô tả hành vi, tuyệt đối không đặt name là 'điểm c' hay 'khoản 2'. (2) Mỗi mức phạt tiền, hình thức xử phạt bổ sung, biện pháp khắc phục hậu quả là một thực thể category Sanction, giữ nguyên con số và đơn vị tiền. (3) Nghĩa vụ, trách nhiệm phải làm dùng category Obligation. (4) Tên văn bản như Luật, Nghị định, Thông tư dùng category LegalDocument và name phải kèm số hiệu nếu đoạn văn có nêu. (5) Điều luật dùng category Article, name theo dạng 'Điều 34'. (6) Cơ quan nhà nước, lực lượng có thẩm quyền dùng category Authority. (7) Tổ chức, cá nhân, doanh nghiệp bị điều chỉnh dùng category RegulatedEntity. (8) Thuật ngữ được luật định nghĩa dùng category LegalTerm. (9) Chỉ khi không xếp được vào nhóm nào mới dùng Others. Nếu đoạn văn không có thực thể nào thì trả về danh sách rỗng. Chỉ trả về một chuỗi JSON, không giải thích thêm.",
    "schema": $schema,
    "example": [
        {
            "input": "Điều 34. Vi phạm quy định về xác thực, định danh, bảo mật tài khoản số\\n1. Phạt tiền từ 20.000.000 đồng đến 30.000.000 đồng đối với một trong các hành vi sau đây: c) Không lưu trữ thông tin thiết bị, địa chỉ IP, thời gian đăng nhập của tài khoản số tối thiểu 90 ngày; d) Không tạm dừng giao dịch hoặc phong tỏa tài khoản số khi phát hiện có sai sót, bị lộ lọt thông tin hoặc khi có thông báo, yêu cầu của lực lượng chuyên trách bảo vệ an ninh mạng.\\n2. Phạt tiền từ 30.000.000 đồng đến 50.000.000 đồng đối với một trong các hành vi sau đây: c) Sử dụng công nghệ trí tuệ nhân tạo (AI), Deepfake hoặc các biện pháp kỹ thuật công nghệ cao để giả mạo dữ liệu sinh trắc học (khuôn mặt, giọng nói) nhằm xác thực tài khoản trái phép.\\n3. Biện pháp khắc phục hậu quả: Buộc khôi phục lại tình trạng ban đầu đối với hành vi vi phạm quy định tại khoản 1, 2 Điều này.",
            "output": [
                {
                    "name": "Điều 34",
                    "type": "Điều luật",
                    "category": "Article",
                    "description": "Điều khoản quy định xử phạt vi phạm về xác thực, định danh và bảo mật tài khoản số."
                },
                {
                    "name": "Sử dụng công nghệ trí tuệ nhân tạo (AI), Deepfake để giả mạo dữ liệu sinh trắc học nhằm xác thực tài khoản trái phép",
                    "type": "Hành vi bị xử phạt",
                    "category": "ProhibitedAct",
                    "description": "Dùng AI hoặc Deepfake làm giả khuôn mặt, giọng nói để vượt qua bước xác thực tài khoản số khi không được phép."
                },
                {
                    "name": "Không lưu trữ thông tin thiết bị, địa chỉ IP, thời gian đăng nhập của tài khoản số tối thiểu 90 ngày",
                    "type": "Hành vi bị xử phạt",
                    "category": "ProhibitedAct",
                    "description": "Không giữ nhật ký thiết bị, IP và thời điểm đăng nhập của tài khoản số đủ thời hạn 90 ngày."
                },
                {
                    "name": "Phạt tiền từ 30.000.000 đồng đến 50.000.000 đồng",
                    "type": "Phạt tiền",
                    "category": "Sanction",
                    "description": "Mức phạt tiền áp dụng cho nhóm hành vi gian dối khi xác thực tài khoản số, trong đó có hành vi dùng AI và Deepfake."
                },
                {
                    "name": "Phạt tiền từ 20.000.000 đồng đến 30.000.000 đồng",
                    "type": "Phạt tiền",
                    "category": "Sanction",
                    "description": "Mức phạt tiền áp dụng cho nhóm hành vi thiếu sót trong lưu trữ và bảo mật tài khoản số."
                },
                {
                    "name": "Buộc khôi phục lại tình trạng ban đầu",
                    "type": "Biện pháp khắc phục hậu quả",
                    "category": "Sanction",
                    "description": "Biện pháp khắc phục hậu quả áp dụng kèm theo các mức phạt tiền tại khoản 1 và khoản 2."
                },
                {
                    "name": "Lưu trữ thông tin thiết bị, địa chỉ IP, thời gian đăng nhập tối thiểu 90 ngày",
                    "type": "Nghĩa vụ lưu trữ dữ liệu",
                    "category": "Obligation",
                    "description": "Nghĩa vụ giữ nhật ký đăng nhập của tài khoản số ít nhất 90 ngày."
                },
                {
                    "name": "tài khoản số",
                    "type": "Thuật ngữ pháp lý",
                    "category": "LegalTerm",
                    "description": "Tài khoản được tạo lập trên không gian mạng, thuộc phạm vi điều chỉnh của quy định về xác thực và định danh."
                },
                {
                    "name": "dữ liệu sinh trắc học",
                    "type": "Thuật ngữ pháp lý",
                    "category": "LegalTerm",
                    "description": "Dữ liệu về đặc điểm sinh học của cá nhân như khuôn mặt, giọng nói, dùng để xác thực danh tính."
                },
                {
                    "name": "lực lượng chuyên trách bảo vệ an ninh mạng",
                    "type": "Lực lượng có thẩm quyền",
                    "category": "Authority",
                    "description": "Lực lượng nhà nước có thẩm quyền yêu cầu tạm dừng giao dịch hoặc phong tỏa tài khoản số."
                },
                {
                    "name": "chủ sở hữu tài khoản số",
                    "type": "Đối tượng bị điều chỉnh",
                    "category": "RegulatedEntity",
                    "description": "Người đứng tên tài khoản số, đối tượng được bảo vệ bởi nghĩa vụ cảnh báo và phong tỏa."
                }
            ]
        }
    ],
    "input": "$input"
}
"""


@PromptABC.register("legal_ner")
class LegalNERPrompt(PromptABC):
    template_en = TEMPLATE
    template_zh = TEMPLATE

    def __init__(self, language: str = "", **kwargs):
        super().__init__(language, **kwargs)
        project_schema = SchemaClient(
            host_addr=self.kag_project_config.host_addr,
            project_id=self.kag_project_config.project_id,
        ).load()
        self.schema = []
        for name, value in project_schema.items():
            # bỏ các kiểu index, chúng không phải nhãn thực thể
            if value.spg_type_enum != SpgTypeEnum.Index:
                self.schema.append(name)

        self.template = Template(self.template).safe_substitute(
            schema=json.dumps(self.schema, ensure_ascii=False)
        )

    @property
    def template_variables(self) -> List[str]:
        return ["input"]

    def parse_response(self, response: str, **kwargs):
        rsp = response
        if isinstance(rsp, str):
            rsp = json.loads(rsp)
        if isinstance(rsp, dict) and "output" in rsp:
            rsp = rsp["output"]
        if isinstance(rsp, dict) and "named_entities" in rsp:
            entities = rsp["named_entities"]
        else:
            entities = rsp
        return entities
