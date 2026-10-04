"""Exact semantic rereview of archive.json[1800:2400], against full corpus."""
from pathlib import Path
import collections,hashlib,json,re
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
WORK=ROOT/'work/title-review/2026-10-03/cglib-retained-pass'
ROWS=json.loads((WORK/'archive-owner-tail-corpus.json').read_text())
EXACT={}
for line in (HERE/'cglib_archive_owner_tail_exact.tsv').read_text().splitlines():
 if line and not line.startswith('#'):
  ident,zh=line.split('\t',1);EXACT['cglib:'+ident]=zh
RETAIN={'cglib:1987':'Macareno 可为地方称谓或人物绰号，题名未限定具体所指。','cglib:2006':'Macarenan 为不确定的题名拼写，不能静默替换为 Macarena。','cglib:2146':'Aloe 的植物词义与此音乐题名的关系未明，保留原文字形。'}
NOTES={'cglib:21311':'原题 Minstrel boy 连列两次，中文主标题合并重复词，完整原转录保留。','cglib:21366':'原题曲选副题及作品4重复列出，中文主标题去重，完整原转录保留。','cglib:21296':'Thos. Moore 作词、Henry Bishop 作曲的原题责任句保留全文，不覆写来源作曲者字段。'}
REFS={'cglib:21340':['https://dictionary.cambridge.org/zhs/词典/英语-汉语-简体/mockingbird','https://blogs.loc.gov/folklife/2015/04/language-of-birds/'],'cglib:21246':['https://www.naxos.com/CatalogueDetail/?id=8.660248-49','https://www.ricordi.com/en-US/Critical-Editions/Boito-Arrigo-Critical-Editions/Boito-Mefistofele.aspx']}

def marked(text):
 if text.startswith('《') and text.endswith('》'):text=text[1:-1]
 return '《'+text.replace('《','〈').replace('》','〉')+'》'

def main():
 canonical=json.loads((ROOT/'work/title-review/2026-10-03/cglib.json').read_text());by={r['id']:r for r in canonical}
 frozen=json.loads((WORK/'archive.json').read_text())['entries'][1800:2400]
 assert len(ROWS)==600 and {r['id'] for r in ROWS}=={e['id'] for e in frozen}
 assert set(EXACT).isdisjoint(RETAIN) and set(EXACT)|set(RETAIN)=={r['id'] for r in ROWS}
 out=[];numeric=[]
 for r in ROWS:
  assert r==by[r['id']]
  isref=r['id'] in EXACT
  refs=REFS.get(r['id'],[]).copy()
  if 'Home sweet home' in r['original']:refs.append('https://tile.loc.gov/storage-services/public/music/mussm2-sm1841-021670/mussm2-sm1841-021670.pdf')
  refs.append(r['source_url'])
  z=marked(EXACT[r['id']]) if isref else marked(r['original'])
  assert z.count('《')==z.count('》')==1 and z.count('〈')==z.count('〉') and z.count('（')==z.count('）')
  if isref:assert re.search('[\u4e00-\u9fff]',z)
  e={'id':r['id'],'original':r['original'],'original_composer':r['composer'],'display_original':r['display_original'],'display_zh':z if isref else marked(r['display_original']),'zh':z,'status':'reference' if isref else 'retained','basis':'cglib_archive_owner_tail_full_semantic_pass_2026_10_04','reason':'核对完整题名的音乐结构、题意与原列版本信息；专名保留原拼写。' if isref else RETAIN[r['id']],'source_refs':refs,'reviewer':'codex_cglib_partition','review_method':'exact_complete_semantic' if isref else 'specific_name_or_transcription_retention'}
  if r['id'] in NOTES:e['reason']=NOTES[r['id']]
  out.append(e)
  src=set(re.findall(r'\d+',r['original']));dst=set(re.findall(r'\d+',z))
  if src!=dst:numeric.append({'id':r['id'],'original':r['original'],'zh':z,'source_digits':sorted(src),'translated_digits':sorted(dst)})
 path=HERE/'cglib_retained_archive_owner_tail_supplement.json';path.write_text(json.dumps({'schema_version':1,'entries':out},ensure_ascii=False,indent=2)+'\n')
 s={'records':len(out),'statuses':dict(collections.Counter(e['status'] for e in out)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'guards':600,'numeric_candidates':len(numeric)}
 (WORK/'archive-owner-tail-validation.json').write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n');(WORK/'archive-owner-tail-numeric.json').write_text(json.dumps(numeric,ensure_ascii=False,indent=2)+'\n')
 (WORK/'archive-owner-tail-ledger.json').write_text(json.dumps([dict(e,input_source_url=by[e['id']]['source_url'],input_status=by[e['id']]['status']) for e in out],ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(s,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
