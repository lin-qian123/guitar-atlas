"""Re-review this frozen CGLIB slice, using manually read whole-title phrases.

The parent assigned original sorted retained indices [0:2200] of legacy.json;
its remaining [2200:2757] is independently owned by root. No first-'by'
splitting, dictionary word replacement, corpus identity merge, or previous
translation-status inheritance is used.
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
INPUT = ROOT/'work/title-review/2026-10-03/cglib-retained-pass/legacy.json'
FROZEN = '8ea87cc8d8d058ec5159b82685fc8c0bf2f8eccad012cc2c5070993a68b37e00'
CORPUS = ROOT/'work/title-review/2026-10-03/cglib.json'


def main():
    assert hashlib.sha256(INPUT.read_bytes()).hexdigest() == FROZEN
    all_rows = json.loads(INPUT.read_text())['entries']
    assert len(all_rows) == 2757
    rows = all_rows[:2200]
    corpus = {r['id']:r for r in json.loads(CORPUS.read_text())}
    titles = {}
    for line in (HERE/'legacy_cglib_retained_titles.tsv').read_text().splitlines():
        i,t = line.split('\t',1); i = int(i)
        assert 0 <= i < 2200 and i not in titles, i
        titles[i] = t
    special_retained = {
      25:'Decca相关造词，题名未说明具体双关释义；保留原词。',
      28:'单词疑有转录错拼，不能补造字母或据相似词断定减弱/减和弦。',
      31:'作者姓名派生造词，保留其拼写及来源编号，不硬译成普通词。',
      32:'作者姓名派生造词，未有合适的完整中文参考释义。',
      37:'缩略口语的具体动作含义未明，不能按片段词义拼造中文。',
      40:'口语感叹/双关短句，未确认此处含义，保留原题。',
      67:'爵士口语及造词组合含义未明，不能按扁平足等字面词硬译。',
      71:'Fox相关造词可能涉及舞曲或称谓，题名未说明词义关系。',
      72:'Vamp可为爵士反复伴奏或人物称谓，此短题没有确定具体义项。',
      189:'可指响铃或响尾蛇等，来源未说明具体意象。',
      192:'区域动物/方言称谓，未确定合适中文对应，保留原词。',
      202:'Samba与lamento融合造词，缺少可确定的整体中文题名。',
      203:'可能是Misiones地理称谓或普通人物称谓，题名未说明所指。',
      208:'可能涉及古巴称谓或源转录错误，未据相似拼写补字。',
      210:'区域词形/转录拼写未确定，不能由小或儿童等猜义。',
      225:'罗马字短句未给原语言写法及可靠语义校对，不强作人名音译。',
      251:'专名或错拼均有可能，不能补成Christmas再宣布为圣诞曲。',
      265:'Papelon有食物/普通名词多义，题名未说明所指。',
      280:'字母及数字可能构成电话号码或地名标签；原格式保留，未猜定作品号。',
      302:'疑有葡萄牙语转录误差，不能按Divagando等相似拼写补字。',
      303:'区域人物称谓/方言词形未确认，保留原词。',
      306:'疑为专门曲名的截词；不能补造开头字母或强定完整曲名。',
      320:'民歌唱词音节/专名，Samba单词不足以证实整题具体歌词义。',
      333:'Gas有气体、能量及俗语双关，来源未说明题名意图，不硬译古典气体。',
      346:'英语语序/词形残缺，不能据片段拼造完整歌词。',
      348:'方言与英语混合的尾语义未明，保留原题而不恢复猜测的德语。',
      351:'方言/人物称谓未获可用释义，保留原拼写。',
      352:'方言词形的具体所指未确定，保留原题。',
      353:'方言缩略词形未确定，不能擅自补全后译作人物身份。',
      354:'词序和人物关系有疑点，不据Hahnemann姓氏补造剧情。',
      355:'英语转录语义关系不完整，不能硬译成完整爱情标题。',
      385:'Brazil/brilliance融合造词，具体双关未确定，保留原词。',
      402:'地方称谓/人物昵称，词形不足以确定具体动作或身份。',
      433:'纸牌、武器等普通义项均可能，题名未说明具体所指。',
      436:'燃料/俗语等多义短题，未确定此处意象，保留原词。',
      444:'品牌、物品或曲名引用的具体所指未明，不猜定成皮革材料。',
      456:'音译唱词未给原文，不能凭重复音节拼造中文歌词。',
      461:'古法语词形/名称未确定，不擅自现代化为朋友。',
      463:'历史题名短词含义未定，不据现代词形补造字符。',
      464:'短题可能为固有舞曲/人物称谓，不能按刷子字面义硬译。',
      466:'古法语词形可能涉及心或题名专称，未定其具体用法。',
      467:'疑有旧拼写或专名含义，不能将Rogue擅自纠为Roque。',
      481:'可指响铃或响尾蛇等，题名未说明具体意象。',
      484:'区域动物/方言称谓，未确定合适中文对应。',
      635:'地方名与普通海湾词义均可能，此短题未说明具体对象。',
      640:'区域/方言词形所指不明，保留原词。',
      661:'盖尔语罗马字题名，源拼写未获完整语义校对，不按相似英文猜译。',
      667:'题名仅为人物姓氏，保留来源姓名，不替作品补造曲种。',
      682:'唱词音节/口语造词组合，未给可用的整体释义。',
      844:'词形可能残缺或区域人名，不能补成牧羊姑娘后认定含义。',
      862:'历史歌曲题名的片段，未获完整歌词上下文，不补造后续句。',
      863:'短题可能为旧歌词/人名或数词用法，未确认其完整所指。',
      993:'Calypso与facto可能构成双关，未据片段解释标题关系。',
      1010:'歌曲名称的转录拼写不明，不能改造成其他常见民歌名。',
      1043:'地域/人物小称所指未明，保留原词而不造专名音译。',
      1044:'词形及语序疑有转录误差，不从resuello单词猜定整题。',
      1050:'源题Job与已知Toy题名不同；不补造源字母或按相似曲名改成小品。',
      1066:'历史专门题名含义未明，不按相似音节硬译。',
      1184:'locomotive/motivation融合造词，整体双关未确定。',
      1198:'专门曲名与孤立编号；不以可能的食物词义代替歌曲题名。',
      1240:'地域/人物小称所指未明，保留原词。',
      1241:'词形及语序疑有转录误差，不按单词拼造整题。',
      1314:'盖尔语罗马字题名的并列词，未有完整原语言释义，不擅造山名。',
      1316:'组合意象/双关的关系未定，不仅据tickle和dew两个词硬拼中文。',
      1333:'孤立词疑有转录误差，不能补成Faena或假定为人名。',
      1407:'宗教专门称谓的所指未定，未用概括性中文替换人物/观念身份。',
      1412:'排印用语与俗语双关均可能，短题未说明其具体意图。',
      1415:'可能为姓名合成词，未确定对应身份或整体义。',
      1420:'合成造词的意象未确定，不能凭root/witch逐词硬译。',
      1438:'宗教称号的具体所指未明，不猜定某位人物或神祇。',
      1458:'疑有英语转录错误，不补造为Finches后宣布鸟类题名。',
      1466:'月光、私酿酒及俗语等多义，题名未明确具体义项。',
      1484:'拟声/造词题名，整体语义未定，不按相似音节硬译。',
      1512:'纯数字标签，未说明日期、地址或作品编号含义，不虚加中文曲名。',
      1715:'地域舞曲称谓或人地名均可能，未确定其具体曲种。',
      1798:'Impov疑为缩写/错拼，未说明Bari与该词的关系，不补写曲种。',
      1803:'英语语序关系不清，不能据sidewalk/night片段造完整剧情。',
      1806:'黄色蛋糕与铀化合物专称均可能，未确定题名意图。',
      1826:'Hana可为花或人名等；来源罗马字未给日文写法，不强定人物或花。',
      1899:'罗马字唱词未给原语言写法及可靠校对，不强作音译。',
      1916:'委内瑞拉音乐专称的具体形式/译法未定，保留原词而不按六个权利字面翻译。',
      1975:'巴西区域族群/舞曲小称的具体所指未说明，不强作身份音译。',
      2004:'孤立转录词未确定原拼写或词义，不能补成其他民歌曲名。',
      2005:'孤立转录词未给语言上下文，未按相似英文猜义。',
      2007:'民歌曲名/音节短题的词义未明确，不强造人物中文名。',
      2155:'疑为Petenera的转录拼写，未改源字符或强定词义。',
      2156:'Pobo疑有转录错误，不能补成Polo后宣布确切舞种。',
      2184:'纯数字标签，未说明日期、拍号或其他编号意义，不虚加中文题名。',
    }
    refs = {
      138:['https://www.comune.novara.it/it/evento/conservatorio---il-mondo-della-chitarra/54701','https://www.rai.it/dl/docs/1450433335396FD5_20151221.pdf'],
      272:['https://www.henry-lemoine.com/assets/pdf/CATAGUI.pdf','https://www.womex.com/virtual/celso_machado/news/celso_machado_new'],
      2120:['https://www.henry-lemoine.com/assets/pdf/CATAGUI.pdf','https://www.womex.com/virtual/celso_machado/news/celso_machado_new'],
      1820:['https://masaaki-kishibe.com/'],
      1836:['https://masaaki-kishibe.com/'],
      1916:['https://www.naxos.com/CatalogueDetail/?id=8.554348'],
    }
    specific_reference = {
      138:'官方音乐会节目及RAI曲目列明Giuliani的Bellini歌剧序曲；据此译序曲，不把所有独立Sinfonia都当序曲。',
      82:'原标piano与吉他独奏正文并存；译出正文，声部标签照留，不猜改配器。',
      83:'第二吉他为可选伴奏，未写成必需双吉他。',
      84:'Pianostemme为附钢琴声部署名，保留原编辑关系。',
      146:'来源末括号缺闭合；仅中文显示配对，完整original不补字符。',
      270:'源andtantino疑转录，完整原拼保留；音乐结构为变奏曲。',
      272:'出版社与作曲家发布列Baiãozinho；参照巴伊昂舞曲的小称译，不改变原空格拼写或合并版本。',
      314:'历史Symfony可能是序曲/交响性段落；保留原词，仅明确译出小步舞曲。',
      358:'源歌词短题开头疑残缺，保留uspiro不补造字母；只译明确练习曲与改编关系。',
      439:'源Dizzi可能是错拼；按完整手指意象参考译，保留原拼而非改写源标题。',
      501:'源Sinfornia疑为转录，保留其拼写；不据目录号补造实际曲式。',
      575:'or只保留为原文乐器选择，不从混合清单推出人数。',
      817:'Study按音乐练习曲处理；专门题意Industrial Melanism保留原词，不断言为科学研究。',
      839:'源Guitana疑为转录，不补成Gitana；只译明确Estampa速写结构。',
      867:'原文Coeur是心，未擅改成Chœur后宣布合唱。',
      908:'源Paillo拼写不补成Pasillo；地域标签与曲种原词照留。',
      927:'源Trunifo拼写保留，不纠成Triunfo后作凯旋解释。',
      1021:'完整题意可作亚麻色头发的少女参考名，源Cheveaux错拼照留。',
      1073:'Puffe含义未确定，保留词形；只译明确夫人称谓。',
      1083:'源Robert与Lady Rich并列有署名冲突，保留此注，不据同名改人物身份。',
      1189:'仅版本号可明确翻译，Mombasa保留原词，不凭地名猜定题意。',
      1274:'源同时署Bach/Gounod/Schubert，有角色或归属冲突；原composer不改，参考题名不作归并依据。',
      1378:'历史Sinfonie曲式未明，保留词形，译牧羊人修饰；未强定现代交响曲。',
      1525:'英语尾语your残缺，歌词原词保留；仅译明确悲歌与第2首。',
      1599:'guyterne/cistre为历史吉他/西特琴，未改成现代曼陀林或人名。',
      1601:'Simon Gorlier为源书目署名，不替换composer的Morlaye来源身份。',
      1641:'角色人名保留原拼写，组曲数量层级明确。',
      1673:'ch/tr缩写关系未确定，原词保留，不推出合唱或三重奏。',
      1710:'连写/错拼的instrument词保留原文；明确如歌曲与小提琴、吉他及D调译出。',
      1714:'2a2编号含义未确定，作品号原标照留，不拆成第2首。',
      1841:'Silver Thaw的具体气象含义/意象未定，保留原短语，译明光辉。',
      1847:'Thank You For句尾未给宾语，省略保留，不补造感谢对象。',
      1916:'Naxos明确将Lauro的Seis por derecho列为Joropo，参考译其霍罗波曲式；专门短题保留，不当成六个权利或人数。',
      1979:'原composer与题末署名不同；只译东方与作品号，不重写归属。',
      2036:'salerosa是风情/魅力修饰，未误作盐或直接等同舞种。',
      2037:'salerosa是风情/魅力修饰，保留三重奏声部编号。',
      2038:'salerosa是风情/魅力修饰，保留三重奏声部编号。',
      2057:'Patio所指未定，保留原词；Alegrias为弗拉门戈曲式，不凭普通欢乐词义替代。',
      2068:'Sy含义/错拼未定，保留原词；明确探戈与法尔塞塔结构译出。',
      2088:'源Op.a8a为作品号标记，保留8a，不补造为另一版本。',
      2120:'出版社和作曲家发布列Baiãozinho；参考译小巴伊昂舞曲，源分词不改，不据名称合并文件。',
      2150:'Caña在弗拉门戈语境是曲式，不译甘蔗。',
      2151:'Caña在弗拉门戈语境是曲式，Fillo姓名保留。',
      2179:'源Zamra拼写含义边界未定，保留原词；Mora为摩尔修饰。',
      2180:'Thais及完整音乐语境可对应沉思曲，源Mediation拼写不改。',
      2199:'Right Hand为右手声部/技法标签，独立译出，不作友人姓名。',
    }
    entries=[]
    ledger=[]
    for i,r in enumerate(rows):
        c=corpus[r['id']]
        assert c['original']==r['original'] and c['composer']==r['original_composer'], r['id']
        if i in titles:
            zh=wrapped(titles[i]);status='reference'
            reason=specific_reference.get(i,'完整题名语义及音乐结构已复核；未定专名保留原拼写，中文为参考译法。')
            if r['original'].startswith('BWV '):
                reason='按来源唱词/曲种作参考翻译，目录号照留；未凭BWV编号替换成另一歌词或推定实际谱例。'
            if i in (802,803,813):
                reason='乐器清单与原二重奏标签有疑点，两者都保留；未按曲种推断人数。'
            if i in (1917,1918,1919,1920):
                reason='套曲与第1—4首层级保留，Registro等专名未按普通词义猜译。'
            if any(w in r['original'].lower() for w in ('fre ie vereinigung','freie vereinigung','gitarristische vereinigung')):
                reason='明确曲种与系列编号译出；Vereinigung系列名保留，不误作音乐即兴组合。'
            assert balanced(zh) and re.search(r'[\u3400-\u9fff]',zh), i
            display=zh
            if i in (1274,1979):display=wrapped(titles[i].split('（来源',1)[0])
        else:
            zh=r['original'];status='retained';display=zh
            reason=special_retained.get(i,'孤立人名/地名或专门曲名，来源未说明所指；保留原拼写，避免生硬音译。')
        e=dict(id=r['id'],original=r['original'],original_composer=r['original_composer'],display_original=c['display_original'],zh=zh,display_zh=display,status=status,basis='cglib_retained_legacy_second_complete_title_review',reason=reason,source_refs=refs.get(i,[]),review_method='manual_complete_title_semantics' if status=='reference' else 'specific_semantic_boundary_retention')
        entries.append(e)
        ledger.append(dict(index=i,id=r['id'],original=r['original'],original_composer=r['original_composer'],status=status,reason=reason,zh=zh,source_refs=e['source_refs']))
    assert len(entries)==2200 and len({e['id'] for e in entries})==2200
    out=HERE/'cglib_retained_legacy_supplement.json'
    out.write_text(json.dumps(dict(schema_version=1,entries=entries),ensure_ascii=False,indent=2)+'\n')
    dest=ROOT/'work/title-review/2026-10-03/legacy-review'
    (dest/'cglib-retained-ledger.json').write_text(json.dumps(dict(input_sha256=FROZEN,reviewed_slice=[0,2200],entries=ledger),ensure_ascii=False,indent=2)+'\n')
    defects=[]
    for i,e in enumerate(entries):
        if e['status']=='reference':
            missing=number_values(e['original'])-number_values(e['zh'],True)
            if missing:defects.append(dict(index=i,id=e['id'],original=e['original'],zh=e['zh'],missing=dict(missing)))
    report=dict(total=2200,input_total=2757,owned_indices_inclusive=[0,2199],input_sha256=FROZEN,output_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),statuses=dict(Counter(e['status'] for e in entries)),read_ranges_inclusive=[[0,239],[240,529],[530,829],[830,1149],[1150,1449],[1450,1799],[1800,2199]],all_id_original_composer_display_guards_checked=True,number_candidates=defects)
    (dest/'cglib-retained-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
