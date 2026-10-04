import csv
import io
import json
from pathlib import Path

import pytest

from refresh_legacy_category_display import (
    current_translations, html_links, refresh, refresh_csv, refresh_html, refresh_markdown,
)


def fixture_data():
    works=[{'work_id':'17','title_en':'Theme (with notes), Op.7','composer':'Smith, John',
            'title_zh':'《旧误译》','composer_zh':'旧名','imslp_url':'https://imslp.org/wiki/Theme_(Smith,_John)',
            'score_file_count':1,'relative_directory':'scores/Smith, John/Theme'}]
    reviewed={'17':{'work_id':'17','title_en':works[0]['title_en'],'original_composer':'Smith, John',
                    'title_zh':'《主题，作品7（完整参考说明）》','display_zh':'《主题，作品7》',
                    'display_original':works[0]['title_en'],'status':'corrected','basis':'semantic_correction',
                    'reason':'逐项检查。','reviewer':'Test','source_refs':[]}}
    musicians={'Smith, John':{'original':'Smith, John','zh':'约翰·史密斯','status':'reference','basis':'checked','reason':''}}
    manifest=[{**{k:works[0][k] for k in ['work_id','title_en','composer','imslp_url']},
               'composer_zh':'旧名','filename':'part.pdf','relative_path':'scores/Smith, John/Theme/part.pdf',
               'file_id':'99','expected_size':13,'description':'Guitar 1 Part'}]
    html='''<html><details open data-composer="Smith, John｜旧名"><summary>Smith, John｜旧名</summary>
<article class="work" data-search="smith, john 旧名 theme (with notes), op.7 《旧误译》">
<div class="en">Theme (with notes), Op.7</div>
<div class="zh">《旧误译》</div>
<div class="links"><a href="https://imslp.org/wiki/Theme_(Smith,_John)">IMSLP 原页</a> <a href="scores/Smith%2C%20John/Theme/part.pdf">Guitar 1 Part</a></div>
</article></details></html>'''
    md='''# Library
### Smith, John｜旧名

- **英文名：** Theme (with notes), Op.7
  - **中文名：** 《旧误译》
  - **来源：** [IMSLP](https://imslp.org/wiki/Theme_(Smith,_John))
  - **乐谱：** [Guitar 1 Part](scores/Smith%2C%20John/Theme/part.pdf)
'''
    return works,reviewed,musicians,manifest,html,md


def csv_bytes(rows, fields):
    out=io.StringIO(newline='')
    writer=csv.DictWriter(out,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    return b'\xef\xbb\xbf'+out.getvalue().encode()


def make_library(tmp_path):
    works,reviewed,musicians,manifest,html,md=fixture_data()
    category=tmp_path/'For 2 guitars'
    (category/'metadata').mkdir(parents=True)
    (tmp_path/'config').mkdir()
    (tmp_path/'config/categories.json').write_text(json.dumps({'schema_version':1,'categories':[{
        'name':category.name,'kind':'original','url':'https://imslp.org/wiki/Category:For_2_guitars'}]}))
    (tmp_path/'config/mixed_categories.json').write_text(json.dumps({'schema_version':1,'categories':[]}))
    tr=tmp_path/'metadata/translations';tr.mkdir(parents=True)
    (tr/'title_overrides_reviewed_zh.json').write_text(json.dumps({'schema_version':1,'entries':list(reviewed.values())}))
    (tr/'musicians_zh.json').write_text(json.dumps({'schema_version':1,'entries':{'imslp':musicians}}))
    (category/'metadata/catalog.json').write_text(json.dumps(works))
    (category/'metadata/score_manifest.json').write_text(json.dumps(manifest))
    (category/'index.html').write_text(html)
    for name in ['README.md','乐谱库目录.md']:(category/name).write_text(md)
    work_rows=[{**w,'score_paths':manifest[0]['relative_path']} for w in works]
    (category/'catalog.csv').write_bytes(csv_bytes(work_rows,['composer','composer_zh','title_en','title_zh','imslp_url','score_file_count','relative_directory','score_paths']))
    (category/'score_manifest.csv').write_bytes(csv_bytes(manifest,['composer','composer_zh','title_en','filename','description','file_id','relative_path','imslp_url']))
    pdf=category/manifest[0]['relative_path'];pdf.parent.mkdir(parents=True);pdf.write_bytes(b'NOT A REAL PDF')
    return category,pdf


def test_refresh_keeps_full_native_search_and_exact_links():
    works,reviewed,musicians,manifest,html,md=fixture_data()
    translated=current_translations(Path('.'),works,reviewed,musicians)
    result=refresh_html(html,translated)
    assert html_links(result)==html_links(html)
    assert '<div class="en">Theme (with notes), Op.7</div>' in result
    assert 'theme (with notes), op.7' in result
    assert 'title="《主题，作品7（完整参考说明）》">《主题，作品7》' in result
    assert 'Smith, John｜约翰·史密斯' in result
    after_md=refresh_markdown(md,translated)
    assert '[Guitar 1 Part](scores/Smith%2C%20John/Theme/part.pdf)' in after_md
    assert '**英文名：** Theme (with notes), Op.7' in after_md
    assert '**中文名：** 《主题，作品7》' in after_md


@pytest.mark.parametrize('field,value',[('title_en','Another theme'),('composer','Jones, John')])
def test_reviewed_original_or_attribution_drift_rejected(field,value):
    works,reviewed,musicians,*_=fixture_data()
    works[0][field]=value
    with pytest.raises(ValueError,match='drift'):
        current_translations(Path('.'),works,reviewed,musicians)


def test_primary_display_guard_rejects_boundary_drift():
    works,reviewed,musicians,*_=fixture_data()
    reviewed['17']['display_original']='Different primary boundary'
    with pytest.raises(ValueError,match='primary title original drift'):
        current_translations(Path('.'),works,reviewed,musicians)


def test_empty_primary_translation_is_rejected():
    works,reviewed,musicians,*_=fixture_data()
    reviewed['17']['display_zh']=''
    with pytest.raises(ValueError,match='primary title empty'):
        current_translations(Path('.'),works,reviewed,musicians)


def test_existing_html_source_or_original_drift_rejected():
    works,reviewed,musicians,_,html,_=fixture_data()
    translated=current_translations(Path('.'),works,reviewed,musicians)
    with pytest.raises(ValueError,match='original drift'):
        refresh_html(html.replace('<div class="en">Theme','<div class="en">Corrupted'),translated)
    with pytest.raises(ValueError,match='mapping drift'):
        refresh_html(html.replace('wiki/Theme_','wiki/Wrong_'),translated)


def test_manifest_csv_mapping_drift_rejected():
    works,reviewed,musicians,manifest,*_=fixture_data()
    translated=current_translations(Path('.'),works,reviewed,musicians)
    raw=csv_bytes([{**manifest[0],'file_id':'wrong'}],['composer','composer_zh','title_en','filename','file_id','relative_path','imslp_url'])
    with pytest.raises(ValueError,match='mapping drift'):
        refresh_csv(raw,translated,manifest,file_manifest=True)


def test_dry_run_then_backup_apply_preserves_metadata_and_never_reads_pdf(tmp_path,monkeypatch):
    category,pdf=make_library(tmp_path)
    all_before={p:p.read_bytes() for p in category.rglob('*') if p.is_file()}
    real_read=Path.read_bytes
    def reject_pdf_read(path):
        if path.suffix=='.pdf':raise AssertionError('display refresh must not read PDF bytes')
        return real_read(path)
    monkeypatch.setattr(Path,'read_bytes',reject_pdf_read)
    report=tmp_path/'work/refresh'
    dry=refresh(tmp_path,report)
    assert dry['mode']=='dry_run' and dry['changed_files']==5
    assert not (report/'backup').exists()
    assert all(real_read(p)==data for p,data in all_before.items())
    result=refresh(tmp_path,report,apply=True)
    assert result['mode']=='applied' and result['offline_input_fingerprint_unchanged']
    assert real_read(pdf)==all_before[pdf]
    for file in ['catalog.json','score_manifest.json']:
        p=category/'metadata'/file
        assert real_read(p)==all_before[p]
    for name in ['index.html','README.md','乐谱库目录.md','catalog.csv','score_manifest.csv']:
        backup=report/'backup'/category.name/name
        assert real_read(backup)==all_before[category/name]
    old=list(csv.DictReader(io.StringIO(all_before[category/'catalog.csv'].decode('utf-8-sig'))))[0]
    new=list(csv.DictReader(io.StringIO((category/'catalog.csv').read_text(encoding='utf-8-sig'))))[0]
    assert new['display_title_zh']=='《主题，作品7》'
    assert new['title_zh']=='《主题，作品7（完整参考说明）》'
    assert {k:v for k,v in old.items() if k not in {'composer_zh','title_zh'}}=={
        k:v for k,v in new.items() if k not in {'composer_zh','title_zh','display_title_zh'}}
    again=refresh(tmp_path,tmp_path/'work/idempotent')
    assert again['changed_files']==0


def test_apply_refuses_original_drift_before_backup_or_write(tmp_path):
    category,_=make_library(tmp_path)
    index=category/'index.html';bad=index.read_text().replace('<div class="en">Theme','<div class="en">Corrupt')
    index.write_text(bad)
    with pytest.raises(ValueError,match='original drift'):
        refresh(tmp_path,tmp_path/'work/rejected',apply=True)
    assert index.read_text()==bad
    assert not (tmp_path/'work/rejected/backup').exists()
