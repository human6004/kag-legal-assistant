# Benchmark Harness Validation & Comparative Dry-Run Report (Objective Measurement)

**Execution Date**: 2026-09-21  
**Execution Environment**: Isolated Worktree Virtualenv (`wt-evidence-m1/.venv`)  
**Evaluation Scope**: Offline Deterministic Simulation on 8 Synthetic Multi-Strata Queries  
**IMPORTANT DISCLAIMER**:  
> **ĐÂY LÀ KẾT QUẢ XÁC NHẬN HARNESS (HARNESS VALIDATION), KHÔNG PHẢI KẾT QUẢ THỰC NGHIỆM THẬT (NOT EMPIRICAL FINDINGS).**  
> KHÔNG sử dụng kết quả mô phỏng mock này để tuyên bố hiệu quả thực tế của A1 so với A0. Toàn bộ runner và evaluator hoạt động với bộ dữ liệu giả lập (mock chunks) nhằm chuẩn hóa schema, tính toán công thức metric, và kiểm chứng cơ chế chặn finish gate fail-closed.

---

## 1. Objective Comparative Metrics (A0 vs A1)

| Metric | A0 (Baseline Iterative KAG) | A1 (Evidence-Aware KAG) | Delta / Assessment |
|---|---|---|---|
| **Task Success Rate (TSR)** | 25.00% | 100.00% | Correctness across all 4 strata |
| **Evidence Sufficiency Rate (ESR)** | 25.00% | 50.00% | Genuinely verified vs gold requirements (A0 credited on Q1/Q2) |
| **Attempted Premature Finish** | 75.00% | 75.00% | Frequency planner proposed Finish early (identical planning behavior) |
| **Accepted Premature Finish** | 75.00% | 0.00% | A0 accepted premature Finish; A1 blocked all premature finishes |
| **False Rejection Rate** | 0.00% | 0.00% | Zero false rejections when evidence was genuinely sufficient |
| **Unsupported Claim Rate (UCR)** | 40.00% | 0.00% | Claims unsupported by retrieved chunks in final answer |
| **Conflict Handling Accuracy** | 0.00% | 100.00% | A0 produced unverified answer; A1 safely abstained with conflict |
| **Unanswerable Abstention** | 0.00% | 100.00% | A0 finished with empty chunks; A1 safely abstained |
| **Average Iterations** | 2.00 | 4.00 | +2.00 iters (+100% overhead due to replanning & conflict checks) |
| **Average Rejections** | 0.00 | 2.00 | Active feedback loops forced by finish gate |
| **Average Latency (s)** | 0.0010s | 0.0021s | Minimal in-memory simulation latency |
| **Hypothesis H4 Status** | Reference Baseline | **NOT SUPPORTED** | **Iteration overhead is +100.0%, which exceeded the pre-registered 35% threshold.** |

---

## 2. Invariant & Methodology Refinements

1. **Elimination of Circular Generator Bias**:
   - Generator no longer receives `ground_truth_answer`.
   - Generator does not branch on `mode == "A0"` or `"A1"`.
   - Answers are generated purely from chunks in `context.gen_task()`.
2. **Separation of Attempted vs Accepted Premature Finish**:
   - Both A0 and A1 exhibited identical `attempted_premature_finish_rate` (75%), demonstrating that the unconstrained planner proposes early termination on multi-aspect, conflicting, and unanswerable questions.
   - A0 accepted all premature proposals (`accepted_premature_finish_rate = 75%`).
   - A1 intercepted every premature finish proposal (`accepted_premature_finish_rate = 0%`).
3. **Objective Baseline Credit**:
   - When A0 finished with sufficient evidence on single-aspect queries (Q1, Q2), it was correctly recognized as `evidence_genuinely_sufficient = True` (ESR = 25%), rather than being automatically penalized for lacking an EvidenceState.
4. **Honest H4 Reporting**:
   - The average iteration count under A1 was 4.00 vs 2.00 in A0 (+100.0% overhead). Because this exceeds the pre-registered 35% ceiling, Hypothesis H4 is officially recorded as **NOT SUPPORTED** under these simulation test conditions.
