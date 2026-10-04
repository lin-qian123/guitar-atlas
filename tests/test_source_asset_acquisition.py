"""Acquisition boundary tests with real PDF/ZIP parsing and an isolated HTTP transport."""
import hashlib
import io
import json
import os
import stat
import zipfile
from pathlib import Path

import pytest
from pypdf import PdfWriter

import acquire_source_assets as acquisition


HOST = 'scores.example.org'
URL = 'https://' + HOST + '/edition.pdf'


def pdf_bytes(width=100):
    writer = PdfWriter()
    writer.add_blank_page(width=width, height=100)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def zip_bytes(members):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, body in members:
            archive.writestr(name, body)
    return output.getvalue()


class Response:
    def __init__(self, url, body=b'', *, status=200, headers=None):
        self.url = url
        self.body = body
        self.status_code = status
        self.headers = headers if headers is not None else {'Content-Length': str(len(body))}
        self.text = body.decode('utf-8', errors='replace')
        self.closed = False

    def iter_content(self, chunk_size):
        for start in range(0, len(self.body), chunk_size):
            yield self.body[start:start + chunk_size]

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class Transport:
    def __init__(self, responses):
        self.responses = responses
        self.headers = {}
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        value = self.responses[url]
        return value() if callable(value) else value


def config(source_id='newsource'):
    return {'id': source_id, 'catalog': f'sources/{source_id}/catalog.json',
            'adapter': 'normalized_catalog', 'asset_hosts': [HOST],
            'acquisition_settings': {'delay': 0.8}}


def client_with_body(tmp_path, monkeypatch, body, *, status=200, headers=None,
                     source_id='newsource', robots='User-agent: *\nDisallow:\n', url=URL):
    monkeypatch.setattr(acquisition.time, 'sleep', lambda _: None)
    client = acquisition.PDFClient(tmp_path, config(source_id))
    client.session = Transport({f'https://{HOST}/robots.txt': Response(f'https://{HOST}/robots.txt', robots.encode()),
                                url: Response(url, body, status=status, headers=headers)})
    return client


def asset(url=URL, **fields):
    return {'source_url': url, 'format': 'PDF', 'status': 'pending', **fields}


def object_files(root):
    return sorted((root / 'sources').glob('**/objects/**/*.pdf'))


@pytest.mark.parametrize('body,expected_exception', [
    (b'<html><title>Login</title></html>', ValueError),
    (b'<html>Verify you are human</html>', acquisition.StopSource),
    (b'<html><script src="/cf-chl-check"></script></html>', acquisition.StopSource),
])
def test_success_http_status_does_not_turn_html_or_a_challenge_into_a_score(tmp_path, monkeypatch, body, expected_exception):
    client = client_with_body(tmp_path, monkeypatch, body)
    with pytest.raises(expected_exception):
        client.acquire(asset())
    assert object_files(tmp_path) == []


@pytest.mark.parametrize('status', [206, 404])
def test_partial_and_missing_http_responses_are_not_verified(tmp_path, monkeypatch, status):
    client = client_with_body(tmp_path, monkeypatch, pdf_bytes(), status=status)
    with pytest.raises(ValueError, match='full PDF response'):
        client.acquire(asset())
    assert object_files(tmp_path) == []


@pytest.mark.parametrize('status', [401, 403, 429])
def test_restricted_http_responses_stop_the_source(tmp_path, monkeypatch, status):
    client = client_with_body(tmp_path, monkeypatch, b'Access denied', status=status)
    with pytest.raises(acquisition.StopSource, match='access stopped'):
        client.acquire(asset())
    assert object_files(tmp_path) == []


def test_truncated_pdf_is_rejected_against_the_declared_content_length(tmp_path, monkeypatch):
    original = pdf_bytes()
    client = client_with_body(tmp_path, monkeypatch, original[:-50], headers={'Content-Length': str(len(original))})
    with pytest.raises(ValueError, match='Content-Length mismatch'):
        client.acquire(asset())
    assert object_files(tmp_path) == []


def test_correct_header_and_length_still_require_real_pdf_parseability(tmp_path, monkeypatch):
    client = client_with_body(tmp_path, monkeypatch, b'%PDF-1.7\nNot a PDF object graph\n%%EOF\n')
    with pytest.raises(ValueError):
        client.acquire(asset())
    assert object_files(tmp_path) == []


@pytest.mark.parametrize('upstream', [{'expected_size': 999999}, {'sha256_upstream': '0' * 64}, {'sha1_upstream': '0' * 40}])
def test_supplied_upstream_integrity_evidence_is_not_silently_ignored(tmp_path, monkeypatch, upstream):
    client = client_with_body(tmp_path, monkeypatch, pdf_bytes())
    with pytest.raises(ValueError, match='upstream'):
        client.acquire(asset(**upstream))
    assert object_files(tmp_path) == []


def test_matching_upstream_checksum_and_no_checksum_have_distinct_receipts(tmp_path, monkeypatch):
    body = pdf_bytes()
    client = client_with_body(tmp_path, monkeypatch, body)
    plain = client.acquire(asset())
    checksum = client.acquire(asset(sha1_upstream=hashlib.sha1(body).hexdigest()))
    assert plain['upstream_checksum_status'] == 'not_supplied'
    assert checksum['upstream_checksum_status'] == 'verified'
    assert plain['sha256'] == checksum['sha256'] == hashlib.sha256(body).hexdigest()


def test_equal_content_from_two_sources_preserves_both_paths_with_one_physical_object(tmp_path, monkeypatch):
    body = pdf_bytes()
    first = client_with_body(tmp_path, monkeypatch, body, source_id='first')
    second = client_with_body(tmp_path, monkeypatch, body, source_id='second')
    receipt_a, receipt_b = first.acquire(asset()), second.acquire(asset())
    path_a, path_b = tmp_path / receipt_a['local_path'], tmp_path / receipt_b['local_path']
    pool = next((tmp_path / 'sources/objects/sha256').glob('*/*.pdf'))
    assert path_a != path_b
    assert os.path.samefile(path_a, path_b) and os.path.samefile(path_a, pool)
    assert path_a.read_bytes() == path_b.read_bytes() == body
    assert len(list((tmp_path / 'sources/objects/sha256').glob('*/*.pdf'))) == 1


def test_zip_preserves_every_score_and_part_name_and_deduplicates_identical_members(tmp_path, monkeypatch):
    score, part = pdf_bytes(120), pdf_bytes(90)
    body = zip_bytes([('edition/score.pdf', score), ('edition/guitar-1.pdf', part),
                      ('edition/guitar-2.pdf', part), ('README.txt', b'Provenance')])
    zip_url = URL.replace('.pdf', '.zip')
    client = client_with_body(tmp_path, monkeypatch, body, url=zip_url)
    receipt = client.acquire(asset(zip_url, container='ZIP'))
    assert receipt['status'] == 'verified'
    assert [member['name'] for member in receipt['members']] == ['edition/score.pdf', 'edition/guitar-1.pdf', 'edition/guitar-2.pdf']
    assert all(member['status'] == 'verified' for member in receipt['members'])
    assert receipt['members'][1]['sha256'] == receipt['members'][2]['sha256']
    assert os.path.samefile(tmp_path / receipt['members'][1]['local_path'], tmp_path / receipt['members'][2]['local_path'])
    assert len(list((tmp_path / 'sources/objects/sha256').glob('*/*.pdf'))) == 2
    assert receipt['container_sha256'] == hashlib.sha256(body).hexdigest()
    assert receipt['container_size'] == len(body)


@pytest.mark.parametrize('name', ['../outside.pdf', '/outside.pdf', 'folder/../../outside.pdf', r'folder\outside.pdf'])
def test_zip_rejects_traversal_before_creating_any_score_object(tmp_path, monkeypatch, name):
    body = zip_bytes([(name, pdf_bytes())])
    zip_url = URL.replace('.pdf', '.zip')
    client = client_with_body(tmp_path, monkeypatch, body, url=zip_url)
    with pytest.raises(ValueError, match='unsafe'):
        client.acquire(asset(zip_url, container='ZIP'))
    assert object_files(tmp_path) == []
    assert not (tmp_path / 'outside.pdf').exists()


def test_zip_cannot_claim_completion_when_any_pdf_member_is_invalid(tmp_path, monkeypatch):
    body = zip_bytes([('score.pdf', pdf_bytes()), ('part.pdf', b'<html>Missing part</html>')])
    zip_url = URL.replace('.pdf', '.zip')
    client = client_with_body(tmp_path, monkeypatch, body, url=zip_url)
    with pytest.raises(ValueError):
        client.acquire(asset(zip_url, container='ZIP'))


@pytest.mark.parametrize('robots,url', [
    ('User-agent: *\nDisallow: /*.pdf$\n', URL),
    ('User-agent: *\nDisallow: /*?\n', URL + '?download=1'),
])
def test_robots_wildcards_prevent_the_file_request_itself(tmp_path, monkeypatch, robots, url):
    client = client_with_body(tmp_path, monkeypatch, pdf_bytes(), robots=robots, url=url)
    with pytest.raises(acquisition.StopSource, match='robots disallows'):
        client.acquire(asset(url))
    assert client.session.calls == [f'https://{HOST}/robots.txt']
    assert object_files(tmp_path) == []


@pytest.mark.parametrize('conflict_location', ['pool', 'source'])
def test_readonly_existing_object_conflict_preserves_original_bytes_and_permissions(tmp_path, monkeypatch, conflict_location):
    incoming, existing = pdf_bytes(120), pdf_bytes(90)
    sha = hashlib.sha256(incoming).hexdigest()
    client = client_with_body(tmp_path, monkeypatch, incoming)
    relative = Path('sources/objects/sha256') / sha[:2] / (sha + '.pdf') if conflict_location == 'pool' else Path('sources/newsource/objects') / (sha + '.pdf')
    conflicting = tmp_path / relative
    conflicting.parent.mkdir(parents=True, exist_ok=True)
    conflicting.write_bytes(existing)
    conflicting.chmod(0o444)
    with pytest.raises(ValueError, match='immutable.*corrupted'):
        client.acquire(asset())
    assert conflicting.read_bytes() == existing
    assert stat.S_IMODE(conflicting.stat().st_mode) == 0o444


def pipeline_catalog(tmp_path, rows):
    path = tmp_path / config()['catalog']
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'schema_version': 1, 'source_id': 'newsource', 'snapshot': {},
                               'works': [{'id': 'newsource:1', 'assets': rows}]}))
    return path


def test_human_challenge_marks_the_trigger_and_leaves_later_assets_pending(tmp_path, monkeypatch):
    other_url = URL.replace('edition', 'later')
    path = pipeline_catalog(tmp_path, [asset(), asset(other_url)])
    client = client_with_body(tmp_path, monkeypatch, b'<html>Verify you are human</html>')
    client.session.responses[other_url] = Response(other_url, pdf_bytes())
    monkeypatch.setattr(acquisition, 'PDFClient', lambda root, source: client)
    report = acquisition.acquire_source(tmp_path, config(), workers=1)
    saved = json.loads(path.read_text())['works'][0]['assets']
    assert saved[0]['status'] == 'blocked' and saved[1]['status'] == 'pending'
    assert report['stopped_reason'] == 'human verification required'
    assert other_url not in client.session.calls


def test_resuming_a_verified_zip_checks_its_members_and_keeps_its_receipt(tmp_path, monkeypatch):
    zip_url = URL.replace('.pdf', '.zip')
    path = pipeline_catalog(tmp_path, [asset(zip_url, container='ZIP')])
    client = client_with_body(tmp_path, monkeypatch, zip_bytes([('score.pdf', pdf_bytes())]), url=zip_url)
    monkeypatch.setattr(acquisition, 'PDFClient', lambda root, source: client)
    acquisition.acquire_source(tmp_path, config())
    before = json.loads(path.read_text())['works'][0]['assets'][0]
    assert before['status'] == 'verified'
    requests_before = len(client.session.calls)
    acquisition.acquire_source(tmp_path, config())
    after = json.loads(path.read_text())['works'][0]['assets'][0]
    assert after['status'] == 'verified'
    assert after['members'] == before['members']
    assert len(client.session.calls) == requests_before
