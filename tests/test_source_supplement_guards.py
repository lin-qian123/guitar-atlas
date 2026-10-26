import copy
import json

import pytest

from discover_supplement_sources import register
from catalog_unification import instrumentation_topic
from verify_source_supplement import preserved_records


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


@pytest.fixture
def source(tmp_path):
    old = {'id': 'imslp', 'name': 'IMSLP', 'homepage': 'https://imslp.org/',
           'allowed_hosts': ['imslp.org'], 'adapter': 'imslp_categories'}
    write(tmp_path/'config/sources.json', {'schema_version': 1, 'version': 'old', 'sources': [old]})
    proposal = {'id': 'example', 'name': 'Example', 'homepage': 'https://example.org/',
                'allowed_hosts': ['example.org'], 'adapter': 'normalized_catalog',
                'catalog': 'sources/example/catalog.json', 'family': 'example',
                'family_name_zh': '示例', 'family_name_en': 'Example',
                'page_url_rules': [{'path': '/records/[0-9]+', 'query': {}, 'human_page': True}]}
    native = {'schema_version': 1, 'source_id': 'example', 'categories': [
        {'id': 'guitar', 'name': 'Guitar', 'source_url': 'https://example.org/records/1'}],
        'works': [{'id': 'example:1', 'title_en': 'A piece', 'composer_en': '',
                   'source_url': 'https://example.org/records/1', 'category_ids': ['guitar']}]}
    write(tmp_path/'sources/example/catalog.json', native)
    return tmp_path, old, proposal, native


def test_register_appends_and_never_rewrites_existing_source(source):
    root, old, proposal, _ = source
    assert register(root, [proposal])['appended_sources'] == ['example']
    before = (root/'config/sources.json').read_bytes()
    assert register(root, [proposal])['appended_sources'] == []
    assert (root/'config/sources.json').read_bytes() == before
    changed = {**proposal, 'allowed_hosts': ['unapproved.example']}
    with pytest.raises(ValueError, match='rewrite'):
        register(root, [changed])
    assert (root/'config/sources.json').read_bytes() == before
    assert json.loads(before)['sources'][0] == old


@pytest.mark.parametrize('mutation', ['duplicate', 'orphan', 'download'])
def test_invalid_catalog_cannot_mutate_registry(source, mutation):
    root, _, proposal, native = source
    before = (root/'config/sources.json').read_bytes()
    if mutation == 'duplicate':
        native['works'].append(copy.deepcopy(native['works'][0]))
    elif mutation == 'orphan':
        native['works'][0]['category_ids'] = ['missing']
    else:
        native['works'][0]['source_url'] = 'https://example.org/scores/one.pdf'
    write(root/'sources/example/catalog.json', native)
    with pytest.raises(ValueError):
        register(root, [proposal])
    assert (root/'config/sources.json').read_bytes() == before


def test_preservation_requires_complete_old_offline_file_mapping():
    original = [{'id': 'old:1', 'title_en': 'Original', 'local_editions': [
        {'files': [{'label': 'Full score', 'href': 'scores/old.pdf'}]}]}]
    assert preserved_records(original, original + [{'id': 'new:1'}], 'offline') == 1
    altered = copy.deepcopy(original)
    altered[0]['local_editions'][0]['files'][0]['href'] = 'scores/other.pdf'
    with pytest.raises(ValueError, match='previously published fields changed'):
        preserved_records(original, altered, 'offline')
    with pytest.raises(ValueError, match='duplicate'):
        preserved_records(original, original * 2, 'offline')


def test_collective_string_declaration_stays_exact_and_does_not_count_players():
    assert instrumentation_topic('guitar and strings') == 'strings'
    assert instrumentation_topic('guitar and strings, voice') is None
    assert instrumentation_topic('guitar and strings or piano') is None
    assert instrumentation_topic('Classical guitar') == 'guitar_unspecified'


def test_preservation_protects_legacy_category_navigation():
    original = [{'id': 2, 'name': 'For 2 guitars', 'local_href': 'For%202%20guitars/index.html'}]
    altered = [{'id': 2, 'name': 'For 2 guitars'}]
    with pytest.raises(ValueError, match='previously published fields changed'):
        preserved_records(original, altered, 'offline category navigation')


def test_score_note_evidence_changes_invalidate_offline_fingerprint(tmp_path):
    from render_offline_site import offline_input_fingerprint
    write(tmp_path/'config/categories.json', {'schema_version': 1, 'categories': []})
    write(tmp_path/'config/mixed_categories.json', {'schema_version': 1, 'categories': []})
    write(tmp_path/'config/score_exclusions.json', {'schema_version': 1, 'entries': []})
    write(tmp_path/'config/sources.json', {'schema_version': 1, 'sources': [{
        'id': 'imslp', 'name': 'IMSLP', 'homepage': 'https://imslp.org/',
        'allowed_hosts': ['imslp.org'], 'adapter': 'imslp_categories'}]})
    before = offline_input_fingerprint(tmp_path)
    packet = tmp_path/'sources/source-expansion/csun-score-samples.json'
    write(packet, {'sample': 'first printed-page observation'})
    observed = offline_input_fingerprint(tmp_path)
    assert observed != before
    write(packet, {'sample': 'different observation'})
    assert offline_input_fingerprint(tmp_path) != observed
    packet.unlink()
    assert offline_input_fingerprint(tmp_path) == before


def test_verified_new_manifest_cannot_silently_lose_its_offline_control():
    from verify_source_supplement import verify_new_file_controls
    native = [{'id': 'new:one', 'assets': [
        {'format': 'PDF', 'status': 'verified', 'local_path': 'sources/new/score a.pdf'}]},
        {'id': 'new:restricted', 'assets': [{'format': 'PDF', 'status': 'restricted'}]}]
    offline = {'new:one': {'local_editions': [{'files': [
        {'href': 'sources/new/score%20a.pdf'}]}]}, 'new:restricted': {'local_editions': []}}
    assert verify_new_file_controls(native, offline) == {
        'records': 2, 'pdf_controls': 1, 'local_records': 1}
    offline['new:one']['local_editions'] = []
    with pytest.raises(ValueError, match='controls differ'):
        verify_new_file_controls(native, offline)
    offline['new:one']['local_editions'] = [{'files': [{'href': 'sources/new/wrong.pdf'}]}]
    with pytest.raises(ValueError, match='controls differ'):
        verify_new_file_controls(native, offline)
