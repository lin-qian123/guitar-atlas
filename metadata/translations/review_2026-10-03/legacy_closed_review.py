"""Contextual decisions for musical formulae read in the 2026-10-03 corpus.

The caller may use these repairs only on that exact, fully read source snapshot.
They are not a translation dictionary for arbitrary prose or future discoveries.
Open lyric/title clauses must pass through the separately read manual decisions.
"""
import re
from legacy_review_helper import norm, formula

# These are music terms with definite contextual false-friend defects in the
# complete formula corpus. Every application is materialized with full ID,
# original and original_composer guards by legacy_build_decisions.py.
CONTEXTUAL = [
 (r'\barabesk(?:en|e)?\b|\barabesques?\b',r'阿拉伯式花纹|蔓藤花纹','阿拉伯风格曲','Arabesque为器乐阿拉伯风格曲，非花纹或藤蔓。'),
 (r'\besquisses?\b',r'幅\s*草图|草图','首素描小品','Esquisse在器乐标题中为素描小品，不是图画文件。'),
 (r'\bminiatures?\b',r'幅\s*缩影|缩影','首微型曲','Miniature为音乐微型曲，非照片/实体缩影。'),
 (r'\bminues?\b',r'分钟','首小步舞曲','Minué为小步舞曲体裁，非分钟时间单位。'),
 (r'\bmonf?er(?:r)?ines?\b|\bmontferines\b',r'蒙费林|蒙弗林|蒙费里纳(?!舞曲)','蒙费里纳舞曲','Monferrine为意大利蒙费里纳舞曲，非人物名。'),
 (r'\bstudettes\b',r'名\s*学生|学生','首小练习曲','Studette为小练习曲，非学生数量。'),
 (r'\brecreations?\b',r'项\s*休闲活动|休闲活动|娱乐','首消遣曲','Recreation为器乐消遣小品，非活动安排。'),
 (r'\bbasses dances\b',r'贝斯舞曲','低步舞曲','Basse danse为历史低步舞曲，非贝斯乐器。'),
 (r'\btarentelles?\b|\btarantellas?\b',r'塔伦泰勒斯|塔兰泰尔|塔兰泰勒','塔兰泰拉舞曲','Tarentelle为塔兰泰拉舞曲体裁，不是新专名。'),
 (r'\bgalopes?\b',r'加洛普斯','加洛普舞曲','Galope为加洛普舞曲体裁，不是人名复数。'),
 (r'\blyre\b',r'七弦琴|竖琴','里拉琴','Lyre为里拉琴，不是Harp竖琴或七弦琴。'),
 (r'\btriangle\b',r'三角钢琴','三角铁','Triangle为打击乐三角铁，不是钢琴。'),
 (r'\bduets?\b',r'二重唱','二重奏','此完整器乐Duet标题对应二重奏，不能改成声乐二重唱。'),
 (r'\badagio\b',r'慢板','柔板','Adagio音乐速度为柔板，与Lento慢板分开。'),
 (r'\bfinale\b',r'结局','终曲','Finale在音乐中为终曲，非故事结局。'),
 (r'\bpetits?\b',r'佩蒂','小','petit为规模修饰小，非佩蒂人名。'),
 (r'\bfandanguillo\b',r'范丹吉约|范丹吉罗','小凡丹戈舞曲','Fandanguillo为指小舞曲体裁，保留小的体裁层级。'),
 (r'\bchoro\b|\bchoros\b',r'绍罗|乔罗','肖罗','Choro为巴西肖罗曲体裁，统一同义对应。'),
 (r'\blandler\b|\blandlers\b',r'连德勒(?:舞曲)?|兰德勒(?!舞曲)','兰德勒舞曲','Ländler为历史舞曲体裁，leicht难度简易、original原创分别保留。'),
 (r'\bgrazioso\b',r'格拉齐奥索','优美','Grazioso为音乐表情优美，非专名。'),
 (r'\bsiciliana\b',r'西西里岛','西西里舞曲','Siciliana为音乐舞曲体裁，非岛屿本身。'),
 (r'\bzarabanda\b',r'扎拉班达','萨拉班德舞曲','Zarabanda为萨拉班德舞曲体裁的西语名称。'),
 (r'\btoccata\b',r'托卡塔([三四六])世',None,'罗马序号是曲目编号，非人物世代。'),
]

def outer(text):
    # An enclosure ends only when its matching first opener closes at the end.
    # 《A》与《B》 or 〈A〉与〈B〉 must keep their two separate inner titles.
    if len(text)>1 and text[0] in '《〈' and text[-1]=={'《':'》','〈':'〉'}[text[0]]:
        opener=text[0];closer=text[-1];depth=0
        for i,c in enumerate(text):
            if c==opener:depth+=1
            elif c==closer:depth-=1
            if depth==0 and i<len(text)-1:return text
            if depth<0:return text
        if depth==0:return text[1:-1]
    return text

def repair(row):
    original=row['original'];zh=outer(row['zh']);normalized=norm(original)
    if not formula(original):return None
    reasons=[]
    for source_pattern, bad, replacement, reason in CONTEXTUAL:
        if re.search(source_pattern,normalized) and re.search(bad,zh):
            if replacement is None:continue # separately guarded exact entries
            zh=re.sub(bad,replacement,zh);reasons.append(reason)
    # concertant modifies how parts interact; it is not the concerto noun.
    if re.search(r'\bconcertan(?:t[es]?|ts|s|ti)\b',normalized) and not re.search(r'\bconcerto\b',normalized):
        old=zh
        zh=zh.replace('协奏曲二重奏','协奏性二重奏').replace('二重奏协奏曲','协奏性二重奏')
        zh=zh.replace('协奏曲三重奏','协奏性三重奏').replace('三重奏协奏曲','协奏性三重奏')
        zh=zh.replace('小夜曲协奏曲','协奏性小夜曲').replace('夜曲协奏曲','协奏性夜曲')
        zh=zh.replace('协奏曲奏鸣曲','协奏性奏鸣曲')
        zh=zh.replace('协奏曲变奏曲','协奏性变奏曲').replace('音乐会二重奏','协奏性二重奏')
        if old!=zh:reasons.append('concertant为声部之间的协奏性修饰，非协奏曲体裁或音乐会标题。')
    if 'themes varies' in normalized or 'themes varies' in normalized.replace('^','') or 'varied themes' in normalized:
        old=zh;zh=zh.replace('变奏主题','主题变奏曲')
        if old!=zh:reasons.append('thème varié为完整主题变奏曲体裁。')
    if re.search(r'\boriginal\b',normalized):
        old=zh;zh=zh.replace('原版','原创').replace('原始','原创')
        if old!=zh:reasons.append('Original作为音乐题名修饰为原创，非原始物体或文件版本。')
    if re.search(r'\bserenade\b|\bserenata\b',normalized) and re.search(r'\bgrand(?:es?|s)?\b|\bgran\b',normalized):
        old=zh;zh=zh.replace('大小夜曲','大型小夜曲')
        if old!=zh:reasons.append('Grand修饰小夜曲的规模，采用大型避免大小二义。')
    if re.search(r'\bfacile(?:s)?\b|\beasy\b',normalized):
        old=zh
        zh=zh.replace('二重奏简单','简易二重奏').replace('轻松小夜曲','简易小夜曲').replace('轻松华尔兹','简易圆舞曲').replace('轻松练习曲','简易练习曲')
        if old!=zh:reasons.append('facile/easy为演奏难度简易而非曲情轻松。')
    # A source plural count is distinct from instrumentation counts.  Existing
    # classifiers are kept; an initial "2把吉他" is not rewritten as "2首".
    plural=r"pieces|piezas|morceaux|duos|duets|trios|rondos|rondeaux|sonatas|sonates|preludes|preludios|vals(?:es)?|waltzes|walzes|walses|nocturnes|quartets|quatuors|suites|partitas|minuets|menuets|fugues|galopes|esquisses|arabesken|arabesques|miniatures|studettes|studies|etudes|estudios|exercises|exercices|monferrine|monferine|landler|landlers|basses dances"
    if re.match(r'^\d+\s+(?:[^,]*\s)?(?:'+plural+r')(?:\s|,|$)',normalized):
        m=re.match(r'^(\d+)\s+',original);n=m[1];old=zh
        zmatch=re.match(r'^'+re.escape(n)+r'\s*(.+)$',zh)
        if zmatch and not re.match(r'首|个|第|幅|名|项|把|支|台|部',zmatch[1]):
            classifier='项' if re.search(r'\bexercices\b|\bexercises\b',normalized) else '首'
            zh=n+classifier+zmatch[1]
        if old!=zh:reasons.append('源题开头明确为曲目数量，补量词以区分作品号及乐章序号。')
    zh=re.sub(r'首\s*首','首',zh)
    zh=re.sub(r'舞曲舞曲','舞曲',zh)
    if reasons and zh!=outer(row['zh']):return {'zh':zh,'status':'reference','reason':' '.join(dict.fromkeys(reasons))}
    return None
