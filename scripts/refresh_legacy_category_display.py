#!/usr/bin/env python
"""Refresh existing IMSLP category views without rebuilding source metadata.

Only Chinese display text/search terms and Chinese CSV columns can change.
Native titles, attributions, ordering, every link and the source manifests are
checked before planning and after writing. No PDF bytes are read or modified.
The default is a dry run; --apply backs up every existing view before writes.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import os
import re
import shutil
import tempfile
from collections import Counter
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

from catalog_display import apply_display_projection
from catalog_translations import checked_entry, display_source_title, read_asset, wrap_display_title
from export_public_site import configured_categories
from imslp_library.title_review import load_reviewed_titles
from render_offline_site import offline_input_fingerprint

VIEW_FILES = ('index.html', 'README.md', '乐谱库目录.md', 'catalog.csv', 'score_manifest.csv')
DISPLAY_COLUMNS = {'title_zh', 'composer_zh', 'display_title_zh'}
ARTICLE = re.compile(r'<article class="work"\s+data-search="[^"]*">.*?</article>', re.S)
MD_WORK = re.compile(
    r'^- \*\*英文名：\*\* (?P<title>[^\n]*)\n'
    r'  - \*\*中文名：\*\* (?P<zh>[^\n]*)\n'
    r'  - \*\*来源：\*\* \[IMSLP\]\((?P<url>[^\n]*)\)$', re.M)


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def fail(message: str):
    raise ValueError(message)


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.values = []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in {'href', 'src'}:
                self.values.append((tag, key, value))


def html_links(text: str) -> list:
    parser = Links()
    parser.feed(text)
    return parser.values


def current_translations(root: Path, works: list[dict], reviewed: dict, musicians: dict) -> dict:
    result = {}
    for work in works:
        identity = str(work['work_id'])
        row = reviewed.get(identity)
        if not row or row['title_en'] != work['title_en']:
            fail(f'legacy title original drift: {identity}')
        if row.get('original_composer') != work['composer']:
            fail(f'legacy title attribution drift: {identity}')
        musician = musicians.get(work['composer'])
        if musician is None:
            fail(f'legacy musician review missing: {work["composer"]}')
        composer_zh, _ = checked_entry(musician, work['composer'], f'imslp: {work["composer"]}')
        full_zh = wrap_display_title(display_source_title(row['title_zh']))
        projected = {'id': identity, 'source_id': 'imslp', 'title_en': work['title_en'],
                     'title_zh': full_zh, 'composer_en': work['composer'], 'composer_zh': composer_zh}
        apply_display_projection(projected)
        if 'display_zh' in row:
            if row.get('display_original') != projected.get('display_title_en', work['title_en']):
                fail(f'legacy primary title original drift: {identity}')
            if not isinstance(row['display_zh'],str) or not row['display_zh'].strip():
                fail(f'legacy primary title empty: {identity}')
            primary = wrap_display_title(display_source_title(row['display_zh']))
        else:
            primary = projected.get('display_title_zh', full_zh)
        if not isinstance(primary,str) or not primary.strip() or primary == '《》':
            fail(f'legacy primary title empty: {identity}')
        result[work['imslp_url']] = {**work, 'title_zh': full_zh, 'display_title_zh': primary,
                                    'composer_zh': composer_zh,
                                    'display_composer_zh': projected.get('display_composer_zh', composer_zh)}
    if len(result) != len(works):
        fail('duplicate source URL in category')
    return result


def refresh_html(text: str, translations: dict) -> str:
    seen = []
    def article(match):
        old = match.group(0)
        urls = [url for tag,key,url in html_links(old) if tag == 'a' and key == 'href' and url.startswith('https://imslp.org/wiki/')]
        if len(urls) != 1 or urls[0] not in translations:
            fail('legacy HTML source/work mapping drift')
        work = translations[urls[0]]
        names = re.findall(r'<div class="en">(.*?)</div>',old,re.S)
        if len(names) != 1 or html.unescape(names[0]) != work['title_en']:
            fail(f'legacy HTML original drift: {work["work_id"]}')
        seen.append(urls[0])
        search = ' '.join([work['composer'],work['composer_zh'],work['display_composer_zh'],
                           work['title_en'],work['title_zh'],work['display_title_zh']]).casefold()
        if work['title_en'].casefold() not in search:
            fail('full source title missing from search')
        value,n = re.subn(r'data-search="[^"]*"',lambda _: 'data-search="'+html.escape(search,quote=True)+'"',old,count=1)
        if n != 1: fail('legacy HTML search field drift')
        value,n = re.subn(r'<div class="zh"(?:\s+[^>]*)?>.*?</div>',
                         lambda _: '<div class="zh" title="'+html.escape(work['title_zh'],quote=True)+'">'+html.escape(work['display_title_zh'])+'</div>',value,count=1,flags=re.S)
        if n != 1: fail('legacy HTML Chinese field drift')
        return value
    updated,n = ARTICLE.subn(article,text)
    if n != len(translations) or Counter(seen) != Counter(translations.keys()):
        fail('legacy HTML membership drift')
    composers = {w['composer']: w['display_composer_zh'] for w in translations.values()}
    def group(match):
        attribute,label = map(html.unescape,match.groups())
        matches=[name for name in composers if label.startswith(name+'｜')]
        if len(matches) != 1 or attribute != label: fail('legacy HTML attribution group drift')
        label=html.escape(matches[0]+'｜'+composers[matches[0]],quote=True)
        return '<details open data-composer="'+label+'"><summary>'+label+'</summary>'
    updated,count = re.subn(r'<details open data-composer="([^"]*)"><summary>(.*?)</summary>',group,updated)
    if count != len(composers): fail('legacy HTML attribution count drift')
    if html_links(updated) != html_links(text): fail('legacy HTML link invariance failed')
    # Scrub only the permitted Chinese/search slots; all original titles,
    # source labels, layout, counters, scripts and href bytes must be identical.
    def frozen(value):
        value=re.sub(r'data-search="[^"]*"','data-search="DISPLAY"',value)
        value=re.sub(r'<div class="zh"(?:\s+[^>]*)?>.*?</div>','<div class="zh">DISPLAY</div>',value,flags=re.S)
        value=re.sub(r'data-composer="([^"]*)"',lambda m:'data-composer="'+m[1].split('｜')[0]+'｜DISPLAY"',value)
        value=re.sub(r'<summary>(.*?)</summary>',lambda m:'<summary>'+m[1].split('｜')[0]+'｜DISPLAY</summary>',value)
        return value
    if frozen(text) != frozen(updated): fail('legacy HTML non-display fields changed')
    return updated


def refresh_markdown(text: str, translations: dict) -> str:
    seen=[]
    def work(match):
        url=match['url']
        if url not in translations or match['title'] != translations[url]['title_en']:
            fail('legacy Markdown original/work mapping drift')
        seen.append(url)
        start=match.start('zh')-match.start()
        end=match.end('zh')-match.start()
        return match[0][:start]+translations[url]['display_title_zh']+match[0][end:]
    updated,count=MD_WORK.subn(work,text)
    if count != len(translations) or Counter(seen) != Counter(translations.keys()):
        fail('legacy Markdown membership drift')
    composers={w['composer']:w['display_composer_zh'] for w in translations.values()}
    def group(match):
        label=match[1]
        names=[name for name in composers if label.startswith(name+'｜')]
        if len(names)!=1: fail('legacy Markdown attribution group drift')
        return '### '+names[0]+'｜'+composers[names[0]]
    updated,count=re.subn(r'^### ([^\n]*)$',group,updated,flags=re.M)
    if count != len(composers): fail('legacy Markdown attribution count drift')
    def frozen(value):
        value=re.sub(r'^  - \*\*中文名：\*\* [^\n]*$', '  - **中文名：** DISPLAY',value,flags=re.M)
        return re.sub(r'^### ([^\n]*?)｜[^\n]*$',r'### \1｜DISPLAY',value,flags=re.M)
    if frozen(text)!=frozen(updated): fail('legacy Markdown non-display fields changed')
    return updated


def cell(value) -> str:
    return '' if value is None else str(value)


def refresh_csv(raw: bytes, translations: dict, manifest: list[dict], *, file_manifest: bool) -> bytes:
    original=raw.decode('utf-8-sig')
    reader=csv.DictReader(io.StringIO(original,newline=''))
    fields=reader.fieldnames
    if not fields: fail('legacy CSV header missing')
    rows=list(reader)
    old_rows=[dict(r) for r in rows]
    if file_manifest:
        if len(rows)!=len(manifest): fail('legacy manifest CSV membership drift')
        for row,record in zip(rows,manifest,strict=True):
            for key in fields:
                if key not in DISPLAY_COLUMNS and row.get(key)!=cell(record.get(key,'')):
                    fail(f'legacy manifest CSV/source mapping drift: {key}, {record.get("relative_path")}')
    else:
        if len(rows)!=len(translations): fail('legacy catalog CSV membership drift')
        paths={}
        for record in manifest: paths.setdefault(str(record['work_id']),[]).append(record['relative_path'])
        if Counter(row['imslp_url'] for row in rows)!=Counter(translations.keys()):
            fail('legacy catalog CSV source identity drift')
        for row in rows:
            work=translations[row['imslp_url']]
            for key in fields:
                if key in DISPLAY_COLUMNS: continue
                expected=' | '.join(paths.get(str(work['work_id']),[])) if key=='score_paths' else cell(work.get(key,''))
                if row[key]!=expected: fail(f'legacy catalog CSV/source mapping drift: {key}, {work["work_id"]}')
        if 'display_title_zh' not in fields: fields=[*fields,'display_title_zh']
    for row in rows:
        work=translations.get(row['imslp_url'])
        if not work or row['title_en']!=work['title_en'] or row['composer']!=work['composer']:
            fail('legacy CSV original/attribution drift')
        row['composer_zh']=work['composer_zh']
        if not file_manifest:
            row['title_zh']=work['title_zh']
            row['display_title_zh']=work['display_title_zh']
    for old,new in zip(old_rows,rows,strict=True):
        if {k:v for k,v in old.items() if k not in DISPLAY_COLUMNS}!={k:v for k,v in new.items() if k not in DISPLAY_COLUMNS}:
            fail('legacy CSV non-display fields changed')
    buffer=io.StringIO(newline='')
    writer=csv.DictWriter(buffer,fieldnames=fields,lineterminator='\r\n' if '\r\n' in original else '\n')
    writer.writeheader();writer.writerows(rows)
    return (b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'')+buffer.getvalue().encode('utf-8')


def stat_snapshot(paths: set[Path]) -> dict:
    states={}
    for path in sorted(paths):
        try:
            s=path.stat()
            states[str(path)]=(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        except FileNotFoundError:
            states[str(path)]=None
    return states


def refresh(root: Path, report_dir: Path, *, apply: bool=False) -> dict:
    root=root.resolve();report_dir=report_dir.resolve()
    if not report_dir.is_relative_to(root / 'work'): fail('private report must remain under project work/')
    fingerprint=offline_input_fingerprint(root)
    reviewed_path=root/'metadata/translations/title_overrides_reviewed_zh.json'
    musician_path=root/'metadata/translations/musicians_zh.json'
    reviewed=load_reviewed_titles(reviewed_path)
    musicians=read_asset(root,'musicians_zh.json').get('imslp',{})
    protected={str(reviewed_path.relative_to(root)):digest(reviewed_path.read_bytes()),
               str(musician_path.relative_to(root)):digest(musician_path.read_bytes())}
    planned=[];score_paths=set();membership=[];original_search_count=0;total_links=0
    categories=configured_categories(root)
    for category in categories:
        directory=root/str(category['name'])
        catalog_path=directory/'metadata/catalog.json';manifest_path=directory/'metadata/score_manifest.json'
        catalog_bytes=catalog_path.read_bytes();manifest_bytes=manifest_path.read_bytes()
        protected[str(catalog_path.relative_to(root))]=digest(catalog_bytes)
        protected[str(manifest_path.relative_to(root))]=digest(manifest_bytes)
        works=json.loads(catalog_bytes);manifest=json.loads(manifest_bytes)
        translations=current_translations(root,works,reviewed,musicians)
        by_id={str(w['work_id']):w for w in works}
        if len(by_id)!=len(works): fail('duplicate native work ID in category')
        for record in manifest:
            work=by_id.get(str(record['work_id']))
            if not work or any(record[key]!=work[key] for key in ['title_en','composer','imslp_url']):
                fail('legacy manifest native identity drift')
            relative=PurePosixPath(record['relative_path'])
            if relative.is_absolute() or '..' in relative.parts or not relative.parts or relative.parts[0]!='scores':
                fail('unsafe source manifest path')
            path=directory/relative
            if not path.resolve().is_relative_to(root): fail('source score path escapes library')
            score_paths.add(path)
        membership.append({'category':category['name'],'work_ids':[str(w['work_id']) for w in works],
                           'manifest_records':len(manifest)})
        for name in VIEW_FILES:
            path=directory/name
            old=path.read_bytes()
            if name=='index.html':
                text=old.decode('utf-8');new=refresh_html(text,translations).encode('utf-8')
                total_links+=len(html_links(text));original_search_count+=len(translations)
                for tag,key,href in html_links(text):
                    if not href:continue
                    parsed=urlsplit(href)
                    if parsed.scheme or parsed.netloc:continue
                    relative=PurePosixPath(unquote(parsed.path))
                    if relative.is_absolute() or '..' in relative.parts or '\\' in parsed.path:fail('unsafe existing HTML link')
                    local=directory/relative
                    if not local.resolve().is_relative_to(root):fail('existing HTML link escapes library')
                    if local not in score_paths:fail('existing local HTML link lacks category manifest mapping')
            elif name.endswith('.md'):
                new=refresh_markdown(old.decode('utf-8'),translations).encode('utf-8')
            else:new=refresh_csv(old,translations,manifest,file_manifest=name=='score_manifest.csv')
            planned.append({'path':path,'old':old,'new':new})
    before_stats=stat_snapshot(score_paths)
    def check_inputs():
        if offline_input_fingerprint(root)!=fingerprint:fail('offline input fingerprint changed')
        for relative,sha in protected.items():
            if digest((root/relative).read_bytes())!=sha:fail(f'protected source/review input changed: {relative}')
        if stat_snapshot(score_paths)!=before_stats:fail('score file availability/stat changed during display refresh')
    check_inputs()
    changed=[p for p in planned if p['old']!=p['new']]
    report_dir.mkdir(parents=True,exist_ok=True)
    backup_dir=None
    if apply:
        backup_dir=report_dir/'backup'
        if backup_dir.exists():fail('backup directory already exists; use a fresh private report directory')
        # Complete all backups before replacing any view. Verify the exact
        # source bytes again to reject concurrent/stale edits.
        for item in planned:
            path=item['path']
            if path.read_bytes()!=item['old']:fail('legacy view changed after planning')
            target=backup_dir/path.relative_to(root)
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,target)
            if target.read_bytes()!=item['old']:fail('backup bytes mismatch')
        check_inputs()
        for item in changed:
            path=item['path']
            if path.read_bytes()!=item['old']:fail('legacy view changed before write')
            fd,temp=tempfile.mkstemp(prefix='.'+path.name+'.display-',dir=path.parent)
            try:
                with os.fdopen(fd,'wb') as stream:stream.write(item['new']);stream.flush();os.fsync(stream.fileno())
                os.chmod(temp,path.stat().st_mode)
                os.replace(temp,path)
            finally:
                if os.path.exists(temp):os.unlink(temp)
        for item in planned:
            if item['path'].read_bytes()!=item['new']:fail('written view readback mismatch')
    check_inputs()
    summary={'schema_version':1,'mode':'applied' if apply else 'dry_run','timestamp':datetime.now().astimezone().isoformat(),
             'categories_checked':len(categories),'html_pages_checked':len(categories),'view_files_checked':len(planned),
             'changed_files':len(changed),'changed_files_by_name':dict(Counter(p['path'].name for p in changed)),
             'category_work_memberships':sum(len(c['work_ids']) for c in membership),
             'unique_native_work_ids':len({identifier for c in membership for identifier in c['work_ids']}),
             'manifest_records':sum(c['manifest_records'] for c in membership),'score_paths_stat_checked':len(score_paths),
             'missing_score_paths_unchanged':sum(s is None for s in before_stats.values()),
             'html_href_src_sequence_checked':total_links,'full_native_title_search_checked':original_search_count,
             'source_metadata_and_review_sha_unchanged':True,'offline_input_fingerprint_unchanged':True,
             'offline_input_fingerprint':fingerprint,'protected_sha256':protected,
             'backup_directory':str(backup_dir.relative_to(root)) if backup_dir else None,
             'scope':'Display-only: no source metadata rebuilt, no PDF bytes read, parsed, hashed or modified; prior file validation/exclusions retained.',
             'memberships':membership,'score_stat_snapshot':before_stats,
             'files':[{'path':str(p['path'].relative_to(root)),'before_sha256':digest(p['old']),
                       'after_sha256':digest(p['new']),'changed':p['old']!=p['new']} for p in planned]}
    (report_dir/('applied.json' if apply else 'dry-run.json')).write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    return {key:value for key,value in summary.items() if key not in {'memberships','score_stat_snapshot','files','offline_input_fingerprint','protected_sha256'}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--report-dir',type=Path,default=Path('work/title-review/2026-10-03/legacy-display-refresh'))
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    report_dir=args.report_dir if args.report_dir.is_absolute() else args.root/args.report_dir
    print(json.dumps(refresh(args.root,report_dir,apply=args.apply),ensure_ascii=False,indent=2))


if __name__=='__main__': main()
