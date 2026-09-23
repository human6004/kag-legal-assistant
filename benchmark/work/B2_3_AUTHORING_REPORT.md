# B2.3 AUTHORING REPORT

40 câu mới, `origin = b2_3_new`, id N001–N040, trong `benchmark/work/new_questions_b2_3.json`. Không gộp vào `candidate_questions.json`. Không tạo `benchmark_v1.json`. Không đối chiếu nguồn chính thức. Không chạy KAG, HybridRAG, NativeRAG.

`verification_status = CORPUS_VERIFIED` với câu trả lời được nghĩa là đoạn gold nằm nguyên văn trong `data/processed`, đúng điều, khoản, điểm. Với 15 câu unanswerable, cùng giá trị này nghĩa là đã tìm trên cả 23 văn bản và corpus không đủ để trả lời. Không có OFFICIAL VERIFIED.

## Số lượng

| Nhóm | Số |
|---|---:|
| sanction_numeric | 12 |
| effectiveness_metadata | 5 |
| inter_document | 8 |
| unanswerable | 15 |
| Tổng | 40 |
| answerable true | 25 |
| answerable false | 15 |

Không viết thêm definition, obligation, multi_hop.

## Coverage của 25 câu trả lời được

14 văn bản. 127/QĐ-TTg không có câu mới: quyết định này đã bị 1671 thay thế, không có fact mới vừa đúng vừa không trùng pool.

| Văn bản | Điều |
|---|---|
| 330/2026/NĐ-CP | 14, 48, 56, 60 |
| 341/2026/NĐ-CP | 1, 9, 17 |
| 331/2026/NĐ-CP | 1, 23 |
| 333/2026/NĐ-CP | 24 |
| 142/2026/NĐ-CP | 21, 26 |
| 86/2015/QH13 | 32, 53 |
| 13/2023/NĐ-CP | 43 |
| 53/2022/NĐ-CP | 1, 5, 29 |
| 356/2025/NĐ-CP | 5, 42 |
| 329/2026/NĐ-CP | 20 |
| 116/2025/QH15 | 45 |
| 71/2025/QH15 | 49 |
| 91/2025/QH15 | 39 |
| 35/2018/QH14 | 27 |

25 cặp văn bản–điều, không cặp nào trùng nhau. 24/2018/QH14 và 328/2026/NĐ-CP không có câu mới. Đúng hơn phủ.

## Kiểm tra trùng

`duplicate_with_legacy = 0`. `duplicate_with_new = 0`.

Đối chiếu 25 câu với 148 câu pool: không trùng vị trí `văn bản|điều|khoản|điểm`, không trùng marker trên cùng một điều. Câu mới với câu mới cũng không chung vị trí đó.

Các cặp gần, đã tách bằng kết luận khác:

- N005, giấy phép xuất nhập khẩu mật mã 03 năm, khác giấy phép kinh doanh 10 năm.
- N010, miễn 02 năm đầu theo Nghị định 13, khác mức 05 năm của Luật 91. Câu hỏi gọi đúng số 13. Không kết luận nghị định này hiện còn hiệu lực.
- N012, 02 ngày làm việc / 20 ngày / 30 ngày của Nghị định 356, khác mốc 72 giờ của Nghị định 13.
- N014, Luật 86 có hiệu lực 01/7/2016, khác ngày Luật 116 thay luật này.
- N017, giấy phép cũ còn đến hết hạn ghi trên giấy, khác hạn 12 tháng của hệ thống đã phân loại.
- N018 và N019, hai danh sách "quy định chi tiết" khác nhau. Marker giữ phần riêng: điểm i khoản 1 Điều 5 và khoản 5 Điều 36 cho Nghị định 53; khoản 2 Điều 8 và khoản 5 Điều 9 cho Nghị định 331.
- N021, sửa khoản 2 Điều 16 Nghị định 165, khác khoản hiệu lực và khoản hết hiệu lực của Nghị định 13 trong cùng Điều 42.
- N024, Nghị định 341 còn điểm a khoản 1 và điểm c khoản 2, phạm vi mật mã dân sự, không chỉ hai khoản mà nghị định khác đã dẫn.

Đã bỏ, không đưa vào 40 câu: hạn 12 tháng đặt chi nhánh của Nghị định 333 vì cùng kết luận với Nghị định 53; bậc nhân sự 05 người vì cùng bảng với bậc 12 người đã có trong pool; trần tin nhắn quảng cáo vì Nghị định 330 đã trả lời được.

## Cách audit câu unanswerable

Mỗi câu được grep trên toàn bộ `data/processed` (23 file), bằng đúng cụm, cụm gần nghĩa, và dẫn chiếu chéo. Nếu corpus trả lời được thì bỏ câu. Một câu đã bị bỏ: số tin nhắn, thư, cuộc gọi quảng cáo tối đa trong 24 giờ. Nghị định 330 đã ghi quá 03 tin nhắn, quá 03 thư, hoặc quá 01 cuộc gọi trong 24 giờ.

`CORPUS_VERIFIED` ở 15 câu này nghĩa là đã kiểm tra corpus và corpus không đủ. Không bịa evidence để chứng minh sự vắng mặt. `gold_markers` và `gold_evidence` đều rỗng. Lý do nằm trong `notes`, mở đầu bằng `CORPUS UNANSWERABLE CHECK`.

| Id | Vì sao corpus không đủ |
|---|---|
| N026 | Luật 134 giao Thủ tướng ban hành danh mục hệ thống rủi ro cao. Nghị định 142 chỉ có tiêu chí và quy trình đề xuất, không có tên hệ thống, cũng không chỉ hệ thống nào phải chứng nhận trước. |
| N027 | Điều 17 Luật 134 chỉ liệt kê lĩnh vực ưu tiên. Nghị định 142 và Quyết định 367 chỉ giao soạn danh mục bộ dữ liệu. |
| N028 | Điều 16 Luật 134 buộc ứng dụng quan trọng theo danh mục của Thủ tướng phải chạy trên hạ tầng quốc gia. Danh mục đó không có trong corpus. |
| N029 | Điều 22 Luật 134 giao Chính phủ quy định tổ chức, quản lý, giám sát quỹ. Quyết định 367 chỉ giao soạn nghị định. Nghị định 142 chỉ dùng quỹ làm nguồn tiền phiếu hỗ trợ. |
| N030 | Khoản 5 Điều 29 Luật 134 giao Chính phủ khung phạt cho vi phạm do hệ thống trí tuệ nhân tạo gây ra. Nghị định 330 Điều 67 phạt hành vi dữ liệu cá nhân khi dùng trí tuệ nhân tạo, không phải khung đó. Không có nghị định xử phạt thi hành Luật 134. |
| N031 | Điều 19 Luật 71 nói tiêu chí do Chính phủ quy định. Thẻ tạm trú 05 năm chỉ dành cho người đã thuộc diện. Nghị định 329 là tiêu chí lực lượng an ninh mạng. |
| N032 | Điều 48 Luật 71 giao Chính phủ điều kiện kinh doanh dịch vụ tài sản mã hóa. Luật 116 chỉ cấm chiếm đoạt tài sản mã hóa của người khác. |
| N033 | Điều 23 Luật 71 nêu tiêu chí quy mô diện tích nhưng không có số, và giao Chính phủ hồ sơ, trình tự. |
| N034 | Điểm d khoản 2 Điều 25 Luật 116 để ngỏ thời hạn sau khi người dùng ngừng dịch vụ. 24 tháng và 12 tháng của Nghị định 53 là hạn theo yêu cầu lưu trữ và hạn nhật ký điều tra, khác đồng hồ. |
| N035 | Điều 27 Luật 116 giao Bộ trưởng Bộ Công an ban hành quy chuẩn. Không có chuỗi QCVN và không có bảng chỉ tiêu trong 23 văn bản. |
| N036 | Điều 24 Nghị định 333 giao ban hành khung chương trình, không kèm số giờ. 24 tháng và 36 tháng là lộ trình tổ chức tập huấn. 80% là tỷ lệ chuyên cần, không phải điểm đạt. |
| N037 | Điều 33 Luật 116 dẫn sang Luật Giáo dục quốc phòng và an ninh. Luật đó không có trong corpus. Không có bài học hay khối lớp. |
| N038 | Điều 22 Luật 116 giao Chính phủ quy định chi tiết. Nghị định 330 chỉ có mức phạt, không có cơ quan chủ trì hay hạn báo cáo. |
| N039 | Điều 5 Luật 116 dẫn khởi tố, điều tra sang Bộ luật Tố tụng hình sự và nói Chính phủ không quy định chi tiết điểm này. Bộ luật đó không có trong corpus. |
| N040 | Luật 91 định nghĩa dữ liệu đã khử nhận dạng và cấm tái nhận dạng. Nghị định 356 chỉ giao xây dựng quy chuẩn. Không có phương pháp hay ngưỡng. |

## Kiểm tra khoản, điểm

Parser đọc `#### Điều` đầu tiên, khoản là dòng `N.` tăng dần ở tầng điều, điểm là dòng `a)` dưới khoản đang mở. Dòng trong ngoặc kép không tính. Đoạn gold, sau khi chuẩn hóa khoảng trắng, phải nằm trong điều; nếu có khoản thì nằm trong khoản đó; nếu có điểm thì cả đoạn nằm trên đúng dòng điểm và khoản cha khớp.

25 câu answerable: 0 lỗi. `point_without_clause = 0`. N008 để `point = null` vì câu 50% nằm trong khoản 3, sau điểm c, không phải một điểm. N025 lấy tiêu đề Điều 27, `clause = null`, vì thân điều không nhắc tên Luật Quảng cáo.

Không key hệ thống: `chunk_id`, `node_id`, `vector_id`, `candidate_hits` và các biến thể. 0. `CATEGORY_REVIEW` 0. `NEEDS_REVIEW` 0.

## Dọn scratch

Đã xóa helper của B2.3: `_b23_legacy_index.json`, `_b23_check.py`, `_b23_probe.py`, `_b23_probe_out.txt`. Không đụng các file `_audit_*` có sẵn từ trước.

## Pool gộp, chưa cắt

148 legacy + 40 mới = 188. Không cắt xuống 150. Không sửa definition hay obligation.

| Category | Legacy | B2.3 | Gộp | Target |
|---|---:|---:|---:|---:|
| definition | 30 | 0 | 30 | 20 |
| obligation | 53 | 0 | 53 | 25 |
| sanction_numeric | 13 | 12 | 25 | 25 |
| effectiveness_metadata | 15 | 5 | 20 | 20 |
| inter_document | 12 | 8 | 20 | 20 |
| multi_hop | 25 | 0 | 25 | 25 |
| unanswerable | 0 | 15 | 15 | 15 |
| Tổng | 148 | 40 | 188 | 150 |

Ba nhóm còn dư so với target là definition, obligation, và tổng. Việc cắt sang 150 không thuộc B2.3.
