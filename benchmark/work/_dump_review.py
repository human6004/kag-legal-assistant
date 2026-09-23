# -*- coding: utf-8 -*-
import json
from pathlib import Path

rep = json.loads(Path("benchmark/work/_match_report.json").read_text(encoding="utf-8"))
flagged, clean = [], []
for it in rep["items"]:
    (flagged if it["flags"] else clean).append(it)


def block(it, full):
    lines = []
    lines.append("=" * 78)
    lines.append(
        "%s [%s] flags=%s"
        % (it["legacy_id"], it["nhom"], ",".join(it["flags"]) or "CLEAN")
    )
    lines.append(
        "docs=%s cited=%s common=%s"
        % (it["source_doc_ids"], it["cited_articles"], it["common_articles"])
    )
    lines.append("Q: " + it["question"])
    lines.append("A: " + " || ".join(it["answers"]))
    if full:
        for m in it["markers"]:
            if m["kind"] != "substantive":
                lines.append("  [%s] %s" % (m["kind"], m["text"]))
                continue
            lines.append("  MARKER: " + m["text"])
            lines.append(
                "    in_source=%s loose=%s header=%s other=%s n=%s"
                % (
                    m.get("in_source_articles"),
                    m.get("loose_only_in_source"),
                    m.get("header_hit"),
                    m.get("corpus_hits_if_absent"),
                    m.get("n_corpus_verbatim"),
                )
            )
            w = m.get("window")
            if w:
                lines.append(
                    "    WIN %s Dieu %s k=%s d=%s chars=%s | %s"
                    % (
                        w["doc_id"],
                        w["article"],
                        w["clause"],
                        w["point"],
                        w["article_chars"],
                        w["heading"][:90],
                    )
                )
                lines.append("    SNIP: " + (w.get("snippet") or "")[:400])
    else:
        # one window is enough for spot checks
        for m in it["markers"]:
            w = m.get("window")
            if not w:
                continue
            lines.append(
                "  @%s Dieu %s (%s ch) %s"
                % (w["doc_id"], w["article"], w["article_chars"], (w.get("snippet") or "")[:220])
            )
            break
    return "\n".join(lines)


Path("benchmark/work/_review_flagged.txt").write_text(
    "\n".join(block(it, True) for it in flagged), encoding="utf-8"
)
Path("benchmark/work/_review_clean.txt").write_text(
    "\n".join(block(it, False) for it in clean), encoding="utf-8"
)
print("flagged", len(flagged), "clean", len(clean))
