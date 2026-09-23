"""Write B2.5 audit records for Q011-Q020 (batch 2)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _b25_audit import make, upsert  # noqa: E402

OK = dict(document=True, article=True, clause=True, point=True,
          evidence=True, question_supported=True, markers_supported=True)
OK_NOP = dict(document=True, article=True, clause=True, point=None,
              evidence=True, question_supported=True, markers_supported=True)

R = [
    make("Q011", "OFFICIAL_VERIFIED", ["329/2026/NĐ-CP"], OK_NOP,
         "D4.1 Nghi dinh 329/2026/ND-CP dung nguyen van, liet ke dung 3 luc luong "
         "(chuyen trach, thuong truc, du bi) khop ca 2 marker.",
         location={"article": "4", "clause": "1", "point": None}),
    make("Q012", "OFFICIAL_VERIFIED", ["341/2026/NĐ-CP"], OK_NOP,
         "D3.1 Nghi dinh 341/2026/ND-CP dung nguyen van. Luu y: cau hoi neu chung "
         "'nghi dinh ve hoat dong mat ma dan su' - dung la 341/2026/ND-CP.",
         location={"article": "3", "clause": "1", "point": None}),
    make("Q013", "OFFICIAL_VERIFIED", ["332/2026/NĐ-CP"], OK,
         "D3.2 (san pham giam sat an ninh mang) va D3.4 diem d (san pham che giau dia chi "
         "IP) deu khop nguyen van Cong bao 332/2026/ND-CP.",
         location={"article": "3", "clause": "2, 4", "point": "đ"}),
    make("Q014", "OFFICIAL_VERIFIED", ["134/2025/QH15"], OK_NOP,
         "D3.1 (tri tue nhan tao) va D3.2 (he thong tri tue nhan tao) khop nguyen van; "
         "4 marker deu nam trong hai khoan nay.",
         location={"article": "3", "clause": "1, 2", "point": None}),
    make("Q015", "OFFICIAL_VERIFIED", ["134/2025/QH15"], OK,
         "D9 gom khoan 1 diem a/b/c (rui ro cao, trung binh, thap) va khoan 2 (tieu chi). "
         "Marker 'Dieu 9' dung. Ca 7 marker khop nguyen van.",
         location={"article": "9", "clause": "1, 2", "point": "a-c"}),
    make("Q016", "OFFICIAL_VERIFIED", ["134/2025/QH15"], OK_NOP,
         "D3 khoan 3/4/5 dinh nghia nha phat trien, nha cung cap, ben trien khai - khop "
         "nguyen van. Marker 3 ('duoi ten, thuong hieu hoac nhan hieu cua minh') thuoc "
         "khoan 4; marker 4 ('khong bao gom truong hop su dung cho muc dich ca nhan, phi "
         "thuong mai') thuoc khoan 5. Tat ca deu duoc nguon chinh thuc ho tro.",
         location={"article": "3", "clause": "3, 4, 5", "point": None}),
    make("Q017", "OFFICIAL_VERIFIED", ["05/2026/TT-BKHCN"], OK_NOP,
         "D2 khoan 1/2/3 Thong tu 05/2026/TT-BKHCN khop nguyen van ca 3 dinh nghia.",
         location={"article": "2", "clause": "1, 2, 3", "point": None}),
    make("Q018", "OFFICIAL_VERIFIED", ["05/2026/TT-BKHCN"], OK_NOP,
         "D3 khoan 1/2/3/4 la 4 nguyen tac dao duc, khop nguyen van 4 marker.",
         location={"article": "3", "clause": "1, 2, 3, 4", "point": None}),
    make("Q019", "OFFICIAL_VERIFIED", ["05/2026/TT-BKHCN"], OK,
         "D3.1 diem a (thiet ke an toan ngay tu dau) va diem c (kiem soat cua con nguoi) "
         "khop nguyen van ca 4 marker.",
         location={"article": "3", "clause": "1", "point": "a, c"}),
    make("Q020", "OFFICIAL_VERIFIED", ["1528/QĐ-TTg"], OK,
         "D1.2 (03 tang nhan luc: pho cap, ung dung, chuyen sau) va D1.1 diem a (Khung "
         "nang luc AI quoc gia) khop nguyen van 6 marker.",
         location={"article": "1", "clause": "1, 2", "point": "a"}),
]

if __name__ == "__main__":
    a, u, n = upsert(R)
    print(f"batch2 written: added={a} updated={u} total_records={n}")
