# -*- coding: utf-8 -*-
"""GD5 — Provenance cho fact: hai loai bang chung, va trang thai xac minh.

YEU CAU GIAI DOAN 5. Tach ro hai loai, KHONG dung loai nay thay loai kia:

  extraction_provenance   fact duoc SINH TU input nao. Tra loi "may sinh ra fact".
  supporting_evidence     doan nguon THUC SU ho tro phat bieu nao. Tra loi
                          "co gi chong lung cho fact".

Mot fact co the co extraction provenance (biet chunk nao sinh ra no) ma KHONG
co supporting evidence (chua doi chieu doan trich). Audit cu do dung tinh trang
nay: 9859/10473 canh o muc PARTIAL, FULL = 0.

Trang thai ho tro nguon (dinh nghia kiem chung duoc):

  FULL        chuoi bang chung day du: co extraction provenance, co doan trich
              kiem chung duoc trong nguon, va locator dung cap.
  PARTIAL     truy duoc mot phan: thieu truong, hoac co chunk nhung chua co
              doan trich dan doi chieu.
  AMBIGUOUS   nhieu kha nang chua phan giai (nhieu van ban / nhieu chunk khac
              van ban), hoac bang chung mau thuan.
  UNTRACEABLE chua truy duoc nguon theo tieu chi da cong bo.

Quan trong:
- Nhieu nguon cung ho tro KHONG tu dong la AMBIGUOUS. Nhieu chunk CUNG mot van
  ban van la nhat quan.
- Fact thuoc van ban khong chia Dieu/Khoan/Diem: locator ghi "khong ap dung",
  KHONG bia Dieu.
- Quan he phap ly (sua doi / huong dan / thay the) phai kiem dung nghia va dung
  chieu, khong chi thay hai ten van ban trong cung mot doan.

Trang thai review tach khoi trang thai ho tro:
  review_status = AI_CHECKED | HUMAN_REVIEWED | NOT_REVIEWED
  human_verified chi True khi co nguoi thuc su review. AI khong tu gan.
"""

import hashlib
import re

__all__ = [
    "fact_key",
    "content_hash",
    "EvidenceBundle",
    "classify_support",
    "evaluation_policy",
    "verify_quote",
    "COORD_RAW",
    "COORD_NORMALIZED",
    "REVIEW_NOT_REVIEWED",
    "REVIEW_AI_CHECKED",
    "REVIEW_HUMAN_REVIEWED",
]

REVIEW_NOT_REVIEWED = "NOT_REVIEWED"
REVIEW_AI_CHECKED = "AI_CHECKED"
REVIEW_HUMAN_REVIEWED = "HUMAN_REVIEWED"

SUPPORT_FULL = "FULL"
SUPPORT_PARTIAL = "PARTIAL"
SUPPORT_AMBIGUOUS = "AMBIGUOUS"
SUPPORT_UNTRACEABLE = "UNTRACEABLE"

# He toa do cua `span`. PHAI ghi ro vi cung mot cap so chi co nghia khi biet
# dang ap len chuoi nao:
#   RAW         chi so tren chuoi GOC, y nguyen nhu nguon luu.
#   NORMALIZED  chi so tren chuoi da qua norm_text() (gop khoang trang, NFC).
# Khong suy doan: bang chung khong khai bao thi coi la khong kiem chung duoc.
COORD_RAW = "raw"
COORD_NORMALIZED = "normalized"

_WS = re.compile(r"\s+", re.U)


def norm_text(text):
    """Chuan hoa de so khop doan trich: gop khoang trang, NFC.

    KHONG bo dau, KHONG bo so, KHONG bo dau cau — vì làm vậy sẽ che mất lỗi
    nội dung. Chỉ gộp khoảng trắng, đúng như phép kiểm của R4.
    """
    import unicodedata

    return _WS.sub(" ", unicodedata.normalize("NFC", str(text))).strip()


def content_hash(text):
    """SHA-256 cua noi dung da chuan hoa khoang trang.

    Dung de phat hien nguon doi: bang chung cu tro vao hash cu se khong con
    khop, va phai duoc danh dau can kiem lai.
    """
    return hashlib.sha256(norm_text(text).encode("utf-8")).hexdigest()


def fact_key(source_label, source_id, relation, target_label, target_id):
    """Khoa on dinh cua mot fact. KHONG dung elementId Neo4j.

    Ghep bang ky tu phan cach khong the xuat hien trong id thuc te, de khoa
    khong the trung gia.
    """
    parts = [source_label, source_id, relation, target_label, target_id]
    if any(p is None for p in parts):
        raise ValueError("fact_key thieu thanh phan")
    return "\x1f".join(str(p) for p in parts)


def verify_quote(quote, span, source_text, coordinate=COORD_NORMALIZED):
    """Kiem tra mot doan trich CO THAT nam trong nguon, tai dung span khai bao.

    Tra ``(ok: bool, reason: str)``. Day la cho DUY NHAT quyet dinh mot doan
    trich co gia tri hay khong; ``classify_support`` goi lai ham nay.

    Kiem bon thu, khong bo qua thu nao:

    1. Co nguon de doi chieu. Nguon rong/None -> khong kiem chung duoc.
    2. Quote khong rong va **nam trong** nguon (theo he toa do khai bao).
    3. Span la cap so nguyen, khong am, khong vuot bien nguon.
    4. Cat nguon theo span phai ra **dung** quote da chuan hoa. Doi chieu ca
       ``quote`` lan phan chenh: mot span dung nhung quote dat sai cho la mau
       thuan, khong duoc coi la dat.

    Khong tu sua quote hay span de "cho khop". Lech thi bao lech.
    """
    if source_text is None:
        return False, "khong co nguon de doi chieu"
    raw = str(source_text)
    if not raw.strip():
        return False, "nguon rong"

    if quote is None or not str(quote).strip():
        return False, "quote rong"
    q_norm = norm_text(quote)

    haystack = raw if coordinate == COORD_RAW else norm_text(raw)
    if q_norm not in haystack:
        return False, "quote KHONG nam trong nguon"

    if not span:
        return False, "thieu span"
    try:
        start, end = int(span[0]), int(span[1])
    except (TypeError, ValueError, IndexError):
        return False, f"span khong phai cap so nguyen: {span!r}"

    if start < 0 or end < 0:
        return False, f"span am: ({start}, {end})"
    if end < start:
        return False, f"span dao nguoc: ({start}, {end})"
    if end > len(haystack):
        return False, (
            f"span vuot bien: ({start}, {end}) > do dai nguon {len(haystack)}"
        )

    sliced = norm_text(haystack[start:end]) if coordinate == COORD_NORMALIZED \
        else haystack[start:end]
    if sliced != q_norm:
        return False, (
            f"quote khong khop noi dung tai span: span cat ra "
            f"{sliced[:60]!r}, quote la {q_norm[:60]!r}"
        )
    return True, "quote co that, dung tai span da khai bao"


class EvidenceBundle:
    """Bang chung cho MOT fact, tach ro hai loai.

    extraction  : fact sinh ra tu dau (chunk/keyword/metadata). CHI tra loi
                  "may sinh ra", KHONG chung minh noi dung.
    supporting  : doan nguon da doi chieu THAT SU ho tro phat bieu.

    Moi ban ghi supporting giu DU bang chung de kiem lai ve sau: quote, span,
    he toa do, hash nguon, chunk va van ban/version. Thieu truong nao thi ban
    ghi do khong the len FULL — xem ``classify_support``.
    """

    __slots__ = (
        "fact_key", "source", "predicate_raw", "target",
        "origin", "extraction", "supporting", "locator",
        "review_status", "human_verified", "limitations",
    )

    def __init__(self, fact_key, source, predicate_raw, target):
        self.fact_key = fact_key
        self.source = source
        self.predicate_raw = predicate_raw
        self.target = target
        # origin: LLM_EXTRACTION | METADATA_IMPORT | OTHER
        self.origin = None
        self.extraction = []   # [{chunk_id, document_key, content_sha256}]
        self.supporting = []   # [{quote, span, coordinate, content_sha256,
                               #   chunk_id, document_key, locator, verified}]
        self.locator = {}
        self.review_status = REVIEW_NOT_REVIEWED
        self.human_verified = False
        self.limitations = []

    def add_extraction(self, chunk_id, document_key=None, chunk_content=None):
        rec = {"chunk_id": chunk_id, "document_key": document_key}
        if chunk_content is not None:
            rec["content_sha256"] = content_hash(chunk_content)
        self.extraction.append(rec)

    def add_support(self, quote, span, source_text, locator=None,
                    chunk_id=None, document_key=None,
                    coordinate=COORD_NORMALIZED):
        """Them doan nguon da doi chieu.

        Chay ``verify_quote`` NGAY tai day va luu ket qua. Khong tu gan FULL:
        ``classify_support`` moi quyet dinh, dua tren ket qua da luu.

        ``source_text`` la chuoi nguon THAT ma quote phai nam trong. Khong
        truyen nguon thi ban ghi duoc danh dau chua kiem chung duoc, va se
        khong bao gio len FULL.
        """
        ok, why = verify_quote(quote, span, source_text, coordinate)
        rec = {
            "quote": quote,
            "span": list(span) if span else None,
            "coordinate": coordinate,
            "content_sha256": content_hash(source_text)
            if source_text is not None else None,
            "chunk_id": chunk_id,
            "document_key": document_key,
            "verified": ok,
            "verify_reason": why,
        }
        if locator:
            rec["locator"] = dict(locator)
        self.supporting.append(rec)

    def to_dict(self):
        return {
            "fact_key": self.fact_key,
            "source": self.source,
            "predicate_raw": self.predicate_raw,
            "target": self.target,
            "origin": self.origin,
            "extraction_provenance": self.extraction,
            "supporting_evidence": self.supporting,
            "locator": self.locator,
            "support_status": classify_support(self),
            "review_status": self.review_status,
            "human_verified": self.human_verified,
            "limitations": self.limitations,
        }


def _locator_agrees(loc, doc_key):
    """Locator co mau thuan voi van ban da khai bao khong?

    Tra ``(state, why)`` voi state:
      ``"ok"``        locator day du cap, hoac da ghi ro khong ap dung.
      ``"incomplete"`` thieu cap -> chua du de len FULL.
      ``"conflict"``  locator tro van ban khac -> mau thuan, phai cach ly.
    """
    loc = loc or {}
    loc_doc = loc.get("document_key")
    if loc_doc and doc_key and loc_doc != doc_key:
        return "conflict", (
            f"locator tro van ban {loc_doc!r} nhung bang chung thuoc {doc_key!r}"
        )
    if loc.get("articles") is not None:
        # Nhieu Dieu duoc trich: locator cap fact khong xac dinh duoc mot Dieu.
        arts = loc.get("articles") or []
        if len(arts) > 1 and not loc.get("article"):
            return "incomplete", (
                f"doan trich trai {len(arts)} Dieu, locator chua chon duoc cap"
            )
    if loc.get("article") is None and not loc.get("not_applicable"):
        return "incomplete", "thieu locator cap Dieu va khong danh dau khong ap dung"
    return "ok", "locator dung cap"


def classify_support(bundle):
    """Phan loai muc ho tro theo tieu chi cong bo. Thuan ham, kiem chung duoc.

    FULL chi khi HOI DU, khong thieu muc nao:

      1. co extraction provenance (biet chunk sinh ra fact);
      2. moi ban ghi supporting da qua ``verify_quote`` (quote co that, dung span);
      3. hash nguon cua ban ghi khop chunk tuong ung trong extraction provenance
         — bat truong hop nguon doi sau khi lap bang chung;
      4. chunk/van ban cua bang chung khong mau thuan voi extraction provenance;
      5. locator dung cap (hoac danh dau khong ap dung) va khong tro van ban khac;
      6. tat ca bang chung cung MOT van ban (khac van ban -> AMBIGUOUS).

    Thieu bat ky muc nao -> PARTIAL. Mau thuan -> AMBIGUOUS. Khong truy duoc
    nguon nao -> UNTRACEABLE. KHONG suy doan de lap cho trong.
    """
    if not bundle.extraction and not bundle.supporting:
        return SUPPORT_UNTRACEABLE

    docs = {e.get("document_key") for e in bundle.extraction}
    docs.discard(None)

    # Nhieu van ban khac nhau -> chua phan giai duoc thuoc ve van ban nao.
    if len(docs) > 1:
        return SUPPORT_AMBIGUOUS

    if not bundle.supporting:
        # Biet noi sinh ra fact, nhung CHUA co doan trich doi chieu.
        return SUPPORT_PARTIAL

    extraction_by_chunk = {
        e.get("chunk_id"): e for e in bundle.extraction if e.get("chunk_id")
    }
    support_docs = set()

    for s in bundle.supporting:
        # (2) quote phai da duoc kiem chung that su.
        if not s.get("verified"):
            return SUPPORT_PARTIAL

        s_doc = s.get("document_key")
        s_chunk = s.get("chunk_id")
        if s_doc:
            support_docs.add(s_doc)

        # (4) van ban cua bang chung phai nhat quan voi extraction provenance.
        if doc_key := (s_doc or next(iter(docs), None)):
            if docs and s_doc and s_doc not in docs:
                return SUPPORT_AMBIGUOUS
            # (5) locator khong duoc tro van ban khac.
            state, _ = _locator_agrees(s.get("locator") or bundle.locator, doc_key)
            if state == "conflict":
                return SUPPORT_AMBIGUOUS
            if state == "incomplete":
                return SUPPORT_PARTIAL
        else:
            return SUPPORT_PARTIAL

        # (3) hash nguon phai khop chunk tuong ung -> bat nguon doi.
        if s_chunk:
            ext = extraction_by_chunk.get(s_chunk)
            if ext is None:
                # Bang chung tro chunk khong nam trong extraction provenance.
                return SUPPORT_PARTIAL
            ext_hash = ext.get("content_sha256")
            if ext_hash and s.get("content_sha256") and ext_hash != s["content_sha256"]:
                # Nguon da doi sau khi lap bang chung -> phai kiem lai.
                return SUPPORT_PARTIAL
        else:
            # Khong gan duoc bang chung voi chunk nao -> chua doi chieu duoc.
            return SUPPORT_PARTIAL

    # (6) bang chung tra cac van ban khac nhau -> mo ho.
    if len(support_docs) > 1:
        return SUPPORT_AMBIGUOUS
    return SUPPORT_FULL


def evaluation_policy(record):
    """Chinh sach loai fact khoi tap danh gia chat luong.

    Tra (eligible: bool, reason: str). Mac dinh KHONG duoc vao tap danh gia:
    phai co bang chung nguon day du VA co nguoi review. AI kiem khong du.
    """
    status = record.get("support_status")
    review = record.get("review_status", REVIEW_NOT_REVIEWED)
    human = bool(record.get("human_verified", False))

    if status == SUPPORT_UNTRACEABLE:
        return False, "khong truy duoc nguon theo tieu chi da cong bo"
    if status == SUPPORT_AMBIGUOUS:
        return False, "nhieu kha nang chua phan giai hoac bang chung mau thuan"
    if status == SUPPORT_PARTIAL:
        return False, "thieu doan bang chung hoac thieu locator dung cap"
    if status != SUPPORT_FULL:
        return False, f"trang thai ho tro khong xac dinh: {status!r}"
    if review != REVIEW_HUMAN_REVIEWED or not human:
        return False, (
            f"AI kiem khong thay the nguoi kiem; review_status={review!r}, "
            f"human_verified={human}"
        )
    return True, "bang chung nguon day du VA da duoc nguoi review"


def _self_check():
    """Ca kiem chung: khong tu gan FULL, khong tu gan human_verified."""
    # 1. Khong bang chung -> UNTRACEABLE
    b = EvidenceBundle("k1", "A", "quyNhNghAV", "B")
    assert classify_support(b) == SUPPORT_UNTRACEABLE
    print(f"  khong bang chung        -> {classify_support(b)}")

    # 2. Chi co extraction provenance -> PARTIAL (KHONG duoc FULL)
    b = EvidenceBundle("k2", "A", "quyNhNghAV", "B")
    b.origin = "LLM_EXTRACTION"
    b.add_extraction("chunk1", "328-2026-ND-CP", "noi dung chunk")
    assert classify_support(b) == SUPPORT_PARTIAL, classify_support(b)
    print(f"  chi biet chunk sinh ra  -> {classify_support(b)}  (khong duoc FULL)")

    # 3. Nhieu chunk CUNG mot van ban -> van PARTIAL, KHONG phai AMBIGUOUS
    b = EvidenceBundle("k3", "A", "quyNhNghAV", "B")
    b.add_extraction("c1", "328-2026-ND-CP", "x")
    b.add_extraction("c2", "328-2026-ND-CP", "y")
    assert classify_support(b) == SUPPORT_PARTIAL, classify_support(b)
    print(f"  nhieu chunk CUNG van ban-> {classify_support(b)}  (khong phai AMBIGUOUS)")

    # 4. Nhieu van ban khac nhau -> AMBIGUOUS
    b = EvidenceBundle("k4", "A", "quyNhNghAV", "B")
    b.add_extraction("c1", "328-2026-ND-CP")
    b.add_extraction("c2", "5-2026-TT-BKHCN")
    assert classify_support(b) == SUPPORT_AMBIGUOUS, classify_support(b)
    print(f"  nhieu VAN BAN khac nhau -> {classify_support(b)}")

    # 5. Doan trich CO THAT + dung span + chunk khop + locator dung cap -> FULL
    src = "Điều 2. Đối tượng áp dụng của Nghị định này gồm các tổ chức, cá nhân."
    q5 = "Điều 2. Đối tượng áp dụng"
    span5 = (0, len(norm_text(q5)))   # span tinh tren chuoi DA chuan hoa
    b = EvidenceBundle("k5", "A", "quyNhNghAV", "B")
    b.add_extraction("c1", "328-2026-ND-CP", src)
    b.add_support(q5, span5, src, {"article": "2", "clause": "1"},
                  chunk_id="c1", document_key="328-2026-ND-CP")
    assert classify_support(b) == SUPPORT_FULL, classify_support(b)
    print(f"  doan trich that+span dung -> {classify_support(b)}")

    # 5b. Quote KHONG ton tai trong nguon -> KHONG duoc FULL
    b = EvidenceBundle("k5b", "A", "quyNhNghAV", "B")
    b.add_extraction("c1", "328-2026-ND-CP", src)
    b.add_support("NO SUCH QUOTE", (0, 13), src, {"article": "2"},
                  chunk_id="c1", document_key="328-2026-ND-CP")
    assert classify_support(b) == SUPPORT_PARTIAL, classify_support(b)
    print(f"  quote khong co trong nguon-> {classify_support(b)}  (khong duoc FULL)")

    # 5c. Span am / vuot bien -> KHONG duoc FULL
    for bad_span in ((-10, 999), (0, 10 ** 6), (50, 10)):
        b = EvidenceBundle("k5c", "A", "quyNhNghAV", "B")
        b.add_extraction("c1", "328-2026-ND-CP", src)
        b.add_support(q5, bad_span, src, {"article": "2"},
                      chunk_id="c1", document_key="328-2026-ND-CP")
        assert classify_support(b) == SUPPORT_PARTIAL, (bad_span, classify_support(b))
    print(f"  span am / vuot bien / dao -> {SUPPORT_PARTIAL}  (khong duoc FULL)")

    # 5d. Quote dung nhung nam SAI CHO so voi span -> KHONG duoc FULL
    b = EvidenceBundle("k5d", "A", "quyNhNghAV", "B")
    b.add_extraction("c1", "328-2026-ND-CP", src)
    b.add_support(q5, (5, 5 + len(norm_text(q5))), src, {"article": "2"},
                  chunk_id="c1", document_key="328-2026-ND-CP")
    assert classify_support(b) == SUPPORT_PARTIAL, classify_support(b)
    print(f"  quote dat sai cho so span-> {classify_support(b)}  (khong duoc FULL)")

    # 5e. Nguon DOI sau khi lap bang chung -> hash lech -> KHONG duoc FULL
    b = EvidenceBundle("k5e", "A", "quyNhNghAV", "B")
    b.add_extraction("c1", "328-2026-ND-CP", src)
    b.add_support(q5, span5, src, {"article": "2"},
                  chunk_id="c1", document_key="328-2026-ND-CP")
    b.extraction[0]["content_sha256"] = content_hash(src + " (sua doi)")
    assert classify_support(b) == SUPPORT_PARTIAL, classify_support(b)
    print(f"  nguon doi sau khi lap BC -> {classify_support(b)}  (khong duoc FULL)")

    # 5f. Locator tro SAI van ban -> mau thuan -> AMBIGUOUS
    b = EvidenceBundle("k5f", "A", "quyNhNghAV", "B")
    b.add_extraction("c1", "328-2026-ND-CP", src)
    b.add_support(q5, span5, src,
                  {"article": "2", "document_key": "5-2026-TT-BKHCN"},
                  chunk_id="c1", document_key="328-2026-ND-CP")
    assert classify_support(b) == SUPPORT_AMBIGUOUS, classify_support(b)
    print(f"  locator tro van ban khac-> {classify_support(b)}")

    # 5g. Bang chung tro chunk khong co trong extraction provenance
    b = EvidenceBundle("k5g", "A", "quyNhNghAV", "B")
    b.add_extraction("c1", "328-2026-ND-CP", src)
    b.add_support(q5, span5, src, {"article": "2"}, chunk_id="c_KHAC",
                  document_key="328-2026-ND-CP")
    assert classify_support(b) == SUPPORT_PARTIAL, classify_support(b)
    print(f"  BC tro chunk khong co   -> {classify_support(b)}  (khong duoc FULL)")

    # 5h. Bang chung thuoc van ban KHAC extraction provenance -> AMBIGUOUS
    b = EvidenceBundle("k5h", "A", "quyNhNghAV", "B")
    b.add_extraction("c1", "328-2026-ND-CP", src)
    b.add_support(q5, span5, src, {"article": "2"}, chunk_id="c1",
                  document_key="5-2026-TT-BKHCN")
    assert classify_support(b) == SUPPORT_AMBIGUOUS, classify_support(b)
    print(f"  BC khac van ban voi EP   -> {classify_support(b)}")

    # 6. Doan trich nhung KHONG locator -> PARTIAL (khong bia Dieu)
    b = EvidenceBundle("k6", "A", "quyNhNghAV", "B")
    b.add_extraction("c1", "328-2026-ND-CP", src)
    b.add_support(q5, span5, src, chunk_id="c1", document_key="328-2026-ND-CP")
    assert classify_support(b) == SUPPORT_PARTIAL, classify_support(b)
    print(f"  doan trich, thieu locator-> {classify_support(b)}")

    # 7. Van ban khong chia Dieu: locator not_applicable -> FULL
    src7 = "Quyết định phê duyệt Chiến lược quốc gia về trí tuệ nhân tạo đến năm 2030."
    q7 = "phê duyệt Chiến lược"
    b = EvidenceBundle("k7", "A", "quyNhNghAV", "B")
    b.add_extraction("c1", "1671-NDQ-QD-TTG", src7)
    b.add_support(q7, (len(norm_text("Quyết định ")),
                       len(norm_text("Quyết định " + q7))), src7,
                  {"article": None, "not_applicable": True},
                  chunk_id="c1", document_key="1671-NDQ-QD-TTG")
    assert classify_support(b) == SUPPORT_FULL, classify_support(b)
    print(f"  van ban khong chia Dieu -> {classify_support(b)}  (not_applicable)")

    # 8. AI kiem KHONG lam fact duoc vao tap danh gia
    rec = b.to_dict()
    ok, why = evaluation_policy(rec)
    assert not ok, why
    print(f"  FULL nhung chua nguoi kiem -> eligible={ok}  ({why[:52]}...)")

    # 9. Chi khi HUMAN_REVIEWED moi eligible
    b.review_status = REVIEW_HUMAN_REVIEWED
    b.human_verified = True
    ok, why = evaluation_policy(b.to_dict())
    assert ok, why
    print(f"  FULL + nguoi review     -> eligible={ok}")

    # 10. AI_CHECKED khong du
    b.review_status = REVIEW_AI_CHECKED
    b.human_verified = False
    ok, why = evaluation_policy(b.to_dict())
    assert not ok, why
    print(f"  FULL + chi AI kiem      -> eligible={ok}  (AI khong thay nguoi)")

    # 11. hash doi khi noi dung doi
    h1 = content_hash("Điều 2. Đối tượng áp dụng")
    h2 = content_hash("Điều 2.  Đối tượng áp dụng")  # chi khac khoang trang
    h3 = content_hash("Điều 2. Đối tượng áp dụng (sửa)")
    assert h1 == h2, "gop khoang trang phai cho cung hash"
    assert h1 != h3, "doi noi dung phai doi hash"
    print(f"  hash on dinh qua khoang trang, doi khi noi dung doi")

    # 12. fact_key khong dung elementId
    k = fact_key("Article", "dieu:328-2026-ND-CP#2", "quyNhNghAV", "Obligation", "x")
    assert "14808249" not in k
    assert fact_key("A", "a", "p", "B", "b") == fact_key("A", "a", "p", "B", "b")
    print(f"  fact_key on dinh, khong dung elementId")

    # 13. verify_quote tu no phai tu choi duoc (khong chi la toan tu substring)
    good, _ = verify_quote("Điều 2", (0, len(norm_text("Điều 2"))), src)
    assert good, "quote dung tai span dung phai dat"
    for bad in [
        ("NO SUCH QUOTE", (0, 13)),
        ("Điều 2", (-10, 999)),
        ("Điều 2", (0, 10 ** 6)),
        ("Điều 2", (5, 5 + len(norm_text("Điều 2")))),
        ("Điều 2", None),
        ("", (0, 0)),
        (None, (0, 6)),
        ("Điều 2", (len(norm_text("Điều 2")), 0)),
    ]:
        ok, why = verify_quote(bad[0], bad[1], src)
        assert not ok, f"verify_quote phai tu choi {bad!r}, nhung tra True"
    ok, why = verify_quote("Điều 2", (0, len(norm_text("Điều 2"))), None)
    assert not ok, "thieu nguon phai bi tu choi"
    ok, why = verify_quote("Điều 2", (0, len(norm_text("Điều 2"))), "   ")
    assert not ok, "nguon rong phai bi tu choi"
    print(f"  verify_quote tu choi quote gia/span sai/thieu nguon")

    # 14. tu dong kiem tra KHONG bao gio tu gan human_verified
    b = EvidenceBundle("k14", "A", "p", "B")
    b.add_extraction("c1", "328-2026-ND-CP", src)
    b.add_support(q5, span5, src, {"article": "2"},
                  chunk_id="c1", document_key="328-2026-ND-CP")
    d = b.to_dict()
    assert d["support_status"] == SUPPORT_FULL
    assert d["human_verified"] is False
    assert d["review_status"] == REVIEW_NOT_REVIEWED
    ok, why = evaluation_policy(d)
    assert not ok, "FULL nhung chua nguoi kiem KHONG duoc eligible"
    print(f"  FULL nhung chua nguoi kiem -> eligible={ok}")

    print("[self-check ok] tach extraction provenance khoi supporting evidence")
    return 0


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(_self_check())
