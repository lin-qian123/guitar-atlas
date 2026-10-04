"""Regression cases for actual music-domain failures and review boundaries."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from review_source_translations import TERMS
from title_translation_quality import contextual_draft_repair, review_title_entry, terminology_grammar


@pytest.mark.parametrize(('source','expected'),[
    ('Op. 1 Douze Valses','作品1：十二首圆舞曲'),
    ('Op. 1 Waltz','作品1：圆舞曲'),
    ('Opus 50 No. 1','作品50：第1号'),
    ('8 Petites Pièces for Guitar, No. 1','8首吉他小品，第1号'),
    ('Six Progressive Studies: No. I','六首渐进练习曲：第I号'),
    ('Study in A Minor','A小调练习曲'),
    ('Ricercar en la mineur','A小调里切尔卡尔'),
    ('Prelude in E-flat minor','降E小调前奏曲'),
    ('Allegretto in A','A调小快板'),
    ('Andantino mosso','稍活跃的小行板'),
    ('Slur Studies','连音练习'),
    ('String Crossing','换弦'),
    ('Sonata for Guitar','吉他奏鸣曲'),
    ('BWV 1005 Prelude','BWV 1005 前奏曲'),
    ('Etude II','练习曲 II'),
    ('Spagnoletta','斯帕尼奥莱塔舞曲'),
    ('Maxixe','马希谢舞曲'),
    ('A New Guitar Method','新吉他教程'),
])
def test_complete_music_title_grammar(source,expected):
    assert terminology_grammar(source,TERMS)==expected


def test_exact_declared_attribution_only():
    assert terminology_grammar('Dionisio Aguado, Op. 3 Huit Petites Pièces',TERMS,'Dionisio Aguado')=='作品3：八首小品'
    assert terminology_grammar('Another Aguado, Op. 3 Huit Petites Pièces',TERMS,'Dionisio Aguado') is None
    assert terminology_grammar('25 Etudes, Op.60 by Carcassi',TERMS,'Carcassi')=='25首练习曲，作品60'
    assert terminology_grammar('25 Etudes, Op.60 by Carcassi',TERMS,'Carcassi, Matteo') is None


@pytest.mark.parametrize('source',[
    'Andantino named after a hidden fictional city','Major','Minor',
    'Sonata with Unknown Instrument','A Secret Title',
    'Op. 9-1. b-moll Nocturne No.1','No. 2 / unfamiliar lyric incipit / title-page price',
])
def test_unknown_semantics_and_ambiguous_notes_not_reviewed(source):
    assert terminology_grammar(source,TERMS) is None


def draft(original,zh):
    return {'original':original,'zh':zh,'status':'machine','basis':'google_reference_draft','reason':'未复核。'}


def test_partial_term_repair_does_not_upgrade_machine_draft():
    original='Op. 10 Air from the unknown ballet'
    row,changes=review_title_entry('test:1',original,'',draft(original,'《操作。10 空气来自未知芭蕾舞团》'),TERMS)
    assert row['zh']=='《作品10 曲调来自未知芭蕾舞剧》'
    assert row['status']=='machine'
    assert 'opus_abbreviation' in changes
    assert 'air_is_melody' in changes
    assert row['original']==original


@pytest.mark.parametrize('separator',[':', '：'])
def test_opus_colon_is_musical_work_number(separator):
    source='Op'+separator+' 22 Sonata'
    assert terminology_grammar(source,TERMS)=='作品22：奏鸣曲'


def test_archival_opus_colon_operand_repair_stays_machine():
    source='Grande / SONATE / pour la / Guitare seule / Composée et dédiée / au Prince de la Paix / PAR / F. SOR. / Op: 22 / Prix 1 Fr. 50 Cs. / Bonn chez N. Simrock PN 2814 [1830] . 11 pp. Engraved.'
    zh='《大奏鸣曲 / 为吉他而作 / F. SOR. / 操作数：22 / 价格1 Fr.50 Cs. / N. Simrock PN2814 [1830]，11页。》'
    row,changes=review_title_entry('dga:12298',source,'Sor, F.',draft(source,zh),TERMS)
    assert '操作数' not in row['zh']
    assert '作品22' in row['zh']
    assert row['status']=='machine'
    assert row['original']==source
    assert changes==['opus_abbreviation']


def test_safe_closed_grammar_upgrades_only_complete_semantic_context():
    source='Study in A Minor'
    row,_=review_title_entry('test:1',source,'',draft(source,'《未成年人学习》'),TERMS)
    assert row['status']=='reference'
    assert row['zh']=='《A小调练习曲》'


@pytest.mark.parametrize(('source','zh'),[
    ('Unknown title, Op. 47','《未知标题，作品》'),
    ('Unknown title, Op. 47 No. 5','《未知标题，作品47第4号》'),
    ('Unknown title in A minor','《未成年人未知标题》'),
    ('Unknown title','《未知《标题》'),
])
def test_unsafe_draft_is_retained_with_reason_and_exact_original(source,zh):
    row,changes=review_title_entry('test:1',source,'',draft(source,zh),TERMS)
    assert row['zh']=='《'+source+'》'
    assert row['status']=='retained'
    assert row['reason']
    assert 'unsafe_draft_retained_original' in changes


def test_rank_word_repair_guarded_by_source_number():
    assert contextual_draft_repair('Unknown, No. 3','《未知，第3名》')[0]=='《未知，第3号》'
    assert contextual_draft_repair('Third place','《第3名》')[0]=='《第3名》'


def test_quoted_archival_lyric_not_treated_as_etude_genre():
    source='Unknown song / ' + 'title-page attribution and publication data '*12 + "/ L'Etude est inutile..."
    assert contextual_draft_repair(source,'《未知歌，学习毫无用处》')[0]=='《未知歌，学习毫无用处》'


def test_two_tempo_movements_remain_distinct():
    source='Andantino, Andante, op. 241, no. 5'
    assert terminology_grammar(source,TERMS)=='小行板，行板，作品241，第5号'


def test_mixed_major_minor_context_does_not_overwrite_both_keys():
    source='Unreviewed two-section title: D major and D minor'
    assert contextual_draft_repair(source,'《未知标题：D专业和D未成年人》')[0]=='《未知标题：D大调和D小调》'


@pytest.mark.parametrize(('source','draft_zh','expected'),[
    ('Unknown title in E Flat Major','《未知曲目降E大调》','《未知曲目降E大调》'),
    ('Unknown title in F Sharp Major','《未知曲目升 升升F大调》','《未知曲目升F大调》'),
    ('Unknown title in B flat minor','《未知曲目降降B小调》','《未知曲目降B小调》'),
])
def test_accidental_key_repair_is_idempotent(source,draft_zh,expected):
    first,_=contextual_draft_repair(source,draft_zh)
    second,_=contextual_draft_repair(source,first)
    assert first==expected
    assert second==expected


def test_source_review_requires_exact_title_and_attribution_guards():
    source='Unknown title';current=draft(source,'《未知标题》')
    overrides={'test:1':{'original':source,'original_composer':'Person A','zh':'《未知标题》','status':'reference','basis':'exact_review','reason':'逐项复核。'}}
    with pytest.raises(ValueError,match='stale title or attribution'):
        review_title_entry('test:1',source,'Person B',current,TERMS,overrides)
    with pytest.raises(ValueError,match='stale original'):
        review_title_entry('test:1','Changed title','Person A',current,TERMS,overrides)
    assert review_title_entry('test:1',source,'Person A',current,TERMS,overrides)[0]['status']=='reference'


def test_retained_original_is_not_promoted_by_nonempty_text():
    source='El Macareno';current=draft(source,'《马卡雷诺酒店》')
    override={'original':source,'original_composer':'Aguado','zh':'《El Macareno》','status':'retained','basis':'exact_review','reason':'原题为专名，原作没有酒店释义。'}
    row,_=review_title_entry('test:1',source,'Aguado',current,TERMS,{'test:1':override})
    assert row['status']=='retained'
    assert row['reason']==override['reason']
    override['status']='reference'
    with pytest.raises(ValueError,match='requires a Chinese rendering'):
        review_title_entry('test:1',source,'Aguado',current,TERMS,{'test:1':override})


def test_exact_assets_cover_reported_asturias_and_both_numbers():
    path=Path(__file__).resolve().parents[1]/'metadata/translations/source_title_quality_review_zh.json'
    reviewed=json.loads(path.read_text())['entries']['cglib:1088']
    assert reviewed['original']=='Op. 47 Suite Espanola No. 1 5. Asturias (Leyenda)'
    assert reviewed['zh']=='《西班牙组曲第1号，作品47：第5曲“阿斯图里亚斯（传奇）”》'
    assert reviewed['status']=='reference'
    assert reviewed['original_composer']=='Albeniz. Isaac'
