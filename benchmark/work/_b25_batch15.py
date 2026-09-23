"""Write B2.5 audit records for Q136-Q150 (the 15 unanswerable items, batch 15).

For each item we verify:
  (1) the nearest in-corpus provision (premise) genuinely exists and is quoted;
  (2) whether an official document OUTSIDE the 23-doc corpus answers the question.
answerable stays false regardless: the benchmark is fixed to the 23-doc corpus.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _b25_audit import make, upsert  # noqa: E402

# For unanswerable items: no official_sources (no provision answers them), checks null.
NA = dict(document=None, article=None, clause=None, point=None,
          evidence=None, question_supported=None, markers_supported=None)

# outside_corpus_answer_exists values, reasoned per item.
FALSE = False
TRUE_ = True
UNK = None


def na(qid, docs, outside, notes):
    return make(qid, "OFFICIAL_VERIFIED", docs, NA, notes,
                location=None, outside=outside)


R = [
    na("Q136", [], TRUE_,
       "CORPUS-UNANSWERABLE dung nghia (khong phai 'phap luat VN khong co dap an'). "
       "PREMISE verified: Luat 134/2025/QH15 D13.2 diem a giao danh muc he thong AI phai "
       "chung nhan su phu hop truoc khi dua vao su dung; ND 142/2026/ND-CP D1.1 liet ke "
       "Dieu 9/Dieu 13 nhu noi dung duoc quy dinh chi tiet, va D7/D8 chi mo ta tieu chi + "
       "quy trinh de xuat. Da doi chieu Cong bao 134/2025/QH15 va 142/2026/ND-CP: KHONG "
       "co ban than danh muc. outside_corpus_answer_exists=true: danh muc nay do Thut "
       "tuong ban hanh bang quyet dinh rieng (ngoai 23 van ban). => giu answerable=false "
       "vi benchmark co dinh tren corpus 23 van ban.",
       ),
    na("Q137", [], TRUE_,
       "PREMISE verified: Luat 134/2025/QH15 D17.5 'Thu tuong Chinh phu ban hanh Danh muc "
       "bo du lieu phuc vu phat trien tri tue nhan tao trong cac linh vuc thiet yeu, trong "
       "do uu tien du lieu van hoa, ngon ngu tieng Viet...' - chi neu linh vuc uu tien, "
       "khong liet ke ten bo du lieu. ND 142 cung chi giao Bo KHCN trinh danh muc. "
       "outside_corpus_answer_exists=true (quyet dinh cua Thu tuong ban hanh danh muc la "
       "van ban rieng, khong nam trong 23 van ban).",
       ),
    na("Q138", [], TRUE_,
       "PREMISE verified: Luat 134/2025/QH15 D16 quy dinh ve ha tang AI quoc gia; nghia vu "
       "trien khai tren ha tang quoc gia gan voi 'danh muc ung dung AI quan trong trong "
       "cac linh vuc thiet yeu' chua duoc ban hanh trong corpus. Da doi chieu Cong bao "
       "134/2025/QH15: khong co danh muc kem theo. "
       "outside_corpus_answer_exists=true (danh muc do Thu tuong ban hanh rieng).",
       ),
    na("Q139", [], TRUE_,
       "PREMISE verified: Luat 134/2025/QH15 D22 'Quy Phat trien tri tue nhan tao quoc "
       "gia' - khoan 1 noi Chinh phu thanh lap, khoan 5 giao Chinh phu quy dinh to chuc, "
       "quan ly, su dung va giam sat quy. Da doi chieu Cong bao: khong neu co quan quan ly "
       "cu the hay co che giam sat. outside_corpus_answer_exists=true (nghi dinh cua Chinh "
       "phu ve to chuc va giam sat quy).",
       ),
    na("Q140", [], TRUE_,
       "PREMISE verified: Luat 134/2025/QH15 D29.5 giao Chinh phu quy dinh xu phat hanh vi "
       "vi pham do he thong AI gay ra, KHONG kem khung tien. ND 330/2026/ND-CP D67 chi xu "
       "phat mot so hanh vi bao ve du lieu ca nhan khi dung AI, khong phai khung phat theo "
       "D29.5. outside_corpus_answer_exists=true (nghi dinh xu phat VPHC thi hanh Luat Tri "
       "tue nhan tao chua co trong corpus).",
       ),
    na("Q141", [], TRUE_,
       "PREMISE verified: Luat 71/2025/QH15 D19 quy dinh uu dai dac biet voi nhan luc cong "
       "nghiep cong nghe so chat luong cao nhung tieu chi cu the giao Chinh phu quy dinh; "
       "D20 dan chieu tieu chi nhan tai sang linh vuc khoa hoc cong nghe. Da doi chieu "
       "Cong bao 71/2025/QH15: khong co ban tieu chi. "
       "outside_corpus_answer_exists=true (nghi dinh quy dinh tieu chi).",
       ),
    na("Q142", [], TRUE_,
       "PREMISE verified: Luat 71/2025/QH15 D48 khoan 1 diem d va khoan 2 giao Chinh phu "
       "quy dinh tham quyen va noi dung quan ly ve dieu kien kinh doanh dich vu tai san ma "
       "hoa; D3 chi dinh nghia 'tai san ma hoa'. Khong co dieu kien, ho so hay co quan cap "
       "phep trong corpus. outside_corpus_answer_exists=true (nghi dinh ve kinh doanh dich "
       "vu tai san ma hoa).",
       ),
    na("Q143", [], TRUE_,
       "PREMISE verified: Luat 71/2025/QH15 D23.1 diem b neu tieu chi 'quy mo dien tich' "
       "nhung khong co con so; khoan 3 giao Chinh phu quy dinh chi tiet khoan 1 va trinh "
       "tu, thu tuc; D3.6 dinh nghia khu cong nghe so tap trung. Da doi chieu Cong bao: "
       "khong co nguong dien tich hay danh muc giay to. outside_corpus_answer_exists=true "
       "(nghi dinh quy dinh chi tiet Dieu 23).",
       ),
    na("Q144", [], TRUE_,
       "PREMISE verified: Luat 116/2025/QH15 D25.2 diem d yeu cau luu ten tai khoan, thoi "
       "gian su dung dich vu, thong tin thanh toan, dia chi IP 'trong thoi gian theo quy "
       "dinh cua phap luat' sau khi nguoi dung ket thuc su dung dich vu, va khoan 4 giao "
       "Chinh phu quy dinh chi tiet - KHONG co so. ND 53/2022/ND-CP D26/D27 co 24 thang va "
       "12 thang nhung dong ho la 'tu khi nhan duoc yeu cau luu tru' va nhat ky dieu tra, "
       "khac nghia. outside_corpus_answer_exists=true (van ban an dinh thoi han do).",
       ),
    na("Q145", [], TRUE_,
       "PREMISE verified: Luat 116/2025/QH15 D27.5 'Bo truong Bo Cong an ban hanh quy chuan "
       "ky thuat quoc gia ve an ninh mang' - giao ban hanh nhung khong kem so hieu QCVN "
       "hay bang chi tieu. Da kiem toan bo 23 van ban: khong co chuoi QCVN nao. "
       "outside_corpus_answer_exists=true (Thong tu ban hanh QCVN la van ban rieng).",
       ),
    na("Q146", [], TRUE_,
       "PREMISE verified: ND 333/2026/ND-CP D24.6 giao Bo truong Bo Cong an ban hanh khung "
       "chuong trinh tap huan va chuan kien thuc, ky nang, khong kem thoi luong hay thang "
       "diem; D28.1 diem a chi yeu cau tham du toi thieu 80% thoi luong va diem c noi 'dat "
       "yeu cau' khong co diem so. outside_corpus_answer_exists=true (khung chuong trinh "
       "do Bo Cong an ban hanh rieng).",
       ),
    na("Q147", [], TRUE_,
       "PREMISE verified: Luat 116/2025/QH15 D33.1 noi kien thuc an ninh mang duoc dua vao "
       "mon giao duc quoc phong va an ninh theo quy dinh cua Luat Giao duc quoc phong va an "
       "ninh - dan chieu, khong liet ke bai hoc hay khoi lop. "
       "outside_corpus_answer_exists=true: Luat Giao duc quoc phong va an ninh la van ban "
       "ngoai corpus va quy dinh noi dung mon hoc o tung cap.",
       ),
    na("Q148", [], TRUE_,
       "PREMISE verified: Luat 116/2025/QH15 D22 'Ngan chan xung dot thong tin tren khong "
       "gian mang' khoan 1 dinh nghia xung dot thong tin, khoan 4 giao Chinh phu quy dinh "
       "chi tiet ca dieu - khong neu co quan chu tri hay han bao cao. ND 330 D25 chi dat "
       "muc phat. outside_corpus_answer_exists=true (nghi dinh quy dinh chi tiet Dieu 22).",
       ),
    na("Q149", [], TRUE_,
       "PREMISE verified: Luat 116/2025/QH15 D5.1 diem n neu bien phap 'khoi to, dieu tra, "
       "truy to, xet xu theo quy dinh cua Bo luat To tung hinh su'; khoan 2 xac nhan Chinh "
       "phu khong quy dinh chi tiet diem nay. Ket qua la dan chieu, khong co so thang. "
       "outside_corpus_answer_exists=true: Bo luat To tung hinh su (van ban ngoai corpus) "
       "quy dinh thoi han dieu tra; da xac nhan 3 van ban trong corpus co dan chieu sang "
       "bo luat nay.",
       ),
    na("Q150", [], TRUE_,
       "PREMISE verified: ND 356/2025/ND-CP D34.4 giao Bo Cong an phoi hop xay dung quy "
       "chuan ky thuat ve khu nhan dang - tuc quy chuan CHUA duoc ban hanh trong corpus; "
       "Luat 91/2025/QH15 D2.1 va D14 chi neu dinh nghia, cam tai nhan dang, khong co "
       "phuong phap hay nguong. outside_corpus_answer_exists=true (quy chuan ky thuat khu "
       "nhan dang du lieu ca nhan la van ban rieng, chua ban hanh).",
       ),
]

if __name__ == "__main__":
    a, u, n = upsert(R)
    print(f"batch15 (unanswerable) written: added={a} updated={u} total_records={n}")
