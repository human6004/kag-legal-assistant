# Data — KAG Chatbot Tư vấn Luật (An ninh mạng & AI)

Dữ liệu dùng chung của project KAG và HybridRAG. `processed/` là đầu vào
Markdown đã chuẩn bị sẵn; repo hiện không có pipeline tái tạo từ `raw/`.

## Cấu trúc hiện tại

```
data/
├── raw/          bản gốc PDF/DOCX/HTML, giữ nguyên để đối chiếu
├── processed/    Markdown trong vn_ai/ và vn_an_ninh_mang/, chưa phải checkpoint chunk
├── metadata/     JSON từng văn bản, _template.json và _index.json
├── graph/        nodes.json, edges.json cho external graph
├── trial/        bốn Markdown dùng thử ingestion
├── SOURCES.md    nguồn dữ liệu
└── README.md
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
- `jurisdiction` (chỉ nhận `VN`, kho đã bỏ văn bản nước ngoài), `language`

## Quy tắc trả lời khi văn bản cũ và mới cùng tồn tại

Có văn bản mới thì trả lời theo văn bản mới. Văn bản cũ chỉ dùng bổ sung, cho đúng phần
mà văn bản mới còn dẫn chiếu tới, ví dụ điều khoản chuyển tiếp về hồ sơ đã nộp trước ngày
văn bản mới có hiệu lực. Khi dùng văn bản cũ thì phải nêu rõ nguồn và nêu rõ nó đã hết hiệu lực.

Không suy đoán tình trạng hiệu lực. Mốc hết hiệu lực phải neo vào một văn bản có toàn văn
trong `data/raw`, không neo vào nguyên tắc chung nhớ được. Nếu nguồn nhà nước mâu thuẫn nhau
thì ghi hết vào `status_conflict` và ghi căn cứ đã chọn vào `status_basis`.

## Khi nào thì xong để đưa vào project

Khi mỗi văn bản trong 2 nhóm (`vn_an_ninh_mang`, `vn_ai`) đều có:
1. File thô trong `data/raw/...`
2. File metadata tương ứng trong `data/metadata/...`
3. Trạng thái hiệu lực đã được xác minh (không để trống `status`)

Cần Markdown đã chuẩn bị trong `data/processed/` và JSON graph từ metadata trước
khi ingestion. Chỉ có raw/metadata chưa đủ; xem luồng chạy trong README gốc.

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
| `date_applicable` | Ngày bắt đầu áp dụng, tách khỏi ngày có hiệu lực. Văn bản VN thường trùng hai mốc, để trống là bình thường. |
| `supersedes` | Chiều ngược của `superseded_by`. |
| `implements` / `implemented_by` | Quan hệ luật ↔ nghị định/thông tư hướng dẫn. |
| `source_name` / `source_tier` | Tên nguồn và cấp độ tin cậy của nguồn. |
| `raw_files` | Danh sách file thô (một văn bản có thể có cả bản HTML để chunk và bản PDF ký số để đối chiếu). `raw_file` giữ lại là file chính. |
| `text_extractable` | `false` nghĩa là file là ảnh scan, cần OCR trước khi chunk. |

`data/metadata/_index.json` là bảng tổng hợp được lưu sẵn. Công cụ sinh chưa xác định;
`metadata_to_graph.py` bỏ qua file có tên bắt đầu bằng `_`, không dùng bảng này để lọc.

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

## Công cụ hiện có và lịch sử chuẩn hóa

Công cụ đang có: `kag/builder/metadata_to_graph.py` đọc JSON metadata, sinh
`data/graph/nodes.json` và `edges.json`; `injection.py` nạp graph đó lên server.
Đây không phải công cụ chuyển raw thành Markdown.

Các tên từng ghi trong tài liệu nhưng **không có trong repo hiện tại**:
`scripts/fetch_vbpl.py`, `fetch_congbao.py`, `fetch_congbao_docx.py`,
`docx_text.py`, `gen_metadata.py`, `check_dataset.py`,
`build_processed.py`, `test_build_processed.py`. Không có lệnh chạy hợp lệ
cho các script này; lịch sử Git khả dụng (`git log --all -- scripts`) cũng
không chứa chúng.

`kag/builder/clean_corpus.py` từng có từ `0ec9c40`, bị xóa ở `df241d3`.
Bản cuối đọc Markdown qua `fix_h1.all_md`, sửa heading/phụ lục/ký tự vô hình;
`--write` ghi lại corpus. Nó chỉ hậu xử lý Markdown, không chuyển raw/OCR và
phụ thuộc `fix_h1.py` cũng đã bị xóa. Chưa chứng minh phù hợp corpus mới,
nên không khôi phục hay chạy lại.

Markdown đã được đưa vào Git từ `0e5599e`, tiếp tục sửa ở nhiều commit; lần
cập nhật gần nhất trước bước A là `2d9ea1c` (11 file). Commit đó không cung cấp
công cụ tái sinh. Tài liệu cũ ghi bốn PDF scan (127/QĐ-TTg, 367/QĐ-TTg,
1671/QĐ-TTg, 341/2026/NĐ-CP) có Markdown từ OCR trước đó, nhưng chưa xác minh
được công cụ, phiên bản hay quy trình OCR. Không khẳng định tái tạo được toàn
bộ `processed` từ raw bằng code hiện có.

Bước A chỉ làm rõ nguồn vào; không chuẩn hóa lại hoặc sửa dữ liệu.
