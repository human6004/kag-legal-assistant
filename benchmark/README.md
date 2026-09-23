# Common Benchmark — Hướng dẫn sử dụng

Harness đánh giá chung, trung lập kiến trúc, để so sánh **KAG**, **HybridRAG** và **NativeRAG** trên bài toán hỏi–đáp pháp luật tiếng Việt.

Tài liệu này ưu tiên phần **cách chạy / nộp kết quả**. Chi tiết metric và evaluator nằm ở cuối.

---

## 1. Quick start

1. Đọc bộ câu hỏi chuẩn: `benchmark/work/final_150_corpus_verified.json` (đúng **150** câu).
2. Cho hệ thống của bạn chạy retrieval + generation trên **đúng 150 câu đó** (không sửa câu hỏi; không dùng gold để “giúp” trả lời).
3. Chuyển output gốc của hệ thống sang đúng shape `benchmark/system_output_schema.json`.
4. **Citations** chỉ được parse từ **nội dung `answer`** bằng `benchmark/adapters/citation_parser.py` — **không** copy từ `retrieved_contexts`.
5. Chạy evaluator:

```bash
python -m benchmark.evaluator.evaluate \
  --dataset benchmark/work/final_150_corpus_verified.json \
  --system-output <system-output.json> \
  --out <report.json> \
  --k 1,3,5,10 \
  --budgets 2000 \
  --judge null
```

PowerShell (dùng backtick để xuống dòng):

```powershell
python -m benchmark.evaluator.evaluate `
  --dataset benchmark/work/final_150_corpus_verified.json `
  --system-output <system-output.json> `
  --out <report.json> `
  --k 1,3,5,10 `
  --budgets 2000 `
  --judge null
```

6. Kiểm tra unit test evaluator (không chạy hệ thống RAG):

```bash
python -m pytest benchmark/tests -q
```

---

## 2. Trạng thái canonical dataset

| Mốc | Trạng thái |
|---|---|
| **B1** — protocol, schema, evaluator, metrics, unit tests | **DONE** |
| **B2** — xây dựng bộ câu hỏi | **DONE** |
| **B2.5C** — đóng / xác minh corpus | **DONE** |
| **B3.1** — common runner/adapter | **CÓ CODE, CHƯA FREEZE** (chưa chạy 150 câu) |

- Canonical dataset: `benchmark/work/final_150_corpus_verified.json`
- **Chưa** có kết quả benchmark 3 hệ thống trong repo từ evaluator này; đừng giả định `benchmark/runs/*.json` đã tồn tại.
- Runner/adapter B3.1 đã có; cấu hình và kết quả vẫn chờ B3.2.

---

## 3. Canonical dataset

**Đường dẫn:** `benchmark/work/final_150_corpus_verified.json`

- **150** câu hỏi
- Corpus cố định **23** văn bản (cùng tập tài liệu pháp lý dùng chung; gold evidence trong file phủ các văn bản được trích dẫn)
- Mọi item có `verification_status: CORPUS_VERIFIED`
- 7 categories (đếm thực tế trong file):

| `category` | Số câu |
|---|---|
| `definition` | 20 |
| `obligation` | 25 |
| `sanction_numeric` | 25 |
| `effectiveness_metadata` | 20 |
| `inter_document` | 20 |
| `multi_hop` | 25 |
| `unanswerable` | 15 |
| **Tổng** | **150** |

Mỗi item tối thiểu gồm: `id`, `question`, `category`, `answerable`, cùng gold trung lập kiến trúc (`gold_evidence`, `gold_markers`, …) theo `benchmark/benchmark_schema.json`. Gold **không** chứa `chunk_id` / `vector_id` / `node_id` của bất kỳ hệ thống nào.

---

## 4. Workflow — “Tôi cần làm gì?”

### STEP 1 — Đọc dataset, chạy đúng 150 câu

- Load `benchmark/work/final_150_corpus_verified.json`.
- Chạy **đúng** 150 câu (`id` + `question` như trong file).
- Không rút gọn, không thay wording, không bỏ câu `unanswerable`.

### STEP 2 — Hệ thống tự retrieval + generation

- Hệ thống dùng pipeline của mình (index / graph / vector / LLM).
- **Không** đọc `gold_evidence` / `gold_markers` / `gold_claims` để soạn câu trả lời.
- Gold chỉ dùng khi **evaluate**, không dùng khi **sinh** answer.

### STEP 3 — Map sang `system_output_schema.json`

- Output gốc của KAG / HybridRAG / NativeRAG khác nhau.
- Adapter (hoặc script chuyển đổi) phải emit đúng contract trong `benchmark/system_output_schema.json`.
- File có thể là mảng JSON thuần, hoặc object có key `outputs` / `results`.

### STEP 4 — Một record / một câu hỏi

Mỗi record cần các field sau (xem schema để biết kiểu đầy đủ):

| Field | Ý nghĩa |
|---|---|
| `question_id` | Khớp `BenchmarkItem.id` trong dataset |
| `system` | Tên hệ thống: `"kag"` / `"hybridrag"` / `"nativerag"` (thống nhất trong một file) |
| `answer` | Câu trả lời (string hoặc `null` nếu lỗi) |
| `retrieved_contexts` | Danh sách context đã retrieve (xem mục 6) |
| `citations` | Trích dẫn **trong answer** — xem mục 5 (CRITICAL) |
| `latency_ms` | Thời gian end-to-end (ms), hoặc `null` |
| `error` | `null` nếu OK; string mô tả lỗi nếu fail (metric sẽ *unavailable*, không bị coi là 0) |

Ví dụ tối thiểu:

```json
{
  "question_id": "…",
  "system": "hybridrag",
  "answer": "…",
  "retrieved_contexts": [
    {
      "rank": 1,
      "document_id": "13/2023/NĐ-CP",
      "article": "8",
      "clause": "2",
      "point": null,
      "text": "…",
      "score": null
    }
  ],
  "citations": [
    {"document_id": "13/2023/NĐ-CP", "article": "8", "clause": "2", "point": null}
  ],
  "latency_ms": 1234,
  "error": null
}
```

---

## 5. CITATIONS — CRITICAL

`citations[]` = những gì **câu trả lời thực sự chỉ ra**, parse từ **`answer` text**.

- Dùng `benchmark/adapters/citation_parser.py` (`parse_citations` / `parse_citation_payloads`).
- **CẤM** copy từ `retrieved_contexts`, metadata chunk, hay field “citations” kiểu danh sách tài liệu retrieve của engine.
- Nếu retrieve được Điều 5 nhưng **answer không trích** Điều 5 → **không** thêm citation Điều 5.
- Lý do: NativeRAG `rag_core/engine.py` có thể trả retrieved docs dưới tên `citations`; copy nguyên field đó sẽ làm Citation Recall ≈ retrieval recall mà answer không hề trỏ nguồn.
- Tag kiểu `<reference id="chunk:…">` của KAG bị parser bỏ qua (trỏ trace log, không phải vị trí pháp lý).
- Citation không ghi số hiệu văn bản sẽ kế thừa document gần nhất xuất hiện **trước** nó trong cùng answer — cùng một rule cho cả ba hệ thống.

Evaluator có thể ghi **note** nếu `citations` trùng hệt `retrieved_contexts` (mirror); đó là cảnh báo, không phải reject cứng.

---

## 6. Định dạng `retrieved_contexts`

Mỗi phần tử map:

| Field | Ghi chú |
|---|---|
| `rank` | 1-based; nếu bỏ trống, loader lấy vị trí trong list |
| `document_id` | Số hiệu / id văn bản pháp lý (không phải chunk id nội bộ) |
| `article` / `clause` / `point` | Nhãn cấu trúc; thiếu thì `null` — **không bịa** |
| `text` | Nội dung passage đã retrieve |
| `score` | Được phép `null`; **không** so sánh score giữa các kiến trúc |

Đừng bịa metadata. Đừng dùng id chunk/vector/node của một hệ thống làm `document_id` chung.

---

## 7. Tên hệ thống (`system`)

Trong một file output, dùng nhất quán một trong:

- `"kag"`
- `"hybridrag"`
- `"nativerag"`

---

## 8. File output khuyến nghị

Khuyến nghị (chưa bắt buộc tạo sẵn thư mục):

```text
benchmark/runs/kag.json
benchmark/runs/hybridrag.json
benchmark/runs/nativerag.json
```

Runner tạo thư mục output khi chạy. B3.1 chưa sinh kết quả chính thức.

---

## 9. Lệnh evaluate (đã đối chiếu CLI)

Entry: `python -m benchmark.evaluator.evaluate`  
File: `benchmark/evaluator/evaluate.py`

Flag thực tế (đã verify trong code):

| Flag | Bắt buộc | Mặc định / ghi chú |
|---|---|---|
| `--dataset` | yes | JSON dataset (`benchmark_schema.json`) |
| `--system-output` | yes | JSON output (`system_output_schema.json`) |
| `--out` | no | Ghi full JSON report |
| `--system` | no | Override tên hệ thống trong report |
| `--k` | no | mặc định `1,3,5,10` (`DEFAULT_K_VALUES`) |
| `--budgets` | no | mặc định `2000` (`PAPER_CONTEXT_BUDGET`) |
| `--judge` | no | chỉ `"null"` trên CLI |
| `--bootstrap-samples` / `--seed` / `--no-bootstrap` | no | CI |
| `--no-per-question` | no | Bỏ per-question khi ghi `--out` |

Lệnh chuẩn để so sánh công bằng:

```bash
python -m benchmark.evaluator.evaluate \
  --dataset benchmark/work/final_150_corpus_verified.json \
  --system-output <system-output.json> \
  --out <report.json> \
  --k 1,3,5,10 \
  --budgets 2000 \
  --judge null
```

PowerShell:

```powershell
python -m benchmark.evaluator.evaluate `
  --dataset benchmark/work/final_150_corpus_verified.json `
  --system-output <system-output.json> `
  --out <report.json> `
  --k 1,3,5,10 `
  --budgets 2000 `
  --judge null
```

`--k` nên gồm `5` và `--budgets` nên gồm `2000` (đây cũng là default) để bảng headline đủ hàng.

---

## 10. Rules everyone must follow (công bằng)

1. Cùng một file dataset: `benchmark/work/final_150_corpus_verified.json`.
2. Cùng evaluator: `python -m benchmark.evaluator.evaluate` (package `benchmark/`, không import `kag` / `hybridRAG` / `nativeRAG`).
3. Cùng `--k`, `--budgets`, `--judge`, cùng cấu hình bootstrap khi công bố số.
4. Không sửa câu hỏi; không dùng gold lúc sinh answer.
5. `citations` chỉ từ answer text qua `citation_parser.py`.
6. Không bịa `document_id` / `article` / `clause` / `point`.
7. Không so sánh `score` giữa kiến trúc khác nhau.
8. Run lỗi: ghi `error` (không “điền” metric = 0 giả).
9. Kết quả 3 hệ thống chỉ được so khi cả ba đi qua **cùng** pipeline evaluate ở trên.

---

## 11. Phân biệt Dataset / System output / Evaluation report

```text
+-------------------------------------+
|  Dataset (gold)                     |
|  final_150_corpus_verified.json     |
|  schema: benchmark_schema.json      |
+------------------+------------------+
                   |
                   |  hệ thống chạy 150 câu
                   v
+-------------------------------------+
|  System output                      |
|  ví dụ: benchmark/runs/<system>.json|
|  schema: system_output_schema.json  |
+------------------+------------------+
                   |
                   |  python -m benchmark.evaluator.evaluate
                   v
+-------------------------------------+
|  Evaluation report                  |
|  <report.json>                      |
|  (micro / macro / per_question / CI)|
+-------------------------------------+
```

- **Dataset** = câu hỏi + gold trung lập kiến trúc.
- **System output** = answer + retrieved_contexts + citations (+ latency/error) của **một** hệ thống.
- **Report** = điểm số từ evaluator chung.

---

## 12. Nếu bạn chỉ phụ trách HybridRAG hoặc NativeRAG

1. Chạy đúng 150 câu từ canonical dataset bằng pipeline hệ thống của bạn.
2. Viết / dùng adapter map sang `system_output_schema.json`.
3. Parse citations bằng `benchmark/adapters/citation_parser.py` từ `answer`.
4. Xuất file (khuyến nghị `benchmark/runs/hybridrag.json` hoặc `benchmark/runs/nativerag.json`).
5. Chạy lệnh evaluate ở mục 9.
6. **Không** dùng bộ evaluate riêng của HybridRAG (`hybridRAG/evaluation/...`, RAGAS / production eval) làm số liệu so sánh 3 hệ thống — đó là harness nội bộ, khác contract chung.

---

## 13. Nếu bạn phụ trách KAG

Cùng workflow mục 4-9.

- **Không** dùng evaluator legacy KAG (`kag/solver/eval.py`, `gold_chunks`, marker/chunk nội bộ KAG) để so sánh 3 hệ thống.
- Legacy KAG vẫn có thể phục vụ nghiên cứu nội bộ KAG; so sánh chung **chỉ** qua `benchmark.evaluator.evaluate` + dataset canonical.
- Tag `<reference id="chunk:...">` không thay cho prose citation pháp lý trong `citations[]`.

---

## 14. Entrypoints hệ thống (runners)

Runner B3.1 dùng chung `benchmark/runners/common.py`: đọc đúng `id` + `question`, đo thời gian query đến answer + retrieval, ghi một output cho mỗi câu (lỗi ghi `error`). Citation luôn parse từ answer. Ba lệnh CLI thực tế (chạy từ root repo, sau khi chuẩn bị dependencies, API key và index của từng hệ thống):

```powershell
python -m benchmark.runners.kag_runner --dataset benchmark/work/final_150_corpus_verified.json --out benchmark/runs/kag.json
python -m benchmark.runners.hybridrag_runner --dataset benchmark/work/final_150_corpus_verified.json --out benchmark/runs/hybridrag.json
python -m benchmark.runners.nativerag_runner --dataset benchmark/work/final_150_corpus_verified.json --out benchmark/runs/nativerag.json
```

**Chưa chạy các lệnh này trên 150 câu trong B3.1.** KAG cần OpenSPG/config và prompt trong `kag/`; HybridRAG cần các dependency của API và index; NativeRAG cần LLM key. HybridRAG `load_vector_index()` hiện ưu tiên Chroma NativeRAG nếu có. NativeRAG đang cấu hình embedding `text-embedding-3-small` trong khi Chroma lưu chiều 3072; cần xác minh/sửa cấu hình trước khi chạy chính thức. B3.2 phải xác nhận index/config runtime và thống nhất generator. CLI `--help` và adapter contract đã được kiểm offline; chưa kiểm pipeline thật trên môi trường này.

---

## 15. Pytest

```bash
python -m pytest benchmark/tests -q
```

- Test **evaluator / schema / citation_parser / isolation** trên dữ liệu synthetic.
- Unit test offline **không** gọi KAG / HybridRAG / NativeRAG.
- Package `benchmark` cố ý nằm ngoài `kag/` và không import ba hệ thống (`tests/test_isolation.py`).

---

## 16. Layout thư mục (liên quan benchmark)

```text
benchmark/
  README.md                      file này
  benchmark_schema.json          contract dataset
  system_output_schema.json      contract system output
  work/
    final_150_corpus_verified.json   canonical 150 câu (B2 + B2.5C)
  evaluator/
    evaluate.py                  CLI + orchestration
    ...                          metrics / models / matching / ...
  adapters/
    citation_parser.py           parser citation chung
  runners/                       common.py + 3 adapter/CLI
  tests/                         unit tests offline
  runs/                          (khuyến nghị) chỗ để system output — có thể chưa có
```

Không tham chiếu các file work B2 tạm đã xóa (audit/gap/authoring/selection/candidate, ...). Canonical duy nhất cần cho chạy benchmark là `final_150_corpus_verified.json`.

---

# Phụ lục — Protocol & metrics (sau hướng dẫn thực dụng)

Phần dưới giữ lại hợp đồng kỹ thuật của harness. Đọc khi cần hiểu cách chấm; không cần để “chạy một lượt” lần đầu.

## A. Harness này là gì / không phải gì

**Có:** protocol đánh giá, 2 JSON schema, evaluator dùng chung, định nghĩa metric, unit test offline.

**Chưa có:** runner ba hệ thống đã freeze, retriever/generator/prompt dùng chung, hay file kết quả so sánh đã chạy xong.

Gold truth dùng ngôn ngữ của văn bản pháp luật:

```text
document -> article -> clause -> point -> evidence text -> gold claim
```

`benchmark_schema.json` và `evaluator/models.py` (`FORBIDDEN_DATASET_KEYS`) từ chối dataset mang id nội bộ hệ thống (`chunk_id`, `gold_chunks`, `vector_id`, `node_id`, ...).

## B. Dataset contract (tóm tắt)

| Field | Bắt buộc | Ý nghĩa |
|---|---|---|
| `id` | yes | id câu hỏi |
| `question` | yes | nội dung câu hỏi |
| `category` | yes | nhãn macro-average |
| `answerable` | yes | `false` = cố ý không trả lời được từ corpus |
| `gold_evidence[]` | với câu answerable | `{document_id, text, article, clause, point, required, ...}` |
| `gold_markers[]` / `gold_claims[]` | optional | marker / claim |

`clause` / `point` ghi để phân tích lỗi; độ sâu so sánh chính là **document + article**. `text` trong evidence là bắt buộc để cả ba hệ thống cùng có đường text-match.

## C. Catalogue metric (tóm tắt)

**Retrieval:** `evidence_recall`, `evidence_recall@k`, `evidence_recall_required`, `context_precision`, `hit@k`, `mrr`, `evidence_recall@Ntok` (ví dụ `@2000tok`).

**Answer:** `hit_rate`, `hit_all`, `claim_precision` / `claim_recall` / `claim_f1`.

**Grounding:** `faithfulness`, `hallucination_rate`, `retrieval_gap_rate`, `unsupported_claim_rate`.

**Citation:** `document_accuracy`, `article_accuracy`, `clause_accuracy` / `point_accuracy` (diagnostic), `citation_precision`, `citation_recall`.

**Unanswerable:** `correct_abstention`, `false_answer_rate`.

**Operational:** `latency_ms`, `error_rate`.

Paper profile ưu tiên metric **deterministic** (không cần LLM judge). Với `--judge null`, các metric phụ thuộc judge báo `None` / unavailable chứ không bịa 0.

`hallucination_rate` **không** phải `1 - faithfulness` (còn bucket retrieval gap và undecided).

## D. Evidence matching

Thứ tự: **structural** -> **text** -> **judge** (nếu có).  
Mismatch cứng ở `(document, article)` là hard negative. Mismatch `clause`/`point` không quyết định scoring so sánh — chuyển sang text route. Undecided != False.

## E. Normalization

`normalization.py`: NFC, strip markdown, collapse whitespace, dung sai dấu ngăn nghìn, fold dấu chỉ trên nhãn cấu trúc (`Điều`/`Khoản`/`Điểm`). **Không** gộp số điều khác nhau, không gộp số hiệu văn bản khác nhau, giữ phủ định và đơn vị tiền/tỷ lệ.

## F. Judge

CLI chỉ build `NullJudge` (`--judge null`). `RuleBasedJudge` / `ScriptedJudge` dùng nội bộ/test, không phải lựa chọn CLI công bố. Metric phụ thuộc judge chỉ vào paper khi đủ điều kiện độc lập / prompt pháp lý Việt / calibrate / `JudgeConfig` đóng băng — xem code `judge.py`.

## G. `None` không phải 0

- `not_applicable` — gold không đặt câu hỏi đó.
- `unavailable` — run lỗi hoặc thiếu judge.

Câu không có system output bị **loại khỏi trung bình**, không chấm 0.

## H. Aggregation

- **micro** — trung bình trên câu có giá trị thật.
- **macro** — trung bình theo category rồi trung bình các category.
- **95% CI** — bootstrap trên micro (seed cố định); macro không bootstrap.

## I. Giới hạn đã biết

- Không có contradiction từ `RuleBasedJudge` trên CLI.
- `claim_*` / `faithfulness` / `hallucination_rate` thường unavailable với `NullJudge` nếu adapter không cung cấp `answer_claims`.
- Clause/point agreement chỉ diagnostic.
- Đếm token budget là ước lượng không tokenizer (`max(words, ceil(chars/4))`) — nhất quán giữa hệ thống, không trùng tokenizer model cụ thể.
