from copy import deepcopy
import hashlib
import json

import pytest

from catalog_classification import (APPLIED_CLASSIFICATIONS, REVIEW_PATH,
    apply_classification_reviews, digest, public_details)
from catalog_unification import instrumentation_topic


def fixture(tmp_path, *, score=False):
    category = {'id': 'solo', 'name': 'Solo Guitar'}
    work = {'id': 'example:1', 'title_en': 'Example', 'category_ids': ['solo'],
            'metadata': {'instrumentation': 'Solo guitar'}, 'assets': []}
    evidence = [{'kind': 'native_field', 'path': ['metadata', 'instrumentation'], 'value': 'Solo guitar'}]
    if score:
        data = b'%PDF-1.4 immutable test bytes'
        path = tmp_path / 'score.pdf'; path.write_bytes(data)
        asset = {'format': 'PDF', 'status': 'verified', 'sha256': hashlib.sha256(data).hexdigest(),
                 'size': len(data), 'local_path': 'score.pdf'}
        work['assets'].append(asset)
        evidence.append({'kind': 'file', 'format': 'PDF', 'sha256': asset['sha256'],
                         'size': len(data), 'observation': 'Printed solo guitar declaration.'})
    decision = {'native_record_sha256': digest(work), 'topic_id': 'solo', 'player_count': 1,
        'basis': 'reviewed_score_evidence' if score else 'reviewed_source_evidence',
        'instrumentation': '吉他独奏', 'note': '明确的独奏声明；保留原始分类。', 'evidence': evidence}
    catalog = {'source_id': 'example', 'categories': [category], 'works': [work]}
    review = {'schema_version': 1, 'status': 'complete', 'entries': {'example:1': decision}}
    path = tmp_path / REVIEW_PATH; path.parent.mkdir(parents=True); path.write_text(json.dumps(review))
    return catalog, review, path


def test_review_preserves_native_and_distinguishes_source_count(tmp_path):
    native, _, _ = fixture(tmp_path)
    original = deepcopy(native)
    result = apply_classification_reviews(tmp_path, native, native)
    decision = result[APPLIED_CLASSIFICATIONS]['example:1']
    assert native == original
    assert public_details(decision)['declared_player_count'] == '1'
    assert 'reviewed_player_count' not in public_details(decision)
    assert result['works'] == original['works']


@pytest.mark.parametrize('field,value', [('title_en', 'Changed title'), ('assets', [{'license': 'changed'}])])
def test_full_native_guard_rejects_changes(tmp_path, field, value):
    native, _, _ = fixture(tmp_path)
    native['works'][0][field] = value
    with pytest.raises(ValueError, match='stale native'):
        apply_classification_reviews(tmp_path, native, native)


def test_score_evidence_rechecks_actual_bytes_on_change(tmp_path):
    native, _, _ = fixture(tmp_path, score=True)
    apply_classification_reviews(tmp_path, native, native)
    path = tmp_path / 'score.pdf'; path.write_bytes(path.read_bytes().replace(b'immutable', b'IMMUTABLE'))
    with pytest.raises(ValueError, match='score guard changed'):
        apply_classification_reviews(tmp_path, native, native)


@pytest.mark.parametrize('mutation', ['field', 'count', 'forged', 'missing_file', 'leak'])
def test_invalid_evidence_fails_closed(tmp_path, mutation):
    native, review, path = fixture(tmp_path)
    decision = review['entries']['example:1']
    if mutation == 'field': decision['evidence'][0]['value'] = 'Duet'
    if mutation == 'count': decision['player_count'] = None
    if mutation == 'forged': native[APPLIED_CLASSIFICATIONS] = {}
    if mutation == 'missing_file': decision['basis'] = 'reviewed_score_evidence'
    if mutation == 'leak': decision['note'] = 'sources/private/example.pdf'
    path.write_text(json.dumps(review))
    with pytest.raises(ValueError):
        apply_classification_reviews(tmp_path, native, native)


@pytest.mark.parametrize('label,topic', [('For 12 guitars', 'guitar_ensemble'),
    ('For 12 guitars (arr)', 'guitar_ensemble'), ('For 7-string guitar (arr)', 'solo'),
    ('For 7 string guitar', 'solo'), ('For 7 string guitar and bass', None),
    ('For 12 guitars and voice', None), ('Guitar', 'guitar_unspecified')])
def test_extended_string_and_larger_ensemble_categories(label, topic):
    assert instrumentation_topic(label) == topic


def test_current_broad_baseline_has_precedence_over_older_publications(tmp_path):
    from expand_musescore_library import (active_baseline_path, CONTINUATION,
        DEEP_CONTINUATION, BROAD_CONTINUATION)
    for path in (CONTINUATION, DEEP_CONTINUATION, BROAD_CONTINUATION):
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).touch()
        assert active_baseline_path(tmp_path) == tmp_path / path


def test_classification_public_preservation_rejects_unrelated_changes(tmp_path):
    from verify_library_classification import compare_classified_public
    from verify_musescore_instrumentation import AuditFailure
    native, review, _ = fixture(tmp_path)
    before = {'categories': [], 'works': [{'id': 'example:1', 'source_id': 'example',
        'title_en': 'Example', 'details': {'license': 'Original license'}, 'category_ids': [7],
        'topic_ids': ['unspecified', 'studies'],
        'topic_evidence': {'unspecified': 'no_exact_instrumentation_evidence', 'studies': 'title_keyword'},
        'topic_category_ids': {'unspecified': [7], 'studies': [7]}}]}
    after = deepcopy(before)
    row = after['works'][0]
    row.update(topic_ids=['solo', 'studies'],
        topic_evidence={'solo': 'reviewed_source_evidence', 'studies': 'title_keyword'},
        topic_category_ids={'solo': [7], 'studies': [7]})
    row['details'].update(public_details(review['entries']['example:1']))
    assert compare_classified_public(before, after, review['entries'])['all_other_public_work_fields_exact']
    row['details']['license'] = 'Altered license'
    with pytest.raises(AuditFailure, match='unreviewed public field'):
        compare_classified_public(before, after, review['entries'])


@pytest.mark.parametrize('text', ['/Users/example/private', 'C:\\Users\\secret', 'private/inventory',
                                  'note /Volumes/library/score', '/tmp/local'])
def test_classification_rejects_private_paths(tmp_path, text):
    native, review, path = fixture(tmp_path)
    review['entries']['example:1']['note'] = text
    path.write_text(json.dumps(review))
    with pytest.raises(ValueError, match='unsafe reviewed'):
        apply_classification_reviews(tmp_path, native, native)


@pytest.mark.parametrize('topic', ['unspecified', 'guitar_unspecified', 'reference'])
def test_unresolved_and_reference_counts_are_unknown(tmp_path, topic):
    native, review, path = fixture(tmp_path)
    review['entries']['example:1']['topic_id'] = topic
    path.write_text(json.dumps(review))
    with pytest.raises(ValueError, match='cannot claim'):
        apply_classification_reviews(tmp_path, native, native)


def test_inconclusive_source_audit_does_not_claim_a_declaration(tmp_path):
    native, review, path = fixture(tmp_path)
    decision = review['entries']['example:1']
    decision.update(topic_id='unspecified', player_count=None, basis='reviewed_source_audit')
    path.write_text(json.dumps(review))
    checked = apply_classification_reviews(tmp_path, native, native)[APPLIED_CLASSIFICATIONS]['example:1']
    assert public_details(checked)['classification_basis'] == '来源审查·仍待确认'


def test_unification_rejects_review_for_a_mistyped_source(tmp_path):
    from tests.test_catalog_unification import unified_fixture
    fixture(tmp_path)
    with pytest.raises(ValueError, match='unapplied or unknown'):
        unified_fixture(tmp_path, [{'id': 'different_source:1', 'metadata': {'instrumentation': 'Guitar'}}])


def test_broad_prepare_recovers_between_semantic_writes_and_rejects_drift(tmp_path, monkeypatch):
    import review_musescore_broad as broad
    from verify_musescore_instrumentation import AuditFailure
    directory = tmp_path / broad.BASE; directory.mkdir(parents=True)
    old = {'scope-review.json': {'old': 'scope'}, 'final-review.json': {'old': 'final'}}
    for name, value in old.items():
        broad._atomic_json(directory / name, value)
    before = {name: broad.file_guard(directory / name) for name in old}
    scope, final = {'new': 'scope'}, {'inputs': {}, 'new': 'final'}
    real_atomic = broad._atomic_json
    def interrupted(path, value):
        if path.name == 'final-review.json':
            raise OSError('simulated interruption')
        real_atomic(path, value)
    monkeypatch.setattr(broad, 'check_final_input_guards', lambda *args: None)
    monkeypatch.setattr(broad, '_atomic_json', interrupted)
    with pytest.raises(OSError):
        broad.write_semantic_transaction(tmp_path, scope, final, before)
    assert broad.load(directory / 'scope-review.json') == scope
    assert broad.load(directory / 'final-review.json') == old['final-review.json']
    monkeypatch.setattr(broad, '_atomic_json', real_atomic)
    broad.write_semantic_transaction(tmp_path, scope, final, before)
    assert broad.load(directory / 'broad-prepare.json')['status'] == 'complete'
    assert broad.load(directory / 'final-review.json') == final
    broad.write_semantic_transaction(tmp_path, scope, final, before)
    with pytest.raises(AuditFailure):
        broad.write_semantic_transaction(tmp_path, {'unreviewed': 'drift'}, final, before)
