"""Combine six mutually exclusive rereview partitions and exact late repairs.

The first-pass private baseline is immutable. Do not rerun build_cglib_review.py
on the canonical review asset: that would overwrite this complete second pass.
"""
from pathlib import Path
import collections,hashlib,json,re,shutil
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
WORK=ROOT/'work/title-review/2026-10-03/cglib-retained-pass'
BASELINE=WORK/'initial-decisions-frozen.json'
ASSET=HERE/'cglib_decisions.json'
CORPUS=ROOT/'work/title-review/2026-10-03/corpus.json'
PARTITIONS=[
 ('owner2757','cglib_owner_retained_supplement.json','owner.json',0,2757),
 ('legacy2200','cglib_retained_legacy_supplement.json','legacy.json',0,2200),
 ('root557','cglib_retained_root_supplement.json','legacy.json',2200,2757),
 ('archive1800','cglib_retained_archive_supplement.json','archive.json',0,1800),
 ('archive_owner600','cglib_retained_archive_owner_tail_supplement.json','archive.json',1800,2400),
 ('archive_legacy357','cglib_retained_archive_root_tail_supplement.json','archive.json',2400,2757),
]
OVERLAYS=['cglib_initial_reference_repairs.json','cglib_retained_owner_late_semantic_supplement.json']

def read(path):return json.loads(path.read_text())
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def current_cglib_corpus():
 rows=[r for r in read(CORPUS) if r['source_id']=='cglib']
 corpus={r['id']:r for r in rows}
 assert len(rows)==len(corpus)==16544,('current CGLIB corpus identities',len(rows),len(corpus))
 return corpus
def guard(e,corpus):
 r=corpus[e['id']]
 assert e['original']==r['original'],('original',e['id'])
 assert e['original_composer']==r['composer'],('composer',e['id'])
 # A translated display title requires its own exact source-title guard, even
 # when the submitted decision omitted display_original altogether.
 if 'display_zh' in e:
  assert e.get('display_original')==r['display_original'],('display',e['id'])
  assert isinstance(e['display_zh'],str) and e['display_zh'].strip(),('display text',e['id'])
 if 'display_original' in e:assert e['display_original']==r['display_original'],('display',e['id'])
 assert e['status'] in {'reference','reviewed','retained'} and e['reason'].strip(),('status',e['id'])
 if e['status'] in {'reference','reviewed'}:
  z=e.get('display_zh') or e['zh'];assert re.search('[\u4e00-\u9fff]',z),('Han',e['id'])
  assert z.count('《')==z.count('》')==1 and z.count('〈')==z.count('〉'),('marks',e['id'])
 if e['status']=='reviewed':assert any(x.startswith('https://') for x in e.get('source_refs',[])),('reviewed proof',e['id'])

def main():
 corpus=current_cglib_corpus()
 if not BASELINE.exists():
  old=read(ASSET);counts=collections.Counter(e['status'] for e in old['entries'])
  assert counts=={'reference':8271,'reviewed':2,'retained':8271},counts
  shutil.copyfile(ASSET,BASELINE)
 base=read(BASELINE);by={e['id']:e for e in base['entries']};assert len(base['entries'])==len(by)==len(corpus)==16544
 original_retained={e['id'] for e in base['entries'] if e['status']=='retained'}
 consumed=set();partition_receipts=[]
 for label,filename,inputfile,start,end in PARTITIONS:
  path=HERE/filename;entries=read(path)['entries'];expected={e['id'] for e in read(WORK/inputfile)['entries'][start:end]}
  got={e['id'] for e in entries};assert len(entries)==len(got)==end-start and got==expected,(label,len(entries),len(expected))
  assert not consumed&got,('overlap',label,consumed&got)
  assert got<=original_retained,('not original retained',label)
  for e in entries:guard(e,corpus);by[e['id']]=e
  consumed|=got;partition_receipts.append({'partition':label,'file':filename,'records':len(entries),'statuses':dict(collections.Counter(e['status'] for e in entries)),'sha256':digest(path)})
 assert consumed==original_retained and len(consumed)==8271,('missing',original_retained-consumed)
 overlay_receipts=[]
 for filename in OVERLAYS:
  path=HERE/filename;entries=read(path)['entries'];assert len(entries)==len({e['id'] for e in entries})
  for e in entries:guard(e,corpus);by[e['id']]=e
  overlay_receipts.append({'file':filename,'records':len(entries),'sha256':digest(path)})
 entries=[by[e['id']] for e in base['entries']]
 for e in entries:guard(e,corpus)
 # All identity and source guards remain exact; conventional-name evidence is
 # preserved byte-for-byte from the first pass, not upgraded from a draft.
 assert [e for e in entries if e['status']=='reviewed']==[e for e in base['entries'] if e['status']=='reviewed']
 tmp=ASSET.with_suffix('.tmp');tmp.write_text(json.dumps({'schema_version':1,'entries':entries},ensure_ascii=False,indent=2)+'\n');tmp.replace(ASSET)
 s={'records':len(entries),'statuses':dict(collections.Counter(e['status'] for e in entries)),'validation_corpus':str(CORPUS.relative_to(ROOT)),'validation_corpus_sha256':digest(CORPUS),'source_original_and_composer_guards':16544,'display_titles_requiring_original_guards':sum('display_zh' in e for e in entries),'rereview_mutually_exclusive_coverage':8271,'partitions':partition_receipts,'exact_overlays':overlay_receipts,'first_pass_sha256':digest(BASELINE),'final_sha256':digest(ASSET),'guard_errors':0}
 (WORK/'final-cglib-validation.json').write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n');(WORK/'final-cglib-ledger.json').write_text(json.dumps(entries,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(s,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
