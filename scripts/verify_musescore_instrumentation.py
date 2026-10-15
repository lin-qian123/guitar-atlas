#!/usr/bin/env python
"""Independently verify preservation after the frozen 924-score file review.

Only the private receipt is written.  The precheck verifies immutable source,
score and translation bytes but is explicitly not a completed publication audit.
Final mode also rejects stale public/offline projections, compares every local
edition to the pre-review baseline, and checks all current links and sizes.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
from urllib.parse import quote, unquote, urlsplit

from catalog_payload import unpack_payload

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHANGED_WORK_FIELDS = frozenset({'details','instrumentation_status','topic_ids',
                                 'topic_evidence','topic_category_ids'})
INSTRUMENT_DETAILS = frozenset({'instrumentation','instrumentation_zh','source_instrumentation',
    'instrumentation_review','guitar_player_count','ensemble_player_count','file_title',
    'file_identity_note','file_part_labels','written_guitar_part_count','ensemble_size_note'})
REVIEW_STATUSES = frozenset({'file_verified','file_reviewed_uncertain'})
REVIEW_RELATIVE = 'sources/musescore/instrumentation-review.json'
DEDUP_RELATIVE = 'sources/objects/deduplication_report.json'


class AuditFailure(ValueError):
    """An explicit invariant failed; no guard is relaxed to finish the receipt."""


def require(condition, reason):
    if not condition:
        raise AuditFailure(reason)


def _unique_pairs(pairs):
    result={}
    for key,value in pairs:
        require(key not in result, f'duplicate JSON field: {key}')
        result[key]=value
    return result


def read_json(path):
    return json.loads(Path(path).read_bytes(),object_pairs_hook=_unique_pairs)


def sha256(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source,'sha256').hexdigest()


def fingerprint(path):
    value=Path(path).stat()
    return value.st_dev,value.st_ino,value.st_size,value.st_mtime_ns,value.st_ctime_ns


def _by_id(rows, context):
    require(isinstance(rows,list),f'{context}: expected records list')
    result={}
    for row in rows:
        require(isinstance(row,dict) and isinstance(row.get('id'),str),f'{context}: invalid identity')
        require(row['id'] not in result,f'{context}: duplicate identity {row["id"]}')
        result[row['id']]=row
    return result


def compare_public_works(before_rows, after_rows, reviews):
    before=_by_id(before_rows,'baseline public');after=_by_id(after_rows,'current public')
    require(set(before)==set(after),'public work identity scope changed')
    ms={key for key,row in before.items() if row.get('source_id')=='musescore'}
    require(set(reviews)==ms,'completed review coverage differs from exact MuseScore scope')
    changed=Counter()
    for key,old in before.items():
        new=after[key]
        if key not in ms:
            require(new==old,f'non-MuseScore public record changed: {key}')
            continue
        protected=lambda row:{k:v for k,v in row.items() if k not in CHANGED_WORK_FIELDS}
        require(protected(new)==protected(old),f'protected work fields changed: {key}')
        review=reviews[key]
        require(new.get('instrumentation_status') in REVIEW_STATUSES and
                new['instrumentation_status']==review.get('status'),f'completed review status missing or stale: {key}')
        details=new.get('details');old_details=old.get('details',{})
        require(isinstance(details,dict),f'new instrumentation details missing: {key}')
        non_instrument=lambda row:{k:v for k,v in row.items() if k not in INSTRUMENT_DETAILS}
        require(non_instrument(details)==non_instrument(old_details),f'non-instrumentation details changed: {key}')
        require(details.get('source_instrumentation')==old_details.get('instrumentation'),
                f'original instrumentation transcription lost: {key}')
        for field in ('instrumentation','instrumentation_zh'):
            require(details.get(field)==review.get(field),f'public review detail disagrees: {key}/{field}')
        explanation=review.get('summary','')
        if review.get('source_difference'):
            explanation+='；来源差异：'+review['source_difference']
        require(explanation and details.get('instrumentation_review')==explanation,
                f'public review explanation missing or stale: {key}')
        for field in ('guitar_player_count','ensemble_player_count','file_title','file_identity_note','file_part_labels'):
            value=review.get(field)
            expected=str(value) if value is not None and value!='' else None
            require(details.get(field)==expected,f'public reviewed count/title disagrees: {key}/{field}')
        old_evidence=old.get('topic_evidence',{})
        secondary={topic:basis for topic,basis in old_evidence.items()
                   if basis not in {'explicit_source_instrumentation','no_exact_instrumentation_evidence'}}
        expected={**secondary,review['topic_id']:'file_crosscheck'}
        require(new.get('topic_evidence')==expected and new.get('topic_ids')==sorted(expected),
                f'file-crosschecked topic or preserved secondary topics disagree: {key}')
        memberships={topic:old['topic_category_ids'][topic] for topic in secondary}
        memberships[review['topic_id']]=old['category_ids']
        require(new.get('topic_category_ids')==memberships,f'file-review topic membership changed: {key}')
        for field in CHANGED_WORK_FIELDS:
            if old.get(field)!=new.get(field):changed[field]+=1
    return {'records':len(before),'non_musescore_records':len(before)-len(ms),
            'musescore_records':len(ms),'changed_fields':dict(changed)}


def compare_offline_works(before_rows, after_rows, public_rows):
    before=_by_id(before_rows,'baseline offline');after=_by_id(after_rows,'current offline')
    public=_by_id(public_rows,'current public')
    require(set(before)==set(after)==set(public),'offline/public/baseline identities differ')
    local_members=0
    for key,old in before.items():
        row=after[key]
        require('local_editions' in row and row['local_editions']==old.get('local_editions'),
                f'baseline local editions changed: {key}')
        require({k:v for k,v in row.items() if k!='local_editions'}==public[key],
                f'offline/public shared work fields differ: {key}')
        local_members+=sum(len(edition['files']) for edition in row['local_editions'])
    return {'records':len(before),'local_file_members':local_members,
            'all_local_editions_exact':True,'all_public_shared_fields_exact':True}


def check_local_link(root, href, expected_size=None):
    require(isinstance(href,str), 'local href is not text')
    parts=urlsplit(href);relative=unquote(parts.path);pure=PurePosixPath(relative)
    require(relative and not(parts.scheme or parts.netloc or parts.query or parts.fragment),f'unsafe relative link: {href}')
    require(not(pure.is_absolute() or '..' in pure.parts or '\\' in relative or '\x00' in relative),f'unsafe local link: {href}')
    root=Path(root).resolve();path=root/relative
    require(path.resolve().is_relative_to(root) and path.is_file(),f'link missing or escapes root: {href}')
    size=path.stat().st_size
    require(size>0 and (expected_size is None or size==expected_size),f'linked byte-size differs from manifest: {href}')
    return {'href':href,'size':size}


def _review_entries(root, native, catalog_sha):
    payload=read_json(root/REVIEW_RELATIVE)
    require(payload.get('schema_version')==1 and payload.get('source_id')=='musescore' and
            payload.get('status')=='complete' and payload.get('catalog_sha256')==catalog_sha,
            'completed fresh native-catalog-bound instrumentation review required')
    entries=_by_id(payload.get('works'),'private instrumentation review')
    natives=_by_id(native['works'],'native source')
    require(set(entries)==set(natives) and len(entries)==924,'private review must cover all924 native identities exactly')
    result={}
    for key,entry in entries.items():
        work=natives[key]
        require(all(entry.get(k)==work.get(k) for k in ('title_en','composer_en','source_url')),
                f'exact native review guard changed: {key}')
        assets={a['format']:{'sha256':a['sha256'],'size':a['size']} for a in work['assets']}
        guards=entry.get('assets')
        require(isinstance(guards,dict) and set(guards)=={'PDF','MUSICXML','MIDI'},f'review format guards incomplete: {key}')
        require(all(isinstance(guards[k],dict) and all(guards[k].get(field)==value
                    for field,value in expected.items()) for k,expected in assets.items()),
                f'review guards differ from preserved assets: {key}')
        review=entry.get('review')
        require(isinstance(review,dict) and review.get('status') in REVIEW_STATUSES and review.get('summary'),
                f'incomplete individual review: {key}')
        result[key]=review
    return result


def _compare_public_structure(before,after):
    require(set(before)==set(after),'public top-level schema changed')
    for key in set(before)-{'works','topics','summary'}:
        require(after[key]==before[key],f'public source/category/relationship field changed: {key}')
    require(len(after['sources'])==17 and len(after['relationships'])==700,
            'source/relationship scope differs from17 sources and700 relationships')
    old=_by_id(before['topics'],'baseline topics');new=_by_id(after['topics'],'new topics')
    require(set(old)<=set(new) and set(new)-set(old)<={'other_instrumentation'},'unexpected common topic addition/removal')
    for key,row in old.items():
        without_counts=lambda value:{k:v for k,v in value.items() if k not in {'work_count','source_count'}}
        require(without_counts(new[key])==without_counts(row),f'common topic meaning changed: {key}')
    counts=Counter();sources=defaultdict(set)
    for work in after['works']:
        for topic in work['topic_ids']:
            counts[topic]+=1;sources[topic].add(work['source_id'])
    require(set(counts)<=set(new),'work topic absent from topic directory')
    for key,row in new.items():
        require(row['work_count']==counts[key] and row['source_count']==len(sources[key]),f'topic count closure failed: {key}')
    require({k:v for k,v in after['summary'].items() if k!='topic_count'}==
            {k:v for k,v in before['summary'].items() if k!='topic_count'},'public summary changed outside topics')
    require(after['summary']['topic_count']==len(new),'common topic summary count mismatch')


def _linked_sizes(root, all_hrefs):
    from export_public_site import configured_categories
    from catalog_sources import load_registry
    sizes={};states={}
    def add(href,value):
        if href not in all_hrefs:return
        require(type(value) is int and value>0,f'linked score lacks positive manifest size: {href}')
        require(href not in sizes or sizes[href]==value,f'linked size receipts conflict: {href}')
        sizes[href]=value
    for category in configured_categories(root):
        manifest=root/category['name']/'metadata/score_manifest.json';states[manifest]=fingerprint(manifest)
        for record in read_json(manifest):
            relative=record.get('relative_path')
            if isinstance(relative,str):
                add(quote(f"{category['name']}/{relative}",safe='/._-~()'),record.get('download_expected_size') or record.get('expected_size'))
    for source in load_registry(root):
        if source['adapter']!='normalized_catalog':continue
        path=root/source['catalog'];states[path]=fingerprint(path)
        for work in read_json(path)['works']:
            for asset in work.get('assets',[]):
                members=asset.get('members',[]) if asset.get('container')=='ZIP' else [asset]
                for member in members:
                    relative=member.get('local_path')
                    if isinstance(relative,str):add(quote(relative,safe='/._-~()'),member.get('size'))
    require(set(sizes)==all_hrefs,'some preserved local score links lack current size receipts')
    return sizes,states


def _node_adapter(root):
    source=r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),zlib=require('node:zlib');
const codec=require('./public_site/assets/catalog-codec.js'),search=require('./public_site/assets/search.js');
const page=fs.readFileSync('index.html','utf8'),envelope=JSON.parse(page.match(/<script type="application\/json" id="offline-data">([\s\S]*?)<\/script>/)[1]);
const wrapper=envelope.codec?codec.unpack(JSON.parse(zlib.gunzipSync(Buffer.from(envelope.payload,'base64')))):envelope;
class Element{constructor(tag,className='',text=''){this.tag=tag;this.className=className;this.text=text;this.children=[];this.attributes={};}append(...children){this.children.push(...children);}setAttribute(k,v){this.attributes[k]=v;}querySelector(){return null;}insertBefore(child){this.append(child);}}
const descend=node=>[node,...node.children.flatMap(descend)];
const context={window:{},TextEncoder,GuitarSearch:search,makeElement:(...args)=>new Element(...args)};
vm.runInNewContext(fs.readFileSync('scripts/assets/offline-catalog.js','utf8'),context);
const cats=new Map(wrapper.data.categories.map(r=>[r.id,r]));let records=0,controls=0,downloads=0,restricted=0;
for(const item of wrapper.data.works.filter(r=>r.source_id==='musescore')){
 assert.ok(['file_verified','file_reviewed_uncertain'].includes(item.instrumentation_status));
 const article=new Element('article');context.window.GuitarCatalogAdapter.decorateCard(article,{categories:item.category_ids.map(id=>cats.get(id)),item});
 const all=descend(article),links=all.filter(n=>n.className==='local-score-link');
 assert.deepEqual(links.map(n=>n.href).sort(),item.local_editions.flatMap(e=>e.files).map(f=>f.href).sort());
 assert.deepEqual(all.filter(n=>n.className==='local-format').map(n=>n.text),['PDF','MXL','MIDI']);
 for(const link of links){if(link.href.endsWith('.pdf')){assert.equal(link.target,'_blank');assert.equal(link.attributes.download,undefined);}else{const name=link.attributes.download;assert.ok(typeof name==='string'&&name.length);assert.ok(Array.from(name).length<=100);assert.ok(new TextEncoder().encode(name).length<=240);assert.ok(!/[<>:"/\\|?*\u0000-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/.test(name));assert.ok(name.endsWith(` - ${item.source_record_id}.${link.href.endsWith('.mxl')?'mxl':'mid'}`));downloads++;}}
 const filtered=new Element('article');context.window.GuitarCatalogAdapter.decorateCard(filtered,{categories:[],item});
 assert.equal(descend(filtered).filter(n=>n.className==='local-score-link').length,0);records++;controls+=links.length;restricted++;
}
console.log(JSON.stringify({records,controls,downloads,restricted,failures:0}));
'''
    result=subprocess.run(['node','-e',source],cwd=root,capture_output=True,text=True,timeout=120)
    require(result.returncode==0,'actual final offline adapter VM failed: '+result.stderr[:3000])
    values=json.loads(result.stdout)
    require(values=={'records':924,'controls':2772,'downloads':1848,'restricted':924,'failures':0},
            'actual offline adapter format/category controls differ from preserved scope')
    return {'method':'Actual final snapshot with production codec/search/adapter in Node VM; no browser/file-protocol UI claim',**values}


def verify(root,baseline_path,full_report_path,*,precheck=False,run_node=True):
    root=Path(root).resolve();baseline_path=Path(baseline_path);full_report_path=Path(full_report_path)
    with gzip.open(baseline_path,'rt') as source:
        before=json.load(source,object_pairs_hook=_unique_pairs)
    require(before.get('schema_version')==1,'instrumentation baseline schema must be1')
    guarded=[baseline_path,root/'sources/musescore/catalog.json']
    if not precheck:
        guarded.extend(root/name for name in ['index.html','public_site/data/catalog.json',
            'public_site/data/catalog.compact.json','public_site/data/search-aliases.json',
            'public_site/data/ranking.json',REVIEW_RELATIVE])
        guarded.append(full_report_path)
    initial={path:fingerprint(path) for path in guarded}
    source_path=root/'sources/musescore/catalog.json';native=read_json(source_path)
    require(sha256(source_path)==before['catalog_sha256'] and native==before['source_catalog'],
            'raw MuseScore source catalog bytes/native fields/assets changed')
    natives=_by_id(native['works'],'native source');require(len(natives)==924,'native924 identity scope changed')
    assets=before['assets'];require(len(assets)==2769,'baseline unique object scope differs from2769')
    paths={a['local_path'] for w in native['works'] for a in w['assets']}
    require(paths==set(assets),'native asset paths differ from complete frozen inventory')
    formats=Counter(a['format'] for w in native['works'] for a in w['assets'])
    require(formats=={'PDF':924,'MUSICXML':924,'MIDI':924},'native format association counts changed')
    asset_states={}
    def check_asset(relative):
        pure=PurePosixPath(relative);path=root/relative;guard=assets[relative]
        require(not(pure.is_absolute() or '..' in pure.parts or '\\' in relative) and
                path.resolve().is_relative_to(root) and path.is_file(),f'unsafe/missing preserved asset: {relative}')
        state=fingerprint(path)
        require(state[1]==guard['inode'] and state[2]==guard['size'] and sha256(path)==guard['sha256'],
                f'preserved asset SHA/size/inode changed: {relative}')
        require(fingerprint(path)==state,f'preserved asset changed during fresh read: {relative}')
        return relative,state
    with ThreadPoolExecutor(max_workers=4) as pool:asset_states.update(pool.map(check_asset,sorted(assets)))
    translations={path.relative_to(root).as_posix():sha256(path) for path in (root/'metadata/translations').rglob('*.json')}
    require(len(translations)==63 and translations==before['translations'],'translation source bytes changed')
    result={'schema_version':1,'status':'precheck_passed_not_final' if precheck else 'passed',
      'completed_final_verification':not precheck,'checked_at':datetime.now(timezone.utc).isoformat(),
      'scope':'existing frozen924 native records and all49373 unified/offline records',
      'baseline_sha256':sha256(baseline_path),'native_catalog_sha256':before['catalog_sha256'],
      'native_catalog_bytes_exact':True,'native_records':924,'format_associations':dict(formats),
      'fresh_score_sha_size_inode_checks':len(asset_states),'translation_assets':63,
      'translation_bytes_exact':True,
      'integrity_boundary':'Fresh SHA-256/size/inode preservation for2769 MuseScore objects; structural score parsing is separate production evidence, not rerun by this preservation verifier.'}
    if not precheck:
        reviews=_review_entries(root,native,before['catalog_sha256']);public=read_json(root/'public_site/data/catalog.json')
        _compare_public_structure(before['public'],public)
        result['public_preservation']=compare_public_works(before['public']['works'],public['works'],reviews)
        require(result['public_preservation']['non_musescore_records']==48449 and
                result['public_preservation']['musescore_records']==924 and len(public['works'])==49373,
                'public native/protected record scope differs from49373')
        compact=read_json(root/'public_site/data/catalog.compact.json')
        require(unpack_payload(compact)==public,'compact catalog differs from canonical JSON')
        require(read_json(root/'public_site/data/search-aliases.json')==before['offline']['aliases'] and
                read_json(root/'public_site/data/ranking.json')==before['offline']['ranking'],
                'existing search aliases or ranking changed')
        page=(root/'index.html').read_bytes()
        require(hashlib.sha256(page).hexdigest()!=before['index_sha256'],'offline entry is the old pre-review index')
        matches=re.findall(r'<script type="application/json" id="offline-data">(.*?)</script>',page.decode(),re.S)
        require(len(matches)==1,'offline embedded snapshot cardinality changed')
        wrapper=unpack_payload(json.loads(matches[0],object_pairs_hook=_unique_pairs));data=wrapper['data']
        require(wrapper['aliases']==before['offline']['aliases'] and wrapper['ranking']==before['offline']['ranking'],
                'offline aliases/ranking differ from original shared assets')
        result['offline_preservation']=compare_offline_works(before['offline']['data']['works'],data['works'],public['works'])
        require(data['categories']==before['offline']['data']['categories'],
                'preserved offline category links or category fields changed')
        require([{k:v for k,v in row.items() if k!='local_href'} for row in data['categories']]==public['categories'],
                'offline/public category definitions differ')
        require(all(data.get(k)==v for k,v in public.items() if k not in {'works','categories','integrity'}),
                'offline/public shared top-level fields differ')
        from render_offline_site import offline_input_fingerprint
        current_inputs=offline_input_fingerprint(root)
        require(data.get('offline_inputs')==current_inputs,'offline source/config/review fingerprint is stale')
        review_sha=sha256(root/REVIEW_RELATIVE)
        require(current_inputs['inputs'].get(REVIEW_RELATIVE)==review_sha,
                'offline input review SHA missing or stale')
        old_inputs=before['offline']['data']['offline_inputs']['inputs']
        require(set(current_inputs['inputs'])-set(old_inputs)<={REVIEW_RELATIVE},'unexpected offline input addition')
        require(set(old_inputs)<=set(current_inputs['inputs']),'old source/config input removed')
        for key,value in old_inputs.items():
            if key not in {REVIEW_RELATIVE,DEDUP_RELATIVE}:
                require(current_inputs['inputs'][key]==value,f'original source/config/manifest input changed: {key}')
        full=read_json(full_report_path);summary=data.get('offline_summary')
        require(summary==before['offline']['data']['offline_summary'],'existing PDF/format availability or unique-content counts changed')
        require({k:v for k,v in full.items() if k!='index'}==summary and 'unique_pdf_contents' in full and
                'mode' not in full and 'input_guard' not in full,'fresh full-render report does not match offline snapshot')
        require(full_report_path.stat().st_mtime_ns>=(root/'index.html').stat().st_mtime_ns,
                'full-render receipt predates the final offline entry')
        members=[file for work in data['works'] for edition in work['local_editions'] for file in edition['files']]
        hrefs={file['href'] for file in members};category_hrefs={c['local_href'] for c in data['categories'] if c.get('local_href')}
        require((len(members),len(hrefs),len(category_hrefs))==(45249,37852,350),'preserved offline link cardinalities changed')
        expected_sizes,size_states=_linked_sizes(root,hrefs)
        with ThreadPoolExecutor(max_workers=8) as pool:
            checked=list(pool.map(lambda href:check_local_link(root,href,expected_sizes.get(href)),sorted(hrefs|category_hrefs)))
        require(len(checked)==38202,'known local link scope differs from38202')
        require(all(fingerprint(path)==state for path,state in size_states.items()),'manifest changed during link-size proof')
        result.update(review_records=len(reviews),review_sha256=review_sha,
          review_status_counts=dict(Counter(value['status'] for value in reviews.values())),
          compact_matches_canonical=True,source_categories_relationships_exact=True,
          search_aliases_ranking_exact=True,offline_review_hash_current=True,
          relationships=len(public['relationships']),sources=len(public['sources']),
          offline_summary=summary,local_score_members=len(members),distinct_score_paths=len(hrefs),
          category_link_paths=len(category_hrefs),checked_safe_links=len(checked),
          linked_manifest_size_checks=len(expected_sizes),link_failures=0,
          index_sha256=hashlib.sha256(page).hexdigest(),index_bytes=len(page),
          full_render_report_sha256=sha256(full_report_path))
        if run_node:result['offline_adapter_vm']=_node_adapter(root)
        result['file_protocol_browser_ui']='Not performed; Node VM is an adapter/DOM contract check.'
    require(all(fingerprint(root/path)==state for path,state in asset_states.items()),'score object changed after fresh hashing')
    require(all(fingerprint(path)==state for path,state in initial.items()),'protected inputs changed during verification')
    require({path.relative_to(root).as_posix():sha256(path) for path in (root/'metadata/translations').rglob('*.json')}==translations,
            'translation bytes changed during verification')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=PROJECT_ROOT)
    parser.add_argument('--baseline',type=Path)
    parser.add_argument('--full-report',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--precheck',action='store_true')
    args=parser.parse_args();root=args.root.resolve();base=root/'sources/musescore/verification'
    baseline=args.baseline or base/'instrumentation-baseline.json.gz'
    full=args.full_report or base/'offline.json';output=args.output or base/'instrumentation-preservation.json'
    try:
        result=verify(root,baseline,full,precheck=args.precheck)
    except Exception as error:
        result={'schema_version':1,'status':'failed','completed_final_verification':False,
                'phase':'precheck' if args.precheck else 'final',
                'checked_at':datetime.now(timezone.utc).isoformat(),
                'error_type':type(error).__name__,'error':str(error)}
    output.parent.mkdir(parents=True,exist_ok=True);temporary=output.with_suffix(output.suffix+'.tmp')
    temporary.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');temporary.replace(output)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 1 if result['status']=='failed' else 0


if __name__=='__main__':
    raise SystemExit(main())
