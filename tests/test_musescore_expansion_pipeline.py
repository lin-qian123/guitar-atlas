"""Append operations must preserve old records and reject unsafe archives."""
import gzip
import copy
import csv
import hashlib
import io
import json
import struct
import tarfile
from pathlib import Path

import pytest

import expand_musescore_library as expansion


def document(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def setup(tmp_path, *, malicious=None, shared=False, missing=False):
    old = {'categories': [{'id': 'guitar'}], 'works': [{'id': 'musescore:1', 'assets': []}]}
    document(tmp_path / 'sources/musescore/catalog.json', old)
    base = tmp_path / expansion.BASE
    base.mkdir(parents=True)
    with gzip.open(base / 'baseline.json.gz', 'wt') as stream:
        json.dump({'documents': {'sources/musescore/catalog.json': {'value': old}}}, stream)
    archive = tmp_path / 'sources/musescore/pdmx/mid.tar.gz'
    archive.parent.mkdir(parents=True)
    track = b'\x00\xc0\x18\x00\x90\x3c\x40\x01\x80\x3c\x00\x00\xff\x2f\x00'
    body = b'MThd' + struct.pack('>IHHH', 6, 0, 1, 480) + b'MTrk' + struct.pack('>I', len(track)) + track
    member = 'mid/1/2/native2.mid'
    with tarfile.open(archive, 'w:gz') as tar:
        if not missing:
            info = tarfile.TarInfo(member)
            info.size = len(body)
            tar.addfile(info, io.BytesIO(body))
        if malicious:
            info = tarfile.TarInfo(malicious)
            info.size = 1
            tar.addfile(info, io.BytesIO(b'x'))
    raw = archive.read_bytes()
    guards = {'bytes': len(raw), 'md5': hashlib.md5(raw).hexdigest(),
              'sha256': hashlib.sha256(raw).hexdigest(),
              'stat': list(expansion.pdf_methods._stat_fingerprint(archive))}
    config = {'files': {'mid.tar.gz': {'size': guards['bytes'], 'md5': guards['md5'], 'sha256': guards['sha256']}}}
    document(tmp_path / expansion.CONFIG, config)
    document(base / 'archive-integrity.json', {'status': 'complete', 'files': {'mid.tar.gz': guards}})
    document(archive.parent / 'mid-receipt.json', {'bytes': len(raw), 'sha256': guards['sha256'],
        'upstream_checksum': 'md5:' + guards['md5'], 'upstream_checksum_verified': True})
    works = [{'id': 'musescore:2', 'metadata': {'pdmx_csv_transcription': {'mid': './' + member}}}]
    if shared:
        works.append({'id': 'musescore:3', 'metadata': {'pdmx_csv_transcription': {'mid': './' + member}}})
    plan = {'configuration_sha256': expansion.sha((tmp_path / expansion.CONFIG).read_bytes()), 'works': works}
    document(base / 'plan.json', plan)
    return old, archive


def test_append_extraction_shares_physical_midi_without_merging_native_records(tmp_path):
    old, _ = setup(tmp_path, shared=True)
    assert expansion.extract(tmp_path, 'MIDI') == {'verified': 2}
    proof = expansion.load(tmp_path / expansion.BASE / 'mid-extraction.json')
    assert set(proof['records']) == {'musescore:2', 'musescore:3'}
    assert proof['records']['musescore:2']['asset'] == proof['records']['musescore:3']['asset']
    assert expansion.load(tmp_path / 'sources/musescore/catalog.json') == old
    assert expansion.extract(tmp_path, 'MIDI') == {'verified': 2}


@pytest.mark.parametrize('name', ['../outside', '/absolute', 'mid/../outside', 'C:/outside', 'mid\\escape'])
def test_append_rejects_unsafe_unselected_members_and_keeps_catalog(tmp_path, name):
    old, _ = setup(tmp_path, malicious=name)
    with pytest.raises(ValueError, match='unsafe'):
        expansion.extract(tmp_path, 'MIDI')
    assert expansion.load(tmp_path / 'sources/musescore/catalog.json') == old
    assert expansion.load(tmp_path / expansion.BASE / 'mid-extraction.json')['status'] == 'interrupted'


def test_exact_missing_locator_is_retained_without_a_local_asset(tmp_path):
    setup(tmp_path, missing=True)
    assert expansion.extract(tmp_path, 'MIDI') == {'missing': 1}
    row = expansion.load(tmp_path / expansion.BASE / 'mid-extraction.json')['records']['musescore:2']
    assert 'asset' not in row and row['archive_member'] == 'mid/1/2/native2.mid'


def test_fresh_whole_archive_stat_must_still_agree(tmp_path):
    _, archive = setup(tmp_path)
    archive.write_bytes(archive.read_bytes() + b'altered')
    with pytest.raises(ValueError, match='stat guard'):
        expansion.guard_archive(tmp_path, 'mid')


def test_archive_proof_is_reproducible_and_failed_hash_never_marks_complete(tmp_path):
    _, archive = setup(tmp_path)
    result = expansion.verify_archives(tmp_path)
    assert result['status'] == 'complete'
    assert expansion.guard_archive(tmp_path, 'mid')[0] == archive
    archive.write_bytes(archive.read_bytes() + b'tamper')
    with pytest.raises(ValueError, match='checksum mismatch'):
        expansion.verify_archives(tmp_path)
    proof = expansion.load(tmp_path / expansion.BASE / 'archive-integrity.json')
    assert proof['status'] == 'failed'


def test_prior_asset_or_metadata_may_not_be_rewritten(tmp_path):
    old, _ = setup(tmp_path)
    old['works'][0]['verified_at'] = 'new timestamp'
    document(tmp_path / 'sources/musescore/catalog.json', old)
    with pytest.raises(ValueError, match='prior native record changed'):
        expansion.old_records_unchanged(tmp_path)


def test_resume_rejects_changed_native_scope(tmp_path):
    setup(tmp_path)
    expansion.extract(tmp_path, 'MIDI')
    plan_path = tmp_path / expansion.BASE / 'plan.json'
    plan = expansion.load(plan_path)
    plan['works'].append({'id': 'musescore:3', 'metadata': {'pdmx_csv_transcription': {'mid': './mid/1/2/native2.mid'}}})
    document(plan_path, plan)
    with pytest.raises(ValueError, match='scope/plan drift'):
        expansion.extract(tmp_path, 'MIDI')


def test_catalog_append_preserves_complete_old_asset_values_and_frozen_evidence():
    old_work = {'id': 'musescore:1', 'metadata': {'native': 'unchanged'}, 'assets': [
        {'format': 'PDF', 'status': 'verified', 'verified_at': 'old', 'private_guard': 'retained'}]}
    original = {'snapshot': {'publication': {'record_id': '15571083'}, 'accepted_record_count': 1},
                'categories': [{'id': 'guitar'}], 'works': [old_work], 'summary': {}}
    addition = {'id': 'musescore:2', 'assets': [{'format': fmt, 'status': 'verified'} for fmt in expansion.FORMATS]}
    result = expansion.append_catalog(original, [addition], {'scope': 'expanded', 'scope_version': 'test'},
                                      {'scope': {'metadata_records': 254077, 'mxl_records': 254077}})
    assert result['works'][0] == old_work
    assert original['snapshot'] == {'publication': {'record_id': '15571083'}, 'accepted_record_count': 1}
    assert result['snapshot']['publication'] == original['snapshot']['publication']
    assert result['snapshot']['accepted_record_count'] == 1  # initial selection, not the current total
    assert result['snapshot']['record_count'] == 2
    assert result['summary']['verified_local_pdfs'] == 2
    assert result['summary']['verified_local_midi'] == 1
    assert result['summary']['source_records'] == 2 and result['summary']['scope'] == 'expanded'


@pytest.mark.parametrize('ids', [[], ['musescore:1'], ['musescore:2', 'musescore:2']])
def test_catalog_append_rejects_empty_duplicate_or_preexisting_ids(ids):
    with pytest.raises(ValueError, match='unique new native'):
        expansion.append_catalog({'works': [{'id': 'musescore:1'}]}, [{'id': value} for value in ids], {}, {})


@pytest.mark.parametrize('mutation', [
    lambda journal: journal.update(format='PDF'),
    lambda journal: journal.update(configuration_sha256='a' * 64),
    lambda journal: journal['records'].update({'musescore:999': {'status': 'missing'}}),
    lambda journal: journal['records']['musescore:2']['asset'].update(archive_member='mid/1/2/other.mid'),
])
def test_resume_rejects_foreign_format_unknown_ids_and_member_drift(tmp_path, mutation):
    setup(tmp_path)
    expansion.extract(tmp_path, 'MIDI')
    path = tmp_path / expansion.BASE / 'mid-extraction.json'
    journal = expansion.load(path); mutation(journal); document(path, journal)
    with pytest.raises(ValueError, match='drift'):
        expansion.extract(tmp_path, 'MIDI')


def commit_fixture(tmp_path, monkeypatch):
    from tests.test_catalog_instrumentation import reviewed_library
    old, overlay = reviewed_library(tmp_path)
    base = tmp_path / expansion.BASE; base.mkdir(parents=True, exist_ok=True)
    config = {'scope': 'full frozen publication reviewed additions', 'scope_version': 'test.2', 'files': {}}
    integrity = {'status': 'complete', 'files': {}}
    for name in ['PDMX.csv', 'metadata.tar.gz', 'pdf.tar.gz', 'mxl.tar.gz', 'mid.tar.gz']:
        path = tmp_path / 'sources/musescore/pdmx' / name
        path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(('frozen test publication ' + name).encode())
        body = path.read_bytes(); md5 = hashlib.md5(body).hexdigest(); sha = hashlib.sha256(body).hexdigest()
        config['files'][name] = {'size': len(body), 'md5': md5, 'sha256': sha}
        integrity['files'][name] = {'bytes': len(body), 'md5': md5, 'sha256': sha,
            'stat': list(expansion.pdf_methods._stat_fingerprint(path))}
    document(tmp_path / expansion.CONFIG, config); document(base / 'archive-integrity.json', integrity)
    document(base / 'candidate-metadata.json', {'status': 'complete'})
    planned = copy.deepcopy(old['works'][0])
    planned.update(id='musescore:101', title_en='Additional Study', source_url='https://musescore.com/user/321/scores/101', assets=[])
    planned['metadata']['pdmx_csv_transcription'] = {code: './' + code + '/1/2/added.' + suffix
                                                    for code, suffix in expansion.FORMATS.values()}
    plan = {'configuration_sha256': expansion.sha((tmp_path / expansion.CONFIG).read_bytes()),
            'candidate_snapshot_sha256': expansion.sha((base / 'candidate-metadata.json').read_bytes()),
            'works': [planned]}
    document(base / 'plan.json', plan)
    projection = copy.deepcopy(overlay['works'][0])
    projection.update({key: planned[key] for key in ['id', 'title_en', 'composer_en', 'source_url']})
    document(base / 'scope-review.json', {'status': 'complete', 'accepted_ids': [planned['id']]})
    document(base / 'final-review.json', {'status': 'complete', 'works': [projection]})
    for label, (code, suffix) in expansion.FORMATS.items():
        asset = copy.deepcopy(next(row for row in old['works'][0]['assets'] if row['format'] == label))
        asset.update(archive_member=code + '/1/2/added.' + suffix,
                     archive_sha256=config['files'][code + '.tar.gz']['sha256'])
        document(base / (code + '-extraction.json'), {'status': 'complete', 'format': label,
            'configuration_sha256': plan['configuration_sha256'], 'plan_sha256': expansion.sha((base / 'plan.json').read_bytes()),
            'scope_ids': [planned['id']], 'archive_integrity': integrity['files'][code + '.tar.gz'],
            'counts': {'verified': 1}, 'records': {planned['id']: {'status': 'verified', 'asset': asset}}})
    document(base / 'full-metadata-audit.json', {'status': 'complete', 'counts': {'unique_metadata_records': 254077}})
    document(base / 'mxl-scope.json', {'status': 'complete', 'coverage_complete': True,
        'archive_checksum_freshly_reverified': True, 'fresh_archive_integrity': integrity['files']['mxl.tar.gz'],
        'archive_input': integrity['files']['mxl.tar.gz'],
        'csv_input_stat': integrity['files']['PDMX.csv']['stat'], 'parse_failures': [], 'missing_mxl_members': [],
        'counts': {'unique_mxl_members': 254077, 'inspected_mxl_members': 254077,
                   'validated_mxl_members': 254077, 'csv_mxl_members_missing_archive': 0,
                   'csv_native_records': 254077, 'csv_mxl_locators': 254077}})
    with gzip.open(base / 'baseline.json.gz', 'wt') as stream:
        json.dump({'documents': {'sources/musescore/catalog.json': {'value': old,
            'sha256': expansion.sha((tmp_path / 'sources/musescore/catalog.json').read_bytes())},
            'sources/musescore/instrumentation-review.json': {'value': overlay}}}, stream)
    from verify_musescore_expansion import FINAL_METHOD_PATHS, EXACT_CASE_PATH
    root = Path(expansion.__file__).resolve().parents[1]
    for relative in FINAL_METHOD_PATHS:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((root / relative).read_bytes())
    document(tmp_path / EXACT_CASE_PATH, {'schema_version': 1, 'entries': []})
    refresh_commit_review_guards(tmp_path)
    # Actual bytes, sizes, and overlay guards remain checked by _check_asset.
    # Archive/member structural validation is covered by extraction tests above.
    monkeypatch.setattr(expansion, 'validate_asset', lambda *args: None)
    return old, overlay, planned


def refresh_commit_review_guards(root):
    from verify_musescore_expansion import FINAL_INPUT_PATHS, FINAL_METHOD_PATHS, SCOPE_METHOD_PATHS, EXACT_CASE_PATH
    def guard(path):
        raw = path.read_bytes()
        return {'sha256': expansion.sha(raw), 'size': len(raw)}
    base = root / expansion.BASE
    case_guard = guard(root / EXACT_CASE_PATH)
    scope = expansion.load(base / 'scope-review.json')
    scope['inputs'] = {'plan': guard(base / 'plan.json'), 'mxl_extraction': guard(base / 'mxl-extraction.json'),
        'methods': {relative: guard(root / relative) for relative in SCOPE_METHOD_PATHS}, 'reviewed_cases': case_guard}
    document(base / 'scope-review.json', scope)
    final = expansion.load(base / 'final-review.json')
    final.update(inputs={name: guard(root / relative) for name, relative in FINAL_INPUT_PATHS.items()},
        methods={relative: guard(root / relative) for relative in FINAL_METHOD_PATHS}, reviewed_cases=case_guard)
    document(base / 'final-review.json', final)


@pytest.mark.parametrize('relative', [
    'metadata/instrumentation/musescore_expansion_reviewed.json',
    'scripts/review_musescore_expansion.py', 'scripts/review_musescore_expansion_final.py',
])
@pytest.mark.parametrize('during_asset_check', [False, True])
def test_commit_rejects_semantic_case_or_method_drift_before_any_prepared_write(tmp_path, monkeypatch, relative, during_asset_check):
    commit_fixture(tmp_path, monkeypatch)
    source = tmp_path / 'sources/musescore/catalog.json'
    overlay = tmp_path / 'sources/musescore/instrumentation-review.json'
    before = (source.read_bytes(), overlay.read_bytes())
    target = tmp_path / relative
    changed = False

    def mutate(*args):
        nonlocal changed
        if not changed:
            target.write_bytes(target.read_bytes() + b'\n')
            changed = True

    if during_asset_check:
        monkeypatch.setattr(expansion, 'validate_asset', mutate)
    else:
        mutate()
    with pytest.raises(ValueError, match='reviewed-case asset changed|review method bytes changed'):
        expansion.commit(tmp_path)
    assert changed
    assert (source.read_bytes(), overlay.read_bytes()) == before
    assert all(not (tmp_path / expansion.BASE / name).exists() for name in
        ['catalog-prepared.json', 'review-prepared.json', 'commit.json', 'integration.json'])


def test_commit_preserves_old_native_and_review_objects_and_is_repeatable(tmp_path, monkeypatch):
    old, overlay, planned = commit_fixture(tmp_path, monkeypatch)
    result = expansion.commit(tmp_path)
    assert result['added_records'] == 1
    assert next(row for row in expansion.load(tmp_path / 'sources/musescore/catalog.json')['works'] if row['id'] == old['works'][0]['id']) == old['works'][0]
    assert expansion.load(tmp_path / 'sources/musescore/instrumentation-review.json')['works'][0] == overlay['works'][0]
    assert expansion.commit(tmp_path) == result
    assert expansion.load(tmp_path / expansion.BASE / 'commit.json')['status'] == 'complete'


def test_commit_recovers_interruption_between_catalog_and_overlay_without_changing_old_values(tmp_path, monkeypatch):
    old, overlay, _ = commit_fixture(tmp_path, monkeypatch)
    real_replace = expansion.os.replace
    overlay_path = tmp_path / 'sources/musescore/instrumentation-review.json'
    def interrupted(source, target):
        if target == overlay_path:
            raise OSError('simulated interruption between committed files')
        return real_replace(source, target)
    monkeypatch.setattr(expansion.os, 'replace', interrupted)
    with pytest.raises(OSError, match='simulated interruption'):
        expansion.commit(tmp_path)
    assert expansion.load(tmp_path / expansion.BASE / 'commit.json')['status'] == 'prepared'
    assert expansion.load(overlay_path) == overlay
    monkeypatch.setattr(expansion.os, 'replace', real_replace)
    assert expansion.commit(tmp_path)['added_records'] == 1
    assert next(row for row in expansion.load(tmp_path / 'sources/musescore/catalog.json')['works'] if row['id'] == old['works'][0]['id']) == old['works'][0]


@pytest.mark.parametrize('mutation,reason', [
    ('config', 'final review input bytes changed'),
    ('candidate', 'configuration/candidate snapshot drift'),
    ('archive', 'stat guard disagreement'),
    ('unknown_projection', 'accepted actual-MXL scope'),
    ('journal', 'exact-plan extraction'),
    ('transaction', 'transaction drift'),
])
def test_commit_rejects_stale_or_out_of_scope_inputs_before_replacing_native_catalog(tmp_path, monkeypatch, mutation, reason):
    old, _, _ = commit_fixture(tmp_path, monkeypatch)
    base = tmp_path / expansion.BASE
    if mutation == 'config':
        value = expansion.load(tmp_path / expansion.CONFIG); value['scope'] = 'drift'; document(tmp_path / expansion.CONFIG, value)
    elif mutation == 'candidate':
        document(base / 'candidate-metadata.json', {'status': 'changed'})
    elif mutation == 'archive':
        path = tmp_path / 'sources/musescore/pdmx/pdf.tar.gz'; path.write_bytes(path.read_bytes() + b'x')
    elif mutation == 'unknown_projection':
        value = expansion.load(base / 'final-review.json'); value['works'][0]['id'] = 'musescore:999'
        document(base / 'final-review.json', value); document(base / 'scope-review.json', {'status': 'complete', 'accepted_ids': ['musescore:999']})
        refresh_commit_review_guards(tmp_path)
    elif mutation == 'journal':
        path = base / 'pdf-extraction.json'; value = expansion.load(path); value['format'] = 'MIDI'; document(path, value)
        refresh_commit_review_guards(tmp_path)
    else:
        document(base / 'commit.json', {'status': 'prepared', 'output_catalog_sha256': 'foreign'})
    with pytest.raises(ValueError, match=reason):
        expansion.commit(tmp_path)
    assert expansion.load(tmp_path / 'sources/musescore/catalog.json') == old


def completed_scan_with_parse_limit():
    integrity = {'bytes': 1000, 'md5': 'a' * 32, 'sha256': 'b' * 64, 'stat': [1, 2, 1000, 3, 4]}
    return {'status': 'complete_with_parse_or_missing_boundaries', 'coverage_complete': False,
        'archive_checksum_freshly_reverified': True, 'archive_input': integrity, 'fresh_archive_integrity': dict(integrity),
        'counts': {'unique_mxl_members': 254077, 'inspected_mxl_members': 254077,
            'validated_mxl_members': 254076, 'parse_failures': 1, 'csv_mxl_members_missing_archive': 0,
            'csv_native_records': 254077, 'csv_mxl_locators': 254077},
        'parse_failures': [{'member': 'mxl/1/2/failed.mxl', 'source_record_ids': ['123'], 'bytes': 100,
            'sha256': 'c' * 64, 'error_type': 'ValueError', 'reason': 'Malformed original notation'}],
        'missing_mxl_members': []}


def test_full_scan_with_preserved_parse_boundary_does_not_reject_other_valid_records():
    scan = completed_scan_with_parse_limit()
    assert expansion.require_complete_mxl_scan(scan)['validated_mxl_members'] == 254076


@pytest.mark.parametrize('mutation', [
    lambda scan: scan.update(status='running'),
    lambda scan: scan.update(coverage_complete=True),
    lambda scan: scan.update(archive_checksum_freshly_reverified=False),
    lambda scan: scan['counts'].update(inspected_mxl_members=254076),
    lambda scan: scan['counts'].update(validated_mxl_members=254077),
    lambda scan: scan['counts'].update(parse_failures=0),
    lambda scan: scan['parse_failures'].clear(),
    lambda scan: scan['parse_failures'][0].pop('source_record_ids'),
    lambda scan: scan['parse_failures'][0].update(member='../unsafe'),
    lambda scan: scan['parse_failures'][0].update(sha256='not-a-hash'),
    lambda scan: scan['counts'].update(csv_mxl_members_missing_archive=1),
    lambda scan: scan.update(missing_mxl_members=['mxl/1/2/failed.mxl']),
    lambda scan: scan['fresh_archive_integrity'].update(sha256='d' * 64),
])
def test_scan_completion_rejects_hidden_failures_missing_rows_or_incomplete_coverage(mutation):
    scan = completed_scan_with_parse_limit(); mutation(scan)
    with pytest.raises(ValueError):
        expansion.require_complete_mxl_scan(scan)


@pytest.mark.parametrize('field,value,status', [
    ('mxl', 'NA', 'pending_missing_publication_format'),
    ('pdf', '', 'pending_missing_publication_format'),
    ('mid', '../outside.mid', 'pending_invalid_publication_locator'),
])
def test_prepare_keeps_missing_or_invalid_declared_formats_pending_without_failing_the_batch(tmp_path, field, value, status):
    from tests.test_pdmx_expansion_adapter import example
    row, metadata = example()
    row.update(pdf='./pdf/1/2/x.pdf', mxl='./mxl/1/2/x.mxl', mid='./mid/1/2/x.mid')
    row[field] = value
    old = {'categories': [{'id': 'guitar'}], 'works': [{'id': 'musescore:1', 'assets': []}]}
    catalog_path = tmp_path / 'sources/musescore/catalog.json'; document(catalog_path, old)
    base = tmp_path / expansion.BASE; base.mkdir(parents=True)
    with gzip.open(base / 'baseline.json.gz', 'wt') as stream:
        json.dump({'documents': {'sources/musescore/catalog.json': {'value': old, 'sha256': expansion.sha(catalog_path.read_bytes())}}}, stream)
    source = tmp_path / 'sources/musescore/pdmx'; source.mkdir()
    with (source / 'PDMX.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(row)); writer.writeheader(); writer.writerow(row)
    (source / 'metadata.tar.gz').write_bytes(b'fixed metadata publication')
    config = {'scope_version': 'test', 'files': {}}; integrity = {'status': 'complete', 'files': {}}
    for name in ['PDMX.csv', 'metadata.tar.gz']:
        path = source / name; body = path.read_bytes()
        asset = {'size': len(body), 'md5': hashlib.md5(body).hexdigest(), 'sha256': hashlib.sha256(body).hexdigest()}
        config['files'][name] = asset
        integrity['files'][name] = {'bytes': len(body), 'md5': asset['md5'], 'sha256': asset['sha256'], 'stat': list(expansion.pdf_methods._stat_fingerprint(path))}
    document(tmp_path / expansion.CONFIG, config); document(base / 'archive-integrity.json', integrity)
    document(base / 'candidate-metadata.json', {'status': 'complete', 'records': {'654': {
        'csv': row, 'metadata': metadata, 'metadata_member': 'metadata/1/654.json', 'metadata_member_sha256': 'a' * 64}}})
    result = expansion.prepare(tmp_path, ['654'])
    assert result['metadata_accepted'] == 0 and result['excluded'] == 0
    plan = expansion.load(base / 'plan.json')
    assert plan['works'] == [] and plan['decisions']['musescore:654']['status'] == status
    assert plan['decisions']['musescore:654']['declared_locators'][{'mxl': 'MUSICXML', 'pdf': 'PDF', 'mid': 'MIDI'}[field]] == value
    assert expansion.load(catalog_path) == old


def extension_fixture(tmp_path):
    from tests.test_musescore_formats_acquisition import mxl_bytes
    base = tmp_path / expansion.BASE; base.mkdir(parents=True)
    source = tmp_path / 'sources/musescore/pdmx'; source.mkdir()
    config = {'files': {}}; integrity = {'status': 'complete', 'files': {}}
    for name in ['PDMX.csv', 'mxl.tar.gz']:
        path = source / name; path.write_bytes(('fixed ' + name).encode()); raw = path.read_bytes()
        config['files'][name] = {'size': len(raw), 'md5': hashlib.md5(raw).hexdigest(), 'sha256': hashlib.sha256(raw).hexdigest()}
        integrity['files'][name] = {'bytes': len(raw), 'md5': config['files'][name]['md5'], 'sha256': config['files'][name]['sha256'],
                                  'stat': list(expansion.pdf_methods._stat_fingerprint(path))}
    document(tmp_path / expansion.CONFIG, config); document(base / 'archive-integrity.json', integrity)
    document(base / 'candidate-metadata.json', {'status': 'complete', 'fixed': 'candidate source'})
    work = {'id': 'musescore:2', 'title_en': 'Native old title', 'assets': [{'format': 'MUSICXML', 'status': 'metadata_only'}],
            'metadata': {'pdmx_csv_transcription': {'mxl': './mxl/1/2/native2.mxl'}}}
    old = {'configuration_sha256': expansion.sha((tmp_path / expansion.CONFIG).read_bytes()),
           'candidate_snapshot_sha256': expansion.sha((base / 'candidate-metadata.json').read_bytes()),
           'original_catalog_sha256': 'f' * 64, 'selected_native_ids': ['2'],
           'decisions': {'musescore:2': {'status': 'candidate'}}, 'works': [work]}
    document(base / 'plan.json', old)
    pending = base / 'initial.mxl.part'; body = mxl_bytes(); pending.write_bytes(body)
    digest = hashlib.sha256(body).hexdigest()
    validation = expansion.format_methods.validate_source_format(pending, 'MUSICXML')
    local = expansion.format_methods._store(tmp_path, pending, digest, len(body), 'MUSICXML')
    receipt = {'sha256': integrity['files']['mxl.tar.gz']['sha256'],
               'upstream_checksum': 'md5:' + integrity['files']['mxl.tar.gz']['md5']}
    asset = expansion.format_methods._verified_asset(len(body), digest, local, 'mxl/1/2/native2.mxl', receipt, 'MUSICXML', validation)
    pending.unlink()
    journal = {'schema_version': 1, 'format': 'MUSICXML', 'status': 'interrupted',
        'configuration_sha256': old['configuration_sha256'], 'plan_sha256': expansion.sha((base / 'plan.json').read_bytes()),
        'scope_ids': ['musescore:2'], 'records': {'musescore:2': {'status': 'verified', 'asset': asset}}, 'counts': {'verified': 1}}
    document(base / 'mxl-extraction.json', journal)
    result = copy.deepcopy(old)
    added = copy.deepcopy(work); added['id'] = 'musescore:3'; added['title_en'] = 'New reviewed candidate'
    added['metadata']['pdmx_csv_transcription']['mxl'] = './mxl/1/2/native3.mxl'
    result['selected_native_ids'].append('3'); result['works'].append(added); result['decisions']['musescore:3'] = {'status': 'candidate'}
    return old, journal, result


def test_explicit_mxl_stage_extension_preserves_prior_bytes_records_and_physical_objects(tmp_path):
    old, journal, result = extension_fixture(tmp_path)
    base = tmp_path / expansion.BASE
    prior_plan = (base / 'plan.json').read_bytes(); prior_journal = (base / 'mxl-extraction.json').read_bytes()
    object_path = tmp_path / journal['records']['musescore:2']['asset']['local_path']
    stat = expansion.pdf_methods._stat_fingerprint(object_path)
    expansion.extend_prepared_plan(tmp_path, result)
    current = expansion.load(base / 'mxl-extraction.json')
    assert current['records']['musescore:2'] == journal['records']['musescore:2']
    assert current['records']['musescore:3']['status'] == 'pending'
    assert current['scope_ids'] == ['musescore:2', 'musescore:3']
    assert expansion.load(base / 'plan.json') == result
    assert expansion.pdf_methods._stat_fingerprint(object_path) == stat
    ledger = expansion.load(base / 'plan-extension.json'); event = ledger['events'][0]
    assert ledger['status'] == 'complete' and event['freshly_reverified_prior_records'] == 1
    assert gzip.decompress(expansion.base64.b64decode(event['prior_plan_gzip_base64'])) == prior_plan
    assert gzip.decompress(expansion.base64.b64decode(event['prior_mxl_journal_gzip_base64'])) == prior_journal
    assert not (base / 'plan-extension-prepared.json').exists()
    assert not (base / 'mxl-extension-prepared.json').exists()


@pytest.mark.parametrize('mutation', [
    lambda value: value['works'][0].update(title_en='Changed old title'),
    lambda value: value['decisions']['musescore:2'].update(status='recomputed'),
    lambda value: value.update(candidate_snapshot_sha256='a' * 64),
    lambda value: value.update(selected_native_ids=['3']),
    lambda value: value['works'].pop(0),
    lambda value: value['works'].append(copy.deepcopy(value['works'][0])),
])
def test_plan_extension_rejects_old_record_source_or_selection_drift(tmp_path, mutation):
    _, _, result = extension_fixture(tmp_path); mutation(result)
    before = (tmp_path / expansion.BASE / 'plan.json').read_bytes()
    with pytest.raises(ValueError, match='exact|superset'):
        expansion.extend_prepared_plan(tmp_path, result)
    assert (tmp_path / expansion.BASE / 'plan.json').read_bytes() == before


@pytest.mark.parametrize('name', ['pdf-extraction.json', 'mid-extraction.json', 'commit.json', 'integration.json'])
def test_plan_extension_cannot_change_scope_after_other_format_or_publication_phase(tmp_path, name):
    _, _, result = extension_fixture(tmp_path)
    document(tmp_path / expansion.BASE / name, {'status': 'complete'})
    with pytest.raises(ValueError, match='only during the MXL stage'):
        expansion.extend_prepared_plan(tmp_path, result)


def test_plan_extension_recovers_two_file_interruption_before_allowing_extraction_resume(tmp_path, monkeypatch):
    _, journal, result = extension_fixture(tmp_path)
    base = tmp_path / expansion.BASE; real_replace = expansion.os.replace
    def interrupted(source, target):
        if target == base / 'mxl-extraction.json':
            raise OSError('simulated extension interruption')
        return real_replace(source, target)
    monkeypatch.setattr(expansion.os, 'replace', interrupted)
    with pytest.raises(OSError, match='simulated'):
        expansion.extend_prepared_plan(tmp_path, result)
    assert expansion.load(base / 'plan.json') == result
    assert expansion.load(base / 'mxl-extraction.json') == journal
    with pytest.raises(ValueError, match='explicit prepare --extend-plan recovery'):
        expansion.extract(tmp_path, 'MUSICXML')
    monkeypatch.setattr(expansion.os, 'replace', real_replace)
    expansion.recover_plan_extension(tmp_path)
    assert expansion.load(base / 'plan-extension.json')['status'] == 'complete'
    assert expansion.load(base / 'mxl-extraction.json')['records']['musescore:2'] == journal['records']['musescore:2']


def test_plan_extension_freshly_detects_an_invalid_prior_object_before_migrating_scope(tmp_path):
    _, journal, result = extension_fixture(tmp_path)
    base = tmp_path / expansion.BASE; old_plan = (base / 'plan.json').read_bytes(); old_journal = (base / 'mxl-extraction.json').read_bytes()
    (tmp_path / journal['records']['musescore:2']['asset']['local_path']).write_bytes(b'corrupt')
    with pytest.raises(ValueError):
        expansion.extend_prepared_plan(tmp_path, result)
    assert (base / 'plan.json').read_bytes() == old_plan and (base / 'mxl-extraction.json').read_bytes() == old_journal


def test_old_pdf_acquisition_refuses_expanded_catalog_even_when_scope_marker_is_empty():
    with pytest.raises(ValueError, match='legacy PDMX PDF acquisition'):
        expansion.pdf_methods._jobs({'snapshot': {'expansion': {}}})


def part(identity, name, *, notes=4, harmonies=0, instrument=None):
    return {'id': identity, 'part_names': [name], 'instrument_names': [instrument or name],
            'note_count': notes, 'harmony_count': harmonies, 'frame_count': 0, 'slash_count': 0}


def test_recall_rejects_explicit_active_voice_but_keeps_evidence():
    result = expansion.recall_member({'parts': [part('P1', 'Guitar'), part('P2', 'Soprano')]})
    assert result['selected'] is False
    assert result['guitar_parts'] == ['P1']
    assert result['excluded_parts'] == [{'part_id': 'P2', 'kinds': ['voice']}]


def test_empty_excluded_placeholder_is_not_a_singing_role():
    assert expansion.recall_member({'parts': [part('P1', 'Guitar'), part('P2', 'Soprano', notes=0)]})['selected']


def test_contradictory_names_require_deep_review_instead_of_automatic_exclusion():
    result = expansion.recall_member({'parts': [part('P1', 'Guitar', instrument='Electric Guitar')]})
    assert result['selected'] and result['unresolved_parts'] == ['P1']


def test_harmony_only_guitar_is_a_positive_scope_candidate():
    result = expansion.recall_member({'parts': [part('P1', 'Guitar', notes=0, harmonies=3)]})
    assert result['selected'] and result['guitar_parts'] == ['P1']


def test_recall_part_name_without_instrument_declaration_remains_a_candidate():
    row = part('P1', 'Steel Guitar')
    row['instrument_names'] = []
    result = expansion.recall_member({'parts': [row]})
    assert result['selected'] and result['unresolved_parts'] == ['P1']


def test_recall_keeps_named_electric_vs_acoustic_patch_conflict_for_review():
    row = part('P1', 'Steel Guitar')
    row['midi_programs_1based'] = [25]
    result = expansion.recall_member({'parts': [row]})
    assert result['selected'] and result['unresolved_parts'] == ['P1']


def test_recall_keeps_unknown_named_instrument_vs_voice_template_conflict():
    result = expansion.recall_member({'parts': [part('P1', 'Laud', instrument='Voice'), part('P2', 'Guitar')]})
    assert result['selected'] and 'P1' in result['unresolved_parts']


def test_recall_does_not_treat_all_declared_instruments_as_active_switches():
    row = part('P1', 'Banjo')
    row['instrument_names'] = ['Banjo', 'Electric Bass']
    result = expansion.recall_member({'parts': [row, part('P2', 'Guitar')]})
    assert result['selected'] and 'P1' in result['unresolved_parts']
