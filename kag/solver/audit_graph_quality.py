"""Read-only graph audit. Run from repo root; writes a NEW evidence directory.

No imports from the builder (which has monkey-patch side effects).
"""
import argparse
import hashlib
import json
import os
import csv
import re
import sqlite3
import pickle
import io
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]


def decode(value):
    # OpenSPG stored JSON string literals in Neo4j string properties.
    if isinstance(value, str) and value.startswith('"'):
        try:
            return json.loads(value)
        except ValueError:
            pass
    return value


def norm(value):
    return ' '.join(re.sub(r'[^\w\s]', ' ', unicodedata.normalize('NFC', str(value)).lower()).split())


class CacheObject:
    pass


class DataOnlyUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if module == 'kag.interface.common.model.sub_graph' and name in {'SubGraph', 'Node', 'Edge'}:
            return CacheObject
        raise pickle.UnpicklingError(f'Unexpected checkpoint class: {module}.{name}')


def load_checkpoint():
    directory = ROOT / 'kag/ckpt/LegalSchemaFreeExtractor'
    db = directory / 'cache.db'
    chunks, edge_chunks, node_chunks = {}, defaultdict(set), defaultdict(set)
    records, empty = 0, 0
    with sqlite3.connect(db.as_uri() + '?mode=ro', uri=True) as conn:
        for key, mode, filename, value in conn.execute('SELECT key,mode,filename,value FROM Cache'):
            records += 1
            if mode != 4:
                raise ValueError(f'Unexpected cache mode {mode}')
            if filename:
                path = (directory / filename).resolve()
                if not path.is_relative_to(directory.resolve()):
                    raise ValueError('Checkpoint filename outside cache')
                value = path.read_bytes()
            graphs = DataOnlyUnpickler(io.BytesIO(value)).load()
            if not graphs:
                empty += 1
            for graph in graphs:
                chunk_nodes = [n for n in graph.nodes if n.label.split('.')[-1] == 'Chunk']
                for c in chunk_nodes:
                    chunks[c.id] = {'name': c.name, 'props': c.properties, 'cache_key': key}
                ids = {c.id for c in chunk_nodes}
                for n in graph.nodes:
                    node_chunks[(n.label.split('.')[-1], n.id)].update(ids)
                for e in graph.edges:
                    edge_chunks[(e.from_type.split('.')[-1], e.from_id, e.label,
                                 e.to_type.split('.')[-1], e.to_id)].update(ids)
    return chunks, edge_chunks, node_chunks, {'records': records, 'empty_records': empty,
                                            'sha256': sha256(db)}


def write_csv(path, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                             for k, v in row.items()})


def analyze(out):
    nodes = json.loads((out / 'nodes.json').read_text(encoding='utf-8'))
    edges = json.loads((out / 'edges.json').read_text(encoding='utf-8'))
    for n in nodes:
        n['props'] = {k: decode(v) for k, v in n['props'].items()}
        n['label'] = next(l.split('.')[-1] for l in n['labels'] if l.startswith('Legal.'))
    by_eid = {n['eid']: n for n in nodes}
    chunks = {n['props']['id']: n for n in nodes if n['label'] == 'Chunk'}
    docs = [n for n in nodes if n['label'] == 'LegalDocument']
    source = defaultdict(set)
    aliases = defaultdict(set)
    for e in edges:
        a, b = by_eid[e['source']], by_eid[e['target']]
        if e['type'] == 'source' and b['label'] == 'Chunk':
            source[a['eid']].add(b['props']['id'])
        if e['type'] == 'OfficialName':
            aliases[a['eid']].add(b['eid'])
            aliases[b['eid']].add(a['eid'])
    ck, ec, nc, cache_info = load_checkpoint()
    def node_key(n):
        return n['label'], n['props']['id']
    def edge_key(e):
        a, b = by_eid[e['source']], by_eid[e['target']]
        return (*node_key(a), e['type'], *node_key(b))
    metas = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((ROOT / 'data/metadata').glob('*.json'))
             if not p.name.startswith('_')]
    processed = {}
    for p in sorted((ROOT / 'data/processed').rglob('*.md')):
        text = p.read_text(encoding='utf-8')
        processed[str(p.relative_to(ROOT))] = text
    # Exact document heading matches only; a citation to another document is not ownership.
    headings = defaultdict(list)
    for path, text in processed.items():
        headings[norm(text.splitlines()[0].lstrip('# '))].append(path)
    chunk_rows, chunk_context = [], {}
    for cid, n in chunks.items():
        name = n['props'].get('name', '')
        head = name.split(' / ')[0]
        paths = headings.get(norm(head), [])
        own_metas = [m for m in metas if paths and any(Path(p).name.startswith(m.get('doc_id', '?') + '_') for p in paths)]
        article = re.findall(r'(?:^| / )Điều\s+(\d+[a-zđ]?)\.', name, flags=re.I)
        content = n['props'].get('content', '')
        payload = content[len(name):].lstrip() if content.startswith(name) else content
        # Whitespace-only normalization. No word deletion, paraphrase, or fuzzy matching.
        compact = lambda s: re.sub(r'\s+', ' ', s).strip()
        matches = [p for p in paths if payload and compact(payload) in compact(processed[p])]
        checkpoint_equal = cid in ck and ck[cid]['props'].get('content') == content
        row = {'chunk_id': cid, 'name': name, 'document_ids': sorted({m['doc_id'] for m in own_metas}),
               'processed_paths': paths, 'article_heading': article,
               'payload_matches_processed': matches, 'checkpoint_content_equal': checkpoint_equal}
        chunk_rows.append(row)
        chunk_context[cid] = row
    write_csv(out / 'chunks.csv', chunk_rows)
    (out / 'checkpoint_chunks.json').write_text(json.dumps(ck, ensure_ascii=False, indent=2), encoding='utf-8')

    numbered = re.compile(r'\b\d{1,5}\s+\d{4}\s+(?:qh\d{1,2}|nđ\s+cp|tt\s+[a-zđ]+)\b', re.I)
    short_number = re.compile(r'\b\d{1,5}\s+(?:qđ\s+ttg|nq\s+(?:cp|tw)|ttr\s+[a-zđ]+|kl\s+tw|bkhcn\s+cncntt)\b', re.I)
    date_pattern = re.compile(r'ngày\s+\d{1,2}\s+tháng\s+\d{1,2}\s+năm\s+\d{4}', re.I)
    def own_numbers(text):
        return sorted(set(numbered.findall(norm(text))))
    doc_rows = []
    for n in docs:
        p = n['props']; name = p['name']; clean = norm(name)
        nums = sorted(set(own_numbers(name) + own_numbers(p['id'])))
        meta_exact = [m['doc_id'] for m in metas if clean == norm(m.get('title', ''))]
        linked = sorted(source[n['eid']])
        alias_numbers = sorted({num for a in aliases[n['eid']] for num in own_numbers(by_eid[a]['props']['name'])})
        contexts = sorted({d for c in linked for d in chunk_context[c]['document_ids']})
        # A linked chunk alone never establishes identity. Require the node's exact
        # title immediately followed by an explicit number/date in that chunk.
        citation_numbers, citation_dates, citation_chunks = set(), set(), set()
        citation_pattern = re.compile(re.escape(clean) + r'\s+(?:số\s+)?(\d{1,5}\s+\d{4}\s+(?:qh\d{1,2}|nđ\s+cp|tt\s+[a-zđ]+))\b')
        citation_date_pattern = re.compile(re.escape(clean) + r'\s+(ngày\s+\d{1,2}\s+tháng\s+\d{1,2}\s+năm\s+\d{4})\b')
        for cid in linked:
            text = norm(chunks[cid]['props']['content'])
            found_numbers = citation_pattern.findall(text)
            found_dates = citation_date_pattern.findall(text)
            citation_numbers.update(found_numbers)
            citation_dates.update(found_dates)
            if found_numbers or found_dates:
                citation_chunks.add(cid)
        if p.get('docNumber'):
            status = 'HAS_DOCNUMBER'; evidence = p['docNumber']
        elif clean.startswith(('mẫu ', 'phụ lục ', 'giấy xác nhận ', 'pháp luật ', 'điều ước quốc tế ')):
            status = 'NOT_SPECIFIC_LEGAL_DOCUMENT'; evidence = 'Form/annex/certificate/general legal field; do not assign parent document identity'
        elif len(nums) == 1:
            status = 'EXPLICIT_NUMBER_IN_NAME_OR_ID'; evidence = nums[0]
        elif len(nums) > 1:
            status = 'AMBIGUOUS'; evidence = nums
        elif date_pattern.search(name):
            status = 'EXPLICIT_NAME_AND_DATE'; evidence = name
        elif any(x in {'mst-gov-vn', 'bo-cong-an-csdl-van-ban'} for x in meta_exact):
            status = 'NOT_SPECIFIC_LEGAL_DOCUMENT'; evidence = 'Government website/catalog, not a legal instrument'
        elif len(meta_exact) == 1 and clean not in {'luật an ninh mạng'}:
            status = 'EXACT_TITLE_IN_LOCAL_CATALOG'; evidence = meta_exact
        elif len(citation_numbers) == 1 and len(citation_dates) <= 1:
            status = 'EXPLICIT_CITATION_IN_LINKED_CHUNK'; evidence = sorted(citation_numbers)
        elif len(citation_numbers) > 1 or len(citation_dates) > 1:
            status = 'CONFLICTING_CITATIONS_IN_LINKED_CHUNKS'; evidence = sorted(citation_numbers | citation_dates)
        elif len(citation_dates) == 1:
            status = 'NAME_AND_DATE_IN_LINKED_CHUNK'; evidence = sorted(citation_dates)
        elif len(alias_numbers) == 1:
            status = 'ALIAS_CANDIDATE_UNVERIFIED'; evidence = alias_numbers
        elif short_number.search(clean):
            status = 'NUMBER_WITHOUT_YEAR_AMBIGUOUS'; evidence = short_number.findall(clean)
        else:
            status = 'UNRESOLVED_VERSION_OR_ID'; evidence = 'Named reference/context only; insufficient evidence for unique document/version'
        doc_rows.append({'element_id': n['eid'], 'id': p['id'], 'name': name,
                         'docNumber': p.get('docNumber', ''), 'status': status, 'identity_evidence': evidence,
                         'alias_element_ids': sorted(aliases[n['eid']]), 'chunk_count': len(linked),
                         'explicit_citation_numbers': sorted(citation_numbers),
                         'explicit_citation_dates': sorted(citation_dates), 'citation_chunk_ids': sorted(citation_chunks),
                         'chunk_ids': linked, 'source_context_document_ids_NOT_identity': contexts,
                         'human_verified': False})
    write_csv(out / 'documents.csv', doc_rows)
    write_csv(out / 'documents_missing_docNumber.csv', [r for r in doc_rows if not r['docNumber']])
    meta_edges = json.loads((ROOT / 'data/graph/edges.json').read_text(encoding='utf-8'))
    meta_keys = {(e['fromType'], e['from'], e['label'], e['toType'], e['to']): e['id'] for e in meta_edges}
    provenance = []
    technical = {'source', 'OfficialName', 'similar'}
    for e in edges:
        if e['type'] in technical:
            continue
        a, b = by_eid[e['source']], by_eid[e['target']]
        actual = sorted(ec.get(edge_key(e), set()))
        actual_live = [c for c in actual if c in chunk_context and chunk_context[c]['checkpoint_content_equal']]
        candidates = sorted(source[a['eid']] & source[b['eid']])
        contexts = [chunk_context[c] for c in actual_live]
        # Strict traceability: checkpoint ties an edge to an extraction input, not a supporting quote.
        if len(actual_live) == 1 and len(contexts[0]['document_ids']) == 1:
            status = 'PARTIAL'
            reason = 'Exact checkpoint edge and input chunk; no per-fact evidence span / clause / point'
        elif actual_live:
            status = 'AMBIGUOUS'
            reason = 'Multiple extraction inputs or unresolved document; evidence span not retained'
        elif candidates:
            status = 'AMBIGUOUS'
            reason = 'Only shared-node chunk candidates; not proven source of this edge'
        else:
            status = 'UNTRACEABLE'
            reason = 'No matching extraction checkpoint or common source chunk; metadata edges may have JSON origin'
        provenance.append({'edge_id': e['eid'], 'source_id': a['props']['id'], 'source_name': a['props']['name'],
                           'source_label': a['label'], 'relation': e['type'], 'target_id': b['props']['id'],
                           'target_name': b['props']['name'], 'target_label': b['label'],
                           'status': status, 'reason': reason, 'checkpoint_chunk_ids': actual_live,
                           'candidate_chunk_ids_NOT_evidence': candidates,
                           'document_ids': sorted({d for c in contexts for d in c['document_ids']}),
                           'article_headings_NOT_fact_locator': sorted({x for c in contexts for x in c['article_heading']}),
                           'origin': 'LLM_CHECKPOINT' if actual_live else ('METADATA_JSON' if edge_key(e) in meta_keys else 'UNESTABLISHED'),
                           'metadata_edge_id': meta_keys.get(edge_key(e), ''),
                           'human_verified': False, 'evaluation_eligible': False})
    write_csv(out / 'fact_provenance.csv', provenance)
    # Separate immutable sidecar exclusion manifest; never modify the original graph or evaluation files.
    (out / 'evaluation_gate.json').write_text(json.dumps({
        'policy': 'Only human-reviewed facts with precise supporting source spans may enter gold-fact evaluation.',
        'scope': 'All non-technical relationships in this export; does not alter existing eval.py inputs.',
        'eligible_edge_ids': [], 'excluded_edge_ids': [r['edge_id'] for r in provenance],
        'reason': 'No human review evidence or persisted fact-level source span established by this audit.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')

    # Use the actual vendored function, parsed with AST, without importing KAG initialization.
    import ast
    tree = ast.parse((ROOT / 'vendor/KAG/kag/common/utils.py').read_text(encoding='utf-8'))
    selected = [x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name in {'processing_phrases', 'to_camel_case'}]
    env = {'re': re}
    exec(compile(ast.Module(body=selected, type_ignores=[]), '<vendored normalization>', 'exec'), env)
    camel = env['to_camel_case']
    mapping = {'thuộc văn bản': 'belongsTo', 'nghiêm cấm': 'prohibits', 'quy định chế tài': 'imposes',
               'quy định nghĩa vụ': 'obliges', 'định nghĩa': 'defines', 'áp dụng cho': 'appliesTo',
               'áp dụng cho hành vi': 'forAct', 'căn cứ pháp lý': 'basedOn', 'thẩm quyền xử phạt': 'enforcedBy',
               'thay thế': 'supersedes', 'bị thay thế bởi': 'supersededBy', 'sửa đổi bổ sung': 'amends',
               'hướng dẫn thi hành': 'implementsDoc'}
    mapped = {camel(k): (k, v) for k, v in mapping.items()}
    counts = Counter(e['type'] for e in edges)
    rel_rows = []
    for rel, count in counts.most_common():
        pairs = Counter((by_eid[e['source']]['label'], by_eid[e['target']]['label']) for e in edges if e['type'] == rel)
        rel_rows.append({'relation': rel, 'count': count, 'label_pairs': [{'source': a, 'target': b, 'count': c} for (a,b),c in pairs.most_common()],
                         'prompt_predicate_candidate': mapped.get(rel, ('', ''))[0],
                         'schema_candidate': mapped.get(rel, ('', ''))[1],
                         'status': 'TECHNICAL' if rel in technical else 'REVIEW_PER_EDGE_BEFORE_MAPPING'})
    write_csv(out / 'relation_types.csv', rel_rows)
    pair_types = defaultdict(list)
    for r in provenance:
        pair_types[(r['source_label'], r['source_id'], r['target_label'], r['target_id'])].append(r)
    duplicate_candidates = [{'source_label': k[0], 'source_id': k[1], 'target_label': k[2], 'target_id': k[3],
                             'relations': sorted({r['relation'] for r in rs}),
                             'edge_ids': [r['edge_id'] for r in rs], 'status': 'CANDIDATE_ONLY_NOT_SYNONYM_PROOF'}
                            for k, rs in pair_types.items() if len({r['relation'] for r in rs}) > 1]
    write_csv(out / 'parallel_relation_candidates.csv', duplicate_candidates)
    # Compare numbered paragraph anchors against the source file, never guess the nearest clause.
    numbered_paragraph = re.compile(r'(?m)^\s*(\d{1,3})\.\s+([^\n]+)')
    paragraph_index = {}
    for path, text in processed.items():
        ix = defaultdict(list)
        for match in numbered_paragraph.finditer(text):
            body = norm(match.group(2))[:120]
            if len(body) >= 45:
                ix[body].append((match.group(1), text.count('\n', 0, match.start()) + 1))
        paragraph_index[path] = ix
    numbering_errors, repeated_chunks = [], []
    for cid, n in chunks.items():
        ctx = chunk_context[cid]
        content = n['props']['content']
        if len(ctx['processed_paths']) != 1:
            continue
        path = ctx['processed_paths'][0]
        for match in numbered_paragraph.finditer(content):
            body = norm(match.group(2))[:120]
            hits = paragraph_index[path].get(body, [])
            if len(hits) == 1 and match.group(1) != hits[0][0]:
                numbering_errors.append({'chunk_id': cid, 'source_path': path, 'source_line': hits[0][1],
                                         'source_number': hits[0][0], 'chunk_number': match.group(1),
                                         'anchor': match.group(2)[:180]})
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        repeated = [a for a, b in zip(lines, lines[1:]) if a == b and len(a) >= 40]
        if repeated:
            repeated_chunks.append({'chunk_id': cid, 'source_path': path, 'adjacent_repeated_lines': repeated})
    write_csv(out / 'numbering_errors.csv', numbering_errors)
    write_csv(out / 'repeated_lines.csv', repeated_chunks)
    article_rows = []
    for n in nodes:
        if n['label'] != 'Article':
            continue
        cids = sorted(nc.get(node_key(n), set()))
        doc_ids = sorted({d for c in cids if c in chunk_context for d in chunk_context[c]['document_ids']})
        article_rows.append({'id': n['props']['id'], 'name': n['props']['name'],
                             'bare_article_name': bool(re.fullmatch(r'điều\s+\d+[a-zđ]?', n['props']['name'], re.I)),
                             'source_document_ids': doc_ids, 'source_document_count': len(doc_ids),
                             'checkpoint_chunk_ids': cids})
    write_csv(out / 'article_identity.csv', article_rows)
    summary = {'nodes': len(nodes), 'edges': len(edges), 'node_labels': dict(Counter(n['label'] for n in nodes)),
               'relation_types': len(counts), 'singleton_relation_types': sum(v == 1 for v in counts.values()),
               'edge_property_keys': dict(Counter(k for e in edges for k in e['props'])),
               'document_status_all': dict(Counter(r['status'] for r in doc_rows)),
               'document_status_missing_docNumber': dict(Counter(r['status'] for r in doc_rows if not r['docNumber'])),
               'node_property_keys': dict(Counter(k for n in nodes for k in n['props'])),
               'checkpoint': cache_info, 'checkpoint_chunks': len(ck),
               'live_chunks_matching_checkpoint': sum(r['checkpoint_content_equal'] for r in chunk_rows),
               'chunks_unique_document': sum(len(r['document_ids']) == 1 for r in chunk_rows),
               'chunks_with_article_heading': sum(bool(r['article_heading']) for r in chunk_rows),
               'chunks_payload_exact_in_processed': sum(bool(r['payload_matches_processed']) for r in chunk_rows),
               'technical_edges': {k: counts[k] for k in sorted(technical)},
               'fact_edges': len(provenance), 'strict_provenance': {'FULL': 0, **dict(Counter(r['status'] for r in provenance))},
               'facts_matching_checkpoint': sum(bool(r['checkpoint_chunk_ids']) for r in provenance),
               'fact_origins': dict(Counter(r['origin'] for r in provenance)),
               'numbering_mismatches_unique_anchor': len(numbering_errors),
               'chunks_with_numbering_mismatch': len({r['chunk_id'] for r in numbering_errors}),
               'chunks_with_adjacent_repeated_lines': len(repeated_chunks),
               'bare_article_nodes': sum(r['bare_article_name'] for r in article_rows),
               'bare_article_nodes_multiple_document_contexts': sum(r['bare_article_name'] and r['source_document_count'] > 1 for r in article_rows),
               'parallel_relation_candidate_pairs': len(duplicate_candidates),
               'facts_with_one_shared_candidate_chunk': sum(len(r['candidate_chunk_ids_NOT_evidence']) == 1 for r in provenance),
               'human_verified_facts_established': 0, 'evaluation_eligible_facts': 0}
    (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=True, indent=2))


def self_check(out):
    assert decode('"Điều 1\\nNội dung"') == 'Điều 1\nNội dung'
    assert decode('abc') == 'abc'
    assert norm('Luật 24/2018/QH14') == 'luật 24 2018 qh14'
    # Never execute arbitrary globals when reading cached objects.
    try:
        DataOnlyUnpickler(io.BytesIO(b'cos\nsystem\n.')).load()
    except pickle.UnpicklingError:
        pass
    else:
        raise AssertionError('Unsafe pickle global accepted')
    if (out / 'summary.json').exists():
        summary = json.loads((out / 'summary.json').read_text(encoding='utf-8'))
        facts = list(csv.DictReader((out / 'fact_provenance.csv').open(encoding='utf-8-sig')))
        docs = list(csv.DictReader((out / 'documents_missing_docNumber.csv').open(encoding='utf-8-sig')))
        assert len(docs) == sum(summary['document_status_missing_docNumber'].values()) == 218
        assert len(facts) == sum(summary['strict_provenance'].values()) == 10473
        assert all(r['human_verified'] == 'False' and r['evaluation_eligible'] == 'False' for r in facts)
        manifest = json.loads((out / 'manifest.json').read_text(encoding='utf-8'))
        for name, expected in manifest['export_sha256'].items():
            assert sha256(out / name) == expected, name
        assert manifest['dump_sha256_before'] == manifest['dump_sha256_after'] == sha256(ROOT / 'dist/legal.dump')
        assert summary['live_chunks_matching_checkpoint'] == 1121
        # Fixed real regression examples, independent of aggregate statistics.
        numbering = list(csv.DictReader((out / 'numbering_errors.csv').open(encoding='utf-8-sig')))
        cid = 'b515851733aba23d8be3cff8c17c11ceddb8193ec0d2e116daf3fe91e80918ef'
        assert {r['source_number'] for r in numbering if r['chunk_id'] == cid and r['chunk_number'] == '1'} >= {'2', '3'}
        articles = list(csv.DictReader((out / 'article_identity.csv').open(encoding='utf-8-sig')))
        assert next(r for r in articles if r['id'] == 'điều 2')['source_document_count'] == '21'
    print('self-check OK')


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def export(out):
    from neo4j import GraphDatabase
    out.mkdir(parents=True, exist_ok=False)
    dump = ROOT / 'dist/legal.dump'
    before = sha256(dump)
    with GraphDatabase.driver(os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
                              auth=(os.getenv('NEO4J_USER', 'neo4j'),
                                    os.getenv('NEO4J_PASSWORD', 'neo4j@openspg'))) as driver:
        with driver.session(database='legal', default_access_mode='READ') as session:
            def read(tx):
                rows = tx.run(
                    'MATCH (n) RETURN elementId(n) AS eid, labels(n) AS labels, '
                    '[k IN keys(n) WHERE NOT toLower(k) CONTAINS "vector" '
                    'AND NOT toLower(k) CONTAINS "embedding" | [k,n[k]]] AS pairs')
                nodes = [{'eid': r['eid'], 'labels': r['labels'], 'props': dict(r['pairs'])} for r in rows]
                edges = [r.data() for r in tx.run(
                    'MATCH (s)-[r]->(t) RETURN elementId(r) AS eid, '
                    'elementId(s) AS source, elementId(t) AS target, '
                    'type(r) AS type, properties(r) AS props')]
                return nodes, edges
            nodes, edges = session.execute_read(read)
    after = sha256(dump)
    assert before == after, 'Snapshot hash changed during audit'
    for name, data in [('nodes.json', nodes), ('edges.json', edges)]:
        (out / name).write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    manifest = {'captured_at_utc': datetime.now(timezone.utc).isoformat(),
                'database': 'legal', 'mode': 'READ', 'nodes': len(nodes), 'edges': len(edges),
                'dump_sha256_before': before, 'dump_sha256_after': after,
                'dump_size_bytes': dump.stat().st_size,
                'scope': 'Live graph export; matching counts do not prove equality with dump.',
                'export_sha256': {name: sha256(out / name) for name in ['nodes.json', 'edges.json']}}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--analyze', action='store_true')
    parser.add_argument('--self-check', action='store_true')
    args = parser.parse_args()
    if args.self_check:
        self_check(args.out)
    elif args.analyze:
        analyze(args.out)
    else:
        export(args.out)
