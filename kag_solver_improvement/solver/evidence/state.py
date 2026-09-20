# kag/solver/evidence/state.py
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class FactItem(BaseModel):
    statement: str
    source_id: Optional[str] = None  # chunk id hoặc node id
    confidence: float = 1.0

class ConflictItem(BaseModel):
    fact_a: FactItem
    fact_b: FactItem
    conflict_reason: str

class StructuredEvidenceState(BaseModel):
    covered_facts: List[FactItem] = Field(default_factory=list)
    missing_facts: List[str] = Field(default_factory=list)
    conflicting_facts: List[ConflictItem] = Field(default_factory=list)
    unsupported_claims: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    intermediate_answers: List[Dict[str, Any]] = Field(default_factory=list)
    iteration: int = 0

    def to_summary_text(self) -> str:
        """Chuyển đổi trạng thái có cấu trúc thành prompt context cho LLM."""
        return (
            f"Iteration: {self.iteration}\n"
            f"Covered Facts: {[f.statement for f in self.covered_facts]}\n"
            f"Missing Facts: {self.missing_facts}\n"
            f"Conflicting Facts: {[{'a': c.fact_a.statement, 'b': c.fact_b.statement, 'reason': c.conflict_reason} for c in self.conflicting_facts]}\n"
            f"Unsupported Claims: {self.unsupported_claims}\n"
            f"Intermediate Answers: {self.intermediate_answers}\n"
        )