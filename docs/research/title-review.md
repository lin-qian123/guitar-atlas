# 名称、题名与中文字段审读记录

本页合并2026-10-02中文文本整理、既有译名复核、2026-10-03名称调整及10-03至10-04全库题名审读的有效记录。下文最终处置统计属于10-04冻结目录；10-02的机器草稿数量、旧字段扫描和品牌阶段验证仅为历史，不代表当前待办。来源接入范围与文件实核另见[多来源接入记录](2026-10-01-integration-log.md)，线上发布另见[发布记录](publication.md)。

全量 **48,449条来源记录、16来源**已完成题名处置：**47,340条参考译文、7条有据惯用名、1,102条明确保留原名；机器题名与未处置题名均为0**。相比本轮开始时的冻结资产，共32,167条记录的译文、状态或主标题发生改变；数字不是权威中文定名数量。

## 范围与口径

本轮于2026-10-03开始，对固定的16来源、48,449条来源记录重新审读题名，包含旧参考译文和原文保留项，非仅清除19,723条机器草稿。记录包含不同版本、合集与馆藏；48,449不是跨站唯一乐曲数。未增加来源、取得乐谱或合并身份。

采用三种最终处置：有可靠中文对应的惯用名（reviewed）、完整题名语义与音乐结构已核的参考意译（reference）、有具体歧义或来源缺损原因的原文保留（retained）。没有把翻译服务结果、中文非空或局部术语修复认作完整审读。旧`reviewed`声明没有足够惯用中文名证据时，按完整语义审读结果改为`reference`或`retained`；不能把状态数量变化解读成曲目删除。保留原文是最终展示决定，不需要用户逐条批准。

## 审读与研究方法

先保存全量原题、原署名、来源ID、旧译文、状态、显示题名及资产位置，分区审读开放语义题名与仅含受限音乐句法的题名。对惯用名称、含双关的当代曲名、教材品牌、历史术语及歌剧引用，查询作曲家、出版社、演奏机构、图书馆和原作文本；其余按完整原文作参考意译。并非48,449条都逐一上网，亦不宣称所有参考译名是权威中文定名。

每条最终决定同时守卫稳定ID、精确原题与完整来源署名。主标题边界另守卫 `display_original`，避免已有中文被斜线、引号、书目责任句或污染的来源署名截掉。公开数据不包含完整审读台账、查询资料或私有路径；审校资产与私有检查报告分别保留。

## 项目名称与显示约定

中文名为 **六弦漫行**，英文原名为 **Guitar Atlas**。左上角导航显示英文名，中文主标题显示六弦漫行，双语页面标题为“六弦漫行｜Guitar Atlas”，离线版本保留“· 离线版”。GitHub仓库、Pages地址、本地根目录和Python包名继续使用 `guitar-atlas`，Codex项目名保持Guitar Atlas。源网站名称、原题、原署名、来源ID、译名及证据均不属于项目更名范围。

2026-10-03曾把用户关于导航显示语言的反馈误解为英文更名，临时使用 `Six-String Wanderings`；用户澄清后已撤回。本页只保留最终名称约定和误改已撤回这一事实，避免将中间名称作为另一个版本继续维护。

名称调整覆盖中英文README、AGENTS、TODO、许可说明中的项目称谓、公开/离线模板、生成器、包描述及旧分类标题；许可条款不变。历史验收中372个 `For *` 目录和 `for3guitars/` 共373目录的1,119份 `index.html`、`README.md`、`乐谱库目录.md` 只改品牌标题，其余字节逐文件保持一致。目录数不是来源数，也不是新入口可链接旧分类数。

最终名称阶段的页面/离线保护/公开目录/无损载荷测试85项通过；公开验证通过且 `score_file_links=0`。完整离线载荷、公共目录/压缩目录/别名/排序摘要及来源指纹未变，包括48,449来源记录、35,083不同PDF路径及350个当时可链接旧分类入口。HTTP预览显示最终导航、标题和页脚，控制台无错误或警告；离线HTML另外静态核对。这个名称阶段只改展示，未重新计算PDF哈希或解析乐谱，亦未单独推送或部署。

## 2026-10-02中文字段修订：历史基础

首轮覆盖冻结16来源、48,449来源记录和2,228原分类，最终扫描306,714个已投影题名、署名、版本和曲集文本字段。不同条目修改数如下；同一条目的多批修订只计一次，不能视为权威中文定名、乐曲实体或PDF数量。

| 资产 | 扫描条目 | 修改条目 |
| --- | ---: | ---: |
| 新增14来源曲名 | 30,316 | 11,205 |
| IMSLP work-ID曲名 | 11,393 | 247 |
| ClassClef full-ID曲名 | 6,740 | 57 |
| source-scoped音乐家署名 | 7,957 | 591 |
| source-scoped栏目 | 2,228 | 154 |

合计11,509题名、591署名、154栏目资产修订，内容包含译文、标点、依据、状态和保留原文决定。既有IMSLP/ClassClef/署名/栏目四资产合计扫描28,318字段、修改1,049条；其中独立末轮追加31条精确语义修订（IMSLP30、ClassClef1）。扩展题名的353条定点复核绑定完整来源ID、原题和署名，其余只有完整音乐语法或已有精确对应才能给参考状态；局部修复的机器草稿当时仍保持待核。

### 词义与数字

| 原题或术语 | 明确修订 |
| --- | --- |
| `Op. 47 Suite Espanola No. 1 5. Asturias (Leyenda)` | 从“操作。47”改为西班牙组曲第1号，作品47：第5曲“阿斯图里亚斯（传奇）”，保留真实编号 |
| `Fitzwilliam Virginal Book`、`Werken voor Orgel` | 菲茨威廉维吉纳琴曲集、管风琴作品集；键盘乐器不译作“处女”或“器官” |
| `Consort VIII/VI`、`Intabolatura de Lauto` | 合奏曲VIII/VI、鲁特琴指法谱；不作王妃或制表 |
| `Tento do Segundo Tom`、`Pequeña Copla Sefardí`、`Clarines y Trompetas` | 第二调式蒂恩托曲、塞法迪小歌谣、号角与小号 |
| `Choro Teimoso, Op.12`、`Pass'e mezzo a la villana`、`Aloha Oe` | 倔强的肖罗作品12、乡村风格帕萨梅佐舞曲、与你告别（Aloha Oe） |
| `Cantio Lodomerica LXXIII`、`Opus 211 No 10 Poco Allegretto` | 洛多梅里亚歌曲LXXIII，不编造773；作品211第10首：小快板（Poco Allegretto），保留程度限定 |
| `Cutting's Comfort`、`Prelúdio Microtonal No.1` | 卡廷的慰藉、微分音前奏曲第1号；不把姓氏译作切割 |
| `Viola da Gamba Sonata in G major, WK 157`、`Gavota infantil`、`Chorea rustica, f.169r` | G大调维奥尔琴奏鸣曲WK157、儿童加沃特舞曲、乡村舞曲f.169r |
| `Grande Sérénade, Op.17`、`Flaxy Cunninghams Cake Walk` | 大型小夜曲作品17、Flaxy Cunninghams凯克沃克舞曲；Grand等仅在具体体裁语境译为大/大型 |

书名号采用外层 `《》`、内层 `〈〉`，只移除真正完整的外层包围，不误删嵌套闭合符号。`Cello Suite No.5` 为第5号大提琴组曲，避免读成5把大提琴；明确复数乐曲数量用“首”。首轮115条“中文有阿拉伯数字而原题没有”线索多为合法罗马数字、外语序数或日期转换，没有为消除告警删有效信息。其他题名数字、目录号、真实括号和编辑补拟标题同样保留。

参考资料：[菲茨威廉博物馆键盘曲集说明](https://www.fitzmuseum.cam.ac.uk/explore-our-collection/highlights/Music-MS-168)、[美国国会图书馆Aloha oe及另题Farewell to thee](https://www.loc.gov/item/jukebox-21810/)。`La Noce di Benevento` 参考译为“贝内文托的胡桃树”，[Treccani的noce²词条](https://www.treccani.it/vocabolario/noce2/)说明传奇中的胡桃树；Noce不能与Nozze（婚礼）混同。资料支持原词语义，不认证项目中文名称，也不建立跨站版本身份。

`Bribes No.1` 保留Bribes并只译序号。[CNRTL词条](https://www.cnrtl.fr/definition/bribes)有法语零片/片段语义并区分英语词义，[原作品页](https://imslp.org/wiki/Bribes_No.1_(Cooper,_Valiha_Nic%C3%A9phore))未明确命名语言或含义，不能按作者国籍猜“片段”或“贿赂”。`retention_reason` 优先于题名包含“第1号”，不能因此升级成参考状态；`L'or est une chimère` 也不套生物学嵌合体。首轮将 `Solid Air` 从音乐术语规则中排除，最终完整语义审读的意译见后文。

### 姓名、角色与字段投影

姓名按完整原署名、明确姓氏和已有首字母核对；不展开仅有首字母的名字，不按近似名字合并人物。30组跨来源相同完整署名的参考显示差异已统一，但显示一致不证明人物同一。6条默茨署名及 `Ernest Shand, Study` 只把明确人名用于显示，混入作品号和题名的原字段继续保留。`Folger's Dowland Lute Book` 是书名，没有明确作曲者人名，不从书名推定道兰德的角色。

DGA的5条含U+001A损坏字符署名中，3条有完整姓名、年份及机构/出版社拼写支持参考音译；2条 `Hole…ek, Josef, 1939-` 保留原文，以省略号标损坏位置，明确尚未确认完整拼写。证据：[德沃夏克学会](https://www.dvorakantonin.com/about-us-in-english/)、[Naxos出版物后封](https://cdn.naxos.com/sharedfiles/pdf/rear/UP0118-2r.pdf)、[Schott出版条目](https://schottmusiclondon.com/the-russian-collection-vol-1-no441058.html)。原始受损值不改，机构拼写证据不等于中文惯用名审定。`Mall Simmes`、`Curro cuchares`、`Wascha mesa`、`Americano` 等无依据专名字典译法撤回为有原因的原文保留。

首轮8,518记录使用独立 `display_title_en/zh`、`display_composer_en/zh` 分离标题显示与完整转录：明确手稿标记、馆藏号、曲集来源、编曲/转写/编辑、出版责任段、页数/尺寸、生卒年移入对应字段。来源的真实补拟标题、音乐编号、别称和未知括号保留。全部来源明确 `[Arr: …]`、`(Arranged by …)`、`(arr. …)` 标签及ClassClef7条省略标点标签采用受守卫拆分；德语 `bearb.` 保留责任说明，不擅定编辑或改编角色。DGA缩写作者须与该条完整署名一致且后续明确标转写/编辑才拆分；HWV432、第7组曲等真实信息保留。来源编辑、编纂者、演奏者或角色不明姓名不能自动成为作曲者。

版本字段统一显示语言、调性、馆藏机构/号、目录编号、曲集、ISBN、出版、年代、许可、载体、尺寸和可用情况。明确语言代码与调性给中文对应并保留原文；录音、期刊按明确载体区分，不改变冻结来源范围或原生记录类型。未知资料继续未知。损坏下载标记或文件后缀仅从显示投影中移开，原文、ID和完整搜索信息继续保留。

### 旧资产的独立精确守卫与历史验收

`metadata/translations/review_2026-10-02/legacy_exact_corrections.json` 仍是可执行审读资产，包含资产路径、精确原文、完整修改前后行和原因。`scripts/apply_legacy_translation_review.py` 默认只检查；只有所有受影响资产的原文、ID、完整行和结构校验通过才允许 `--apply`。接受前批旧行也必须事先冻结，不覆盖不同或并发修改的行。这套守卫不能以10-03全库最终资产替代或因文档合并而删除。

```sh
python scripts/apply_legacy_translation_review.py --root .
python -m pytest -q tests/test_legacy_translation_review.py tests/test_catalog_translations.py
```

当日旧资产复查1,049修改全为已应用，28,318字段指定结构/音乐语境检查0问题；相关测试42项通过，其中新增审查文件18项。整体文本整理测试1,206项Python、66项Node通过，公开谱文件链接0，压缩目录与规范JSON一致。另对28,656非机器题名疑词、236条非机器数字提示、1,618明确调性逐候选核对；最后74条旧规则提示有6条误报，68条不可靠机器草稿撤回。语义候选和合法书目注记继续单列，全量扫描不等于权威名称考证。

10-02末仍有19,723机器标题和11,910有具体保留原因的字段，译名审计 `ready=false`、退出1，没有降低发布门槛。10-03至10-04已重新审读全部题名，当前冻结结果见本页开头和最终来源表，不能将旧待核数字继续列为当前状态。

当日公开/离线共享字段、350旧分类入口、35,083不同PDF路径映射与大小均保留，沿用35,385有效PDF清单关系、33,820内容种类及1,890未就绪记录。此轮为metadata-only刷新，未获取、移动或删除乐谱，未重算PDF哈希或解析。公开HTTP浏览器验证包括阿斯图里亚斯、跨源微分音和编曲/语言/原题字段；file协议被工具拒绝，离线依据静态嵌入数据、来源指纹、链接及大小检查，没有宣称实际file浏览器渲染。10-02末离线入口7,422,443字节、常用压缩目录5,639,648字节、完整审计JSON66,000,710字节；未重测浏览器启动耗时。各阶段均为本地整理，后续远端结果由发布记录单列。

## 修正示例与依据

- `Op.`统一作为作品号，`No.`作为序号；保留调性、作品号、分册、合集首数、声部、实际三重奏与曲中三声中部的区别。Concierto/Concertant、Air、Étude、Sonatina、Postlude、Folia等依音乐语义解释，不套普通词典义。
- 巴里奥斯的 `Julia Florida` 采用《花样的朱莉娅》，纠正“佛罗里达”地名式误解；参照[杨雪霏官方演奏发布](https://www.bilibili.com/list/618775304?bvid=BV1Hh4y1B7GK&oid=662381921)。
- `Que ne suis-je la fougère` 采用《但愿我是一株蕨草》，对照[原诗文本](https://fr.wikisource.org/wiki/Que_ne_suis-je_la_foug%C3%A8re)，不作“我是什么蕨类”。
- Julia Piston的 `Air varié de Vive Henry IV` 采用《〈亨利四世万岁〉曲调变奏》，保留姓名与所引曲调的关系；[乐谱出版者说明](https://www.thisisclassicalguitar.com/air-varie-de-vive-henry-iv-julia-piston/)。
- 威尔第歌剧历史题名 `Nabucodonosor` 可对应《纳布科》；[Ricordi校订版](https://www.ricordi.com/en-US/Critical-Editions/Verdi-Giuseppe-Critical-Editions/Verdi-Giuseppe-WGV/Verdi-Nabucodonosor.aspx)明确其与Nabucco的关系，[国家大剧院中英乐季资料](https://www.chncpa.org/subsite/NCPAO2023-24/pdf/index/17-18.pdf)给出中文对应。仅对原文明确的歌剧引用采用，不据此合并不同吉他版本或把同字人名都替换为歌剧名。
- 意大利歌剧书目中的 `Sinfonia nell'opera` 为序曲语境，不能机械作交响曲；[Treccani音乐术语说明](https://www.treccani.it/enciclopedia/sinfonia_%28Enciclopedia-dei-ragazzi%29/)与[法兰西学院词典](https://www.dictionnaire-academie.fr/article/A9S1723)。无此语境的裸Sinfonia保留其具体歧义。
- 《悲怆》奏鸣曲中的引用采用惯用名称，并保持实际乐章及编号；[国家大剧院中英曲目](https://ncpa-classic.cntv.cn/sxlb/five/index.shtml)、[乐季册](https://en.chncpa.org/whatson/calendar/seasonbrochure/P020180418584167476705.pdf)。
- `Click Go The Shears` 的剪羊毛语境由[澳大利亚国家图书馆乐谱记录](https://nla.gov.au/nla.obj-169068877/view)支持。`Djembe`作为乐器使用《金杯鼓》，参照[剑桥词典中文解释](https://dictionary.cambridge.org/zht/%E8%A9%9E%E5%85%B8/%E8%8B%B1%E8%AA%9E-%E6%BC%A2%E8%AA%9E-%E7%B9%81%E9%AB%94/djembe)。

## 跨来源一致性与最后补审

重新审读CGLIB首轮保留的8,271条，包括长书目和历史语言题名；六个互斥分片完整覆盖，确认可意译的题名转为参考译文，其余逐条记录原文保留原因。随后对170条再做精确补审：32条植物题、63条跨源一致性与歌剧语义、75条主题关系/缩写/语序。随后独立通读主标题中的责任括注、原题标记及整理说明，将纯责任字段移回完整参考转录；保留选集号、实际编制、调性、年份和原生版本字母。相同译法只作用于确有相同原题及署名的记录，不建立作品或版本身份合并。

- Mertz的 `Cyanen` 为矢车菊：德文历史词义参照[萨尔大学学术版词注](https://publikationen.sulb.uni-saarland.de/bitstream/20.500.11880/30472/1/bognersaar.pdf)，植物中文参照[植物智](https://www.iplant.cn/fsz/info/Centaurea%20cyanus)。`Nachtviolen` 用“夜紫罗兰”，结合[Hal Leonard英文释名](https://www.halleonard.com/product/8551177/nachtviolen)和[Myrios唱片资料](https://media.nativedsd.com/storage/nativedsd.com/wp-content/uploads/2020/07/02183610/MYR018.pdf)。这些是有词义依据的参考意译，不宣称吉他界已有唯一惯用中文曲名。
- Auber的 `Le domino noir` 为《黑色斗篷》，修正“黑色多米诺骨牌”式误解；[巴黎喜歌剧院演出说明](https://www.opera-comique.com/fr/spectacles/le-domino-noir-2024)与[法兰西学院词典](https://www.dictionnaire-academie.fr/article/A8D1848)说明domino的带帽长斗篷语义。
- `La Maja de Goya` 为《戈雅的美人》，[台湾博硕士论文原始索引](https://ndltd.ncl.edu.tw/cgi-bin/gs32/gsweb.cgi?o=dnclcdr&s=id%3D%22090NTNU0248008%22.&searchmode=basic)有吉他曲分析的中英对应；页面遇验证时停止，不绕过验证。其他歌曲与舞曲的完整音乐结构按原题逐条整理。
- 博伊托的 `Mefistofele`采用国家大剧院双语资料的《梅菲斯托斐斯》，多尼采蒂的`Lucia di Lamermoor`对应《拉美莫尔的露琪亚》，保留来源误拼而不改原文守卫。[国家大剧院乐季册](https://www.chncpa.org/subsite/NCPAO2023-24/pdf/index/17-18.pdf)、[《拉美莫尔的露琪亚》演出专题](https://www.chncpa.org/zwzt/ycjm/gjlmmedlqy/)给出中文对应。Hérold的`Zampa`虽有[巴黎喜歌剧院原作资料](https://www.opera-comique.com/fr/spectacles/zampa-ou-la-fiancee-de-marbre)，本轮未取得合适中文题名，统一保留原名；其幻想曲、回旋曲、集成曲仍完整意译音乐结构。
- `Study On The E And Variation` 按《E弦练习曲与变奏》理解，[原发布页面](https://www.thisisclassicalguitar.com/exercise-on-the-e-string-mertz-free-pdf/)明确E Saite。该词义不被用于补填来源中缺失的作曲家字段。
- `German Theme` 与Allemande舞曲不混淆；Rossini主题引用不被 `by`责任句规则误切；D. F. E. Auber为人名缩写，不能拆为多位作者。实际完整标题继续保留数量、作品号和定弦说明。
- 四条DGA封面原文中的献辞不再占据主标题，实际曲名与合集首数独立显示，原献辞、责任句、出版和版式转录仍在版本信息中。CGLIB一批补审资产缺少显示原题守卫的编译问题已修复：在原题/原署名完全一致后绑定当前投影，全量应用仍严格拒绝显示边界漂移。

## 实际生成投影的最终补审

生产生成严格检查发现861条英文主标题仅有空白边界差异，显式逐ID更新原值/新值守卫（其中620条已声明主标题守卫），保留原题、署名、中文语义与状态不变。并发现1,614条已经审读的中文被通用书目拆分规则清空：完整重读1,595条CGLIB与19条ClassClef，逐条写入精确主标题，不使用全局回退掩盖问题。纠正乐章号误作首数、独立字母误作连词或调性、作者说明混入曲名等实际内容错误。

另读277条主标题中较长Latin短语：区分合理保留的被引歌曲专名与应完整意译的外语句法，修复一般词句、歌剧曲调关系、数量、作品号和配器。保留项具体记录原因。所有最终补审绑定前一阶段完整中文和主标题旧值；没有弱化发布守卫或把“含中文”当完整语义审校。

`Solid Air` 是具有隐喻意义的歌曲题名，按[John Martyn官方原作说明](https://johnmartyn.com/discography/1970s/solid-air-1973/)采用参考意译《凝固的空气》，不将Air强译成咏叹调。Eiler三册教材恢复Book II/III/IV；Rung《Ingolf og Valgerd》歌曲恢复原剧题与第1—6号，参照[丹麦皇家图书馆原始史料](https://www.kb.dk/e-mat/dod/130021699048-bw.pdf)，未强造专名中文。旧无依据音译和不明确的专名释义可以转为明确原题保留。

## 原文保留与证据边界

`Pumping Nylon` 是技巧教材系列品牌，采用[出版社原名](https://www.alfred.com/products/pumping-nylon-second-edition-00-44950)，避免“泵送尼龙”。Andrew York的 `Moontan`、`Kinderlight` 等特殊构词保留作者原名，[作者下载目录](https://andrewyork.net/sheetmusicdownloads.html)、[出版目录](https://andrewyork.net/Publications.php/SheetMusic/)不能据以确定中文构词。`Waltzing Matilda` 含澳大利亚历史俚语，依[国家图书馆背景](https://www.library.gov.au/learn/digital-classroom/documenting-federation/national-identity)保留原名，避免误列为华尔兹。

个人、地名、歌剧、曲调或特殊拼写没有足够对应时保留原词，仍可翻译其完整且明确的音乐结构；孤立专名采用完整来源原题。残缺转录、缺题、献辞而无实际曲名、未知古和弦符号不猜补。`Sanz por la E/O/Cruz` 不据字母臆断调性；档案里的 `Ch. di Sol` 是高音谱号语境，不是G大调。

原文与来源署名继续完整保存；翻译不认证印刷总谱编制，也不把教材书名中的人名推定为作曲家。旧来源关于BWV、责任署名或作品号的冲突在原文与报告中保留，不凭近似作品更换来源身份。

## 资产与复现

- 全量最终审校池：`metadata/translations/review_2026-10-03/{legacy,cglib,archive,root}_decisions.json`；逐条完整原文与署名守卫。
- 最终主标题补充：`root_final_credit_display_supplement.json`；同时绑定前一轮完整中文及主标题旧值，只作用于已逐条审读的精确ID，完整参考转录保留于版本信息。清理后中文仅来自元数据标签的专名转为明确原文保留，不能靠加“歌剧题名”等说明凑翻译覆盖率。
- 实际投影补审：`final_projection_decisions.json`、`final_projection_expanded_decisions.json`、`final_latin_semantic_review.json`、`final_context_root_decisions.json`；在第四阶段之后按前值严格叠加，不能覆盖不同的已审译文。
- 实际页面读回补审：`final_actual_headline_decisions.json`、`final_actual_toponym_decisions.json`；位于投影补审之后，213条完整决定绑定前一阶段的 `before_zh` 和 `before_display_zh`，并继续校验原题、署名与 `display_original`。主标题边界漂移须另行精确审读，不能模糊接受或用通用回退。
- 生产中文资产：IMSLP work-ID审校、ClassClef全ID审校、新来源全ID审校与精确质量覆盖表；`scripts/apply_title_review.py`默认仅检查，`--apply`要求已存在本轮备份。
- 复现所需私有输入：默认Corpus为 `work/title-review/2026-10-03/corpus.json`；`--apply`还要求该目录 `before/metadata/translations/` 内四份原资产备份。长期整理不得按“历史备份”直接删除这些仍被入口使用的守卫；若迁移，须连同命令默认路径和验证一并更新。其它临时分片、重复输出和查看截图不属于审读决定资产。
- 主标题投影与守卫：`catalog_display.py`、`catalog_translations.py`、`title_translation_quality.py`。Delcamp中混入题名的来源署名仅按冻结的精确对应修显示，不改变原署名。
- 私有前后差异、Corpus、应用/译名/文本/压缩及离线对比：`work/title-review/2026-10-03/`；旧入口由离线生成器额外自动备份。

```bash
python scripts/apply_title_review.py
python scripts/apply_title_review.py --apply
python scripts/review_source_translations.py --quality-refresh
python scripts/export_public_site.py
python scripts/validate_public_site.py
python scripts/audit_translations.py
python scripts/audit_catalog_text.py
python scripts/refresh_legacy_category_display.py
python scripts/refresh_legacy_category_display.py --apply
python scripts/render_master_index.py . --metadata-only
python -m pytest -q
node --test tests/*.test.cjs
```

译名覆盖审计与全文本规则扫描有不同用途：ready=true证明所有声明字段具有合规最终处置，规则无错误不证明每个名称具有唯一权威译法。原文保留、缺失来源署名、实际文件编制待核和未取得的谱文件继续单列。

本轮仅刷新题名和显示。metadata-only核对来源指纹、分类、排除规则、清单映射、本地链接存在与文件大小，沿用此前PDF完整性结果；没有重新计算全库PDF哈希或解析谱面。全部工作在本地完成，未推送或部署Pages。

## 最后页面读回的定点修正

实际页面和全库字段读回又暴露135条目录、叶码或处理说明仍占主标题，以及42条同模板集锦曲的数量/语序问题。完整读这些精确原题，将纯整理标签移回全文详情；保留真实册号、作品号、音乐目录编号，不机械删除所有括号或数字。明确的Lucia di Lammermoor歌剧引用统一为《拉美莫尔的露琪亚》，裸人名不受影响。另14条地域曲名自然译为“门多萨姑娘”“萨尔塔姑娘”等，参照词义和已有中文地名；不将某地名的字母串臆断为新的作曲家身份。

第六阶段共213条精确决定，单独绑定第五阶段完整译文/主标题前值。中文只来自目录整理标签的9条未知专名转为明确原文保留。新增主标题规则拒绝“原目录标记”“歌剧题名含补入标记”“册号及作品号依此来源”等处理文字；完整源题和转录仍保留。前述英版NCPA《梦游女》资料只用于其直接支持的贝利尼作品对应，Lucia采用自身中文专题和双语乐季册，避免错配资料页。

## 最终逐来源题名统计

| 来源 | 来源记录 | 参考译文 | 惯用名 | 原文保留 | 来源署名缺失 |
| --- | ---: | ---: | ---: | ---: | ---: |
| IMSLP | 11,393 | 11,218 | 2 | 173 | 0 |
| ClassClef | 6,740 | 6,656 | 1 | 83 | 4 |
| Mutopia | 392 | 391 | 0 | 1 | 0 |
| The Guitar School | 370 | 357 | 0 | 13 | 0 |
| Classical Guitar Library | 16,544 | 15,961 | 2 | 581 | 0 |
| Delcamp | 2,911 | 2,825 | 1 | 85 | 188 |
| Andrew York | 107 | 91 | 0 | 16 | 0 |
| Guitar Downunder | 324 | 308 | 1 | 15 | 0 |
| ClassicalGuitar.org | 14 | 13 | 0 | 1 | 8 |
| FreeGuitarMusic.Net | 14 | 13 | 0 | 1 | 5 |
| Cantorion | 20 | 20 | 0 | 0 | 0 |
| Library of Congress | 5 | 5 | 0 | 0 | 5 |
| Boije Collection | 1,154 | 1,151 | 0 | 3 | 97 |
| Digital Guitar Archive | 7,481 | 7,382 | 0 | 99 | 351 |
| RISM | 672 | 650 | 0 | 22 | 44 |
| This is Classical Guitar / Werner | 308 | 299 | 0 | 9 | 158 |

题名保留理由逐条写入精确ID审校资产。译名审计`ready=true`、待核字段0；共有9,637个字段保留原文（分别包括题名、人名和栏目），860条来源记录缺失原署名，仍标为不适用，不从题名中的人名补造作曲家。

## 最终验证与速度边界

全文本规则检查覆盖299,758个实际展示、版本和曲集内容字段，明确错误0。数字线索与源括号仍单列；汉字数词、档案地址/出版编号及合法音乐注记不自动判错，规则审计不证明每个名称具有唯一权威译法。纯整理说明另有主标题错误检查，版本中的完整转录不受删除。

旧分类352个目录、1,760份视图全部备份后更新1,247份。12,548条分类成员的完整原题可检索，35,120个HTML链接及顺序、原始元数据/清单、22,637条旧清单与谱文件大小保持不变。旧清单中40条已缺失路径没有新增或恢复链接，不能与新入口的35,083条有效路径混算。执行后的重跑变化0；备份与收据保存在`work/title-review/2026-10-03/legacy-display-refresh/`。

公开与离线共享字段完全一致，压缩数据解码与正式JSON逐字段相同；原生身份、完整原题、署名、分类成员、曲集内容、共同分类、有证据关系、全部既有本地分谱、别名、知名度权重及源指纹均与本轮开始快照一致。

| 产物 | 更新前字节 | 最终字节 | 变化 |
| --- | ---: | ---: | ---: |
| `public_site/data/catalog.json` | 66,000,710 | 69,885,738 | +5.89% |
| `public_site/data/catalog.compact.json` | 5,639,648 | 5,628,832 | -0.19% |
| `index.html` | 7,422,443 | 7,431,767 | +0.13% |

浏览器优先使用压缩目录；完整JSON用于审计和兼容回退。审读台账、查询依据与私有日志不随浏览器载入，首次18张结果卡片按需显示，全文与模糊词汇按需建立。

最终公开验证、译名审计、全文本审计、离线元数据刷新、Python与Node测试均成功退出。**1,256项Python测试通过、66项Node测试通过**；Python环境另有一条既有Requests依赖兼容警告，不影响本轮结果。完整输出分别保存在`final-public-validation.log`、`final-translation-audit.log`、`final-text-audit.log`、`final-offline-render.log`、`python-tests-final.log`与`node-tests-final.log`。

第二轮旧分类刷新将最后3个IMSLP题名应用到12份视图；这些文件均与第一轮重叠，两轮最终唯一修改文件数仍为1,247。逐一读回两轮3,520份备份及1,760份当前视图；704份源catalog/manifest JSON与372项离线输入指纹保持完全一致，最终dry-run变化0。跨轮验证见`work/title-review/2026-10-03/legacy-display-refresh/two-round-verification.json`，详细收据为同目录`STAGE6_RECEIPT.md`。没有读改PDF内容。

最终实际目录另由独立审读者只读核对全部48,449条记录、六阶段精确原文/署名/显示守卫与最后213条完整前后决定；明确的处理标签、错误音乐编号模板、机器/未处置状态均为0。原文与公开显示的既有差异全部对应合法空白、文件后缀及损坏链接投影；完整中文与主标题的差异均对应书名号包装或显式责任语分离。读回证据见`archive-review/final-actual-readback.json`与`final-all-native-and-headline-guard.json`；这不是48,449条官方惯用名认证。

本地HTTP浏览器检查采用实际压缩目录：默认分类页不生成全库作品卡片；有查询时首次显示18条。检查了阿斯图里亚斯、YamkoRambeYamko、索尔/吉他二重奏、阿斯图里亚斯姑娘及拉美莫尔的露琪亚。后两项在最终导出后重新载入，叶码整理说明只在展开版本详情中可见，统一歌剧译名可跨来源检索；最终控制台错误和警告均为空。查询“索尔”的二重奏29条优先列Fernando Sor，无查询二重奏1,789条沿用参考知名度排序。用户正在打开的本地文件页没有被自动重载；其最终内嵌数据与公共压缩目录一致性由`final-comparison.json`静态核对。

本机Node单次观察（已解析正式JSON后）：建索引369.58ms、无查询二重奏筛选69.52ms、首次“索尔”二重奏检索126.07ms；这是当前机器的程序观测，不是浏览器网络测速或跨设备时延保证。报告为`final-search-benchmark.json`。审读台账没有进入浏览器载荷：压缩目录5,628,832字节，较本轮前减少0.19%；离线入口7,431,767字节，增加0.13%。完整审计JSON因保留新译文及证据字段增长5.89%，浏览器仍优先载入压缩版本。

最后的`final-comparison.json`确认：公开与离线全部共享字段一致、压缩载荷逐字段无损、48,449条来源身份/原题/署名及57,062条分类成员未变，700条已证关系、17类共同主题、全部既有本地版本链接、搜索别名、知名度权重与源快照指纹未变。此处沿用既有PDF验证快照，不宣称本轮重新做全库谱面编制、哈希或解析验证。没有推送或部署线上版本。
