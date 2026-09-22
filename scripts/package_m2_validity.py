# -*- coding: utf-8 -*-
"""Package M2 Validity Release Candidate into standardized zip artifact."""

import os
import sys
import zipfile
import hashlib
import time

WT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTIFACTS_DIR = os.path.abspath(os.path.join(WT_ROOT, "..", "artifacts"))
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

timestamp = time.strftime("%Y%m%d-%H%M%S")
zip_name = f"evidence-aware-m2-validity-{timestamp}.zip"
zip_path = os.path.join(ARTIFACTS_DIR, zip_name)
sha256_path = zip_path + ".sha256"

INCLUDE_DIRS = [
    os.path.join("kag", "solver", "evidence_aware"),
    "tests",
    "benchmark",
    "docs",
    "scripts",
]

INCLUDE_FILES = [
    "MANIFEST.json",
    "README.md",
    "requirements.txt",
]

print(f"Creating Release Candidate ZIP: {zip_path}")

with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
    for d in INCLUDE_DIRS:
        abs_d = os.path.join(WT_ROOT, d)
        if os.path.exists(abs_d):
            for root, dirs, files in os.walk(abs_d):
                dirs[:] = [dr for dr in dirs if dr not in ("__pycache__", ".pytest_cache", ".venv")]
                for file in files:
                    if file.endswith((".pyc", ".pyo")):
                        continue
                    full_p = os.path.join(root, file)
                    rel_p = os.path.relpath(full_p, WT_ROOT)
                    zf.write(full_p, rel_p)
                    print(f"  + {rel_p}")

    for f in INCLUDE_FILES:
        abs_f = os.path.join(WT_ROOT, f)
        if os.path.exists(abs_f):
            zf.write(abs_f, f)
            print(f"  + {f}")

sha256 = hashlib.sha256()
with open(zip_path, "rb") as f:
    while chunk := f.read(65536):
        sha256.update(chunk)
zip_hash = sha256.hexdigest()

with open(sha256_path, "w", encoding="utf-8") as f:
    f.write(f"{zip_hash}  {zip_name}\n")

print("\n=======================================================")
print(f"ZIP Created:   {zip_path}")
print(f"ZIP SHA-256:   {zip_hash}")
print(f"Checksum File: {sha256_path}")
print("=======================================================")
