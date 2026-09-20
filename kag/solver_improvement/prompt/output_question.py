# -*- coding: utf-8 -*-
"""Prompt trả lời cho node Output (bước "xuất kết quả"), bản tiếng Việt miền pháp luật.

Thay cho default_output_question của KAG. Bản mặc định mở đường cho mô hình bịa: mục 4
của nó ghi "If the context is empty, respond based on the model's internal knowledge",
và mục 5 ép một khuôn câu "tôi nghĩ xxx, rồi yyy" — với trợ lý luật thì đó là công thức
sinh số hiệu nghị định và mức phạt không có trong dữ liệu.

AI GỌI
  kag/solver/executor/deduce/kag_output_executor.py:54
    init_prompt_with_fallback("output_question", biz_scene) -> chọn qua biz_scene.
    Được bật trong kag_config.yaml: kag_solver_pipeline.executors có
    kag_output_executor.
  invoke() ở dòng 98 truyền đúng hai biến: {"question": query, "context": dep_context}
  với with_json_parse=False, nên kết quả trả về ở dạng văn bản thuần.

Không cần sửa kag_config.yaml cho file này.
"""

from typing import List

from kag.interface import PromptABC

TEMPLATE = """Hãy trả lời câu hỏi "$question" dựa trên các đoạn văn bản luật tra được trong
phần NGỮ CẢNH, kết hợp với thông tin ở các bước trước.

YÊU CẦU
1. Không nhắc lại nguyên văn nội dung câu hỏi.
2. Trả lời bằng thông tin có trong NGỮ CẢNH. Nếu có nhiều khả năng thì nêu hết.
3. Không bịa số hiệu văn bản, số điều, khoản, mức phạt hay thời hạn. Giữ nguyên mọi con
   số và số hiệu như trong NGỮ CẢNH, không diễn nôm con số.
4. NGỮ CẢNH rỗng hoặc không đủ để trả lời thì viết đúng câu
   "Không đủ thông tin trong dữ liệu để trả lời."
   rồi nói ngắn gọn còn thiếu gì. TUYỆT ĐỐI không dùng kiến thức sẵn có của mô hình để
   lấp chỗ trống.
5. Trả lời thẳng vào câu hỏi, giải thích sau nếu cần. Văn phong tự nhiên, không máy móc,
   không hỏi lại người dùng.
6. Trả lời bằng tiếng Việt, trừ khi câu hỏi viết bằng ngôn ngữ khác.

NGỮ CẢNH:
$context

TRẢ LỜI:
"""


@PromptABC.register("legal_output_question")
class LegalOutputQuestionPrompt(PromptABC):
    # cùng một bản tiếng Việt cho cả hai, để đổi project.language không đổi kết quả
    template_en = TEMPLATE
    template_zh = TEMPLATE

    @property
    def template_variables(self) -> List[str]:
        return ["context", "question"]

    def parse_response(self, response: str, **kwargs):
        return response


if __name__ == "__main__":
    import sys
    from string import Template

    sys.stdout.reconfigure(encoding="utf-8")
    out = Template(TEMPLATE).substitute(context="C", question="Q")
    assert "$question" in TEMPLATE and "$context" in TEMPLATE, "thiếu placeholder"
    assert out.count("Q") == 1 and "C\n" in out, "placeholder không được thay"
    assert "internal knowledge" not in out, "còn sót đường cho mô hình bịa"
    print("[self-check ok] legal_output_question: đúng 2 biến context/question")
