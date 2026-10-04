"""Reproducible root-partition title review, using exact phrases and closed music syntax."""
import json, re, sys, unicodedata
from collections import Counter
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from cglib_semantic_rules import semantic_title, normphrase, title_body
from build_cglib_review import phrase_vocab, PHRASES as CGLIB_PHRASES
from catalog_translations import display_source_title, wrap_display_title
from catalog_display import DELCAMP_ATTRIBUTION_LABELS, DELCAMP_TITLE_CONTAMINATED_ATTRIBUTIONS
from review_source_translations import TERMS
from build_classclef_translations import MUSIC_TERMS
BASE_TERMS={**MUSIC_TERMS,**TERMS}
BASE_TERMS.update({'quintette':'五重奏','rondeaux':'回旋曲','rondos':'回旋曲','varié':'变奏','varie':'变奏','variés':'变奏','arpèges':'琶音','parte':'部分','walzes':'圆舞曲','walses':'圆舞曲','polonaisen':'波兰舞曲','polonais':'波兰舞曲','número':'第','numero':'第','tre':'三','ou':'或','lyre':'里拉琴','very':'极','très':'极','tres':'极','landler':'兰德勒舞曲','waltzing':'圆舞曲',"to":"至","buxwv":"BuxWV","holograph manuscript":"亲笔手稿","ca":"约","grande":"大型","duets and trios for classicals guitars":"古典吉他二重奏与三重奏","grades":"级别","grade":"级别","pages":"页","string":"弦","strings":"弦","tunes":"曲调","seis":"六","triad":"三和弦"})
BASE_TERMS.update({'Dresde':'德累斯顿','Varsovie':'华沙','Vienne':'维也纳','Harrach':'Harrach','part a':'部分a','part b':'部分b','after':'源自','with facsimiles':'与影印本','self instructor':'自学教程','aliás':'别名','alias':'别名','illustrated':'图解','edited by':'由…编订','principally':'主要','cadences':'终止式','modulations':'转调','œuvres':'作品','catalan':'加泰罗尼亚','tablatures':'指法谱','facsimiles':'影印本','lute works':'鲁特琴作品','songs with lyrics':'附歌词的歌曲','con letra':'附歌词','mandore':'曼多尔琴','segunda edizione':'第二版','viola d’amore':'柔音中提琴'})
BASE_TERMS.update({'study':'练习曲','studies':'练习曲集'})
rows=json.loads((ROOT/'work/title-review/2026-10-03/root.json').read_text())
phrases={unicodedata.normalize('NFC',k):v for k,v in json.loads((HERE/'root_semantic_phrases.json').read_text()).items()}
# The original source spellings and attribution are guards, not new identities.
phrases.update({'Españoletas':'西班牙小舞曲','Sevillianas (populares)':'传统塞维利亚舞曲','12-tone blues':'十二音蓝调','2 Mandolins Concerto':'双曼陀林协奏曲','Mandolin Concerto':'曼陀林协奏曲','Lute Concerto':'鲁特琴协奏曲','Air - Sailing':'曲调：航行','Allegro Brillante':'辉煌的快板','Choro Andaluz':'安达卢西亚肖罗曲','Serenade for guitar, flute, and viola':'吉他、长笛与中提琴小夜曲','Hand-book for Guitar':'吉他手册','Works for guitar':'吉他作品','La Original':'独特'})
refs_by_phrase={
 'Julia Florida':['https://www.bilibili.com/list/618775304?bvid=BV1Hh4y1B7GK&oid=662381921'],
 'Air varié de Vive Henry IV by Piston':['https://www.thisisclassicalguitar.com/air-varie-de-vive-henry-iv-julia-piston/'],
 'Que ne suis-je la fougère':['https://fr.wikisource.org/wiki/Que_ne_suis-je_la_foug%C3%A8re'],
 'Click Go The Shears':['https://nla.gov.au/nla.obj-169068877/view'],
 'Djembe':['https://dictionary.cambridge.org/us/dictionary/english/djembe'],
 'Ashokan Farewell':['https://www.jayandmolly.com/about-2'],
 'Sonata No. 8 “Pathétique” (2nd Movement: Adagio cantabile)':['https://ncpa-classic.cntv.cn/sxlb/five/index.shtml','https://en.chncpa.org/whatson/calendar/seasonbrochure/P020180418584167476705.pdf'],
 'Op. 15. Divertissement aus der Oper: Don Pasquale, von G. Donizetti':['https://www.chncpa.org/zxdt_331/zxdtlm/yczx_332/201607/t20160714_132255.shtml'],
}
EXACT_PHRASES={normphrase(k):v for k,v in phrases.items()}
retentions={
 'Waltzing Matilda': ('澳大利亚民歌题名中的 waltzing/Matilda 是历史俚语；国家图书馆保存歌曲与流浪工背景，不按华尔兹舞曲直译。', ['https://www.library.gov.au/learn/digital-classroom/documenting-federation/national-identity']),
 'And The Band Played Waltzing Matilda': ('歌曲题名引用澳大利亚民歌 Waltzing Matilda；保留该历史专名，避免把引用误写成华尔兹。', ['https://www.library.gov.au/learn/digital-classroom/documenting-federation/national-identity']),
 'Moontan': ('作曲家官网使用 Moontan 并说明为木村大创作；这是特殊造词，没有足够依据确定中文构词，保留原文。', ['https://andrewyork.net/sheetmusicdownloads.html']),
 'Kinderlight': ('作曲家官网以 Kinderlight 列出七首组曲；混合语言造词不能据字面确认命名意图，保留原文。', ['https://andrewyork.net/Publications.php/SheetMusic/']),
 'Centerpeace': ('Centerpeace 是含 peace/piece 文字游戏的原题；单译中心或和平会丢失题名构词，保留原文。', []),
 'DissFunkShun': ('标题通过 Funk 与原词拼写形成双关；不造生硬音译，保留作者原拼写。', []),
 'I Yam What I Yam': ('I Yam 与 I am 形成拼写和语音双关；保留原题，不将 Yam 硬译成山药。', []),
 'Rhimes': ('来源使用 Rhimes 而非 Rhymes；不能擅自更正拼写或把它认定为人名，保留原题。', []),
 'Trambone': ('题名为 Trambone，不能当作 trampoline（蹦床）或擅改为 trombone（长号）；保留原拼写。', []),
 'Somberland Views': ('Somberland 是题名中的专名式造词；不能确认所指地点或构词，保留完整原题。', []),
 '45. Romanza Deluxe - Score.pdf': ('Romanza Deluxe 是版本式专题名；保留原题主体，Score 与文件后缀作为格式信息分离。', []),
 'Pumping Nylon': ('出版社将 Pumping Nylon 作为技巧教材系列名；Nylon 指尼龙弦，标题含训练隐喻，保留出版原名，不直译成泵送尼龙。', ['https://www.alfred.com/products/pumping-nylon-second-edition-00-44950']),
}
# Source-specific complete titles, rather than a substring guessed attribution.
exact={
 'loc:hlas-bi2006003084': ('曼努埃尔·庞塞吉他作品全集：依原始手稿编订（Miguel Alcázar编订）', ['https://cid-albertobeltran.cultura.gob.mx/catalogo-biblioteca/obra-completa-para-guitarra-de-manuel-m-ponce-de-acuerdo-a-los-manuscritos-originales-miguel-de-alcazar/']),
 'loc:hlas-bi97017637': ('Santiago de Murcia〈Saldívar手稿第4号〉：墨西哥巴洛克世俗吉他音乐宝库（Craig H. Russell编订）', []),
 'loc:scsm000213': ('王国将临（John Molter吉他改编）', []),
 'loc:afcreed000049': ('A调快舞曲／霜晨', []),
 'loc:afcreed000050': ('咯咯叫的老母鸡', []),
}
exact.update({
 'mutopia:1108': ('第18曲：Kelvin Grove', []),
 'mutopia:1145': ('第48曲：致Alexis', []),
 'mutopia:1148': ('第51曲：苏格兰曲调〈Kelso〉', []),
 'guitarschool:3022': ('Yarou Yarou：匈牙利幻想曲', []),
 'guitarschool:1017': ('第四调式幻想曲：和弦与快速音阶幻想曲', ['https://recursos.march.es/web/musica/jovenes/cuadros-que-suenan/pdf/guias-cuadros-que-suenan.pdf']),
 'guitarschool:1204': ('〈Terpsichore〉选曲4首', []),
 'guitarschool:1015': ('来自Alabama的微风／Pecherine拉格泰姆', []),
 'guitarschool:1191': ('狩猎', []),
 'guitardownunder:aint_misbehaving.php': ('不再胡闹', []),
 'guitardownunder:alices_restaurant.php': ('Alice的餐馆', []),
 'guitardownunder:the_band_played_waltzing_matilda.php': ('乐队奏起〈Waltzing Matilda〉', ['https://www.library.gov.au/learn/digital-classroom/documenting-federation/national-identity']),
 'guitardownunder:trumpton.php': ('Trumpton消防员', []),
 'guitardownunder:walk-away-renee.php': ('走开吧，Renee', []),
 'andrewyork:KingLotvin.html': ('Lotvin国王', []),
 'andrewyork:NumenSuite.html': ('Numen组曲', ['https://andrewyork.net/SheetMusicDownloads.php']),
 'andrewyork:NuoDuo.html': ('Nuo二重奏', ['https://andrewyork.net/SheetMusicDownloads.php']),
 'werner:rosita-polka-francisco-tarrega-pdf': ('Rosita波尔卡', []),
 'werner:rossini-giuliani-se-inclinassi-a-prender-moglie': ('Rossini〈若我愿娶妻〉（Giuliani改编）', ['https://www.thisisclassicalguitar.com/rossini-giuliani-se-inclinassi-a-prender-moglie/']),
 'werner:tarletons-riserrectione-dowland-guitar': ('Tarleton的复活', []),
 'werner:payssanos-greensleeves-murcia-pdf': ('Murica：Payssanos（〈绿袖子〉主题）', []),
 'freeguitarmusic:1p7qgdY00PSj_fUjSXDm3NmOYSFPx3Gif': ('Somberland景致', []),
})


def tidy(text):
 text=re.sub(r'小步([升降]?[A-G](?:大调|小调|调))舞曲',r'\1小步舞曲',text)
 text=re.sub(r'(教程|新教程|完整教程)吉他',lambda m:'吉他'+m[1],text)
 text=text.replace('吉他教程完整','吉他完整教程').replace('作品集为吉他独奏','吉他独奏作品集')
 text=re.sub(r'(柔板|广板|回旋曲|协奏曲)为(两把吉他(?:与中提琴)?|长笛与吉他|曼陀林)',r'\2\1',text)
 text=re.sub(r'(众赞歌|二重奏|帕凡舞曲集|琶音练习曲|练习曲)\s*([升降]?[A-G](?:大调|小调|调))',r'\2\1',text)
 text=text.replace('编排','改编').replace('编号 c','夜曲')
 text=re.sub(r'(作品\d+[a-z]?)：\s*[–—-]\s*',r'\1：',text)
 text=text.replace('教程完整','完整教程').replace('变奏华丽','华丽变奏').replace('二把吉他','双吉他').replace('两把吉他','双吉他').replace('三把吉他','三吉他')
 text=re.sub(r'(奏鸣曲|前奏曲|夜曲|小夜曲|幻想曲|三重奏|二重奏|圆舞曲|回旋曲|柔板|广板|协奏曲)为([^：。，;]+)',r'\2\1',text)
 text=re.sub(r'(协奏曲|玛祖卡舞曲|苏格兰舞曲|练习|众赞歌)\s*([升降]?[A-G](?:大调|小调|调))',r'\2\1',text)
 text=re.sub(r'(前奏曲第)\s*(\d+)(?!\d)(?!号)',r'\1\2号',text)
 text=text.replace(' & ','与')
 text=re.sub(r'作品(\d+[a-z]?)：与\s*(\d+[a-z]?)',r'作品\1与\2：',text)
 text=text.replace('作品全集（为吉他而作）','吉他作品全集')
 text=text.replace('手册（为吉他而作）','吉他手册').replace('作品（为吉他而作）','吉他作品')
 text=re.sub(r'组曲\s*(\d+)\s*SW\s*(\d+)\s*([升降]?[A-G](?:大调|小调))\s*德累斯顿',r'\3第\1号组曲（SW\2，德累斯顿）',text)
 text=re.sub(r'(小奏鸣曲|组曲)\s*(\d+)(?=\s*作品)',r'第\2号\1，',text)
 text=re.sub(r'第(\d+)课\s*与\s*(\d+)(?!\d)(?!课)',r'第\1与\2课',text)
 text=re.sub(r'简易吉他圣诞歌曲\(卷\.([\d-]+) 完整\)',r'简易吉他圣诞歌曲（第\1卷，全套）',text)
 pattern=r'(\d+|[一二三四五六七八九十]+)\s*(精选|渐进|简易|华丽)?(练习|二重奏|三重奏|兰德勒舞曲|卡瓦蒂纳曲)'
 def classifier(m):
  return m[0] if re.search(r'(?:作品|第|BWV|RV|K|SW)\s*$',text[:m.start()]) else m[1]+'首'+(m[2] or '')+m[3]
 text=re.sub(pattern,classifier,text)
 return text.strip(' ,，.。')


def translate(row):
 if row['id']=='guitardownunder:michelle.php':
  return None,'proper_name_retention',[]
 raw=row['original']; title=unicodedata.normalize('NFC',display_source_title(row['display_original']))
 attribution=row['composer']
 if row['source_id']=='delcamp':
  attribution={**DELCAMP_ATTRIBUTION_LABELS,**DELCAMP_TITLE_CONTAMINATED_ATTRIBUTIONS}.get(attribution,attribution)
  if attribution=='来源未注明作曲者':attribution=''
 # Only the independently supplied full name (including an exact inverted
 # spelling) can be a removable prefix. Contaminated title words stay.
 if ',' in attribution and len(attribution.split(','))==2:
  parts=[x.strip() for x in attribution.split(',')]
  candidates=[attribution,parts[1]+' '+parts[0]]
 else:candidates=[attribution]
 body=title
 for name in candidates:
  if name:
   body=re.sub(r'^'+re.escape(name)+r'(?:\s*[:：,–—-]\s*|\s+(?=[A-ZÉ]))','',body,flags=re.I)
   body=re.sub(r'\s+by\s+'+re.escape(name)+r'\s*$','',body,flags=re.I)
 if len(body)>300:return None,'unresolved',[]
 # A prefix stripped here literally equals the independent source attribution.
 if row['id'] in exact:
  return exact[row['id']][0],'exact_semantic',exact[row['id']][1]
 if raw in retentions or title in retentions: return None,'explicit_retention',[]
 if re.fullmatch(r'Book ([1-3]) by Carlos Roldan',body):
  return re.sub(r'Book ([1-3]) by Carlos Roldan',r'第\1册（Carlos Roldan整理）',body),'exact_semantic',[]
 # Dedicated grades/extent templates preserve every source number.
 m=re.fullmatch(r'(Sheet Music for Beginner|TABS for Beginner|Intermediate Classical Guitar Sheet Music|Advanced Classical Guitar Sheet Music)\s*[–,—-]?\s*(?:(Baroque|Classical|Renaissance) period\s*[–,—-]?\s*)?(?:Grades?\s*([\d, -]+))?(?:[–, -]+(\d+) pages)?',body,re.I)
 if m:
  head={'sheet music for beginner':'初级乐谱','tabs for beginner':'初级六线谱','intermediate classical guitar sheet music':'中级古典吉他乐谱','advanced classical guitar sheet music':'高级古典吉他乐谱'}[m[1].lower()]
  return head+('（'+({'baroque':'巴洛克','classical':'古典','renaissance':'文艺复兴'}[m[2].lower()])+'时期）' if m[2] else '')+('，'+m[3].strip(' ,-')+'级' if m[3] else '')+('，'+m[4]+'页' if m[4] else ''),'closed_template',[]
 m=re.fullmatch(r'Blank (sheet music|tablature) for guitar, (\d+) staves',body,re.I)
 if m:return '吉他空白'+('五线谱' if m[1].lower()=='sheet music' else '六线谱')+'，'+m[2]+'行','closed_template',[]
 # Full exact phrase takes precedence over word vocabulary and number grammar.
 normalized=normphrase(body)
 if normalized in EXACT_PHRASES:return EXACT_PHRASES[normalized],'exact_semantic',next((refs_by_phrase[k] for k in refs_by_phrase if normphrase(k)==normalized),[])
 if normalized in CGLIB_PHRASES:return CGLIB_PHRASES[normalized],'shared_exact_semantic',[]
 name_terms={word:word for word in re.findall(r'[^\W\d_]+',attribution) if len(word)>2 and word.casefold() not in BASE_TERMS}
 proper_names=('Rossini','Mozart','Beethoven','Schubert','Bach','Sor','Giuliani','Carulli','Carcassi','Coste','Paganini','Haendel','Handel','Gelinek','Cherubini','Gallenberg','Pleyel','Narvaez','Narváez','Poulton','Stover','Sagreras','Schumann','Mendelssohn','Segovia','Kellner','Iznaola','Koonce','Noad','Pratten','Sanz','Dalza','Milano','Milan','Mertz','Weiss','Logy','Bosch','Aguado','Cutting','Holborne','Meissonnier','Molino','Susato','Murcia','Obregon','Tarrega','Tárrega','Fuhrman','Capirola','Robin Hoode','Dowland','Mudarra','Caroso','Le Roy','Domeniconi','Robinson','Bellini','Paesiello','Paisiello','Meyerbeer','Auber','Donizetti','Verdi','Flotow','Gustave','Faust','Zampa','Zanetta','Sarah','Simrock','Meissonier','Dresden','Hambourg','Copenhague','Carlos Roldan','Manuelito','Malbroug','Malboroug','Madrid','Ponce','Ferrer','de Visee','De Visee','Albeniz','Albéniz','Llobet','Viñas','Gaspar Sanz','Frank Koonce','Shearer','Kikta','Hirsh','Manjon')
 name_terms.update({name:name for name in proper_names})
 notation={word:word for word in re.findall(r'(?<!\w)\d+[a-z](?!\w)',body)}
 result=semantic_title(body,phrases={**phrase_vocab(body),**phrases},terms={**BASE_TERMS,**name_terms,**notation})
 if result:
  result=tidy(result)
  if Counter(re.findall(r'\d+',body))!=Counter(re.findall(r'\d+',result)):
   return None,'number_guard',[]
  if any(token not in result for token in notation):
   return None,'number_guard',[]
  matched=[p for p in refs_by_phrase if p.casefold() in body.casefold()]
  return result,'closed_template',[u for p in matched for u in refs_by_phrase[p]]
 return None,'unresolved',[]


def retained_reason(row,method):
 if row['id']=='guitardownunder:michelle.php':
  return '歌曲以人名Michelle为题，缺少合适意译；不另造音译，直接采用原名。'
 title=row['display_original']
 if row['original'] in retentions or title in retentions:
  return retentions.get(row['original'],retentions.get(title))[0]
 if method=='number_guard':return '原题“'+title+'”含编号或年代；候选中文无法逐项保留编号结构，采用完整来源题名。'
 if len(title)>250:return '来源题名包含长篇书目转录、献辞或歌剧歌词；分离已标注书目字段后仍不能确认完整句义，保留“'+title[:60]+'…”原文。'
 if re.search(r'\b(?:from|sur|opera|opéra|fantas|variat|Pot.?pourri)\b',title,re.I):return '原题“'+title+'”含引用作品或专名主题；不把未经确认的引用改造成中文作品名，保留原文。'
 return '原题“'+title+'”含专名、古拼写或尚无法确定的词义；不另造音译或猜补题名，直接采用来源原文。'

entries=[]; unresolved=[]
for row in rows:
 zh,method,refs=translate(row)
 status='reference' if zh else 'retained'
 if zh and 'Julia Florida' in row['display_original'] and 'Barrios' in row['composer']:
  status='reviewed'
 if zh:zh=tidy(zh)
 if not zh:
  unresolved.append(row)
  zh=display_source_title(row['display_original'])
  reason=retained_reason(row,method)
  refs=retentions.get(row['original'],retentions.get(row['display_original'],('',[])))[1]
  method='proper_name_retention' if method!='number_guard' else 'number_guard_retention'
 else:
  reason='按完整原题复核词义、音乐体裁、调性与编号；中文为参考意译，原题与署名保留。'
  if refs:reason='核对所列原作、出版或演奏资料后采用中文参考名；原題与来源署名保留。'
 entry={'id':row['id'],'original':row['original'],'original_composer':row['composer'],
        'zh':wrap_display_title(zh),'status':status,'basis':'semantic_title_review_2026_10_03' if status!='retained' else 'original_title_retention_2026_10_03',
        'reason':reason,'source_refs':refs,'review_method':method,'reviewer':'Codex 2026-10-03',
        'display_original':row['display_original'],'display_zh':wrap_display_title(zh)}
 entries.append(entry)
supplement_path=HERE/'root_delcamp_supplement.json'
if supplement_path.exists():
 by_id={row['id']:row for row in rows}
 extras={entry['id']:entry for entry in json.loads(supplement_path.read_text())['entries']}
 if len(extras)!=len(json.loads(supplement_path.read_text())['entries']):raise ValueError('duplicate Delcamp supplemental decision')
 for ident,entry in extras.items():
  r=by_id[ident]
  if r['source_id']!='delcamp' or entry['original']!=r['original'] or entry['original_composer']!=r['composer'] or entry.get('display_original')!=r['display_original']:
   raise ValueError('Delcamp supplemental review original drift: '+ident)
 entries=[extras.get(entry['id'],entry) for entry in entries]
 retained_ids={entry['id'] for entry in entries if entry['status']=='retained'}
 unresolved=[row for row in rows if row['id'] in retained_ids]
(HERE/'root_decisions.json').write_text(json.dumps({'schema_version':1,'entries':entries},ensure_ascii=False,indent=2)+'\n')
(ROOT/'work/title-review/2026-10-03/root-unresolved.json').write_text(json.dumps(unresolved,ensure_ascii=False,indent=2)+'\n')
print(len(entries),Counter(r['status'] for r in entries),Counter(r['source_id'] for r in unresolved))
for r in unresolved[:100]:print(r['source_id'],'|',r['composer'],'|',r['display_original'],'|',r['zh'])
