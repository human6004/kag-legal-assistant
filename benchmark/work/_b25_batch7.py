"""Write B2.5 audit records for Q061-Q070 (batch 7). Q067 blocked on 86/2015 source."""
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
    make("Q061", "OFFICIAL_VERIFIED", ["330/2026/NĐ-CP"], OK,
         "D56.3 (dan nhap ve chuyen du lieu xuyen bien gioi, phat theo % doanh thu) va "
         "D56.3 diem a (1%-2% voi 10.000 den duoi 100.000 chu the la cong dan Viet Nam) "
         "khop nguyen van 3 marker.",
         location={"article": "56", "clause": "3", "point": "a"}),
    make("Q062", "OFFICIAL_VERIFIED", ["330/2026/NĐ-CP"], OK_NOP,
         "D60.3 dung nguyen van: 100.000.000 - 200.000.000 dong, 'khong the khoi phuc', "
         "du lieu ca nhan cua tre em, gom ca truong hop cha me/nguoi giam ho rut lai "
         "dong y. Khop 3 marker.",
         location={"article": "60", "clause": "3", "point": None}),
    make("Q063", "OFFICIAL_VERIFIED", ["341/2026/NĐ-CP"], OK_NOP,
         "D9.2 dung nguyen van: Giay phep xuat khau, nhap khau san pham mat ma dan su co "
         "thoi han 03 nam.",
         location={"article": "9", "clause": "2", "point": None}),
    make("Q064", "OFFICIAL_VERIFIED", ["331/2026/NĐ-CP"], OK,
         "D23.3 diem b dung nguyen van: 25 ngay lam viec cho cap do 4 hoac cap do 5 "
         "(diem a la 15 ngay cho cap do 3 - khong bi lan). Khop 3 marker.",
         location={"article": "23", "clause": "3", "point": "b"}),
    make("Q065", "OFFICIAL_VERIFIED", ["333/2026/NĐ-CP"], OK,
         "D24.8 diem b dung nguyen van: 36 thang ke tu ngay Nghi dinh co hieu luc thi "
         "hanh (diem a la 24 thang cho doi tuong khac - khong bi lan). Khop 4 marker.",
         location={"article": "24", "clause": "8", "point": "b"}),
    make("Q066", "OFFICIAL_VERIFIED", ["142/2026/NĐ-CP"], OK_NOP,
         "D26.3 dung nguyen van: ho tro toi da khong vuot qua 50% tong chi phi hop le "
         "thuc te phat sinh.",
         location={"article": "26", "clause": "3", "point": None}),
    make("Q067", "BLOCKER", ["86/2015/QH13"], BLK, BLOCK_86, location=None),
    make("Q068", "OFFICIAL_VERIFIED", ["13/2023/NĐ-CP"], OK_NOP,
         "D43.2 dung nguyen van: mien tru quy dinh chi dinh ca nhan va bo phan bao ve du "
         "lieu ca nhan trong thoi gian 02 nam dau ke tu khi thanh lap doanh nghiep. "
         "Khop 4 marker.",
         location={"article": "43", "clause": "2", "point": None}),
    make("Q069", "OFFICIAL_VERIFIED", ["53/2022/NĐ-CP"], OK_NOP,
         "D5.6 dung nguyen van: thoi gian khao sat, kiem tra thuc te khong qua 20 ngay. "
         "Khop 3 marker.",
         location={"article": "5", "clause": "6", "point": None}),
    make("Q070", "OFFICIAL_VERIFIED", ["356/2025/NĐ-CP"], OK_NOP,
         "D5.4 dung nguyen van: phan hoi trong 02 ngay lam viec; thuc hien trong 20 ngay; "
         "truong hop can ben xu ly/ben thu ba thi 30 ngay. Khop 4 marker (ca 3 moc thoi "
         "gian nam trong cung khoan 4).",
         location={"article": "5", "clause": "4", "point": None}),
]

if __name__ == "__main__":
    a, u, n = upsert(R)
    print(f"batch7 written: added={a} updated={u} total_records={n}")
