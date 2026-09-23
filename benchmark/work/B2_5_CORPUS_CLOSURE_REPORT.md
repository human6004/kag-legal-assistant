# B2.5C CORPUS CLOSURE REPORT

## Benchmark Scope & Methodology Note

The benchmark evaluates legal retrieval and generation across three architectural paradigms (**KAG**, **HybridRAG**, and **NativeRAG**) over a fixed knowledge corpus consisting of 23 legal documents situated in `data/processed/**`.

**Benchmark Ground Truth Definition:**
- Benchmark ground truth is strictly defined against the text, article/clause/point structure, and semantics of this fixed 23-document corpus.
- Any benchmark item labeled `CORPUS_READY` has been verified directly against the corresponding Markdown documents in `data/processed/**`.
- `CORPUS_READY` indicates that:
  1. The document exists in `data/processed/**`.
  2. The cited article/clause/point hierarchy exists in that document.
  3. The `gold_evidence` text is present character-for-character (or normalized whitespace) in that exact location.
  4. The question is answerable from that evidence.
  5. All `gold_markers` are supported by the evidence.
- `CORPUS_READY` does **not** mean independently official-source verified via external scanned PDFs.

**Methodology & Distinction between Corpus Verification and Supplementary Official Audit:**
- The benchmark evaluates retrieval and generation over a fixed corpus. Therefore benchmark gold is defined by the content of that fixed corpus.
- Official-source verification is maintained as an additional provenance and legal-quality audit, but inability to machine-read an official scanned representation (due to image scans lacking OCR layers on official portals) does not make a corpus-grounded benchmark item invalid.
- Accordingly:
  - **150/150 CORPUS_READY**: All 150 benchmark items are fully verified against the benchmark corpus.
  - **135/150 independently OFFICIAL_VERIFIED in the supplementary audit**: 135 items have external official portal text backing, 14 items were blocked solely due to image-only PDF scans without OCR on government websites, and 1 item (Q097) required corpus repair.

---

## Previous Official Audit Summary

From the initial supplementary official audit (`B2_5_OFFICIAL_VERIFICATION.json` / `B2_5_OFFICIAL_VERIFICATION_REPORT.md`):
- **OFFICIAL_VERIFIED**: 135 items
- **Official-source unresolved (BLOCKER)**: 14 items
  - Root cause: Official documents on `vanban.chinhphu.vn` or `congbao.chinhphu.vn` were published as scanned image-only PDFs without digital text layers (XObject `/Im0`, no fonts), and the local audit environment has no OCR tools installed.
- **MINOR_REPAIR**: 1 item (Q097)
  - Root cause: Question asked two sub-questions (effective date and status of Decree 13/2023), but candidate gold evidence only included clause 2.

The official audit record (`benchmark/work/B2_5_OFFICIAL_VERIFICATION.json` and its report) is retained completely unchanged for provenance and traceability.

---

## Corpus Closure for the 14 Blocked Items

All 14 items blocked in the official-source scan audit have been re-verified directly against the fixed Markdown corpus (`data/processed/**`):

| ID | Category | Document ID | Corpus File | Article | Clause / Point | Evidence Check | Markers Check | Corpus Status |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Q008** | `definition` | 86/2015/QH13 | `vn_an_ninh_mang/86-2015-QH13_luat-an-toan-thong-tin-mang.md` | 3 | Clause 4, Point null | PASS (Exact match) | PASS | `CORPUS_READY` |
| **Q009** | `definition` | 86/2015/QH13 | `vn_an_ninh_mang/86-2015-QH13_luat-an-toan-thong-tin-mang.md` | 3 | Clause 11, Point null | PASS (Exact match) | PASS | `CORPUS_READY` |
| **Q032** | `obligation` | 86/2015/QH13 | `vn_an_ninh_mang/86-2015-QH13_luat-an-toan-thong-tin-mang.md` | 7 | Clause 5, Point null | PASS (Exact match) | PASS | `CORPUS_READY` |
| **Q045** | `obligation` | 367/QĐ-TTg | `vn_ai/367-QD-TTg_ke-hoach-trien-khai-thi-hanh-luat-tri-tue-nhan-tao.md` | 3 | Clause 3 / Plan tasks, Point null | PASS (Exact match) | PASS | `CORPUS_READY` |
| **Q067** | `sanction_numeric` | 86/2015/QH13 | `vn_an_ninh_mang/86-2015-QH13_luat-an-toan-thong-tin-mang.md` | 32 | Clause 3, Point null | PASS (Exact match) | PASS | `CORPUS_READY` |
| **Q087** | `effectiveness_metadata` | 86/2015/QH13 | `vn_an_ninh_mang/86-2015-QH13_luat-an-toan-thong-tin-mang.md` | 53 | Clause null, Point null | PASS (Exact match) | PASS | `CORPUS_READY` |
| **Q092** | `inter_document` | 35/2018/QH14 | `vn_an_ninh_mang/35-2018-QH14_sua-doi-37-luat-lien-quan-quy-hoach.md` | 2 | Clause 2, Point null | PASS (Exact match) | PASS | `CORPUS_READY` |
| **Q093** | `inter_document` | 35/2018/QH14 | `vn_an_ninh_mang/35-2018-QH14_sua-doi-37-luat-lien-quan-quy-hoach.md` | 18 | Clause null, Point null | PASS (Exact match) | PASS | `CORPUS_READY` |
| **Q094** | `inter_document` | 35/2018/QH14 | `vn_an_ninh_mang/35-2018-QH14_sua-doi-37-luat-lien-quan-quy-hoach.md` | 8 | Clause 4, Point null | PASS (Exact match) | PASS | `CORPUS_READY` |
| **Q095** | `inter_document` | 86/2015/QH13 & 35/2018/QH14 | `vn_an_ninh_mang/86-2015-QH13_luat-an-toan-thong-tin-mang.md`<br>`vn_an_ninh_mang/35-2018-QH14_sua-doi-37-luat-lien-quan-quy-hoach.md` | 51 (Luật 86), 18 (Luật 35) | Clause 1 (Luật 86), Clause null (Luật 35) | PASS (Exact match on both legs) | PASS | `CORPUS_READY` |
| **Q102** | `inter_document` | 367/QĐ-TTg | `vn_ai/367-QD-TTg_ke-hoach-trien-khai-thi-hanh-luat-tri-tue-nhan-tao.md` | 3 | Clause null, Point null | PASS (Exact / Normalized match) | PASS | `CORPUS_READY` |
| **Q110** | `inter_document` | 35/2018/QH14 | `vn_an_ninh_mang/35-2018-QH14_sua-doi-37-luat-lien-quan-quy-hoach.md` | 27 | Clause null, Point null | PASS (Exact match) | PASS | `CORPUS_READY` |
| **Q122** | `multi_hop` | 86/2015/QH13 | `vn_an_ninh_mang/86-2015-QH13_luat-an-toan-thong-tin-mang.md` | 40, 45 | Clause 2 (Điều 40), Clause 3 (Điều 45) | PASS (Exact match on both legs) | PASS | `CORPUS_READY` |
| **Q135** | `multi_hop` | 367/QĐ-TTg | `vn_ai/367-QD-TTg_ke-hoach-trien-khai-thi-hanh-luat-tri-tue-nhan-tao.md` | 2, 3 | Clause null, Point null | PASS (Exact match on both legs) | PASS | `CORPUS_READY` |

Every single one of the 14 items is verified with full hierarchy checking (`document -> article -> clause -> point`), evidence exact matching, question coverage, and marker support against the fixed corpus.

---

## Q097 Corpus Repair

**Question**: *"Nghị định 356/2025/NĐ-CP có hiệu lực thi hành từ ngày nào và Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân sẽ như thế nào?"*

### Before Repair (`final_150_candidate.json`)
- **gold_evidence**:
  ```json
  [
    {
      "document_id": "356/2025/NĐ-CP",
      "article": "42",
      "clause": "2",
      "point": null,
      "text": "2. Nghị định số 13/2023/NĐ-CP ngày 17 tháng 4 năm 2023 của Chính phủ về bảo vệ dữ liệu cá nhân hết hiệu lực kể từ ngày Nghị định này có hiệu lực thi hành."
    }
  ]
  ```
- **gold_markers**:
  ```json
  [
    "Nghị định số 13/2023/NĐ-CP",
    "hết hiệu lực kể từ ngày Nghị định này có hiệu lực thi hành"
  ]
  ```
- **Deficiency**: The first part of the question (*"có hiệu lực thi hành từ ngày nào"*) was not covered by the gold evidence (which only cited Clause 2).

### After Repair (`final_150_corpus_verified.json`)
- **gold_evidence**:
  ```json
  [
    {
      "document_id": "356/2025/NĐ-CP",
      "article": "42",
      "clause": "1",
      "point": null,
      "text": "1. Nghị định này có hiệu lực thi hành từ ngày 01 tháng 01 năm 2026."
    },
    {
      "document_id": "356/2025/NĐ-CP",
      "article": "42",
      "clause": "2",
      "point": null,
      "text": "2. Nghị định số 13/2023/NĐ-CP ngày 17 tháng 4 năm 2023 của Chính phủ về bảo vệ dữ liệu cá nhân hết hiệu lực kể từ ngày Nghị định này có hiệu lực thi hành."
    }
  ]
  ```
- **gold_markers**:
  ```json
  [
    "01 tháng 01 năm 2026",
    "Nghị định số 13/2023/NĐ-CP",
    "hết hiệu lực kể từ ngày Nghị định này có hiệu lực thi hành"
  ]
  ```
- **Result**: Fully answers both sub-questions; both clauses verified with 100% exact character match in `data/processed/vn_an_ninh_mang/356-2025-ND-CP_quy-dinh-chi-tiet-luat-bao-ve-du-lieu-ca-nhan.md`. Question, category (`inter_document`), ID (`Q097`), and source ID (`C086`) remain unchanged.

---

## Final Corpus-Verified Dataset

- Output file: `benchmark/work/final_150_corpus_verified.json`
- Total records: **150**
- Substantive preservation: All 149 other questions are 100% byte-equivalent on substantive fields (`question`, `category`, `answerable`, `gold_markers`, `gold_evidence`). Only Q097 underwent the audited corpus repair.

### Category Distribution
| Category | Target Count | Verified Dataset Count | Status |
| :--- | :---: | :---: | :---: |
| `definition` | 20 | 20 | PASS |
| `obligation` | 25 | 25 | PASS |
| `sanction_numeric` | 25 | 25 | PASS |
| `effectiveness_metadata` | 20 | 20 | PASS |
| `inter_document` | 20 | 20 | PASS |
| `multi_hop` | 25 | 25 | PASS |
| `unanswerable` | 15 | 15 | PASS |
| **Total** | **150** | **150** | **PASS** |

### Answerability Distribution
- `answerable = true`: 135
  - All 135 items have non-empty `gold_evidence` and non-empty `gold_markers`.
- `answerable = false`: 15 (Q136–Q150)
  - All 15 items have empty `gold_evidence` (`[]`) and empty `gold_markers` (`[]`).
  - Answerability is defined strictly against the fixed 23-document benchmark corpus: insufficient evidence within the 23 documents implies unanswerable.

---

## Validation Summary

| Check | Expected | Actual | Result |
| :--- | :---: | :---: | :---: |
| Total items | 150 | 150 | **PASS** |
| ID continuity | Q001–Q150 | Q001–Q150 | **PASS** |
| 7 Category distribution | Exact target breakdown | Exact target breakdown | **PASS** |
| Answerability split | 135 True / 15 False | 135 True / 15 False | **PASS** |
| Answerable evidence & markers non-empty | 135 items | 135 items | **PASS** |
| Unanswerable evidence & markers empty | 15 items | 15 items | **PASS** |
| Hierarchy integrity (`point_without_clause`) | 0 | 0 | **PASS** |
| Forbidden retrieval / graph IDs | 0 | 0 | **PASS** |
| Q097 repair compliance | D42.1 + D42.2 + 01/01/2026 | Verified | **PASS** |
| Byte equivalence for other 149 items | 149/149 identical | 149/149 identical | **PASS** |

---

## Overall Assessment

**B2.5C READY FOR REVIEW**
