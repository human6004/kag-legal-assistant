"""Write B2.5 audit records for Q001-Q010 (batch 1)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _b25_audit import make, upsert  # noqa: E402

OK = dict(document=True, article=True, clause=True, point=True,
          evidence=True, question_supported=True, markers_supported=True)
OK_NOP = dict(document=True, article=True, clause=True, point=None,
              evidence=True, question_supported=True, markers_supported=True)

R = [
    make("Q001", "OFFICIAL_VERIFIED", ["116/2025/QH15"], OK_NOP,
         "Cong bao 116/2025/QH15 D8.1 verbatim khop gold, gom 5 cap do a-d va diem d. "
         "Marker 'phan loai theo 5 cap do' va 'Cap do 5 ... an ninh quoc gia' deu duoc "
         "nguon chinh thuc ho tro. Cau hoi khong rong hon evidence.",
         location={"article": "8", "clause": "1", "point": "đ"}),
    make("Q002", "OFFICIAL_VERIFIED", ["116/2025/QH15"], OK_NOP,
         "Dinh nghia an ninh mang tai D2.1 dung nguyen van. Marker 'Dieu 2' dung: "
         "D2 la 'Giai thich tu ngu', khoan 1 la dinh nghia an ninh mang.",
         location={"article": "2", "clause": "1", "point": None}),
    make("Q003", "OFFICIAL_VERIFIED", ["116/2025/QH15"], OK_NOP,
         "Khong gian mang tai D2.5 dung nguyen van, gom ca ve 'khong bi gioi han boi "
         "khong gian va thoi gian' khop marker.",
         location={"article": "2", "clause": "5", "point": None}),
    make("Q004", "OFFICIAL_VERIFIED", ["24/2018/QH14"], OK_NOP,
         "Khung bo mang tai D2.9 dung nguyen van trong Cong bao 24/2018/QH14.",
         location={"article": "2", "clause": "9", "point": None}),
    make("Q005", "OFFICIAL_VERIFIED", ["24/2018/QH14"], OK,
         "D2.5 dinh nghia co so ha tang khong gian mang quoc gia; diem a liet ke dung "
         "4 he thong truyen dan khop ca 5 marker. Article-level evidence (clause 5) "
         "va point-level evidence (diem a) deu co trong nguon chinh thuc.",
         location={"article": "2", "clause": "5", "point": "a"}),
    make("Q006", "OFFICIAL_VERIFIED", ["91/2025/QH15"], OK_NOP,
         "Dinh nghia du lieu ca nhan tai D2.1 dung nguyen van, bao gom ca cau "
         "'sau khi khu nhan dang khong con la du lieu ca nhan' khop marker.",
         location={"article": "2", "clause": "1", "point": None}),
    make("Q007", "OFFICIAL_VERIFIED", ["13/2023/NĐ-CP"], OK,
         "D2.4 va toan bo diem a den k deu khop nguyen van voi Cong bao 13/2023/ND-CP. "
         "11 evidence point tuong ung 11 marker liet ke loai du lieu ca nhan nhay cam.",
         location={"article": "2", "clause": "4", "point": "a-k"}),
    make("Q008", "BLOCKER", ["86/2015/QH13"],
         dict(document=None, article=None, clause=None, point=None,
              evidence=None, question_supported=None, markers_supported=None),
         "Chua co van ban chinh thuc de doi chieu: congbao.chinhphu.vn khong con luu "
         "Cong bao 2015; vanban.chinhphu.vn khong index luat cua Quoc hoi; vbpl.vn la SPA "
         "chan truy cap tu dong. Corpus markdown bi loi ma hoa (mojibake) nen khong dung "
         "lam nguon. CAN: tai ban chinh thuc tu congbao/vbpl bang trinh duyet.",
         location={"article": "3", "clause": "4", "point": None}),
    make("Q009", "BLOCKER", ["86/2015/QH13"],
         dict(document=None, article=None, clause=None, point=None,
              evidence=None, question_supported=None, markers_supported=None),
         "Cung blocker nguon nhu Q008. Evidence trich D3.11 nhung chua doi chieu duoc "
         "voi van ban chinh thuc.",
         location={"article": "3", "clause": "11", "point": None}),
    make("Q010", "OFFICIAL_VERIFIED", ["328/2026/NĐ-CP"], OK_NOP,
         "D3.1 Nghi dinh 328/2026/ND-CP dung nguyen van, liet ke du 7 loai thong tin "
         "khop marker thu hai.",
         location={"article": "3", "clause": "1", "point": None}),
]

if __name__ == "__main__":
    a, u, n = upsert(R)
    print(f"batch1 written: added={a} updated={u} total_records={n}")
