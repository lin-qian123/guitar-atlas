import hashlib
import json
from copy import deepcopy

import pytest

from discover_open_sources import CachedClient, DiscoveryBlocked
from source_adapters import guitarschool, mutopia


MUTOPIA_LISTING = '''<table class="outer-table"><tr><td><table class="result-table">
<tr><td>Étude</td><td>by D. Aguado (1784–1849)</td><td>Op. 3 No. 1</td><td></td></tr>
<tr><td>for Guitar</td><td>1830</td><td>Romantic</td><td></td></tr>
<tr><td>Schott, plate 2674</td><td><a href="../legal.html">Creative Commons Attribution-ShareAlike 4.0</a></td><td><a href="piece-info.cgi?id=2041">More Information</a></td><td>2016/02/12</td></tr>
<tr><td><a href="/ftp/A/score.ly">.ly file</a></td><td><a href="/ftp/A/score.mid">.mid file</a></td><td><a href="/ftp/A/score-a4.pdf">A4 PDF</a></td><td><a href="/ftp/A/score-let.pdf">Letter PDF</a></td></tr>
</table></td></tr></table><a href="make-table.cgi?Instrument=Guitar&amp;startat=10">Next 10</a>'''


def school_directory(extra='', files=1):
    return f'''<div class="container mt-2"><h2>All</h2><h3><a>Traditional</a></h3>
    <ul><li><b><a href="/en/Download/4007">La Pastoreta</a></b><span> - Guitar quartet.</span><span>Score and parts.</span>{extra}</li></ul>
    <p>Authors: 1 • Pages: 9 • Files: {files}</p></div>'''


def school_detail(price='Free download', license=True, category='Quartets'):
    rel = '<a rel="license" href="http://creativecommons.org/licenses/by-nc/4.0/">Free download</a>' if license else price
    return f'''<div class="container mt-2"><h1><a href="/en/{category}">{category}</a></h1><h2><a>Traditional</a></h2><h3>La Pastoreta</h3>
    <ul class="list-unstyled"><li>🔢 <strong>For</strong>: Guitar quartet</li>
    <li>✍️ <strong>Arrangement:</strong><a>Eythor Thorlaksson</a></li>
    <li>ℹ️ <strong>Information:</strong>Score and parts.</li>
    <li>🎖️ <strong>Grade:</strong><a>2</a>, <a>3</a></li>
    <li>🎼 <strong>ISBN:</strong>978-9935-446-84-8</li><li><strong>Pages:</strong>9</li>
    <li><strong>Price:</strong>{rel}</li></ul><a href="/en/Files/4007.pdf">Download</a></div>'''


def test_mutopia_native_identity_formats_and_exact_original_name():
    rows, next_url = mutopia.parse_listing(MUTOPIA_LISTING)
    assert len(rows) == 1 and rows[0]['id'] == 'mutopia:2041'
    assert rows[0]['title_en'] == 'Étude'
    assert rows[0]['composer_en'] == 'D. Aguado'
    assert rows[0]['metadata']['composer_attribution'] == 'D. Aguado (1784–1849)'
    assert rows[0]['formats'] == ['LILYPOND', 'MIDI', 'PDF']
    assert next_url.endswith('make-table.cgi?Instrument=Guitar&startat=10')
    assert [a['paper_size'] for a in rows[0]['assets'] if a['format'] == 'PDF'] == ['A4', 'Letter']
    assert all(a['upstream_checksum_status'] == 'not_supplied' for a in rows[0]['assets'])


def test_mutopia_zipped_pdf_is_an_asset_container_not_a_fake_pdf_filename():
    rows, _ = mutopia.parse_listing(MUTOPIA_LISTING.replace('score-a4.pdf', 'score-a4-pdfs.zip'))
    asset = next(a for a in rows[0]['assets'] if a['filename'].endswith('.zip'))
    assert asset['format'] == 'PDF' and asset['container'] == 'ZIP'


@pytest.mark.parametrize('instrumentation', ['Voice, Guitar', "Flute, and 'Cello or Guitar"])
def test_mutopia_explicit_voice_and_alternative_scope_excluded(instrumentation):
    row = mutopia.parse_listing(MUTOPIA_LISTING)[0][0]
    row['metadata']['instrumentation'] = instrumentation
    assert mutopia.apply_scope(row) == 'excluded'


@pytest.mark.parametrize('instrumentation', ['Lute, Guitar', 'Lute, Guitar, Vihuela', 'Guitar and bass', ''])
def test_ambiguous_or_unapproved_mutopia_instrumentation_stays_visible_but_not_acquirable(instrumentation):
    row = mutopia.parse_listing(MUTOPIA_LISTING)[0][0]
    row['metadata']['instrumentation'] = instrumentation
    assert mutopia.apply_scope(row) == 'pending_review'
    assert row['instrumentation_status'] == 'unverified'
    assert all(a['status'] == 'restricted' for a in row['assets'] if a['format'] == 'PDF')


def test_school_directory_retains_unpaid_and_paid_records_and_original_text():
    rows, summary = guitarschool.parse_directory(school_directory('<strong class="text-muted">$4.99</strong>'))
    assert rows[0]['id'] == 'guitarschool:4007'
    assert rows[0]['metadata']['directory_price'] == '$4.99'
    assert rows[0]['metadata']['instrumentation'] == 'Guitar quartet'
    assert rows[0]['formats'] == [] and rows[0]['assets'] == []
    assert summary['declared_file_records'] == 1


def test_school_directory_count_disagreement_is_not_reported_as_complete():
    with pytest.raises(ValueError, match='count disagrees'):
        guitarschool.parse_directory(school_directory(files=2))


def test_school_confirmed_free_license_retains_parts_grade_isbn_arranger():
    record = guitarschool.parse_directory(school_directory())[0][0]
    guitarschool.parse_detail(school_detail(), record)
    assert record['metadata']['license'] == 'CC BY-NC 4.0'
    assert record['metadata']['arranger'] == 'Eythor Thorlaksson'
    assert record['metadata']['grades'] == ['2', '3']
    assert record['metadata']['source_pages'] == 9
    assert record['metadata']['information'] == 'Score and parts.'
    assert record['metadata']['isbn'] == '978-9935-446-84-8'
    assert record['assets'][0]['status'] == 'pending'
    assert record['category_ids'] == ['all', 'quartets']


@pytest.mark.parametrize('price,expected', [('Free download', 'unknown'), ('$1.99', 'restricted')])
def test_school_free_without_license_and_paid_pdf_remain_restricted(price, expected):
    record = guitarschool.parse_directory(school_directory())[0][0]
    guitarschool.parse_detail(school_detail(price, license=False), record)
    assert record['metadata']['acquisition_status'] == expected
    assert record['assets'][0]['status'] == 'restricted'
    assert record['metadata']['original_arrangement_status'] == 'arrangement'


@pytest.mark.parametrize('category', ['Theory', 'Catalogues'])
def test_school_reference_material_is_not_counted_as_scores(category):
    record = guitarschool.parse_directory(school_directory())[0][0]
    guitarschool.parse_detail(school_detail(category=category), record)
    assert record['resource_type'] == 'reference'


def test_school_source_title_change_is_rejected_instead_of_relabeling_translation_identity():
    record = guitarschool.parse_directory(school_directory())[0][0]
    with pytest.raises(ValueError, match='title changed'):
        guitarschool.parse_detail(school_detail().replace('<h3>La Pastoreta</h3>', '<h3>Another edition</h3>'), record)


def test_metadata_cache_integrity_is_checked_and_verified_asset_receipts_survive_rebuild(tmp_path):
    client = CachedClient(tmp_path, 'mutopia', mutopia.REQUEST_HOSTS)
    url = 'https://www.mutopiaproject.org/a'
    raw = b'<html>Frozen</html>'
    path = client.root / 'snapshots/pages' / (hashlib.sha256(url.encode()).hexdigest() + '.html')
    path.parent.mkdir(parents=True)
    path.write_bytes(raw)
    client.receipts[url] = {'status_code': 200, 'sha256': hashlib.sha256(raw).hexdigest()}
    assert client.get(url) == raw.decode()
    path.write_bytes(b'<html>changed</html>')
    with pytest.raises(ValueError, match='integrity mismatch'):
        client.get(url)
    catalog = {'works': [{'id': 'mutopia:1', 'assets': [{'source_url': url, 'status': 'verified', 'sha256': 'a' * 64}]}]}
    client.save_catalog(catalog)
    rebuilt = deepcopy(catalog)
    rebuilt['works'][0]['assets'][0] = {'source_url': url, 'status': 'pending'}
    client.save_catalog(rebuilt)
    saved = json.loads((client.root / 'catalog.json').read_text())
    assert saved['works'][0]['assets'][0]['status'] == 'verified'
    assert saved['works'][0]['assets'][0]['sha256'] == 'a' * 64


def test_metadata_requests_cannot_escape_the_approved_host(tmp_path):
    client = CachedClient(tmp_path, 'mutopia', mutopia.REQUEST_HOSTS)
    with pytest.raises(ValueError, match='unapproved metadata'):
        client.get('https://outside.example/record')
