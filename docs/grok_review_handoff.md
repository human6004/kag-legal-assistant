# Grok 4.6 Single Reviewer Handoff Document: M2 Bounded Final Closeout

**Target Candidate**: Evidence-Aware KAG-Solver M2 Release Candidate  
**Research Worktree**: `D:\Dev\Workspaces\KAG\wt-evidence-m1`  
**Candidate Artifact**: `artifacts/evidence-aware-m2-gemini-grok-<timestamp>.zip`  
**Review Mode**: Independent Adversarial Audit (Read-Only)  
**Dispatch Status in Current Session**: `GROK_DISPATCH_BLOCKED` (Grok CLI not present on host; handoff prepared for external execution)

---

## 1. Audit Mandate & Reviewer Rules

1. Do NOT accept any claims or prose statements from Gemini as verified truth. Verify directly against source code and executable commands.
2. Do NOT edit production code (`kag/solver/evidence_aware/`). Write new counter-examples or mutant tests in a separate review test file.
3. Classify all findings strictly into:
   - `BLOCKING`: A concrete violation of M2 invariants with an executable reproducer.
   - `NON_BLOCKING`: Maintainability, style, or clarity improvement that does not violate contract invariants.
   - `POST_M2`: Feature requests, online LLM integrations, or indexing improvements out of scope for M2.
4. Do NOT cite test pass counts as a reason to dismiss a valid adversarial counter-example.

---

## 2. The Four Invariants Under Review

### Invariant C1: Provenance Integrity
- **Contract Rule**: A retriever returning a chunk claiming to belong to a corpus document does NOT prove it belongs to that document. Without an authoritative corpus doc-to-chunk mapping (`valid_corpus_chunk_ids_by_doc`), provenance MUST remain `PROVENANCE_INVALID`.
- **Prohibited**: Runtime code in `models.py` must NOT maintain hidden fixture fallbacks (e.g., `DEFAULT_FIXTURE_DOC_CHUNKS`) that grant `PROVENANCE_VERIFIED` behind the caller's back.
- **Verification Target**: `FourStageEvidenceVerifier.stage2_verify_provenance(evidence, valid_corpus_doc_ids, valid_corpus_chunk_ids_by_doc=None)` returns `status = ProvenanceValidationStatus.PROVENANCE_INVALID`.

### Invariant C2: Presence Lineage
- **Contract Rule**: Evidence presence is bound strictly to the retrieval task that retrieved it. When Task 1 retrieves chunk `C1` and Task 2 retrieves an empty result (`{"chunks": []}`), Task 2 must NOT issue a presence receipt or Stage 4 receipt for `C1` with Task 2's `run_id`.
- **Prohibited**: `auto_verify_retrieval()` must NOT fall back to `set(self.evidences.keys())` when a task returns empty retrieval.
- **Verification Target**: Zero receipts issued for past chunks under an empty task retrieval run.

### Invariant C3: Semantic Oracle Isolation
- **Contract Rule**: Entailment is a relation between a specific claim and evidence. When requirements R1 and R2 share evidence `C1` but make different assertions, certifying R1's claim in `semantic_oracle` must NOT satisfy R2 via an evidence-only alias (e.g. `oracle["C1"]`).
- **Prohibited**: Evidence-only keys in `semantic_oracle` must NOT overwrite or bypass claim matching when claim-specific keys are present.
- **Verification Target**: In `auto_verify_retrieval()`, R2 remains `UNSATISFIED` when oracle only certifies R1.

### Invariant C4: Benchmark Evaluator Fidelity
- **Contract Rule**: Sufficiency evaluation must strictly enforce per-requirement aspect-to-document binding. A query requiring Aspect A from Doc 1 and Aspect B from Doc 2 is NOT satisfied by retrieving Aspect A from Doc 2 and Aspect B from Doc 1.
- **Prohibited**: Treating document scopes and aspects as disjoint bags of strings.
- **Verification Target**: `evaluate_single_trace()` evaluates crossed/mismatched retrieval as `evidence_genuinely_sufficient = False` and `accepted_premature_finish = True`.

---

## 3. Independent Reproduction Commands

To reproduce the four invariants and regression suite:
```powershell
# In worktree root (D:\Dev\Workspaces\KAG\wt-evidence-m1):
& ".venv\Scripts\python.exe" "tests\test_m2_bounded_closeout_red.py"
& ".venv\Scripts\python.exe" "tests\run_all_m2_tests.py"
& ".venv\Scripts\python.exe" "tests\test_d2_integration_probe.py"
& ".venv\Scripts\python.exe" "tests\test_benchmark_metrics.py"
& ".venv\Scripts\python.exe" "tests\test_benchmark_trace_fidelity.py"
& ".venv\Scripts\python.exe" "scripts\secret_scan.py"
```

---

## 4. Expected Independent Review Deliverable Format

When running Grok in an external session, format findings as:
```text
FINDING-ID: [BLOCKING | NON_BLOCKING | POST_M2]
Target File: line_number
Description:
Repro Command:
Expected Behavior:
Actual Behavior:
Impact on M2:
```
