# Guitar Atlas 多来源接入日志：2026-10-01


## 机构、作者与教学资料补充：2026-10-26至27

本轮从47项候选台账中的13个新增线索，正式补充5个来源、706条来源记录（699条乐谱、7条参考资料）。目录采用相同的搜索、中文参考字段、共同分类和来源身份，不按网站建立隔离书架。当前注册范围为22来源、50,498记录（50,406乐谱、92参考资料）、2,337原站分类、59,111分类关系；这些不是跨网站唯一乐曲数。

| 来源及固定范围 | 来源记录 | 原站分类 | 本轮取得的文件与边界 |
| --- | ---: | ---: | --- |
| CSUN IGRA：官方CONTENTdm固定`guitar`关键词候选 | 424 | 100 | 424份历史扫描PDF已取得并验证；没有提供逐PDF上游校验和。 |
| yawnoc/guitar：固定release/tag与LilyPond头字段 | 5 | 1 | 9份release PDF受robots限制，未请求或改换下载路线；5份谱源文字用于元数据核对，与可用离线格式分开。 |
| Maikstrings：完整吉他页与9个明确作曲者分组 | 112 | 1 | 112份PDF取得并验证；作者制版署名和原作署名分开。 |
| Derek Hasted：4个免费编制分节 | 23 | 4 | 23份PDF取得并验证；灵活编制不推算固定人数。初始人工数24已更正为23唯一定位符，没有虚构缺项。 |
| The Guitar Classroom：Classical与Guitar Ensemble两目录 | 142 | 2 | 135条乐谱、7条参考资料；151份PDF取得并验证。8个明确多文件版本的17份总谱／分谱／TAB同条关联，不同版本分开。 |

CSUN的1,145个原生ID逐一取得完整单件元数据并核对身份，结果为424收录、8明确不符、713待补器种或版本证据。官方批量接口的五个字段有100字节长度限制，只用于发现ID，不用于正式题名或作者。明确排除与待定逐项保留；合集中原作声乐题名不等于当前改编有人声，“24首独奏”中的24也不是24名演奏者。裸Bass、未明规模的管弦乐和器种择一声明保留其限制。原生ID 0有效。最初缺少`/digital`前缀的相对下载URI曾产生164次失败，均在未经批准的重定向前被拒；按同一官方前端挂载修正端点，原URI、同ID对应、旧失败事件和修正账本保留，未放行OCLC外部主机。

三个人工编订／教学来源的286份不同PDF、共1,310页完成完整文字读取与结构检查，并对异常谱页目视核对；112份Maik的实际页数均与来源一致。六条差异／范围限制通过精确原生记录与PDF字节守卫覆盖显示：Classroom的Study No.19 Op.60目录署Carulli、实际PDF署Fernando Sor；Carneirunho的实际PDF印Carneirinho；Maik的Adelita明确为双吉他且另署J. J. Olson；Recuerdos de la Alhambra另有编配署名；CSUN 1071的谱页列出一把或两把吉他选项，保留来源双吉他声明但不认定固定二重奏；CSUN 1024第10页实际有带歌词的合唱及吉他伴奏，整册归其他编制，人数未知，不推及各曲。保留来源原题和署名，显示实际谱题／差异说明，并使实际题名或人物可统一搜索；不推广为整站规则，不以谱表数代替演奏者数。另对6份CSUN扫描件实际看封面和谱页；这些扫描件无可用文字层，抽样不等于全库编制核验。全页文字覆盖不是逐页人工或逐音校对。

无原生记录ID的三个人工目录使用精确原始href的SHA-256定位符身份；编组主谱href、原始编码和大小写、所有文件及旧未发布slug保留在私有identity map。迁移仅发生在这些来源首次发布之前，旧17来源身份和译名不变。新题名采用完整原题＋完整署名参考、受限音乐术语和96条精确题名参考；无可靠中文专名时保留原文和原因。108个新原生栏目逐条审读，103条精确类别译名采用完整原文、栏目ID及人类来源页守卫，其余沿用已有译文或保留专名。作曲者、编者、编曲者、制版者分别保存；Conway (edits)不误列为编曲者。

作者明确允许的个人／教学下载进入私有离线库，其公开再分发权不据此推断。公开站只有人类可读的来源页和书目资料，谱件、下载端点、本地路径、哈希、私有库存及全文证据不进入Git或Pages。Yawnoc的CC0与robots规则分别记录。Jonty Dawson、gurgeh、eLuna、Duolenz、Martin Lohse、BNE、Soundboard Scholar与Vihuela Database八个后续线索保留在[选源研究](2026-10-01-source-expansion.md)，许可未核、证书失败、访问拒绝及不属乐谱的原因分别注明。

本轮710份PDF均已取得并验证，共1,707,045,956B；当前失败、缺失及待取得均为0，Yawnoc另有9份受限。CSUN首轮421份成功、3份暂时失败，在同一获准端点重试后3份成功；保留先前164次端点挂载错误及3次暂时失败的历史事件。新来源去重扫描7,215个对象，10组、20条路径经新鲜SHA-1／SHA-256、大小和PDF解析匹配后共享，减少44,365,593B重复内容存储；最终32组均已共享，0待替换、0失败，不合并来源作品。ClassClef独立检查保留169共享及2项与历史完全一致的安全拒绝，原件不变。

公开导出已更新为22来源、50,498记录及710条有证据的关联；浏览器核查另发现Maikstrings和Yawnoc的处理说明进入读者详情，已仅在这两个新来源公共投影中精简，实际署名、权利事实及完整私有原文保留。完整离线重建与旧数据保全通过：原49,792条公开／离线记录及旧文件映射精确不变，23项旧native输入、31,693组旧译名条目保留；40,162条本地链接零失败。新增701条记录的710个PDF入口与原生资产逐项对应。整库PDF清单39,337条，其中37,437有效、1,900未就绪、35,862份不同内容；原七条排除与MuseScore三格式各1,343条可用状态保持。最终Python2,974项、Node83项及公开／译名／446,823文本字段审计通过。新入口8,267,472B，不嵌入谱件字节；完整性与链接验收不等于全库演奏角色或逐音保真。已审计移除89项项目内提案副本、旧日志和缓存，共2,555,170逻辑字节，441项受保护文件清理前后SHA完全相同；临时验收检出在412项暂存对应后清理。原谱、来源、翻译编译输入及有效证据保留。内容cb281cf已同步仓库，[Pages运行40417774758](https://github.com/lin-qian123/guitar-atlas/actions/runs/40417774758)精确对应head并全部成功；18个HTTP内容文件均为200且大小／SHA相同。实际HTTPS的新来源、谱题异名、双吉他及跨来源“索尔”检索通过，控制台无warn/error。最终文档同步保持同一公共树；完整发布与范围证据见[发布记录](publication.md#2026-10-26至27机构作者与教学资料补充)。前置出版基线仅一个`source-expansion/baseline.zip`，六条谱面证据与首次发布前的身份／角色绑定修正保存为单一规范回执，完整PDF文字证据压缩保存。不得用历史完整性检查代替本轮新鲜验证。


## PDMX剩余候选续核：2026-10-15至16

本轮逐条复核首轮留下的759个原生候选：PDF、MXL、MIDI全部重新核对实际字节、结构及出版包定位；PDF共10,621页（A组5,111页、B组5,510页）完成全页文字提取，并对关键器种、标准谱／TAB、预备层、声乐与异常标题作定点谱面查看。全页文字覆盖与逐页人工目视、逐音符校对分别记录；音轨、谱表、GM、歌词字段都不直接等于演奏人数或器种。

| 本轮759条互斥去向 | 记录数 | 处置 |
| --- | ---: | --- |
| 正式追加 | 28 | 三格式关联、统一主题／搜索、原生身份及逐记录许可保留 |
| 明确不符当前范围 | 182 | 具名声乐／电吉他／贝司等范围例外、完整非吉他谱或已证实的大编制；逐项保留实际文件依据 |
| 仍无法确认 | 549 | 保留具体器种、角色、人数或文件对应原因及全部文件，不充作已收录 |

累计在原924条之上增加首轮296＋本轮28条，MuseScore共**1,248条**；1,641条追加候选的最终去向为324收录、768范围排除、549待定。前置1,810条器种排除及838条许可／访问快照排除另计；42条未声明格式和3份坏MXL属于全出版物的另一边界，不混入本轮759条。

本轮增加独奏2条、混合合奏25条、吉他人数／源题对应未定1条。当前为独奏725、二重奏75、三重奏13、四重奏22、吉他合奏7、混合合奏359、其他编制22，另25条保留器种／人数或来源关联边界。1,174条编制信息明确，74条保留具体限制；本轮28条中分别为17和11条。器种已明确、演奏人数未知的合奏可按器族收录，显示“演奏人数未定”，不把两条书写行显示为两位演奏者。

例如，索尔作品60按实际标准谱／TAB及137个预备计拍音符核明独奏；Gurlitt的两份Easy Guitar仍保留来源标题，实际Petites Etudes Mélodiques另外显示并可中文检索，未凭同作者和泛称免除题名警告。6355488的Claves印在谱面，保留其活动与演奏者归属边界；5951405的独立Contra Guitar按吉他属处理，保留专门器种，不改成贝司。5968722《crystals》已核明共享端口／通道音色设置冲突，保留原MIDI及可见播放警示，不宣称修复或逐音保真。

独立复核44条排除提案：43条得到完整非吉他、明确声乐或至少9个同时独立角色的支持；3455266在保守合并后仅能证明同时角色下界8，撤去大编制排除回待定，不把它误作全曲人数上界。5866416另以实际吉他角色补足9角色同刻证据，完全不计歧义Acoustic Bass。其余待定包括Primo／Secondo等无实际器种的书写名、模板与真实谱面冲突；6153971为来源Daniel与实际Fill This Place及Voice/Piano用途未闭环，4796528则为MXL书写265音与MIDI362次发音、Mandola轨名／通道来源不能完整对应，均非下载缺失或结构损坏。

三格式文件先前均已取得，本轮无新下载、无新谱件字节写入；新增84条正式曲目格式关系，复用候选对象池，相对原1,220条正式范围新增84份不同内容／4,902,637B。当前PDF关联1,248条／不同内容1,248份／87,340,851B；MXL为1,248／1,248／14,962,781B；MIDI为1,248／1,240／9,427,035B。各格式失败、缺失、待取得均为0；MIDI重复内容继续复用，不据此合并作品、版本或PDF身份。

新28条题名为6条中文参考、22条有理由保留原文；当前MuseScore为147参考、1,101保留。只对新ID补5条精确音乐语义参考，保留作品号、未解释的(2)、完整源责任转录与空署名；两份实际Petites Etudes Mélodiques的中文别名“旋律小练习曲”用于检索，不替换源标题或推定同一作品。旧题名、其他来源及已有署名决定不重放。

本轮起点1,220条及前轮有效证据冻结在单一私有continuation-baseline.zip；759条完整JSON语义与最终去向无损归并到remaining-review.json.gz。精确case中历史提案路径通过压缩包的original_proposals解析：a／b／root／a_followup／exclusion_crosscheck保留全部原始值、原文件摘要和语义摘要，不要求继续保留重复的独立JSON。已审计删除20项旧中间文件／重复日志56,701,988B，原字节可由冻结ZIP恢复；当前源记录、译名编译输入、原获取journal和候选谱件保留。完整离线验收、最终清理、测试及远端发布证据见[发布记录](publication.md)。

完整离线重建与独立保全已通过：原49,669条记录及其文件映射逐值不变，28条追加与权威CSV、当前3,744条格式守卫对应；39,169条本地链接安全有效、失败0，最终快照的1,248条曲目、3,744格式控件、2,496安全下载名和1,248次分类限制全部通过。整库PDF清单38,523条，36,633条有效、1,890条未就绪、35,068份不同PDF内容；6条精确排除保留。新入口7,928,476B，不嵌入乐谱字节；该验证不作为实际file协议浏览器验收。未录取候选对象仍由提取journal及本轮核验记录引用，保留用于复查，不作为无用文件删除。


最终清理共199个已审计文件、315,738,702逻辑字节：20项旧中间文件56,701,988B，5份无损归并提案244,118,664B，12张过程PNG912,587B，4份被完整测试替代的日志7,090B，157个缓存文件6,202,785B及1份旧入口回退7,795,588B。保留唯一最新7,904,148B回退、全部源谱件及有效来源／翻译／出版证据；ZIP与GZIP另有保留成本，不把删除逻辑字节写成净物理回收量。清理前后当前源目录、编制覆盖、精确case、译名及新入口守卫不变。

远端仓库与Pages已同步：内容8541832、测试修正b7a76a4及成功运行38773298799对应，线上18个内容文件逐个200且字节一致；实际HTTPS的1,248条来源目录、中文谱题检索和MIDI限制提示已确认。最终回执及文档同步证据见[本轮发布记录](publication.md#pdmx剩余759条续核2026-10-15至16)；重测产生的147个缓存另行清理，不重复累计主清理统计。

## PDMX全库复查与补充：2026-10-15

以下为首轮924→1,220的冻结回执；本轮759条续核结果见上节。

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

远端仓库和Pages已同步，精确提交、成功工作流、线上字节核对及实际HTTPS搜索验收见[本轮发布记录](publication.md#pdmx全库复查与追加2026-10-15)。

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


## PDMX549条候选深入核验：2026-10-16

本次固定于上轮仍未确认的549个原生编号，先冻结任务前已发布的1,248条、旧3736个不同格式对象、旧native／review／译名及公开／离线映射。新的 `deep-continuation-baseline.zip` 为55,406,162B，SHA-256为`8b5c801621e4ac7148e007f1d09e48d2eece2c1ace03fd6e8346b25a5b58d62f`；它引用保留1,220条的父基线，不复制或改写旧759条完整回执。全部1,641条plan、三格式journal、权威CSV及原924条获取／审读证据保持。五份完整出版文件共12,115,490,948B再次通过实际大小、提供者MD5和内部SHA-256检查，没有网络请求、新下载、谱件写入或原文件修补。

| 本轮549条去向 | 数量 | 边界 |
| --- | ---: | --- |
| 正式追加 | 34 | 16条编制明确，18条保留人数、谱题或MIDI播放限制 |
| 明确范围排除 | 219 | 具名声乐、电／贝斯／合成器、无活动原声吉他或大编制；逐条依据保留 |
| 仍待确认 | 296 | 293条自动器种／角色歧义，3条精确审读后仍保留的范围疑点 |
| 遗漏候选 | 0 | 所有原生身份、原始提案及最终去向可逐条追溯 |

全部549份MXL、549份MIDI及549份PDF（5,709页）都重新核对实际字节与结构，完整保留逐页PDF文字、分部、换器、实际所用ID、音符／休止／和弦／节奏活动及MIDI发音事件。两组实际视觉检查分别为27页和45页，另外对18条／23页排除证据及少量具体文件作交叉看谱，有重叠，不合计为全页视觉覆盖；不声称5,709页都经过人工视觉或逐音声学校验。初审中三项过强排除／活动性说明已撤回或纠正，包括有活动Classical Guitar的5885372、模板Elektrische Gitarre与实际Piano／E-Organ／Guitar冲突的5844883，以及把有音符声乐写成全休止的5698047。纠正前后完整差异保存在归并证据里，未把初步提案直接发布。

末轮再次实际核对两条：5545961的完整Classical Guitar声明、原生两吉他及实际MIDI轨名一致；两页PDF的Tenor／Contratenor为无歌词的C谱号复调角色标签，保留其原貌而不另加歌者，新增接收1条。5891176的Flute与Mark Tree已识别；九个实际活动角色的全曲同时峰值为7，两对角色时域不重叠仅支持可能兼奏，作者未说明实际兼奏，仍无法确认八人以内范围，因此改为具体人数／范围待定。原始过度保守理由与完整补充决定同时保留，不改写历史提案。最终追加34条，已有33条临时生成的native／review逐对象完整继承。

### 关键判据与修正

- 官方MuseScore 3.6.2完整器乐定义与多语译名用于核对精确的Acoustic Bass／Basse acoustique／Bajo acústico等名称；实际F谱号、八度移调、无TAB／换器及完整活动声明共同支持具体文件中的拨奏低音提琴。保留来源Bass guitar旧分类，绝不把裸Bass、GM32、四弦TAB或低音音域做全局低音提琴规则。5884794的四弦TAB反证仍留待核。
- Frame Drum、Congas、手拍等有限具名打击角色分别处理；Rabeca与Viola Amarantina各保留本名和真实器类，不合并为吉他。弦乐组、铜管组和复数Contrabaixos保留集合人数未定；同名钢琴行、真正齐奏与普通谱／TAB不直接换算成演奏者。4443266重复普通谱、5310359普通谱／TAB音符差异等均保持可见人数边界。
- 4796528《Drei Haselnüsse Für Aschenbrödel》的长笛265个记谱音符段，经实际反复、第一／第二结尾、连音和6个谱面颤音展开，与MIDI完整362次音高／起始拍攻击逐一对应，零未匹配；5984209的90段连音同理对应76次攻击。两者均重新从实际文件计算完整proof，绑定具体part、track和三格式摘要；原跨轨共享通道程序冲突仍保留，网页说明原MIDI导出音色限制，不宣称文件已修复或音长／力度／音色保真。解析边界参考[MusicXML反复](https://www.w3.org/2021/06/musicxml40/musicxml-reference/elements/repeat/)、[结尾](https://www.w3.org/2021/06/musicxml40/musicxml-reference/elements/ending/)和[颤音](https://www.w3.org/2021/06/musicxml40/musicxml-reference/elements/trill-mark/)的正式定义。
- 全1,641条生产scope和最终三格式审读重新完成；原324条已发布追加记录不重放其新生成review，而逐对象继承旧值。累计358收录、987排除、296待定。不存在用歌词元素、软件part数、播放音色或相近题名直接放行；也不把仅MIDI相同作PDF身份或版本合并依据。

34条新编制为独奏1、吉他与弦乐8、多乐器族合奏25；当前MuseScore共1,282条。独奏726、二重奏75、三重奏13、四重奏22、吉他合奏7，混合合奏392，其他编制22，吉他人数／类型／关联未明17、器种未明8；其中1,190条编制明确、92条保留具体边界。新记录8条保守谱题身份警示（包括重音或编码表示差异，不等于8条已确认错配）、2条文件题名不足分别记录，不能把内部模板题名自动认作另一作品；来源原题、署名、许可和原生编号保持不变。

| 当前正式格式 | 关系数 | 不同内容 | 不同内容字节 | 失败／缺失／待取得 |
| --- | ---: | ---: | ---: | --- |
| PDF | 1,282 | 1,282 | 92,098,055 | 0／0／0 |
| MXL | 1,282 | 1,282 | 15,986,797 | 0／0／0 |
| MIDI | 1,282 | 1,274 | 10,175,035 | 0／0／0 |

本次新增102条正式关系、102个相对旧正式范围新增内容，共6,529,220B，全部复用已取得对象；三格式合计3,846条关系、3,838份内容／118,259,887B。MIDI的8份重复关系只共享物理内容，不合并任何作品。34个新题名决定与16个新署名决定追加，旧条目逐对象保留；《Autumn Leaves》结合实际PDF、Joseph Kosma和既有同作曲者《秋叶》参考单独补审，其余33题保留原文，合计148参考／1,134原题保留。原始Maitetsu题名的完整可逆UTF-8误编码仅在显示层恢复，原题字节不改。

仍未闭环的代表性原因如下；全部296个编号及具体证据在私有归并回执中，而不是留给用户逐项补译或凭空猜测。

| 原生编号 | 当前具体边界 |
| --- | --- |
| 5686242 | 谱题与吉他写法线索存在，但完整原生器名及文件声明仍为Mandolino ottavo；不能仅凭题名／音域／泛音断定吉他 |
| 5884794 | Acoustic Bass模板与实际四弦TAB及源Bass guitar声明冲突，尚未确认品格低音还是低音提琴 |
| 5885372 | 活动Classical Guitar已确认，另有Oud／Shamisen与MIDI跨轨程序对应及鼓组描述未闭环；已撤回无吉他排除 |
| 5844883 | Elektrische Gitarre模板同时用于Piano／E-Organ／Guitar；谱面未写电吉他，实际吉他类型与键盘角色仍冲突 |
| 5305655 | 明确允许Voix ou Guitare 1，当前版本是人声还是两吉他编制未定，不能静默选定一个版本 |
| 5891176 | 九个活动书写角色、并奏峰7及两对可能兼奏均已核；缺少作者兼奏声明，不能确认八人以内范围 |

全549条原始提案、纠正前后交叉证据、全页文字、完整MXL／MIDI及最终去向无损保存于单一私有 `deep-review.json.gz`，读回和新鲜格式守卫通过后清理可重建图片、旧手工补写器及提案副本；`review_musescore_deep.py` 默认只读验证不依赖这些临时文件。旧759条gzip、两层有效基线、原出版包、取得journal、当前exact cases与译名及编译输入继续保留。完整离线重建、清理量、最终测试和远端发布证据接续于[发布记录](publication.md)。

## 全库宽泛编制核验：2026-10-17

本轮逐条审查原“编制尚未核明”或“吉他人数未明”的35,802条正式记录（35,717乐谱、85参考资料），另核296条MuseScore候选。允许有证据的吉他相关性、器乐家族和明确备选版本先进入统一分类；不以网站、播放音色、软件分部、曲目数或单独分谱猜人数。共同分类ID不变，“吉他人数未明”改称“吉他相关·编制未细分”；详情分别显示来源声明、谱面核对、来源审查仍待确认和具体疑点。

来源原文／目录审查包括CGLIB、DGA、Boije、RISM、Cantorion等24,963条，ClassClef／Delcamp／Mutopia等10,015条，其余799条及25条正式MuseScore未细分记录。CGLIB另核16,293条原生CMS详情；正文只有阅读器时解码原谱标签，不下载或按题名拼接其他来源，9条原未明记录因此获得有效分类。独立检查纠正562份同号category/tag响应错绑，全部重新绑定原post的ID、精确原页、题名、类别、标签及冻结字节；错误初值保留，原生catalog不变。

Delcamp人数未明的2,893条都有逐条筛查结果：2,890份实际PDF、40,662页完成全文抽取及目录SHA／大小匹配，3条分别保留HTTP 404。全文阴性不证明独奏；站点导航、单首练习或合集中的部分曲目不推广到整册。16条经封面、目录、首／末谱页等明确证据细分为12独奏、1三重奏、1四重奏和2吉他与弦乐，各条实际查看页与限制入档。另纠正两份帕格尼尼“3 Guitar Quartets”为吉他、小提琴、中提琴、大提琴混编，“3”是作品数。

IMSLP原495＋33个文件级疑点全部完成本轮可用证据审查，528份PDF的SHA-256、适用上游SHA-1、大小及解析均通过。301份无可用文本的扫描谱完成前三页OCR，保留文字、页摘要和边界。最终129份有来源／封面声明、36份支持宽泛家族、362份仍缺当前作品明确器种／角色证据，1份确认非吉他；前165份不等于全部通过精确人数及类别纯度核验。422329的ByrdALL五页实际为两支Flugelhorn与低音长号，精确排除该PDF链接，原文件、清单、作品和分类保留。九份曾被关键词误判的伴随乐器分谱继续保留，不据单独分谱否定整部作品。

在最新1,282条MuseScore出版范围上冻结独立基线，不重放旧阶段。296候选实际三格式与PDF证据全部形成最终处置：61条接纳、21条确认范围外、214条保留具体原因。新增包括日文原声吉他声明、旧复调Tenor／Contratenor音域名和Flute/Guitar、Guitarra o Piano择一版本；替代乐器不相加成人数。Voice Oohs的歌词事件实为署名注释，其范围排除依据是原生Vocals声明及谱面声部，未凭歌词计数或音色判断。空置吉他模板不作活动证据。1,641追加候选累计419接纳、1,008排除、214待定，正式MuseScore为1,343条；61条复用已验证文件，没有新下载，旧native／review、原题／许可／文件身份和历史取得回执继续继承。

5946862的MXL及来源器名为Flute，实际PDF明确写Flute/Guitar；仅以同一活动书写声部的打印备选声明收为吉他可用版本，不声称MXL原器名是吉他，也不定为二重奏。6099968同样保留Guitarra o Piano。网页详情中一项历史合成的“Guitar-related source declaration; file scope pending”占位说明改为原生source_instruments的原序器名；没有原声明则不显示该字段。该修正仅涉及来源声明的显示，实际编制核验、native、许可、文件和人数结论均不改。

最终召回复查未发现只因其他角色／人数未知而遗漏的可接纳项。214条中209条仍有活动MXL角色的器种或对应未定，另5条保留具体来源／谱件身份冲突。5926443的PDF虽印Guitar／Gtr.，对应MXL吉他声部却为0音符、74个休止，实际TAB行也全休止；5545538的活动MXL模板为Classical Guitar，PDF则印Tenor并有法语歌词。5759006为理论讲义中的模板转换，5827390存在Baixo／低音谱号冲突，5792620存在Steel Gtr／Bouzouki冲突；均未以一个软件标签强行确认吉他版本。

35,802条正式范围都有最终处置：35,791条采用完整native守卫的分类覆盖层，另11条由准确的7弦独奏／12把吉他类别语法修复。覆盖层中16,824条为有证据的吉他相关、15,235条仍未核明编制（15,230来源审查、5谱件审查），其余是明确人数、器乐家族、486条其他编制及85条参考资料。Andrew York《When Angels Sing》原声明为钢琴独奏，保留记录并归其他编制。

同一批准类别语法也补齐18条本已归独奏等分类记录的成员映射，未改变其整曲编制；连同上述11条，共29条IMSLP记录增加33个精确类别成员关联。例如8410原已通过普通吉他类别归独奏，七弦吉他改编类别现在也参加同一独奏筛选。来源原生类别及其成员关系未改，扩展弦数不误当演奏人数。

全量提案、Delcamp逐条全文筛查、IMSLP全页文字／OCR、MuseScore三格式证据、错误初值和最终去向无损归并于单一私有`sources/classification/review.json.gz`。生产分类只保留精确守卫及公开说明，完整账本不进入浏览器；仍采用重复字符串去重的压缩目录及按需索引，未加前端依赖。完整离线验收、清理与远端发布证据接续于[发布记录](publication.md)。

本轮内容提交246db01已通过精确head的Pages运行38946686415并部署，18个线上内容文件全部200且字节相同。实际HTTPS中6099968的原始器名、打印备选及未知人数说明完整可见；索尔在跨来源二重奏检索中优先显示精确署名作品。完整离线保全39,452条链接零失败，旧译名、来源身份与谱件原字节保留；最终文档ref及相同公开网站树的部署证明接续规范私有回执。
