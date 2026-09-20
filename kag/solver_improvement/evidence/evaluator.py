# kag/solver/evidence/evaluator.py
import json
from enum import Enum
from kag.interface import LLMClient
from kag.solver.evidence.state import StructuredEvidenceState

class EvidenceStatus(str, Enum):
    SUFFICIENT = "Sufficient"
    INCOMPLETE = "Incomplete"
    UNSUPPORTED = "Unsupported"
    CONFLICTING = "Conflicting"

EVALUATOR_PROMPT = """Bạn là thẩm phán đánh giá chứng cứ.
Dựa trên CÂU HỎI GỐC và TRẠNG THÁI CHỨNG CỨ hiện tại:
CÂU HỎI: {query}
TRẠNG THÁI CHỨNG CỨ:
{state_summary}

Hãy chọn ĐÚNG 1 trong 4 trạng thái sau:
1. "Sufficient": Đã đủ bằng chứng vững chắc, không còn thiếu sót hay mâu thuẫn nào, sẵn sàng sinh câu trả lời cuối cùng.
2. "Incomplete": Còn thiếu các dữ kiện quan trọng (missing_facts) để trả lời đầy đủ.
3. "Unsupported": Có nhận định hoặc câu trả lời trung gian nhưng thiếu căn cứ xác thực, cần truy vấn bổ sung chứng cứ.
4. "Conflicting": Có dữ kiện mâu thuẫn trực tiếp giữa các văn bản/điều khoản cần ưu tiên đối chiếu làm rõ (hiệu lực, thẩm quyền).

Định dạng trả về:
{{
  "status": "Sufficient" | "Incomplete" | "Unsupported" | "Conflicting",
  "reason": "Giải thích ngắn gọn lý do chọn",
  "action_hint": "Gợi ý việc cần làm tiếp theo"
}}
"""

class EvidenceAwareEvaluator:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def evaluate(self, query: str, state: StructuredEvidenceState) -> (EvidenceStatus, Dict[str, Any]):
        # Điều kiện dừng cứng nếu không còn thiếu sót và không mâu thuẫn
        if not state.missing_facts and not state.conflicting_facts and not state.unsupported_claims and len(state.covered_facts) > 0:
            return EvidenceStatus.SUFFICIENT, {"reason": "Tất cả facts đã đầy đủ"}

        prompt = EVALUATOR_PROMPT.format(
            query=query,
            state_summary=state.to_summary_text()
        )
        resp = await self.llm.acall(prompt)
        clean = resp.replace("```json", "").replace("```", "").strip()
        try:
            data = json.loads(clean)
            status_str = data.get("status", "Incomplete")
            return EvidenceStatus(status_str), data
        except Exception:
            return EvidenceStatus.INCOMPLETE, {"reason": "Lỗi phân tích JSON, mặc định tra cứu tiếp"}