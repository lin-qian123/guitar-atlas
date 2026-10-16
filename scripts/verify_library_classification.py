"""Verify every classification change against the current-publication baseline."""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
from copy import deepcopy
import re
from urllib.parse import unquote

from catalog_classification import REVIEW_PATH, digest, public_details
from source_adapters.pdmx import _atomic_json
from verify_musescore_expansion import (decode_offline, read_baseline, compare_offline_records,
    unpack_payload, require, compare_existing_records, check_old_objects, compare_public_structure)

BASE = Path('sources/classification')
_IMSLP_7_STRING_GUITAR = re.compile(r'for [1-9][0-9]*[ -]string guitar(?: \(arr\))?\Z')
_IMSLP_NUMERIC_GUITAR_ENSEMBLE = re.compile(r'for ([1-9][0-9]*) guitars(?: \(arr\))?\Z')


def _new_approved_imslp_topic(category):
    """Recognize only the two newly approved pure-category grammars."""
    if category.get('family') != 'pure':
        return None
    name = re.sub(r'\s+', ' ', str(category.get('name', '')).casefold()).strip()
    if _IMSLP_7_STRING_GUITAR.fullmatch(name):
        return 'solo'
    match = _IMSLP_NUMERIC_GUITAR_ENSEMBLE.fullmatch(name)
    if match and int(match.group(1)) >= 10:
        return 'guitar_ensemble'
    return None


def corrected_offline_baseline(root, before_rows):
    """Allow only separately guarded removals of proven mismatched score links."""
    path = root / BASE / 'score-link-corrections.json'
    if not path.is_file():
        return before_rows, 0
    correction = json.loads(path.read_bytes())
    scope = json.loads((root / BASE / 'scope.json').read_bytes())
    frozen = read_baseline(root / scope['parent_baseline']['path'])
    raw = correction['before_config_bytes'].encode()
    require(hashlib.sha256(raw).hexdigest() == correction['before_config_sha256'] ==
        frozen['offline_snapshot']['data']['offline_inputs']['inputs']['config/score_exclusions.json'],
        'score-link correction does not preserve the original exclusion input')
    previous = json.loads(raw)
    current = json.loads((root / 'config/score_exclusions.json').read_bytes())
    expected = {**previous, 'reviewed_at': current['reviewed_at'],
        'entries': previous['entries'] + correction['entries']}
    require(current == expected, 'unreviewed score-link exclusion change')
    for file in correction['files']:
        actual = root / file['path']
        require(actual.resolve().is_relative_to(root.resolve()) and actual.is_file(), 'excluded original file was removed')
        body = actual.read_bytes()
        require(hashlib.sha256(body).hexdigest() == file['sha256'] and len(body) == file['size']
            and hashlib.sha1(body).hexdigest() == file['sha1'] == file['original_manifest']['sha1_imslp'],
            'excluded original bytes or upstream file identity changed')
    result = deepcopy(before_rows)
    rows = {r['id']: r for r in result}
    categories = {c['name']: c['id'] for c in frozen['offline_snapshot']['data']['categories'] if c['source_id'] == 'imslp'}
    removed = 0
    for entry in correction['entries']:
        row = rows[entry['work_id']]
        editions = [e for e in row['local_editions'] if e['category_id'] == categories[entry['category']]]
        require(len(editions) == 1, 'exact excluded category membership differs')
        edition = editions[0]
        matches = [f for f in edition['files'] if unquote(f['href']).split('/')[-1] == entry['filename']]
        require(len(matches) == 1, 'expected exactly one previously linked mismatched file')
        edition['files'].remove(matches[0]); edition['unavailable_count'] += 1
        edition['excluded_count'] = edition.get('excluded_count', 0) + 1
        edition['exclusion_reason'] = entry['reason']; removed += 1
    return result, removed


def compare_classified_public(before, after, entries, source_native=None):
    """Permit only the exact reviewed topic/details changes; retain all else."""
    from catalog_sources import (MUSESCORE_SYNTHETIC_SOURCE_INSTRUMENTATION,
                                 public_source_instrumentation)

    source_native = source_native or {}
    old = {w['id']: w for w in before['works']}
    current = {w['id']: w for w in after['works']}
    require(set(old) <= set(current), 'classification removed existing source identities')
    require(set(entries) <= set(old), 'formal classification decisions exceed the captured public scope')
    old_categories = {c['id']: c for c in before['categories']}
    changed = Counter()
    source_declaration_projection_repairs = 0
    approved_category_membership_repairs = 0
    for identity, previous in old.items():
        expected = dict(previous)
        if identity in entries:
            decision = entries[identity]
            topics = {decision['topic_id']} | (set(previous['topic_ids']) & {'studies', 'historical', 'reference'})
            evidence = {t: previous['topic_evidence'][t] for t in topics if t in {'studies', 'historical', 'reference'} and t != decision['topic_id']}
            evidence[decision['topic_id']] = decision['basis']
            mapping = {t: previous['topic_category_ids'][t] for t in topics if t in {'studies', 'historical', 'reference'} and t != decision['topic_id']}
            mapping[decision['topic_id']] = sorted(previous['category_ids'])
            expected.update(details={**previous['details'], **public_details(decision)},
                topic_ids=sorted(topics), topic_evidence=evidence,
                topic_category_ids={t: mapping[t] for t in sorted(topics)})
        elif previous['source_id'] == 'imslp':
            # Add only the two newly approved pure-category memberships. Existing
            # source categories and all unrelated topic mappings stay exact.
            additions = {}
            for cid in previous['category_ids']:
                topic = _new_approved_imslp_topic(old_categories[cid])
                if topic and cid not in previous['topic_category_ids'].get(topic, []):
                    additions.setdefault(topic, []).append(cid)
            if additions:
                topics = set(previous['topic_ids'])
                evidence = dict(previous['topic_evidence'])
                mapping = deepcopy(previous['topic_category_ids'])
                for topic, category_ids in additions.items():
                    topics.add(topic)
                    evidence[topic] = 'approved_source_category'
                    mapping[topic] = sorted(set(mapping.get(topic, [])) | set(category_ids))
                    approved_category_membership_repairs += len(category_ids)
                if (evidence.get('unspecified') == 'no_exact_instrumentation_evidence'
                        and any(topic in topics for topic in additions)):
                    topics.discard('unspecified')
                    evidence.pop('unspecified', None)
                    mapping.pop('unspecified', None)
                expected.update(topic_ids=sorted(topics), topic_evidence=evidence,
                    topic_category_ids={t: mapping[t] for t in sorted(topics)})
        classification_expected = deepcopy(expected)
        native = source_native.get(identity)
        old_source_declaration = previous.get('details', {}).get('source_instrumentation')
        if (previous.get('source_id') == 'musescore'
                and old_source_declaration == MUSESCORE_SYNTHETIC_SOURCE_INSTRUMENTATION
                and isinstance(native, dict)
                and native.get('metadata', {}).get('instrumentation') == MUSESCORE_SYNTHETIC_SOURCE_INSTRUMENTATION):
            repaired_declaration = public_source_instrumentation(native, current=old_source_declaration)
            expected_details = dict(expected.get('details', {}))
            if repaired_declaration is None:
                expected_details.pop('source_instrumentation', None)
            else:
                expected_details['source_instrumentation'] = repaired_declaration
            expected['details'] = expected_details
            if repaired_declaration != old_source_declaration:
                source_declaration_projection_repairs += 1
        require(current[identity] == expected, 'unreviewed public field changed: ' + identity)
        if previous != classification_expected:
            changed[previous['source_id']] += 1
    return {'preserved_native_public_identities': len(old), 'changed_classifications_by_source': dict(changed),
            'source_declaration_projection_repairs': source_declaration_projection_repairs,
            'approved_category_membership_repairs': approved_category_membership_repairs,
            'all_other_public_work_fields_exact': True, 'added_records': len(current) - len(old)}


def compare_added_source_declarations(after, added_ids, source_native):
    """Check and count exact placeholder repairs on records added after the baseline."""
    from catalog_sources import (MUSESCORE_SYNTHETIC_SOURCE_INSTRUMENTATION,
                                 public_source_instrumentation)

    rows = {row['id']: row for row in after['works']}
    repairs = 0
    for identity in added_ids:
        public = rows[identity]
        if public.get('source_id') != 'musescore':
            continue
        native = source_native.get(identity)
        require(isinstance(native, dict),
                'added public MuseScore record lacks its protected native source record: ' + identity)
        original = native.get('metadata', {}).get('instrumentation')
        if original != MUSESCORE_SYNTHETIC_SOURCE_INSTRUMENTATION:
            continue
        expected = public_source_instrumentation(native)
        require(public.get('details', {}).get('source_instrumentation') == expected,
                'unreviewed added MuseScore source declaration projection changed: ' + identity)
        if expected != original:
            repairs += 1
    return repairs


def verify(root, *, full_report=None, display_refresh_report=None):
    root = Path(root).resolve()
    scope = json.loads((root / BASE / 'scope.json').read_bytes())
    baseline_path = root / scope['parent_baseline']['path']
    require(hashlib.sha256(baseline_path.read_bytes()).hexdigest() == scope['parent_baseline']['sha256'],
            'classification baseline changed')
    baseline = read_baseline(baseline_path)
    review = json.loads((root / REVIEW_PATH).read_bytes())
    entries = review['entries']
    receipt = json.loads(gzip.decompress((root / BASE / 'review.json.gz').read_bytes()))
    require(receipt.get('status') == 'complete' and receipt['scope'] == scope,
            'complete classification receipt with the frozen scope required')
    require(set(receipt['formal_outcomes']) == set(scope['formal_ids'])
            and set(receipt['candidate_outcomes']) == set(scope['pending_musescore_ids']),
            'classification receipt does not cover every frozen identity')
    broad = json.loads((root / 'metadata/instrumentation/musescore_broad_reviewed.json').read_bytes())
    expected_candidates = {r['id']: {'status': 'accepted', 'remaining_gap': r['review']['summary']}
                           for r in broad['entries']}
    expected_candidates.update({r['id']: {'status': r['status'], 'remaining_gap': r['remaining_gap']}
                                for r in broad['outcomes']})
    require(receipt['candidate_outcomes'] == expected_candidates,
            'consolidated candidate outcomes differ from the guarded production decisions')
    require(all(digest(value) == receipt['proposal_semantic_guards'][name]
            for name, value in receipt['original_proposals'].items()), 'lossless proposal readback differs')
    review_raw = (root / REVIEW_PATH).read_bytes()
    require(receipt['production_review'] == {'path': str(REVIEW_PATH),
            'sha256': hashlib.sha256(review_raw).hexdigest(), 'size': len(review_raw)},
            'classification receipt and compiled production decisions differ')
    expected_ids = {i for i in scope['formal_ids'] if ':' in i}
    require(set(entries) == expected_ids, 'classification failed complete frozen formal coverage')
    native_guards = {}
    current_musescore_native = {}
    from catalog_sources import load_registry, source_catalog
    from catalog_classification import APPLIED_CLASSIFICATIONS
    applied = set()
    for source in load_registry(root):
        if not source.get('catalog'):
            continue
        raw = (root / source['catalog']).read_bytes()
        current_native = json.loads(raw)
        native_guards.update((w['id'], digest(w)) for w in current_native['works'])
        if source['id'] == 'musescore':
            current_musescore_native = {w['id']: w for w in current_native['works']}
        if source['id'] != 'musescore':
            require(hashlib.sha256(raw).hexdigest() == scope['source_catalogs'][source['id']]['sha256'],
                    'classification changed a native source catalog: ' + source['id'])
        else:
            compare_existing_records(baseline['documents'][source['catalog']]['value']['works'],
                current_native['works'], 'original MuseScore native')
        effective = source_catalog(root, source)
        applied.update(effective.get(APPLIED_CLASSIFICATIONS, {}))
    require(applied == set(entries), 'not every reviewed classification was checked and applied')
    public = json.loads((root / 'public_site/data/catalog.json').read_bytes())
    require(unpack_payload(json.loads((root / 'public_site/data/catalog.compact.json').read_bytes())) == public,
            'compact and canonical public catalog differ')
    old_public = baseline['documents']['public_site/data/catalog.json']['value']
    old_public_ids = {work['id'] for work in old_public['works']}
    protected_musescore_native = current_musescore_native
    result = compare_classified_public(old_public, public, entries, protected_musescore_native)
    added = {w['id'] for w in public['works']} - old_public_ids
    new_source_repairs = compare_added_source_declarations(public, added, protected_musescore_native)
    result['source_declaration_projection_repairs'] = {
        'previously_published_records': result['source_declaration_projection_repairs'],
        'newly_added_records': new_source_repairs,
    }
    result['structure'] = compare_public_structure(old_public, public, added, classification_update=True)
    result.update(schema_version=1, status='precheck_passed_not_final' if full_report is None else 'complete',
        frozen_formal_scope=len(scope['formal_ids']), pending_musescore_scope=len(scope['pending_musescore_ids']),
        reviewed_entries=len(entries), evidence_levels=dict(Counter(d['basis'] for d in entries.values())),
        topics=dict(Counter(d['topic_id'] for d in entries.values())),
        native_catalogs_unchanged_except_guarded_musescore_append=True,
        review_sha256=hashlib.sha256((root / REVIEW_PATH).read_bytes()).hexdigest())
    if full_report is not None:
        from render_offline_site import offline_input_fingerprint
        wrapper, _ = decode_offline(root / 'index.html')
        expected_old, removed = corrected_offline_baseline(root, baseline['offline_snapshot']['data']['works'])
        result['offline'] = compare_offline_records(expected_old, wrapper['data']['works'], public['works'])
        result['offline']['reviewed_mismatched_file_links_removed_originals_retained'] = removed
        require(wrapper['data']['offline_inputs'] == offline_input_fingerprint(root), 'offline classification fingerprint is stale')
        full = json.loads(Path(full_report).read_bytes())
        require({k:v for k,v in full.items() if k != 'index'} == wrapper['data']['offline_summary']
                and 'mode' not in full, 'a fresh complete render receipt is required')
        if display_refresh_report is not None:
            from offline_display_refresh import validate_display_refresh
            result['offline_display_refresh'] = validate_display_refresh(
                root, full_report, display_refresh_report)
        else:
            from offline_display_refresh import require_fresh_full_render_report
            require_fresh_full_render_report(full_report, root / 'index.html')
        result['prior_musescore_objects_freshly_checked'] = check_old_objects(root, baseline['files'])
    else:
        require(display_refresh_report is None,
                'display-refresh evidence requires a full-render receipt')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--full-render-report', type=Path)
    parser.add_argument('--display-refresh-report', type=Path,
                        help='guarded receipt for the exact metadata-only source declaration refresh')
    args = parser.parse_args()
    result = verify(args.root, full_report=args.full_render_report,
                    display_refresh_report=args.display_refresh_report)
    _atomic_json(args.root / BASE / 'preservation.json', result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
