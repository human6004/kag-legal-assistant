import json
import sys
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')

with open('benchmark/work/final_150_corpus_verified.json', 'r', encoding='utf-8') as f:
    dataset = json.load(f)

# Rule 1: Total = 150
assert len(dataset) == 150, f"Expected 150 items, got {len(dataset)}"
print("[CHECK PASS] Total items: 150")

# Rule 2: IDs Q001-Q150 consecutive
ids = [x['id'] for x in dataset]
expected_ids = [f"Q{i:03d}" for i in range(1, 151)]
assert ids == expected_ids, "IDs are not Q001-Q150 consecutive"
print("[CHECK PASS] IDs Q001-Q150 consecutive: True")

# Rule 3: Category distribution
expected_cats = {
    'definition': 20,
    'obligation': 25,
    'sanction_numeric': 25,
    'effectiveness_metadata': 20,
    'inter_document': 20,
    'multi_hop': 25,
    'unanswerable': 15
}
cat_counts = Counter(x['category'] for x in dataset)
assert cat_counts == expected_cats, f"Category mismatch: {cat_counts} vs {expected_cats}"
print("[CHECK PASS] Category distribution:", dict(cat_counts))

# Rule 4: Answerability 135 true, 15 false
ans_counts = Counter(x['answerable'] for x in dataset)
assert ans_counts[True] == 135 and ans_counts[False] == 15, f"Answerability mismatch: {ans_counts}"
print(f"[CHECK PASS] Answerability: {ans_counts[True]} True, {ans_counts[False]} False")

# Rule 5: Answerable & Unanswerable evidence/markers constraints
for x in dataset:
    qid = x['id']
    if x['answerable']:
        assert len(x['gold_evidence']) > 0, f"{qid} is answerable but gold_evidence is empty"
        assert len(x['gold_markers']) > 0, f"{qid} is answerable but gold_markers is empty"
    else:
        assert len(x['gold_evidence']) == 0, f"{qid} is unanswerable but gold_evidence is not empty"
        assert len(x['gold_markers']) == 0, f"{qid} is unanswerable but gold_markers is not empty"
print("[CHECK PASS] Answerable/Unanswerable evidence and markers constraints verified")

# Rule 6: Hierarchy: point_without_clause = 0
pt_without_cl = []
for x in dataset:
    for ev in x.get('gold_evidence', []):
        if ev.get('point') is not None and ev.get('clause') is None:
            pt_without_cl.append((x['id'], ev))
assert len(pt_without_cl) == 0, f"Found point without clause: {pt_without_cl}"
print("[CHECK PASS] point_without_clause count: 0")

# Rule 7: Forbidden fields
forbidden_fields = ['chunk_id', 'node_id', 'vector_id', 'candidate_hits', 'kag_id', 'hybrid_id', 'nativerag_id']
for x in dataset:
    for k in forbidden_fields:
        assert k not in x, f"Forbidden field '{k}' found in {x['id']}"
    for ev in x.get('gold_evidence', []):
        for k in forbidden_fields:
            assert k not in ev, f"Forbidden field '{k}' found in evidence of {x['id']}"
print("[CHECK PASS] Forbidden fields check (chunk_id, node_id, vector_id, candidate_hits, etc.): 0 found")

# Rule 8: Q097 check
q097 = next(x for x in dataset if x['id'] == 'Q097')
assert len(q097['gold_evidence']) == 2, f"Q097 must have 2 evidence legs, got {len(q097['gold_evidence'])}"
ev_clauses = [e.get('clause') for e in q097['gold_evidence']]
assert '1' in ev_clauses and '2' in ev_clauses, f"Q097 must have clause 1 and clause 2, got {ev_clauses}"
assert any('01 tháng 01 năm 2026' in m for m in q097['gold_markers']), "Q097 markers must contain '01 tháng 01 năm 2026'"
print("[CHECK PASS] Q097 has D42 clause 1, D42 clause 2, and marker '01 tháng 01 năm 2026'")

# Rule 9: B2_5_CORPUS_CLOSURE.json verification
with open('benchmark/work/B2_5_CORPUS_CLOSURE.json', 'r', encoding='utf-8') as f:
    closure_items = json.load(f)

assert len(closure_items) == 15, f"Expected 15 closure items, got {len(closure_items)}"
expected_keys = {'id', 'source_id', 'corpus_status', 'corpus_file', 'verified_location', 'checks', 'notes'}
expected_checks_keys = {'document', 'article', 'clause', 'point', 'evidence', 'question_supported', 'markers_supported'}
allowed_statuses = {'CORPUS_READY', 'CORPUS_REPAIR', 'CORPUS_BLOCKER'}

for it in closure_items:
    qid = it['id']
    assert set(it.keys()) == expected_keys, f"{qid} invalid keys: {it.keys()}"
    assert it['corpus_status'] in allowed_statuses, f"{qid} invalid status: {it['corpus_status']}"
    assert set(it['checks'].keys()) == expected_checks_keys, f"{qid} invalid check keys: {it['checks'].keys()}"
    # All checks that are not None must be True
    for ck, cv in it['checks'].items():
        if cv is not None:
            assert cv is True, f"{qid} check {ck} is {cv}"
print("[CHECK PASS] B2_5_CORPUS_CLOSURE.json has 15 valid records matching exact schema")

print("\nALL VALIDATION RULES PASSED SUCCESSFULLY!")
