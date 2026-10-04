#!/usr/bin/env python
"""Persist exact-text Chinese display assets; distinguish references and drafts.

Existing checked exact text and a small reviewed terminology grammar are reused.
Other titles may receive explicitly machine-marked reference drafts. Identity,
instrumentation and translation review are never inferred from Chinese presence.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime, timezone

from acquire_source_assets import atomic_json
from catalog_sources import load_registry
from catalog_translations import HAN, read_asset, wrap_display_title
from fill_translations import translate_batch
from title_translation_quality import review_title_entry, terminology_grammar

TERMS = {
    "allegretto":"小快板", "allegro":"快板", "andante":"行板", "andantino":"小行板", "adagio":"柔板", "largo":"广板", "lento":"慢板", "moderato":"中板", "presto":"急板", "vivace":"活板",
    "etude":"练习曲", "étude":"练习曲", "etudes":"练习曲", "études":"练习曲", "studies":"练习曲", "study":"练习曲", "exercise":"练习", "exercises":"练习", "exercices":"练习", "exercice":"练习", "lesson":"课题", "lessons":"课题",
    "waltz":"圆舞曲", "waltzes":"圆舞曲", "valse":"圆舞曲", "valses":"圆舞曲", "walzer":"圆舞曲", "valzer":"圆舞曲", "vals":"圆舞曲",
    "prelude":"前奏曲", "prélude":"前奏曲", "preludes":"前奏曲", "préludes":"前奏曲", "fantasia":"幻想曲", "fantasie":"幻想曲", "fantaisie":"幻想曲", "fantasy":"幻想曲",
    "sonata":"奏鸣曲", "sonate":"奏鸣曲", "sonatina":"小奏鸣曲", "sonatine":"小奏鸣曲", "rondo":"回旋曲", "rondeau":"回旋曲", "rondino":"小回旋曲", "polonaise":"波兰舞曲", "polonoise":"波兰舞曲", "polacca":"波兰舞曲",
    "minuet":"小步舞曲", "menuet":"小步舞曲", "menuetto":"小步舞曲", "minuetto":"小步舞曲", "mazurka":"玛祖卡", "mazurkas":"玛祖卡", "mazurca":"玛祖卡", "polka":"波尔卡", "galop":"加洛普舞曲",
    "gavotte":"加沃特舞曲", "gavota":"加沃特舞曲", "gigue":"吉格舞曲", "sarabande":"萨拉班德舞曲", "bourree":"布列舞曲", "bourrée":"布列舞曲", "allemande":"阿勒曼德舞曲", "courante":"库朗特舞曲",
    "march":"进行曲", "marche":"进行曲", "marches":"进行曲", "marsch":"进行曲", "nocturne":"夜曲", "nocturno":"夜曲", "notturno":"夜曲", "romance":"浪漫曲", "romanza":"浪漫曲", "serenade":"小夜曲", "serenata":"小夜曲",
    "caprice":"随想曲", "caprices":"随想曲", "capricho":"随想曲", "capriccio":"随想曲", "fugue":"赋格", "fuga":"赋格", "fughetta":"小赋格", "scherzo":"谐谑曲", "scherzando":"诙谐地", "bagatelle":"小品", "bagatelles":"小品", "tango":"探戈", "habanera":"哈巴涅拉", "bolero":"波莱罗", "cancion":"歌曲", "canción":"歌曲", "song":"歌曲", "songs":"歌曲", "air":"曲调", "aria":"咏叹调", "arietta":"小咏叹调",
    "variation":"变奏", "variations":"变奏曲", "variazioni":"变奏曲", "variationen":"变奏曲", "duet":"二重奏", "duets":"二重奏", "duo":"二重奏", "trio":"三重奏", "quartet":"四重奏", "quartetto":"四重奏",
    "guitar":"吉他", "guitars":"吉他", "guitare":"吉他", "guitarre":"吉他", "guitarra":"吉他", "chitarra":"吉他", "guitarren":"吉他", "solo":"独奏", "easy":"简易", "facile":"简易", "faciles":"简易", "facili":"简易", "simple":"简易", "simples":"简易", "short":"短", "petit":"小", "petite":"小", "petites":"小", "little":"小", "new":"新", "nouveau":"新", "nouvelle":"新", "brillante":"华丽", "brillant":"华丽", "cantabile":"如歌地", "grazioso":"优美地", "graziosa":"优美地", "espressivo":"富于表情地", "con":"以", "moto":"流动", "major":"大调", "minor":"小调", "dur":"大调", "moll":"小调", "maggiore":"大调", "minore":"小调", "sharp":"升", "flat":"降",
    "one":"一", "two":"二", "three":"三", "four":"四", "five":"五", "six":"六", "seven":"七", "eight":"八", "nine":"九", "ten":"十", "twelve":"十二", "twenty":"二十", "thirty":"三十", "forty":"四十", "fifty":"五十", "sixty":"六十", "cent":"一百", "douze":"十二", "six":"六", "trois":"三", "quatre":"四", "cinq":"五", "dix":"十", "vingt":"二十", "trente":"三十", "quarante":"四十", "cinquante":"五十",
}
FUNCTION_WORDS = {"in", "for", "a", "an", "the", "de", "des", "du", "d", "pour", "per", "et", "and", "und", "en", "on", "by", "aus", "di", "da", "del", "della", "le", "la", "les", "il", "i", "op", "opus", "no", "nr", "n", "nos", "vol", "volume", "book", "part", "bwv", "rv", "k", "kv", "wo", "woo", "d", "l", "s", "arr"}


def name_key(text):
    value = ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))
    return tuple(sorted(re.findall(r"[a-z]+", value.casefold())))


def entry(original, zh, status, basis, reason=""):
    return {"original":original, "zh":zh, "status":status, "basis":basis, "reason":reason}


def grammar_title(title, terms):
    words = re.findall(r"[A-Za-zÀ-ž]+", title)
    known = {key.casefold() for key in terms} | FUNCTION_WORDS | set("abcdefg")
    if not words or any(word.casefold() not in known for word in words):
        return None
    text = title
    for original in sorted(terms, key=len, reverse=True):
        text = re.sub(r"(?<![\w])"+re.escape(original)+r"(?![\w])", terms[original], text, flags=re.I)
    text = re.sub(r"\b(?:for|pour|per)\b", "为", text, flags=re.I)
    text = re.sub(r"\b(?:in|en)\b", "", text, flags=re.I)
    text = re.sub(r"\b(?:and|et|und)\b", "与", text, flags=re.I)
    if not HAN.search(text):
        return None
    return text


def build(root: Path, *, machine=False, workers=2):
    registry = [row for row in load_registry(root) if row['id'] not in {'imslp','classclef'}]
    catalogs = {row['id']:json.loads((root/row['catalog']).read_text()) for row in registry}
    outdir = root/'metadata/translations'
    titles = read_asset(root,'source_titles_zh.json')
    musicians = read_asset(root,'musicians_zh.json')
    categories = read_asset(root,'categories_zh.json')
    old_title_refs = defaultdict(set)
    reviewed = json.loads((outdir/'title_overrides_reviewed_zh.json').read_text())['entries']
    for row in reviewed:
        old_title_refs[row['title_en']].add(row['title_zh'])
    for row in read_asset(root,'classclef_titles_zh.json').values():
        if row['status'] in {'reference','reviewed'}:
            old_title_refs[row['original']].add(row['zh'])
    name_refs = defaultdict(set)
    for group in musicians.values():
        for original,row in group.items():
            if row['status'] in {'reviewed','reference'}:
                name_refs[name_key(original)].add(row['zh'])
    for original,zh in read_asset(root,'composer_overrides_reviewed_zh.json').items():
        name_refs[name_key(original)].add(zh)
    manual = {'terms':{}, 'titles':{}, 'musicians':{}, 'categories':{}}
    manual_path = outdir/'expansion_terminology_zh.json'
    if manual_path.exists():
        raw_manual = json.loads(manual_path.read_text())
        for row in raw_manual['entries']:
            context = row['context']
            group = ('titles' if context == 'exact_title' else 'musicians' if context == 'composer_attribution'
                     else 'categories' if context == 'source_category' else 'terms')
            manual[group][row['original']] = row
    terms = dict(TERMS)
    for row in manual.get('terms', {}).values():
        terms[row['original'].casefold()] = row['zh']
    quality_path = outdir/'source_title_quality_review_zh.json'
    quality_overrides = json.loads(quality_path.read_text())['entries'] if quality_path.exists() else {}
    manual_names = manual.get('musicians', {})
    cachepath = root/'sources/translations/draft_cache.json'
    cache = json.loads(cachepath.read_text()) if cachepath.exists() else {}
    missing = set()
    for catalog in catalogs.values():
        for work in catalog['works']:
            original = work['title_en']
            if len(old_title_refs[original]) == 1 or terminology_grammar(original, terms, work.get('composer_en','')):
                continue
            if original not in cache:
                missing.add(original)
    if machine and missing:
        values = sorted(missing)
        batches = [values[i:i+20] for i in range(0,len(values),20)]
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(translate_batch, batch):batch for batch in batches}
            for number,future in enumerate(as_completed(futures),1):
                for original,result in zip(futures[future],future.result()):
                    if result:
                        cache[original] = result
                atomic_json(cachepath,cache)
                if number % 20 == 0:
                    print(json.dumps({'translation_batches':number,'total_batches':len(batches),'cached_titles':len(cache)}),flush=True)
    report = {}
    current = set()
    for source,catalog in catalogs.items():
        musicians.setdefault(source,{})
        categories[source] = {}
        composer_names = {work['composer_en'] for work in catalog['works'] if work['composer_en']}
        for original in sorted(composer_names):
            if original in manual_names and (not manual_names[original].get('sources') or source in manual_names[original]['sources']):
                row=manual_names[original]
                musicians[source][original] = entry(original,row['zh'],'reference',row.get('basis','checked_music_name_variant'))
            elif len(name_refs[name_key(original)]) == 1:
                musicians[source][original] = entry(original,next(iter(name_refs[name_key(original)])),'reference','existing_exact_full_name_tokens','沿用已核全名对应；不合并来源人物身份。')
            elif original in {'Traditional','Trad.','Anonymous','Anonym','Anon.','Various','Various composers'}:
                zh = '传统曲调' if original in {'Traditional','Trad.'} else '多位作曲家' if original.startswith('Various') else '佚名'
                musicians[source][original] = entry(original,zh,'reference','checked_attribution_label')
            else:
                reason = '来源仅给缩写，无法据此唯一确认规范中文姓名。' if any(len(token)==1 for token in name_key(original)) else '本轮未获得该来源署名的可靠中文人名对应；保留完整原拼写供检索。'
                musicians[source][original] = entry(original,original,'retained','source_attribution_preservation',reason)
        # Prune only this source's stale entries; no changes to existing sources.
        musicians[source] = {name:row for name,row in musicians[source].items() if name in composer_names}
        for category in catalog['categories']:
            original = category['name']
            zh = None
            if original in manual.get('categories',{}):
                zh = manual['categories'][original]['zh']
            elif original in composer_names:
                row = musicians[source][original]
                if row['status'] != 'retained':zh = row['zh']+'作品'
            else:
                zh = grammar_title(original,terms)
            if zh:
                categories[source][str(category['id'])] = entry(original,zh,'reference','checked_source_category_label')
            else:
                categories[source][str(category['id'])] = entry(original,original,'retained','native_directory_identity','来源目录或馆藏索引标签，保留原始目录命名以便对照。')
        for work in catalog['works']:
            identity,original = work['id'],work['title_en'];current.add(identity)
            if len(old_title_refs[original]) == 1:
                zh,status,basis,reason = next(iter(old_title_refs[original])),'reference','existing_checked_exact_title_text','复用完全相同原题的参考译文，仅用于显示，不建立作品同一性。'
                if not HAN.search(zh):
                    status,reason = 'retained','已有复核资产将该原题按专名保留，本轮沿用原文显示决定。'
            elif (zh:=terminology_grammar(original,terms,work.get('composer_en',''))):
                status,basis,reason = 'reference','closed_musical_title_grammar_v2','完整原题通过闭合音乐术语、调性和编号语法；非通行中文专名声明。'
            elif original in manual.get('titles',{}):
                row=manual['titles'][original];zh=row['zh'];status,basis,reason='reference',row.get('basis','checked_title_reference'),''
            elif cache.get(original) and HAN.search(cache[original]):
                zh,status,basis,reason=cache[original],'machine','google_reference_draft','自动参考译文，尚待逐条语义复核。'
            else:
                zh,status,basis,reason=original,'retained','source_title_preservation','本轮无法确认该原题的可靠中文译法，保留完整原题及编号供检索。'
            candidate = entry(original,wrap_display_title(zh),status,basis,reason)
            titles[identity], _ = review_title_entry(identity, original, work.get('composer_en', ''), candidate, terms, quality_overrides)
        rows = [titles[work['id']] for work in catalog['works']]
        report[source] = {'title':dict(Counter(row['status'] for row in rows)), 'composer':dict(Counter(musicians[source][name]['status'] for name in composer_names)),
                          'category':dict(Counter(row['status'] for row in categories[source].values()))}
    titles = {key:row for key,row in titles.items() if key in current}
    if not set(quality_overrides).issubset(current):
        raise ValueError('title quality review has stale source record IDs')
    for name,entries in [('source_titles_zh.json',titles),('musicians_zh.json',musicians),('categories_zh.json',categories)]:
        atomic_json(outdir/name,{'schema_version':1,'entries':entries})
    atomic_json(root/'sources/translations/review_report.json',report)
    print(json.dumps(report,ensure_ascii=False),flush=True)
    return report


def refresh_title_quality(root: Path):
    """Recheck all additional-source titles without touching other field assets."""
    outdir = root/'metadata/translations'
    titles = read_asset(root,'source_titles_zh.json')
    terms = dict(TERMS)
    manual_path = outdir/'expansion_terminology_zh.json'
    if manual_path.exists():
        for row in json.loads(manual_path.read_text())['entries']:
            if row['context'] in {'title_term','key_signature'}:
                terms[row['original'].casefold()] = row['zh']
    quality_path = outdir/'source_title_quality_review_zh.json'
    overrides = json.loads(quality_path.read_text())['entries'] if quality_path.exists() else {}
    rows = []
    for source in load_registry(root):
        if source['id'] in {'imslp','classclef'}:
            continue
        rows.extend(json.loads((root/source['catalog']).read_text())['works'])
    ids = {row['id'] for row in rows}
    if set(titles) != ids:
        raise ValueError('source title asset IDs do not exactly match registered source records')
    if not set(overrides).issubset(ids):
        raise ValueError('title quality review has stale source record IDs')
    reviewed = {}
    decisions = []
    for work in rows:
        identity = work['id']
        row, changes = review_title_entry(identity, work['title_en'], work.get('composer_en',''), titles[identity], terms, overrides)
        reviewed[identity] = row
        if changes:
            decisions.append({'id':identity, 'source_id':identity.split(':',1)[0], 'original':work['title_en'],
                              'before':titles[identity], 'after':row, 'corrections':changes})
    report = {'checked_records':len(reviewed), 'changed_records':len(decisions),
              'before_status':dict(Counter(row['status'] for row in titles.values())),
              'after_status':dict(Counter(row['status'] for row in reviewed.values())),
              'corrections':dict(Counter(kind for decision in decisions for kind in decision['corrections'])),
              'sources':{source: {'checked':sum(1 for key in reviewed if key.startswith(source+':')),
                                  'changed':sum(1 for decision in decisions if decision['source_id']==source),
                                  'status':dict(Counter(row['status'] for key,row in reviewed.items() if key.startswith(source+':')))}
                         for source in sorted({key.split(':',1)[0] for key in reviewed})}}
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    private_dir = root/'sources/translations/title_quality'/timestamp
    # Save every changed draft and its exact source guard before replacing data.
    atomic_json(private_dir/'decisions.json', {'schema_version':1, 'entries':decisions})
    atomic_json(private_dir/'report.json', report)
    atomic_json(outdir/'source_titles_zh.json', {'schema_version':1,'entries':reviewed})
    atomic_json(root/'sources/translations/title_quality_latest.json', {'report':report, 'decision_receipt':str((private_dir/'decisions.json').relative_to(root))})
    print(json.dumps(report,ensure_ascii=False),flush=True)
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--machine-drafts',action='store_true')
    parser.add_argument('--workers',type=int,default=2)
    parser.add_argument('--quality-refresh',action='store_true',help='Recheck only existing additional-source title assets; preserve all other field assets.')
    args=parser.parse_args()
    if args.quality_refresh:
        refresh_title_quality(args.root.resolve())
    else:
        build(args.root.resolve(),machine=args.machine_drafts,workers=args.workers)
