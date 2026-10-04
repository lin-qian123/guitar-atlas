#!/usr/bin/env python
"""Audit or replay the source-guarded legacy title/name/category review.

This edits display review assets only. No source discovery, score acquisition,
source identity normalization, or catalogue export occurs here. All affected
files are validated in memory before the first write, and exact original/before
row guards make the review fail on source drift or a concurrent display edit.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
from collections import Counter
from pathlib import Path

ASSETS = {'title_overrides_reviewed_zh.json', 'classclef_titles_zh.json',
          'musicians_zh.json', 'categories_zh.json'}
DEFAULT_REVIEW = 'metadata/translations/review_2026-10-02/legacy_exact_corrections.json'


def _row(document: dict, path: list) -> dict:
    row = document['entries']
    for key in path:
        row = row[key]
    if not isinstance(row, dict):
        raise ValueError('review path is not a translation row')
    return row


def prepare_review(root: Path, review: dict) -> tuple[dict, dict]:
    if review.get('schema_version') != 1 or not isinstance(review.get('changes'), list):
        raise ValueError('invalid legacy translation review')
    documents = {}
    counts = Counter()
    seen = set()
    for change in review['changes']:
        name, path = change.get('asset'), change.get('path')
        if name not in ASSETS or not isinstance(path, list) or not path:
            raise ValueError('invalid translation review asset/path')
        marker = (name, tuple(path))
        if marker in seen:
            raise ValueError('duplicate translation review row')
        seen.add(marker)
        if name not in documents:
            documents[name] = json.loads((root/'metadata/translations'/name).read_text())
        before, after = change.get('before'), change.get('after')
        if not isinstance(before, dict) or not isinstance(after, dict):
            raise ValueError('review requires complete before/after rows')
        original_key = 'title_en' if name=='title_overrides_reviewed_zh.json' else 'original'
        if before.get(original_key) != change.get('original') or after.get(original_key) != change.get('original'):
            raise ValueError('review original drift')
        identity_key = 'work_id' if name=='title_overrides_reviewed_zh.json' else None
        if identity_key and before.get(identity_key) != after.get(identity_key):
            raise ValueError('review cannot change work identity')
        predecessors=change.get('accepted_predecessors',[])
        if not isinstance(predecessors,list) or any(not isinstance(p,dict) or p.get(original_key)!=change['original'] or (identity_key and p.get(identity_key)!=before.get(identity_key)) for p in predecessors):
            raise ValueError('review predecessor original/identity drift')
        row = _row(documents[name], path)
        if row == after:
            counts['already_applied'] += 1
            continue
        if row != before and row not in predecessors:
            raise ValueError(f'translation row drift: {name}: {path}')
        row.clear()
        row.update(copy.deepcopy(after))
        counts['pending_changes'] += 1
        counts[name] += 1
    for name, document in documents.items():
        if 'updated_at' in document:
            document['updated_at'] = review['reviewed_at']
        if name=='classclef_titles_zh.json':
            statuses = Counter(row['status'] for row in document['entries'].values())
            document['summary'] = {'records':len(document['entries']), 'status_counts':dict(statuses)}
    return documents, dict(counts)


def audit_assets(root: Path, prepared: dict | None = None) -> dict:
    """Structural and music-context checks over every row, not sampled titles."""
    prepared = prepared or {}
    counts, issues = {}, []
    false_friends = [
        (r'\bvirginal\b','处女','virginal_instrument'),
        (r'\b(?:orgel|organo|organica)\b','器官|有机和谐','organ_instrument'),
        (r'\b(?:tabulature|intabolatura)\b','制表|标签','tablature_not_table'),
        (r'\bconsort\b','配偶|王妃|世妃','consort_ensemble'),
        (r'\b(?:tiento|tento|tentos)\b','触碰|尝试','tiento_form'),
        (r'\bchoro\b','偷窃|呐喊','choro_genre'),
        (r'\b(?:passomezo|pass.?e? ?mezzo)\b','半小时|二世','passamezzo_dance'),
        (r'\b(?:Op\.|Opus)\s*\d','操作|欧普','opus_number'),
    ]
    for name in sorted(ASSETS):
        document = prepared.get(name) or json.loads((root/'metadata/translations'/name).read_text())
        rows = document['entries']
        if name=='title_overrides_reviewed_zh.json':
            iterator = [(str(r['work_id']),r['title_en'],r['title_zh']) for r in rows]
        elif name=='classclef_titles_zh.json':
            iterator = [(i,r['original'],r['zh']) for i,r in rows.items()]
        else:
            iterator = [(s+':'+i,r['original'],r['zh']) for s,m in rows.items() for i,r in m.items()]
        counts[name] = len(iterator)
        for ident,original,zh in iterator:
            bad=[]
            if '\ufffd' in zh or re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]',zh):
                bad.append('malformed_display_text')
            if name in {'title_overrides_reviewed_zh.json','classclef_titles_zh.json'}:
                if any(zh.count(a)!=zh.count(b) for a,b in [('《','》'),('〈','〉'),('（','）')]):
                    bad.append('unbalanced_title_delimiters')
                for en,cn,code in false_friends:
                    if re.search(en,original,re.I) and re.search(cn,zh):
                        bad.append(code)
            if bad:
                issues.append({'asset':name,'id':ident,'original':original,'zh':zh,'flags':bad})
    return {'scope':counts, 'issue_count':len(issues), 'issues':issues,
            'boundary':'Full structural and specified music-context sweep. Not independent authoritative-name certification or a claim that every retained/legacy reference has been philologically reviewed.'}


def _atomic_json(path: Path, data: dict) -> None:
    temporary = path.with_suffix(path.suffix+'.part')
    temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    os.replace(temporary,path)


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('.'))
    parser.add_argument('--review',type=Path,default=Path(DEFAULT_REVIEW))
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    root=args.root.resolve()
    review_path=args.review if args.review.is_absolute() else root/args.review
    review=json.loads(review_path.read_text())
    documents,counts=prepare_review(root,review)
    audit=audit_assets(root,documents)
    if audit['issues']:
        raise ValueError('prepared review contains structural or specified musical false-friend errors')
    if args.apply and counts.get('pending_changes'):
        backups=root/'work/translation-review'/review['reviewed_at']/'legacy-assets-before'
        backups.mkdir(parents=True,exist_ok=True)
        for name,document in documents.items():
            path=root/'metadata/translations'/name
            backup=backups/name
            if not backup.exists():
                backup.write_bytes(path.read_bytes())
            _atomic_json(path,document)
    result={'applied':bool(args.apply), 'review':str(review_path.relative_to(root)),
            'counts':counts,'audit':audit}
    if args.report:
        report=args.report if args.report.is_absolute() else root/args.report
        report.parent.mkdir(parents=True,exist_ok=True)
        _atomic_json(report,result)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
