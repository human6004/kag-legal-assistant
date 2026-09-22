# B2.2 GAP REPORT

Nguồn: 166 câu legacy. B2.1: PASS 82, FIX 79, DROP 5 (L040, L043, L044, L048, L054 — không vào pool). Mọi gold trong pool là đoạn nguyên văn trong `data/processed`, `verification_status = CORPUS_VERIFIED`. Không có OFFICIAL VERIFIED. `candidate_hits` không được chép vào gold.

Đề xuất KEEP/DROP ở mục trùng **chưa áp dụng**. Câu trùng vẫn nằm trong pool.

## Candidate pool

- Dùng được: **154**
- PASS chuyển sang: **82** (`origin = legacy_pass`)
- FIX_KEEP: **44**
- FIX_REWRITE: **28**
- FIX_DROP: **7** (không vào pool)
- NEEDS_REVIEW còn mở: **0** (19/19 đã thành KEEP, REWRITE hoặc DROP)

FIX_DROP:

- L050 — câu hỏi “nghị định nào”, Điều 1 chỉ viết “Nghị định này”, không có số 356. Cùng câu đã được L096 hỏi đúng các khoản được quy định chi tiết.
- L114 — cột Phiếu khai báo Mẫu số 08 bị parser nuốt vào Điều 19 (Trách nhiệm thi hành). Gắn điều 19 là trỏ sai.
- L145 — chín dòng đối chiếu của mẫu báo cáo nằm trong bảng gộp, heading giả “Điều 5. Hiệu lực”.
- L154 — Phụ lục I dính span Điều 5. Gắn khoản 2 sẽ đè khoản 2 thật.
- L156 — chỉ tiêu 2030 của Quyết định 127 là danh sách mở; quyết định đã bị 1671 thay thế.
- L157 — không có danh sách khép cho cả tác động kinh tế và nhân lực.
- L158 — nhiệm vụ ba bộ trong Điều 1 Quyết định 127, marker bị cắt giữa câu; quyết định đã bị thay.

## Category distribution vs target 150

| Category | Pool | Target | Gap (target − pool) |
|---|---:|---:|---:|
| definition | 30 | 20 | −10 |
| obligation | 54 | 25 | −29 |
| sanction_numeric | 14 | 25 | 11 |
| effectiveness_metadata | 18 | 20 | 2 |
| inter_document | 13 | 20 | 7 |
| multi_hop | 25 | 25 | 0 |
| unanswerable | 0 | 15 | 15 |
| **Tổng** | **154** | **150** | |

Gap âm = pool nhiều hơn đích. B2.2 không cắt. B2.3 không viết thêm definition hay obligation.

`multi_hop` chỉ khi hai evidence độc lập, khác điều hoặc khác văn bản, và notes có evidence A, evidence B, vì sao một evidence không đủ. Hai khoản cùng một điều không tính multi_hop.

## Document coverage 23/23

Có mặt 22/23. Đếm theo số câu có ít nhất một evidence của văn bản đó (một câu nhiều văn bản được tính mỗi văn bản một lần).

- 116/2025/QH15: 19 (obligation 9, effectiveness_metadata 6, definition 4)
- 24/2018/QH14: 19 (obligation 10, definition 4, effectiveness_metadata 3, multi_hop 2)
- 134/2025/QH15: 14 (multi_hop 6, definition 4, obligation 3, inter_document 1)
- 330/2026/NĐ-CP: 12 (sanction_numeric 9, multi_hop 1, effectiveness_metadata 1, definition 1)
- 91/2025/QH15: 9 (multi_hop 3, sanction_numeric 2, definition 2, obligation 1, effectiveness_metadata 1)
- 328/2026/NĐ-CP: 8 (obligation 4, effectiveness_metadata 2, multi_hop 1, definition 1)
- 142/2026/NĐ-CP: 8 (obligation 4, effectiveness_metadata 2, definition 1, inter_document 1)
- 86/2015/QH13: 8 (definition 3, obligation 3, multi_hop 1, inter_document 1)
- 356/2025/NĐ-CP: 6 (obligation 2, inter_document 2, multi_hop 1, definition 1)
- 71/2025/QH15: 6 (multi_hop 5, sanction_numeric 1)
- 13/2023/NĐ-CP: 5 (multi_hop 3, definition 1, obligation 1)
- 35/2018/QH14: 5 (inter_document 4, obligation 1)
- 329/2026/NĐ-CP: 5 (obligation 3, definition 2)
- 331/2026/NĐ-CP: 5 (multi_hop 3, obligation 2)
- 341/2026/NĐ-CP: 5 (obligation 2, sanction_numeric 1, definition 1, effectiveness_metadata 1)
- 332/2026/NĐ-CP: 5 (obligation 2, sanction_numeric 1, definition 1, multi_hop 1)
- 333/2026/NĐ-CP: 5 (inter_document 2, obligation 2, effectiveness_metadata 1)
- 1671/QĐ-TTg: 4 (inter_document 2, effectiveness_metadata 1, obligation 1)
- 05/2026/TT-BKHCN: 4 (definition 3, multi_hop 1)
- 1528/QĐ-TTg: 3 (obligation 2, definition 1)
- 367/QĐ-TTg: 3 (inter_document 1, obligation 1, multi_hop 1)
- 53/2022/NĐ-CP: 2 (obligation 1, multi_hop 1)
- 127/QĐ-TTg: **0**

Lệch: hai luật an ninh mạng chiếm 19 câu mỗi luật; 53/2022 chỉ 2 câu. 127/QĐ-TTg bằng 0 vì các câu legacy trên quyết định này là danh sách mở và quyết định đã bị 1671 thay. Không bịa câu cho đủ mặt văn bản.

## Duplicate groups

Đề xuất, chưa xóa khỏi pool.

Trùng thật:

- L004 / L099 — cùng 330/2026 Điều 34 khoản 2 điểm c, phạt 30–50 triệu, AI/Deepfake giả khuôn mặt, giọng nói. L004 thêm “ngân hàng”, chữ đó không có trong điểm c. **KEEP L099, DROP L004.**
- L005 / L012 / L017 — cùng 116/2025 Điều 25. L005 là hạn cung cấp thông tin người dùng. L012 là hạn gỡ thông tin. L017 gộp cả hai. **KEEP L005, KEEP L012, DROP L017.**
- L011 / L041 — cùng 116/2025 Điều 44 khoản 1 và khoản 2. L041 hỏi “còn hiệu lực không”, đáp án phụ thuộc ngày chấm. **KEEP L011, DROP L041.**
- L046 / L052 — cùng Điều 44 khoản 2. L046 hỏi những luật nào hết hiệu lực. L052 chỉ hỏi 86/2015. **KEEP L046, DROP L052.** L011 hỏi ngày, không cùng kết luận, giữ.
- L042 / L051 — cùng 328/2026 Điều 23, cùng hỏi ngày 05/10/2026. **KEEP L042, DROP L051.**
- L047 / L160 — cùng 1671 Điều 3. L047 chỉ câu thay thế 127. L160 thêm khoản 3 (việc đang làm theo 127 được tiếp tục). **KEEP L160, DROP L047.**
- L026 / L039 — cùng 24/2018 Điều 43, hạn sau khi được đưa vào danh mục hệ thống quan trọng. L039 hỏi thêm trách nhiệm của chủ quản. **KEEP L039, DROP L026.**

Cùng vùng nhưng không trùng, giữ cả hai:

- L002 / L100 — cùng 330/2026 Điều 53 khoản 3 (không có khoản thu), khác bậc: nhạy cảm 200–dưới 400 chủ thể, và cơ bản từ 10.000 trở lên.
- L022 / L024 — cùng 24/2018 Điều 13, nhánh 72 giờ và nhánh 12 giờ.
- L028 / L037 — trùng vế đặt chi nhánh, văn phòng đại diện (Điều 26). L037 còn hỏi nghĩa vụ cảnh báo và phương án sự cố ở Điều 41.
- L055 / L056 — cùng 91/2025 Điều 8, một câu là mua bán dữ liệu, một câu là chuyển xuyên biên giới.
- L152 / L153 — cùng 05/2026 Điều 3. L152 là danh sách nguyên tắc. L153 hỏi yêu cầu của riêng nguyên tắc an toàn.

Matcher gộp nhầm, không lập nhóm trùng: L010/L018/L019/L033 (bốn định nghĩa khác nhau); L015/L017 (khoản 3 lưu trữ và khoản 2 thời hạn); L060/L062; L071/L072/L073; L076/L080 (hai luật bị sửa khác nhau).

## Questions requiring new authoring

Chỉ phần còn thiếu so với đích 150. Không viết câu ở B2.2.

- sanction_numeric: 11
- effectiveness_metadata: 2
- inter_document: 7
- unanswerable: 15
- multi_hop: 0

definition và obligation đã vượt đích. Việc cắt bớt thuộc bước chọn bộ 150, không phải viết câu mới. Nếu sau này áp dụng các DROP ở trên, pool giảm 7 câu (L004, L017, L041, L052, L051, L047, L026) và các gap dương tăng tương ứng. B2.2 chưa áp dụng.
