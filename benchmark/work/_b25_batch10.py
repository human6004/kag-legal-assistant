"""Write B2.5 audit records for Q091-Q100 (batch 10).

Q092 Q093 Q094 Q095 Q110 blocked on 35/2018/QH14 source.
Q097 flagged MINOR_REPAIR: question asks effective date but evidence has only clause 2.
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
    make("Q091", "OFFICIAL_VERIFIED", ["134/2025/QH15"], OK_NOP,
         "D33 Luat 134/2025/QH15 dung nguyen van: bai bo khoan 9 D3, khoan 7 D4, khoan 6 "
         "D12, diem d khoan 2 D34 va Chuong IV cua Luat Cong nghiep cong nghe so so "
         "71/2025/QH15. Kiem CHIEU sua doi: dung la Luat AI bai bo mot phan Luat 71, "
         "khong phai nguoc lai. Khop 2 marker.",
         location={"article": "33", "clause": None, "point": None}),
    make("Q092", "BLOCKER", ["35/2018/QH14"], BLK, BLOCK_35, location=None),
    make("Q093", "BLOCKER", ["35/2018/QH14"], BLK, BLOCK_35, location=None),
    make("Q094", "BLOCKER", ["35/2018/QH14"], BLK, BLOCK_35, location=None),
    make("Q096", "OFFICIAL_VERIFIED", ["356/2025/NĐ-CP"], OK_NOP,
         "D1 dung nguyen van: liet ke day du cac dieu/khoan cua Luat Bao ve du lieu ca "
         "nhan duoc quy dinh chi tiet.",
         location={"article": "1", "clause": None, "point": None}),
    make("Q097", "MINOR_REPAIR", ["356/2025/NĐ-CP"], OK_NOP,
         "FACT dung: D42.2 xac nhan Nghi dinh 13/2023/ND-CP het hieu luc ke tu ngay Nghi "
         "dinh nay co hieu luc; D42.1 cho ngay hieu luc 01/01/2026. NHUNG cau hoi hoi 2 "
         "y (ngay hieu luc + so phan ND 13/2023) trong khi gold_evidence chi co khoan 2. "
         "Phan 'hieu luc tu ngay nao' khong duoc evidence bao phu.",
         location={"article": "42", "clause": "1, 2", "point": None},
         repair={
             "issue": "gold_evidence thieu khoan 1 Dieu 42, trong khi cau hoi hoi ca ngay "
                      "hieu luc cua Nghi dinh 356/2025/ND-CP.",
             "before": "gold_evidence = [D42 khoan 2]",
             "after": "gold_evidence = [D42 khoan 1 (hieu luc 01/01/2026), "
                      "D42 khoan 2 (ND 13/2023 het hieu luc)]",
             "not_applied": True,
         }),
    make("Q098", "OFFICIAL_VERIFIED", ["333/2026/NĐ-CP"], OK_NOP,
         "D1.1 dung nguyen van: quy dinh chi tiet diem a,b,c,d,đ,g,k,l,m khoan 1 Dieu 5, "
         "khoan 4 Dieu 25, khoan 5 Dieu 34 Luat An ninh mang.",
         location={"article": "1", "clause": "1", "point": None}),
    make("Q099", "OFFICIAL_VERIFIED", ["333/2026/NĐ-CP"], OK_NOP,
         "D31 dung nguyen van: ho so tiep nhan hop le theo Nghi dinh 53/2022/ND-CP truoc "
         "ngay Nghi dinh nay co hieu luc ma chua co ket qua thi tiep tuc giai quyet theo "
         "Nghi dinh 53/2022/ND-CP. Khop 2 marker. Kiem chieu chuyen tiep dung.",
         location={"article": "31", "clause": None, "point": None}),
    make("Q100", "OFFICIAL_VERIFIED", ["142/2026/NĐ-CP"], OK,
         "D1.1 diem b (Dieu 9 ve phan loai muc do rui ro) va diem e (Dieu 13 ve danh gia "
         "su phu hop voi he thong AI co rui ro cao) khop nguyen van 2 marker. Nghi dinh "
         "142 quy dinh chi tiet Luat Tri tue nhan tao 134/2025/QH15.",
         location={"article": "1", "clause": "1", "point": "b, e"}),
]

if __name__ == "__main__":
    a, u, n = upsert(R)
    print(f"batch10 written: added={a} updated={u} total_records={n}")
