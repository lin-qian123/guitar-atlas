#!/usr/bin/env python
"""Resume the separately scoped institutional and author-source supplement.

Each adapter owns its discovery, identities, rights and exclusions. Registration
only appends inspected normalized catalogs; it never rewrites an existing source
or expands any historical acquisition command.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from catalog_sources import load_registry, validate_record_source_url, validate_source_url
from source_adapters.additional import atomic_json


def adapters():
    from source_adapters import csun, open_guitar, teaching
    return {
        'csun': (csun.discover, csun.registry_proposal()),
        'yawnoc': (open_guitar.discover_yawnoc, open_guitar.registry_proposals()['yawnoc']),
        'maikstrings': (open_guitar.discover_maikstrings, open_guitar.registry_proposals()['maikstrings']),
        'derekhasted': (teaching.discover_derekhasted, teaching.registry_proposals()['derekhasted']),
        'guitarclassroom': (teaching.discover_guitarclassroom, teaching.registry_proposals()['guitarclassroom']),
    }


def register(root: Path, proposals: list[dict]) -> dict:
    path = root / 'config/sources.json'
    before = path.read_bytes()
    document = json.loads(before)
    existing = {row['id']: row for row in document['sources']}
    rows = document['sources'][:]
    appended = []
    for proposal in proposals:
        sid = proposal['id']
        if sid in existing:
            if proposal != existing[sid]:
                raise ValueError('refusing to rewrite existing source configuration: ' + sid)
            continue
        catalog = json.loads((root/proposal['catalog']).read_text())
        if (catalog.get('schema_version') != 1 or catalog.get('source_id') != sid
                or not catalog.get('works') or not catalog.get('categories')):
            raise ValueError('source lacks a completed usable catalog: ' + sid)
        identities, category_ids = set(), {row['id'] for row in catalog['categories']}
        if len(category_ids) != len(catalog['categories']):
            raise ValueError('duplicate native category: ' + sid)
        for category in catalog['categories']:
            validate_source_url(category['source_url'], sid, [proposal])
        for work in catalog['works']:
            identity = work['id']
            if not identity.startswith(sid + ':') or identity in identities:
                raise ValueError('duplicate or invalid native identity: ' + sid)
            identities.add(identity)
            validate_record_source_url(work['source_url'], sid, identity.split(':', 1)[1], [proposal])
            memberships = work['category_ids']
            if (not memberships or len(memberships) != len(set(memberships))
                    or not set(memberships).issubset(category_ids)):
                raise ValueError('invalid source membership: ' + identity)
        rows.append(proposal)
        existing[sid] = proposal
        appended.append(sid)
    if path.read_bytes() != before:
        raise ValueError('source registry changed during append preparation')
    if appended:
        document.update(version='2026-10-26.1', sources=rows)
        atomic_json(path, document)
        load_registry(root)
    return {'appended_sources': appended, 'registered_sources': len(rows)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--source', action='append', required=True,
                        choices=['csun', 'yawnoc', 'maikstrings', 'derekhasted', 'guitarclassroom'])
    parser.add_argument('--register', action='store_true',
                        help='Append the completed source configurations after discovery succeeds')
    parser.add_argument('--cached-only', action='store_true',
                        help='Register existing completed catalogs without accessing source websites')
    args = parser.parse_args()
    root = args.root.resolve()
    choices = adapters()
    if len(args.source) != len(set(args.source)):
        raise ValueError('select each source only once')
    proposals = []
    for sid in args.source:
        discover, proposal = choices[sid]
        if not args.cached_only:
            result = discover(root)
            print(json.dumps({'source': sid, 'result': result}, ensure_ascii=False), flush=True)
        proposals.append(proposal)
    if args.register:
        print(json.dumps(register(root, proposals), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
