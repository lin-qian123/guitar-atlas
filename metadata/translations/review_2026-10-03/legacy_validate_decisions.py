"""Validate the frozen semantic decisions against their complete source corpus.

The number/key checks are preservation checks, not authoritative Chinese-name
certification. Recognize a few ordinary Chinese number equivalents explicitly;
do not guess a catalogue number from a bare musical key such as F1.
"""
from __future__ import annotations
import hashlib,json,re
from collections import Counter
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
CN=dict(zip('〇零一二两三四五六七八九',[0,0,1,2,2,3,4,5,6,7,8,9]))

def chinese_number(s):
    if not any(c in s for c in '十百千'):
        return int(''.join(str(CN[c]) for c in s))
    total=current=0
    for c in s:
        if c in CN:current=CN[c]
        else:total+=(current or 1)*{'十':10,'百':100,'千':1000}[c];current=0
    return total+current

def number_values(s,chinese=False):
    values=Counter(int(v) for v in re.findall(r'\d+',s))
    if chinese:
        # 二四拍 expresses 2/4, not the integer 24. Other Chinese integers
        # retain their normal reading. 三重奏 is a form, not a source work no.
        s=re.sub(r'([二三四五六七八九])([二四八])拍',lambda m:m[1]+'、'+m[2]+'拍',s)
        for phrase in re.findall(r'[〇零一二两三四五六七八九十百千]+',s):
            values[chinese_number(phrase)]+=1
        values[1]+=len(re.findall(r'单层(?:键盘|或)',s))
        values[2]+=len(re.findall(r'双',s))
    # I and II stand alone in some literal translated ordinal headings.
    roman={'I':1,'II':2,'III':3,'IV':4,'V':5,'VI':6,'VII':7,'VIII':8,'IX':9,'X':10,'XI':11,'XII':12,'XIII':13,'XIV':14,'XV':15,'XVI':16,'XVII':17,'XVIII':18,'XIX':19,'XX':20}
    # Count these only in target headings: I in an English incipit is a
    # pronoun, I in an Italian title is an article, V in Czech is a preposition.
    # Explicit structural source Roman numbers have their separate check below.
    if chinese:
        for v in re.findall(r'(?<![A-Za-z0-9_])(?:XVIII|XVII|XVI|XIII|XII|VIII|XIX|XIV|XV|XI|VII|III|II|IV|VI|IX|XX|X|I|V)(?![A-Za-z0-9_])',s):values[roman[v]]+=1
    return values

def balanced(text):
    stack=[];pairs={'》':'《','〉':'〈','）':'（',')':'(',']':'[','}':'{'}
    for c in text:
        if c in '《〈（([{':stack.append(c)
        elif c in pairs:
            if not stack or stack.pop()!=pairs[c]:return False
    return not stack

def errors(rows,entries):
    defects=[]
    if len(rows)!=len(entries):defects.append(('count',len(rows),len(entries)))
    if len({e['id'] for e in entries})!=len(entries):defects.append(('duplicate IDs',))
    keys=re.compile(r'\b([A-G])([- ]?(?:flat|sharp))?\s+(major|minor|dur|moll)\b|\b([A-G])[- ](Dur|Moll)\b',re.I)
    for r,e in zip(rows,entries):
        if (e['id'],e['original'],e['original_composer'])!=(r['id'],r['original'],r['composer']):defects.append(('source guard',r['id']))
        if e['status'] not in {'reference','reviewed','retained'}:defects.append(('status',e['id']))
        if not e.get('reason') or not e.get('basis'):defects.append(('missing reasoning',e['id']))
        if not isinstance(e.get('source_refs'),list) or any(not u.startswith('https://') for u in e['source_refs']):defects.append(('source refs',e['id']))
        if 'display_original' in e and e['display_original']!=r['display_original']:defects.append(('display guard',e['id']))
        if e['status']=='retained':
            if e['zh']!=e['original']:defects.append(('retention changed original',e['id']))
            continue
        for field in ('zh','display_zh'):
            if field in e and not balanced(e[field]):defects.append(('unbalanced title',e['id'],field,e[field]))
            if re.search(r'https?://|<[^>]+>|操作。',e.get(field,'')):defects.append(('display pollution',e['id'],field))
        if not (e['zh'].startswith('《') and e['zh'].endswith('》')):defects.append(('outer title marks',e['id']))
        missing=number_values(e['original'])-number_values(e['zh'],True)
        if missing:defects.append(('number preservation',e['id'],dict(missing),e['original'],e['zh']))
        for m in keys.finditer(e['original']):
            letter=(m[1] or m[4]).upper();mode='小调' if (m[3] or m[5]).lower() in ('minor','moll') else '大调'
            if not re.search(letter+r'\s*'+mode,e['zh']):defects.append(('key preservation',e['id'],m[0],e['zh']))
    return defects

def main():
    rows=sum((json.loads((ROOT/'work/title-review/2026-10-03'/f'{s}.json').read_text()) for s in ('imslp','classclef')),[])
    p=HERE/'legacy_decisions.json';payload=json.loads(p.read_text());assert payload['schema_version']==1
    defects=errors(rows,payload['entries'])
    result=dict(total=len(rows),decision_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),number_key_delimiter_guard_defects=defects)
    out=ROOT/'work/title-review/2026-10-03/legacy-review/final-validation.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2));assert not defects
if __name__=='__main__':main()
