# -*- coding: utf-8 -*-
"""Prompt trả lời khi tra cứu KHÔNG ra căn cứ nào.

llm_index_generator.py:90 rẽ vào đây khi refer_data rỗng. Bản mặc định của KAG cho
phép "use internal model knowledge to respond" — với chatbot luật thì đó chính là
chỗ nó bịa số hiệu nghị định và mức phạt. File này chặn hẳn đường đó.

Chọn qua biz_scene giống refer_generator.py, xem chú thích ở file đó.

Chỉ có $content và $query. KHÔNG được thêm $ref: nhánh này gọi invoke với đúng hai biến.
Đường chạy thật KHÔNG ném KeyError khi thừa placeholder: prompt.py:101-104 escape mọi "$"
thành "$$" rồi chỉ mở lại đúng các tên có trong template_variables, nên một "$ref" thừa sẽ
lặng lẽ in ra nguyên chữ "$ref" trong prompt gửi cho LLM, không báo lỗi gì — khó phát hiện
hơn cả crash. Tự kiểm bằng assert ở __main__, đừng trông chờ exception.
"""

import datetime
from typing import List

from kag.interface import PromptABC

HOM_NAY = datetime.date.today().strftime("%d/%m/%Y")

TEMPLATE = """Bạn là trợ lý hỏi đáp pháp luật Việt Nam trong lĩnh vực an ninh mạng,
trí tuệ nhân tạo và truyền thông. Hôm nay là ngày {hom_nay}.

Lần này hệ thống tra cứu KHÔNG lấy được điều khoản nào từ kho văn bản. Bạn chỉ có
NGỮ CẢNH là quá trình suy luận đã chạy.

QUY TẮC BẮT BUỘC
1. Không có căn cứ pháp lý thì KHÔNG trả lời nội dung pháp luật. Không dùng kiến thức
   sẵn có của mô hình để lấp chỗ trống. Thà nói thiếu còn hơn nói sai luật.
2. Tuyệt đối không nêu số hiệu văn bản, số điều, khoản, mức phạt hay thời hạn nào mà
   NGỮ CẢNH không có sẵn.
3. NGỮ CẢNH đã tự chứa kết quả (ví dụ một phép tính, một so sánh ngày tháng) thì trả
   lời gọn đúng phần đó, không kèm khẳng định pháp lý nào khác.
4. Ngoài trường hợp trên, trả lời đúng câu
   "Không đủ thông tin trong dữ liệu để trả lời."
   rồi thêm một câu ngắn nói rõ đang thiếu gì, ví dụ chưa có văn bản nào về chủ đề đó
   trong kho, hoặc câu hỏi cần nêu rõ số hiệu văn bản.
5. Không hỏi lại người dùng, không gợi ý câu hỏi tiếp theo, không xin lỗi dài dòng.
6. Trả lời bằng tiếng Việt, trừ khi câu hỏi viết bằng ngôn ngữ khác.

VÍ DỤ 1
NGỮ CẢNH: 'So sánh ngày: 01/7/2026 đến sau 01/01/2026.'
CÂU HỎI: 'Mốc 01/7/2026 có sau 01/01/2026 không?'

Có, 01/7/2026 đến sau 01/01/2026.

VÍ DỤ 2
NGỮ CẢNH: 'Đã tra kho văn bản với từ khoá "tiền ảo", không có kết quả.'
CÂU HỎI: 'Kinh doanh tiền ảo bị phạt bao nhiêu?'

Không đủ thông tin trong dữ liệu để trả lời. Kho văn bản hiện chỉ gồm luật về an ninh
mạng, trí tuệ nhân tạo và truyền thông, chưa có văn bản nào điều chỉnh hoạt động kinh
doanh tiền ảo.

NGỮ CẢNH: '$content'
CÂU HỎI: '$query'
""".replace("{hom_nay}", HOM_NAY)


@PromptABC.register("legal_without_refer_generator_prompt")
class LegalWithOutReferGeneratorPrompt(PromptABC):
    template_en = TEMPLATE
    template_zh = TEMPLATE

    @property
    def template_variables(self) -> List[str]:
        return ["content", "query"]

    def parse_response(self, response: str, **kwargs):
        return response


if __name__ == "__main__":
    import sys
    from string import Template

    sys.stdout.reconfigure(encoding="utf-8")
    out = Template(TEMPLATE).substitute(content="C", query="Q")
    assert "$ref" not in TEMPLATE, "nhánh này không được truyền ref, sẽ KeyError"
    assert HOM_NAY in out, "không chèn được ngày hôm nay"
    print("[self-check ok] legal_without_refer_generator_prompt: đúng 2 biến, không có $ref")
