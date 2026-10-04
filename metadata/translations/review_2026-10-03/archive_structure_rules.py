"""Checked complete title structures for the 2026-10-03 archive review."""
import re,json
from archive_semantics import norm,grammar,EXACT,SOURCE_REFS,polish,tq,HERE
from archive_exact_supplement import EXACT as SUPPLEMENT

ROLE_MARKERS=re.compile(r'''(?ix)
 \s*(?:[,;.]\s*|/\s*)?(?:
  paroles\s+(?:de|par)\b|parole\s+(?:di|del)\b|po[ée]sie\s+(?:de|par)\b|
  musique\s+(?:de|par)\b|musica\s+(?:di|del)\b|musik\s+von\b|
  chant[ée](?:e|s)?\s+par\b|sung\s+by\b|
  (?:compiled|collected|edited|fingered|arranged|transcribed)\s+by\b|
  transcri(?:ption|pcion|p[ct]ion|tta|tto|tti|tas?)\s+(?:per|por|para|da)\b|
  trascri(?:zione|tta|tto|tti|tte)\s+(?:per|da)\b|
  (?:herausgegeben|bearbeitet|compon[iie]rt)\s+(?:von|f[üu]r)\b|
  revisione\s+e\s+diteggiatura\b|a\s+cura\s+di\b|
  composed\s+(?:and\s+dedicated\s+)?by\b|
  compos[ée]e?s?\s+(?:et\s+d[eé]di[ée]e?s?\s+)?par\b|
  comp(?:osta|oste|osti|osto)\s+(?:e\s+dedicat[aeio]\s+)?da\b|
  composizioni\s+di\b|
  transcri(?:bed|pta|tta)\s+(?:para|pour|per|for)\b|
  transcribed\s+by\b|
  edited\s+and\s+revised\b|enlarged\s+and\s+revised\b|
  r[ií]d(?:ott[aoie]|uzione|uz\.)?\s+(?:per|para)\b|
  arrang[eé](?:es?|ée?s?)\s+(?:par|pour|for)\b|
  arranged\s+(?:by|for)\b|
  dedi[ée](?:es?|ée?s?)\s+(?:à|a|au|aux)\b|
  dedicat[aeio]\s+(?:a|all[aeio]?)\b
 )''')
SERIES=re.compile(r'(?i)\s*\.?\s*Guitar\s+Archiv(?:es?|e)?\s+Series\s*,?\s*(?:No|no)\.\s*\d+\s*\.?$')

def primary_candidates(r):
 """Explicit responsibility/series statements only, never arbitrary slashes."""
 text=norm(r['display_original'])
 out=[(text,'complete_display_title')]
 m=SERIES.search(text)
 if m and m.start()>0:out.append((text[:m.start()].strip(' ,.;/'),'explicit_archive_series_tail'))
 m=ROLE_MARKERS.search(text)
 if m and m.start()>0:
  p=text[:m.start()].strip(' ,.;/')
  if len(p)>3:out.append((p,'explicit_responsibility_or_dedication_tail'))
 # The following role prepositions are removed only with a source attribution
 # token occurring in their entire suffix. This does not assign a new role or
 # identity to any name; the source composer field stays untouched.
 composer=norm(r['composer'])
 surname=composer.split(',',1)[0]
 surname=surname.split('(')[0].strip()
 if len(surname)>=3:
  for m in re.finditer(r'\s*(?:[,;.]\s*|/\s*)?(?:\b(?:par|von|by|af|da|di|v\.|comp\. von)\s+|/\s*)',text,re.I):
   suffix=text[m.end():]
   # A slash elsewhere in the musical title is not a responsibility boundary.
   # The name must begin the suffix, after only a stated honorific/initial.
   direct=re.match(r"(?:(?:M(?:r|me|lle)?|Signor|Sigr|Sig|Herr|Fr|D|Dr)[.]?\s+)*(?:[A-Z][.]\s*)*"+re.escape(surname)+r'(?!\w)',suffix,re.I)
   if not direct:continue
   after=suffix[direct.end():]
   # Do not strip a title's later named musical sections as a role statement.
   if re.search(r'\b(?:fantai?sie|nocturne|rondo|romanza|serenad[ae]|cavatina|variazioni|for|pour|per|für)\b',after,re.I):continue
   if len(suffix)<200:
    p=text[:m.start()].strip(' ,.;/')
    if len(p)>3:out.append((p,'source_attribution_role_tail'))
 # DGA's diplomatic transcription uses slash as an original printed line
 # break. A full word sequence can be read without displaying that layout.
 # Never flatten slash-separated numeric catalogues or instrument alternatives.
 if r['source_id']=='dga' and '/' in text and not re.search(r'\d\s*/\s*\d|(?:Guitar|Guitare|Guitarre|Chitarra|Flute|Piano|Violin)\s*/',text,re.I):
  flat=norm(text.replace('/',' '))
  rr=dict(r,display_original=flat)
  out.extend((c,'diplomatic_line_break_'+rule) for c,rule in primary_candidates(rr))

 return out

PARENT_PHRASES={norm(k).casefold():v for k,v in json.loads((HERE/'root_semantic_phrases.json').read_text()).items()}
def basic_translation(s):
 z=SUPPLEMENT.get(norm(s).casefold()) or EXACT.get(norm(s).casefold()) or PARENT_PHRASES.get(norm(s).casefold()) or grammar(s)
 return polish(z) if z else None

def structured(r):
 text=norm(r['display_original'])
 # RISM's explicit collection labels and shelfmarks are descriptions, not
 # distinctive work titles. Identifier and exact item count remain literal.
 m=re.fullmatch(r'(\d+) Items; Composite; (.+)',text)
 if m:return (f'{m[1]}项合编文献（{m[2]}）','reference','rism_explicit_composite_catalogue_label','Items 是目录项目数，Composite 为合编来源描述；不宣称为同名乐曲或等量独立作品。')
 m=re.fullmatch(r'Manuscrits\. Paris\. Bibliothèque nationale de France\. Rés\. Vmc\. ms\. (\d+)',text)
 if m:return (f'巴黎法国国家图书馆手稿（Rés. Vmc. ms. {m[1]}）','reference','exact_archival_locator_label','该字段为藏馆及手稿号，不是作品题名；ms. 是手稿缩写，不能译为疾病名称。')
 # A Boije joined record names its serial explicitly, with issue data. This
 # review translates the serial-level heading and leaves its entire contents
 # and all Se: references searchable in the original transcription.
 if r['source_id']=='boije' and ' | ' in text:
  serials=[
   (r'(?:^|\|\s*)Gitarristische Vereinigung\s+([IVXLCDM]+)\.\s*Jahrg\.\s*Nr\.?\s*([\d-]+)\.\s*(\d{4})(?=\s*\||\s*$)','〈吉他协会〉'),
   (r'(?:^|\|\s*)Freie Vereinigung\s*\.\.\.\s*(\[?\d+\.\s*Jahrg\.\]?)\s*Nr\.?\s*([\d-]+)\.\s*(\d{4})(?=\s*\||\s*$)','〈自由协会〉'),
   (r'(?:^|\|\s*)Der Guitarrefreund Musikbeilage(?:\.{3}|\s+zu Jahrg\.)\s*([\d./\s-]+)\.?\s*(?:Nr\.?|N\.|H\.)\s*(\d+)(?=\s*\||\s*$)','〈吉他之友〉音乐增刊'),
  ]
  for pat,name in serials:
   m=re.search(pat,text,re.I)
   if m:
    if len(m.groups())==3:z=f'{name}：{m[3]}年，第{m[1]}卷第{m[2]}期'
    else:z=f'{name}：{m[1].strip()}，第{m[2]}期'
    return(z,'reference','exact_serial_collection_heading','该原题以竖线合并多项曲目和 Se: 交叉索引；仅翻译其中明确的期刊集合标题，完整曲目、原编号和文献互见仍保留于原始转录，不将多个标题合成一个作品名。')
  if '| NOTBOK |' in text:
   return('乐谱册（附曲目目录）','reference','explicit_notbok_collection_heading','NOTBOK 为来源明确的乐谱册标题；其余为多项曲目及瑞典语 Se: 页码互见，完整原始目录保留，不据其推出单一作品身份。')
 # Complete numbered statements about a source book, without guessing an opus.
 m=re.fullmatch(r'(Op\.\s*\d+\.?\s*)?Collection des oeuvres\s*\.{3}',text,re.I)
 if m:return((grammar(m[1]).rstrip('：')+'：' if m[1] else '')+'作品集…','reference','complete_collection_book_title','Collection des œuvres 是作品集；原文尾端省略号照录，不补写未提供的内容。')
 m=re.fullmatch(r'(?:ALBUM|BIBLIOTHEK) för Guitarr-Spelare\.\s*(Valda sånger\s*)?\.\.\.\s*H\.\s*(\d+)\.',text,re.I)
 if m:return(f'吉他演奏者'+('精选歌曲集' if m[1] else '曲库')+f'，第{m[2]}册…','reference','complete_swedish_book_heading','瑞典语 för 为为，Spelare 为演奏者；H. 为册号；Valda sånger 是精选歌曲，省略处不补文。')
 m=re.fullmatch(r'Samling af kompositioner\s*\.\.\.\s*H\.\s*(\d+)\.',text,re.I)
 if m:return(f'作品集，第{m[1]}册…','reference','complete_swedish_collection_heading','Samling af kompositioner 为作品集；册号和原省略号保留。')
 m=re.fullmatch(r'(?:NOTBOK|\[NOTBOK\]|NOT-BOK)',text,re.I)
 if m:return('乐谱册','reference','exact_swedish_notbok','瑞典语书目标题 Notbok 意为乐谱册，不是自动识别失败的否定词。')
 # A complete simple phrase around an exact theme title may preserve the theme
 # literally. This is a reference translation of the whole construction,
 # never an asserted conventional Chinese name for that theme.
 m=re.fullmatch(r'(Op\.\s*\d+\.?\s*)?(?:Grande?\s+)?Fantai?s[iy]e?\s+(?:sur|über)\s+(?:des\s+motifs\s+(?:de\s+)?(?:l[’\']opéra\s+)?|(?:les\s+)?motifs\s+de\s+|(?:un\s+)?(?:motif|thème)\s+(?:favori\s+)?de\s+)(.+)',text,re.I)
 if m:
  title=m[2].strip(' .…')
  if ' | ' not in title and len(title)<130:
   op=grammar(m[1]).rstrip('：')+'：' if m[1] else ''
   return(op+f'〈{title}〉主题'+('大型' if re.search(r'\bGrande?\b',text) else '')+'幻想曲','reference','complete_literal_theme_fantasy_structure','完整句法表明后段为引用主题名；主题专名保持来源拼写，音乐体裁 Fantaisie 译为幻想曲，不把主题所属角色或同名作品身份补入。')
 m=re.fullmatch(r'(Op\.\s*\d+\.?\s*)?(?:Grandes?\s+)?Variations?\s+(?:sur|über)\s+(?:un\s+air\s+|(?:un\s+)?th[èeê]me\s+)?(.+)',text,re.I)
 if m:
  title=m[2].strip(' .…')
  if ' | ' not in title and len(title)<130:
   op=grammar(m[1]).rstrip('：')+'：' if m[1] else ''
   return(op+f'〈{title}〉主题变奏曲','reference','complete_literal_variation_structure','完整句法给出变奏所用主题，引用题名保留来源原拼写；不把 varié 误译为各种，不推断缺失的歌剧或歌手身份。')
 m=re.fullmatch(r'(?:Six|\d+) Airs from (.+)',text,re.I)
 if m:
  number=text.split()[0];number='六' if number.casefold()=='six' else number
  return(f'选自 {m[1]} 的{number}首曲调','reference','complete_selected_air_source_structure','Airs 指曲调，from 后的作曲家和歌剧题名照录；句法对应是选曲，不据它合并到另一来源同名作品。')
 m=re.fullmatch(r'(.+?)\s*\((Grand valse|Valse|Schottisch|Schottische|Schottische|Polka) for Mandolin and Guitar\)',text,re.I)
 if m:return(f'{m[1]}（曼陀林与吉他'+({'grand valse':'大型圆舞曲','valse':'圆舞曲','schottisch':'肖蒂什舞曲','schottische':'肖蒂什舞曲','polka':'波尔卡'}[m[2].casefold()])+'）','reference','complete_named_dance_instrumentation','前段题名照录，括号完整说明体裁和乐器；Schottisch 是舞种，不是国籍或乐器名。')
 return None

def translate_row(r):
 z=structured(r)
 if z:return z
 for candidate,rule in primary_candidates(r):
  z=basic_translation(candidate)
  if z:
   if rule!='complete_display_title':
    for op in tq.OPUS.finditer(norm(r['display_original'])):
     token='作品'+op[1]
     if not re.search(r'(?<!\d)'+re.escape(token)+r'(?!\d)',z):
      uncertain='?' if norm(r['display_original'])[op.end():].startswith('?') else ''
      z+='，'+token+uncertain
   return(z,'reference','exact_semantic_title' if norm(candidate).casefold() in EXACT else 'complete_closed_archive_music_grammar',
          '核对实际题名的语义、完整体裁/乐器/调式/编号结构；仅给出参考译名，不声明所有条目均有权威通行中文名。'+('明确的书目责任或出版系列余文保留于原始转录。' if rule!='complete_display_title' else ''))
 return None
