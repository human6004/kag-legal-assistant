#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Bao cao provenance + gioi han cua do thi da ban giao.

Chay o goc repo, Neo4j dang chay:
    .venv\\Scripts\\python.exe kag\\solver\\bao_cao_provenance.py

CHI DOC. Khong ghi vao Neo4j. Ket qua in ra man hinh va ghi vao
dist/PROVENANCE_REPORT.txt
"""

import json
import os
import subprocess
import sys

GOC = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RA = os.path.join(GOC, "dist", "PROVENANCE_REPORT.txt")

CT, MK, DB = "release-openspg-neo4j", "neo4j@openspg", "legal"

_dong = []


def ghi(s=""):
    _dong.append(s)
    # Console Windows mac dinh la cp1252, khong in duoc tieng Viet co dau
    # (vi du '\u1ecb'). Ghi ra stdout dang bytes UTF-8 de khong chet giua chung.
    try:
        sys.stdout.buffer.write((str(s) + "\n").encode("utf-8"))
    except (AttributeError, UnicodeEncodeError):
        print(str(s).encode("ascii", "replace").decode("ascii"))


def bang(truy_van, db=DB):
    """Cypher -> list cac list o, tach theo CSV chuan."""
    import csv
    import io
    try:
        r = subprocess.run(
            ["docker", "exec", CT, "cypher-shell", "-u", "neo4j", "-p", MK,
             "-d", db, "--format", "plain", truy_van],
            capture_output=True, text=True, timeout=180,
            encoding="utf-8", errors="replace")
    except Exception as e:
        return [["<loi: %s>" % e]]
    d = list(csv.reader(io.StringIO(r.stdout)))
    return [x for x in d[1:] if x] if len(d) > 1 else []


def mot(truy_van, db=DB):
    b = bang(truy_van, db)
    return b[0][0].strip() if b and b[0] else None


def muc(t):
    ghi("")
    ghi("=" * 72)
    ghi(" " + t)
    ghi("=" * 72)


# ---------------------------------------------------------------------------
muc("BAO CAO PROVENANCE VA GIOI HAN - DO THI KAG LEGAL")
ghi("Nguon: do truc tiep tu database 'legal' dang chay.")
ghi("Moi so lieu duoi day la DO DUOC, khong suy luan.")
ghi("Cac muc ghi UNVERIFIED nghia la CHUA DO, khong phai da do ra 0.")

# --- 1. Provenance chain ---------------------------------------------------
muc("1. DUONG TRUY NGUOC: relationship -> chunk -> van ban")

ghi("")
ghi("[1a] Cac loai quan he noi Chunk voi node khac (top 15):")
for h in bang("MATCH (c:`Legal.Chunk`)-[r]-(x) "
              "RETURN type(r) AS quan_he, labels(x)[0] AS nhan_dich, count(*) AS n "
              "ORDER BY n DESC LIMIT 15"):
    ghi("    %-28s -> %-22s %s" % (h[0], h[1], h[2]))

ghi("")
ghi("[1b] Chunk co noi duoc toi van ban khong?")
n_chunk = mot("MATCH (c:`Legal.Chunk`) RETURN count(c)")
n_noi = mot("MATCH (c:`Legal.Chunk`)-[]-(:`Legal.LegalDocument`) RETURN count(DISTINCT c)")
ghi("    tong chunk              : %s" % n_chunk)
ghi("    chunk noi toi van ban   : %s" % n_noi)
try:
    ty = 100.0 * int(n_noi) / int(n_chunk)
    ghi("    ty le                   : %.1f%%" % ty)
except Exception:
    ghi("    ty le                   : UNVERIFIED")

ghi("")
ghi("[1c] Vi du cu the: chunk va van ban chua chung (qua quan he 'source')")
for h in bang("MATCH (c:`Legal.Chunk`)-[:source]-(d:`Legal.LegalDocument`) "
              "RETURN c.name, d.name, d.docNumber LIMIT 3"):
    ghi("    chunk  : %s" % h[0])
    ghi("    van ban: %s  (docNumber: %s)"
        % (h[1], h[2] if len(h) > 2 and h[2] else "<khong co>"))
    ghi("")

ghi("")
ghi("[1d] Node trich xuat co noi ve chunk khong? (LLM extraction vs metadata)")
for nhan in ["Legal.Obligation", "Legal.ProhibitedAct", "Legal.Sanction",
             "Legal.Authority", "Legal.RegulatedEntity", "Legal.LegalTerm"]:
    t = mot("MATCH (n:`%s`) RETURN count(n)" % nhan)
    c = mot("MATCH (n:`%s`)-[]-(:`Legal.Chunk`) RETURN count(DISTINCT n)" % nhan)
    try:
        ghi("    %-24s tong %5s | noi toi chunk %5s | %.1f%%"
            % (nhan, t, c, 100.0 * int(c) / int(t)))
    except Exception:
        ghi("    %-24s tong %5s | noi toi chunk %5s" % (nhan, t, c))

# --- 2. Metadata bo sung thu cong ------------------------------------------
muc("2. PHAN BIET: LLM TRICH XUAT vs METADATA BO SUNG THU CONG")

ghi("")
ghi("Metadata (do nguoi viet, KHONG qua LLM):")
ghi("    nguon: data/metadata/*.json -> data/graph/nodes.json")
ghi("    nap bang: kag/builder/injection.py")
for h in bang("MATCH (n:`Legal.LegalDocument`) "
              "RETURN count(n) AS tong, "
              "count(n.dateEffective) AS co_ngay_hieu_luc, "
              "count(n.status) AS co_trang_thai, "
              "count(n.sourceUrl) AS co_nguon_url"):
    ghi("    LegalDocument tong        : %s" % h[0])
    ghi("    co dateEffective          : %s" % h[1])
    ghi("    co status (con het hieu luc): %s" % h[2])
    ghi("    co sourceUrl              : %s" % h[3])

ghi("")
ghi("Trich xuat bang LLM (khong co nguon nguoi kiem):")
for nhan in ["Legal.Obligation", "Legal.ProhibitedAct", "Legal.Sanction",
             "Legal.Article", "Legal.LegalTerm", "Legal.RegulatedEntity",
             "Legal.Authority", "Legal.Others"]:
    ghi("    %-24s %s" % (nhan, mot("MATCH (n:`%s`) RETURN count(n)" % nhan)))

# --- 3. Van de da biet ------------------------------------------------------
muc("3. CAC VAN DE DA BIET (chua sua)")

ghi("")
ghi("[3a] LegalDocument thieu docNumber (khong doi chieu duoc voi van ban goc):")
n_co = mot("MATCH (d:`Legal.LegalDocument`) WHERE d.docNumber IS NOT NULL RETURN count(d)")
n_khong = mot("MATCH (d:`Legal.LegalDocument`) WHERE d.docNumber IS NULL RETURN count(d)")
ghi("    246 node LegalDocument:")
ghi("      co docNumber    : %s" % n_co)
ghi("      THIEU docNumber : %s" % n_khong)
ghi("")
ghi("    Day la con so DO DUOC. Neu tai lieu nao noi '4 cap sinh doi' thi do la")
ghi("    uoc luong cu chua kiem chung, khong phai so do tu do thi nay.")

ghi("")
ghi("[3c] Node Article co ten 'tran' (chi la so dieu, khong kem ten van ban):")
n_article = mot("MATCH (n:`Legal.Article`) RETURN count(n)")
ghi("    Legal.Article tong      : %s" % n_article)
# Ten that bi mangled: '\u0110i\u1ec1u 4\\"" - co dau \\ dau va \\"" cuoi.
# Nen dem theo do dai: 'Ddieu N' = 8 ky tu, 'Ddieu NN' = 9. Ten day du thi dai hon.
n_8 = mot("MATCH (n:`Legal.Article`) WHERE size(n.name) <= 9 RETURN count(n)")
ghi("    ten tran 'Dieu N'/'Dieu NN': %s node" % n_8)
ghi("    Article ten day du      : %s node" % (int(n_article) - int(n_8) if n_8 else "?"))
ghi("")
ghi("    Vi du ten that (chu y dau \\ va \\\"\" bi dinh vao ten):")
for h in bang("MATCH (n:`Legal.Article`) WHERE size(n.name) <= 10 "
              "RETURN n.name ORDER BY n.name LIMIT 4"):
    ghi("      %s" % h[0])
for h in bang("MATCH (n:`Legal.Article`) RETURN n.name ORDER BY size(n.name) DESC LIMIT 2"):
    ghi("      %s" % h[0][:110])

ghi("")
ghi("[3d] Article co noi toi van ban va chunk khong?")
a_tong = mot("MATCH (n:`Legal.Article`) RETURN count(n)")
a_doc = mot("MATCH (n:`Legal.Article`)-[]-(:`Legal.LegalDocument`) RETURN count(DISTINCT n)")
a_chunk = mot("MATCH (n:`Legal.Article`)-[]-(:`Legal.Chunk`) RETURN count(DISTINCT n)")
ghi("    Article tong            : %s" % a_tong)
ghi("    noi toi van ban         : %s" % a_doc)
ghi("    noi toi chunk           : %s" % a_chunk)

ghi("")
ghi("[3e] Loai quan he bi bop meo boi to_camel_case:")
n_rt = mot("MATCH ()-[r]->() RETURN count(DISTINCT type(r))")
ghi("    tong so loai quan he    : %s" % n_rt)
r1 = mot("MATCH ()-[r]->() WITH type(r) AS t, count(*) AS n WHERE n = 1 RETURN count(t)")
ghi("    loai chi xuat hien 1 lan: %s loai" % r1)
ghi("")
ghi("    Vi du ten quan he bi bop meo (dang le phai la tieng Viet co dau):")
for h in bang("MATCH ()-[r]->() WITH type(r) AS t, count(*) AS n "
              "RETURN t, n ORDER BY n DESC LIMIT 12"):
    if h[0] in ("source", "OfficialName"):
        continue
    if any(c.isupper() for c in h[0][1:]):
        ghi("      %-24s %s lan" % (h[0], h[1]))

# --- 4. Chua do duoc --------------------------------------------------------
muc("4. CHUA DO DUOC - GHI UNVERIFIED")

ghi("")
ghi("    Ty le provenance day du (fact -> chunk -> doc_id -> Dieu/Khoan/Diem)")
ghi("        : UNVERIFIED")
ghi("    Ty le chunk loi / bi bo qua khi build")
ghi("        : UNVERIFIED")
ghi("    Danh sach van ban stub thieu full text")
ghi("        : UNVERIFIED")
ghi("    So chunk bi LLM tra ve rong nhung van bao thanh cong")
ghi("        : UNVERIFIED")
ghi("")
ghi("    Nhung muc nay KHONG anh huong viec restore dump. Chung chi co nghia")
ghi("    khi danh gia chat luong do thi lam baseline nghien cuu.")

# --- Ket ---------------------------------------------------------------------
muc("KET")
ghi("")
ghi("Do thi restore duoc va provenance co ban con nguyen: chunk -> van ban.")
ghi("Phan chua do duoc ghi ro o muc 4, khong suy dien thanh so.")

os.makedirs(os.path.dirname(RA), exist_ok=True)
with open(RA, "w", encoding="utf-8") as f:
    f.write("\n".join(_dong) + "\n")
print("\nDa ghi: %s" % RA)
