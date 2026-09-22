# B2.1 audit summary

Audit 166 câu trong `kag/solver/data/questions_mo_rong.json`. Đây là hồ sơ phân loại, không phải bộ gold cuối.

## Cách làm

Đối từng câu với văn bản trong `data/processed/**`. Không đối vbpl.vn hay công báo. Không chạy KAG, HybridRAG, NativeRAG. Không lấy kết quả hệ thống để sửa câu.

`CHECKED`: đã đọc câu luật tương ứng trong corpus. `NEEDS_REVIEW`: còn một điểm chưa chốt (danh sách mở, cách đọc, gán nhiệm vụ). Không có `VERIFIED`.

## Số liệu

| | |
|---|---|
| PASS | 82 |
| FIX | 79 |
| DROP | 5 |
| CHECKED | 147 |
| NEEDS_REVIEW | 19 |

DROP giữ nguyên: L040, L043, L044, L048, L054.

Cleanup sau review: L021, L088, L116, L121, L130 chuyển PASS sang FIX vì danh sách gold thiếu điểm đã đọc được trong điều. L016, L152, L164 giữ PASS và lên CHECKED. L067 giữ PASS; thêm candidate hit cho Điều 9 và Điều 22 Nghị định 13/2023 vì matcher bỏ marker chỉ là số điều.

## candidate_hits không phải gold

`candidate_hits` là cửa sổ matcher, hoặc hit bổ sung tay khi matcher bỏ sót. Có thể trỏ sai điều. Không được lấy làm `gold_evidence` ở B2.2. Gold sau này phải là câu chép nguyên văn từ corpus, gắn đúng văn bản và điều.

## corpus_checked không phải đối nguồn chính thức

`corpus_checked: true` chỉ nghĩa là đã đọc file markdown trong repo. `official_source_checked: false` trên mọi record. Chưa đối nguồn chính thức thì không được ghi đã đối.
