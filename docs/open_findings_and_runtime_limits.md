# Open Findings and Runtime Limitations: Evidence-Aware KAG-Solver (M2)

**Document Version**: 1.0.0  
**Date**: 2026-09-21  
**Target Module**: `kag/solver/evidence_aware/`  
**Status**: DOCUMENTED FOR OWNER ARCHITECTURAL REVIEW  

---

## 1. Threat Model and Trust Boundary Clarification

1. **Intended Protection Boundary**:
   - The 4-Stage Verification Chain (`FourStageEvidenceVerifier`) and `StructuredEvidenceState` protect against **untrusted LLM agent outputs**, hallucinations, premature planner finishes, cross-query receipt replays, and out-of-order task completions across asynchronous execution loops.
2. **Clarification on Cryptographic Terminology**:
   - SHA-256 tokens in `Stage4VerificationReceipt` function as **cryptographic integrity tokens and lineage binders** (binding query hash, requirement ID, claim ID, evidence content hash, and stage timestamps).
   - They are **NOT** asymmetric digital signatures (e.g., RSA/Ed25519) and do NOT claim to prevent tampering by hostile, arbitrary Python code running within the same local process memory space.
   - Trust boundary is established by in-memory trusted issuance ledgers (`_issued_receipts_ledger`).

---

## 2. Benchmark & Experimental Runtime Status

### Finding 1: Online Benchmark Blocked (`ONLINE_BENCHMARK_BLOCKED`)
- **Current State**: M2 contract verification and offline harness dry-runs use deterministic oracle fixtures.
- **Limitation**: Running a live, empirical benchmark comparing A0 vs A1 on real legal questions cannot use gold benchmark labels as a runtime oracle for A1 (to avoid circular data leakage).
- **Prerequisite**: An independent, offline local Semantic Verifier runtime (e.g., a fine-tuned Vietnamese NLI model or calibrated cross-encoder) must be deployed before live benchmarks can commence.

### Finding 2: Hypothesis H4 (Iteration Overhead) Outcome
- **Pre-registered Threshold**: Iteration overhead $\le 35\%$.
- **Observed Result**: Under simulation test conditions on multi-aspect, conflicting, and unanswerable queries, average iterations increased from 2.00 (A0) to 4.00 (A1), representing a $+100\%$ overhead.
- **Verdict**: Hypothesis H4 is officially recorded as **NOT SUPPORTED** under these conditions. The extra iterations were consumed by active replanning loops (retrieving missing aspects) and conflict detection loops.

### Finding 3: Corpus Chunking and Knowledge Graph Indexing
- **Observation**: While 23 processed Markdown legal documents exist in `kag-legal-assistant/data/processed`, no pre-computed vector index or article-level chunk database is stored on disk.
- **Action Required**: Prior to live retrieval evaluation, the OpenSPG document chunking, embedding generation, and vector index persistence pipelines must be executed.

---

## 3. Operational Invariants Verified

- **Zero Vendor Modifications**: `vendor/KAG/` remains untouched (100% clean diff against upstream pin `fdab15b3929d2ee40dfcdd388f90233096a6afc9`).
- **Zero Paid LLM Calls**: All tests and dry-runs executed locally without external API dependencies or costs.
- **No Git Branches Polluted**: Research worktree `wt-evidence-m1` isolated on `research/m1-red-evidence-aware`; no merge or push executed.
