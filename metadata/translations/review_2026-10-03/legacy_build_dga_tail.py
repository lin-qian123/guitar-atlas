"""Materialize the individually read 531-row DGA bibliographic tail.

The numbered TSV contains complete title decisions, not word replacement rules.
Input SHA-256 and every original/composer/display guard are frozen. Preserve
credits, dedications and supplied bibliographic brackets in exact original;
do not turn source contributors into a different composer attribution.
"""
import hashlib,json,re
from collections import Counter
from pathlib import Path
from legacy_build_decisions import wrapped
from legacy_validate_decisions import balanced,number_values
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
INPUT=ROOT/'work/title-review/2026-10-03/archive-review/legacy-archive-tail-531.json'
FROZEN='d9ba391c2bf91612c87f1f7735cf12ec32b9565732c56ce0e881fa7e9b31aab7'

def main():
    assert hashlib.sha256(INPUT.read_bytes()).hexdigest()==FROZEN,'DGA frozen review input changed'
    rows=json.loads(INPUT.read_text());assert len(rows)==531
    titles={}
    for line in (HERE/'legacy_dga_tail_titles.tsv').read_text().splitlines():
        i,title=line.split('\t',1);i=int(i);assert i not in titles;titles[i]=title
    assert set(titles)==set(range(531))
    entries=[]
    detailed={
      7:'整个源题的方括号为书目补入标记，原题逐字保留；中文显示为书目支持的五重奏及变奏曲、波兰舞曲，不声称为原刊题名。',
      37:'源目录明确称balletto，不因〈Il barbiere di Seviglia〉同名而改成歌剧；保留舞剧的来源说法与作品16。',
      59:'源文pia疑有转录误差；已明确的6首变奏、华丽/简易难度和原唱段保留，不在原文补造字母。',
      80:'Danza de\' tre Moretti的具体人物/称谓含义不明，保留该唱段/舞段原词，只翻译确切舞剧主题变奏结构。',
      91:'历史Sinfonia可指序曲或交响曲；此来源仅给题名和协奏编制，未明确实际曲式，保留Sinfonia而译出明确编制与协奏修饰，不据脱离歌剧语境就断定现代交响曲。',
      95:'源书目并列Il Posto Abbandonato和方括号ADELE ed EMERICO，两者均保留，不据相似名称私自纠正或归并歌剧身份。',
      100:'历史Sinfonia可指序曲或交响曲；此来源仅给吉他独奏题名，未明确实际曲式，保留Sinfonia而译出吉他独奏，不据脱离歌剧语境就断定现代交响曲。',
      105:'方括号Zadig ed Astarte为原始书目补注，全文原题仍在original；不把该标签变成作曲者或自动归并另一同名作品。',
      127:'源1.:位置在舞剧题名前，含义不明确，完整original保留该标记；中文全字段标注来源标记，主标题只显示可确定作品34及主题变奏关系。',
      151:'Cm缩写不强行扩成调性或另一体裁；Di tanti palpiti和Cav唱段引用保留原词，明确变奏曲与回旋曲的并列结构。',
      210:'末尾dal sud可能是目录上下文指代缩写，不能译成南方；主标题仅显示明确歌剧二重唱、Allegro moderato与吉他改编。',
      272:'意大利语Danza in giro与德语Ball-Contouren题名并列，参考中文概括舞会画面并保留两种原题，不假定它们逐字同义。',
      307:'Früchteln可能是特定方言/人物谐称，不能按普通水果词硬译；保留完整德文短题，仅翻译明确吉他圆舞曲及作品167。',
      340:'意大利题名Moldavia与德语Moldau-Klänge可能涉及不同地理称谓，中文对应意大利题名并保留德语原题，不猜定河流或跨目录纠正作品号。',
      341:'来源首字符1可能为目录转录或序标，不能补造为冠词I，也不宣布为第1首；raw original保留，中文全字段记该标记，主标题显示领舞者与作品189。',
      355:'Gli Addetti为参与/附属人员称谓，参考译为参与者并保留原词，避免虚构具体机构或正式中文定名。',
      357:'Aeaciden为专名/历史称谓，语境不足以定具体中文身份，保留原词；不可机械音译成七叶树，吉他圆舞曲和作品222可明确译出。',
      413:'Pfte ad libitum为钢琴伴奏可选；保留9或6弦的选择，不能把自由加入伴奏误成随意讨论。',
      437:'Gioconda/Linda/Alcina/Ida只作为来源给出的短题原词保留，不将Gioconda猜作蒙娜丽莎；逐个曲种和1—6顺序保留。',
      459:'源quarte libri含语法/目录转录疑点，既不能断言是第四册，也不补造quattro后宣布分4册；显示明确奏鸣曲分册结构，完整原注保留在original。',
      460:'源quarte libri含语法/目录转录疑点，既不能断言是第四册，也不补造quattro后宣布分4册；显示明确奏鸣曲分册结构，完整原注保留在original。',
      469:'esimio dilettante为表扬或题献残语，不能并入音乐体裁；原书目尾文保留，主标题为吉他独奏回旋曲，不扩展G.L.身份。',
      474:'mediocre facilità为中等演奏难度，不能对作品内容作平庸评价；明确12首嬉游小品与作品37。',
      475:'mediocre facilità为中等演奏难度，不能对作品内容作平庸评价；明确12首嬉游小品与作品37。',
      476:'mediocre facilità为中等演奏难度，不能对作品内容作平庸评价；明确12首嬉游小品与作品37。',
      477:'mediocre facilità为中等演奏难度，不能对作品内容作平庸评价；明确12首嬉游小品与作品37。',
      514:'作品5ta与第1部分按明确序数解释；sda.ed.疑为版次缩写的目录转录，原拼写保留，不补造字符。中文主标题保留明确曲数、乐器、作品号与部分，未确定版次单独保留原词。',
      517:'libro 1o di sonate为方括号书目补注；原文不删除，中文全字段保留奏鸣曲第1册信息，主标题显示3首吉他奏鸣曲。',
      526:'un violino in mancanza del canto明确缺少歌者时由小提琴替代旋律，不能改成声乐与小提琴同时必需；来源署名不作身份推断。',
    }
    for i,r in enumerate(rows):
        s=r['original'];reason='本轮逐条对照完整意大利语/并列书目原题复核音乐形式、数量层级、主题与配器；中文为参考意译，未凭机器草稿或旧状态认证通行名。'
        if re.search(r'Ch\.?\.?\s*(?:di|Di)\s+Sol|Chiave di Sol',s):reason+='Ch.di Sol/Chiave di Sol为高音谱号，不能推出G大调或太阳之歌。'
        if re.search(r'\bSinfonia\s*/?\s*(?:nell|dell)',s,re.I):reason+='Sinfonia dell\'/nell\'Opera在这里是歌剧序曲；不把独立Sinfonia一律改成序曲。'
        if re.search(r'\b(?:Pot[- ]?pourri|Pot Pourri)',s,re.I):reason+='Pot-pourri在音乐中为集锦曲，不是花香。'
        if re.search(r'\b(?:Cav\.|Fant\.|Rom\.|rid\.)',s):reason+='Cav./Fant./Rom./rid.按完整音乐句法分别读作卡瓦蒂纳/幻想曲/浪漫曲/改编，非骑兵、婴儿、只读存储器或红色。'
        if 'Grimm' in s:reason+='Grimm为来源改编者署名，不是格林童话题名；其署名在original保留。'
        if '/' in s or re.search(r'(?i)dedicat|compost|trascrit|ridott|\bda\b',s):reason+='作曲、改编、编辑、题献和书目余文保留在完整original，未更改来源composer字段；清洁主标题聚焦音乐内容。'
        if '〈' in titles[i]:reason+='引号内未定唱段/专名保留原词；未借同名判定相同作品，亦不将残缺唱词强行译成完整句子。'
        reason+=detailed.get(i,'')
        refs=[]
        if i in (91,100):refs=['https://www.treccani.it/enciclopedia/sinfonia_%28Enciclopedia-dei-ragazzi%29/','https://www.treccani.it/vocabolario/sinfonia/']
        if i in (38,201):refs=['https://www.naxos.com/CatalogueDetail/?id=8.574272'];reason+='Naxos明确朱利亚尼六首Rossiniane采用罗西尼歌剧主题；中文仅为说明性参考名，第6号与作品124保留。'
        zh=wrapped(titles[i]);display=zh
        if i==127:display=wrapped(titles[i].replace('（原目录标记1.）',''))
        if i==341:display=wrapped(titles[i].replace('（来源开头标记1）',''))
        if i==7:display=zh
        if i==28:display=wrapped('来自远方：苏格兰舞曲（吉他独奏）')
        if i==67:display=wrapped('36首吉他独奏曲（随想曲）')
        if i==517:display=wrapped('3首吉他奏鸣曲，第1册')
        if i==514:
            # Do not turn a visibly uncertain sda. transcription into a sure
            # second-edition claim. Preserve exact original rather than guess.
            zh=wrapped(titles[i].replace('第2版','版次原注sda. ed.'))
            display=wrapped(titles[i].replace('（第2版）',''))
        e=dict(id=r['id'],original=s,original_composer=r['composer'],display_original=r['display_original'],zh=zh,display_zh=display,status='reference',basis='legacy_dga_tail_complete_title_semantic_reading',reason=reason,source_refs=refs)
        assert balanced(zh) and balanced(display);assert e['display_original']==r['display_original']
        entries.append(e)
    assert len({e['id'] for e in entries})==531
    output=HERE/'legacy_dga_tail_supplement.json';output.write_text(json.dumps(dict(schema_version=1,entries=entries),ensure_ascii=False,indent=2)+'\n')
    numeric=[]
    for i,(r,e) in enumerate(zip(rows,entries)):
        missing=number_values(r['original'])-number_values(e['zh'],True)
        if missing:numeric.append(dict(index=i,id=r['id'],original=r['original'],zh=e['zh'],missing=dict(missing)))
    report=dict(total=531,input_sha256=FROZEN,output_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),statuses=Counter(e['status'] for e in entries),all_id_original_composer_display_guards_checked=True,read_ranges_inclusive=[[0,134],[135,269],[270,404],[405,530]],changed_zh=sum(e['zh']!=r['zh'] for e,r in zip(entries,rows)),number_candidates=numeric)
    out=ROOT/'work/title-review/2026-10-03/legacy-review/dga-tail-validation.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
