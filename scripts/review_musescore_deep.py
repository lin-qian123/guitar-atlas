#!/usr/bin/env python
"""Lossless private receipt and fresh-file verification of the fixed 549 scope.

The complete original proposal JSON values and optional temporary producer
source are embedded once. Default verification needs none of those temporary
files and never rewrites a receipt, source catalog, score or historical review.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import io
import os
from pathlib import Path
import re
import tempfile

import review_musescore_remaining as shared
from catalog_instrumentation import per_record_guard
from review_musescore_expansion_final import validate_extraction_journal
from score_instrumentation import read_mxl_evidence
from score_midi_crosscheck import read_sounding_midi
from verify_musescore_expansion import (check_final_input_guards, FINAL_INPUT_PATHS,
    FINAL_METHOD_PATHS, SCOPE_METHOD_PATHS, EXACT_CASE_PATH)

BASE = shared.BASE
SCOPE = BASE / 'deep-review-scope.json'
DESTINATION = BASE / 'deep-review.json.gz'
METHOD = Path('scripts/review_musescore_deep.py')
PROPOSALS = {name: BASE / ('deep-review-' + name + '.json') for name in ('a', 'b', 'root')}
AUXILIARY_SOURCES = {'b_producer': Path('scripts/review_musescore_deep_b.py')}
EXPECTED_COUNT = 549
EXPECTED_COHORTS = {'a': 275, 'b': 274}
EXPECTED_PAGES = 5709
EXPECTED_ROOT_IDS = {'musescore:4796528'}
FORMATS = shared.FORMATS
require = shared.require
_PLACEHOLDER = re.compile(r'awaiting.*semantic|individual semantic.*pending|semantic.*in.progress', re.I)


def _secure(root, relative):
    path = shared._path(root, relative)
    current = root
    for part in Path(relative).parts:
        current /= part
        require(not current.is_symlink(), 'symlink in a deep-review input or output path')
    return path


def _json(root, relative, states):
    _secure(root, relative)
    return shared._read_json(root, relative, states)


def _load_context(root):
    from expand_musescore_library import DEEP_CONTINUATION, _baseline_file
    root, states = Path(root).resolve(), {}
    manifest, scope_guard = _json(root, SCOPE, states)
    ids, cohorts = manifest.get('ids'), manifest.get('cohorts')
    require(manifest.get('schema_version') == 1 and isinstance(ids, list)
            and len(ids) == EXPECTED_COUNT and all(isinstance(identity, str)
                and re.fullmatch(r'musescore:[1-9][0-9]*', identity) for identity in ids)
            and len(set(ids)) == len(ids), 'deep scope must contain exactly its fixed unique native identities')
    require(isinstance(cohorts, dict) and set(cohorts) == set(EXPECTED_COHORTS), 'deep cohort names differ')
    for name, count in EXPECTED_COHORTS.items():
        require(isinstance(cohorts[name], list) and len(cohorts[name]) == count
                and all(isinstance(identity, str) for identity in cohorts[name])
                and len(set(cohorts[name])) == count, 'deep cohort coverage differs')
    require(set(cohorts['a']).isdisjoint(cohorts['b']) and set(cohorts['a']) | set(cohorts['b']) == set(ids),
            'deep cohorts must form an exact disjoint partition')
    archive = _secure(root, DEEP_CONTINUATION)
    capture, capture_guard = _json(root, BASE / 'deep-baseline-capture.json', states)
    archive_guard = shared._file_guard(root, DEEP_CONTINUATION, states)
    require(capture.get('status') == 'captured' and capture.get('sha256') == archive_guard['sha256'],
            'deep baseline no longer matches its completed capture receipt')
    frozen = _baseline_file(archive, shared._stamp(archive))
    stage = frozen.get('continuation', {})
    require(stage.get('stage') == 'deep-pending-review' and stage.get('review_scope_path') == str(SCOPE)
            and stage.get('review_scope_guard') == scope_guard and stage.get('pending_records') == len(ids)
            and capture.get('records') == stage.get('prior_record_count'), 'scope differs from the captured published stage')
    published_ids = {row['id'] for row in frozen['documents']['sources/musescore/catalog.json']['value']['works']}
    require(not published_ids & set(ids), 'deep scope contains an already published native record')
    del frozen
    _baseline_file.cache_clear()
    prior_guard = shared._file_guard(root, BASE / 'remaining-review.json.gz', states)
    require(prior_guard['sha256'] == manifest.get('prior_remaining_review_sha256')
            and stage['immutable_inputs'][str(BASE / 'remaining-review.json.gz')] == prior_guard,
            'historical 759-review receipt changed')
    plan, plan_guard = _json(root, BASE / 'plan.json', states)
    require(stage['immutable_inputs'].get(str(BASE / 'plan.json')) == plan_guard,
            'native plan differs from the frozen deep-stage capture')
    require(plan.get('status') == 'prepared' and isinstance(plan.get('works'), list), 'prepared native plan required')
    works = {work['id']: work for work in plan['works']}
    require(len(works) == len(plan['works']) and set(ids) <= set(works), 'deep identities outside the frozen native plan')
    for name in ('scope-review.json', 'final-review.json'):
        _secure(root, BASE / name)
    scope, scope_rows, scope_bytes = shared._read_report(root, BASE / 'scope-review.json', states, shared._scope_outcome)
    final, final_rows, final_bytes = shared._read_report(root, BASE / 'final-review.json', states, shared._final_outcome)
    require(scope.get('status') == final.get('status') == 'complete'
            and scope.get('review_stage') == 'mxl_scope_only' and final.get('review_stage') == 'actual_pdf_mxl_midi'
            and set(scope_rows) == set(works), 'complete canonical scope/final reviews are required')
    accepted = scope.get('accepted_ids')
    require(isinstance(accepted, list) and len(set(accepted)) == len(accepted)
            and set(accepted) == {identity for identity, row in scope_rows.items() if row['status'] == 'accepted'}
            and set(final_rows) == set(accepted), 'canonical final/scope identity coverage differs')
    for relative in FINAL_METHOD_PATHS | SCOPE_METHOD_PATHS | set(FINAL_INPUT_PATHS.values()) | {EXACT_CASE_PATH}:
        _secure(root, relative)
    check_final_input_guards(root, final, scope)
    require(final['inputs']['configuration']['sha256'] == plan['configuration_sha256'],
            'current configuration differs from the frozen plan')
    semantic_guards = {**final['methods'], str(EXACT_CASE_PATH): final['reviewed_cases'],
        str(FINAL_INPUT_PATHS['configuration']): final['inputs']['configuration']}
    for relative, expected in semantic_guards.items():
        require(shared._file_guard(root, relative, states) == expected,
                'semantic method, case or configuration changed while binding the deep receipt')
    journals = {}
    guards = {'deep_scope': scope_guard, 'plan': plan_guard, 'scope_review': scope_bytes,
              'final_review': final_bytes, 'published_baseline': archive_guard,
              'baseline_capture': capture_guard, 'prior_remaining': prior_guard}
    for label, suffix in FORMATS.items():
        journal, guard = _json(root, BASE / (suffix + '-extraction.json'), states)
        require(stage['immutable_inputs'].get(str(BASE / (suffix + '-extraction.json'))) == guard,
                'format journal differs from the frozen deep-stage capture')
        validate_extraction_journal(journal, label, plan_ids=works, accepted_ids=accepted,
            plan_sha256=plan_guard['sha256'], configuration_sha256=plan['configuration_sha256'])
        require(set(ids) <= set(journal['records']), 'every deep candidate needs all three canonical assets')
        journals[label], guards[label] = journal, guard
    for name, relative in (('method', METHOD), ('shared_method', shared.METHOD)):
        _secure(root, relative)
        guards[name] = shared._file_guard(root, relative, states)
    return {'root': root, 'states': states, 'scope_manifest': manifest, 'ids': ids, 'works': works,
            'scope_rows': scope_rows, 'final_rows': final_rows, 'journals': journals, 'guards': guards,
            'semantic_input_verification': {'scope_inputs': scope['inputs'], 'final_inputs': final['inputs'],
                'final_methods': final['methods'], 'reviewed_cases': final['reviewed_cases']}}


def _native(row, work):
    require(isinstance(row, dict), 'proposal record must be an object')
    source = row.get('source', row)
    require(isinstance(source, dict) and row.get('id') == work['id']
            and row.get('native_record_sha256') == per_record_guard(work)
            and all(source.get(key) == work.get(key) for key in ('title_en', 'composer_en', 'source_url')),
            'deep proposal native identity or licensing guard changed: ' + work['id'])


def _pages(row):
    pages = row.get('PDF', {}).get('pages') if isinstance(row.get('PDF'), dict) else row.get('pdf_pages')
    require(isinstance(pages, list) and bool(pages)
            and all(isinstance(page, dict) and isinstance(page.get('text'), str) for page in pages)
            and [page.get('page') for page in pages] == list(range(1, len(pages) + 1)),
            'missing, duplicated or unordered complete PDF-page evidence')
    return pages


def _subset(claim, actual):
    if isinstance(claim, dict):
        return isinstance(actual, dict) and all(key in actual and _subset(value, actual[key]) for key, value in claim.items())
    if isinstance(claim, list):
        return isinstance(actual, list) and len(claim) == len(actual) and all(_subset(a, b) for a, b in zip(claim, actual))
    return type(claim) is type(actual) and claim == actual


def _decision(row, identity=None):
    status, reason = row.get('decision', row.get('proposed_status')), row.get('reason')
    require(isinstance(status, str) and status in {'accepted', 'excluded', 'pending'} and isinstance(reason, str)
            and reason.strip() and not _PLACEHOLDER.search(reason)
            and reason.strip().casefold() not in {'pending', 'unknown', 'uncertain', 'awaiting review', '待核', '待确认', '待审核'},
            'unfinished or nonspecific deep proposal decision: ' + str(identity or row.get('id', '?')))
    return {'status': status, 'reason': reason}


def _proposal_records(context, documents, original_bytes):
    require(isinstance(documents, dict) and set(documents) == set(PROPOSALS), 'all original deep proposal documents required')
    require(isinstance(original_bytes, dict) and set(original_bytes) == set(documents)
            and all(isinstance(guard, dict) and set(guard) == {'sha256', 'size'}
                and shared._SHA.fullmatch(str(guard['sha256'])) and type(guard['size']) is int and guard['size'] > 0
                for guard in original_bytes.values()), 'original proposal byte guards missing')
    records, originals = {}, {}
    for cohort in ('a', 'b'):
        document = documents[cohort]
        require(isinstance(document, dict) and document.get('status') == 'complete'
                and isinstance(document.get('records'), dict)
                and set(document['records']) == set(context['scope_manifest']['cohorts'][cohort]),
                'deep cohort review is incomplete or has changed identity coverage')
        require(document.get('cohort', cohort) == cohort, 'proposal cohort label changed')
        if 'scope_sha256' in document:
            require(document['scope_sha256'] == context['guards']['deep_scope']['sha256'], 'proposal scope byte guard changed')
        if 'scope_ids' in document:
            declared = document['scope_ids']
            require(isinstance(declared, list) and all(isinstance(identity, str) for identity in declared)
                    and len(declared) == len(set(declared))
                    and set(declared) == set(context['scope_manifest']['cohorts'][cohort]), 'proposal declared cohort coverage differs')
        inputs = document.get('inputs', {})
        require(isinstance(inputs, dict), 'invalid proposal input guards')
        for name, canonical in (('scope', 'deep_scope'), ('plan', 'plan'), ('prior_remaining', 'prior_remaining')):
            if name in inputs:
                require(inputs[name] == context['guards'][canonical], 'proposal input byte guard changed: ' + name)
        for identity, row in document['records'].items():
            _native(row, context['works'][identity])
            assets = {label: shared._asset(context, identity, label, shared._artifact(row, label)) for label in FORMATS}
            pages = _pages(row)
            decision = _decision(row, identity)
            outcome = shared._outcome(context['scope_rows'][identity], context['final_rows'].get(identity))
            records[identity] = {'native_record_sha256': per_record_guard(context['works'][identity]),
                'cohort': cohort, 'assets': assets, 'pdf_pages': len(pages), 'outcome': outcome,
                'decision': outcome['status'], 'reason': decision['reason'], 'proposal_decisions': {cohort: decision}}
            originals[identity] = row
    require(set(records) == set(context['ids']) and sum(row['pdf_pages'] for row in records.values()) == EXPECTED_PAGES,
            'deep review does not cover the exact candidate and PDF-page counts')
    root = documents['root']
    require(root.get('status') == 'complete' and isinstance(root.get('records'), dict)
            and set(root['records']) == EXPECTED_ROOT_IDS <= set(records), 'root follow-up identity coverage differs')
    for identity, row in root['records'].items():
        decision = _decision(row, identity)
        dryrun = row.get('production_final_dry_run', {})
        require(isinstance(dryrun, dict) and dryrun.get('status') in {'accepted', 'pending', 'excluded'},
                'root follow-up lacks its complete production review')
        for label in FORMATS:
            shared._asset(context, identity, label, dryrun.get('asset_guards', {}).get(label, {}))
        records[identity]['proposal_decisions']['root'] = decision
        records[identity]['reason'] = decision['reason']
    for row in records.values():
        decision = row['proposal_decisions'].get('root', row['proposal_decisions'][row['cohort']])
        row['proposal_status_matches_canonical'] = decision['status'] == row['decision']
        if not row['proposal_status_matches_canonical']:
            row['reason'] = row['outcome']['reason'] + '; original semantic proposal: ' + decision['reason']
    for document in documents.values():
        entries = document.get('entries')
        require(isinstance(entries, list) and all(isinstance(entry, dict) for entry in entries)
                and all(isinstance(entry.get('id'), str) for entry in entries)
                and len({entry.get('id') for entry in entries}) == len(entries), 'exact proposals need unique native identities')
        for entry in entries:
            identity = entry.get('id')
            require(identity in records and identity in document['records'], 'exact proposal outside its documented scope')
            _native(entry, context['works'][identity])
            require(all(entry.get(key) == records[identity]['assets'][label]['sha256']
                        for key, label in (('pdf_sha256', 'PDF'), ('mxl_sha256', 'MUSICXML'), ('midi_sha256', 'MIDI'))),
                    'exact proposal three-format byte guard changed')
    return records, originals


def _fresh_record(context, identity, original, record):
    root, states = context['root'], {}
    paths = {}
    for label, asset in record['assets'].items():
        paths[label] = _secure(root, asset['local_path'])
        actual = shared._file_guard(root, asset['local_path'], states)
        require(actual == {key: asset[key] for key in ('sha256', 'size')}, 'actual deep-review score bytes changed: ' + identity)
    mxl = read_mxl_evidence(paths['MUSICXML'])
    claimed_parts = original.get('MXL', {}).get('parts') if isinstance(original.get('MXL'), dict) else original.get('mxl_parts')
    require(isinstance(claimed_parts, list) and bool(claimed_parts)
            and all(isinstance(part, dict) and {'part_id', 'name', 'note_count', 'rest_count',
                'score_instruments', 'midi_instruments'} <= set(part) for part in claimed_parts)
            and _subset(claimed_parts, mxl['parts']), 'complete fresh MXL roles differ from proposal evidence: ' + identity)
    if 'mxl_groups' in original:
        require(original['mxl_groups'] == mxl['part_groups'], 'fresh MXL part groups differ')
    midi = read_sounding_midi(paths['MIDI'])
    claimed_midi = original.get('MIDI', original.get('midi_evidence'))
    require(isinstance(claimed_midi, dict) and claimed_midi == midi, 'fresh complete MIDI events differ from proposal evidence: ' + identity)
    import fitz
    pages = _pages(original)
    with paths['PDF'].open('rb') as stream:
        require(stream.read(5) == b'%PDF-', 'actual candidate is not a PDF')
    page_hashes = []
    with fitz.open(paths['PDF']) as document:
        require(document.is_pdf and not document.needs_pass and len(document) == len(pages),
                'fresh PDF parse or page count differs from complete proposal evidence')
        for claimed, page in zip(pages, document):
            text = claimed['text']
            require(text == page.get_text(sort=True) or text == page.get_text(sort=False),
                    'fresh complete PDF-page text differs from proposal evidence: ' + identity + ' page ' + str(claimed['page']))
            page_hashes.append(hashlib.sha256(text.encode()).hexdigest())
    require(all(shared._stamp(path) == stamp for path, stamp in states.items()), 'actual formats changed while parsing')
    return identity, {'mxl_complete_evidence_sha256': shared.canonical_sha256(mxl),
        'midi_complete_evidence_sha256': shared.canonical_sha256(midi), 'pdf_all_page_text_sha256': page_hashes,
        'format_structures_freshly_verified': True}, states


def _derived(context, documents, original_bytes):
    records, originals = _proposal_records(context, documents, original_bytes)
    # PyMuPDF documents are read sequentially in this process. Its native
    # document operations are not safe in a Python thread pool.
    for identity, row in records.items():
        _, fresh, states = _fresh_record(context, identity, originals[identity], row)
        for path, stamp in states.items():
            require(path not in context['states'] or context['states'][path] == stamp, 'shared score object changed during review')
            context['states'][path] = stamp
        row.update(fresh)
    summary = {'records': len(records), 'pdf_pages': sum(row['pdf_pages'] for row in records.values()),
        'format_record_associations': {label: len(records) for label in FORMATS},
        'unique_physical_format_objects': {label: len({row['assets'][label]['sha256'] for row in records.values()}) for label in FORMATS},
        'statuses': dict(Counter(row['decision'] for row in records.values())),
        'canonical_reasons': dict(Counter(row['outcome']['reason'] for row in records.values())), 'missing_records': 0,
        'boundary': 'Fresh structural, exact native, complete PDF-page and event evidence does not certify every visual glyph, repaired MIDI, acoustic fidelity or resolved instrumentation.'}
    shared._unchanged(context)
    return records, summary


def _auxiliary(bundle):
    values = bundle.get('auxiliary_sources', {})
    require(isinstance(values, dict) and set(values) <= set(AUXILIARY_SOURCES), 'unexpected temporary producer source')
    for key, row in values.items():
        require(isinstance(row, dict) and set(row) == {'path', 'text', 'sha256', 'size'}
                and row['path'] == str(AUXILIARY_SOURCES[key]) and isinstance(row['text'], str), 'invalid embedded producer source')
        body = row['text'].encode('utf-8')
        require(len(body) == row['size'] and hashlib.sha256(body).hexdigest() == row['sha256'], 'embedded producer source bytes changed')


def _supplement_records(context, bundle, records, summary):
    """Bind an optional lossless follow-up to current exact cases and outcomes."""
    if 'review_supplement' not in bundle:
        return records, summary
    supplement = bundle['review_supplement']
    require(isinstance(supplement, dict) and set(supplement) == {'value', 'original_bytes', 'semantic_sha256'},
            'invalid embedded review supplement')
    document, original = supplement['value'], supplement['original_bytes']
    require(isinstance(original, dict) and set(original) == {'sha256', 'size'}
            and shared._SHA.fullmatch(str(original['sha256'])) and type(original['size']) is int
            and original['size'] > 0 and supplement['semantic_sha256'] == shared.canonical_sha256(document),
            'lossless supplement JSON values or original byte guard changed')
    require(isinstance(document, dict) and document.get('schema_version') == 1
            and document.get('status') == 'complete' and isinstance(document.get('records'), list)
            and 0 < len(document['records']) <= len(context['ids']), 'incomplete review supplement')
    rows = document['records']
    identities = [row.get('id') if isinstance(row, dict) else None for row in rows]
    require(all(isinstance(identity, str) and identity in records for identity in identities)
            and len(set(identities)) == len(identities), 'duplicate or out-of-scope supplement identity')
    require(all(isinstance(row.get('exact_entry'), dict) for row in rows), 'missing complete supplement exact case')
    if 'scope_ids' in document:
        declared = document['scope_ids']
        require(isinstance(declared, list) and len(declared) == len(identities)
                and all(isinstance(identity, str) for identity in declared)
                and set(declared) == set(identities), 'supplement declared identity scope differs')
    cases, case_guard = _json(context['root'], EXACT_CASE_PATH, context['states'])
    require(case_guard == context['semantic_input_verification']['reviewed_cases']
            and isinstance(cases, dict) and cases.get('schema_version') == 1
            and isinstance(cases.get('entries'), list), 'current exact cases changed while binding supplement')
    entries = cases['entries']
    require(all(isinstance(entry, dict) and isinstance(entry.get('id'), str) for entry in entries)
            and len({entry['id'] for entry in entries}) == len(entries), 'duplicate or invalid current exact cases')
    current = {entry['id']: entry for entry in entries}
    if 'entries' in document:
        declared = document['entries']
        require(isinstance(declared, list) and all(isinstance(entry, dict)
                    and isinstance(entry.get('id'), str) for entry in declared)
                and len(declared) == len(rows) and {entry.get('id') for entry in declared} == set(identities)
                and all(shared.canonical_sha256(entry) == shared.canonical_sha256(
                            next(row['exact_entry'] for row in rows if row['id'] == entry.get('id')))
                        for entry in declared), 'supplement exact-entry declarations differ')
    for row in rows:
        identity, entry = row['id'], row.get('exact_entry')
        require(isinstance(entry, dict) and identity in current
                and shared.canonical_sha256(entry) == shared.canonical_sha256(current[identity]),
                'supplement must preserve the complete current exact case: ' + identity)
        _native(entry, context['works'][identity])
        require(row.get('native_record_sha256') == per_record_guard(context['works'][identity]),
                'supplement native identity or licensing guard changed: ' + identity)
        decision = _decision(row, identity)
        outcome = records[identity]['outcome']
        require(decision['status'] == outcome['status'] and row.get('canonical_reason') == outcome['reason'],
                'supplement decision or reason differs from canonical outcome: ' + identity)
        reason = decision['reason'].strip()
        require(len(reason) >= 24 and reason != outcome['reason'] and reason.casefold() not in {
            'review complete; see evidence.', 'review completed; see evidence.',
            'all files have been reviewed.', 'all evidence has been reviewed.'},
            'unfinished or nonspecific supplement reason: ' + identity)
        require(isinstance(row.get('assets'), dict) and set(row['assets']) == set(FORMATS),
                'supplement needs complete three-format guards: ' + identity)
        for label, hash_key in (('PDF', 'pdf_sha256'), ('MUSICXML', 'mxl_sha256'), ('MIDI', 'midi_sha256')):
            evidence = row['assets'][label]
            require(isinstance(evidence, dict) and {'sha256', 'size', 'local_path',
                    'archive_member', 'archive_sha256'} <= set(evidence), 'invalid supplement format guard: ' + identity)
            asset = shared._asset(context, identity, label, evidence)
            require(asset == records[identity]['assets'][label] and entry.get(hash_key) == asset['sha256'],
                    'supplement exact-case format guard changed: ' + identity + ' ' + label)
        records[identity]['proposal_decisions']['supplement'] = {**decision, 'canonical_reason': outcome['reason']}
        records[identity]['reason'] = decision['reason']
        records[identity]['proposal_status_matches_canonical'] = True
    return records, {**summary, 'supplement_records': len(rows)}


def _verify_bundle(bundle, context, *, refresh=False, derived=None):
    require(isinstance(bundle, dict) and bundle.get('schema_version') == 1 and bundle.get('status') == 'complete'
            and bundle.get('scope_manifest') == context['scope_manifest'], 'invalid or changed consolidated deep scope')
    documents = bundle.get('original_proposals')
    require(isinstance(documents, dict) and set(documents) == set(PROPOSALS), 'missing lossless original deep proposals')
    digests = {key: shared.canonical_sha256(value) for key, value in documents.items()}
    require(bundle.get('proposal_semantic_sha256') == digests, 'lossless original JSON values changed')
    _auxiliary(bundle)
    records, summary = derived if derived is not None else _derived(context, documents, bundle.get('proposal_original_bytes'))
    records, summary = _supplement_records(context, bundle, records, summary)
    if refresh:
        frozen = {'deep_scope', 'plan', 'published_baseline', 'baseline_capture', 'prior_remaining', *FORMATS}
        require(all(bundle.get('canonical_inputs', {}).get(key) == context['guards'][key] for key in frozen),
                'refresh cannot replace frozen scope, native plan, history or acquired format bytes')
    else:
        require(bundle.get('canonical_inputs') == context['guards']
                and bundle.get('semantic_review_inputs') == context['semantic_input_verification'],
                'canonical review inputs changed; refresh outcomes explicitly')
        require(bundle.get('records') == records and bundle.get('summary') == summary, 'consolidated deep decisions or evidence changed')
    shared._unchanged(context)
    return records, summary


def _load_bundle(context):
    path = _secure(context['root'], DESTINATION)
    before = shared._stamp(path)
    value = shared._read_gzip_json(path)
    require(shared._stamp(path) == before, 'deep receipt changed while reading')
    context['states'][path] = before
    return value


def _atomic_gzip(context, value):
    root = context['root']
    destination = _secure(root, DESTINATION)
    destination.parent.mkdir(parents=True, exist_ok=True)
    original = shared._stamp(destination) if destination.exists() else None
    expected = shared.canonical_sha256(value)
    descriptor, name = tempfile.mkstemp(prefix='deep-review-', suffix='.json.gz.part', dir=destination.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, 'wb') as output:
            with gzip.GzipFile(filename='', fileobj=output, mode='wb', compresslevel=6, mtime=0) as compressed:
                with io.BufferedWriter(compressed, buffer_size=256 * 1024) as buffered:
                    total = 0
                    for chunk in shared._ENCODER.iterencode(value):
                        body = chunk.encode('utf-8'); total += len(body)
                        require(total <= shared.MAX_JSON_BYTES, 'deep receipt exceeds serialization bound')
                        buffered.write(body)
            output.flush(); os.fsync(output.fileno())
        recovered = shared._read_gzip_json(temporary)
        require(shared.canonical_sha256(recovered) == expected, 'compressed deep receipt semantic readback differs')
        require(all(shared.canonical_sha256(recovered['original_proposals'][key]) == digest
                    for key, digest in value['proposal_semantic_sha256'].items()), 'lossless compressed proposal readback differs')
        shared._unchanged(context)
        _secure(root, DESTINATION)
        require((shared._stamp(destination) if destination.exists() else None) == original, 'deep receipt changed before atomic replacement')
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    context['states'].pop(destination, None)
    guard = shared._file_guard(root, DESTINATION, context['states'])
    shared._unchanged(context)
    return {'path': str(DESTINATION), **guard, 'semantic_sha256': expected}


def consolidate(root):
    context = _load_context(root)
    require(not _secure(context['root'], DESTINATION).exists(), 'deep receipt already exists; verify or explicitly refresh')
    documents, byte_guards = {}, {}
    for name, relative in PROPOSALS.items():
        documents[name], byte_guards[name] = _json(context['root'], relative, context['states'])
    auxiliary = {}
    for name, relative in AUXILIARY_SOURCES.items():
        path = _secure(context['root'], relative)
        if path.exists():
            guard = shared._file_guard(context['root'], relative, context['states'])
            require(guard['size'] <= 1024 * 1024, 'temporary producer source exceeds bound')
            text = path.read_bytes().decode('utf-8')
            body = text.encode('utf-8')
            require(len(body) == guard['size'] and hashlib.sha256(body).hexdigest() == guard['sha256'], 'temporary producer source changed')
            auxiliary[name] = {'path': str(relative), 'text': text, **guard}
    derived = _derived(context, documents, byte_guards)
    records, summary = derived
    bundle = {'schema_version': 1, 'status': 'complete', 'checked_at': datetime.now(timezone.utc).isoformat(),
        'scope_manifest': context['scope_manifest'], 'original_proposals': documents,
        'proposal_original_bytes': byte_guards, 'proposal_semantic_sha256': {
            key: shared.canonical_sha256(value) for key, value in documents.items()}, 'auxiliary_sources': auxiliary,
        'canonical_inputs': context['guards'], 'semantic_review_inputs': context['semantic_input_verification'],
        'records': records, 'summary': summary}
    _verify_bundle(bundle, context, derived=derived)
    return {'status': 'consolidated', **_atomic_gzip(context, bundle), 'summary': summary}


def verify(root):
    context = _load_context(root)
    bundle = _load_bundle(context)
    _, summary = _verify_bundle(bundle, context)
    guard = shared._file_guard(context['root'], DESTINATION, context['states'])
    shared._unchanged(context)
    return {'status': 'verified', 'path': str(DESTINATION), **guard,
        'semantic_sha256': shared.canonical_sha256(bundle), 'proposal_semantic_sha256': bundle['proposal_semantic_sha256'], 'summary': summary}


def refresh_outcomes(root, supplement=None):
    context = _load_context(root)
    bundle = _load_bundle(context)
    if supplement is not None:
        relative = Path(supplement)
        if relative.is_absolute():
            require(relative.is_relative_to(context['root']), 'supplement must be inside the project root')
            relative = relative.relative_to(context['root'])
        value, original = _json(context['root'], relative, context['states'])
        embedded = {'value': value, 'original_bytes': original, 'semantic_sha256': shared.canonical_sha256(value)}
        require('review_supplement' not in bundle or bundle['review_supplement'] == embedded,
                'cannot replace an existing lossless review supplement')
        bundle['review_supplement'] = embedded
    records, summary = _verify_bundle(bundle, context, refresh=True)
    bundle.update(checked_at=datetime.now(timezone.utc).isoformat(), canonical_inputs=context['guards'],
        semantic_review_inputs=context['semantic_input_verification'], records=records, summary=summary)
    _verify_bundle(bundle, context, derived=(records, summary))
    return {'status': 'outcomes_refreshed', **_atomic_gzip(context, bundle), 'summary': summary}


def main():
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--consolidate', action='store_true')
    actions.add_argument('--verify', action='store_true', help='default; temporary proposals and producer scripts are unnecessary')
    actions.add_argument('--refresh-outcomes', action='store_true')
    parser.add_argument('--supplement', type=Path, help='complete exact-case follow-up; only with --refresh-outcomes')
    args = parser.parse_args()
    if args.supplement is not None and not args.refresh_outcomes:
        parser.error('--supplement requires --refresh-outcomes')
    action = consolidate if args.consolidate else refresh_outcomes if args.refresh_outcomes else verify
    result = action(args.root, supplement=args.supplement) if args.refresh_outcomes else action(args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
