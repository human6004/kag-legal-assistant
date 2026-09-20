# -*- coding: utf-8 -*-
"""Prompt viết lại câu hỏi của sub-task, bản tiếng Việt miền pháp luật.

Thay cho default_rewrite_sub_task_query của KAG (ví dụ "vợ của ông X", "anh em của ông A").

AI GỌI
  kag/solver/planner/lf_kag_static_planner.py:76 query_rewrite()
    KAGLFStaticPlanner ("lf_kag_static_planner"), gọi khi task có
    is_need_rewrite=True. Truyền đúng hai biến:
      input   = câu hỏi của sub-task, còn chứa chỉ định thực thể
      content = json {"target question": ..., "history_qa": [...]}

PHẢI SỬA TAY kag_config.yaml: khoá này khai tên THẲNG trong yaml
(kag_solver_pipeline.planner.rewrite_prompt.type) nên biz_scene KHÔNG với tới:
  default_rewrite_sub_task_query  ->  legal_rewrite_sub_task_query

is_json_format() trả False là BẮT BUỘC giữ: lf_kag_static_planner.py:101 truyền
with_json_parse=self.rewrite_prompt.is_json_format(). Quên là nó đi parse JSON và chết.
Đầu ra phải là câu hỏi đã viết lại, dạng văn bản thuần.
"""

from typing import List

from kag.interface import PromptABC

TEMPLATE = """Bạn viết lại câu hỏi của một bước trong chuỗi suy luận pháp luật: thay các chỉ
định thực thể còn mơ hồ bằng tên thực thể cụ thể đã có ở các bước trước, rồi trả về câu hỏi
đã viết lại.

LƯU Ý: Không xuất ra định dạng JSON. Chỉ xuất câu hỏi đã viết lại bằng văn bản thuần, viết
đầy đủ nhất có thể, không bỏ sót, không thêm thông tin nào khác.

VÍ DỤ 1
content:
{
  "target question": "Luật An ninh mạng hiện hành là luật nào và điều khoản đó quy định gì?",
  "history_qa": [
    "Step1: Luật An ninh mạng hiện hành là luật nào?\\nanswer: Luật 116/2025/QH15"
  ]
}
question: "Văn bản ở Step1 có hiệu lực từ khi nào?"
rewrite question: "Luật 116/2025/QH15 có hiệu lực từ khi nào?"

VÍ DỤ 2
content:
{
  "target question": "Nghị định nào hướng dẫn thi hành Luật An ninh mạng và nghị định đó quy định mức phạt bao nhiêu?",
  "history_qa": [
    "Step1: Nghị định nào hướng dẫn thi hành Luật An ninh mạng?\\nanswer: Nghị định 53/2022/NĐ-CP"
  ]
}
question: "Nghị định ở Step1 quy định mức phạt bao nhiêu?"
rewrite question: "Nghị định 53/2022/NĐ-CP quy định mức phạt bao nhiêu?"

content: $content
question: $input
"""


@PromptABC.register("legal_rewrite_sub_task_query")
class LegalRewriteSubTaskQueryPrompt(PromptABC):
    # cùng một bản tiếng Việt cho cả hai, để đổi project.language không đổi kết quả
    template_en = TEMPLATE
    template_zh = TEMPLATE

    def is_json_format(self):
        return False

    @property
    def template_variables(self) -> List[str]:
        return ["content", "input"]

    def parse_response(self, response: list, **kwargs):
        return response


if __name__ == "__main__":
    import sys
    from string import Template

    sys.stdout.reconfigure(encoding="utf-8")
    out = Template(TEMPLATE).substitute(content="C", input="Q")
    assert (
        LegalRewriteSubTaskQueryPrompt.__dict__["is_json_format"](None) is False
    ), "is_json_format phải trả False"
    assert out.rstrip().endswith("Q"), "input phải nằm cuối prompt"
    assert "Luật 116/2025/QH15" in out, "mất ví dụ miền luật"
    assert "json" in out.lower(), "mất ràng buộc không xuất JSON"
    print("[self-check ok] legal_rewrite_sub_task_query: 2 biến, is_json_format()=False")
