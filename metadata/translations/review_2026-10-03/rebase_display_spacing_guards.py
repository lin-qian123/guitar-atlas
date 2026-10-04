"""Rebase only the listed exact English spacing guards; dry-run by default.

Native titles/attributions and all semantic decisions remain unchanged. This
finishes the display-only spacing fix, without making publication guards fuzzy.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    root = here.parents[2]
    report_dir = root/'work/title-review/2026-10-03/display-spacing-rebase'
    plan = json.loads((here/'display_spacing_guard_rebase.json').read_text())
    changes = {row['id']: row for row in plan['entries']}
    assert len(changes) == len(plan['entries']) == 861
    for row in changes.values():
        assert re.sub(r'\s+', ' ', row['before_display_original']).strip() == row['display_original']
        assert row['before_display_original'] != row['display_original']
    corpus_path = root/'work/title-review/2026-10-03/corpus.json'
    corpus = json.loads(corpus_path.read_text())
    corpus_map = {row['id']: row for row in corpus}
    for ident, change in changes.items():
        row = corpus_map[ident]
        assert row['original'] == change['original'] and row['composer'] == change['original_composer']
        assert row['display_original'] in {change['before_display_original'], change['display_original']}
    paths = [corpus_path, *[here/name for name in (
        'legacy_decisions.json', 'cglib_decisions.json', 'archive_decisions.json', 'root_decisions.json',
        'root_cross_source_botanical_supplement.json', 'root_cross_source_consistency_supplement.json',
        'root_final_naturalness_supplement.json', 'root_final_credit_display_supplement.json')]]
    pending, receipt = [], []
    for path in paths:
        before = path.read_bytes()
        payload = json.loads(before)
        rows = payload if isinstance(payload, list) else payload['entries']
        changed = 0
        for row in rows:
            change = changes.get(row['id'])
            if change is None or 'display_original' not in row:
                continue
            assert row['original'] == change['original']
            assert row.get('composer', row.get('original_composer')) == change['original_composer']
            assert row['display_original'] in {change['before_display_original'], change['display_original']}
            if row['display_original'] != change['display_original']:
                row['display_original'] = change['display_original']
                changed += 1
        after = (json.dumps(payload, ensure_ascii=False, indent=2)+'\n').encode()
        receipt.append({'path': str(path.relative_to(root)), 'changed_display_guards': changed,
                        'before_sha256': hashlib.sha256(before).hexdigest(),
                        'after_sha256': hashlib.sha256(after).hexdigest() if changed else hashlib.sha256(before).hexdigest()})
        if changed:
            pending.append((path, before, after))
    if args.apply:
        from sys import path as module_path
        module_path.insert(0, str(root/'scripts'))
        from apply_title_review import atomic_json
        for path, before, after in pending:
            backup = report_dir/'before'/path.relative_to(root)
            backup.parent.mkdir(parents=True, exist_ok=True)
            if not backup.exists():
                backup.write_bytes(before)
            atomic_json(path, json.loads(after))
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir/('applied.json' if args.apply else 'dry-run.json')).write_text(
        json.dumps({'applied': args.apply, 'exact_record_ids': len(changes), 'files': receipt}, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
