#!/usr/bin/env python
"""Append actual-file-reviewed PDMX guitar records without replaying old imports.

All traffic is local: whole-archive receipts bind exact CSV member locators.
The old 924 native objects, acquisition journals and semantic decisions remain
historical inputs. New extraction and publication decisions have their own
resumable journals; no title-based work merging is performed.
"""
from __future__ import annotations

import argparse
import base64
import copy
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import tarfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

from source_adapters.pdmx import _atomic_json, _stream_members
from source_adapters.pdmx import _metadata_locator
from source_adapters import pdmx_assets as pdf_methods, pdmx_formats as format_methods

BASE = Path('sources/musescore/expansion')
CONFIG = Path('config/musescore_pdmx_expansion.json')
FORMATS = {'PDF': ('pdf', 'pdf'), 'MUSICXML': ('mxl', 'mxl'), 'MIDI': ('mid', 'mid')}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def canonical(value):
    return sha(json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(',', ':'), allow_nan=False).encode())


def baseline(root):
    with gzip.open(root / BASE / 'baseline.json.gz', 'rt', encoding='utf-8') as stream:
        return json.load(stream)


def original_catalog(root):
    return baseline(root)['documents']['sources/musescore/catalog.json']['value']


def verify_archives(root):
    """Reproduce fresh checksums without downloading or rewriting source files."""
    config = load(root / CONFIG)
    result = {'schema_version': 1, 'source_id': 'musescore', 'status': 'running',
              'checked_at': pdf_methods.now(), 'files': {}, 'live_source_requests': 0}
    destination = root / BASE / 'archive-integrity.json'
    try:
        for filename, expected in config['files'].items():
            if filename not in {'PDMX.csv', 'metadata.tar.gz', 'pdf.tar.gz', 'mxl.tar.gz', 'mid.tar.gz'}:
                raise ValueError('unapproved publication file in expansion configuration')
            path = root / 'sources/musescore/pdmx' / filename
            if path.is_symlink() or not path.is_file():
                raise ValueError('frozen publication file must be a regular local file')
            before = pdf_methods._stat_fingerprint(path)
            md5, digest, size = hashlib.md5(), hashlib.sha256(), 0
            with path.open('rb') as stream:
                while block := stream.read(8*1024*1024):
                    size += len(block)
                    md5.update(block)
                    digest.update(block)
            if (pdf_methods._stat_fingerprint(path) != before or size != expected['size']
                    or md5.hexdigest() != expected['md5'] or digest.hexdigest() != expected['sha256']):
                raise ValueError('frozen publication size/checksum mismatch: ' + filename)
            result['files'][filename] = {'bytes': size, 'md5': md5.hexdigest(),
                'sha256': digest.hexdigest(), 'stat': list(before)}
            print(json.dumps({'archive_verified': filename, 'bytes': size}), flush=True)
        # Validate every captured fingerprint again before the proof is complete.
        if any(list(pdf_methods._stat_fingerprint(root / 'sources/musescore/pdmx' / name)) != row['stat']
               for name, row in result['files'].items()):
            raise ValueError('publication files changed while completing archive receipt')
        result['status'] = 'complete'
    except BaseException as error:
        result.update(status='failed', error=str(error))
        raise
    finally:
        _atomic_json(destination, result)
    return {'status': result['status'], 'files': len(result['files']),
            'bytes': sum(row['bytes'] for row in result['files'].values())}


def guard_archive(root, code):
    """Use fresh independently calculated digests only for the same inode/stat."""
    config = load(root / CONFIG)
    proof = load(root / BASE / 'archive-integrity.json')
    if proof.get('status') != 'complete':
        raise ValueError('complete fresh whole-publication verification required')
    filename = code if code.endswith('.csv') else code + '.tar.gz'
    expected, actual = config['files'][filename], proof['files'][filename]
    path = root / 'sources/musescore/pdmx' / filename
    if (actual['bytes'] != expected['size'] or actual['md5'] != expected['md5']
            or actual['sha256'] != expected['sha256']
            or list(pdf_methods._stat_fingerprint(path)) != actual['stat']):
        raise ValueError('archive verification/configuration/stat guard disagreement: ' + filename)
    return path, actual


def locator(row, label):
    code, _ = FORMATS[label]
    return (pdf_methods._locator(row[code]) if label == 'PDF'
            else format_methods._locator(row[code], label))


def old_records_unchanged(root):
    old = original_catalog(root)
    current = load(root / 'sources/musescore/catalog.json')
    indexed = {row['id']: row for row in current['works']}
    if len(indexed) != len(current['works']):
        raise ValueError('duplicate native record identity')
    for row in old['works']:
        if indexed.get(row['id']) != row:
            raise ValueError('prior native record changed: ' + row['id'])
    if current['categories'] != old['categories']:
        raise ValueError('prior source categories changed')
    return old, current


def recall_member(summary):
    """Cheap actual-file recall; explicit excluded active roles stay separate.

    This does not establish final instrumentation or player counts. Empty
    placeholders are ignored only using complete full-MXL activity counters.
    Unknown/contradictory labels remain candidates for the detailed review.
    """
    from review_musescore_expansion import expansion_kind
    positives, exclusions, unknown = [], [], []
    for part in summary['parts']:
        if not any(part.get(field, 0) for field in ['note_count', 'harmony_count', 'frame_count', 'slash_count']):
            continue
        names = part.get('part_names', []) + part.get('instrument_names', [])
        kinds = {expansion_kind(name) for name in names if name.strip()}
        kinds.discard(None)
        declared_names = [name for name in part.get('instrument_names', []) if name.strip()]
        declared_values = [expansion_kind(name) for name in declared_names]
        declared_kinds = set(declared_values)
        declared_kinds.discard(None)
        if 'guitar' in kinds:
            positives.append(part['id'])
        negative = kinds & {'voice', 'electric_guitar', 'bass_guitar', 'synthesizer'}
        # A conflicting named role needs deeper review, rather than automatic
        # rejection of the complete work from one inconsistent declaration.
        acoustic_patch_conflict = ('electric_guitar' in negative
            and bool(set(part.get('midi_programs_1based', [])) & {25, 26}))
        primary = next(iter(part.get('part_names', [])), '')
        unknown_primary = bool(primary.strip()) and expansion_kind(primary) is None
        unanimous_excluded_declaration = (bool(declared_values) and None not in declared_values
            and len(declared_kinds) == 1 and declared_kinds <= negative)
        if (negative and kinds <= negative and unanimous_excluded_declaration
                and not unknown_primary and not acoustic_patch_conflict):
            exclusions.append({'part_id': part['id'], 'kinds': sorted(negative)})
        elif not kinds or len(kinds) > 1 or negative:
            unknown.append(part['id'])
    if exclusions:
        return {'selected': False, 'reason': 'explicit_active_excluded_file_role',
                'guitar_parts': positives, 'excluded_parts': exclusions, 'unresolved_parts': unknown}
    return {'selected': True, 'reason': 'actual_file_scope_recall',
            'guitar_parts': positives, 'excluded_parts': [], 'unresolved_parts': unknown}


def require_complete_mxl_scan(report):
    """Require every unique member inspected; keep parse/missing limits visible."""
    if not isinstance(report, dict) or not isinstance(report.get('counts'), dict):
        raise ValueError('complete inspected MXL scan counts required')
    counts = report.get('counts', {})
    failures, missing = report.get('parse_failures'), report.get('missing_mxl_members')
    inspected, unique, validated = (counts.get(key) for key in
        ['inspected_mxl_members', 'unique_mxl_members', 'validated_mxl_members'])
    failed, absent = counts.get('parse_failures', 0), counts.get('csv_mxl_members_missing_archive')
    if (report.get('status') not in {'complete', 'complete_with_parse_or_missing_boundaries'}
            or report.get('archive_checksum_freshly_reverified') is not True
            or any(type(value) is not int or value < 0 for value in [inspected, unique, validated, failed, absent])
            or not unique or inspected != unique or validated + failed != inspected
            or not isinstance(failures, list) or len(failures) != failed
            or not isinstance(missing, list) or len(missing) != absent
            or any(not isinstance(member, str) for member in missing) or len(set(missing)) != absent):
        raise ValueError('complete inspected MXL scan with exact parse/missing boundaries required')
    failure_members = set()
    for row in failures:
        if (not isinstance(row, dict) or not isinstance(row.get('source_record_ids'), list)
                or any(not isinstance(identity, str) or not identity.isascii() or not identity.isdigit()
                       or identity.startswith('0') for identity in row['source_record_ids'])
                or type(row.get('bytes')) is not int or row['bytes'] < 0
                or not isinstance(row.get('sha256'), str) or len(row['sha256']) != 64
                or not all(char in '0123456789abcdef' for char in row['sha256'])
                or not isinstance(row.get('reason'), str) or not row['reason']
                or not isinstance(row.get('error_type'), str) or not row['error_type']):
            raise ValueError('complete original MXL parse-failure evidence required')
        member = format_methods._locator(row.get('member'), 'MUSICXML')
        if member in failure_members:
            raise ValueError('duplicate MXL parse-failure member')
        failure_members.add(member)
    if any(format_methods._locator(member, 'MUSICXML') != member for member in missing) or failure_members & set(missing):
        raise ValueError('MXL parse/missing member evidence disagrees')
    all_valid = not failed and not absent
    if (report.get('coverage_complete') is not all_valid
            or report['status'] != ('complete' if all_valid else 'complete_with_parse_or_missing_boundaries')):
        raise ValueError('MXL inspected completion must distinguish parse/missing boundaries')
    fresh, archive = report.get('fresh_archive_integrity'), report.get('archive_input')
    if (not isinstance(fresh, dict) or not isinstance(archive, dict)
            or any(archive.get(key) != fresh.get(key) for key in ['bytes', 'md5', 'sha256', 'stat'])):
        raise ValueError('MXL scan input differs from freshly bound archive integrity')
    return counts


def recall_selection(root):
    raw = (root / BASE / 'mxl-scope.json').read_bytes()
    mxl = json.loads(raw)
    require_complete_mxl_scan(mxl)
    _, integrity = guard_archive(root, 'mxl')
    _, csv_integrity = guard_archive(root, 'PDMX.csv')
    if (mxl.get('fresh_archive_integrity') != integrity
            or mxl.get('csv_input_stat') != csv_integrity['stat']):
        raise ValueError('MXL full scan differs from fresh whole-publication evidence')
    metadata = load(root / BASE / 'metadata-selection.json')
    clean_ids = set(map(str, metadata.get('candidate_ids', [])))
    decisions, selected = {}, set()
    for identity, row in mxl['candidates'].items():
        decision = recall_member(row)
        has_file_signal = bool(row.get('guitar_label_evidence') or row.get('tab_part_ids')
                               or row.get('gm_programs_0based'))
        if decision['selected'] and (identity in clean_ids or has_file_signal):
            selected.add(identity)
        else:
            decision['selected'] = False
            if not has_file_signal and identity not in clean_ids:
                decision['reason'] = 'no_positive_guitar_or_fretted_file_recall'
        decisions['musescore:' + identity] = decision
    # Source-explicit acoustic candidates are retained even when the notation
    # recall had no signal: a source/file mismatch needs an explicit decision.
    for identity in clean_ids - mxl['candidates'].keys():
        selected.add(identity)
        decisions['musescore:' + identity] = {'selected': True, 'reason': 'source_explicit_guitar_file_recall_absent'}
    report = {'schema_version': 1, 'status': 'complete', 'mxl_scope_sha256': sha(raw),
        'method_sha256': sha(Path(__file__).read_bytes()),
        'counts': dict(Counter(row['reason'] for row in decisions.values())),
        'selected_ids': sorted(selected, key=int), 'records': decisions}
    _atomic_json(root / BASE / 'recall-selection.json', report)
    _atomic_json(root / BASE / 'selected-records.json', report['selected_ids'])
    return {'selected_records_including_old_scope': len(selected), 'reasons': report['counts']}


def prepare(root, selected_ids, *, extend_plan=False):
    """Bind a final file-recall selection to complete frozen native metadata."""
    from source_adapters.pdmx_expansion import validate_candidate
    if extend_plan:
        recover_plan_extension(root)
    guard_archive(root, 'PDMX.csv')
    guard_archive(root, 'metadata')
    old, _ = old_records_unchanged(root)
    existing = {row['id'] for row in old['works']}
    source_path = root / BASE / 'candidate-metadata.json'
    source_bytes = source_path.read_bytes()
    source = json.loads(source_bytes)
    if source.get('status') != 'complete':
        raise ValueError('full metadata candidate snapshot required')
    selected_ids = set(map(str, selected_ids))
    csv_rows = {}
    csv_path, _ = guard_archive(root, 'PDMX.csv')
    with csv_path.open(encoding='utf-8-sig', newline='') as stream:
        for csv_row in csv.DictReader(stream, strict=True):
            native_id, _ = _metadata_locator(csv_row['metadata'])
            if native_id in selected_ids:
                if native_id in csv_rows:
                    raise ValueError('duplicate authoritative native CSV identity')
                csv_rows[native_id] = csv_row
    if set(csv_rows) != selected_ids:
        raise ValueError('selected native identities absent from authoritative CSV')
    decisions, works = {}, []
    for native_id in sorted(selected_ids, key=int):
        identity = 'musescore:' + native_id
        if identity in existing:
            continue
        row = source['records'].get(native_id)
        if row is None:
            raise ValueError('file candidate lacks complete frozen metadata: ' + identity)
        if row['csv'] != csv_rows[native_id]:
            raise ValueError('candidate snapshot differs from exact authoritative CSV: ' + identity)
        work, reason, evidence = validate_candidate(row['csv'], row['metadata'])
        decisions[identity] = {'status': 'candidate' if work else 'excluded_metadata',
            'reason': reason, 'evidence': evidence,
            'metadata_member': row['metadata_member'],
            'metadata_member_sha256': row['metadata_member_sha256']}
        if work:
            # Every locator remains the exact authoritative CSV transcription.
            missing, invalid = [], []
            for label in FORMATS:
                declared = row['csv'].get(FORMATS[label][0])
                if declared in (None, '', 'NA'):
                    missing.append(label)
                    continue
                try:
                    locator(row['csv'], label)
                except ValueError as error:
                    invalid.append({'format': label, 'declared_locator': declared, 'reason': str(error)})
            if missing or invalid:
                decisions[identity].update(
                    status='pending_missing_publication_format' if missing else 'pending_invalid_publication_locator',
                    reason='native identity is valid; declared publication formats require separate recovery',
                    missing_formats=missing, invalid_format_locators=invalid,
                    declared_locators={label: row['csv'].get(FORMATS[label][0]) for label in FORMATS})
                continue
            works.append(work)
    result = {'schema_version': 1, 'status': 'prepared', 'source_id': 'musescore',
        'scope_version': load(root / CONFIG)['scope_version'],
        'configuration_sha256': sha((root / CONFIG).read_bytes()),
        'original_catalog_sha256': baseline(root)['documents']['sources/musescore/catalog.json']['sha256'],
        'candidate_snapshot_sha256': sha(source_bytes),
        'selected_native_ids': sorted(set(map(str, selected_ids)), key=int),
        'decisions': decisions, 'works': works}
    destination = root / BASE / 'plan.json'
    if destination.exists() and load(destination) != result:
        if not extend_plan:
            raise ValueError('prepared scope changed; use explicit --extend-plan only during the MXL stage')
        extend_prepared_plan(root, result)
    elif not destination.exists():
        _atomic_json(destination, result)
    statuses = Counter(row['status'] for row in decisions.values())
    return {'selected': len(decisions), 'metadata_accepted': len(works),
            'pending_missing_publication_format': statuses['pending_missing_publication_format'],
            'pending_invalid_publication_locator': statuses['pending_invalid_publication_locator'],
            'excluded': statuses['excluded_metadata']}


def validate_asset(root, asset):
    if asset['format'] == 'PDF':
        pdf_methods._validate_object(root, asset)
    else:
        format_methods._validate_object(root, asset, asset['format'])


def fresh_verified_records(root, records, label, members, archive_sha):
    """Read-only bounded validation; journal values are never reconstructed."""
    def check_one(item):
        identity, record = item
        if record.get('status') != 'verified':
            return None
        asset = record['asset']
        if (asset.get('format') != label or asset.get('archive_member') != members[identity]
                or asset.get('archive_sha256') != archive_sha):
            raise ValueError('prior expansion object format/native member drift')
        validate_asset(root, asset)
        return asset['archive_member'], record
    selected = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for checked in pool.map(check_one, records.items()):
            if checked is not None:
                name, record = checked
                if name in selected and selected[name] != record:
                    raise ValueError('shared member has conflicting prior extraction records')
                selected[name] = record
    return selected


def extension_stage_guard(root):
    pdf_methods._safe_local(root, root / BASE)
    if any((root / BASE / name).exists() or (root / BASE / name).is_symlink() for name in
           ['pdf-extraction.json', 'mid-extraction.json', 'commit.json', 'integration.json']):
        raise ValueError('plan extension is permitted only during the MXL stage, before PDF/MIDI or commit')


def recover_plan_extension(root):
    ledger_path = root / BASE / 'plan-extension.json'
    if not ledger_path.exists():
        return
    ledger = load(ledger_path)
    if ledger.get('status') == 'complete':
        return
    extension_stage_guard(root)
    if ledger.get('schema_version') != 1 or ledger.get('status') != 'prepared' or not ledger.get('events'):
        raise ValueError('invalid prepared plan-extension ledger')
    event = ledger['events'][-1]
    if (event['configuration_sha256'] != sha((root / CONFIG).read_bytes())
            or event['candidate_snapshot_sha256'] != sha((root / BASE / 'candidate-metadata.json').read_bytes())):
        raise ValueError('plan extension source/configuration changed before recovery')
    prior_plan_raw = gzip.decompress(base64.b64decode(event['prior_plan_gzip_base64'], validate=True))
    prior_journal_raw = gzip.decompress(base64.b64decode(event['prior_mxl_journal_gzip_base64'], validate=True))
    if sha(prior_plan_raw) != event['prior_plan_sha256'] or sha(prior_journal_raw) != event['prior_mxl_journal_sha256']:
        raise ValueError('plan-extension historical byte guards disagree')
    prior = json.loads(prior_journal_raw)
    outputs = [('plan.json', 'plan-extension-prepared.json', 'prior_plan_sha256', 'output_plan_sha256'),
               ('mxl-extraction.json', 'mxl-extension-prepared.json', 'prior_mxl_journal_sha256', 'output_mxl_journal_sha256')]
    bodies = {}
    observed = {}
    for name, prepared, old_key, new_key in outputs:
        path = root / BASE / name
        current = sha(path.read_bytes()) if path.exists() else sha(b'')
        allowed = {event[old_key], event[new_key]}
        if name == 'mxl-extraction.json' and event.get('absent_prior_journal_sha256'):
            allowed.add(event['absent_prior_journal_sha256'])
        if current not in allowed:
            raise ValueError('unexpected source state during plan-extension recovery: ' + name)
        observed[name] = current
        target = path if current == event[new_key] else root / BASE / prepared
        if not target.is_file() or sha(target.read_bytes()) != event[new_key]:
            raise ValueError('prepared plan-extension output is missing or changed: ' + name)
        bodies[name] = load(target)
    plan, journal = bodies['plan.json'], bodies['mxl-extraction.json']
    members = {work['id']: locator(work['metadata']['pdmx_csv_transcription'], 'MUSICXML') for work in plan['works']}
    if (journal['plan_sha256'] != event['output_plan_sha256'] or journal['scope_ids'] != sorted(members)
            or any(journal['records'].get(identity) != record for identity, record in prior['records'].items())):
        raise ValueError('plan-extension prior records or complete target scope changed')
    _, archive = guard_archive(root, 'mxl')
    guard_archive(root, 'PDMX.csv')
    fresh_verified_records(root, prior['records'], 'MUSICXML', members, archive['sha256'])
    if any((sha((root / BASE / name).read_bytes()) if (root / BASE / name).exists() else sha(b'')) != digest
           for name, digest in observed.items()):
        raise ValueError('plan/journal changed during fresh extension-object verification')
    for name, prepared, old_key, new_key in outputs:
        path = root / BASE / name
        if not path.exists() or sha(path.read_bytes()) != event[new_key]:
            os.replace(root / BASE / prepared, path)
    event['freshly_reverified_prior_records'] = sum(row.get('status') == 'verified' for row in prior['records'].values())
    event['status'] = 'complete'
    ledger['status'] = 'complete'
    _atomic_json(ledger_path, ledger)


def extend_prepared_plan(root, result):
    """Explicit monotone MXL-only migration; preserve exact prior bytes/records."""
    extension_stage_guard(root)
    plan_path, journal_path = root / BASE / 'plan.json', root / BASE / 'mxl-extraction.json'
    prior_raw = plan_path.read_bytes()
    prior = json.loads(prior_raw)
    for key in ['configuration_sha256', 'candidate_snapshot_sha256', 'original_catalog_sha256']:
        if prior.get(key) != result.get(key):
            raise ValueError('plan extension must retain the exact frozen configuration/CSV/candidate scope')
    old_works = {work['id']: work for work in prior['works']}
    new_works = {work['id']: work for work in result['works']}
    if (len(old_works) != len(prior['works']) or len(new_works) != len(result['works'])
            or not set(old_works) < set(new_works)
            or not set(prior['selected_native_ids']) <= set(result['selected_native_ids'])
            or any(canonical(new_works[identity]) != canonical(work) for identity, work in old_works.items())
            or any(result['decisions'].get(identity) != decision for identity, decision in prior['decisions'].items())):
        raise ValueError('plan extension requires a strict ID superset and exact prior work/decision guards')
    journal_raw = journal_path.read_bytes() if journal_path.exists() else b'{}'
    journal = json.loads(journal_raw)
    if journal and (journal.get('format') != 'MUSICXML' or journal.get('plan_sha256') != sha(prior_raw)
            or journal.get('configuration_sha256') != prior['configuration_sha256']
            or journal.get('scope_ids') != sorted(old_works) or not isinstance(journal.get('records'), dict)
            or not set(journal['records']) <= set(old_works)):
        raise ValueError('prior MXL journal does not match the exact pre-extension plan')
    if not journal:
        journal = {'schema_version': 1, 'format': 'MUSICXML', 'records': {},
                   'configuration_sha256': prior['configuration_sha256']}
        journal_raw = json.dumps(journal).encode()
        absent_journal_sha = sha(b'')
    else:
        absent_journal_sha = None
    prepared_plan = root / BASE / 'plan-extension-prepared.json'
    prepared_journal = root / BASE / 'mxl-extension-prepared.json'
    _atomic_json(prepared_plan, result)
    updated = copy.deepcopy(journal)
    updated.update(status='pending', plan_sha256=sha(prepared_plan.read_bytes()), scope_ids=sorted(new_works))
    for identity, work in new_works.items():
        updated['records'].setdefault(identity, {'status': 'pending', 'archive_member': locator(work['metadata']['pdmx_csv_transcription'], 'MUSICXML')})
    updated['counts'] = dict(Counter(row['status'] for row in updated['records'].values()))
    _atomic_json(prepared_journal, updated)
    ledger_path = root / BASE / 'plan-extension.json'
    ledger = load(ledger_path) if ledger_path.exists() else {'schema_version': 1, 'events': []}
    if ledger.get('status', 'complete') != 'complete':
        raise ValueError('recover the preceding prepared extension first')
    ledger['status'] = 'prepared'
    ledger['events'].append({'status': 'prepared', 'configuration_sha256': prior['configuration_sha256'],
        'candidate_snapshot_sha256': prior['candidate_snapshot_sha256'],
        'prior_plan_sha256': sha(prior_raw), 'prior_mxl_journal_sha256': sha(journal_raw),
        **({'absent_prior_journal_sha256': absent_journal_sha} if absent_journal_sha else {}),
        'output_plan_sha256': sha(prepared_plan.read_bytes()), 'output_mxl_journal_sha256': sha(prepared_journal.read_bytes()),
        'prior_plan_gzip_base64': base64.b64encode(gzip.compress(prior_raw, mtime=0)).decode(),
        'prior_mxl_journal_gzip_base64': base64.b64encode(gzip.compress(journal_raw, mtime=0)).decode(),
        'added_ids': sorted(set(new_works) - set(old_works)),
        'prior_work_sha256': {identity: canonical(work) for identity, work in old_works.items()},
        'prior_record_sha256': {identity: canonical(record) for identity, record in journal['records'].items()}})
    _atomic_json(ledger_path, ledger)
    recover_plan_extension(root)


def extract(root, label, *, identities=None):
    """Safely stream the entire cached archive, adding only new exact members."""
    extension_path = root / BASE / 'plan-extension.json'
    if extension_path.exists() and load(extension_path).get('status') != 'complete':
        raise ValueError('prepared extension requires explicit prepare --extend-plan recovery')
    plan_raw = (root / BASE / 'plan.json').read_bytes()
    plan = json.loads(plan_raw)
    if plan['configuration_sha256'] != sha((root / CONFIG).read_bytes()):
        raise ValueError('expansion configuration changed')
    old_records_unchanged(root)
    code, extension = FORMATS[label]
    archive_path, integrity = guard_archive(root, code)
    receipt = load(root / 'sources/musescore/pdmx' / (code + '-receipt.json'))
    if (receipt['sha256'] != integrity['sha256'] or receipt['bytes'] != integrity['bytes']
            or receipt['upstream_checksum'] != 'md5:' + integrity['md5']
            or receipt.get('upstream_checksum_verified') is not True):
        raise ValueError('cached publication receipt disagrees with fresh digest')
    work_list = [work for work in plan['works'] if identities is None or work['id'] in identities]
    wanted = defaultdict(list)
    for work in work_list:
        wanted[locator(work['metadata']['pdmx_csv_transcription'], label)].append(work['id'])
    path = root / BASE / (code + '-extraction.json')
    journal = load(path) if path.exists() else {'schema_version': 1, 'format': label,
        'plan_sha256': sha(plan_raw), 'scope_ids': sorted(work['id'] for work in work_list),
        'configuration_sha256': plan['configuration_sha256'], 'records': {}}
    if (journal.get('plan_sha256') != sha(plan_raw)
            or journal.get('scope_ids') != sorted(work['id'] for work in work_list)
            or journal.get('format') != label
            or journal.get('configuration_sha256') != plan['configuration_sha256']
            or not isinstance(journal.get('records'), dict)
            or not set(journal['records']) <= set(journal['scope_ids'])):
        raise ValueError('append extraction scope/plan drift')
    journal.update(status='running', live_source_requests=0, archive_integrity=integrity)
    expected_members = {work['id']: locator(work['metadata']['pdmx_csv_transcription'], label) for work in work_list}
    selected = fresh_verified_records(root, journal['records'], label, expected_members, integrity['sha256'])
    _atomic_json(path, journal)
    seen, counts = set(), Counter()
    partials = root / BASE / 'partials'
    partials.mkdir(parents=True, exist_ok=True)
    try:
        with archive_path.open('rb') as compressed, gzip.GzipFile(fileobj=compressed) as uncompressed:
            bounded = pdf_methods._BoundedReader(uncompressed, 32*1024**3)
            with tarfile.open(fileobj=bounded, mode='r|') as archive:
                for member in _stream_members(archive):
                    counts['archive_members'] += 1
                    if counts['archive_members'] > 300000:
                        raise ValueError('archive member count exceeded')
                    name = pdf_methods._member_name(member)
                    if name in seen:
                        raise ValueError('duplicate archive path')
                    seen.add(name)
                    if member.isdir():
                        if member.size:
                            raise ValueError('nonempty archive directory')
                        continue
                    if not 0 <= member.size <= 512*1024**2:
                        raise ValueError('archive member size exceeded')
                    counts['regular_bytes'] += member.size
                    if name not in wanted:
                        continue
                    counts['selected_members'] += 1
                    counts['selected_bytes'] += member.size
                    if counts['selected_bytes'] > 4*1024**3:
                        raise ValueError('selected expansion size exceeded')
                    temporary = partials / (sha(name.encode()) + '.' + extension + '.part')
                    try:
                        handle = archive.extractfile(member)
                        if handle is None:
                            raise ValueError('selected member unreadable')
                        if name in selected:
                            with handle:
                                digest = hashlib.file_digest(handle, 'sha256').hexdigest()
                            asset = selected[name]['asset']
                            if asset['sha256'] != digest or asset['size'] != member.size:
                                raise ValueError('resumed object differs from exact archive member')
                            result = selected[name]
                        else:
                            digest, size = hashlib.sha256(), 0
                            with handle, temporary.open('wb') as output:
                                while block := handle.read(1024*1024):
                                    size += len(block)
                                    if size > member.size:
                                        raise ValueError('member exceeds declared size')
                                    output.write(block)
                                    digest.update(block)
                                output.flush()
                                os.fsync(output.fileno())
                            if size != member.size:
                                raise ValueError('truncated member')
                            digest = digest.hexdigest()
                            if label == 'PDF':
                                pdf_methods.validate_readable_pdf(temporary)
                                local = pdf_methods._store_pdf(root, temporary, digest, size)
                                asset = pdf_methods._verified_asset(size, digest, local, name, receipt)
                            else:
                                validation = format_methods.validate_source_format(temporary, label)
                                local = format_methods._store(root, temporary, digest, size, label)
                                asset = format_methods._verified_asset(size, digest, local, name, receipt, label, validation)
                            result = {'status': 'verified', 'asset': asset}
                        selected[name] = result
                    except (OSError, ValueError, RuntimeError) as error:
                        result = {'status': 'failed', 'archive_member': name, 'reason': str(error)}
                    finally:
                        temporary.unlink(missing_ok=True)
                    for identity in wanted[name]:
                        journal['records'][identity] = result
                    if counts['selected_members'] % 50 == 0:
                        journal['archive_counts'] = dict(counts)
                        _atomic_json(path, journal)
                        print(json.dumps({'format': label, 'processed': counts['selected_members']}), flush=True)
                if archive.fileobj.tell() - archive.offset < tarfile.BLOCKSIZE:
                    raise ValueError('first TAR end marker missing')
                trailing = archive.fileobj.buf
                tail_size = len(trailing)
                if any(trailing):
                    raise ValueError('nonzero TAR trailing data')
            while block := bounded.read(1024*1024):
                tail_size += len(block)
                if any(block):
                    raise ValueError('nonzero data after TAR end')
            if tail_size < tarfile.BLOCKSIZE:
                raise ValueError('second TAR end marker missing')
            counts['decompressed_bytes'] = bounded.bytes
        guard_archive(root, code)
        for name, native_ids in wanted.items():
            if name not in seen:
                for identity in native_ids:
                    journal['records'][identity] = {'status': 'missing', 'archive_member': name,
                        'reason': 'exact CSV locator absent from verified publication'}
        journal.update(status='complete', archive_counts=dict(counts),
            counts=dict(Counter(row['status'] for row in journal['records'].values())),
            completed_at=pdf_methods.now())
    except BaseException as error:
        journal.update(status='interrupted', error=str(error), archive_counts=dict(counts))
        raise
    finally:
        _atomic_json(path, journal)
    return journal['counts']


def append_catalog(old, additions, config, integration):
    """Pure append: original work/asset dictionaries are never reconstructed."""
    result = copy.deepcopy(old)
    existing = {work['id'] for work in old['works']}
    new_ids = [work['id'] for work in additions]
    if not additions or len(set(new_ids)) != len(new_ids) or existing & set(new_ids):
        raise ValueError('append requires nonempty unique new native identities')
    result['works'].extend(copy.deepcopy(additions))
    result['works'].sort(key=lambda work: int(work['id'].split(':', 1)[1]))
    result['snapshot']['scope'] = config['scope']
    result['snapshot']['record_count'] = len(result['works'])
    result['snapshot']['expansion'] = {
        'scope_version': config['scope_version'], 'configuration_sha256': canonical(config),
        'original_record_count': len(old['works']), 'added_record_count': len(additions),
        'current_record_count': len(result['works']),
        'full_metadata_records_checked': integration['scope']['metadata_records'],
        'full_mxl_records_checked': integration['scope']['mxl_records'],
        'live_source_coverage_complete': False,
        **{key: integration['scope'][key] for key in ['mxl_inspected_records', 'mxl_validated_records',
                'mxl_parse_failures', 'mxl_missing_csv_members', 'csv_native_records', 'undeclared_mxl_records'] if key in integration['scope']},
    }
    summary = result.setdefault('summary', {})
    summary['records'] = len(result['works'])
    summary['source_records'] = len(result['works'])
    summary['scope'] = config['scope']
    for label, field in [('PDF', 'verified_local_pdfs'), ('MUSICXML', 'verified_local_mxl'), ('MIDI', 'verified_local_midi')]:
        summary[field] = sum(any(a['format'] == label and a['status'] == 'verified'
                                  for a in w['assets']) for w in result['works'])
    return result


def commit(root):
    """Publish a prepared append and a per-record guarded overlay transaction."""
    from catalog_instrumentation import per_record_guard, _check_review, _check_asset
    from verify_musescore_expansion import check_final_input_guards
    old, current = old_records_unchanged(root)
    catalog_path = pdf_methods._safe_local(root, root / 'sources/musescore/catalog.json')
    overlay_path = pdf_methods._safe_local(root, root / 'sources/musescore/instrumentation-review.json')
    pdf_methods._safe_local(root, root / BASE)
    pdf_methods._safe_local(root, root / CONFIG)
    config = load(root / CONFIG)
    plan_raw = (root / BASE / 'plan.json').read_bytes()
    plan = json.loads(plan_raw)
    scope = load(root / BASE / 'scope-review.json')
    final_path = root / BASE / 'final-review.json'
    final = load(final_path)
    check_final_input_guards(root, final, scope)
    if (plan.get('configuration_sha256') != sha((root / CONFIG).read_bytes())
            or plan.get('candidate_snapshot_sha256') != sha((root / BASE / 'candidate-metadata.json').read_bytes())):
        raise ValueError('prepared expansion configuration/candidate snapshot drift')
    archives = {name: guard_archive(root, name if name.endswith('.csv') else name.removesuffix('.tar.gz'))[1]
                for name in config['files']}
    if scope.get('status') != 'complete' or not isinstance(scope.get('accepted_ids'), list):
        raise ValueError('complete actual-MXL acceptance scope required')
    if final.get('status') != 'complete' or not isinstance(final.get('works'), list):
        raise ValueError('complete cross-format review required before append')
    projections = {work['id']: work for work in final['works']}
    planned_ids = {work['id'] for work in plan['works']}
    if (not projections or len(planned_ids) != len(plan['works']) or len(projections) != len(final['works'])
            or not set(projections) <= set(scope['accepted_ids']) & planned_ids):
        raise ValueError('cross-format review exceeds accepted actual-MXL scope')
    extractions = {label: load(root / BASE / (code + '-extraction.json'))
                   for label, (code, _) in FORMATS.items()}
    if any(proof.get('status') != 'complete' or proof.get('plan_sha256') != sha(plan_raw)
           or proof.get('format') != label or proof.get('configuration_sha256') != plan['configuration_sha256']
           or not set(projections) <= set(proof.get('scope_ids', []))
           or proof.get('archive_integrity') != archives[FORMATS[label][0] + '.tar.gz']
           for label, proof in extractions.items()):
        raise ValueError('complete exact-plan extraction journals required')
    watched = [catalog_path, overlay_path, root / CONFIG, root / BASE / 'plan.json',
               root / BASE / 'scope-review.json', final_path, root / BASE / 'candidate-metadata.json',
               root / BASE / 'archive-integrity.json', root / BASE / 'full-metadata-audit.json', root / BASE / 'mxl-scope.json',
               *(root / BASE / (code + '-extraction.json') for code, _ in FORMATS.values())]
    input_stats = {path: pdf_methods._stat_fingerprint(path) for path in watched}
    additions = []
    for planned in plan['works']:
        identity = planned['id']
        if identity not in projections:
            continue
        work = copy.deepcopy(planned)
        assets = []
        for label, proof in extractions.items():
            row = proof['records'].get(identity, {})
            if row.get('status') != 'verified':
                raise ValueError('reviewed append lacks verified format: ' + identity + '/' + label)
            asset = row['asset']
            if (asset['archive_member'] != locator(work['metadata']['pdmx_csv_transcription'], label)
                    or asset['archive_sha256'] != config['files'][FORMATS[label][0] + '.tar.gz']['sha256']):
                raise ValueError('new file provenance differs from exact frozen native locator')
            validate_asset(root, asset)
            assets.append(asset)
        work['assets'] = sorted(assets, key=lambda asset: asset['format'])
        work['metadata']['scope_status'] = 'accepted_actual_file_review'
        work['metadata']['availability'] = 'PDMX 历史出版记录；来源页面现状未核。'
        if work['metadata'].get('historical_file_access_restrictions'):
            work['metadata']['availability'] += '源站历史文件访问受限。'
        work['metadata']['license_note'] = '按 PDMX 逐条历史许可和无冲突标记整理；具体条件参见出版页与原站标注。'
        work['metadata']['acquisition_status'] = 'verified_publication_exports'
        projection = projections[identity]
        if any(projection.get(key) != work.get(key) for key in ['title_en', 'composer_en', 'source_url']):
            raise ValueError('final review native identity mismatch')
        if not isinstance(projection.get('assets'), dict) or set(projection['assets']) != set(FORMATS):
            raise ValueError('final review requires exactly three format guards')
        _check_review(work, projection['review'])
        for label in FORMATS:
            _check_asset(root, work, label, projection['assets'][label])
        additions.append(work)
    metadata_audit = load(root / BASE / 'full-metadata-audit.json')
    mxl_audit = load(root / BASE / 'mxl-scope.json')
    mxl_counts = require_complete_mxl_scan(mxl_audit)
    if (metadata_audit.get('status') != 'complete'
            or mxl_audit.get('fresh_archive_integrity') != archives['mxl.tar.gz']
            or mxl_audit.get('csv_input_stat') != archives['PDMX.csv']['stat']):
        raise ValueError('complete full-database and notation recall required')
    integration = {'schema_version': 1, 'source_id': 'musescore', 'status': 'complete',
        'scope_version': config['scope_version'], 'live_source_requests': 0,
        'input_catalog_sha256': baseline(root)['documents']['sources/musescore/catalog.json']['sha256'],
        'configuration_sha256': sha((root / CONFIG).read_bytes()),
        'plan_sha256': sha(plan_raw), 'final_review_sha256': sha(final_path.read_bytes()),
        'scope': {'metadata_records': metadata_audit['counts']['unique_metadata_records'],
                  'csv_native_records': mxl_counts['csv_native_records'],
                  'undeclared_mxl_records': mxl_counts['csv_native_records'] - mxl_counts['csv_mxl_locators'],
                  'mxl_records': mxl_counts['unique_mxl_members'],
                  'mxl_inspected_records': mxl_counts['inspected_mxl_members'],
                  'mxl_validated_records': mxl_counts['validated_mxl_members'],
                  'mxl_parse_failures': mxl_counts.get('parse_failures', 0),
                  'mxl_missing_csv_members': mxl_counts['csv_mxl_members_missing_archive']},
        'mxl_scan_sha256': sha((root / BASE / 'mxl-scope.json').read_bytes()),
        'mxl_parse_failure_details': mxl_audit['parse_failures'], 'mxl_missing_members': mxl_audit['missing_mxl_members'],
        'original_records': len(old['works']), 'added_records': len(additions),
        'current_records': len(old['works']) + len(additions),
        'added_native_ids': sorted(projections),
        'new_topics': dict(Counter(row['review']['topic_id'] for row in projections.values())),
        'new_review_statuses': dict(Counter(row['review']['status'] for row in projections.values())),
        'new_formats': {label: {
            'verified_relations': len(additions),
            'unique_objects': len({next(a['sha256'] for a in w['assets'] if a['format'] == label) for w in additions}),
            'unique_bytes': sum({a['sha256']: a['size'] for w in additions for a in w['assets'] if a['format'] == label}.values()),
            'extraction_counts': proof['counts'],
        } for label, proof in extractions.items()},
        'boundaries': ['Frozen PDMX v9, not the live MuseScore database.',
            'Only acoustic-guitar instrumental solo/small ensemble scope is appended.',
            'GM, tracks, staves and title keywords are recall, not performing-player counts.',
            'Source historical licenses are distinct from publication licensing and live access.',
            'Format integrity and written roles do not certify note-by-note or acoustic fidelity.']}
    updated = append_catalog(old, additions, config, integration)
    original_overlay = baseline(root)['documents']['sources/musescore/instrumentation-review.json']['value']
    overlay_works = original_overlay['works'] + [projections[work['id']] for work in additions]
    overlay = {'schema_version': 2, 'source_id': 'musescore', 'status': 'complete',
        'native_record_sha256': {work['id']: per_record_guard(work) for work in updated['works']},
        'works': overlay_works}
    if current != old and current != updated:
        raise ValueError('unexpected previous append; refusing to replace current source snapshot')
    current_overlay = load(overlay_path)
    if current_overlay not in (original_overlay, overlay):
        raise ValueError('prior semantic overlay changed outside this prepared append')
    transaction_path = root / BASE / 'commit.json'
    prepared_catalog = root / BASE / 'catalog-prepared.json'
    prepared_overlay = root / BASE / 'review-prepared.json'
    check_final_input_guards(root, final, scope)
    _atomic_json(prepared_catalog, updated)
    _atomic_json(prepared_overlay, overlay)
    transaction = {'schema_version': 1, 'status': 'prepared',
        'input_catalog_sha256': integration['input_catalog_sha256'],
        'configuration_sha256': plan['configuration_sha256'], 'plan_sha256': sha(plan_raw),
        'final_review_sha256': integration['final_review_sha256'],
        'output_catalog_sha256': sha(prepared_catalog.read_bytes()),
        'output_overlay_sha256': sha(prepared_overlay.read_bytes())}
    if transaction_path.exists():
        preceding = load(transaction_path)
        if (preceding.get('status') not in {'prepared', 'complete'}
                or {key: value for key, value in preceding.items() if key != 'status'} !=
                   {key: value for key, value in transaction.items() if key != 'status'}):
            raise ValueError('prior append transaction drift')
    if any(pdf_methods._stat_fingerprint(path) != stamp for path, stamp in input_stats.items()):
        raise ValueError('append inputs changed during final file validation; source catalog preserved')
    _atomic_json(transaction_path, transaction)
    os.replace(prepared_catalog, catalog_path)
    os.replace(prepared_overlay, overlay_path)
    integration.update(output_catalog_sha256=sha(catalog_path.read_bytes()),
                       output_overlay_sha256=sha(overlay_path.read_bytes()))
    _atomic_json(root / BASE / 'integration.json', integration)
    transaction['status'] = 'complete'
    _atomic_json(transaction_path, transaction)
    return {key: integration[key] for key in ['original_records', 'added_records', 'current_records', 'new_topics']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['verify-archives', 'recall', 'prepare', 'extract', 'commit'])
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--selection', type=Path)
    parser.add_argument('--format', choices=FORMATS)
    parser.add_argument('--accepted-only', action='store_true')
    parser.add_argument('--extend-plan', action='store_true')
    args = parser.parse_args()
    if args.extend_plan and args.phase != 'prepare':
        parser.error('--extend-plan is only valid with prepare')
    root = args.root.resolve()
    with pdf_methods.source_lock(root / 'sources/musescore/.expansion.lock'), format_methods._source_locks(root):
        if args.phase == 'verify-archives':
            result = verify_archives(root)
        elif args.phase == 'recall':
            result = recall_selection(root)
        elif args.phase == 'prepare':
            if args.selection is None:
                parser.error('--selection JSON list required')
            result = prepare(root, load(args.selection), extend_plan=args.extend_plan)
        elif args.phase == 'extract':
            if args.format is None:
                parser.error('--format required')
            identities = None
            if args.accepted_only:
                identities = set(load(root / BASE / 'scope-review.json')['accepted_ids'])
            result = extract(root, args.format, identities=identities)
        else:
            result = commit(root)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
