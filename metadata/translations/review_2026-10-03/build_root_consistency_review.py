"""Compile fully read, exact-ID title consistency decisions; never merge records."""
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT/'scripts'))
from catalog_translations import wrap_display_title

corpus_path = ROOT/'work/title-review/2026-10-03/corpus.json'
corpus = json.loads(corpus_path.read_text())
if isinstance(corpus, dict):
    corpus = corpus['entries']
source = {row['id']:row for row in corpus}
entries, seen = [], set()
for line in (HERE/'root_consistency_readings.tsv').read_text().splitlines():
    ident, title = line.split('\t')
    assert ident in source and ident not in seen
    seen.add(ident)
    row = source[ident]
    zh = wrap_display_title(title)
    refs = []
    reason = '完整审读相同原题与署名的不同来源记录，统一参考语序、术语与已有中文对应；每个来源ID独立保留。'
    if re.search(r'\bdomino\s+noir\b',row['original'],re.I):
        refs = ['https://www.opera-comique.com/fr/spectacles/le-domino-noir-2024',
                'https://www.dictionnaire-academie.fr/article/A8D1848']
        reason = '依据歌剧首演机构剧情与法兰西学院词义，domino在此指带兜帽的化装斗篷；采用参考意译，不误作多米诺骨牌或面纱。'
    if ident in {'classclef:94940d4d3b2d45ea7436c26a', 'guitarschool:1098'}:
        refs = ['https://ndltd.ncl.edu.tw/cgi-bin/gs32/gsweb.cgi?o=dnclcdr&s=id%3D%22090NTNU0248008%22.&searchmode=basic']
        reason = '对照音乐诠释研究中的原题与中文对应，采用戈雅的美人，避免把女性称谓机械音译成专名。'
    entries.append(dict(id=ident, source_id=row['source_id'], original=row['original'],
        original_composer=row['composer'], display_original=row['display_original'],
        zh=zh, display_zh=zh, status='reference', basis='exact_full_title_consistency_review',
        reason=reason, source_refs=refs, review_method='cross_source_exact_semantic_consistency_2026_10_04',
        reviewer='Codex 2026-10-04'))
assert len(entries) == 63
output = HERE/'root_cross_source_consistency_supplement.json'
output.write_text(json.dumps({'schema_version':1,'entries':entries},ensure_ascii=False,indent=2)+'\n')
report = dict(records=len(entries), source_identity_merge=False,
    original_attribution_display_guards=True, statuses={'reference':63},
    input_sha256=hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
    output_sha256=hashlib.sha256(output.read_bytes()).hexdigest())
(ROOT/'work/title-review/2026-10-03/consistency-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
