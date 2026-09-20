# -*- coding: utf-8 -*-
"""Nhận diện thực thể trong CÂU HỎI pháp luật tiếng Việt (bước truy hồi).

Khác với kag/builder/prompt/ner.py: file kia chạy lúc BUILD, đọc cả đoạn văn
luật dài và trích ra mọi thực thể (hành vi, chế tài, điều luật...). File này
chạy lúc HỎI, chỉ nhận một câu hỏi ngắn, và mục đích hẹp hơn nhiều: rút ra vài
cái tên để làm điểm xuất phát cho Personalized PageRank trên đồ thị.

Vì sao cần file này: Ner.__init__ (kag/common/tools/algorithm_tool/ner.py:31)
gọi init_prompt_with_fallback("question_ner", biz_scene). Với biz_scene=legal,
PromptABC tìm "legal_question_ner"; không có thì rơi về "default_question_ner"
là bản tiếng Anh của KAG, vốn chỉ có ví dụ về tạp chí Mỹ ("Which magazine was
started first...") và schema lấy từ ReasonerClient. Bản tiếng Anh không hỏng
hẳn vì LLM vẫn hiểu câu hỏi tiếng Việt, nhưng nó không được dặn gì về cách gọi
tên văn bản luật Việt Nam, nên hay trả về tên chung chung như "Nghị định",
"Chính phủ" - đúng những tên xuất hiện ở hàng trăm chunk, làm điểm xuất phát
PageRank bị loãng.

Ba ràng buộc kỹ thuật phải giữ, đọc từ chính mã nguồn đang chạy:

1. category BẮT BUỘC có. Ner.invoke (ner.py:128-139) đọc item["category"]; thiếu
   khóa này là KeyError. Dòng 134 so category với works/person/other, khớp thì
   lấy name gốc, không khớp thì lấy official_name. Ở đường này with_semantic
   mặc định False (ppr_chunk_retriever.py:63 không truyền), nên
   named_entity_standardization KHÔNG chạy và official_name luôn thiếu ->
   invoke lấy entity = item.get("official_name", entity) = chính name. Nghĩa là
   trường name mới là thứ đi vào đồ thị. Vẫn trả category vì nó là khóa bắt buộc
   và vì un_std_entity_type dùng nó về sau.
2. category phải là một kiểu CÓ THẬT trong schema. Trả tên bịa thì entity bị
   đẩy về Others và mất hết tác dụng phân biệt. Vì vậy template nhúng $schema
   lấy động, giống bản default.
3. Không được lấy schema qua SchemaClient.load() như builder/prompt/ner.py.
   Cách đó đọc file schema của builder, còn ở tiến trình eval thì đường đúng là
   ReasonerClient.get_reason_schema() - bản default_question_ner dùng cách này
   và nó chạy được trong chính môi trường này. Bám theo bản chạy được.

Về chọn category nào: chỉ dùng 4 nhóm hẹp. Article cho "Điều 34", LegalDocument
cho văn bản kèm số hiệu, LegalTerm cho thuật ngữ được luật định nghĩa,
Authority/RegulatedEntity cho cơ quan và đối tượng. Cố tình KHÔNG dùng
ProhibitedAct/Sanction/Obligation: đó là các nhóm dành cho việc mô tả hành vi
trong văn bản luật, còn câu hỏi thì hiếm khi nêu nguyên một hành vi bị cấm, và
một cái tên dài như câu mô tả hành vi gần như không trùng node nào trên đồ thị
nên vô ích cho PageRank.

Về SỐ LƯỢNG thực thể - chỗ này đã đo rồi mới viết, đừng đoán lại: bản đầu của
file này dặn "tối đa 6 thực thể" vì lý luận rằng ít mà trúng thì PageRank đỡ
loãng. Chạy thử 5 câu rồi so với bản tiếng Anh (không giới hạn) cho kết quả
NGƯỢC LẠI: hit@1 tụt 0.600 -> 0.200, MRR tụt 0.711 -> 0.461, trong khi hit@20
vẫn 1.000 ở cả hai. Tức chunk đúng vẫn luôn được lấy về nhưng bị đẩy xuống hạng
thấp hơn. Với PageRank thì nhiều điểm xuất phát lại tốt hơn, miễn mỗi điểm đủ
cụ thể. Nên quy tắc (8) hiện tại yêu cầu trích càng nhiều càng tốt.

Chỗ dễ nhầm: cái làm loãng PageRank là thực thể CHUNG CHUNG khớp hàng trăm node
(như "Chính phủ", "Nghị định"), chứ không phải SỐ LƯỢNG thực thể. Hai chuyện
khác nhau. Quy tắc (1) lo phần chung chung, quy tắc (8) nói về số lượng.
"""

import json
from string import Template
from typing import List

from kag.interface import PromptABC
from knext.reasoner.client import ReasonerClient


TEMPLATE = """
{
    "instruction": "Bạn là chuyên gia trích xuất thực thể từ câu hỏi pháp luật Việt Nam về an ninh mạng, dữ liệu cá nhân, báo chí và truyền thông. Trường input là MỘT CÂU HỎI, không phải văn bản luật. Nhiệm vụ: rút ra những cái tên cụ thể trong câu hỏi để tra cứu trên đồ thị tri thức. Mỗi thực thể trả về 2 trường: name và category. Quy tắc: (1) Chỉ lấy tên riêng, số hiệu, thuật ngữ và con số ĐỊNH DANH được, tuyệt đối không lấy từ chung chung như 'quy định', 'hành vi', 'trường hợp', 'đối tượng', 'cơ quan'. (2) Tên văn bản phải giữ nguyên số hiệu nếu câu hỏi có nêu, ví dụ 'Nghị định 330/2026/NĐ-CP', 'Luật 116/2025/QH15'; nếu câu hỏi chỉ nói 'Nghị định' hoặc 'Luật' mà không có số hiệu thì BỎ QUA, không đoán số hiệu. (3) Số điều viết dạng 'Điều 34' nếu câu hỏi có nêu số điều cụ thể. (4) Thuật ngữ được luật định nghĩa như 'dữ liệu cá nhân nhạy cảm', 'hệ thống trí tuệ nhân tạo có rủi ro cao', 'xử lý dữ liệu cá nhân', 'chuyển dữ liệu cá nhân ra nước ngoài' là thực thể, giữ đúng cụm từ trong câu hỏi. (5) Cơ quan cụ thể như 'Bộ Công an', 'Bộ Thông tin và Truyền thông' là thực thể; 'cơ quan nhà nước' thì không. (6) Loại chủ thể cụ thể như 'doanh nghiệp', 'cá nhân', 'trẻ em' là thực thể; 'tổ chức, cá nhân' chung chung thì không. (7) category BẮT BUỘC chọn đúng một tên trong danh sách schema bên dưới, không được bịa tên mới. Ưu tiên Article cho số điều, LegalDocument cho tên văn bản, LegalTerm cho thuật ngữ và chủ thể, Authority cho cơ quan. (8) Hãy trích CÀNG NHIỀU càng tốt: liệt kê mọi tên, thuật ngữ, số hiệu, con số và chủ thể định danh được có trong câu hỏi, kể cả tên gọi ở dạng ngắn hay cách diễn đạt khác nhau của cùng một thứ, vì mỗi thực thể là một điểm xuất phát riêng khi tra đồ thị và nhiều điểm xuất phát thì tìm được nhiều đoạn luật liên quan hơn. Đừng tự giới hạn số lượng, chỉ bỏ những từ thật sự chung chung theo quy tắc (1). (9) Câu hỏi không có tên cụ thể nào thì trả về danh sách rỗng, KHÔNG bịa ra thực thể cho đủ. Chỉ trả về một chuỗi JSON, không giải thích thêm.",
    "schema": $schema,
    "example": [
        {
            "input": "Trước khi đưa vào sử dụng, hệ thống trí tuệ nhân tạo có rủi ro cao bắt buộc phải qua thủ tục gì?",
            "output": [
                {"name": "hệ thống trí tuệ nhân tạo có rủi ro cao", "category": "LegalTerm"},
                {"name": "trí tuệ nhân tạo", "category": "LegalTerm"},
                {"name": "hệ thống trí tuệ nhân tạo", "category": "LegalTerm"},
                {"name": "đánh giá sự phù hợp", "category": "LegalTerm"}
            ]
        },
        {
            "input": "Một công ty mua bán trái phép dữ liệu cá nhân nhạy cảm của 300 người thì bị xử phạt bao nhiêu?",
            "output": [
                {"name": "dữ liệu cá nhân nhạy cảm", "category": "LegalTerm"},
                {"name": "mua bán dữ liệu cá nhân", "category": "LegalTerm"},
                {"name": "doanh nghiệp", "category": "RegulatedEntity"}
            ]
        },
        {
            "input": "Theo Nghị định 330/2026/NĐ-CP thì Điều 34 quy định mức phạt nào?",
            "output": [
                {"name": "Điều 34", "category": "Article"},
                {"name": "Nghị định 330/2026/NĐ-CP", "category": "LegalDocument"}
            ]
        },
        {
            "input": "Cơ quan nào có thẩm quyền xử phạt vi phạm về an ninh mạng?",
            "output": []
        }
    ],
    "input": "$input"
}
"""


# TAT: ten dang ky co _tat o cuoi de biz_scene=legal KHONG tim thay no, va
# init_prompt_with_fallback roi ve default_question_ner (tieng Anh).
#
# Ly do, do bang so chu khong phai cam tinh: chay 5 cau ba lan (xem README muc 11)
# cho thay ban tieng Anh XEP HANG TOT HON -
#     hit@1  0.600 (Anh) vs 0.200 (Viet)
#     hit@3  0.800 (Anh) vs 0.600 (Viet)
#     MRR    0.711 (Anh) vs 0.461 (Viet)
# trong khi hit@20 = 1.000 o ca hai, tuc chunk dung khong he mat, chi tut hang.
# Ban Viet lai trich dan chinh xac hon (precision 0.686 vs 0.581), nhung hit@k va
# MRR moi la chi so chinh cua buoc truy hoi, nen chon ban Anh.
#
# CANH BAO: 5 cau la mau QUA NHO de ket luan vung (chenh hit@1 chi la 2 cau).
# Neu sau nay chay 40-50 cau ma ban Viet thang thi doi ten dang ky ve
# "legal_question_ner" la xong, khong phai viet lai gi. Code van con nguyen o day
# vi ly do do - dung xoa file nay.
@PromptABC.register("legal_question_ner_tat")
class LegalQuestionNERPrompt(PromptABC):
    template_en = TEMPLATE
    template_zh = TEMPLATE

    def __init__(self, language: str = "", **kwargs):
        super().__init__(language, **kwargs)
        # Giong default_question_ner: lay schema tu ReasonerClient chu khong phai
        # SchemaClient.load(). Xem ghi chu dau file, muc 3.
        #
        # get_reason_schema() tra ve ten CO TIEN TO namespace, vi du
        # 'Legal.Article'. Phai bo tien to truoc khi dua vao template, vi:
        #   - category LLM tra ve khong dung de tra cuu. ppr_chunk_retriever.py
        #     :227-244 tim node bang vector tren entity_name, roi :242 ghi de
        #     type bang nhan that doc tu __labels__ cua Neo4j.
        #   - Ner.invoke (ner.py:134) so category.lower() voi "works"/"person"/
        #     "other"; de nguyen tien to thi phep so truot.
        # Dem tien to ra cung lam schema de doc hon voi LLM.
        self.schema = []
        for ten in ReasonerClient(
            project_id=self.kag_project_config.project_id,
            host_addr=self.kag_project_config.host_addr,
            namespace=self.kag_project_config.namespace,
        ).get_reason_schema().keys():
            # 'Legal.Article' -> 'Article'; ten khong co dau cham thi giu nguyen
            if "." in ten:
                ten = ten.split(".", 1)[1]
            self.schema.append(ten)

        # ensure_ascii=False de ten kieu tieng Viet khong bi doi thanh \uXXXX;
        # safe_substitute vi template con nhieu dau $ khac khong truyen vao.
        self.template = Template(self.template).safe_substitute(
            schema=json.dumps(self.schema, ensure_ascii=False)
        )

    @property
    def template_variables(self) -> List[str]:
        return ["input"]

    def parse_response(self, response: str, **kwargs):
        """Giu nguyen logic cua default_question_ner, chi them mot lop chan.

        LLM doi khi tra ve mot object don thay vi list, hoac list chua phan tu
        khong phai dict. Ner.invoke goi item.get(...) nen phan tu khong phai dict
        se no AttributeError; loc ngay o day de loi khong roi vao retry cua
        named_entity_recognition (ner.py:40, thu lai 3 lan roi moi nem).
        """
        rsp = response
        if isinstance(rsp, str):
            rsp = json.loads(rsp)
        if isinstance(rsp, dict) and "output" in rsp:
            rsp = rsp["output"]
        if isinstance(rsp, dict) and "named_entities" in rsp:
            entities = rsp["named_entities"]
        else:
            entities = rsp

        if isinstance(entities, dict):
            entities = [entities]
        if not isinstance(entities, list):
            return []

        ket_qua = []
        for e in entities:
            if not isinstance(e, dict):
                continue
            name = e.get("name")
            if not name or not isinstance(name, str):
                continue
            # category la khoa bat buoc voi Ner.invoke; thieu thi gan Others chu
            # khong bo di, vi bo di la mat luon diem xuat phat PageRank.
            ket_qua.append({"name": name, "category": e.get("category") or "Others"})
        return ket_qua
