# indexing/graph/graph_schema.py
from typing import Literal

POSSIBLE_ENTITIES = [
    "VanBanPhapLuat",      # Luật, Nghị định, Thông tư, Quyết định
    "DieuKhoan",           # Điều, Khoản, Điểm cụ thể (ví dụ: Điều 34, Khoản 2 Điều 8)
    "CoQuanBanHanh",       # Quốc hội, Chính phủ, Bộ TT&TT, Bộ KH&CN, Bộ Công an
    "ChuThe",              # Cá nhân, Tổ chức, Doanh nghiệp, Chủ quản hệ thống, Bên kiểm soát DLCN
    "HanhViViPham",        # Hành vi bị nghiêm cấm, vi phạm quy định an ninh mạng, AI, dữ liệu
    "CheTai_HinhPhat",     # Phạt tiền, tịch thu tang vật, tước giấy phép, đình chỉ hoạt động
    "KhaiNiemPhapLy",      # Dữ liệu cá nhân nhạy cảm, Hệ thống AI rủi ro cao, Không gian mạng
    "LinhVuc",             # An ninh mạng, Trí tuệ nhân tạo, Dữ liệu cá nhân, Mật mã dân sự
]

POSSIBLE_RELATIONS = [
    "BAN_HANH",            # Cơ quan ban hành -> Văn bản pháp luật
    "QUY_DINH_CHI_TIET",   # Nghị định -> quy định chi tiết cho -> Luật
    "SUA_DOI_BO_SUNG",     # Văn bản sửa đổi -> sửa đổi bổ sung cho -> Văn bản cũ
    "THAY_THE",            # Văn bản mới -> thay thế -> Văn bản cũ
    "THUOC_VAN_BAN",       # Điều khoản -> thuộc về -> Văn bản pháp luật
    "VIEN_DAN",            # Điều khoản -> viện dẫn/tham chiếu tới -> Điều khoản khác
    "QUY_DINH_VE",         # Điều khoản -> quy định về -> Khái niệm pháp lý / Hành vi
    "XU_PHAT",             # Hành vi vi phạm / Điều khoản -> áp dụng mức phạt -> Chế tài
    "AP_DUNG_CHO",         # Điều khoản / Nghĩa vụ -> áp dụng đối với -> Chủ thể
]

# Type Literal cho LlamaIndex SchemaLLMPathExtractor
entities = Literal[tuple(POSSIBLE_ENTITIES)]
relations = Literal[tuple(POSSIBLE_RELATIONS)]