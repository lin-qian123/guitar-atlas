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
OPUS = re.compile(r"(?<!\w)(?:op(?:us)?|oeuv(?:re)?|œuv(?:re)?)\s*[.:：]?\s*(" + NUMBER + r")", re.I)
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
        if reviewed.get('status') not in {'reference', 'reviewed', 'retained'} or not reviewed.get('reason'):
            raise ValueError(f'{identity}: incomplete title-quality review evidence')
        if reviewed.get('status') in {'reference', 'reviewed'} and not HAN.search(reviewed.get('zh','')):
            raise ValueError(f'{identity}: reference review requires a Chinese rendering')
        if reviewed.get('status') == 'reviewed':
            refs = reviewed.get('source_refs', [])
            if not isinstance(refs, list) or not refs or any(not isinstance(ref, str) or not ref.startswith('https://') for ref in refs):
                raise ValueError(f'{identity}: conventional title review requires HTTPS references')
        row = {key: reviewed[key] for key in ('original', 'zh', 'status', 'basis', 'reason')}
        for key in ('original_composer', 'aliases_zh', 'display_original', 'display_zh', 'source_refs', 'review_method', 'reviewer'):
            if key in reviewed:
                row[key] = reviewed[key]
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
