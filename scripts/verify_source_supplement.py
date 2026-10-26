#!/usr/bin/env python
"""Verify an append-only source supplement against its frozen prior publication."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote

from catalog_payload import unpack_payload
from render_offline_site import offline_input_fingerprint
from source_adapters.additional import atomic_json, utcnow
from verify_musescore_expansion import decode_offline, node_offline_adapter
from verify_musescore_instrumentation import check_local_link


def require(condition, message):
    if not condition:
        raise ValueError(message)


def decode_bytes(body: bytes) -> dict:
    found = re.findall(rb'<script type="application/json" id="offline-data">(.*?)</script>', body, re.S)
    require(len(found) == 1, 'baseline HTML needs exactly one offline snapshot')
    return unpack_payload(json.loads(found[0]))


def preserved_records(before: list[dict], after: list[dict], label: str) -> int:
    old, current = {row['id']: row for row in before}, {row['id']: row for row in after}
    require(len(old) == len(before) and len(current) == len(after), label + ': duplicate identities')
    require(set(old).issubset(current), label + ': old record missing')
    for identity, row in old.items():
        require(row == current[identity], label + ': previously published fields changed: ' + str(identity))
    return len(old)



def verify_new_file_controls(native_rows: list[dict], offline_rows: dict) -> dict:
    controls = local_records = 0
    for native in native_rows:
        identity = native['id']
        expected = []
        for asset in native.get('assets', []):
            if asset.get('format') != 'PDF' or asset.get('status') != 'verified':
                continue
            members = asset['members'] if asset.get('container') == 'ZIP' else [asset]
            expected.extend(quote(member['local_path'], safe='/._-~()') for member in members)
        actual = [item['href'] for edition in offline_rows[identity]['local_editions']
                  for item in edition['files']]
        require(sorted(actual) == sorted(expected),
                'new verified PDF controls differ from native receipts: ' + identity)
        controls += len(actual)
        local_records += bool(actual)
    return {'records': len(native_rows), 'pdf_controls': controls, 'local_records': local_records}


def verify(root: Path, sources: list[str], full_report: Path) -> dict:
    root = root.resolve()
    basepath = root/'sources/source-expansion/baseline.zip'
    with zipfile.ZipFile(basepath) as archive:
        baseline = json.loads(archive.read('baseline.json'))
        for name, guard in baseline['members'].items():
            body = archive.read(name)
            require(len(body) == guard['size'] and hashlib.sha256(body).hexdigest() == guard['sha256'],
                    'frozen baseline member drift: ' + name)
        old_public = json.loads(archive.read('public_site/data/catalog.json'))
        old_offline = decode_bytes(archive.read('index.html'))['data']
        old_aliases = json.loads(archive.read('public_site/data/search-aliases.json'))
        old_ranking = json.loads(archive.read('public_site/data/ranking.json'))
        registry = json.loads((root/'config/sources.json').read_text())
        old_registry = json.loads(archive.read('config/sources.json'))
        old_policies = json.loads(archive.read('config/source_acquisition_policies.json'))
        current_policies = json.loads((root/'config/source_acquisition_policies.json').read_text())
        policy_map = {row['source_id']: row for row in current_policies['sources']}
        require(all(policy_map.get(row['source_id']) == row for row in old_policies['sources']),
                'earlier source policy/acquisition evidence changed')
        old_source_ids = set(baseline['old_sources'])
        require([row for row in registry['sources'] if row['id'] in old_source_ids]
                == old_registry['sources'], 'previously registered source configuration changed')
        require(set(sources) == {row['id'] for row in registry['sources']} - old_source_ids,
                'new registered source set differs from the reviewed supplement')
        for name, expected in baseline['protected_native_inputs'].items():
            require(hashlib.sha256((root/name).read_bytes()).hexdigest() == expected,
                    'previous native catalog/review input changed: ' + name)
        translation_entries = 0
        for name in baseline['members']:
            if not name.startswith('metadata/translations/'):
                continue
            before = archive.read(name)
            current = (root/name).read_bytes()
            if name.split('/')[-1] not in {'source_titles_zh.json', 'musicians_zh.json', 'categories_zh.json'}:
                require(current == before, 'frozen translation/compiler input changed: ' + name)
                continue
            old, new = json.loads(before), json.loads(current)
            require({k: v for k, v in old.items() if k != 'entries'}
                    == {k: v for k, v in new.items() if k != 'entries'}, 'translation header changed: ' + name)
            for key, value in old['entries'].items():
                require(new['entries'].get(key) == value, 'previous translation decision changed: ' + name + ':' + key)
                translation_entries += 1
            added = set(new['entries']) - set(old['entries'])
            require(all((key.split(':', 1)[0] if name.endswith('source_titles_zh.json') else key) in sources
                        for key in added), 'translation append escaped the selected new sources')
    public = json.loads((root/'public_site/data/catalog.json').read_text())
    compact = unpack_payload(json.loads((root/'public_site/data/catalog.compact.json').read_text()))
    require(compact == public, 'compact/canonical catalog mismatch')
    old_count = preserved_records(old_public['works'], public['works'], 'public')
    old_ids = {row['id'] for row in old_public['works']}
    additions = [row for row in public['works'] if row['id'] not in old_ids]
    require(additions and all(row['source_id'] in sources for row in additions), 'unexpected public additions')
    for key in ['categories', 'families', 'sources']:
        require(public[key][:len(old_public[key])] == old_public[key], 'old public structure changed: ' + key)
    require(all(edge in public['relationships'] for edge in old_public['relationships']), 'old relationship lost')
    wrapper, index_sha = decode_offline(root/'index.html')
    offline = wrapper['data']
    require(preserved_records(old_offline['works'], offline['works'], 'offline') == old_count,
            'baseline public/offline identity scope differs')
    preserved_records(old_offline['categories'], offline['categories'], 'offline category navigation')
    require(offline['offline_inputs'] == offline_input_fingerprint(root), 'offline source fingerprint stale')
    offline_rows = {row['id']: row for row in offline['works']}
    require(len(offline_rows) == len(public['works']), 'public/offline record scope differs')
    for row in public['works']:
        require({k: v for k, v in offline_rows[row['id']].items() if k != 'local_editions'} == row,
                'public/offline work fields differ: ' + row['id'])
    require([{k: v for k, v in row.items() if k != 'local_href'} for row in offline['categories']]
            == public['categories'], 'public/offline categories differ')
    for key in ('aliases', 'ranking'):
        name = 'search-aliases' if key == 'aliases' else key
        require(wrapper[key] == json.loads((root/f'public_site/data/{name}.json').read_text()),
                'offline/current ' + key + ' differs')
    new_native = [row for source in registry['sources'] if source['id'] in sources
                  for row in json.loads((root/source['catalog']).read_text())['works']]
    require({row['id'] for row in new_native} == {row['id'] for row in additions},
            'new native/public identity scope differs')
    public_rows = {row['id']: row for row in additions}
    for row in new_native:
        require(all(public_rows[row['id']][key] == row[key] for key in ('title_en', 'composer_en')),
                'new native title/attribution changed in projection: ' + row['id'])
    new_controls = verify_new_file_controls(new_native, offline_rows)
    full = json.loads(full_report.read_text())
    require({k: v for k, v in full.items() if k != 'index'} == offline['offline_summary']
            and 'mode' not in full and 'input_guard' not in full, 'full-render receipt differs')
    require(full_report.stat().st_mtime_ns >= (root/'index.html').stat().st_mtime_ns,
            'full-render receipt predates current HTML')
    links = {item['href'] for row in offline['works'] for edition in row['local_editions'] for item in edition['files']}
    links.update(row['local_href'] for row in offline['categories'] if row.get('local_href'))
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda href: check_local_link(root, href), sorted(links)))
    require(wrapper['aliases'] == old_aliases and wrapper['ranking'] == old_ranking,
            'supplement unexpectedly changed existing aliases/ranking')
    muse_count = sum(row['source_id'] == 'musescore' for row in public['works'])
    result = {'schema_version': 1, 'checked_at': utcnow(), 'status': 'complete',
        'baseline_sha256': hashlib.sha256(basepath.read_bytes()).hexdigest(),
        'old_public_and_offline_records_preserved': old_count,
        'old_native_inputs_preserved': len(baseline['protected_native_inputs']),
        'old_translation_entry_groups_preserved': translation_entries,
        'new_sources': sources, 'new_records': len(additions), 'new_file_controls': new_controls,
        'current_records': len(public['works']), 'compact_canonical_and_offline_parity': True,
        'old_local_editions_exact': True, 'local_links_checked': len(links), 'local_links_failed': 0,
        'offline_index_sha256': index_sha, 'offline_entry_bytes': (root/'index.html').stat().st_size,
        'full_render_report': str(full_report.relative_to(root)),
        'musescore_adapter': node_offline_adapter(root, muse_count)}
    atomic_json(root/'sources/source-expansion/preservation.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--source', action='append', required=True)
    parser.add_argument('--full-render-report', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    report = args.full_render_report if args.full_render_report.is_absolute() else root/args.full_render_report
    print(json.dumps(verify(root, args.source, report), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
