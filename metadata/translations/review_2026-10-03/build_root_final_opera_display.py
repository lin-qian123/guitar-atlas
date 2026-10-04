"""Five exact final opera-title correspondences; do not merge source records."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT/'scripts'))
from apply_title_review import FILES, SUPPLEMENT_FILES, validate_decisions, overlay_supplements

def read(path):
    return json.loads(path.read_text())

corpus = read(ROOT/'work/title-review/2026-10-03/corpus.json')
if isinstance(corpus, dict):
    corpus = corpus['entries']
by = {r['id']:r for r in corpus}
base = validate_decisions(corpus, [read(HERE/name) for name in FILES])
base = overlay_supplements(corpus, base, [read(HERE/name) for name in SUPPLEMENT_FILES])
readings = {
    'cglib:21246': ('Mefistofele', 'Boito. Arrigo', '《梅菲斯托斐斯》'),
    '74884': ("Fantaisie sur des motifs de 'Zampa', Op.40", 'Carcassi, Matteo', '《〈Zampa〉主题幻想曲，作品40》'),
    '859391': ("3 Rondos on Favorite Melodies from 'Zampa'", 'Schultz, Leonard', '《〈Zampa〉著名旋律主题的三首回旋曲》'),
    '1179497': ("Potpourri aus 'Zampa'", 'Busch, J.G.', '《〈Zampa〉集成曲》'),
    '1418216': ('Fantasy on Zampa de Hérold', 'Alexeeff, Konstantin', '《Hérold歌剧〈Zampa〉主题幻想曲》'),
}
entries = []
for ident, (original, composer, title) in readings.items():
    old = base[ident]
    assert old['original'] == original and old['original_composer'] == composer
    reference = ('https://www.chncpa.org/subsite/NCPAO2023-24/pdf/index/17-18.pdf'
                 if ident == 'cglib:21246' else 'https://www.opera-comique.com/fr/spectacles/zampa-ou-la-fiancee-de-marbre')
    reason = ('国家大剧院双语曲目给出博伊托歌剧的中文对应，统一参考题名。'
              if ident == 'cglib:21246' else '来源明确引用Zampa歌剧，保留未取得合适中文对应的原名，翻译完整音乐结构；跨源显示一致，不合并版本。')
    entries.append(dict(old, before_zh=old['zh'], before_display_zh=old.get('display_zh', old['zh']),
                        display_original=by[ident]['display_original'], zh=title, display_zh=title,
                        reason=reason, source_refs=list(dict.fromkeys([*old.get('source_refs', []), reference])),
                        review_method='exact_final_opera_display_correspondence_2026_10_04'))
out = ROOT/'work/title-review/2026-10-03/archive-review/display-final/root-opera-output.json'
out.write_text(json.dumps({'schema_version':1, 'entries':entries}, ensure_ascii=False, indent=2)+'\n')
print('Frozen exact opera display repairs:', len(entries))
