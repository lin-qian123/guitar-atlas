"""Guarded, source-preserving classification of previously unclassified records.

The reviewed asset is a compiler input, never browser data. Source declarations
and score observations have different public evidence labels. Neither changes
native records, licenses, source categories, or the historical MuseScore review.
"""
from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

REVIEW_PATH = Path('metadata/instrumentation/source_classification_reviewed.json')
APPLIED_CLASSIFICATIONS = '_applied_classification_reviews'
TOPICS = {'solo', 'duo', 'trio', 'quartet', 'guitar_ensemble', 'strings', 'woodwinds',
          'brass', 'keyboard_reed', 'plucked', 'percussion', 'mixed_chamber',
          'guitar_unspecified', 'other_instrumentation', 'unspecified', 'reference'}
BASES = {'reviewed_source_evidence', 'reviewed_score_evidence', 'reviewed_source_audit'}
PUBLIC_FIELDS = {'classification_note', 'classification_basis', 'reviewed_instrumentation',
                 'declared_player_count', 'reviewed_player_count'}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _safe_text(value):
    from catalog_instrumentation import _PRIVATE_TEXT
    return (isinstance(value, str) and bool(value.strip()) and len(value) <= 1600
        and not re.search(r'https?://|file:|(?:sources|objects|metadata)/|[a-f0-9]{64}|\.(?:pdf|mxl|mid)\b', value, re.I)
        and not _PRIVATE_TEXT.search(value)
        and not re.search(r'(?:^|\s)(?:/(?:Users|Volumes|tmp|private|home|var)/|[A-Za-z]:[\\/])|\bprivate/', value, re.I)
        and not any(ord(c) < 32 and c not in '\n\t' for c in value))


def field_value(work, path):
    value = work
    for key in path:
        value = value[key]
    return value


@lru_cache(maxsize=1)
def _read_review(path, stamp):
    raw = path.read_bytes()
    value = json.loads(raw)
    if (value.get('schema_version') != 1 or value.get('status') != 'complete'
            or not isinstance(value.get('entries'), dict)):
        raise ValueError('incomplete source classification review')
    if path.stat().st_mtime_ns != stamp[1] or path.stat().st_size != stamp[0]:
        raise ValueError('classification review changed while reading')
    return value


@lru_cache(maxsize=16384)
def _verify_file(path, expected, stamp):
    hasher = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            hasher.update(block)
    after = path.stat()
    if (hasher.hexdigest() != expected
            or (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) != stamp):
        raise ValueError('classification score guard changed: ' + str(path))


def check_decision(root, work, categories, decision):
    if decision.get('native_record_sha256') != digest(work):
        raise ValueError('stale native classification guard: ' + work['id'])
    topic, basis = decision.get('topic_id'), decision.get('basis')
    if topic not in TOPICS or basis not in BASES:
        raise ValueError('invalid reviewed classification topic/basis')
    if not _safe_text(decision.get('note')) or not _safe_text(decision.get('instrumentation')):
        raise ValueError('unsafe reviewed classification description')
    count = decision.get('player_count')
    if count is not None and (type(count) is not int or not 1 <= count <= 128):
        raise ValueError('invalid reviewed performing player count')
    if topic in {'solo', 'duo', 'trio', 'quartet'} and count != {'solo': 1, 'duo': 2, 'trio': 3, 'quartet': 4}[topic]:
        raise ValueError('precise classification requires its performing player count')
    if count is not None and (topic in {'unspecified', 'guitar_unspecified', 'reference'}
                              or basis == 'reviewed_source_audit'):
        raise ValueError('unresolved/reference classification cannot claim a player count')
    if basis == 'reviewed_source_audit' and topic != 'unspecified':
        raise ValueError('inconclusive source audit cannot establish instrumentation')
    evidence = decision.get('evidence')
    if not isinstance(evidence, list) or not evidence:
        raise ValueError('reviewed classification lacks exact evidence')
    saw_file = False
    for item in evidence:
        if item.get('kind') == 'native_field':
            path = item.get('path')
            if not isinstance(path, list) or not path or any(not isinstance(k, (str, int)) for k in path):
                raise ValueError('invalid classification source-field path')
            try:
                actual = field_value(work, path)
            except (KeyError, IndexError, TypeError) as error:
                raise ValueError('classification source-field no longer exists') from error
            matches = (digest(actual) == item['value_sha256'] if 'value_sha256' in item
                       else actual == item.get('value'))
            if not matches or actual in (None, '', [], {}):
                raise ValueError('classification source-field evidence differs')
        elif item.get('kind') == 'category':
            category = categories.get(item.get('id'))
            if (category is None or item['id'] not in work['category_ids']
                    or digest(category) != item.get('sha256')):
                raise ValueError('classification source-category evidence differs')
        elif item.get('kind') == 'file':
            matches = [a for a in work.get('assets', []) if a.get('status') == 'verified'
                and a.get('format') == item.get('format') and a.get('sha256') == item.get('sha256')
                and a.get('size') == item.get('size') and a.get('container') != 'ZIP']
            # One immutable file can be cited by several exact source editions.
            if not matches or not _safe_text(item.get('observation')):
                raise ValueError('classification file evidence lacks a verified asset')
            path = root / matches[0]['local_path']
            if not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
                raise ValueError('classification file leaves the library')
            stat = path.stat()
            stamp = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
            if stat.st_size != item['size']:
                raise ValueError('classification file size differs')
            _verify_file(path, item['sha256'], stamp)
            saw_file = True
        elif item.get('kind') == 'source_snapshot':
            relative = Path(item.get('path', ''))
            path = root / relative
            if (relative.is_absolute() or '..' in relative.parts
                    or relative.parts[:2] != ('sources', work['id'].split(':', 1)[0])
                    or not path.resolve().is_relative_to(root.resolve()) or not path.is_file()
                    or not _safe_text(item.get('observation'))):
                raise ValueError('unsafe classification source snapshot')
            stat = path.stat()
            if stat.st_size != item.get('size') or not re.fullmatch('[0-9a-f]{64}', str(item.get('sha256', ''))):
                raise ValueError('classification source snapshot guard differs')
            _verify_file(path, item['sha256'],
                (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns))
        else:
            raise ValueError('unsupported classification evidence type')
    if basis == 'reviewed_score_evidence' and not saw_file:
        raise ValueError('score classification requires fresh file evidence')
    return decision


def apply_classification_reviews(root, effective, native):
    """Attach only checked runtime decisions; never trust a native marker."""
    if APPLIED_CLASSIFICATIONS in native:
        raise ValueError('native catalog cannot forge a classification review marker')
    path = root / REVIEW_PATH
    if not path.exists() and not path.is_symlink():
        return effective
    if not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('unsafe source classification review')
    stat = path.stat()
    review = _read_review(path, (stat.st_size, stat.st_mtime_ns, stat.st_ino, stat.st_ctime_ns))
    entries = {i: d for i, d in review['entries'].items() if i.startswith(native['source_id'] + ':')}
    indexed = {w['id']: w for w in native['works']}
    if set(entries) - set(indexed):
        raise ValueError('classification review refers to a missing native identity')
    categories = {c['id']: c for c in native['categories']}
    applied = {i: check_decision(root, indexed[i], categories, d) for i, d in entries.items()}
    if not applied:
        return effective
    result = dict(effective)
    result[APPLIED_CLASSIFICATIONS] = applied
    return result


def require_classification_coverage(root, applied):
    """Do not silently ignore decisions for missing or mistyped source IDs."""
    path = root / REVIEW_PATH
    if not path.exists() and not path.is_symlink():
        return
    if not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('unsafe source classification review')
    stat = path.stat()
    review = _read_review(path, (stat.st_size, stat.st_mtime_ns, stat.st_ino, stat.st_ctime_ns))
    if set(applied) != set(review['entries']):
        raise ValueError('classification contains an unapplied or unknown source identity')


def public_details(decision):
    fields = {'classification_note': decision['note'],
        'classification_basis': {'reviewed_score_evidence': '谱面核对',
            'reviewed_source_evidence': '原始来源声明',
            'reviewed_source_audit': '来源审查·仍待确认'}[decision['basis']],
        'reviewed_instrumentation': decision['instrumentation']}
    if decision.get('player_count') is not None:
        fields['reviewed_player_count' if decision['basis'] == 'reviewed_score_evidence'
               else 'declared_player_count'] = str(decision['player_count'])
    return fields
