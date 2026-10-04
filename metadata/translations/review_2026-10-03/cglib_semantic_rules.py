"""Conservative musical-title grammar and contextual draft repairs.

This module does not translate arbitrary prose.  A reference result requires
the *entire* title (apart from an exact source attribution) to be consumed by
the checked grammar.  Local repairs of a draft retain its machine status.
Source identity, original text, names, and catalogue numbers are never guessed.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from functools import lru_cache

HAN = re.compile(r"[\u3400-\u9fff]")
NUMBER = r"(?:\d+(?:[/-]\d+)*(?:[a-z])?|[IVXLCDM]+)"
OPUS = re.compile(r"(?<!\w)(?:op(?:us)?|oeuv(?:re)?|œuv(?:re)?)\s*[.:：]?\s*(" + NUMBER + r")(?!\w)", re.I)
SERIAL = re.compile(r"(?<!\w)(?:no(?:s)?|nr|n[º°]|n)\s*[.°º]?\s*(" + NUMBER + r")(?!\w)", re.I)

# Checked music vocabulary, scoped to titles; bare major/minor and note names
# are deliberately absent.  Their meaning requires a complete key expression.
EXTRA_TERMS = {
    "airs": "曲调", "air varie": "曲调变奏", "air varié": "曲调变奏",
    "airs varies": "曲调变奏集", "airs variés": "曲调变奏集",
    "air variato": "曲调变奏", "andantino mosso": "稍活跃的小行板",
    "allegro moderato": "中速快板", "allegro ma non troppo": "快板，但不太快",
    "allegretto moderato": "中速小快板", "andante moderato": "中速行板",
    "andante con moto": "流动的行板", "allegretto con moto": "流动的小快板",
    "allegro con brio": "有活力的快板", "largo maestoso": "庄严的广板",
    "poco andante": "稍行板", "poco adagio": "稍柔板", "un poco allegro": "稍快的快板",
    "slur studies": "连音练习", "slur exercises": "连音练习",
    "string crossing": "换弦", "parallel octaves": "平行八度",
    "scales": "音阶", "arpeggio": "琶音", "arpeggios": "琶音",
    "studies": "练习曲", "études": "练习曲", "etudes": "练习曲",
    "estudios": "练习曲", "estudi": "练习曲", "esercizi": "练习",
    "exercices": "练习", "ejercicios": "练习", "exercises": "练习",
    "lessons": "课题", "leçons": "课题", "lezioni": "课题",
    "petits pièces": "小品", "petites pièces": "小品", "petites pieces": "小品", "petits pieces": "小品",
    "petits morceaux": "小品", "small pieces": "小品", "little pieces": "小品",
    "piezas": "乐曲", "pièces": "乐曲", "pieces": "乐曲", "morceaux": "乐曲",
    "pezzi": "乐曲", "stücke": "乐曲", "stucke": "乐曲",
    "rondos": "回旋曲", "brillants": "华丽", "brilliants": "华丽",
    "brillantes": "华丽", "brilliant": "华丽", "brillanti": "华丽",
    "contre-danses": "对舞曲", "contredanses": "对舞曲", "contredanse": "对舞曲",
    "ecossaise": "苏格兰舞曲", "ecossaises": "苏格兰舞曲", "écossaise": "苏格兰舞曲",
    "écossaises": "苏格兰舞曲", "ecossaisses": "苏格兰舞曲",
    "sérénade": "小夜曲", "serenades": "小夜曲", "sérénades": "小夜曲",
    "nocturnes": "夜曲", "minuetti": "小步舞曲", "menuets": "小步舞曲",
    "menuette": "小步舞曲", "menuetten": "小步舞曲", "mazurkas": "玛祖卡",
    "polonaises": "波兰舞曲", "valses": "圆舞曲", "waltzes": "圆舞曲",
    "valsas": "圆舞曲", "divertimenti": "嬉游曲", "divertissement": "嬉游曲",
    "divertissements": "嬉游曲", "divertimentos": "嬉游曲",
    "ricercar": "里切尔卡尔", "ricercare": "里切尔卡尔", "ricercari": "里切尔卡尔",
    "sicilliano": "西西里舞曲", "ländler": "兰德勒舞曲",
    "concerto": "协奏曲", "concertino": "小协奏曲", "overtures": "序曲",
    "ouverture": "序曲", "ouvertures": "序曲", "sinfonia": "交响曲",
    "chorale": "众赞歌", "choral": "众赞歌", "hymne": "赞歌",
    "spagnoletta": "斯帕尼奥莱塔舞曲", "maxixe": "马希谢舞曲",
    "branle": "布朗勒舞曲", "bransle": "布朗勒舞曲", "branle gay": "欢快的布朗勒舞曲",
    "branle simple": "简易布朗勒舞曲", "tiento": "蒂恩托", "tientos": "蒂恩托曲集",
    "giga": "吉格舞曲", "gigas": "吉格舞曲", "courante": "库朗特舞曲",
    "corrente": "库朗特舞曲", "bourrée": "布列舞曲", "bourree": "布列舞曲",
    "passacaille": "帕萨卡利亚", "passacaglia": "帕萨卡利亚",
    "passacaglias": "帕萨卡利亚", "almain": "阿勒曼德舞曲", "alman": "阿勒曼德舞曲",
    "canarie": "卡纳里舞曲", "canario": "卡纳里舞曲", "canarios": "卡纳里舞曲",
    "aubade": "晨歌", "petenera": "佩特内拉", "peteneras": "佩特内拉",
    "larghetto": "小广板", "rag": "拉格泰姆", "sicilienne": "西西里舞曲",
    "saltarello": "萨尔塔雷洛舞曲", "tyrolienne": "蒂罗尔舞曲",
    "polaca": "波兰舞曲", "polacca": "波兰舞曲", "gigue": "吉格舞曲",
    "granadinas": "格拉纳迪纳斯", "melodia": "旋律", "melodía": "旋律",
    "alleluia": "哈利路亚", "hallelujah": "哈利路亚", "melodies": "旋律",
    "operatic melodies": "歌剧旋律", "national": "民族", "melody": "旋律",
    "suites": "组曲", "suite espagnole": "西班牙组曲", "suite espanola": "西班牙组曲",
    "suite española": "西班牙组曲", "danse": "舞曲", "danses": "舞曲",
    "danze": "舞曲", "dances": "舞曲", "danza": "舞曲", "danzas": "舞曲",
    "instrumental pieces": "器乐曲", "complete works": "作品全集",
    "collected works": "作品集", "works": "作品", "collection": "曲集",
    "recueil": "曲集", "album": "曲集", "albums": "曲集",
    "guitar albums": "吉他曲集", "guitar skole": "吉他教程", "guitar-skole": "吉他教程",
    "méthode": "教程", "methode": "教程", "método": "教程", "metodo": "教程",
    "méthode complète": "完整教程", "méthode compléte": "完整教程",
    "methode complete": "完整教程", "nouvelle methode": "新教程",
    "method": "教程", "tutor": "教程", "hand-book": "手册", "handbook": "手册",
    "instructive lessons": "教学课题", "progressive": "渐进", "progressifs": "渐进",
    "progressives": "渐进", "practical": "实用", "complete": "完整",
    "complet": "完整", "completo": "完整", "complète": "完整", "compléte": "完整",
    "nouvelle": "新", "nuevo": "新", "nuovo": "新", "brève": "短小",
    "faciles": "简易", "facile": "简易", "facili": "简易", "faciles et tres utiles": "简易且实用",
    "exercices faciles et tres utiles": "简易且实用的练习",
    "morceaux agreables non difficiles": "悦耳的简易乐曲",
    "petites pieces non difficiles": "简易小品", "petites pièces non difficiles": "简易小品",
    "non difficiles": "简易", "non difficile": "简易", "favorite": "精选",
    "favored": "精选", "favourite": "精选", "favorites": "珍爱之曲", "les favorites": "珍爱之曲",
    "guitare": "吉他", "guitares": "吉他", "guitarre": "吉他", "guitarra": "吉他",
    "guitarras": "吉他", "guitarren": "吉他", "guitar": "吉他", "guitars": "吉他",
    "classical guitar": "古典吉他", "spanish guitar": "西班牙吉他",
    "guitarra espanola": "西班牙吉他", "guitarra española": "西班牙吉他",
    "violin": "小提琴", "violon": "小提琴", "violino": "小提琴",
    "violins": "小提琴", "violons": "小提琴", "viola": "中提琴",
    "violoncello": "大提琴", "violoncelle": "大提琴", "cello": "大提琴",
    "flute": "长笛", "flûte": "长笛", "flauto": "长笛", "piano": "钢琴",
    "mandolin": "曼陀林", "mandolins": "曼陀林", "lute": "鲁特琴",
    "theorbo": "西奥伯琴", "vihuela": "维乌埃拉琴", "tab": "六线谱",
    "tablature": "指法谱", "score": "总谱", "parts": "分谱",
    "book": "册", "volume": "卷", "vol": "卷", "part": "部分",
    "cahier": "册", "heft": "册", "livre": "册", "movement": "乐章",
    "and": "与", "et": "与", "und": "与", "y": "与", "from": "选自",
    "for": "为", "pour": "为", "per": "为", "para": "为", "für": "为",
    "by": "由", "arranged": "改编", "arrangement": "改编", "arrangements": "改编",
    "arr": "改编", "arranged for": "改编为", "accompaniment": "伴奏",
    "accompagnement": "伴奏", "with": "与", "avec": "与", "avec accompagnement": "伴奏",
    "solo": "独奏", "seule": "独奏", "seul": "独奏", "in an easy style": "以简易风格",
    "for the guitar": "为吉他而作", "for guitar": "为吉他而作",
    "pour la guitare": "为吉他而作", "para guitarra": "为吉他而作",
    "per chitarra": "为吉他而作", "guitar pieces": "吉他乐曲", "lute suite": "鲁特琴组曲",
    "grand": "大型", "grande": "大型", "gran": "大型", "grandes": "大型",
    "deux": "二", "huit": "八", "seis": "六", "sei": "六", "sieben": "七",
    "drei": "三", "vier": "四", "fünf": "五", "fuenf": "五", "sechs": "六",
    "zwei": "二", "ocho": "八", "nueve": "九", "diez": "十", "doce": "十二",
    "sei": "六", "dodici": "十二", "tre": "三", "quattro": "四", "cinque": "五",
    "dieci": "十", "veinte": "二十", "twenty four": "二十四", "twenty-four": "二十四",
    "bis": "bis", "ter": "ter", "1st": "第一", "2nd": "第二", "3rd": "第三",
    "slurs with the first finger": "第一指连音练习",
    "lo scherzo": "谐谑曲", "la melanconia": "忧郁", "l'amoroso": "多情者",
    "l'armonia": "和谐", "l'allegria": "欢乐", "la risoluzione": "决心",
}

ARTICLES = {"a", "an", "the", "de", "des", "du", "d", "di", "da", "del", "della", "le", "la", "les", "lo", "il", "i", "in", "en"}
KEY_NOTE = {"do": "C", "ut": "C", "ré": "D", "re": "D", "mi": "E", "fa": "F", "sol": "G", "la": "A", "si": "B"}
KEY_RE = re.compile(r"(?<![\w])(?P<note>[A-G]|do|ut|ré|re|mi|fa|sol|la|si)\s*[- ]?\s*(?P<acc>sharp|flat|diesis|bemolle|dièse|bémol|sostenido|bemol|#|♯|♭)?\s*[- ]?\s*(?P<mode>major|minor|majeur|mineur|mayor|menor|maggiore|minore|dur|moll)(?!\w)", re.I)
NOTE_ONLY_RE = re.compile(r"(?<!\w)(?:in|en)\s+([A-G])(?:\s*([#♯♭]|sharp|flat))?(?!\w)", re.I)


def key_zh(match):
    note = match.group('note')
    note = KEY_NOTE.get(note.casefold(), note.upper())
    accidental = match.group('acc') or ''
    prefix = ('降' if accidental.casefold() in {'flat', 'bemolle', 'bémol', 'bemol', '♭'} else '升') if accidental else ''
    mode = '小调' if match.group('mode').casefold() in {'minor', 'mineur', 'menor', 'minore', 'moll'} else '大调'
    return prefix + note + mode


# The 2026-10-03 review uses complete title clauses, rather than arbitrary
# translation-service output. Phrase meanings are literal reference readings;
# proper-name and catalogue slots preserve their exact source spelling.
MUSIC = {
    'preludio':'前奏曲', 'preludios':'前奏曲', 'preludes':'前奏曲',
    'préludes':'前奏曲', 'prélude':'前奏曲', 'prelude':'前奏曲',
    'pavana':'帕凡舞曲', 'pavanas':'帕凡舞曲', 'pavane':'帕凡舞曲', 'pavan':'帕凡舞曲',
    'nocturne':'夜曲', 'nocturno':'夜曲', 'notturno':'夜曲',
    'barcarolle':'船歌', 'barcarola':'船歌', 'barcarole':'船歌',
    'humoresque':'幽默曲', 'impromptu':'即兴曲', 'tarantella':'塔兰泰拉舞曲',
    'tarantelle':'塔兰泰拉舞曲', 'ciacona':'恰空', 'ciaccona':'恰空',
    'chacona':'恰空', 'chaconne':'恰空', 'chaconna':'恰空', 'chaccone':'恰空',
    'estudio':'练习曲', 'estudios':'练习曲', 'study':'练习曲', 'etude':'练习曲',
    'étude':'练习曲', 'lecon':'课题', 'leçon':'课题', 'lecons':'课题',
    'ejercicio':'练习', 'ejercicios':'练习', 'exercise':'练习',
    'menuett':'小步舞曲', 'minueto':'小步舞曲', 'minuet':'小步舞曲',
    'minuetto':'小步舞曲', 'menuetto':'小步舞曲', 'menuet':'小步舞曲',
    'berceuse':'摇篮曲', 'wiegenlied':'摇篮曲', 'wiegenliedchen':'小摇篮曲',
    'canción de cuna':'摇篮曲', 'cancion cuna':'摇篮曲', 'cancion de cuna':'摇篮曲',
    'cavatina':'卡瓦蒂纳', 'canon':'卡农', 'ballet':'芭蕾舞曲', 'ballade':'叙事曲',
    'ballad':'叙事歌', 'song':'歌曲', 'songs':'歌曲', 'lied':'歌曲', 'lieder':'歌曲',
    'fantasia':'幻想曲', 'fantasía':'幻想曲', 'fantasie':'幻想曲', 'fantasie':'幻想曲',
    'fantaisie':'幻想曲', 'fantasy':'幻想曲', 'phantasia':'幻想曲', 'phantasie':'幻想曲',
    'fuga':'赋格', 'fugue':'赋格', 'fughetta':'小赋格', 'fugueta':'小赋格',
    'sonata':'奏鸣曲', 'sonatas':'奏鸣曲', 'sonate':'奏鸣曲', 'sonates':'奏鸣曲',
    'sonatina':'小奏鸣曲', 'sonatine':'小奏鸣曲', 'sonatinas':'小奏鸣曲',
    'gavota':'加沃特舞曲', 'gavotte':'加沃特舞曲', 'gavota choros':'加沃特肖罗曲',
    'schottische':'肖蒂什舞曲', 'schottisch':'肖蒂什舞曲', 'schotisch':'肖蒂什舞曲',
    'bourée':'布列舞曲', 'gique':'吉格舞曲', 'gigue':'吉格舞曲',
    'allemande':'阿勒曼德舞曲', 'almande':'阿勒曼德舞曲', 'alemana':'阿勒曼德舞曲',
    'angloise':'英国舞曲', 'anglaise':'英国舞曲', 'galliard':'加利亚德舞曲',
    'gallardas':'加利亚德舞曲', 'gaillarde':'加利亚德舞曲',
    'blues':'布鲁斯', 'ragtime':'拉格泰姆', 'polka':'波尔卡', 'tango':'探戈', 'tangos':'探戈',
    'rumba':'伦巴', 'samba':'桑巴', 'choro':'肖罗', 'choros':'肖罗', 'chorinho':'小肖罗',
    'mazurka':'玛祖卡舞曲', 'mazurkas':'玛祖卡舞曲', 'jota':'霍塔舞曲',
    'fandango':'凡丹戈舞曲', 'fandangos':'凡丹戈舞曲', 'fandanguillo':'小凡丹戈舞曲',
    'malagueña':'马拉加风格舞曲', 'malaguena':'马拉加风格舞曲',
    'zapateado':'萨帕特阿多舞曲', 'sevillanas':'塞维利亚舞曲',
    'alegrias':'阿莱格里亚斯', 'alegrías':'阿莱格里亚斯', 'bulerias':'布莱里亚斯',
    'bulerías':'布莱里亚斯', 'cueca':'奎卡舞曲', 'zamba':'赞巴舞曲',
    'pericon':'佩里孔舞曲', 'furiante':'富里安特舞曲', 'furiant':'富里安特舞曲',
    'habanera':'哈巴涅拉舞曲', 'españoleta':'西班牙小舞曲', 'espanoleta':'西班牙小舞曲',
    'villancico':'维良西科', 'zarabanda':'萨拉班德舞曲', 'sarabande':'萨拉班德舞曲',
    'madrigal':'牧歌', 'intermezzo':'间奏曲', 'rondo':'回旋曲', 'rondeau':'回旋曲',
    'rondoletto':'小回旋曲', 'rondino':'小回旋曲', 'romanze':'浪漫曲',
    'romanza':'浪漫曲', 'romance':'浪漫曲', 'serenata':'小夜曲', 'serenade':'小夜曲',
    'waltz':'圆舞曲', 'valse':'圆舞曲', 'vals':'圆舞曲', 'valsa':'圆舞曲',
    'walzer':'圆舞曲', 'valzer':'圆舞曲', 'wals':'圆舞曲',
    'marcia':'进行曲', 'march':'进行曲', 'marche':'进行曲', 'marsch':'进行曲',
    'capricho':'随想曲', 'caprice':'随想曲', 'capriccio':'随想曲',
    'allegro':'快板', 'allegretto':'小快板', 'allegro spiritoso':'活泼的快板',
    'andante':'行板', 'andantino':'小行板', 'adagio':'柔板', 'largo':'广板',
    'lento':'慢板', 'moderato':'中板', 'vivace':'活板', 'vivace assai':'很活跃地',
    'cantabile':'如歌地', 'tempo di marcia':'进行曲速度', 'tempo di mazurka':'玛祖卡速度',
    'allegro non troppo':'不太快的快板', 'andante lento':'缓慢的行板',
    'andante largo':'宽广的行板', 'andante sentimental':'感伤的行板',
    'andante sentimentale':'感伤的行板', 'grave':'庄板', 'loure':'卢尔舞曲',
    'badinage':'诙谐曲', 'bagatela':'小品', 'bagatelle':'小品', 'arabesque':'阿拉伯风格曲',
    'introduction':'引子', 'introduzione':'引子', 'introduccion':'引子',
    'introducción':'引子', 'overture':'序曲', 'toccata':'托卡塔', 'toccate':'托卡塔',
    'elegie':'悲歌', 'élégie':'悲歌', 'elegy':'悲歌', 'elegia':'悲歌',
    'reverie':'遐想', 'rêverie':'遐想', 'variations':'变奏曲', 'variation':'变奏',
    'variazioni':'变奏曲', 'variazione':'变奏', 'variaciones':'变奏曲',
    'theme and variations':'主题与变奏', 'tema con variazioni':'主题与变奏',
    'thème varié':'主题变奏曲', 'theme varié':'主题变奏曲', 'theme varie':'主题变奏曲',
    'theme':'主题', 'thème':'主题', 'tema':'主题', 'thema':'主题',
    'divertimento':'嬉游曲', 'trio':'三重奏', 'duo':'二重奏', 'duet':'二重奏',
    'menuet et trio':'小步舞曲与三声中部', 'minuet and trio':'小步舞曲与三声中部',
    'menuet trio':'小步舞曲与三声中部', 'minuetto con trio':'小步舞曲与三声中部',
    'duets':'二重奏', 'duetto':'二重奏', 'duetti':'二重奏', 'dúo':'二重奏',
    'trios':'三重奏', 'quartet':'四重奏', 'quatuor':'四重奏',
    'quartetto':'四重奏', 'quintet':'五重奏', 'quintetto':'五重奏',
    'suite':'组曲', 'partita':'组曲', 'parthia':'组曲', 'sinfonia':'交响曲',
    'symphony':'交响曲', 'concerto':'协奏曲', 'concert':'音乐会', 'concertante':'协奏性',
    'finale':'终曲', 'coda':'尾声', 'pot-pourri':'集成曲', 'pot pourri':'集成曲',
    'quodlibet':'混成曲', 'invention':'创意曲', 'minore':'小调段', 'maggiore':'大调段',
    'grand solo':'大型独奏曲', 'solo de guitarra':'吉他独奏曲',
    'concerto for guitar':'吉他协奏曲', 'guitar sonata':'吉他奏鸣曲',
    'exercices très faciles':'极简易练习', 'exercices tres faciles':'极简易练习',
    'leçons progressives':'渐进课题', 'lecons progressives':'渐进课题',
    'estudio de concierto':'音乐会练习曲', 'estudios de concierto':'音乐会练习曲',
    'estudio en arpegio':'琶音练习曲', 'estudio de ligados':'连音练习曲',
    'estudio para ambos manos':'双手练习曲', 'estudio vals':'圆舞曲练习曲',
    'variaciones sobre un tema':'主题变奏曲', 'variations sur un thème original':'原创主题变奏曲',
    'variations sur un theme original':'原创主题变奏曲',
    'petites pièces faciles':'简易小品', 'pièces faciles':'简易乐曲', 'piezas fáciles':'简易乐曲',
    'petites pieces faciles':'简易小品', 'pieces faciles':'简易乐曲', 'piezas faciles':'简易乐曲',
    'guitar school':'吉他教程', 'guitar skole':'吉他教程', 'guitar-skole':'吉他教程',
    'guitarre schule':'吉他教程', 'nouvelle méthode':'新教程', 'new method':'新教程',
    'guitar method':'吉他教程', 'método para guitarra':'吉他教程',
    'method for guitar':'吉他教程', 'complete method':'完整教程',
    'tremolo variation':'轮指变奏', 'tremolo piece':'轮指乐曲',
    '1st movement':'第1乐章', '2nd movement':'第2乐章', '3rd movement':'第3乐章',
    'first mnt':'第1乐章', 'first mov':'第1乐章', 'second mov':'第2乐章',
    'third mov':'第3乐章', 'first movement':'第1乐章',
    'original for lute':'原作为鲁特琴而作', 'all parts':'全部分谱',
    'complete parts':'全部分谱', 'complete score':'完整总谱', 'complete works':'作品全集',
    'score and parts':'总谱与分谱', 'melancholy':'忧郁', 'melancolia':'忧郁', 'mélancolie':'忧郁',
    'guitar solo':'吉他独奏', 'guitar duo':'吉他二重奏', 'guitar quartet':'吉他四重奏',
    'guitar trio':'吉他三重奏', 'duet for two guitars':'双吉他二重奏',
    'air with variations':'曲调与变奏', 'air varié':'曲调变奏曲',
    'romance sans paroles':'无言浪漫曲', 'melodie':'旋律', 'souvenir':'回忆',
}
MUSIC.update({
    'violine':'小提琴','alto':'中提琴','chitarra':'吉他','mandolino':'曼陀林',
    'piano forte':'钢琴','piano-forte':'钢琴','pianoforte':'钢琴','mandola':'曼多拉琴',
    'flutes':'长笛','lyre':'里拉琴','violoncell':'大提琴','cithara':'西塔拉琴',
    'national airs of different nations':'各国民族曲调','national airs':'民族曲调',
    'spanish dance':'西班牙舞曲','spanish dances':'西班牙舞曲',
    'russian dance':'俄罗斯舞曲','russian songs':'俄罗斯歌曲','italian air':'意大利曲调',
    'venetian air':'威尼斯曲调','portuguese air':'葡萄牙曲调','austrian air':'奥地利曲调',
    'german air':'德国曲调','french air':'法国曲调','scotch air':'苏格兰曲调',
    'irish air':'爱尔兰曲调','english air':'英国曲调','swiss air':'瑞士曲调',
    'german dance':'德国舞曲','hungarian dance':'匈牙利舞曲','russian song':'俄罗斯歌曲',
    'themes with variations':'主题与变奏曲','thêmes avec variations':'主题与变奏曲',
    'thème avec variations':'主题与变奏曲','thème et variations':'主题与变奏曲',
    'arpeggio study':'琶音练习曲','slur study':'连音练习曲','tremolo':'轮指',
    'fuga y misterio':'赋格与神秘','contre danses':'对舞曲','contre-danses':'对舞曲',
    'funèbre':'葬礼','funebre':'葬礼','marche funebre':'葬礼进行曲',
    'marche funèbre':'葬礼进行曲','march funebre':'葬礼进行曲',
    'string guitar':'弦吉他','7 string guitar':'七弦吉他',
    '7-string guitar':'七弦吉他','7 cordes':'七弦','sept cordes':'七弦',
    'voix':'声乐','canto':'声乐','voice':'声乐','soprano':'女高音',
    'grade':'级别','lite':'简易版','alt. take':'另一次录制',
    'take 1':'第1次录制','take 2':'第2次录制','bonus track':'附加曲目',
    'original':'原作','transcription':'移植','transcriptions':'移植曲集',
    'melodia popular catalana':'加泰罗尼亚民间旋律','melodía popular catalana':'加泰罗尼亚民间旋律',
    'melodia campera':'乡野旋律','estilo criollo':'克里奥尔风格曲',
    'tempos':'速度','theme from':'主题选自','mov':'乐章','mov.':'乐章',
    'partie':'部分','part':'部分','parte':'部分','satz':'乐章',
    'guitar part':'吉他声部','flute part':'长笛声部','violin part':'小提琴声部',
    'brillantes':'华丽','sentimental':'感伤','apasionada':'热情',
    'capricciosa':'任性','polonaise':'波兰舞曲','sonate brillante':'华丽奏鸣曲',
    'a guitar duet':'吉他二重奏','easy pieces':'简易乐曲','little preludes':'小前奏曲',
    'tendres':'温柔','tendrement':'温柔地','varié':'变奏','varie':'变奏',
    'v1':'版本1','v2':'版本2','v3':'版本3','cah':'册','ca':'约',
    'tarentella':'塔兰泰拉舞曲','romanesca':'罗曼内斯卡','balleto':'芭蕾舞曲',
    'balletto':'芭蕾舞曲','badinerie':'诙谐曲','padouana':'帕凡舞曲',
    'recercar':'里切尔卡尔','ricercata':'里切尔卡尔','intrada':'开场曲',
    'anglois':'英国舞曲','tientos':'蒂恩托曲集',
    'duos':'二重奏','thême':'主题','thêmes':'主题','themes':'主题',
    'leccion':'课题','lección':'课题','lecciones':'课题','etuden':'练习曲',
    'gitarre':'吉他','guitarres':'吉他','cordes':'弦','corde':'弦',
    'periodical amusements for the guitar':'吉他定期消遣曲集',
    'amusement du guitariste':'吉他演奏者的消遣曲集',
    'amusement':'消遣曲','amusements':'消遣曲集','potpourri':'集成曲',
    'potpourris':'集成曲','rondeaux':'回旋曲','concertant':'协奏性',
    'cavatine':'卡瓦蒂纳','aria':'咏叹调','arias':'咏叹调','a tre':'三声部',
    'facsimile tablature':'指法谱影印本','facsimile':'影印本','manuscript':'手稿',
    'première partie':'第1部分','premiere partie':'第1部分',
    'première sérénade':'第1小夜曲','deuxième':'第二','troisième':'第三',
    'selections':'选曲','selected pieces':'精选乐曲','morceaux choisis':'精选乐曲',
    'opera':'歌剧','opéra':'歌剧','opéras':'歌剧','operas':'歌剧','oper':'歌剧',
    'opern-revue':'歌剧选曲集','opern revue':'歌剧选曲集','opern':'歌剧',
    'operatic':'歌剧风格','morceaux de salon':'沙龙乐曲','guitariste':'吉他演奏者',
    'ausgewählte melodien für die guitar':'吉他旋律精选',
    'ausgewählte melodien für die guitare':'吉他旋律精选',
    'sur des motifs':'根据主题','sur les motifs':'根据主题',
    'fantasy on themes from':'根据主题而作的幻想曲，选自',
    'fantaisie sur les thêmes favoris':'精选主题幻想曲',
    'fantaisie sur les thèmes favoris':'精选主题幻想曲',
    'fantaisie sur un thème':'根据主题而作的幻想曲',
    'fantaisie sur un theme':'根据主题而作的幻想曲',
    'variations sur un thème':'主题变奏曲','variations sur un theme':'主题变奏曲',
    'thème russe':'俄罗斯主题','theme russe':'俄罗斯主题',
    'italian melodies':'意大利旋律','italien':'意大利风格','italian':'意大利风格',
    'danse espagnole':'西班牙舞曲','danzas espanolas':'西班牙舞曲',
    'danzas españolas':'西班牙舞曲','danza española':'西班牙舞曲',
    'capriccio diabolico':'魔鬼随想曲','sonata giocosa':'诙谐奏鸣曲',
    'viola da gamba':'维奥尔琴','violon basse':'低音小提琴',
    'ad libitum':'可选','avec soudine':'弱音演奏','string':'弦',
    'with capo on':'变调夹夹第','sans basse':'无低音伴奏',
    'f.':'f.','rda':'Rda','live':'现场版','intro':'引子',
    'theme from 2nd movement':'第2乐章主题','complete_parts':'全部分谱',
    'sans paroles':'无言','bagatelles':'小品','fantasiestücke':'幻想小品',
    'recreations':'音乐消遣小品','miniatures':'微型曲','studettes':'小练习曲',
    'arabe':'阿拉伯风格','andaluza':'安达卢西亚风格','española':'西班牙风格',
    'espanola':'西班牙风格','spagnola':'西班牙风格',
    'tendre':'温柔','scherzo':'谐谑曲','scherzo-vals':'谐谑圆舞曲',
    'tempo di valse':'圆舞曲速度','allegretto grazioso':'优美的小快板',
    'lento espressivo':'富于表情的慢板','andante espressivo':'富于表情的行板',
    'allegro moderato':'中速快板','allegretto mosso':'稍活跃的小快板',
    'petitsduos concertans':'协奏性小二重奏','petits duos concertans':'协奏性小二重奏',
    'barden-klange':'吟游诗人的歌声','barden-klänge':'吟游诗人的歌声',
    'bardenklänge':'吟游诗人的歌声','bardenklange':'吟游诗人的歌声',
    '7 string guitar':'7弦吉他','7-string guitar':'7弦吉他',
    'take five':'Take Five',
    'poco allegretto':'稍小快板',
    'gavotta':'加沃特舞曲',
    'petits duos':'小二重奏','duo de guitares':'吉他二重奏',
    'rondeau de concert':'音乐会回旋曲','rondo de concert':'音乐会回旋曲',
    'allegro de sonate':'奏鸣曲快板乐章','waltz musette':'风笛圆舞曲',
    'vingt-quatre':'二十四','vingt quatre':'二十四',
    'violin sonata':'小提琴奏鸣曲', 'violin concerto':'小提琴协奏曲',
    'slap':'拍击标记','strum':'扫弦标记','tap':'敲击标记','horses':'马匹标记',
    'same':'同题标记','extract':'节选','fragment':'片段',
    'bass':'低音声部','ending lick':'结尾乐句',
    'morceaux de concert':'音乐会乐曲','con':'与',
    'arranged with variations':'改编并加变奏',
})

FRENCH_KEY = re.compile(r'(?<!\w)([a-g]|do|ut|ré|re|mi|fa|sol|la|si)\s*(bémol|bemol|b|dièse|diese|#|♯|♭)?\s+(majeur|mineur|major|minor|mayor|menor|maggiore|minore|majo|min|maj)(?!\w)',re.I)

def normalize_key(m):
    note=KEY_NOTE.get(m[1].casefold(),m[1].upper())
    acc=m[2] or ''
    mode=m[3].casefold()
    return ('降' if acc.casefold() in {'bémol','bemol','b','♭'} else '升' if acc else '')+note+('小调' if mode in {'mineur','minor','menor','minore','min'} else '大调')

def source_key(text):
    return ''.join(c for c in unicodedata.normalize('NFKD',text) if not unicodedata.combining(c)).casefold()

def normphrase(text):
    text=source_key(text).replace('’',"'").replace('_',' ')
    return re.sub(r'\s+',' ',text).strip(' .!')

def semantic_title(original, phrases=None, terms=None):
    """Closed complete-title translation, with keys/IDs and provenance slots.

    Caller removes an attribution only after a separate exact full-name guard.
    Unknown words make this fail; no service-output confidence shortcut exists.
    """
    text=unicodedata.normalize('NFC',original).replace('_',' ')
    if len(text)>300 or not text.strip(): return None
    slots=[]
    def hold(value):
        slots.append(value); return '\ue000'+str(len(slots)-1)+'\ue001'
    text=re.sub(r'\b(lecon|leçon|leccion|etude|étude|ejercicio|study|preludio|sonate)(?=\d)',r'\1 ',text,flags=re.I)
    text=re.sub(r'(\b(?:minueto|minuet|menuet|prelude|preludio|courante|estudio|etude))\s+([a-g])$',lambda m:m[1]+' '+hold('（原题标记：'+m[2]+'）'),text,flags=re.I)
    # Bare numbers following a named suite/sonata and before a distinct dance
    # or tempo are movement indexes, not the number of separately supplied
    # pieces. This is an explicit musical-title frame in the source catalog.
    if re.search(r'\b(?:suite|sonata|sonate|partita)\b',text,re.I):
        movements='prelude|preludio|allemande|courante|bourree|bouree|bourée|sarabande|menuet|menuett|gigue|marche|allegro|presto|toccata|aria|spirituoso'
        text=re.sub(r'(?<![\w.])([1-9])\s+('+movements+r')(?!\w)',lambda m:hold('第'+m[1]+'乐章')+' '+m[2],text,flags=re.I)
    # Source quotation delimiters explicitly mark a named/incidental title.
    # Keep that full label, without claiming a phonetic or literal explanation.
    text=re.sub(r'[“"]([^“”"]+)[”"]',lambda m:hold('“'+m[1]+'”'),text)
    if re.search(r'(?<!\w)[BH]\s*-?\s*(?:dur|moll)\b',text,re.I):return None
    german_notes={'cis':'升C','des':'降D','dis':'升D','es':'降E','eis':'升E','fes':'降F','fis':'升F','ges':'降G','gis':'升G','as':'降A','ais':'升A','ces':'降C','his':'升B'}
    text=re.sub(r'(?<!\w)('+'|'.join(german_notes)+r')\s*-?\s*(dur|moll)(?!\w)',lambda m:hold(german_notes[m[1].casefold()]+('大调' if m[2].casefold()=='dur' else '小调')),text,flags=re.I)
    text=FRENCH_KEY.sub(lambda m:hold(normalize_key(m)),text)
    text=KEY_RE.sub(lambda m:hold(key_zh(m)),text)
    if re.search(r'(?<!\w)[BH]\s*-?\s*(?:dur|moll)\b',text,re.I):return None
    text=NOTE_ONLY_RE.sub(lambda m:hold(('降' if m[2] in {'flat','♭'} else '升' if m[2] else '')+m[1].upper()+'调'),text)
    # Solfège without an explicit major/minor is retained as a tonal centre.
    text=re.sub(r'(?<!\w)(?:en|in)\s+(Do|Re|Ré|Mi|Fa|Sol|La|Si)(?:\s+(sostenido|bemol))?(?!\w)',lambda m:hold(('升' if m[2]=='sostenido' else '降' if m[2] else '')+KEY_NOTE[m[1].casefold()]+'调'),text,flags=re.I)
    text=re.sub(r'(?<!\w)(WeissSW|SW|BWV|RV|KV|K|L|MS|Hob|D|HWV|WoO|Poulton|App)\s*\.?\s*\d+(?:[/:.-]\d+)*(?:[a-z])?(?!\w)',lambda m:hold(m[0]),text,flags=re.I)
    # A trailing isolated source variant letter is not an English article.
    text=re.sub(r'(?<=\d)\s+([a-z])$',lambda m:' '+hold('（原题标记：'+m[1]+'）'),text)
    text=OPUS.sub(lambda m:hold('作品'+m[1]),text)
    text=SERIAL.sub(lambda m:hold('第'+m[1]+'号'),text)
    # Manuscript locations are provenance, never guessed title translations.
    cities={'Londres':'伦敦','Varsovie':'华沙','Vienne':'维也纳','Dresde':'德累斯顿','Munich':'慕尼黑','Brno':'布尔诺','Moscou':'莫斯科','Wroclaw':'弗罗茨瓦夫'}
    text=re.sub(r'\(\s*(?:Le|Les) manuscrit(?:s)?\s+(?:de |d[’\x27])?([^()]*)\)',lambda m:hold('（'+cities.get(m[1].strip(),m[1].strip())+'手稿）'),text,flags=re.I)
    # Instrument/player and part syntax are translated as a complete phrase.
    inst={'guitar':'吉他','guitare':'吉他','guitarra':'吉他','guitarre':'吉他','guitars':'吉他','guitares':'吉他','guitarras':'吉他','guitarren':'吉他','chitarra':'吉他','piano':'钢琴','pianoforte':'钢琴','piano forte':'钢琴','piano-forte':'钢琴','flute':'长笛','flûte':'长笛','flutes':'长笛','violon':'小提琴','violin':'小提琴','violins':'小提琴','violons':'小提琴','viola':'中提琴','mandolin':'曼陀林','mandolins':'曼陀林','mandolino':'曼陀林','mandolini':'曼陀林','mandoline':'曼陀林','mandola':'曼多拉琴','lute':'鲁特琴','the lute':'鲁特琴'}
    it='|'.join(re.escape(k) for k in sorted(inst,key=len,reverse=True))
    text=re.sub(r'(?<!\w)('+it+r')(?:\s*(?:part|parte|声部)\s*|\s*)([1-9])(?:[ªa])?(?!\w)',lambda m:hold(inst[m[1].casefold()]+'第'+m[2]+'声部'),text,flags=re.I)
    text=re.sub(r'(?<!\w)('+it+r')\s+(?:(?:part|parte|声部)\s+)?([IV]+)(?!\w)',lambda m:hold(inst[m[1].casefold()]+'第'+m[2]+'声部'),text)
    numbers={'two':'二','three':'三','four':'四','deux':'二','trois':'三','zwei':'二','zwey':'二','dos':'二','due':'二'}
    def instrument_count(m):
        instrument=inst[m[2].casefold()]
        classifier='台' if instrument=='钢琴' else '支' if instrument=='长笛' else '把'
        return hold(numbers.get(m[1].casefold(),m[1])+classifier+instrument)
    text=re.sub(r'(?<!\w)(\d+|two|three|four|deux|trois|zwei|zwey|dos|due)\s+('+it+r')(?!\w)(?!\s+(?:pieces|studies|etudes|sonatas|parts|pièces|morceaux|songs)\b)',instrument_count,text,flags=re.I)
    # Full title phrases precede the music clauses; every remaining lexical
    # item must belong to a reviewed musical construction.
    vocabulary=dict(EXTRA_TERMS);vocabulary.update(terms or {});vocabulary.update(MUSIC);vocabulary.update(phrases or {})
    for k in ['for the guitar','for guitar','pour la guitare','para guitarra','per chitarra']:
        vocabulary.pop(k,None)
    # Sinfonia has both operatic-overture and autonomous orchestral senses;
    # the isolated word cannot certify either without a complete source frame.
    vocabulary.pop('sinfonia',None)
    for k in ['i','ii','iii','iv','v','vi','vii','viii','ix','x','major','minor','dur','moll','sharp','flat']:vocabulary.pop(k,None)
    vocabulary={k.casefold():v for k,v in vocabulary.items()}
    vocabulary.update({source_key(k):v for k,v in list(vocabulary.items())})
    vocabulary,pattern=vocabulary_pattern(tuple(sorted(vocabulary.items())))
    text=pattern.sub(lambda m:hold(vocabulary[m[0].casefold()]),text)
    text=re.sub(r'(?<!\w)[IVXLCDM]+(?!\w)',lambda m:hold(m[0]),text)
    text=re.sub(r'(?<!\w)(?:ii|iii|iv|vi|vii|viii|ix|xi|xii)(?!\w)',lambda m:hold(m[0]),text)
    text=re.sub(r'(?<!\w)[A-G](?!\w)',lambda m:hold(m[0]),text)
    allowed=ARTICLES|{'sur','con','una','un','of','on','a','à','aus','der','den','die','das','delle','dello','im','lo','da','dalla','dall','dell','nell','sul','sulle','sulla','sobre','e','ou','mit','par','von','los','las','alla'}
    words=re.findall(r'[^\W\d_]+',text)
    if any(w.casefold() not in allowed for w in words):return None
    # Connectives retain structural meaning; articles carry no Chinese word.
    for p,z in [('sur','根据'),('sobre','根据'),('con','与'),('of','的'),('on','根据'),('aus','选自'),('ou','或'),('mit','与'),('von','由'),('par','由')]:text=re.sub(r'(?<!\w)'+p+r'(?!\w)',z,text,flags=re.I)
    text=re.sub(r'(?<!\w)(?:'+ '|'.join(re.escape(k) for k in sorted(allowed,key=len,reverse=True))+r')(?!\w)', '',text,flags=re.I)
    text=re.sub(r'\ue000(\d+)\ue001',lambda m:slots[int(m[1])],text)
    if not HAN.search(text):return None
    text=re.sub(r'\s+',' ',text).strip(' .')
    text=re.sub(r'(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])','',text)
    text=re.sub(r'\s*[,，]\s*','，',text)
    text=re.sub(r'\s*[:：]\s*','：',text)
    # Natural word order for the repeatedly attested full musical patterns.
    text=re.sub(r'(组曲|奏鸣曲|小奏鸣曲|前奏曲|小步舞曲|船歌|赋格|吉格舞曲|回旋曲|二重奏|幻想曲|夜曲|练习曲|小快板|快板|小行板|行板|圆舞曲)\s*([升降]?[A-G](?:大调|小调|调))',r'\2\1',text)
    text=re.sub(r'(小品|乐曲|练习曲|圆舞曲|课题)(渐进|简易|华丽)',r'\2\1',text)
    text=re.sub(r'(?<![\d/.-])((?:\d+|[一二三四五六七八九十]+))\s*(渐进|简易|华丽)?(小品|乐曲|练习曲|圆舞曲|课题|前奏曲|夜曲|小步舞曲|对舞曲|变奏曲)(?!第)',lambda m:m[0] if (m[1].isdigit() and int(m[1])>999) or re.search(r'(?:作品|BWV|RV|KV|K|L|SW|WeissSW|Hob|D|HWV|MS)\s*$',text[:m.start()]) else m[1]+'首'+(m[2] or '')+m[3],text)
    text=re.sub(r'(组曲|奏鸣曲|小奏鸣曲|二重奏)\s+(\d+|[IVXLCDM]+)\s+([升降]?[A-G](?:大调|小调|调))',r'\3第\2号\1',text)
    text=re.sub(r'(组曲|奏鸣曲|小奏鸣曲|二重奏)\s+(第\d+号)\s+([升降]?[A-G](?:大调|小调|调))',r'\3\2\1',text)
    text=polish_reference(text)
    text=re.sub(r'^(作品'+NUMBER+r')\s*[.， ]\s*(.+)$',r'\1：\2',text)
    # Reject malformed title delimiters rather than balancing by deletion.
    if text.count('(')!=text.count(')') or text.count('（')!=text.count('）'):return None
    return text

def polish_reference(text):
    """Format only already established musical meanings, never fill unknowns."""
    genre_names='小品 乐曲 练习曲 奏鸣曲 小奏鸣曲 幻想曲 前奏曲 夜曲 回旋曲 圆舞曲 变奏曲 变奏 组曲 玛祖卡舞曲 玛祖卡 进行曲 集成曲 嬉游曲 课题 教程 小夜曲 悲歌 二重奏 三重奏 四重奏 小赋格 曲调变奏曲 谐谑曲 里切尔卡尔 西西里舞曲 波兰舞曲 加沃特舞曲 布列舞曲 阿勒曼德舞曲 库朗特舞曲 萨拉班德舞曲 吉格舞曲 恰空 帕萨卡利亚 兰德勒舞曲 船歌 小快板 快板 小行板 行板 慢板 柔板 广板 小广板 蒙费里纳舞曲 匈牙利舞曲 苏格兰舞曲 对舞曲 民族曲调 各国民族曲调 旋律 歌曲 舞曲 随想曲 协奏曲 克里奥尔风格曲'.split()
    genre_names += ['小步舞曲'] + [v for v in MUSIC.values() if re.fullmatch(r'[\u3400-\u9fff]+',v) and v.endswith(('舞曲','随想曲','奏鸣曲','协奏曲'))]
    genres='(?:'+'|'.join(re.escape(x) for x in sorted(genre_names,key=len,reverse=True))+')'
    text=re.sub('('+genres+r')(渐进|简易|华丽|感伤)',r'\2\1',text)
    text=re.sub(r'为二把吉他', '为双吉他',text)
    text=re.sub('('+genres+r')为吉他(?:而作)?(?:独奏)?(?![，与或]?\s*(?:(?:[一二三四五六七八九十\d]+(?:把|支|台))?(?:吉他|长笛|小提琴|中提琴|大提琴|钢琴|曼陀林|里拉琴|鲁特琴)))',r'吉他\1',text)
    text=re.sub(r'(?:完整|新)教程为吉他(?:而作)?',lambda m:'吉他'+m[0].split('为')[0],text)
    inst=r'(?:(?:[一二三四五六七八九十\d]+(?:把|支|台))?(?:(?:西班牙|古典)?吉他|长笛|小提琴|中提琴|大提琴|曼陀林|曼多拉琴|里拉琴|鲁特琴|钢琴)|双吉他|声乐|女高音)(?!第)'
    # A complete destination instrumentation is rendered as a Chinese clause.
    def instrument_clause(m):
        instruments=m[1]
        if '或' not in instruments:
            items=re.findall(inst,instruments)
            if len(items)>1:instruments='、'.join(items[:-1])+'与'+items[-1]
        return '（为'+instruments+'而作）'
    text=re.sub(r'为\s*('+inst+r'(?:\s*(?:与|或|，|、)?\s*'+inst+r')*)(?:而作)?',instrument_clause,text)
    text=text.replace('小吉他小品','吉他小品')
    text=re.sub(r'(?<![\d/.-])([一二三四五六七八九十\d]+)\s*((?:大型|小型|小|协奏性|简易|渐进|华丽|感伤|社交)*(?:(?:吉他|鲁特琴|曼陀林)?'+genres+r'|练习|曲调变奏集))',lambda m:m[0] if re.search(r'(?:作品|第|BWV|RV|KV|K|L|D|Poulton|App|WeissSW|SW|Hob|HWV|MS)\s*$',text[:m.start()]) or (m[1].isdigit() and int(m[1])>999) else m[1]+'首'+m[2],text)
    text=re.sub('('+genres+r')(\s*第\d+号)?\s+([升降]?[A-G](?:大调|小调|调))',lambda m:m[3]+m[1]+(m[2] or ''),text)
    text=re.sub(r'(稍|中速|优美的|流动的|稍活跃的|富于表情的)([升降]?[A-G](?:大调|小调|调))('+genres+r')',r'\2\1\3',text)
    text=re.sub(r'(\d+)\s+(吉他|鲁特琴|曼陀林)(小品|乐曲|练习曲|奏鸣曲)',r'\1首\2\3',text)
    text=re.sub(r'(课题)\s*(\d+)(?!\d)',r'第\2课',text)
    text=re.sub(r'(小步舞曲|练习曲|前奏曲|匈牙利舞曲)\s+(\d+)(?![\d/:.-])',r'第\2号\1',text)
    text=re.sub(r'(册|卷|部分)\s*(\d+|[IVXLCDM]+)(?!\w)',r'第\2\1',text)
    text=re.sub(r'教程教程', '教程',text)
    text=re.sub(r'\s+([（(])',r'\1',text)
    text=re.sub(r'([）)])\s+',r'\1',text)
    return text


def title_body(original, composer=''):
    """Strip attribution only when it literally equals this record's source field."""
    text = original.strip()
    if composer:
        literal = re.escape(composer)
        text = re.sub(r'^' + literal + r'\s*[:：,–—-]\s*', '', text, flags=re.I)
        text = re.sub(r'\s+by\s+' + literal + r'\s*$', '', text, flags=re.I)
    return text


@lru_cache(maxsize=8)
def vocabulary_pattern(entries):
    vocabulary = dict(entries)
    alternatives = '|'.join(re.escape(word) for word in sorted(vocabulary, key=lambda t: (-len(t), t)))
    return vocabulary, re.compile(r'(?<![\w])(?:' + alternatives + r')(?![\w])', re.I)


def terminology_grammar(original, terms=None, composer=''):
    """Return a reference only for a complete closed-vocabulary musical title."""
    text = unicodedata.normalize('NFC', title_body(original, composer))
    # No attempt to consume bibliographic prose or unknown names/lyric incipits.
    if len(text) > 350 or '|' in text or '{' in text or '}' in text:
        return None
    # B in German notation can mean B-flat; English titles sometimes also use
    # dur/moll labels.  Without an exact reviewed title this is ambiguous.
    if re.search(r'(?<!\w)[BH]\s*-?\s*(?:dur|moll)\b', text, re.I):
        return None
    text = re.sub(r'^A\s+(?!(?:major|minor|dur|moll|and|in)\b)(?=[A-Za-z])', '', text)
    vocabulary = dict(terms or {})
    # Instrument/roman contexts are not automatically title vocabulary.
    for word in ('major', 'minor', 'dur', 'moll', 'maggiore', 'minore', 'sharp', 'flat', 'i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii', 'ix', 'x'):
        vocabulary.pop(word, None)
    vocabulary.update(EXTRA_TERMS)
    vocabulary = {k.casefold(): v for k, v in vocabulary.items()}
    slots = []
    def slot(value):
        slots.append(value)
        return '\ue000' + str(len(slots)-1) + '\ue001'
    text = KEY_RE.sub(lambda m: slot(key_zh(m)), text)
    text = NOTE_ONLY_RE.sub(lambda m: slot(('降' if m.group(2) in {'flat', '♭'} else '升' if m.group(2) else '') + m.group(1).upper() + '调'), text)
    text = OPUS.sub(lambda m: slot('作品' + m.group(1)), text)
    text = SERIAL.sub(lambda m: slot('第' + m.group(1) + '号'), text)
    text = re.sub(r'(?<!\w)(?:BWV|RV|KV|K|Hob|D|SWV|HWV|WoO|MWV|S)\s*\.?\s*\d+(?:[/:.-]\d+)*(?:[a-z])?', lambda m: slot(m.group(0)), text, flags=re.I)
    # Roman numerals are identifiers, not words.  Only uppercase numerals are
    # accepted; lowercase Italian articles must not become random piece numbers.
    text = re.sub(r'(?<!\w)[IVXLCDM]+(?!\w)', lambda m: slot(m.group(0)), text)
    vocabulary, pattern = vocabulary_pattern(tuple(sorted(vocabulary.items())))
    text = pattern.sub(lambda m: slot(vocabulary[m.group(0).casefold()]), text)
    # A bare note letter is not evidence of a major key; retain it literally.
    text = re.sub(r'(?<!\w)[A-G](?!\w)', lambda m: slot(m.group(0)), text)
    words = re.findall(r'[^\W\d_]+', text, flags=re.UNICODE)
    if any(word.casefold() not in ARTICLES for word in words):
        return None
    text = re.sub(r"(?<!\w)(?:" + '|'.join(sorted(ARTICLES, key=len, reverse=True)) + r")(?!\w)'?", '', text, flags=re.I)
    text = re.sub(r'\ue000(\d+)\ue001', lambda m: slots[int(m.group(1))], text)
    if not HAN.search(text):
        return None
    # Counts precede classifiers in Chinese.  A catalogue/work number is not
    # the number of pieces, so never append 首 to Op./BWV/etc. numeric tokens.
    text = re.sub(r'(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])', '', text)
    count_pattern = r'(\d+|[一二三四五六七八九十]+)\s*(?=(?:(?:渐进|简易|华丽|小型|小|大型|精选|吉他)*(?:小品|乐曲|练习曲|圆舞曲|夜曲|小步舞曲|回旋曲|玛祖卡|曲调|课题|歌曲|波兰舞曲|前奏曲|随想曲|对舞曲|二重奏)))'
    def count_classifier(match):
        prefix = text[:match.start()]
        if match.group(1).isdigit() and int(match.group(1)) > 999:
            return match.group(0)
        if re.search(r'(?:作品|BWV|RV|KV|K|Hob|D|SWV|HWV|WoO|MWV|S)\s*$', prefix, re.I):
            return match.group(0)
        return match.group(1) + '首'
    text = re.sub(count_pattern, count_classifier, text)
    text = re.sub(r'(?<=[A-Z\d])\s+(?=[大小]调)', '', text)
    text = re.sub(r'\b(作品|第)\s+', r'\1', text)
    text = re.sub(r'\s*[,，]\s*', '，', text)
    text = re.sub(r'\s*[:：]\s*', '：', text)
    text = re.sub(r'\s+', ' ', text).strip(' .。')
    genre = r'(?:小快板|小行板|快板|行板|柔板|广板|小广板|中板|奏鸣曲|小奏鸣曲|前奏曲|里切尔卡尔|圆舞曲|小步舞曲|练习曲|幻想曲|夜曲|回旋曲|协奏曲)'
    text = re.sub(r'^(' + genre + r')\s*([升降]?[A-G](?:大调|小调|调))(.*)$', r'\2\1\3', text)
    text = re.sub(r'((?:\d+|[一二三四五六七八九十]+)首)?(小品|乐曲|练习曲|奏鸣曲|小奏鸣曲|幻想曲|前奏曲|夜曲|回旋曲|圆舞曲|变奏曲)为吉他而作', lambda m: (m.group(1) or '') + '吉他' + m.group(2), text)
    text = re.sub(r'(小品|乐曲|练习曲|圆舞曲|回旋曲|夜曲)(简易|华丽)', r'\2\1', text)
    text = re.sub(r'^(作品' + NUMBER + r')\s*\.\s*(.+)$', r'\1：\2', text)
    text = re.sub(r'^(作品' + NUMBER + r')\s+(.+)$', r'\1：\2', text)
    # Do not introduce/deletе source digits in a fully generated reference.
    if Counter(re.findall(r'\d+', original)) != Counter(re.findall(r'\d+', text)):
        return None
    return text


def contextual_draft_repair(original, zh):
    """Repair only explicitly paired source/target musical usages.

    Return corrections for audit.  Partial correction is never semantic review.
    """
    text = zh
    # In archival catalogue transcriptions an isolated genre word can instead
    # belong to a quoted lyric (e.g. L'Etude est inutile).  Limit lexical draft
    # substitution to short source titles, not their long title-page prose.
    lexical_source = original if len(original) <= 350 else original.split(' / ', 1)[0]
    changes = []
    def replace(pattern, replacement, label):
        nonlocal text
        value, count = re.subn(pattern, replacement, text)
        if count and value != text:
            changes.append(label)
            text = value
    for number in {m.group(1) for m in OPUS.finditer(original)}:
        n = re.escape(number)
        replace(r'(?:操作数|操作|作品|同前|同上|运算|工作|手术)\s*[。.：:]\s*(' + n + r')(?!\d)', r'作品\1', 'opus_abbreviation')
    for number in {m.group(1) for m in SERIAL.finditer(original)}:
        n = re.escape(number)
        replace(r'(?:没有|编号|号|不)\s*[。.：:]\s*(' + n + r')(?!\d)', r'第\1号', 'serial_abbreviation')
        replace(r'第\s*(' + n + r')(?!\d)\s*(?:名|期)', r'第\1号', 'serial_not_rank_or_issue')
    pairs = [
        (r'\bair(?:s)?\b|\baire\b', r'空气|航空', '曲调', 'air_is_melody'),
        (r'\b(?:study|studies|études?|etudes?|estudios?)\b', r'研究|学习', '练习曲', 'study_is_etude'),
        (r'\b(?:slur|slurs)\b', r'诽谤', '连音', 'slur_is_technical'),
        (r'\bstring crossing\b', r'字符串交叉', '换弦', 'string_is_instrument_string'),
        (r'\b(?:ch[oô]ro)\b', r'哭泣|偷窃', '肖罗', 'choro_is_genre'),
        (r'\b(?:contredanses?|contradanzas?)\b', r'矛盾|对比', '对舞曲', 'contredanse_is_dance'),
        (r'\b(?:ecossaises?|écossaises?)\b', r'苏格兰女人', '苏格兰舞曲', 'ecossaise_is_dance'),
        (r'\b(?:divertiment(?:o|i)|divertissements?)\b', r'娱乐', '嬉游曲', 'divertimento_is_genre'),
        (r'\bsuite(?:s)?\b', r'套房', '组曲', 'suite_is_genre'),
        (r'\brag\b', r'抹布', '拉格泰姆', 'rag_is_genre'),
        (r'\bch[oô]ros?\b', r'合唱团|合唱', '肖罗', 'choro_not_choir'),
        (r'\btiento\b', r'尝试|诱惑|帐篷', '蒂恩托', 'tiento_is_genre'),
        (r'\bgiga\b', r'演出时间', '吉格舞曲', 'giga_is_dance'),
        (r'\bpassacaille\b', r'通道', '帕萨卡利亚', 'passacaille_is_genre'),
        (r'\bspagnoletta\b', r'乳交', '斯帕尼奥莱塔舞曲', 'spagnoletta_is_dance'),
        (r'\bmaxixe\b', r'小黄瓜', '马希谢舞曲', 'maxixe_is_dance'),
        (r'\bmelodia\b', r'对不起', '旋律', 'melodia_is_melody'),
        (r'\bgranadinas?\b', r'石榴糖浆', '格拉纳迪纳斯', 'granadina_is_genre'),
        (r'\bsicilienne\b', r'西西里岛', '西西里舞曲', 'sicilienne_is_dance'),
        (r'\btyrolienne\b', r'滑索', '蒂罗尔舞曲', 'tyrolienne_is_dance'),
        (r'\bpeteneras?\b', r'伯特利', '佩特内拉', 'petenera_is_genre'),
        (r'\bsaltarell[oi]?\b', r'跳线', '萨尔塔雷洛舞曲', 'saltarello_is_dance'),
        (r'\bpolonaises?\b', r'波兰人', '波兰舞曲', 'polonaise_is_dance'),
        (r'\b(?:fugue|fuga|fuge|fugas)\b', r'逃走|航班|逃脱', '赋格', 'fugue_is_genre'),
        (r'\b(?:courante|corrente)\b', r'当前|现状|职务|电流', '库朗特舞曲', 'courante_is_dance'),
        (r'\b(?:polacca|polaca)\b', r'抛光|波兰语', '波兰舞曲', 'polacca_is_dance'),
        (r'\bbol[ée]ros?\b', r'短上衣', '波莱罗舞曲', 'bolero_is_dance'),
        (r'\bcontradanza\b', r'对比度', '对舞曲', 'contradanza_is_dance'),
        (r'\b(?:minuets?|menuets?|minuett[oi]?)\b', r'菜单', '小步舞曲', 'minuet_is_dance'),
        (r'\bgigue\b', r'抖动', '吉格舞曲', 'gigue_is_dance'),
        (r'\bbourr[ée]e?\b', r'酿造|酿', '布列舞曲', 'bourree_is_dance'),
        (r'\b(?:baletto|ballet|ballett)\b', r'芭蕾舞团', '芭蕾舞剧', 'ballet_not_troupe'),
        (r'\bcanarie\b', r'金丝雀', '卡纳里舞曲', 'canarie_is_dance'),
        (r'\balmain\b', r'德国人|德国|国际金融公司', '阿勒曼德舞曲', 'almain_is_dance'),
        (r'\b(?:duos?|duets?|duettinos?|duetti)\b', r'二人组|双人组|双人舞|对奏|双重奏', '二重奏', 'duo_is_ensemble'),
        (r'\b(?:variations?|variaciones|variazioni|variationen)\b', r'变化|变体', '变奏', 'variation_is_form'),
        (r'\b(?:preludes?|preludios?|pr[eé]ludes?)\b', r'序幕', '前奏曲', 'prelude_is_form'),
        (r'\b(?:pieces?|pi[eè]ces?|piezas?|pezzi|st[uü]cke|morceaux)\b', r'小块|小片段', '小品', 'pieces_not_objects'),
        (r'\bprogres(?:s)?iv\w*\b', r'前卫', '渐进', 'progressive_not_avant_garde'),
        (r'\bandante\b', r'行走|步行|走路', '行板', 'andante_is_tempo'),
        (r'\bandantino\b', r'安丹蒂诺', '小行板', 'andantino_is_tempo'),
        (r'\ballegretto\b', r'阿勒格雷托', '小快板', 'allegretto_is_tempo'),
        (r'\baubade\b', r'奥巴德', '晨歌', 'aubade_is_form'),
    ]
    for source_pattern, target_pattern, translated, label in pairs:
        if re.search(source_pattern, lexical_source, re.I):
            replace(target_pattern, translated, label)
    if re.search(r'\b(?:pieces?|pi[eè]ces?|piezas?|pezzi|st[uü]cke|morceaux)\b', lexical_source, re.I):
        replace(r'(\d+|[一二三四五六七八九十百两]+)\s*(?:个小件|件)', r'\1首乐曲', 'pieces_classifier')
        replace(r'(?<!文)小件', '小品', 'pieces_not_objects')
    if lexical_source != 'Les fantasies del castell' and re.search(r'\b(?:fantasia|fantaisie|fantasie|fantaisies)\b', lexical_source, re.I):
        replace(r'幻想(?=》|[，,、与和第0-9一二三四五六七八九十])', '幻想曲', 'fantasia_is_form')
    if re.search(r'\b(?:minuets?|menuets?|minuett[oi]?)\b', lexical_source, re.I):
        replace(r'小步舞(?!曲)', '小步舞曲', 'minuet_requires_form')
    if re.search(r'\b(?:waltz(?:es)?|valse(?:s)?|walzer)\b', lexical_source, re.I):
        replace(r'错误|虚假|瓦尔泽', '圆舞曲', 'waltz_is_dance')
    if re.search(r'\b(?:ordenes|órdenes)\b', lexical_source, re.I):
        replace(r'(\d+|[一二三四五六七八九十]+)\s*阶', r'\1弦组', 'guitar_courses_not_steps')
    if re.search(r'\b(?:branle|bransle)\b', lexical_source, re.I):
        # The complete mistranslated phrase has to be replaced; translating only
        # gay would leave another non-musical ordinary-language sense behind.
        gay = bool(re.search(r'\b(?:branle|bransle)\s+gay\b', lexical_source, re.I))
        replace(r'同性恋自慰|同性恋打手枪|同性恋打飞机', '欢快的布朗勒舞曲' if gay else '布朗勒舞曲', 'branle_is_dance')
        replace(r'打手枪|打飞机|布兰斯勒|布兰勒', '布朗勒舞曲', 'branle_is_dance')
        if gay:
            replace(r'同性恋', '欢快的', 'branle_gay_is_tempo')
    if re.search(r'\b(?:duos?|duets?)\b', lexical_source, re.I) and not re.search(r'\b(?:trios?|quartets?|sextets?)\b', lexical_source, re.I):
        replace(r'六重奏', '六首二重奏', 'duo_count_not_sextet')
        replace(r'三重奏', '三首二重奏', 'duo_count_not_trio')
    for source_word, other_source, bad, good in [('Sonatina','Sonata',r'(?<!小)奏鸣曲','小奏鸣曲'),('Larghetto','Largo',r'(?<!小)广板|拉盖托|长音','小广板')]:
        if re.search(r'\b'+source_word+r'\b', lexical_source, re.I) and not re.search(r'\b'+other_source+r'\b', lexical_source, re.I):
            replace(bad, good, source_word.casefold() + '_diminutive')
    # Overlapping tempo names are corrected only if the other tempo does not
    # occur in the source.  This avoids changing a genuine Allegro in a suite.
    for source_word, bad, good in [('Allegretto', '快板', '小快板'), ('Andantino', '行板', '小行板')]:
        if re.search(r'\b'+source_word+r'\b', original, re.I) and not re.search(r'\b'+('Allegro' if source_word=='Allegretto' else 'Andante')+r'\b', original, re.I):
            replace(r'(?<!小)'+bad, good, 'tempo_' + source_word.casefold())
    for match in KEY_RE.finditer(original):
        source_note = match.group('note')
        target_notes = {source_note, source_note.upper(), source_note.title()}
        target_notes.update({'do': {'多', 'Do'}, 'ré': {'雷', '热', 'Re'}, 're': {'雷', 'Re'}, 'mi': {'米', 'Mi'}, 'fa': {'法', 'Fa'}, 'sol': {'索尔', 'Sol'}, 'la': {'拉', 'La'}, 'si': {'西', 'Si'}}.get(source_note.casefold(), set()))
        target_pattern = '|'.join(re.escape(n) for n in sorted(target_notes, key=len, reverse=True))
        mode_terms = '未成年人|未成年|次要|小调' if match.group('mode').casefold() in {'minor', 'mineur', 'menor', 'minore', 'moll'} else '专业|少校|大调'
        replace(r'(?<![A-Za-z])(?:[升降]\s*)*(?:' + target_pattern + r')\s*(?:' + mode_terms + r')', key_zh(match), 'key_signature_context')
        # A translated major/minor word used in ordinary-language senses is
        # unsafe to transplant: discard the draft rather than invent its key.
        if re.search(r'专业|未成年人|未成年|次要|少校', text):
            changes.append('unsafe_key_draft')
    text = re.sub(r'[\u200b\ufeff\u2060]', '', text)
    return text, list(dict.fromkeys(changes))


def unsafe_draft_reasons(original, zh):
    reasons = []
    if OPUS.search(original) and re.search(r'操作|同前|同上|手术|运算', zh):
        reasons.append('作品号缩写仍被译作普通词语')
    if KEY_RE.search(original) and re.search(r'专业|未成年人|未成年|次要|少校', zh):
        reasons.append('调性术语被译作普通词语，无法可靠恢复调名位置')
    for match in KEY_RE.finditer(original):
        if key_zh(match) not in re.sub(r'\s+', '', zh):
            reasons.append('原题的调性在旧机器译文中缺失或不一致')
            break
    if re.search(r'(?i)\b(?:mosso|slur|choro|ecossaise)\b', original) and re.search(r'搬家|诽谤|偷窃|苏格兰女人', zh):
        reasons.append('音乐术语仍存在不适用的日常语义')
    # Equal numeric inventories catch dropped/changed work, movement, date,
    # volume and shelfmark digits without deleting archival source numbers.
    if Counter(re.findall(r'\d+', original)) != Counter(re.findall(r'\d+', zh)):
        reasons.append('旧机器译文的数字与原题不一致')
    if zh.count('《') != zh.count('》') or zh.count('[') != zh.count(']') or zh.count('{') != zh.count('}'):
        reasons.append('旧机器译文存在不配对的标题或说明括号')
    return reasons


def review_title_entry(identity, original, composer, current, terms, overrides=None):
    """Apply exact review, complete grammar, or non-upgrading draft repairs."""
    if current.get('original') != original:
        raise ValueError(f'{identity}: stale original title in translation asset')
    reviewed = (overrides or {}).get(identity)
    if reviewed:
        if reviewed.get('original') != original or reviewed.get('original_composer') != composer:
            raise ValueError(f'{identity}: stale title or attribution in title-quality review')
        if reviewed.get('status') not in {'reference', 'retained'} or not reviewed.get('reason'):
            raise ValueError(f'{identity}: incomplete title-quality review evidence')
        if reviewed.get('status') == 'reference' and not HAN.search(reviewed.get('zh','')):
            raise ValueError(f'{identity}: reference review requires a Chinese rendering')
        row = {key: reviewed[key] for key in ('original', 'zh', 'status', 'basis', 'reason')}
        return row, ['exact_source_title_review'] if row != current else []
    row = dict(current)
    generated = terminology_grammar(original, terms, composer)
    if generated and (row['status'] == 'machine' or row.get('basis') in {'checked_terminology_grammar', 'closed_musical_title_grammar_v2'}):
        row.update(zh='《' + generated + '》', status='reference', basis='closed_musical_title_grammar_v2',
                   reason='完整原题仅含已核音乐术语、调性、编号或精确来源署名；逐字保留原编号，参考译文不声明通行专名或谱面编制已审校。')
        return row, ['complete_musical_grammar'] if row != current else []
    if row['status'] != 'machine':
        if row['zh'].count('《') != row['zh'].count('》'):
            row.update(zh='《' + original + '》', status='retained', basis='rejected_malformed_reference_title_2026_10_02',
                       reason='既有参考译文的书名号不配对，不能可靠恢复标题范围；保留原题，旧译文已私有存档待逐条复核。')
            return row, ['malformed_reference_retained_original']
        return row, []
    repaired, corrections = contextual_draft_repair(original, row['zh'])
    unsafe = unsafe_draft_reasons(original, repaired)
    if unsafe:
        row.update(zh='《' + original + '》', status='retained', basis='rejected_unsafe_machine_title_2026_10_02',
                   reason='；'.join(unsafe) + '；原草稿已私有存档，保留原题直至逐条语义校核。')
        return row, ['unsafe_draft_retained_original'] + corrections
    if repaired != row['zh']:
        row.update(zh=repaired, basis='context_corrected_machine_title_2026_10_02',
                   reason='已按精确原题校正音乐术语或编号（' + '、'.join(corrections) + '）；仅局部校正，其余仍为待逐条语义复核的机器草稿。')
        return row, corrections
    return row, []
