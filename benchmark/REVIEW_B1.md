# B1 — Evaluator chung: nó chạy thế nào và nó có dùng được cho paper không

> Tài liệu này gồm hai phần: **(1)** giải thích luồng chấm điểm bằng một câu hỏi
> chạy thật từ đầu đến cuối, **(2)** đánh giá độc lập xem thiết kế hiện tại có
> phù hợp để viết báo hay đang quá phức tạp.
>
> Đọc 2 phút thì đọc mục "Tóm tắt". Đọc 15 phút thì đọc hết.

---

## Tóm tắt

**Nó làm gì.** B1 là một bộ chấm điểm dùng chung cho KAG, HybridRAG và NativeRAG.
Nó không chạy hệ thống nào cả — nó ăn hai file JSON (đề + đáp án, và bài làm của
một hệ) rồi trả về một bảng số. Chạy ba lần, mỗi hệ một lần, cùng một file đề,
cùng cấu hình → ba bảng đặt cạnh nhau.

**Điểm hay nhất.** Đáp án không chứa chunk id của bất kỳ hệ nào. Nó nói "sự thật
nằm ở Nghị định 13, Điều 63, Khoản 3, nội dung là chuỗi này" — ba hệ chia chunk
khác nhau hoàn toàn nhưng cả ba đều phải tìm ra *nội dung* đó. Đây là quyết định
đúng, và chính KAG gốc cũng làm vậy (xem mục "So với KAG gốc").

**Vấn đề.** Có hai lỗ hổng công bằng thật, nằm trong code, khiến `evidence_recall`
có thể đang thưởng cho *metadata phong phú hơn* thay vì *truy xuất tốt hơn* — và
KAG là hệ có metadata phong phú nhất. Cộng thêm việc bề mặt metric lớn gấp đôi
những gì một bảng paper dùng được.

**Kết luận.** Giữ nguyên framework, chỉ chốt lại một "paper profile" với ít metric
chính (**phương án B**). Nhưng phải sửa 6 blocker trước khi bắt đầu gán nhãn 150
câu, vì 4 trong số đó thay đổi *thứ mà người gán nhãn phải viết ra*.

**Trạng thái: B1 NOT READY FOR B2.**

---

# Phần 1 — Nó hoạt động thế nào

## 1.1 Ảnh tổng thể

```
benchmark.json          đề + đáp án — viết 1 lần, dùng chung cho cả 3 hệ
system_output.json      bài làm của 1 hệ — mỗi hệ 1 file
        │
        ▼
   models.py             nạp + kiểm tra + CHẶN chunk_id / node_id / gold_chunks
        │
        ▼
   evaluate_question()   chạy 1 lần cho mỗi (câu hỏi × hệ thống)
        │
        ├── retrieval_metrics    lấy đúng điều luật về chưa?
        ├── answer_metrics       câu trả lời có nói đúng số/mốc không?
        ├── grounding_metrics    câu trả lời có bịa không?
        ├── citation_metrics     trích dẫn có trỏ đúng Điều không?
        └── abstention_metrics   câu không trả lời được thì có biết từ chối không?
        │
        ▼
   aggregate.py          micro / macro theo category / bootstrap CI
        │
        ▼
   report.json + bảng in ra màn hình  (KHÔNG có điểm tổng)
```

Evaluator nằm **ngoài** `kag/` và không import `kag`, `hybridRAG` hay `nativeRAG`.
File `tests/test_isolation.py` ép điều đó về mặt cấu trúc, và còn ép luôn là cả gói
chỉ dùng thư viện chuẩn của Python.

## 1.2 Đề trông như thế nào

```json
{
  "id": "q042",
  "category": "muc_phat",
  "answerable": true,
  "question": "Làm lộ dữ liệu cá nhân bị phạt bao nhiêu tiền?",
  "gold_evidence": [
    { "document_id": "13/2023/NĐ-CP", "article": "63", "clause": "3",
      "text": "Phạt tiền từ 50.000.000 đồng đến 100.000.000 đồng đối với hành vi..." }
  ],
  "gold_markers": ["100.000.000 đồng"]
}
```

Điểm mấu chốt: **không có chunk id nào cả**.

Lý do: KAG chia văn bản theo đồ thị tri thức với id node/chunk riêng; HybridRAG và
NativeRAG dùng vector store với id riêng của chúng. Lấy chunk id của một hệ làm đáp
án chung nghĩa là bắt hai hệ kia phải tái tạo cách chia chunk của hệ đó. Schema
`benchmark_schema.json` **chủ động từ chối** các khoá như `chunk_id`, `node_id`,
`gold_chunks` — và có test pin lại đúng hình dạng file `kag/solver/data/gold_chunks.json`
cũ trong repo, để nó không bao giờ nạp được vào đây.

## 1.3 Bài làm trông như thế nào

```json
{ "question_id": "q042", "system": "kag",
  "answer": "Mức phạt là **100.000.000 đồng** theo Điều 63 khoản 3...",
  "retrieved_contexts": [
    { "rank": 1, "document_id": "13/2023/NĐ-CP", "article": "63", "clause": "3",
      "text": "Phạt tiền từ 50.000.000 đồng đến 100.000.000 đồng..." }
  ],
  "citations": [ { "document_id": "13/2023/NĐ-CP", "article": "63" } ],
  "latency_ms": 1234 }
```

Hai chi tiết đáng chú ý:

- `score` (điểm truy xuất) là tuỳ chọn và **không bao giờ được so sánh giữa các hệ**.
  Điểm của graph traversal và cosine similarity không cùng một đại lượng. Chỉ `rank`,
  `text` và metadata pháp lý được dùng để chấm.
- `error` khác null đánh dấu lần chạy hỏng. Metric của nó thành *unavailable*, **không
  bao giờ thành 0**. Một lần chạy crash không được phép trông giống một câu trả lời sai.

## 1.4 Trái tim: làm sao nó biết "lấy đúng rồi"

Đây là phần quan trọng nhất, nằm ở `evidence_matching.py`. Với **từng cặp** (1 context,
1 gold evidence), nó hỏi ba câu theo thứ tự:

```
Tuyến 1 — STRUCTURAL: vị trí pháp lý khai báo có khớp không?
   ├─ Lệch (context nói Điều 52, gold nói Điều 63) → FALSE, ĐÓNG LẠI.
   │                                                  Judge cũng không cứu được.
   ├─ Khớp hết mọi cấp mà gold khai → TRUE, xong luôn
   └─ Không lệch, nhưng context im lặng (không khai Điều) → chưa quyết được
        │
        ▼
Tuyến 2 — TEXT: chuỗi gold có nằm trong text của context không?
   ├─ Nằm trọn → TRUE
   ├─ Phủ ≥ 80% số token của gold → TRUE
   └─ Không → đi tiếp
        │
        ▼
Tuyến 3 — JUDGE: nhờ mô hình phán đoán ngữ nghĩa
   └─ Mặc định là NullJudge → trả UNKNOWN → kết quả là UNDECIDED (None)
```

Ba điều cần nhớ:

**Sai vị trí là chết ngay.** Đưa nguyên văn Điều 52 ra cho gold Điều 63 thì bị từ chối
thẳng, kể cả text có giống đến đâu. "Đúng nội dung, sai địa chỉ" trong luật là một
loại lỗi riêng, và nó được báo cáo riêng ở nhóm citation.

**`None` không phải `False`.** Nếu không tuyến nào quyết được thì kết quả là *không
biết* — nó không vào tử số, cũng không bị tính là sai, và được đếm riêng ở
`n_undecided`. Đây là chỗ phần lớn benchmark code làm ẩu (mặc định cho 0).

**Tuyến 2 chính là thứ làm ba hệ so được với nhau.** Một hệ chia chunk 2000 token chứa
cả E1 lẫn E2 → support cả hai. Hệ khác chia 200 token, mỗi chunk một cái → cũng support
cả hai. Cách chia chunk không còn ảnh hưởng đến điểm.

## 1.5 Rồi ra số gì

Với câu q042 ở trên, KAG khớp tuyến 1 ngay ở rank 1:

| Nhóm | Metric | Giá trị | Tính kiểu gì |
|---|---|---|---|
| retrieval | `evidence_recall` | 1.0 | 1 evidence được support / 1 evidence tổng |
| retrieval | `mrr` | 1.0 | 1 / hạng context đầu tiên trúng = 1/1 |
| retrieval | `hit@5` | 1.0 | có trúng trong top-5 không |
| answer | `hit_rate` | 1.0 | "100.000.000 đồng" có trong câu trả lời |
| answer | `hit_all` | 1.0 | trúng hết mọi marker |
| citation | `citation_article_accuracy` | 1.0 | trích dẫn Điều 63, gold Điều 63 |
| grounding | `faithfulness` | **None** | cần judge, mà mặc định là NullJudge |
| abstention | `correct_abstention` | **None** | `not_applicable` — câu này trả lời được |

### Về chuẩn hoá văn bản

`hit_rate` có một chi tiết hay: câu trả lời viết `**100.000.000 đồng**` với dấu `**`
markdown, và `normalization.py` bỏ markdown + bỏ dấu phân cách hàng nghìn trước khi so,
nên `100.000.000` ≡ `100 000 000`.

Nhưng nó **cố tình không** gộp những thứ khác nghĩa trong luật:

| Giữ nguyên khác biệt | Vì sao |
|---|---|
| `Điều 13` ≠ `Điều 31` | không đảo thứ tự chữ số |
| `30,5%` ≠ `305%` | chỉ bỏ dấu phân cách *bên trong nhóm 3 chữ số* |
| `330/2026/NĐ-CP` ≠ `331/2026/NĐ-CP` | số hiệu văn bản không bao giờ bị gộp |
| `không bị xử phạt` ≠ `bị xử phạt` | phủ định được giữ |
| `triệu` ≠ `tỷ` | đơn vị tiền được giữ |

So sánh: evaluator cũ trong repo (`kag/solver/eval.py:norm_text`) xoá `.` và `,` toàn
cục, nên `30,5%` biến thành `305%`. Bộ mới sửa đúng chỗ đó.

## 1.6 Gộp lại

Sau 150 câu × 3 hệ, `aggregate.py` làm ba việc:

- **micro** — trung bình phẳng trên mọi câu *có giá trị thật*. Câu nào `None` bị loại
  khỏi mẫu số và được đếm riêng vào `n_not_applicable` (đề không hỏi chuyện đó) hoặc
  `n_unavailable` (đề có hỏi nhưng không trả lời được).
- **macro** — trung bình *theo category*, để nhóm "mức phạt" có 60 câu không đè bẹp
  nhóm "thời hiệu" có 10 câu.
- **CI 95%** — bootstrap 1000 lần với seed cố định. Cùng input + cùng seed → đúng cùng
  một khoảng. Với n = 150 thì đây không phải trang trí: nó là thứ quyết định chênh lệch
  3% giữa hai hệ có ý nghĩa hay không.

Và nó **cố tình không có điểm tổng hợp**. Trộn recall với faithfulness rồi lấy trung
bình sẽ giấu mất đúng cái người đọc cần biết: hệ nào yếu ở khâu nào.

### Faithfulness và Hallucination không phải là bù của nhau

Mỗi claim trong câu trả lời rơi vào đúng một ô:

| Claim nằm ở đâu | Tính vào faithfulness | Tính vào hallucination |
|---|---|---|
| có trong context của chính hệ đó | ✅ | — |
| đúng theo gold nhưng context không có (**retrieval gap**) | — | — |
| sai hoặc trái với gold | — | ✅ |
| không quyết được | — | — |

Một hệ mà bộ sinh tốt nhưng bộ truy xuất đói tài liệu sẽ mất điểm faithfulness **mà
không bị buộc tội bịa đặt**. Gộp hai cái lại sẽ báo một lỗi truy xuất thành một lỗi
hallucination — cách nhanh nhất để một bài so sánh RAG nói sai sự thật.

---

# Phần 2 — Đánh giá

## 2.1 Những thứ làm đúng

1. **Đáp án trung lập kiến trúc.** Quyết định quan trọng nhất, và nó đúng. Có ba nguồn
   độc lập ủng hộ (xem 2.4).
2. **`None` không phải 0**, và câu thiếu output bị loại khỏi trung bình thay vì chấm 0.
3. **Tách faithfulness / retrieval gap / hallucination.** Đây là phần thiết kế tốt nhất.
4. **Lệch vị trí là hard negative.** Đúng về mặt pháp lý.
5. **Chuẩn hoá giữ nghĩa pháp lý**, sửa được một lỗi thật của bộ cũ.
6. **Bootstrap CI seed cố định**, `random.Random(seed)` cục bộ nên không phụ thuộc trạng
   thái random toàn cục.
7. **172 test chạy offline**, không gọi API nào.

## 2.2 Những thứ hỏng — hai lỗ hổng công bằng

### Lỗ hổng 1: metadata giàu hơn được điểm cao hơn

Metadata chunk thật của ba hệ trong repo này:

| Hệ | Có `document` | Có `article` | Có `clause` / `point` |
|---|---|---|---|
| KAG (`kag/builder/reader.py`) | ✅ | ✅ | ✅ |
| NativeRAG (`nativeRAG/rag_core/chunker.py`) | ✅ | ✅ (chuỗi heading) | ❌ |
| HybridRAG (`hybridRAG/ingestion/loader/load_markdown.py`) | ✅ | ❌ | ❌ |

HybridRAG chỉ có `source` / `file_name` / `file_path`. Giờ cho nó chạy qua ba tuyến với
câu q042:

```json
{ "rank": 1, "document_id": "13/2023/NĐ-CP", "article": null, "clause": null,
  "text": "...Phạt tiền từ 50.000.000 đồng đến 100.000.000 đồng..." }
```

- Tuyến 1: gold khai `article` và `clause`, context im lặng cả hai → chưa quyết được.
- Tuyến 2: gold có `text`, context có `text`, chuỗi nằm trọn → **TRUE**. ✅

May quá, vẫn đúng. **Nhưng chỉ vì gold evidence có trường `text`.** Mà trong schema hiện
tại `text` là **optional**.

Giả sử người gán nhãn câu q043 chỉ ghi `{document_id, article, clause}` mà không chép
nguyên văn:

- **KAG**: tuyến 1 khớp đủ 4 cấp → TRUE → `evidence_recall = 1.0`
- **HybridRAG**: tuyến 1 chưa quyết được → tuyến 2 không có gold text để so → tuyến 3
  NullJudge trả UNKNOWN → **UNDECIDED** → không vào tử số → `evidence_recall = 0.0`

**Hai hệ lấy về đúng cùng một điều luật. Một hệ 1.0, một hệ 0.0.** Khác biệt duy nhất là
KAG giữ số Khoản/Điểm trong metadata.

Tệ hơn: nó chỉ gãy trên đúng những câu mà người gán nhãn ghi thiếu, nên **bạn sẽ không
phát hiện ra bằng cách nhìn bảng kết quả**.

→ Đây là BLOCKER #1 và #2 ở Phần 4.

### Lỗ hổng 2: `context_precision` đo cả độ dài dòng

`context_precision` = (số context có support gold) / (**số context hệ thống trả về**).
Mẫu số do chính hệ thống chọn. Hệ trả top-3 và hệ trả top-20 không so được với nhau trên
con số này. Nó đang nằm trong danh sách PRIMARY.

→ Phải cố định `k` chung, hoặc hạ xuống diagnostic.

### Hai rủi ro nhỏ hơn

- **Citation**: KAG sinh `<reference id="chunk:...">` sẵn. Nếu HybridRAG / NativeRAG
  không được prompt yêu cầu trích dẫn Điều/Khoản y hệt, thì mọi metric citation đang đo
  *thiết kế prompt* chứ không đo kiến trúc.
- **Abstention**: `ABSTENTION_CUES` là danh sách từ khoá tiếng Việt cứng. Với NullJudge,
  bất kỳ câu trả lời có nội dung mà không trúng từ khoá nào đều bị chấm là "đã trả lời".
  Một câu rào đón diễn đạt khác đi sẽ bị phạt oan, và hệ nào có prompt dùng đúng cụm
  trong danh sách sẽ được lợi.

## 2.3 Những thứ thừa

**Thừa rõ ràng:**

- **24 tên metric** cho một bảng paper vốn chỉ chứa nổi 6–8 cột.
- **Năm lớp judge** (`Null` / `RuleBased` / `Scripted` / `Callable` / `Caching`) trong
  khi judge thật chưa tồn tại. `RuleBasedJudge` là lớp nguy hiểm: nó coi "phủ 0.8 token"
  là entailment trên văn xuôi pháp lý tiếng Việt, và **không bao giờ trả CONTRADICTED**
  — nghĩa là `hallucination_rate` bị lệch về 0 một cách có hệ thống. Hợp lý làm test
  double, không hợp lý làm nguồn số cho paper. Mà hiện nó đang nằm trong lựa chọn
  `--judge` của CLI.
- **`MatchingPolicy` có 7 knob**, trong đó `coarse_metadata_counts` và
  `verify_text_when_available` đều tắt và không cấu hình paper nào dùng.
- **Cấu hình chết** cho tới khi có dataset: `required: false`, citation precision theo
  `claim_index`, đường `answer_claims` do adapter cấp, `token_count` override, ma trận
  4 giá trị k × nhiều budget.

**KHÔNG phải thừa — đừng đụng vào:**

- Ngữ nghĩa `None` ba trạng thái + nhãn `not_applicable` / `unavailable`.
- `evidence_matching.py` — đó chính là hợp đồng công bằng, phức tạp ở đây là chính đáng.
- Bootstrap CI seed cố định.
- 172 test.

### Chi phí gán nhãn 150 câu

| Phương án | Ước lượng | Ghi chú |
|---|---|---|
| Schema đầy đủ (có `gold_claims`) | **50–60 giờ người** | ~20–25 phút/câu |
| Bỏ `gold_claims` | **25–30 giờ người** | ~10–12 phút/câu |

`gold_claims` là trường đắt nhất, và hiện nó **chỉ nuôi những metric đang `unavailable`**
(vì chưa có judge). Đây là lý do mạnh nhất để bỏ nhóm `claim_*`.

## 2.4 So với KAG gốc

Đọc trực tiếp `vendor/KAG/kag/common/benchmarks/` và `vendor/KAG/kag/open_benchmark/`:

**Answer**: chỉ có EM và F1 kiểu SQuAD (`normalize_answer` bỏ mạo từ, bỏ dấu câu,
lowercase; F1 là token-overlap). Cộng `LLM-Accuracy` = tỉ lệ câu mà judge trả về chuỗi
`"true"`. ROUGE-L tuỳ chọn. `answer_similarity` là **stub trả về 0.0** (phần RAGAS đã bị
comment hết).

**Retrieval**: chỉ có `recall_top3` / `recall_top5` / `recall_all`. Đơn vị ground truth:

| Dataset | Gold là gì | Khớp kiểu gì |
|---|---|---|
| HotpotQA, 2Wiki | **tiêu đề đoạn văn** trong `supporting_facts` | substring hai chiều |
| MuSiQue | chuỗi **title + nội dung đoạn** đã chuẩn hoá | substring hai chiều |

**Nghĩa là KAG gốc cũng không dùng chunk id của chính nó làm gold.** Nó dùng danh tính
nội dung. Đây là điểm ủng hộ mạnh cho thiết kế B1 và nên viết thẳng vào paper.

**Bài báo** (arXiv 2409.13731): Table 8 = `EM | F1`. Table 9 và 11 = `Recall@2 | Recall@5`.
Table 12 (E-Government) = `SampleNum | Precision | Recall`, n = 492.

**KAG gốc KHÔNG có**: context precision, faithfulness, hallucination rate, bất kỳ metric
citation nào, abstention, confidence interval, macro-average theo category. Tất cả những
thứ đó là phần B1 tự thêm.

### Hai điều về KAG gốc cần biết trước khi bắt chước

1. **Judge của nó là self-judging.** `getBenchMark` dùng `KAG_CONFIG.all_config["llm_judge"]`
   nếu có, không thì rơi về `get_default_chat_llm_config()`. Trong repo này **không có
   block `llm_judge` nào cả** → mô hình được chấm chính là mô hình đi chấm.
2. **Prompt judge của nó là tiếng Trung, chủ đề y khoa trắc nghiệm.**
   `JudgerPrompt.py` đặt `template_en = template_zh`, và template đó là few-shot với hai
   ví dụ y khoa. Không có bản tiếng Anh, càng không có tiếng Việt pháp lý.

→ Không được port thiết kế judge của KAG làm chuẩn. "Chúng tôi theo protocol judging của
KAG" không phải là lập luận dùng được cho bài này.

**Một điểm vênh nữa**: bài báo ghi Recall@2/@5, nhưng code chỉ sinh ra
`recall_top3/5/all` — số Recall@2 đã công bố **không tái lập được** từ code hiện tại.
Vì vậy đừng viết "chúng tôi theo protocol truy xuất của KAG"; hãy nêu rõ `k` của mình.
`k = 5` là giá trị duy nhất xuất hiện ở **cả** bài báo lẫn code.

---

# Phần 3 — Quyết định

## 3.1 Ba phương án

| | Nội dung | Kết luận |
|---|---|---|
| **A** | Giữ nguyên evaluator hiện tại | ❌ Loại |
| **B** | Giữ framework, chỉ chốt một "paper profile" ít metric | ✅ **CHỌN** |
| **C** | Đơn giản hoá luôn code/schema | ❌ Loại |

**Vì sao loại A**: không phải vì code tệ, mà vì (i) ba trong chín metric PRIMARY hiện tại
(`claim_f1`, `faithfulness`, `hallucination_rate`) trả `None` ở cấu hình mặc định vì chưa
có judge, (ii) `context_precision` và bất đối xứng metadata là lỗi công bằng đang sống,
(iii) `hit_all` đang là primary còn `hit_rate` là diagnostic — ngược với cách EM/F1 được
báo cáo ở upstream. Một bảng mà một phần ba số dòng ghi "unavailable" tệ hơn một bảng sáu
dòng đầy đủ.

**Vì sao loại C**: phần đắt và đúng nhất của B1 (ngữ nghĩa `None`, chuẩn hoá giữ nghĩa
pháp lý, ba tuyến matching, chặn khoá hệ thống, 172 test) sẽ phải viết lại và kiểm chứng
lại từ đầu. Đồng hồ đang chạy cho B2 (dataset), không phải cho B1. Xoá code không mua
được gì cho paper, và mỗi lần xoá là một lần rủi ro phá vỡ một bất biến đang được test
bảo vệ.

**Vì sao chọn B**: sửa các lỗi công bằng, đổi hai hằng số `PRIMARY_METRICS` /
`DIAGNOSTIC_METRICS`, thêm `evidence_recall@k`, bắt buộc `text`. Những metric còn lại vẫn
được tính, chỉ là không báo cáo. Khoảng một ngày công, không phải viết lại.

## 3.2 Metric giữ gì bỏ gì

### PRIMARY — bảng chính của paper

| # | Metric | Hướng | Vì sao |
|---|---|---|---|
| 1 | `evidence_recall` | ↑ | Metric lõi, đối ứng Recall@k của KAG |
| 2 | `evidence_recall@5` | ↑ | **Cần bổ sung.** k=5 là giá trị duy nhất có ở cả bài báo lẫn code KAG |
| 3 | `evidence_recall@Ntok` | ↑ | Kiểm soát công bằng duy nhất chống nhồi 8k token context |
| 4 | `hit_rate` | ↑ | Đối ứng F1 — điểm từng phần |
| 5 | `hit_all` | ↑ | Đối ứng EM — all-or-nothing |
| 6 | `citation_article_accuracy` | ↑ | Deterministic, và là câu hỏi pháp lý có ý nghĩa nhất |
| 7 | `citation_recall` | ↑ | Deterministic |
| 8 | `correct_abstention` | ↑ | Cần nhãn người trên tập unanswerable |
| 9 | `latency_ms` | ↓ | Cột chi phí |

**Có điều kiện** — chỉ vào bảng chính nếu giao được LLM-judge adapter + calibration:
`faithfulness` ↑ và `hallucination_rate` ↓. Không có calibration thì xuống phụ lục.

### DIAGNOSTIC — chỉ dùng phân tích lỗi

`mrr`, `hit@5`, `context_precision` (chỉ ở k cố định chung), `citation_precision`,
`citation_document_accuracy`, `citation_clause_accuracy` + `citation_point_accuracy`
(**không bao giờ so sánh giữa ba hệ**), `retrieval_gap_rate` (nếu có judge), `error_rate`,
và `n_undecided` / `n_unavailable` cho mọi metric.

### REMOVE — bỏ hẳn khỏi report

| Metric | Vì sao bỏ |
|---|---|
| `claim_precision` / `claim_recall` / `claim_f1` | Tốn gấp ba (cần `gold_claims` + judge + trích xuất claim), tín hiệu trùng `hit_rate`/`hit_all` và `faithfulness` |
| `unsupported_claim_rate` | Cùng tử số với `hallucination_rate`, chỉ khác mẫu số |
| `false_answer_rate` | Bù chính xác của `correct_abstention` — chính docstring nói vậy |
| `evidence_recall_required` | Bằng hệt `evidence_recall` nếu khai tất cả evidence là required |
| `hit@1` / `hit@3` / `hit@10` | Giữ đúng một k |
| `citation_clause_accuracy` / `citation_point_accuracy` (trong bảng) | Thiên vị KAG có hệ thống |

---

# Phần 4 — Phải làm gì trước B2

## 🔴 BLOCKER — chặn việc bắt đầu gán nhãn

| # | Việc | Vì sao |
|---|---|---|
| 1 | **Bắt buộc `gold_evidence[].text`** trong cả `benchmark_schema.json` lẫn `models.EvidenceRef` | Không có nó, matching structural cho KAG điểm miễn phí mà HybridRAG/NativeRAG không kiếm được (xem 2.2) |
| 2 | **Cố định độ sâu chấm điểm ở mức Điều**, và chỉ hard-negative ở `document_id` + `article`. Lệch `clause`/`point` **không được** tạo ra `supported = False` mà phải rơi xuống tuyến text; vẫn ghi lại làm metadata phân tích lỗi. Loại `citation_clause_accuracy` / `citation_point_accuracy` khỏi mọi bảng | Cùng lý do với #1, nhưng bắt buộc `text` ở #1 **không** đủ để sửa: `structural_decision` đang `return False` ngay khi lệch bất kỳ cấp nào, short-circuit trước tuyến text. Hệ quả là hệ có metadata `clause` nhưng lệch (KAG, khi một chunk ôm nhiều khoản) bị đánh trượt cứng, còn hệ không khai `clause` (HybridRAG) lại được tuyến text cứu — tức **có metadata sâu bị phạt nặng hơn không có metadata**, đúng chiều ngược lại của bất đối xứng ban đầu |
| 3 | **Thêm `evidence_recall@k`** và chốt một `k` chung cho cả ba hệ | B1 hiện chỉ có recall toàn danh sách và recall theo budget — thiếu đúng dạng metric mà upstream và literature báo cáo |
| 4 | **Hoặc** giao LLM-judge adapter thật + calibration (≥50 cặp có nhãn người, báo cáo agreement và flip-rate) **hoặc** bỏ `faithfulness` / `hallucination_rate` / toàn bộ `claim_*` khỏi bảng chính | Judge phải là mô hình **khác** ba hệ đang thi, prompt tiếng Việt pháp lý viết mới. Không port judge của KAG (xem 2.4) |
| 5 | **Gỡ `rule_based` khỏi `JUDGE_FACTORIES`** trong CLI | Để nó không vô tình sinh ra một con số công bố được. Giữ lớp lại cho test |
| 6 | **Thống nhất hợp đồng trích dẫn cho cả ba hệ bằng một parser dùng chung** chạy trên trường `answer` (`benchmark/adapters/citation_parser.py`), cộng guard mềm phát hiện `citations[]` sao chép `retrieved_contexts` | Nếu không, metric citation đo thiết kế prompt chứ không đo kiến trúc. Nghiêm trọng nhất: `nativeRAG/rag_core/engine.py::generate` dựng `citations` từ chính `docs` đã truy xuất, nên adapter copy thẳng sẽ cho `citation_recall` = recall truy xuất, miễn phí. Sửa prompt của ba hệ không phải là cơ chế đúng — mẫu số chung duy nhất là trích dẫn văn xuôi trong `answer`, nên parse ở đó và bỏ qua thẻ `<reference>` của KAG |

> Mục **1, 2, 3, 6** thay đổi *thứ mà người gán nhãn phải viết ra*. Gán nhãn 150 câu xong
> rồi mới phát hiện `text` là optional hay gold ở mức Khoản là không công bằng — nghĩa là
> **gán nhãn lại từ đầu**.

## 🟡 SHOULD FIX

7. Viết lại `PRIMARY_METRICS` / `DIAGNOSTIC_METRICS` theo mục 3.2.
8. Định nghĩa lại hoặc hạ cấp `context_precision`; chỉ báo ở `k` cố định chung.
9. **Gán nhãn tay abstention** trên tập unanswerable thay vì tin `ABSTENTION_CUES`.
10. **Bỏ `gold_claims` khỏi kế hoạch gán nhãn B2** (giữ field trong schema). Tiết kiệm
    ~25 giờ người.
11. Thêm artefact đóng băng vào header report: hash snapshot corpus, cấu hình
    retriever/k/budget, judge fingerprint, git SHA của evaluator.
12. **Double-annotation ~20% số câu**, báo cáo agreement trên (tập evidence, answerable).

## 🟢 OPTIONAL

13. Tỉa `MatchingPolicy` còn `text_overlap_threshold` và `use_judge`.
14. Bỏ `required: false` khỏi dataset contract — khai tất cả evidence là required.
15. Giữ `latency_ms` như cột chi phí.

---

## Exit criteria — điều kiện chuyển sang `B1 READY FOR B2`

Năm điều kiện, kiểm được bằng test chứ không bằng đọc code:

1. **`text` bắt buộc** ở cả `benchmark_schema.json` (`$defs.evidenceRef.required`) lẫn
   `EvidenceRef`, có test chứng minh evidence thiếu `text` bị từ chối.
2. **Độ sâu hard-negative chốt ở `("document", "article")`** và có mặt trong
   `report["config"]["policy"]["hard_negative_levels"]`; lệch `clause`/`point` không bao
   giờ tạo ra `supported is False`; lệch `article` vẫn là hard negative kể cả khi judge
   luôn trả SUPPORTED. Có test chứng minh ba dạng metadata clause (đúng / lệch / không
   khai) cho **cùng một** `evidence_recall`. `citation_clause_accuracy` và
   `citation_point_accuracy` không còn trong bảng in, nhưng vẫn có trong `per_question`.
3. **`evidence_recall@5` được tính**, có mặt trong `report["metrics"]` với micro/macro/CI
   đầy đủ, và `k` nằm trong cấu hình đóng băng của report.
4. **`benchmark/adapters/citation_parser.py` tồn tại**, có test chứng minh ba phong cách
   câu trả lời (KAG có thẻ `<reference>`, HybridRAG có dòng `"Căn cứ:"`, NativeRAG dạng
   `"Theo Điều ..."`) cho ra cùng một tập citation; `README.md` ghi contract cấm dựng
   `citations[]` từ `retrieved_contexts`; guard mềm ở loader hoạt động.
5. **`PRIMARY_METRICS` đúng 9 tên**, tất cả đều có `micro is not None` khi chạy với
   `NullJudge`; `"rule_based"` không còn trong `JUDGE_FACTORIES`; toàn bộ test suite xanh.

Điều kiện thứ sáu chỉ cần trước khi nộp bài, **không chặn B2**: nếu muốn đưa
`faithfulness` / `hallucination_rate` / `claim_*` lên bảng chính thì phải có adapter judge
độc lập với cả ba hệ, prompt pháp lý tiếng Việt viết mới, calibration tối thiểu 50 cặp có
nhãn người và báo cáo agreement. Không có thì giữ nguyên nhánh hiện tại và những metric đó
nằm ngoài cả hai bảng.

## Kết luận

**B1 NOT READY FOR B2** tại thời điểm review.

Framework thì sẵn sàng; **schema thì chưa**. Sáu blocker ở trên, trong đó bốn cái thay đổi
hợp đồng dữ liệu, phải chốt xong trước khi ai đó gõ câu hỏi số 1.

Đây là khoảng **một ngày công** sửa `benchmark_schema.json`, `models.py`,
`evidence_matching.py`, `retrieval_metrics.py` và hai hằng số trong `evaluate.py` — không
phải viết lại. Sau khi sáu blocker đóng lại, chuyển thẳng sang B2 với schema đã đóng băng.

### Trạng thái sau khi sửa

Cả sáu blocker đã được đóng và năm exit criteria ở trên đều có test bảo vệ:

| # | Đóng ở đâu |
|---|---|
| 1 | `benchmark_schema.json` (`required: ["document_id", "text"]`), `models.EvidenceRef.from_dict` |
| 2 | `MatchingPolicy.hard_negative_levels`, `evidence_matching.structural_decision`, `SupportDecision.soft_mismatch`; `tests/test_evidence_matching.py` |
| 3 | `retrieval_metrics.evaluate_retrieval` (`topk_evidence_recall`), `evaluate.QuestionResult.metric_values` |
| 4 | `evaluate.PRIMARY_METRICS` (9 tên, tất cả deterministic), điều kiện judge ghi ở `README.md` §9 |
| 5 | `evaluate.JUDGE_FACTORIES` chỉ còn `"null"` |
| 6 | `benchmark/adapters/citation_parser.py`, `models.citations_mirror_contexts`, `README.md` §5 |

Chi tiết thiết kế nằm ở `README.md`; file này giữ nguyên là biên bản review.
