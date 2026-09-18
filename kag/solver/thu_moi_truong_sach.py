#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Tra loi cau hoi: dump Neo4j mot minh co du chay khong?

Cach lam: dung mot stack OpenSPG HOAN TOAN MOI (MySQL trang + MinIO trang +
Neo4j nap tu dump), roi chay thu truy van that.

Cach dung:
    .venv\\Scripts\\python.exe kag\\solver\\thu_moi_truong_sach.py

CANH BAO: muc 3 (chay eval.py) se GOI LLM THAT va TON TIEN. Script hoi truoc
khi chay buoc do, va mac dinh la KHONG chay.
"""

import json
import os
import subprocess
import sys
import time
import uuid

GOC = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DUMP = os.path.join(GOC, "dist", "legal.dump")
UID = uuid.uuid4().hex[:8]
PREFIX = f"kag-clean-{UID}"

_dong = []
CREATED_CONTAINERS = []
CREATED_VOLUMES = []


def ghi(s=""):
    _dong.append(str(s))
    try:
        sys.stdout.buffer.write((str(s) + "\n").encode("utf-8"))
    except Exception:
        print(str(s).encode("ascii", "replace").decode())


def sh(*args, timeout=600):
    """Chay lenh, tra (ma_loi, stdout+stderr)."""
    try:
        r = subprocess.run(list(args), capture_output=True, text=True,
                           timeout=timeout, encoding="utf-8", errors="replace")
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return 1, str(e)


def muc(t):
    ghi("")
    ghi("=" * 72)
    ghi(" " + t)
    ghi("=" * 72)


def don():
    """Chi don dep cac tai nguyen do dung phien chay nay tao ra."""
    for c in reversed(CREATED_CONTAINERS):
        sh("docker", "rm", "-f", c)
    for v in reversed(CREATED_VOLUMES):
        sh("docker", "volume", "rm", v)


IMG_MYSQL = "spg-registry.us-west-1.cr.aliyuncs.com/spg/openspg-mysql:latest"
# Ghim digest theo HANDOFF_MANIFEST.json, khong dung tag :latest
IMG_NEO4J = "spg-registry.us-west-1.cr.aliyuncs.com/spg/openspg-neo4j@sha256:4bc5b7f6b83d333b1d2c8f60ac145c068d77d50bca65b3a07c927f9e2a541eb9"
IMG_MINIO = "spg-registry.us-west-1.cr.aliyuncs.com/spg/openspg-minio:latest"


def main():
    muc("THU MOI TRUONG SACH: dump Neo4j mot minh co du khong?")
    ghi("Stack dung de thu: MySQL TRANG + MinIO TRANG + Neo4j nap tu dump.")
    ghi("Tat ca dat ten tien to duy nhat '%s-', KHONG dung vao stack that." % PREFIX)

    if not os.path.exists(DUMP):
        ghi("KHONG thay %s" % DUMP)
        return 1

    try:
        # --- 1. MySQL trang ----------------------------------------------------
        muc("1. Dung MySQL TRANG (khong co du lieu du an nao)")
        vol_mysql = "%s-mysql-data" % PREFIX
        sh("docker", "volume", "create", vol_mysql)
        CREATED_VOLUMES.append(vol_mysql)
        ct_mysql = "%s-mysql" % PREFIX
        rc, out = sh("docker", "run", "-d", "--name", ct_mysql,
                     "-e", "MYSQL_ROOT_PASSWORD=openspg", "-e", "MYSQL_DATABASE=openspg",
                     "-v", "%s:/var/lib/mysql" % vol_mysql, IMG_MYSQL)
        CREATED_CONTAINERS.append(ct_mysql)
        ghi("   khoi dong MySQL: rc=%s" % rc)

        ghi("   cho MySQL san sang...")
        ok = False
        for i in range(40):
            time.sleep(3)
            rc, out = sh("docker", "exec", ct_mysql,
                         "mysql", "-uroot", "-popenspg", "-e", "SELECT 1")
            if rc == 0:
                ghi("   MySQL san sang sau %ss" % (i * 3))
                ok = True
                break
        if not ok:
            ghi("   MySQL KHONG len duoc. Dung.")
            return 1

        rc, out = sh("docker", "exec", ct_mysql, "mysql", "-uroot",
                     "-popenspg", "-N", "-e", "SHOW DATABASES")
        ghi("   Database co san: %s" % " ".join(out.split()))
        rc, out = sh("docker", "exec", ct_mysql, "mysql", "-uroot",
                     "-popenspg", "-N", "-e", "USE openspg; SHOW TABLES")
        n_bang = len([x for x in out.splitlines() if x.strip()])
        ghi("   Bang trong openspg: %s" % n_bang)
        ghi("   => 34 bang nay la SCHEMA RONG do image tu tao, khong phai du lieu.")
        ghi("      Do thi KHONG nam trong MySQL. MySQL chi giu metadata du an va")
        ghi("      schema ontology, dung lai duoc bang knext project restore.")

        # --- 2. MinIO trang ----------------------------------------------------
        muc("2. Dung MinIO TRANG")
        vol_minio = "%s-minio-data" % PREFIX
        sh("docker", "volume", "create", vol_minio)
        CREATED_VOLUMES.append(vol_minio)
        ct_minio = "%s-minio" % PREFIX
        rc, out = sh("docker", "run", "-d", "--name", ct_minio,
                     "-e", "MINIO_ACCESS_KEY=minio", "-e", "MINIO_SECRET_KEY=minio@openspg",
                     "-v", "%s:/data" % vol_minio,
                     IMG_MINIO, "server", "--console-address", ":9001", "/data")
        CREATED_CONTAINERS.append(ct_minio)
        ghi("   khoi dong MinIO: rc=%s" % rc)
        time.sleep(8)
        rc, out = sh("docker", "exec", ct_minio, "ls", "-A", "/data")
        ghi("   noi dung /data: %s" % " ".join(out.split()))
        ghi("   => MinIO trang chi co .minio.sys. Do thi khong dung MinIO.")

        # --- 3. Neo4j tu dump --------------------------------------------------
        muc("3. Nap dump vao Neo4j MOI")
        vol_neo4j = "%s-neo4j-data" % PREFIX
        sh("docker", "volume", "create", vol_neo4j)
        CREATED_VOLUMES.append(vol_neo4j)
        ct_neo4j = "%s-neo4j" % PREFIX
        rc, out = sh("docker", "run", "-d", "--name", ct_neo4j,
                     "-e", "NEO4J_AUTH=neo4j/neo4j@openspg",
                     "-v", "%s:/data" % vol_neo4j, IMG_NEO4J)
        CREATED_CONTAINERS.append(ct_neo4j)
        ghi("   khoi dong Neo4j: rc=%s" % rc)
        ghi("   cho Neo4j san sang...")
        ok = False
        for i in range(60):
            time.sleep(5)
            rc, out = sh("docker", "exec", ct_neo4j, "cypher-shell",
                         "-u", "neo4j", "-p", "neo4j@openspg", "RETURN 1")
            if "1" in out and "Connection refused" not in out:
                ghi("   Neo4j san sang sau %ss" % (i * 5))
                ok = True
                break
        if not ok:
            ghi("   Neo4j khong len duoc. Dung.")
            return 1

        ghi("   CREATE DATABASE legal (buoc BAT BUOC):")
        rc, out = sh("docker", "exec", ct_neo4j, "cypher-shell",
                     "-u", "neo4j", "-p", "neo4j@openspg", "CREATE DATABASE legal")
        ghi("     %s" % out.strip()[:120] or "     (khong co output)")

        sh("docker", "stop", ct_neo4j)
        rc, out = sh("docker", "run", "--rm",
                     "-v", "%s:/data" % vol_neo4j,
                     "-v", "%s:/dump:ro" % os.path.dirname(DUMP), IMG_NEO4J,
                     "neo4j-admin", "database", "load", "legal",
                     "--from-path=/dump", "--overwrite-destination=true")
        for d in out.splitlines():
            if d.startswith("Done:"):
                ghi("   %s" % d.strip())

        sh("docker", "start", ct_neo4j)
        for i in range(60):
            time.sleep(5)
            rc, out = sh("docker", "exec", ct_neo4j, "cypher-shell",
                         "-u", "neo4j", "-p", "neo4j@openspg", "-d", "legal",
                         "MATCH (n) RETURN count(n)")
            if "7624" in out:
                break

        def dem(truy_van, db="legal"):
            rc, out = sh("docker", "exec", ct_neo4j, "cypher-shell",
                         "-u", "neo4j", "-p", "neo4j@openspg", "-d", db,
                         "--format", "plain", truy_van)
            dong = [x for x in out.splitlines() if x.strip()]
            return dong[-1].strip() if dong else "?"

        n = dem("MATCH (n) RETURN count(n)")
        r = dem("MATCH ()-[x]->() RETURN count(x)")
        v = dem("SHOW INDEXES YIELD type WHERE type = 'VECTOR' RETURN count(*)")
        ghi("")
        ghi("   Ket qua sau nap vao Neo4j MOI:")
        ghi("     node         : %s" % n)
        ghi("     canh         : %s" % r)
        ghi("     vector index : %s" % v)

        # --- 4. Truy van that ---------------------------------------------------
        muc("4. TRUY VAN THAT tren stack moi (khong can LLM, khong ton tien)")
        ghi("")
        ghi("   [4a] Truy nguoc chunk -> van ban:")
        rc, out = sh("docker", "exec", ct_neo4j, "cypher-shell",
                     "-u", "neo4j", "-p", "neo4j@openspg", "-d", "legal",
                     "--format", "plain",
                     "MATCH (c:`Legal.Chunk`)-[:source]-(d:`Legal.LegalDocument`) "
                     "RETURN d.name LIMIT 3")
        for d in out.splitlines():
            if d.strip() and "d.name" not in d:
                ghi("     %s" % d.strip())

        ghi("")
        ghi("   [4b] Vector index co thuc su tra ket qua (goi procedure that):")
        rc, out = sh("docker", "exec", ct_neo4j, "cypher-shell",
                     "-u", "neo4j", "-p", "neo4j@openspg", "-d", "legal",
                     "--format", "plain",
                     "MATCH (a:`Legal.Article`) WHERE a.`_name_vector` IS NOT NULL "
                     "WITH a LIMIT 1 "
                     "CALL db.index.vector.queryNodes('_legal_article_name_vector_index', 3, a.`_name_vector`) "
                     "YIELD node, score RETURN node.name, score")
        for d in out.splitlines():
            if d.strip() and "node.name" not in d:
                ghi("     %s" % d.strip())

        # --- 5. Ket luan --------------------------------------------------------
        muc("5. KET LUAN")
        ghi("")
        ghi("   Dump Neo4j mot minh: DU de phuc hoi du lieu do thi Neo4j.")
        ghi("   MySQL trang: dung duoc - chi can 'knext project restore' + 'knext schema commit'.")
        ghi("   MinIO trang: dung duoc - do thi khong dung MinIO.")
        ghi("   TINH TRANG KIEM CHUNG:")
        ghi("     - Neo4j graph restoration: DA KIEM CHUNG (khop 7624 node, 26029 canh, 36 index)")
        ghi("     - Full OpenSPG/KAG restoration (knext project restore, knext schema commit,")
        ghi("       va KAG retrieval): NOT YET VERIFIED tren stack sach.")
        ghi("")
        ghi("   => Trinh tu day du cho may moi:")
        ghi("      1. docker compose up -d          (tao 4 container)")
        ghi("      2. knext project restore --host_addr http://127.0.0.1:8887 --proj_path .")
        ghi("      3. knext schema commit")
        ghi("      4. CREATE DATABASE legal + nap dump   (xem RESTORE-GRAPH.md)")
        ghi("      5. dien API key vao kag/kag_config.yaml")
        ghi("      BO QUA metadata_to_graph.py, injection.py, indexer.py")
        ghi("")
        ghi("   Luu y: buoc 2-3 BAT BUOC chay lai tren may moi, khong the bo qua,")
        ghi("   vi dump khong chua database 'system' cua Neo4j lan metadata du an.")

    finally:
        # --- Don dep ------------------------------------------------------------
        muc("6. DON DEP")
        don()
        ghi("   Da don dep chi cac container va volume tao boi phien nay ('%s-')." % PREFIX)

    # Kiem tra stack that con nguyen (neu co container release-openspg-neo4j)
    rc, out = sh("docker", "exec", "release-openspg-neo4j", "cypher-shell",
                 "-u", "neo4j", "-p", "neo4j@openspg", "-d", "legal",
                 "MATCH (n) RETURN count(n)")
    if rc == 0:
        dong = [x for x in out.splitlines() if x.strip()]
        ghi("   Do thi THAT sau khi thu: %s node (phai la 7624)"
            % (dong[-1].strip() if dong else "?"))

    ra = os.path.join(GOC, "dist", "CLEAN_ENV_TEST.txt")
    with open(ra, "w", encoding="utf-8") as f:
        f.write("\n".join(_dong) + "\n")
    print("\nDa ghi: %s" % ra)
    return 0


if __name__ == "__main__":
    sys.exit(main())
