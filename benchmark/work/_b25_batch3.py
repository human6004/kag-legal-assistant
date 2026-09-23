"""Write B2.5 audit records for Q021-Q030 (batch 3)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _b25_audit import make, upsert  # noqa: E402

OK = dict(document=True, article=True, clause=True, point=True,
          evidence=True, question_supported=True, markers_supported=True)
OK_NOP = dict(document=True, article=True, clause=True, point=None,
              evidence=True, question_supported=True, markers_supported=True)

R = [
    make("Q021", "OFFICIAL_VERIFIED", ["116/2025/QH15"], OK,
         "D25.2 diem a dung nguyen van: 24 gio (co yeu cau bang van ban/thu dien tu/...), "
         "03 gio khi khan cap. Ca 2 marker khop.",
         location={"article": "25", "clause": "2", "point": "a"}),
    make("Q022", "OFFICIAL_VERIFIED", ["116/2025/QH15"], OK,
         "D16 (tieu de Dieu) va D16.3 cac diem a-den-d khop nguyen van 6 marker. "
         "Article-level evidence cite dung tieu de Dieu 16.",
         location={"article": "16", "clause": "3", "point": "a-đ"}),
    make("Q023", "OFFICIAL_VERIFIED", ["116/2025/QH15"], OK,
         "D7 (tieu de 'Cac hanh vi bi nghiem cam ve an ninh mang') va D7.2 diem g khop "
         "nguyen van, tra loi dung CAU HOI CO/KHONG kem can cu.",
         location={"article": "7", "clause": "2", "point": "g"}),
    make("Q024", "OFFICIAL_VERIFIED", ["116/2025/QH15"], OK,
         "D25.2 diem b dung nguyen van: 24 gio (kem 'luu nhat ky he thong'), 06 gio khi "
         "khan cap. Ca 3 marker khop.",
         location={"article": "25", "clause": "2", "point": "b"}),
    make("Q025", "OFFICIAL_VERIFIED", ["116/2025/QH15"], OK_NOP,
         "D38.1 dung nguyen van: toi thieu 15% tong kinh phi chuong trinh/de an/du an dau "
         "tu chuyen doi so. Marker 'Dieu 38' dung.",
         location={"article": "38", "clause": "1", "point": None}),
    make("Q026", "OFFICIAL_VERIFIED", ["116/2025/QH15"], OK_NOP,
         "D25.3 dung nguyen van, gom ca nghia vu dat chi nhanh/van phong dai dien. "
         "Cau hoi chi hoi bien phap + noi luu tru + thoi gian, deu nam trong khoan 3.",
         location={"article": "25", "clause": "3", "point": None}),
    make("Q027", "OFFICIAL_VERIFIED", ["24/2018/QH14"], OK,
         "D13.5 diem a dung nguyen van: 12 gio (su co/xam pham) va 72 gio (yeu cau quan ly "
         "nha nuoc hoac het thoi han khac phuc). Cau hoi hoi dung nhanh 72 gio. Marker "
         "'Dieu 13' dung.",
         location={"article": "13", "clause": "5", "point": "a"}),
    make("Q028", "OFFICIAL_VERIFIED", ["24/2018/QH14"], OK,
         "D13.5 (article), diem a (12 gio) va diem b (30 ngay) khop nguyen van 2 marker.",
         location={"article": "13", "clause": "5", "point": "a, b"}),
    make("Q029", "OFFICIAL_VERIFIED", ["24/2018/QH14"], OK,
         "D26.3 dung nguyen van gom ca cau 'Doanh nghiep ngoai nuoc ... phai dat chi nhanh "
         "hoac van phong dai dien tai Viet Nam'. Evidence thu 2 la trich article-level "
         "nhung noi dung cau do nam trong khoan 3 - da xac nhan bang nguon chinh thuc. "
         "Marker 'Dieu 26' dung.",
         location={"article": "26", "clause": "3", "point": None}),
    make("Q030", "OFFICIAL_VERIFIED", ["53/2022/NĐ-CP"], OK_NOP,
         "D27.1 (thoi gian luu tru toi thieu 24 thang, tinh tu khi nhan yeu cau) va D27.3 "
         "(nhat ky he thong toi thieu 12 thang) khop nguyen van 3 marker.",
         location={"article": "27", "clause": "1, 3", "point": None}),
]

if __name__ == "__main__":
    a, u, n = upsert(R)
    print(f"batch3 written: added={a} updated={u} total_records={n}")
