# -*- coding: utf-8 -*-
"""
Kiem tra tu dong bo ban giao do thi (Graph Handoff Audit Test Suite).

Verifies all constraints from the user prompt:
1. Export and restore scripts are non-destructive (refuse overwrite, unique names, cleanup only own resources).
2. HANDOFF_MANIFEST contains dynamic commit, proven snapshot identity vs inferred build commit,
   vector index options recorded or UNKNOWN, hashes for schema/configs/corpus/metadata.
3. Image references pinned to recorded digest.
4. Clean environment claims mark full OpenSPG/KAG restoration as NOT YET VERIFIED.
5. Non-LLM integration check stops before paid retrieval and does not fake PASS.
6. Provenance limitations preserved without modifying graph.
"""

import hashlib
import json
import os
import subprocess
import sys
import pytest

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if GOC not in sys.path:
    sys.path.insert(0, GOC)

PINNED_DIGEST = (
    "spg-registry.us-west-1.cr.aliyuncs.com/spg/openspg-neo4j"
    "@sha256:4bc5b7f6b83d333b1d2c8f60ac145c068d77d50bca65b3a07c927f9e2a541eb9"
)


def test_export_script_non_destructive():
    p = os.path.join(GOC, "docker", "xuat-do-thi.ps1")
    assert os.path.exists(p)
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        code = f.read()

    # Image pinned
    assert PINNED_DIGEST in code
    assert "openspg-neo4j:latest" not in code

    # Refuse to overwrite existing nonempty destination
    assert "da ton tai va khong rong" in code
    assert "Tu choi ghi de" in code

    # Never delete existing dump before new dump is complete (dump into temp first)
    assert "dumpTamDir" in code
    assert "neo4j-data-tmp-" in code

    # Clean up only resources created by current invocation
    assert "finally" in code
    assert "Remove-Item $tam -Recurse -Force" in code
    assert "Remove-Item $dumpTamDir -Recurse -Force" in code


def test_restore_evidence_script_non_destructive():
    p = os.path.join(GOC, "docker", "bang-chung-restore.ps1")
    assert os.path.exists(p)
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        code = f.read()

    # Image pinned
    assert PINNED_DIGEST in code
    assert "openspg-neo4j:latest" not in code

    # Unique temporary container/volume
    assert "kag-handoff-tmp-$uId" in code or "kag-handoff-tmp-" in code
    assert "kag-handoff-verify-$uId" in code or "kag-handoff-verify-" in code

    # Mount dump read-only
    assert ":/dump:ro" in code


def test_clean_env_script_non_destructive():
    p = os.path.join(GOC, "kag", "solver", "thu_moi_truong_sach.py")
    assert os.path.exists(p)
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        code = f.read()

    # Image pinned
    assert PINNED_DIGEST in code
    assert "openspg-neo4j:latest" not in code

    # Unique temporary container/volume prefix
    assert "uuid.uuid4()" in code
    assert "PREFIX = f\"kag-clean-{UID}\"" in code or "kag-clean-" in code

    # Clean up only resources created by this invocation
    assert "CREATED_CONTAINERS" in code
    assert "CREATED_VOLUMES" in code
    assert "don()" in code

    # Mount dump read-only
    assert ":/dump:ro" in code

    # Explicitly marks full OpenSPG/KAG restoration as NOT YET VERIFIED
    assert "NOT YET VERIFIED" in code


def test_docker_compose_pinned():
    p = os.path.join(GOC, "docker", "docker-compose-west.yml")
    assert os.path.exists(p)
    with open(p, "r", encoding="utf-8") as f:
        code = f.read()
    assert PINNED_DIGEST in code


def test_handoff_manifest_integrity():
    p = os.path.join(GOC, "HANDOFF_MANIFEST.json")
    assert os.path.exists(p)
    with open(p, "r", encoding="utf-8") as f:
        m = json.load(f)

    # 1. Base commit recorded; no self-referential commit claiming its own commit SHA
    git_sec = m.get("git", {})
    assert git_sec.get("base_repo_commit") == "014782390dcfe18bd58ddd337652a1b5f8be93f1"
    assert "commit_current" not in git_sec or git_sec.get("commit_current") is None
    assert git_sec.get("commit_current_short") != "2707798"

    # Embedding constraint requires exact model, not just dimensions
    emb_sec = m.get("embedding", {})
    assert "DUNG model" in emb_sec.get("note_constraint", "") or "same model" in emb_sec.get("note_constraint", "").lower()

    # 2. Proven build snapshot identity distinguished from build code commit
    assert "proven_build_snapshot_identity" in m
    snapshot_id = m["proven_build_snapshot_identity"]
    assert snapshot_id["dump_sha256"] == "bb43903bad89f2902f23406918dbf1e97331a302ccd8af17086c8e74fa87e9e1"
    assert snapshot_id["node_count"] == 7624
    assert snapshot_id["relationship_count"] == 26029
    assert snapshot_id["vector_index_count"] == 36
    assert snapshot_id["legal_chunk_count"] == 1121
    assert snapshot_id["legal_document_count"] == 246
    assert snapshot_id["pinned_neo4j_image_digest"] == PINNED_DIGEST

    assert "build_code_commit" in m
    build_commit = m["build_code_commit"]
    assert build_commit["inferred_commit"] == "cb25997"
    assert "INFERRED_FROM_REPO_HISTORY" in build_commit["provenance_nature"]

    # 3. Vector indexes have options recorded or UNKNOWN
    indexes = m.get("vector_indexes", {}).get("indexes", [])
    assert len(indexes) == 36
    for idx in indexes:
        assert "options" in idx
        assert idx["options"] is not None

    # 4. Hashes for schema, configs, corpus, metadata
    assert "hashes" in m
    h = m["hashes"]
    assert "schema" in h
    assert "kag/schema/Legal.schema" in h["schema"]
    assert h["schema"]["kag/schema/Legal.schema"] is not None

    assert "configs" in h
    assert "kag/kag_config.example.yaml" in h["configs"]
    assert "docker/docker-compose-west.yml" in h["configs"]
    assert "data/graph/nodes.json" in h["configs"]

    assert "corpus" in h
    assert h["corpus"]["file_count"] == 23
    assert len(h["corpus"]["files"]) == 23
    assert len(h["corpus"]["composite_sha256"]) == 64

    assert "metadata" in h
    assert h["metadata"]["file_count"] == 37
    assert len(h["metadata"]["files"]) == 37
    assert len(h["metadata"]["composite_sha256"]) == 64

    # 5. Clean environment claims
    clean_ver = m.get("dependencies", {}).get("clean_environment_verification", {})
    assert clean_ver.get("neo4j_graph_restoration") == "VERIFIED"
    assert clean_ver.get("full_openspg_kag_restoration") == "NOT YET VERIFIED"

    # 6. Pinned image
    assert m["neo4j"]["image_digest"] == PINNED_DIGEST


def test_schema_validity():
    from kag.schema.check_schema import check
    schema_path = os.path.join(GOC, "kag", "schema", "Legal.schema")
    types, errs = check(schema_path)
    assert len(errs) == 0
    assert len(types) == 10


def test_integration_retrieval_guard():
    from kag.solver.kiem_tra_tich_hop_sach import kiem_tra_cau_hinh_retrieval
    can_run_free, report = kiem_tra_cau_hinh_retrieval()
    # Retrieval cannot run without paid API call
    assert can_run_free is False
    assert report["requires_paid_embedding"] is True
    assert "dg/text-embedding-3-large" in report["embedding_model"]
    assert "https://api.vilao.ai/v1" in report["embedding_gateway"]
    assert report["embedding_dimensions"] == 3072
    assert report["has_local_vectorizer"] is False


def test_provenance_report_limits_preserved():
    p = os.path.join(GOC, "dist", "PROVENANCE_REPORT.txt")
    assert os.path.exists(p)
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        nd = f.read()
    # Preserved limitations
    assert "218" in nd and "docNumber" in nd
    assert "91" in nd and "Article" in nd
    assert "554" in nd and "quan he" in nd
