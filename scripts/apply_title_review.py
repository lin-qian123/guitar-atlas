#!/usr/bin/env python
"""Apply a complete, guarded title review ledger; dry-run unless --apply."""
from __future__ import annotations
import argparse
import json
import os
import re
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from catalog_translations import wrap_display_title

HAN = re.compile(r'[\u3400-\u9fff]')
FILES = ('cglib_decisions.json', 'legacy_decisions.json', 'archive_decisions.json', 'root_decisions.json')
SUPPLEMENT_FILES = ('root_cross_source_botanical_supplement.json', 'root_cross_source_consistency_supplement.json',
                    'root_final_naturalness_supplement.json')
DISPLAY_REPAIR_FILE = 'root_final_credit_display_supplement.json'
FINAL_PROJECTION_FILES = ('final_projection_decisions.json', 'final_projection_expanded_decisions.json',
                          'final_latin_semantic_review.json', 'final_context_root_decisions.json')
FINAL_ACTUAL_FILES = ('final_actual_headline_decisions.json', 'final_actual_toponym_decisions.json')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=path.name + '.', suffix='.part', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def validate_decisions(corpus, payloads):
    source = {row['id']: row for row in corpus}
    if len(source) != len(corpus):
        raise ValueError('duplicate corpus identities')
    decisions = {}
    for payload in payloads:
        if payload.get('schema_version') != 1 or not isinstance(payload.get('entries'), list):
            raise ValueError('invalid decision ledger')
        for decision in payload['entries']:
            ident = decision['id']
            if ident not in source or ident in decisions:
                raise ValueError(f'unknown or duplicate reviewed identity: {ident}')
            row = source[ident]
            if decision.get('original') != row['original'] or decision.get('original_composer') != row['composer']:
                raise ValueError(f'review original title/attribution drift: {ident}')
            state = decision.get('status')
            if state not in {'reference', 'reviewed', 'retained'}:
                raise ValueError(f'unresolved title review: {ident}')
            for field in ('zh', 'basis', 'reason'):
                if not isinstance(decision.get(field), str) or not decision[field].strip():
                    raise ValueError(f'missing {field}: {ident}')
            if state in {'reference', 'reviewed'} and not HAN.search(decision['zh']):
                raise ValueError(f'Chinese title missing: {ident}')
            refs = decision.get('source_refs', [])
            if not isinstance(refs, list) or any(not isinstance(ref, str) or not ref.startswith('https://') for ref in refs):
                raise ValueError(f'invalid title references: {ident}')
            if state == 'reviewed' and not refs:
                raise ValueError(f'conventional title lacks references: {ident}')
            if 'display_zh' in decision:
                if decision.get('display_original') != row['display_original'] or not isinstance(decision['display_zh'], str) or not decision['display_zh'].strip():
                    raise ValueError(f'review display title drift: {ident}')
            decisions[ident] = decision
    if set(source) != set(decisions):
        missing = sorted(set(source) - set(decisions))
        raise ValueError(f'incomplete review ledger: {len(missing)} missing, first {missing[0]}')
    return decisions


def overlay_supplements(corpus, decisions, payloads):
    """Revalidate the complete result after explicit, exact-ID final research."""
    combined = dict(decisions)
    seen = set()
    for payload in payloads:
        if payload.get('schema_version') != 1 or not isinstance(payload.get('entries'), list):
            raise ValueError('invalid final review supplement')
        for row in payload['entries']:
            ident = row['id']
            if ident not in combined or ident in seen:
                raise ValueError(f'unknown or duplicate final supplement identity: {ident}')
            seen.add(ident)
            combined[ident] = row
    return validate_decisions(corpus, [{'schema_version': 1, 'entries': list(combined.values())}])


def overlay_display_repairs(corpus, decisions, payload):
    """Apply the final hand-read display pass against the preceding exact text."""
    if payload.get('schema_version') != 1 or not isinstance(payload.get('entries'), list):
        raise ValueError('invalid final display review')
    combined, seen = dict(decisions), set()
    for row in payload['entries']:
        ident = row['id']
        if ident not in combined or ident in seen:
            raise ValueError(f'unknown or duplicate final display identity: {ident}')
        before = combined[ident]
        if row.get('before_zh') != before['zh'] or row.get('before_display_zh') != before.get('display_zh', before['zh']):
            raise ValueError(f'preceding title review drift: {ident}')
        explicit_original_retention = (
            before['status'] == 'reference' and row['status'] == 'retained'
            and not HAN.search(row.get('display_zh', ''))
            and row.get('state_change_basis') in {'chinese_was_metadata_only', 'unsupported_phonetic_title', 'source_title_ambiguity'}
            and row.get('basis', '').startswith('explicit_original_title_retention')
        )
        if row['status'] != before['status'] and not explicit_original_retention:
            raise ValueError(f'display review changed semantic state: {ident}')
        seen.add(ident)
        combined[ident] = row
    return validate_decisions(corpus, [{'schema_version': 1, 'entries': list(combined.values())}])


def apply(root, corpus, decisions):
    folder = root / 'metadata/translations'
    assets = {name: read(folder/name) for name in (
        'source_titles_zh.json', 'source_title_quality_review_zh.json',
        'classclef_titles_zh.json', 'title_overrides_reviewed_zh.json')}
    imslp = {str(row['work_id']): row for row in assets['title_overrides_reviewed_zh.json']['entries']}
    report = {'schema_version': 1, 'scope': 'Frozen 2026-10-03 catalog titles; semantic review, not PDF/instrumentation certification.',
              'review_started_date': '2026-10-03', 'completed_at': datetime.now(timezone.utc).isoformat(),
              'records': len(corpus), 'before': dict(Counter(row['status'] for row in corpus)),
              'after': dict(Counter(row['status'] for row in decisions.values())), 'sources': {}, 'changes': []}
    by_source = defaultdict(list)
    for original in corpus:
        ident, source = original['id'], original['source_id']
        decision = decisions[ident]
        by_source[source].append(decision)
        optional = {key: decision[key] for key in ('source_refs', 'review_method', 'display_original', 'display_zh', 'aliases_zh') if key in decision}
        if source == 'imslp':
            row = imslp[ident]
            if row['title_en'] != original['original']:
                raise ValueError(f'current IMSLP review changed since snapshot: {ident}')
            row.update(title_zh=wrap_display_title(decision['zh']), original_composer=original['composer'],
                       status='accepted' if row['title_zh'] == wrap_display_title(decision['zh']) else 'corrected',
                       basis='common_name' if decision['status'] == 'reviewed' else 'semantic_correction',
                       reason=decision['reason'], reviewer=decision.get('reviewer', 'Codex semantic title review 2026-10-04'),
                       source_refs=decision.get('source_refs', []), **{k:v for k,v in optional.items() if k != 'source_refs'})
            row.pop('retention_reason', None)
            if decision['status'] == 'retained':
                row['retention_reason'] = decision['reason']
        else:
            name = 'classclef_titles_zh.json' if source == 'classclef' else 'source_titles_zh.json'
            old = assets[name]['entries'][ident]
            if old['original'] != original['original']:
                raise ValueError(f'current translation changed since snapshot: {ident}')
            row = {'original': original['original'], 'original_composer': original['composer'],
                   'zh': wrap_display_title(decision['zh']), 'status': decision['status'],
                   'basis': decision['basis'], 'reason': decision['reason'],
                   'reviewer': decision.get('reviewer', 'Codex semantic title review 2026-10-04'), **optional}
            if 'aliases_zh' not in optional and old.get('aliases_zh'):
                row['aliases_zh'] = old['aliases_zh']
            assets[name]['entries'][ident] = row
            if source != 'classclef':
                # Pin the exact final decision before any legacy draft/grammar
                # lookup in future discovery metadata rebuilds.
                assets['source_title_quality_review_zh.json']['entries'][ident] = row.copy()
        changed = original['zh'] != wrap_display_title(decision['zh']) or original['status'] != decision['status']
        if changed or 'display_zh' in decision and wrap_display_title(decision['display_zh']) != original['display_zh']:
            report['changes'].append({'id': ident, 'source_id': source, 'original': original['original'],
                                      'before_zh': original['zh'], 'before_status': original['status'],
                                      'zh': decision['zh'], 'status': decision['status'],
                                      'display_zh': decision.get('display_zh', ''), 'method': decision.get('review_method', '')})
    for name, asset in assets.items():
        asset['updated_at'] = '2026-10-04'
        asset['review_scope'] = 'Complete frozen-catalogue title decisions in review_2026-10-03; source titles and IDs remain exact guards.'
        if isinstance(asset['entries'], dict):
            asset['summary'] = {'records': len(asset['entries']), 'status_counts': dict(Counter(r['status'] for r in asset['entries'].values()))}
    for source, rows in sorted(by_source.items()):
        report['sources'][source] = {'records': len(rows), 'statuses': dict(Counter(r['status'] for r in rows)),
                                    'methods': dict(Counter(r.get('review_method', '') for r in rows))}
    return assets, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--corpus', type=Path, default=Path('work/title-review/2026-10-03/corpus.json'))
    parser.add_argument('--decisions', type=Path, default=Path('metadata/translations/review_2026-10-03'))
    parser.add_argument('--report', type=Path, default=Path('work/title-review/2026-10-03/application-report.json'))
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve()
    corpus = read(root/args.corpus)
    if isinstance(corpus, dict):
        corpus = corpus['entries']
    decisions = validate_decisions(corpus, [read(root/args.decisions/name) for name in FILES])
    decisions = overlay_supplements(corpus, decisions, [read(root/args.decisions/name) for name in SUPPLEMENT_FILES])
    decisions = overlay_display_repairs(corpus, decisions, read(root/args.decisions/DISPLAY_REPAIR_FILE))
    final_rows = [row for name in FINAL_PROJECTION_FILES for row in read(root/args.decisions/name)['entries']]
    decisions = overlay_display_repairs(corpus, decisions, {'schema_version': 1, 'entries': final_rows})
    actual_rows = [row for name in FINAL_ACTUAL_FILES for row in read(root/args.decisions/name)['entries']]
    decisions = overlay_display_repairs(corpus, decisions, {'schema_version': 1, 'entries': actual_rows})
    assets, report = apply(root, corpus, decisions)
    report['applied'] = args.apply
    if args.apply:
        backup = root/'work/title-review/2026-10-03/before/metadata/translations'
        for name in assets:
            if not (backup/name).exists():
                raise ValueError(f'pre-review backup missing: {name}')
        for name, value in assets.items():
            atomic_json(root/'metadata/translations'/name, value)
    atomic_json(root/args.report, report)
    print(json.dumps({k:v for k,v in report.items() if k not in {'changes'}}, ensure_ascii=False, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
