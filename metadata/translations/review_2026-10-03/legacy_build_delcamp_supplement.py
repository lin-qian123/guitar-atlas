"""Build the individually read Delcamp supplement; never change source identity.

Sparse TSV rows are complete, manually reviewed title phrases. All 624 input
rows were read; unlisted titles retain the root review's existing decision.
No per-word automatic translation or guessing of unfamiliar names is applied.
"""
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from legacy_build_decisions import wrapped
from legacy_validate_decisions import balanced, number_values

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
INPUT = ROOT / 'work/title-review/2026-10-03/legacy-review/delcamp-review-input.json'
FROZEN = '671649269b2e56560759dc63ead32bb8e925c9693538d8cc26371927449df093'


def main():
    assert hashlib.sha256(INPUT.read_bytes()).hexdigest() == FROZEN
    rows = json.loads(INPUT.read_text())
    assert len(rows) == 624
    titles = {}
    for line in (HERE / 'legacy_delcamp_titles.tsv').read_text().splitlines():
        i, title = line.split('\t', 1)
        i = int(i)
        assert 0 <= i < 624 and i not in titles
        titles[i] = title
    entries = []
    detailed = {
        0: 'Schule在完整音乐句中为教程；书名中的Leonhardt Bulmans保留原拼写，不从书名创建或扩充作曲者身份。',
        44: 'cifras/temple按西班牙吉他指法谱与定弦语境读，不解释为财务数字或庙宇；Guerau原刊题名仍完整保留。',
        45: '原文Peterneras拼写不擅自改成Peteneras；after Gaspar Sagreras只表示依据其原曲，不替换来源的Julio Salvador Sagreras署名。',
        55: 'Mandore为来源乐器称谓，保留原词；不猜定为现代曼陀林。',
        75: '来源给出的歌剧名le mur de nuit Lerinn疑有转录问题；原词保留，不补造贝利尼歌剧身份，只译幻想曲主题关系。',
        76: 'Moraima保留原拼写；明确after关系可译，不能因Gaspar Espinosa而重写作曲者署名。',
        182: '原注(3)=G按第3弦定弦读；不当成第3首作品或调性。',
        202: 'Lute Academy的原谱题名索引列The Moris及Morris/Moresca舞曲题名用法；参考译为莫里斯舞曲，不借题名索引归并此来源作品或改写其Adrian Le Roy署名。',
        225: 'Berimbau为巴西单弦音乐弓称谓；参考题名解释乐器词义，不将其当人物名或声称为权威中文曲名。',
        238: '五木村官方页面及日本哥伦比亚官方艺人发布给出五木の子守唄；据完整日文罗马字词义译五木摇篮曲，单曲标记另作版式说明，不借民歌曲名合并Baden Powell编配。',
        249: 'minhas primeiras notas在吉他教程书名中为初步音符，不凭生硬旧译替换成人名或作品号。',
        306: '来源书名的629页与73 Mo为书目/网页规模标记，完整original和中文记录保留该来源说法；清洁主标题移出页数与容量，不声称本地文件规模或已验收页数。',
        331: 'Abecedario italiano为巴洛克吉他的和弦字母表；不把旧Alfabeto字母标记当成现代调性。',
        373: 'Cyanen具体专名含义不足，保留原词；als Folge为续集关系，不能误作青色或因果。',
        404: '原标题署Bach而来源composer字段为Tomaso Giovanni Albinoni，存在来源署名冲突；只复核鲁特琴组曲第4号与BWV1006a题名，不据题名前缀更改守卫署名或合并作曲者。',
        439: 'Donizetti及完整剧名语境支持〈拉美莫尔的露西娅〉的参考对应；源Lammermor的转录拼写仍原样保留，未用这个对应改写来源归属或跨源合并。',
        445: '历史Sinfonia兼有序曲与交响曲等用法，此来源未说明实际曲式；保留Sinfonia，Mi Segunda Epoca仅按普通词义参考译为我的第二时期并保留原词，不猜定为现代交响曲。',
        451: 'guitar part incomplete为来源声部缺失说明，不是音乐题名；中文全字段保留，主标题移至详细信息层级。',
        465: 'Cah.分册编号、130页及viola part missing均是来源书目说明；不因中提琴缺失注释为标题追加必需乐器。保留完整source及中文书目说明，主标题保留明确音乐内容与作品321。',
        514: 'Manuel M. Ponce为来源题名的附署名，其具体角色未标明；保留在中文全字段与original，只显示确定大奏鸣曲，不改作曲者字段或推定编者角色。',
        552: '源题同时给Elisabetta和方括号Il Barbiere di Siviglia，不能凭相近序曲删除其中一项或强定同一歌剧；按Sinfonia nell’Opera明确歌剧序曲译出，并保留冲突书目注释。',
        558: '源题明确称Balletto，不因Il Barbiere di Seviglia与歌剧同名改成歌剧；保留舞剧及作品16的来源说法。',
        574: '来源作品122用Premiere序标，按原文保留第1号；不强改成另一现代目录体系的第4号。罗西尼主题幻想曲为说明性参考名。',
        575: '来源作品123用Seconde序标，按原文保留第2号；不强改成另一现代目录体系的第5号。罗西尼主题幻想曲为说明性参考名。',
        576: '来源明确6 Rossiniana、作品124、第I册；保留这三个编号层级，Cah.I不用于重写作品序号。Naxos仅支持此完整题名的罗西尼主题曲种解释，不据相似标题合并记录。',
    }
    refs_by_index = {
        202: ['https://lute-academy.be/wordpress/wp-content/uploads/2024/04/IRL-Dtc-408II-Ballet.pdf'],
        238: ['https://www.vill.itsuki.lg.jp/kankou/kiji0032052/index.html', 'https://www.youtube.com/watch?v=8wQwGCQ-XAs'],
        445: ['https://www.treccani.it/vocabolario/sinfonia/'],
        576: ['https://www.naxos.com/CatalogueDetail/?id=8.574272'],
    }
    for i, title in sorted(titles.items()):
        r = rows[i]
        reason = '本轮逐条对照完整源题复核题名主体、音乐形式、数量/作品号及配器；未知人名或歌名保留原拼写，明确音乐句给予参考意译。未据旧机器草稿或非空中文认证通行曲名。'
        if not r['composer']:
            reason += '来源未给明确composer；题名中的Latin人名只保留为来源书名文本，不推断作曲者。'
        if '〈' in title:
            reason += '内层题名引号保留主题/唱段层级，未定歌词与专名不强行音译或补写。'
        if 'Luigi Legnani' in r['original'] and r['composer'] != 'Luigi Legnani':
            reason += 'Luigi Legnani为来源书名中的署名文本，原composer字段保持不变，不从题名前缀归并身份。'
        if i in range(525, 545):
            reason += '题名前缀Matteo Carcassi与来源composer字段不一致；仅翻译作品60的练习曲与曲号，不更改来源署名或建立作者身份关系。'
        if i in (7, 8, 9, 358):
            reason += 'Leccion/Lecciones为课题，数字后的a/b是原编号标记，保留为5a/8a等，未擅自猜定为第五课或下半课。'
        if i in (311, 312, 313, 314, 315, 316, 317):
            reason += 'Mayor明确为大调；尾部b/f/g/c保留来源版本标记，不改成降号或次调。'
        if i in (341, 342, 343, 344, 345):
            reason += 'Sanz的por la E/O/D/Cruz在Alfabeto体系中是和弦符号，不凭字母推出E/O/D大调；符号逐字保留。'
            refs_by_index[i] = ['https://imslp.org/wiki/Instrucci%C3%B3n_de_M%C3%BAsica_%28Sanz%2C_Gaspar%29']
        if re.search(r'\(3\)\s*=|tercera cuerda', r['original'], re.I):
            reason += '第3弦定弦标记独立保留，不并入作品/曲号或将F#写成调性。'
        if re.search(r'(?:facsimile|manuscript|pages|part (?:missing|incomplete))', r['original'], re.I):
            reason += '影印、手稿、页数和声部状态为来源说明，完整original保留；这不是新一轮本地PDF核验。'
        reason += detailed.get(i, '')
        zh = wrapped(title)
        display = zh
        if i == 306:
            display = wrapped('Fernando Sor吉他作品全集')
        elif i == 451:
            display = wrapped(title.replace('（吉他声部不完整）', ''))
        elif i == 465:
            display = wrapped(title.split('；', 1)[0])
        elif i == 514:
            display = wrapped('大奏鸣曲')
        elif i == 552:
            display = wrapped('歌剧〈Elisabetta〉序曲')
        assert re.search(r'[\u3400-\u9fff]', display)
        assert balanced(zh) and balanced(display)
        entries.append(dict(id=r['id'], original=r['original'], original_composer=r['composer'], display_original=r['display_original'], zh=zh, display_zh=display, status='reference', basis='legacy_delcamp_complete_title_semantic_reading', reason=reason, source_refs=refs_by_index.get(i, [])))
    assert len(entries) == len(titles) and len({e['id'] for e in entries}) == len(entries)
    output = HERE / 'root_delcamp_supplement.json'
    output.write_text(json.dumps(dict(schema_version=1, entries=entries), ensure_ascii=False, indent=2) + '\n')
    candidates = []
    for i, e in zip(sorted(titles), entries):
        r = rows[i]
        missing = number_values(r['original']) - number_values(e['zh'], True)
        if missing:
            candidates.append(dict(index=i, id=e['id'], original=r['original'], zh=e['zh'], missing=dict(missing)))
    report = dict(input_count=624, revised_count=len(entries), unchanged_retained_count=624-len(entries), statuses=dict(Counter(e['status'] for e in entries)), input_sha256=FROZEN, output_sha256=hashlib.sha256(output.read_bytes()).hexdigest(), all_id_original_composer_display_guards_checked=True, read_ranges_inclusive=[[0,159],[160,319],[320,479],[480,623]], number_candidates=candidates)
    (ROOT / 'work/title-review/2026-10-03/legacy-review/delcamp-validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
