"""Write B2.5 audit records for Q095 and Q101-Q109 (batch 11).

Q095 blocked (needs both 86/2015 and 35/2018). Q102 blocked (367/QD-TTg scanned PDF).
Q110 deferred to batch with 35/2018 handling.
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

BLOCK_86_35 = ("Chua co van ban chinh thuc de doi chieu: Can ca Luat 86/2015/QH13 VA "
               "Luat 35/2018/QH14; ca hai khong con tren congbao.chinhphu.vn, khong duoc "
               "vanban.chinhphu.vn index, vbpl.vn la SPA chan truy cap tu dong, corpus "
               "markdown bi mojibake. Day la cau multi-leg inter_document nen CAN ca 2 "
               "leg chinh thuc moi duoc ket luan.")
BLOCK_367 = ("Chua co van ban chinh thuc co text layer: Quyet dinh 367/QD-TTg "
             "(28/02/2026) dinh vi duoc tren vanban.chinhphu.vn nhung ban dinh kem "
             "signed PDF la ban scan; may khong co OCR. CAN: OCR hoac ban .doc/.docx "
             "chinh thuc.")

R = [
    make("Q095", "BLOCKER", ["86/2015/QH13", "35/2018/QH14"], BLK, BLOCK_86_35, location=None),
    make("Q101", "OFFICIAL_VERIFIED", ["1671/QĐ-TTg"], OK_NOP,
         "D3.2 (thay the Quyet dinh 127/QD-TTg ngay 26/01/2021) va D3.3 (cac nhiem vu "
         "dang trien khai tiep tuc thuc hien den khi hoan thanh hoac duoc dieu chinh, "
         "tich hop) khop nguyen van 3 marker. Kiem chieu quan he: 1671 THAY THE 127, "
         "dung chieu.",
         location={"article": "3", "clause": "2, 3", "point": None}),
    make("Q102", "BLOCKER", ["367/QĐ-TTg"], BLK, BLOCK_367, location=None),
    make("Q103", "OFFICIAL_VERIFIED", ["53/2022/NĐ-CP"], OK_NOP,
         "D1 dung nguyen van, liet ke day du cac diem/khoan cua Luat An ninh mang duoc "
         "quy dinh chi tiet. Khop 8 marker.",
         location={"article": "1", "clause": None, "point": None}),
    make("Q104", "OFFICIAL_VERIFIED", ["116/2025/QH15"], OK,
         "D43.17 dung nguyen van: bai bo khoan 3 Dieu 49 cua Luat Thu vien so "
         "46/2019/QH14. Khop 3 marker.",
         location={"article": "43", "clause": "17", "point": None}),
    make("Q105", "OFFICIAL_VERIFIED", ["71/2025/QH15"], OK,
         "D49 (Chuong VI, muc 'Sua doi, bo sung, thay the, bai bo mot so dieu cua cac "
         "luat co lien quan') khoan 1 dung nguyen van: bai bo khoan 9,10,11,12 Dieu 4; "
         "Muc 3 va Muc 4 Chuong III cua Luat Cong nghe thong tin so 67/2006/QH11. "
         "Khop 4 marker.",
         location={"article": "49", "clause": "1", "point": None}),
    make("Q106", "OFFICIAL_VERIFIED", ["356/2025/NĐ-CP"], OK,
         "D42.3 dung nguyen van: sua doi khoan 2 Dieu 16 cua Nghi dinh so "
         "165/2025/ND-CP. Khop 3 marker.",
         location={"article": "42", "clause": "3", "point": None}),
    make("Q107", "OFFICIAL_VERIFIED", ["91/2025/QH15"], OK,
         "D39.2 dung nguyen van: ho so da tiep nhan theo Nghi dinh 13/2023/ND-CP truoc "
         "ngay Luat co hieu luc thi tiep tuc duoc su dung va khong phai lap lai. Khop "
         "3 marker. Tra loi dung CAU HOI KHONG (khong phai lap lai).",
         location={"article": "39", "clause": "2", "point": None}),
    make("Q108", "OFFICIAL_VERIFIED", ["142/2026/NĐ-CP"], OK_NOP,
         "D21.6 dung nguyen van: trach nhiem dan su, hinh su, hanh chinh theo Dieu 22 va "
         "Dieu 23 cua Luat Khoa hoc, cong nghe va doi moi sang tao. Khop 3 marker. "
         "Kiem chieu dan chieu dung.",
         location={"article": "21", "clause": "6", "point": None}),
    make("Q109", "OFFICIAL_VERIFIED", ["341/2026/NĐ-CP"], OK_NOP,
         "D1 dung nguyen van: quy dinh chi tiet diem a khoan 1, diem c khoan 2, khoan 3 "
         "Dieu 28, khoan 3 Dieu 29 Luat An ninh mang ve mat ma dan su. Khop 6 marker.",
         location={"article": "1", "clause": None, "point": None}),
]

if __name__ == "__main__":
    a, u, n = upsert(R)
    print(f"batch11 written: added={a} updated={u} total_records={n}")
