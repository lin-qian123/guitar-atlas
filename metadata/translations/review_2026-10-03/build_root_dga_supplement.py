"""Exact ID readings from all 927 independently read archival primary titles."""
import json,re
from pathlib import Path
from collections import Counter
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
rows=json.loads((ROOT/'work/title-review/2026-10-03/archive-review/root-dga-over20000.json').read_text())
readings={}
for line in (HERE/'root_dga_readings.tsv').read_text().splitlines():
 if not line.strip():continue
 ident,z=line.split('|',1)
 if 'dga:'+ident in readings:raise ValueError('duplicate '+ident)
 readings['dga:'+ident]=z
# Do not restore OCR tokens into conjectured original characters or resolve an
# ambiguous place/month name from a near-matching title.
readings.pop('dga:25839',None);readings.pop('dga:23799',None);readings.pop('dga:26450',None)
readings['dga:36137']='Hispanae Citharae Ars Viva：古指法谱吉他选集——〈Fantasia del quarto Toro〉／和声与疾奏幻想曲'
readings['dga:38532']='Hisparee Citharae Ars Viva：古指法谱吉他选集——〈Soneto del Primer Grade〉1／2'
readings['dga:36752']='波兰舞曲选（吉他，22首歌曲）'
retained={
 '23081':'来源记录仅保留献给Edward Field夫人的责任句，没有实际曲名；不从献辞虚构乐谱名称。',
 '23435':'Carulli是来源提供的人名式标题，未给具体作品；不将它猜补为教程或某一首乐曲。',
 '23436':'来源标题仅列Vivaldi、Telemann等人名，无曲目主体；保留原列名，不虚构统一曲名。',
 '23170':'Oberon是歌剧式专名；来源没有确定中文对应资料，保留原名。',
 '23174':'El Ole是以西班牙喝彩语构成的专名式曲名；普通感叹词直译会改变命名风格，采用原题。',
 '23177':'Ambolena Snow是历史歌曲的专名式标题，不能把Snow单独当成降雪题材，保留来源完整拼写。',
 '23369':'Ambolina Snow与其他拼写近似记录不作为同一曲目证据；无法确认其中文专名，保留原题。',
 '25839':'Noun与fretwork circle带有作者的命名隐喻；无法确认circle所指结构，不编造吉他技术术语，保留原题。',
 '26674':'档案记录没有来源曲名；原字段是带DGA编号的缺题占位，不作为实际作品名称。',
 '28287':'FiUe Diuersions含疑似排印或转录损伤；没有原版依据，不能补成Five或推定五首，保留来源原题。',
 '20958':'Ernani是歌剧专名，没有可靠中文题名证据；保留原名，不按普通单词音译。',
 '21657':'Euryanthe是歌剧专名；保留原题及印出的Weber责任信息，不再造音译。',
 '21973':'Marco Spada是人名式歌剧题名；保留原名及Auber来源署名。',
 '22030':'Nabucodonosor是特定人名式歌剧题名；不能不核源就替换为另一Nabucco版本名，保留来源写法。',
 '22129':'Satanella是专名式舞剧标题，单译恶魔可能改变命名意图，保留原文及来源署名。',
 '23799':'Mars在法文中既可指三月又可指火星或战神；没有足够命名证据，保留原题而不猜义。',
 '26450':'indienne可能指印度或美洲原住民语境；仅凭团体名不能确定这个版本的正式中文书名，保留原文。',
 '25164':'Nén是简短专名式原题；语言和命名所指不明，不造音译。',
 '37334':'Mince不能仅凭近似拼写认定为Minué或小步舞曲；保留原题，不修补未获证明的音乐体裁。',
 '26130':'Mizoona是来源专名式曲名；没有足够语义解释，保留完整原题。',
 '24536':'Cordofoni既是弦鸣乐器术语又可能是作品构思名；无法确认作者命名意图，保留原文。',
 '26703':'Ferdinando Sor是来源人名式书目标题；不猜补特定作品，也不擅改为Fernando拼写。',
 '36523':'Scala Obliqua e Contraria是历史技术语境的音阶标题；未确定该教材对Obliqua的技术定义，采用完整原题。',
}
truncated_ids='26991 28785 34776 34772 34771 35380 36008 36952 35092 35095 35733 29203 36446 36447 37605 27104'.split()
for ident in truncated_ids:
 retained[ident]='来源题名的书目或曲目尾部已截断；没有足够原版证据恢复缺失文字，保留完整现存原题及省略标记，不猜补作品。'
HAN=re.compile(r'[\u3400-\u9fff]')


def family(r):
 t=r['display_original']
 m=re.fullmatch(r'"Kukuk\." / Musikalische Rundschau\. / 136 / Kurze Unterhaltungs=Stücke für die Guitarre\. / Heft (\d+)',t)
 if m:return '杜鹃——音乐纵览：136首吉他娱乐短曲，第'+m[1]+'册'
 # These recurring complete edition statements were each read in the same
 # supplied-title batch. All volumes/opuses, absence of opus, and part numbers
 # are carried through verbatim; no composer identity follows from the book.
 if re.match(r'(?i)^(?:o?The Guitar Works|Complete ?Works(?: for G(?:u?uit?ar|ultar))?)\b',t) and not '...' in t:
  z=t
  z=re.sub(r'(?i)^o?The Guitar Works','吉他作品',z)
  z=re.sub(r'(?i)^Complete ?Works for G(?:u?uit?ar|ultar)','吉他作品全集',z)
  z=re.sub(r'(?i)^Complete ?Works','作品全集',z)
  z=re.sub(r'(?i)\bvol\.?\s*(\d+)',lambda m:'第'+m[1]+'卷',z)
  z=re.sub(r'(?i)Solo ?Works|Guitar Solos','吉他独奏作品',z)
  z=re.sub(r'(?i)Music for 2 Guitars','双吉他乐曲',z)
  z=re.sub(r'(?i)Works for Oboe','双簧管作品',z)
  z=re.sub(r'(?i)Unpublished','未发表的',z)
  z=re.sub(r'(?i)(?:G\.\s*Duets|Guitar Duets)','吉他二重奏',z)
  z=re.sub(r'(?i)Works for Guitar & Keyboard','吉他与键盘作品',z)
  z=re.sub(r'(?i)Works for Guitar & Flute/Violin','吉他与长笛／小提琴作品',z)
  z=re.sub(r'(?i)Works without (?:Opus Number|op\. No\.)','无作品号作品',z)
  z=re.sub(r'(?i)Studio per la Chitarra','吉他练习曲',z)
  z=re.sub(r'(?i)Grand Duo Concertant','大型协奏性二重奏',z)
  z=re.sub(r'(?i)1st G\.\s*Pt\.','第1吉他声部',z)
  z=re.sub(r'(?i)2nd G\.\s*Pt\.','第2吉他声部',z)
  z=re.sub(r'(?i)facs\.\s*ed\.?','（影印版）',z)
  z=re.sub(r'(?i)\bop\.?\s*','作品',z)
  # Remaining lexical text must be only catalogue/range literals, punctuation
  # and already interpreted Chinese descriptors.
  if re.search(r'[A-Za-z]{2,}',z):return None
  return z.strip(' .')
 return None

entries=[];unhandled=[]
for r in rows:
 z=readings.get(r['id']) or family(r)
 ident=r['id'].split(':')[-1]
 if not z or not HAN.search(z):
  if ident not in retained:unhandled.append(r);continue
  z='来源未载题名（DGA26674）' if ident=='26674' else r['display_original']
  entries.append(dict(id=r['id'],original=r['original'],original_composer=r['composer'],display_original=r['display_original'],zh='《'+r['original']+'》',display_zh='《'+z+'》',status='retained',basis='exact_archive_original_retention_2026_10_03',reason=retained[ident],source_refs=[r['source_url']],review_method='exact_original_retention',reviewer='Codex 2026-10-03'))
  continue
 entries.append(dict(id=r['id'],original=r['original'],original_composer=r['composer'],display_original=r['display_original'],zh='《'+z+'》',display_zh='《'+z+'》',status='reference',basis='exact_primary_title_semantic_reading_2026_10_03',reason='逐项审读主标题的实际语义、乐器关系与音乐编号；参考中文保留不能确认中文专名的原拼写，出版、献辞、责任说明及完整合订转录保留于原文。',source_refs=[r['source_url']],review_method='exact_primary_title_reading',reviewer='Codex 2026-10-03'))
(ROOT/'work/title-review/2026-10-03/archive-review/root-dga-unhandled.json').write_text(json.dumps(unhandled,ensure_ascii=False,indent=2)+'\n')
(HERE/'root_dga_supplement.json').write_text(json.dumps({'schema_version':1,'entries':entries},ensure_ascii=False,indent=2)+'\n')
print('input',len(rows),'decided',len(entries),'unhandled',len(unhandled))
for r in unhandled:print(r['id'],'|',r['display_original'])
