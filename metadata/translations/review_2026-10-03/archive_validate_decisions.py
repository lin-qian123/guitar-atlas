"""Verify archive review guards and record concrete semantic regressions."""
import json,hashlib,re
from collections import Counter
from pathlib import Path
from archive_semantics import ROOT,HERE,PRIVATE,load_rows
rows=load_rows();ids={r['id']:r for r in rows}
p=HERE/'archive_decisions.json'
assert p.exists(),'Final review decisions are not complete yet'
d=json.loads(p.read_text());assert d['schema_version']==1
entries=d['entries'];by={e['id']:e for e in entries}
assert len(by)==len(entries)==len(rows)==9307
assert by.keys()==ids.keys()
for e in entries:
 r=ids[e['id']]
 assert e['original']==r['original']
 assert e['original_composer']==r['composer']
 assert e['display_original']==r['display_original']
 assert e['status'] in {'reference','reviewed','retained'}
 if e['status']!='retained':
  assert re.search(r'[\u3400-\u9fff]',e['zh']) and re.search(r'[\u3400-\u9fff]',e['display_zh']),(e['id'],'no Han')
 assert e['reason'].strip() and e['basis'].strip()
 assert isinstance(e['source_refs'],list) and e['source_refs']
 assert all(u.startswith(('https://','http://')) for u in e['source_refs'])
 for k in ('zh','display_zh'):
  assert e[k].strip(),(e['id'],k)
  assert e[k].startswith('《') and e[k].endswith('》'),(e['id'],k,e[k])
# Exact facts and false friends with source identities unchanged.
checks={
 'dga:15204':['二重唱','Oh! Come lieto','La Sonnambula','吉他'],
 'dga:15209':['序曲','I Capuleti e Montecchi','吉他'],
 'dga:16282':['高音谱号','作品8'],
 'dga:2249':['序曲','Il Barbiere di Sivivlia'],
 'dga:28875':['续篇','71'],
 'dga:18346':['八','VI'],
 'boije:582':['练习','续篇'],
 'rism:990039230':['指法谱','1'],
 'dga:16450':['Semiramide','进行曲','Giuliani','吉他改编'],
 'dga:16663':['ERNANI','Elvira','卡瓦蒂纳','长笛','吉他'],
 'dga:22030':['纳布科','Verdi'],
 'dga:14527':['Segovia','吉他','29'],
 'dga:23081':['Eugenie','圆舞曲'],
 'dga:23082':['Forget Me Not','加沃特'],
 'dga:23054':['夜间沉思','圆舞曲'],
 'dga:10542':['十五','幻想曲'],
 'dga:12347':['Mary Gray','吉他改编'],
}
for i,tokens in checks.items():
 z=by[i]['display_zh'];assert all(t in z for t in tokens),(i,z,tokens)
for i in ('dga:2249','dga:14525','dga:15138','dga:15180','dga:15208'):
 assert not re.search(r'作品(?:Il|IL|L)(?![A-Za-z])',by[i]['display_zh']),(i,by[i]['display_zh'])
for i in ('dga:16293','dga:16295','dga:16328','dga:16332','dga:19772'):
 assert '交响曲' not in by[i]['display_zh'] and by[i]['status']=='retained'
for i in ('dga:15216','dga:15228'):
 assert '交响曲' not in by[i]['display_zh'] and 'Sinfonia' in by[i]['display_zh']
assert all('操作' not in e['display_zh'] for e in entries if e['status']!='retained')
# Numeric differences include safely extracted bibliographic statements and
# Chinese/Roman spelled quantities; they are clues, not automatic errors.
number_clues=[]
for e in entries:
 if e['status']=='retained':continue
 a=Counter(re.findall(r'\d+',e['display_original']));b=Counter(re.findall(r'\d+',e['display_zh']))
 if a!=b:number_clues.append({'id':e['id'],'display_original':e['display_original'],'display_zh':e['display_zh'],'original_numbers':dict(a),'display_numbers':dict(b),'basis':e['basis'],'reason':e['reason']})
report={'schema_version':1,'scope':{'dga':7481,'boije':1154,'rism':672},'total':len(entries),'identity_guards_verified':len(entries),'missing_ids':[],'duplicate_ids':0,'machine':0,'untranslated':0,'status_counts':dict(Counter(e['status'] for e in entries)),'final_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'source_counts':{s:dict(Counter(e['status'] for e in entries if ids[e['id']]['source_id']==s)) for s in ('dga','boije','rism')},'semantic_regression_ids':list(checks)+['dga:2249','dga:14525','dga:15138','dga:15180','dga:15208','dga:16293','dga:16295','dga:16328','dga:16332','dga:19772','dga:15216','dga:15228'],'numeric_display_difference_clues':len(number_clues),'numeric_clue_boundary':'Differences may be spelled-out Chinese quantities, Roman ordinal normalization, or bibliographic roles/contents deliberately preserved in full source transcription. They are not certification of every historical source number.','limitations':['No per-record claim of web searching or authoritative conventional Chinese names.','Complete closed musical syntax and exact manual reference readings are distinguished from conventional-name evidence.','All original titles, source attributions and clean original display guards remain unchanged; source relationships and scores are untouched.']}
PRIVATE.mkdir(parents=True,exist_ok=True)
(PRIVATE/'final-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
(PRIVATE/'numeric-display-clues.json').write_text(json.dumps(number_clues,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False))
