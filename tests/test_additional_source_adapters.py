from __future__ import annotations
import json
from pathlib import Path
from unittest.mock import Mock
import pytest
from bs4 import BeautifulSoup
from source_adapters.additional import (
    DiscoveryClient, category, parse_classicalguitarorg, parse_delcamp_page,
    guitardownunder_record_id, parse_freeguitarmusic, parse_werner, robots_allows, save_catalog, werner_attribution, work,
)


def test_robots_wildcard_query_denies_pagination_and_sru():
    rules = 'User-agent: *\nDisallow: /*page=2*\nDisallow: /*?\nAllow: /music/\n'
    assert robots_allows(rules, 'GuitarAtlas/1.0', 'https://example.org/music/123/')
    assert not robots_allows(rules, 'GuitarAtlas/1.0', 'https://example.org/search?page=2')
    assert not robots_allows(rules, 'GuitarAtlas/1.0', 'https://example.org/SRU?query=guitar')


def test_specific_robot_group_and_longest_rule_override():
    rules = 'User-agent: *\nDisallow: /\nUser-agent: GuitarAtlas\nDisallow: /private/\nAllow: /private/catalog$\n'
    assert robots_allows(rules, 'GuitarAtlas/1.0', 'https://example.org/public/')
    assert robots_allows(rules, 'GuitarAtlas/1.0', 'https://example.org/private/catalog')
    assert not robots_allows(rules, 'GuitarAtlas/1.0', 'https://example.org/private/catalog/child')
    empty_allow = 'User-agent: GuitarAtlas\nDisallow:\nUser-agent: *\nDisallow: /\n'
    assert robots_allows(empty_allow, 'GuitarAtlas/1.0', 'https://example.org/catalog')


def test_delcamp_collection_and_part_share_edition_identity_without_expanding_count():
    soup = BeautifulSoup('''<div class="single-entry-summary"><p>
       <a href="https://site.test/apdfsdelcamp/collection.pdf">Francisco Tárrega : Complete Guitar Works, 101 original compositions</a>
       This collection contains 101 pieces. Content:<strong>Francisco Tárrega</strong>:
       <a href="https://site.test/apdfsdelcamp/lagrima.pdf">Lágrima</a>
       <a href="https://site.test/apdfsdelcamp/lagrima.pdf">Lágrima - tab</a></p></div>''', 'html.parser')
    works = parse_delcamp_page(soup, 'https://site.test/tarrega/', 'tarrega')
    assert len(works) == 2
    collection = next(row for row in works if row['metadata']['native_record_locator'].endswith('collection.pdf'))
    assert collection['id'].startswith('delcamp:pdf:')
    assert len(collection['id'].split(':')[-1]) == 64
    assert collection['metadata']['record_level'] == 'collection'
    assert collection['metadata']['contained_piece_count'] == 101
    assert collection['composer_en'] == 'Francisco Tárrega'
    edition = next(row for row in works if row['metadata']['native_record_locator'].endswith('lagrima.pdf'))
    assert edition['composer_en'] == 'Francisco Tárrega'
    assert edition['metadata']['record_level'] == 'edition'
    assert edition['assets'][0]['status'] == 'pending'
    assert edition['assets'][0]['upstream_checksum_available'] is False
    assert edition['source_url'] == 'https://site.test/tarrega/'
    assert 'editor' not in edition['metadata']
    assert edition['metadata']['catalog_compiler'] == 'Jean-François Delcamp'


def test_score_subscription_and_reference_remain_distinct():
    soup = BeautifulSoup('''<div class="singular-entry"><h2>Classical Guitar eBooks</h2>
      <a class="free-ebook" id="ebook-everynote" href="/private/notes.pdf">Learn Every Note</a>
      <h2>Free Sheet Music</h2><h4>Mauro Giuliani</h4>
      <a class="free-music" id="music-giuliani-op45" href="/scores/op45.pdf">Six Variations</a></div>''', 'html.parser')
    cats, works = parse_classicalguitarorg(soup, 'https://www.classicalguitar.org/free/')
    assert len(cats) == 2
    assert works[0]['resource_type'] == 'reference'
    assert works[0]['metadata']['requires_email_subscription'] is True
    assert works[0]['composer_en'] == ''
    assert works[0]['assets'][0]['status'] == 'restricted'
    assert works[1]['composer_en'] == 'Mauro Giuliani'
    assert works[1]['source_url'].endswith('/free/')


def test_arranger_is_not_invented_as_composer_from_freeguitarmusic_link():
    soup = BeautifulSoup('''<a href="https://drive.google.com/file/d/native-A/view">"Greensleeves" - Arranged by Isaac Gish</a>
      <iframe data-src="https://drive.google.com/file/d/native-A/preview" aria-label="Drive, Greensleeves - Score.pdf"></iframe>
      <iframe data-src="https://drive.google.com/file/d/native-B/preview" aria-label="Drive, Yesterday - Score.pdf"></iframe>''', 'html.parser')
    _, works = parse_freeguitarmusic(soup, 'https://www.freeguitarmusic.net/fingerstyle/modern-and-classical-solos')
    assert len(works) == 2
    assert works[0]['composer_en'] == ''
    assert works[0]['metadata']['arranger'] == 'Isaac Gish'
    assert works[0]['title_en'] == 'Greensleeves'
    assert works[1]['title_en'] == 'Yesterday - Score.pdf'
    assert works[1]['formats'] == ['PDF']
    assert works[1]['assets'][0]['status'] == 'restricted'


@pytest.mark.parametrize('context,composer,difficulty', [
    ('Piece by Gaspar Sanz , Grade 5', 'Gaspar Sanz', 'Grade 5'),
    ('Piece by Sagreras , Grade 4, Free Sheet Music , Free Tab', 'Sagreras', 'Grade 4'),
    ('Collection by Carcassi , Classical, Grades 5-9', 'Carcassi', 'Grades 5-9'),
    ('Piece by Carcassi , Late-Beginer, Free', 'Carcassi', 'Late-Beginer'),
    ('Duet by Satie , Duet for 2 Guitars, Intermediate', 'Satie', 'Intermediate'),
    ('Piece by Beethoven for Easy Guitar', 'Beethoven', None),
    ('Piece by Bach & Stölzel , Grade 6', 'Bach & Stölzel', 'Grade 6'),
    ('Piece by Bach/Petzold , Grade 4', 'Bach/Petzold', 'Grade 4'),
    ('Piece by Tielman Susato . 4 parts', 'Tielman Susato', None),
    ('Variations on a Theme by Handel Op.107 by Giuliani , Grade 9', 'Giuliani', 'Grade 9'),
    ('Piece by Sor, Fernando , Grade 5', 'Sor, Fernando', 'Grade 5'),
    ('Piece by José Ferrer , Grade 4', 'José Ferrer', 'Grade 4'),
    ('Piece with no source attribution, Grade 1', '', 'Grade 1'),
])
def test_werner_directory_labels_do_not_pollute_composer_names(context, composer, difficulty):
    actual, metadata = werner_attribution(context)
    assert actual == composer
    assert metadata['difficulty'] == difficulty
    assert metadata['directory_label'] == metadata['original_context'] == context
    assert metadata['original_composer_attribution'] == (composer or None)
    assert metadata['original_attribution_absent'] is (not bool(composer))


def test_werner_preserves_raw_combined_label_and_explicit_arranger_separately():
    soup = BeautifulSoup('''<div class="entry-content"><h2>Sheet Music &amp; Collections with Videos</h2>
      <ul><li><a href="/test-edition/">Piece by Mozart</a>, arr. Pratten , Grade 4-5, Free Sheet Music</li></ul></div>''', 'html.parser')
    _, works = parse_werner(soup, 'https://www.thisisclassicalguitar.com/sheet-music-for-classical-guitar/')
    record = works[0]
    assert record['id'] == 'werner:test-edition'
    assert record['title_en'] == 'Piece by Mozart'
    assert record['source_url'] == 'https://www.thisisclassicalguitar.com/test-edition/'
    assert record['composer_en'] == 'Mozart'
    assert record['metadata']['arranger'] == 'Pratten'
    assert record['metadata']['original_arrangement_status'] == 'arrangement'
    assert record['metadata']['source_attribution_combined_label'] == 'Mozart , arr. Pratten , Grade 4-5, Free Sheet Music'
    assert record['metadata']['directory_label'] == 'Piece by Mozart , arr. Pratten , Grade 4-5, Free Sheet Music'
    assert 'editor' not in record['metadata']
    assert record['metadata']['catalog_compiler'] == 'Bradford Werner'


@pytest.mark.parametrize('context,composer', [
    ('Piece by Sor, edited by Bradford Werner , Grade 5', 'Sor'),
    ('Piece edited by Bradford Werner , Grade 5', ''),
])
def test_werner_explicit_editor_requires_evidence_and_never_replaces_composer(context, composer):
    actual, metadata = werner_attribution(context)
    assert actual == composer
    assert metadata['editor'] == 'Bradford Werner'
    assert metadata['editor_evidence'] == 'edited by Bradford Werner '


def test_guitardownunder_file_identity_is_opaque_but_native_page_identity_remains_stable():
    import hashlib
    native = 'kiselev_etude2.pdf'
    assert guitardownunder_record_id(native) == 'pdf:' + hashlib.sha256(native.encode('utf-8')).hexdigest()
    assert guitardownunder_record_id('bach/etude.html') == 'bach/etude.html'


def test_human_verification_cannot_become_valid_resumable_cache(tmp_path):
    client = DiscoveryClient(tmp_path, 'test', {'site.test'}, delay=0)
    client.robots['https://site.test'] = (404, '')
    response = Mock(status_code=200, url='https://site.test/catalog', headers={}, content=b'verify you are human', text='verify you are human')
    client._raw = Mock(return_value=response)
    with pytest.raises(PermissionError, match='human verification required'):
        client.get('https://site.test/catalog')
    resumed = DiscoveryClient(tmp_path, 'test', {'site.test'}, delay=0)
    resumed.robots['https://site.test'] = (404, '')
    with pytest.raises(PermissionError, match='remains pending'):
        resumed.get('https://site.test/catalog')


def test_catalog_counts_memberships_separately_from_files(tmp_path):
    client = DiscoveryClient(tmp_path, 'test', {'site.test'}, delay=0)
    cats = [category('a', 'Solo', 'https://site.test/a/'), category('b', 'Etudes', 'https://site.test/b/')]
    record = work('test', '42', 'Etude', '', 'https://site.test/42/', ['a', 'b'])
    report = save_catalog(client, 'Test', 'https://site.test/', cats, [record], 'Frozen selected directories')
    assert report['source_record_count'] == 1
    assert report['category_membership_count'] == 2
    assert report['verified_pdf_count'] == report['unique_physical_pdf_count'] == 0
    snapshot = json.loads((tmp_path / 'sources/test/catalog.json').read_text())['snapshot']
    assert snapshot['fresh_file_integrity_verification'] is False
    assert snapshot['fresh_instrumentation_verification'] is False


def test_conflicting_native_identity_fails_instead_of_title_merging(tmp_path):
    client = DiscoveryClient(tmp_path, 'test', {'site.test'}, delay=0)
    cats = [category('a', 'Solo', 'https://site.test/a/')]
    records = [work('test', '42', 'Etude', 'Composer A', 'https://site.test/42/', ['a']),
               work('test', '42', 'Etude', 'Composer B', 'https://site.test/42/', ['a'])]
    with pytest.raises(ValueError, match='duplicate native source identity'):
        save_catalog(client, 'Test', 'https://site.test/', cats, records, 'Frozen selected directories')


def test_rediscovery_preserves_receipt_by_record_and_exact_asset_url(tmp_path):
    from source_adapters.additional import atomic_json, restore_asset_receipts, delcamp_record_id
    old = work('delcamp', 'apdfsdelcamp/example.pdf', 'Old source title', '', 'https://site.test/catalog/', ['a'],
               assets=[{'source_url': 'https://site.test/example.pdf', 'format': 'PDF', 'status': 'verified',
                        'local_path': 'sources/delcamp/objects/example.pdf', 'sha256': 'abcd', 'size': 42, 'attempts': 2}])
    path = tmp_path / 'catalog.json'
    atomic_json(path, {'works': [old]})
    fresh = work('delcamp', delcamp_record_id('apdfsdelcamp/example.pdf'), 'Fresh source title', '', 'https://site.test/catalog/', ['a'],
                 assets=[{'source_url': 'https://site.test/example.pdf', 'format': 'PDF', 'status': 'pending'}],
                 metadata={'native_record_locator': 'apdfsdelcamp/example.pdf'})
    restore_asset_receipts(path, [fresh])
    assert fresh['title_en'] == 'Fresh source title'
    assert fresh['assets'][0]['status'] == 'verified'
    assert fresh['assets'][0]['size'] == 42
    assert fresh['assets'][0]['attempts'] == 2
