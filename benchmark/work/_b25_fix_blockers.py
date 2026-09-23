"""Fix BLOCKER records: a source that did not yield verifiable text must not be listed
as an official source, and notes must record where the document was actually located."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _b25_verify import AUDIT  # noqa: E402

# Where the document was genuinely located (even though text could not be extracted)
LOCATED = {
    "86/2015/QH13": "https://vanban.chinhphu.vn/?pageid=27160&docid=183196",
    "35/2018/QH14": "https://vanban.chinhphu.vn/?pageid=27160&docid=206103&classid=1&typegroupid=3",
    "367/QĐ-TTg": "https://vanban.chinhphu.vn/?pageid=27160&docid=210020&classid=2",
}

REASON = {
    "86/2015/QH13": (
        "Van ban DA dinh vi duoc tren congbao/vanban chinh thuc, nhung ban dinh kem "
        "signed PDF la anh scan (1 XObject /Im0, khong co font) nen khong co text layer; "
        "may khong co OCR (tesseract/gs/pdftoppm deu khong co). "
        "Corpus markdown va raw HTML la ban sao noi bo (class 'prov-*'), khong co dau hieu "
        "nguon chinh thuc, nen theo quy tac B2.5 KHONG duoc dung de nang len "
        "OFFICIAL_VERIFIED. CAN: OCR ban signed PDF hoac lay .doc/.docx chinh thuc."
    ),
    "35/2018/QH14": (
        "Van ban DA dinh vi duoc tren congbao/vanban chinh thuc, nhung ban dinh kem "
        "signed PDF la anh scan (khong co text layer); may khong co OCR. "
        "Corpus raw HTML la ban sao noi bo, khong co provenance chinh thuc. "
        "CAN: OCR ban signed PDF hoac lay .doc/.docx chinh thuc."
    ),
    "367/QĐ-TTg": (
        "Van ban DA dinh vi duoc tren vanban.chinhphu.vn (docid=210020) nhung ban dinh "
        "kem signed PDF la anh scan, khong co text layer; may khong co OCR. "
        "CAN: OCR ban signed PDF hoac lay .doc/.docx chinh thuc."
    ),
}


def main():
    aud = json.loads(AUDIT.read_text(encoding="utf-8"))
    fixed = 0
    for r in aud["records"]:
        if r["status"] != "BLOCKER":
            continue
        docs = [s["document_id"] for s in r.get("official_sources", [])]
        # keep the entries only as "located but unusable", recorded separately
        r["official_sources"] = []
        r["blocked_documents"] = [
            {
                "document_id": d,
                "located_at": LOCATED.get(d),
                "usable_text": False,
                "reason": REASON.get(d, "Khong trich xuat duoc text chinh thuc."),
            }
            for d in docs
        ]
        r["notes"] = "; ".join(REASON.get(d, "") for d in docs)
        fixed += 1
    AUDIT.write_text(json.dumps(aud, ensure_ascii=False, indent=2), encoding="utf-8")
    json.loads(AUDIT.read_text(encoding="utf-8"))
    print(f"blocker records normalized: {fixed} / total {len(aud['records'])}")


if __name__ == "__main__":
    main()
