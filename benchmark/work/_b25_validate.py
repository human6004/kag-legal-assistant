"""B2.5 pre-declaration validation: enforce every completion criterion."""
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _b25_tools import WORK  # noqa: E402
from _b25_verify import AUDIT, CAND, OFFICIAL  # noqa: E402

VALID = {"OFFICIAL_VERIFIED", "MINOR_REPAIR", "REPLACE_REQUIRED", "BLOCKER"}
REQ = ("id", "source_id", "category", "status", "official_sources", "checks", "notes")
CHECK_KEYS = ("document", "article", "clause", "point", "evidence",
              "question_supported", "markers_supported")
CAT_EXPECT = {"definition": 20, "obligation": 25, "sanction_numeric": 25,
              "effectiveness_metadata": 20, "inter_document": 20,
              "multi_hop": 25, "unanswerable": 15}


def main():
    cand = json.loads(CAND.read_text(encoding="utf-8"))
    aud = json.loads(AUDIT.read_text(encoding="utf-8"))
    recs = aud["records"]
    errs, warns = [], []

    # 1. record count / ids / duplicates
    ids = [r["id"] for r in recs]
    if len(recs) != 150:
        errs.append(f"record count {len(recs)} != 150")
    if len(set(ids)) != len(ids):
        dup = [k for k, v in collections.Counter(ids).items() if v > 1]
        errs.append(f"duplicate ids: {dup}")
    want = [f"Q{i:03d}" for i in range(1, 151)]
    missing = [i for i in want if i not in set(ids)]
    if missing:
        errs.append(f"missing ids: {missing}")

    cand_by = {c["id"]: c for c in cand}
    audit_by = {r["id"]: r for r in recs}

    # 2. required fields + status vocabulary + no placeholders
    for r in recs:
        for f in REQ:
            if f not in r:
                errs.append(f"{r['id']}: missing field {f}")
        if r.get("status") not in VALID:
            errs.append(f"{r['id']}: bad status {r.get('status')!r}")
        if r["id"] not in cand_by:
            errs.append(f"{r['id']}: not in candidate dataset")
            continue
        c = cand_by[r["id"]]
        if r["source_id"] != c["source_id"]:
            errs.append(f"{r['id']}: source_id mismatch")
        if r["category"] != c["category"]:
            errs.append(f"{r['id']}: category mismatch")
        # checks: all 7 keys present, values in {True, None}
        ch = r.get("checks") or {}
        for k in CHECK_KEYS:
            if k not in ch:
                errs.append(f"{r['id']}: checks missing key {k}")
            elif ch[k] not in (True, None):
                errs.append(f"{r['id']}: checks[{k}] = {ch[k]!r} (must be true or null)")
        if not r.get("notes"):
            errs.append(f"{r['id']}: empty notes")

    # 3. answerable items must cite an official source and have substantive checks
    for r in recs:
        c = cand_by.get(r["id"])
        if not c:
            continue
        if c["answerable"]:
            if r["status"] == "BLOCKER":
                # A blocked item must record where the document was located, and must
                # NOT pretend to cite a source whose text could not be read.
                if not r.get("blocked_documents"):
                    errs.append(f"{r['id']}: BLOCKER without blocked_documents")
                if r.get("official_sources"):
                    errs.append(f"{r['id']}: BLOCKER must not claim official_sources")
            elif not r.get("official_sources"):
                errs.append(f"{r['id']}: answerable but no official_sources")
            for s in r.get("official_sources", []):
                u = s.get("url", "")
                if not u.startswith("http"):
                    errs.append(f"{r['id']}: bad official url {u!r}")
                if s.get("document_id") not in OFFICIAL:
                    warns.append(f"{r['id']}: doc {s.get('document_id')} not in OFFICIAL map")
            if r["status"] == "OFFICIAL_VERIFIED":
                ch = r["checks"]
                for k in ("document", "evidence", "question_supported"):
                    if ch.get(k) is not True:
                        errs.append(f"{r['id']}: OFFICIAL_VERIFIED but checks[{k}] != true")
        else:
            # unanswerable: must record the outside-corpus verdict explicitly
            if "outside_corpus_answer_exists" not in r:
                errs.append(f"{r['id']}: unanswerable missing outside_corpus_answer_exists")
            if c.get("gold_evidence"):
                errs.append(f"{r['id']}: unanswerable but has gold_evidence")

    # 4. per-category coverage
    got = collections.Counter(audit_by[i]["category"] for i in audit_by)
    for k, v in CAT_EXPECT.items():
        if got.get(k, 0) != v:
            errs.append(f"category {k}: {got.get(k,0)} != {v}")

    # 5. status counts / unresolved blockers
    st = collections.Counter(r["status"] for r in recs)
    blockers = [r["id"] for r in recs if r["status"] == "BLOCKER"]
    repairs = [r["id"] for r in recs if r["status"] in ("MINOR_REPAIR", "REPLACE_REQUIRED")]
    for i in repairs:
        if not audit_by[i].get("proposed_fix"):
            errs.append(f"{i}: repair status without proposed_fix")

    print(f"records={len(recs)} unique={len(set(ids))} missing={len(missing)}")
    print("status:", dict(st))
    print("blockers:", blockers)
    print("repairs:", repairs)
    print(f"\nERRORS ({len(errs)}):")
    for e in errs:
        print("  -", e)
    print(f"\nWARNINGS ({len(warns)}):")
    for w in warns[:20]:
        print("  -", w)
    print("\nRESULT:", "PASS" if not errs else "FAIL")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
