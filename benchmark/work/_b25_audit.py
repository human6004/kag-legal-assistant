"""Append/update B2.5 audit records atomically with validation (checkpoint-safe)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _b25_tools import WORK  # noqa: E402
from _b25_verify import AUDIT, CAND, OFFICIAL  # noqa: E402

VALID_STATUS = {"OFFICIAL_VERIFIED", "MINOR_REPAIR", "REPLACE_REQUIRED", "BLOCKER"}
REQ_FIELDS = ("id", "source_id", "category", "status", "official_sources", "checks", "notes")
CHECK_KEYS = ("document", "article", "clause", "point", "evidence",
              "question_supported", "markers_supported")


def load():
    if AUDIT.exists():
        return json.loads(AUDIT.read_text(encoding="utf-8"))
    return {
        "task": "B2.5_official_verification",
        "dataset": "benchmark/work/final_150_candidate.json",
        "baseline_head": "00d58a93cd0a2a8aa00653280876442fe7bddfdb",
        "status_vocabulary": sorted(VALID_STATUS),
        "records": [],
    }


def save(aud):
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    tmp = AUDIT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(aud, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(AUDIT)


def make(qid, status, docs, checks, notes, location=None, outside=None, repair=None):
    cand = {r["id"]: r for r in json.loads(CAND.read_text(encoding="utf-8"))}
    rec = cand[qid]
    srcs = []
    for d in docs:
        name, url, host = OFFICIAL.get(d, (d, "", ""))
        srcs.append({"url": url, "source_name": name, "document_id": d})
    out = {
        "id": qid,
        "source_id": rec["source_id"],
        "category": rec["category"],
        "answerable": rec["answerable"],
        "status": status,
        "official_sources": srcs,
        "verified_location": location,
        "checks": {k: checks.get(k) for k in CHECK_KEYS},
        "outside_corpus_answer_exists": outside,
        "proposed_fix": repair,
        "notes": notes,
    }
    assert status in VALID_STATUS, status
    for f in REQ_FIELDS:
        assert out[f] is not None, f
    return out


def upsert(records):
    aud = load()
    by_id = {r["id"]: i for i, r in enumerate(aud["records"])}
    added = updated = 0
    for r in records:
        if r["id"] in by_id:
            aud["records"][by_id[r["id"]]] = r
            updated += 1
        else:
            aud["records"].append(r)
            by_id[r["id"]] = len(aud["records"]) - 1
            added += 1
    aud["records"].sort(key=lambda r: r["id"])
    save(aud)
    # verify it parses back
    json.loads(AUDIT.read_text(encoding="utf-8"))
    return added, updated, len(aud["records"])


if __name__ == "__main__":
    aud = load()
    print("records:", len(aud["records"]))
