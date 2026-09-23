# B2.2 GAP REPORT

Nguồn: 166 câu legacy. B2.1: PASS 82, FIX 79, DROP 5 (L040, L043, L044, L048, L054 — không vào pool). Mọi gold trong pool là đoạn nguyên văn trong `data/processed`, `verification_status = CORPUS_VERIFIED`. Không có OFFICIAL VERIFIED. `candidate_hits` không được chép vào gold.

Duplicate decisions are now applied. Sáu câu trùng đã bị xóa khỏi pool. L026 và L039 giữ cả hai.

## Candidate pool

- Dùng được: **148** (154 trừ 6 câu trùng đã áp dụng)
- PASS chuyển sang: **82** (`origin = legacy_pass`)
- FIX_KEEP: **42**
- FIX_REWRITE: **24**
- FIX_DROP: **7** (không vào pool, từ B2.2 trước bước dedup)
- Duplicate DROP đã áp dụng: **6** — L004 (FIX_KEEP), L047 (FIX_KEEP), L017, L041, L051, L052 (FIX_REWRITE)
- NEEDS_REVIEW còn mở: **0**

Mọi `gold_evidence` có `point` đã được điền `clause` bằng cách đọc điều trong `data/processed` (khoản là dòng `N.` của chính điều đó; điểm nằm trong ngoặc kép của luật sửa đổi không được tính là khoản của điều). 165 điểm, 0 điểm không có khoản cha. Ba clause cũ trỏ nhầm vào khoản được trích: L078 cả hai evidence từ khoản 3 và 4 sang khoản 2 Điều 1 Luật 35/2018 (khối bổ sung Điều 6a); L080 từ khoản 1 sang khoản 4 Điều 8. Chữ evidence không đổi.

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
| obligation | 53 | 25 | −28 |
| sanction_numeric | 13 | 25 | 12 |
| effectiveness_metadata | 15 | 20 | 5 |
| inter_document | 12 | 20 | 8 |
| multi_hop | 25 | 25 | 0 |
| unanswerable | 0 | 15 | 15 |
| **Tổng** | **148** | **150** | |

Gap âm = pool nhiều hơn đích. B2.2 không cắt. B2.3 không viết thêm definition hay obligation.

`multi_hop` chỉ khi hai evidence độc lập, khác điều hoặc khác văn bản, và notes có evidence A, evidence B, vì sao một evidence không đủ. Hai khoản cùng một điều không tính multi_hop.

## Document coverage 23/23

Có mặt 22/23. Đếm theo số câu có ít nhất một evidence của văn bản đó (một câu nhiều văn bản được tính mỗi văn bản một lần).

- 116/2025/QH15: 16 (obligation 8, effectiveness_metadata 4, definition 4)
- 24/2018/QH14: 19 (obligation 10, definition 4, effectiveness_metadata 3, multi_hop 2)
- 134/2025/QH15: 14 (multi_hop 6, definition 4, obligation 3, inter_document 1)
- 330/2026/NĐ-CP: 11 (sanction_numeric 8, multi_hop 1, effectiveness_metadata 1, definition 1)
- 91/2025/QH15: 9 (multi_hop 3, sanction_numeric 2, definition 2, obligation 1, effectiveness_metadata 1)
- 328/2026/NĐ-CP: 7 (obligation 4, effectiveness_metadata 1, multi_hop 1, definition 1)
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
- 1671/QĐ-TTg: 3 (inter_document 1, effectiveness_metadata 1, obligation 1)
- 05/2026/TT-BKHCN: 4 (definition 3, multi_hop 1)
- 1528/QĐ-TTg: 3 (obligation 2, definition 1)
- 367/QĐ-TTg: 3 (inter_document 1, obligation 1, multi_hop 1)
- 53/2022/NĐ-CP: 2 (obligation 1, multi_hop 1)
- 127/QĐ-TTg: **0**

Lệch: 24/2018/QH14 còn 19 câu; 116/2025/QH15 còn 16 sau khi bỏ trùng; 53/2022 chỉ 2 câu. 127/QĐ-TTg bằng 0 vì các câu legacy trên quyết định này là danh sách mở và quyết định đã bị 1671 thay. Không bịa câu cho đủ mặt văn bản.

## Duplicate groups

Duplicate decisions are now applied. Sáu DROP đã xóa khỏi pool. Câu KEEP còn lại.

Đã áp dụng:

- L004 / L099 — cùng 330/2026 Điều 34 khoản 2 điểm c. L004 thêm “ngân hàng”, chữ không có trong điểm c. **KEEP L099, DROP L004.**
- L005 / L012 / L017 — cùng 116/2025 Điều 25. L005 là hạn cung cấp thông tin người dùng. L012 là hạn gỡ thông tin. L017 gộp cả hai. **KEEP L005, KEEP L012, DROP L017.**
- L011 / L041 — cùng 116/2025 Điều 44 khoản 1 và khoản 2. L041 hỏi “còn hiệu lực không”, đáp án phụ thuộc ngày chấm. **KEEP L011, DROP L041.**
- L046 / L052 — cùng Điều 44 khoản 2. L046 hỏi những luật nào hết hiệu lực. L052 chỉ hỏi 86/2015. **KEEP L046, DROP L052.** L011 hỏi ngày, giữ.
- L042 / L051 — cùng 328/2026 Điều 23, cùng ngày 05/10/2026. **KEEP L042, DROP L051.**
- L047 / L160 — cùng 1671 Điều 3. L047 chỉ câu thay thế 127. L160 thêm khoản 3. **KEEP L160, DROP L047.**

Cùng vùng nhưng không trùng, giữ cả hai:

- L026 / L039 — cùng 24/2018 Điều 43, hai tình huống khác nhau. L026 là khoản 3: hệ thống đang vận hành được **bổ sung** vào Danh mục, 12 tháng kể từ ngày được bổ sung. L039 là khoản 2: hệ thống đang vận hành được **đưa vào** Danh mục, 12 tháng kể từ ngày luật có hiệu lực. **KEEP L026, KEEP L039.** Gold của L026 trước đây dính cả khoản 2; đã bỏ evidence đó, chỉ còn khoản 3.
- L002 / L100 — cùng 330/2026 Điều 53 khoản 3 (không có khoản thu), khác bậc.
- L022 / L024 — cùng 24/2018 Điều 13, nhánh 72 giờ và nhánh 12 giờ.
- L028 / L037 — trùng vế đặt chi nhánh, văn phòng đại diện (Điều 26). L037 còn hỏi nghĩa vụ cảnh báo và phương án sự cố ở Điều 41.
- L055 / L056 — cùng 91/2025 Điều 8, một câu là mua bán dữ liệu, một câu là chuyển xuyên biên giới.
- L152 / L153 — cùng 05/2026 Điều 3. L152 là danh sách nguyên tắc. L153 hỏi riêng nguyên tắc an toàn.

Matcher gộp nhầm, không lập nhóm trùng: L010/L018/L019/L033; L015 với hạn ở khoản 2 (L017 đã drop vì gộp L005/L012, không phải vì trùng L015); L060/L062; L071/L072/L073; L076/L080.

## Questions requiring new authoring

Chỉ phần còn thiếu so với đích 150, tính trên pool 148 sau dedup. Không viết câu ở B2.2.

- sanction_numeric: 12
- effectiveness_metadata: 5
- inter_document: 8
- unanswerable: 15
- multi_hop: 0

Tổng câu mới: **40**.

definition dư 10, obligation dư 28. Cắt bớt thuộc bước chọn bộ 150, không phải viết câu mới.
