# Nguồn uy tín đã thẩm định

Nguyên tắc chọn nguồn cho dữ liệu luật (đặc biệt quan trọng vì sẽ nạp vào chatbot tư vấn):

1. **Ưu tiên tuyệt đối nguồn Nhà nước / cơ quan ban hành** (Công báo, Quốc hội, Chính phủ, Bộ chủ quản).
   Đây là bản gốc, có giá trị pháp lý, không qua diễn giải của bên thứ ba.
2. Nguồn tổng hợp tư nhân (thuvienphapluat.vn, hethongphapluat.com...) chỉ dùng để **tra cứu nhanh /
   đối chiếu / xem bản dịch tiếng Anh**, không dùng làm nguồn chính thức cuối cùng — vì các trang này
   có thể cập nhật chậm hoặc gắn bình luận không phải văn bản gốc. Luôn đối chiếu với bản Công báo/gốc.
3. Với luật quốc tế, chỉ lấy từ **cổng chính thức của cơ quan lập pháp/tổ chức đó** (EUR-Lex, Federal
   Register, NIST.gov, OECD.AI, UNESCO.org...), không lấy qua báo chí diễn giải lại.

## 1. Luật An ninh mạng & bảo mật dữ liệu — Việt Nam

| Văn bản | Nguồn chính thống ưu tiên | Ghi chú |
|---|---|---|
| Luật An ninh mạng 2018 (số 24/2018/QH14) | [Cơ sở dữ liệu quốc gia về pháp luật – vbpl.vn](https://vbpl.vn/Pages/vbpq-timkiem.aspx) (Bộ Tư pháp quản lý, đây là **nguồn gốc chính thức cấp nhà nước**, nên tra ở đây trước) | Tra số hiệu 24/2018/QH14. Bản tiếng Việt full-text kèm tình trạng hiệu lực. |
| Bản đối chiếu nhanh | [thuvienphapluat.vn – Toàn văn Luật An ninh mạng 2018](https://thuvienphapluat.vn/chinh-sach-phap-luat-moi/vn/ho-tro-phap-luat/chinh-sach-moi/20609/toan-van-luat-an-ninh-mang-2018) | Chỉ dùng đối chiếu, không dùng làm bản gốc |
| Văn bản hướng dẫn thi hành (Nghị định 53/2022/NĐ-CP quy định chi tiết Luật ANM) | vbpl.vn, tra số 53/2022/NĐ-CP | Bắt buộc lấy kèm — Luật gốc không đủ, cần cả Nghị định hướng dẫn |
| Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân | [Cổng TTĐT Chính phủ – xaydungchinhsach.chinhphu.vn (toàn văn)](https://xaydungchinhsach.chinhphu.vn/toan-van-nghi-dinh-13-2023-nd-cp-bao-ve-du-lieu-ca-nhan-119230516104357809.htm) | Liên quan mật thiết đến an ninh mạng, dữ liệu cá nhân — chatbot tư vấn luật nên gộp |
| Tổng hợp văn bản ngành TT&TT về an toàn/an ninh mạng | [mic.gov.vn (Bộ TT&TT / nay là Bộ KH&CN quản lý mảng này)](https://mic.gov.vn/cac-van-ban-quy-pham-phap-luat-ve-bao-mat-an-toan-va-an-ninh-mang-ban-hanh-nam-2018-197143857.htm) | Trang bộ chủ quản, liệt kê đầy đủ văn bản liên quan theo năm |
| Luật An toàn thông tin mạng 2015 (số 86/2015/QH13) | vbpl.vn, tra số 86/2015/QH13 | Hay bị nhầm với Luật ANM 2018 — đây là luật khác, **cả hai đều cần** cho chatbot vì phạm vi bổ sung nhau |

## 2. Luật / khung an ninh mạng — Quốc tế

Có. An ninh mạng có nhiều văn bản/khung quốc tế quan trọng, nên tách riêng nhóm này
(`data/raw/quoc_te_an_ninh_mang/`) thay vì gộp vào phần AI quốc tế.

| Văn bản | Nguồn chính thống (bắt buộc lấy từ đây) | Ghi chú |
|---|---|---|
| **UN Convention against Cybercrime ("Hanoi Convention")** | [UNODC – trang chính thức Công ước](https://www.unodc.org/unodc/en/cybercrime/convention/home.html); văn bản gốc/tình trạng ký kết tại **United Nations Treaty Collection** | LHQ thông qua 24/12/2024, mở ký lần đầu **tại Hà Nội ngày 25/10/2025** — Việt Nam là nước chủ nhà lễ ký. Rất đáng để đưa vào vì gắn trực tiếp với VN và là công ước hình sự mạng đa phương đầu tiên của LHQ. |
| EU — NIS2 Directive (Directive (EU) 2022/2555) | [EUR-Lex – bản chính thức](https://eur-lex.europa.eu/eli/dir/2022/2555/2022-12-27/eng) | Khung an ninh mạng bắt buộc cho hạ tầng trọng yếu của EU — hay được dùng để đối chiếu mô hình quản lý với Luật ANM VN |
| Council of Europe — Budapest Convention on Cybercrime (2001) + Nghị định thư bổ sung | [coe.int – Budapest Convention, trang chính thức](https://www.coe.int/en/web/cybercrime/the-budapest-convention) | Công ước tội phạm mạng đa phương lâu đời nhất, nền tảng cho nhiều luật quốc gia (VN không phải thành viên nhưng hay được luật VN tham chiếu so sánh) |
| Mỹ — NIST Cybersecurity Framework (CSF 2.0, 2024) | [nist.gov/cyberframework](https://www.nist.gov/cyberframework) (bản PDF gốc tại [nvlpubs.nist.gov](https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf)) | Framework kỹ thuật/quản trị rủi ro, không phải luật cứng nhưng là chuẩn tham chiếu toàn cầu |
| Mỹ — CISA (Cybersecurity and Infrastructure Security Agency) | [cisa.gov](https://www.cisa.gov/resources-tools/resources/framework-improving-critical-infrastructure-cybersecurity) | Cơ quan liên bang, hướng dẫn áp dụng framework cho hạ tầng trọng yếu |
| EU — GDPR (Regulation (EU) 2016/679) | [EUR-Lex – bản chính thức](https://eur-lex.europa.eu/eli/reg/2016/679/oj) | Không phải "luật an ninh mạng" thuần túy nhưng là chuẩn bảo vệ dữ liệu cá nhân quốc tế được Nghị định 13/2023/NĐ-CP của VN tham khảo mô hình — nên có để đối chiếu |

## 3. Luật / quy định AI — Việt Nam

| Văn bản | Nguồn chính thống ưu tiên | Ghi chú |
|---|---|---|
| **Luật Trí tuệ nhân tạo 2025 (số 134/2025/QH15)** — hiệu lực từ 01/3/2026 | vbpl.vn, tra số 134/2025/QH15 (khi có trên hệ thống); tạm thời đối chiếu tại [thuvienphapluat.vn – Luật Trí tuệ nhân tạo 2025 số 134/2025/QH15](https://thuvienphapluat.vn/van-ban/Cong-nghe-thong-tin/Luat-Tri-tue-nhan-tao-2025-so-134-2025-QH15-679013.aspx) và [Bộ Khoa học và Công nghệ – mst.gov.vn](https://mst.gov.vn/ai-la-cong-cu-ho-tro-quyet-dinh-cuoi-cung-van-la-con-nguoi-19726030111172663.htm) | **Đây là văn bản quan trọng nhất cho use case của bạn** — luật chuyên biệt đầu tiên về AI của VN. Vì rất mới (2025/2026), nhớ tra lại vbpl.vn để lấy đúng bản Công báo cuối cùng, không chỉ tin bài báo tổng hợp. |
| Luật Công nghiệp công nghệ số 2024 (có điều khoản về AI, tài sản số) | vbpl.vn | Luật khung rộng hơn, ban hành trước Luật AI chuyên biệt — cần để hiểu quan hệ giữa 2 luật |
| Chiến lược quốc gia về nghiên cứu, phát triển và ứng dụng AI đến 2030 (Quyết định 127/QĐ-TTg, 2021) | vbpl.vn, tra số 127/QĐ-TTg | Văn bản định hướng chính sách, không phải quy phạm bắt buộc nhưng hay được chatbot tư vấn dẫn chiếu |
| Cơ quan chủ quản để theo dõi văn bản mới | [Bộ Khoa học và Công nghệ – mst.gov.vn](https://mst.gov.vn/) | Sau hợp nhất, đây là bộ phụ trách AI — theo dõi để cập nhật Nghị định hướng dẫn Luật AI 2025 khi ban hành |

## 4. Luật / khung AI — Quốc tế

| Văn bản | Nguồn chính thống (bắt buộc lấy từ đây) | Ghi chú |
|---|---|---|
| EU AI Act (Regulation (EU) 2024/1689) | [EUR-Lex – bản chính thức](https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng) (có tất cả ngôn ngữ EU) | Đây LÀ bản luật gốc, không phải bản diễn giải |
| EU AI Act — bản có chú giải, điều khoản dễ tra cứu | [artificialintelligenceact.eu (Future of Life Institute – phi lợi nhuận, được cộng đồng pháp lý dùng rộng rãi)](https://artificialintelligenceact.eu/the-act/) | Không phải nguồn chính thức của EU nhưng rất uy tín để tra cứu nhanh theo điều khoản |
| OECD AI Principles (2019, cập nhật 2024) | [OECD Legal Instruments – legalinstruments.oecd.org](https://legalinstruments.oecd.org/en/instruments/oecd-legal-0449) | Văn bản khuyến nghị (soft law), nhiều nước kể cả VN tham chiếu |
| UNESCO Recommendation on the Ethics of AI (2021) | [unesco.org – trang chính thức](https://www.unesco.org/en/artificial-intelligence/recommendation-ethics) | Khung đạo đức AI được 193 nước thông qua |
| Mỹ — NIST AI Risk Management Framework | [nist.gov/itl/ai-risk-management-framework](https://www.nist.gov/itl/ai-risk-management-framework) | Framework kỹ thuật, không phải luật cứng nhưng ảnh hưởng lớn tới chuẩn quốc tế |
| Mỹ — các Executive Order / hành động lập pháp về AI | [nist.gov – AI Congressional Mandates, Executive Orders and Actions](https://www.nist.gov/artificial-intelligence/ai-congressional-mandates-executive-orders-and-actions) | Mỹ chưa có luật liên bang thống nhất về AI như EU — cần nói rõ điều này trong chatbot để tránh gây hiểu lầm |

## Ghi chú khi cào

- Luôn lưu **ngày cào** (`retrieved_date`) vào metadata — luật thay đổi liên tục, đặc biệt Luật AI VN vừa ban hành.
- Với các trang tổng hợp tư nhân, nếu thấy mâu thuẫn với vbpl.vn/EUR-Lex/nist.gov thì **luôn tin nguồn chính thống**.
- Luật Trí tuệ nhân tạo VN 2025 và các nghị định hướng dẫn còn đang trong giai đoạn hoàn thiện (hiệu lực 3/2026)
  — nên định kỳ quay lại mst.gov.vn / vbpl.vn kiểm tra văn bản hướng dẫn mới trước khi coi data là "hoàn chỉnh".
