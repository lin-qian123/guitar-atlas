"""Reproducible CGLIB partition review; writes decisions, never source assets.

No translation API is called. Every accepted full phrase has a semantic entry
in the curated phrase table; grammar accepts only complete musical clauses.
Unknown text remains in a specifically described original-name slot or the
entire exact original is retained. This is reference naming, not title identity.
"""
from __future__ import annotations
import ast, collections, hashlib, importlib.util, json, re, unicodedata
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
FROZEN_PATH=HERE/'cglib_frozen_lexicon.json'
FROZEN=json.loads(FROZEN_PATH.read_text()) if FROZEN_PATH.exists() else None
spec=importlib.util.spec_from_file_location('cglib_semantic_rules',HERE/'cglib_semantic_rules.py')
q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)

def read_phrases():
    if FROZEN:return dict(FROZEN['phrases'])
    out={}
    for line in (HERE/'cglib_title_phrases.tsv').read_text().splitlines():
        if not line or line.startswith('#'):continue
        key,value=line.split('\t',1)
        out[q.normphrase(key)]=value
    shared=HERE/'root_semantic_phrases.json'
    if shared.exists():
        for key,value in json.loads(shared.read_text()).items():
            if 'julia florida' in q.normphrase(key):continue
            out.setdefault(q.normphrase(key),value)
    return out

def read_terms():
    if FROZEN:return dict(FROZEN['terms'])
    tree=ast.parse((ROOT/'scripts/review_source_translations.py').read_text())
    for item in tree.body:
        if isinstance(item,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='TERMS' for t in item.targets):
            return ast.literal_eval(item.value)
    raise AssertionError('TERMS missing')

PHRASES=read_phrases();TERMS=read_terms()
legacy_terms=HERE/'legacy_music_vocabulary.json'
if legacy_terms.exists() and not FROZEN:
    for key,value in json.loads(legacy_terms.read_text()).get('terms',{}).items():TERMS.setdefault(key,value)
PHRASE_PATTERN=re.compile(r'(?<!\w)(?:'+'|'.join(re.escape(k) for k in sorted(PHRASES,key=len,reverse=True))+r')(?!\w)',re.I)
# Supplied publisher/source citation transcriptions are not attribution claims.
AUTHOR_BRACKET=re.compile(r'\(([^()]+,[^()]+)\)')
PRIOR_EXACT=FROZEN['prior_exact'] if FROZEN else json.loads((ROOT/'metadata/translations/source_title_quality_review_zh.json').read_text())['entries']
SOURCE_SURNAMES={'Bach','Beethoven','Bellini','Berlioz','Bizet','Boieldieu','Chopin','Donizetti','Grieg','Haendel','Handel','Haydn','Herold','Hérold','Mendelssohn','Mendelssohn','Mendelsshon','Meyerbeer','Mozart','Rossini','Schubert','Schumann','Strauss','Tchaikovsky','Valverde','Verdi','Wagner','Weber','Waldteufel'}

def nameset(text):
    return sorted(re.findall(r'[a-z]+',q.source_key(text)))

def body_of(row):
    body=row['display_original'];notes=[]
    body=re.sub(r'(?<=\d)by(?=\s)',' by',body,flags=re.I)
    m=re.search(r'\s+by\s+([^\n]+)$',body,re.I)
    if m:
        tail=m[1]
        # A mid-title "by" followed by a book/arrangement clause is not an
        # author-only suffix. Keep the full title for separate semantic review.
        if len(tail.split())>8 or re.search(r'\b(?:op|opus|no|nr|grades|arranged|accompaniment|duets|for|pour|para|per|teacher)\b',tail,re.I):
            return body,notes
        part=re.search(r'\s+(Guitare?\s*[1-9]|Guitar\s*[1-9])$',tail,re.I)
        if part:tail=tail[:part.start()]
        marker=None
        if not part:
            marker=re.search(r'\s+(\(?\d+\)?)$',tail)
            if marker:tail=tail[:marker.start()]
        notes.append('原题 by 引用“'+tail+'”作为明确的来源署名保留在完整原题，不把它推定为作曲者或改写独立署名字段。')
        body=body[:m.start()]+(' '+part[1] if part else '')+(' ('+marker[1].strip('()')+')' if marker else '')
    # Parentheses matching "surname, given name" are explicitly a source
    # bibliographic attribution. Preserve as Latin text in a typed note slot.
    return body,notes

def wrap(text):
    if text.startswith('《') and text.endswith('》'):text=text[1:-1]
    return '《'+text.replace('《','〈').replace('》','〉')+'》'

def phrase_vocab(body):
    """Bind known full phrases to their exact accented forms in this title."""
    out={}
    # Match phrase boundaries on a normalized copy and recover exact source
    # intervals: combining accent removal never changes source identity.
    folded=q.source_key(body).replace('’',"'").replace('_',' ')
    # NFKD expansion in unusual ligatures can shift offsets; require equality.
    if len(folded)!=len(body):
        for phrase,zh in PHRASES.items():
            if q.normphrase(body)==phrase:out[body]=zh
        return out
    for m in PHRASE_PATTERN.finditer(folded):
        out[body[m.start():m.end()]]=PHRASES[m[0].casefold()]
    return out

def full_music(body):
    # Retain exact source bibliographic author labels, not invented Chinese
    # musician names or inferred composers, within the reference title.
    body=re.sub(r'\s+',' ',body)
    annotations=[]
    def label(m):
        annotations.append(m[1]);return ' '+str(900000+len(annotations))+' '
    parsebody=AUTHOR_BRACKET.sub(label,body)
    def bibliographic_note(m):
        annotations.append(m[1]);return ' '+str(900000+len(annotations))+' '
    parsebody=re.sub(r'\(('+'|'.join(re.escape(k) for k in sorted(SOURCE_SURNAMES,key=len,reverse=True))+r')\)',bibliographic_note,parsebody)
    def source_prefix_note(m):
        token=q.normphrase(m[1])
        if token in q.MUSIC or token in PHRASES or token in TERMS:return m[0]
        annotations.append(m[1]);return str(900000+len(annotations))+' '
    parsebody=re.sub(r'^\(([A-Za-zÀ-ž .\-\x27’]{2,45})\)\s*',source_prefix_note,parsebody)
    value=q.semantic_title(parsebody,phrases=phrase_vocab(parsebody),terms=TERMS)
    if not value:return None,[]
    for i,name in enumerate(annotations,1):value=value.replace(str(900000+i),'（原题括注：'+name+'）')
    return value,annotations

def opaque_music(body):
    """Translate a complete genre/part/opus frame around an opaque title label.

    This preserves a full named label, rather than assuming its words are a
    person's name or inventing a meaning. At most one opaque span is allowed.
    """
    # A source title at either end of an explicit genre clause is a label.
    genres=r'(?:waltz|valse|vals|valsa|walzer|polka|mazurka|tango|habanera|gavotte|gavota|schottische|march|marche|serenade|serenata|romance|romanza|blues|rag|nocturne|fantasia|fantaisie|fantasy|capricho|caprice|ballad|song|melody|lullaby|sonata|suite)'
    opus=[]
    body=q.OPUS.sub(lambda m:opus.append('作品'+m[1]) or '',body).strip(' .,-')
    m=re.match(r'(.{1,65}?)\s+(('+genres+r')(?:\s+.*)?)$',body,re.I)
    if not m:
        m=re.match(r'(.{1,65}?)\s*\((('+genres+r')(?:\s+.*)?)\)(.*)$',body,re.I)
        if m:m=(m[1],m[2]+' '+m[4])
    if not m:
        # "Choro para Metronomo" / "A choro for Aline" has an explicitly
        # named dedicatee/object, whose exact label can be retained naturally.
        dedicated=re.fullmatch(r'(?:a\s+)?(choro|blues|waltz|serenade|song|canto)\s+(?:for|para|de)\s+(.{1,50})',body,re.I)
        if dedicated:
            genre,_=full_music(dedicated[1]);name=dedicated[2]
            if dedicated[1].casefold()=='canto':genre='歌'
            if genre and not re.search(r'\d|\b(?:and|et|y|with)\b',name,re.I):
                phrasing=(name+'之'+genre if re.search(r'\s+de\s+',body,re.I) else '为 '+name+' 而作的'+genre)
                return phrasing+('，'+ '，'.join(opus) if opus else ''),name,True
        return None
    label,frame=(m[1],m[2]) if not isinstance(m,tuple) else m
    # If a title label is a still-unparsed musical/bibliographical clause,
    # retaining it as a proper-name label would conceal a failed parser.
    bad=r'\b(?:op|opus|oeuv|no|nr|bwv|weisssw|suite|guitar|guitare|pour|for|para|per|by|von|arr|variations|and|et|y|with|sur|from|mov|volume|book|recueil|fantasie|fantaisie|fantasia|rondo|rondeau|landler|mazurka|allegro|andante|sarabande|polka|first|second|premier|première|quatrieme|three|four|six|orchestral|fragmento|invitation)\b'
    if re.search(bad,label,re.I) or re.search(r'\d',label) or len(label.split())>7:return None
    f,ann=full_music(frame)
    if not f:return None
    # Literal full phrases have priority. Unknown label is kept fully verbatim.
    translated=PHRASES.get(q.normphrase(label))
    return (translated or label)+'——'+f+('，'+'，'.join(opus) if opus else ''),label,not bool(translated)

def retain_reason(body):
    if re.search(r'(?<!\w)sinfonia(?!\w)',body,re.I):
        return '原题中的 Sinfonia 既可指歌剧序曲，也可指独立交响性作品；本条完整结构尚不足以可靠限定此处体裁，保留完整原题，不据裸词强译交响曲。','ambiguous_genre_retention'
    if re.search(r'\.\.\.|…|i\.e\.|degree mark|<|>|_{2,}',body,re.I):
        return '原题含截断、转录残片或字形说明（'+body[:100]+'）；缺少足够上下文，保留完整原题避免补造题名。','incomplete_source_retention'
    if len(body)>100 or re.search(r'\b(?:arranged|arrange|von|arr\.|sung|written|published|journal|opera|oper|opéra|libro|livre|recueil)\b',body,re.I):
        return '原题包含书目说明、来源/编改署名或引文（'+body[:100]+'）；主从关系或引用题名未全部核实，保留完整转录。','bibliographic_scope_retention'
    if re.search(r'(?<!\w)[BH]\s*-?\s*(?:dur|moll)\b',body,re.I):
        return '原题使用 B/H 与德语 dur/moll 混合记谱，无法仅凭题名判断 B 与降B；保留完整原题避免错置调性。','ambiguous_key_retention'
    if len(body.split())<=3 and not re.search(r'\d',body):
        return '简短专名或语义多义题名“'+body+'”；没有支持此处具体所指的可靠释义，不强作音译或按普通词义猜译。','proper_name_retention'
    return '题名“'+body+'”含尚不能可靠解释的短语、诗句/引文或专名关系；保留完整原题，不把逐词猜译作为中文定名。','semantic_ambiguity_retention'

def opera_revue(row,body):
    """The explicitly numbered Mertz opera-selection collection, not identity."""
    if row['composer']!='Mertz. Johann Kaspar':return None
    # Two source transcriptions of the same *structure*, not merged records.
    # Unknown names remain raw labels; the full opera-selection meaning is
    # independently present in "Opern-Revue", or Mertz's guarded Op.8 series.
    ops=q.OPUS.findall(body);numbers=q.SERIAL.findall(body)
    if not ops or len(set(ops))!=1 or ops[0]!='8' or len(numbers)!=1:return None
    if not (re.search(r'Opern.?Revue',body,re.I) or re.match(r'^Op\.?\s*8\s+No',body,re.I)):return None
    stripped=q.OPUS.sub('',body);stripped=q.SERIAL.sub('',stripped)
    stripped=re.sub(r'Opern.?Revue\.?|Ausgewählte Melodien für die Guitar(?:e)?','',stripped,flags=re.I).strip(' .,')
    m=re.match(r'(Bellini|Donizetti|Verdi|Weber|Meyerbeer|Auber|Rossini|Flotow|Nicolai|Wagner|Balfe|Halevy|Halévy|Adam|Pugni|Herold|Hérold)\s+(.+)',stripped,re.I)
    if not m:return None
    name,title=m[1],m[2].strip()
    if re.search(r'\b(?:arr|pour|for|von|musique|music)\b',title,re.I):return None
    titlezh=PHRASES.get(q.normphrase(title),title)
    return '歌剧选曲集，作品8：第'+numbers[0]+'曲——“'+titlezh+'”（原题署名：'+name+'）'

def decision(row):
    body,notes=body_of(row)
    value,annotations=full_music(body)
    method='closed_template'
    reason='完整音乐题名已按体裁、数量/编号、调性、乐章/声部及明确的用途结构解析；没有未解释的实义词。'
    if value:
        known=[m[0].casefold() for m in PHRASE_PATTERN.finditer(q.source_key(body).replace('’',"'").replace('_',' '))]
        if known:
            method='exact_semantic_phrase_template'
            reason='按完整题名短语的语义复核，并与明确音乐结构组合；参考意译不声称是通行中文定名。短语：'+ '；'.join(known[:5])+'。'
    else:
        named=opaque_music(body)
        if named:
            value,label,opaque=named;method='named_music_template'
            reason=('标题标签“'+label+'”完整保留原文，不猜定人名、地名或词义；' if opaque else '完整题名短语“'+label+'”已核对语义；')+'体裁、明确编制/声部及作品号按独立音乐句法翻译。'
    # The exact title/attribution corrections separately checked on Oct 2 are
    # rechecked against this partition; no title similarity or ID-only reuse.
    old=PRIOR_EXACT.get(row['id'])
    if old and old['original']==row['original'] and old.get('original_composer')==row['composer'] and old['status'] in {'reference','reviewed'} and (not value or row['id']=='cglib:1088'):
        value=old['zh'];method='exact_semantic_recheck';reason='复核完整原题与精确署名守卫，并采用已逐题校订的语义修订：'+old.get('reason','')
    refs=[];status='reference' if value else 'retained'
    operavalue=opera_revue(row,body)
    if operavalue:
        value=operavalue;status='reference';method='exact_collection_semantic_template'
        reason='本条为原题明确的 Mertz《Opern-Revue》作品8编号选曲结构，逐项保留第'+q.SERIAL.findall(body)[0]+'曲及引用歌剧原题/署名。歌剧作者标签只解释原题，不替换本记录原文作曲者字段，也不合并各版身份。'
        refs.append('https://cdn.naxos.com/sharedfiles/pdf/naxoscat2008may.pdf')
    normalized=q.normphrase(body)
    operatic_sinfonia=re.fullmatch(r'sinfonia nell opera (la cenerentola|semiramide)',normalized)
    if operatic_sinfonia:
        title='灰姑娘' if operatic_sinfonia[1]=='la cenerentola' else '塞米拉米德'
        value='歌剧〈'+title+'〉序曲';status='reference';method='exact_semantic_research'
        reason='完整意大利语题名明确为歌剧中的 Sinfonia；Treccani 将此歌剧语境说明为 ouverture，译序曲，不能使用脱离语境的交响曲。源题歌剧名称与原文署名保留，不据题名改换本记录作曲者或版本身份。'
        refs=['https://www.treccani.it/enciclopedia/ouverture/']
    if row['composer']=='Giuliani. Mauro' and re.search(r'(?<!\w)rossinian[ae](?!\w)',normalized):
        opus=q.OPUS.findall(body);number=q.SERIAL.findall(body)
        if len(opus)==1 and len(number)==1 and opus[0] in {'119','120','121','122','123','124'} and number[0]==str(int(opus[0])-118):
            framed=q.semantic_title(body,phrases={**phrase_vocab(body),'Rossiniane':'罗西尼歌剧主题幻想曲','Rossiniana':'罗西尼歌剧主题幻想曲'},terms=TERMS)
            if framed:
                value=framed;status='reference';method='exact_collection_semantic_template'
                reason='Naxos 的 Giuliani 作品说明明确 Rossiniane 为罗西尼歌剧主题幻想曲；本条精确核对 Giuliani 原文署名与原题作品119—124、第1—6号对应关系。保留此来源原题和版本身份，不泛用于同名他人作品。'
                refs=['https://www.naxos.com/CatalogueDetail/?id=8.574272']
    if 'julia florida' in normalized and 'barrios' in q.source_key(row['composer']):
        framed=q.semantic_title(body,phrases={**phrase_vocab(body),'Julia Florida':'花样的朱莉娅'},terms=TERMS)
        if framed:
            value=framed;status='reviewed';method='official_chinese_title_exact_attribution'
            reason='杨雪霏官方发布明确将巴里奥斯船歌 Julia Florida 称为《花样的朱莉娅》，已精确核对本记录原题及 Barrios 原文署名；没有把 Florida 误作美国州名。'
            refs=['https://www.bilibili.com/list/618775304?bvid=BV1Hh4y1B7GK&oid=662381921']
    if row['id']=='cglib:1049':
        assert row['original']=='Escuela para tocar con perfeccion la guitarra de cinco y seis ordenes, con reglas generales de mano izquierda y derecha'
        assert row['composer']=='Abreu. Antonio'
        value='五弦组与六弦组吉他演奏完善教程：左右手通则';status='reference';method='exact_semantic_research'
        reason='完整西语书目题名按教程及演奏规则释义。RAE orden 的音乐义明确为一根弦或同奏的弦组，因此 cinco y seis ordenes 译五弦组与六弦组，绝不解释为五/六位演奏者。'
        refs=['https://dle.rae.es/orden']
    if value and re.search(r'barden.?kl',normalized):
        refs.append('https://www.naxos.com/CatalogueDetail/?id=8.554556')
    if value and re.search(r'(?<!\w)cueca(?!\w)',normalized):refs.append('https://dle.rae.es/cueca')
    if value and re.search(r'(?<!\w)(?:cis|des|dis|es|eis|fes|fis|ges|gis|as|ais|ces|his)\s*-?\s*(?:dur|moll)\b',body,re.I):refs.append('https://www.dolmetsch.com/musictheory9.htm')
    if value and re.search(r'suite\s+(?:popular|populaire)\s+(?:brasileira|bresilienne)',normalized):refs.append('https://www.durand-salabert-eschig.com/-/media/Images/DSE/PDFs/Brochures/V/villa-lobos_heitor.ashx?hash=2514016EDCDF33ECC83BB7EF10A052567E410A8E&la=en-GB')
    if row['composer']=='Emmanuel. Tommy' and any(word in normalized for word in ['locomotivation','borsalino','luttrell','biskie','to b or not to b','to c or not to c','classical gas']):
        status='retained';value=row['original'];method='author_title_proper_name_retention'
        reason='题名“'+body+'”属于专名、造词或带字母/习语的双关，没有支持此处具体所指的可靠中文释义。保留完整原题，不强作音译或译成普通物名。'
        refs=[]
        if any(word in normalized for word in ['locomotivation','luttrell']):
            reason+=' 作者官方乐谱页面确认相关原文题名存在；该证据并不解释其中文含义。'
            refs=['https://shop.tommyemmanuel.com/collections/guitar-tab?page=2']
    if not value:reason,method=retain_reason(body);value=row['original']
    if annotations:reason+=' 原题括号署名按原拼写保留，不改作作曲者证据。'
    if notes:reason+=' '+' '.join(notes)
    return {'id':row['id'],'original':row['original'],'original_composer':row['composer'],'zh':wrap(value),'status':status,'basis':'cglib_complete_semantic_review_2026_10_03','reason':reason,'source_refs':refs, 'reviewer':'codex_cglib_partition','review_method':method}

def main():
    records=json.loads((ROOT/'work/title-review/2026-10-03/cglib.json').read_text())
    out=[decision(row) for row in records]
    path=HERE/'cglib_decisions.json';path.write_text(json.dumps({'schema_version':1,'entries':out},ensure_ascii=False,indent=2)+'\n')
    target=ROOT/'work/title-review/2026-10-03/cglib-review'
    report={'records':len(out),'statuses':dict(collections.Counter(x['status'] for x in out)),'methods':dict(collections.Counter(x['review_method'] for x in out)),'changed_text':sum(x['zh']!=r['zh'] for r,x in zip(records,out)),'previous_status':dict(collections.Counter(x['status'] for x in records)),'phrase_entries':len(PHRASES),'scope':'All CGLIB frozen records, exact title and original attribution guards. No acquisition/export. Each record receives a semantic-template or concrete retention decision; research is shared terminology/title evidence, not per-record web search.'}
    report['status_transitions']={a+' -> '+b:n for (a,b),n in collections.Counter((r['status'],x['status']) for r,x in zip(records,out)).items()}
    inputs=[HERE/'build_cglib_review.py', HERE/'cglib_semantic_rules.py', FROZEN_PATH, ROOT/'work/title-review/2026-10-03/cglib.json']
    report['input_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs if p.exists()}
    report['decision_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    report['source_refs']=[{'url':url,'decisions':count} for url,count in sorted(collections.Counter(u for x in out for u in x['source_refs']).items())]
    (target/'coverage.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    (target/'full-ledger.json').write_text(json.dumps([dict(x,before=r) for r,x in zip(records,out)],ensure_ascii=False,indent=2)+'\n')
    (target/'retained-titles.tsv').write_text('\n'.join('\t'.join([x['id'],x['original_composer'],x['original'],x['review_method']]) for x in out if x['status']=='retained'))
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
