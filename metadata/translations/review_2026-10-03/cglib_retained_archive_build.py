"""Exclusive retained CGLIB follow-up; complete clauses, exact source guards."""
import json,re,sys,hashlib
from pathlib import Path
from collections import Counter
import build_cglib_review as cg
from cglib_retained_archive_exact import READINGS, RETAINED
from cglib_retained_archive_books import book_read
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
PRIVATE=ROOT/'work/title-review/2026-10-03/archive-review/cglib-retained'
PRIVATE.mkdir(parents=True,exist_ok=True)
INPUT=ROOT/'work/title-review/2026-10-03/cglib-retained-pass/archive.json'
rows=json.loads(INPUT.read_text())['entries']
rows=rows[:1800]  # Frozen disjoint scope; owner 1800:2400, root 2400:2757.
corpus=json.loads((ROOT/'work/title-review/2026-10-03/corpus.json').read_text())
if isinstance(corpus,dict):corpus=corpus['entries']
by={r['id']:r for r in corpus}
manual_path=HERE/'cglib_retained_archive_manual.tsv'
MANUAL={}
if manual_path.exists():
 for line in manual_path.read_text().splitlines():
  if line and not line.startswith('#'):
   i,s,v=line.split('\t',2);MANUAL[i]=(s,v)
EXTERNAL={}
weiss_path=HERE/'cglib_retained_archive_weiss_supplement.json'
if weiss_path.exists():
 for e in json.loads(weiss_path.read_text())['entries']:
  r=by[e['id']]
  assert (e['original'],e['original_composer'],e['display_original'])==(r['original'],r['composer'],r['display_original'])
  assert e['id'] not in EXTERNAL and e['id'] not in MANUAL
  EXTERNAL[e['id']]=e
for k,v in json.loads((HERE/'root_semantic_phrases.json').read_text()).items():
 cg.PHRASES[cg.q.normphrase(k)]=v
for line in (HERE/'cglib_owner_phrases.tsv').read_text().splitlines():
 if line and not line.startswith('#'):
  a,b=line.split('\t',1);cg.PHRASES[cg.q.normphrase(a)]=b
archive=json.loads((HERE/'archive_decisions.json').read_text())['entries']
# Reuse literal complete language readings only, never source identity. Long
# archival responsibility/edition transcriptions need their own exact reading.
for e in archive:
 if e['status']=='reference' and len(e['display_original'])<=150 and not re.search(r'\b(?:by|par|von|da|composed|composés|dedicated|édition|edition|libro|livre)\b',e['display_original'],re.I):
  cg.PHRASES.setdefault(cg.q.normphrase(e['display_original']),e['display_zh'][1:-1])
own=HERE/'cglib_retained_archive_phrases.tsv'
if own.exists():
 for line in own.read_text().splitlines():
  if line and not line.startswith('#'):
   a,b=line.split('\t',1);cg.PHRASES[cg.q.normphrase(a)]=b
frozen_path=HERE/'cglib_retained_archive_frozen_lexicon.json'
if frozen_path.exists():
 frozen=json.loads(frozen_path.read_text());cg.PHRASES=dict(frozen['phrases']);cg.TERMS=dict(frozen['terms'])
else:
 frozen_path.write_text(json.dumps({'schema_version':1,'boundary':'Literal complete language readings; not cross-source work identity or authoritative conventional naming.','phrases':cg.PHRASES,'terms':cg.TERMS},ensure_ascii=False,indent=2)+'\n')
cg.PHRASE_PATTERN=re.compile(r'(?<!\w)(?:'+'|'.join(re.escape(k) for k in sorted(cg.PHRASES,key=len,reverse=True))+r')(?!\w)',re.I)
def translate(r):
 if r['id'] in MANUAL:
  status,value=MANUAL[r['id']]
  if status=='reference':return cg.wrap(value),status,'完整原题语义审读；保留引用名、编号及明确音乐结构。'
  return cg.wrap(r['display_original']),status,value
 if r['id'] in READINGS:
  return cg.wrap(READINGS[r['id']]),'reference','完整原题核对；保留音乐主标题、声部及编改责任。'
 if r['id'] in RETAINED:
  return cg.wrap(r['display_original']),'retained',RETAINED[r['id']]
 body=r['display_original'];suffix=[]
 # Explicit version and arranger clauses carry names without guessing identity.
 def version(m):
  suffix.append(m[1].strip()+'版');return ''
 body=re.sub(r'\(version\s+([^()]+)\)',version,body,flags=re.I)
 def arranger(m):
  suffix.append(m[1].strip()+'改编');return ''
 body=re.sub(r'\s+arr\.?\s+([A-Za-zÀ-ž][A-Za-zÀ-ž .\-]*)$',arranger,body,flags=re.I)
 def role(m):
  suffix.append(('改编：' if m[1].casefold().startswith('arr') else '原题作曲署名：')+m[2].strip(' .'))
  return ''
 body=re.sub(r'\s+(Arranger|Composer)\s+([A-Za-zÀ-ž][A-Za-zÀ-ž .()\-]*)$',role,body)
 body=re.sub(r'\s+arr\.?\s+af\s+([A-Za-zÀ-ž][A-Za-zÀ-ž .\-]*)$',arranger,body,flags=re.I)
 notes=[]
 def source_name(m):notes.append('原题署名：'+m[1]);return ''
 body=re.sub(r'^\(([^()]+)\)\s*',source_name,body)
 body=body.strip()
 book=book_read(body)
 if book:return cg.wrap(book),'reference','完整作品集句法已核对；保留引用题名、编制及册次曲号。'
 series=re.match(r'^([12])a\s+Serie\s+Nr\.?\s*(\d+)\s+(.+)$',body,re.I)
 if series:
  notes.append('第'+series[1]+'系列第'+series[2]+'号');body=series[3]
 # Exact full source name may be preserved by an explicitly printed author.
 value,_=cg.full_music(body)
 if not value:
  out=cg.opaque_music(body)
  if out:value=out[0]
 if not value:
  # Fully delimited source title plus a separate, completely consumed music
  # clause: keep the named label intact while translating the explicit frame.
  opus=[]
  clean=cg.q.OPUS.sub(lambda m:opus.append('作品'+m[1]) or '',body).strip(' .')
  genres=r'Zamacueca|Zamba|Gato|Ranchera|Rancherita|Pericon|Vidala|Vidalita|Yaravi|Carnavalito|Candombe|Chacarera|Maxixe|Estilo|Huella|Gavotta|Valzer|Melodia|Minuetto|Marcia|Fox.?Trot|Black.Bottom|Pagina d album|Preludio|Cancion|Canción|Legend|Leyenda|Cueca'
  match=re.fullmatch(r'(.{1,80}?)\s*\((('+genres+r')(?:[^()]*))\)(.*)',clean,re.I)
  if match:
   label=match[1].strip();frame=match[2]+' '+match[4]
   framezh,_=cg.full_music(frame)
   if framezh and not re.search(r'\b(?:op|suite|sonata|sonate|bwv|variations|rondo|study|studies|by|arr|and|et|sur|sobre|pour|for|per)\b',label,re.I):
    labelzh=cg.PHRASES.get(cg.q.normphrase(label),label)
    value=labelzh+'——'+framezh+('，'+'，'.join(opus) if opus else '')
  if not value:
   match=re.fullmatch(r'(.{1,70}?)\s+(\(?7 string guitar\)?|\(?for [^()]+\)?|\(?pour [^()]+\)?|\(?per [^()]+\)?|\(?para [^()]+\)?)',clean,re.I)
   if match:
    label=match[1].strip();frame=match[2].strip('() ')
    framezh,_=cg.full_music(frame)
    if framezh and not re.search(r'\b(?:op|suite|sonata|sonate|bwv|variations|rondo|by|arr|and|et|sur|sobre)\b',label,re.I):
     labelzh=cg.PHRASES.get(cg.q.normphrase(label),label)
     value=labelzh+'（'+framezh+'）'+('，'+'，'.join(opus) if opus else '')
 if value:
  return cg.wrap(value+('（'+'；'.join(suffix+notes)+'）' if suffix or notes else '')),'reference','核对完整题义与音乐结构；未知引用名保留原拼写。'
 return None

out=[];remaining=[]
for old in rows:
 r=by[old['id']]
 assert old['original']==r['original'] and old['original_composer']==r['composer']
 if r['id'] in EXTERNAL:
  item=dict(EXTERNAL[r['id']])
  if not item.get('source_refs'):item['source_refs']=[r['source_url']] if r.get('source_url') else ['https://www.cglib.org/']
  out.append(item);continue
 result=translate(r)
 if result:
  z,status,reason=result
  out.append(dict(id=r['id'],original=r['original'],original_composer=r['composer'],display_original=r['display_original'],zh=z,display_zh=z,status=status,basis='cglib_retained_archive_complete_semantic_reading_2026_10_04',reason=reason,source_refs=[r['source_url']] if r.get('source_url') else ['https://www.cglib.org/']))
 else:remaining.append(r)
EXTRA_REFS={
 'cglib:1893':['https://dle.rae.es/hipocondr%C3%ADa'],
 'cglib:12644':['https://dle.rae.es/porte%C3%B1o'],
 'cglib:13462':['https://dle.rae.es/gato'],
 'cglib:12584':['https://denshou.kengeki.or.jp/en/traditional/itsuki-no-komoriuta-itsuki-lullaby/','https://www.vill.itsuki.lg.jp/kankou/kiji0032052/index.html'],
 'cglib:12585':['https://denshou.kengeki.or.jp/en/traditional/itsuki-no-komoriuta-itsuki-lullaby/','https://www.vill.itsuki.lg.jp/kankou/kiji0032052/index.html'],
}
for e in out:
 e['source_refs']+=EXTRA_REFS.get(e['id'],[])
output=(HERE/'cglib_retained_archive_supplement.json') if not remaining else (PRIVATE/'cglib_retained_archive_partial.json')
output.write_text(json.dumps({'schema_version':1,'entries':out},ensure_ascii=False,indent=2)+'\n')
(PRIVATE/'unresolved.json').write_text(json.dumps(remaining,ensure_ascii=False,indent=2)+'\n')
(PRIVATE/'candidate-read.tsv').write_text('\n'.join('\t'.join([e['id'],e['original'],e['display_zh']]) for e in out))
(PRIVATE/'remaining-read.tsv').write_text('\n'.join('\t'.join([e['id'],e['composer'],e['display_original']]) for e in remaining))
print(json.dumps({'input':len(rows),'decided':len(out),'remaining':len(remaining),'statuses':dict(Counter(e['status'] for e in out))},ensure_ascii=False))
