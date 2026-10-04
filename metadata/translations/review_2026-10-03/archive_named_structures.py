"""Checked archival book/anthology headings and explicit musical citations."""
import re
from archive_semantics import norm,grammar,tq
from archive_structure_rules import primary_candidates

def opus_suffix(text):
 seen=[]
 for m in re.finditer(r'(?<!\w)(?:op(?:us)?|oeuv(?:re)?|œuv(?:re)?|opera|opa|oeuvr)\s*[.:：]?\s*(\d+(?:[/-]\d+)*(?:[a-z])?|[IVXLCDM]+)(?!\w)',text,re.I):
  value=m[1]
  if value.isalpha() and (value!=value.upper() or not re.fullmatch(r'M{0,4}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})',value)):continue
  z='作品'+value;z+='?' if text[m.end():].startswith('?') else ''
  if z not in seen:seen.append(z)
 for m in re.finditer(r'(?<!\w)(\d+)(?:tes|ter|te)\s*Werk\b',text,re.I):
  z='作品'+m[1]
  if z not in seen:seen.append(z)
 return ('，'+'、'.join(seen)) if seen else ''

def named_structure(r):
 if r['source_id']!='dga':return None
 t=norm(r['display_original']);op=opus_suffix(t)
 # Explicit series head with a content description: neither flower's botanical
 # identity nor the missing tails are asserted by its Chinese display.
 m=re.match(r'^(Cyanen|Nachtviolen)\s*[:.]?\s*(.*)$',t,re.I)
 if m and ('melodisch' in m[2].casefold() or 'folge der' in m[2].casefold()):
  head=m[1]+('（〈Nachtviolen〉续集）' if 'folge der nachtviolen' in m[2].casefold() else '')+op
  return(head,'reference','complete_named_series_and_contents_description','原题明确区分 Cyanen/Nachtviolen 命名系列与其原创旋律乐曲说明；系列专名照录，明确作品号保留，花名的植物学中文身份不臆定。内容说明、作者及责任原句仍保留在完整原始转录。')
 if re.match(r'^Vaterlands-Bl[üu]then\b',t,re.I) and 'ungarische' in t.casefold():
  return('祖国之花：原创匈牙利风格吉他曲'+op,'reference','complete_original_hungarian_series_heading','完整句法表明是命名系列及原创匈牙利风格作品说明；出处、献辞、责任余文保留完整转录，不从系列名推断国籍或编制。')
 # Sinfonia has a documented opera-overture sense; this guard consumes the
 # explicitly supplied opera name, leaving it literally quoted.
 m=re.match(r'^Sinfonia\s+(?:(?:nell[’\']|dell[’\']|nella\b|della\b|nel\b)\s*(?:opera\s*)?)(.+?)(?=\s*,?\s*rid(?:ott[aeio]|\.)?\b|\s+del\s+(?:Mo\.|celebre|Sigr\.|Sig\.|Maestro)|\s+di\s+Rossini|\s+per\s+Chitarra|\s*/|$)',t,re.I)
 if m:
  title=m[1].strip(' .;,')
  return(f'歌剧〈{title}〉序曲'+op,'reference','explicit_italian_opera_sinfonia_overture','该句明确给出歌剧所属或歌剧题名。Sinfonia 在歌剧语境中为序曲；原歌剧名、原作品号和编配责任均照录，不误当作独立交响曲。')
 m=re.fullmatch(r"(.+?),\s*Opera[.]\s*Sinfonia\s+rid[.]\s+per\s+Chitarra\s+(?:da|di)\s+(.+)",t,re.I)
 if m:
  return(f'歌剧〈{m[1]}〉序曲的吉他改编','reference','explicit_opera_first_sinfonia_overture','完整句法明确先给歌剧题名，再给序曲的吉他改编与改编者责任句；歌剧未知专名保持完整拼写，Sinfonia 以明示歌剧语境译为序曲，原责任与余文保留完整转录。')
 if re.fullmatch(r'Sinfonia\s+per\s+Chitarra\s+francese\.?',t,re.I):
  return(t,'retained','sinfonia_dual_meaning_without_work_context','Sinfonia 可指歌剧序曲，也可指独立交响曲；原題只说法式吉他，没有歌剧出处或可辨认作品的资料，完整保留，不能仅凭音乐术语表选定其中一个中文曲种。')
 # Explicit anthology labels and issue/book number, rather than an invented
 # independent title for each named/numbered contents entry.
 m=re.match(r'^(L[’\']Aurore ou Journal de Guitare),\s*Choix des plus beaux morceaux,\s*composés pour cet instrument\.\s*No\.\s*(\d+)',t,re.I)
 if m:return(f'曙光，或吉他期刊：吉他乐曲精选，第{m[2]}号'+op,'reference','complete_periodical_main_heading','原题明确命名期刊/精选乐谱册，后面的 Contenant 是附曲目目录。主标题、期号与明确作品号给中文对应；完整曲目数量、原引句及作者列表保留原始转录。')
 m=re.match(r'^Scelta delle Danze più favor(?:i|l)te per Chitarra\s*[:.]?\s*Fasc\.\s*(\d+)\.°?',t,re.I)
 if m:return('吉他热门舞曲精选，第'+m[1]+'分册'+op,'reference','complete_italian_dance_anthology_heading','Scelta delle Danze 明确是舞曲精选，Fasc. 是分册；后文为分册内独立曲名目录，全部原题与曲目数保留于原始转录，不把多首目录当作同一曲的副标题。')
 m=re.match(r'^(Il Chitarrista moderno)[,. :]\s*Pezzi fav(?:oriti|\.)\.?\s*d[’\']\s*Opere teatrali',t,re.I)
 if m:
  n=re.search(r':\s*N\.\s*(\d+)',t,re.I)
  return('现代吉他演奏者：歌剧精选改编曲'+('，第'+n[1]+'号' if n else '')+op,'reference','complete_modern_guitarist_operatic_anthology_heading','主标题 Il Chitarrista moderno 与精选歌剧改编说明明确；编号保留。后面的咏叹调/合唱/舞曲原名、歌词引句、作者与角色信息完整保留在原始目录，不据系列标签指定本条作曲者。')
 # These are generic pedagogical book titles. The full subtitle explains
 # teaching process, examples, exercises and printing; no work-level identity
 # is synthesized from the short display label.
 method_patterns=[r'M[ée]thode\s+(?:compl[èeé]te\s+)?(?:pour|ou [ée]tudes pour)\s+(?:la\s+)?guitare\b',r'Metodo\s+(?:completo\s+)?(?:per Chitarra|per imparare a conoscere la musica e suonare la [Cc]hitarra)\b',r'(?:Vollständige Anweisung|Neue theoretisch-practische Guitare-Schule|Gemeinnützige Guitareschule|Guitar School)\b',r'(?:Elementi di musica e Princip(?:ii|i) di Chitarra|Primi elementi per la chitarra)\b']
 if any(re.match(p,t,re.I) for p in method_patterns) and re.search(r'guit|chitar',t,re.I):
  full=('完整' if re.search(r'compl[èeé]te|completo|vollständig',t,re.I) else '')
  return(full+'吉他教程'+op,'reference','complete_pedagogical_book_main_heading','核对完整原题后确认主标题为吉他教程/基础法则，余文是教学方法、例题、练习、内容目录或责任出版说明。中文显示给明确的书名主干与作品号；所有原副标题、册次、语种、例题数量及责任全文继续保留原始转录，并不声明这一简题是唯一通行出版名。')
 # These full families were read as musical books/periodical anthologies,
 # not as a set of novel identities inferred from their word similarity.
 anthology_patterns=[
  (r"^Le Delizie dell'Italia, select Italian Melodies from the operas of",'意大利的欢乐：意大利歌剧旋律精选（吉他与钢琴）'),
  (r"^Récréations Musicales, Rondeaux, Variations et Fantasies pour la Guitare sur 24 Thêmes Choisis",'音乐消遣：24首精选主题的吉他回旋曲、变奏曲与幻想曲'),
  (r"^Choix de Douze Ouvertures de la Composition de Rossini, arrangées pour Guitare & Piano",'Rossini 十二首序曲精选（吉他与钢琴改编）'),
  (r"^Douze Ouvertures des plus Célèbres Compositions, arrangées pour Guitare & Violon\. Première Livraison",'著名作品十二首序曲（吉他与小提琴改编），第一分册'),
  (r"^Periodical Amusements for the (?:Spanish )?Guitar\.",'吉他消遣定期曲集'),
  (r"^The Harmonic Union\. No\.",'和谐联合'),
  (r"^Opern-Revue[.:]\s*Ausgewählte Melodien für die Guitar",'歌剧荟萃：吉他旋律精选'),
  (r"^Potpourris für eine Guitarre über beliebte Opern Melodieen",'吉他热门歌剧旋律集成曲'),
  (r"^Beliebte Walzer und Galopen für die Guitarre eingerichtet\.",'热门圆舞曲与加洛普舞曲（吉他改编）'),
  (r"^Le Troubadour Ambulant\s*:\s*Journal de Guitar",'巡回吟游诗人：吉他期刊'),
  (r"^Journal de Pièces de Musique pour la Guitare Tirées de divers Auteurs Espagnols & autres",'吉他乐曲期刊：西班牙等作曲家的选曲'),
 ]
 for pat,label in anthology_patterns:
  m=re.match(pat,t,re.I)
  if m:
   numbers=[]
   for num in tq.SERIAL.finditer(t):
    z='第'+num[1]+'号'
    if z not in numbers:numbers.append(z)
   quotes=re.findall(r'"([^"\n]+)"',t[m.end():])
   titles='；'.join('〈'+x+'〉' for x in quotes)
   out=label+('，'+'、'.join(numbers) if numbers else '')+op+(('：'+titles) if titles else '')
   return(out,'reference','complete_read_anthology_main_heading_and_literal_contents','逐组核对完整同构书目，明确为命名作品集/期刊、选曲说明与原编号。中文保留原曲集主标题、编号、作品号及明确引用曲名；其余独立目录、歌词引句、作者、声部、献辞和印刷说明完整保留原始转录，不臆造被省略的目录项目或合并为单一作品。')
 # Whole formal potpourri sentence with a supplied named theme. Instrument
 # list is separately consumed by the checked grammar; theme is not relabeled.
 m=re.fullmatch(r'((?:Primo |Secondo |Due |\d+ )?Pot[- ]?pourri?s?\s*(?:per|pour)\s+(.+?))\s+(?:sur(?: des thèmes favoris de l[’\']opéra)?|sulla|sul|sull[’\']|sui)\s+(.+?)(?:\s*:\s*N\.\s*(\d+))?\s*\.?',t,re.I)
 if m:
  head=grammar(m[1]);theme=m[3].strip(' .')
  if head and len(theme)<140 and not re.search(r'\b(?:paroles|rid|trascri|par |compos)\b',theme,re.I):
   return(f'{head}（〈{theme}〉主题）'+(f'，第{m[4]}号' if m[4] else '')+op,'reference','complete_named_potpourri_instrument_theme_sentence','完整句法分别说明乐器/体裁和主题引用，音乐主干完整消费；主题原名照录，不能按普通名词翻译歌剧人物，也不从引用作曲者替换来源署名。')
 return None
