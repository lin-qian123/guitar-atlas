"""Full-ID and original/composer guarded legacy title review builder.

The vocabulary is allowed only for wholly consumed musical formulae. It does
not turn every alphabetic word into a dictionary lookup or authorize a person
identity merge. Manual exact decisions take precedence over formula evidence.
"""
from __future__ import annotations
import argparse
import copy
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
WORK=ROOT/'work/title-review/2026-10-03'

def read(path):
    return json.loads(path.read_text())

def norm(s):
    s=''.join(c for c in unicodedata.normalize('NFKD',s) if not unicodedata.combining(c))
    return s.casefold()

TERMS=read(HERE/'legacy_music_vocabulary.json')['terms']
TERMS.update({
 'poco allegretto':'小快板（Poco Allegretto）',
 'canzon':'坎佐纳曲','canzons':'坎佐纳曲','canzona':'坎佐纳曲','canzonas':'坎佐纳曲',
 'canzoni':'坎佐纳曲','canzone':'坎佐纳曲','canzones':'坎佐纳曲',
 'ricercar':'利切尔卡尔曲','recercare':'利切尔卡尔曲','recercares':'利切尔卡尔曲',
 'recercari':'利切尔卡尔曲','recercars':'利切尔卡尔曲','ricercars':'利切尔卡尔曲',
 'ricercares':'利切尔卡尔曲','ricercari':'利切尔卡尔曲','ricercar':'利切尔卡尔曲',
 'fantasias':'幻想曲','fantasies':'幻想曲','fantaisies':'幻想曲','fantaisie':'幻想曲',
 'fantazias':'幻想曲','phantasie':'幻想曲','fantasien':'幻想曲',
 'duetti':'二重奏','duettini':'小二重奏','duettino':'小二重奏','duos':'二重奏','duets':'二重奏',
 'dui':'二重奏','trios':'三重奏','quartets':'四重奏','quatuors':'四重奏',
 'quintet':'五重奏','sextet':'六重奏','sonatas':'奏鸣曲','sonates':'奏鸣曲','sonate':'奏鸣曲',
 'sonatinas':'小奏鸣曲','sonatines':'小奏鸣曲','sonatinen':'小奏鸣曲',
 'sinfonie':'交响曲','sinfonia':'交响曲','symphony':'交响曲','symphonies':'交响曲',
 'overture':'序曲','ouverture':'序曲','ouvertures':'序曲','overtur':'序曲','obertura':'序曲',
 'contrapunto':'对位曲','contrappunto':'对位曲','counterpoint':'对位曲','invention':'创意曲','inventions':'创意曲',
 'canticle':'颂歌','canticles':'颂歌','motet':'经文歌','motets':'经文歌','morceaux':'小品',
 'morceau':'小品','pezzi':'小品','pezzo':'小品','piece':'小品','pieces':'小品','piezas':'小品',
 'miniature':'微型曲','miniatures':'微型曲','esquisse':'素描小品','esquisses':'素描小品',
 'arabesque':'阿拉伯风格曲','arabesques':'阿拉伯风格曲','arabesken':'阿拉伯风格曲',
 'feuillets d album':'纪念册页','album leaves':'纪念册页','albumblatt':'纪念册页','albumblad':'纪念册页',
 'chanson':'歌曲','chansons':'歌曲','cancion':'歌曲','canciones':'歌曲','canto':'歌曲','canti':'歌曲',
 'songs':'歌曲','lied':'歌曲','lieder':'歌曲','oden':'颂歌','psalm':'诗篇','psalms':'诗篇',
 'serenades':'小夜曲','serenatas':'小夜曲','serenaten':'小夜曲','nocturnes':'夜曲','nocturnos':'夜曲',
 'divertissemens':'嬉游曲','divertimenti':'嬉游曲','divertimentos':'嬉游曲','divertissements':'嬉游曲',
 'recreations':'消遣小品','recreation':'消遣小品','rondinos':'小回旋曲','rondeaux':'回旋曲','rondos':'回旋曲',
 'rondo':'回旋曲','rondoletto':'小回旋曲','rondolettos':'小回旋曲','rondoletti':'小回旋曲',
 'monferrine':'蒙费里纳舞曲','monferine':'蒙费里纳舞曲','montferines':'蒙费里纳舞曲',
 'landler':'兰德勒舞曲','laendler':'兰德勒舞曲','landlers':'兰德勒舞曲','walzer':'圆舞曲',
 'walses':'圆舞曲','walzes':'圆舞曲','walzes':'圆舞曲','mazurkas':'玛祖卡舞曲','polkas':'波尔卡舞曲',
 'ecossaises':'埃科塞斯舞曲','ecossoises':'埃科塞斯舞曲','ecossaise':'埃科塞斯舞曲',
 'tarentelles':'塔兰泰拉舞曲','tarantellas':'塔兰泰拉舞曲','saltarelli':'萨尔塔雷洛舞曲',
 'galopes':'加洛普舞曲','galops':'加洛普舞曲','galopade':'加洛普舞曲','gallopade':'加洛普舞曲',
 'minues':'小步舞曲','minue':'小步舞曲','menuets':'小步舞曲','minuets':'小步舞曲',
 'allemandes':'阿勒曼德舞曲','courantes':'库朗特舞曲','paduana':'帕凡舞曲','paduan':'帕凡舞曲',
 'galliards':'加利亚德舞曲','basses dances':'低步舞曲','basse danse':'低步舞曲',
 'quadrille':'四对舞曲','quadrilles':'四对舞曲','country dances':'乡村舞曲',
 'contre-danses':'对舞曲','contredanses':'对舞曲','contre danses':'对舞曲',
 'marches':'进行曲','marcias':'进行曲','marche':'进行曲','dances':'舞曲','balli':'舞曲',
 'themes':'主题','themen':'主题','temi':'主题','temas':'主题',
 'variaciones':'变奏曲','variationen':'变奏曲','variationes':'变奏曲','varyed':'变奏',
 'air varie':'曲调变奏曲','airs varies':'曲调变奏曲','themes varies':'主题变奏曲',
 'theme varie':'主题变奏曲','varied themes':'主题变奏曲',
 'fugues':'赋格','fugen':'赋格','toccatas':'托卡塔','tocatas':'托卡塔','preludien':'前奏曲',
 'praludien':'前奏曲','praeludium':'前奏曲','praeludia':'前奏曲','preludes':'前奏曲',
 'guitars':'吉他','guitarre':'吉他','guitarres':'吉他','guitarren':'吉他','gitarre':'吉他',
 'gitarren':'吉他','chitarra':'吉他','chitarre':'吉他','guitarras':'吉他','guitarres':'吉他',
 'guitarres':'吉他','gitarra':'吉他','guitares':'吉他','lutes':'鲁特琴','luth':'鲁特琴',
 'harpsichord':'大键琴','cembalo':'大键琴','clavecin':'大键琴','keyboard':'键盘','piano':'钢琴',
 'pianoforte':'钢琴','piano forte':'钢琴','fortepiano':'早期钢琴','organ':'管风琴','organo':'管风琴',
 'orgel':'管风琴','orgue':'管风琴','viola da gamba':'维奥尔琴','bass viol':'低音维奥尔琴',
 'baryton':'巴里顿琴','viols':'维奥尔琴','viol':'维奥尔琴','violone':'维奥隆琴',
 'viola':'中提琴','violas':'中提琴','alto':'中提琴','violin':'小提琴','violino':'小提琴',
 'violinos':'小提琴','violini':'小提琴','violon':'小提琴','violons':'小提琴','violine':'小提琴',
 'cellos':'大提琴','violoncello':'大提琴','flutes':'长笛','flauto':'长笛','flute':'长笛',
 'oboes':'双簧管','oboe':'双簧管','clarinet':'单簧管','bassoon':'巴松管','horn':'圆号',
 'tambourine':'铃鼓','triangle':'三角铁','timpani':'定音鼓','strings':'弦乐','string':'弦乐',
 'recorder':'竖笛','recorders':'竖笛','accordion':'手风琴','mandolino':'曼陀林',
 'mandoline':'曼陀林','mandolins':'曼陀林','lyre':'里拉琴','lyra':'里拉琴',
 'partitas':'组曲','partiten':'组曲','suites':'组曲','consort':'合奏曲','contrapunctus':'对位曲',
 'potpourri':'集锦曲','potpourris':'集锦曲','pot-pourri':'集锦曲','pot-pourris':'集锦曲',
 'pot pourri':'集锦曲','pot pourris':'集锦曲','ballet airs':'芭蕾舞曲',
 'easy':'简易','facile':'简易','faciles':'简易','leichte':'简易','leicht':'简易',
 'tres faciles':'非常简易','extremement faciles':'极为简易','non difficiles':'简易',
 'progressive':'渐进','progressives':'渐进','progressivi':'渐进','progressifs':'渐进',
 'concertante':'协奏性','concertantes':'协奏性','concertant':'协奏性','concertants':'协奏性',
 'concertans':'协奏性','concertanti':'协奏性','notturni':'夜间','sencillos':'简易',
 'brillants':'华丽','brillans':'华丽','brillantes':'华丽','brillant':'华丽',
 'brillanti':'华丽','brillante':'华丽','große':'大','grosse':'大','grosses':'大','grand':'大',
 'grande':'大','grandes':'大','gran':'大','grandi':'大',
 'petits':'小','petit':'小','petites':'小','piccoli':'小','pequenas':'小','kleine':'小',
 'kleinen':'小','klein':'小','small':'小','short':'短小','little':'小','new':'新',
 'neue':'新','nouvelles':'新','nouvelle':'新','nouveaux':'新','nouveau':'新',
 'original':'原创','originales':'原创','favorites':'精选','favorite':'精选','favoris':'精选',
 'favoriti':'精选','favourites':'精选','adored':'精选','admired':'精选','choice':'精选',
 'characteristic':'性格','caracteristiques':'性格','charakteristische':'性格',
 'characteristiques':'性格','caracteristicas':'性格','contemporanei':'当代',
 'national':'民族','nationaux':'民族','nationales':'民族','instructive':'教学',
 'instructives':'教学','harmonische':'和声','angenehme':'悦耳','lyrique':'抒情',
 'lyrische':'抒情','sentimentale':'抒情','gracieux':'优美','expressive':'富于表情',
 'german':'德国','deutsche':'德国','deutscher':'德国','russian':'俄罗斯',
 'russes':'俄罗斯','russie':'俄罗斯','russe':'俄罗斯','autrichiennes':'奥地利',
 'french':'法国','francais':'法国','italian':'意大利','italiens':'意大利','mexicanas':'墨西哥',
 'americanas':'美洲','american':'美国','ukrainian':'乌克兰','spanish':'西班牙',
 'suisses':'瑞士','swiss':'瑞士','irish':'爱尔兰','tyrolian':'蒂罗尔','hebraiques':'希伯来',
 'practical':'实用','practicas':'实用','studettes':'小练习曲','exercices':'练习',
 'excersises':'练习','exercices':'练习','excercices':'练习','exercicios':'练习',
 'ejercicios':'练习','lezioni':'练习','lecon':'练习','lecons':'练习','lectionen':'练习',
 'studies':'练习曲','studi':'练习曲','estudos':'练习曲','estude':'练习曲',
 'estudes':'练习曲','collection':'曲集','recueil':'曲集','coleccion':'曲集',
 'set':'组','cahier':'册','heft':'册','livre':'册','vol':'卷','volume':'卷',
 'without bass':'无低音伴奏','sans basse':'无低音伴奏','senza basso':'无低音伴奏',
 'solo':'独奏','solos':'独奏曲','seule':'独奏','seul':'独奏','sola':'独奏','allein':'独奏',
 'obbligata':'必奏','obligato':'必奏','obbligato':'必奏','accompaniment':'伴奏',
 'avec accompagnement':'附伴奏','arranged':'改编','arrangees':'改编','arranges':'改编',
 'arranges':'改编','arrangement':'改编','arrangements':'改编','formés':'组成',
 'mit':'与','with':'与','ohne':'无','und':'与','and':'与','et':'与','e':'与','y':'与',
 'con':'与','avec':'与','or':'或','ou':'或','o':'或','oder':'或','per':'为','pour':'为',
 'for':'为','fur':'为','para':'为','of':'的','de':'的','di':'的','del':'的','della':'的',
 'the':'','le':'','la':'','il':'','lo':'','les':'','des':'','die':'','der':'','das':'',
 'du':'的','d':'的','a':'','une':'','un':'','il':'','d':'的','do':'C',
 'two':'2','due':'2','deux':'2','zwey':'2','zwei':'2','three':'3','drei':'3',
 'four':'4','five':'5','six':'6','sechs':'6','seven':'7','eight':'8','nine':'9',
 'ten':'10','twelve':'12','seis':'6','sei':'6','dos':'2','funf':'5',
})
COMPILED_TERMS=[(term,re.compile(r'(?<![a-z])'+re.escape(term)+r'(?![a-z])'),TERMS[term])
                for term in sorted(TERMS,key=len,reverse=True)]

def formula(original):
    text=norm(original)
    held=[]
    def hold(s):
        held.append(s)
        return '〚'+str(len(held)-1)+'〛'
    # Abbreviations are identifiers, not translated words or diagnoses.
    text=re.sub(r'\b(?:bwv|buxwv|twv|krebs-wv|hwv|rv|lv|sz|ms|wsw|weisssw|hoo|hess|wo[o]?|hob|k\.anh\.c|k|l|d|p|r|mt|rc|t|f|apg|wp|fo|ijc|iah|vb|zd|m\.a|mj|b|bi|w|eng[k]?|fvg|fvb)\.?\s*(?:[ivxlcdm]+[.:])?\d+(?:[.:/][a-z0-9]+)*(?:[-–]\d+)?[a-z]?\b',
                lambda m:hold(m[0].upper() if m[0].startswith(('bwv','hwv','rv','twv','ms','wk')) else m[0]),text)
    text=re.sub(r'\b(?:op(?:us)?|opp)\.?(?:\s+no\.?\s*)?\s*(\d+[a-z]?(?:\s*[,/]\s*\d+[a-z]?)*)(?!\w)',lambda m:hold('作品'+m[1]),text)
    def key(m):
        key={'do':'C','re':'D','mi':'E','fa':'F','sol':'G','la':'A','si':'B'}.get(m[1],m[1].upper())
        acc={'flat':'降','sharp':'升','b':'降','#':'升','♭':'降','':''}.get(m[2] or '','')
        mode={'major':'大调','majeur':'大调','mayor':'大调','dur':'大调','minor':'小调','mineur':'小调','menor':'小调','moll':'小调','':'调'}[m[3] or '']
        return hold(acc+key+mode)
    text=re.sub(r'\b(?:in|en)\s+([a-g]|do|re|mi|fa|sol|la|si)(?:[- ]?(flat|sharp|b|#|♭))?(?:\s+(major|minor|majeur|mineur|mayor|menor|dur|moll))?(?![a-z0-9])',key,text)
    text=re.sub(r'\b([a-g])(?:[- ]?(flat|sharp|b|#|♭))?\s+(major|minor|dur|moll)\b',key,text)
    text=re.sub(r'\b(?:no\.?|number)\s*(\d+[a-z]?)\b',lambda m:'第'+m[1]+'号',text)
    # Source Roman numerals are preserved, never converted to guesses.
    text=re.sub(r'(?<![a-z])(?:x{0,3}(?:ix|iv|v?i{1,3})|[ivxlcdm]{2,})(?![a-z])',lambda m:hold(m[0].upper()),text)
    consumed=[]
    for term,pat,translation in COMPILED_TERMS:
        if pat.search(text):
            consumed.append(term)
            text=pat.sub(translation,text)
    if re.search('[a-z]',text):
        return None
    for i,s in enumerate(held):text=text.replace('〚'+str(i)+'〛',s)
    if not re.search('[\u3400-\u9fff]',text):return None
    # Numeral counts and identifiers must survive; closed formula generation
    # is not permitted to turn a player quantity into an ordinal work number.
    if set(re.findall(r'\d+',original))-set(re.findall(r'\d+',text)):return None
    text=re.sub(r'\s+',' ',text).strip()
    return {'translation':text,'terms':consumed,'identifiers':held}

def main():
    rows=[]
    for partition in ['imslp','classclef']:rows+=read(WORK/(partition+'.json'))
    groups=[]; covered=[]
    for row in rows:
        f=formula(row['original'])
        (covered if f else groups).append({**row,**({'formula':f} if f else {})})
    out=WORK/'legacy-review';out.mkdir(parents=True,exist_ok=True)
    (out/'closed-formula-rows.json').write_text(json.dumps(covered,ensure_ascii=False,indent=2)+'\n')
    (out/'open-semantic-rows.json').write_text(json.dumps(groups,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'formula':len(covered),'semantic':len(groups),'sources':Counter(r['source_id'] for r in covered)},ensure_ascii=False))

if __name__=='__main__':main()
