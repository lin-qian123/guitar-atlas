"""Compile exclusive archive review decisions; no production asset writes."""
import json,sys,re,hashlib
from collections import Counter
from pathlib import Path
from archive_semantics import ROOT,HERE,PRIVATE,norm,marked,SOURCE_REFS,load_rows,tq
from archive_structure_rules import translate_row,primary_candidates
from archive_id_readings import READINGS as IREAD,RETAINED_IDS
from archive_dga_manual import READINGS as DREAD,RETAINED as DRETAIN
from archive_exact_supplement import RETAINED as TITLE_RETAIN
from archive_citation_rules import citation_decision
from archive_named_structures import named_structure
from archive_final_readings import READINGS as FINAL_READ, RETAINED as FINAL_RETAIN, REFS as FINAL_REFS

def refs(r):
 out=[r['source_url']] if r.get('source_url') else []
 t=norm(r['original']).casefold()
 if r['source_id']=='rism':out.append(SOURCE_REFS['rism_rules'])
 if any(w in t for w in ('intavol','tablature')):out.append(SOURCE_REFS['intavolatura'])
 if any(w in t for w in ('folies','folia','folía')):out.append(SOURCE_REFS['folia'])
 if any(w in t for w in ('fantas','fantais')):out.append(SOURCE_REFS['fantaisie'])
 if any(w in t for w in ('potpour','pot-pour','pot pour')):out.append(SOURCE_REFS['potpourri'])
 if 'barden' in t:out.append(SOURCE_REFS['mertz'])
 if 'rossinian' in t and 'giuliani' in r['composer'].casefold():out.append('https://www.naxos.com/CatalogueDetail/?id=8.574272')
 if 'rigoletto' in t and 'verdi' in t:out.append('https://www.chncpa.org/subsite/chn2016/index.html')
 if ('vespri siciliani' in t or 'vêpes siciliennes' in t) and 'verdi' in t:out.append('https://www.lcsd.gov.hk/CE/CulturalService/Programme/pdf/program_note2_1836_1.pdf')
 if 'chitarra' in t and ('solea' in t or 'siguir' in t or 'buler' in t or 'flamenc' in t):out.append('https://ich.unesco.org/en/RL/flamenco-00363')
 if 'sinfonia' in t:out.append('https://www.treccani.it/enciclopedia/sinfonia_%28Enciclopedia-dei-ragazzi%29/')
 if 'chamuyo' in t:out.append('https://dle.rae.es/chamuyo')
 if 'jarabe' in t:out.append('https://dle.rae.es/jarabe')
 if 'cimarr' in t:out.append('https://dle.rae.es/cimarr%C3%B3n')
 if 'miosotis' in t:out.append('https://dle.rae.es/miosotis')
 return list(dict.fromkeys(out))

rows=load_rows();ids={r['id']:r for r in rows}
manual=dict(IREAD,**DREAD)
manual_retain=dict(RETAINED_IDS,**DRETAIN)
# A full semantic phrase shared by exact display text and exact attribution is
# a language reading, not evidence that source record identities are the same.
phrase_read={(norm(ids[i]['display_original']),ids[i]['composer']):z for i,z in manual.items() if i in ids}
phrase_retain={(norm(ids[i]['display_original']),ids[i]['composer']):z for i,z in manual_retain.items() if i in ids}
external={}
cover_boundaries={
 'dga:23081':('Respectfully dedicated to Mrs. Edward Field','Eugenie — Waltz'),
 'dga:23082':('Respectfully dedicated to Mrs. Edward Field',"Flow'ret, Forget Me Not — Gavotte"),
 'dga:23054':('Dédiée À Miss C. Rust. Pensées Nocturnes Valse Sentimentale for the Spanish Guitar Composed','Pensées Nocturnes — Valse Sentimentale for the Spanish Guitar'),
 'dga:10542':('DÉDIÉ AUX ESTUDIANTINAS DE FRANCE Recueil progressif pour GUITARE composé de Quinze fantaisies faciles','Recueil progressif pour guitare, composé de Quinze fantaisies faciles'),
}
for fname in ('root_dga_supplement.json','root_dga_10000_supplement.json','cglib_dga_supplement.json','dga_10000_supplement.json','root_dga_13000_supplement.json','legacy_dga_tail_supplement.json','root_archive_grammar_supplement.json','cglib_archive_grammar_supplement.json'):
 p=HERE/fname
 if p.exists():
  doc=json.loads(p.read_text());entries=doc.get('entries',[]) if isinstance(doc,dict) else doc
  for e in entries:
   r=ids[e['id']]
   assert e['original']==r['original'],(fname,e['id'],'original')
   assert e['original_composer']==r['composer'],(fname,e['id'],'composer')
   if e['id'] in cover_boundaries and e.get('display_original')==cover_boundaries[e['id']][0]:
    # Root repaired the exact cover-title boundary in the corpus. The frozen
    # earlier supplement is read-only; the final exact reading below supersedes it.
    assert e['id'] in FINAL_READ
    assert r['display_original']==cover_boundaries[e['id']][1]
    e=dict(e,display_original=r['display_original'])
   assert e.get('display_original',r['display_original'])==r['display_original'],(fname,e['id'],'display')
   assert e['status'] in {'reference','reviewed','retained'}
   external[e['id']]=e
   # This supplements only the literal exact source title and attribution.
   external[(r['original'],r['composer'],r['display_original'])]=e

entries=[];unresolved=[];method=Counter()
for r in rows:
 key=(norm(r['display_original']),r['composer'])
 e=external.get(r['id']) or external.get((r['original'],r['composer'],r['display_original']))
 if r['id'] in FINAL_READ or r['id'] in FINAL_RETAIN:
  e=None
  z=FINAL_READ.get(r['id']) or r['display_original']
  status='reference' if r['id'] in FINAL_READ else 'retained'
  basis='exact_final_archive_semantic_reading_2026_10_04'
  reason=FINAL_RETAIN.get(r['id']) or '核对完整原题的音乐结构、配器、编号与引用关系；未确认的引用专名保留原拼写，书目余文保留于原始转录。'
  source_refs=refs(r)+FINAL_REFS.get(r['id'],[]);method['exact_final_semantic_reading']+=1
 elif e:
  z=e.get('display_zh') or e['zh'];status=e['status'];basis=e['basis'];reason=e['reason'];source_refs=e['source_refs'];method['external_semantic_reading']+=1
 elif r['id'] in manual or key in phrase_read:
  z=manual.get(r['id']) or phrase_read[key];status='reference';basis='exact_archive_title_semantic_reading_2026_10_03'
  reason='逐项核对完整原始题名与来源署名，给出实际主标题的参考译文；书目责任、出版余文、原标注及合订曲目完整保留在原始转录，不据同名跨源合并作品。引用的未知专名保留来源拼写，不声明其已有通行中文名。'
  source_refs=refs(r);method['exact_manual_reading']+=1
 elif r['id'] in manual_retain or key in phrase_retain or norm(r['display_original']) in TITLE_RETAIN:
  z=r['display_original'];status='retained';basis='exact_archive_ambiguity_review_2026_10_03'
  reason=manual_retain.get(r['id']) or phrase_retain.get(key) or TITLE_RETAIN[norm(r['display_original'])];source_refs=refs(r);method['exact_retained_reason']+=1
 else:
  result=named_structure(r) or translate_row(r) or citation_decision(r)
  if not result:
   unresolved.append(r);continue
  z,status,basis,reason=result;source_refs=refs(r)
  if status!='retained' and not tq.HAN.search(z):
   status='retained';z=r['display_original'];basis='exact_proper_name_heading_retained'
   reason='该主标题是原文人名/专名，未提供足以确认其通行中文对应的题名资料；保持来源完整拼写，不按普通词义翻译，也不根据相似姓名改归另一作曲家。'
  method[basis]+=1
 source_refs=list(dict.fromkeys(([r['source_url']] if r.get('source_url') else [])+source_refs))
 if e:
  zh=e['zh'];display_zh=e.get('display_zh') or (marked(r['display_original']) if status=='retained' else e['zh'])
 elif status=='retained':zh=marked(r['original']);display_zh=marked(r['display_original'])
 else:zh=marked(z);display_zh=marked(z)
 entries.append(dict(id=r['id'],original=r['original'],original_composer=r['composer'],display_original=r['display_original'],zh=zh,display_zh=display_zh,status=status,basis=basis,reason=reason,source_refs=source_refs))
assert len({e['id'] for e in entries})==len(entries)
for e in entries:
 r=ids[e['id']];assert e['original']==r['original'] and e['original_composer']==r['composer'] and e['display_original']==r['display_original']
 assert e['reason'] and e['basis'] and isinstance(e['source_refs'],list)
PRIVATE.mkdir(parents=True,exist_ok=True)
complete=not unresolved
out=(HERE/'archive_decisions.json') if complete else (PRIVATE/'archive_partial_decisions.json')
out.write_text(json.dumps({'schema_version':1,'entries':entries},ensure_ascii=False,indent=2)+'\n')
(PRIVATE/'unresolved-rows.json').write_text(json.dumps(unresolved,ensure_ascii=False,indent=2)+'\n')
summary={'total_input':len(rows),'decided':len(entries),'unresolved':len(unresolved),'complete':complete,'method_counts':dict(method),'status_counts':dict(Counter(e['status'] for e in entries)),'source_counts':{s:dict(Counter(e['status'] for e in entries if ids[e['id']]['source_id']==s)) for s in ('dga','boije','rism')},'input_hashes':{s:hashlib.sha256((ROOT/f'work/title-review/2026-10-03/{s}.json').read_bytes()).hexdigest() for s in ('dga','boije','rism')},'identity_guards_verified':len(entries),'limitations':['Full consumed music-language grammar and exact manual primary-title readings are reference translations, not authoritative Chinese name certification.','Research is grouped by music term, archive cataloging practice, and selected identifiable works; each record was not separately searched on the web.','No assets, original fields, composer identities, downloads, production exports, or source relationships were modified by this compiler.']}
(PRIVATE/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False))
