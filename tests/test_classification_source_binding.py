"""Regression tests for exact source-record and publication-scope binding."""
from copy import deepcopy
import hashlib
import json

import pytest

from catalog_classification import digest
from review_library_classification import _archive_decision, _local_decision
from verify_library_classification import compare_classified_public
from verify_musescore_instrumentation import AuditFailure


def _freeze_json(root, sid, name, payload, url):
    relative = f'sources/{sid}/{name}'
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, ensure_ascii=False).encode()
    path.write_bytes(body)
    sha = hashlib.sha256(body).hexdigest()
    state = root / 'sources' / sid / 'discovery_state.json'
    state.write_text(json.dumps({'requests': {url: {
        'status': 200, 'cache': name, 'sha256': sha}}}))
    return relative, sha


def _archive_case(tmp_path, *, record=None, proposed=None):
    url = 'https://archive.example/record/op-15/'
    title = 'Op. 15: Twelve Studies'
    native_id = 1057
    work = {
        'id': 'cglib:1057', 'source_url': url, 'title_en': title,
        'category_ids': ['23'], 'metadata': {'cms_post_id': native_id},
        'resource_type': 'score', 'assets': [],
    }
    original = record or {
        'id': native_id, 'link': url, 'title': {'rendered': title},
        'categories': [23], 'tags': [811],
    }
    relative, sha = _freeze_json(tmp_path, 'cglib', 'posts.json', [original], url)
    evidence_record = {
        'id': original['id'], 'link': original['link'],
        'title': original.get('title', {}).get('rendered'),
        'categories': original.get('categories'), 'tags': original.get('tags'),
        'response_path': relative, 'response_file_sha256': sha,
    }
    if proposed:
        evidence_record.update(proposed)
    row = {
        'native_record_canonical_sha256': digest(work),
        'topic': 'guitar_unspecified', 'player_count': None,
        'reason': 'source evidence retained',
        'evidence': [{'field': 'frozen_source_page.record', 'raw_value': evidence_record}],
    }
    return work, row, original


def test_archive_decision_accepts_complete_original_posts_record(tmp_path):
    work, row, record = _archive_case(tmp_path)

    decision = _archive_decision(tmp_path, work, row)

    assert decision['topic_id'] == 'guitar_unspecified'
    assert decision['evidence'][0]['kind'] == 'source_snapshot'
    assert decision['evidence'][0]['sha256'] == row['evidence'][0]['raw_value']['response_file_sha256']
    assert record['categories'] == [23] and record['tags'] == [811]


@pytest.mark.parametrize(('field', 'replacement'), [
    ('id', 1058),
    ('link', 'https://archive.example/record/other/'),
    ('title', 'Wrong title'),
    ('categories', [24]),
    ('tags', [812]),
])
def test_archive_decision_rejects_proposed_posts_field_drift(tmp_path, field, replacement):
    work, row, record = _archive_case(tmp_path)
    if field == 'title':
        proposed = {'title': replacement}
    else:
        proposed = {field: replacement}
    # The frozen original page remains valid; only the proposal's copied row is forged.
    row['evidence'][0]['raw_value'].update(proposed)

    with pytest.raises(ValueError, match='proposed source snapshot row differs'):
        _archive_decision(tmp_path, work, row)
    assert record['id'] == 1057


def test_archive_decision_rejects_same_source_term_id_with_different_link(tmp_path):
    term = {
        'id': 1057, 'link': 'https://archive.example/category/eulenstein/',
        'name': 'Eulenstein',
    }
    work, row, _ = _archive_case(tmp_path, record=term)

    with pytest.raises(ValueError, match='not this native identity/title/URL'):
        _archive_decision(tmp_path, work, row)


def _local_case(tmp_path, evidence_url):
    url = 'https://scores.example/catalog/record-7/'
    title = 'Collection No. 7'
    work = {
        'id': 'boije:record-7', 'source_url': url, 'title_en': title,
        'category_ids': ['cat-1'], 'source_category_names': ['Guitar'],
        'metadata': {}, 'assets': [],
    }
    page = '<html><h1>Collection No. 7</h1></html>'
    body = page.encode()
    sha = hashlib.sha256(body).hexdigest()
    relative = tmp_path / 'sources/boije/record.html'
    relative.parent.mkdir(parents=True, exist_ok=True)
    relative.write_bytes(body)
    state = tmp_path / 'sources/boije/discovery_state.json'
    state.write_text(json.dumps({'requests': {url: {
        'status': 200, 'cache': 'record.html', 'sha256': sha}}}))
    row = {
        'source_id': 'boije', 'native_record_sha256': digest(work),
        'topic_id': 'guitar_unspecified', 'basis': 'reviewed_source_evidence',
        'instrumentation': '吉他相关，编制未细分', 'player_count': None,
        'note': '来源页标题可用于该条目。',
        'evidence': [{'kind': 'native_field', 'path': ['frozen_source_page', 'h1'],
            'source_url': evidence_url, 'page_sha256': sha, 'value': title}],
    }
    return work, row


def test_local_decision_accepts_heading_from_exact_native_source_url(tmp_path):
    url = 'https://scores.example/catalog/record-7/'
    work, row = _local_case(tmp_path, url)

    decision = _local_decision(tmp_path, work, {'cat-1': {'id': 'cat-1', 'name': 'Guitar'}}, row)

    assert decision['evidence'][0]['kind'] == 'source_snapshot'
    assert decision['evidence'][0]['observation'].endswith('Collection No. 7')


def test_local_decision_rejects_heading_from_another_source_url(tmp_path):
    work, row = _local_case(tmp_path, 'https://scores.example/catalog/other-record/')

    with pytest.raises(ValueError, match='source heading URL is not this native record URL'):
        _local_decision(tmp_path, work, {'cat-1': {'id': 'cat-1', 'name': 'Guitar'}}, row)


def test_public_comparison_rejects_review_id_outside_captured_baseline():
    before = {'categories': [], 'works': [{
        'id': 'example:1', 'source_id': 'example', 'category_ids': [],
        'details': {}, 'topic_ids': ['unspecified'],
        'topic_evidence': {'unspecified': 'no_exact_instrumentation_evidence'},
        'topic_category_ids': {'unspecified': []},
    }]}
    after = deepcopy(before)

    with pytest.raises(AuditFailure, match='formal classification decisions exceed the captured public scope'):
        compare_classified_public(before, after, {'example:2': {}})


def _public_pair(source_declaration_before, source_declaration_after, source_id='musescore'):
    identity = f'{source_id}:1'
    before = {'categories': [], 'works': [{
        'id': identity, 'source_id': source_id, 'category_ids': [],
        'details': {'source_instrumentation': source_declaration_before, 'license': 'CC0'},
        'topic_ids': ['unspecified'],
        'topic_evidence': {'unspecified': 'no_exact_instrumentation_evidence'},
        'topic_category_ids': {'unspecified': []},
    }]}
    after = deepcopy(before)
    after['works'][0]['details']['source_instrumentation'] = source_declaration_after
    return before, after, identity


def test_public_comparison_accepts_only_guarded_exact_musescore_placeholder_repair():
    from catalog_sources import MUSESCORE_SYNTHETIC_SOURCE_INSTRUMENTATION

    before, after, identity = _public_pair(
        MUSESCORE_SYNTHETIC_SOURCE_INSTRUMENTATION, 'Guitar；Piano')
    native = {identity: {'id': identity, 'metadata': {
        'instrumentation': MUSESCORE_SYNTHETIC_SOURCE_INSTRUMENTATION,
        'source_instruments': [{'name': 'Guitar', 'count': 1}, {'name': 'Piano', 'count': 1}],
    }}}

    result = compare_classified_public(before, after, {}, native)

    assert result['source_declaration_projection_repairs'] == 1
    assert result['changed_classifications_by_source'] == {}
    assert result['all_other_public_work_fields_exact']


def test_public_comparison_rejects_repair_without_matching_native_guard():
    from catalog_sources import MUSESCORE_SYNTHETIC_SOURCE_INSTRUMENTATION

    before, after, identity = _public_pair(
        MUSESCORE_SYNTHETIC_SOURCE_INSTRUMENTATION, 'Guitar；Piano')
    native = {identity: {'id': identity, 'metadata': {
        'instrumentation': 'Guitar',
        'source_instruments': [{'name': 'Guitar'}, {'name': 'Piano'}],
    }}}

    with pytest.raises(AuditFailure, match='unreviewed public field changed'):
        compare_classified_public(before, after, {}, native)
    with pytest.raises(AuditFailure, match='unreviewed public field changed'):
        compare_classified_public(before, after, {})


def test_public_comparison_rejects_nonplaceholder_source_declaration_change():
    before, after, identity = _public_pair('Guitar', 'Guitar；Piano')
    native = {identity: {'id': identity, 'metadata': {
        'instrumentation': 'Guitar',
        'source_instruments': [{'name': 'Guitar'}, {'name': 'Piano'}],
    }}}

    with pytest.raises(AuditFailure, match='unreviewed public field changed'):
        compare_classified_public(before, after, {}, native)


def test_added_source_declaration_projection_repairs_are_counted_and_guarded():
    from catalog_sources import MUSESCORE_SYNTHETIC_SOURCE_INSTRUMENTATION
    from verify_library_classification import compare_added_source_declarations

    identity = 'musescore:2'
    native = {identity: {'id': identity, 'metadata': {
        'instrumentation': MUSESCORE_SYNTHETIC_SOURCE_INSTRUMENTATION,
        'source_instruments': [{'name': 'Guitar'}, {'name': 'Piano'}],
    }}}
    public = {'works': [{'id': identity, 'source_id': 'musescore', 'details': {
        'source_instrumentation': 'Guitar；Piano'}}]}

    assert compare_added_source_declarations(public, {identity}, native) == 1
    public['works'][0]['details']['source_instrumentation'] = 'Guitar'
    with pytest.raises(AuditFailure, match='added MuseScore source declaration projection changed'):
        compare_added_source_declarations(public, {identity}, native)


def test_classification_compiler_receipt_preserves_literal_root_proposal_and_fallback_is_idempotent(tmp_path, monkeypatch):
    import gzip
    from catalog_classification import REVIEW_PATH, digest
    from review_library_classification import BASE, compile_review

    source = {'id': 'root', 'catalog': 'sources/root/catalog.json'}
    monkeypatch.setattr('catalog_sources.load_registry', lambda _root: [source])
    work = {
        'id': 'root:1', 'title_en': 'Fixture score', 'source_url': 'https://root.example/1',
        'category_ids': ['guitar'],
        'metadata': {'source_instruments': [{'name': 'Guitar', 'count': 1}]},
    }
    catalog = {'schema_version': 1, 'source_id': 'root',
        'categories': [{'id': 'guitar', 'name': 'Guitar'}], 'works': [work]}
    (tmp_path / 'sources/root').mkdir(parents=True)
    (tmp_path / 'sources/root/catalog.json').write_text(json.dumps(catalog, ensure_ascii=False))
    scope = {'formal_ids': ['root:1'], 'pending_musescore_ids': []}
    (tmp_path / BASE).mkdir(parents=True)
    (tmp_path / BASE / 'scope.json').write_text(json.dumps(scope))

    literal = 'Guitar'
    root_bundle = {
        'records': {'root:1': {'status': 'confirmed', 'remaining_gap': 'none'}},
        'entries': {'root:1': {
            'native_record_sha256': digest(work), 'topic_id': 'guitar_unspecified',
            'basis': 'reviewed_source_evidence', 'instrumentation': '吉他相关，编制未细分',
            'player_count': None, 'note': '来源原生器种字段明确列出吉他。',
            'evidence': [{'kind': 'native_field', 'path': ['metadata', 'source_instruments', 0, 'name'],
                          'value': literal}],
        }},
    }
    bundles = {
        'archive-source-proposals.json': {'proposals': []},
        'cglib-detail-proposals.json': {'proposals': []},
        'local-source-proposals.json': {'entries': []},
        'local-refinement-proposals.json': {'entries': []},
        'imslp-file-proposals.json': {'entries': []},
        'root-source-proposals.json': root_bundle,
    }
    for name, value in bundles.items():
        (tmp_path / BASE / name).write_text(json.dumps(value, ensure_ascii=False))
    musescore_bundle = {'formal_25_actual_file_review': []}
    musescore_path = tmp_path / 'sources/musescore/expansion/broad-review-proposals.json'
    musescore_path.parent.mkdir(parents=True)
    musescore_path.write_text(json.dumps(musescore_bundle))
    broad_path = tmp_path / 'metadata/instrumentation/musescore_broad_reviewed.json'
    broad_path.parent.mkdir(parents=True)
    broad_path.write_text(json.dumps({'entries': [], 'outcomes': []}))

    first_summary = compile_review(tmp_path)
    receipt_path = tmp_path / BASE / 'review.json.gz'
    first_receipt = json.loads(gzip.decompress(receipt_path.read_bytes()))
    production_path = tmp_path / REVIEW_PATH
    first_production_bytes = production_path.read_bytes()
    production = json.loads(first_production_bytes)

    assert first_receipt['original_proposals']['root'] == root_bundle
    proof = production['entries']['root:1']['evidence'][0]
    assert proof['value_sha256'] == digest(literal) and 'value' not in proof

    for name in [*bundles, 'sources/musescore/expansion/broad-review-proposals.json']:
        (tmp_path / BASE / name if not name.startswith('sources/') else tmp_path / name).unlink()

    second_summary = compile_review(tmp_path)
    second_receipt = json.loads(gzip.decompress(receipt_path.read_bytes()))

    assert second_summary == first_summary
    assert production_path.read_bytes() == first_production_bytes
    assert second_receipt['original_proposals']['root'] == root_bundle
    assert second_receipt['proposal_semantic_guards']['root'] == digest(root_bundle)
    assert second_receipt['production_review']['sha256'] == hashlib.sha256(first_production_bytes).hexdigest()
