import io
from pathlib import Path

import pytest
from pypdf import PdfWriter

from classclef_library.pipeline import (
    canonical_url, make_catalog, parse_page, title_composer, validate_pdf,
)


def item(content, title='A: Classical Guitar Tabs, PDF, MIDI', ident=1, link='https://www.classclef.com/'):
    return {'id': ident, 'link': link, 'title': {'rendered': title}, 'content': {'rendered': content}}


def test_canonical_url_preserves_filename_case_and_escaping():
    assert canonical_url('http://classclef.com/pdf/A Piece%20(2).pdf#page=1') == 'https://www.classclef.com/pdf/A%20Piece%20(2).pdf'
    with pytest.raises(ValueError):
        canonical_url('https://outside.example/x.pdf')


def test_directory_retains_composer_and_tab_note_pair_without_guessing_instrumentation():
    rows = parse_page(item('''<p><strong>Abreu, Zequinha</strong> (1880-1935)<br>
        Tico Tico <a href="/pdf/tico.pdf">TAB</a> | <a href="/source/tico.pdf">NOTE</a>
        | <a href="tico-info/">INFO</a><br>
        Second <a href="/pdf/second.pdf">PDF</a></p>'''), 'pages')
    assert len(rows) == 2
    assert rows[0]['title_en'] == 'Tico Tico'
    assert rows[0]['composer_en'] == 'Abreu, Zequinha'
    assert rows[1]['composer_en'] == 'Abreu, Zequinha'
    assert rows[0]['source_url'] == 'https://www.classclef.com/tico-info/'
    assert [a['label'] for a in rows[0]['assets']] == ['TAB', 'NOTE']


def test_post_image_links_and_dedup_preserve_each_source_and_category():
    page = parse_page(item('<p>A work <a href="/pdf/a.pdf">PDF</a></p>'), 'pages')
    post = parse_page(item('<a href="/pdf/a.pdf"><img src="/img/downloadPdf_tab.gif"></a><a href="/source/a.pdf"><img src="/img/downloadPdf_note.gif"></a>',
                           title='A work by Exact Composer (Guitar Tab)', ident=2, link='https://www.classclef.com/a/'), 'posts')
    catalog = make_catalog(page + post, [], {'discovery_complete': True})
    assert len(catalog['works']) == 1
    work = catalog['works'][0]
    assert work['composer_en'] == 'Exact Composer'
    assert work['category_ids'] == ['page:1']
    assert work['instrumentation_status'] == 'unverified'
    assert len(work['assets']) == 2
    assert len(work['assets'][0]['source_pages']) == 2


def test_same_title_is_never_a_reason_to_merge_distinct_scores():
    records = parse_page(item('<p>Minuet <a href="/pdf/one.pdf">PDF</a><br>Minuet <a href="/pdf/two.pdf">PDF</a></p>'), 'pages')
    catalog = make_catalog(records, [], {})
    assert len(catalog['works']) == 2
    assert all(w['composer_en'] == '' for w in catalog['works'])
    assert len({w['id'] for w in catalog['works']}) == 2


def test_pdf_validation_rejects_html_partial_size_mismatch_and_zero_pages():
    writer = PdfWriter()
    stream = io.BytesIO()
    writer.add_blank_page(100, 100)
    writer.write(stream)
    data = stream.getvalue()
    result = validate_pdf(data, len(data))
    assert result['pages'] == 1
    assert len(result['sha1']) == 40 and len(result['sha256']) == 64
    for bad in [b'<html>captcha</html>', data[:-20]]:
        with pytest.raises(ValueError):
            validate_pdf(bad)
    with pytest.raises(ValueError):
        validate_pdf(data, len(data) + 1)
    empty = io.BytesIO()
    PdfWriter().write(empty)
    with pytest.raises(ValueError, match='no pages'):
        validate_pdf(empty.getvalue())


def test_source_title_and_author_preserved():
    assert title_composer('Lágrima by Francisco Tárrega (Classical Guitar Tab)') == ('Lágrima', 'Francisco Tárrega')
    assert title_composer('Traditional tune') == ('Traditional tune', '')


def test_malformed_br_does_not_hide_scores():
    rows = parse_page(item('<p>One <a href="/pdf/one.pdf">PDF</a><br>Two <a href="/pdf/two.pdf">PDF</a></br></p>'), 'pages')
    assert {a['source_url'] for row in rows for a in row['assets']} == {'https://www.classclef.com/pdf/one.pdf', 'https://www.classclef.com/pdf/two.pdf'}


def test_shared_wrong_source_link_cannot_merge_two_rows_on_same_directory():
    rows = parse_page(item('<p>Peasant Costume <a href="/pdf/a.pdf">PDF</a><a href="piece/">INFO</a><br>Standing Still <a href="/pdf/a.pdf">PDF</a><a href="piece/">INFO</a></p>'), 'pages')
    rows += parse_page(item('<a href="/pdf/a.pdf">PDF</a>', title='Peasant Costume by Bartok (Guitar Tab)', ident=2, link='https://www.classclef.com/piece/'), 'posts')
    catalog = make_catalog(rows, [], {})
    assert len(catalog['works']) == 2
    assert any(w['title_en'] == 'Standing Still' for w in catalog['works'])


def test_companion_button_mistyped_pdf_extension_is_not_a_score():
    rows = parse_page(item('<a href="/gpx/a.pdf"><img src="/img/downloadGpx.gif"></a><a href="/pdf/a.pdf">PDF</a>', title='A by Person'), 'posts')
    companion = next(a for a in rows[0]['assets'] if '/gpx/' in a['source_url'])
    assert companion['format'] == 'GPX'
    assert companion['status'] == 'metadata_only'
    assert companion['url_extension_mismatch']


def test_by_inside_title_or_arrangement_credit_preserves_composer():
    assert title_composer('Always by Your Side by Ralph Towner (Guitar Tab)') == ('Always by Your Side', 'Ralph Towner')
    assert title_composer('BWV 1007 (Arranged by Julian Bream) by J.S.Bach') == ('BWV 1007 (Arranged by Julian Bream)', 'J.S.Bach')
    assert title_composer('Manha De Carnaval 1970 by Luiz Bonfa-Arranged by Baden Powell') == ('Manha De Carnaval 1970', 'Luiz Bonfa')


def test_zip_only_scores_are_indexed_and_archive_paths_never_extracted():
    import zipfile
    from classclef_library.pipeline import zip_pdf_members
    rows = parse_page(item('<p>Duet <a href="/pdf/duet.zip">PDF</a></p>'), 'pages')
    assert rows[0]['assets'][0]['container'] == 'ZIP'
    writer = PdfWriter()
    writer.add_blank_page(100, 100)
    pdf = io.BytesIO()
    writer.write(pdf)
    package = io.BytesIO()
    with zipfile.ZipFile(package, 'w') as archive:
        archive.writestr('scores/Part I.pdf', pdf.getvalue())
        archive.writestr('scores/Part II.pdf', pdf.getvalue())
        archive.writestr('readme.txt', 'Attribution')
    members, ignored = zip_pdf_members(package.getvalue())
    assert [m[0] for m in members] == ['scores/Part I.pdf', 'scores/Part II.pdf']
    assert ignored == ['readme.txt']
    hostile = io.BytesIO()
    with zipfile.ZipFile(hostile, 'w') as archive:
        archive.writestr('../outside.pdf', pdf.getvalue())
    with pytest.raises(ValueError, match='unsafe'):
        zip_pdf_members(hostile.getvalue())


def test_cached_snapshot_tampering_is_detected(tmp_path):
    import json
    from classclef_library.pipeline import cache_request
    (tmp_path / 'item.json').write_text(json.dumps({'url': 'https://www.classclef.com/', 'body': 'changed', 'sha256': '0' * 64}))
    with pytest.raises(ValueError, match='SHA-256'):
        cache_request(None, tmp_path, 'item', 'https://www.classclef.com/')


def test_pdf_link_evidence_wins_over_inconsistent_companion_icon_for_same_url():
    rows = parse_page(item('<p>Jerusalem <a href="/pdf/a.pdf">PDF</a><a href="jerusalem/">INFO</a></p>'), 'pages')
    rows += parse_page(item('<a href="/pdf/a.pdf"><img src="/img/downloadGpx.gif"></a><a href="/pdf/a.pdf">PDF</a>', title='Jerusalem by Parry', ident=2, link='https://www.classclef.com/jerusalem/'), 'posts')
    catalog = make_catalog(rows, [], {})
    asset = next(a for w in catalog['works'] for a in w['assets'] if a['source_url'].endswith('/a.pdf'))
    assert asset['format'] == 'PDF'
    assert asset['declared_formats'] == ['GPX', 'PDF']


def test_failed_fresh_verification_downgrades_catalog_and_resume_state(tmp_path):
    import hashlib
    import json
    from classclef_library.pipeline import atomic_json, verify
    body = b'%PDF-truncated'
    digest = hashlib.sha256(body).hexdigest()
    base = tmp_path / 'sources/classclef'
    path = base / 'objects' / digest[:2] / (digest + '.pdf')
    path.parent.mkdir(parents=True)
    path.write_bytes(body)
    asset = {'format': 'PDF', 'source_url': 'https://www.classclef.com/pdf/a.pdf', 'status': 'verified', 'local_path': path.relative_to(tmp_path).as_posix(), 'sha256': digest, 'sha1': hashlib.sha1(body).hexdigest(), 'size': len(body), 'pages': 1}
    catalog = {'works': [{'id': 'classclef:test', 'instrumentation_status': 'unverified', 'category_ids': [], 'formats': ['PDF'], 'source_records': [], 'assets': [asset]}], 'categories': [], 'snapshot': {'id': 'test', 'discovery_complete': True}}
    atomic_json(base / 'catalog.json', catalog)
    report = verify(tmp_path)
    assert not report['structural_valid']
    assert json.loads((base / 'catalog.json').read_text())['works'][0]['assets'][0]['status'] == 'invalid_pdf'
    assert json.loads((base / 'download-state.json').read_text())[asset['source_url']]['status'] == 'invalid_pdf'


def test_guitarpro_only_score_is_preserved_as_metadata_without_a_pdf():
    rows = parse_page(item('<a href="/gpx/solo.gpx">GPX</a><a href="/midi/solo.mid">MIDI</a>', title='Solo by Person', ident=9), 'posts')
    catalog = make_catalog(rows, [], {})
    assert len(catalog['works']) == 1
    assert catalog['works'][0]['formats'] == ['GPX', 'MIDI']
    assert all(a['status'] == 'metadata_only' for a in catalog['works'][0]['assets'])


def test_external_pdf_reference_is_indexed_without_becoming_a_download_target():
    rows = parse_page(item('<a href="http://vmirror.imslp.org/files/score.pdf">PDF</a>', title='Score by Person'), 'posts')
    catalog = make_catalog(rows, [], {})
    asset = catalog['works'][0]['assets'][0]
    assert asset['external']
    assert asset['status'] == 'external_reference'


def test_empty_user_password_and_null_encrypt_are_readable_without_changing_source():
    writer = PdfWriter()
    writer.add_blank_page(100, 100)
    writer.encrypt(user_password='', owner_password='owner')
    output = io.BytesIO()
    writer.write(output)
    data = output.getvalue()
    assert validate_pdf(data)['pdf_encryption'] == 'empty_user_password'
    plain = PdfWriter()
    plain.add_blank_page(100, 100)
    output = io.BytesIO()
    plain.write(output)
    null_encrypt = output.getvalue().replace(b'trailer\n<<', b'trailer\n<<\n/Encrypt null', 1)
    assert validate_pdf(null_encrypt)['pdf_encryption'] == 'null_encrypt_compatibility'
    locked = PdfWriter()
    locked.add_blank_page(100, 100)
    locked.encrypt(user_password='needed', owner_password='owner')
    output = io.BytesIO()
    locked.write(output)
    with pytest.raises(ValueError, match='non-empty user password'):
        validate_pdf(output.getvalue())


def test_external_reuse_requires_exact_approved_imslp_manifest_identity(tmp_path):
    import hashlib
    from classclef_library.pipeline import atomic_json, reuse_external_assets, reuse_record
    writer = PdfWriter()
    writer.add_blank_page(100, 100)
    output = io.BytesIO()
    writer.write(output)
    body = output.getvalue()
    category = tmp_path / 'For guitar (arr)'
    pdf = category / 'scores/source.pdf'
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(body)
    record = {'relative_path': 'scores/source.pdf', 'expected_size': len(body), 'sha1_imslp': hashlib.sha1(body).hexdigest(), 'file_id': '123', 'work_id': '456', 'filename': 'source.pdf'}
    manifest = category / 'metadata/score_manifest.json'
    atomic_json(manifest, [record])
    atomic_json(tmp_path / 'config/categories.json', {'categories': [{'name': category.name}]})
    asset = {'source_url': 'http://vmirror.imslp.org/files/IMSLP123-source.pdf', 'external': True, 'format': 'PDF', 'status': 'external_reference'}
    catalog = {'works': [{'assets': [asset]}]}
    reuse_external_assets(tmp_path, catalog)
    assert asset['status'] == 'verified'
    assert asset['storage_source'] == 'imslp'
    assert asset['local_path'] == 'For guitar (arr)/scores/source.pdf'
    assert not (tmp_path / 'sources/classclef/objects').exists()
    with pytest.raises(ValueError, match='not approved'):
        reuse_record(tmp_path, tmp_path / 'other/For guitar (arr)/metadata/score_manifest.json', record)


def test_shared_generic_title_and_wrong_link_cannot_merge_different_composers():
    rows = parse_page(item('<p>Prelude <a href="/pdf/shared.pdf">PDF</a></p>', title='First Composer (Guitar Tabs)', ident=1), 'pages')
    rows += parse_page(item('<p>Prelude <a href="/pdf/shared.pdf">PDF</a></p>', title='Second Composer (Guitar Tabs)', ident=2, link='https://www.classclef.com/second/'), 'pages')
    catalog = make_catalog(rows, [], {})
    assert len(catalog['works']) == 2
    assert {w['composer_en'] for w in catalog['works']} == {'First Composer', 'Second Composer'}


def test_unknown_author_bridge_cannot_join_two_distinct_composers():
    rows = parse_page(item('<p>Prelude <a href="/pdf/shared.pdf">PDF</a></p>', title='First Composer (Guitar Tabs)', ident=1), 'pages')
    rows += parse_page(item('<p>Prelude <a href="/pdf/shared.pdf">PDF</a></p>', title='Collection', ident=3, link='https://www.classclef.com/unknown/'), 'pages')
    rows += parse_page(item('<p>Prelude <a href="/pdf/shared.pdf">PDF</a></p>', title='Second Composer (Guitar Tabs)', ident=2, link='https://www.classclef.com/second/'), 'pages')
    catalog = make_catalog(rows, [], {})
    assert len(catalog['works']) == 2
    assert sum(len(w['source_records']) for w in catalog['works']) == 3


def test_default_source_page_must_exist_in_frozen_inventory():
    from classclef_library.pipeline import normalize_source_pages
    rows = parse_page(item('<p>Piece <a href="/pdf/piece.pdf">PDF</a><a href="broken-info/">INFO</a></p>', ident=1), 'pages')
    catalog = make_catalog(rows, [], {})
    identity = catalog['works'][0]['id']
    normalize_source_pages(catalog, {'https://www.classclef.com/'})
    work = catalog['works'][0]
    assert work['id'] == identity
    assert work['source_url'] == 'https://www.classclef.com/'
    assert 'https://www.classclef.com/broken-info/' in work['unverified_source_urls']
