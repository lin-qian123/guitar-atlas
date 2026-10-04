"""Mutopia's Guitar directory, with per-record licensing and frozen Git provenance."""
from __future__ import annotations

import re
from collections import Counter
from urllib.parse import parse_qs, unquote, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

SOURCE_ID = 'mutopia'
BASE = 'https://www.mutopiaproject.org/'
DIRECTORY = BASE + 'cgibin/make-table.cgi?Instrument=Guitar'
REQUEST_HOSTS = {'www.mutopiaproject.org', 'mutopiaproject.org', 'api.github.com', 'raw.githubusercontent.com'}
REPOSITORY = 'https://github.com/MutopiaProject/MutopiaProject'
API = 'https://api.github.com/repos/MutopiaProject/MutopiaProject/'
INCLUDED_INSTRUMENTATIONS = {'Guitar', 'Classical Guitar', '2 Guitars', 'Guitar Duet',
                            'Flute and Guitar', 'Recorder, Guitar', 'Clarinet, Guitar', 'Violin, Guitar'}


def apply_scope(row):
    instrumentation = row['metadata'].get('instrumentation') or ''
    if re.search(r'\bvoice\b|\bchorus\b', instrumentation, re.I):
        status, reason = 'excluded', 'Source explicitly includes voice, outside the approved instrumental guitar scope.'
    elif re.search(r'\bor\b', instrumentation, re.I):
        status, reason = 'excluded', 'Source explicitly presents guitar as an alternative instrument, outside the approved scope.'
    elif instrumentation not in INCLUDED_INSTRUMENTATIONS:
        status, reason = 'pending_review', 'Source declaration does not establish an approved instrumentation; file-level review is pending.'
        row['instrumentation_status'] = 'unverified'
        for asset in row['assets']:
            if asset['format'] == 'PDF':
                asset.update(status='restricted', restriction_reason='Instrumental scope requires file-level review before acquisition.')
    else:
        status, reason = 'included', 'Source declares guitar solo, multiple guitars or an approved small instrumental combination.'
    row['metadata'].update(scope_status=status, scope_reason=reason)
    return status


def text(node):
    return ' '.join(node.get_text(' ', strip=True).split()) if node else ''


def own_url(value, base=BASE):
    parsed = urlsplit(urljoin(base, value))
    if parsed.hostname not in {'www.mutopiaproject.org', 'mutopiaproject.org'}:
        raise ValueError('Mutopia link escaped the source host')
    return urlunsplit(('https', 'www.mutopiaproject.org', parsed.path, parsed.query, ''))


def composer_fields(value):
    original = re.sub(r'^by\s+', '', value)
    match = re.search(r'\s*\(([^()]*(?:\d{3,4}|[?])[^()]*)\)$', original)
    return {'composer_en': original[:match.start()].strip() if match else original,
            'composer_attribution': original, 'composer_dates': match.group(1) if match else None}


def assets_from(node, base, license_text, license_url=None):
    assets = []
    for anchor in node.find_all('a', href=True):
        url = own_url(anchor['href'], base) if urlsplit(urljoin(base, anchor['href'])).hostname in {'www.mutopiaproject.org', 'mutopiaproject.org'} else None
        if not url:
            continue
        path = urlsplit(url).path.lower()
        label = text(anchor)
        fmt = ('PDF' if path.endswith('.pdf') or (path.endswith('.zip') and 'pdf' in label.lower()) else
               'LILYPOND' if path.endswith('.ly') or (path.endswith('.zip') and ('.ly' in label.lower() or 'lilypond' in label.lower())) else
               'MIDI' if path.endswith(('.mid', '.midi')) or (path.endswith('.zip') and 'mid' in label.lower()) else None)
        if fmt and url not in {asset['source_url'] for asset in assets}:
            asset = {'source_url': url, 'filename': unquote(urlsplit(url).path.rsplit('/', 1)[-1]),
                     'format': fmt, 'label': label,
                     'status': 'pending' if fmt == 'PDF' else 'metadata_only',
                     'license': license_text, 'license_url': license_url,
                     'acquisition_basis': BASE + 'legal.html', 'upstream_checksum_status': 'not_supplied'}
            if path.endswith('.zip'):
                asset['container'] = 'ZIP'
            if 'a4' in label.lower() or '-a4.' in path:
                asset['paper_size'] = 'A4'
            elif 'letter' in label.lower() or '-let.' in path:
                asset['paper_size'] = 'Letter'
            assets.append(asset)
    return assets


def parse_listing(html, url=DIRECTORY):
    soup = BeautifulSoup(html, 'html.parser')
    result = []
    for table in soup.select('table.outer-table table.result-table'):
        rows = table.find_all('tr', recursive=False)
        if len(rows) < 3:
            raise ValueError('malformed Mutopia listing record')
        cells = [row.find_all('td', recursive=False) for row in rows[:3]]
        info = cells[2][2].find('a', href=True)
        if not info:
            raise ValueError('Mutopia listing lacks a stable record page')
        source_url = own_url(info['href'], url)
        identity = parse_qs(urlsplit(source_url).query).get('id', [])
        if len(identity) != 1 or not identity[0].isdigit():
            raise ValueError('invalid Mutopia record ID')
        attribution = composer_fields(text(cells[0][1]))
        license_text = text(cells[2][1])
        assets = assets_from(table, url, license_text)
        instrumentation = re.sub(r'^for\s+', '', text(cells[1][0]))
        result.append({'id': SOURCE_ID + ':' + identity[0], 'title_en': text(cells[0][0]),
                       'composer_en': attribution['composer_en'], 'source_url': source_url,
                       'category_ids': ['guitar'], 'formats': sorted({asset['format'] for asset in assets}),
                       'instrumentation_status': 'source_declared' if instrumentation else 'unverified',
                       'resource_type': 'score', 'assets': assets,
                       'metadata': {'instrumentation': instrumentation or None,
                                    'composer_attribution': attribution['composer_attribution'],
                                    'composer_dates': attribution['composer_dates'],
                                    'opus': text(cells[0][2]) or None,
                                    'composition_date': text(cells[1][1]) or None,
                                    'style': text(cells[1][2]) or None,
                                    'source_edition': text(cells[2][0]) or None,
                                    'license': license_text or None, 'updated_at_source': text(cells[2][3]) or None,
                                    'arranger': None, 'editor': None, 'difficulty': None,
                                    'original_arrangement_status': 'unspecified', 'detail_status': 'pending'}})
    next_link = soup.find('a', string=lambda value: bool(value and re.fullmatch(r'Next\s+\d+', value.strip())))
    next_url = own_url(next_link['href'], url) if next_link else None
    if not result and soup.select_one('table.outer-table'):
        raise ValueError('Mutopia listing table contained no parseable records')
    return result, next_url


def parse_detail(html, record):
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.find('h2')
    if not title:
        raise ValueError('Mutopia detail page has no title')
    content = title.parent
    if text(title) != record['title_en']:
        raise ValueError('Mutopia title changed between directory and detail')
    metadata = dict(record['metadata'])
    key_map = {'instrument(s)': 'instrumentation', 'style': 'style', 'opus': 'opus',
               'date of composition': 'composition_date', 'source': 'source_edition',
               'copyright': 'license', 'last updated': 'updated_at_source',
               'music id number': 'music_id', 'typeset using': 'typesetting',
               'maintainer': 'maintainer'}
    license_url = None
    for cell in content.select('td'):
        bold = cell.find('b')
        if not bold:
            continue
        label = text(bold).rstrip(':').casefold()
        if label not in key_map:
            continue
        clone = BeautifulSoup(str(cell), 'html.parser')
        clone.find('b').decompose()
        value = text(clone)
        if label == 'last updated':
            value = value.split('View change history')[0].strip().rstrip('.')
        if label == 'copyright':
            value = text(cell.find('a')) or value
            cc = cell.find('a', href=re.compile(r'creativecommons\.org/'))
            if cc:
                license_url = cc['href'].replace('http://', 'https://', 1)
        metadata[key_map[label]] = value or None
    attribution = content.find('h4')
    if attribution:
        composer = composer_fields(text(attribution))
        if composer['composer_en'].strip('()') != record['composer_en'].strip('()'):
            raise ValueError('Mutopia attribution changed between directory and detail')
        metadata['detail_composer_attribution'] = composer['composer_attribution']
    metadata['license_url'] = license_url
    metadata['detail_status'] = 'complete'
    # Keep maintainer's name; do not export their personal email contact.
    record['metadata'] = metadata
    record['assets'] = assets_from(content, record['source_url'], metadata.get('license'), license_url)
    record['formats'] = sorted({asset['format'] for asset in record['assets']})
    return record


def registry_proposal():
    return {'id': SOURCE_ID, 'name': 'Mutopia', 'homepage': BASE,
            'allowed_hosts': ['www.mutopiaproject.org', 'mutopiaproject.org'],
            'adapter': 'normalized_catalog', 'catalog': 'sources/mutopia/catalog.json',
            'family': SOURCE_ID, 'family_name_zh': 'Mutopia 来源目录', 'family_name_en': 'Mutopia collections',
            'asset_hosts': ['www.mutopiaproject.org', 'mutopiaproject.org'],
            'acquisition_settings': {'delay': 0.8, 'formats': ['PDF'], 'licensing': 'per_record_and_official_license_details'},
            'public_page_rules': [{'path': r'/cgibin/piece-info\.cgi', 'query': {'id': r'[0-9]+'}},
                                  {'path': r'/cgibin/make-table\.cgi', 'query': {'Instrument': 'Guitar'}}]}


def discover(client, max_details=None):
    client.write_json('registry_proposal.json', registry_proposal())
    client.get(BASE + 'legal.html')
    repo_state_path = client.root / 'snapshots/github_commit.json'
    if repo_state_path.exists() and not client.refresh:
        import json
        repo = json.loads(repo_state_path.read_text())
    else:
        head = client.json(API + 'commits?per_page=1')[0]
        repo = {'repository': REPOSITORY, 'commit': head['sha'], 'committed_at': head['commit']['committer']['date']}
        client.write_json('snapshots/github_commit.json', repo)
    tree = client.json(API + 'git/trees/' + repo['commit'] + '?recursive=1')
    if tree.get('truncated'):
        raise ValueError('GitHub source tree is truncated; provenance snapshot is incomplete')
    tree_files = {row['path']: row for row in tree['tree'] if row['type'] == 'blob'}
    records, pages, seen_urls = {}, 0, set()
    url = DIRECTORY
    while url:
        if url in seen_urls:
            raise ValueError('Mutopia pagination repeated a page')
        seen_urls.add(url)
        rows, url = parse_listing(client.get(url), url)
        if not rows and url:
            raise ValueError('Mutopia pagination returned an empty intermediate page')
        for row in rows:
            if row['id'] in records:
                raise ValueError('Mutopia pagination duplicated an identity')
            for asset in row['assets']:
                source_path = unquote(urlsplit(asset['source_url']).path.lstrip('/'))
                if source_path in tree_files:
                    asset['source_repository'] = {'commit': repo['commit'], 'path': source_path,
                        'git_blob_id': tree_files[source_path]['sha'], 'size': tree_files[source_path].get('size')}
            records[row['id']] = row
        pages += 1
        client.log('directory_progress', pages=pages, records=len(records))
    catalog = {'schema_version': 1, 'source_id': SOURCE_ID,
               'snapshot': {'frozen_at': client.frozen_at, 'discovery_complete': False, 'page_count': pages,
                            'scope': 'official Guitar directory; native instrument declarations retained separately',
                            'scope_version': '2026-10-01.1', 'directory_url': DIRECTORY, 'repository': repo,
                            'directory_discovery_complete': True, 'snapshot_basis': 'cached official directory and detail pages; fixed Git tree provenance'},
               'categories': [{'id': 'guitar', 'name': 'Guitar', 'kind': 'unspecified', 'source_url': DIRECTORY}],
               'works': list(records.values()), 'summary': {}}
    client.save_catalog(catalog)
    detail_complete = 0
    for index, row in enumerate(catalog['works']):
        if max_details is not None and index >= max_details:
            break
        try:
            old_assets = {asset['source_url']: asset for asset in row['assets']}
            parse_detail(client.get(row['source_url']), row)
            for asset in row['assets']:
                if asset['source_url'] in old_assets and 'source_repository' in old_assets[asset['source_url']]:
                    asset['source_repository'] = old_assets[asset['source_url']]['source_repository']
            detail_complete += 1
        except Exception as exc:
            row['metadata'].update(detail_status='failed', detail_error=str(exc))
            if exc.__class__.__name__ == 'DiscoveryBlocked':
                catalog['snapshot']['blocked_reason'] = str(exc)
                client.save_catalog(catalog)
                break
        if (index + 1) % 25 == 0:
            client.log('detail_progress', checked=index + 1, total=len(catalog['works']))
            client.save_catalog(catalog)
    catalog['snapshot'].update(discovery_complete=detail_complete == len(catalog['works']),
                               detail_page_count=detail_complete, page_count=pages + detail_complete)
    catalog['summary'] = {'source_records': len(catalog['works']), 'category_memberships': len(catalog['works']),
                          'detail_complete': detail_complete, 'detail_pending_or_failed': len(catalog['works']) - detail_complete,
                          'asset_records': sum(len(row['assets']) for row in catalog['works']),
                          'pdf_asset_records': sum(asset['format'] == 'PDF' for row in catalog['works'] for asset in row['assets']),
                          'instrumentation': dict(Counter(row['metadata']['instrumentation'] for row in catalog['works'])),
                          'license': dict(Counter(row['metadata']['license'] for row in catalog['works']))}
    discovered_records = list(catalog['works'])
    discovered_summary = dict(catalog['summary'])
    excluded = []
    for row in discovered_records:
        if apply_scope(row) == 'excluded':
            excluded.append(row)
    client.write_json('discovered_catalog.json', catalog)
    catalog['works'] = [row for row in discovered_records if row not in excluded]
    catalog['summary'].update(discovered_source_records=len(discovered_records),
                              source_records=len(catalog['works']), category_memberships=len(catalog['works']),
                              detail_complete=sum(row['metadata']['detail_status'] == 'complete' for row in catalog['works']),
                              detail_pending_or_failed=sum(row['metadata']['detail_status'] != 'complete' for row in catalog['works']),
                              discovered_detail_complete=detail_complete,
                              excluded_source_records=len(excluded),
                              scope_review_pending=sum(row['metadata']['scope_status'] == 'pending_review' for row in catalog['works']),
                              pdf_asset_records=sum(asset['format'] == 'PDF' for row in catalog['works'] for asset in row['assets']),
                              pdf_acquisition_pending=sum(asset['format'] == 'PDF' and asset['status'] == 'pending' for row in catalog['works'] for asset in row['assets']),
                              pdf_scope_restricted=sum(asset['format'] == 'PDF' and asset['status'] == 'restricted' for row in catalog['works'] for asset in row['assets']))
    catalog['summary'].update(asset_records=sum(len(row['assets']) for row in catalog['works']),
                              instrumentation=dict(Counter(row['metadata']['instrumentation'] for row in catalog['works'])),
                              license=dict(Counter(row['metadata']['license'] for row in catalog['works'])))
    client.write_json('scope_exclusions.json', {'excluded_records': excluded, 'source_scope_version': '2026-10-01.1'})
    client.write_json('discovery_report.json', {'snapshot': catalog['snapshot'], 'summary': catalog['summary'], 'discovered_summary': discovered_summary,
        'limits': ['Directory memberships do not establish file-level instrumentation correctness.',
                   'Git blob IDs are provenance identifiers, not source-provided PDF checksums.',
                   'No PDF, MIDI or LilyPond files were acquired or validated by discovery.']})
    return catalog
