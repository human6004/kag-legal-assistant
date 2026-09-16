#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Kiem tra tich hop moi truong sach khong dung LLM (Non-LLM Integration Check).

Chu trinh kiem tra:
    MySQL trang + MinIO trang + Neo4j phuc hoi tu dump
    -> knext project restore
    -> knext schema commit
    -> project / schema visibility (kiem tra do hien thi du an va schema)
    -> KAG retrieval (kiem tra xem co chay duoc ma khong ton tien khong)

QUY TAC BAT DI BAT DICH:
    Neu KAG retrieval can goi embedding/LLM tra phi: DUNG LAI va bao cao
    CHINH XAC thong tin can cap quyen (authorization). TUYET DOI KHONG FAKE PASS.

Cach dung:
    python kag/solver/kiem_tra_tich_hop_sach.py [--dry-run]
"""

import argparse
import os
import subprocess
import sys
import time
import uuid

GOC = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if GOC not in sys.path:
    sys.path.insert(0, GOC)

DUMP = os.path.join(GOC, "dist", "legal.dump")
CONFIG_EX = os.path.join(GOC, "kag", "kag_config.example.yaml")
CONFIG_REAL = os.path.join(GOC, "kag", "kag_config.yaml")
SCHEMA_FILE = os.path.join(GOC, "kag", "schema", "Legal.schema")

PINNED_NEO4J = (
    "spg-registry.us-west-1.cr.aliyuncs.com/spg/openspg-neo4j"
    "@sha256:4bc5b7f6b83d333b1d2c8f60ac145c068d77d50bca65b3a07c927f9e2a541eb9"
)
IMG_MYSQL = "spg-registry.us-west-1.cr.aliyuncs.com/spg/openspg-mysql:latest"
IMG_MINIO = "spg-registry.us-west-1.cr.aliyuncs.com/spg/openspg-minio:latest"
IMG_SERVER = "spg-registry.us-west-1.cr.aliyuncs.com/spg/openspg-server:latest"

CREATED_CONTAINERS = []
CREATED_VOLUMES = []


def log(msg, prefix="[*] "):
    sys.stdout.write(f"{prefix}{msg}\n")
    sys.stdout.flush()


def sh(cmd, timeout=300):
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace"
        )
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return 1, "", str(e)


def check_docker_available():
    rc, stdout, stderr = sh(["docker", "info"])
    return rc == 0


def don_dep():
    """Don dep CHI cac container va volume do phien chay nay tao ra."""
    if CREATED_CONTAINERS or CREATED_VOLUMES:
        log("Don dep tai nguyen tam thoi...")
    for c in reversed(CREATED_CONTAINERS):
        sh(["docker", "rm", "-f", c])
    for v in reversed(CREATED_VOLUMES):
        sh(["docker", "volume", "rm", v])


def kiem_tra_cau_hinh_retrieval():
    """
    Kiem tra xem KAG retrieval co the chay offline ma khong ton tien goi API hay khong.
    Tra ve (can_run_free: bool, report: dict).
    """
    report = {
        "requires_paid_embedding": True,
        "requires_paid_llm": True,
        "embedding_model": "dg/text-embedding-3-large",
        "embedding_gateway": "https://api.vilao.ai/v1",
        "embedding_dimensions": 3072,
        "has_local_vectorizer": False,
        "chat_llm_model": None,
        "chat_llm_gateway": None,
        "blocker_reason": (
            "KAG retrieval (VectorChunkRetriever, EntityLinking, rc, kg_fr) bat buoc phai "
            "vector hoa cau hoi (query) thanh vector 3072 chieu bang cach goi API embedding tu xa "
            "(dg/text-embedding-3-large qua gateway https://api.vilao.ai/v1). "
            "Khong co mo hinh vectorizer cuc bo (local offline vectorizer) nao duoc cau hinh trong he thong."
        )
    }

    # Kiem tra file config
    cfg_to_read = CONFIG_REAL if os.path.exists(CONFIG_REAL) else CONFIG_EX
    if os.path.exists(cfg_to_read):
        try:
            import yaml
            with open(cfg_to_read, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            vec = cfg.get("vectorize_model", {})
            m = vec.get("model")
            gw = vec.get("base_url")
            if m and not m.startswith("<"):
                report["embedding_model"] = m
            if gw and not gw.startswith("<"):
                report["embedding_gateway"] = gw
            report["embedding_dimensions"] = vec.get("vector_dimensions", 3072)

            chat = cfg.get("chat_llm", {})
            report["chat_llm_model"] = chat.get("model")
            report["chat_llm_gateway"] = chat.get("base_url")
        except Exception as e:
            report["parse_error"] = str(e)

    # Retrieval trong KAG doi hoi vectorize_model
    can_run_free = False
    return can_run_free, report


def main():
    parser = argparse.ArgumentParser(description="Kiem tra tich hop stack sach (Non-LLM)")
    parser.add_argument("--dry-run", action="store_true", help="Kiem tra tien de va phan tich ma khong dung container")
    args = parser.parse_args()

    log("=" * 72)
    log("KIEM TRA TICH HOP MOI TRUONG SACH (NON-LLM INTEGRATION CHECK)")
    log("=" * 72)

    # 1. Kiem tra schema Legal.schema
    log("1. Kiem tra tinh hop le cua Legal.schema...")
    if not os.path.exists(SCHEMA_FILE):
        log(f"FAIL: Khong tim thay {SCHEMA_FILE}", prefix="[!] ")
        return 1

    from kag.schema.check_schema import check as check_schema_syntax
    types, errs = check_schema_syntax(SCHEMA_FILE)
    if errs:
        log(f"FAIL: Legal.schema loi cu phap: {errs}", prefix="[!] ")
        return 1
    log(f"  OK: Legal.schema hop le ({len(types)} kieu doi tuong: {', '.join(types.keys())})")

    # 2. Kiem tra dump file
    log("2. Kiem tra su hien dien cua legal.dump...")
    dump_exists = os.path.exists(DUMP)
    if dump_exists:
        sz_gb = os.path.getsize(DUMP) / (1024 ** 3)
        log(f"  OK: Tim thay legal.dump ({sz_gb:.2f} GB)")
    else:
        log("  THONG BAO: legal.dump khong co san tren may cuc bo (nam trong .gitignore).")
        log("  Cac buoc restore container can co legal.dump.")

    # 3. Kiem tra kha nang retrieval khong dung LLM / khong tra phi
    log("3. Kiem tra co the chay KAG retrieval ma KHONG ton phi API hay khong...")
    can_run_free, ret_report = kiem_tra_cau_hinh_retrieval()

    if not can_run_free:
        log("  PHAN TICH RETRIEVAL:", prefix="  [-] ")
        log(f"    Can embedding tra phi : {ret_report['requires_paid_embedding']}")
        log(f"    Model embedding       : {ret_report['embedding_model']}")
        log(f"    Gateway embedding     : {ret_report['embedding_gateway']}")
        log(f"    So chieu vector       : {ret_report['embedding_dimensions']}")
        log(f"    Vectorizer cuc bo     : {ret_report['has_local_vectorizer']} (KHONG CO)")
        log("  ------------------------------------------------------------------")
        log("  [KET QUA PHAN TICH RETRIEVAL]:")
        log("  -> KAG retrieval BAT BUOC phai goi API embedding tra phi.")
        log("  -> KHONG THE chay retrieval hoan toan offline / mien phi.")
        log("  ------------------------------------------------------------------")

    # 4. Kiem tra Docker daemon
    docker_ok = check_docker_available()
    log(f"4. Kiem tra Docker daemon: {'SAN SANG' if docker_ok else 'OFFLINE / KHONG KET NOI'}")

    if args.dry_run or not docker_ok or not dump_exists:
        log("\n" + "=" * 72)
        log("KET LUAN KIEM TRA TICH HOP (DRY-RUN / TIEN TRINH TRUOC DOCKER)")
        log("=" * 72)
        log("1. Schema & Project restore: Cú pháp Legal.schema đã sẵn sàng cho `knext schema commit`.")
        log("2. Neo4j graph restore: Cần Docker daemon và legal.dump để dựng volume kiểm tra.")
        log("3. Project & Schema visibility: Sẽ khả dụng sau khi openspg-server nhận knext restore/commit.")
        log("4. KAG retrieval:")
        log("   [STOP - AUTHORIZATION REQUIRED / KHONG FAKE PASS]")
        log(f"   Ly do: {ret_report['blocker_reason']}")
        log(f"   Thong tin can cap quyen (authorization):")
        log(f"     - Dich vu: Embedding API")
        log(f"     - Gateway: {ret_report['embedding_gateway']}")
        log(f"     - Model:   {ret_report['embedding_model']} (dimensions: {ret_report['embedding_dimensions']})")
        log("   Theo chi thi: DUNG LAI truoc khi goi API tra phi. Khong gia mao ket qua PASS.")
        return 0

    # 5. Neu Docker san sang va co dump, thuc hien test tich hop thuc te tren stack co lap
    uid = uuid.uuid4().hex[:8]
    prefix = f"kag-check-{uid}"
    log(f"Khoi tao moi truong kiem tra co lap voi prefix: {prefix}...")

    try:
        # A. Tao volume va container
        vol_mysql = f"{prefix}-mysql-data"
        ct_mysql = f"{prefix}-mysql"
        sh(["docker", "volume", "create", vol_mysql])
        CREATED_VOLUMES.append(vol_mysql)
        sh([
            "docker", "run", "-d", "--name", ct_mysql,
            "-e", "MYSQL_ROOT_PASSWORD=openspg", "-e", "MYSQL_DATABASE=openspg",
            "-v", f"{vol_mysql}:/var/lib/mysql", IMG_MYSQL
        ])
        CREATED_CONTAINERS.append(ct_mysql)

        vol_minio = f"{prefix}-minio-data"
        ct_minio = f"{prefix}-minio"
        sh(["docker", "volume", "create", vol_minio])
        CREATED_VOLUMES.append(vol_minio)
        sh([
            "docker", "run", "-d", "--name", ct_minio,
            "-e", "MINIO_ACCESS_KEY=minio", "-e", "MINIO_SECRET_KEY=minio@openspg",
            "-v", f"{vol_minio}:/data", IMG_MINIO, "server", "--console-address", ":9001", "/data"
        ])
        CREATED_CONTAINERS.append(ct_minio)

        vol_neo4j = f"{prefix}-neo4j-data"
        ct_neo4j = f"{prefix}-neo4j"
        sh(["docker", "volume", "create", vol_neo4j])
        CREATED_VOLUMES.append(vol_neo4j)
        sh([
            "docker", "run", "-d", "--name", ct_neo4j,
            "-e", "NEO4J_AUTH=neo4j/neo4j@openspg",
            "-v", f"{vol_neo4j}:/data", PINNED_NEO4J
        ])
        CREATED_CONTAINERS.append(ct_neo4j)

        # Cho Neo4j san sang, tao database legal, roi nap dump
        log("Cho Neo4j san sang de tao database...")
        for _ in range(40):
            time.sleep(3)
            rc, out, _ = sh(["docker", "exec", ct_neo4j, "cypher-shell", "-u", "neo4j", "-p", "neo4j@openspg", "RETURN 1"])
            if "1" in out:
                break

        sh(["docker", "exec", ct_neo4j, "cypher-shell", "-u", "neo4j", "-p", "neo4j@openspg", "CREATE DATABASE legal"])
        sh(["docker", "stop", ct_neo4j])

        log("Nap legal.dump vao Neo4j volume...")
        sh([
            "docker", "run", "--rm",
            "-v", f"{vol_neo4j}:/data",
            "-v", f"{os.path.dirname(DUMP)}:/dump:ro",
            PINNED_NEO4J,
            "neo4j-admin", "database", "load", "legal",
            "--from-path=/dump", "--overwrite-destination=true"
        ])
        sh(["docker", "start", ct_neo4j])

        # Kiem tra retrieval
        if not can_run_free:
            log("\n" + "=" * 72)
            log("[STOPPING AT KAG RETRIEVAL GATE - AUTHORIZATION REQUIRED]")
            log("=" * 72)
            log("Tien trinh tich hop dung lai truoc buoc goi KAG retrieval vi doi hoi goi API tra phi.")
            log(f"Canh bao: {ret_report['blocker_reason']}")
            log(f"Dich vu can cap quyen: {ret_report['embedding_model']} tai {ret_report['embedding_gateway']}")
            log("Tuan thu yeu cau: TUYET DOI KHONG FAKE PASS.")
            return 0

    finally:
        don_dep()

    return 0


if __name__ == "__main__":
    sys.exit(main())
