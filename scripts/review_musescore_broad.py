"""Prepare guarded broad guitar-related admissions without replaying old reviews.

Only exact reviewed decisions are compiled. A known active guitar role can be
kept with explicitly unknown additional roles/counts. It cannot establish a pure
guitar ensemble, resolve a conflicting instrument, or certify MIDI fidelity.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from pathlib import Path

from catalog_instrumentation import _check_asset, _check_review, per_record_guard
from expand_musescore_library import (BASE, BROAD_CONTINUATION, BROAD_SCOPE,
    baseline, check_continuation_state, load, canonical, sha)
from review_musescore_expansion_final import (read_mxl_title_evidence, review_file_title,
    public_part_labels)
from score_instrumentation import read_mxl_evidence, read_midi_evidence
from score_pdf_evidence import read_pdf_evidence
from review_musescore_expansion import expansion_kind
from source_adapters.pdmx import _atomic_json
from verify_musescore_expansion import (BROAD_INPUTS, FINAL_INPUT_PATHS, check_final_input_guards,
    require)
from verify_musescore_instrumentation import AuditFailure


def file_guard(path):
    body = path.read_bytes()
    return {'sha256': sha(body), 'size': len(body)}


def check_outcome(root, planned, case, assets):
    """Guard a non-admission without replacing its original automatic evidence."""
    require(case.get('native_record_sha256') == per_record_guard(planned), 'outcome native guard differs')
    require(all(case.get(k) == planned[k] for k in ('id', 'title_en', 'composer_en', 'source_url')),
            'outcome identity transcription differs')
    work = {**planned, 'assets': list(assets.values())}
    for label, asset in assets.items():
        expected = {'sha256': asset['sha256'], 'size': asset['size']}
        require(case.get('assets', {}).get(label) == expected, 'outcome asset guard differs')
        _check_asset(root, work, label, expected)
    require(case.get('status') in {'pending', 'excluded'} and isinstance(case.get('remaining_gap'), str)
            and bool(case['remaining_gap'].strip()), 'outcome needs its exact reason or gap')
    if case['status'] == 'excluded':
        require(bool(case.get('reviewed_scope_evidence')), 'excluded outcome lacks its reviewed source/file evidence')
    return {'status': case['status'], 'reason': case['remaining_gap'],
            'broad_case': deepcopy(case), 'boundary': 'Original automatic conflicts and file bytes remain unchanged.'}


def write_semantic_transaction(root, scope, final, before):
    """Resume either half of the exact two-file transaction, rejecting drift."""
    import json
    scope_raw = (json.dumps(scope, ensure_ascii=False, indent=2) + '\n').encode()
    final['inputs']['scope_review'] = file_guard_from_bytes(scope_raw)
    final_raw = (json.dumps(final, ensure_ascii=False, indent=2) + '\n').encode()
    after = {'scope-review.json': file_guard_from_bytes(scope_raw),
             'final-review.json': file_guard_from_bytes(final_raw)}
    journal_path = root / BASE / 'broad-prepare.json'
    current = {name: file_guard(root / BASE / name) for name in before}
    require(all(current[name] in (before[name], after[name]) for name in before),
            'semantic reports differ from both captured and prepared broad values')
    if journal_path.is_file():
        previous = load(journal_path)
        require(previous.get('before') == before and previous.get('after') == after,
                'broad prepared transaction drift')
    _atomic_json(journal_path, {'schema_version': 1, 'status': 'prepared', 'before': before, 'after': after})
    _atomic_json(root / BASE / 'scope-review.json', scope)
    _atomic_json(root / BASE / 'final-review.json', final)
    check_final_input_guards(root, final, scope)
    _atomic_json(journal_path, {'schema_version': 1, 'status': 'complete', 'before': before, 'after': after})


def check_case(root, planned, case, assets):
    identity = planned['id']
    require(case.get('native_record_sha256') == per_record_guard(planned), 'broad native guard differs: ' + identity)
    require(all(case.get(k) == planned[k] for k in ('id', 'title_en', 'composer_en', 'source_url')),
            'broad identity transcription differs')
    work = deepcopy(planned); work['assets'] = list(assets.values())
    for label, asset in assets.items():
        guard = case.get('assets', {}).get(label)
        require(guard == {'sha256': asset['sha256'], 'size': asset['size']}, 'broad format guard differs')
        _check_asset(root, work, label, guard)
    mxl = read_mxl_evidence(root / assets['MUSICXML']['local_path'])
    read_midi_evidence(root / assets['MIDI']['local_path'])
    pdf = read_pdf_evidence(root / assets['PDF']['local_path'])
    parts = {p['part_id']: p for p in mxl['parts']}
    require(case.get('part_names') == [p['name'] for p in mxl['parts']], 'broad part labels differ')
    guitar = case.get('guitar_parts')
    require(isinstance(guitar, list) and guitar, 'broad admission requires actual guitar evidence')
    for proof in guitar:
        part = parts.get(proof.get('part_id'))
        require(part is not None and any(part.get(k, 0) > 0 for k in ('note_count', 'harmony_count', 'slash_count'))
                and proof.get('part_sha256') == canonical(part),
                'broad guitar part is silent, missing or changed: ' + identity + '/' + str(proof.get('part_id')))
        # This exact reviewed declaration is a word from the notation, never a
        # numeric patch, a track count or a generic template inference.
        label = proof.get('declaration')
        names = [part['name'], *(i['name'] for i in part['score_instruments'])]
        import re
        alternative = proof.get('kind') == 'printed_alternative'
        if alternative:
            require(label == 'Flute/Guitar' and bool(proof.get('observation')),
                    'reviewed alternative must retain its exact printed instrument choice')
        else:
            require(label in names and isinstance(label, str) and label.strip(), 'broad guitar declaration differs')
            role = label.split(',', 1)[0].strip()
            require(expansion_kind(role) in {'guitar', 'contra_guitar'}
                    or re.fullmatch(r'(?:Jazz Guitar|(?:Nylon |Rytm )?Gtr\.?|Gtr\.?\s*Harmonics|Gt\.[1-9][0-9]*|アコースティックギター)', role, re.I)
                    or re.fullmatch(r'(?:Muted|Clean) Guitar|DistortionGtr', role, re.I),
                    'broad role lacks an explicit guitar declaration')
        printed = proof.get('pdf')
        require(isinstance(printed, list) and printed, 'printed guitar corroboration required')
        for row in printed:
            page = row.get('page'); text = row.get('text')
            require(type(page) is int and 1 <= page <= len(pdf['page_evidence']), 'printed guitar page differs')
            if row.get('kind') == 'visual_review':
                import pymupdf
                with pymupdf.open(root / assets['PDF']['local_path']) as document:
                    page_bytes = document[page-1].read_contents()
                require(sha(page_bytes) == row.get('page_contents_sha256')
                        and isinstance(row.get('observation'), str) and row['observation'].strip(),
                        'visually reviewed PDF page guard differs')
            else:
                require(isinstance(text, str) and text.strip()
                        and text in pdf['page_evidence'][page-1]['text'], 'printed guitar evidence differs')
        if alternative:
            require(any(r.get('text') == label for r in printed),
                    'alternative-only role requires the exact printed instrument option')
    review = case.get('review')
    require(review.get('status') == 'file_reviewed_uncertain'
            and review.get('topic_id') not in {'solo', 'duo', 'trio', 'quartet', 'guitar_ensemble'}
            and review.get('guitar_player_count') is None and review.get('ensemble_player_count') is None,
            'broad admission cannot invent precise player counts')
    _check_review(work, review)
    title = review_file_title(planned['title_en'], read_mxl_title_evidence(
        root / assets['MUSICXML']['local_path'], mxl), pdf)
    if title['status'] == 'identity_conflict':
        require(bool(review.get('file_identity_note')), 'a source/file title conflict needs its visible warning')
    return {'id': identity, 'title_en': planned['title_en'], 'composer_en': planned['composer_en'],
        'source_url': planned['source_url'], 'assets': case['assets'], 'review': review}, {
        'status': 'accepted', 'reason': 'confirmed_guitar_related_file_scope_with_explicit_limits',
        'file_title_review': title, 'broad_case': deepcopy(case),
        'actual_guitar_part_ids': [p['part_id'] for p in guitar if p.get('kind') != 'printed_alternative'],
        'alternative_guitar_part_ids': [p['part_id'] for p in guitar if p.get('kind') == 'printed_alternative'],
        'mxl_evidence_sha256': canonical(mxl), 'pdf_complete_evidence_sha256': canonical(pdf),
        'boundary': 'Actual guitar presence and record-bound files; unknown roles/counts and original playback evidence remain unresolved.'}


def prepare(root):
    root = Path(root).resolve()
    frozen = baseline(root)
    state = check_continuation_state(root, frozen)
    require(state.get('stage') == 'broad-pending-review', 'latest publication broad baseline required')
    original_scope = load(root / BASE / 'scope-review.json')
    original_final = load(root / BASE / 'final-review.json')
    journal_path = root / BASE / 'broad-prepare.json'
    try:
        check_final_input_guards(root, original_final, original_scope)
    except AuditFailure:
        journal = load(journal_path) if journal_path.is_file() else {}
        require(journal.get('status') == 'prepared' and all(
            file_guard(root / BASE / name) in (journal['before'][name], journal['after'][name])
            for name in ('scope-review.json', 'final-review.json')),
            'inconsistent semantic inputs are not an interrupted guarded broad transaction')
    decisions = load(root / BROAD_INPUTS['decisions'])
    require(decisions.get('schema_version') == 1 and decisions.get('status') == 'complete', 'complete broad decisions required')
    entries = decisions['entries']; ids = [c['id'] for c in entries]
    other = decisions.get('outcomes', []); other_ids = [c['id'] for c in other]
    allowed = set(load(root / BROAD_SCOPE)['ids'])
    native_before = {w['id'] for w in frozen['documents']['sources/musescore/catalog.json']['value']['works']}
    require(ids and len(set(ids)) == len(ids) and set(ids) <= allowed and not set(ids) & native_before,
            'broad admission exceeds current pending native scope')
    require(len(set(other_ids)) == len(other_ids) and not set(ids) & set(other_ids)
            and set(ids) | set(other_ids) == allowed,
            'each current pending identity requires exactly one final broad outcome')
    planned = {w['id']: w for w in load(root / BASE / 'plan.json')['works']}
    journals = {f: load(root / BASE / (s + '-extraction.json'))
        for f, s in {'PDF': 'pdf', 'MUSICXML': 'mxl', 'MIDI': 'mid'}.items()}
    # Resume from the captured canonical reviews, never accumulate or regenerate
    # earlier publication values under this new broad interpretation.
    import zipfile, json
    with zipfile.ZipFile(root / BROAD_CONTINUATION) as archive:
        evidence = frozen['continuation']['evidence']
        scope = json.loads(archive.read(evidence[str(BASE / 'scope-review.json')]['member']))
        final = json.loads(archive.read(evidence[str(BASE / 'final-review.json')]['member']))
    projections = {w['id']: w for w in final['works']}
    guard = {key: file_guard(root / path) for key, path in BROAD_INPUTS.items()}
    for case in entries:
        identity = case['id']
        assets = {label: j['records'][identity]['asset'] for label, j in journals.items()}
        projection, outcome = check_case(root, planned[identity], case, assets)
        scope['records'][identity]['status'] = 'accepted'
        scope['records'][identity]['reason'] = outcome['reason']
        scope['records'][identity]['broad_review'] = outcome
        projections[identity] = projection
        final['records'][identity] = outcome
    for case in other:
        identity = case['id']
        assets = {label: j['records'][identity]['asset'] for label, j in journals.items()}
        outcome = check_outcome(root, planned[identity], case, assets)
        scope['records'][identity]['status'] = outcome['status']
        scope['records'][identity]['reason'] = outcome['reason']
        scope['records'][identity]['broad_review'] = outcome
        final['records'][identity] = {**final['records'].get(identity, {}), **outcome}
    scope['accepted_ids'] = sorted(set(scope['accepted_ids']) | set(ids))
    scope['broad_review'] = guard
    scope['summary'] = {**scope.get('summary', {}), 'broad_guitar_related_admissions': len(ids),
        'statuses': dict(Counter(r['status'] for r in scope['records'].values()))}
    final['works'] = [projections[i] for i in sorted(projections)]
    final['inputs'] = {key: file_guard(root / path) for key, path in FINAL_INPUT_PATHS.items()}
    final['broad_review'] = guard
    final['summary'] = {**final.get('summary', {}), 'scope_accepted': len(scope['accepted_ids']),
        'new_three_format_records': len(projections), 'broad_guitar_related_admissions': len(ids),
        'statuses': dict(Counter(r['status'] for r in final['records'].values())),
        'topics': dict(Counter(r['review']['topic_id'] for r in projections.values())),
        'review_statuses': dict(Counter(r['review']['status'] for r in projections.values()))}
    with zipfile.ZipFile(root / BROAD_CONTINUATION) as archive:
        before = {name: file_guard_from_bytes(archive.read(evidence[str(BASE / name)]['member']))
            for name in ('scope-review.json', 'final-review.json')}
    write_semantic_transaction(root, scope, final, before)
    return {'status': 'prepared', 'admissions': len(ids), 'native_catalog_modified': False}


def file_guard_from_bytes(body):
    return {'sha256': sha(body), 'size': len(body)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    args = parser.parse_args()
    import json
    from source_adapters import pdmx_assets as pdf_methods, pdmx_formats as format_methods
    root = args.root.resolve()
    with pdf_methods.source_lock(root / 'sources/musescore/.expansion.lock'), format_methods._source_locks(root):
        result = prepare(root)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
