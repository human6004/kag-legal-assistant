# Real Corpus Verification, Validity Status & Index Readiness Report

**Verification Date**: 2026-09-21  
**Target Path**: `D:\Dev\Workspaces\KAG\kag-legal-assistant\data`  
**Auditor**: Multi-Agent Research Lane (Agent D)  
**Status**: READ-ONLY AUDIT COMPLETE — CORPUS VALIDATED, INDEXING PREREQUISITES IDENTIFIED  

---

## 1. Physical Verification of Corpus & Legal Status

A complete physical audit of `kag-legal-assistant/data` verified 23 full-text Markdown legal documents and 25 metadata JSONs:

| Document ID | Document Type | Legal Status | Markdown File (Bytes) | Title / Subject |
|---|---|---|---|---|
| **116-2025-QH15** | Luật | Còn hiệu lực | 116-2025-QH15_...md (103 KB) | Luật An ninh mạng (2025) |
| **134-2025-QH15** | Luật | Còn hiệu lực | 134-2025-QH15_...md (66 KB) | Luật Trí tuệ nhân tạo |
| **91-2025-QH15**  | Luật | Còn hiệu lực | 91-2025-QH15_...md (87 KB) | Luật Bảo vệ dữ liệu cá nhân |
| **05-2026-TT-BKHCN**| Thông tư | Còn hiệu lực | 05-2026-TT-BKHCN_...md (18 KB) | Khung đạo đức trí tuệ nhân tạo quốc gia |
| **142-2026-ND-CP**| Nghị định | Còn hiệu lực | 142-2026-ND-CP_...md (251 KB) | Quy định chi tiết Luật Trí tuệ nhân tạo |
| **329-2026-ND-CP**| Nghị định | Còn hiệu lực | 329-2026-ND-CP_...md (38 KB) | Lực lượng bảo vệ an ninh mạng |
| **330-2026-ND-CP**| Nghị định | Còn hiệu lực | 330-2026-ND-CP_...md (210 KB) | Xử phạt vi phạm hành chính an ninh mạng |
| **331-2026-ND-CP**| Nghị định | Còn hiệu lực | 331-2026-ND-CP_...md (83 KB) | Bảo vệ an ninh mạng hệ thống thông tin |
| **332-2026-ND-CP**| Nghị định | Còn hiệu lực | 332-2026-ND-CP_...md (48 KB) | Kinh doanh sản phẩm, dịch vụ an ninh mạng |
| **333-2026-ND-CP**| Nghị định | Còn hiệu lực | 333-2026-ND-CP_...md (63 KB) | Biện pháp thi hành Luật An ninh mạng |
| **341-2026-ND-CP**| Nghị định | Còn hiệu lực | 341-2026-ND-CP_...md (78 KB) | Hoạt động mật mã dân sự |
| **356-2025-ND-CP**| Nghị định | Còn hiệu lực | 356-2025-ND-CP_...md (92 KB) | Quy định chi tiết Luật Bảo vệ dữ liệu cá nhân |
| **367-QD-TTg**   | Quyết định | Còn hiệu lực | 367-QD-TTg_...md (22 KB) | Kế hoạch triển khai thi hành Luật AI |
| **1528-QD-TTg**  | Quyết định | Còn hiệu lực | 1528-QD-TTg_...md (49 KB) | Chương trình phát triển nhân lực AI |
| **1671-QD-TTg**  | Quyết định | Còn hiệu lực | 1671-QD-TTg_...md (36 KB) | Chiến lược quốc gia phát triển AI |
| **328-2026-ND-CP**| Nghị định | Chưa có hiệu lực | 328-2026-ND-CP_...md (41 KB) | Phòng, chống tin giả, tin sai sự thật |
| **35-2018-QH14**  | Luật | Một phần hết hiệu lực | 35-2018-QH14_...md (75 KB) | Sửa đổi 37 luật liên quan quy hoạch |
| **71-2025-QH15**  | Luật | Một phần hết hiệu lực | 71-2025-QH15_...md (145 KB) | Luật Công nghiệp công nghệ số |
| **24-2018-QH14**  | Luật | Hết hiệu lực | 24-2018-QH14_...md (88 KB) | Luật An ninh mạng (2018) |
| **53-2022-ND-CP** | Nghị định | Hết hiệu lực | 53-2022-ND-CP_...md (58 KB) | Quy định chi tiết Luật An ninh mạng (cũ) |
| **86-2015-QH13**  | Luật | Hết hiệu lực | 86-2015-QH13_...md (112 KB) | Luật An toàn thông tin mạng |
| **13-2023-ND-CP** | Nghị định | Hết hiệu lực | 13-2023-ND-CP_...md (76 KB) | Bảo vệ dữ liệu cá nhân (cũ) |
| **127-QD-TTg**   | Quyết định | Hết hiệu lực | 127-QD-TTg_...md (37 KB) | Chiến lược quốc gia AI đến 2030 (cũ) |
| *bo-cong-an-csdl*| Portal | Không áp dụng | *(Trang thông tin tra cứu, không có MD)* | Cơ sở dữ liệu văn bản Bộ Công an |
| *mst-gov-vn*     | Portal | Không áp dụng | *(Trang thông tin tra cứu, không có MD)* | Cổng thông tin Bộ KH&CN |

---

## 2. Knowledge Graph and Index Readiness

1. **Seed Knowledge Graph (`data/graph/`)**:
   - `nodes.json`: Exactly 30 conceptual nodes.
   - `edges.json`: Exactly 38 conceptual edges.
   - **Finding**: High-level seed graph only. Not an article-level or clause-level traversal graph.
2. **Chunk Index Status**:
   - **0 persisted vector or chunk index files** found on disk (no FAISS, Milvus, SQLite, or Parquet chunks).

---

## 3. Minimal Prerequisites for Joint A0 vs A1 Retrieval Snapshot

To ensure scientific validity and 100% comparability between Baseline A0 and Evidence-Aware A1, both configurations must query an identical frozen snapshot.

### Required Steps for Data/Index Preparation Session (For Owner Approval):
1. **Deterministic Text Chunking**:
   - Execute an isolated chunking script across all 23 Markdown documents (e.g., 512-token chunks with 64-token overlap, aligned to Article/Clause headers).
   - Persist into an immutable `corpus_chunks.jsonl` with sha256 checksum.
2. **Offline Vector Indexing**:
   - Run local embedding generation (e.g., `bkai-foundation-models/vietnamese-bi-encoder` or `bge-m3`) to build a local FAISS index.
3. **Graph Expansion / Article Linking (Optional for Graph RAG)**:
   - Generate Article-to-Clause subgraphs or maintain the frozen 30-node seed graph.
4. **Local NLI Verifier Deployment**:
   - Deploy a local NLI model (e.g., `xlm-roberta-large-xnli` or fine-tuned PhoBERT) as the runtime semantic verifier for A1 to remove the `ONLINE_BENCHMARK_BLOCKED` gate.
