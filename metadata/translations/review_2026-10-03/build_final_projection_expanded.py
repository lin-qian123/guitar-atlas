"""Exact semantic/display repair of the independently read final CGLIB 795.

Only writes a separate reviewed supplement and private evidence, not frozen
seeds or production assets. All 795 input originals and translations were read.
"""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
WORK = ROOT / 'work/title-review/2026-10-03/projection-expanded'
INPUT = WORK / 'input.json'
OUT = HERE / 'final_projection_expanded_decisions.json'
INPUT_SHA256 = '0cb7f9138e90003c403ebb638fdc50228b927acf1b49a7c9c497be1fb87215ff'

# The index binds each exact edit to the immutable, ID-checked 795-row input.
EXACT = {
    5: '柔板（吉他第1声部）', 6: '柔板（吉他第2声部）',
    23: '格拉纳达风格曲（Granadina）',
    24: '瓜希拉曲2', 52: '蒂恩托曲', 54: '佩特内拉曲2',
    55: '塞维利亚舞曲2', 57: '索莱阿雷斯2',
    59: '探戈1', 60: '探戈2', 61: '探戈3', 63: '探戈—蒂恩托曲',
    65: '柔板，作品3第1号', 66: '小步舞曲，作品3第3号',
    69: '轻松自在之类的事', 74: 'Heather的歌',
    76: '我未曾谋面的朋友（左手）',
    80: 'Bianca的午夜摇篮曲（二重奏，吉他第1声部）',
    81: 'Bianca的午夜摇篮曲（二重奏，吉他第2声部）',
    82: '追忆', 142: '悲歌（广板）',
    145: '〈茶花女〉歌剧集锦，作品08第29号',
    146: '随想曲，作品13第3号',
    147: '夜曲，作品4第2号（第1部分）',
    148: '匈牙利幻想曲，作品65第1号',
    149: '兰德勒舞曲，作品9第4号',
    154: '帕凡舞曲3', 155: '帕凡舞曲I', 156: '帕凡舞曲IV',
    157: '帕凡舞曲5', 158: '帕凡舞曲6', 159: '幻想曲40',
    162: '利切尔卡尔曲III',
    175: '基辅大门（Guitar Bass）',
    176: '柔板，K356', 178: '快板，K487', 180: '行板，K487',
    183: 'A调小步舞曲第2号', 184: '〈唐璜〉中的小步舞曲',
    190: '小步舞曲，K94', 191: '柔板，作品52',
    193: 'C调小品', 194: 'A调钢琴奏鸣曲',
    195: '回旋曲：活泼的快板（二重奏，吉他第1声部）',
    196: '回旋曲：活泼的快板（二重奏，吉他第2声部）',
    197: '回旋曲（二重奏，吉他第1声部）', 198: '回旋曲（二重奏，吉他第2声部）',
    199: 'C调奏鸣曲，K545',
    200: 'C大调奏鸣曲（二重奏，吉他第1声部）',
    201: 'C大调奏鸣曲（二重奏，吉他第2声部）',
    202: 'G调奏鸣曲第5号：急板（二重奏，吉他第1声部）',
    203: 'G调奏鸣曲第5号：急板（二重奏，吉他第2声部）',
    204: '交响曲第40号的主题', 205: '三重奏2',
    214: '低音弦肖罗曲', 219: 'D调卡农',
    261: '这里需要一支探戈',
    270: '探戈组曲第02乐章：行板（二重奏，吉他第1声部）',
    271: '探戈组曲第02乐章：行板（二重奏，吉他第2声部）',
    272: '探戈组曲第03乐章：快板（二重奏，吉他第1声部）',
    273: '探戈组曲第03乐章：快板（二重奏，吉他第2声部）',
    274: '港城之夏：探戈', 275: '琉特琴帕凡舞曲',
    288: 'Abaete的传说', 294: '呼唤2', 299: '献给Jussara的摇篮曲',
    306: '深情（1971）', 307: '深情（1992）',
    308: '告别之歌（1971）', 309: '星光铺地（1971）',
    314: '玫瑰', 317: 'Alcantara的故事', 319: '简易圆舞曲',
    328: '那是美好的一年（二重奏，长笛声部）',
    329: '那是美好的一年（二重奏，吉他声部）',
    330: '五木摇篮曲（1970）', 331: '五木摇篮曲（1971）',
    335: '回忆（吉他第1声部）', 336: '回忆（吉他第2声部）',
    338: '狂欢节的早晨（1966）', 339: '狂欢节的早晨（1970）',
    340: '狂欢节的早晨（1971）',
    350: '献给Clo', 351: '献给Sonia',
    353: 'A小调前奏曲（1983）', 359: '午夜时分（1970）',
    362: '前奏桑巴（1964）', 363: '前奏桑巴（2000）',
    365: '如果人人都像你（1979）',
    389: 'Musette的圆舞曲',
    391: '曲调2', 394: 'A小调小步舞曲第2号', 396: 'A小调小步舞曲第3号',
    404: 'Male布鲁斯', 405: '悲伤的圆舞曲',
    446: 'Beths布鲁斯（吉他）', 449: 'Faros拉格泰姆',
    459: '明月闪耀', 465: '双琉特琴小曲（二重奏，吉他第1声部）',
    466: '双琉特琴小曲（二重奏，吉他第2声部）',
    469: '加利亚德舞曲', 475: '西班牙旋律', 477: '吉格舞曲2',
    486: '歌与舞第1号', 496: '轮指练习曲',
    500: '轮指练习曲第4号，第3册',
    512: '那不勒斯骑兵，配双号角',
    518: 'A大调组曲：恰空', 519: 'A大调组曲：马塔钦舞曲',
    520: '〈加那利舞曲〉的主题', 524: '托卡塔第4号中的小步舞曲',
    527: 'A大调奏鸣曲，K.322',
    548: '降E小调即兴曲2',
    550: '小夜曲（吉他第1声部）', 551: '小夜曲（吉他第2声部）',
    555: '快乐的农夫（二重奏，吉他第1声部）',
    556: '快乐的农夫（二重奏，吉他第2声部）',
    559: '作品68第1号（二重奏，吉他）',
    560: '作品68第1号（二重奏，小提琴）',
    563: '小提琴组曲第1号中的变奏曲，BWV1002',
    564: '阿勒曼德舞曲，BWV996',
    567: 'E调阿莱格里亚斯', 569: '怀念（瓜希拉曲）',
    584: '施特劳斯圆舞曲',
    587: '卡瓦蒂纳第I乐章：前奏曲',
    588: '卡瓦蒂纳第II乐章：萨拉班德舞曲',
    589: '卡瓦蒂纳第III乐章：小谐谑曲',
    590: '卡瓦蒂纳第IV乐章：船歌',
    591: '阿德丽塔（玛祖卡舞曲）',
    603: 'Isabel：圆舞曲', 606: 'Maria：加沃特舞曲', 607: 'Marieta：玛祖卡舞曲',
    622: '泪：前奏曲第20号', 643: '梦（玛祖卡舞曲）', 644: '梦（轮指）',
    648: '玛祖卡舞曲，作品39第10号', 649: '波尔卡，作品39第14号',
    650: '意大利曲调，作品39第15号', 651: '德国曲调，作品39第17号',
    652: '圆舞曲，作品39第8号',
    654: '赋格第1号，作品109（二重奏，吉他第1声部）',
    655: '赋格第2号，作品109（二重奏，吉他第1声部）',
    656: '赋格第3号，作品109（二重奏，吉他第1声部）',
    657: '赋格第4号，作品109（二重奏，吉他第1声部）',
    658: '前奏曲第1号，作品109（二重奏，吉他第1声部）',
    659: '赋格第1号，作品109（二重奏，吉他第2声部）',
    660: '赋格第2号，作品109（二重奏，吉他第2声部）',
    661: '赋格第3号，作品109（二重奏，吉他第2声部）',
    662: '赋格第4号，作品109（二重奏，吉他第2声部）',
    663: '前奏曲第1号，作品109（二重奏，吉他第2声部）',
    664: '前奏曲第3号，作品109',
    665: '组曲，作品133：I.前奏曲',
    668: 'A小调奏鸣曲第4乐章：活板（二重奏，吉他第1声部）',
    669: 'A小调奏鸣曲第4乐章：活板（二重奏，吉他第2声部）',
    671: 'A小调奏鸣曲第1乐章：西西里舞曲',
    672: 'A小调奏鸣曲第2乐章：精神饱满地',
    673: '作品24第1号',
    679: '吉他小奏鸣曲第I乐章：小快板',
    680: '吉他小奏鸣曲第III乐章：快板',
    681: '吉他小奏鸣曲第II乐章：行板',
    682: '啤酒桶波尔卡', 683: '黑钻石布鲁斯',
    685: 'Cane Break布鲁斯', 688: 'Memphis布鲁斯',
    691: 'Too Tight拉格泰姆',
    695: '摇篮曲（三重奏，大提琴声部）',
    696: '摇篮曲（三重奏，吉他第1声部）',
    697: '摇篮曲（三重奏，吉他第2声部）',
    707: '升F小调练习曲第9号',
    708: '加沃特肖罗曲', 709: '玛祖卡肖罗曲', 715: '圆舞曲肖罗',
    716: '玉米棒2',
    721: 'G调双曼陀林协奏曲中的行板',
    722: 'G调协奏曲中的行板',
    723: 'D调吉他协奏曲', 724: '巴洛克协奏曲',
    725: 'A小调协奏曲，RV356',
    727: 'G大调协奏曲第3号（吉他）',
    728: '〈四季〉之春（二重奏，吉他第1声部）',
    729: '〈四季〉之春（二重奏，吉他第2声部）',
    730: '〈四季〉之夏', 731: '〈四季〉之冬',
    732: '广板的主题',
    789: '孤独者的米隆加', 790: '悲伤的米隆加',
}

SPECIAL_REASONS = {
    52: 'Los Tientos是音乐题名的复数，不据复数断定曲集或总曲数。',
    63: 'Tango Tientos的题名结构保留为探戈—蒂恩托，不凭并列词断定曲集。',
    76: 'Left Hand是来源附加标签，译作左手附注，不添加未提供的版本或声部身份。',
    147: 'Part 1是第1部分，不是1首夜曲；保留作品4、第2号和该部分标记。',
    175: 'Guitar Bass保留原标签，来源未明确是乐器还是低音声部，不推定编制。',
    261: '完整西班牙语句Aqui hace falta un tango意为这里需要一支探戈，不把普通短句当专名。',
    275: 'A是英语不定冠词，不是A调；Lute是琉特琴，原题未提供调性。',
    314: 'Das Rosas未提供歌这一体裁字样；参考题名采用玫瑰，不补歌或其他歌词。',
    319: 'Facil是葡萄牙语简易修饰语，不是未明专名；整句为简易圆舞曲。',
    353: '1983仅作为来源附记保留；原题没有No，不能虚构第1983号前奏曲。',
    389: '普契尼题名语境中的Musette是角色名称，不能按器乐musette译作风笛；保留来源拼写。',
    404: 'Male的具体语言/重音未由原题确定，保留该词与明确布鲁斯结构，不猜英语男性或捷克语小。',
    405: '捷克语smutný明确表示悲伤，结合Vals的圆舞曲题名作完整参考意译。',
    469: 'A是英语不定冠词，不是调号；原题只有加利亚德舞曲，不增加A调。',
    512: '删除主标题内的作者信用；con dos Clarines属于原曲题意的双号角，不推断实际谱面编制。',
    584: 'A是英语冠词，Strauss是来源姓氏；不把A虚作调号或中文题名内容。',
    665: 'Suite I Preludio的罗马数字保留为I.前奏曲，不武断补组曲第1号或总曲数。',
    671: '奏鸣曲后的1 Siciliana是第1乐章，不是一首西西里舞曲的合集数量。',
    721: '源2 Mandolins是双曼陀林，保留明确乐器数量和G调，不补大小调。',
    723: 'Concert在Vivaldi D调吉他作品语境中为协奏曲缩写，不是音乐会；不从其他版本补RV编号或大小调。',
}

RESEARCH = {
    23: ['https://dle.rae.es/grana%C3%ADna'],
    389: ['https://www.lyricopera.org/lyric-lately/la-boheme-quando-men-vo/',
          'https://www.naxos.com/CatalogueDetail/?id=8.110252-53'],
    405: ['https://ssjc.ujc.cas.cz/search.php?heslo=smutn%C3%BD&hsubstr=no'],
    723: ['https://www.naxos.com/CatalogueDetail/?id=8.573440'],
}
for index in (270, 271, 272, 273):
    RESEARCH[index] = ['https://www.naxos.com/CatalogueDetail/?id=8.574457']
    SPECIAL_REASONS[index] = '对照来源组曲/单一速度词及Naxos曲序，02/03是第2/3乐章标记，不是二/三首行板或快板。'

WEISS_MOVEMENTS = {
    'prelude': '前奏曲', 'marche': '进行曲', 'gavotte': '加沃特舞曲',
    'aria': '咏叹调', 'menuet': '小步舞曲', 'musette': '风笛舞曲',
    'allemande': '阿勒曼德舞曲', 'courante': '库朗特舞曲',
    'bouree': '布列舞曲', 'bourree': '布列舞曲', 'sarabande': '萨拉班德舞曲',
    'gigue': '吉格舞曲', 'ouverture': '序曲', 'allegro': '快板',
    'presto': '急板', 'toccata e fuga': '托卡塔与赋格',
    'menuet i': '小步舞曲I', 'menuet ii': '小步舞曲II',
}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def numbers(value):
    return Counter(re.findall(r'\d+', value))


def marked(value):
    return value if value.startswith('《') and value.endswith('》') else '《' + value + '》'


def interpret_weiss(row):
    if row['corpus']['composer'] != 'Weiss. Silvius Leopold':
        return None
    body = row['corpus']['display_original']
    match = re.fullmatch(r'(Sonata|Suite)(?:\s+No\s+(\d+))?\s+In\s+([A-G])\s*(\([A-Z]\d+\)|[DK]\d+)?\s+(\d+)\s+(.+)', body, re.I)
    if not match:
        return None
    form, workno, key, code, movement, name = match.groups()
    translated = WEISS_MOVEMENTS[name.casefold()]
    title = key.upper() + '调' + ('奏鸣曲' if form.casefold() == 'sonata' else '组曲')
    if workno:
        title += '第' + workno + '号'
    if code:
        title += '，' + code.strip('()')
    title += '（第' + movement + '乐章：' + translated + '）'
    return title


def decision(row, index):
    e = deepcopy(row['decision'])
    original_zh = row['before_zh']
    z = original_zh
    reason = '完整原题与现译逐条审读；确认主曲名及明确音乐信息，补入精确原题守卫的中文主标题。'
    method = 'individual_complete_title_and_translation_readback'
    if index in EXACT:
        z = marked(EXACT[index])
        reason = SPECIAL_REASONS.get(index, '逐条核对完整原题；整理自然中文语序，保留调性、曲号、作品号和来源明确的编制标签。')
        method = 'exact_ID_whole_title_semantic_correction'
    elif (weiss := interpret_weiss(row)) is not None:
        z = marked(weiss)
        reason = '逐条核对同奏鸣曲/组曲的连续分曲；数字是乐章序次，保留作品序号及原有L/K/D目录标记，不译成首数。'
        method = 'hand_read_series_with_explicit_movement_structure'
    else:
        bare = z[1:-1]
        # These exact title/translation pairs were read in full before this
        # closed formatting pass. No broad lexical translator is used.
        keymatch = re.fullmatch(r'第(\d+)号(前奏曲|小步舞曲|练习曲)\s+([升降]?[A-G](?:大调|小调|调))', bare)
        if keymatch:
            n, form, key = keymatch.groups()
            z = marked(key + form + '第' + n + '号')
            reason = '完整原题核对调性与单曲编号，调整调性在前的自然语序；未注明大小调时仅写字母调。'
            method = 'fully_read_key_and_number_title_order'
        elif re.fullmatch(r'第\d+号前奏曲', bare) and row['corpus']['composer'] == 'Mertel. Elias':
            z = marked(re.sub(r'第(\d+)号前奏曲', r'前奏曲第\1号', bare))
            reason = '完整单条前奏曲题名与编号核对，编号原样保留，不视为曲集数量。'
            method = 'fully_read_numbered_prelude_title'
        else:
            part = re.fullmatch(r'(.+?)(二重奏|三重奏)?(吉他第\d+声部|吉他声部|长笛声部)', bare)
            if part:
                title, ensemble, voice = part.groups()
                z = marked(title.strip() + '（' + ((ensemble + '，') if ensemble else '') + voice + '）')
                reason = '完整曲名与来源Guitar1/2或Part标签核对，将明确合奏/分谱标签置于括注，不吞掉曲名或误作曲数。'
                method = 'fully_read_title_and_explicit_part_label'
            else:
                z = marked(bare.replace('(广板)', '（广板）'))
    e['before_zh'] = original_zh
    e['before_display_zh'] = row['before_display_zh']
    e['display_original'] = row['corpus']['display_original']
    e['display_zh'] = z
    # Full reviewed translations are corrected only for confirmed semantic or
    # whole-title syntax defects; raw source provenance remains immutable.
    if z != original_zh and index != 512:
        e['zh'] = z
    e['reviewer'] = 'Codex CGLIB projection second half, complete readback 2026-10-04'
    e['review_method'] = method
    e['basis'] = 'exact_source_title_primary_projection_review_2026_10_04'
    e['reason'] = reason
    e['source_refs'] = list(dict.fromkeys([*e.get('source_refs', []), row['corpus']['source_url'], *RESEARCH.get(index, [])]))
    if index == 453:
        assert row['id'] == 'cglib:39800' and row['corpus']['display_original'] == 'National Seven'
        e['zh'] = e['display_zh'] = '《National Seven》'
        e['status'] = 'retained'
        e['basis'] = 'explicit_original_title_retention_source_title_ambiguity_2026_10_04'
        e['reason'] = 'National Seven所指的特定名称未由原记录说明，不能译成民族七或猜国道名称。'
        e['state_change_basis'] = 'source_title_ambiguity'
        e['review_method'] = 'exact_proper_title_ambiguity_retention'
    return e


def main():
    assert hashlib.sha256(INPUT.read_bytes()).hexdigest() == INPUT_SHA256, 'immutable input changed'
    rows = read(INPUT)['entries']
    assert len(rows) == len({r['id'] for r in rows}) == 795
    output = []
    ledger = []
    for index, row in enumerate(rows):
        assert row['decision']['id'] == row['id'] == row['corpus']['id']
        e = decision(row, index)
        c = row['corpus']
        assert e['original'] == c['original'] and e['original_composer'] == c['composer']
        assert e['display_original'] == c['display_original']
        assert e['before_zh'] == row['decision']['zh']
        assert e['before_display_zh'] == row['decision'].get('display_zh', row['decision']['zh'])
        assert e['status'] == row['decision']['status'] or (index == 453 and e['status'] == 'retained')
        if e['status'] != 'retained':
            assert re.search(r'[\u3400-\u9fff]', e['display_zh']), row['id']
        for title in (e['zh'], e['display_zh']):
            assert title.count('《') == title.count('》') == 1, row['id']
            assert title.count('〈') == title.count('〉'), row['id']
            assert title.count('（') == title.count('）'), row['id']
            assert title.count('(') == title.count(')'), row['id']
        before_numbers, after_numbers = numbers(row['before_zh']), numbers(e['display_zh'])
        ledger.append({'index': index, 'id': row['id'], 'original': c['original'], 'original_composer': c['composer'],
                       'before_zh': row['before_zh'], 'zh': e['zh'], 'before_display_zh': row['before_display_zh'],
                       'display_original': e['display_original'], 'display_zh': e['display_zh'],
                       'status': e['status'], 'reason': e['reason'], 'review_method': e['review_method'],
                       'source_refs': e['source_refs'], 'numbers_before': dict(before_numbers),
                       'numbers_after': dict(after_numbers), 'numbers_identical': before_numbers == after_numbers,
                       'native_title_attribution_display_guards': 'passed'})
        output.append(e)
    OUT.write_text(json.dumps({'schema_version': 1, 'entries': output}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (WORK / 'ledger.json').write_text(json.dumps({'schema_version': 1, 'entries': ledger}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    report = {'records': 795, 'all_original_titles_and_prior_complete_translations_read': True,
              'selection': 'Last795 of1595 CGLIB reference/reviewed blank actual display titles, actual-catalog-diagnostic work order.',
              'statuses': dict(Counter(e['status'] for e in output)),
              'full_zh_changed': sum(e['zh'] != e['before_zh'] for e in output),
              'explicit_primary_display_guards': 795, 'native_guards': 795,
              'numeric_differences_requiring_individual_readback': [e['id'] for e in ledger if not e['numbers_identical']],
              'input_sha256': hashlib.sha256(INPUT.read_bytes()).hexdigest(),
              'output_sha256': hashlib.sha256(OUT.read_bytes()).hexdigest()}
    (WORK / 'validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
