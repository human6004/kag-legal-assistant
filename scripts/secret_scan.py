# -*- coding: utf-8 -*-
"""
Kiem tra an toan bi mat (Secret Scan) tren repository.

Quet cac mau key, token, credential trong tat ca cac file duoc track boi git
hoac cac file duoc sua doi.
"""

import os
import re
import subprocess
import sys

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PATTERNS = [
    (r"sk-[a-zA-Z0-9]{20,}", "OpenAI API Key"),
    (r"ghp_[a-zA-Z0-9]{36}", "GitHub Personal Access Token"),
    (r"gho_[a-zA-Z0-9]{36}", "GitHub OAuth Token"),
    (r"glpat-[a-zA-Z0-9\-]{20,}", "GitLab Personal Access Token"),
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
    (r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----", "Private Key"),
    (r"(?:api[_-]?key|secret[_-]?key|auth[_-]?token)\s*[:=]\s*['\"]([a-zA-Z0-9_\-]{20,})['\"]", "API/Secret Key Assignment"),
]

# Danh sach bo qua: cac placeholder hoac gia tri test duoc phep
ALLOWLIST = [
    "<URL_GATEWAY_LLM>",
    "<TEN_MODEL_LLM>",
    "<URL_DICH_VU_EMBEDDING>",
    "<TEN_MODEL_EMBEDDING>",
    "neo4j@openspg",
    "minio@openspg",
    "openspg",
    "testonly"
]


def get_tracked_and_modified_files():
    cmd = ["git", "-C", GOC, "ls-files"]
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    files = [f.strip() for f in r.stdout.splitlines() if f.strip()]

    cmd2 = ["git", "-C", GOC, "status", "--porcelain"]
    r2 = subprocess.run(cmd2, capture_output=True, text=True, errors="replace")
    for line in r2.stdout.splitlines():
        if len(line) > 3:
            f = line[3:].strip()
            if f not in files and os.path.isfile(os.path.join(GOC, f)):
                files.append(f)
    return files


def scan():
    files = get_tracked_and_modified_files()
    findings = []

    for rel_path in sorted(files):
        # Bo qua binary, dump, pyc
        if rel_path.endswith((".pyc", ".dump", ".png", ".jpg", ".idx", ".pack", ".rev")):
            continue

        full_path = os.path.join(GOC, rel_path)
        if not os.path.isfile(full_path):
            continue

        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception:
            continue

        for line_no, line in enumerate(lines, 1):
            for pat, desc in PATTERNS:
                matches = re.finditer(pat, line, re.IGNORECASE)
                for m in matches:
                    matched_str = m.group(0)
                    # Kiem tra allowlist
                    if any(al in line for al in ALLOWLIST):
                        continue
                    findings.append({
                        "file": rel_path,
                        "line": line_no,
                        "desc": desc,
                        "match": matched_str[:20] + "..." if len(matched_str) > 20 else matched_str
                    })

    return findings


if __name__ == "__main__":
    print(f"Bat dau quet bi mat tren {GOC}...")
    findings = scan()
    if findings:
        print(f"\n[CANH BAO] Phat hien {len(findings)} vi tri nghi van:")
        for f in findings:
            print(f"  {f['file']}:{f['line']} - {f['desc']}: {f['match']}")
        sys.exit(1)
    else:
        print("[OK] Khong phat hien secret, token hoac khoa API nao bi lo.")
        sys.exit(0)
