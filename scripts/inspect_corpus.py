# -*- coding: utf-8 -*-
"""Inspect real legal corpus metadata and files in kag-legal-assistant/data."""

import os
import json

BASE_DATA = os.environ.get("KAG_DATA_DIR") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
META_DIR = os.path.join(BASE_DATA, "metadata")
PROC_DIR = os.path.join(BASE_DATA, "processed")

print(f"{'Doc ID':<20} | {'Type':<12} | {'Status':<12} | {'MD File':<35} | Title")
print("-" * 110)

for f in sorted(os.listdir(META_DIR)):
    if f.endswith(".json") and not f.startswith("_"):
        p = os.path.join(META_DIR, f)
        with open(p, "r", encoding="utf-8") as fp:
            d = json.load(fp)
            doc_id = d.get("doc_id") or f.replace(".json", "")
            doc_type = d.get("doc_type", "N/A")
            status = d.get("status") or d.get("validity_status", "VALID")
            title = d.get("title") or d.get("document_name", "")

            # Find matching markdown file
            md_match = "MISSING"
            for root, dirs, files in os.walk(PROC_DIR):
                for mf in files:
                    if doc_id in mf and mf.endswith(".md"):
                        md_match = mf[:35]
                        break

            print(f"{doc_id:<20} | {doc_type:<12} | {status:<12} | {md_match:<35} | {title[:35]}")
