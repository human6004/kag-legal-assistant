"""Write B2.5 audit records for Q051-Q060 (batch 6)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _b25_audit import make, upsert  # noqa: E402

OK = dict(document=True, article=True, clause=True, point=True,
          evidence=True, question_supported=True, markers_supported=True)
OK_NOP = dict(document=True, article=True, clause=True, point=None,
              evidence=True, question_supported=True, markers_supported=True)

R = [
    make("Q051", "OFFICIAL_VERIFIED", ["330/2026/NĐ-CP"], OK,
         "D9.2 (khung 10-20 trieu, dieu kien 'chua den muc truy cuu TNHS') va D9.2 diem a "
         "khop nguyen van 3 marker.",
         location={"article": "9", "clause": "2", "point": "a"}),
    make("Q052", "OFFICIAL_VERIFIED", ["330/2026/NĐ-CP"], OK,
         "D23.1 (khung 20-30 trieu) va D23.1 diem c (dua HTTT vao van hanh khi chua duoc "
         "phe duyet cap do, cap do 3 den 5) khop nguyen van 2 marker.",
         location={"article": "23", "clause": "1", "point": "c"}),
    make("Q053", "OFFICIAL_VERIFIED", ["330/2026/NĐ-CP"], OK,
         "D37.3 (khung 30-50 trieu) va D37.3 diem o (tin nhan quang cao ngoai khoang "
         "07h-22h) khop nguyen van 2 marker.",
         location={"article": "37", "clause": "3", "point": "o"}),
    make("Q054", "OFFICIAL_VERIFIED", ["330/2026/NĐ-CP"], OK,
         "D36.1 (khung 75-100 trieu), D36.1 diem a (nhap khau khong giay phep) va D36.2 "
         "(hinh phat bo sung: tuoc quyen su dung Giay phep 01-03 thang) khop nguyen van "
         "2 marker.",
         location={"article": "36", "clause": "1, 2", "point": "a"}),
    make("Q055", "OFFICIAL_VERIFIED", ["330/2026/NĐ-CP"], OK,
         "D4.2 diem a/b/c/d khop nguyen van 4 marker hinh thuc xu phat bo sung.",
         location={"article": "4", "clause": "2", "point": "a-d"}),
    make("Q056", "OFFICIAL_VERIFIED", ["341/2026/NĐ-CP"], OK,
         "D8.1 (article + cac diem a/b/c, thoi han khong qua 06 thang) khop nguyen van "
         "4 marker.",
         location={"article": "8", "clause": "1", "point": "a-c"}),
    make("Q057", "OFFICIAL_VERIFIED", ["332/2026/NĐ-CP"], OK,
         "D14.2 (article + cac diem a-den-d, thoi han 03-06 thang) khop nguyen van "
         "6 marker.",
         location={"article": "14", "clause": "2", "point": "a-đ"}),
    make("Q058", "OFFICIAL_VERIFIED", ["71/2025/QH15"], OK_NOP,
         "D28.2 Luat 71/2025/QH15 dung nguyen van: phat trien he thong AI va dau tu xay "
         "dung trung tam du lieu AI la nganh, nghe dac biet uu dai dau tu. Marker "
         "'Dieu 28' dung.",
         location={"article": "28", "clause": "2", "point": None}),
    make("Q059", "OFFICIAL_VERIFIED", ["330/2026/NĐ-CP"], OK_NOP,
         "D14.1 dung nguyen van: 5.000.000 - 10.000.000 dong, kem liet ke loai tai khoan.",
         location={"article": "14", "clause": "1", "point": None}),
    make("Q060", "OFFICIAL_VERIFIED", ["330/2026/NĐ-CP"], OK,
         "D48.3 (dan nhap ve bien phap cong nghe, ky thuat) va D48.3 diem a (100-200 "
         "trieu voi du lieu co ban duoi 500 chu the hoac du lieu nhay cam duoi 100 chu "
         "the) khop nguyen van 4 marker.",
         location={"article": "48", "clause": "3", "point": "a"}),
]

if __name__ == "__main__":
    a, u, n = upsert(R)
    print(f"batch6 written: added={a} updated={u} total_records={n}")
