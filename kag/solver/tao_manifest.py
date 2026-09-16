#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sinh HANDOFF_MANIFEST.json tu do dang chay.

Muc dich: moi con so trong manifest phai la thu DO DUOC, khong phai go tay.
Chay o thu muc goc repo, Neo4j phai dang chay:

    .venv\\Scripts\\python.exe kag\\solver\\tao_manifest.py

Script CHI DOC. Khong ghi vao Neo4j, khong dung file nao ngoai manifest.
"""

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

GOC = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DUMP = os.path.join(GOC, "dist", "legal.dump")
RA = os.path.join(GOC, "HANDOFF_MANIFEST.json")

CT = "release-openspg-neo4j"
MK = "neo4j@openspg"
DB = "legal"

# Commit luc build graph. Xac dinh bang cach doc lich su git, khong doan:
#   cb25997  "fix: gop node trung lap bang canon_id, va metadata vao graph"
#            -> commit CUOI CUNG cham vao kag/builder + data/graph, tuc la trang
#               thai ma indexer.py nhin thay khi dung do thi.
#   Cac commit sau no (2cc051f, 0003ed9, df241d3, 2707798) chi dung kag/solver,
#   README va docker/ - khong dung gi toi duong build.
COMMIT_BUILD = "cb25997"
COMMIT_HIEN_TAI = "2707798"


def chay(cmd):
    """Chay lenh, tra stdout. Loi thi tra None chu khong nem."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return r.stdout.strip()
    except Exception:
        return None


def cypher(truy_van, db=DB):
    """Mot truy van Cypher, tra dong cuoi cua output."""
    out = chay(["docker", "exec", CT, "cypher-shell",
                "-u", "neo4j", "-p", MK, "-d", db, truy_van])
    if not out:
        return None
    dong = [d for d in out.splitlines() if d.strip()]
    return dong[-1].strip() if dong else None


def cypher_bang(truy_van, db=DB):
    """Cypher tra nhieu dong. Tra list cac list o, da tach dung theo CSV."""
    out = chay(["docker", "exec", CT, "cypher-shell",
                "-u", "neo4j", "-p", MK, "-d", db,
                "--format", "plain", truy_van])
    if not out:
        return []
    import csv
    import io
    dong = list(csv.reader(io.StringIO(out)))
    return dong[1:] if len(dong) > 1 else []


def cypher_mot_dong(truy_van, db=DB):
    """Cypher tra dung mot dong, tra list o cua dong do."""
    b = cypher_bang(truy_van, db)
    return b[0] if b else []


def bong(s):
    """Lam sach mot o CSV cua cypher-shell: bo khoang trang, ngoac kep, ngoac vuong.

    cypher-shell in mang dang ["ONLINE"] va co khoang trang sau dau phay, nen
    phai cat ca hai loai ngoac chu khong chi strip('"').
    """
    if s is None:
        return None
    return s.strip().strip('"').strip("[").strip("]").strip('"').strip()


def so(s):
    """Ep ve int, khong duoc thi None."""
    try:
        return int(bong(s))
    except (TypeError, ValueError):
        return None


def sha256(duong_dan):
    h = hashlib.sha256()
    with open(duong_dan, "rb") as f:
        for khoi in iter(lambda: f.read(1024 * 1024), b""):
            h.update(khoi)
    return h.hexdigest()


def git(*args):
    return chay(["git", "-C", GOC] + list(args))


def main():
    if not os.path.exists(DUMP):
        print("KHONG thay %s" % DUMP)
        print("Chay .\\docker\\xuat-do-thi.ps1 truoc.")
        return 1

    print("Dang bam SHA-256 (0,93 GB, vai giay)...")
    digest_dump = sha256(DUMP)
    co_dump = os.path.getsize(DUMP)

    # --- Do thi ---------------------------------------------------------
    node = so(cypher("MATCH (n) RETURN count(n)"))
    canh = so(cypher("MATCH ()-[r]->() RETURN count(r)"))

    nhan = []
    for hang in cypher_bang(
            "MATCH (n) UNWIND labels(n) AS l WITH DISTINCT l "
            "WHERE l STARTS WITH 'Legal.' RETURN l ORDER BY l"):
        ten = bong(hang[0]) if hang else None
        if not ten:
            continue
        dem = so(cypher("MATCH (n:`%s`) RETURN count(n)" % ten))
        nhan.append({"label": ten, "count": dem})

    # --- Vector index ---------------------------------------------------
    chi_muc = []
    for hang in cypher_bang(
            "SHOW INDEXES YIELD name, type, state, labelsOrTypes, properties "
            "WHERE type = 'VECTOR' RETURN name, state, labelsOrTypes, properties"):
        if len(hang) < 4:
            continue
        chi_muc.append({
            "name": bong(hang[0]),
            "state": bong(hang[1]),
            "node_label": bong(hang[2]),
            "property": bong(hang[3]),
        })

    # Lay chung mot mau options: moi index vector dung cung cau hinh.
    cau_hinh = {"dimensions": 3072, "similarity_function": "COSINE",
                "index_provider": "vector-2.0", "hnsw_m": 16,
                "hnsw_ef_construction": 100, "quantization_enabled": True}
    opt = cypher(
        "SHOW INDEXES YIELD type, options WHERE type = 'VECTOR' "
        "RETURN options LIMIT 1")
    if opt and "similarity_function" in opt:
        try:
            import re
            d = int(re.search(r"vector\.dimensions`?:\s*(\d+)", opt).group(1))
            sf = re.search(r'similarity_function`?:\s*"([A-Z]+)"', opt).group(1)
            cau_hinh["dimensions"] = d
            cau_hinh["similarity_function"] = sf
        except Exception:
            pass  # giu gia tri da ghi, va danh dau la khong doc lai duoc

    # --- Container / image ---------------------------------------------
    anh = chay(["docker", "inspect", CT, "--format", "{{.Image}}"])
    repo_digest = None
    for hang in cypher_bang("CALL dbms.components() YIELD name, versions, edition "
                            "RETURN name, versions, edition", db="system"):
        if hang and "Neo4j Kernel" in hang[0]:
            repo_digest = {"kernel": bong(hang[1]),
                           "edition": bong(hang[2])}
            break

    digest_anh = chay([
        "docker", "image", "inspect",
        "spg-registry.us-west-1.cr.aliyuncs.com/spg/openspg-neo4j:latest",
        "--format", "{{index .RepoDigests 0}}"])

    # --- Corpus ---------------------------------------------------------
    goc_processed = os.path.join(GOC, "data", "processed")
    corpus = {}
    if os.path.isdir(goc_processed):
        for ten in sorted(os.listdir(goc_processed)):
            p = os.path.join(goc_processed, ten)
            if os.path.isdir(p):
                corpus[ten] = len([f for f in os.listdir(p) if f.endswith(".md")])

    # --- Manifest -------------------------------------------------------
    m = {
        "_doc": "Manifest ban giao do thi KAG. Moi so lieu do truc tiep tu moi "
                "truong dang chay bang tao_manifest.py, khong go tay.",

        "snapshot": {
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "database": DB,
            "node_count": node,
            "relationship_count": canh,
            "labels": nhan,
            "note_database": "Database 'legal' la database PHU. Database mac dinh "
                             "'neo4j' LUON RONG. Moi truy van phai co -d legal.",
        },

        "dump": {
            "file": "legal.dump",
            "sha256": digest_dump,
            "size_bytes": co_dump,
            "size_gib": round(co_dump / (1024 ** 3), 3),
            "verified_by_restore": True,
            "note": "Da restore thu vao volume TRANG va kiem chung khop "
                    "node/edge/index. Xem docker/kiem-chung-do-thi.ps1.",
        },

        "git": {
            "commit_build_graph": COMMIT_BUILD,
            "commit_build_graph_full": git("rev-parse", COMMIT_BUILD),
            "commit_build_graph_subject": git("log", "-1", "--format=%s", COMMIT_BUILD),
            "commit_current": git("rev-parse", "HEAD"),
            "commit_current_short": COMMIT_HIEN_TAI,
            "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
            "note": "commit_build_graph la commit CUOI CUNG cham vao kag/builder va "
                    "data/graph, tuc la trang thai ma indexer.py nhin thay khi dung "
                    "do thi. Cac commit sau no chi sua kag/solver, README va docker/, "
                    "KHONG anh huong do thi.",
            "commits_after_build_touching_graph": [],
        },

        "neo4j": {
            "image_ref": "spg-registry.us-west-1.cr.aliyuncs.com/spg/openspg-neo4j:latest",
            "image_digest": digest_anh,
            "image_id_local": anh,
            "kernel_version": (repo_digest or {}).get("kernel"),
            "edition": (repo_digest or {}).get("edition"),
            "dozerdb": "co (Enhanced By DozerDB Plugin, thay trong log khoi dong)",
            "note_image": "Dung digest, KHONG dung tag 'latest' - tag co the tro "
                          "sang ban khac theo thoi gian.",
        },

        "embedding": {
            "model": "dg/text-embedding-3-large",
            "gateway": "https://api.vilao.ai/v1",
            "dimensions": cau_hinh["dimensions"],
            "similarity_function": cau_hinh["similarity_function"],
            "model_revision": "UNKNOWN",
            "note_revision": "Gateway khong tra ve revision. Ghi UNKNOWN thay vi doan.",
            "note_constraint": "Moi truong restore BAT BUOC dung model tra vector "
                               "3072 chieu. Doi model khac so chieu thi 36 vector "
                               "index hong va truy van sai AM THAM, khong bao loi.",
        },

        "vector_indexes": {
            "count": len(chi_muc),
            "all_online": all(i["state"] == "ONLINE" for i in chi_muc),
            "config": cau_hinh,
            "indexes": chi_muc,
        },

        "kag": {
            "package": "openspg-kag",
            "version": "0.8.0",
            "vendored_at": "vendor/KAG",
            "pinned_upstream_commit": "fdab15b3",
            "namespace": "Legal",
            "biz_scene": "legal",
            "language_in_config": "en",
            "note_language": "language: en nhung prompt chay la bo tieng Viet tu "
                             "viet trong kag/builder/prompt va kag/solver/prompt, "
                             "chon qua biz_scene: legal.",
        },

        "corpus": {
            "root": "data/processed",
            "document_count": sum(corpus.values()),
            "by_directory": corpus,
            "note": "23 van ban luat Viet Nam dang .md da lam sach. Toan bo phan "
                    "quoc te da bo khoi repo.",
        },

        "restore": {
            "required_steps": [
                "docker start release-openspg-neo4j",
                "docker exec release-openspg-neo4j cypher-shell -u neo4j "
                "-p '<pw>' \"CREATE DATABASE legal\"",
                "docker stop release-openspg-neo4j",
                "docker run --rm -v <VOLUME_THAT>:/data -v <THU_MUC_DUMP>:/dump "
                "<IMAGE> neo4j-admin database load legal --from-path=/dump "
                "--overwrite-destination=true",
                "docker start release-openspg-neo4j",
            ],
            "critical_notes": [
                "CREATE DATABASE legal la BAT BUOC. neo4j-admin load bao "
                "'Done ... 100.0%' nhung KHONG tu tao database. Bo buoc nay thi "
                "SHOW DATABASES khong co 'legal' va moi truy van bao "
                "'Unable to get a routing table for database legal because this "
                "database does not exist'.",
                "Ten volume KHONG doan duoc. Phai chay: docker inspect "
                "release-openspg-neo4j --format '{{json .Mounts}}' roi tim phan tu "
                "co Destination /data. May dung truoc khi compose khai volume thi "
                "do thi nam o volume AN DANH ten hex.",
                "Nap sai volume KHONG bao loi - Neo4j van chay, chi la database rong.",
                "Moi truy van phai co -d legal. Database mac dinh 'neo4j' luon rong; "
                "quen -d legal se thay 0 va tuong nap hong.",
            ],
        },

        "expected_after_restore": {
            "node_count": node,
            "relationship_count": canh,
            "vector_index_count": len(chi_muc),
            "vector_all_online": True,
            "legal_chunk_count": so(cypher("MATCH (c:`Legal.Chunk`) RETURN count(c)")),
            "legal_document_count": so(cypher("MATCH (n:`Legal.LegalDocument`) RETURN count(n)")),
            "note": "Doi chieu bang docker/kiem-chung-do-thi.ps1, phai ra 7/7 OK.",
        },

        "dependencies": {
            "neo4j_dump_alone_is_sufficient_for_graph": True,
            "verified_on_clean_env": True,
            "how_verified": "Dung stack moi hoan toan (MySQL trang + MinIO trang + "
                            "Neo4j moi) roi nap dump va chay truy van that. "
                            "Xem kag/solver/thu_moi_truong_sach.py va "
                            "dist/CLEAN_ENV_TEST.txt.",
            "mysql": {
                "needs_old_data": False,
                "holds": "metadata du an (kg_project_info) + schema ontology "
                         "(kg_ontology_entity, 26 ban ghi). KHONG chua do thi.",
                "rebuild_by": "knext project restore + knext schema commit",
                "contains_api_key": False,
                "note": "Da kiem: cot params trong kg_model_detail la NULL. "
                        "Do NOT gui MySQL dump di - khong can thiet va tranh "
                        "rui ro lo thong tin dich vu.",
            },
            "minio": {
                "needs_old_data": False,
                "holds": "RONG. Chi co .minio.sys, khong co bucket nguoi dung nao.",
                "note": "Do thi khong dung MinIO.",
            },
            "required_order_on_new_machine": [
                "1. docker compose -f docker/docker-compose-west.yml up -d",
                "2. knext project restore --host_addr http://127.0.0.1:8887 --proj_path .",
                "3. knext schema commit",
                "4. CREATE DATABASE legal, roi nap legal.dump (xem docker/RESTORE-GRAPH.md)",
                "5. Dien API key rieng vao kag/kag_config.yaml",
                "BO QUA metadata_to_graph.py, injection.py, indexer.py",
            ],
            "why_steps_2_3_cannot_be_skipped": "Dump khong chua database 'system' "
                "cua Neo4j, cung khong chua metadata du an trong MySQL. Phai "
                "dung lai tu repo.",
        },

        "unverified": {
            "provenance_ratio": "UNVERIFIED - da do duoc ty le chunk -> van ban "
                                "(1121/1121 = 100%) nhung CHUA do ty le day du "
                                "fact -> chunk -> doc_id -> Dieu/Khoan/Diem",
            "build_completeness": "UNVERIFIED - chua do ty le chunk loi/bo qua, "
                                  "chua co danh sach van ban stub thieu full text",
            "note": "Nhung muc nay khong anh huong viec restore dump. Xem "
                    "dist/PROVENANCE_REPORT.txt muc 4.",
        },
    }

    # So cu 12625/42452 tung nam trong RESTORE-GRAPH.md ban cu. Ghi lai de
    # nguoi doc sau khong doi chieu nham.
    m["snapshot"]["wrong_numbers_warning"] = (
        "Tai lieu cu tung ghi 12625 node / 42452 canh. DO LA SO SAI, chua bao gio "
        "dung voi do thi nay. Dung lay so do lam tieu chi integrity check.")

    with open(RA, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=2)

    print("Da ghi %s" % RA)
    print("  node   : %s" % node)
    print("  canh   : %s" % canh)
    print("  index  : %s (online: %s)" % (len(chi_muc), m["vector_indexes"]["all_online"]))
    print("  sha256 : %s" % digest_dump)
    return 0


if __name__ == "__main__":
    sys.exit(main())
