from __future__ import annotations

import gzip
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
import zipfile

import fitz
import pytest

import review_musescore_deep as deep
import review_musescore_remaining as shared
from catalog_instrumentation import per_record_guard
from score_instrumentation import read_mxl_evidence
from score_midi_crosscheck import read_sounding_midi
from tests.test_musescore_remaining_review import fixture as remaining_fixture, guard, write_json
from verify_musescore_expansion import FINAL_INPUT_PATHS


def actual_bytes(pages):
    from io import BytesIO
    pdf = fitz.open()
    for index in range(pages):
        pdf.new_page().insert_text((50, 50), 'Guitar score page ' + str(index + 1))
    body = pdf.tobytes(); pdf.close()
    xml = ('<score-partwise version="3.1"><part-list><score-part id="P1"><part-name>Guitar</part-name>'
        '<score-instrument id="I1"><instrument-name>Guitar</instrument-name></score-instrument>'
        '<midi-instrument id="I1"><midi-channel>1</midi-channel><midi-program>25</midi-program></midi-instrument>'
        '</score-part></part-list><part id="P1"><measure number="1"><attributes><divisions>1</divisions>'
        '<clef><sign>G</sign><line>2</line></clef></attributes><note><pitch><step>C</step><octave>4</octave></pitch>'
        '<duration>1</duration></note></measure></part></score-partwise>')
    output = BytesIO()
    with zipfile.ZipFile(output, 'w') as archive:
        archive.writestr('META-INF/container.xml', '<container><rootfiles><rootfile full-path="score.xml" '
            'media-type="application/vnd.recordare.musicxml+xml"/></rootfiles></container>')
        archive.writestr('score.xml', xml)
    track = b'\0\xff\x03\x06Guitar\0\xc0\x18\0\x90\x3c\x40\x01\x80\x3c\0\0\xff\x2f\0'
    midi = b'MThd' + struct.pack('>IHHH', 6, 1, 1, 480) + b'MTrk' + struct.pack('>I', len(track)) + track
    return {'PDF': body, 'MUSICXML': output.getvalue(), 'MIDI': midi}


@pytest.fixture
def fixture(remaining_fixture, monkeypatch):
    root, _, final, _ = remaining_fixture
    monkeypatch.setattr(deep, 'EXPECTED_COUNT', 2)
    monkeypatch.setattr(deep, 'EXPECTED_COHORTS', {'a': 1, 'b': 1})
    monkeypatch.setattr(deep, 'EXPECTED_PAGES', 3)
    monkeypatch.setattr(deep, 'EXPECTED_ROOT_IDS', {'musescore:1'})
    plan = json.loads((root / shared.BASE / 'plan.json').read_bytes())
    works = {row['id']: row for row in plan['works']}
    ids = list(works)
    assets = {identity: {} for identity in ids}
    for index, identity in enumerate(ids):
        for label, raw in actual_bytes(index + 1).items():
            digest = hashlib.sha256(raw).hexdigest()
            relative = 'sources/musescore/objects/' + digest + '.' + deep.FORMATS[label]
            (root / relative).write_bytes(raw)
            assets[identity][label] = {'format': label, 'status': 'verified', 'sha256': digest,
                'size': len(raw), 'local_path': relative, 'archive_member': deep.FORMATS[label] + '/native/' + identity.split(':')[1],
                'archive_sha256': 'a' * 64}
    for label, suffix in deep.FORMATS.items():
        path = root / shared.BASE / (suffix + '-extraction.json')
        journal = json.loads(path.read_bytes())
        journal['records'] = {identity: {'status': 'verified', 'asset': assets[identity][label]} for identity in ids}
        write_json(root, path.relative_to(root), journal)
    scope_path = shared.BASE / 'scope-review.json'
    scope = json.loads((root / scope_path).read_bytes())
    scope['inputs']['mxl_extraction'] = guard(root / FINAL_INPUT_PATHS['MUSICXML'])
    write_json(root, scope_path, scope)
    final['inputs'] = {name: guard(root / relative) for name, relative in FINAL_INPUT_PATHS.items()}
    write_json(root, shared.BASE / 'final-review.json', final)
    prior = gzip.compress(b'{"historical":true}', mtime=0)
    (root / shared.DESTINATION).write_bytes(prior)
    manifest = {'schema_version': 1, 'ids': ids, 'cohorts': {'a': ids[:1], 'b': ids[1:]},
        'prior_remaining_review_sha256': hashlib.sha256(prior).hexdigest()}
    write_json(root, deep.SCOPE, manifest)
    frozen = {'schema_version': 1, 'documents': {'sources/musescore/catalog.json': {'value': {'works': [{'id': 'musescore:99'}]}}},
        'continuation': {'stage': 'deep-pending-review', 'review_scope_path': str(deep.SCOPE),
            'review_scope_guard': guard(root / deep.SCOPE), 'pending_records': 2, 'prior_record_count': 1,
            'immutable_inputs': {str(shared.DESTINATION): guard(root / shared.DESTINATION)}}}
    frozen['continuation']['immutable_inputs'].update({str(shared.BASE / name): guard(root / shared.BASE / name)
        for name in ['plan.json', 'pdf-extraction.json', 'mxl-extraction.json', 'mid-extraction.json']})
    archive = root / shared.BASE / 'deep-continuation-baseline.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as stream:
        stream.writestr('baseline.json', json.dumps(frozen))
    write_json(root, shared.BASE / 'deep-baseline-capture.json', {'status': 'captured', 'records': 1,
        'sha256': guard(archive)['sha256']})
    (root / deep.METHOD).write_text('Exact current deep receipt method')
    (root / deep.AUXILIARY_SOURCES['b_producer']).write_bytes(b'# Original temporary producer\r\nprint("complete")\r\n')
    documents = {}
    for index, cohort in enumerate(('a', 'b')):
        identity = ids[index]; work = works[identity]
        midi = read_sounding_midi(root / assets[identity]['MIDI']['local_path'])
        mxl = read_mxl_evidence(root / assets[identity]['MUSICXML']['local_path'])
        with fitz.open(root / assets[identity]['PDF']['local_path']) as document:
            pages = [{'page': number + 1, 'text': page.get_text(sort=True)} for number, page in enumerate(document)]
        row = {'id': identity, 'native_record_sha256': per_record_guard(work), 'decision': 'accepted' if index == 0 else 'pending',
            'reason': 'Actual named guitar role confirmed.' if index == 0 else 'Alto label lacks a confirmed physical instrument.'}
        if cohort == 'a':
            row.update(source={key: work[key] for key in ('title_en', 'composer_en', 'source_url')}, assets=assets[identity],
                MXL={'parts': mxl['parts']}, MIDI=midi, PDF={'pages': pages})
        else:
            row.update({key: work[key] for key in ('title_en', 'composer_en', 'source_url')})
            row.update(asset_guards=assets[identity], mxl_parts=mxl['parts'], mxl_groups=mxl['part_groups'],
                midi_evidence=midi, pdf_pages=pages)
        documents[cohort] = {'schema_version': 1, 'status': 'complete', 'records': {identity: row}, 'entries': [],
            'original_ordered_value': {'z': '原文', 'a': None}}
    documents['root'] = {'schema_version': 1, 'status': 'complete', 'entries': [], 'records': {
        ids[0]: {'proposed_status': 'accepted', 'reason': 'Exact guarded target attack correspondence confirmed.',
            'production_final_dry_run': {'status': 'accepted', 'asset_guards': assets[ids[0]]}}}}
    for key, relative in deep.PROPOSALS.items():
        write_json(root, relative, documents[key])
    return root, documents, final, assets


def read_bundle(root):
    return shared._read_gzip_json(root / deep.DESTINATION)


def test_lossless_deep_receipt_verifies_after_all_temporary_proposals_and_source_are_removed(fixture):
    root, documents, _, _ = fixture
    prior = (root / shared.DESTINATION).read_bytes()
    result = deep.consolidate(root)
    assert result['summary']['statuses'] == {'accepted': 1, 'pending': 1}
    assert result['summary']['pdf_pages'] == 3
    bundle = read_bundle(root)
    assert bundle['original_proposals'] == documents
    assert bundle['auxiliary_sources']['b_producer']['text'].endswith('\r\n')
    before = (root / deep.DESTINATION).read_bytes()
    for relative in [*deep.PROPOSALS.values(), *deep.AUXILIARY_SOURCES.values()]:
        (root / relative).unlink()
    assert deep.verify(root)['status'] == 'verified'
    assert (root / deep.DESTINATION).read_bytes() == before
    assert (root / shared.DESTINATION).read_bytes() == prior
    assert not list((root / deep.BASE).glob('*.part'))


def test_existing_receipt_requires_explicit_refresh_and_keeps_full_original_values(fixture):
    root, documents, final, _ = fixture
    deep.consolidate(root)
    with pytest.raises(ValueError, match='already exists'): deep.consolidate(root)
    final['records']['musescore:1'].update(status='pending', reason='unresolved_midi_correspondence')
    write_json(root, deep.BASE / 'final-review.json', final)
    with pytest.raises(ValueError, match='refresh outcomes explicitly'): deep.verify(root)
    assert deep.refresh_outcomes(root)['summary']['statuses'] == {'pending': 2}
    assert read_bundle(root)['original_proposals'] == documents
    assert 'unresolved_midi_correspondence' in read_bundle(root)['records']['musescore:1']['reason']


@pytest.mark.parametrize('mutation', ['incomplete', 'native', 'asset', 'PDF_text', 'PDF_page', 'MXL', 'MIDI', 'reason', 'root'])
def test_incomplete_or_stale_actual_evidence_never_creates_a_deep_receipt(fixture, mutation):
    root, documents, _, _ = fixture
    row = documents['a']['records']['musescore:1']
    if mutation == 'incomplete': documents['a']['status'] = 'semantic_in_progress'
    elif mutation == 'native': row['source']['title_en'] += ' wrong'
    elif mutation == 'asset': row['assets']['PDF']['sha256'] = 'b' * 64
    elif mutation == 'PDF_text': row['PDF']['pages'][0]['text'] += ' not in PDF'
    elif mutation == 'PDF_page': row['PDF']['pages'][0]['page'] = 2
    elif mutation == 'MXL': row['MXL']['parts'][0]['name'] = 'Wrong instrument'
    elif mutation == 'MIDI': row['MIDI']['tracks'][0]['note_on_count'] += 1
    elif mutation == 'reason': row['reason'] = 'Awaiting exact semantic review'
    else: documents['root']['records'].clear()
    for key, relative in deep.PROPOSALS.items(): write_json(root, relative, documents[key])
    with pytest.raises(ValueError): deep.consolidate(root)
    assert not (root / deep.DESTINATION).exists()


def test_duplicate_proposal_json_keys_are_rejected(fixture):
    root, _, _, _ = fixture
    (root / deep.PROPOSALS['a']).write_text('{"status":"complete","status":"complete"}')
    with pytest.raises(ValueError, match='duplicate JSON'): deep.consolidate(root)


def test_default_verification_freshly_rejects_changed_score_bytes(fixture):
    root, _, _, assets = fixture
    deep.consolidate(root)
    path = root / assets['musescore:2']['MIDI']['local_path']
    raw = path.read_bytes(); path.write_bytes(b'!' + raw[1:])
    with pytest.raises(ValueError, match='score bytes changed'): deep.verify(root)


def test_symlinked_score_and_output_paths_are_rejected_even_inside_root(fixture):
    root, _, _, assets = fixture
    path = root / assets['musescore:1']['PDF']['local_path']
    target = path.with_name('original.pdf'); path.rename(target); path.symlink_to(target)
    with pytest.raises(ValueError, match='unsafe private path|symlink'): deep.consolidate(root)
    path.unlink(); target.rename(path)
    output = root / deep.DESTINATION; output.symlink_to(root / 'foreign.gz')
    with pytest.raises(ValueError, match='unsafe private path|symlink'): deep.consolidate(root)


@pytest.mark.parametrize('target', ['plan', 'semantic_method', 'cases'])
def test_input_drift_during_actual_parsing_prevents_any_receipt(fixture, monkeypatch, target):
    root, _, _, _ = fixture
    reader = deep.read_mxl_evidence
    changed = False
    def mutate(path):
        nonlocal changed
        if not changed:
            relative = (deep.BASE / 'plan.json' if target == 'plan' else deep.EXACT_CASE_PATH
                        if target == 'cases' else sorted(deep.FINAL_METHOD_PATHS)[0])
            with (root / relative).open('a') as stream: stream.write(' ')
            changed = True
        return reader(path)
    monkeypatch.setattr(deep, 'read_mxl_evidence', mutate)
    with pytest.raises(ValueError, match='changed during verification'): deep.consolidate(root)
    assert not (root / deep.DESTINATION).exists()


def test_compressed_readback_failure_preserves_the_previous_receipt(fixture, monkeypatch):
    root, _, _, _ = fixture
    deep.consolidate(root)
    path = root / deep.DESTINATION; before = path.read_bytes()
    reader = shared._read_gzip_json
    def corrupt_temporary(value):
        return {'corrupt': True} if str(value).endswith('.part') else reader(value)
    monkeypatch.setattr(shared, '_read_gzip_json', corrupt_temporary)
    with pytest.raises(ValueError, match='semantic readback differs'): deep.refresh_outcomes(root)
    assert path.read_bytes() == before and not list(path.parent.glob('*.part'))


def test_interrupted_refresh_preserves_prior_receipt_and_cleans_temporary_files(fixture, monkeypatch):
    root, _, _, _ = fixture
    deep.consolidate(root)
    path = root / deep.DESTINATION; before = path.read_bytes()
    replace = deep.os.replace
    def fail(source, destination):
        if Path(destination) == path: raise OSError('interrupted atomic receipt replacement')
        return replace(source, destination)
    monkeypatch.setattr(deep.os, 'replace', fail)
    with pytest.raises(OSError, match='interrupted atomic'): deep.refresh_outcomes(root)
    assert path.read_bytes() == before and not list(path.parent.glob('*.part'))


def supplement_fixture(root, final, assets):
    plan = json.loads((root / deep.BASE / 'plan.json').read_bytes())
    work = plan['works'][0]
    identity = work['id']
    entry = {key: work[key] for key in ('id', 'title_en', 'composer_en', 'source_url')}
    entry.update(native_record_sha256=per_record_guard(work),
        pdf_sha256=assets[identity]['PDF']['sha256'], mxl_sha256=assets[identity]['MUSICXML']['sha256'],
        midi_sha256=assets[identity]['MIDI']['sha256'], part_names=['Guitar'],
        part_decisions={'P1': {'resolved': True, 'role_active': True}},
        note='The actual written P1 guitar role and all original score bytes were independently checked.')
    write_json(root, deep.EXACT_CASE_PATH, {'schema_version': 1, 'entries': [entry]})
    case_guard = guard(root / deep.EXACT_CASE_PATH)
    scope = json.loads((root / deep.BASE / 'scope-review.json').read_bytes())
    scope['inputs']['reviewed_cases'] = case_guard
    write_json(root, deep.BASE / 'scope-review.json', scope)
    final['reviewed_cases'] = case_guard
    final['inputs'] = {name: guard(root / relative) for name, relative in FINAL_INPUT_PATHS.items()}
    write_json(root, deep.BASE / 'final-review.json', final)
    value = {'schema_version': 1, 'status': 'complete', 'entries': [deepcopy(entry)],
        'records': [{'id': identity, 'decision': 'accepted', 'reason': entry['note'],
            'canonical_reason': 'three_format_review_complete', 'native_record_sha256': per_record_guard(work),
            'assets': deepcopy(assets[identity]), 'exact_entry': deepcopy(entry),
            'full_original_supplement_evidence': {'unknown': None, 'original': '♭ / 吉他 / original'}}]}
    relative = deep.BASE / 'supplemental-decision.json'
    write_json(root, relative, value)
    return relative, value


def test_lossless_supplement_is_independently_verified_without_temporary_files(fixture):
    root, documents, final, assets = fixture
    deep.consolidate(root)
    before = read_bundle(root)
    relative, supplement = supplement_fixture(root, final, assets)
    raw_guard = guard(root / relative)
    assert deep.refresh_outcomes(root, supplement=relative)['summary']['supplement_records'] == 1
    bundle = read_bundle(root)
    assert bundle['original_proposals'] == documents
    assert bundle['proposal_original_bytes'] == before['proposal_original_bytes']
    assert bundle['proposal_semantic_sha256'] == before['proposal_semantic_sha256']
    assert bundle['review_supplement'] == {'value': supplement, 'original_bytes': raw_guard,
        'semantic_sha256': shared.canonical_sha256(supplement)}
    row = bundle['records']['musescore:1']
    assert row['reason'] == supplement['records'][0]['reason']
    assert row['proposal_decisions']['root']['reason'] == documents['root']['records']['musescore:1']['reason']
    assert row['proposal_decisions']['supplement']['canonical_reason'] == row['outcome']['reason']
    for path in [relative, *deep.PROPOSALS.values(), *deep.AUXILIARY_SOURCES.values()]: (root / path).unlink()
    content = (root / deep.DESTINATION).read_bytes()
    assert deep.verify(root)['status'] == 'verified'
    assert (root / deep.DESTINATION).read_bytes() == content
    assert deep.refresh_outcomes(root)['status'] == 'outcomes_refreshed'
    assert read_bundle(root)['review_supplement'] == bundle['review_supplement']


@pytest.mark.parametrize('mutation', ['case', 'case_type', 'native', 'asset', 'decision', 'canonical_reason',
    'reason', 'duplicate', 'outside', 'missing_case', 'unfinished'])
def test_stale_or_unfinished_supplements_cannot_replace_the_existing_receipt(fixture, mutation):
    root, _, final, assets = fixture
    deep.consolidate(root)
    original = (root / deep.DESTINATION).read_bytes()
    relative, value = supplement_fixture(root, final, assets)
    row = value['records'][0]
    if mutation == 'case': row['exact_entry']['note'] += ' fabricated new explanation'
    elif mutation == 'case_type': row['exact_entry']['part_decisions']['P1']['role_active'] = 1
    elif mutation == 'native': row['native_record_sha256'] = '0' * 64
    elif mutation == 'asset': row['assets']['MIDI']['sha256'] = '0' * 64
    elif mutation == 'decision': row['decision'] = 'pending'
    elif mutation == 'canonical_reason': row['canonical_reason'] = 'ambiguous_actual_instrumentation'
    elif mutation == 'reason': row['reason'] = 'All files have been reviewed.'
    elif mutation == 'duplicate': value['records'].append(deepcopy(row))
    elif mutation == 'outside': row['id'] = 'musescore:999'
    elif mutation == 'missing_case': del row['exact_entry']
    else: value['status'] = 'semantic_in_progress'
    # Keep the optional declarations in agreement, so each negative exercises
    # the actual binding rather than only the duplicate representation check.
    value.pop('entries')
    write_json(root, relative, value)
    with pytest.raises(ValueError): deep.refresh_outcomes(root, supplement=relative)
    assert (root / deep.DESTINATION).read_bytes() == original
    assert not list((root / deep.BASE).glob('*.part'))


def test_embedded_supplement_cannot_be_replaced_or_forged_after_source_removal(fixture):
    root, _, final, assets = fixture
    deep.consolidate(root)
    relative, value = supplement_fixture(root, final, assets)
    deep.refresh_outcomes(root, supplement=relative)
    content = (root / deep.DESTINATION).read_bytes()
    value['records'][0]['reason'] += ' Replacement would lose an original decision.'
    write_json(root, relative, value)
    with pytest.raises(ValueError, match='cannot replace'): deep.refresh_outcomes(root, supplement=relative)
    assert (root / deep.DESTINATION).read_bytes() == content
    bundle = read_bundle(root)
    embedded = bundle['review_supplement']
    embedded['value']['records'][0]['exact_entry']['note'] += ' Tampered in the gzip.'
    embedded['value'].pop('entries')
    embedded['semantic_sha256'] = shared.canonical_sha256(embedded['value'])
    with gzip.open(root / deep.DESTINATION, 'wt', encoding='utf-8') as stream: json.dump(bundle, stream)
    (root / relative).unlink()
    with pytest.raises(ValueError, match='complete current exact case'): deep.verify(root)


@pytest.mark.parametrize('mutation', ['duplicate_keys', 'symlink', 'outside_root'])
def test_unsafe_supplement_inputs_never_replace_the_existing_receipt(fixture, tmp_path, mutation):
    root, _, final, assets = fixture
    deep.consolidate(root)
    relative, _ = supplement_fixture(root, final, assets)
    content = (root / deep.DESTINATION).read_bytes()
    if mutation == 'duplicate_keys':
        (root / relative).write_text('{"status":"complete","status":"complete"}')
    elif mutation == 'symlink':
        path = root / relative
        original = path.with_suffix('.original.json')
        path.rename(original); path.symlink_to(original)
    else:
        relative = tmp_path.parent / 'outside-project.json'
    with pytest.raises(ValueError): deep.refresh_outcomes(root, supplement=relative)
    assert (root / deep.DESTINATION).read_bytes() == content
    assert not list((root / deep.BASE).glob('*.part'))


@pytest.mark.parametrize('arguments', [[], ['--verify'], ['--consolidate']])
def test_supplement_requires_explicit_outcome_refresh(monkeypatch, arguments):
    monkeypatch.setattr('sys.argv', ['review_musescore_deep.py', *arguments, '--supplement', 'proposal.json'])
    with pytest.raises(SystemExit) as error: deep.main()
    assert error.value.code == 2
