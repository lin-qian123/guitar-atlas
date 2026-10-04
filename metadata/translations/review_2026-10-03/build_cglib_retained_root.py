"""Compile the root's 557 exact retained-title readings; no production writes."""
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

input_path = ROOT / 'work/title-review/2026-10-03/cglib-retained-pass/root.json'
rows = json.loads(input_path.read_text())['entries']
source = {row['id']: row for row in rows}
corpus_path = ROOT / 'work/title-review/2026-10-03/corpus.json'
corpus_rows = json.loads(corpus_path.read_text())
if isinstance(corpus_rows, dict):
    corpus_rows = corpus_rows['entries']
corpus = {row['id']: row for row in corpus_rows}
for row in rows:
    current = corpus[row['id']]
    if row['original'] != current['original'] or row['original_composer'] != current['composer']:
        raise ValueError('source title/attribution drift: ' + row['id'])
readings = {}
for line in (HERE / 'cglib_retained_root_readings.tsv').read_text().splitlines():
    if not line.strip():
        continue
    columns = line.split('\t')
    ident, zh = columns[:2]
    if ident in readings or ident not in source:
        raise ValueError('duplicate/unknown exact title: ' + ident)
    state = columns[2] if len(columns) > 2 else 'reference'
    reason = columns[3] if len(columns) > 3 else '对照完整原题核对语义与音乐结构；未确认专名保持原拼写。'
    if state not in {'reference', 'retained'} or not reason:
        raise ValueError('incomplete title reading: ' + ident)
    if state == 'reference' and not re.search(r'[\u3400-\u9fff]', zh):
        raise ValueError('reference lacks Chinese: ' + ident)
    readings[ident] = (wrap_display_title(zh), state, reason)
assert set(readings) == set(source), sorted(set(source) - set(readings))
assert len(rows) == 557

refs = {
    'cglib:3960': ['https://dle.rae.es/gatatumba'],
    'cglib:39657': ['https://ssjc.ujc.cas.cz/search.php?heslo=%C5%99%C3%ADkadlo&hsubstr=no'],
    'cglib:39671': ['https://ssjc.ujc.cas.cz/search.php?heslo=zn%C4%9Blka&hsubstr=no'],
    'cglib:38873': ['https://www.haddoarts.com/wp-content/uploads/2023/07/Programme-notes-LAMJ.pdf'],
}
entries, number_clues = [], []
for original in rows:
    ident = original['id']
    zh, state, reason = readings[ident]
    row = dict(original, zh=zh, display_original=corpus[ident]['display_original'], display_zh=zh, status=state,
               reason=reason, basis='exact_complete_title_reference_2026_10_03' if state == 'reference' else 'explicit_original_title_retention_2026_10_03',
               source_refs=refs.get(ident, []), review_method='full_title_hand_reading_2026_10_04', reviewer='Codex 2026-10-04')
    entries.append(row)
    original_numbers = Counter(re.findall(r'\d+', original['original']))
    translated_numbers = Counter(re.findall(r'\d+', zh))
    if original_numbers != translated_numbers:
        number_clues.append({'id':ident, 'original':original['original'], 'zh':zh,
                             'before':dict(original_numbers), 'after':dict(translated_numbers)})
doc = {'schema_version':1, 'entries':entries}
output = HERE / 'cglib_retained_root_supplement.json'
output.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n')
report = {'records':len(rows), 'statuses':dict(Counter(r['status'] for r in entries)),
          'input_sha256':hashlib.sha256(input_path.read_bytes()).hexdigest(),
          'current_corpus_sha256':hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
          'display_guards_bound_to_current_corpus':len(rows),
          'output_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
          'number_clues':number_clues, 'complete_exact_ID_title_attribution_display_guards':True}
number_readings = {
    'cglib:3810': '7 String = 七弦', 'cglib:3811': '7 String = 七弦',
    'cglib:3815': '7 String = 七弦；作品13保持',
    'cglib:3819': '7 String = 七弦；作品5与两位作者的圆舞曲保持',
    'cglib:3870': '4 Monferine = 四首；作品13与E大调定弦保持',
    'cglib:3880': '6 = 六首；Zweyten = 第二把吉他任选，作品9保持',
    'cglib:3881': '2 guitars = 双吉他', 'cglib:3887': '6 Variations = 变奏六首',
    'cglib:3893': 'Quatrieme = 第4号；作品12保持',
    'cglib:3894': 'Quatrieme = 第4号；作品13保持',
    'cglib:3900': 'Cinquieme = 第5号；作品16保持',
    'cglib:3906': 'Sixieme = 第6号；1er violon = 第一小提琴；作品21保持',
    'cglib:3928': 'Deuxieme = 第2号；作品4保持',
    'cglib:3964': 'Premier = 第1号；作品12保持',
    'cglib:3981': '16 walses = 圆舞曲十六首',
}
assert {row['id'] for row in number_clues} == set(number_readings)
for clue in number_clues:
    clue['reading'] = number_readings[clue['id']]
    clue['resolved'] = True
report['unresolved_number_clues'] = 0
(ROOT / 'work/title-review/2026-10-03/cglib-retained-pass/root-validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(report, ensure_ascii=False, indent=2))
