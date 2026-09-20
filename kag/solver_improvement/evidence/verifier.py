# kag/solver/evidence/verifier.py
from kag.interface import Task, LLMClient
from kag.solver.evidence.state import ConflictItem

class EvidenceVerifier:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def create_verification_task(self, conflict: ConflictItem) -> Task:
        """Tạo task logic form chuyên dụng để giải quyết mâu thuẫn (tra hiệu lực, văn bản thay thế)."""
        prompt = f"""Phát hiện mâu thuẫn giữa hai dữ kiện:
A: {conflict.fact_a.statement}
B: {conflict.fact_b.statement}
Lý do: {conflict.conflict_reason}

Hãy tạo 1 subquery ngắn gọn để kiểm chứng mâu thuẫn này (ưu tiên kiểm tra ngày hiệu lực, văn bản sửa đổi bổ sung hoặc điều khoản loại trừ):"""
        verify_query = await self.llm.acall(prompt)
        
        # Tạo Task giao thẳng cho Reasoner (kg_hybrid_retrieval_executor)
        return Task(
            name="verify_conflict",
            executor="kag_hybrid_executor",
            arguments={"query": verify_query.strip(), "is_need_rewrite": False}
        )