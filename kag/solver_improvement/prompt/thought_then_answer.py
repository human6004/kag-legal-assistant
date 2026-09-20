# -*- coding: utf-8 -*-
"""Prompt tóm tắt một sub-task, bản tiếng Việt cho miền pháp luật.

Thay cho default_thought_then_answer của KAG (ví dụ Sylvester / Charlemagne).

AI GỌI
  kag/solver/executor/retriever/kag_hybrid_retrieval_executor.py:76
    summary_prompt, bật bởi `enable_summary: true` trong kag_config.yaml
    (kag_hybrid_executor.enable_summary). invoke truyền đúng ba biến
    cur_question / questions / docs.
  .../kag_retriever/kag_component/kag_merger.py:91
    cùng tên prompt, cùng ba biến.

Chọn qua biz_scene, không qua yaml: init_prompt_with_fallback("thought_then_answer", ...)
thử "legal_thought_then_answer" trước, lỗi mới rơi về "default_...".
Đặt project.biz_scene về default là im lặng quay lại bản tiếng Anh.

VÌ SAO QUAN TRỌNG NHẤT: đây là bước tóm tắt từng sub-task, và kết quả của nó chính là
chuỗi $content bơm vào legal_refer_generator_prompt. Prompt sinh câu trả lời cuối cùng
đang viết tiếng Việt; để bước này trả về tiếng Anh là bắt nó đọc ngữ cảnh tiếng Anh.

Viết tiếng Việt vào template_en vì project.language: en. Không đặt language: vi được,
xem chú thích đầu kag/solver/prompt/refer_generator.py.
"""

from typing import List

from kag.interface import PromptABC

TEMPLATE = """Bạn là chuyên gia giải các câu hỏi pháp luật nhiều bước thuộc lĩnh vực an ninh
mạng, trí tuệ nhân tạo và truyền thông. Câu hỏi gốc đã được chia thành nhiều câu hỏi đơn
giản hơn; mỗi câu sau có thể dựa vào câu trả lời của các câu trước. Tôi sẽ đưa ra những gì
đã giải được ở các bước trước, hoặc chính câu trả lời của chúng, và các đoạn văn bản luật
tra được cho câu hỏi hiện tại.

LƯU Ý: Không có trong Docs thì phải nói rõ là không có. TUYỆT ĐỐI không dùng kiến thức
sẵn có của mô hình để suy đoán hay lấp chỗ trống. Thà nói thiếu còn hơn nói sai luật.

QUY TẮC BẮT BUỘC
1. Giữ NGUYÊN VĂN mọi thông tin định danh và mọi con số:
   - số hiệu văn bản (ví dụ "Luật 116/2025/QH15", "Nghị định 13/2023/NĐ-CP");
   - số điều, khoản, điểm (ví dụ "khoản 2 Điều 8");
   - mức phạt, khung tiền, thời hạn, mốc thời gian, ngày có hiệu lực / hết hiệu lực;
   - id chunk nếu Docs có ghi, ví dụ "chunk:1_2".
   Không viết lại "một trăm triệu" cho "100.000.000", không đổi "Điều 8" thành "điều thứ
   tám", không làm tròn, không quy đổi đơn vị, không diễn nôm con số.
2. Không bịa. Không thêm số hiệu, điều khoản, mức phạt hay nguồn nào không có trong Docs.
3. Docs không trả lời được câu hỏi thì ghi thẳng là không có thông tin trong Docs, nói
   ngắn gọn còn thiếu gì. Không đoán.
4. Docs mâu thuẫn nhau thì nêu cả hai kèm số hiệu, không tự chọn bên nào.
5. Viết bằng tiếng Việt, giữ nguyên thuật ngữ pháp lý.

Bắt đầu bằng "Thought: ", trình bày từng bước suy luận dẫn tới kết luận. Kết thúc bằng
"Answer: " và câu trả lời rõ ràng, chính xác, không thêm bình luận nào khác.

Docs:
Luật 24/2018/QH14. status: hết hiệu lực. dateExpired: 2026-07-01. Bị thay thế bởi
Luật 116/2025/QH15.

Luật 116/2025/QH15. status: còn hiệu lực. dateEffective: 2026-07-01. Điều 26. Bảo đảm an
ninh thông tin trên không gian mạng. Doanh nghiệp trong nước và ngoài nước cung cấp dịch
vụ trên mạng viễn thông, mạng Internet phải xác thực thông tin người dùng. (chunk:1_2)

Questions:
Step1: Luật An ninh mạng hiện hành là luật nào?
Thought: Docs ghi Luật 24/2018/QH14 đã hết hiệu lực từ 2026-07-01 và bị thay thế bởi
Luật 116/2025/QH15, nên văn bản đang có hiệu lực là Luật 116/2025/QH15. Answer:
Luật 116/2025/QH15.

Docs:
$docs

Questions:
$questions

$cur_question
"""


@PromptABC.register("legal_thought_then_answer")
class LegalThoughtThenAnswerPrompt(PromptABC):
    # cùng một bản tiếng Việt cho cả hai, để đổi project.language không đổi kết quả
    template_en = TEMPLATE
    template_zh = TEMPLATE

    @property
    def template_variables(self) -> List[str]:
        return ["docs", "cur_question", "questions"]

    def parse_response(self, response: str, **kwargs):
        return response


if __name__ == "__main__":
    # Template.substitute nghiêm ngặt hơn đường chạy thật: đường thật escape hết "$"
    # rồi chỉ mở lại đúng ba biến trên, nên gõ sai "$doc" sẽ lặng lẽ thành chữ thường
    # chứ không báo gì. Ở đây thì nó ném KeyError ngay.
    import sys
    from string import Template

    sys.stdout.reconfigure(encoding="utf-8")
    out = Template(TEMPLATE).substitute(docs="D", questions="Q", cur_question="C")
    assert "Luật 116/2025/QH15" in out, "mất ví dụ miền luật"
    assert out.rstrip().endswith("C"), "cur_question phải nằm cuối prompt"
    assert "Thought: " in out and "Answer: " in out, "mất khuôn Thought/Answer"
    print("[self-check ok] legal_thought_then_answer: đủ 3 biến docs/cur_question/questions")
