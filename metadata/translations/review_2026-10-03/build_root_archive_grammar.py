"""ID-scoped complete readings after independently auditing long grammar output."""
import json
from pathlib import Path
from collections import Counter

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
pool = json.loads((ROOT/'work/title-review/2026-10-03/archive-review/root-grammar-long-extra.json').read_text())
rows = pool[:250]+pool[375:]
readings = {}
for line in (HERE/'root_archive_grammar_readings.tsv').read_text().splitlines():
    ident, value = line.split('|', 1)
    if 'dga:'+ident in readings:
        raise ValueError('duplicate '+ident)
    readings['dga:'+ident] = value
if set(readings) != {row['id'] for row in rows}:
    raise ValueError('frozen long-title partition coverage drift')
retentions = {
    '4605': '作品44的来源曲目列表在第15号后截断且括号未闭合；不猜补未载编号或补写剩余曲目，保留完整现存书目原文。',
    '4479': '来源只写Six pour la guitare，未提供所指数目的乐曲体裁；不从Sor作品8反推并补写嬉游曲，保留原题及编号。',
}
entries = []
for row in rows:
    ident = row['id'].split(':')[1]
    retained = ident in retentions
    value = readings[row['id']]
    entries.append({
        'id': row['id'], 'original': row['original'], 'original_composer': row['composer'],
        'display_original': row['display_original'],
        'zh': '《'+(row['original'] if retained else value)+'》',
        'display_zh': '《'+(row['display_original'] if retained else value)+'》',
        'status': 'retained' if retained else 'reference',
        'basis': 'exact_archive_original_retention_2026_10_03' if retained else 'exact_primary_title_semantic_reading_2026_10_03',
        'reason': retentions[ident] if retained else '完整审读长题名后直接整理自然中文语序；区分合集首数、声部与演奏者、曲中三声中部、乐器替代关系、册次及作品号。原文书目、责任句及截断标记保留，不从标题推定谱面编制。',
        'source_refs': [row['source_url']],
        'review_method': 'exact_original_retention' if retained else 'exact_primary_title_reading',
        'reviewer': 'Codex 2026-10-03',
    })
(HERE/'root_archive_grammar_supplement.json').write_text(json.dumps({'schema_version': 1, 'entries': entries},ensure_ascii=False,indent=2)+'\n')
print(len(entries), dict(Counter(row['status'] for row in entries)))
