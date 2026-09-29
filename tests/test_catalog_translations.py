from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from catalog_translations import apply_translations, fallback, translation_summary
from export_public_site import build_public_catalog, PublicExportError
from render_offline_site import refresh_display_metadata
from tests.basic_helpers import ROOT
from tests.test_catalog_sources import add_source
from tests.test_public_site import make_library, write_json
from tests.test_master_index import offline_library, render
from validate_public_site import validate_payload, PublicSiteValidationError


def asset(root, original='Lagrima', zh='《泪》'):
    entry = {'original': original, 'zh': zh, 'status': 'reference',
             'basis': 'music_title_review', 'reason': '参考译名；保留原文。', 'aliases_zh': ['眼泪']}
    write_json(root / 'metadata/translations/classclef_titles_zh.json',
               {'schema_version': 1, 'entries': {'classclef:42': entry}})


def test_persistent_translation_survives_source_metadata_rebuild(tmp_path):
    make_library(tmp_path)
    add_source(tmp_path)
    asset(tmp_path)
    first = build_public_catalog(tmp_path)
    add_source(tmp_path)  # Acquisition deliberately writes blank Chinese fields again.
    second = build_public_catalog(tmp_path)
    assert first == second
    work = next(r for r in second['works'] if r['id'] == 'classclef:42')
    assert work['title_zh'] == '《泪》'
    assert work['title_en'] == 'Lagrima'
    assert work['title_aliases'] == ['眼泪']
    assert work['translation']['title']['status'] == 'reference'
    assert work['translation_status'] == 'untranslated'  # Composer is still missing.
    assert second['translation_summary'] == translation_summary(second)
    validate_payload(second)


@pytest.mark.parametrize('fault', ['original', 'identity'])
def test_stale_translation_cannot_silently_relabel_another_record(tmp_path, fault):
    make_library(tmp_path)
    add_source(tmp_path)
    asset(tmp_path, original='Other title' if fault == 'original' else 'Lagrima')
    if fault == 'identity':
        p=tmp_path/'metadata/translations/classclef_titles_zh.json'
        data=json.loads(p.read_text()); data['entries']['classclef:absent']=data['entries'].pop('classclef:42')
        write_json(p,data)
    with pytest.raises(PublicExportError, match='drift|absent'):
        build_public_catalog(tmp_path)


@pytest.mark.parametrize('zh', ['', 'Lagrima', '《Lagrima》', '1984', '   '])
def test_unreviewed_non_chinese_text_is_untranslated_not_retained(zh):
    display, proof = fallback('Lagrima', zh)
    assert display == ''
    assert proof == {'status': 'untranslated', 'basis': '', 'reason': ''}


def test_fallback_distinguishes_missing_original_and_unreviewed_chinese():
    assert fallback('', '')[1]['status'] == 'not_applicable'
    assert fallback('Lagrima', '《泪》')[1]['status'] == 'machine'


def test_only_explicit_asset_can_retain_source_spelling(tmp_path):
    make_library(tmp_path)
    add_source(tmp_path)
    data = build_public_catalog(tmp_path)
    work = next(r for r in data['works'] if r['source_id'] == 'classclef')
    category = next(r for r in data['categories'] if r['source_id'] == 'classclef')
    work['title_zh'] = '《Lagrima》'
    work['composer_zh'] = work['composer_en']
    category['name_zh'] = category['name']
    apply_translations(tmp_path, data)
    assert work['title_zh'] == work['composer_zh'] == category['name_zh'] == ''
    assert work['translation']['title']['status'] == 'untranslated'
    assert work['translation']['composer']['status'] == 'untranslated'
    assert category['translation']['status'] == 'untranslated'

    asset(tmp_path, zh='《Lagrima》')
    path = tmp_path / 'metadata/translations/classclef_titles_zh.json'
    review = json.loads(path.read_text())
    review['entries']['classclef:42'].update(
        status='retained', basis='explicit_title_review',
        reason='该源题作为专名保留原文，尚未确认稳定中文定名。')
    write_json(path, review)
    apply_translations(tmp_path, data)
    assert work['title_zh'] == '《Lagrima》'
    assert work['translation']['title']['status'] == 'retained'


@pytest.mark.parametrize('missing_id', ['99', 'classclef:42'])
def test_reviewed_imslp_title_ids_must_exist_in_imslp_snapshot(tmp_path, missing_id):
    make_library(tmp_path)
    add_source(tmp_path)
    data = build_public_catalog(tmp_path)
    imslp = next(r for r in data['works'] if r['source_id'] == 'imslp')
    valid = {'work_id': imslp['id'], 'title_en': imslp['title_en'],
             'title_zh': '《经复核的参考曲名》', 'basis': 'corpus_review',
             'reason': '逐题语义复核。'}
    path = tmp_path / 'metadata/translations/title_overrides_reviewed_zh.json'
    write_json(path, {'schema_version': 1, 'entries': [valid]})
    apply_translations(tmp_path, copy.deepcopy(data))
    orphan = dict(valid, work_id=missing_id)
    write_json(path, {'schema_version': 1, 'entries': [valid, orphan]})
    with pytest.raises(ValueError, match='IMSLP titles absent from current snapshot'):
        apply_translations(tmp_path, copy.deepcopy(data))


def test_broken_inline_source_download_link_is_not_exported(tmp_path):
    make_library(tmp_path)
    raw=add_source(tmp_path)
    original='Naquele Tempo a href=”http://www.classclef.com/midi/example.mid”>MIDI'
    raw['works'][0]['title_en']=original
    write_json(tmp_path/'sources/classclef/catalog.json',raw)
    asset(tmp_path,original=original,zh='《当时》')
    data=build_public_catalog(tmp_path)
    work=next(r for r in data['works'] if r['id']=='classclef:42')
    assert work['title_en']=='Naquele Tempo'
    assert 'source_title_note' in work
    assert json.loads((tmp_path/'sources/classclef/catalog.json').read_text())['works'][0]['title_en']==original
    validate_payload(data)
    work['title_en']=original
    with pytest.raises(PublicSiteValidationError,match='forbidden public'):
        validate_payload(data)


def test_metadata_refresh_preserves_all_verified_parts_and_backup(tmp_path):
    offline_library(tmp_path)
    _,html,old=render(tmp_path)
    # Change only display text; there are no title overrides in this fixture.
    for category in old['data']['categories']:
        path=tmp_path/category['name']/'metadata/catalog.json'
        rows=json.loads(path.read_text()); rows[0]['title_zh']='《新参考译名》';write_json(path,rows)
    report=refresh_display_metadata(tmp_path)
    assert report['checked_local_paths']==4
    assert 'PDF integrity' in report['refresh_method']
    assert '《新参考译名》' in (tmp_path/'index.html').read_text()
    assert any(p.read_text()==html for p in (tmp_path/'backups/offline-ui').glob('*.html'))


def test_metadata_refresh_refuses_missing_links_and_source_drift(tmp_path):
    offline_library(tmp_path)
    _,_,old=render(tmp_path)
    path=tmp_path/'For guitar/metadata/catalog.json'
    rows=json.loads(path.read_text());rows[0]['title_en']='Different work';write_json(path,rows)
    with pytest.raises((PublicExportError,ValueError),match='drift|changed'):
        refresh_display_metadata(tmp_path)


def test_committed_music_names_do_not_repeat_dictionary_mistranslations():
    names=json.loads((ROOT/'metadata/translations/musicians_zh.json').read_text())['entries']['imslp']
    for original,bad in [('Verotta, Davide','税收'),('Versluis, Tyler','闭嘴'),('Kellner, David','服务员'),('Schüler, Wilhelm','学生'),('Sor, Carlos','姐姐')]:
        assert bad not in names[original]['zh']
        assert names[original]['status'] in {'reference','reviewed'}
    for original in ['Chen, Yihan','Shen, Yichuan']:
        assert names[original]['zh']==original
        assert names[original]['status']=='retained'
        assert names[original]['reason']
    titles=json.loads((ROOT/'metadata/translations/title_overrides_reviewed_zh.json').read_text())['entries']
    by_id={r['work_id']:r for r in titles}
    assert by_id['395329']['title_zh']=='《斯帕尼奥莱塔舞曲》'
    assert by_id['759582']['title_zh']=='《帕萨卡利亚舞曲》'


@pytest.mark.parametrize('work_id,required', [
    ('187515','拉格泰姆'), ('817377','肖罗'), ('172790','吉格'),
    ('83177','两把小提琴'), ('884758','A小调'), ('356851','第三调式'),
    ('1579333','17. str: 1738'),
])
def test_reviewed_titles_keep_music_meaning_and_identity(work_id,required):
    rows=json.loads((ROOT/'metadata/translations/title_overrides_reviewed_zh.json').read_text())['entries']
    entry=next(row for row in rows if row['work_id']==work_id)
    assert required in entry['title_zh']
