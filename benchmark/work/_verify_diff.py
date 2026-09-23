import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('benchmark/work/final_150_candidate.json', 'r', encoding='utf-8') as f:
    cand = json.load(f)

with open('benchmark/work/final_150_corpus_verified.json', 'r', encoding='utf-8') as f:
    ver = json.load(f)

assert len(cand) == 150
assert len(ver) == 150

diffs = []
substantive_fields = ['question', 'category', 'answerable', 'gold_markers', 'gold_evidence']

for c, v in zip(cand, ver):
    qid = c['id']
    assert qid == v['id'], f"ID mismatch: {qid} != {v['id']}"
    if qid == 'Q097':
        # Check Q097 specifically
        assert v['question'] == c['question']
        assert v['category'] == c['category']
        assert v['answerable'] == c['answerable']
        assert v['source_id'] == c['source_id']
        assert len(v['gold_evidence']) == 2
        assert v['gold_evidence'][0]['article'] == '42' and v['gold_evidence'][0]['clause'] == '1'
        assert v['gold_evidence'][1]['article'] == '42' and v['gold_evidence'][1]['clause'] == '2'
        assert '01 tháng 01 năm 2026' in v['gold_markers']
        assert 'Nghị định số 13/2023/NĐ-CP' in v['gold_markers']
        assert 'hết hiệu lực kể từ ngày Nghị định này có hiệu lực thi hành' in v['gold_markers']
        print("Q097 repair verified correctly!")
    else:
        # Check all substantive fields are strictly identical
        for field in substantive_fields:
            if c[field] != v[field]:
                diffs.append((qid, field, c[field], v[field]))

if diffs:
    print(f"FAILED: Found unexpected diffs in {len(diffs)} fields:")
    for d in diffs:
        print(f"  {d[0]} [{d[1]}]:")
        print(f"    old: {d[2]}")
        print(f"    new: {d[3]}")
    sys.exit(1)
else:
    print("SUCCESS: All 149 other questions are 100% byte-equivalent on substantive fields!")
