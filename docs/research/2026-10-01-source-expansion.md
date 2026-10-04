# Guitar Atlas 新来源调研与扩展路线

调研日期：2026-10-01（Asia/Shanghai）。状态：**候选调研完成，尚未接入新来源**。

## 结论与建议顺序

建议把 Guitar Atlas 建成同时可检索作品、编曲、出版版本、馆藏和谱格式的来源图谱。近期优先评估 **Mutopia、Boije Collection、The Guitar School – Iceland**；以 **Digital Guitar Archive（DGA）和 RISM** 扩展馆藏发现与权威关系。Delcamp、CGLIB、独立编订者和出版社补充版本与教学资料；大型社区、商业平台与中文指弹站保留为合作或扩围候选。

本次列出 **34 个新候选**，另保留两个待核名称。它们的优先级是本项目的研究判断；目录可读、PDF 免费、存在 API、允许个人使用、允许自动采集和允许公开复用是不同事实。具体许可必须落实到所选数据和版本，不能按网站整体推断。涉及明确禁止自动采集的平台，后续应使用官方合作、授权数据或人工选编路径。

现有公开目录于本次本地读取确认如下。它是既有来源快照，未重新抓取上游或验证全库 PDF。

| 来源 | 来源记录 | 分类 | 备注 |
| --- | ---: | ---: | --- |
| IMSLP | 11,393 | 352 | 经配置限定的古典/原声吉他与室内乐 |
| ClassClef | 6,740 | 77 | 6,739 乐谱记录、1 参考资料 |
| 合计 | 18,133 | 429 | 19,573 条分类关系；不是跨网站唯一乐曲数 |

本地依据：`config/sources.json`、`public_site/data/catalog.json`、`scripts/catalog_sources.py`、`AGENTS.md`。现有注册表仍只有 IMSLP 和 ClassClef。本报告与同目录候选清单不属于批准的生产配置。

## 1. 最值得优先评估的五个来源

| 来源 | 能增加什么 | 站方规模口径 | 建议接入方式与证据 |
| --- | --- | --- | --- |
| **Mutopia** | 可编辑 LilyPond 谱源、重排 PDF、MIDI、维护者与原始版次 | Guitar 分类 **395 条**，不是跨源新增独立作品数 | 优先使用[官方源码库](https://github.com/MutopiaProject/MutopiaProject)固定提交快照；[分类计数](https://www.mutopiaproject.org/browse.html)、[吉他目录](https://www.mutopiaproject.org/cgibin/make-table.cgi?Instrument=Guitar)。[Aguado Op.3 No.1 / ID 2041](https://www.mutopiaproject.org/cgibin/piece-info.cgi?id=2041)有原版、编制、维护者、A4/Letter PDF 和 CC BY-SA 4.0；逐条保留实际许可。 |
| **Boije Collection** | 19世纪原始印本、手稿及 Mertz 原稿；可追溯馆藏版本 | [官方集合页](https://old.capricemusic.se/musikochteaterbiblioteket/ladda-ner-noter/boijes-samling/?lang=en)称近 **1,000 部作品**；编号/文件数另计 | [可用官方字母目录](https://old.capricemusic.se/musikochteaterbiblioteket/ladda-ner-noter/boijes-samling/boijes-samling-a/)有标题、作品号、Boije 编号、URN 与来源署名条款；使用 Boije 原生号保存身份。目录包含声乐、特殊多弦及参考资料，逐项选编制。 |
| **The Guitar School – Iceland** | Eythor Thorlaksson 等编订的教学、独奏和二至四重奏版本 | [首页](https://classicalguitarschool.azurewebsites.net/)称 **3,726 页、165 作者**；不是 3,726 首曲 | [全目录](https://classicalguitarschool.azurewebsites.net/en/All)、[La Pastoreta / ID 4007](https://classicalguitarschool.azurewebsites.net/en/Download/4007)提供编曲者、四重奏、总谱/分谱、等级、ISBN、9页及 CC BY-NC 4.0；该免费子集适合先接，其他条目含付费。 |
| **Digital Guitar Archive** | 跨机构吉他书目、馆藏号、出版与版本线索，帮助发现更多原始档案 | [旧检索页](https://digitalguitararchive.com/archive/)显示 **31,599 records / 52,246 pages**；不能作为可下载 PDF 数 | 官方提供[API/MCP说明](https://www.digitalguitararchive.com/digital-guitar-archive-search-api-and-mcp-server/)与[作者维护的代码](https://github.com/rcoldwell/mcp)。本次实际 GET 验证 API；先用于发现和回链，数据公开再利用条款仍待核。 |
| **RISM Online** | 权威人物、馆藏机构、音乐源文献、手稿与合集关系；使目录逐步成为图谱 | 本次 `q=guitar` 返回 **1,189 关键词结果**；不是已审定吉他范围数 | [官方数据许可](https://rism.info/fr/community/data-services.html)为 CC BY 3.0；[JSON-LD API](https://rism.online/docs/api/api/)适合结构化接入。[Giuliani 手稿记录 452020028](https://rism.online/sources/452020028)有母合集与馆藏关系。许可适用于其元数据，外链扫描件另核。 |

**Mutopia 是最稳妥的第三来源候选。** 它规模适中、身份和许可字段明确，又有可固定提交的谱源。主要收益是版本与可编辑格式，而非保证大量新作品。Boije 与 The Guitar School 可形成随后两个适配器，但先限定编制与许可明确的子集。

Boije 官方条款允许注明来源后出版，并要求向馆方寄两份。该表述不应被简化成无条件开放；本项目公开端继续只给来源页链接。Boije 18 的 URN 已点开但本次 PDF 获取失败，另一个 Boije 772 样本 PDF 可打开；单一样本不证明全收藏可用。[官方目录与条款](https://old.capricemusic.se/musikochteaterbiblioteket/ladda-ner-noter/boijes-samling/boijes-samling-a/)

The Guitar School 的 `/en/Download/4007` 实际是记录页，`/en/Files/4007.pdf` 才是文件；现有公共 URL 校验一律拒绝 `/download/` 路径，未来需按该来源的明确路径规则处理，不能把这个作品页误判为下载文件。样本谱面确认四吉他改编；尚未进行项目级文件哈希和全量解析验证。[记录页](https://classicalguitarschool.azurewebsites.net/en/Download/4007)

### DGA 的接口实测及重要限制

本次用带研究用途 User-Agent 的普通 GET 请求核实：

| 接口 | 结果 | 含义 |
| --- | --- | --- |
| [OpenAPI](https://digitalguitararchive.com/archive/api/openapi.json) | HTTP 200，JSON，API 2.0.0 | 提供 `/sources`、`/search`、`/record/{id}` |
| [sources](https://digitalguitararchive.com/archive/api/sources) | HTTP 200；15 个来源组，`record_count` 合计 **20,526** | 这是 legacy API 的分组统计，与旧首页 31,599 口径不一致；没有合并成一个总量 |
| `search?author=Sor&limit=1&offset=0` | HTTP 200；返回 ID **1260** | 有 Sor 原署名、题名、`Boije 465` 馆藏号、原始机构文件链接；大量其他字段为空，继续保持未知 |

API 的样本 `total=1` 不足以证明 Sor 仅有一条记录；分页与总数字段行为须在适配时复核。官网还指向新的 Omeka S 检索系统，不能假设新旧系统 ID 和覆盖范围相同。DGA 明确不托管这些机构的谱文件：应保留 DGA 的发现证据及原机构身份，再到原机构核查权限、当前页面与文件。其 API 软件的 ISC 许可也不等于整个馆藏数据库的复用许可。[官方代码](https://github.com/rcoldwell/mcp)、[旧检索声明](https://digitalguitararchive.com/archive/)

API 可作为继续调查的线索，涉及瑞典、丹麦、爱尔兰、德国、奥地利、意大利、美国等机构。当前只核实接口和少量元数据；没有把这些馆藏自动注册成 Guitar Atlas 来源，亦未证明每条已有数字文件。

### RISM 的接口实测

普通 GET `https://rism.online/search?q=guitar`，请求头 `Accept: application/ld+json`，本次返回 HTTP 200、JSON-LD 和 `totalItems=1189`。首条为 Giuliani 的 *La Risoluzione*，身份 `sources/452020028`，母合集 `sources/452020027`，有手稿类型、人物和馆藏线索。关键词仍可能命中注记、特殊吉他或非目标编制，不能直接导入全部结果。[API说明](https://rism.online/docs/api/api/)、[代表记录](https://rism.online/sources/452020028)

初次人为指定 `rows=1&mode=sources` 返回 400；改用官方默认检索成功。未来应按接口返回的 `pageSizes`、模式和分页链接续传，不硬编码未经确认的参数。本次没有取得或验证这批记录的外链扫描件。

## 2. 古典专门站、独立编订者与出版社

这些来源与现有古典/原声方向接近，常见收益是新编订、教学配套、当代原作或出版证据。它们的免费项目与付费项目须分别处理。

| 候选 | 增量、格式与代表记录 | 建议及边界 |
| --- | --- | --- |
| **Delcamp / Classical-guitar-sheet-music.com** | [总站](https://www.classical-guitar-sheet-music.com/)自称约18,000曲、40,000余页；[Tárrega目录](https://www.classical-guitar-sheet-music.com/francisco-tarrega/)与作曲家全集、方法册、等级目录 | **目录优先**。本次打开的[Tárrega编订版PDF](https://www.classical-guitar-sheet-music.com/apdfsdelcamp/Francisco_Tarrega_Complete_Guitar_Works.pdf)为2026-09-02版、101首、236页；第2页限定个人使用并禁止再分发。条款针对该编辑版，不推广到历史原作。汇编需区分册与内部曲目。 |
| **CGLIB / Classical Guitar Library** | [作曲家目录](https://www.cglib.org/composers/)、作品号、年代、风格/编制标签；[Walzer-Guirlande Op.47](https://www.cglib.org/walzer-guirlande-in-e-major-op-47/)有独立页面、内嵌谱览 | **目录优先**。总量未核；首页分页数不是作品数。页脚标 CC BY-SA 4.0，单谱同时提示各国谱文件版权需另核；不能据页脚认定所有第三方谱已开放。实际 HTML 可读，未验证样本文件完整性。 |
| **Classical Guitar Shed** | [编曲目录](https://classicalguitarshed.com/sm-guitar-arrangements/)称1,300余曲；[Bach Bourrée二重奏](https://classicalguitarshed.com/sm-bach-bourree-duo/)有PDF、难度和教学；常带标准谱/TAB | **教学层优先**。[Usage Rules 所在目录](https://classicalguitarshed.com/free-guitar-sheet-music/)许可段本次只有官方搜索抽取证据，显示编曲保留版权但准许带署名的非商业分享；生产接入前需固化完整条款，不能标全站已核准。 |
| **This is Classical Guitar / Werner Guitar Editions** | [作品目录](https://www.thisisclassicalguitar.com/sheet-music-for-classical-guitar/)、等级/时代/独奏合奏/视频；[Late-Beginner Collection](https://www.thisisclassicalguitar.com/late-beginner-collection-free-pdf/)18首、25页 | **目录与教学关联优先**。样本免费PDF仍标© Bradford Werner 2023、All Rights Reserved；免费不代表开放授权。编辑者网站和商店属于关联渠道，不能双算同版。全站数量未知。 |
| **Tecla Editions** | [数字目录](https://tecla.com/tecla-digital-downloads-complete-list/)、[Sor 27个免费条目](https://tecla.com/fernando-sor-the-27-free-to-everybody-files/)、[Carcassi Op.60 No.2](https://tecla.com/shop/digital-downloads-pdfs/carcassi-matteo-pdfs/carcassi-etude-op-60-no-2-pdf-free/) | **出版版本优先**。27条中有主题、首乐章、第一页等节选，不能均标完整作品；零元项仍走购物篮，本次未结账。[现代重排版权说明](https://tecla.com/what-you-need-to-know-about-copyright/)须保留。 |
| **Bergmann Edition** | [当代目录](https://bergmann-edition.com/collections/contemporary-1)、[单曲目录](https://bergmann-edition.com/collections/single-sheet-music)；[Boyko Suite No.3](https://bergmann-edition.com/collections/contemporary-1/products/boyko-suite-no-3)有独奏、12页、等级、出版日期、BE-250632、ISMN | **当代作品和购买页优先**。PDF/按需印刷；不是已证实免费大库，总量未知。[条款](https://bergmann-edition.com/policies/terms-of-service)限制未经许可利用与复制；批量元数据合作须另核。 |
| **Andrew York官网** | [作者目录](https://andrewyork.net/sheetmusicdownloads.html)有独奏、二重奏、四重奏；明确3个零元项目，含[Blues for J.D.](https://andrewyork.net/scores/BluesforJD.html) | **作者权威专题**。标准谱PDF、不提供TAB，其他多付费；零元仍需结账，本次未操作。详情页仅提取导航，主要字段证据来自同站目录；无开放许可证证据，非吉他项目另排除。 |
| **Guitar Downunder** | [古典目录](https://www.guitardownunder.com/classical.php)、[Lagrima](https://www.guitardownunder.com/_scores/lagrima.php)，Bill Tyers编曲、PDF/TAB/视频/合奏 | **补充候选**。样本PDF可打开；[首页](https://www.guitardownunder.com/)保留版权。未确认批采/API/复用许可；总量未知，作者拼写和重复链接需校核。 |
| **FreeGuitarMusic.Net** | [古典/现代指弹目录](https://www.freeguitarmusic.net/fingerstyle/modern-and-classical-solos)，Isaac Gish编曲、PDF链接、视频与教材 | **访问待核**。样本外链[Drive记录](https://drive.google.com/file/d/1bXYGDsaUHAFQg1nVKRHokkXAI4ARxWve/view?usp=sharing)只显示Loading/Sign in，PDF获取未确认；版权与批采未知。不能假定`.com`与`.net`是同一来源迁移。 |
| **ClassicalGuitar.org** | [免费目录](https://www.classicalguitar.org/free/)、Christopher Davis原作/练习、Giuliani与Satie版本；Giuliani Op.45样本PDF可打开 | **专题补充**。[政策](https://www.classicalguitar.org/about/site-policies/)分别处理文章CC BY-NC-ND 3.0、作者原作、免费公版谱和销售产品；不能整站套同一许可。有些资源需Gumroad零元流程或订阅邮件，不代用户订阅。 |

## 3. 历史档案与综合开放目录

| 候选 | 能增加什么、身份与接口 | 当前核查边界与建议 |
| --- | --- | --- |
| **BnF Gallica** | [Carulli第二版书目](https://catalogue.bnf.fr/ark:/12148/cb428940797)与[扫描对象](https://gallica.bnf.fr/ark:/12148/btv1b100704044)；版次、96页、Carli版号142、馆藏号；以ARK区分书目和数字对象。[SRU](https://api.bnf.fr/fr/api-gallica-de-recherche)、[文档API](https://api.bnf.fr/fr/api-document-de-gallica)、[IIIF](https://api.bnf.fr/fr/api-iiif-de-recuperation-des-images-de-gallica) | **历史版本元数据优先**。[BnF元数据开放许可](https://www.bnf.fr/fr/reutiliser-les-donnees-de-la-bnf)不自动覆盖扫描内容；本次查看器/内容条款403，未确认PDF或内容复用。样本题名有“guitare ou lyre”，并非已通过当前精确编制。 |
| **Library of Congress** | [乐谱集合](https://www.loc.gov/notated-music/collections/)、[Guitar made perfect / 2023813885](https://www.loc.gov/item/2023813885/)；1870年、作者/出版者/主题/图像、PDF及IIIF。[官方JSON/YAML API](https://www.loc.gov/apis/json-and-yaml/) | **美国历史谱优先**。代表所属Music for the Nation 1870–1885集合的Rights & Access标可自由使用；不能推广到全站。本次样本内容来自官网索引，重新open为403，未验PDF；全站/全集合数不作吉他数。 |
| **Royal Danish Library / Rischel & Birket-Smith** | [现行馆藏说明](https://www.kb.dk/en/find-materials/collections/sheet-music-collection)确认这两个吉他收藏，有印本、手稿与部分数字化 | **入口修复后再试点**。旧专题入口转通用页面，本次未核到当前独立目录、代表记录、API或稳定ID。不引用第三方旧1,566条为当前规模。[版权说明](https://www.kb.dk/en/copyright-and-use-our-materials)、[数据服务](https://www.kb.dk/en/services/cultural-heritage-research-and-study/cultural-heritage-data-and-datasets)不能替代全收藏许可。 |
| **RIAM Hudleston Collection** | [官方数字入口](https://www.riam.ie/digital-media/)、[收藏说明](https://www.riam.ie/student-life/library/special-collections)确认19世纪独奏/室内乐原版PDF；[资源页](https://www.riam.ie/student-life/library/online-resources)称1,100余作品 | **书目导航及合作**。典型[馆方PDF的使用说明](https://www.riam.ie/digital-media/h14/h_14a_01_001.pdf)限定个人非商业，未经许可不得下载整卷或相当部分；不规划整库下载。当前专用谱记录ID/入口需进一步核对。 |
| **Internet Archive** | [高级检索](https://archive.org/advancedsearch.php)、[Sor方法书](https://archive.org/details/imslp-complte-pour-la-guitare-sor-fernando)；identifier/ARK、扫描者、PDF/OCR/JP2、文件尺寸和校验信息；[开发者入口](https://archivesupport.zendesk.com/hc/en-us/articles/360001495812-Developer-Resources) | **机构扫描者白名单候选**。样本明确IMSLP镜像，不能算独立新作品。[Rights说明](https://archivesupport.zendesk.com/hc/en-us/articles/360014759692-Rights)不保证上传者版权；账户、借阅和无下载状态保留。 |
| **Cantorion** | [吉他检索](https://es.cantorion.org/musicsearch/instruments/Guitar)本次普通GET显示 **574 条结果**；[Incursions / 957](https://cantorion.org/music/957/Incursions)有作曲家、编曲者、吉他二重奏、难度、6页、许可 | **目录补充**。单谱标All rights reserved，且下载可能外链Archive；部分目录明确来自Mutopia。许可逐条核，574不是净增作品/可用PDF。页面字段和介绍有潜在错误，保留原文与核查状态。 |

## 4. 大型免费目录：价值高，自动采集条件需先落实

| 候选 | 价值和代表记录 | 决策依据 |
| --- | --- | --- |
| **Free-scores.com** | [吉他目录](https://www.free-scores.com/free-sheet-music.php?CATEGORIE=999)、[Sor Op.35 No.22 / 34385](https://www.free-scores.com/download-sheet-music.php?pdf=34385)，编制、编辑者、PDF、音频、多版本 | **合作授权优先**。[现行条款](https://www.free-scores.com/conditions-generales-uk.php)10.3未经事先书面授权禁止大量/反复数据库提取、自动获取及公开再利用，明确涉及脚本/索引机器人。个人下载配额与数据库复用分别处理；不能直接实施生产爬库。 |
| **8notes** | [吉他](https://www.8notes.com/guitar/)、[古典分类](https://www.8notes.com/guitar/classical/sheet_music/)、[Ode to Joy / 578](https://www.8notes.com/scores/578.asp)；标准谱/TAB、难度、调性、范围、其他编制版本 | **来源导航/教学合作**。样本PDF为Premium；[条款](https://www.8notes.com/help/terms.asp)区分可免费查看打印和现代版数字复制/分享限制。吉他总量/API未核，只有记录明确标的Public Domain才按该标记评估。 |
| **Musopen** | [吉他目录](https://musopen.org/music/instrument/guitar/)、[Julia Florida / 13022](https://musopen.org/music/13022-julia-florida-barcarolle/)，曲式/作者/难度/谱入口 | **暂列合作候选**。[条款](https://musopen.org/tos/)限定一份个人非商业临时查看，限制镜像/转交/公开显示，不保证所有素材公版。样本介绍D major、结构字段A Major有冲突。100,000 PDF宣传是全站，不作吉他规模。 |

## 5. 当代、社区与中文来源

这些来源可显著拓宽曲目和版本导航，但本轮没有建立“当前批准范围内可批量纳入”的数量。电吉他、贝斯、弹唱、乐队总谱与歌词和弦应与现有古典/原声器乐分区；确认范围后才能按网站目录独立采集。社区标签不是编制或版权的审定结论。

| 候选 | 官方目录与代表记录 | 格式、元数据和当前建议 |
| --- | --- | --- |
| **Sheet Music Plus** | [独奏目录](https://www.sheetmusicplus.com/en/category/instruments/guitar/guitar-solo/)、[Hoy y Siempre / 20741254](https://www.sheetmusicplus.com/en/product/hoy-y-siempre-20741254.html) | 当代出版谱，作曲者、出版社、编制、产品ID和SKU；付费PDF/streaming、购买水印及份数限制。**出版目录合作优先**；未核开放元数据API/自动采集许可。 |
| **吉他世界** | [指弹目录](https://www.guitarworld.com.cn/pu/top/cat/1)、[Sacred Play Secret Place / q84335](https://www.guitarworld.com.cn/pu/q84335) | 制谱者、曲作者、版本、原调/选调、Capo、调弦、BPM、页数、五线谱/六线谱/试听；样本登录购买。[协议](https://download.guitarworld.com.cn/agreement/service.html)限制服务使用；实际导出格式与API未核。**中文指弹合作优先**；正式域名不是guitarschina.com。 |
| **吉他社** | [作者目录](https://www.jitashe.org/artist/9684/)、[狮子山下 / 1333502](https://www.jitashe.org/tab/1333502/) | GTP/PDF/图片谱分类、上传者/词曲/音轨；样本为钢弦吉他音轨，范围归属仍需确认。[协议](https://www.jitashe.org/info/disclaimer/)的站内发布授权不等于第三方转载许可。**中文原声合作候选**；`/thread/`与`/tab/`别名不可双算。 |
| **MuseScore.com** | [吉他目录](https://musescore.com/sheetmusic/guitar)、[One / 11278984](https://musescore.com/user/51380273/scores/11278984) | 可编辑谱、PDF/MIDI/MusicXML等随条目权限变化；样本独奏、DADGAD、页数、声部、上传用户和版权字段。[条款](https://ja.musescore.com/legal/terms)20–21节限制个人用途/分发及平台之外自动系统访问。**作者授权或官方合作**，不作直接爬库计划。 |
| **Musicnotes** | [吉他目录](https://www.musicnotes.com/instruments/guitar)、[Back to the Future / MN0101823](https://www.musicnotes.com/sheetmusic/back-to-the-future/back-to-the-future/MN0101823) | Guitar TAB/Instrumental Solo、出版社/速度/调性/页数；[产品类型](https://help.musicnotes.com/hc/en-us/articles/201185376-What-are-the-different-product-types-that-Musicnotes-sells)区分授权打印、App副本、另购PDF。[条款](https://www.musicnotes.com/secure/)第9条限制自动脚本访问。**合作目录**；全站Guitar筛选不能视为纯吉他新增量。 |
| **nkoda** | [官网](https://www.nkoda.com/)、[Brouwer Preludio](https://www.nkoda.com/work/Preludio) | 版权期内出版谱、出版社/乐器/分谱；本次未核内部稳定版次ID，不能靠题名认同版本。[FAQ](https://www.nkoda.com/help/faq)明确库谱不能下载/打印。**出版版本导航**；App离线缓存不进入PDF归档流程。 |
| **mySongBook** | [官方目录](https://www.guitar-pro.com/tabs)、[Tárrega Preludio N°20 / 7510](https://www.guitar-pro.com/tabs/t/7510-preludio-n20) | Guitar Pro官方播放谱；目录区分独奏、二/三重奏、吉他声乐、总谱；可筛古典/弗拉门戈。[官方支持](https://support.guitar-pro.com/hc/en-us/articles/200570231-mSB-Can-I-save-a-mySongBook-score-on-my-computer)确认库谱不可存成电脑文件。**来源导航**，批采许可未核。 |
| **Songsterr** | [吉他检索](https://www.songsterr.com/?inst=guitar)、[Gran Vals / s3888279](https://www.songsterr.com/a/wsa/francisco-tarrega-gran-vals-classical-guitar-tab-s3888279) | 互动TAB、多轨、修订；[Plus](https://www.songsterr.com/plus)提供GP/MIDI/音频下载与打印。[条款](https://www.songsterr.com/terms)限制绕过付费/干扰播放器，关联ai.txt此次未读全。**纯器乐选编/合作待核**；单个尼龙弦音轨不证明全谱符合范围。 |
| **Ultimate Guitar** | [官网目录](https://www.ultimate-guitar.com/explore)；代表谱页本次读取失败 | [官方帮助](https://help.ultimate-guitar.com/en/articles/6749046-website-how-to-download-guitar-pro-and-power-tabs)确认用户GP/GPX/GP3–5/PTB可按页下载，[Official](https://help.ultimate-guitar.com/en/articles/6749040-website-can-i-download-the-official-tab)不可下载。[条款](https://www.ultimate-guitar.com/about/tos.htm)限制个人用途和文件转交；**当前访问/范围/授权待核**。不能因提到API就称有开放接口。 |
| **虫虫吉他** | [指弹合集](https://www.ccguitar.cn/album/1541217.htm)、[十七岁 / 941357789](https://www.ccguitar.cn/cchtml/941357789.htm) | 官网索引显示六线图片谱/GTP/和弦文本/教学，歌手、制谱者、调性/Capo/难度等。**当前访问待核的中文候选**；部分open超时，登录/付费/文件格式/授权/自动政策未核全，不作为已批准生产源。 |

### 本轮未确立专用谱库的两个名称

- [吉他中国 guitarschina.com](https://www.guitarschina.com/)是另一个资讯/论坛门户。未核实可适配的结构化专用谱库，不能混认成吉他世界。
- 吉他达人 `jitadaren.com` 的多个入口本次均未读到当前目录、单谱和条款；保持待重试，不用第三方导航信息替代一手证据。

## 6. 统一图谱需要保留的层次

目前 `source_id + source_record_id` 已能统一多来源检索。建议在这一身份层上逐步增加有证据的关系，而不是把同名记录合并。以下是未来数据建模建议，本轮未实现。

| 层次 | 表示什么 | 关键字段或关系 |
| --- | --- | --- |
| 作品 | 音乐作品本身 | 原题、作曲者、作品号/权威ID；跨源关系须附证据和审查状态 |
| 编曲 | 某目标编制/调弦的处理 | 编曲者、目标乐器与人数、调弦、原作/改编状态 |
| 版本/出版物 | 某编订、影印、商品或合集 | 编订者、出版社、版次、出版年、版号、ISMN/ISBN、总谱/分谱/节选 |
| 馆藏/来源记录 | 网站记录及实际收藏 | source/native ID、馆藏号、ARK/URN、机构ID、原始署名、冻结版本 |
| 文件/格式 | 实际可用的谱载体 | PDF/GP/MusicXML/LilyPond/TAB/图片；获取、许可、验证状态独立 |
| 教学/参考资料 | 指法、讲解、演示与方法 | 教学视频/文章/方法书关系，保留reference分类与来源 |

例如《阿尔罕布拉宫的回忆》的 Boije 扫描、Mutopia 重排、Delcamp 指法版和社区TAB可并列显示，并在证据充分后关联到作品。文件字节完全一致可以共享物理对象；它不决定编曲或版本身份。一本合集的一份PDF也不能与内部每首曲形成多个唯一PDF实体。

人物关系保留作曲、编曲、编订、演奏/演唱、上传者各自角色；中文站“歌手”字段不能直接填进作曲家。调性、难度和编制取来源明示值，并记录冲突和未知。来源ID保留稳定；规范化标题和译名只帮助显示/搜索。

建议分别记载元数据获取依据、公开目录复用依据、文件获取依据、文件使用/分享限制以及核查日期。三个权限状态都采用`confirmed / restricted / unknown`并带证据；未知不会从“有下载按钮”或“有API”自动变成confirmed。许可原文和文件链接仅在内部资产保留，公开端按现有白名单导出。

## 7. 分批推进和验收

| 批次 | 范围 | 可交付成果与验收 |
| --- | --- | --- |
| **第一批：开放子集** | Mutopia → Boije → The Guitar School明确许可免费项目 | 固定来源快照和范围；原生ID/版本/署名/许可；续传发现与失败台账；许可允许的PDF验证与离线链接；翻译审校后公开来源页检索 |
| **第二批：图谱关系与历史版本** | RISM权威数据；DGA用于发现；Gallica/LoC元数据；Delcamp、CGLIB、编订者/出版社选编 | 人物—版本—馆藏关系有证据；新旧接口覆盖差异与空字段明确；目录合作条件落实后再规模化；未开放文件保持来源导航 |
| **第三批：中文与当代扩围** | 吉他世界/吉他社优先合作；MuseScore、出版社平台；其余互动TAB平台按适用范围加入 | 单独确认原声指弹、古典、弹唱、乐队等范围；保留制谱者、调弦、Capo、谱种和访问条件；批准格式的文件管线与PDF管线独立 |

既有生产管线应继续采用可恢复发现、下载、验证、导出和渲染。不需要为来源扩展额外建立规格审批流程；明确的站方采集限制、账户购买或扩大项目范围仍是实际约束，本轮没有替用户联系网站、订阅、登录、购买或发起全量获取。

每批报告至少分别统计：来源记录、分类关系、版本/合集、文件清单、已验证PDF、不同内容SHA-256、物理对象、无PDF/无权限/真实404/编制未知/翻译待审。净新增来源记录不等于净新增作品；跨源重合率须通过样本和实际快照测得。网站宣传数、关键词命中、谱页数和文件数不能相加，不承诺尚未取得的十万首规模。

### 现有实现需要注意的具体位置

- `scripts/catalog_sources.py` 目前拒绝所有query/fragment，以及`/download/`路径。Mutopia使用`piece-info.cgi?id=...`，Free-scores使用`...?pdf=...`表示记录，The Guitar School用`/en/Download/<id>`表示详情。以后只为确认的来源记录路径和参数增加精确规则，并继续拒绝文件、私有地址、未知参数与重定向到下载的页面。
- 现有生产注册表要求已存在的规范化目录；不能仅因写进候选表就加入`config/sources.json`，否则会影响正常导出。候选清单放在`docs/research/`，与批准范围分开。
- 公开版本继续只给来源记录页。新增GP、MusicXML、LilyPond等不意味着其文件、下载链接或私有路径进入`public_site/`。
- 已有IMSLP 495条Work-level与33条其他候选的逐文件编制审查，以及ClassClef真实404边界继续按现有TODO接续。本次选源调研未解决这些文件级缺口。

## 8. 调研方法和证据限度

本次先核对本地来源注册与公开目录，再分三组检查古典专门站、开放档案、商业/社区/中文站，优先官方目录、记录页、条款与正式API。一开始`search-layer`两个发现查询返回0条；随后通过Web检索/打开官方资料及少量普通GET API继续。0条搜索不代表没有来源。

报告中明确区分实际页面读取、官方索引文本、API实测、少量样本PDF打开与未完成获取。HTTP 200和可打开样本不是项目级PDF完整性验证；没有进行全站冻结、去重、编制审查、译名审校或批量PDF下载，因此新增记录净数、唯一作品净数和下载覆盖率均未知。

所有链接核查于上述日期；网站会迁移、收费或调整规则。Gallica/LoC部分请求403、丹麦旧入口迁移、虫虫部分超时、Drive加载页、DGA部分普通页的人机核验等均保留为局限，没有尝试绕过。来源表中的研究建议与数量不能升级成已完成接入、版权法结论或完整覆盖声明。

同目录[候选清单与少量接口观察](2026-10-01-source-candidates.json)保存来源ID建议、证据入口、建议路径和已核查/未知状态，便于后续接续；它不存储乐谱或原始全站快照。
