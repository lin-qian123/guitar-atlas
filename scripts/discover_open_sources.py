#!/usr/bin/env python
"""Freeze resumable Mutopia and The Guitar School metadata, without score downloads.

Raw pages, request receipts, catalogs and logs stay under the ignored sources/ tree.
Cached successes are immutable within a snapshot. Use --refresh to explicitly start
a new discovery snapshot; existing verified asset receipts are preserved by URL.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import requests

from source_adapters import guitarschool, mutopia


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + '.part')
    with part.open('w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    part.replace(path)


class DiscoveryBlocked(RuntimeError):
    """Access requires a human or the upstream asks crawlers to stop."""


class CachedClient:
    def __init__(self, root, source_id, allowed_hosts, delay=0.8, refresh=False):
        self.root = Path(root) / 'sources' / source_id
        self.root.mkdir(parents=True, exist_ok=True)
        self.source_id = source_id
        self.allowed_hosts = set(allowed_hosts)
        self.delay = delay
        self.refresh = refresh
        self.last_request = 0
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'GuitarAtlas/1.0 (reproducible source-attributed guitar score catalog)'
        self.receipt_path = self.root / 'snapshots' / 'requests.json'
        self.receipts = json.loads(self.receipt_path.read_text()) if self.receipt_path.exists() else {}
        self.robots = {}
        state_path = self.root / 'discovery_state.json'
        state = json.loads(state_path.read_text()) if state_path.exists() and not refresh else {}
        self.frozen_at = state.get('frozen_at') or now()
        self.errors = []
        self.write_json('discovery_state.json', {'frozen_at': self.frozen_at, 'started_at': now(), 'status': 'running'})

    def write_json(self, relative, value):
        atomic_json(self.root / relative, value)

    def log(self, event, **fields):
        row = {'at': now(), 'source_id': self.source_id, 'event': event, **fields}
        with (self.root / 'discovery_log.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')

    def _request(self, url):
        remaining = self.delay - (time.monotonic() - self.last_request)
        if remaining > 0:
            time.sleep(remaining)
        self.last_request = time.monotonic()
        return self.session.get(url, timeout=(15, 60), allow_redirects=True)

    def check_robots(self, url):
        parsed = urlsplit(url)
        host = parsed.hostname
        if host in self.robots or host in {'api.github.com', 'raw.githubusercontent.com'}:
            robot = self.robots.get(host)
        else:
            robot_url = f'https://{host}/robots.txt'
            response = self._request(robot_url)
            if response.status_code in {401, 403, 429}:
                raise DiscoveryBlocked(f'robots request stopped: HTTP {response.status_code} {robot_url}')
            robot = urllib.robotparser.RobotFileParser(robot_url)
            robot.parse(response.text.splitlines() if response.status_code == 200 else [])
            self.robots[host] = robot
            self.write_json(f'snapshots/robots-{host}.json', {'url': robot_url, 'status_code': response.status_code, 'text': response.text, 'checked_at': now()})
            if response.status_code == 200:
                crawl_delay = robot.crawl_delay('GuitarAtlas') or robot.crawl_delay('*')
                if crawl_delay:
                    self.delay = max(self.delay, crawl_delay)
        if robot and not robot.can_fetch('GuitarAtlas', url):
            raise DiscoveryBlocked(f'robots disallows: {url}')

    def get(self, url):
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.hostname not in self.allowed_hosts
                or parsed.username or parsed.password or parsed.fragment or parsed.port not in (None, 443)):
            raise ValueError(f'unapproved metadata request: {url}')
        key = hashlib.sha256(url.encode()).hexdigest()
        path = self.root / 'snapshots' / 'pages' / (key + '.html')
        previous = self.receipts.get(url, {})
        if path.exists() and previous.get('status_code') == 200 and not self.refresh:
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != previous.get('sha256'):
                raise ValueError(f'cached snapshot integrity mismatch: {url}')
            return raw.decode('utf-8-sig')
        self.check_robots(url)
        try:
            response = self._request(url)
            final = urlsplit(response.url)
            if final.scheme != 'https' or final.hostname not in self.allowed_hosts:
                raise DiscoveryBlocked(f'unapproved metadata redirect: {response.url}')
            raw = response.content
            receipt = {'url': url, 'final_url': response.url, 'status_code': response.status_code,
                       'content_type': response.headers.get('Content-Type'), 'bytes': len(raw),
                       'sha256': hashlib.sha256(raw).hexdigest(), 'fetched_at': now()}
            self.receipts[url] = receipt
            self.write_json('snapshots/requests.json', self.receipts)
            self.log('request', **receipt)
            if response.status_code in {401, 403, 429}:
                raise DiscoveryBlocked(f'HTTP {response.status_code}: {url}')
            response.raise_for_status()
            # Known challenge-page language, not ordinary ASP.NET CSRF fields.
            lowered = response.text.lower()
            if any(marker in lowered for marker in ('verify you are human', 'cf-chl-', 'g-recaptcha', 'hcaptcha', 'attention required! | cloudflare')):
                raise DiscoveryBlocked(f'human verification required: {url}')
            path.parent.mkdir(parents=True, exist_ok=True)
            part = path.with_name(path.name + '.part')
            part.write_bytes(raw)
            part.replace(path)
            return raw.decode('utf-8-sig')
        except Exception as exc:
            self.errors.append({'url': url, 'error': str(exc), 'at': now()})
            self.log('error', url=url, error=str(exc))
            self.write_json('discovery_errors.json', self.errors)
            raise

    def json(self, url):
        return json.loads(self.get(url))

    def save_catalog(self, payload):
        path = self.root / 'catalog.json'
        old = json.loads(path.read_text()) if path.exists() else {}
        old_assets = {(row['id'], asset.get('source_url')): asset
                      for row in old.get('works', []) for asset in row.get('assets', [])}
        for row in payload['works']:
            for asset in row.get('assets', []):
                previous = old_assets.get((row['id'], asset.get('source_url')))
                if previous and previous.get('status') == 'verified' and asset.get('status') == 'pending':
                    receipt_fields = {'status', 'sha256', 'sha1', 'size', 'pages', 'local_path', 'members',
                                      'archive_sha256', 'archive_sha1', 'archive_size', 'verified_at',
                                      'final_url', 'http_content_length', 'source_sha1', 'source_sha1_status',
                                      'attempted_at', 'pdf_encryption', 'storage_source', 'downloaded_at'}
                    asset.update({key: value for key, value in previous.items() if key in receipt_fields})
        self.write_json('catalog.json', payload)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--source', choices=['mutopia', 'guitarschool', 'all'], default='all')
    parser.add_argument('--delay', type=float, default=0.8)
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--max-details', type=int, help='Limit detail reads for inspection; leaves discovery_complete false.')
    args = parser.parse_args(argv)
    if args.delay < 0.25:
        parser.error('--delay must be at least 0.25 seconds')
    exit_code = 0
    for adapter in [mutopia, guitarschool]:
        if args.source not in {'all', adapter.SOURCE_ID}:
            continue
        client = CachedClient(args.root, adapter.SOURCE_ID, adapter.REQUEST_HOSTS, args.delay, args.refresh)
        try:
            catalog = adapter.discover(client, max_details=args.max_details)
            client.save_catalog(catalog)
            status = ('complete' if catalog['snapshot']['discovery_complete'] else
                      'blocked' if catalog['snapshot'].get('blocked_reason') else 'partial')
            state = {'frozen_at': client.frozen_at, 'finished_at': now(), 'status': status, 'summary': catalog['summary']}
            client.write_json('discovery_state.json', state)
            print(json.dumps({'source_id': adapter.SOURCE_ID, **state}, ensure_ascii=False), flush=True)
            if status != 'complete':
                exit_code = 1
        except Exception as exc:
            client.write_json('discovery_state.json', {'frozen_at': client.frozen_at, 'stopped_at': now(),
                'status': 'blocked' if isinstance(exc, DiscoveryBlocked) else 'failed', 'error': str(exc)})
            print(json.dumps({'source_id': adapter.SOURCE_ID, 'error': str(exc)}, ensure_ascii=False), flush=True)
            exit_code = 1
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
