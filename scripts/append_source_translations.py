#!/usr/bin/env python
"""Append checked display references for explicitly selected new source catalogs.

Previously published decisions are immutable. This command uses exact complete
title/attribution references or the existing closed music grammar; unsupported
names and titles retain their source spelling, with an explicit reason.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from catalog_sources import load_registry, validate_source_url
from catalog_translations import HAN, checked_entry, wrap_display_title
from review_musescore_translations import (
    ASSETS, ATTRIBUTION_LABELS as LEGACY_ATTRIBUTION_LABELS, attribution_key, entry, full_name_key,
    load_document, primary_title, reference_indexes,
)
from review_source_translations import TERMS
from source_adapters.additional import atomic_json, utcnow
from title_translation_quality import terminology_grammar

# Literal attribution labels only; these never supply an individual identity.
ATTRIBUTION_LABELS = {**LEGACY_ATTRIBUTION_LABELS,
    'Spanish Traditional': '西班牙传统音乐',
    'Russian Traditional': '俄罗斯传统音乐',
    '[Various]': '多位作曲家'}


def _terms(root: Path, source_id: str) -> tuple[dict, dict]:
    terms, categories = dict(TERMS), {}
    path = root / 'metadata/translations/expansion_terminology_zh.json'
    if path.exists():
        for row in load_document(path)['entries']:
            if row.get('status') not in {'reference', 'reviewed'}:
                continue
            if row.get('sources') and source_id not in row['sources']:
                continue
            if row.get('context') in {'title_term', 'key_signature'}:
                terms[row['original'].casefold()] = row['zh']
            elif row.get('context') == 'source_category':
                categories[row['original']] = row['zh']
    return terms, categories


def _retained(original: str, *, title: bool = False) -> dict:
    return entry(original, wrap_display_title(original) if title else original,
                 'retained', 'exact_new_source_text_preservation',
                 '未取得能确认该完整来源文字的可靠中文对应；保留原文及真实编号供统一检索，不补猜人名或专名。')


def _exact_name_references(root: Path, documents: dict) -> dict:
    """Index checked display translations by the verbatim source attribution."""
    exact = defaultdict(lambda: defaultdict(list))
    for source, group in documents[ASSETS[1]]['entries'].items():
        # MuseScore entries have a dedicated reviewer and are intentionally not
        # used as spelling references by reference_indexes either.
        if source == 'musescore':
            continue
        for original, row in group.items():
            if row.get('status') not in {'reference', 'reviewed'}:
                continue
            zh, _ = checked_entry(row, original, f'{source}: {original}')
            if isinstance(zh, str) and HAN.search(zh):
                exact[original][zh].append(f'{ASSETS[1]}:{source}:{original}')

    overrides_path = root / 'metadata/translations/composer_overrides_reviewed_zh.json'
    if overrides_path.exists():
        for original, zh in load_document(overrides_path)['entries'].items():
            if isinstance(original, str) and isinstance(zh, str) and HAN.search(zh):
                exact[original][zh].append(f'composer_overrides_reviewed_zh.json:{original}')
    return exact


def _checked_manual_categories(source_id: str, categories: list, registry_row: dict,
                               category_entries: dict, supplement_path: Path,
                               root: Path) -> dict:
    """Validate source-local category text and human-page evidence guards."""
    raw = category_entries.get(source_id, {})
    if not isinstance(raw, dict):
        raise ValueError('category supplement source entries must be an object: ' + source_id)
    native = {str(row['id']): row['name'] for row in categories}
    allowed_hosts = {str(host).casefold() for host in registry_row.get('allowed_hosts', [])}
    checked = {}
    for identity, row in raw.items():
        identity = str(identity)
        if identity not in native or not isinstance(row, dict):
            raise ValueError('unknown or malformed exact category supplement: ' + source_id + ':' + identity)
        original, zh = row.get('original'), row.get('zh')
        reason, evidence_url = row.get('reason'), row.get('evidence_url')
        if not isinstance(original, str) or original != native[identity]:
            raise ValueError('exact category supplement source-text guard drift: ' + source_id + ':' + identity)
        if not isinstance(zh, str) or not zh.strip() or not HAN.search(zh):
            raise ValueError('manual category translation must contain checked Chinese text: ' + source_id + ':' + identity)
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError('manual category translation needs a reason: ' + source_id + ':' + identity)
        if not isinstance(evidence_url, str):
            raise ValueError('manual category translation needs a human source page: ' + source_id + ':' + identity)
        parsed = urlsplit(evidence_url)
        if (parsed.scheme != 'https' or not parsed.hostname
                or parsed.hostname.casefold() not in allowed_hosts
                or parsed.path.startswith(('/api/', '/digital/api/'))):
            raise ValueError('category evidence must be an approved human source page: ' + source_id + ':' + identity)
        try:
            validate_source_url(evidence_url, source_id, [registry_row])
        except ValueError as error:
            raise ValueError('category evidence must be an approved human source page: '
                             + source_id + ':' + identity) from error
        checked[identity] = {**row, 'reference': str(supplement_path.relative_to(root)) + ':' + source_id + ':' + identity}
    return checked


def append(root: Path, source_ids: list[str], *, apply: bool = False) -> dict:
    root = root.resolve()
    if not source_ids or len(source_ids) != len(set(source_ids)):
        raise ValueError('select distinct source identities explicitly')
    registry = {row['id']: row for row in load_registry(root)}
    if any(sid not in registry or registry[sid]['adapter'] != 'normalized_catalog'
           or sid in {'musescore', 'classclef'} for sid in source_ids):
        raise ValueError('use the existing source-owned reviewer for a legacy special source')
    paths = {name: root / 'metadata/translations' / name for name in ASSETS}
    before = {name: path.read_bytes() for name, path in paths.items()}
    documents = {name: load_document(path) for name, path in paths.items()}
    proposed = copy.deepcopy(documents)
    names, titles, _, _ = reference_indexes(root, documents)
    exact_names = _exact_name_references(root, documents)
    exact_path = root / 'metadata/translations/source_supplement_reviewed_zh.json'
    supplement = load_document(exact_path) if exact_path.exists() else {'entries': {}}
    exact = supplement['entries']
    manual_category_entries = supplement.get('category_entries', {})
    if not isinstance(manual_category_entries, dict):
        raise ValueError('category_entries must be an object keyed by source ID')
    catalog_guards, report = {}, {}
    for sid in source_ids:
        path = root / registry[sid]['catalog']
        body = path.read_bytes()
        catalog_guards[str(path.relative_to(root))] = hashlib.sha256(body).hexdigest()
        catalog = json.loads(body)
        if catalog.get('schema_version') != 1 or catalog.get('source_id') != sid:
            raise ValueError('source/catalog identity mismatch: ' + sid)
        works = {row['id']: row for row in catalog['works']}
        if (len(works) != len(catalog['works']) or not works
                or any(not key.startswith(sid + ':') for key in works)):
            raise ValueError('invalid or empty native source identity set: ' + sid)
        title_entries = proposed[ASSETS[0]]['entries']
        musicians = proposed[ASSETS[1]]['entries'].setdefault(sid, {})
        categories = proposed[ASSETS[2]]['entries'].setdefault(sid, {})
        terms, category_terms = _terms(root, sid)
        manual_categories = _checked_manual_categories(
            sid, catalog['categories'], registry[sid], manual_category_entries,
            exact_path, root)
        added = Counter()
        for original in sorted({row['composer_en'] for row in works.values()}):
            if original in musicians:
                checked_entry(musicians[original], original, sid + ': ' + original)
                continue
            exact_candidates = exact_names.get(original, {})
            candidates = names.get(full_name_key(original), {})
            if not original:
                row = entry('', '', 'not_applicable', 'absent_source_attribution',
                            '来源未提供作曲者署名；不从编者、上传者或书名补猜。')
            elif original in ATTRIBUTION_LABELS:
                row = entry(original, ATTRIBUTION_LABELS[original], 'reference',
                            'exact_source_attribution_label', '翻译来源署名标签，不推断具体作者。')
            elif len(exact_candidates) == 1:
                zh, refs = next(iter(exact_candidates.items()))
                row = entry(original, zh, 'reference', 'existing_exact_source_name_reference',
                            '原始署名字符串与已有已核参考完全一致；只复用中文显示文字，不推断跨站人物身份。')
                row['reference_entries'] = sorted(set(refs))
            elif len(candidates) == 1:
                zh, refs = next(iter(candidates.items()))
                row = entry(original, zh, 'reference', 'existing_checked_full_name_reference',
                            '完整姓名与已有已核参考一致；仅复用中文姓名，不建立跨站人物或版本身份。')
                row['reference_entries'] = sorted(set(refs))
            else:
                row = _retained(original)
            musicians[original] = row
            added['composer'] += 1
        for category in catalog['categories']:
            key, original = str(category['id']), category['name']
            if key in categories:
                checked_entry(categories[key], original, sid + ' category ' + key)
                continue
            manual = manual_categories.get(key)
            if manual:
                zh = manual['zh']
                categories[key] = entry(original, zh, 'reference',
                    'checked_exact_source_supplement_category', manual['reason'])
                categories[key]['reference_entries'] = [manual['reference']]
                added['category'] += 1
                continue
            zh = category_terms.get(original) or terminology_grammar(original, terms)
            categories[key] = (entry(original, zh, 'reference', 'checked_source_category_terms',
                '翻译明确栏目文字；具体编制仍由独立来源或谱件证据建立。') if zh else _retained(original))
            added['category'] += 1
        for identity, work in works.items():
            original, composer = work['title_en'], work['composer_en']
            primary = primary_title(original, sid, composer)
            if identity in title_entries:
                row = title_entries[identity]
                checked_entry(row, original, identity)
                if row.get('original_composer') != composer or row.get('display_original') != primary:
                    raise ValueError('existing source attribution/display guard drift: ' + identity)
                continue
            candidates = titles.get((primary, attribution_key(composer)), {})
            refs = []
            if identity in exact:
                decision = exact[identity]
                if (decision.get('original') != original or decision.get('original_composer') != composer
                        or decision.get('display_original') != primary):
                    raise ValueError('exact new-source title review drift: ' + identity)
                if not decision.get('reason') or not decision.get('evidence_url'):
                    raise ValueError('exact title review lacks reason or source evidence: ' + identity)
                row = entry(original, wrap_display_title(decision['zh']), 'reference',
                            'checked_exact_source_supplement_title', decision['reason'])
                refs = [str(exact_path.relative_to(root)) + ':' + identity]
            elif len(candidates) == 1:
                zh, refs = next(iter(candidates.items()))
                row = entry(original, wrap_display_title(zh), 'reference',
                    'existing_exact_title_full_attribution_reference',
                    '完整显示原题与完整来源署名同时匹配已有已核参考；仅复用译文，不建立作品或版本同一性。')
            elif (zh := terminology_grammar(primary, terms, composer)):
                row = entry(original, wrap_display_title(zh), 'reference',
                    'complete_musical_title_grammar',
                    '完整显示原题通过受限音乐术语、调性及编号语法；这是参考译法，不是权威中文专名认证。')
            else:
                row = _retained(primary, title=True)
                row['original'] = original
            row.update(original_composer=composer, display_original=primary,
                       display_zh=row['zh'], reference_entries=sorted(set(refs)))
            checked_entry(row, original, identity)
            title_entries[identity] = row
            added['title'] += 1
        report[sid] = {'records': len(works), 'added': dict(added),
            'titles': dict(Counter(title_entries[key]['status'] for key in works)),
            'musicians': dict(Counter(row['status'] for row in musicians.values()))}
    # Every old entry, including earlier decisions inside the selected source,
    # remains exactly the same JSON object; source/header fields cannot disappear.
    for name in ASSETS:
        for key, value in documents[name]['entries'].items():
            if name == ASSETS[0]:
                if proposed[name]['entries'].get(key) != value:
                    raise ValueError('published title decision changed: ' + key)
            elif any(proposed[name]['entries'].get(key, {}).get(k) != v for k, v in value.items()):
                raise ValueError('published name/category decision changed: ' + key)
    result = {'schema_version': 1, 'checked_at': utcnow(), 'applied': apply,
              'sources': report, 'catalog_sha256': catalog_guards,
              'all_previous_entries_preserved': True}
    if apply:
        if any(path.read_bytes() != before[name] for name, path in paths.items()):
            raise ValueError('translation assets changed while preparing append')
        if any(hashlib.sha256((root/name).read_bytes()).hexdigest() != sha
               for name, sha in catalog_guards.items()):
            raise ValueError('native catalog changed while preparing append')
        for name, path in paths.items():
            if proposed[name] != documents[name]:
                atomic_json(path, proposed[name])
        atomic_json(root / 'sources/source-expansion/translation-review.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--source', action='append', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(json.dumps(append(args.root, args.source, apply=args.apply), ensure_ascii=False))


if __name__ == '__main__':
    main()
