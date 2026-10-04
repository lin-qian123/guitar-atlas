"""Exact, finite regional-title semantic repairs; no source/production writes."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
import apply_title_review as application

HERE = Path(__file__).resolve().parent
WORK = ROOT / 'work/title-review/2026-10-03/actual-toponym'
OUT = HERE / 'final_actual_toponym_decisions.json'

ARGENTINA = 'https://www.mofcom.gov.cn/dl/gbdqzn/upload/agenting.pdf'
SANTANDER = 'https://es.china-embassy.gov.cn/zxgx/201704/t20170425_3229469.htm'
BAHIA = 'https://br.china-embassy.gov.cn/gzbx/202104/t20210416_9079094.htm'
VALENCIA = 'https://es.china-embassy.gov.cn/chn/sghd/200406/t20040630_3229630.htm'
MENDOCINO = 'https://dle.rae.es/mendocino'
SALTENA = 'https://dle.rae.es/salte%C3%B1o'
BAIANA = 'https://dicionario.priberam.org/baiana'
PARISIENNE = 'https://catalogue.bnf.fr/ark:/12148/cb44858761h'

# Each entry was read with the complete original and exact native attribution.
# No vocabulary matching can add an entry or change unrelated feminine forms.
EDITS = {
    'cglib:49915': ('La mendozina, Op.41', 'Alais. Juan', '门多萨姑娘，作品41', None, 'Mendoza'),
    'cglib:13067': ('Op.41 La Mendozina (Zamacueca)', 'Alais. Juan', '门多萨姑娘（扎马库埃卡舞曲），作品41', None, 'Mendoza'),
    'cglib:54934': ('La mendozina, Op.41 (Alais, Juan)', 'Marieh Collection', '门多萨姑娘，作品41', None, 'Mendoza'),
    'cglib:48916': ('Santanderina', 'Azpiazu. Jose', '桑坦德姑娘', None, 'Santander'),
    'cglib:54930': ('La Salteña (Quijano, Pedro Miguel)', 'Marieh Collection', '萨尔塔姑娘', None, 'Salta'),
    'cglib:13250': ('(Quijano) La Saltena Zamacueca', 'Del Valle. Adela', '萨尔塔姑娘：扎马库埃卡舞曲', '萨尔塔姑娘：扎马库埃卡舞曲（原题署名：Quijano）', 'Salta'),
    'cglib:13580': ('La Saltena (Zamacueca)', 'Quijano. Pedro', '萨尔塔姑娘（扎马库埃卡舞曲）', None, 'Salta'),
    'cglib:13578': ('La Saltena (Zamacueca) para dos guitarras', 'Quijano. Pedro', '萨尔塔姑娘（扎马库埃卡舞曲，双吉他）', None, 'Salta'),
    'cglib:57000': ('La Salteña', 'Quijano. Pedro Miguel', '萨尔塔姑娘', None, 'Salta'),
    'cglib:39748': ('Conversa De Baiana by Dilermando Reis', 'Reis. Dilermando', '巴伊亚姑娘的谈话', None, 'Bahia'),
    'cglib:39762': ('Xodo Da Baiana by Dilermando Reis', 'Reis. Dilermando', '巴伊亚姑娘的心上人', None, 'Bahia'),
    'cglib:1785': ('Op. 332 La Parisienne, Marche nationale variee', 'Carulli. Ferdinando', '巴黎之歌：民族进行曲变奏，作品332', None, 'Parisienne'),
    'cglib:7197': ('Rapsodia valenciana', 'Pujol. Emilio', '瓦伦西亚狂想曲', None, 'Valencia'),
    'cglib:15686': ('Serenata salteña', 'Guestrin. Néstor', '萨尔塔小夜曲', None, 'Salta-adjective'),
}
REFERENCES = {
    'Mendoza': [ARGENTINA, MENDOCINO],
    'Salta': [ARGENTINA, SALTENA, 'https://isfd805-chu.infd.edu.ar/sitio/upload/BIBLIOTECA_ISFDA_N_805-INVENTARIO_PARTITURAS.pdf'],
    'Salta-adjective': [ARGENTINA, SALTENA],
    'Santander': [SANTANDER, 'https://dle.rae.es/santanderino', 'https://archivo.sgae.es/heritageobject/juventud--musica-facil-para-guitarra-en-dificultad-progresiva--cuaderno-ii--jose-de-azpiazu/'],
    'Bahia': [BAHIA, BAIANA],
    'Parisienne': [PARISIENNE],
    'Valencia': [VALENCIA],
}
REASONS = {
    'Mendoza': '对照完整舞曲题名与门多萨地域词义，采用自然参考译名门多萨姑娘，保留明确曲号/体裁；不据题名推定人物身份。',
    'Salta': '对照完整扎马库埃卡题名及萨尔塔地域词义，采用自然参考译名萨尔塔姑娘；不把女性形式统一当作音乐演员或作曲者。',
    'Salta-adjective': 'salteña在Serenata后是地域修饰语，不是女子或人名；使用成熟地名萨尔塔，保留小夜曲体裁。',
    'Santander': 'Santanderina在曲名中作地域女性名词，参考译作桑坦德姑娘；SGAE确认原曲题名，未凭词形推定具体女性身份。',
    'Bahia': 'Priberam的baiana为巴伊亚女子，整句以巴伊亚姑娘自然表达；保留谈话/心上人的完整题意，不补入实际人物。',
    'Parisienne': '原题明确Marche nationale variée；结合BnF记录的La Parisienne爱国歌曲主题语境，参考译作巴黎之歌的进行曲变奏，保留作品332，不机械译为巴黎女子或建立版本同一性。',
    'Valencia': 'valenciana修饰Rapsodia，是瓦伦西亚风格的狂想曲，不表示女性人物；保留明确音乐形式。',
}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    corpus = read(ROOT / 'work/title-review/2026-10-03/corpus.json')
    by_id = {r['id']: r for r in corpus}
    before = application.validate_decisions(corpus, [read(HERE / n) for n in application.FILES])
    before = application.overlay_supplements(corpus, before, [read(HERE / n) for n in application.SUPPLEMENT_FILES])
    before = application.overlay_display_repairs(corpus, before, read(HERE / application.DISPLAY_REPAIR_FILE))
    stage5 = {'schema_version': 1, 'entries': [r for n in application.FINAL_PROJECTION_FILES for r in read(HERE / n)['entries']]}
    before = application.overlay_display_repairs(corpus, before, stage5)
    metadata_ids = {r['id'] for r in read(ROOT / 'work/title-review/2026-10-03/archive-review/actual-headline-candidates.json')['rows']}
    assert len(EDITS) == 14 and not (set(EDITS) & metadata_ids)
    assert 'cglib:56152' not in EDITS and 'cglib:56152' in metadata_ids
    output, ledger = [], []
    for ident, (original, composer, primary, complete, group) in EDITS.items():
        old = before[ident]
        assert old['original'] == original and old['original_composer'] == composer
        assert old['status'] == 'reference' and old['display_original'] == by_id[ident]['display_original']
        e = deepcopy(old)
        e['before_zh'] = old['zh']
        e['before_display_zh'] = old.get('display_zh', old['zh'])
        e['display_original'] = by_id[ident]['display_original']
        e['zh'] = '《' + (complete or primary) + '》'
        e['display_zh'] = '《' + primary + '》'
        e['basis'] = 'exact_source_title_contextual_toponym_reference_2026_10_04'
        e['reason'] = REASONS[group]
        e['reviewer'] = 'Codex finite actual regional title semantics review 2026-10-04'
        e['review_method'] = 'exact_full_title_and_attribution_regional_context'
        e['source_refs'] = list(dict.fromkeys([*old.get('source_refs', []), by_id[ident]['source_url'], *REFERENCES[group]]))
        assert Counter(re.findall(r'\d+', e['before_display_zh'])) == Counter(re.findall(r'\d+', e['display_zh'])), ident
        for value in (e['zh'], e['display_zh']):
            assert value.count('《') == value.count('》') == 1
            assert value.count('（') == value.count('）') and value.count('〈') == value.count('〉')
        output.append(e)
        ledger.append({'id': ident, 'original': original, 'original_composer': composer,
                       'before_zh': old['zh'], 'before_display_zh': e['before_display_zh'],
                       'zh': e['zh'], 'display_zh': e['display_zh'], 'group': group, 'reason': e['reason'],
                       'source_refs': e['source_refs'], 'number_check': 'unchanged', 'stage5_guards': 'passed'})
    payload = {'schema_version': 1, 'entries': output}
    application.overlay_display_repairs(corpus, before, payload)
    other = HERE / 'final_actual_headline_decisions.json'
    other_ids = {r['id'] for r in read(other)['entries']} if other.exists() else metadata_ids
    assert not set(EDITS) & other_ids
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / 'ledger.json').write_text(json.dumps({'schema_version': 1, 'entries': ledger}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    public = read(ROOT / 'public_site/data/catalog.json')['works']
    candidates = []
    for row in public:
        title = row.get('display_title_zh', row['title_zh'])
        if ('女子' in title and re.search(r'[A-Za-z]+\s*女子', title)) or (row['source_id'] == 'cglib' and re.search(r'(asturiana|valenciana|française|francaise|santanderina|mendozina|saltena|salteña|baiana|italiana|cordobesa|granadina|sevillana|parisienne|parisiense)', row['title_en'], re.I)):
            candidates.append({'id': row['id'], 'original': row['title_en'], 'original_composer': row['composer_en'],
                               'before_display_zh': title,
                               'decision': 'exact correction' if row['id'] in EDITS else ('metadata owner and semantic proposal shared' if row['id'] == 'cglib:56152' else 'full title read; no correction needed in this regional feminine scope')})
    (WORK / 'finite-candidates.json').write_text(json.dumps({'schema_version': 1, 'entries': candidates}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    report = {'records': 14, 'statuses': {'reference': 14}, 'finite_title_pairs_read': len(candidates),
              'all_current_stage5_double_before_native_attribution_display_guards': 'passed',
              'all_music_number_multisets_unchanged': True, 'overlap_with_metadata_owner': 0,
              'cglib56152_owner': 'final_text_review; semantic proposal shared; no duplicate decision',
              'full_reference_Quijano_credit_preserved': output[5]['zh'].endswith('（原题署名：Quijano）》'),
              'source_fields_categories_identities_changed': 0, 'production_assets_changed': False,
              'whole_48449_candidate_overlay': 'passed', 'output_sha256': hashlib.sha256(OUT.read_bytes()).hexdigest()}
    (WORK / 'validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
