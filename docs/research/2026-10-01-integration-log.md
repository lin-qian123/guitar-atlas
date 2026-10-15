# Guitar Atlas 多来源接入日志：2026-10-01

## PDMX全库复查与补充：2026-10-15

原先924条是固定PDMX v9出版物中的筛选子集，不是全部吉他相关记录。本轮从同一出版物的全部 **254,077条CSV与原始metadata** 重新核对，保持MuseScore原生编号、来源页、题名、署名、逐条许可和出版包成员路径。全量元数据均可解析且与CSV原生编号对应；实际器种、演奏人数和文件题名另作核验，不由音色程序、网站分类或歌词字段代替。

全部 **254,035份已声明MXL** 均逐份读取并执行ZIP路径／类型、CRC、容器和XML检查，对可解析XML核对全部记谱分部；其中 **254,032份通过结构解析、3份结构异常**。另有 **42条CSV的PDF、MXL、MIDI均无声明**，而非42份下载失败；已声明路径在出版包中缺失为0。异常原生编号74895、59439、6284及其原始字节摘要、错误和元数据保留于私有全量报告，不能断言这三份不存在吉他。全量扫描已执行与全量文件均可解析是两个不同结论。

召回结合来源器种、原始分部名、实际MXL器种／TAB与GM声明，之后分别审核精确身份、许可和实际编制。完整HTML实体的一次可逆表示差异可核明为相同原题；来源URL别名必须仍指向同一上传者与同一原生编号。不使用相似曲名、姓氏、模糊URL或程序号建立作品身份。`Gitarre`等实际分部能找回来源器种只列Piano、CSV仅列GM 0的遗漏；电吉他、贝司、人声及超出约定规模的编制继续分列排除或待核。

按原生编号去重的召回链为：12,735条有广义metadata线索，实际MXL另召回249条（原metadata无线索），合为12,984条；原始候选证据另保留3份坏MXL，共12,987条，不能将其称为吉他曲数。谱件审计池5,213条包含原924条及4,289条新ID；新ID先排1,810条实际活跃禁用角色，再对2,479条核对身份和许可，其中827条许可冲突、11条受限快照，余1,641条进入实际三格式审核。原924条完整保留，不混入新增计数；初次plan的1,456条经受控追加185条达到1,641，旧中间数不作为最终口径。

五份既有出版文件共12,115,490,948B均重新核对提供者MD5、精确大小与内部SHA-256。本轮直接读取这批已验证本地出版包，不请求MuseScore／LibreScore或改变既有来源访问边界。原924条完整记录、旧文件关系、对象及审读决定在追加基线中保存。全量扫描、召回／排除、计划扩展恢复、每格式取得结果及实际文件审读统一记录于私有 `sources/musescore/expansion/`；旧PDF／MXL／MIDI获取日志仍是原批次的历史证据。

多语言器种对应核对[MuseScore官方v3.6.2乐器词表](https://github.com/musescore/MuseScore/tree/v3.6.2/share/locale)，保留逐语言原文件URL、完整字节摘要和精确source／translation对照；裸Bass、Alto、日文“ベース”等歧义词不作无条件器种映射。156条Primo／Secondo候选的原始来源为148条Tambura＋Piano、7条Tambura、1条Bass guitar，纯吉他声明为0；音色召回不能将它们变成吉他二重奏。乐器复数名称保留集合人数未知；鼓组内多个实际打击组件不额外计演奏者。

单曲审核保留原始模板字段及自动结果。例如41996《Amor que viene cantando》的四页PDF明确标注Bandurria、Laud、Guitarra，三部MXL分别有347、309、719个非休止音符，吉他另35个和声标记；Laud内部Voice模板经该首实际谱面核明，采用独立拨弦器种，未改成曼陀林或鲁特琴。5718386则相反：PDF第6页及MXL第55小节明确“To Electric Bass”，第63至94小节247个非休止音符实际使用Electric Bass，按活跃贝司编制排除。两者均以精确原生编号、来源字段、MXL／PDF摘要和全分部名守卫，不推广成全库替换规则。

本轮1,641条新ID的PDF、MXL和MIDI各1,641份均完成结构、字节摘要与精确成员关联核验，取得失败／缺失／待取得均为0；这些是候选文件取得数，不是正式收录数。最终范围审读为298条可进入三格式核对、586条明确不符、757条实际器种／角色尚不明确；三格式核对再保留2条MIDI对应未闭环，**正式追加296条**，全MuseScore目录由924增至**1,220条**。759条未定候选的文件及原因仍在私有证据中，不当作新增成功记录。新增4,289条候选的互斥去向为：1,810条前置器种排除＋838条许可／访问快照排除＋586条实际范围排除＋759条未定＋296条收录。

新增分类：独奏165、二重奏6、三重奏4、四重奏4、吉他合奏1、混合合奏105、吉他人数未明11。原924条审读与原生记录完全保留，合并后为独奏723、二重奏75、三重奏13、四重奏22、吉他合奏7、混合合奏334、其他编制22、器种／人数或来源关联边界24。1,157条编制信息明确，63条保留具体角色、人数、谱题等边界；缺少人数时不按轨道数或谱表数补整数。

| 当前MuseScore格式 | 已关联记录 | 失败／缺失／待取得 | 格式内不同内容 | 不同内容字节 |
| --- | ---: | --- | ---: | ---: |
| PDF | 1,220 | 0／0／0 | 1,220 | 83,628,367B |
| MXL | 1,220 | 0／0／0 | 1,220 | 14,228,878B |
| MIDI | 1,220 | 0／0／0 | 1,212 | 8,970,785B |

本次收录增加888条文件关系；新增批次内部884份不同内容，其中1份MIDI与旧库重合，实际相对旧库新增883个内容对象／25,901,700B。每条原生记录及格式关系完整保留，MXL／MIDI复用不建立PDF同版关系，也不合并作品版本。中文资产只追加296条题名决定（19条参考译法、277条原名保留）及120条原生署名条目，旧条目与其他来源决定保持不变；当前MuseScore共141条参考题名、1,079条有理由原名保留。

人工异常审读按完整native、MXL、PDF摘要与全部分部名守卫，题名和编制分别记录。来源与PDF的真实题名差异继续显示；韩文分谱的声音用途、葡萄牙传统乐器与Erhu模板冲突保持待定，不强改源字段。仅见两个未标器名谱表的PDF，不冒称印有MXL的乐器名称。跨格式缺印声部保留真实MXL音符并令人数未知；吉他琴体敲击不自动增认独立打击乐手。

最终两条MIDI未闭环分别为6153971（来源Daniel与实际Fill This Place／Voice-Piano内容冲突）和5968722（crystals题名一致、原声吉他359个音符对应正常，但大提琴与钢琴共享端口／通道，program 44覆盖钢琴后续1,558个音的状态）。二者都不是下载缺失或结构损坏，保留实际字节及跨格式冲突，不用改名或默认音色豁免掩盖。

完整离线重建重新散列并解析所有适用PDF，核对MXL的ZIP／CRC／MusicXML及MIDI结构；PDF清单38,495条、有效关系36,605条、不同内容35,040份，原1,890条未就绪及6条精确排除保持。完整性验收不替代既有IMSLP的495＋33条文件级编制待核事项。本次2,654项Python、83项Node、公开边界、译名状态及全字段文本审计通过；最终全路径／控件及线上发布回执见发布记录。

最终独立保全通过：旧924条原生及review、2,769旧物理对象、全49,373条旧公开／离线记录和全部旧文件映射保持；39,085条本地路径零失效，实际NodeVM的3,660格式控件、2,440安全下载名及1,220次分类限制检查通过。最终收据为私有 `sources/musescore/expansion/preservation.json`，状态complete；完整机器来源盘点与人类日志分开维护，公开站不包含私有清单或谱件。

## 初次多来源接入概况

记录生成：2026-10-01T07:08:01.599722+00:00；注册范围版本：`2026-10-01.1`。

新增 **14 个来源**，合计 **30,316 条来源记录**。全库 **16 个来源、48,449 条记录、2,228 个原站分类、57,062 条分类关系**。作品身份、版本和合集保持来源证据，不把这些数字表述成跨站唯一乐曲数。

共同入口按编制与用途组织；所有来源参加同一搜索，原分类可展开查看。搜索覆盖原题、中文参考名、音乐家、编曲/编辑、作品号、格式与版本资料；精确筛选、中文别名及拼写恢复共用规则。

## 冻结来源与取得范围

| 来源 | 纳入记录（乐谱 / 参考） | 原分类 / 分类成员关系 | PDF 资产状态 | 中文曲名参考 / 草稿 / 保留 |
| --- | ---: | ---: | --- | ---: |
| [Mutopia](https://www.mutopiaproject.org/) | 392（392 / 0） | 1 / 392 | verified 796；restricted 16 | 239 / 153 / 0 |
| [The Guitar School](https://classicalguitarschool.azurewebsites.net/) | 370（362 / 8） | 10 / 740 | verified 254；failed 1 | 244 / 126 / 0 |
| [Classical Guitar Library](https://www.cglib.org/) | 16,544（16,544 / 0） | 1,677 / 16,555 | 未批准文件获取 | 3,983 / 12,517 / 44 |
| [Delcamp](https://www.classical-guitar-sheet-music.com/) | 2,911（2,911 / 0） | 52 / 9,346 | verified 2,908；failed 3 | 31 / 2,864 / 16 |
| [Andrew York](https://andrewyork.net/) | 107（107 / 0） | 6 / 129 | 未批准文件获取 | 12 / 94 / 1 |
| [Guitar Downunder](https://www.guitardownunder.com/) | 324（324 / 0） | 3 / 328 | restricted 325 | 91 / 233 / 0 |
| [ClassicalGuitar.org](https://www.classicalguitar.org/) | 14（11 / 3） | 3 / 14 | restricted 13 | 5 / 9 / 0 |
| [FreeGuitarMusic.Net](https://www.freeguitarmusic.net/) | 14（14 / 0） | 1 / 14 | restricted 14 | 6 / 8 / 0 |
| [Cantorion](https://cantorion.org/) | 20（20 / 0） | 1 / 20 | 未批准文件获取 | 9 / 11 / 0 |
| [Library of Congress](https://www.loc.gov/) | 5（3 / 2） | 1 / 5 | 未批准文件获取 | 0 / 5 / 0 |
| [Boije Collection](https://old.capricemusic.se/musikochteaterbiblioteket/ladda-ner-noter/boijes-samling/) | 1,154（1,153 / 1） | 23 / 1,460 | restricted 1,154 | 113 / 1,039 / 2 |
| [Digital Guitar Archive](https://digitalguitararchive.com/archive/) | 7,481（7,418 / 63） | 16 / 7,481 | 未批准文件获取 | 198 / 7,260 / 23 |
| [RISM](https://rism.online/) | 672（665 / 7） | 1 / 672 | 未批准文件获取 | 288 / 383 / 1 |
| [This is Classical Guitar / Werner](https://www.thisisclassicalguitar.com/) | 308（308 / 0） | 4 / 333 | restricted 60 | 12 / 292 / 4 |

PDF 资产状态是来源链接/容器的取得清单单位；ZIP 中每份 PDF、同一内容的重复清单关系、真实文件路径和 inode 另计，不能混用。

本轮获准取得的有效PDF清单关系合计 3964 条；其中Mutopia包含ZIP分谱，各来源重复清单仍保留。Guitar School1个HTTP500、Delcamp3个HTTP404在复试后仍未取得，原链接与失败原因不变。

## 各来源范围与信息边界

- **Mutopia**：official Guitar directory; native instrument declarations retained separately。发现完整：`True`；源署名缺失 0 条、格式未知 0 条；编制状态 `{"source_declared": 384, "unverified": 8}`。
- **The Guitar School**：All English directory records; free licensed PDFs only for acquisition。发现完整：`True`；源署名缺失 0 条、格式未知 115 条；编制状态 `{"source_declared": 370}`。
- **Classical Guitar Library**：All publicly exposed CMS posts with composer-index category; exclude voice tags and non-score editorial/accessory categories; source instrumentation remains unverified。发现完整：`True`；源署名缺失 0 条、格式未知 16,544 条；编制状态 `{"unspecified": 16544}`。
- **Delcamp**：All PDF edition/collection anchors on the homepage and directly linked site directory pages; same native PDF path merges memberships; collection internal works are not counted as separate records。发现完整：`True`；源署名缺失 188 条、格式未知 0 条；编制状态 `{"unspecified": 2911}`。
- **Andrew York**：Every product in guitar solo, collection, duo, quartet and instrumental ensemble sections of the author catalog; voice, piano/harp alternatives, contrabass and orchestral descriptions excluded; no checkout。发现完整：`True`；源署名缺失 0 条、格式未知 0 条；编制状态 `{"unspecified": 107}`。
- **Guitar Downunder**：Complete classical, fingerstyle and ensemble tables; duplicate responsive tables merged by native score path; explicitly excluded instrument labels omitted。发现完整：`True`；源署名缺失 0 条、格式未知 1 条；编制状态 `{"unspecified": 324}`。
- **ClassicalGuitar.org**：Every explicitly labeled free-music, free-exercise and free-ebook entry in the Free Stuff directory; no newsletter subscription or checkout; books separately labeled references。发现完整：`True`；源署名缺失 8 条、格式未知 1 条；编制状态 `{"unspecified": 14}`。
- **FreeGuitarMusic.Net**：Every named score anchor and explicitly named PDF viewer in the Modern and Classical Fingerstyle Solos directory; lesson guide links excluded; no Drive-file acquisition。发现完整：`True`；源署名缺失 5 条、格式未知 0 条；编制状态 `{"unspecified": 14}`。
- **Cantorion**：Public Guitar instrument search pages allowed by current robots; pagination denials retained as an incomplete boundary; explicit voice/bass/electric/orchestra instrumentation excluded; mirrored editions preserve Cantorion IDs。发现完整：`False`；源署名缺失 0 条、格式未知 20 条；编制状态 `{"unspecified": 20}`。
- **Library of Congress**：Official notated-music JSON API keyword guitar; retained only LoC item pages, excluded finding aids and explicit songs/voice/bass/electric/orchestral subjects; keyword candidates are not instrumentation-verified。发现完整：`True`；源署名缺失 5 条、格式未知 4 条；编制状态 `{"unspecified": 5}`。
- **Boije Collection**：official complete alphabetical collection index; explicit scoring exclusions retained。发现完整：`True`；源署名缺失 97 条、格式未知 0 条；编制状态 `{"unknown": 1154}`。
- **Digital Guitar Archive**：advertised official legacy API multilingual full-text keyword union; keyword discovery only。发现完整：`True`；源署名缺失 351 条、格式未知 7,481 条；编制状态 `{"unknown": 5501, "source_declared": 1980}`。
- **RISM**：official q=guitar full-text keyword discovery; scoring not approved。发现完整：`True`；源署名缺失 44 条、格式未知 672 条；编制状态 `{"unknown": 97, "source_declared": 575}`。
- **This is Classical Guitar / Werner**：Every same-site repertoire and collection entry in the canonical Sheet Music & Collections with Videos directory; linked editor shop not counted independently; edition PDFs remain restricted。发现完整：`True`；源署名缺失 158 条、格式未知 255 条；编制状态 `{"unspecified": 308}`。

Mutopia 完整目录发现395条，3条明确声乐/替代编制排除，8条 Lute/Vihuela/Guitar 声明保持待核且不下载；官方 Git 树固定到 `2144afd6f52d56c5b6995b8b589ef1268b3139f0`。Guitar School 全部370详情及有效分类页已取得，255条明确免费 CC BY-NC 文件候选，115条付费仅导航；Theory目录404回退已验证All页。

Boije完整字母目录保留1154原生馆藏号及逐题组件；文件URN robots禁止批取、对象主机robots检查403，因此只纳入目录。DGA采用官方legacy API五种吉他关键词并集9453条原始记录，排除1972条明确不符编制后纳入7481条；新Omeka系统只核入口，未混同新旧ID。RISM冻结1189关键词结果，全部详情分别用215份JSON-LD和974份官方SRU MARCXML取得，排除517条明确不符编制后纳入672条；人物/机构权威ID、馆藏及母子合集关系保留，无机构谱文件获取。

CGLIB全CMS17574篇/176页冻结，排除1030条明确声乐或非谱编辑记录，纳入16544条；元数据CC BY-SA与谱文件版权分开。Delcamp限定官方53目录的2911个版本/合集，保留不同目录关系及明确个人非商业使用限制，源文件不公开。Cantorion仅可访问首页20条；574条搜索总量的分页被robots阻止，范围不完整。Werner8个503、Downunder1个500详情保留失败及来源目录回退，未伪称全详情完整。

## 文件验证与去重

本轮共享 SHA-256 对象池：**3,940 个路径、3,940 个 inode、4,903,563,908 字节**。来源对象路径以硬链接复用，原始来源关系全部保留。对象池只覆盖本轮新增文件；既有 IMSLP 重复实体尚未全部物理去重。

每份文件检查PDF头、传输/已知预期字节数、适用的上游摘要、内部SHA-256与可解析性。没有上游摘要的来源明确记 `not_supplied`；ZIP检查安全成员路径、展开限制与每份分谱，挑战/认证/429会停止该来源并保留未尝试条目。

新增来源与IMSLP实核复用：**22组内容、44条对象/来源路径原子替换、回收16,450,021字节**。最终dry检查already_shared=22、would_link=0；所有记录和文件路径继续保留。

原ClassClef工具最终dry检查：既有共享169组，拒绝2个IMSLP锚点核验不符候选，继续保留ClassClef原件；这类安全拒绝不作为已完成去重。

最终全量离线重建：PDF清单 **37,275**、有效关系 **35,385**、未就绪 **1,890**、不同内容SHA-256 **33,820**。这是本次完整哈希/解析与归属检查，未就绪及既有6条排除继续保留；不是全库编制纯度证明。

公开版与离线版共享目录字段及搜索别名逐字段一致；离线专有的分类本地入口和总谱/分谱链接单独检查。**35,083 条不同PDF路径、350 条旧分类页入口、34,892 个被链接PDF inode**均存在且非空，失效链接0；6条精确排除及受影响旧页入口继续隔离。这里的路径/stat检查与上段全量PDF哈希解析分别记录。

IMSLP原有495条work-level目标吉他候选及33条其他分段候选仍待逐文件编制核明；本轮文件完整性验证不能替代该项审查。

## 中文字段与关联证据

新增804条人工参考词典；标题资产按完整ID、音乐家与分类按来源保存，并以精确原文防漂移。已有相同原题或全名对应只复用显示翻译；术语规则有独立参考依据。自动译文标 `machine`、尚待逐条语义复核；无法确认的署名或专名保持原文并记录原因，来源缺失署名记 `not_applicable`。

有证据的关联按类型计数：`{"identical_pdf": 239, "holding_record": 53, "shared_source_file": 255, "collection_membership": 153}`。来源明确引用同一文件、实际PDF内容一致、机构+馆藏号对应、来源合集/子条目关系分别呈现；任何同名或模糊名字都不会触发记录合并。

译名审计：`ready=false`，待复核/漏译字段 **24,994**，明确保留原文字段 **10,345**。自动草稿使发布审校门槛未通过，本轮没有推送GitHub或部署Pages。中文覆盖率与来源缺失按完整报告逐站列出，不把有中文等同于权威定名。

| 来源 | 中文曲名 / 记录 | 中文署名 / 有源署名记录 | 中文分类 / 原分类 |
| --- | ---: | ---: | ---: |
| IMSLP | 11,380 / 11,393 | 11,379 / 11,393 | 352 / 352 |
| ClassClef | 6,666 / 6,740 | 6,729 / 6,736 | 77 / 77 |
| Mutopia | 392 / 392 | 392 / 392 | 1 / 1 |
| The Guitar School | 370 / 370 | 370 / 370 | 10 / 10 |
| Classical Guitar Library | 16,500 / 16,544 | 13,492 / 16,544 | 957 / 1,677 |
| Delcamp | 2,895 / 2,911 | 1,092 / 2,723 | 12 / 52 |
| Andrew York | 106 / 107 | 107 / 107 | 4 / 6 |
| Guitar Downunder | 324 / 324 | 94 / 324 | 0 / 3 |
| ClassicalGuitar.org | 14 / 14 | 1 / 6 | 0 / 3 |
| FreeGuitarMusic.Net | 14 / 14 | 2 / 9 | 0 / 1 |
| Cantorion | 20 / 20 | 7 / 20 | 1 / 1 |
| Library of Congress | 5 / 5 | 0 / 0 | 0 / 1 |
| Boije Collection | 1,152 / 1,154 | 494 / 1,057 | 23 / 23 |
| Digital Guitar Archive | 7,458 / 7,481 | 3,823 / 7,130 | 16 / 16 |
| RISM | 671 / 672 | 90 / 628 | 0 / 1 |
| This is Classical Guitar / Werner | 304 / 308 | 139 / 150 | 4 / 4 |

中文字段覆盖按记录/分类统计，包含待复核机器草稿；音乐家按被署名记录计，并非不同音乐家人数。无源署名不伪造中文姓名；拉丁题名、字母目录、机构码或无法可靠确定的名称可保持原文，并单独保留理由。

## 验收记录

最终Python测试通过1010项，Node搜索测试通过50项。公开目录隐私/身份/分类/翻译状态校验单独运行；中文语义发布审校仍未通过，二者不混为同一验收。

浏览器检查涵盖16来源/17共同分类、索尔/巴赫/塔瑞加跨来源搜索、同一分类成员筛选、ISBN与合集、Boije/DGA馆藏关系及Mutopia/IMSLP相同PDF关系、390px手机布局。离线Rialto Ripples保留A4/Letter各四份总谱与分谱，实际点击本地总谱并在Chrome显示7页；School1039及Delcamp三条404均显示未就绪且无缺失文件链接。公共和离线浏览器error/warn为空。范围内来源计数与网站编纂者/版本编辑署名问题已修正。私有具体操作证据在 `work/source-expansion/2026-10-01/ui-qa.md`。

版本审校线索：Mutopia1200目录署名/编制原文为G. Gershwin / Guitar；实际总谱另印George Gershwin and Will Donaldson、arranged for 3 guitars by jeff covey。保留目录原文与文件证据的区别，后续增加文件级署名/编制复核，不从一个样本推断全目录。

完整测试输出、公开验证、译名审计、文件重建与去重输出位于 `work/source-expansion/2026-10-01/`；逐站请求、失败、续传和冻结证据位于 `sources/<source>/`。

## 未接入的候选

34候选的政策台账见 [`config/source_acquisition_policies.json`](../../config/source_acquisition_policies.json)。未注册来源分别记录自动访问限制、需许可、入口不可用或采集范围未确定；不把所有阻塞都写成版权问题。Free-scores、MuseScore和Musicnotes明示限制自动访问；付费订阅、登录、购买及第三方文件复用未执行。

## 目录与复现

```text
config/                     来源注册、范围与政策
scripts/source_adapters/    各站发现与规范化
scripts/catalog_*.py        共同目录、翻译和关联
sources/<source>/           私有快照、规范目录、续传状态、日志与来源对象
sources/objects/sha256/     本轮共享不可变PDF对象
metadata/translations/      持久参考对应、原文guard和草稿状态
public_site/                共用网页与无谱文件公共投影
index.html                  已验证本地链接的离线入口
work/source-expansion/      本次机器验收、统计与测试日志
```

```bash
python scripts/discover_open_sources.py --help
python scripts/discover_archive_sources.py --help
python scripts/discover_additional_sources.py --help
python scripts/acquire_source_assets.py --source mutopia --source guitarschool --source delcamp --retry-failed
python scripts/review_source_translations.py --machine-drafts --workers 2
python scripts/deduplicate_added_pdfs.py --root .
# dry日志无异常时可用 --apply，然后重跑dry
python scripts/deduplicate_source_pdfs.py --root .
python scripts/export_public_site.py
python scripts/validate_public_site.py
python scripts/audit_translations.py --output work/source-expansion/2026-10-01/translation-audit.json
python scripts/render_master_index.py .
python -m pytest -q
node --test tests/search.test.cjs tests/unified_search.test.cjs
python scripts/report_source_expansion.py
```

原始页面、谱文件、哈希对象、采集日志及机器报告均在Git忽略区；本文记录来源范围、统计单位和验收边界。原有未暂存改动保留，本轮未创建提交。


## MuseScore / PDMX 补记：2026-10-11

本次把 LibreScore 所检索的实际来源保留为 `musescore`，取得渠道为作者发布的 [PDMX v9](https://zenodo.org/records/15571083)，独立入口为 `scripts/build_musescore_library.py`，固定范围见 `config/musescore_pdmx.json`。没有从 LibreScore 应用或仓库提取数据库，没有访问 MuseScore 内部接口或取得乐谱文件。

| 单位 | 本次统计 |
| --- | ---: |
| 冻结PDMX CSV行 | 254,077 |
| 含原声吉他音色程序的候选 | 3,146 |
| 无许可冲突且可定位的候选／找到的原始元数据 | 2,300 / 2,300 |
| 最终纳入的MuseScore原生记录 | 924 |
| 未纳入的候选 | 1,376 |
| 明确纯吉他声明，人数未明／小编制混合器乐 | 682 / 242 |
| 题名参考译法／有理由保留原文／机器草稿 | 122 / 802 / 0 |
| 有中文姓名参考／保留原署名／未给可用作曲署名的作品字段 | 174 / 357 / 393 |
| 独立姓名审读项／新增来源分类 | 341 / 1 |
| 题名／署名的可逆显示编码修复 | 28 / 8 |
| 调性／上传者的可逆显示编码修复 | 70 / 1 |
| 新取得的乐谱文件／新增本地PDF链接 | 0 / 0 |

候选排除为：未知或范围外乐器529、两处原题冲突158、歌词327、原页信息冲突171、无明确吉他声明121、历史隐藏或阻塞13、大编制24、声部含排除乐器31、排除的合奏标签2。各条原文与原因保留，计数闭合；不能把元数据失败当作PDF失败或新作品数量。3条历史文件访问受限的记录仍可作为许可范围内元数据纳入，不生成下载端点。

纯吉他记录不因 `Solo`、`Guitar (2)`、TAB或音轨数被归为独奏／二重奏。混合编制使用同一套共同分类和搜索；没有按同名曲自动合并跨站作品。作者标签、编曲者与上传者分开，全文责任转录保留。终审修正38条责任角色：31条误作作曲者的字段清空，1条按明确Composer标签提取署名，不由前置姓名猜作曲者。最终责任角色为作曲531、未明315、编曲72、制谱4、编辑1、作者1；角色与作曲字段计数分别记录。原作／改编关系未核时仍为 `unspecified`。

两份元数据共384,844,503B；各文件均核对提供者MD5、实际大小及内部SHA-256。压缩档流式读取，全部254,088成员接受路径、类型和大小边界检查，未全量解包，选中元数据无缺失。许可依据是作者发布数据集的CC BY 4.0；逐谱历史CC0／Public Domain Mark及冲突字段另存，不认证当前源站或第三方谱文件许可。

原有30,316条扩展来源题名、7,957条姓名、2,228条分类翻译及资产头部逐项保持不变。具体新增决定含原题、署名及主显示边界精确守卫；终审另逐条复用23个既有已核参考，为10首常演曲补上有据中文主题名，包括《阿尔罕布拉宫的回忆》《泪》《G弦上的咏叹调》。完整中文转录保留题内署名、重复内容、日期与指法谱标记；不补源题没有的作品号、曲序或作曲署名。完整审读回执在私有 `sources/musescore/translation-review.json`，取得／排除回执在 `sources/musescore/import-report.json`。大型元数据、原始快照及机器日志均留在Git忽略区。

加入后目录为17个来源、49,373条记录（49,288条乐谱、85条参考），2,229个原分类、57,986条成员关系、17个共同分类。这是固定历史子集，尚未接入MuseScore／LibreScore的实时全库。验收及远端状态以[发布记录](publication.md)为准。

### PDMX PDF 获取补记：2026-10-12至13

在用户继续下载并融入离线库的明确授权下，按既有924条记录的原生MuseScore编号和精确出版路径，取得[同一PDMX v9出版](https://zenodo.org/records/15571083)的导出PDF。未请求MuseScore、调用LibreScore下载器或扩大历史曲目范围。作者CSV重新核对254,077行、文件大小及MD5，并逐条绑定924个编号、元数据位置、PDF位置、许可和无冲突字段；原始快照、分类、署名角色及63份译名资产保持不变。

| 文件取得结果 | 数量 |
| --- | ---: |
| 冻结目标记录 | 924 |
| 独立验收成功 | 924 |
| PDF失败 / 出版包缺失 / 未尝试 | 0 / 0 / 0 |
| 不同PDF内容 | 924 |
| 选中PDF总字节 | 63,081,172 |
| MusicXML / MIDI仅元数据条目 | 924 / 924 |

完整出版包为9,621,915,440B，通过提供者MD5及内部SHA-256检查。按robots和共享请求时钟，最多两条响应流；中途只在原进程退出后保留已收字节重分或继续精确Range，没有访问拒绝、挑战或绕过。全部255,054个TAR成员和gzip尾部通过安全扫描，未全量解包；每份选中PDF独立核对头部、实际大小、解析性及SHA-256，存入现有不可变对象池并保留来源硬链接。出版包MD5不等于提供者给出了逐PDF校验和：后者未提供。取得的是PDMX导出PDF，未取得原生MSCZ。

逐记录许可仍为829条CC0和95条Public Domain Mark历史标记；原站三条历史文件限制保留，与独立出版取得分开。PDF完整性不认证当前原站许可、音乐内容或演奏人数。统一分类、原站身份、原题和全部译名决定不因取得文件而重建；同名曲目不作为跨站合并依据。

私有最终文件回执为 `sources/musescore/acquisition_report.json`，恢复与安全扫描journal为 `sources/musescore/pdmx/pdf-extraction.json`；保留冻结归档、CSV绑定、大小与摘要、逐记录成功／失败／缺失状态及来源路径。元数据重建在已有获取journal或已验证PDF时会拒绝覆盖。公开站点继续只发布目录和来源页，本地文件不入Git或Pages。跨来源去重、完整离线重建及最终部署结果接续于[发布记录](publication.md)。


## PDMX MXL 与 MIDI 获取补记：2026-10-13

按用户明确授权，为同一冻结子集的924条MuseScore原生记录补齐PDMX v9发布的MXL和MIDI，按原生编号与权威CSV中的精确成员路径关联已有PDF。未增加曲目或来源范围，未访问MuseScore／LibreScore下载服务，未转换或取得原生MSCZ。来源原题、责任角色、历史许可、三个原站访问限制与已有PDF资产保持不变。

| 格式 | 成功记录 | 失败 | 出版包缺失 | 待处理 | 不同内容对象 | 不同内容字节 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 已有PDF | 924 | 0 | 0 | 0 | 924 | 63,081,172 |
| 新增MXL | 924 | 0 | 0 | 0 | 924 | 10,772,167 |
| 新增MIDI | 924 | 0 | 0 | 0 | 921 | 7,072,991 |

历史元数据获取状态保留；当前文件可用性以已验证assets及逐格式journal为准。新增1,848条格式／曲目关联，1,845份不同内容共17,845,158B；三格式合计2,772条文件关系、2,769份不同内容共80,926,330B。这些是文件内容与记录关系，不是不同作品数。MIDI的三对相同内容记录分别为70007／70013、4802034／4972483、5912036／5912317；仅复用物理文件，不合并原生记录、作品、版本或类别。MIDI所有清单成员计7,076,395B，重复关系不增加物理存储。

完整重新导出时发现旧关系层会把任意已验证格式的相同摘要标为相同PDF，已改为仅接受PDF及明确的PDF归档成员，并补充回归覆盖。三对MIDI的物理复用不进入`identical_pdf`，冻结的700条公开关系与原版直接相等；全部49,373条记录、2,229个分类及公开／离线共享字段保持一致。

| 完整出版包 | 精确字节数 | 发布方MD5 | 内部SHA-256 |
| --- | ---: | --- | --- |
| MXL | 1,894,335,797 | 49ffd75ecf5489c0be6d41182eb11ff7 | 01949cc0d9215e2f30924eadc8b1dd148aca90c02e2cf1999bb83df5ffe4d7a4 |
| MIDI | 214,395,208 | d920a21b2fcd99a56d9c381b39debbb2 | e444f9b466f02c9a054d31478c9886847f39c575a65ec45a0aaa1a5ee088c1d1 |

两包都核对完整大小和上游MD5，流式安全扫描各255,054个TAR成员，并检查完整gzip及TAR结束标记。MXL解压流2,177,341,440B，MIDI解压流1,557,207,040B；只保存924个精确目标成员，不批量展开全库。逐文件另外核对内部SHA-256：MXL检查ZIP路径、成员类型、CRC、容器根与完整MusicXML，不获取外部DTD或展开实体；MIDI检查SMF头、轨道、VLQ、事件边界与结束标记。完整包MD5不代表发布方提供了每个文件的校验和；结构完整性不代表逐音对应、MuseScore导入保真或声学播放验收。

MXL初次传输出现连接中断，保留1,086,628,506B后从同一固定出版页续传。较慢低段与完整高段随后在所有写入进程退出后做本地守卫重排：保留439,353,344B连续前缀和947,167,898B完整尾段，仅507,814,555B缺口拆为8个64 MiB以内区间，最多两路、共用请求时钟。独立原字节守卫、prepared事务与恢复测试通过；没有来源拒绝、切换入口或丢弃已收字节。最终整包MD5验收通过后才清理分片。这是一次传输中断和一次主动暂停，不是乐谱文件失败。

不可变内容存于 `sources/objects/sha256/`，来源视图在 `sources/musescore/objects/` 以硬链接共享；MXL和MIDI分别保持格式身份。当前逐记录结果与恢复证据固定保存在 `sources/musescore/pdmx/mxl-extraction.json`、`mid-extraction.json`，汇总为 `sources/musescore/formats-acquisition-report.json`；原PDF获取报告和journal保留。独立字段、译名、内容与硬链接核对在 `sources/musescore/verification/formats-preservation.json`，离线全库与发布验收在同目录的当前固定回执及[发布记录](publication.md)接续。

完整离线重建后，原36,309条有效PDF及34,744份不同PDF内容不变；独立最终核对旧48,449条映射、924份已有PDF、63份译名资产和全部公开共享字段均保持一致。38,202条本地链接全部有效且乐谱路径大小与清单相符；924首实际快照的三格式入口、下载命名与分类限制通过自动化检查。该入口核对不是实际file协议浏览器或逐音验收。


## PDMX 实际编制核验补记：2026-10-15

本次只核验既有924条原生MuseScore/PDMX记录，不新增来源或获取文件。此前编制仅来自历史来源声明，924条的吉他人数均未明；现以全部924份MXL、924份MIDI及924份PDF（2,913页）交叉核对。每条有独立决定，897条编制信息明确，27条完成审读后保留具体器种、人数或来源—文件关联边界。702条的主要共同分类发生变化；另50条题名关键词形成的“练习曲与教学”叠加标签保留，不计作新增曲目。

| 主要分类 | 记录数 |
| --- | ---: |
| 吉他独奏 | 558 |
| 吉他二重奏 | 69 |
| 吉他三重奏 | 9 |
| 吉他四重奏 | 18 |
| 吉他合奏 | 6 |
| 吉他与木管 | 45 |
| 吉他与弦乐 | 24 |
| 吉他与键盘／自由簧 | 40 |
| 吉他与其他拨弦 | 5 |
| 吉他与打击乐 | 11 |
| 吉他与铜管 | 4 |
| 多乐器族室内乐 | 100 |
| 其他编制／来源范围例外 | 22 |
| 吉他人数、类型或谱题关联未明 | 5 |
| 器种或编制信息未明 | 8 |
| 合计 | 924 |

表中是来源记录数，不是去重后的作品或演奏人数。6条吉他合奏包含13个记谱分部但未标分部人数的一条，归合奏而不写成13位演奏者。22条“其他编制”保留原生Guitar来源目录与三格式入口，包括实际没有活动吉他、声乐／贝司／合成器或超出原小型合奏范围的记录。原始来源、原题、署名、许可、原分类和资产清单完全保留；文件结论通过私有精确守卫覆盖层进入共同分类、详情和搜索。

### 实际文件与声部处理

- 全量提取MXL的实际part、score-instrument、所用ID、谱表、音符／和弦／节奏斜线、换器及分组；MIDI按音符发生时的端口、通道和程序变化交叉核对，PDF读取全部页面的文字与首系统布局。另对空白、集合、换器、模板冲突及多谱表等疑难实际看谱；没有声称2,913页都逐页人工视觉校对。
- 260首含299个TAB part：144个在同一part内，106个跨part TAB视图已与标准谱对应，45个是独立TAB角色，4个无内容。106对中55对完整事件对应，51对为布局与角色可确认、但装饰／节奏／音高等仍有记谱差异的视图。只归一演奏角色，不删除文件、声部或这些差异，也不声称逐音保真。
- 33个最初“无音符part”中，29个确无音符、和弦或节奏内容；2330946、4078421、5950541各一条吉他声部实际写了80、11、102个和弦，保留伴奏角色。5891304的Bầu只有一个孤立Dm，活动性保持未定。另4个已审明辅助层未额外计演奏者。
- 《冬》80344补全两吉他、小提琴与大提琴；45923是两吉他与钢琴；5830766去掉空第四吉他占位，实际三条活动吉他。真正齐奏的相同音符不按重复视图删除；MIDI内容相同也不合并作品或PDF身份。
- 口琴Harmonika、葡萄牙吉他／口琴模板冲突、巴西拨弦Viola、越南民族乐器、钢琴练习的两种伴奏写法、钹提示、大号／长号换器、竖笛集合与击打辅助层分别审读。原模板音色不覆盖谱面明确器名；独立角色、集合人数、替代与兼奏分别记录。
- MIDI跨格式声部审查为476条一致、448条播放差异已有解释、0条剩余声部对应冲突；其中8条为跨轨通道程序复用，8条为和弦符号的额外钢琴程序层。72份音符配对语义警告保留；结构通过、音色解释、来源身份与逐音／声学保真是不同结论。

### 来源题名与实际谱题

全924条另外审读原题与MXL/PDF实际题名：348条一致、534条为相容变体，37条文件题名证据不足，5条保留明确冲突。没有把内部MusicXML旧模板题目自动当成错曲。

| 原生编号 | 原来源声明与实际谱题差异 |
| --- | --- |
| 62197 | 来源Op.29 No.1，实际谱面Op.20 No.1 |
| 4902710 | 来源Bardenklänge，实际Elegie；不能据相同作者当作同一套曲版本 |
| 5179640 | 来源朱利亚尼Op.78 No.5，实际Opus059_5 |
| 5847999 | 来源Happy Birthday，实际Dance of the Ghost／Yoru’s Theme |
| 5989551 | 来源库夫纳双吉他第59课，实际Two Italian Melodies for an Orchestra／La Paloma，含11个记谱角色 |

这5条保留出版包与原生记录的原始关联；实际谱面人数与原生作品身份分开，不能用一个不同作品的独奏文件认证原记录已是独奏。网页主区显示冲突提示，详情并列实际谱题与原始题名，并支持检索实际谱题。37条缺题保留“无法单凭文件题名独立确认”的边界，不扩成已全面认证作品身份。另5865604《Miss Marple Theme》曲题相符，来源Ron Newman与谱面Ron Goodwin署名不同，证据单列，未擅自替换来源署名。

27条保留边界的编号、逐声部决定、空占位、视图差异、MIDI解释、题名判断和全部文件守卫保存在私有 `sources/musescore/verification/` 的固定instrumentation报告中。精确异常审读资产为 `metadata/instrumentation/musescore_reviewed.json`；私有 `sources/musescore/instrumentation-review.json` 对所有924条做原生字段与三格式实际字节守卫。旧来源与全部63份译名决定不重放、不改写。

语义参考包括[MusicXML乐器ID](https://www.w3.org/2021/06/musicxml40/musicxml-reference/elements/instrument/)、[标准谱与TAB实例](https://www.w3.org/2021/06/musicxml40/musicxml-reference/examples/tutorial-tablature/)、[巴西国家民俗文化中心的Viola资料](https://antigo.cnfcp.gov.br/interna.php?ID_Materia=115)，以及[Mertz Bardenklänge目录](https://imslp.org/wiki/Bardenkl%C3%A4nge,_Op.13_(Mertz,_Johann_Kaspar))和[独立Elegie目录](https://imslp.org/wiki/Elegie_(Mertz,_Johann_Kaspar))。这些参考解释具体术语或曲集边界，不替代本地文件核验。正式导出、完整离线重建、保全验收和远端回执在[发布记录](publication.md)连续更新。
