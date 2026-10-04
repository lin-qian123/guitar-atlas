"""Build the independently assigned last 357 CGLIB archival title decisions.

All source titles and attributions were read in two complete ordered batches,
[0:180] and [180:357]. The TSV contains whole-title semantic decisions, not
unrestricted word substitutions. Keep original and display guards immutable;
source bylines may be translated in zh but do not enter the clean display_zh.
No previous machine/reference status is accepted as semantic evidence.
"""
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from legacy_build_decisions import wrapped
from legacy_validate_decisions import errors

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
INPUT = ROOT/'work/title-review/2026-10-03/cglib-retained-pass/archive-root-tail.json'
FROZEN = 'bb234309c7515d7cc370448dd536744263cfdd086dee7541941b35332ca90c28'
OUTPUT = HERE/'cglib_retained_archive_root_tail_supplement.json'

OPERA = 'https://www.digitalguitararchive.com/product/j-k-mertz-opern-revue-op-8-nos-1-8-volume-i/'
VIOLET = ['https://www.halleonard.com/product/8551177/nachtviolen',
          'https://media.nativedsd.com/storage/nativedsd.com/wp-content/uploads/2020/07/02183610/MYR018.pdf']
CYANEN = ['https://publikationen.sulb.uni-saarland.de/bitstream/20.500.11880/30472/1/bognersaar.pdf',
          'https://www.iplant.cn/fsz/info/Centaurea%20cyanus']

REASONS = {
  6:'24为简易娱乐小品的曲集标记；布谷鸟为主标题，未据曲集数猜定声部或作品号。',
  31:'出版社译Nachtviolen为Evening Violets，唱片册列Mertz作品2；夜紫罗兰为参考意译。',
  33:'出版社及唱片册支持夜紫罗兰词义；旋律小品与作品2层级保留。',
  38:'亲王姓名保留原拼写，第1—4号为曲目范围，不把Oginski音译成另一位作曲者。',
  39:'亲王姓名保留原拼写，第5—7号为曲目范围，不据姓名改composer。',
  43:'购藏说明移入完整译文，主标题只含浪漫曲与吉他独奏；J.G.V.未擅自展开。',
  45:'法德文吉卜赛歌曲标签为同一题意；图林根民歌另列，未猜改曲数或编号。',
  50:'夫人及所属关系可译；Puffe为未定专门曲名，保留原拼写。',
  59:'Bardenklänge为吟游诗人的歌声；作品13、第4号及船歌层级完整。',
  60:'Bardenklänge为吟游诗人的歌声；作品13、第5号及芬格尔洞穴层级完整。',
  61:'源magnonnes疑为mignonnes的转录字形；按变奏曲上下文译精巧，原题不改。',
  71:'学术注释明确Cyanen为Kornblumen，植物志对应矢车菊；保留夜紫罗兰续集、吉他及作品5。',
  72:'Cyanen词义有主源证据；作品5及重复5tes Werk完整保留，主标题不重复同一作品号。',
  73:'曲名El ole la madrilena词序/转录未定；完整西班牙民族舞曲、吉他改编与作品号可译。',
  74:'sei corde明确六弦；音乐基础与编写署名分开，未据书名更改composer。',
  75:'seis ordenes为六组弦而非六根弦；上尉编写署名与主标题分开。',
  80:'声乐、钢琴、吉他、小提琴及交替变奏完整保留；texte为歌词而非序号。',
  81:'原or保留钢琴与吉他或双钢琴的选择；合署名不代替来源composer。',
  87:'quattro为4首奏鸣曲；法式吉他为历史名称，不推断具体琴型或现代编制。',
  88:'in C修饰单簧管调式，不推断作品为C大调；瑞士为题名修饰。',
  89:'3首四重奏与作品4第1号为不同层级；四种原乐器均保留。',
  97:'from指第2首主题变奏曲中的变奏，未把作品22改作第二首全曲。',
  100:'少女与死神为完整题意，不根据同名标题合并作品或确定吉他版本。',
  103:'Romeo保留专名；莎士比亚小夜曲为来源所写关系，未补成另一首歌曲题名。',
  106:'Schuman与来源composer Schumann字形不一致；教程署名保留原拼，不宣称罗伯特·舒曼创作。',
  109:'12首与作品6续集、作品29的层级完整，未把suite在这里译成组曲。',
  110:'德意双语各有25首的转录，两次25照留，未当成50首曲目。',
  112:'sic明确指出源作品号有疑点；作品34原样保留，不按已知索尔目录改号。',
  113:'XII为12首；源自带walzes/waltzes排印说明不进入主标题。',
  119:'日本风格修饰波尔卡舞曲；来源音乐作者及改编者单列，不据标题改署名。',
  120:'老鼠及探戈可译；de la cadera可能为特定舞曲/动作标签，保留该短语。',
  123:'Feuilles variees按各色叶片参考意译，未据作者/同名猜成某一已知钢琴曲。',
  129:'只译源明确的作品与舞段关系；原题自带排印解释保留在完整译文。',
  138:'原四重奏、D小调、K.421及小步舞曲关系完整，未据改编者更改composer。',
  139:'来源同时写第2号夜曲和作品9第2号，两处编号均保留。',
  140:'degree mark是序数排印描述；第6号保留，未误当成温度或调性。',
  141:'degree mark是序数排印描述；第7号保留，未误当成温度或调性。',
  146:'3个前奏曲编号6、7、20分别保留，不让肖邦署名吞掉前两曲。',
  149:'小提琴2把与四重奏编制、H.III:74及G小调完整；Largo assai为很慢的广板。',
  150:'源只列小提琴、中提琴、大提琴，未从五重奏补造各乐器数量。',
  157:'英雄之死修饰葬礼进行曲；降A大调、第12号与作品26保留。',
  158:'C diez为升C，minor为小调；sostenuto保留绵延的柔板速度层级。',
  163:'BWV1001—1006为总集范围；第1帕蒂塔及布列舞曲速度标签分别保留。',
  164:'BWV1001—1006为总集范围；第1奏鸣曲及赋格分别保留。',
  165:'Suspiro de amor可译爱的叹息；源Repòs另一题名拼写照留，不强行纠成Repos。',
  166:'明确唐豪瑟歌剧语境的sinfonia按序曲译，未泛化到独立Sinfonia。',
  169:'保留舒伯特署名与来源作品11，不从通行目录补造D号。',
  181:'Eureka作为教程专名保留；宣传语单列，未作已验证的教程质量结论。',
  182:'6与Six为来源同一数字的解释，不当成两个不同曲集。',
  185:'完整方言句可理解为当我清晨起床，按题意参考译；原引文拼写保持不变。',
  187:'last thought是所引曲名；未把题名中的Weber当作新的composer证据。',
  188:'完整德语缩略句可理解为当我清晨起床；原Fruh拼写照留，不补源字符。',
  189:'完整意语曲名可理解为哦，亲爱的回忆；作为普通参考意译，未宣称官方中文名。',
  190:'last thought是所引曲名；原C.M. Weber署名保留，不据曲名重写composer。',
  191:'Ronde按轮舞译，capriccetto为小随想曲；未按相似Rondo字形改源标题。',
  196:'Rondo按回旋曲译，原capricietto字形照留在来源，不据同名合并版本。',
  204:'4首总数与各曲1—4编号完整；Ragozy/Hujnady字形未擅自补成其他专名。',
  206:'Troi疑为数词转录残片，原词保留；不擅补s后断言3首。',
  207:'裸D与G只译D调、G调，未猜大调或小调。',
  209:'violone是历史低音乐器词形，未具体推断成现代低音提琴；其余配器完整。',
  215:'24首小品与10首伴奏歌曲分开，原Costa字形保留，未擅自更改姓名。',
  216:'总题可译吉他教学曲集；Total词义未定并留注，第II卷与梅尔茨范围保留。',
  217:'源GuitarTotal连写不明并留注；I—II卷范围及教学、指法层级完整。',
  225:'Love s ritornella含特定歌词/曲名词形，原题保留；二重奏编制与作品18可译。',
  227:'6及12指吉他弦数；未误作第6首/第12首或加入大调。',
  228:'por música指依谱演奏；未从作者常识补造书中具体乐器或弦数。',
  229:'por música指依谱演奏；原西语字符保持不变。',
  233:'gallina ciega的蒙眼游戏义有政府文化资料；作为参考题意，二重唱声部完整。',
  239:'La gallegada可能为地方专称；保留该词，田园幻想曲与变奏可明确译出。',
  256:'do与mi是C及E调名，原未指明大小调；2首及作品8保留。',
  262:'basse为低音声部，不强定低音提琴；3首总数及第1号保留。',
  263:'basse为低音声部，不强定低音提琴；3首总数及第2号保留。',
  264:'basse为低音声部，不强定低音提琴；3首总数及第3号保留。',
  265:'5首对舞曲及2首圆舞曲分别保留；来源选自歌剧不推断版本同一性。',
  268:'Afmo为题献中afectísimo缩写；siempre的永远关系保留，未新增人物身份。',
  270:'按原目录guitarra译吉他，不凭作者常识替换成维乌埃拉琴；摹真、地点、年份单列。',
  272:'edita缩略/字形未定，原标注保留；茶花女咏叹调及作品43可译。',
  277:'Alba flor、La Pesarosa的题名关系未定，保留原短语；baile译舞蹈，不猜定舞会或芭蕾。',
  280:'La Pardon的原冠词不补成Le，保留整段专名；歌剧中的舞曲关系清楚。',
  285:'2首为奏鸣曲集总数，1为加沃特所在条目；不改成第2奏鸣曲。',
  286:'2首为奏鸣曲集总数，2为玛祖卡所在条目；两处数字均保留。',
  295:'Miserere可参考译求主垂怜；只保留来源的剧中关系，不新增合唱编制。',
  304:'国家音乐图书馆列蝴蝶及Contessa dAmalfi；题名保留邻接关系，未补造来源未写的角色。',
  305:'Pizzicato为拨弦；Giovanni Strauss来源姓名照留，不按家族常识改成另一位施特劳斯。',
  306:'作品46与原作作品364分别保留；同姓作者不据作品号自动归并身份。',
  309:'两个歌剧题名同列保留，未把逗号前后的标题删除或改成两个曲目。',
  322:'nell’opera明确歌剧序曲语境；Daidi为原改编署名，未推断其composer身份。',
  323:'obligée译必奏声部，不误作强制练习或省略；未补造其他乐器。',
  329:'忠贞之死为德语完整题名参考意译；图书馆证实原题但不证实中文通行名。',
  332:'Cordes quatuor按源弦乐四重奏标签保留，未根据朱利亚尼作品目录猜改配器。',
  339:'完整意语所引曲名按哦，亲爱的回忆参考译；源Carafa署名及作品114保留。',
  343:'Fianle为终曲上下文的转录字形；4段变奏与终曲可译，original不修字符。',
  344:'Flora按意大利之花参考意译，未硬译成植物志；第1及第2部分完整。',
  345:'Tersicore是舞蹈缪斯称谓，普通参考译题意，不硬造专名中文身份。',
  346:'曲中所引意语歌词保留原句，作品147b与变奏关系明确。',
  347:'Giulianate为姓名派生专门曲集名，保留其拼写及作品148，不按单词拆译。',
  348:'16为曲数、16a为作品号；三度吉他与普通吉他是两种原乐器标签。',
  354:'括号guitar是来源声部标签，未把第1协奏曲改成第一吉他作品集。',
  355:'piano是改编钢琴声部，未改题为第1钢琴协奏曲或原作钢琴配器。',
  356:'钢琴声部与钢琴伴奏说明分别保留，未凭声部标签补造独奏乐器。',
}

REFS = {31:VIOLET,33:VIOLET,71:CYANEN+VIOLET,72:CYANEN+VIOLET,
        6:['https://ci.nii.ac.jp/ncid/BA86301638'],
        233:['https://culturarecreacionydeporte.gov.co/es/bogotanitos/juguemos-en-el-bosque/la-gallina-ciega'],
        304:['https://old.capricemusic.se/musikochteaterbiblioteket/ladda-ner-noter/boijes-samling/boijes-samling-g/'],
        329:['https://www.deutsche-digitale-bibliothek.de/item/D5RTPVNALNN7NSM7SHPUQ2NQGT3PACGR']}


def build():
    assert hashlib.sha256(INPUT.read_bytes()).hexdigest() == FROZEN
    rows = json.loads(INPUT.read_text())['entries']
    assert len(rows) == 357 and len({r['id'] for r in rows}) == 357
    titles = {}
    for line in (HERE/'legacy_cglib_archive_tail_titles.tsv').read_text().splitlines():
        fields = line.split('\t')
        assert len(fields) in (2,3), fields
        i = int(fields[0]); assert 0 <= i < 357 and i not in titles, i
        titles[i] = fields[1:]
    assert set(titles) == set(range(357))-{68}
    corpus = {r['id']:r for r in json.loads((ROOT/'work/title-review/2026-10-03/cglib.json').read_text())}
    entries=[]; ledger=[]
    for i,r in enumerate(rows):
        c = corpus[r['id']]
        assert (r['original'],r['composer'],r['display_original']) == (c['original'],c['composer'],c['display_original']),r['id']
        reason=REASONS.get(i,'完整题意、曲种及书目层级已复核；未定专名照留，中文为参考译法。')
        if i in {235,236,237,238,239,240,242,243,244,245,246}:
            reason='曲种、曲数、作品号完整；原题末年份保存在完整译文，不作为中文主标题。'
            if i==239:reason+='La gallegada地方专称照留。'
        refs=REFS.get(i,[])
        if i == 68:
            zh=display=r['original']; status='retained'
            reason='Robin既可为人名也可指知更鸟；孤立题名未给所指，保留原词。'
        else:
            full,*clean=titles[i]
            zh=wrapped(full);display=wrapped(clean[0] if clean else full);status='reference'
            assert re.search(r'[\u3400-\u9fff]',zh) and re.search(r'[\u3400-\u9fff]',display),i
        if 'opern-revue' in r['original'].lower():
            refs=[OPERA]+refs
            reason='出版社明确Opern-Revue为歌剧主题幻想曲集；曲集号、曲名及署名分别保留。'
        e=dict(id=r['id'],original=r['original'],original_composer=r['composer'],
               display_original=r['display_original'],zh=zh,display_zh=display,status=status,
               basis='cglib_archive_root_tail_complete_title_semantic_review',reason=reason,
               source_refs=refs,review_method='manual_complete_title_semantics')
        entries.append(e)
        ledger.append(dict(index=i,id=r['id'],original=r['original'],original_composer=r['composer'],
                           prior_zh=r.get('zh',''),prior_status=r.get('status'),decision=e,
                           primary_title_separated_from_full_translation=(zh!=display)))
    defects=errors(rows,entries)
    assert not defects,defects
    return rows,entries,ledger


def main():
    rows,entries,ledger=build()
    OUTPUT.write_text(json.dumps(dict(schema_version=1,entries=entries),ensure_ascii=False,indent=2)+'\n')
    digest=hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    report=dict(input_sha256=FROZEN,decision_sha256=digest,total=len(rows),
                statuses=dict(Counter(e['status'] for e in entries)),
                changed=sum(r.get('zh')!=e['zh'] for r,e in zip(rows,entries)),
                separate_primary_titles=sum(e['zh']!=e['display_zh'] for e in entries),
                complete_read_batches=[[0,180],[180,357]],guard_defects=errors(rows,entries))
    dest=ROOT/'work/title-review/2026-10-03/legacy-review'
    (dest/'cglib-archive-tail-ledger.json').write_text(json.dumps(dict(input_sha256=FROZEN,entries=ledger),ensure_ascii=False,indent=2)+'\n')
    (dest/'cglib-archive-tail-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
