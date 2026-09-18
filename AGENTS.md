# Làm việc với graph pháp lý

- Trả lời người dùng bằng tiếng Việt. Lệnh shell bắt đầu bằng `rtk`.
- Trước khi sửa graph, đọc [bản đồ dữ liệu](dist/README.md). Kiểm nguồn ở `data/raw/`, `data/processed/`, `data/metadata/` và đường chạy thật trong `kag/`; báo cáo audit không thay thế nguồn hoặc mã.
- Giữ nguyên `dist/legal.dump`, `kag/ckpt/LegalSchemaFreeExtractor/cache.db` và `dist/audit-2026-09-17/` để đối chứng. Bản mới phải có đường dẫn, changelog và SHA-256 riêng.
- Reader R4 là mốc kiểm tra hiện tại. Gói 4–6 R2 **chưa được chốt**: đọc `dist/review-v2-phase4-6-r2/REVIEW.md` trước khi dùng số liệu embedding/migration. Các gói cũ chỉ để tra lịch sử.
- Không tự đánh dấu fact `VERIFIED`/`human_verified` từ LLM, checkpoint hoặc phép khớp chuỗi. Fact thiếu nguồn rõ ràng không được đưa vào tập đánh giá.
- `kag/kag_config.yaml` có thể chứa bí mật; không chép nguyên file vào báo cáo hoặc manifest công khai.
