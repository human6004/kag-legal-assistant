# Data — KAG Chatbot Tư vấn Luật (An ninh mạng & AI)

Thư mục này chứa dữ liệu thô phục vụ xây dựng knowledge base cho chatbot tư vấn luật
theo kiến trúc KAG (Knowledge-Augmented Generation / Graph). Khi cào xong, copy nguyên
cụm `data/` này vào project chính.

## Cấu trúc

```
kag-legal-data/
├── README.md              <- file này
├── SOURCES.md              <- danh sách nguồn đã thẩm định độ uy tín (đọc trước khi cào)
├── data/
│   ├── raw/                <- dữ liệu thô, giữ NGUYÊN VĂN, chưa chỉnh sửa/tóm tắt
│   │   ├── vn_an_ninh_mang/   <- Luật An ninh mạng VN + văn bản hướng dẫn
│   │   ├── quoc_te_an_ninh_mang/ <- Luật/công ước an ninh mạng quốc tế (UN, EU NIS2, Budapest, NIST CSF...)
│   │   ├── vn_ai/             <- Luật/Nghị định/Chiến lược AI Việt Nam
│   │   └── quoc_te_ai/        <- Luật/khung AI quốc tế (EU, Mỹ, OECD, UNESCO...)
│   ├── processed/          <- (dùng sau) bản đã làm sạch, chunk, chuẩn hoá cho pipeline KAG
│   └── metadata/           <- file index mô tả từng văn bản (xem template bên dưới)
├── prompts/
│   └── scrape_prompt_vi.md <- bản prompt đã viết lại rõ ràng, đưa cho AI đi cào là hiểu ngay
└── scripts/                 <- script cào, sinh metadata, dựng processed/exports
```

## Quy tắc đặt tên file thô (trong `data/raw/<nhóm>/`)

`<so-hieu-van-ban>_<ten-ngan-gon>.<ext>`
Ví dụ: `24-2018-QH14_luat-an-ninh-mang.pdf`, `13-2023-ND-CP_bao-ve-du-lieu-ca-nhan.pdf`

- Giữ file gốc (PDF/HTML) nguyên văn, KHÔNG sửa nội dung.
- Mỗi file thô nên có 1 file metadata `.json` cùng tên trong `data/metadata/` (xem template).
- Vietnamese: giữ dấu tiếng Việt trong nội dung, tên file có thể bỏ dấu cho an toàn hệ thống file.

## Vì sao cần metadata riêng (quan trọng với luật)

Văn bản pháp luật có vòng đời: còn hiệu lực / hết hiệu lực / bị sửa đổi, bổ sung, thay thế.
Một chatbot tư vấn luật mà trộn văn bản hết hiệu lực vào knowledge base ngang hàng với văn bản
còn hiệu lực là rủi ro lớn nhất. Vì vậy bắt buộc track các trường sau cho từng văn bản (xem
`data/metadata/_template.json`):

- `doc_number` (số hiệu), `doc_type` (Luật/Nghị định/Thông tư/Quyết định/Regulation/...)
- `issuing_body` (cơ quan ban hành), `date_issued`, `date_effective`
- `status` (còn hiệu lực / hết hiệu lực / một phần hết hiệu lực) — **phải tự tra cập nhật**, đừng suy đoán
- `amends` / `amended_by` / `superseded_by` (quan hệ với văn bản khác — rất quan trọng để dựng graph cho KAG)
- `source_url`, `retrieved_date`
- `jurisdiction` (VN / EU / US / quốc tế), `language`

## Quy tắc trả lời khi văn bản cũ và mới cùng tồn tại

Có văn bản mới thì trả lời theo văn bản mới. Văn bản cũ chỉ dùng bổ sung, cho đúng phần
mà văn bản mới còn dẫn chiếu tới, ví dụ điều khoản chuyển tiếp về hồ sơ đã nộp trước ngày
văn bản mới có hiệu lực. Khi dùng văn bản cũ thì phải nêu rõ nguồn và nêu rõ nó đã hết hiệu lực.

Không suy đoán tình trạng hiệu lực. Mốc hết hiệu lực phải neo vào một văn bản có toàn văn
trong `data/raw`, không neo vào nguyên tắc chung nhớ được. Nếu nguồn nhà nước mâu thuẫn nhau
thì ghi hết vào `status_conflict` và ghi căn cứ đã chọn vào `status_basis`.

## Khi nào thì xong để đưa vào project

Khi mỗi văn bản trong 4 nhóm (`vn_an_ninh_mang`, `quoc_te_an_ninh_mang`, `vn_ai`, `quoc_te_ai`) đều có:
1. File thô trong `data/raw/...`
2. File metadata tương ứng trong `data/metadata/...`
3. Trạng thái hiệu lực đã được xác minh (không để trống `status`)

Sau đó copy cả `data/` vào project là dùng được ngay cho bước chunk/embed/build graph.

---

# Cập nhật sau đợt rà soát ngày 2026-09-09

## Trường metadata bổ sung so với bản README ban đầu

Bản `_template.json` đã mở rộng để trả lời đúng câu hỏi "văn bản này có đang áp dụng
không, căn cứ vào đâu":

| Trường | Ý nghĩa |
|---|---|
| `in_force` | `true` / `false` / `null`. Kết luận máy đọc được, thay cho việc phải parse chuỗi `status`. `null` = chưa xác minh được. |
| `in_force_as_of` | Ngày đối chiếu hiệu lực. Mọi kết luận `in_force` chỉ đúng tại ngày này. |
| `status_basis` | Điều khoản cụ thể làm căn cứ kết luận hiệu lực. Không được để trống với văn bản pháp luật. |
| `status_source` | Nguồn đã tra để kết luận. |
| `status_conflict` | Ghi lại khi các nguồn nhà nước mâu thuẫn nhau. Đây là trường quan trọng nhất khi soát tay. |
| `date_applicable` | Ngày bắt đầu áp dụng, tách khỏi ngày có hiệu lực (EU hay tách hai mốc này). |
| `supersedes` | Chiều ngược của `superseded_by`. |
| `implements` / `implemented_by` | Quan hệ luật ↔ nghị định/thông tư hướng dẫn. |
| `source_name` / `source_tier` | Tên nguồn và cấp độ tin cậy của nguồn. |
| `raw_files` | Danh sách file thô (một văn bản có thể có cả bản HTML để chunk và bản PDF ký số để đối chiếu). `raw_file` giữ lại là file chính. |
| `text_extractable` | `false` nghĩa là file là ảnh scan, cần OCR trước khi chunk. |

`data/metadata/_index.json` là bảng tổng hợp toàn bộ, sinh tự động, dùng để lọc nhanh
trong pipeline.

## Cách xử lý văn bản "luật mới bao hàm luật cũ nhưng luật cũ chưa được ghi hết hiệu lực"

Đây là tình huống có thật trong bộ dữ liệu này: Luật An ninh mạng 116/2025/QH15 thay thế
cả Luật 24/2018/QH14 lẫn Luật 86/2015/QH13 từ 01/7/2026, nhưng vbpl.vn tại ngày cào vẫn
ghi Luật 24/2018/QH14 là "Còn hiệu lực". Quy tắc đã áp dụng cho toàn bộ dữ liệu:

1. **Điều khoản trong chính văn bản luật thắng trường trạng thái của cơ sở dữ liệu.**
   Ghi kết luận vào `status` / `in_force`, ghi điều khoản vào `status_basis`.
2. **Không xóa mâu thuẫn, mà ghi lại** vào `status_conflict` để người soát tay biết chỗ
   nào cần theo dõi khi CSDL cập nhật.
3. **Không suy diễn.** Khi không có điều khoản nào tuyên bố bãi bỏ và cũng không có nguồn
   nhà nước xác nhận, để `status = "cần xem lại"` và `in_force = null` thay vì đoán.
   Hiện chỉ còn Nghị định 53/2022/NĐ-CP rơi vào nhóm này.
4. **Vẫn giữ văn bản hết hiệu lực trong kho**, không xóa, vì chatbot cần trả lời được câu
   hỏi lịch sử; nhưng bắt buộc lọc theo `in_force` trước khi dùng làm căn cứ tư vấn.

## Quy tắc chọn định dạng file thô

Ưu tiên định dạng có text Unicode sạch, vì bản PDF ký số của Việt Nam thường là ảnh scan:

1. HTML toàn văn từ API vbpl.vn — tốt nhất cho luật, nghị định đã lên CSDL quốc gia.
2. DOCX của Công báo Chính phủ — dùng cho văn bản mới chưa lên vbpl.vn.
3. PDF ký số (`datafiles.chinhphu.vn`, `congbaocdn.chinhphu.vn`) — chỉ dùng khi không có
   hai loại trên; đánh dấu `text_extractable: false` nếu là ảnh scan.

## Script

| Script | Việc |
|---|---|
| `scripts/fetch_vbpl.py` | Tải toàn văn + metadata từ API CSDL quốc gia về pháp luật. |
| `scripts/fetch_congbao.py` | Tải PDF ký số từ Công báo / hệ thống văn bản Chính phủ. **Chưa viết lại.** |
| `scripts/fetch_congbao_docx.py` | Tải bản DOCX của Công báo (text sạch, dùng để chunk). |
| `scripts/docx_text.py` | Rút text từ DOCX, tra nhanh điều khoản hiệu lực. **Chưa viết lại.** |
| `scripts/gen_metadata.py` | Sinh lại toàn bộ metadata + `_index.json`. |
| `scripts/check_dataset.py` | Kiểm tra tính đầy đủ, đối xứng quan hệ, và in danh sách cần soát tay. |
| `scripts/build_processed.py` | Sinh `data/processed/**/*.md` và `docs/exports/*.docx` từ raw (docx/html/pdf), không sửa raw/metadata. |
| `scripts/test_build_processed.py` | Self-check của `build_processed.py` (quy tắc tiêu đề, chốt chặn mất chữ, danh sách bỏ qua). |

`build_processed.py` chạy tăng dần: chỉ dựng lại `.md` khi thiếu hoặc raw mới hơn,
dùng `--force` để dựng lại toàn bộ. Văn bản có `status: "không áp dụng"` (trang web
điều hướng, không phải văn bản pháp luật) và văn bản có `text_extractable: false`
đều bị bỏ qua, và mọi `.md`/`.docx` không còn nằm trong danh sách kỳ vọng sẽ bị xoá.

Bốn PDF ký số dạng ảnh scan (`127/QĐ-TTg`, `367/QĐ-TTg`, `1671/QĐ-TTg`,
`341/2026/NĐ-CP`) không có lớp text: mọi trình rút chữ chỉ đọc được vài trăm ký tự
của chữ ký số. Toàn văn trong `data/processed` của bốn văn bản này đến từ bước OCR
trước đó. `build_processed.py` có chốt chặn `SHRINK_FLOOR`: nếu bản rút mới ngắn hơn
hẳn bản `.md` đang có thì giữ nguyên file cũ và báo cảnh báo, không ghi đè.
