# B2.4 FINAL-150 SELECTION REPORT

## Input

- Pool legacy: `benchmark/work/candidate_questions.json`, 148 câu, `candidate_id` C001–C148.
- Pool mới: `benchmark/work/new_questions_b2_3.json`, 40 câu, `id` N001–N040, `origin = b2_3_new`.
- Tổng đầu vào: 188. Không viết câu mới. Không sửa câu, category, answerable, gold_markers, gold_evidence, verification_status.
- Chọn không dùng kết quả KAG, HybridRAG, NativeRAG, retrieval score, answer score, latency hay benchmark result. Không chạy ba hệ thống.

## Final

- Giữ 150. Bỏ 38. Chỉ bỏ trong definition (10) và obligation (28).
- `benchmark/work/final_150_candidate.json`: id Q001–Q150. `source_id` là Cxxx hoặc Nxxx. Câu legacy giữ `candidate_id`, `legacy_id`, `fix_action` (kể cả null), `notes`. Câu mới giữ `origin = b2_3_new`, không bịa `candidate_id`.
- Thứ tự Q: definition, obligation, sanction_numeric, effectiveness_metadata, inter_document, multi_hop, unanswerable. Trong mỗi nhóm: legacy C trước, rồi N, theo số.
- `benchmark/work/B2_4_SELECTION_MANIFEST.json`: 188 dòng, thứ tự C001–C148 rồi N001–N040. DROP có `selected_id` null.

## Category distribution

| Category | Vào | Giữ | Bỏ | Đích |
|---|---:|---:|---:|---:|
| definition | 30 | 20 | 10 | 20 |
| obligation | 53 | 25 | 28 | 25 |
| sanction_numeric | 25 | 25 | 0 | 25 |
| effectiveness_metadata | 20 | 20 | 0 | 20 |
| inter_document | 20 | 20 | 0 | 20 |
| multi_hop | 25 | 25 | 0 | 25 |
| unanswerable | 15 | 15 | 0 | 15 |
| Tổng | 188 | 150 | 38 | 150 |

Id mới: definition Q001–Q020, obligation Q021–Q045, sanction_numeric Q046–Q070, effectiveness_metadata Q071–Q090, inter_document Q091–Q110, multi_hop Q111–Q135, unanswerable Q136–Q150.

## Definition selection

30 → 20. Giữ: C006, C009, C016, C032, C033, C048, C049, C060, C061, C076, C077, C104, C109, C116, C117, C118, C137, C138, C139, C145.

10 DROP:

- C017 — Cùng Điều 2 Luật 116 với C009 và C016. Không coi là trùng fact. Cắt vì luật này đã dày và hai khái niệm nền của điều đó được giữ.
- C025 — Cùng câu hỏi lực lượng bảo vệ an ninh mạng gồm những lực lượng nào với C077. Hai danh sách không giống nhau. Giữ C077 vì Nghị định 329 mỏng hơn; Luật 24/2018 còn C032 và C033.
- C031 — Cùng Điều 2 Luật 24/2018 với C033 đã giữ. Không coi là trùng C009. Cắt vì luật dày, giữ định nghĩa đối tượng cụ thể hơn ở cùng điều.
- C050 — Cùng Điều 2 Luật 91 với C048. B2.2 không coi L060 và L062 là trùng. Câu là danh mục hoạt động xử lý, có đuôi mở "hoạt động khác tác động đến dữ liệu cá nhân". C048 giữ khái niệm dữ liệu cá nhân. Luật 91 đã có nhiều câu ở nhóm khóa.
- C059 — Cùng Điều 3 Luật 86 với C060 và C061 đã giữ. B2.2 không gộp ba câu này. Cắt định nghĩa mục tiêu chung, giữ hai định nghĩa đối tượng cụ thể.
- C078 — Câu gói định nghĩa, nơi bố trí và đủ bảy nhiệm vụ, điểm g là "nhiệm vụ khác theo quy định của pháp luật". Không trùng C077: C077 chỉ nêu tên ba lực lượng, không nêu nơi bố trí và không nêu nhiệm vụ. Cắt danh mục nhiệm vụ; cơ cấu ba lực lượng vẫn ở C077, điều cấm của lực lượng dự bị ở C079.
- C085 — Định nghĩa vũ trụ ảo, khái niệm phụ. Nghị định 356 giữ hai nghĩa vụ có hạn cụ thể là C082 và C083.
- C095 — Định nghĩa khoản thu dùng cho cách tính tiền phạt. Nghị định 330 đã có 14 câu ở các nhóm không cắt.
- C119 — Điều 13 Luật 134 trùng phần thủ tục đánh giá sự phù hợp trước khi đưa vào sử dụng với C001 đã khóa. Phần riêng là chủ thể đánh giá. Luật 134 còn C116, C117, C118.
- C134 — Nghị định 142 đã có các câu nhóm khóa và nghĩa vụ hạn báo cáo C130. Cắt định nghĩa thẻ mô hình để giữ cả hai câu nguyên tắc của Thông tư 05, vì B2.2 xác định hai câu đó không trùng.

## Obligation selection

53 → 25. Giữ: C004, C005, C008, C011, C012, C014, C020, C022, C026, C047, C052, C062, C071, C073, C079, C082, C083, C098, C103, C106, C113, C120, C121, C130, C147.

28 DROP:

- C007 — Câu chủ yếu hỏi điều nào và lực lượng nào kiểm tra. Không giữ được một nghĩa vụ có hành vi và điều kiện riêng. Luật 24/2018 giữ C020, C022 và C026.
- C015 — Nghĩa vụ gỡ thông tin bí mật nhà nước, bí mật cá nhân, không có hạn, chỉ "kịp thời". Không cùng đối tượng với C011. C011 giữ hạn gỡ 24 giờ và 06 giờ. Luật 116 đã giữ sáu nghĩa vụ có điều kiện rõ hơn.
- C018 — Nghĩa vụ thẩm định trước khi vận hành. Luật 116 đã giữ hai hạn khác nhau ở Điều 25 (C004 và C011), cùng C005, C008, C012 và C014.
- C021 — Một điểm về an ninh vật lý. Luật 24/2018 đã giữ hai nhánh thời hạn kiểm tra mà B2.2 tách riêng (C020, C022) và nghĩa vụ lưu trữ, đặt chi nhánh (C026).
- C023 — Mệnh đề chung: kinh phí nằm trong dự toán ngân sách, không có mức hay điều kiện. Quy tắc ngân sách có mức được giữ ở C012.
- C027 — Hành vi đã nằm trong câu hỏi: phát tán chương trình gây hại, xâm nhập trái phép. Phần còn lại chủ yếu là số điều và số hiệu luật. Không trùng khoản 2 Điều 8. Khoản 2 là C029 và cũng bị cắt, vì luật dày, không phải vì trùng câu này.
- C028 — Công thức xử lý chung: kỷ luật, xử phạt, trách nhiệm hình sự, bồi thường. Không phải một nghĩa vụ có chủ thể và điều kiện riêng. Cùng kiểu với C063.
- C029 — Khoản 2 Điều 8 cấm tấn công mạng, khủng bố mạng, gián điệp mạng và phá hoại hệ thống quan trọng. Không trùng khoản 3 (C027) và không có câu khác giữ cụm này. Cắt vì Luật 24/2018 đã giữ ba nghĩa vụ có điều kiện: C020, C022, C026.
- C034 — Marker là "kịp thời cung cấp thông tin", không có hạn hay điều kiện. Luật 24/2018 đã giữ ba nghĩa vụ cụ thể hơn.
- C053 — Danh mục năm hành vi cấm của Nghị định 13. Cấm ở tầng luật được giữ bằng C052. Nghị định 13 còn câu ở nhóm khóa.
- C063 — Cùng công thức trách nhiệm chung như C028, đặt ở Luật 86. Luật này giữ C062.
- C066 — Quy hoạch kết cấu hạ tầng giao thông đường bộ, ngoài miền an ninh mạng, dữ liệu cá nhân và trí tuệ nhân tạo. Luật 35 còn câu liên văn bản ở nhóm khóa.
- C069 — Câu chủ yếu hỏi điều nào và tên cơ quan điều phối. Luật 86 giữ C062, là cấm cụ thể đối với thông tin cá nhân.
- C074 — Chỉ dẫn sang cơ quan tố tụng và Bộ luật Tố tụng hình sự, nghĩa vụ không khép kín trong corpus. Nghị định 328 giữ C071 và C073.
- C075 — Không cùng kết luận với C071. Đây là ngoại lệ không gắn nhãn với tin thuộc điểm a khoản 2 Điều 4. C071 giữ nghĩa vụ gắn nhãn trong 24 giờ. Cắt ngoại lệ, giữ nghĩa vụ chính. Nghị định 328 còn C073.
- C080 — Mức hỗ trợ 300% lương là chế độ đãi ngộ, không phải nghĩa vụ phải làm hoặc không được làm. C079 giữ điều cấm của lực lượng dự bị.
- C081 — Câu trỏ số điều và điểm dẫn chiếu, không nêu nghĩa vụ. Cùng Điều 7 với C079.
- C097 — Ba tên hình thức kiểm tra hộp đen, hộp xám, hộp trắng. Nghị định 331 giữ C098, là hạn báo cáo sự cố.
- C101 — Hỏi số mẫu và số phụ lục, không phải nghĩa vụ. Nghị định 341 giữ C103.
- C107 — Hạn bổ sung hồ sơ và hạn thẩm định. Điều kiện nhân sự của chính hoạt động được giữ ở C106. Nghị định 332 còn định nghĩa C109.
- C114 — Danh mục thành phần hồ sơ thẩm định. Nghị định 333 giữ C113, là ngưỡng khóa tài khoản.
- C122 — Cùng kết luận với C001 đã khóa: thông báo phân loại cho Bộ Khoa học và Công nghệ qua Cổng một cửa, Điều 10 khoản 3.
- C131 — Danh mục thành phần hồ sơ phân loại rủi ro. Nghị định 142 giữ C130, là hạn báo cáo sự cố.
- C132 — Danh mục bảy nội dung phải công khai về kết quả đánh giá sự phù hợp. Không trùng C001: C001 không hỏi nội dung công khai. Cắt vì là danh mục thành phần. Nghị định 142 giữ hạn báo cáo sự cố C130.
- C133 — Ba biện pháp an ninh hạ tầng và dữ liệu, không trùng hạn báo cáo của C130. Cắt vì là danh mục biện pháp trên Nghị định 142, nghị định này đã giữ C130.
- C141 — Danh mục giao việc của hai bộ, marker là cả đoạn nhiệm vụ hành chính. Quyết định 1671 còn câu ở nhóm khóa. Mẫu giao chủ trì được giữ gọn ở C147.
- C143 — Cùng khoản 2 Điều 1 Quyết định 1528 với C145. C145 giữ ba tầng nhân lực. C143 là dãy chỉ tiêu phần trăm.
- C144 — Danh mục nhiệm vụ của Bộ Giáo dục, cùng kiểu giao việc đã cắt ở C141. Quyết định 1528 được giữ bằng C145.

## Other categories

105/105 giữ. sanction_numeric 25, effectiveness_metadata 20, inter_document 20, multi_hop 25, unanswerable 15. Không có blocker substantive nên không đổi quota. 15 câu không trả lời được là N026–N040, `answerable = false`, gold_markers và gold_evidence rỗng.

## Coverage before/after

Một câu nhiều văn bản được đếm ở mỗi văn bản. `(none)` là 15 câu không trả lời được. Cặp điều = `(document_id, article)` khi article khác null. Corpus 23 văn bản. 127/QĐ-TTg = 0 trước và sau. Không giữ câu yếu để phủ 127. Không văn bản nào bị cắt sạch.

- Văn bản có câu: 22 → 22.
- Cặp điều: 155 → 130.

| Văn bản | Trước | Sau |
|---|---:|---:|
| 24/2018/QH14 | 19 | 10 |
| 116/2025/QH15 | 18 | 15 |
| 330/2026/NĐ-CP | 15 | 14 |
| 134/2025/QH15 | 14 | 12 |
| 142/2026/NĐ-CP | 10 | 6 |
| 91/2025/QH15 | 10 | 9 |
| 86/2015/QH13 | 10 | 7 |
| 356/2025/NĐ-CP | 8 | 7 |
| 341/2026/NĐ-CP | 8 | 7 |
| 328/2026/NĐ-CP | 7 | 5 |
| 71/2025/QH15 | 7 | 7 |
| 13/2023/NĐ-CP | 6 | 5 |
| 35/2018/QH14 | 6 | 5 |
| 329/2026/NĐ-CP | 6 | 3 |
| 331/2026/NĐ-CP | 6 | 5 |
| 333/2026/NĐ-CP | 6 | 5 |
| 53/2022/NĐ-CP | 5 | 5 |
| 332/2026/NĐ-CP | 5 | 4 |
| 05/2026/TT-BKHCN | 4 | 4 |
| 1671/QĐ-TTg | 3 | 2 |
| 1528/QĐ-TTg | 3 | 1 |
| 367/QĐ-TTg | 3 | 3 |
| 127/QĐ-TTg | 0 | 0 |

Nhóm theo văn bản sau khi chọn (chỉ văn bản còn lệch):

- 116/2025/QH15, 15: definition 3, obligation 6, effectiveness_metadata 5, inter_document 1.
- 330/2026/NĐ-CP, 14: sanction_numeric 12, effectiveness_metadata 1, multi_hop 1. Chỉ cắt được 1 definition. 12 câu phạt nằm ở nhóm khóa.
- 134/2025/QH15, 12: definition 3, obligation 2, inter_document 1, multi_hop 6.
- 24/2018/QH14, 10: definition 2, obligation 3, effectiveness_metadata 3, multi_hop 2. Từ 19 xuống 10.
- 1528/QĐ-TTg còn 1, là C145. 1671/QĐ-TTg còn 2, cả hai ở nhóm khóa.

Lệch còn lại nằm ở nhóm không được cắt, nhất là phạt của Nghị định 330 và multi_hop của Luật 71 (7 câu, không đổi) và Luật 134.

## Duplicate/redundancy audit

B2.2 đã chốt vài cặp không trùng. Bộ 150 giữ đúng các cặp đó:

- C004 (L005) và C011 (L012): hạn cung cấp thông tin người dùng và hạn gỡ thông tin. Giữ cả hai.
- C020 (L022) và C022 (L024): nhánh 72 giờ và nhánh 12 giờ của Luật 24/2018 Điều 13. Giữ cả hai.
- C138 (L152) và C139 (L153): danh sách nguyên tắc và nội dung nguyên tắc an toàn. Giữ cả hai. C134 bị cắt thay cho C139.
- C026 (L028) giữ. Nghĩa vụ đặt chi nhánh không có trong C014. Không gộp hai câu lưu trữ.
- Không gọi các nhóm matcher gộp nhầm là trùng fact: L010/L018/L019/L033, L060/L062, L071/L072/L073. Cắt trong các nhóm này, nếu có, chỉ vì luật dày hoặc đuôi mở, và lý do ghi là không trùng.
- L026 và L039 thuộc effectiveness_metadata, nhóm khóa, giữ cả hai.

Cụm 72 giờ không phải trùng: C082 là sự cố dữ liệu vị trí hoặc sinh trắc, C098 là sự cố an ninh mạng, C130 là sự cố nghiêm trọng của hệ thống trí tuệ nhân tạo. Khác chủ thể, văn bản và điều kiện.

Cắt vì gần trùng hoặc cùng kết luận: C122 với C001 (thông báo phân loại qua Cổng một cửa); C028 với C063 (cùng công thức trách nhiệm, cả hai cắt); C143 với C145 (cùng khoản, giữ cấu trúc ba tầng, cắt dãy chỉ tiêu).

Fact bị mất có chủ ý, không còn câu nào giữ: cụm cấm tấn công mạng ở C029; nơi bố trí và nhiệm vụ lực lượng chuyên trách ở C078; ngoại lệ không gắn nhãn ở C075. Không đủ để thành blocker vì câu gốc không sai và quota buộc cắt.

Không còn cặp trùng fact trong 150 mà lý do không giải thích được.

## Validation

- total 150. Id Q001–Q150 liên tục.
- source_id duy nhất. Không source nào vào hai lần.
- Quota đúng bảy nhóm.
- Câu trả lời được: gold_evidence và gold_markers không rỗng.
- N026–N040: answerable false, marker rỗng, evidence rỗng.
- point_without_clause = 0.
- Forbidden system id = 0. candidate_hits = 0.
- CATEGORY_REVIEW = 0. NEEDS_REVIEW = 0.
- verification_status = CORPUS_VERIFIED trên cả 150.
- Manifest 188. KEEP 150. DROP 38. definition DROP 10. obligation DROP 28. Nhóm khác DROP 0.
- So với pool gốc: category, answerable, question, gold_markers, gold_evidence, verification_status không đổi.
- Hai file pool gốc không bị sửa.

Không blocker.

B2.4 READY FOR REVIEW
