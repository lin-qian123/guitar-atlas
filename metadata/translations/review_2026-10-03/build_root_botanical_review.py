"""Compile exact cross-source Mertz botanical-title references, without merging IDs."""
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from catalog_translations import wrap_display_title

corpus_path = ROOT/'work/title-review/2026-10-03/corpus.json'
corpus = json.loads(corpus_path.read_text())
if isinstance(corpus, dict):
    corpus = corpus['entries']
source = {row['id']: row for row in corpus}
readings = {}
for line in (HERE/'root_botanical_readings.tsv').read_text().splitlines():
    ident, title = line.split('\t')
    assert ident in source and ident not in readings
    readings[ident] = title
scope = {row['id'] for row in corpus if re.search(r'\b(Cyanen|Nachtviolen)\b',row['original'],re.I)}
assert set(readings) == scope and len(readings) == 32
cyan_refs = [
    'https://publikationen.sulb.uni-saarland.de/bitstream/20.500.11880/30472/1/bognersaar.pdf',
    'https://www.iplant.cn/fsz/info/Centaurea%20cyanus',
]
violet_refs = [
    'https://www.halleonard.com/product/8551177/nachtviolen',
    'https://media.nativedsd.com/storage/nativedsd.com/wp-content/uploads/2020/07/02183610/MYR018.pdf',
]
entries = []
for ident, title in readings.items():
    row = source[ident]
    assert 'mertz' in row['composer'].casefold()
    zh = wrap_display_title(title)
    refs = (cyan_refs if 'cyan' in row['original'].casefold() else []) + (violet_refs if 'nachtviolen' in row['original'].casefold() else [])
    entries.append(dict(id=ident, source_id=row['source_id'], original=row['original'],
        original_composer=row['composer'], display_original=row['display_original'],
        zh=zh, display_zh=zh, status='reference', basis='exact_researched_botanical_title_reference',
        reason='核对历史德语植物词义、植物志中文名及出版资料；这是参考意译，不声称已有通行的中文乐曲名。完整原题与独立来源身份保留。',
        review_method='cross_source_exact_semantic_consistency_2026_10_04',
        reviewer='Codex 2026-10-04', source_refs=refs))
output = HERE/'root_cross_source_botanical_supplement.json'
output.write_text(json.dumps({'schema_version':1,'entries':entries},ensure_ascii=False,indent=2)+'\n')
report = dict(records=len(entries), input_sha256=hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
    output_sha256=hashlib.sha256(output.read_bytes()).hexdigest(), complete_exact_scope=True,
    source_identity_merge=False, statuses={'reference':32})
(ROOT/'work/title-review/2026-10-03/botanical-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
