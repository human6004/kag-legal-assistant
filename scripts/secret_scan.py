# -*- coding: utf-8 -*-
"""Secret Scanner for repository.

Scans all workspace files for API keys, private keys, and credentials.
"""

import os
import re
import sys

WT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PATTERNS = [
    (r"sk-[a-zA-Z0-9]{20,}", "OpenAI API Key"),
    (r"ghp_[a-zA-Z0-9]{36}", "GitHub Personal Access Token"),
    (r"gho_[a-zA-Z0-9]{36}", "GitHub OAuth Token"),
    (r"glpat-[a-zA-Z0-9\-]{20,}", "GitLab Personal Access Token"),
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
    (r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----", "Private Key"),
    (r"(?:api[_-]?key|secret[_-]?key|auth[_-]?token)\s*[:=]\s*['\"]([a-zA-Z0-9_\-]{20,})['\"]", "API/Secret Key Assignment"),
]

ALLOWLIST = [
    "<URL_GATEWAY_LLM>",
    "<TEN_MODEL_LLM>",
    "testonly",
    "FAKE",
    "TEST",
    "FORGED_TOKEN",
]


def scan():
    findings = []
    scanned_count = 0

    scan_dirs = ["kag", "tests", "benchmark", "docs", "scripts"]
    for d in scan_dirs:
        abs_d = os.path.join(WT_ROOT, d)
        if not os.path.exists(abs_d):
            continue
        for root, dirs, files in os.walk(abs_d):
            dirs[:] = [dr for dr in dirs if dr not in ("__pycache__", ".venv", ".git")]
            for file in files:
                if file.endswith((".pyc", ".pyo", ".zip", ".png", ".jpg")):
                    continue
                full_p = os.path.join(root, file)
                rel_p = os.path.relpath(full_p, WT_ROOT)
                scanned_count += 1

                try:
                    with open(full_p, "r", encoding="utf-8", errors="ignore") as f:
                        for line_no, line in enumerate(f, 1):
                            for pat, desc in PATTERNS:
                                m = re.search(pat, line, re.IGNORECASE)
                                if m:
                                    val = m.group(0)
                                    if any(al.lower() in val.lower() for al in ALLOWLIST):
                                        continue
                                    findings.append({
                                        "file": rel_p,
                                        "line": line_no,
                                        "type": desc,
                                        "match": val[:10] + "...",
                                    })
                except Exception as e:
                    pass

    print(f"Secret Scan Complete: {scanned_count} files scanned.")
    if findings:
        print(f"WARNING: {len(findings)} potential secrets found!")
        for f in findings:
            print(f"  - {f['file']}:{f['line']} ({f['type']}): {f['match']}")
        return 1
    else:
        print("PASS: 0 secrets detected. Repository clean.")
        return 0


if __name__ == "__main__":
    sys.exit(scan())
