"""Compile individually guarded source/file proposals into one classification input.

The private lossless receipt retains the complete proposals and their gaps.
Only the compact, reviewed decisions are versioned; no native catalog changes.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
from functools import lru_cache

from catalog_classification import REVIEW_PATH, check_decision, digest, field_value
from source_adapters.pdmx import _atomic_json

BASE = Path('sources/classification')
LABELS = {'solo': '吉他独奏', 'duo': '吉他二重奏', 'trio': '吉他三重奏',
    'quartet': '吉他四重奏', 'guitar_ensemble': '吉他合奏（人数未标）',
    'strings': '吉他与弦乐', 'woodwinds': '吉他与木管', 'brass': '吉他与铜管',
    'keyboard_reed': '吉他与键盘／自由簧', 'plucked': '吉他与其他拨弦乐器',
    'percussion': '吉他与打击乐', 'mixed_chamber': '吉他与多类器乐',
    'other_instrumentation': '其他编制（来源器种声明保留）',
    'guitar_unspecified': '吉他相关，编制未细分', 'unspecified': '实际编制尚未核明',
    'reference': '参考资料（不适用演奏人数）'}


def load(path):
    return json.loads(Path(path).read_bytes())


@lru_cache(maxsize=4096)
def _guard_cached(path, stamp):
    body = path.read_bytes()
    current = path.stat()
    if (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns, current.st_ctime_ns) != stamp:
        raise ValueError('classification evidence changed while reading')
    return {'sha256': hashlib.sha256(body).hexdigest(), 'size': len(body)}


def guard(path):
    stat = path.stat()
    return _guard_cached(path, (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns))


def _field(work, path):
    value = field_value(work, path)
    if value in (None, '', [], {}):
        return None
    # A digest also guards a source's exact file label without copying its
    # download endpoint or private locator into a versioned review asset.
    return {'kind': 'native_field', 'path': path, 'value_sha256': digest(value)}


@lru_cache(maxsize=256)
def _snapshot_heading(root, sid, url, expected):
    from bs4 import BeautifulSoup
    state = load(root / 'sources' / sid / 'discovery_state.json')['requests'][url]
    relative = Path('sources') / sid / state['cache']
    proof = guard(root / relative)
    if proof['sha256'] != expected or state['sha256'] != expected:
        raise ValueError('frozen source page differs from the proposed heading')
    soup = BeautifulSoup((root / relative).read_bytes(), 'html.parser')
    headings = [h.get_text(' ', strip=True) for h in soup.select('h1')]
    return relative.as_posix(), proof, headings


@lru_cache(maxsize=512)
def _snapshot_records(path, stamp):
    payload = load(path)
    if not isinstance(payload, list) or any(not isinstance(row, dict) or 'id' not in row for row in payload):
        raise ValueError('source snapshot is not an original CMS record page')
    indexed = {row['id']: row for row in payload}
    if len(indexed) != len(payload):
        raise ValueError('duplicate native CMS IDs in source snapshot')
    return indexed


@lru_cache(maxsize=32)
def _snapshot_registrations(root, sid, state_sha):
    state = load(root / 'sources' / sid / 'discovery_state.json')
    return {(str(Path('sources') / sid / row['cache']), row['sha256'])
            for row in state['requests'].values() if row.get('status') == 200 and row.get('cache') and row.get('sha256')}


def _check_snapshot_record(root, work, relative, expected_hash, proposed=None):
    """Bind an original CMS page row to this exact native identity and URL."""
    from source_adapters.additional import text
    path = root / relative
    proof = guard(path)
    if proof['sha256'] != expected_hash:
        raise ValueError('stale original source page')
    sid = work['id'].split(':', 1)[0]
    state = root / 'sources' / sid / 'discovery_state.json'
    if (relative, expected_hash) not in _snapshot_registrations(root, sid, guard(state)['sha256']):
        raise ValueError('source snapshot is absent from the guarded discovery request mapping')
    record = _snapshot_records(path, proof['sha256']).get(work['metadata']['cms_post_id'])
    if (record is None or record.get('link') != work['source_url']
            or text(record.get('title', {}).get('rendered', '')) != work['title_en']):
        raise ValueError('source snapshot row is not this native identity/title/URL')
    if 'categories' in record and sorted(map(str, record['categories'])) != sorted(work['category_ids']):
        raise ValueError('source snapshot categories differ from the native record')
    if proposed is not None and any(proposed.get(key) != value for key, value in {
            'id': record['id'], 'link': record['link'], 'title': record['title']['rendered'],
            'categories': record.get('categories'), 'tags': record.get('tags')}.items()):
        raise ValueError('proposed source snapshot row differs from its original record')
    return proof


def _archive_decision(root, work, row):
    if row['native_record_canonical_sha256'] != digest(work):
        raise ValueError('stale archive proposal: ' + work['id'])
    evidence = []
    for item in row['evidence']:
        field = item['field']
        if field == 'frozen_source_page.record':
            value = item['raw_value']; path = root / value['response_path']
            proof = _check_snapshot_record(root, work, value['response_path'], value['response_file_sha256'], value)
            evidence.append({'kind': 'source_snapshot', 'path': value['response_path'],
                **proof, 'observation': '该原生编号的冻结目录题名、类别与来源链接逐项核对。'})
        else:
            path = field.split('.')
            try:
                proof = _field(work, path)
            except (KeyError, TypeError, IndexError):
                proof = None
            if proof:
                evidence.append(proof)
    topic = row['topic']
    if work.get('resource_type') == 'reference':
        topic = 'reference'
    return {'native_record_sha256': digest(work), 'topic_id': topic,
        'basis': 'reviewed_source_evidence', 'instrumentation': LABELS[topic],
        'player_count': row.get('player_count') if topic in {'solo', 'duo', 'trio', 'quartet'} else None,
        'note': row['reason'] if topic != 'reference' else '来源明确标为参考资料，演奏人数不适用。',
        'evidence': evidence or [_field(work, ['title_en'])]}


def _local_decision(root, work, categories, row):
    if row['native_record_sha256'] != digest(work):
        raise ValueError('stale local proposal: ' + work['id'])
    decision = {k: deepcopy(row[k]) for k in
        ('native_record_sha256', 'topic_id', 'basis', 'instrumentation', 'player_count', 'note')}
    if decision['basis'] == 'unresolved' and decision['topic_id'] == 'unspecified':
        decision['basis'] = 'reviewed_source_evidence'
    evidence = []
    for item in row['evidence']:
        item = deepcopy(item)
        if item['kind'] == 'native_field':
            path = item['path']
            # The proposal's category item is a member declaration, rather
            # than an equality assertion between a list and a scalar.
            if path == ['category_ids'] and isinstance(item.get('value'), str):
                cid = item['value']
                if cid not in work['category_ids']:
                    raise ValueError('unknown proposed category membership')
                item = {'kind': 'category', 'id': cid, 'sha256': digest(categories[cid])}
            elif path == ['source_category_names']:
                names = item['value']
                matches = [categories[cid] for cid in work['category_ids'] if categories[cid]['name'] in names]
                if set(names) - {c['name'] for c in matches}:
                    raise ValueError('proposed source category names differ')
                evidence.extend({'kind': 'category', 'id': c['id'], 'sha256': digest(c)} for c in matches)
                continue
            elif path == ['frozen_source_page', 'h1']:
                if item['source_url'] != work['source_url']:
                    raise ValueError('source heading URL is not this native record URL')
                relative, proof, headings = _snapshot_heading(root, row['source_id'], item['source_url'], item['page_sha256'])
                if item['value'] not in headings:
                    raise ValueError('proposed source heading differs from its original page')
                item = {'kind': 'source_snapshot', 'path': relative, **proof,
                    'observation': '该记录所对应来源目录的原始标题：' + item['value']}
            else:
                item = _field(work, path)
                if not item:
                    continue
        elif item['kind'] == 'file':
            if decision['basis'] == 'reviewed_source_evidence':
                # Integrity-only acquisition evidence is retained privately.
                # A source-declared classification does not depend on having
                # downloaded a local file or certify its written instruments.
                continue
            item = {k: item[k] for k in ('kind', 'format', 'sha256', 'size', 'observation')}
        evidence.append(item)
    decision['evidence'] = evidence
    return decision


def compile_review(root):
    root = Path(root).resolve()
    scope = load(root / BASE / 'scope.json')
    bundles, input_guards = {}, {}
    names = {'archive': BASE / 'archive-source-proposals.json',
        'cglib_detail': BASE / 'cglib-detail-proposals.json',
        'local': BASE / 'local-source-proposals.json',
        'local_refinement': BASE / 'local-refinement-proposals.json',
        'imslp_files': BASE / 'imslp-file-proposals.json',
        'root': BASE / 'root-source-proposals.json',
        'musescore': Path('sources/musescore/expansion/broad-review-proposals.json')}
    existing = None
    missing = {name for name, path in names.items() if not (root / path).is_file()}
    if missing:
        existing = json.loads(gzip.decompress((root / BASE / 'review.json.gz').read_bytes()))
    for name, path in names.items():
        if name in missing:
            bundles[name] = existing['original_proposals'][name]
            if digest(bundles[name]) != existing['proposal_semantic_guards'][name]:
                raise ValueError('consolidated proposal differs from its semantic guard')
            input_guards[name] = existing['proposal_byte_guards'][name]
        else:
            raw = (root / path).read_bytes()
            bundles[name] = json.loads(raw)
            input_guards[name] = {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}
    source_catalogs = {}
    from catalog_sources import load_registry
    for source in load_registry(root):
        if source.get('catalog'):
            source_catalogs[source['id']] = load(root / source['catalog'])
    native = {w['id']: w for cat in source_catalogs.values() for w in cat['works']}
    categories = {sid: {c['id']: c for c in cat['categories']} for sid, cat in source_catalogs.items()}
    entries, outcomes = {}, {}
    for row in bundles['archive']['proposals']:
        identity = row['native_record_id']; work = native[identity]
        entries[identity] = _archive_decision(root, work, row)
        outcomes[identity] = {'status': row['status'], 'remaining_gap': row['reason']}
    # More complete detail evidence supplements an unresolved original decision;
    # it never silently replaces an already supported contradictory conclusion.
    for row in bundles['cglib_detail']['proposals']:
        identity = row['native_record_id']
        if entries[identity]['topic_id'] != 'unspecified' or row['topic'] == 'unspecified':
            continue
        work = native[identity]; detail = row['evidence']; path = root / detail['response_path']
        proof = _check_snapshot_record(root, work, detail['response_path'], detail['response_sha256'])
        if digest(work) != row['native_record_canonical_sha256']:
            raise ValueError('CGLIB detail source guard differs')
        topic = row['topic']
        entries[identity] = {'native_record_sha256': digest(work), 'topic_id': topic,
            'basis': 'reviewed_source_evidence', 'instrumentation': LABELS[topic],
            'player_count': row.get('player_count') if topic in {'solo', 'duo', 'trio', 'quartet'} else None,
            'note': '原始逐条网页嵌入的谱件标签补全器种声明；保留原题、原始来源与未明版本信息。',
            'evidence': [_field(work, ['id']), {'kind': 'source_snapshot',
                'path': detail['response_path'], **proof,
                'observation': '该原生记录的来源链接与冻结正文一致，嵌入谱件原标签明确给出器种。'}]}
        outcomes[identity] = {'status': row['status'], 'remaining_gap': row.get('reason', '')}
    for row in bundles['local']['entries']:
        identity = row['source_id'] + ':' + row['source_record_id']
        if identity in entries:
            raise ValueError('overlapping independent classification batches')
        entries[identity] = _local_decision(root, native[identity], categories[row['source_id']], row)
        outcomes[identity] = {'status': row.get('proposal_status', 'confirmed'), 'remaining_gap': row['note']}
    for row in bundles['local_refinement']['entries']:
        identity = row['source_id'] + ':' + row['source_record_id']
        if identity not in entries or entries[identity]['topic_id'] != 'guitar_unspecified':
            raise ValueError('local refinement exceeded the unresolved performing-count scope')
        entries[identity] = _local_decision(root, native[identity], categories[row['source_id']], row)
        outcomes[identity] = {'status': row.get('proposal_status', 'confirmed'), 'remaining_gap': row['note']}
    for identity, row in bundles['root']['records'].items():
        if identity in outcomes:
            raise ValueError('overlapping root classification batch')
        outcomes[identity] = row
    # Later publication projection replaces literal field guards with digests.
    # Keep the private original proposal lossless rather than mutating its rows.
    entries.update(deepcopy(bundles['root']['entries']))
    for row in bundles['musescore']['formal_25_actual_file_review']:
        identity = row['id']; work = native[identity]
        if row['native_record_sha256'] != digest(work):
            raise ValueError('stale formal MuseScore proposal')
        topic = row['proposed_topic_id']
        note = ('此次确认吉他相关性；' if topic == 'guitar_unspecified' else '实际器种仍缺充分证据；')
        note += row['remaining_evidence_gap']
        entries[identity] = {'native_record_sha256': digest(work), 'topic_id': topic,
            'basis': 'reviewed_score_evidence', 'instrumentation': LABELS[topic], 'player_count': None,
            'note': note, 'evidence': [{'kind': 'file', 'format': label,
                'sha256': asset['sha256'], 'size': asset['size'],
                'observation': '原始文件字节与本次编制、角色和具体未决项复核相对应。'}
                for label, asset in row['assets'].items()]}
        outcomes[identity] = {'status': row['proposed_disposition'], 'remaining_gap': row['remaining_evidence_gap']}
    if set(outcomes) != set(scope['formal_ids']) or set(entries) != set(scope['formal_ids']) - {
            i for i in scope['formal_ids'] if re.fullmatch(r'[0-9]+', i)}:
        raise ValueError('every frozen formal record needs exactly one classification outcome')
    for identity, decision in entries.items():
        work = native[identity]
        if decision['topic_id'] == 'unspecified' and decision['basis'] == 'reviewed_source_evidence':
            decision['basis'] = 'reviewed_source_audit'
        check_decision(root, work, categories[work['id'].split(':', 1)[0]], decision)
        for proof in decision['evidence']:
            if proof['kind'] == 'native_field' and 'value' in proof:
                proof['value_sha256'] = digest(proof.pop('value'))
    if any(guard(root / path) != input_guards[name] for name, path in names.items() if name not in missing):
        raise ValueError('a proposal changed during classification compilation; retry after writers stop')
    broad = load(root / 'metadata/instrumentation/musescore_broad_reviewed.json')
    candidate_outcomes = {r['id']: {'status': 'accepted', 'remaining_gap': r['review']['summary']}
        for r in broad['entries']}
    candidate_outcomes.update({r['id']: {'status': r['status'], 'remaining_gap': r['remaining_gap']}
        for r in broad['outcomes']})
    if set(candidate_outcomes) != set(scope['pending_musescore_ids']):
        raise ValueError('every pending MuseScore identity needs its exact final outcome')
    result = {'schema_version': 1, 'status': 'complete', 'scope_id': 'guitar-related-evidence-review-v1',
        'entries': dict(sorted(entries.items()))}
    review_path = root / REVIEW_PATH
    review_raw = (json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode()
    if not review_path.is_file() or review_path.read_bytes() != review_raw:
        _atomic_json(review_path, result)
    receipt = {'schema_version': 1, 'status': 'complete', 'checked_at': datetime.now(timezone.utc).isoformat(),
        'scope': scope, 'original_proposals': bundles,
        'proposal_byte_guards': input_guards,
        'proposal_semantic_guards': {name: digest(value) for name, value in bundles.items()},
        'production_review': {'path': str(REVIEW_PATH), **guard(root / REVIEW_PATH)},
        'formal_outcomes': outcomes, 'candidate_outcomes': candidate_outcomes,
        'summary': {'formal_records': len(outcomes),
            'production_entries': len(entries), 'topics': dict(Counter(d['topic_id'] for d in entries.values())),
            'evidence_levels': dict(Counter(d['basis'] for d in entries.values()))}}
    destination = root / BASE / 'review.json.gz'; temporary = destination.with_suffix('.gz.part')
    raw = json.dumps(receipt, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
    with temporary.open('wb') as output:
        with gzip.GzipFile(fileobj=output, mode='wb', compresslevel=6, mtime=0) as stream:
            stream.write(raw)
        output.flush(); os.fsync(output.fileno())
    if json.loads(gzip.decompress(temporary.read_bytes())) != receipt:
        raise ValueError('classification receipt lossless readback failed')
    os.replace(temporary, destination)
    return receipt['summary']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    args = parser.parse_args()
    print(json.dumps(compile_review(args.root), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
