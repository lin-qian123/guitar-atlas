"""The Guitar School source records, licensed free subset and purchase boundaries."""
from __future__ import annotations

import re
from collections import Counter
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

SOURCE_ID = 'guitarschool'
BASE = 'https://classicalguitarschool.azurewebsites.net/'
DIRECTORY = BASE + 'en/All'
REQUEST_HOSTS = {'classicalguitarschool.azurewebsites.net', 'www.classical-guitar-school.com', 'classical-guitar-school.com'}
CATEGORY_NAMES = ('Methods', 'Studies', 'Collections', 'Solo', 'Duos', 'Trios', 'Quartets', 'Catalogues', 'Theory', 'All')


def text(node):
    return ' '.join(node.get_text(' ', strip=True).split()) if node else ''


def own_url(value, base=BASE):
    parsed = urlsplit(urljoin(base, value))
    if parsed.hostname not in REQUEST_HOSTS or parsed.username or parsed.password:
        raise ValueError('The Guitar School link escaped the source host')
    return urlunsplit(('https', urlsplit(BASE).hostname, parsed.path, parsed.query, ''))


def categories():
    # Record pages link to /en/Theory, but that upstream directory is a real 404.
    # Keep its source label while navigating to the confirmed All directory.
    return [{'id': name.casefold(), 'name': name, 'kind': 'unspecified',
             'source_url': DIRECTORY if name == 'Theory' else BASE + 'en/' + name,
             **({'raw_source_url': BASE + 'en/Theory', 'source_page_status': 'unavailable_404'} if name == 'Theory' else {})}
            for name in CATEGORY_NAMES]


def parse_directory(html, directory_name='All'):
    soup = BeautifulSoup(html, 'html.parser')
    container = soup.select_one('div.container.mt-2')
    if not container or not container.find('h2') or text(container.find('h2')) != directory_name:
        raise ValueError(f'The Guitar School did not return its {directory_name} directory')
    records = []
    for heading in container.find_all('h3', recursive=False):
        composer = text(heading)
        listing = heading.find_next_sibling('ul')
        if not listing:
            raise ValueError('The Guitar School author heading has no record list')
        for item in listing.find_all('li', recursive=False):
            link = item.find('a', href=re.compile(r'^/en/Download/[0-9]+$', re.I))
            if not link:
                raise ValueError('The Guitar School directory record lacks a stable ID')
            native_id = link['href'].rsplit('/', 1)[-1]
            spans = item.find_all('span', recursive=False)
            instrumentation = text(spans[0]).lstrip(' -').rstrip('.') if spans else None
            amount = item.find('strong', class_='text-muted')
            records.append({'id': SOURCE_ID + ':' + native_id, 'title_en': text(link),
                            'composer_en': composer, 'source_url': own_url(link['href']),
                            'category_ids': [directory_name.casefold()], 'formats': [],
                            'instrumentation_status': 'source_declared' if instrumentation else 'unverified',
                            'resource_type': 'score', 'assets': [],
                            'metadata': {'instrumentation': instrumentation or None,
                                         'directory_information': text(item), 'directory_price': text(amount) or None,
                                         'arranger': None, 'editor': None, 'opus': None,
                                         'license': None, 'source_edition': None, 'difficulty': None,
                                         'original_arrangement_status': 'unspecified',
                                         'detail_status': 'pending', 'acquisition_status': 'unknown'}})
    if len({row['id'] for row in records}) != len(records):
        raise ValueError('The Guitar School directory duplicated a record identity')
    summary = next((text(p) for p in container.find_all('p', recursive=False) if 'Files:' in text(p)), '')
    declared_files = re.search(r'Files:\s*([0-9]+)', summary)
    if declared_files and int(declared_files.group(1)) != len(records):
        raise ValueError('The Guitar School parsed count disagrees with the directory Files count')
    return records, {'source_summary_text': summary, 'declared_file_records': int(declared_files.group(1)) if declared_files else None}


def parse_detail(html, record):
    soup = BeautifulSoup(html, 'html.parser')
    container = soup.select_one('div.container.mt-2')
    title = container.find('h3', recursive=False) if container else None
    if not title or text(title) != record['title_en']:
        raise ValueError('The Guitar School title changed between directory and detail')
    author = container.find('h2', recursive=False)
    if not author or text(author) != record['composer_en']:
        raise ValueError('The Guitar School attribution changed between directory and detail')
    metadata = dict(record['metadata'])
    fields = {}
    for item in container.select('ul.list-unstyled > li'):
        label = item.find('strong')
        if not label:
            continue
        name = text(label).rstrip(':').casefold()
        # Preserve author names and descriptive field text; omit icon prefix.
        clone = BeautifulSoup(str(item), 'html.parser')
        tag = clone.find('strong')
        for sibling in list(tag.previous_siblings):
            sibling.extract()
        tag.decompose()
        fields[name] = text(clone).lstrip(':').strip()
    mapping = {'for': 'instrumentation', 'arrangement': 'arranger', 'revision': 'editor',
               'information': 'information', 'grade': 'difficulty', 'isbn': 'isbn',
               'ismn': 'ismn', 'pages': 'source_pages', 'price': 'price',
               'musical style': 'style', 'added': 'added_at_source'}
    for name, key in mapping.items():
        if name in fields:
            metadata[key] = fields[name] or None
    if 'source_pages' in metadata and metadata['source_pages'] and metadata['source_pages'].isdigit():
        metadata['source_pages'] = int(metadata['source_pages'])
    grade_item = next((item for item in container.select('ul.list-unstyled > li')
                       if item.find('strong') and text(item.find('strong')).rstrip(':').casefold() == 'grade'), None)
    metadata['grades'] = [text(anchor) for anchor in grade_item.find_all('a')] if grade_item else []
    metadata['source_fields'] = fields
    metadata['collection_contents'] = [text(label) for label in container.find_all('label') if text(label)]
    metadata['teaching_videos'] = [frame['src'] for frame in container.find_all('iframe', src=True)
                                  if urlsplit(frame['src']).hostname in {'www.youtube.com', 'youtube.com'}]
    information = metadata.get('information') or ''
    editor = re.search(r'(?:Revised and fingered|Revised|Collected and fingered) by ([^.]+)\.', information)
    if editor:
        metadata['editor'] = editor.group(1).strip()
    if metadata.get('arranger'):
        metadata['original_arrangement_status'] = 'arrangement'
    license_links = container.select('a[rel~="license"][href]')
    license_urls = sorted({anchor['href'].replace('http://', 'https://', 1) for anchor in license_links
                           if re.fullmatch(r'https?://creativecommons\.org/(?:licenses/[a-z-]+/[0-9.]+|publicdomain/(?:zero|mark)/[0-9.]+)/?', anchor['href'])})
    if len(license_urls) > 1:
        raise ValueError('The Guitar School record declares conflicting licenses')
    license_url = license_urls[0] if license_urls else None
    metadata['license_url'] = license_url
    if license_url:
        segments = urlsplit(license_url).path.strip('/').split('/')
        metadata['license'] = ('CC ' + segments[1].upper() + ' ' + segments[2]) if segments[0] == 'licenses' else '/'.join(segments)
    price = metadata.get('price') or metadata.get('directory_price') or ''
    free = price.casefold() == 'free download'
    purchase = bool(re.search(r'\$\s*[0-9]|€\s*[0-9]|£\s*[0-9]', price))
    metadata['acquisition_status'] = 'confirmed' if free and license_url and not purchase else 'restricted' if purchase else 'unknown'
    metadata['acquisition_reason'] = ('Source record explicitly declares free download and a Creative Commons license.'
                                     if metadata['acquisition_status'] == 'confirmed' else
                                     'Paid record; purchase was not attempted.' if purchase else
                                     'A free button without a confirmed per-record license does not authorize bulk file acquisition.')
    header = container.find('h1', recursive=False)
    category = header.find('a', href=True) if header else None
    if category:
        name = text(category)
        if name not in CATEGORY_NAMES:
            raise ValueError('The Guitar School returned an unrecognized source category')
        record['category_ids'] = sorted(set(record['category_ids']) | {name.casefold()})
        record['resource_type'] = 'reference' if name in {'Catalogues', 'Theory'} else 'score'
    assets = []
    for anchor in container.find_all('a', href=True):
        path = urlsplit(urljoin(BASE, anchor['href'])).path
        if not re.fullmatch(r'/en/Files/[0-9]+\.pdf', path, re.I):
            continue
        url = own_url(anchor['href'])
        if url in {asset['source_url'] for asset in assets}:
            continue
        assets.append({'source_url': url, 'format': 'PDF', 'filename': unquote(path.rsplit('/', 1)[-1]),
                       'label': anchor.get('title') or text(anchor),
                       'status': 'pending' if metadata['acquisition_status'] == 'confirmed' else 'restricted',
                       'license': metadata.get('license'), 'license_url': license_url,
                       'acquisition_basis': record['source_url'], 'upstream_checksum_status': 'not_supplied',
                       'expected_pages': metadata.get('source_pages')})
    # PDF is asserted only when a real source file is linked or explicitly named.
    record['formats'] = ['PDF'] if assets or re.search(r'\bPDF\b', text(container), re.I) else []
    record['assets'] = assets
    metadata['detail_status'] = 'complete'
    record['metadata'] = metadata
    record['instrumentation_status'] = 'source_declared' if metadata.get('instrumentation') else 'unverified'
    return record


def registry_proposal():
    return {'id': SOURCE_ID, 'name': 'The Guitar School', 'homepage': BASE,
            'allowed_hosts': sorted(REQUEST_HOSTS), 'adapter': 'normalized_catalog',
            'catalog': 'sources/guitarschool/catalog.json', 'family': SOURCE_ID,
            'asset_hosts': sorted(REQUEST_HOSTS),
            'acquisition_settings': {'delay': 0.8, 'formats': ['PDF'], 'licensing': 'explicit_per_record_free_creative_commons_only'},
            'family_name_zh': 'The Guitar School 来源目录', 'family_name_en': 'The Guitar School collections',
            'public_page_rules': [{'path': r'/en/Download/[0-9]+'},
                                  {'path': r'/en/(?:Methods|Studies|Collections|Solo|Duos|Trios|Quartets|Catalogues|All)'}]}


def discover_category_memberships(client, records):
    """Resolve cross-directory memberships by native ID, never title similarity."""
    by_id = {row['id']: row for row in records}
    memberships = {row['id']: set(row['category_ids']) for row in records}
    directory_counts = {'All': len(records)}
    for name in CATEGORY_NAMES:
        if name in {'All', 'Theory'}:
            continue
        directory_url = BASE + 'en/' + name
        rows, summary = parse_directory(client.get(directory_url), name)
        directory_counts[name] = len(rows)
        for row in rows:
            if row['id'] not in by_id:
                raise ValueError(f'Upstream directory drift: {row["id"]} is absent from the frozen All directory')
            frozen = by_id[row['id']]
            if row['title_en'] != frozen['title_en'] or row['composer_en'] != frozen['composer_en']:
                raise ValueError(f'Upstream directory attribution/title drift: {row["id"]}')
            memberships[row['id']].add(name.casefold())
    directory_counts['Theory'] = sum('theory' in values for values in memberships.values())
    patch = {'schema_version': 1, 'source_id': SOURCE_ID, 'frozen_at': client.frozen_at,
             'directory_counts': directory_counts,
             'directory_evidence': {'Theory': {'status': 'unavailable_404', 'raw_source_url': BASE + 'en/Theory',
                                               'fallback_url': DIRECTORY, 'membership_basis': 'record_page_source_category_header'}},
             'records': [{'id': identity, 'category_ids': sorted(values)} for identity, values in memberships.items()]}
    client.write_json('category_memberships_patch.json', patch)
    return patch


def discover(client, max_details=None):
    client.write_json('registry_proposal.json', registry_proposal())
    records, source_summary = parse_directory(client.get(DIRECTORY))
    membership_patch = discover_category_memberships(client, records)
    membership_map = {row['id']: row['category_ids'] for row in membership_patch['records']}
    for row in records:
        row['category_ids'] = membership_map[row['id']]
    catalog = {'schema_version': 1, 'source_id': SOURCE_ID,
               'snapshot': {'frozen_at': client.frozen_at, 'discovery_complete': False, 'page_count': len(CATEGORY_NAMES) - 1,
                            'scope': 'All English directory records; free licensed PDFs only for acquisition',
                            'scope_version': '2026-10-01.1', 'directory_url': DIRECTORY,
                            'directory_discovery_complete': True, 'directory_counts': membership_patch['directory_counts'],
                            'directory_evidence': membership_patch['directory_evidence'], **source_summary},
               'categories': categories(), 'works': records, 'summary': {}}
    client.save_catalog(catalog)
    detail_complete = 0
    for index, row in enumerate(records):
        if max_details is not None and index >= max_details:
            break
        try:
            parse_detail(client.get(row['source_url']), row)
            detail_complete += 1
        except Exception as exc:
            row['metadata'].update(detail_status='failed', detail_error=str(exc))
            if exc.__class__.__name__ == 'DiscoveryBlocked':
                catalog['snapshot']['blocked_reason'] = str(exc)
                client.save_catalog(catalog)
                break
        if (index + 1) % 25 == 0:
            client.log('detail_progress', checked=index + 1, total=len(records))
            client.save_catalog(catalog)
    catalog['snapshot'].update(discovery_complete=detail_complete == len(records),
                               detail_page_count=detail_complete, page_count=len(CATEGORY_NAMES) - 1 + detail_complete)
    catalog['snapshot']['directory_counts']['Theory'] = sum('theory' in row['category_ids'] for row in records)
    catalog['summary'] = {'source_records': len(records), 'category_memberships': sum(len(row['category_ids']) for row in records),
                          'detail_complete': detail_complete, 'detail_pending_or_failed': len(records) - detail_complete,
                          'score_records': sum(row['resource_type'] == 'score' for row in records),
                          'reference_records': sum(row['resource_type'] == 'reference' for row in records),
                          'pdf_asset_records': sum(asset['format'] == 'PDF' for row in records for asset in row['assets']),
                          'pdf_acquisition_pending': sum(asset['status'] == 'pending' for row in records for asset in row['assets']),
                          'pdf_acquisition_restricted': sum(asset['status'] == 'restricted' for row in records for asset in row['assets']),
                          'acquisition_status': dict(Counter(row['metadata']['acquisition_status'] for row in records)),
                          'instrumentation': dict(Counter(row['metadata']['instrumentation'] for row in records)),
                          'license': dict(Counter(row['metadata']['license'] for row in records))}
    client.write_json('discovery_report.json', {'snapshot': catalog['snapshot'], 'summary': catalog['summary'],
        'limits': ['Paid records are metadata navigation only; no purchase, login or subscription was attempted.',
                   'Directory file/page counts are source-provided edition counts, not unique works or physical PDFs.',
                   'Source-declared instrumentation has not been checked against every file.',
                   'No PDF files were acquired or validated by discovery.']})
    return catalog
