# Dataset Inventory and Research Readiness Report

**Investigation Date**: 2026-09-21  
**Scope**: Read-only inventory of datasets, corpora, metadata, and ground truth in `kag-legal-assistant` and `wt-evidence-m1`.  
**Operational Rule**: STRICTLY READ-ONLY. No corpus files, graphs, or metadata were altered.

---

## 1. Corpus Inventory Overview

The legal corpus in `kag-legal-assistant/data` consists of official Vietnamese legal documents spanning two major technological and regulatory domains:
1. **Cybersecurity & Data Privacy (`vn_an_ninh_mang`)**
2. **Artificial Intelligence & Digital Technology (`vn_ai`)**

### Summary Statistics
- **Total Registered Legal Documents**: 22 documents + 1 portal lookup catalog.
- **Raw Formats**: HTML (9 files), PDF (6 files), DOCX (8 files).
- **Processed Text**: Markdown format with structured Article/Clause demarcations.
- **Metadata Coverage**: 100% of documents have structured JSON metadata (`data/metadata/*.json`) detailing legal validity, issuing authority, and article counts.
- **Knowledge Graph**:
  - `data/graph/nodes.json`: Legal concepts, articles, decrees, and ministry entities.
  - `data/graph/edges.json`: Inter-document cross-references, amendment relations, detailing relationships.

---

## 2. Document Catalog & Applicability Analysis

| Document ID | Type | Title / Subject | Articles | Suitability for A0 vs A1 Experiments |
|---|---|---|---|---|
| **116-2025-QH15** | Luật | Luật An ninh mạng (2025) | 45 | **High**: Ideal for multi-aspect queries (prohibitions, system classification). |
| **24-2018-QH14** | Luật | Luật An ninh mạng (2018) | 43 | **High**: Ideal for historical conflict & norm supersession testing. |
| **13-2023-ND-CP** | Nghị định | Bảo vệ dữ liệu cá nhân | 44 | **High**: Cross-document referencing with Decrees 356 and 330. |
| **330-2026-ND-CP**| Nghị định | Xử phạt vi phạm hành chính an ninh mạng | 82 | **Critical**: Benchmark standard for penalty aspects in multi-aspect queries. |
| **328-2026-ND-CP**| Nghị định | Phòng chống tin giả, tin sai sự thật | 24 | **Medium**: Single-aspect & procedural queries. |
| **331-2026-ND-CP**| Nghị định | Bảo vệ an ninh mạng hệ thống thông tin | 40 | **Medium**: Critical infrastructure security level assessments. |
| **332-2026-ND-CP**| Nghị định | Kinh doanh sản phẩm, dịch vụ an ninh mạng | 22 | **Medium**: Licensing conditions and procedures. |
| **333-2026-ND-CP**| Nghị định | Biện pháp thi hành Luật An ninh mạng | 32 | **Medium**: Law enforcement and data localization measures. |
| **341-2026-ND-CP**| Nghị định | Mật mã dân sự | 35 | **Medium**: Cryptography product licensing and compliance. |
| **356-2025-ND-CP**| Nghị định | Chi tiết Luật Bảo vệ dữ liệu cá nhân | 42 | **High**: Cross-referencing with Law 91/2025/QH15. |
| **53-2022-ND-CP** | Nghị định | Chi tiết một số điều Luật An ninh mạng | 30 | **High**: Prior decree for contradiction / transition evaluation. |
| **86-2015-QH13** | Luật | Luật An toàn thông tin mạng | 54 | **High**: Overlapping jurisdiction and definitions. |
| **91-2025-QH15** | Luật | Luật Bảo vệ dữ liệu cá nhân | 39 | **High**: Primary substantive law on personal data protection. |
| **134-2025-QH15**| Luật | Luật Trí tuệ nhân tạo | 35 | **Critical**: High-risk AI system requirements and transparency obligations. |
| **142-2026-ND-CP**| Nghị định | Chi tiết Luật Trí tuệ nhân tạo | 38 | **Critical**: Specific regulatory thresholds for AI models. |
| **71-2025-QH15** | Luật | Luật Công nghiệp công nghệ số | 60 | **Medium**: Digital asset and semiconductor provisions. |
| **05-2026-TT-BKHCN**| Thông tư | Khung đạo đức trí tuệ nhân tạo quốc gia | 5 | **High**: Ethical guidelines vs legally binding rules (distinction testing). |
| **127-QD-TTg**   | Quyết định | Chiến lược quốc gia AI đến 2030 | 14 p. | **Medium**: National policy goals (unanswerable for legal penalties). |
| **1528-QD-TTg**  | Quyết định | Chương trình phát triển nhân lực AI | 12 p. | **Low**: Education and human resource policy. |
| **1671-QD-TTg**  | Quyết định | Chiến lược quốc gia AI 2030 tầm nhìn 2050 | 15 p. | **Medium**: Strategic planning norms. |
| **367-QD-TTg**   | Quyết định | Kế hoạch triển khai Luật Trí tuệ nhân tạo | 10 p. | **Medium**: Administrative timeline. |

---

## 3. Evaluation Readiness Assessment

### Current Ground-Truth Status
1. **Corpus Quality**: The processed legal corpus is verified and synchronized with metadata (`audit/dataset_inventory_and_audit.csv`).
2. **Pre-existing Query Benchmark**: The repository currently lacks a pre-existing annotated benchmark dataset containing ground-truth evidence receipts, atomic claim entailment pairs, and multi-aspect query specifications.
3. **Implications for Official Empirical Research**:
   - For an official empirical paper comparing A0 and A1, human legal expert annotation or structured semi-synthetic annotation is necessary to generate 50–100 benchmark queries across the 4 strata (Single-Aspect, Multi-Aspect, Conflicting, and Unanswerable).
   - Each query requires:
     * `required_aspects` list
     * `expected_doc_ids` list
     * Reference ground-truth text
     * Verified chunk IDs and entailment relationships for automated scoring.

### Offline Dry-Run Strategy (Immediate Scope)
To validate the **harness, evaluation metrics, and unified runner execution** without incurring external costs or fabricating empirical scientific findings:
- Construct a standard 8-question synthetic evaluation suite (`benchmark/synthetic_sample_dataset.jsonl`) representing all 4 benchmark strata.
- Run the offline benchmark runner against both A0 and A1.
- Produce verified execution logs, metric outputs, and JSONL traces clearly designated as **HARNESS VALIDATION**.
