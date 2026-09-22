# Pre-registered Experimental Protocol: Evaluating Evidence-Aware Finish Gating (A1) vs Baseline Iterative KAG (A0) in Legal Question Answering

**Document Version**: 1.0.0  
**Registration Date**: 2026-09-21  
**Target System**: KAG (Knowledge Augmented Generation) with Evidence-Aware Solver Extension (M2)  
**Study Design**: Comparative Offline/Online Benchmark Evaluation  

---

## 1. Executive Summary & Research Questions

Modern iterative Retrieval-Augmented Generation (RAG) and Knowledge Augmented Generation (KAG) architectures rely on LLM-based planners to iteratively retrieve graph entities and text chunks before deciding when to terminate retrieval and generate an answer. However, unconstrained LLM planners frequently suffer from **premature finish bias**: declaring retrieval complete before all mandatory facets of a complex legal question are substantiated, leading to hallucinated, ungrounded, or contradictory claims.

This study formulates and pre-registers an experimental comparison between:
- **Baseline (A0)**: Standard Upstream Iterative KAG (`KAGIterativePipeline` with `evidence_aware=False`), terminating whenever the planner proposes `finish_executor` or exhausts the iteration budget.
- **Treatment (A1)**: Evidence-Aware Iterative KAG (`KAGEvidenceAwareIterativePipeline` with `evidence_aware=True`), maintaining a request-scoped `StructuredEvidenceState`, executing a 4-Stage Verification Chain (Presence, Provenance, Semantic Entailment, and Coverage), and enforcing a fail-closed Finish Gate with rejection feedback delivery to the planner.

### Core Research Questions
1. **RQ1 (Groundedness & Safety)**: Does the 4-stage evidence verification gate in A1 significantly reduce the rate of unsupported claims and legal hallucinations compared to A0?
2. **RQ2 (Multi-Aspect Requirement Completeness)**: For complex multi-condition queries, does A1 eliminate premature termination and ensure all legal prerequisites (e.g., prohibition AND penalty) are satisfied?
3. **RQ3 (Conflict Handling & Abstention)**: When presented with contradictory or unanswerable queries, does A1 safely fail-closed (`ABSTAIN`) rather than producing fabricated conclusions?
4. **RQ4 (Computational & Latency Overhead)**: What is the cost of evidence-awareness in terms of iteration budget, retrieval calls, and wall-clock execution time?

---

## 2. Formal Hypotheses

- **Hypothesis 1 (H1 — Unsupported Claim Reduction)**:  
  $H_{1a}$: The Unsupported Claim Rate in A1 is strictly lower than in A0 ($\text{UCR}_{A1} < \text{UCR}_{A0}$) with statistical significance ($p < 0.01$, two-tailed paired bootstrap test).
- **Hypothesis 2 (H2 — Premature Finish Elimination)**:  
  $H_{2a}$: The Premature Finish Rate in multi-aspect queries for A1 is reduced to 0% ($\text{PFR}_{A1} = 0\%$) under verifiable corpus conditions, whereas A0 exhibits $\text{PFR}_{A0} > 0\%$.
- **Hypothesis 3 (H3 — Safe Abstention under Conflict & Insufficiency)**:  
  $H_{3a}$: On unanswerable or contradictory query subsets, A1 achieves an Abstention Rate of 100% with Conflict Handling Accuracy of 1.0, whereas A0 attempts generation resulting in false claims.
- **Hypothesis 4 (H4 — Bounded Iteration Overhead)**:  
  $H_{4a}$: A1 incurs an average iteration count increase of at most 35% compared to A0 ($\bar{I}_{A1} \le 1.35 \times \bar{I}_{A0}$), representing an acceptable trade-off for legal safety.

---

## 3. Experimental Architecture & Pipeline Modes

Both configurations share the identical upstream OpenSPG infrastructure, retrieval executors, prompt templates, and generator. No retrieval weights or model checkpoints differ between A0 and A1.

```
+-----------------------------------------------------------------------------------+
| Common Upstream Infrastructure: OpenSPG / KAG Core (pin: fdab15b3929d2ee40df)     |
+-----------------------------------------------------------------------------------+
                                         |
         +-------------------------------+-------------------------------+
         |                                                               |
         v                                                               v
+------------------------------------+          +------------------------------------+
| A0: Baseline Iterative KAG         |          | A1: Evidence-Aware Iterative KAG   |
| - Pipeline: KAGIterativePipeline   |          | - Pipeline: KAGEvidenceAware...    |
| - evidence_aware = False           |          | - evidence_aware = True            |
| - Finish Gate: None                |          | - Finish Gate: 4-Stage Verifier    |
| - Termination: Planner Finish or   |          | - Feedback: Planner Rejection Loop |
|   max_iteration reached            |          | - Termination: Sufficient Gate or  |
| - Generator: called on any Finish  |          |   Fail-Closed (ABSTAIN/EXCEPTION)  |
+------------------------------------+          +------------------------------------+
```

### Invariant Controls
1. **Model & Decoding**: If live LLMs are used in subsequent empirical phases, identical model version, temperature (0.0), top_p, and seed must be passed to both A0 and A1.
2. **Knowledge Base / Corpus**: Identical graph nodes/edges and document chunks from `data/` must be queried by both systems.
3. **Budget**: Identical `max_iteration` (default: 5) for both pipelines.
4. **Executor Schemas**: Same executor tools (`Retriever`, `FinishExecutor`) provided in planner prompt.

---

## 4. Evaluation Metrics

### 4.1 Primary Quality & Safety Metrics

1. **Evidence Sufficiency Rate (ESR)**:
   $$\text{ESR} = \frac{\sum_{i=1}^N \mathbb{I}(\text{status}_i = \text{SUFFICIENT})}{N}$$
   Measures the fraction of queries where all mandatory evidence requirements possess cryptographically verified, entailed Stage 4 receipts.

2. **Unsupported Claim Rate (UCR)**:
   $$\text{UCR} = \frac{\sum_{i=1}^N N_{\text{unsupported}}(answer_i)}{\sum_{i=1}^N N_{\text{total\_claims}}(answer_i)}$$
   Measures the proportion of atomic factual claims in the generated response that lack supporting Stage 4 entailment receipts.

3. **Premature Finish Rate (PFR)**:
   $$\text{PFR} = \frac{\sum_{i=1}^N \mathbb{I}(\text{finished\_by\_planner}_i \land \neg \text{SUFFICIENT}_i)}{N}$$
   Measures how often the planner attempts to terminate before required evidence aspects are satisfied.

4. **Conflict Handling Accuracy (CHA)**:
   $$\text{CHA} = \frac{\sum_{i \in \mathcal{D}_{\text{conflict}}} \mathbb{I}(\text{status}_i = \text{ABSTAIN} \land \text{conflict\_detected}_i)}{|\mathcal{D}_{\text{conflict}}|}$$
   Measures whether queries with contradicting legal provisions are correctly identified and gated.

5. **Abstention Rate (ABR)**:
   $$\text{ABR} = \frac{\sum_{i=1}^N \mathbb{I}(\text{status}_i = \text{ABSTAIN})}{N}$$
   Measures frequency of fail-closed termination. Evaluated separately on answerable vs unanswerable query partitions.

### 4.2 Efficiency & Cost Metrics

6. **Average Iteration Count ($\bar{I}$)**:
   $$\bar{I} = \frac{1}{N} \sum_{i=1}^N \text{iterations}_i$$

7. **Rejection Count ($\bar{R}$)**:
   Average number of times the Finish Gate rejected an inadequate plan and forced replanning in A1.

8. **Average Latency / Elapsed Time ($\bar{T}$)**:
   Average wall-clock time per query (seconds).

---

## 5. Benchmark Data Stratification

The benchmark evaluation corpus is stratified into four distinct query categories:

| Category | Description | Primary Metric Focus |
|---|---|---|
| **CAT-1: Single-Aspect Factual** | Direct lookup of a single legal rule or article. | ESR, Latency, Upstream Parity |
| **CAT-2: Multi-Aspect Complex** | Multi-condition queries requiring both rule and consequence (e.g., prohibition + penalty, condition + procedure). | PFR, ESR, UCR |
| **CAT-3: Conflicting Norms** | Queries involving contradictory evidence (e.g., conflicting decree versions, jurisdictional clash). | CHA, Safe Abstention |
| **CAT-4: Unanswerable / Out-of-Scope** | Queries whose mandatory evidence does not exist in the corpus. | ABR (must be 100%), Zero Hallucination |

---

## 6. Execution & Stopping Conditions

1. **Max Iterations**: 5 iterations per query. If exceeded without `SUFFICIENT`:
   - A0: Calls generator on whatever unverified context exists, or terminates.
   - A1: Returns `IncompleteAnswerResult(status="ABSTAIN")` with missing requirements and unresolved conflicts documented.
2. **Tie-Breaking**: If both A0 and A1 produce answers, answers are evaluated against pre-annotated ground-truth claims.
3. **Error Handling**:
   - Any runtime exception in executor/retrieval triggers retry up to 3 times (upstream `@retry` behavior).
   - In A1, any evaluator crash in `ABSTAIN` mode safely returns `IncompleteAnswerResult` with error rationale, preventing system crashes.
