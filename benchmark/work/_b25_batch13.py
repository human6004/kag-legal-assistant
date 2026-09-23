"""Write B2.5 audit records for Q121-Q130 (batch 13). Q122 blocked on 86/2015 source."""
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
    make("Q121", "OFFICIAL_VERIFIED", ["356/2025/NĐ-CP", "91/2025/QH15"], OK_NOP,
         "MULTI-HOP 3 leg, khac van ban: (A) ND 356 D42.1 - hieu luc 01/01/2026; (B) ND "
         "356 D42.2 - ND 13/2023 het hieu luc ke tu ngay ND nay co hieu luc; (C) Luat "
         "91/2025/QH15 D38.1 - hieu luc 01/01/2026; (D) Luat 91 D39.1 - xu ly da duoc "
         "dong y theo ND 13/2023 truoc ngay Luat co hieu luc thi tiep tuc thuc hien, "
         "khong phai xin dong y lai. Ca 4 leg khop nguyen van 4 marker.",
         location={"article": "42 (NĐ 356), 38+39 (Luật 91)", "clause": "1, 2", "point": None}),
    make("Q122", "BLOCKER", ["86/2015/QH13"], BLK, BLOCK_86, location=None),
    make("Q123", "OFFICIAL_VERIFIED", ["328/2026/NĐ-CP"], OK,
         "MULTI-HOP 2 leg: (A) D11.4 diem b - cong bo, canh bao trong 12 gio lam viec ke "
         "tu khi duoc gan nhan; (B) D4.1 diem b - dinh nghia 'tin gia, tin sai su that "
         "nguy hai'. Ca 2 leg khop nguyen van 2 marker.",
         location={"article": "11, 4", "clause": "4, 1", "point": "b"}),
    make("Q124", "OFFICIAL_VERIFIED", ["331/2026/NĐ-CP"], OK,
         "MULTI-HOP 2 leg: (A) D12.2 diem b - cap do 2 voi dich vu truc tuyen khac xu ly "
         "du lieu ca nhan nhay cam cua duoi 10.000 chu the; (B) D13.2 diem c - cap do 3 "
         "voi tu 10.000 chu the du lieu nhay cam tro len. Ca 2 leg khop nguyen van "
         "6 marker.",
         location={"article": "12, 13", "clause": "2", "point": "b, c"}),
    make("Q125", "OFFICIAL_VERIFIED", ["331/2026/NĐ-CP"], OK_NOP,
         "MULTI-HOP 2 leg: (A) D3.4 - cap do an ninh mang he thong thong tin duoc hieu la "
         "cap do he thong thong tin; (B) D16.4 - he thong thong tin cap do 5 la he thong "
         "thong tin quan trong ve an ninh quoc gia. Ca 2 leg khop nguyen van 2 marker.",
         location={"article": "3, 16", "clause": "4", "point": None}),
    make("Q126", "OFFICIAL_VERIFIED", ["331/2026/NĐ-CP"], OK_NOP,
         "MULTI-HOP 2 leg: (A) D38 - hieu luc 19/8/2026; (B) D39.1 - he thong dang dau tu, "
         "xay dung truoc 01/7/2026: 06 thang de hoan thanh tham dinh/phe duyet cap do "
         "theo ND 85/2016/ND-CP, va 12 thang de bao dam dieu kien theo ND nay. Ca 2 leg "
         "khop nguyen van 4 marker.",
         location={"article": "38, 39", "clause": "1", "point": None}),
    make("Q127", "OFFICIAL_VERIFIED", ["332/2026/NĐ-CP"], OK,
         "MULTI-HOP 2 leg: (A) D1.1 - quy dinh chi tiet khoan 3 Dieu 28, khoan 3 Dieu 29 "
         "Luat An ninh mang 116/2025/QH15; (B) D19.3 diem a/b - tham quyen kiem tra cua "
         "Bo Cong an va UBND tinh tro len. Ca 2 leg khop nguyen van 4 marker.",
         location={"article": "1, 19", "clause": "1, 3", "point": "a, b"}),
    make("Q128", "OFFICIAL_VERIFIED", ["134/2025/QH15"], OK,
         "MULTI-HOP 2 leg: (A) D34 - hieu luc 01/3/2026 (kem ngoai le theo D35); (B) "
         "D35.1 diem a - 18 thang voi linh vuc y te, giao duc, tai chinh; diem b - 12 "
         "thang voi cac he thong con lai. Ca 2 leg khop nguyen van 4 marker.",
         location={"article": "34, 35", "clause": "1", "point": "a, b"}),
    make("Q129", "OFFICIAL_VERIFIED", ["71/2025/QH15", "134/2025/QH15"], OK,
         "MULTI-HOP 2 van ban: (A) Luat 71/2025/QH15 D3.9 - dinh nghia he thong AI (khop "
         "3 marker dau); (B) Luat 134/2025/QH15 D33 - bai bo khoan 9 Dieu 3 cua Luat Cong "
         "nghiep cong nghe so (khop marker 'Bai bo khoan 9 Dieu 3'). Tra loi dung CAU HOI "
         "CO: khoan do DA bi bai bo. Kiem chieu: Luat 134 bai bo Luat 71, dung chieu.",
         location={"article": "3 (Luật 71), 33 (Luật 134)", "clause": "9", "point": None}),
    make("Q130", "OFFICIAL_VERIFIED", ["71/2025/QH15", "134/2025/QH15"], OK,
         "MULTI-HOP 2 van ban: (A) Luat 71/2025/QH15 D43 khoan 1 (rui ro cao + 3 ngoai le "
         "a/b/c) va khoan 2 (tac dong lon) khop nguyen van; (B) Luat 134/2025/QH15 D33 "
         "bai bo Chuong IV cua Luat 71. Da kiem truc tiep tren Cong bao 71/2025/QH15: "
         "Chuong IV 'TRI TUE NHAN TAO' bat dau tai offset 52028, Chuong V tai 57855, va "
         "Dieu 43 nam trong khoang do => Dieu 43 THUOC Chuong IV nen DA bi bai bo. Cau "
         "hoi hoi co/khong kem kiem chung hieu luc - tra loi dung. Khop 7 marker.",
         location={"article": "43 (Luật 71), 33 (Luật 134)", "clause": "1, 2", "point": "a-c"}),
]

if __name__ == "__main__":
    a, u, n = upsert(R)
    print(f"batch13 written: added={a} updated={u} total_records={n}")
