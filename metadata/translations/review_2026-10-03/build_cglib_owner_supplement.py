"""Second complete semantic pass for precisely owner.json, not other partitions."""
import collections,hashlib,json,re,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];sys.path.insert(0,str(HERE))
import build_cglib_review as cg
INPUT=ROOT/'work/title-review/2026-10-03/cglib-retained-pass/owner.json'
ROWS=json.loads((INPUT.parent/'owner-corpus.json').read_text())
FROZEN=json.loads((INPUT.parent/'owner-frozen-lexicon.json').read_text())
PHRASES=FROZEN['phrases'].copy();TERMS=FROZEN['terms'].copy()
for line in (HERE/'cglib_owner_phrases.tsv').read_text().splitlines():
 if line and not line.startswith('#'):
  a,b=line.split('\t',1);PHRASES[cg.q.normphrase(a)]=b
TERMS.update({'opuses':'作品','opp':'作品','brillans':'华丽','brillantes':'华丽','valsas':'圆舞曲','monferine':'蒙费里纳舞曲','monferrine':'蒙费里纳舞曲','monferrina':'蒙费里纳舞曲','loure':'卢尔舞曲','rigodon':'里戈东舞曲','rigodon':'里戈东舞曲','rigodon':'里戈东舞曲','paspied':'帕斯皮耶舞曲','passepied':'帕斯皮耶舞曲','romanza':'浪漫曲','polonoise':'波兰舞曲','polonese':'波兰舞曲','valses':'圆舞曲','walses':'圆舞曲','walzes':'圆舞曲','eccosaises':'苏格兰舞曲','ecossoises':'苏格兰舞曲','eccosaisen':'苏格兰舞曲','waltz':'圆舞曲','lento':'慢板','sostenuto':'持续地','piu mosso':'更快地','più mosso':'更快地','poco animato':'稍活跃地','meno':'较少地','dolorido':'悲伤地','molto adagio':'很慢的柔板','posato':'安静地','presto':'急板','violin solo':'小提琴独奏','vn. solo':'小提琴独奏','choeur':'合唱','rhapsody':'狂想曲','rapsodia de concierto':'音乐会狂想曲','garrotin':'加罗廷舞曲','taranto':'塔兰托曲','tarantos':'塔兰托曲','farruca':'法鲁卡舞曲','farrucas':'法鲁卡舞曲','soleares':'索莱亚曲','siguiriyas':'西吉里亚曲','zambra':'桑布拉舞曲','batucada':'巴图卡达舞曲','song of the tree':'树之歌','buree':'布列舞曲','polcka':'波尔卡（原题拼写照录）','ballabili':'舞曲','preludi':'前奏曲','cantilènes':'歌唱性乐曲','cantilene':'歌唱性乐曲','canzonnette':'小歌','ballabile':'舞曲','arpejo':'琶音','solfege':'视唱','guittarre':'吉他','guitarre':'吉他','guitairre':'吉他','guiterre':'吉他','cordas dedilhadas':'拨弦乐器','fugen':'赋格','orchestra':'管弦乐队','leichte':'简易','progressivi':'渐进','fortschreitende':'渐进','sonaten':'奏鸣曲','solo guitar':'吉他独奏','chitarra sola':'吉他独奏','francese':'法式','chanson':'歌曲','chansons':'歌曲','canto':'歌','cantabile':'如歌地','espressivo':'富于表情','vivo':'活泼地','moderato':'中板','entree':'开场曲','paisanne':'田园曲','paisanna':'田园曲','complète':'完整','petit':'小','petites':'小','easy and instructive pieces':'简易教学小品','saltarelles':'萨尔塔雷洛舞曲','sauteuses':'跳跃舞曲','flute or violin':'长笛或小提琴','the spanish guitar':'西班牙吉他','english guitar':'英式吉他','arpa':'竖琴','bagatelles':'小品','minués':'小步舞曲','minuès':'小步舞曲','aria':'咏叹调','adantino':'小行板（原题拼写照录）','preludo':'前奏曲（原题拼写照录）','sonanta':'奏鸣曲（原题拼写照录）','sonatan':'奏鸣曲（原题拼写照录）','gu iat':'吉他','andande':'行板（原题拼写照录）','sodtenuto':'持续地（原题拼写照录）','prelule':'前奏曲（原题拼写照录）'})
cg.PHRASES=PHRASES;cg.TERMS=TERMS;cg.PHRASE_PATTERN=re.compile(r'(?<!\w)(?:'+'|'.join(re.escape(k) for k in sorted(PHRASES,key=len,reverse=True))+r')(?!\w)',re.I)
EXACT={};RETAIN={};EXTRAREFS={}
extra=HERE/'cglib_owner_exact.json'
if extra.exists():
 d=json.loads(extra.read_text());EXACT=d.get('translations',{});RETAIN=d.get('retentions',{});EXTRAREFS=d.get('source_refs',{})
for line in (HERE/'cglib_owner_exact.tsv').read_text().splitlines():
 if line and not line.startswith('#'):
  ident,value=line.split('\t',1);EXACT['cglib:'+ident]=value

def clean(text):
 return re.sub(r'\s+',' ',text.replace('_',' ')).strip(' .,:;-')
def tidy(z):
 z=re.sub(r'小步([升降]?[A-G](?:大调|小调|调))舞曲',r'\1小步舞曲',z)
 z=z.replace('奇幻想随想曲','奇幻随想曲').replace('变奏华丽','华丽变奏').replace('二把吉他','两把吉他')
 z=re.sub(r'(教程|新教程|完整教程)吉他',r'吉他\1',z)
 return z.strip(' .,:;，。')
def raw_label(text):
 return PHRASES.get(cg.q.normphrase(text),text)
def semantic(body,depth=0):
 if depth>5:return None,None
 body=clean(body)
 direct=PHRASES.get(cg.q.normphrase(body))
 if direct and cg.q.HAN.search(direct):return direct,'full_phrase_semantic'
 m=re.fullmatch(r'Opus ([0-9]+) No ([0-9]+) \(Segovia Study ([0-9]+)\)',body,re.I)
 if m:return '练习曲，作品'+m[1]+'第'+m[2]+'号（原题标记：Segovia 练习曲第'+m[3]+'号）','explicit_edition_study_numbers'
 m=re.fullmatch(r'(.+?)\s+(?:No\.?|N)\s*([0-9]+)',body,re.I)
 if m:
  z,method=semantic(m[1],depth+1)
  if z:return z+'第'+m[2]+'号',method+'_serial'
 m=re.fullmatch(r'(.+?)\s+(Apke|apke)',body)
 if m:
  z,method=semantic(m[1],depth+1)
  if z:return z+'（原题标记：'+m[2]+'）',method+'_copy_label'
 m=re.fullmatch(r'(Pieces for Guitar interlude) ([0-9]+)',body,re.I)
 if m:return '吉他小品：第'+m[2]+'间奏曲','complete_count_genre_frame'
 m=re.fullmatch(r'(21st Century Nocturnes),? (?:Op\.1 )?Part ([12])',body,re.I)
 if m:return '二十一世纪夜曲，作品1，第'+m[2]+'部分','complete_volume_count_genre'
 # Parts are source evidence independent from the opaque/incidental title.
 m=re.fullmatch(r'(.+?)\s+(?:Duo\s+)?(?:Guitar|Guiar|Guiat|GT)\s*([1-9IV]+)',body,re.I)
 if not m:m=re.fullmatch(r'(?:Duo\s+)?(?:Guitar|Guiar|Guiat|GT)\s*([1-9IV]+)\s+(.+)',body,re.I);m=(m[2],m[1]) if m else None
 if m:
  label,number=(m[0],m[1]) if isinstance(m,tuple) else (m[1],m[2]);z,method=semantic(label,depth+1)
  return (z or raw_label(label))+'（吉他第'+number+'分谱）','explicit_part_title_structure'
 m=re.fullmatch(r'(.+?)\s+(?:Violin|Mandoline|Guitar|Banjo)(?:\s+Part)?',body,re.I)
 if m and len(m[1])<180:
  instrument={'violin':'小提琴','mandoline':'曼陀林','guitar':'吉他','banjo':'班卓琴'}[body[m.end(1):].strip().split()[0].casefold()];z,_=semantic(m[1],depth+1)
  return (z or raw_label(m[1]))+'（'+instrument+'分谱）','explicit_instrument_part_title'
 m=re.fullmatch(r'Duo Mandoline and Guitar \((Guit|Mand)\) (.+)',body,re.I)
 if m:return raw_label(m[2])+'（曼陀林与吉他二重奏，'+('吉他' if m[1].lower()=='guit' else '曼陀林')+'分谱）','explicit_scored_part_title'
 # Isolated source-copy labels are not original/arrangement determinations.
 m=re.fullmatch(r'(.+?)\s*(?:[- ]+(orig|org|new|split\s*\d+|manuscript|manusrcito|[ab]))',body,re.I)
 if m:
  z,method=semantic(m[1],depth+1)
  if z:return z+'（原题标记：'+m[2]+'）',method+'_source_copy_label'
 m=re.fullmatch(r'(.+?)\s*(?:Book|vol(?:ume)?|Livre|Liv|H\.|Heft|cah|pt)\.?\s*[- ]?(\d+(?:-\d+)?)(.*)',body,re.I)
 if m and not m[3].strip(' -'):
  z,method=semantic(m[1],depth+1)
  if z:return z+'，第'+m[2]+'册',method+'_volume'
 # Genuine leaf/catalogue references are preserved, never translated as music.
 m=re.fullmatch(r'(.+?)(?:,\s*)?((?:CSdG|CS4|PyO|Rda)[, ]+)?(f\.?\s*\d+[rv]?(?:-\d+[rv]?)?(?:\s+[IV]+)?)',body,re.I)
 if m:
  z,method=semantic(m[1],depth+1)
  if z:return z+'（原目录标记：'+(m[2] or '')+m[3]+'）',method+'_folio'
 m=re.fullmatch(r'(.+?)\s+((?:EL|EV|FP|IGS|Mn|HMW|WVE|TWV|FGC)\s*[-.:]?\s*\d+(?:\s+\d+|[a-z])?)',body,re.I)
 if m:
  z,method=semantic(m[1],depth+1)
  if z:return z+'（'+m[2]+'）',method+'_catalogue'
 # Opus frame around a retained exact label does not invent a name meaning.
 ops=cg.q.OPUS.findall(body)
 if not ops and re.search(r'\bOpp\.',body):ops=re.findall(r'\bOpp\.\s*(\d+)',body)
 if ops:
  stem=clean(re.sub(r'\(\s*\)', '',cg.q.OPUS.sub('',re.sub(r'\bOpp\.', 'Op.',body))))
  if stem!=body:
   z,method=semantic(stem,depth+1)
   if z:return z+'，'+ '、'.join('作品'+x for x in ops),method+'_opus'
   if re.fullmatch(r'[A-Za-zÀ-ž .’\x27-]{2,55}',stem) and len(stem.split())<=6 and not re.search(r'\b(?:de|du|des|le|la|les|for|pour|sur|über|on|and|et|über|delle|della|dell|di|per|variations|fantaisie|sonata|method)\b',stem,re.I):
    return raw_label(stem)+'，'+ '、'.join('作品'+x for x in ops),'named_label_opus_frame'
 # Clear work/collection family, whole subordinate labels kept if uncertain.
 m=re.fullmatch(r'(Castillos de Espana|Castles Of Spain|Puertas de Madrid|Aires de La Mancha|Suite Compostelana|Suite In Modo Polonico|LEsprit Italienne|Suite Castellana|Siete Piezas De Album|Deux Chansons Populaires)\s+(.+)',body,re.I)
 if m:
  title=raw_label(m[1]);tail=m[2];num=re.match(r'(\d+|[IV]+)\s+(.+)',tail)
  if num:tail=num[2];title+='：第'+num[1]+'曲'
  z,_=semantic(tail,depth+1);return title+'——'+(z or raw_label(tail)),'full_collection_and_subtitle'
 m=re.fullmatch(r'12 Fantasias Para 2 Guitarras\s+(\d+)\s+(.+)',body,re.I)
 if m:return '两把吉他的十二首幻想曲：第'+m[1]+'曲——'+raw_label(m[2]),'explicit_count_scoring_title'
 m=re.fullmatch(r'Demian\s+(\d+)\s+(.+)',body,re.I)
 if m:return 'Demian：第'+m[1]+'曲——'+raw_label(m[2]),'numbered_named_title'
 m=re.fullmatch(r'(?:No\.?|N)\s*(\d+)\s+(.+)',body,re.I)
 if m:
  z,_=semantic(m[2],depth+1)
  if z:return '第'+m[1]+'号：'+z,'serial_full_title_structure'
 # Standalone exact source version/count is kept as a label, not a duration.
 m=re.fullmatch(r'(.+?)\s+(\d+)',body)
 if m:
  z,method=semantic(m[1],depth+1)
  if z:return z+'（原题标记：'+m[2]+'）',method+'_source_number'
 # Explicitly quoted thematic labels can remain fully Latin; the relation is
 # independently supplied by the whole variations/fantasy syntax.
 m=re.fullmatch(r'(?:([0-9]+)\s+)?(?:Variations|Variazioni|Variationen|Variaciones)\s+(?:on |sur |sopra |über |sobre )(.+)',body,re.I)
 if m and not re.search(r'\b(?:for|pour|per|para|für|guitar|guitare|guitarre|chitarra|arr|Op|cavatine|thème|theme|tema)\b',m[2],re.I):
  return (m[1]+'段' if m[1] else '')+'〈'+raw_label(m[2])+'〉主题变奏曲','whole_quoted_variation_structure'
 m=re.fullmatch(r'(?:Grand\s+)?(?:Fantasie|Fantaisie|Fantasy|Fantasia)\s+(?:on|sur|über)\s+(.+)',body,re.I)
 if m and not re.search(r'\b(?:for|pour|per|para|für|guitar|guitare|guitarre|chitarra|arr|Op|motives|motifs|thème|theme|thema)\b',m[1],re.I):
  return '〈'+raw_label(m[1])+'〉幻想曲','whole_quoted_fantasy_structure'
 # Exact source-only appendix labels are outside the clean title; retain them
 # while translating the complete genre/key/movement clause.
 normalized=re.sub(r'\b(in)\s+([A-G])([#b]?)(m)\b',lambda m:'in '+m[2]+(' sharp' if m[3]=='#' else ' flat' if m[3]=='b' else '')+' minor',body,flags=re.I)
 normalized=re.sub(r'\b(in)\s+([A-G])(b)\b',lambda m:'in '+m[2]+' flat',normalized,flags=re.I)
 z,annotations=cg.full_music(normalized)
 if z:return tidy(z),'complete_music_full_phrase'
 # Genre is independently explicit, so an opaque single label remains source
 # text beside its Chinese genre instead of suppressing the entire title.
 genres=r'(?:Waltzes?|Val[sz]es?|Valse|Polka|Mazurka|Schottisch|Galop|Gavotte|Chaconne|Caprice|Prelude|Preludio|Sonata|Nocturne|Nocturno|Tango|Samba|Cavatina|Serenade|Romance|March|Marche|Duo|Rag|Rhapsody|Fantasia)'
 m=re.fullmatch(r'(.{1,75}?)\s*[- ]\s*('+genres+r')',body,re.I)
 if not m:m=re.fullmatch(r'('+genres+r')\s+(.{1,75})',body,re.I);m=(m[2],m[1]) if m else None
 if m:
  label,genre=(m[0],m[1]) if isinstance(m,tuple) else (m[1],m[2]);gz,_=cg.full_music(genre)
  if gz and not re.search(r'\b(?:for|pour|per|para|für|with|and|et|sur|on|from|dell|di|de|in|major|minor|guitar|theme|op)\b',label,re.I):
   return raw_label(label)+'——'+gz,'explicit_label_genre'
 return None,None

def retention(body):
 # Specific short explanations derived from this title's actual obstacle.
 if re.fullmatch(r'\d+',body):return '纯数字题名，没有证据说明是年号或曲目编号。'
 if re.search(r'\bsinfon[ií]a\b',body,re.I):return 'Sinfonia 的序曲或独立交响性乐曲含义尚不能由此题名限定。'
 if re.search(r'\.{2,}|…|_{2,}|<|>|i\.e\.|degree mark',body):return '题名含转录残片或字形说明，完整含义无法可靠恢复。'
 if re.search(r'Brombarion|Snowhere|Bluefinger|Musettology|Locomotivation|Snowhere|Snowhere|Snowhere|Viorigolao|B\.A\. Rock|Arpi and Peggio|Arpi|Windy Warm|Moontan|The Jig Is Up|Cap i Cúa',body,re.I):return '作者题名含造词或双关，未查到足以确定此处所指的释义。'
 if len(body.split())<=3:return '孤立题名 '+body+' 的专名或特定所指尚无可靠释义。'
 return '题名含未确认的特定名称或引文关系：'+body[:70]+'。'

def decision(row):
 body=row['display_original'];notes=[]
 # Only remove a final by clause when its full suffix agrees with the source
 # attribution; a title can itself contain By or multiple named works.
 candidates=list(re.finditer(r'\s+by\s+',body,re.I))
 if candidates:
  m=candidates[-1];tail=body[m.end():];suffix=re.search(r'\s+(Guitare?\s*[1-9]|Guitar\s*[1-9]|GT\s*[1-9])$',tail,re.I)
  author=tail[:suffix.start()] if suffix else tail
  marker=re.search(r'\s+(\(?\d+\)?)$',author)
  if marker:author=author[:marker.start()]
  if len(author.split())<=8 and not re.search(r'\b(?:op|opus|no|nr|arranged|accompaniment|duets|for|pour|para|per|teacher|waltz|music|your|side)\b',author,re.I):
   body=body[:m.start()]+(' '+suffix[1] if suffix else '')+(' ('+marker[1].strip('()')+')' if marker else '')
 body=clean(body)
 # Parenthetical supplied attribution is source metadata, not a new identity.
 authors=re.findall(r'\(([^()]*,[^()]*)\)',body)
 for a in authors:body=clean(body.replace('('+a+')',''))
 if row['id'] in RETAIN:value=None;method='specific_retention'
 elif row['id'] in EXACT:value=EXACT[row['id']];method='exact_individual_semantic'
 else:value,method=semantic(body)
 reason='对照完整原题核对音乐结构与语义；未确认专名保留原拼写。' if value else RETAIN.get(row['id'],retention(body))
 refs=EXTRAREFS.get(row['id'],[]).copy()
 for term,url in [('taranto','https://dle.rae.es/taranto'),('garrotin','https://dle.rae.es/garrot%C3%ADn')]:
  if term in cg.q.normphrase(body):refs.append(url)
 if 'Home, sweet home' in body or 'Home, Sweet Home' in body:refs.append('https://tile.loc.gov/storage-services/public/music/mussm2-sm1841-021670/mussm2-sm1841-021670.pdf')
 out={'id':row['id'],'original':row['original'],'original_composer':row['composer'],'zh':cg.wrap(tidy(value)) if value else cg.wrap(row['original']),'status':'reference' if value else 'retained','basis':'cglib_retained_owner_complete_semantic_pass_2026_10_04','reason':reason,'source_refs':refs,'reviewer':'codex_cglib_partition','review_method':method or 'specific_title_retention'}
 if value:out.update(display_original=row['display_original'],display_zh=cg.wrap(tidy(value)))
 return out

def main():
 ids=json.loads(INPUT.read_text())['entries'];assert len(ROWS)==len(ids)==2757 and {r['id'] for r in ROWS}=={e['id'] for e in ids}
 entries=[decision(r) for r in ROWS]
 out=HERE/'cglib_owner_retained_supplement.json';out.write_text(json.dumps({'schema_version':1,'entries':entries},ensure_ascii=False,indent=2)+'\n')
 stats={'records':len(entries),'statuses':dict(collections.Counter(e['status'] for e in entries)),'methods':dict(collections.Counter(e['review_method'] for e in entries)),'sha256':hashlib.sha256(out.read_bytes()).hexdigest()}
 (INPUT.parent/'owner-coverage.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2)+'\n')
 (INPUT.parent/'owner-remaining.tsv').write_text('\n'.join('\t'.join([str(i),e['id'],cg.body_of(r)[0],e['reason']]) for i,(r,e) in enumerate(zip(ROWS,entries)) if e['status']=='retained')+'\n')
 (INPUT.parent/'owner-reference.tsv').write_text('\n'.join('\t'.join([e['id'],cg.body_of(r)[0],e['display_zh'],e['review_method']]) for r,e in zip(ROWS,entries) if e['status']=='reference')+'\n')
 print(json.dumps(stats,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
