# Gold Standard Annotation Protocol for Legal Question Answering Evaluation

**Document Version**: 1.0.0  
**Registration Date**: 2026-09-21  
**Target Domains**: Vietnamese Cybersecurity Law & Artificial Intelligence Regulations  
**Objective**: Standardize human-expert annotation of legal queries to establish a leak-free ground truth for evaluating A0 (Baseline Iterative KAG) vs A1 (Evidence-Aware KAG).

---

## 1. Schema & Field Definitions

Each gold standard benchmark query item must adhere to the following JSON schema:

```json
{
  "query_id": "string (unique identifier, e.g. VNLAW-QA-001)",
  "original_query": "string (verbatim query text)",
  "query_category": "enum (single_aspect | multi_aspect | conflicting | unanswerable)",
  "mandatory_requirements": [
    {
      "requirement_id": "string (unique req identifier, e.g. REQ_PROHIBITION)",
      "description": "string (semantic claim description)",
      "required_aspects": ["string (e.g. prohibition, penalty, procedure, licensing)"],
      "expected_doc_ids": ["string (authoritative document identifiers, e.g. 116-2025-QH15)"]
    }
  ],
  "gold_evidence_spans": [
    {
      "span_id": "string (e.g. SPAN_01)",
      "doc_id": "string (e.g. 116-2025-QH15)",
      "article": "string (e.g. Điều 8)",
      "clause": "string (e.g. Khoản 1)",
      "exact_quote": "string (verbatim text span from official legal corpus)",
      "target_requirement_id": "string",
      "semantic_relation": "enum (ENTAILMENT | CONTRADICTION | NEUTRAL)"
    }
  ],
  "answerability": "enum (ANSWERABLE | UNANSWERABLE_OUT_OF_SCOPE | CONFLICTING_NORMS)",
  "conflict_specification": {
    "has_conflict": "boolean",
    "conflicting_doc_ids": ["string"],
    "conflict_summary": "string (explanation of legal antinomy or temporal contradiction)"
  },
  "reference_answer": "string (authoritative legal synthesis based on verified evidence)"
}
```

---

## 2. Query Categorization & Annotation Rules

### Category 1: Single-Aspect Factual (`single_aspect`)
- **Criterion**: The query asks for a single legal rule, condition, definition, or threshold.
- **Annotation Requirement**: Exactly 1 mandatory requirement. At least 1 gold evidence span with `ENTAILMENT`.
- **Expected System Behavior**: Both A0 and A1 should retrieve the required chunk and terminate cleanly.

### Category 2: Multi-Aspect Complex (`multi_aspect`)
- **Criterion**: The query asks for compound legal facets (e.g., prohibition AND penalty; technical requirement AND licensing procedure).
- **Annotation Requirement**: At least 2 independent mandatory requirements spanning distinct aspects.
- **Evaluation Purpose**: Measures **Premature Finish Rate (PFR)**. A0 typically finishes after aspect 1; A1 must enforce retrieval of all aspects before terminating.

### Category 3: Conflicting Norms (`conflicting`)
- **Criterion**: The query involves conflicting legal provisions across older vs newer legal documents or jurisdictional collisions.
- **Annotation Requirement**: Exactly 2 gold evidence spans with opposing assertions (`CONTRADICTION`). `answerability` set to `CONFLICTING_NORMS`.
- **Expected System Behavior**: A0 prematurely finishes with a one-sided claim. A1 identifies the contradiction, prevents finish, and safely returns `ABSTAIN`.

### Category 4: Unanswerable / Out-of-Scope (`unanswerable`)
- **Criterion**: The query asks about nonexistent legal provisions, wrong legal premises, or topics outside the registered corpus.
- **Annotation Requirement**: `gold_evidence_spans` is empty or only contains `NEUTRAL` chunks. `answerability` set to `UNANSWERABLE_OUT_OF_SCOPE`.
- **Expected System Behavior**: A0 hallucinates an answer. A1 fails-closed with `ABSTAIN`.

---

## 3. Strict Data Leakage Invariants

1. **Post-Hoc Evaluation Only**: Gold annotations must NEVER be provided to A1 during execution. They exist solely for the offline benchmark evaluator (`benchmark/evaluator.py`).
2. **Independent Semantic Verifier Runtime**: A1 in live benchmarks must query an independent NLI model or cross-encoder, never the benchmark gold test labels.
