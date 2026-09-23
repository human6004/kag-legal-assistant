"""Write B2.5 audit records for Q131-Q135 (batch 14). Q135 blocked on 367/QD-TTg scan."""
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

BLOCK_367 = ("Chua co van ban chinh thuc co text layer: Quyet dinh 367/QD-TTg "
             "(28/02/2026) dinh vi duoc tren vanban.chinhphu.vn nhung ban dinh kem "
             "signed PDF la ban scan khong co text layer; may khong co OCR. CAN: OCR "
             "hoac ban .doc/.docx chinh thuc.")

R = [
    make("Q131", "OFFICIAL_VERIFIED", ["71/2025/QH15", "134/2025/QH15"], OK,
         "MULTI-HOP 2 van ban: (A) Luat 71/2025/QH15 D12.4 (gia mao, gian doi de huong "
         "chinh sach uu dai) va D12.6 (su dung, cung cap, trien khai he thong AI ... pha "
         "hoai thuan phong my tuc) khop nguyen van; (B) Luat 134/2025/QH15 D33 bai bo "
         "khoan 6 Dieu 12 cua Luat 71. => Khoan cam su dung AI pha hoai thuan phong my "
         "tuc DA bi bai bo; khoan 4 (gia mao, gian doi) VAN con hieu luc vi khong nam "
         "trong danh muc bai bo. Tra loi dung ca 2 ve cua cau hoi. Khop 4 marker.",
         location={"article": "12 (Luật 71), 33 (Luật 134)", "clause": "4, 6", "point": None}),
    make("Q132", "OFFICIAL_VERIFIED", ["71/2025/QH15", "134/2025/QH15"], OK,
         "MULTI-HOP 2 van ban: (A) Luat 71/2025/QH15 D44 khoan 1, 2, 3 diem a khop nguyen "
         "van; (B) Luat 134/2025/QH15 D33 bai bo Chuong IV cua Luat 71. Da kiem truc tiep "
         "tren Cong bao: Chuong IV 'TRI TUE NHAN TAO' bat dau offset 52028, Chuong V tai "
         "57855, Dieu 44 tai 57310 => THUOC Chuong IV nen DA bi bai bo. Khop 6 marker.",
         location={"article": "44 (Luật 71), 33 (Luật 134)", "clause": "1, 2, 3", "point": "a"}),
    make("Q133", "OFFICIAL_VERIFIED", ["71/2025/QH15"], OK_NOP,
         "MULTI-HOP 2 leg trong cung van ban: (A) D50.1 (hieu luc 01/01/2026) va D50.2 "
         "(cac Dieu 11, 28, 29 co hieu luc tu 01/7/2025); (B) D51.1 (khu cong nghe thong "
         "tin tap trung tu dong chuyen thanh khu cong nghe so tap trung). Khop 4 marker.",
         location={"article": "50, 51", "clause": "1, 2", "point": None}),
    make("Q134", "OFFICIAL_VERIFIED", ["05/2026/TT-BKHCN"], OK_NOP,
         "MULTI-HOP 2 leg: (A) D4 - hieu luc ke tu ngay 10/3/2026; (B) D5.1 - ra soat, "
         "cap nhat dinh ky 03 nam mot lan hoac khi co thay doi lon ve cong nghe, phap luat "
         "va thuc tien quan ly. Khop 3 marker.",
         location={"article": "4, 5", "clause": "1", "point": None}),
    make("Q135", "BLOCKER", ["367/QĐ-TTg"], BLK, BLOCK_367, location=None),
]

if __name__ == "__main__":
    a, u, n = upsert(R)
    print(f"batch14 written: added={a} updated={u} total_records={n}")
