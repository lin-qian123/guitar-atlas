"""Complete semantic decisions for the isolated 1,576-record DGA supplement.

Primary candidates are explicitly supplied source-responsibility boundaries.
Every decision guards the unchanged complete source title, attribution, and
display transcription. No source asset/export is modified.
"""
from __future__ import annotations
import collections, hashlib, importlib.util, json, re, sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE))
import build_cglib_review as cg
import archive_semantics as ar
import archive_exact_supplement as ax
import dga_10000_exact as manual

INPUT=ROOT/'work/title-review/2026-10-03/archive-review/dga-10000-12999.json'
EXTRA_INPUT=ROOT/'work/title-review/2026-10-03/archive-review/dga-10000-supplement/additional-56-input.json'
PHRASES=dict(cg.PHRASES)
PHRASES.update({cg.q.normphrase(k):v for k,v in ar.EXACT.items()})
PHRASES.update({cg.q.normphrase(k):v for k,v in ax.EXACT.items()})
MANUAL=HERE/'dga_10000_phrases.tsv'
if MANUAL.exists():
    for line in MANUAL.read_text().splitlines():
        if line and not line.startswith('#'):
            key,value=line.split('\t',1);PHRASES[cg.q.normphrase(key)]=value
TERMS=dict(cg.TERMS)
TERMS.update({'chant et guitare':'歌唱与吉他','romance à deux voix':'二声部浪漫曲',
             'alto recorder':'中音竖笛','fandango':'凡丹戈舞曲',
             'graded studies':'分级练习曲','guitar solos':'吉他独奏曲',
             'ch. di sol':'高音谱号','arranged with variations':'改编并加变奏',
             'romantic virtuoso guitar music':'浪漫派吉他炫技音乐'})
TERMS.update({'chansonnette':'小歌曲','chansonette':'小歌曲','chansonnettes':'小歌曲',
              'mélodie à deux voix':'二声部旋律曲','romance à une ou deux voix':'独唱或二声部浪漫曲',
              'nocturne à deux voix égales':'同声二部夜曲','nocturne à deux voix':'二声部夜曲',
              'nocturne a 2 voix':'二声部夜曲','barcarolle à deux voix':'二声部船歌',
              'chanson bachique':'饮酒歌','chanson de table':'席间歌曲','fabliau':'故事诗',
              'causerie':'闲谈','narration':'叙述','mélodie':'旋律曲','conte':'故事',
              'romance pastorale':'田园浪漫曲','romance historique':'历史浪漫曲',
              'romance dramatique':'戏剧性浪漫曲','chanson créole':'克里奥尔歌曲',
              'opéra comique':'喜歌剧','opéra historique':'历史歌剧','drame lyrique':'抒情剧',
              'à une ou deux voix':'独唱或二声部','à deux voix':'二声部','a deux voix':'二声部',
              'à 2 voix':'二声部','a 2 voix':'二声部','à trois notes':'三个音',
              'ronde à danser':'圆圈舞曲','ronde villageoise':'乡村圆舞歌',
              'rondoletto':'小回旋曲','duettino':'小二重唱'})
TERMS.update({'couplets':'分节歌曲','couplet':'分节歌曲','stances':'诗节歌曲',
              'chanson':'歌曲','canzonetta':'小歌曲','cavatina':'卡瓦蒂娜','cavatine':'卡瓦蒂娜',
              'boléro':'波莱罗舞曲','bolero':'波莱罗舞曲','tyrolienne':'蒂罗尔歌曲',
              'virelai':'维勒莱歌曲','ariette italienne':'意大利小咏叹调',
              'pastorale':'牧歌','barcarole':'船歌','récit':'叙事','scène':'场景',
              'chant guerrier':'战歌','chant militaire':'军歌','chanson militaire':'军歌',
              'romance héroïque':'英雄浪漫曲','chant dramatique':'戏剧歌曲',
              'tyrolienne à une ou deux voix':'独唱或二声部蒂罗尔歌曲',
              'chansonnette à deux voix':'二声部小歌曲','chanson à deux voix':'二声部歌曲',
              'nocturnes à deux voix':'二声部夜曲','opéra comique en deux actes':'二幕喜歌剧',
              'opéra comique en trois actes':'三幕喜歌剧','opéra comique en 3 actes':'三幕喜歌剧',
              'opéra en trois actes':'三幕歌剧','opéra en un acte':'独幕歌剧',
              'nouvel opéra comique en 3 actes':'新三幕喜歌剧'})
FROZEN=HERE/'dga_10000_frozen_lexicon.json'
if FROZEN.exists():
    frozen=json.loads(FROZEN.read_text());PHRASES=frozen['phrases'];TERMS=frozen['terms']
TERM_FOLDED={cg.q.normphrase(k):v for k,v in TERMS.items()}
PATTERN=re.compile(r'(?<!\w)(?:'+'|'.join(re.escape(k) for k in sorted(PHRASES,key=len,reverse=True))+r')(?!\w)',re.I)

def phrases_for(body):
    folded=cg.q.source_key(body).replace('’',"'").replace('_',' ')
    if len(folded)!=len(body):
        return {body:PHRASES[cg.q.normphrase(body)]} if cg.q.normphrase(body) in PHRASES else {}
    return {body[m.start():m.end()]:PHRASES[m[0].casefold()] for m in PATTERN.finditer(folded)}

def semantic(body):
    body=re.sub(r'\s+',' ',body).strip(' .;')
    direct=PHRASES.get(cg.q.normphrase(body))
    if direct:return direct,'exact_full_title_semantic'
    direct=TERM_FOLDED.get(cg.q.normphrase(body))
    if direct:return direct,'complete_music_and_phrase_template'
    # These are explicitly labelled source responsibilities or dedications,
    # not title words. Preserve every omitted byte in the guarded source field.
    role=re.search(r'\b(?:chant[ée]e?s?\s+par|paroles?\s+(?:de|et)|po[ée]sie\s+et\s+musique|mis(?:e|es)?\s+en\s+musique|compos[ée]e?s?\s+par|d[ée]di[ée]e?s?\s+[àa]|(?:romance|chansonnette)\s+de\s+(?:M(?:r|me|lle|s)?\b))',body,re.I)
    if role:
        head=body[:role.start()].strip(' ,.;')
        # Genre de Mr is responsibility metadata; keep the genre itself.
        if re.match(r'(?:romance|chansonnette)\s+de',role[0],re.I):
            head+=' '+role[0].split()[0]
        if head and head!=body:
            value,method=semantic(head)
            if value:return value,method+'_source_role_boundary'
    # Normalize source orthography only inside an explicit voice declaration.
    body=re.sub(r'\b([àa])\s+1\s*[.]?\s*ou\s*2\s*[.]?\s*voix\b',r'\1 une ou deux voix',body,flags=re.I)
    body=re.sub(r'\bvois(?=[ .]*$)','voix',body,flags=re.I)
    # A complete series number is separate from its musical title.
    n=re.match(r'^(?:No[.]?|N[º°])\s*(\d+)[. ]+(.+)$',body,re.I)
    if n:
        value,method=semantic(n[2])
        if value:return '第'+n[1]+'号：'+value,method+'_series_number'
    # In Italian score bibliography Opera/Opa + a complete number is an opus,
    # distinct from a following named opera; source text remains unchanged.
    body=re.sub(r'(?<!\w)(?:opera|opa)\s*[.:]?\s*(\d+|[IVXLCDM]+)(?!\w)',r'Op.\1',body,flags=re.I)
    value=cg.q.semantic_title(body,phrases=phrases_for(body),terms=TERMS)
    # Explicitly named author/publisher in a complete instructional heading:
    # retain the Latin name, without a Chinese identity/role inference.
    frames=[
      (r"(.{2,55}?)['’]s (new and complete |comprehensive |celebrated |complete |new |easy )?(?:guitar preceptor|guitar method|guitar tutor|guitar instructions|instructions for the guitar)",lambda m:m[1]+' '+{'new and complete ':'新编完整','comprehensive ':'综合','celebrated ':'著名','complete ':'完整','new ':'新','easy ':'简易','':' '}.get((m[2] or '').casefold(),'')+'吉他教程'),
      (r'(.{2,55}?) for (?:the |classical |classic )?guitar',lambda m:m[1]+'（为'+('古典' if re.search(r'classic',m[0],re.I) else '')+'吉他而作）'),
      (r'The (?:guitar )?works of (.{2,65})',lambda m:m[1]+' 的'+('吉他' if re.search(r'guitar',m[0],re.I) else '')+'作品集'),
      (r'(?:A |The )?complete (?:method|instructions) for (?:the )?(?:Spanish )?guitar',lambda m:'完整西班牙吉他教程' if 'spanish' in m[0].casefold() else '完整吉他教程'),
    ]
    for pattern,fn in frames:
        m=re.fullmatch(pattern,body,re.I)
        if m and not re.search(r'\b(?:sur|from|themes?|arranged|with|and|et|vol|book|no)\b',m[1] if m.lastindex else '',re.I):
            return fn(m),'complete_named_book_heading'
    # A single exact named theme inside an unambiguous full musical relation.
    patterns=[
      (r'(?:Grande? )?fantai?s[iy]e\s+(?:sur|on)\s+(?:les? )?(?:motifs?|th[èeê]mes?)\s+(?:de |from )?(?:l[’\x27]op[eé]ra\s+)?(.+)', '主题幻想曲'),
      (r'(?:Grandes? )?variations?\s+(?:sur|on)\s+(?:un |une |le |the )?(?:air|th[èeê]me)?\s*(?:de |from )?(?:l[’\x27]op[eé]ra\s+)?(.+)', '主题变奏曲'),
      (r'Th[èeê]mes?\s+de\s+(.+)', '主题'),
      (r'(?:Valse et galops?|valses? et galops?)\s+sur des motifs de\s+(.+)', '主题圆舞曲与加洛普舞曲'),
    ]
    for pattern,genre in patterns:
        m=re.fullmatch(pattern,body,re.I)
        if m and len(m[1])<70 and not re.search(r'\b(?:par|by|pour|for|d[eé]di[eé]|compos|prix|pp)\b',m[1],re.I):
            label=PHRASES.get(cg.q.normphrase(m[1]),m[1]);return '〈'+label+'〉'+genre,'complete_quoted_theme_structure'
    # A source title label immediately followed by one explicitly named genre
    # is preserved as a whole; the genre/voice declaration itself is complete.
    genre=r'(?:romance héroïque|romance historique|romance pastorale|chant guerrier|chant militaire|chanson militaire|chant dramatique|nouvel opéra comique|opéra comique|opéra|romance|chansonnette|chansonette|chanson|mélodie|melodie|ballade|ballad|serenade|sérénade|nocturnes?|barcarolle|barcarole|boléro|bolero|tyrolienne|valse|polka|canzonetta|cavatina|cavatine|gavotte|narration|conte|couplets|stances|trio|rondo)'
    m=re.fullmatch(r'(.{2,75}?)[ .,:;!—-]+('+genre+r'(?:\s+(?:à|a|en)\s+(?:une ou deux voix|deux voix égales|deux voix|2 voix|trois actes|deux actes|un acte|[235] actes))?)[ .;,]*',body,re.I)
    if m:
        label=m[1].strip(' ,.;');frame=m[2]
        if not re.search(r'\b(?:par|by|from|chant[eé]|compos|d[eé]di[eé]|prix|pp|romance|nocturne)\b',label,re.I):
            z=TERM_FOLDED.get(cg.q.normphrase(frame)) or cg.q.semantic_title(frame,terms=TERMS)
            if z:
                return PHRASES.get(cg.q.normphrase(label),label)+'——'+z,'complete_named_title_genre_structure'
    m=re.fullmatch(r'(?:Air|Romance|Duo|Duetto|Duettino|Trio|Cavatine|Cavatina|Ouverture|Rondo|Rondeau|Polonaise|Couplet|Couplets|Stances|Vaudeville)\s+(?:de |du |des |d[’\x27])(.{2,70})',body,re.I)
    if m and not re.search(r'\b(?:par|chant[eé]|compos|prix|pp)\b',m[1],re.I):
        genre=cg.q.semantic_title(body.split()[0],terms=TERMS)
        if genre:return '〈'+PHRASES.get(cg.q.normphrase(m[1]),m[1])+'〉中的'+genre,'complete_quoted_source_genre_structure'
    if value:return value,'complete_music_and_phrase_template'
    return None,None

def decision(row):
    native=int(row['id'].split(':',1)[1])
    if native in manual.RETAIN:
        return {'id':row['id'],'original':row['original'],'original_composer':row['composer'],'display_original':row['display_original'],'display_zh':'','zh':cg.wrap(row['original']),'status':'retained','basis':'dga_10000_individual_primary_heading_review_2026_10_03','reason':manual.RETAIN[native],'source_refs':manual.REFS.get(native,[]),'reviewer':'codex_cglib_dga_supplement','review_method':'exact_specific_semantic_retention'}
    if int(row['id'].split(':',1)[1]) in manual.EXACT:
        value=manual.EXACT[int(row['id'].split(':',1)[1])]
        return {'id':row['id'],'original':row['original'],'original_composer':row['composer'],'display_original':row['display_original'],'display_zh':cg.wrap(value),'zh':cg.wrap(value),'status':'reference','basis':'dga_10000_individual_primary_heading_review_2026_10_03','reason':'逐条读取完整原题，按明确主标题、体裁、数量、书目描述与分谱关系作合理参考意译；源题明确的编辑、献辞、歌词开头与出版尾部保留于完整原文。不是通行中文定名，不改变署名、版本或作品身份。','source_refs':manual.REFS.get(native,[]),'reviewer':'codex_cglib_dga_supplement','review_method':'exact_bibliographic_primary_semantic'}
    candidates=[]
    for body,rule in row['primary_candidates']:
        if body not in [x[0] for x in candidates]:candidates.append((body,rule))
    for body,rule in candidates:
        value,method=semantic(body)
        if value:
            value=value.rstrip(' ,.;')
            # Vocal casting is established by the explicit source 'Chanté'
            # following the same genre, not by this website's directory.
            raw=row['original'].replace('/',' ')
            for term,old,new in [('duo','二重奏','二重唱'),('duetto','二重奏','二重唱'),('trio','三重奏','三重唱'),('quatuor','四重奏','四重唱')]:
                if re.search(r'\b'+term+r'\s+chant[ée]',raw,re.I):value=value.replace(old,new)
            reason='完整主标题按整句语义或完整音乐结构复核；参考意译不声称通行中文定名。'
            if rule!='complete_display_title':reason+=' 原题明确的书目署名/编辑/献辞尾部与主标题分开，完整源转录、原文署名及版次信息仍保留；不以引用名或编改名推定作曲者。'
            if method=='complete_quoted_theme_structure':reason+=' 引用主题题名如无法可靠释义便完整原文照录，不将相似题名当作作品身份。'
            if 'named_title_genre' in method or 'quoted_source_genre' in method:
                reason+=' 无法确定可靠中文释义的原题标签在中文体裁旁完整照录，未擅自猜测人名或剧名。'
            return {'id':row['id'],'original':row['original'],'original_composer':row['composer'],'display_original':row['display_original'],'display_zh':cg.wrap(value),'zh':cg.wrap(value),'status':'reference','basis':'dga_10000_complete_semantic_review_2026_10_03','reason':reason,'source_refs':[],'reviewer':'codex_cglib_dga_supplement','review_method':method,'primary_candidate':body,'primary_boundary':rule}
    shortest=min(candidates,key=lambda x:len(x[0]))[0] if candidates else row['display_original']
    reason,method=cg.retain_reason(shortest)
    return {'id':row['id'],'original':row['original'],'original_composer':row['composer'],'display_original':row['display_original'],'display_zh':'','zh':cg.wrap(row['original']),'status':'retained','basis':'dga_10000_complete_semantic_review_2026_10_03','reason':reason+' 完整档案转录保留于原文，已有自动草稿不作为正式中文题名。','source_refs':[],'reviewer':'codex_cglib_dga_supplement','review_method':method}

def main():
    if hashlib.sha256(INPUT.read_bytes()).hexdigest()!='b0cf5ce47a1dea08dd9c67427ec00adc26bb6f0c961a3f7d6a97772c351b0b79':
        raise ValueError('DGA frozen corpus changed; individual decisions require fresh source-title review')
    if hashlib.sha256(EXTRA_INPUT.read_bytes()).hexdigest()!='ab92472f6bd9c5bd06bb76e36e89a009520dc2c461610f0b509d29c1fcee3dbf':
        raise ValueError('DGA55 extra corpus changed; individual decisions require fresh source-title review')
    corpus=json.loads(INPUT.read_text());extra=json.loads(EXTRA_INPUT.read_text());corpus+=extra
    if len(corpus)!=1632 or len({x['id'] for x in corpus})!=1632:raise ValueError('DGA supplement corpus identities changed')
    entries=[decision(x) for x in corpus]
    output=HERE/'dga_10000_supplement.json';output.write_text(json.dumps({'schema_version':1,'entries':entries},ensure_ascii=False,indent=2)+'\n')
    private=ROOT/'work/title-review/2026-10-03/archive-review/dga-10000-supplement';private.mkdir(exist_ok=True)
    report={'records':len(entries),'base_records':1576,'additional_boundary_review_records':55,'additional_course_edition_records':1,'statuses':dict(collections.Counter(x['status'] for x in entries)),'methods':dict(collections.Counter(x['review_method'] for x in entries)),'input_sha256':hashlib.sha256(INPUT.read_bytes()).hexdigest(),'extra_input_sha256':hashlib.sha256(EXTRA_INPUT.read_bytes()).hexdigest(),'decision_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'scope':'1576 frozen DGA primary-heading candidates plus55 newly unresolved surname-boundary variants and one course-edition record; original transcription and attribution guarded; no source asset/export mutation.'}
    (private/'coverage.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    (private/'full-ledger.json').write_text(json.dumps([dict(x,before=r) for r,x in zip(corpus,entries)],ensure_ascii=False,indent=2)+'\n')
    (private/'retained.tsv').write_text('\n'.join('\t'.join([x['id'],x['original_composer'],r['display_original'],x['reason']]) for r,x in zip(corpus,entries) if x['status']=='retained')+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
