"""Fully delimited musical citations: preserve specific unverified lyric names.

A source title may reliably state form and relation while its lyric incipit or
proper opera name still lacks a reliable Chinese reading. These decisions do
not elevate a token replacement or default all machine drafts to retained.
"""
import re
from archive_semantics import norm,grammar
from archive_structure_rules import primary_candidates,basic_translation

FORMS={'cavatina':'卡瓦蒂纳','cav.':'卡瓦蒂纳','cav':'卡瓦蒂纳','aria':'咏叹调','rom.':'浪漫曲','romanza':'浪漫曲','duetto':'二重唱','terzetto':'三重唱','quartetto':'四重唱','quintetto':'五重唱','scena ed aria':'场景与咏叹调','scena e duetto':'场景与二重唱','coro':'合唱','ballata':'歌谣','canzone':'歌曲','cabaletta finale':'终结卡巴莱塔','brindisi':'祝酒歌','sortita di riccardo':'Riccardo 出场曲'}

def citation_decision(r):
 t=norm(r['display_original'])
 if r['source_id']!='dga':return None
 # This alternate publisher syntax places the named opera first, then
 # vocal form and lyric incipit; its entire incipit is delimited by clef or
 # accompaniment/arrangement labels, never guessed from capital letters.
 m=re.fullmatch(r"(.+?),\s*Opera(?:\s+per\.?\s*Canto)?[,.]\s*(.+?)(?:\s*\(in\s*Ch(?:iave|[.])?\s*di\s*Sol[.)\s]*|\s*,?\s*(?:con\s+accomp|rid(?:otta|otto|[.])|per\s+Chitarra)).*",t,re.I)
 if m and len(m[1])<100 and len(m[2])<180:
  opera=m[1];incipit=m[2]
  return(t,'retained','explicit_opera_first_vocal_incipit_retained',f'完整书目先标歌剧「{opera}」，再给声乐选段引句「{incipit}」及谱号/伴奏/编配说明；这是历史歌词引名，不能将几个普通词逐个硬译为已定名的歌曲。原题全文和角色、谱号、编配信息完整照录，in Ch. di Sol 不当作G大调。')
 # Several song/lyric catalogs explicitly label lyrics and music separately.
 # Keep the distinctive whole title only when this exact genre/citation
 # context shows why a literal modern noun substitute would be unsafe.
 m=re.search(r'\b(?:nell[’\']?|nella|nel|nei)\s+(?:op[eé]ra\s+)?(.+?)(?=\s*,?\s*(?:rid\.?|ridotta|ridotto|trascrit|per\s+Chitarra|per\s+Flauto)|\s*;|$)',t,re.I)
 if m:
  opera=m[1].strip(' .,:;')
  prefix=t[:m.start()].strip(' .,:;')
  form=re.search(r'(?<!\w)('+('|'.join(re.escape(x) for x in sorted(FORMS,key=len,reverse=True)))+r')(?!\w)',prefix,re.I)
  if form and 1<len(opera)<120 and 1<len(prefix)<180:
   core=prefix[form.end():].strip(' .,;:') or prefix[:form.start()].strip(' .,;:')
   # Known complete headings still take their actual checked reading.
   known=basic_translation(core)
   if known and re.search(r'[\u3400-\u9fff]',known):
    return(f'{FORMS[form.group().casefold()]}〈{known}〉，选自歌剧〈{opera}〉','reference','fully_delimited_lyric_opera_reference','完整语法明示曲种与歌剧引用；能核对的引用词义给出参考译文，歌剧专名照录。改编责任、调号及出版说明完整保留原始转录；不凭歌剧题名推断本条作曲家身份。')
   return(t,'retained','exact_lyric_opera_citation_retained',f'完整原题将「{prefix}」作为{FORMS[form.group().casefold()]}引用，并标明选自「{opera}」；引句的历史歌词/专名尚无可靠中文对应，不能把其中普通词或同名歌剧译名拼接为正式曲名。该引文、曲种、原编号与改编说明完整照录。')
 # Explicitly quoted or apostrophe-inside musical incipits with lyric credits:
 # no inferred Chinese identity or simplistic fragmented noun translation.
 m=re.search(r'\b(?:PAROLES|Paroles|Po[ée]sie|parole)\s+(?:de|par|di)\b',t)
 if m:
  head=t[:m.start()].strip(' .,:;')
  if len(head)>3 and re.search(r'\b(?:ROMANCE|Romance|COUPLETS|CHANSON|Chanson|Chansonnette|CHANSONNETTE|BARCAROLLE|DUO)\b',head):
   result=basic_translation(head)
   if result:return(result,'reference','complete_song_heading_before_lyric_credit','完整主标题的音乐与词义可核对；Paroles/Poésie 后是作词等责任说明，完整保留原始转录，不把作词者当作作曲者。')
   return(t,'retained','exact_song_incipit_with_lyric_credit_retained',f'原题明确以「{head}」为歌曲/浪漫曲主标题，其后 Paroles/Poésie 为词作者责任句；主标题包含无法稳妥意译的历史歌词或专名。保留完整标题和作者原注，不依普通词义机械拼译，也不补写未提供的歌词。')
 return None
