"""Write B2.5 audit records for Q041-Q050 (batch 5). Q045 blocked on 367/QD-TTg source."""
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

BLOCK_367 = ("Chua co van ban chinh thuc de doi chieu: Quyet dinh 367/QD-TTg "
             "(28/02/2026) da dinh vi duoc tren vanban.chinhphu.vn nhung ban dinh kem "
             "signed PDF la ban scan khong co text layer; may khong co OCR "
             "(tesseract/gs/pdftoppm deu khong co). CAN: OCR hoac tai ban .doc/.docx "
             "chinh thuc.")

R = [
    make("Q041", "OFFICIAL_VERIFIED", ["333/2026/NĐ-CP"], OK_NOP,
         "D16 Nghi dinh 333/2026/ND-CP khop nguyen van 4 marker (30 ngay/03 lan -> toi "
         "da 60 ngay; 90 ngay/10 lan -> toi da 180 ngay).",
         location={"article": "16", "clause": None, "point": None}),
    make("Q042", "OFFICIAL_VERIFIED", ["134/2025/QH15"], OK,
         "D14.1 (article + cac diem a-den-g) khop nguyen van 7 marker.",
         location={"article": "14", "clause": "1", "point": "a-g"}),
    make("Q043", "OFFICIAL_VERIFIED", ["134/2025/QH15"], OK_NOP,
         "D11 khoan 1 (nhan biet dang tuong tac), khoan 2 (danh dau dinh dang may doc), "
         "khoan 4 (gan nhan de nhan biet) khop nguyen van 3 marker.",
         location={"article": "11", "clause": "1, 2, 4", "point": None}),
    make("Q044", "OFFICIAL_VERIFIED", ["142/2026/NĐ-CP"], OK,
         "D19.1 diem a-den-d (dinh nghia su co nghiem trong) va D19.3 diem a/b (72 gio "
         "voi diem a+d va truong hop khong the kiem soat voi diem c; 05 ngay lam viec cho "
         "cac su co con lai) khop nguyen van 7 marker.",
         location={"article": "19", "clause": "1, 3", "point": "a-d"}),
    make("Q045", "BLOCKER", ["367/QĐ-TTg"], BLK, BLOCK_367, location=None),
    make("Q046", "OFFICIAL_VERIFIED", ["330/2026/NĐ-CP"], OK_NOP,
         "D53.3 va D53.3 diem b khop nguyen van. Kiem so nghiep vu: 300 chu the du lieu "
         "NHAY CAM roi vao khung 'tu 200 den duoi 400' -> 100.000.000 den "
         "300.000.000 dong. Cau hoi neu dung 'khong thu duoc khoan tien nao' khop "
         "khoan 3. Marker 'Dieu 53' dung.",
         location={"article": "53", "clause": "3", "point": "b"}),
    make("Q047", "OFFICIAL_VERIFIED", ["91/2025/QH15"], OK_NOP,
         "D8.3 (10 lan khoan thu), D8.5 (toi da 03 ty dong), D8.6 (ca nhan bang mot phan "
         "hai muc phat cua to chuc) khop nguyen van 3 marker.",
         location={"article": "8", "clause": "3, 5, 6", "point": None}),
    make("Q048", "OFFICIAL_VERIFIED", ["91/2025/QH15"], OK_NOP,
         "D8.4 (5% doanh thu nam truoc lien ke; neu khong co doanh thu hoac thap hon thi "
         "ap dung khoan 5 = 03 ty dong) khop nguyen van 3 marker.",
         location={"article": "8", "clause": "4, 5", "point": None}),
    make("Q049", "OFFICIAL_VERIFIED", ["330/2026/NĐ-CP"], OK,
         "D34.2 (khung 30.000.000 - 50.000.000 dong) va D34.2 diem c (AI/Deepfake gia mao "
         "du lieu sinh trac hoc) khop nguyen van 3 marker.",
         location={"article": "34", "clause": "2", "point": "c"}),
    make("Q050", "OFFICIAL_VERIFIED", ["330/2026/NĐ-CP"], OK,
         "D53.3 (dan nhap) va D53.3 diem d (500.000.000 - 1.000.000.000 dong voi du lieu "
         "co ban tu 10.000 chu the tro len) khop nguyen van 3 marker.",
         location={"article": "53", "clause": "3", "point": "d"}),
]

if __name__ == "__main__":
    a, u, n = upsert(R)
    print(f"batch5 written: added={a} updated={u} total_records={n}")
