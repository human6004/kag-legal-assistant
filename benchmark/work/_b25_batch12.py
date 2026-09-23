"""Write B2.5 audit records for Q110-Q120 (batch 12).

Q110 blocked (35/2018/QH14 source). All others are multi_hop with legs verified.
"""
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

BLOCK_35 = ("Chua co van ban chinh thuc de doi chieu: Cong bao Luat 35/2018/QH14 (2018) "
            "khong con tren congbao.chinhphu.vn; vanban.chinhphu.vn khong index luat "
            "Quoc hoi; vbpl.vn la SPA chan truy cap tu dong; corpus markdown bi mojibake. "
            "CAN: tai ban chinh thuc bang trinh duyet.")

R = [
    make("Q110", "BLOCKER", ["35/2018/QH14"], BLK, BLOCK_35, location=None),
    make("Q111", "OFFICIAL_VERIFIED", ["134/2025/QH15"], OK,
         "MULTI-HOP 2 leg, ca 2 da verify doc lap: (A) D13.1 - he thong AI rui ro cao phai "
         "duoc danh gia su phu hop truoc khi dua vao su dung; (B) D10.3 - nha cung cap "
         "phai thong bao ket qua phan loai cho Bo Khoa hoc va Cong nghe qua Cong thong tin "
         "dien tu mot cua. Cau hoi thuc su can A+B (thu tuc + co quan nhan thong bao).",
         location={"article": "13, 10", "clause": "1, 3", "point": None}),
    make("Q112", "OFFICIAL_VERIFIED", ["330/2026/NĐ-CP"], OK,
         "MULTI-HOP 3 leg: (A) D11.3 khung 20-30 trieu; (B) D7.1 to chuc vi pham cung hanh "
         "vi phat bang hai lan muc phat cua ca nhan; (C) D11.5 diem b dinh chi hoat dong "
         "01-03 thang voi doanh nghiep vi pham khoan 3. Cau hoi can ca 3 leg - da verify du.",
         location={"article": "11, 7", "clause": "3, 5", "point": "b"}),
    make("Q113", "OFFICIAL_VERIFIED", ["24/2018/QH14"], OK,
         "MULTI-HOP 2 leg: (A) D8.5 hanh vi bi nghiem cam (loi dung hoac lam dung hoat "
         "dong bao ve an ninh mang ... hoac de truc loi); (B) D9 che tai xu ly (ky luat, "
         "xu ly vi pham hanh chinh hoac truy cuu TNHS; neu gay thiet hai thi phai boi "
         "thuong). Ca 2 leg deu khop nguyen van.",
         location={"article": "8, 9", "clause": "5", "point": None}),
    make("Q114", "OFFICIAL_VERIFIED", ["24/2018/QH14"], OK,
         "MULTI-HOP 2 leg: (A) D41.1 diem a/b (canh bao kha nang mat an ninh mang; xay "
         "dung phuong an phan ung nhanh) tai Dieu 41; (B) D26.3 (doanh nghiep ngoai nuoc "
         "phai dat chi nhanh hoac van phong dai dien tai Viet Nam). Ca 2 leg verify du.",
         location={"article": "41, 26", "clause": "1, 3", "point": "a, b"}),
    make("Q115", "OFFICIAL_VERIFIED", ["91/2025/QH15"], OK_NOP,
         "MULTI-HOP 2 leg: (A) D23.1 - thong bao cho co quan chuyen trach cham nhat 72 gio "
         "ke tu khi phat hien; (B) D21.1 - gui ho so danh gia tac dong trong 60 ngay ke tu "
         "ngay dau tien xu ly. Ca 2 leg khop nguyen van.",
         location={"article": "23, 21", "clause": "1", "point": None}),
    make("Q116", "OFFICIAL_VERIFIED", ["13/2023/NĐ-CP"], OK,
         "MULTI-HOP 2 leg: (A) D9.6 diem b - han che xu ly trong 72 gio; (B) D16.5 - xoa "
         "du lieu trong 72 gio. Ca 2 leg khop nguyen van.",
         location={"article": "9, 16", "clause": "6, 5", "point": "b"}),
    make("Q117", "OFFICIAL_VERIFIED", ["13/2023/NĐ-CP"], OK,
         "MULTI-HOP 2 leg: (A) D2.6 dinh nghia chu the du lieu; (B) D9 khoan 1-11 liet ke "
         "11 nhom quyen. 16 evidence item bao phu day du 12 marker.",
         location={"article": "2, 9", "clause": "6, 1-11", "point": None}),
    make("Q118", "OFFICIAL_VERIFIED", ["91/2025/QH15"], OK,
         "MULTI-HOP 2 leg: (A) D20.6 (dan nhap + diem a/b/c/d - cac truong hop khong phai "
         "danh gia tac dong); (B) D8.1 (che tai xu ly vi pham). Ca 2 leg khop nguyen van "
         "7 marker.",
         location={"article": "20, 8", "clause": "6, 1", "point": "a-d"}),
    make("Q119", "OFFICIAL_VERIFIED", ["13/2023/NĐ-CP"], OK_NOP,
         "MULTI-HOP 2 leg: (A) D9 'Quyen cua chu the du lieu'; (B) D22 'Thu thap, chuyen "
         "giao, mua, ban trai phep du lieu ca nhan'. Ca 2 tieu de Dieu khop nguyen van "
         "2 marker.",
         location={"article": "9, 22", "clause": None, "point": None}),
    make("Q120", "OFFICIAL_VERIFIED", ["53/2022/NĐ-CP"], OK_NOP,
         "MULTI-HOP 2 leg: (A) D26 'Luu tru du lieu, dat chi nhanh hoac van phong dai dien "
         "tai Viet Nam'; (B) D27.1 thoi gian luu tru toi thieu 24 thang. Ca 2 leg khop "
         "nguyen van 3 marker.",
         location={"article": "26, 27", "clause": "1", "point": None}),
]

if __name__ == "__main__":
    a, u, n = upsert(R)
    print(f"batch12 written: added={a} updated={u} total_records={n}")
