"""Write B2.5 audit records for Q071-Q080 (batch 8)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _b25_audit import make, upsert  # noqa: E402

OK = dict(document=True, article=True, clause=True, point=True,
          evidence=True, question_supported=True, markers_supported=True)
OK_NOP = dict(document=True, article=True, clause=True, point=None,
              evidence=True, question_supported=True, markers_supported=True)

R = [
    make("Q071", "OFFICIAL_VERIFIED", ["116/2025/QH15"], OK_NOP,
         "D44.1 (hieu luc 01/7/2026) va D44.2 (Luat An ninh mang 24/2018/QH14 het hieu "
         "luc ke tu ngay Luat nay co hieu luc) khop nguyen van 2 marker.",
         location={"article": "44", "clause": "1, 2", "point": None}),
    make("Q072", "OFFICIAL_VERIFIED", ["116/2025/QH15"], OK,
         "D45.1 (12 thang ke tu ngay Luat co hieu luc) va D45 (tieu de 'Dieu khoan "
         "chuyen tiep') khop nguyen van 3 marker.",
         location={"article": "45", "clause": "1", "point": None}),
    make("Q073", "OFFICIAL_VERIFIED", ["116/2025/QH15"], OK,
         "D1 (tieu de), D1.2 va cac diem a/b/c khop nguyen van 4 marker.",
         location={"article": "1", "clause": "2", "point": "a-c"}),
    make("Q074", "OFFICIAL_VERIFIED", ["24/2018/QH14"], OK_NOP,
         "D43.3 dung nguyen van: 12 thang ke tu ngay duoc bo sung.",
         location={"article": "43", "clause": "3", "point": None}),
    make("Q075", "OFFICIAL_VERIFIED", ["24/2018/QH14"], OK,
         "D43.1 (hieu luc 01/01/2019) va doan ket thuc D43 (Quoc hoi khoa XIV, ky hop thu "
         "5) khop nguyen van 3 marker.",
         location={"article": "43", "clause": "1", "point": None}),
    make("Q076", "OFFICIAL_VERIFIED", ["24/2018/QH14"], OK_NOP,
         "D43.2 dung nguyen van: 12 thang ke tu ngay Luat nay co hieu luc; bao dam du "
         "dieu kien an ninh mang; danh gia dieu kien an ninh mang. Khop 3 marker.",
         location={"article": "43", "clause": "2", "point": None}),
    make("Q077", "OFFICIAL_VERIFIED", ["328/2026/NĐ-CP"], OK_NOP,
         "D23 dung nguyen van: hieu luc tu ngay 05 thang 10 nam 2026.",
         location={"article": "23", "clause": None, "point": None}),
    make("Q078", "OFFICIAL_VERIFIED", ["1671/QĐ-TTg"], OK_NOP,
         "D3.1 dung nguyen van: hieu luc ke tu ngay ky ban hanh. Dong thoi xac nhan "
         "D3.2: Quyet dinh nay thay the Quyet dinh 127/QD-TTg ngay 26/01/2021.",
         location={"article": "3", "clause": "1", "point": None}),
    make("Q079", "OFFICIAL_VERIFIED", ["116/2025/QH15"], OK_NOP,
         "D44.2 dung nguyen van: ca Luat 86/2015/QH13 (da sua doi theo Luat "
         "35/2018/QH14) va Luat 24/2018/QH14 deu het hieu luc ke tu ngay Luat nay co "
         "hieu luc. Khop 3 marker.",
         location={"article": "44", "clause": "2", "point": None}),
    make("Q080", "OFFICIAL_VERIFIED", ["142/2026/NĐ-CP"], OK_NOP,
         "D45 dung nguyen van: hieu luc tu ngay 01 thang 5 nam 2026.",
         location={"article": "45", "clause": None, "point": None}),
]

if __name__ == "__main__":
    a, u, n = upsert(R)
    print(f"batch8 written: added={a} updated={u} total_records={n}")
