"""Freeze, index, download and verify publicly listed ClassClef scores."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import html
import io
import json
import logging
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag
from pypdf import PdfReader
from pypdf.generic import NullObject
import requests

logging.getLogger('pypdf').setLevel(logging.ERROR)
HOSTS = {'www.classclef.com', 'classclef.com'}
SUCCESS = 'verified'
BLOCKED_CODES = {401, 403, 429}
SCORE_FORMATS = {'PDF', 'GPX', 'GP3', 'GP4', 'GP5'}
DOWNLOAD_KEYS = {'status', 'sha256', 'sha1', 'size', 'pages', 'local_path', 'members', 'archive_sha256', 'archive_sha1', 'archive_size', 'ignored_archive_members', 'verified_at', 'final_url', 'http_content_length', 'source_sha1', 'source_sha1_status', 'last_error', 'attempted_at', 'pdf_encryption', 'storage_source', 'reused_from_manifest', 'imslp_file_id', 'imslp_work_id'}


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + '.part')
    with part.open('w', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    part.replace(path)


def canonical_url(value: str, base='https://www.classclef.com/') -> str:
    """Normalize percent escaping without changing source path case or filename."""
    # Legacy directory pages use root-relative slugs without their leading slash.
    parsed = urllib.parse.urlsplit(urllib.parse.urljoin(base, html.unescape(value.strip())))
    if parsed.hostname not in HOSTS or parsed.scheme not in {'http', 'https'}:
        raise ValueError('external or unsupported source URL')
    path = urllib.parse.quote(urllib.parse.unquote(parsed.path), safe="/!$&'()*+,;=:@-._~")
    return urllib.parse.urlunsplit(('https', 'www.classclef.com', path or '/', parsed.query, ''))


def text(value: str) -> str:
    return ' '.join(BeautifulSoup(value, 'html.parser').get_text(' ', strip=True).split())


def asset_format(url):
    suffix = Path(urllib.parse.urlsplit(url).path).suffix.lower()
    return {'.pdf': 'PDF', '.mid': 'MIDI', '.midi': 'MIDI', '.gpx': 'GPX', '.gp5': 'GP5', '.gp4': 'GP4', '.gp3': 'GP3', '.zip': 'ZIP'}.get(suffix)


def asset_from_link(link: Tag):
    external = False
    try:
        url = canonical_url(link.get('href', ''))
    except ValueError:
        url = html.unescape(link.get('href', '')).strip()
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password:
            return None
        external = True
    fmt = asset_format(url)
    if not fmt:
        return None
    label = link.get_text(' ', strip=True).upper()
    image = link.find('img')
    icon = image.get('src', '').lower() if image else ''
    container = None
    # Several upstream GPX buttons point to mistaken .pdf suffixes under /gpx/.
    # Respect their explicit companion-format label and preserve the erroneous URL.
    declared_format = 'GPX' if label == 'GPX' or 'downloadgpx' in icon else ('MIDI' if label == 'MIDI' or 'downloadmidi' in icon else None)
    if declared_format is None and label not in {'PDF', 'TAB', 'NOTE'} and 'downloadpdf' not in icon:
        namespace = urllib.parse.urlsplit(url).path.split('/')[1].lower()
        if namespace in {'gpx', 'midi'}:
            declared_format = namespace.upper()
    suffix_format = fmt
    if declared_format and fmt != 'ZIP':
        fmt = declared_format
    if fmt == 'ZIP':
        container = 'ZIP'
        if label in {'PDF', 'TAB', 'NOTE'} or '/pdf/' in url or '/source/' in url or 'downloadpdf' in icon:
            fmt = 'PDF'
        elif '/gpx/' in url or label == 'GPX':
            fmt = 'GPX'
        elif '/midi/' in url or label == 'MIDI':
            fmt = 'MIDI'
    if fmt == 'PDF':
        image = link.find('img')
        icon = image.get('src', '').lower() if image else ''
        if '/source/' in url or 'note' in icon:
            label = 'NOTE'
        elif 'tab' in icon:
            label = 'TAB'
        elif label not in {'TAB', 'NOTE', 'PDF'}:
            label = 'PDF'
    else:
        label = fmt
    result = {'format': fmt, 'label': label, 'source_url': url, 'status': 'pending' if fmt == 'PDF' else 'metadata_only'}
    if container:
        result['container'] = container
    if declared_format and suffix_format != declared_format and suffix_format != 'ZIP':
        result['url_extension_mismatch'] = True
    if external:
        result.update(external=True, status='external_reference')
    return result


def title_composer(title: str):
    title = re.sub(r'\s*(?:[-–—]\s*|\()(?:Classical |Fingerstyle |Flamenco |Acoustic )?Guitar Tabs?\)?\s*$', '', title, flags=re.I)
    depth = 0
    candidates = []
    for match in re.finditer(r'[()]|\s+by\s+', title, flags=re.I):
        token = match.group()
        if token == '(':
            depth += 1
        elif token == ')':
            depth = max(0, depth - 1)
        elif depth == 0 and not re.search(r'(?:arranged|transcribed|edited|tabbed)\s*$', title[:match.start()], re.I):
            candidates.append(match)
    if candidates:
        split = candidates[-1]
        composer = re.split(r'\s*[-–]?\s*(?:Arranged|Transcribed|Edited|Tabbed)\s+by\s+', title[split.end():], maxsplit=1, flags=re.I)[0]
        return title[:split.start()].strip(), re.sub(r'\s*\(\d{4}[^)]*\)\s*$', '', composer).strip()
    return title, ''


def line_fragments(soup):
    """Preserve inline tags and split only at actual source line/block boundaries."""
    pending = []
    def visit(node):
        nonlocal pending
        if isinstance(node, NavigableString):
            pending.append(html.escape(str(node)))
        elif isinstance(node, Tag):
            if node.name in {'script', 'style'}:
                return
            if node.name == 'br':
                yield ''.join(pending)
                pending = []
                # html.parser may nest source text inside malformed <br>...</br>.
                for child in node.children:
                    yield from visit(child)
            elif node.name in {'a', 'strong', 'b', 'u', 'em', 'i', 'span', 'font'}:
                pending.append(str(node))
            elif node.name in {'p', 'div', 'li', 'tr', 'h1', 'h2', 'h3', 'h4', 'h5', 'center', 'figure'}:
                if pending:
                    yield ''.join(pending)
                    pending = []
                for child in node.children:
                    yield from visit(child)
                if pending:
                    yield ''.join(pending)
                    pending = []
            else:
                for child in node.children:
                    yield from visit(child)
    yield from visit(soup)
    if pending:
        yield ''.join(pending)


def parse_page(item, kind):
    title = text(item['title']['rendered'])
    page_url = canonical_url(item['link'])
    soup = BeautifulSoup(item['content']['rendered'].replace('</br>', '<br>'), 'html.parser')
    if kind == 'posts':
        assets = [asset for a in soup.find_all('a', href=True) if (asset := asset_from_link(a))]
        if not any(a['format'] in SCORE_FORMATS for a in assets):
            return []
        work_title, composer = title_composer(title)
        return [{'title_en': work_title, 'composer_en': composer, 'source_url': page_url,
                 'page_url': page_url, 'wp_id': item['id'], 'origin': 'post', 'page_title': title, 'assets': assets,
                 'category_ids': []}]
    category_id = f"page:{item['id']}"
    composer = ''
    match = re.match(r'^(.+?)\s*\((?:Classical|Fingerstyle|Flamenco|Acoustic)?\s*Guitar Tabs?\)$', title, flags=re.I)
    if match and not re.match(r'^[A-Z]:', title):
        composer = match.group(1)
    records = []
    for fragment in line_fragments(soup):
        line = BeautifulSoup(fragment, 'html.parser')
        assets = [asset for a in line.find_all('a', href=True) if (asset := asset_from_link(a))]
        if not any(a['format'] in SCORE_FORMATS for a in assets):
            strong = line.find(['strong', 'b'])
            plain = line.get_text(' ', strip=True)
            if strong and (re.search(r'\(?\d{4}\s*[-–]', plain) or ',' in strong.get_text() or strong.get_text(strip=True) in {'Anonymous', 'Traditional'}):
                composer = strong.get_text(' ', strip=True).strip(' .')
            continue
        first_asset = next(a for a in line.find_all('a', href=True) if asset_from_link(a))
        # Text before the first format link is the source's displayed work title.
        raw = str(line)
        prefix = raw[:raw.find(str(first_asset))]
        work_title = text(prefix).strip(' .|')
        if not work_title:
            work_title = Path(urllib.parse.unquote(urllib.parse.urlsplit(assets[0]['source_url']).path)).stem
        source_url = page_url
        info_urls = []
        for a in line.find_all('a', href=True):
            if a.get_text(' ', strip=True).upper() == 'INFO':
                try:
                    candidate = canonical_url(a['href'])
                    info_urls.append(candidate)
                    if '/https:' not in candidate and '/http:' not in candidate and not urllib.parse.urlsplit(candidate).query:
                        source_url = candidate
                except ValueError:
                    pass
        records.append({'title_en': work_title, 'composer_en': composer, 'source_url': source_url,
                        'page_url': page_url, 'wp_id': item['id'], 'origin': 'page', 'page_title': title, 'assets': assets,
                        'category_ids': [category_id], 'unverified_source_urls': info_urls})
    return records


class Blocked(RuntimeError):
    pass


class Client:
    def __init__(self, config):
        self.config = config
        self.lock = threading.Lock()
        self.next_request = 0.0
        self.stopped = threading.Event()
        self.robot = None
        self.sessions = threading.local()

    def get(self, url):
        url = canonical_url(url)
        if self.robot and not self.robot.can_fetch(self.config['user_agent'], url):
            raise Blocked('robots.txt disallows this URL')
        if self.stopped.is_set():
            raise Blocked('source requests stopped after an access restriction')
        with self.lock:
            pause = self.next_request - time.monotonic()
            if pause > 0:
                time.sleep(pause)
            if self.stopped.is_set():
                raise Blocked('source requests stopped after an access restriction')
            self.next_request = time.monotonic() + self.config['minimum_request_interval_seconds']
        if not hasattr(self.sessions, 'session'):
            self.sessions.session = requests.Session()
            self.sessions.session.headers.update({'User-Agent': self.config['user_agent'], 'Accept-Encoding': 'identity'})
        response = None
        try:
            final_url = url
            for redirect in range(6):
                if self.stopped.is_set():
                    raise Blocked('source requests stopped after an access restriction')
                response = self.sessions.session.get(final_url, timeout=self.config['request_timeout_seconds'], allow_redirects=False, stream=True)
                if response.status_code in {301, 302, 303, 307, 308}:
                    target = canonical_url(response.headers.get('Location', ''), final_url)
                    response.close()
                    final_url = target
                    continue
                break
            else:
                raise ValueError('too many redirects')
            if response.status_code in BLOCKED_CODES:
                self.stopped.set()
                raise Blocked(f'HTTP {response.status_code}; human action or later retry required')
            if response.status_code != 200:
                raise urllib.error.HTTPError(final_url, response.status_code, response.reason, response.headers, None)
            chunks, size = [], 0
            for chunk in response.iter_content(1024 * 1024):
                size += len(chunk)
                if size > 512 * 1024 * 1024:
                    raise ValueError('response exceeds 512 MiB limit')
                chunks.append(chunk)
            body = b''.join(chunks)
            headers = dict(response.headers.items())
            expected = response.headers.get('Content-Length')
            if expected is not None and len(body) != int(expected):
                raise ValueError('response length differs from Content-Length')
            is_html = body[:500].lstrip().lower().startswith((b'<!doctype html', b'<html'))
            if is_html and any(token in body[:20000].lower() for token in [b'cf-chl-', b'cf-challenge', b'just a moment...', b'verify you are human']):
                self.stopped.set()
                raise Blocked('human verification page; stopped without attempting to solve it')
            return body, headers, final_url
        except requests.RequestException as exc:
            raise urllib.error.URLError(str(exc)) from exc
        finally:
            if response is not None:
                response.close()


def cache_request(client, directory, key, url):
    path = directory / f'{key}.json'
    if path.exists():
        data = json.loads(path.read_text())
        if data['url'] != url:
            raise ValueError('cached request URL differs from frozen request')
        if hashlib.sha256(data['body'].encode('utf-8')).hexdigest() != data['sha256']:
            raise ValueError('cached response body differs from frozen SHA-256')
        return data
    body, headers, final_url = client.get(url)
    decoded = body.decode('utf-8-sig')
    data = {'url': url, 'final_url': final_url, 'fetched_at': now(), 'sha256': hashlib.sha256(decoded.encode()).hexdigest(), 'headers': headers, 'body': decoded}
    atomic_json(path, data)
    return data


def discover(root, config, client):
    base = root / 'sources/classclef'
    base.mkdir(parents=True, exist_ok=True)
    snapshot_file = base / 'snapshot.json'
    snapshot = json.loads(snapshot_file.read_text()) if snapshot_file.exists() else {
        'id': 'classclef-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
        'frozen_at': now(), 'discovery_complete': False, 'scope': config['scope'], 'endpoint_totals': {}, 'errors': [],
        'configuration_sha256': hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()}
    snapshot.setdefault('configuration_sha256', hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest())
    snapshot['adapter_version'] = 2
    atomic_json(snapshot_file, snapshot)
    cache = base / 'snapshots' / snapshot['id']
    robots = cache_request(client, cache, 'robots', config['base_url'] + 'robots.txt')
    client.robot = urllib.robotparser.RobotFileParser()
    client.robot.parse(robots['body'].splitlines())
    sitemap = cache_request(client, cache, 'sitemap_index', config['base_url'] + 'sitemap_index.xml')
    sitemap_index = ET.fromstring(sitemap['body'])
    sitemap_pages = set()
    for loc in sitemap_index.findall('{*}sitemap/{*}loc'):
        url = canonical_url(loc.text)
        if not re.search(r'/(?:post|page)-sitemap\d*\.xml$', url):
            continue
        child = cache_request(client, cache, Path(urllib.parse.urlsplit(url).path).stem, url)
        xml = ET.fromstring(child['body'])
        sitemap_pages.update(canonical_url(loc.text) for loc in xml.findall('{*}url/{*}loc'))
    records, page_items, all_urls = [], [], set()
    link_counts = Counter()
    for kind in ['pages', 'posts']:
        fields = 'id,link,title,content'
        first_url = f"{config['api_base']}{kind}?per_page=100&page=1&orderby=id&order=asc&_fields={fields}"
        first = cache_request(client, cache, f'{kind}-0001', first_url)
        headers = {k.lower(): v for k, v in first['headers'].items()}
        total = int(headers['x-wp-total'])
        count = int(headers['x-wp-totalpages'])
        frozen = snapshot['endpoint_totals'].get(kind)
        if frozen and frozen != {'items': total, 'pages': count}:
            raise ValueError('upstream count differs from frozen snapshot')
        snapshot['endpoint_totals'][kind] = {'items': total, 'pages': count}
        atomic_json(snapshot_file, snapshot)
        items = []
        for page in range(1, count + 1):
            url = f"{config['api_base']}{kind}?per_page=100&page={page}&orderby=id&order=asc&_fields={fields}"
            try:
                result = first if page == 1 else cache_request(client, cache, f'{kind}-{page:04}', url)
                response_headers = {k.lower(): v for k, v in result['headers'].items()}
                if int(response_headers['x-wp-total']) != total:
                    raise ValueError('upstream drift during frozen snapshot')
                batch = json.loads(result['body'])
                if not isinstance(batch, list):
                    raise ValueError('API response is not a list')
                items.extend(batch)
                print(f'discover {kind} {page}/{count} ({len(items)}/{total})', flush=True)
            except Exception as exc:
                snapshot['errors'] = [f'{kind} page {page}: {exc}']
                atomic_json(snapshot_file, snapshot)
                raise
        if len(items) != total or len({x['id'] for x in items}) != total:
            raise ValueError('frozen API count or unique identity mismatch')
        for item in items:
            all_urls.add(canonical_url(item['link']))
            parsed = parse_page(item, kind)
            all_links = [a for link in BeautifulSoup(item['content']['rendered'], 'html.parser').find_all('a', href=True) if (a := asset_from_link(link))]
            for link in all_links:
                link_counts['score_links' if link['format'] == 'PDF' else 'companion_links'] += 1
                if link.get('url_extension_mismatch'):
                    link_counts['companion_extension_mismatches'] += 1
            if kind == 'pages' and parsed:
                page_items.append({'id': f"page:{item['id']}", 'name': text(item['title']['rendered']),
                                   'name_zh': '', 'kind': 'unspecified', 'family': 'classclef',
                                   'source_url': canonical_url(item['link'])})
            raw_pdf_urls = {a['source_url'] for link in BeautifulSoup(item['content']['rendered'], 'html.parser').find_all('a', href=True) if (a := asset_from_link(link)) and a['format'] == 'PDF'}
            parsed_pdf_urls = {a['source_url'] for row in parsed for a in row['assets'] if a['format'] == 'PDF'}
            if raw_pdf_urls != parsed_pdf_urls:
                raise ValueError(f'PDF link coverage differs for {item["link"]}: {sorted(raw_pdf_urls - parsed_pdf_urls)}')
            records.extend(parsed)
    missing = sorted(sitemap_pages - all_urls)
    snapshot.update({'discovery_complete': not missing, 'page_count': len(all_urls), 'sitemap_page_count': len(sitemap_pages),
                     'sitemap_pages_missing_from_api': missing, 'discovered_at': now(), 'errors': [], 'score_link_coverage_verified': True, 'source_link_counts': dict(link_counts), 'source_score_rows': len(records)})
    expected_pdf_urls = {a['source_url'] for row in records for a in row['assets'] if a['format'] == 'PDF'}
    catalog = make_catalog(records, page_items, snapshot)
    normalize_source_pages(catalog, all_urls)
    catalog_pdf_urls = {a['source_url'] for work in catalog['works'] for a in work['assets'] if a['format'] == 'PDF'}
    if expected_pdf_urls != catalog_pdf_urls:
        raise ValueError('merged catalog PDF/archive coverage differs from raw source records')
    snapshot['merged_score_link_coverage_verified'] = True
    old = json.loads((base / 'catalog.json').read_text()) if (base / 'catalog.json').exists() else {}
    old_assets = {a['source_url']: a for w in old.get('works', []) for a in w['assets']}
    for work in catalog['works']:
        for asset in work['assets']:
            old_asset = old_assets.get(asset['source_url'])
            if old_asset and asset['format'] == 'PDF' and old_asset['format'] == 'PDF' and asset.get('container') == old_asset.get('container'):
                asset.update({key: value for key, value in old_asset.items() if key in DOWNLOAD_KEYS})
    reuse_external_assets(root, catalog)
    update_stats(catalog)
    atomic_json(base / 'catalog.json', catalog)
    atomic_json(snapshot_file, snapshot)
    print(json.dumps(catalog['stats'], ensure_ascii=False), flush=True)
    return catalog


def make_catalog(records, categories, snapshot):
    # An explicit PDF listing elsewhere disambiguates contradictory source icons.
    known_pdf_urls = {a['source_url'] for row in records for a in row['assets'] if a['format'] == 'PDF'}
    for row in records:
        for asset in row['assets']:
            if asset['source_url'] in known_pdf_urls and asset['format'] != 'PDF':
                asset['original_declared_format'] = asset['format']
                asset['format'] = 'PDF'
                asset['label'] = 'PDF'
                asset['status'] = 'external_reference' if asset.get('external') else 'pending'
    # Shared bytes alone do not identify a musical work: source pages contain wrong links.
    # Merge only an explicit common work page or equal displayed title, AND shared PDF.
    parents = list(range(len(records)))
    def find(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i
    owner = {}
    page_titles = {i: ({r['wp_id']: {r['title_en'].casefold()}} if r['origin'] == 'page' else {}) for i, r in enumerate(records)}
    composer_names = {i: ({r['composer_en'].casefold().strip()} if r['composer_en'].strip() else set()) for i, r in enumerate(records)}
    for i, record in enumerate(records):
        for asset in record['assets']:
            if asset['format'] not in SCORE_FORMATS:
                continue
            url = asset['source_url']
            candidates = owner.setdefault(url, [])
            for previous in candidates:
                other = records[previous]
                same_title = record['title_en'].casefold() == other['title_en'].casefold()
                left_composer = record['composer_en'].casefold().strip()
                right_composer = other['composer_en'].casefold().strip()
                same_title = same_title and (left_composer == right_composer or not left_composer or not right_composer)
                same_post = record['source_url'].rstrip('/') == other['source_url'].rstrip('/') and (record['origin'] == 'post' or other['origin'] == 'post')
                if same_title or same_post:
                    left, right = find(i), find(previous)
                    conflicting = any(page_titles[left][key] != page_titles[right][key] for key in page_titles[left].keys() & page_titles[right].keys())
                    composer_conflict = not same_post and composer_names[left] and composer_names[right] and composer_names[left].isdisjoint(composer_names[right])
                    if not conflicting and not composer_conflict:
                        parents[left] = right
                        composer_names[right].update(composer_names[left])
                        for key, values in page_titles[left].items():
                            page_titles[right].setdefault(key, set()).update(values)
            candidates.append(i)
    groups = {}
    for i, record in enumerate(records):
        groups.setdefault(find(i), []).append(record)
    works = []
    uncategorized = False
    for rows in groups.values():
        # A dedicated post is the strongest source for composer attribution.
        rows.sort(key=lambda r: (r['origin'] != 'post', not bool(r['composer_en']), r['source_url']))
        chosen = rows[0]
        assets = {}
        for row in rows:
            for asset in row['assets']:
                current = assets.setdefault(asset['source_url'], dict(asset, source_pages=[], declared_formats=[]))
                current['declared_formats'] = sorted(set(current['declared_formats'] + [asset['format']] + ([asset['original_declared_format']] if asset.get('original_declared_format') else [])))
                if asset['format'] == 'PDF':
                    current['format'] = 'PDF'
                    current['status'] = 'external_reference' if asset.get('external') else 'pending'
                    if asset.get('container'):
                        current['container'] = asset['container']
                current['source_pages'] = sorted(set(current['source_pages'] + [row['page_url']]))
                if asset['label'] in {'TAB', 'NOTE'}:
                    current['label'] = asset['label']
        asset_list = sorted(assets.values(), key=lambda a: (a['format'] != 'PDF', a['source_url']))
        post_ids = [row['wp_id'] for row in rows if row['origin'] == 'post']
        identity = ('post:' + str(min(post_ids))) if post_ids else ('page:' + str(chosen['wp_id']) + '\n' + chosen['title_en'] + '\n' + min(a['source_url'] for a in asset_list if a['format'] in SCORE_FORMATS))
        category_ids = sorted({c for row in rows for c in row['category_ids']})
        if not category_ids:
            category_ids = ['posts-only']
            uncategorized = True
        composer = chosen['composer_en'] or next((r['composer_en'] for r in rows if r['composer_en']), '')
        works.append({'id': 'classclef:' + hashlib.sha256(identity.encode()).hexdigest()[:24],
                      'title_en': chosen['title_en'], 'title_zh': '', 'composer_en': composer, 'composer_zh': '',
                      'title_aliases': sorted({r['title_en'] for r in rows} - {chosen['title_en']}),
                      'source_id': 'classclef', 'source_url': chosen['source_url'],
                      'source_urls': sorted({r['source_url'] for r in rows} | {r['page_url'] for r in rows} | {u for r in rows for u in r.get('unverified_source_urls', [])}),
                      'source_records': [{'wp_id': r['wp_id'], 'kind': r['origin'], 'source_url': r['page_url'],
                                          'title': r['title_en'], 'composer': r['composer_en'], 'page_title': r.get('page_title', ''),
                                          'asset_source_urls': sorted({a['source_url'] for a in r['assets']})} for r in rows],
                      'category_ids': category_ids, 'formats': sorted({a['format'] for a in asset_list}),
                      'instrumentation_status': 'unverified', 'translation_status': 'untranslated',
                      'arrangement_status': 'unverified', 'resource_type': 'reference' if any('glossary' in r.get('page_title', '').lower() for r in rows) else 'score', 'assets': asset_list})
    if uncategorized:
        categories.append({'id': 'posts-only', 'name': 'Additional indexed scores', 'name_zh': '其他已索引乐谱',
                           'kind': 'unspecified', 'family': 'classclef', 'source_url': 'https://www.classclef.com/'})
    return {'schema_version': 1, 'source_id': 'classclef', 'snapshot': snapshot,
            'categories': sorted(categories, key=lambda c: c['name'].casefold()),
            'works': sorted(works, key=lambda w: (w['composer_en'].casefold(), w['title_en'].casefold(), w['id']))}




def normalize_source_pages(catalog, known_urls):
    folded = {}
    for url in known_urls:
        folded.setdefault(url.casefold().rstrip('/'), set()).add(url)
    changes = 0
    for work in catalog['works']:
        original = work['source_url']
        if original not in known_urls:
            candidates = folded.get(original.casefold().rstrip('/'), set())
            if len(candidates) == 1:
                work['source_url'] = next(iter(candidates))
            else:
                work['source_url'] = next(r['source_url'] for r in work['source_records'] if r['source_url'] in known_urls)
            changes += 1
        work['unverified_source_urls'] = sorted(u for u in work['source_urls'] if u not in known_urls)
        if work['source_url'] not in known_urls:
            raise ValueError('default source URL is not in the frozen source page inventory')
    catalog['snapshot']['public_source_pages_verified'] = True
    catalog['snapshot']['source_page_defaults_normalized'] = changes


def approved_imslp_categories(root):
    names = set()
    for filename in ['categories.json', 'mixed_categories.json']:
        path = root / 'config' / filename
        if path.exists():
            names.update(c['name'] for c in json.loads(path.read_text())['categories'])
    return names


def reuse_record(root, manifest_path, record):
    category = manifest_path.parent.parent
    if manifest_path != root / category.name / 'metadata/score_manifest.json' or category.name not in approved_imslp_categories(root):
        raise ValueError('external reuse category is not approved')
    exclusions_path = root / 'config/score_exclusions.json'
    exclusions = json.loads(exclusions_path.read_text()).get('entries', []) if exclusions_path.exists() else []
    if any(e['category'] == category.name and str(e['work_id']) == str(record['work_id']) and e['filename'] == record['filename'] for e in exclusions):
        raise ValueError('existing IMSLP record is explicitly excluded')
    relative = Path(record['relative_path'])
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('unsafe existing IMSLP relative path')
    path = category / relative
    if path.is_symlink() or not path.resolve().is_relative_to(category.resolve()):
        raise ValueError('unsafe existing IMSLP PDF path')
    evidence = validate_pdf(path.read_bytes(), record['expected_size'])
    if not record.get('sha1_imslp') or evidence['sha1'] != record['sha1_imslp']:
        raise ValueError('existing IMSLP file does not match its source SHA-1')
    return dict(evidence, local_path=path.relative_to(root).as_posix(), status=SUCCESS,
                verified_at=now(), storage_source='imslp',
                reused_from_manifest=manifest_path.relative_to(root).as_posix(),
                imslp_file_id=str(record['file_id']), imslp_work_id=str(record['work_id']),
                source_sha1=record['sha1_imslp'], source_sha1_status='verified_imslp_manifest', last_error=None)


def reuse_external_assets(root, catalog):
    external = {a['source_url']: a for work in catalog['works'] for a in work['assets'] if a.get('external') and a['format'] == 'PDF'}
    if not external:
        return
    manifests = []
    for name in sorted(approved_imslp_categories(root)):
        path = root / name / 'metadata/score_manifest.json'
        if path.exists():
            payload = json.loads(path.read_text())
            manifests.append((path, payload.get('items', []) if isinstance(payload, dict) else payload))
    resolved = {}
    for url, asset in external.items():
        parsed = urllib.parse.urlsplit(url)
        if not parsed.hostname or not (parsed.hostname == 'imslp.org' or parsed.hostname.endswith('.imslp.org')):
            continue
        match = re.fullmatch(r'IMSLP([0-9]+)-(.+\.pdf)', urllib.parse.unquote(Path(parsed.path).name), re.I)
        if not match:
            continue
        for manifest_path, records in manifests:
            record = next((r for r in records if str(r.get('file_id')) == match[1] and r.get('filename') == match[2]), None)
            if record is None:
                continue
            try:
                resolved[url] = reuse_record(root, manifest_path, record)
                break
            except Exception as exc:
                asset['last_error'] = f'local IMSLP reuse not verified: {exc}'
    for work in catalog['works']:
        for asset in work['assets']:
            if asset['source_url'] in resolved:
                asset.update(resolved[asset['source_url']])


def update_stats(catalog):
    assets = {a['source_url']: a for w in catalog['works'] for a in w['assets'] if a['format'] == 'PDF'}
    statuses = Counter(a['status'] for a in assets.values())
    catalog['stats'] = {'works': len(catalog['works']), 'categories': len(catalog['categories']),
                        'resource_type_counts': dict(Counter(w.get('resource_type', 'score') for w in catalog['works'])),
                        'works_with_archives': sum(any(a.get('container') == 'ZIP' and a['format'] == 'PDF' for a in w['assets']) for w in catalog['works']),
                        'category_memberships': sum(len(w['category_ids']) for w in catalog['works']),
                        'pdf_source_urls': len(assets), 'pdf_status_counts': dict(sorted(statuses.items())),
                        'unique_physical_pdfs': len({m['sha256'] for a in assets.values() if a['status'] == SUCCESS for m in physical_members(a)}),
                        'downloaded_bytes': sum({m['sha256']: m['size'] for a in assets.values() if a['status'] == SUCCESS for m in physical_members(a)}.values()),
                        'score_archives': sum(a.get('container') == 'ZIP' for a in assets.values()),
                        'archive_status_counts': dict(Counter(a['status'] for a in assets.values() if a.get('container') == 'ZIP')),
                        'verified_archive_pdf_memberships': sum(len(a.get('members', [])) for a in assets.values() if a.get('container') == 'ZIP' and a['status'] == SUCCESS),
                        'reused_imslp_pdfs': len({a['sha256'] for a in assets.values() if a.get('storage_source') == 'imslp' and a['status'] == SUCCESS}),
                        'own_physical_pdfs': len({m['sha256'] for a in assets.values() if a['status'] == SUCCESS and a.get('storage_source') != 'imslp' for m in physical_members(a)}),
                        'format_work_counts': dict(Counter(f for w in catalog['works'] for f in w['formats'])),
                        'works_without_pdf': sum('PDF' not in w['formats'] for w in catalog['works']),
                        'works_with_pdf_but_no_local_pdf': sum('PDF' in w['formats'] and not any(a['format'] == 'PDF' and a['status'] == SUCCESS for a in w['assets']) for w in catalog['works']),
                        'partially_available_works': sum(any(a['format'] == 'PDF' and a['status'] == SUCCESS for a in w['assets']) and any(a['format'] == 'PDF' and a['status'] != SUCCESS for a in w['assets']) for w in catalog['works']),
                        'works_with_local_pdf': sum(any(a['status'] == SUCCESS for a in w['assets']) for w in catalog['works'])}
    catalog['snapshot']['pdf_status_counts'] = catalog['stats']['pdf_status_counts']
    catalog['snapshot']['downloads_complete'] = all(a['status'] == SUCCESS for a in assets.values())


class _PdfReaderWithNullEncryption(PdfReader):
    null_encryption_compatibility = False

    def _handle_encryption(self, password):
        entry = self.trailer.get('/Encrypt')
        resolved = entry.get_object() if hasattr(entry, 'get_object') else entry
        if resolved is None or isinstance(resolved, NullObject):
            # pypdf 6.x otherwise crashes before the caller can inspect the trailer.
            # PDF null means absent; only the in-memory dictionary is normalized.
            del self.trailer['/Encrypt']
            self.null_encryption_compatibility = True
            return
        super()._handle_encryption(password)


def validate_pdf(data: bytes, expected_size=None):
    if not data.startswith(b'%PDF-'):
        raise ValueError('not a PDF header')
    if expected_size is not None and len(data) != expected_size:
        raise ValueError('expected byte size mismatch')
    if b'%%EOF' not in data[-2048:]:
        raise ValueError('PDF end marker missing; possibly partial response')
    reader = _PdfReaderWithNullEncryption(io.BytesIO(data))
    encryption = 'null_encrypt_compatibility' if reader.null_encryption_compatibility else 'none'
    if reader.is_encrypted:
        entry = reader.trailer.get('/Encrypt')
        resolved = entry.get_object() if hasattr(entry, 'get_object') else entry
        if resolved is None or isinstance(resolved, NullObject):
            # Null Encrypt is not encryption; normalize only the in-memory parser.
            del reader.trailer['/Encrypt']
            encryption = 'null_encrypt_compatibility'
        elif reader.decrypt(''):
            # This is normal opening with the empty user password; original bytes
            # and the PDF's owner permissions are preserved without modification.
            encryption = 'empty_user_password'
        else:
            raise ValueError('PDF requires a non-empty user password')
    pages = len(reader.pages)
    if pages == 0:
        raise ValueError('PDF contains no pages')
    for page in reader.pages:
        _ = page.mediabox
    return {'sha256': hashlib.sha256(data).hexdigest(), 'sha1': hashlib.sha1(data).hexdigest(), 'size': len(data), 'pages': pages, 'pdf_encryption': encryption}


def physical_members(asset):
    return asset.get('members', []) if asset.get('container') == 'ZIP' else [asset]


def store_pdf(root, base, body):
    evidence = validate_pdf(body)
    target = base / 'objects' / evidence['sha256'][:2] / (evidence['sha256'] + '.pdf')
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.is_symlink() or hashlib.sha256(target.read_bytes()).hexdigest() != evidence['sha256']:
            raise ValueError('existing immutable object differs from its hash')
    else:
        temporary = target.with_name(target.name + '.' + str(threading.get_ident()) + '.part')
        with temporary.open('wb') as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, target)
            target.chmod(0o444)
        except FileExistsError:
            if target.is_symlink() or hashlib.sha256(target.read_bytes()).hexdigest() != evidence['sha256']:
                raise ValueError('existing immutable object differs from its hash')
        finally:
            temporary.unlink(missing_ok=True)
    return dict(evidence, local_path=target.relative_to(root).as_posix())


def zip_pdf_members(body):
    """Read PDF members in memory; archive filenames never become filesystem paths."""
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        infos = archive.infolist()
        if len(infos) > 1000 or sum(i.file_size for i in infos) > 500 * 1024 * 1024:
            raise ValueError('archive exceeds safety limits')
        names = set()
        members = []
        ignored = []
        for info in infos:
            name = info.filename.replace('\\', '/')
            path = Path(name)
            if name.startswith('/') or '..' in path.parts or re.match(r'^[A-Za-z]:', name):
                raise ValueError('unsafe archive member path')
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('archive symlinks are not allowed')
            if info.flag_bits & 1:
                raise ValueError('encrypted archive requires manual review')
            if name in names:
                raise ValueError('duplicate archive member name')
            names.add(name)
            if info.is_dir():
                continue
            if not name.lower().endswith('.pdf'):
                ignored.append(name)
                continue
            member_body = archive.read(info)
            validate_pdf(member_body, info.file_size)
            members.append((name, member_body))
        if not members:
            raise ValueError('score archive contains no valid PDF members')
        return members, ignored


def download_one(root, base, asset, client):
    url = asset['source_url']
    part = base / '.parts' / (hashlib.sha256(url.encode()).hexdigest() + '.part')
    try:
        body, headers, final_url = client.get(url)
        content_type = next((v for k, v in headers.items() if k.lower() == 'content-type'), '')
        if 'html' in content_type.lower():
            raise ValueError('HTML response instead of a score')
        part.parent.mkdir(parents=True, exist_ok=True)
        with part.open('wb') as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        if asset.get('container') == 'ZIP':
            members, ignored = zip_pdf_members(body)
            evidence = {'members': [dict(store_pdf(root, base, member), name=name) for name, member in members],
                        'archive_sha256': hashlib.sha256(body).hexdigest(),
                        'archive_sha1': hashlib.sha1(body).hexdigest(), 'archive_size': len(body),
                        'ignored_archive_members': ignored}
        else:
            evidence = store_pdf(root, base, body)
        expected_length = next((v for k, v in headers.items() if k.lower() == 'content-length'), None)
        return dict(evidence, status=SUCCESS, verified_at=now(), final_url=final_url,
                    http_content_length=int(expected_length) if expected_length else None,
                    source_sha1=None, source_sha1_status='not_published', last_error=None)
    except Blocked as exc:
        return {'status': 'access_blocked', 'last_error': str(exc), 'attempted_at': now()}
    except urllib.error.HTTPError as exc:
        return {'status': 'not_found' if exc.code in {404, 410} else 'retryable', 'last_error': f'HTTP {exc.code}', 'attempted_at': now()}
    except (TimeoutError, OSError, urllib.error.URLError) as exc:
        return {'status': 'retryable', 'last_error': str(exc), 'attempted_at': now()}
    except Exception as exc:
        return {'status': 'invalid_pdf', 'last_error': str(exc), 'attempted_at': now()}
    finally:
        if part.exists():
            part.unlink()


def download(root, config, client, limit=None, retry_failed=False):
    base = root / 'sources/classclef'
    catalog = json.loads((base / 'catalog.json').read_text())
    robots_file = base / 'snapshots' / catalog['snapshot']['id'] / 'robots.json'
    if robots_file.exists():
        client.robot = urllib.robotparser.RobotFileParser()
        client.robot.parse(json.loads(robots_file.read_text())['body'].splitlines())
    state_file = base / 'download-state.json'
    states = json.loads(state_file.read_text()) if state_file.exists() else {}
    assets = {}
    for work in catalog['works']:
        for asset in work['assets']:
            if asset['format'] == 'PDF':
                if asset['source_url'] in states:
                    asset.update(states[asset['source_url']])
                assets.setdefault(asset['source_url'], []).append(asset)
    queue = []
    for url, refs in assets.items():
        asset = refs[0]
        if asset['status'] == SUCCESS:
            members = physical_members(asset)
            if members and all((root / member['local_path']).is_file() and (root / member['local_path']).stat().st_size == member['size'] for member in members):
                continue
            asset['status'] = 'pending'
        if asset['status'] == 'pending' or (retry_failed and asset['status'] in {'retryable', 'not_found', 'invalid_pdf', 'access_blocked'}):
            queue.append(asset)
    if limit:
        queue = queue[:limit]
    started = time.monotonic()
    done = 0
    def save():
        update_stats(catalog)
        atomic_json(state_file, states)
        atomic_json(base / 'catalog.json', catalog)
    # Keep only max_workers futures in flight; a block immediately halts new requests.
    iterator = iter(queue)
    with concurrent.futures.ThreadPoolExecutor(max_workers=config['max_workers']) as pool:
        futures = {}
        for _ in range(config['max_workers']):
            asset = next(iterator, None)
            if asset:
                futures[pool.submit(download_one, root, base, asset, client)] = asset
        while futures:
            completed, _ = concurrent.futures.wait(futures, return_when=concurrent.futures.FIRST_COMPLETED)
            for future in completed:
                asset = futures.pop(future)
                result = future.result()
                states[asset['source_url']] = result
                for ref in assets[asset['source_url']]:
                    ref.update(result)
                done += 1
                if done % 25 == 0 or result['status'] != SUCCESS:
                    print(f"download {done}/{len(queue)} {result['status']} elapsed={time.monotonic()-started:.1f}s", flush=True)
                if done % 100 == 0 or result['status'] == 'access_blocked':
                    save()
                if not client.stopped.is_set():
                    next_asset = next(iterator, None)
                    if next_asset:
                        futures[pool.submit(download_one, root, base, next_asset, client)] = next_asset
    save()
    print(json.dumps(catalog['stats']), flush=True)
    return catalog


def verify(root):
    base = root / 'sources/classclef'
    catalog = json.loads((base / 'catalog.json').read_text())
    errors = []
    quarantined = []
    snapshot_dir = base / 'snapshots' / catalog['snapshot']['id']
    if snapshot_dir.exists():
        for cache_file in sorted(snapshot_dir.glob('*.json')):
            try:
                cached = json.loads(cache_file.read_text())
                if hashlib.sha256(cached['body'].encode('utf-8')).hexdigest() != cached['sha256']:
                    raise ValueError('cached response SHA-256 mismatch')
            except Exception as exc:
                errors.append(f'{cache_file.relative_to(root)}: {exc}')
    expected = {}
    reused_paths = set()
    owners = {}
    assets = {}
    bad_urls = set()
    for work in catalog['works']:
        if work['instrumentation_status'] != 'unverified':
            errors.append('unexpected unreviewed instrumentation status')
        for asset in work['assets']:
            if asset['format'] != 'PDF':
                continue
            assets[asset['source_url']] = asset
            if asset['status'] != SUCCESS:
                continue
            for member in physical_members(asset):
                path = root / member['local_path']
                canonical = base / 'objects' / member['sha256'][:2] / f"{member['sha256']}.pdf"
                if member.get('storage_source') == 'imslp':
                    try:
                        manifest_path = root / member['reused_from_manifest']
                        payload = json.loads(manifest_path.read_text())
                        records = payload.get('items', []) if isinstance(payload, dict) else payload
                        record = next(r for r in records if str(r.get('file_id')) == member['imslp_file_id'] and str(r.get('work_id')) == member['imslp_work_id'])
                        reused = reuse_record(root, manifest_path, record)
                        if any(reused[key] != member[key] for key in ['local_path', 'sha1', 'sha256', 'size', 'pages']):
                            raise ValueError('reuse evidence differs from source manifest')
                        reused_paths.add(path)
                        canonical = path
                    except Exception as exc:
                        errors.append(f'IMSLP reuse verification failed: {exc}')
                        bad_urls.add(asset['source_url'])
                        continue
                if path != canonical:
                    errors.append(f'noncanonical local path: {work["id"]}')
                    bad_urls.add(asset['source_url'])
                    continue
                expected[path] = member
                owners.setdefault(path, set()).add(asset['source_url'])
    for i, (path, member) in enumerate(expected.items(), 1):
        try:
            if path.is_symlink():
                raise ValueError('physical PDF object cannot be a symlink')
            evidence = validate_pdf(path.read_bytes(), member['size'])
            for key in ['sha256', 'sha1', 'size', 'pages']:
                if evidence[key] != member[key]:
                    raise ValueError(f'{key} differs from manifest')
        except Exception as exc:
            errors.append(f'{path.relative_to(root)}: {exc}')
            bad_urls.update(owners.get(path, set()))
            if path.is_file() and not path.is_symlink() and path.is_relative_to(base / 'objects'):
                quarantine = base / 'quarantine' / (path.stem + '-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.pdf')
                quarantine.parent.mkdir(parents=True, exist_ok=True)
                path.replace(quarantine)
                quarantined.append({'original_path': path.relative_to(root).as_posix(), 'quarantine_path': quarantine.relative_to(root).as_posix(), 'reason': str(exc)})
        if i % 1000 == 0:
            print(f'verify {i}/{len(expected)}', flush=True)
    own_objects = set((base / 'objects').glob('*/*.pdf'))
    actual = own_objects | {path for path in reused_paths if path.is_file()}
    for path in sorted(actual - set(expected)):
        errors.append(f'unreferenced physical PDF: {path.relative_to(root)}')
    for path in sorted(set(expected) - actual):
        errors.append(f'missing physical PDF: {path.relative_to(root)}')
    if bad_urls:
        state_file = base / 'download-state.json'
        states = json.loads(state_file.read_text()) if state_file.exists() else {}
        for work in catalog['works']:
            for asset in work['assets']:
                if asset['source_url'] in bad_urls:
                    result = {'status': 'invalid_pdf', 'last_error': 'fresh verification failed; inspect verification.json', 'attempted_at': now()}
                    asset.update(result)
                    states.setdefault(asset['source_url'], {}).update(result)
        update_stats(catalog)
        atomic_json(state_file, states)
        atomic_json(base / 'catalog.json', catalog)
    update_stats(catalog)
    atomic_json(base / 'catalog.json', catalog)
    atomic_json(base / 'snapshot.json', catalog['snapshot'])
    statuses = dict(Counter(a['status'] for a in assets.values()))
    report = {'verified_at': now(), 'snapshot_id': catalog['snapshot']['id'], 'errors': errors,
              'quarantined': quarantined, 'manifest_objects': len(expected), 'physical_pdfs': len(actual),
              'own_physical_pdfs': len(own_objects), 'reused_imslp_pdfs': len(reused_paths), 'score_source_urls': len(assets),
              'pdf_status_counts': statuses, 'structural_valid': not errors,
              'complete': not errors and catalog['snapshot']['discovery_complete'] and all(a['status'] == SUCCESS for a in assets.values()),
              'limitations': ['Notation and musical accuracy not manually reviewed.', 'Exact instrumentation and original/arrangement status not reviewed.', 'ClassClef does not publish source hashes; recorded SHA-1/SHA-256 are local integrity evidence.']}
    atomic_json(base / 'verification.json', report)
    write_completion_report(base, catalog, report)
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return report



def write_completion_report(base, catalog, verification):
    all_assets = {a['source_url']: a for work in catalog['works'] for a in work['assets']}
    pdf_assets = {url: asset for url, asset in all_assets.items() if asset['format'] == 'PDF'}
    failures = []
    for url, asset in sorted(pdf_assets.items()):
        if asset['status'] == SUCCESS:
            continue
        error = asset.get('last_error', '') or ''
        category = {'not_found': 'upstream_not_found', 'access_blocked': 'access_restriction',
                    'retryable': 'transport_retryable', 'pending': 'not_attempted',
                    'external_reference': 'external_reference_not_reused'}.get(asset['status'], 'structural_parse_failure')
        if 'non-empty user password' in error:
            category = 'user_password_required'
        elif 'HTML response' in error or 'not a PDF header' in error:
            category = 'unexpected_source_content'
        failures.append({'source_url': url, 'status': asset['status'], 'category': category,
                         'error': error, 'container': asset.get('container', 'PDF'),
                         'work_ids': [w['id'] for w in catalog['works'] if any(a['source_url'] == url for a in w['assets'])]})
    report = {'generated_at': now(), 'snapshot': catalog['snapshot'], 'stats': catalog['stats'],
              'source_record_rows': sum(len(w['source_records']) for w in catalog['works']),
              'all_format_source_urls': len(all_assets), 'direct_pdf_source_urls': sum(a.get('container') != 'ZIP' for a in pdf_assets.values()),
              'archive_source_urls': sum(a.get('container') == 'ZIP' for a in pdf_assets.values()),
              'verified_archive_pdf_memberships': sum(len(a.get('members', [])) for a in pdf_assets.values() if a['status'] == SUCCESS),
              'download_scope': 'Public PDF links and PDF members of score ZIP archives; GPX/MIDI companion files indexed as metadata only.',
              'records_without_pdf': [{key: w[key] for key in ['id', 'title_en', 'composer_en', 'source_url', 'formats']} for w in catalog['works'] if 'PDF' not in w['formats']],
              'failures_by_category': dict(Counter(f['category'] for f in failures)), 'failures': failures,
              'verification': verification}
    atomic_json(base / 'completion-report.json', report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('command', choices=['discover', 'download', 'verify', 'all'])
    parser.add_argument('--limit', type=int)
    parser.add_argument('--retry-failed', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve()
    config = json.loads((root / 'config/classclef.json').read_text())
    client = Client(config)
    try:
        if args.command in {'discover', 'all'}:
            discover(root, config, client)
        if args.command in {'download', 'all'}:
            download(root, config, client, args.limit, args.retry_failed)
        if args.command in {'verify', 'all'}:
            report = verify(root)
            return 0 if report['complete'] else (2 if report['structural_valid'] else 1)
    except Blocked as exc:
        atomic_json(root / 'sources/classclef/blocked.json', {'at': now(), 'reason': str(exc)})
        print(f'STOPPED: {exc}', flush=True)
        return 2
    return 0
