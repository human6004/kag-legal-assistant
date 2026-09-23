"""Write B2.5 audit records for Q031-Q040 (batch 4). Q032 blocked on 86/2015 source."""
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

BLOCK_NOTE = ("Chua co van ban chinh thuc de doi chieu: Cong bao 86/2015/QH13 khong con "
              "tren congbao.chinhphu.vn; vanban.chinhphu.vn khong index luat Quoc hoi; "
              "vbpl.vn la SPA chan truy cap tu dong; corpus markdown bi mojibake. "
              "CAN: tai ban chinh thuc bang trinh duyet.")

R = [
    make("Q031", "OFFICIAL_VERIFIED", ["91/2025/QH15"], OK_NOP,
         "D7.5 Luat 91/2025/QH15 dung nguyen van, tra loi dung CAU HOI CO/KHONG.",
         location={"article": "7", "clause": "5", "point": None}),
    make("Q032", "BLOCKER", ["86/2015/QH13"], BLK, BLOCK_NOTE,
         location=None),
    make("Q033", "OFFICIAL_VERIFIED", ["328/2026/NĐ-CP"], OK,
         "D10.1 (trach nhiem gan nhan) va D10.4 diem a (thoi han 24 gio) khop nguyen van "
         "2 marker.",
         location={"article": "10", "clause": "1, 4", "point": "a"}),
    make("Q034", "OFFICIAL_VERIFIED", ["328/2026/NĐ-CP"], OK,
         "D22.2 diem d dung nguyen van, gom 'dau moi phoi hop 24/7' va 'khoa tam thoi "
         "hoac vinh vien cac tai khoan mang xa hoi' khop ca 2 marker.",
         location={"article": "22", "clause": "2", "point": "đ"}),
    make("Q035", "OFFICIAL_VERIFIED", ["329/2026/NĐ-CP"], OK,
         "D7.5 diem c (khong loi dung) va diem d (chiu trach nhiem truoc phap luat) khop "
         "nguyen van 2 marker.",
         location={"article": "7", "clause": "5", "point": "c, d"}),
    make("Q036", "OFFICIAL_VERIFIED", ["356/2025/NĐ-CP"], OK,
         "D29.1 diem a (72 gio) va diem c (luu ho so toi thieu 5 nam) khop nguyen van "
         "2 marker.",
         location={"article": "29", "clause": "1", "point": "a, c"}),
    make("Q037", "OFFICIAL_VERIFIED", ["356/2025/NĐ-CP"], OK,
         "D19.2 (article + diem a/b/c) va D19.4 (60 ngay) va D19.5 (15 ngay) deu khop "
         "nguyen van. Marker 'trong thoi han 15 ngay' thuoc khoan 5, khong phai khoan 4; "
         "evidence da tach dung 2 khoan nen khong co mismatch.",
         location={"article": "19", "clause": "2, 4, 5", "point": "a-c"}),
    make("Q038", "OFFICIAL_VERIFIED", ["331/2026/NĐ-CP"], OK_NOP,
         "D31 Nghi dinh 331/2026/ND-CP khop nguyen van ca 2 marker (72 gio bao cao su co; "
         "24 gio thong bao ban dau voi su co nghiem trong). Day la Dieu quy dinh che do "
         "bao cao dang bang liet ke, khong chia khoan.",
         location={"article": "31", "clause": None, "point": None}),
    make("Q039", "OFFICIAL_VERIFIED", ["341/2026/NĐ-CP"], OK,
         "D8.2 (article + cac diem a-den-e) khop nguyen van 6 marker.",
         location={"article": "8", "clause": "2", "point": "a-e"}),
    make("Q040", "OFFICIAL_VERIFIED", ["332/2026/NĐ-CP"], OK_NOP,
         "D8.2 dung nguyen van: it nhat 12 nguoi co trinh do dai hoc hoac chung chi an "
         "ninh mang; nguoi dai dien theo phap luat phai co quoc tich Viet Nam.",
         location={"article": "8", "clause": "2", "point": None}),
]

if __name__ == "__main__":
    a, u, n = upsert(R)
    print(f"batch4 written: added={a} updated={u} total_records={n}")
