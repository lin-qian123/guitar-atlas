"""Compile 49 complete, exact Weiss manuscript-title readings."""
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from catalog_translations import wrap_display_title

source_path = ROOT / 'work/title-review/2026-10-03/cglib-retained-pass/archive-weiss.json'
rows = json.loads(source_path.read_text())['entries']
source = {row['id']: row for row in rows}
readings = {}
for line in (HERE / 'cglib_weiss_readings.tsv').read_text().splitlines():
    ident, title = line.split('\t')
    assert ident in source and ident not in readings
    assert re.search(r'[\u3400-\u9fff]', title)
    readings[ident] = title
assert len(rows) == 49 and set(source) == set(readings)

entries = []
for row in rows:
    title = wrap_display_title(readings[row['id']])
    entries.append(dict(id=row['id'], source_id=row['source_id'], original=row['original'],
        original_composer=row['composer'], display_original=row['display_original'],
        zh=title, display_zh=title, status='reference',
        basis='exact_complete_title_reference_2026_10_03',
        reason='完整审读曲式、调性、作品目录与稿本信息；题录署名和归属声明保持为来源陈述，不改写作曲者身份。',
        review_method='full_title_hand_reading_2026_10_04', reviewer='Codex 2026-10-04', source_refs=[]))
by_id = {row['id']: row for row in entries}
# Semantic checks cover errors present in the previous drafts, rather than
# merely checking whether the compiler reproduced its input table.
assert '降B大调' in by_id['cglib:15943']['zh']
assert '降E小调' in by_id['cglib:15970']['zh']
assert '1721' in by_id['cglib:16007']['zh'] and '降B小调' in by_id['cglib:16007']['zh']
assert 'C大调与C小调' in by_id['cglib:16135']['zh']
assert '前奏曲与' in by_id['cglib:16104']['zh'] and '吉格舞曲' in by_id['cglib:16104']['zh']
assert '小品两首' in by_id['cglib:16157']['zh'] and '加沃特舞曲' in by_id['cglib:16157']['zh']
assert '题录归于' in by_id['cglib:16115']['zh']
assert by_id['cglib:16115']['original_composer'] == 'Weiss. Sylvius Leopold'
assert '低音组曲' in by_id['cglib:16076']['zh'] and '贝司' not in by_id['cglib:16076']['zh']
for row in entries:
    # Keep every Arabic catalogue number; explicit Deux / 2 pieces may use 两首.
    before = Counter(re.findall(r'\d+', row['original']))
    after = Counter(re.findall(r'\d+', row['zh']))
    if row['id'] in {'cglib:16157', 'cglib:16171'}:
        before.subtract({'2': 1})
        before = +before
    assert before == after, (row['id'], before, after)
output = HERE / 'cglib_retained_archive_weiss_supplement.json'
output.write_text(json.dumps({'schema_version':1, 'entries':entries}, ensure_ascii=False, indent=2)+'\n')
report = dict(records=len(rows), statuses={'reference':49}, semantic_checks=9,
    full_original_attribution_display_guards=True, unresolved_number_clues=0,
    input_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),
    output_sha256=hashlib.sha256(output.read_bytes()).hexdigest())
(ROOT/'work/title-review/2026-10-03/cglib-retained-pass/weiss-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report, ensure_ascii=False, indent=2))
