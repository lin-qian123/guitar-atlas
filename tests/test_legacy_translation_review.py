import copy
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from apply_legacy_translation_review import ASSETS, DEFAULT_REVIEW, audit_assets, prepare_review


def review():
    return json.loads((ROOT/DEFAULT_REVIEW).read_text())


def current_assets():
    """Inspect current review assets without replaying an older before/after ledger."""
    return {name:json.loads((ROOT/'metadata/translations'/name).read_text())
            for name in ASSETS}


def historical_after(asset, ident):
    """The exact 2026-10-02 correction remains historical evidence, not a refresh."""
    for change in review()['changes']:
        if change['asset']!=asset:
            continue
        row=change['after']
        if (str(row.get('work_id')) if asset=='title_overrides_reviewed_zh.json'
                else change['path'][-1])==ident:
            return row
    raise AssertionError(f'missing historical correction: {asset}: {ident}')


def fixture_assets(tmp_path, changes):
    base=tmp_path/'metadata/translations'
    base.mkdir(parents=True)
    for change in changes:
        path=base/change['asset']
        doc=json.loads(path.read_text()) if path.exists() else {'schema_version':1,'entries':{}}
        cursor=doc['entries']
        for key in change['path'][:-1]:
            cursor=cursor.setdefault(key,{})
        cursor[change['path'][-1]]=copy.deepcopy(change['before'])
        path.write_text(json.dumps(doc,ensure_ascii=False))


def test_review_fixes_the_real_dictionary_false_friends():
    changes=review()['changes']
    by_id={c['before'].get('work_id'):c for c in changes if c['asset']=='title_overrides_reviewed_zh.json'}
    for ident,term in [('12479','维吉纳琴'),('42023','管风琴'),('62146','升圣体'),
                       ('519282','蒂恩托'),('1155901','肖罗'),('961331','号角'),
                       ('485396','塞法迪'),('1565288','鲁特琴'),('1603795','作品2529')]:
        assert term in by_id[ident]['after']['title_zh']
        assert by_id[ident]['before']['title_en']==by_id[ident]['after']['title_en']


def test_review_preserves_every_original_and_identity():
    for change in review()['changes']:
        original_key='title_en' if change['asset']=='title_overrides_reviewed_zh.json' else 'original'
        assert change['original']==change['before'][original_key]==change['after'][original_key]
        assert change['before'].get('work_id')==change['after'].get('work_id')
        assert change['after'].get('status')!='reviewed'


def test_current_assets_pass_full_structural_and_music_context_sweep():
    docs=current_assets()
    result=audit_assets(ROOT,docs)
    assert result['issue_count']==0
    assert sum(result['scope'].values())==28318
    assert set(result['scope'])==ASSETS


def test_single_name_and_source_category_display_stay_consistent():
    docs=current_assets()
    names=docs['musicians_zh.json']['entries']
    categories=docs['categories_zh.json']['entries']
    for original in ['Tarrega. Francisco','Giuliani. Mauro','Mertz. Johann Kaspar','Weiss. Sylvius Leopold']:
        row=names['cglib'][original]
        matching=[r for r in categories['cglib'].values() if r['original']==original]
        assert matching
        assert all(r['zh'] in {row['zh'],row['zh']+'作品'} for r in matching)
    assert names['imslp']['Bassols, Buenaventura']['zh']=='布埃纳文图拉·巴索尔斯'
    assert names['imslp']['Chen, Yihan']['status']=='retained'
    assert names['imslp']['Chen, Yihan']['zh']=='Chen, Yihan'


def test_uncertain_proper_names_are_retained_without_fake_context():
    docs=current_assets()
    titles={r['work_id']:r for r in docs['title_overrides_reviewed_zh.json']['entries']}
    assert titles['364476']['title_zh']=='《Mall Simmes》'
    assert titles['587874']['title_zh']=='《Curro cuchares》'
    assert titles['364476']['retention_reason']
    americano=docs['classclef_titles_zh.json']['entries']['classclef:0d2dc160dba75a35a39bab7a']
    assert americano['status']=='retained'
    assert americano['zh']=='《Americano》'
    assert americano['reason']
    assert '咖啡' not in americano['zh']


def test_preparation_is_idempotent_and_does_not_edit_files(tmp_path):
    change=next(c for c in review()['changes'] if c['asset']=='classclef_titles_zh.json')
    small={'schema_version':1,'reviewed_at':'2026-10-02','changes':[change]}
    fixture_assets(tmp_path,small['changes'])
    path=tmp_path/'metadata/translations'/change['asset']
    old=path.read_bytes()
    docs,count=prepare_review(tmp_path,small)
    assert path.read_bytes()==old
    assert count['pending_changes']==1
    path.write_text(json.dumps(docs[change['asset']],ensure_ascii=False))
    docs,count=prepare_review(tmp_path,small)
    assert count['already_applied']==1
    assert count.get('pending_changes',0)==0


@pytest.mark.parametrize('mutate', [
    lambda c:c['after'].update(original='Changed source title'),
    lambda c:c.update(asset='../unsafe.json'),
    lambda c:c['before'].update(zh='Concurrent changed display'),
])
def test_preparation_rejects_source_or_display_drift_before_any_write(tmp_path,mutate):
    change=copy.deepcopy(next(c for c in review()['changes'] if c['asset']=='classclef_titles_zh.json'))
    fixture_assets(tmp_path,[change])
    path=tmp_path/'metadata/translations'/change['asset']
    old=path.read_bytes()
    mutate(change)
    with pytest.raises(ValueError):
        prepare_review(tmp_path,{'schema_version':1,'reviewed_at':'2026-10-02','changes':[change]})
    assert path.read_bytes()==old


def test_review_scope_and_classclef_status_summary_are_fresh():
    docs=current_assets()
    titles=docs['classclef_titles_zh.json']
    assert titles['summary']['records']==len(titles['entries'])==6740
    assert sum(titles['summary']['status_counts'].values())==6740
    actual=Counter(row['status'] for row in titles['entries'].values())
    assert titles['summary']['status_counts']==dict(actual)
    assert set(actual)<={'reference','reviewed','retained'}
    assert all(row.get('reason') for row in titles['entries'].values()
               if row['status']=='retained')


def test_control_characters_do_not_survive_display_and_damage_remains_explicit():
    docs=current_assets()
    names=docs['musicians_zh.json']['entries']['dga']
    corrupted=[row for original,row in names.items() if '\x1a' in original]
    assert len(corrupted)==5
    assert all('\x1a' not in row['zh'] for row in corrupted)
    assert all('损坏' in row['reason'] for row in corrupted)
    holecek=names['Hole\x1aek, Josef, 1939-']
    assert holecek['status']=='retained'
    assert '…' in holecek['zh']


def test_same_exact_original_has_consistent_spelling_without_expanding_initials():
    docs=current_assets()
    musicians=docs['musicians_zh.json']['entries']
    spellings=defaultdict(set)
    for rows in musicians.values():
        for original,row in rows.items():
            spellings[original].add(row['zh'])
    assert all(len(values)==1 for values in spellings.values())
    assert musicians['mutopia']['D. Aguado']['zh']=='D.·阿瓜多'
    assert musicians['guitardownunder']['D. Aguado']['zh']=='D.·阿瓜多'
    assert musicians['dga']['Giuliani, M.']['zh']=='M.·朱利亚尼'


def test_roman_work_number_and_book_attribution_do_not_turn_into_invented_fields():
    docs=current_assets()
    titles={r['work_id']:r for r in docs['title_overrides_reviewed_zh.json']['entries']}
    assert titles['826224']['title_zh']=='《洛多梅里亚歌曲LXXIII》'
    names=docs['musicians_zh.json']['entries']['delcamp']
    book=names['Folger’s Dowland Lute Book']
    assert book['status']=='retained'
    assert book['zh']=='Folger’s Dowland Lute Book'
    assert '书名' in book['reason'] and '没有明确作曲者' in book['reason']
    mertz=names['Johann Kaspar Mertz Op. 14. Fantasie aus der Oper']
    assert mertz['zh']=='约翰·卡斯帕·默茨'
    assert '混入' in mertz['reason']


def test_only_the_frozen_exact_predecessor_is_accepted(tmp_path):
    change=copy.deepcopy(next(c for c in review()['changes']
                             if c['asset']=='musicians_zh.json' and c.get('accepted_predecessors')))
    fixture_assets(tmp_path,[change])
    path=tmp_path/'metadata/translations'/change['asset']
    document=json.loads(path.read_text())
    cursor=document['entries']
    for key in change['path'][:-1]:
        cursor=cursor[key]
    cursor[change['path'][-1]]=copy.deepcopy(change['accepted_predecessors'][0])
    path.write_text(json.dumps(document,ensure_ascii=False))
    before=path.read_bytes()
    _,counts=prepare_review(tmp_path,{'schema_version':1,'reviewed_at':'2026-10-02','changes':[change]})
    assert counts['pending_changes']==1 and path.read_bytes()==before
    cursor[change['path'][-1]]['zh']='Concurrent display edit'
    path.write_text(json.dumps(document,ensure_ascii=False))
    with pytest.raises(ValueError,match='translation row drift'):
        prepare_review(tmp_path,{'schema_version':1,'reviewed_at':'2026-10-02','changes':[change]})


def test_predecessor_cannot_accept_source_original_drift(tmp_path):
    change=copy.deepcopy(next(c for c in review()['changes']
                             if c['asset']=='musicians_zh.json' and c.get('accepted_predecessors')))
    fixture_assets(tmp_path,[change])
    change['accepted_predecessors'][0]['original']='Changed source attribution'
    with pytest.raises(ValueError,match='predecessor original/identity drift'):
        prepare_review(tmp_path,{'schema_version':1,'reviewed_at':'2026-10-02','changes':[change]})


def test_historical_bilingual_correction_has_explicit_ambiguity_and_sources():
    row=historical_after('title_overrides_reviewed_zh.json','1390180')
    assert row['title_en']=='Bribes No.1'
    assert row['title_zh']=='《Bribes第1号》'
    assert '法语' in row['retention_reason'] and '英语' in row['retention_reason']
    assert '不能凭作者国籍' in row['retention_reason']
    assert 'https://www.cnrtl.fr/definition/bribes' in row['source_refs']


def test_current_bilingual_ambiguity_retains_the_complete_original():
    row=next(r for r in current_assets()['title_overrides_reviewed_zh.json']['entries']
             if r['work_id']=='1390180')
    assert row['title_en']=='Bribes No.1'
    assert row['title_zh']=='《Bribes No.1》'
    assert all(term in row['retention_reason'] for term in ('法语','英语','国籍'))


def test_historical_replay_rejects_overwriting_the_current_title_review():
    change=copy.deepcopy(next(c for c in review()['changes']
                             if c['asset']=='title_overrides_reviewed_zh.json'
                             and c['after'].get('work_id')=='1390180'))
    path=ROOT/'metadata/translations'/change['asset']
    before=path.read_bytes()
    current=json.loads(before)['entries'][change['path'][0]]
    assert current['work_id']==change['after']['work_id']
    assert current['title_en']==change['original']
    assert current not in [change['before'],change['after'],
                           *change.get('accepted_predecessors',[])]
    with pytest.raises(ValueError,match='translation row drift'):
        prepare_review(ROOT,{'schema_version':1,'reviewed_at':'2026-10-02',
                             'changes':[change]})
    assert path.read_bytes()==before


def test_final_music_context_repairs_do_not_keep_literal_dictionary_mistakes():
    docs=current_assets()
    titles={r['work_id']:r for r in docs['title_overrides_reviewed_zh.json']['entries']}
    for ident,good,bad in [
        ('1171669','卡廷的慰藉','切割'),
        ('665218','微分音','微音调'),
        ('1236305','维奥尔琴','中提琴'),
        ('1358682','引子','引言'),
        ('789696','Guajira','瓜吉拉语'),
        ('1107769',"L'or est une chimère",'嵌合体'),
        ('1017092','胡桃树','婚礼'),
        ('1361324','加沃特舞曲','抽屉'),
        ('1497886','乡村舞曲','舞蹈病'),
        ('722751','3首简易华丽回旋曲','执行'),
    ]:
        assert good in titles[ident]['title_zh']
        assert bad not in titles[ident]['title_zh']
    grand_ids=['81765','1036809','1037265','1299619','1010954','998163',
               '1186439','1029251','1135151','1427055','1001514','865080',
               '1168495','1019070','1381312','1363849','1384475']
    assert all('伟大' not in titles[i]['title_zh'] for i in grand_ids)
    assert '大型小夜曲' in titles['1168495']['title_zh']


def test_cakewalk_is_one_dance_term_and_does_not_guess_an_unknown_name_meaning():
    docs=current_assets()
    titles={r['work_id']:r for r in docs['title_overrides_reviewed_zh.json']['entries']}
    assert titles['853276']['title_zh']=='《Flaxy Cunninghams凯克沃克舞曲》'
    assert titles['205387']['title_zh']=='《斯怀普西凯克沃克舞曲》'
    row=docs['classclef_titles_zh.json']['entries']['classclef:c3f7544ce80a6ad1a3271426']
    assert row['zh']=='《Koper凯克沃克舞曲》'
    assert row['status']=='reference' and row['reason']
    assert '铜' not in row['zh']
    historical=historical_after('classclef_titles_zh.json',
                               'classclef:c3f7544ce80a6ad1a3271426')
    assert historical['zh']=='《Koper凯克沃克舞曲》'
    assert '含义未确认' in historical['reason']
