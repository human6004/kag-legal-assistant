# kag/solver/evidence/updater.py
import json
from kag.interface import LLMClient
from kag.solver.evidence.state import StructuredEvidenceState, FactItem, ConflictItem

UPDATE_STATE_PROMPT = """Bạn là chuyên gia phân tích chứng cứ.
Dựa trên mục tiêu ban đầu của câu hỏi, trạng thái chứng cứ hiện tại và kết quả vừa thu thập được ở bước mới nhất:
CÂU HỎI GỐC: {query}
TRẠNG THÁI CHỨNG CỨ TRƯỚC ĐÓ:
{current_state}

KẾT QUẢ VỪA THU THẬP:
{new_observation}

Hãy phân tích và xuất định dạng JSON với cấu trúc:
{{
  "covered_facts": [
    {{"statement": "nội dung dữ kiện đã được xác thực", "source_id": "id chunk nếu có"}}
  ],
  "missing_facts": ["những dữ kiện còn thiếu để trả lời trọn vẹn câu hỏi gốc"],
  "conflicting_facts": [
    {{"fact_a": "nội dung A", "fact_b": "nội dung B đối lập", "reason": "lý do mâu thuẫn (ví dụ khác hiệu lực, khác mức phạt)"}}
  ],
  "unsupported_claims": ["các nhận định đưa ra nhưng chưa có trích dẫn/căn cứ rõ ràng"],
  "intermediate_answer": "tóm tắt câu trả lời của bước hiện tại"
}}
Chỉ trả về định dạng JSON thuần.
"""

class EvidenceStateUpdater:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def update(self, query: str, state: StructuredEvidenceState, new_task_result: Any) -> StructuredEvidenceState:
        state.iteration += 1
        prompt = UPDATE_STATE_PROMPT.format(
            query=query,
            current_state=state.to_summary_text(),
            new_observation=str(new_task_result)
        )
        resp = await self.llm.acall(prompt)
        try:
            clean_resp = resp.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_resp)
            
            # Cập nhật covered facts
            for f in data.get("covered_facts", []):
                state.covered_facts.append(FactItem(statement=f.get("statement"), source_id=f.get("source_id")))
            
            state.missing_facts = data.get("missing_facts", [])
            state.unsupported_claims = data.get("unsupported_claims", [])
            
            # Cập nhật mâu thuẫn
            for c in data.get("conflicting_facts", []):
                state.conflicting_facts.append(ConflictItem(
                    fact_a=FactItem(statement=c.get("fact_a", "")),
                    fact_b=FactItem(statement=c.get("fact_b", "")),
                    conflict_reason=c.get("reason", "")
                ))
            
            if data.get("intermediate_answer"):
                state.intermediate_answers.append({
                    "step": state.iteration,
                    "answer": data.get("intermediate_answer")
                })
        except Exception as e:
            # Fallback nếu JSON bị lỗi parse
            state.intermediate_answers.append({"step": state.iteration, "raw": str(new_task_result)})
            
        return state