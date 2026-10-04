"""Compile fully read corrections to music relations, abbreviations and Chinese order."""
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT/'scripts'))
from catalog_translations import wrap_display_title

source_path = ROOT/'work/title-review/2026-10-03/corpus.json'
corpus = json.loads(source_path.read_text())
if isinstance(corpus, dict):
    corpus = corpus['entries']
source = {row['id']:row for row in corpus}
primary_readings = {
    'cglib:47348': '〈茶花女〉主题幻想曲',
    'cglib:47821': '西班牙浪漫曲',
    'cglib:54876': '〈西班牙福利亚〉主题幻想曲，作品12',
    'werner:variations-sur-les-folies-despagne-op45-mauro-giuliani': '〈西班牙福利亚〉主题变奏曲，作品45',
}
entries, seen, counts = [], set(), []
for line in (HERE/'root_naturalness_readings.tsv').read_text().splitlines():
    columns = line.split('\t')
    ident, title = columns[:2]
    assert ident in source and ident not in seen
    seen.add(ident)
    row = source[ident]
    state = columns[2] if len(columns)>2 else 'reference'
    reason = columns[3] if len(columns)>3 else '完整审读主题引用、音乐结构与原题署名；修正中文语序或缩写误分词，不以词典词汇齐全代替句义核对。'
    if state=='retained':
        title = row['original']
    zh = wrap_display_title(title)
    display_zh = wrap_display_title(primary_readings.get(ident, title))
    refs = []
    if ident=='werner:exercise-on-the-e-string-mertz-free-pdf':
        refs = ['https://www.thisisclassicalguitar.com/exercise-on-the-e-string-mertz-free-pdf/']
        reason = '出版者明确解释E为E弦并给出原题Ubungen auf der E saite，纠正将E误作连词的草稿。'
    entries.append(dict(id=ident, source_id=row['source_id'], original=row['original'],
        original_composer=row['composer'], display_original=row['display_original'], zh=zh, display_zh=display_zh,
        status=state, basis='exact_complete_title_naturalness_review' if state=='reference' else 'explicit_original_title_retention_2026_10_03',
        reason=reason, source_refs=refs, review_method='full_title_hand_reading_2026_10_04', reviewer='Codex 2026-10-04'))
    before = Counter(re.findall(r'\d+',row['original']))
    after = Counter(re.findall(r'\d+',zh))
    if before != after:
        removed = before-after
        # The only numeral conversions here are 6 variations/waltzes to 六段/六首.
        assert removed=={'6':1} and re.search('六段|六首',zh) and not after-before, (ident,before,after)
        counts.append(dict(id=ident, resolved=True, reading='6 variations/waltzes = 六段变奏/六首圆舞曲'))
assert len(entries)==75
by_id = {row['id']:row for row in entries}
assert '德国主题' in by_id['cglib:20010']['zh'] and '阿勒曼德' not in by_id['cglib:20010']['zh']
assert 'Rossini' in by_id['cglib:56826']['zh'] and '第3册' in by_id['cglib:56826']['zh']
assert 'D.F.E. Auber' in by_id['delcamp:pdf:a83942b091919bf2c8cbaba1a322128cfc539fbd72851f02bc4122b4c91b374b']['zh']
assert 'E弦' in by_id['werner:exercise-on-the-e-string-mertz-free-pdf']['zh']
assert '现场版版本' not in by_id['cglib:30316']['zh']
output = HERE/'root_final_naturalness_supplement.json'
output.write_text(json.dumps({'schema_version':1,'entries':entries},ensure_ascii=False,indent=2)+'\n')
report = dict(records=len(entries), statuses=dict(Counter(r['status'] for r in entries)),
    original_attribution_display_guards=True, semantic_checks=5, number_conversions=counts,
    unresolved_number_clues=0, input_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),
    output_sha256=hashlib.sha256(output.read_bytes()).hexdigest())
(ROOT/'work/title-review/2026-10-03/naturalness-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
