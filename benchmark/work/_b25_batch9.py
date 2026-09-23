"""Write B2.5 audit records for Q081-Q090 (batch 9). Q087 blocked on 86/2015 source."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _b25_audit import make, upsert  # noqa: E402

OK = dict(document=True, article=True, clause=True, point=True,
          evidence=True, question_supported=True, markers_supported=True)
OK_NOP = dict(document=True, article=True, clause=True, point=None,
              evidence=True, question_supported=True, markers_supported=True)
BLK = dict(document=None, article=None, clause=None, point=None,
           evidence=None, question_supported=None, markers_supported=None)

BLOCK_86 = ("Chua co van ban chinh thuc de doi chieu: Cong bao 86/2015/QH13 khong con "
            "tren congbao.chinhphu.vn; vanban.chinhphu.vn khong index luat Quoc hoi; "
            "vbpl.vn la SPA chan truy cap tu dong; corpus markdown bi mojibake. "
            "CAN: tai ban chinh thuc bang trinh duyet.")

R = [
    make("Q081", "OFFICIAL_VERIFIED", ["91/2025/QH15"], OK_NOP,
         "D38.1 (hieu luc 01/01/2026) va D38.2 (mien tru 05 nam cho doanh nghiep nho/khoi "
         "nghiep, kem ngoai le) khop nguyen van 3 marker. Nguon Cong bao 91/2025/QH15 co "
         "chen header trang giua cau nhung noi dung phap ly nguyen ven.",
         location={"article": "38", "clause": "1, 2", "point": None}),
    make("Q082", "OFFICIAL_VERIFIED", ["330/2026/NĐ-CP"], OK_NOP,
         "D1.1 dung nguyen van, gom ca 'hanh vi vi pham hanh chinh da ket thuc va hanh vi "
         "vi pham hanh chinh dang thuc hien' khop marker va tra loi dung CAU HOI CO."
         "Khop 3 marker.",
         location={"article": "1", "clause": "1", "point": None}),
    make("Q083", "OFFICIAL_VERIFIED", ["341/2026/NĐ-CP"], OK_NOP,
         "D4.3 dung nguyen van: Giay phep kinh doanh san pham, dich vu mat ma dan su co "
         "thoi han 10 nam.",
         location={"article": "4", "clause": "3", "point": None}),
    make("Q084", "OFFICIAL_VERIFIED", ["333/2026/NĐ-CP"], OK_NOP,
         "D30 dung nguyen van: hieu luc tu ngay 19 thang 8 nam 2026.",
         location={"article": "30", "clause": None, "point": None}),
    make("Q085", "OFFICIAL_VERIFIED", ["142/2026/NĐ-CP"],
         dict(document=True, article=None, clause=None, point=None,
              evidence=True, question_supported=True, markers_supported=True),
         "Cau hoi ve KET CAU van ban (khong phai quy pham cu the), nen evidence khong co "
         "article/clause - da ghi null dung quy uoc, khong gia true. Da doi chieu truc "
         "tiep Cong bao 142/2026/ND-CP: co dung 8 Chuong I-VIII; Chuong VIII ten "
         "'DIEU KHOAN THI HANH'; Phu luc ten 'DANH MUC BIEU MAU'. Khop ca 3 marker. "
         "Checks article/clause/point = null vi not applicable.",
         location={"article": None, "clause": None,
                   "point": "cấu trúc văn bản: Chương I-VIII, Chương VIII, Phụ lục"}),
    make("Q086", "OFFICIAL_VERIFIED", ["53/2022/NĐ-CP"], OK_NOP,
         "D29 dung nguyen van: hieu luc tu ngay 01 thang 10 nam 2022.",
         location={"article": "29", "clause": None, "point": None}),
    make("Q087", "BLOCKER", ["86/2015/QH13"], BLK, BLOCK_86, location=None),
    make("Q088", "OFFICIAL_VERIFIED", ["341/2026/NĐ-CP"], OK_NOP,
         "D17 dung nguyen van: hieu luc ke tu ngay 01 thang 9 nam 2026.",
         location={"article": "17", "clause": None, "point": None}),
    make("Q089", "OFFICIAL_VERIFIED", ["329/2026/NĐ-CP"], OK_NOP,
         "D20.1 dung nguyen van: hieu luc tu ngay 19 thang 8 nam 2026.",
         location={"article": "20", "clause": "1", "point": None}),
    make("Q090", "OFFICIAL_VERIFIED", ["116/2025/QH15"], OK_NOP,
         "D45.2 dung nguyen van: giay phep da cap truoc ngay Luat co hieu luc co gia tri "
         "den het thoi han ghi tren giay phep. Cau hoi mang nghia chuyen tiep nen kiem "
         "dung dieu khoan chuyen tiep. Khop 2 marker.",
         location={"article": "45", "clause": "2", "point": None}),
]

if __name__ == "__main__":
    a, u, n = upsert(R)
    print(f"batch9 written: added={a} updated={u} total_records={n}")
