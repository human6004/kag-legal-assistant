# -*- coding: utf-8 -*-
import os
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
"""Prompt chọn quan hệ (SPO) khi tra đồ thị, bản tiếng Việt miền pháp luật.

Thay cho default_spo_retrieval của KAG (ví dụ "Woman's Viewpoint", "Flute Sonata in C
major, BWV 1033"). Bản mặc định là tiếng Anh, còn chuỗi ứng viên sinh ra từ đồ thị của
đề tài này là tiếng Việt (builder dùng legal_ner/legal_std/legal_triple) — và model gọi
ở đây là openie_llm (qwen2.5-7b-instruct-1m), không phải chat_llm.

AI GỌI — đã grep chứng minh nằm trên đường chạy của kag_config.yaml hiện tại:
  kag_config.yaml:146-156  kg_fr.path_select = fuzzy_one_hop_select
  fuzzy_one_hop_select.py:65  spo_retrieval_prompt = init_prompt_with_fallback(
                                  "spo_retrieval", biz_scene)
  fuzzy_one_hop_select.py:259 invoke() -> match_spo()
  fuzzy_one_hop_select.py:226 match_spo() -> find_best_match_p_name_by_model()
  fuzzy_one_hop_select.py:168 -> select_relation() -> :138 _selected_rel_by_llm()
  fuzzy_one_hop_select.py:105 llm_client.invoke({"question","mention","candis"},
                                  spo_retrieval_prompt, with_json_parse=True)
kg_fr nằm trong kag_hybrid_executor.retrievers (kag_config.yaml:189-192).

BẮT BUỘC GIỮ: template là một chuỗi JSON (is_json_format() mặc định True, và
_selected_rel_by_llm truyền with_json_parse=True), parse_response đọc khóa "output".
Đổi cấu trúc JSON hay đổi tên khóa là chết ở bước parse.
"""

import logging
from typing import List

from kag.interface import PromptABC

logger = logging.getLogger(__name__)

TEMPLATE = """{
  "instruction": "Bạn là chuyên gia ngôn ngữ. Nhiệm vụ của bạn là chọn đúng chỉ số của các ứng viên SPO để trả lời câu hỏi, dựa trên SPO mention đã cho.",
  "requirements": [
    "Đầu ra phải là mảng chuỗi các chỉ số ứng viên SPO (đánh số từ 0)",
    "Chỉ số tương ứng đúng thứ tự ứng viên ban đầu (ứng viên thứ 1 = 0, thứ 2 = 1, ...)",
    "Nếu nhiều ứng viên cùng đúng thì trả về tất cả chỉ số khớp",
    "Nếu không ứng viên nào khớp thì trả về mảng rỗng"
  ],
  "examples": [
    {
      "question": "Luật 116/2025/QH15 thay thế văn bản nào?",
      "spo_mention": "LegalDocument[Luật 116/2025/QH15] supersedes LegalDocument",
      "spo_candidates": [
        "luật 116/2025/qh15 supersedes luật 24/2018/qh14",
        "luật 116/2025/qh15 amends luật 24/2018/qh14",
        "luật 116/2025/qh15 implementsDoc nghị định 53/2022/nđ-cp"
      ],
      "output": ["0"]
    },
    {
      "question": "Nghị định 53/2022/NĐ-CP hướng dẫn thi hành văn bản nào?",
      "spo_mention": "LegalDocument[Nghị định 53/2022/NĐ-CP] implementsDoc LegalDocument",
      "spo_candidates": [
        "nghị định 53/2022/nđ-cp implementsDoc luật 24/2018/qh14",
        "nghị định 53/2022/nđ-cp implementsDoc luật 86/2015/qh13",
        "luật 24/2018/qh14 supersededBy luật 116/2025/qh15"
      ],
      "output": ["0"]
    }
  ],
  "task": {
    "question": "$question",
    "spo_mention": "$mention",
    "spo_candidates": "$candis"
  },
  "output": "Trả về một mảng chuỗi JSON gồm các chỉ số ứng viên khớp"
}
"""


@PromptABC.register("legal_spo_retrieval")
class LegalSpoRetrieval(PromptABC):
    # cùng một bản tiếng Việt cho cả hai, để đổi project.language không đổi kết quả
    template_en = TEMPLATE
    template_zh = TEMPLATE

    @property
    def template_variables(self) -> List[str]:
        return ["question", "mention", "candis"]

    def parse_response(self, response, **kwargs):
        logger.debug(
            f"LegalSpoRetrieval {response} mention:{self.template_variables_value.get('mention', '')} "
            f"candis:{self.template_variables_value.get('candis', '')}"
        )
        if isinstance(response, list):
            return response
        if not isinstance(response, dict):
            return response
        if "output" in response:
            return response["output"]
        if "Output" in response:
            return response["Output"]
        return response


if __name__ == "__main__":
    import json
    import sys
    from string import Template

    sys.stdout.reconfigure(encoding="utf-8")
    # 1. template phải là JSON hợp lệ (with_json_parse=True ở đường chạy thật).
    # Bản gốc để comment "// index 0" trong template — JSON không cho phép comment, nên bản
    # này không giữ comment. Nếu sau này thêm lại thì assert dưới sẽ bắt được.
    data = json.loads(TEMPLATE)
    assert set(data.keys()) == {
        "instruction",
        "requirements",
        "examples",
        "task",
        "output",
    }, sorted(data.keys())
    assert set(data["task"].keys()) == {"question", "spo_mention", "spo_candidates"}
    # 2. đúng 3 biến, thay được thật (không bị escape thành chữ "$mention")
    out = Template(TEMPLATE).substitute(question="Q", mention="M", candis="C")
    assert '"question": "Q"' in out, "biến question không được thay"
    assert '"spo_mention": "M"' in out, "biến mention không được thay"
    assert '"spo_candidates": "C"' in out, "biến candis không được thay"
    assert "$" not in out, "còn ký tự $ sót trong prompt"
    # 3. parse_response vẫn đọc được khóa output như bản gốc
    prompt = LegalSpoRetrieval.__new__(LegalSpoRetrieval)
    prompt.template_variables_value = {}
    assert prompt.parse_response({"output": ["0"]}) == ["0"]
    assert prompt.parse_response(["1"]) == ["1"]
    print("[self-check ok] legal_spo_retrieval: JSON hợp lệ, đủ 3 biến, parse giữ nguyên")
