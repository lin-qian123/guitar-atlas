"""Guard exclusive CGLIB follow-up and concrete semantic review regressions."""
import hashlib,json,re
from collections import Counter
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
PRIVATE=ROOT/'work/title-review/2026-10-03/archive-review/cglib-retained'
inputpath=ROOT/'work/title-review/2026-10-03/cglib-retained-pass/archive.json'
inputs=json.loads(inputpath.read_text())['entries'][:1800]
corpus=json.loads((ROOT/'work/title-review/2026-10-03/corpus.json').read_text());corpus=corpus['entries'] if isinstance(corpus,dict) else corpus
originals={r['id']:r for r in corpus};scope={r['id'] for r in inputs}
p=HERE/'cglib_retained_archive_supplement.json';data=json.loads(p.read_text())
assert data['schema_version']==1
entries=data['entries'];by={e['id']:e for e in entries}
assert len(entries)==len(by)==1800 and set(by)==scope
assert inputs[0]['id']=='cglib:1070' and inputs[-1]['id']=='cglib:19689'
for e in entries:
 r=originals[e['id']]
 assert (e['original'],e['original_composer'],e['display_original'])==(r['original'],r['composer'],r['display_original']),e['id']
 assert e['status'] in {'reference','reviewed','retained'}
 assert e['reason'].strip() and e['basis'].strip()
 assert e['source_refs'] and all(u.startswith('https://') for u in e['source_refs'])
 for k in ('zh','display_zh'):
  assert e[k].startswith('《') and e[k].endswith('》'),(e['id'],e[k])
  if e['status']!='retained':
   assert re.search(r'[\u3400-\u9fff]',e[k]),e['id']
   assert '[' not in e[k] and ']' not in e[k],(e['id'],e[k])
   for left,right in [('《','》'),('〈','〉'),('（','）'),('(',')')]:
    depth=0
    for c in e[k]:
     if c==left:depth+=1
     elif c==right:depth-=1
     assert depth>=0,(e['id'],e[k])
    assert depth==0,(e['id'],e[k])
   assert '（（' not in e[k] and '））' not in e[k],(e['id'],e[k])
checks={
 'cglib:1160':['曼陀林','吉他','第二曼陀林可选','二重奏'],
 'cglib:1162':['钢琴','第二曼陀林可选','快步进行曲'],
 'cglib:1177':['索尔主题','1系列','3号'],
 'cglib:12803':['六首','弱音器','两把吉他','31'],
 'cglib:13081':['第二吉他','Juan Alais','Maria'],
 'cglib:13180':['引子','诺尔玛','曼多拉'],
 'cglib:13462':['加托舞曲'],
 'cglib:13476':['第二吉他','Tarrega','合奏'],
 'cglib:15526':['作者','Mistress','二重奏'],
 'cglib:1604':['guitarra doble','octavilla','bandurria','六弦组','指法谱'],
 'cglib:1609':['吉他幻想曲','源编号2'],
 'cglib:1125':['告别：','忧郁的圆舞曲','七弦'],
 'cglib:17288':['D标记','西班牙曲调变奏','英国吉格','法国小舞曲'],
 'cglib:17578':['第1册','13号','二重奏'],
 'cglib:17801':['第8号','库朗特','441'],
 'cglib:1821':['三首','95'],
 'cglib:1893':['疑病症','波尔卡'],
 'cglib:19362':['第9曲','Ah Tuo fallo','1801','1835'],
 'cglib:19479':['第二吉他','初学者','65'],
 'cglib:19494':['44','六首','第六版','241'],
 'cglib:19538':['第1—3号','里拉琴或吉他','24'],
 'cglib:19622':['二十','1—12','Diabelli','Eulenstein'],
 'cglib:19623':['二十','13—24','Diabelli','Eulenstein'],
 'cglib:19624':['Winter','Caraffa','Metzger','省去歌词','Diabelli'],
 'cglib:19634':['第12曲','Io l udia','Anna Bolena','Torquato Tasso'],
 'cglib:19640':['第6曲','Per veder','Anna Bolena'],
 'cglib:19687':['Bishop','我们从不提及她','变奏'],
}
for i,t in checks.items():assert all(x in by[i]['display_zh'] for x in t),(i,by[i]['display_zh'],t)
assert '作曲者' not in by['cglib:15526']['display_zh']
assert '猫' not in by['cglib:13462']['display_zh']
assert '交响曲' not in by['cglib:1702']['display_zh']
assert '第8乐章' not in by['cglib:17801']['display_zh']
assert 'D大调' not in by['cglib:17288']['display_zh']
assert '两首' not in by['cglib:1609']['display_zh']
assert all('操作' not in e['display_zh'] for e in entries if e['status']!='retained')
for i in ('cglib:15816','cglib:15848','cglib:19453','cglib:19484','cglib:19493','cglib:1839'):
 assert by[i]['status']=='retained',i
numeric=[]
for e in entries:
 if e['status']=='retained':continue
 a=Counter(re.findall(r'\d+',e['display_original']));b=Counter(re.findall(r'\d+',e['display_zh']))
 if a!=b:numeric.append({'id':e['id'],'original':e['display_original'],'zh':e['display_zh'],'original_digits':dict(a),'translated_digits':dict(b),'boundary':'中文数词、罗马编号、重复书目语句及源器乐数量需结合完整原题核对，不把字面数字差异等同漏译。'})
manual=[l.split('\t',2) for l in (HERE/'cglib_retained_archive_manual.tsv').read_text().splitlines() if l and not l.startswith('#')]
assert len(manual)==len({l[0] for l in manual})
assert all(l[0] in scope for l in manual)
report={'schema_version':1,'scope':'cglib-retained-pass/archive.json entries[0:1800]','input_count':1800,'first_id':inputs[0]['id'],'last_id':inputs[-1]['id'],'identity_title_composer_display_guards':1800,'missing':0,'duplicate':0,'statuses':dict(Counter(e['status'] for e in entries)),'machine':0,'untranslated':0,'exact_manual_rows':len(manual),'root_weiss_full_read_rows':49,'remaining_complete_semantic_phrases_or_grammar':1800-len(manual)-49,'semantic_regression_count':len(checks)+6,'numeric_clues':len(numeric),'final_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'input_sha256':hashlib.sha256(inputpath.read_bytes()).hexdigest(),'limitations':['全部冻结分区原题及候选已审读；参考译名不等于每个历史题名的权威中文惯用名。','没有声称逐条联网；在线研究用于特定词义与曲式边界，保留原始专名和未知缩略。','来源题录URL仅是原题出处；对照语义证据及研究过程另存私有台账。','不修改作曲者或源标题；没有合并作品、变更编制元数据、下载或导出。']}
(PRIVATE/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
(PRIVATE/'numeric-clues.json').write_text(json.dumps(numeric,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False))
