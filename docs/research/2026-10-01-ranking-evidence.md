# 目录排序的参考熟悉度依据（2026-10-01）

本次整理服务于用户的两项要求：搜索按匹配程度排序，以及没有搜索词时让较熟悉的曲目更早出现。权重是可追溯的人工编辑基线，依据官方教学选曲与已记录的演奏，**不是网站浏览量、下载量、全球流行度、难度或艺术价值的测量**。官方曲目资料只证明实际选曲使用；各整数权重、分档与选取范围是本项目的编辑判断。

资产：[metadata/ranking/recognition.json](../../metadata/ranking/recognition.json)，schema 1，版本 `2026-10-01.1`。此次仅增加排序资产与研究记录，不改来源署名、翻译、作品ID、类别归属、版次、PDF完整性或授权信息。

## 范围与数值含义

- 人物范围为47位，落实为当前目录中151个精确原文署名键；151是来源全名写法数，不是151位人物。
- 作品范围为40条独立来源记录，不代表40首跨源去重作品。条目逐一保存当前 `title_en` 与 `composer_en`，双方原文守卫必须同时匹配。
- 人物基线为8–20，明确作品奖励为40–70。作品奖励大于人物基线，使常见作品优先于同一知名人物的未整理曲目。相同人物的源全名写法使用同一权重。
- 未整理人物或作品为0。0只表示没有加入本次小型人工基线，不表示作品不值得演奏或人物没有知名度。
- 搜索匹配层级优先于这些值；不允许熟悉度把包含“索尔”的其他姓名排在准确“索尔”署名前面。
- 正常展示可以保留稳定的原文名字/曲名/ID次序作为同权重时的次级顺序。不要按某来源的条目量累积奖励。

人物键只采用当前目录已有的完整署名写法，逐字精确匹配；不使用裸姓、字符串包含或模糊人物身份。`Johann Sebastian Bach`不扩展到其他Bach家族成员，Joaquín Rodrigo不扩展到`Rodrigo y Gabriela`，Agustín Barrios不扩展到Ángel Barrios，Mauro Giuliani不扩展到Emilia Giuliani。权重键存在不构成跨网站人物或作品合并。

当前基线偏向古典吉他的官方教学和录音选曲，不声称覆盖流行、指弹、地区曲目或所有17个统一分类。后续可以沿同一来源与原文守卫合同补充，不需要为运行时加载长段研究文本。

## 一手依据

下列地址在2026-10-01核查。RCM当前官方[考纲索引](https://www.rcmusic.com/learning/examinations/academic-resources-and-policies/syllabi-and-syllabi-errata)仍链接2018版古典吉他考纲；ABRSM当前[Guitar页面](https://www.abrsm.org/en-sg/guitar)仍列出from 2019考纲。年份是文档版本，不能改写为2026版。


| 证据ID | 官方材料 | 使用与核查边界 |
|---|---|---|
| `trinity_diploma_2026` | [Trinity College London Guitar Diploma Repertoire List, April 2026 update](https://trinitycollege.com/resource/?id=8539) | 官方考试选曲目录，证明教学与演奏选曲使用；不是热度或流量统计。 |
| `trinity_grades` | [Trinity College London Classical Guitar grades repertoire](https://www.trinitycollege.com/qualifications/music/grade-exams/classical-guitar/classical-guitar-repertoire) | 官方分级曲目目录；只用于人工参考熟悉度，不复制完整曲目表。 |
| `abrsm_2019` | [ABRSM Guitar Practical syllabus from 2019](https://www.abrsm.org/sites/default/files/2023-10/Guitar%20Practical%20Grade%20Syllabus_0.pdf) | 官网现行Guitar页面确认该版仍有效；本文仅引用零散作品事实，不复制考纲目录。 |
| `rcm_2018` | [The Royal Conservatory Classical Guitar Syllabus, 2018 Edition](https://rcmusic-production-strapi-media.s3.ca-central-1.amazonaws.com/s47_guitarsyllabus_online_2018_f_45cefee42b.pdf) | 由RCM现行Syllabi and Syllabi Errata官方索引链接；不是2026新版或曲目播放量。 |
| `uw_sor_duo` | [University of Washington School of Music Guitar Studio Recital, 9 February 2018](https://music.washington.edu/events/2018-02-10/guitar-studio-recital) | 官方节目明确列出Sor L’Encouragement Op.34，两位学生合奏。 |
| `naxos_sor_duo_1` | [Naxos SOR: Guitar Duets, Vol.1, 8.553302](https://www.naxos.com/CatalogueDetail/?id=8.553302) | 官方录音目录列出Sor Op.34及Op.41；此处不将一张录音等同于量化普及率。 |
| `naxos_sor_duo_2` | [Naxos SOR: Guitar Duets, Vol.2, 8.553418](https://www.naxos.com/CatalogueDetail/?id=8.553418) | 官方搜索索引列出Sor Op.63 Souvenir de Russie；详情页在核查时返回Internal Error，未把失败页面描述为成功全文读取。 |
| `naxos_giuliani_duo` | [Naxos GIULIANI: Music for 2 Guitars, Vol.1, 8.572445](https://www.naxos.com/CatalogueDetail/?id=8.572445) | 官方目录明确列出Variazioni concertanti Op.130及两位吉他演奏者。 |
| `tamu_bream_rca` | [Texas A&M University Libraries: Julian Bream, the complete RCA album collection](https://catalog.library.tamu.edu/Record/in00004152153/Details) | 官方馆藏MARC505记录曲目：Julian & John及Together again等双吉他录音。证明已收录的演奏事实，不推断下载量。 |

| `naxos_sor_official_catalogue` | [Naxos Mozart, Haydn and their Contemporaries catalogue, page 78](https://cdn.naxos.com/sharedfiles/PDF/SegmentCatalogue_Mozart_Haydn_Contemporaries.pdf) | 出版社官方目录明确列出8.553302的L’encouragement/Les deux amis及8.553418的Souvenir de Russie；详情页读取失败时保留这一独立可核查依据。 |

Trinity 2026文凭清单、Trinity分级网页、ABRSM PDF和RCM PDF均可读取；Naxos Sor两个详情页后续读取出现工具Internal Error。Sor第二卷的曲目事实来自该出版社的可检索官方索引，未声称详情页成功全文读取。Sor两卷已由该出版社官方《Mozart, Haydn and their Contemporaries》目录第78页独立交叉确认，资产保存该PDF依据。此读取边界记录于权重资产，不能作为所有Naxos页面已核查的结论。

## 人物基线

下表按资产中首个出现的精确全名示例分组；完整原文键均在JSON中。分组仅用于核对编辑范围，不输出为人物实体合并关系。

| 人物基线示例 | 权重 | 原文键数 | 依据ID |
|---|---:|---:|---|
| Fernando Sor（`Fernando Sor`） | 18 | 3 | `trinity_diploma_2026`, `trinity_grades`, `abrsm_2019`, `uw_sor_duo` |
| Mauro Giuliani（`Mauro Giuliani`） | 18 | 3 | `trinity_diploma_2026`, `trinity_grades`, `naxos_giuliani_duo` |
| Ferdinando Carulli（`Ferdinando Carulli`） | 16 | 3 | `trinity_grades`, `rcm_2018`, `tamu_bream_rca` |
| Matteo Carcassi（`Matteo Carcassi`） | 16 | 3 | `trinity_grades`, `rcm_2018` |
| Francisco Tárrega（`Francisco Tárrega`） | 20 | 5 | `trinity_diploma_2026`, `abrsm_2019`, `rcm_2018` |
| Johann Sebastian Bach（`Johann Sebastian Bach`） | 18 | 3 | `trinity_diploma_2026`, `trinity_grades`, `rcm_2018` |
| Isaac Albéniz（`Isaac Albéniz`） | 18 | 5 | `trinity_diploma_2026`, `rcm_2018` |
| Enrique Granados（`Enrique Granados`） | 16 | 3 | `rcm_2018`, `tamu_bream_rca` |
| Agustín Barrios Mangoré（`Agustín Barrios Mangoré`） | 18 | 6 | `trinity_diploma_2026`, `rcm_2018` |
| Manuel María Ponce（`Manuel María Ponce`） | 16 | 6 | `trinity_diploma_2026`, `rcm_2018` |
| Leo Brouwer（`Leo Brouwer`） | 16 | 2 | `trinity_diploma_2026`, `trinity_grades`, `rcm_2018` |
| Heitor Villa-Lobos（`Heitor Villa-Lobos`） | 18 | 3 | `trinity_diploma_2026`, `rcm_2018` |
| Napoléon Coste（`Napoléon Coste`） | 12 | 4 | `trinity_diploma_2026`, `trinity_grades`, `rcm_2018` |
| Dionisio Aguado（`Dionisio Aguado`） | 12 | 4 | `trinity_diploma_2026`, `trinity_grades`, `rcm_2018` |
| John Dowland（`John Dowland`） | 12 | 3 | `trinity_grades`, `rcm_2018` |
| Silvius Leopold Weiss（`Silvius Leopold Weiss`） | 12 | 6 | `trinity_diploma_2026`, `rcm_2018` |
| Gaspar Sanz（`Gaspar Sanz`） | 12 | 3 | `rcm_2018` |
| Emilio Pujol（`Emilio Pujol`） | 10 | 3 | `rcm_2018` |
| Astor Piazzolla（`Astor Piazzolla`） | 14 | 3 | `trinity_diploma_2026`, `rcm_2018` |
| Roland Dyens（`Roland Dyens`） | 14 | 2 | `trinity_diploma_2026`, `trinity_grades`, `rcm_2018` |
| Andrew York（`Andrew York`） | 14 | 1 | `trinity_diploma_2026` |
| Johann Kaspar Mertz（`Johann Kaspar Mertz`） | 12 | 3 | `trinity_diploma_2026`, `abrsm_2019`, `rcm_2018` |
| Joaquín Rodrigo（`Rodrigo, Joaquín`） | 14 | 2 | `trinity_diploma_2026`, `rcm_2018` |
| Domenico Scarlatti（`Domenico Scarlatti`） | 12 | 3 | `trinity_diploma_2026`, `trinity_grades`, `rcm_2018` |
| José Ferrer（`José Ferrer y Esteve`） | 8 | 4 | `trinity_grades`, `abrsm_2019`, `rcm_2018` |
| Giulio Regondi（`Giulio Regondi`） | 12 | 3 | `trinity_diploma_2026`, `rcm_2018` |
| Julio Salvador Sagreras（`Julio Salvador Sagreras`） | 10 | 4 | `rcm_2018` |
| Antonio Lauro（`Antonio Lauro`） | 12 | 3 | `rcm_2018` |
| Miguel Llobet（`Miguel Llobet`） | 12 | 4 | `rcm_2018`, `tamu_bream_rca` |
| Nikita Koshkin（`Nikita Koshkin`） | 10 | 3 | `rcm_2018` |
| Luys de Narváez（`Luys de Narváez`） | 10 | 2 | `trinity_grades`, `rcm_2018` |
| Alonso Mudarra（`Alonso Mudarra`） | 10 | 3 | `rcm_2018` |
| Anton Diabelli（`Anton Diabelli`） | 8 | 3 | `trinity_grades`, `rcm_2018` |
| Manuel de Falla（`Manuel de Falla`） | 12 | 2 | `trinity_diploma_2026`, `rcm_2018`, `uw_sor_duo` |
| David Kellner（`David Kellner`） | 8 | 3 | `trinity_grades`, `rcm_2018` |
| Carlo Domeniconi（`Carlo Domeniconi`） | 12 | 2 | `trinity_diploma_2026`, `rcm_2018` |
| Máximo Diego Pujol（`Maximo Diego Pujol`） | 8 | 3 | `rcm_2018` |
| Robert de Visée（`Robert de Visée`） | 10 | 2 | `rcm_2018` |
| Francesco Canova da Milano（`Francesco Canova da Milano`） | 10 | 4 | `rcm_2018`, `tamu_bream_rca` |
| Mario Castelnuovo-Tedesco（`Mario Castelnuovo Tedesco`） | 12 | 3 | `trinity_diploma_2026`, `rcm_2018` |
| Federico Moreno Torroba（`Federico Moreno Torroba`） | 12 | 3 | `trinity_diploma_2026`, `rcm_2018` |
| Alexandre Tansman（`Aleksander Tansman`） | 10 | 5 | `trinity_diploma_2026`, `rcm_2018` |
| Joaquín Turina（`Joaquín Turina`） | 10 | 5 | `trinity_diploma_2026`, `rcm_2018`, `uw_sor_duo` |
| Toru Takemitsu（`Takemitsu, Toru`） | 10 | 1 | `trinity_diploma_2026` |
| Francis Kleynjans（`Francis Kleynjans`） | 8 | 2 | `rcm_2018` |
| Sérgio Assad（`Sergio Assad`） | 10 | 2 | `trinity_diploma_2026` |
| John W. Duarte（`Duarte, John W.`） | 8 | 3 | `trinity_diploma_2026`, `rcm_2018` |

## 明确作品奖励

作品字段从本轮现存公共目录逐项读取，保存精确原文守卫。以下记录彼此独立；同名、相似译名、相同主题不触发身份合并。来源对同一作品的另外版本没有自动继承权重，只有明确列入或后续人工核查后才新增。

| 稳定记录ID | 来源曲名 / 原始署名 | 权重 | 依据ID | 选取说明 |
|---|---|---:|---|---|
| `340750` | [Lágrima](https://imslp.org/wiki/L%C3%A1grima_(T%C3%A1rrega,_Francisco)) / Tárrega, Francisco | 70 | `abrsm_2019`, `rcm_2018` | ABRSM Grade 5及RCM曲目涉及Lágrima；此记录包含独奏与双重奏分类，奖励作品熟悉度，不判断各版编配相同。 |
| `33377` | [Recuerdos de la Alhambra](https://imslp.org/wiki/Recuerdos_de_la_Alhambra_(T%C3%A1rrega,_Francisco)) / Tárrega, Francisco | 70 | `trinity_diploma_2026` | Trinity LTCL明确列出Recuerdos de la Alhambra。 |
| `54762` | [Capricho árabe](https://imslp.org/wiki/Capricho_%C3%A1rabe_(T%C3%A1rrega,_Francisco)) / Tárrega, Francisco | 70 | `trinity_diploma_2026` | Trinity ATCL明确列出Capricho Árabe。 |
| `97602` | [Introduction and Variations on a Theme by Mozart, Op.9](https://imslp.org/wiki/Introduction_and_Variations_on_a_Theme_by_Mozart,_Op.9_(Sor,_Fernando)) / Sor, Fernando | 65 | `trinity_diploma_2026` | Trinity LTCL明确列出Sor Mozart主题变奏；当前记录标题与作曲者精确检查。 |
| `97609` | [Grand solo, Op.14](https://imslp.org/wiki/Grand_solo,_Op.14_(Sor,_Fernando)) / Sor, Fernando | 50 | `trinity_diploma_2026` | Trinity LTCL明确列出Sor Grand Solo Op.14。 |
| `378911` | [Fantaisie et variations sur un air écossais, Op.40](https://imslp.org/wiki/Fantaisie_et_variations_sur_un_air_%C3%A9cossais,_Op.40_(Sor,_Fernando)) / Sor, Fernando | 45 | `trinity_diploma_2026` | Trinity ATCL列出Sor Fantasia and Variations Op.40；奖励这一明确作品编号。 |
| `47421` | [Rossiniana No.1, Op.119](https://imslp.org/wiki/Rossiniana_No.1,_Op.119_(Giuliani,_Mauro)) / Giuliani, Mauro | 55 | `trinity_diploma_2026`, `tamu_bream_rca` | Trinity FTCL及Bream官方馆藏录音曲目涉及Giuliani Rossiniana No.1 Op.119。 |
| `749133` | [Grande ouverture, Op.61](https://imslp.org/wiki/Grande_ouverture,_Op.61_(Giuliani,_Mauro)) / Giuliani, Mauro | 55 | `trinity_diploma_2026` | Trinity LTCL明确列出Giuliani Grande Overture Op.61。 |
| `130014` | [Variations on a Theme by Handel, Op.107](https://imslp.org/wiki/Variations_on_a_Theme_by_Handel,_Op.107_(Giuliani,_Mauro)) / Giuliani, Mauro | 50 | `trinity_diploma_2026`, `rcm_2018` | 官方选曲涉及Giuliani Handel主题变奏Op.107。 |
| `475296` | [Guitar Sonata, Op.15](https://imslp.org/wiki/Guitar_Sonata,_Op.15_(Giuliani,_Mauro)) / Giuliani, Mauro | 45 | `trinity_diploma_2026` | Trinity ATCL列出Giuliani Sonata in C Op.15。 |
| `450061` | [La catedral](https://imslp.org/wiki/La_catedral_(Barrios_Mangor%C3%A9,_Agust%C3%ADn)) / Barrios Mangoré, Agustín | 65 | `trinity_diploma_2026`, `rcm_2018` | 官方选曲明确涉及Barrios La Catedral。 |
| `181060` | [Suite in E minor, BWV 996](https://imslp.org/wiki/Suite_in_E_minor,_BWV_996_(Bach,_Johann_Sebastian)) / Bach, Johann Sebastian | 55 | `trinity_diploma_2026`, `rcm_2018` | 官方选曲使用BWV996多个乐章；合集给予低于单曲最高档的熟悉度，不声称整个合集每段同等知名。 |
| `181063` | [Suite in C minor, BWV 997](https://imslp.org/wiki/Suite_in_C_minor,_BWV_997_(Bach,_Johann_Sebastian)) / Bach, Johann Sebastian | 50 | `trinity_diploma_2026`, `rcm_2018` | 官方选曲使用BWV997的指定乐章；合集奖励不推断与指定考试出版版相同。 |
| `181067` | [Prelude, Fugue and Allegro in E-flat major, BWV 998](https://imslp.org/wiki/Prelude,_Fugue_and_Allegro_in_E-flat_major,_BWV_998_(Bach,_Johann_Sebastian)) / Bach, Johann Sebastian | 50 | `trinity_diploma_2026`, `rcm_2018` | 官方选曲使用BWV998指定乐章；当前组合曲目录保持不拆分。 |
| `181073` | [Suite in E major, BWV 1006a](https://imslp.org/wiki/Suite_in_E_major,_BWV_1006a_(Bach,_Johann_Sebastian)) / Bach, Johann Sebastian | 50 | `trinity_diploma_2026`, `rcm_2018` | 官方选曲使用BWV1006a指定乐章；合集奖励不判断任一改编版本身份。 |
| `984916` | [Sonatina meridional](https://imslp.org/wiki/Sonatina_meridional_(Ponce,_Manuel)) / Ponce, Manuel | 50 | `trinity_diploma_2026`, `rcm_2018` | 官方选曲涉及Ponce Sonatina Meridional。 |
| `1485621` | [Sonata romantica](https://imslp.org/wiki/Sonata_romantica_(Ponce,_Manuel)) / Ponce, Manuel | 45 | `trinity_diploma_2026`, `rcm_2018` | 官方选曲使用Ponce Sonata Romantica指定乐章；不把考试级别当作名气分数。 |
| `19962` | [Reverie - Nocturne, Op.19](https://imslp.org/wiki/Reverie_-_Nocturne,_Op.19_(Regondi,_Giulio)) / Regondi, Giulio | 45 | `trinity_diploma_2026` | Trinity LTCL列出Regondi Reverie Op.19。 |
| `527260` | [Suite populaire brésilienne, W020](https://imslp.org/wiki/Suite_populaire_br%C3%A9silienne,_W020_(Villa-Lobos,_Heitor)) / Villa-Lobos, Heitor | 45 | `trinity_diploma_2026`, `rcm_2018` | 官方选曲涉及Suite populaire brésilienne指定乐章；合集较小奖励。 |
| `444038` | [Preludes, W419](https://imslp.org/wiki/Preludes,_W419_(Villa-Lobos,_Heitor)) / Villa-Lobos, Heitor | 55 | `trinity_diploma_2026`, `rcm_2018` | 官方选曲涉及Villa-Lobos的若干前奏曲；本记录为合集，保持合集边界。 |
| `776908` | [Canarios](https://imslp.org/wiki/Canarios_(Sanz,_Gaspar)) / Sanz, Gaspar | 50 | `rcm_2018` | RCM Level7选曲明确使用Sanz Canarios。 |
| `83156` | [L'Encouragement, Op.34](https://imslp.org/wiki/L'Encouragement,_Op.34_(Sor,_Fernando)) / Sor, Fernando | 65 | `uw_sor_duo`, `naxos_sor_duo_1`, `tamu_bream_rca`, `naxos_sor_official_catalogue` | Sor L’Encouragement Op.34有大学合奏节目与双吉他录音资料；双重奏参考曲目。 |
| `763503` | [Souvenir de Russie, Op.63](https://imslp.org/wiki/Souvenir_de_Russie,_Op.63_(Sor,_Fernando)) / Sor, Fernando | 55 | `naxos_sor_duo_2`, `naxos_sor_official_catalogue` | Naxos官方索引列出Sor Souvenir de Russie Op.63；不将索引证据升级为详情页成功读取。 |
| `763474` | [Les deux amis, Op.41](https://imslp.org/wiki/Les_deux_amis,_Op.41_(Sor,_Fernando)) / Sor, Fernando | 55 | `naxos_sor_duo_1`, `naxos_sor_official_catalogue` | Naxos Sor双吉他录音曲目涉及Les deux amis Op.41。 |
| `332332` | [Variazioni concertanti for 2 Guitars, Op.130](https://imslp.org/wiki/Variazioni_concertanti_for_2_Guitars,_Op.130_(Giuliani,_Mauro)) / Giuliani, Mauro | 60 | `naxos_giuliani_duo`, `tamu_bream_rca` | Giuliani Variazioni concertanti Op.130有明确双吉他录音资料。 |
| `83685` | [6 Petits Duos, Op.34](https://imslp.org/wiki/6_Petits_Duos,_Op.34_(Carulli,_Ferdinando)) / Carulli, Ferdinando | 40 | `tamu_bream_rca` | 馆藏录音资料涉及本合集中的Petit duo No.2 Op.34；仅给予合集较小奖励，不声称6首全部同等知名。 |
| `303128` | [3 Sérénades, Op.96](https://imslp.org/wiki/3_S%C3%A9r%C3%A9nades,_Op.96_(Carulli,_Ferdinando)) / Carulli, Ferdinando | 40 | `tamu_bream_rca` | 馆藏双吉他录音资料涉及Op.96 Serenade；该来源记录是3首合集，给予合集较小奖励。 |
| `andrewyork:Sunburst.html` | [Sunburst](https://andrewyork.net/scores/Sunburst.html) / Andrew York | 60 | `trinity_diploma_2026` | Trinity ATCL列出York Sunburst；来源记录仍保持Andrew York自有目录身份。 |
| `mutopia:2103` | [Lágrima](https://www.mutopiaproject.org/cgibin/piece-info.cgi?id=2103) / F. Tarrega | 65 | `abrsm_2019`, `rcm_2018` | Lágrima的独立Mutopia双吉他记录；参考作品熟悉度，不将独奏考纲证明当作此改编版本验证。 |
| `mutopia:2102` | [Adelita](https://www.mutopiaproject.org/cgibin/piece-info.cgi?id=2102) / F. Tarrega | 50 | `rcm_2018` | Adelita的独立Mutopia双吉他记录；RCM确认作品选曲使用，不证明编配版本相同。 |
| `guitarschool:1027` | [Recuerdos de la Alhambra](https://classicalguitarschool.azurewebsites.net/en/Download/1027) / Francisco Tarrega | 70 | `trinity_diploma_2026` | Recuerdos de la Alhambra独立来源记录；原文曲名和署名精确守卫。 |
| `guitarschool:1122` | [La Catedral](https://classicalguitarschool.azurewebsites.net/en/Download/1122) / Agustín Barrios | 65 | `trinity_diploma_2026`, `rcm_2018` | La Catedral独立来源记录；保留来源原署名Agustín Barrios。 |
| `guitarschool:1101` | [Variations - Over a theme from the Magic Flute by Mozart Op . 9](https://classicalguitarschool.azurewebsites.net/en/Download/1101) / Fernando Sor | 65 | `trinity_diploma_2026` | Sor Op.9独立来源记录；来源原始title_en保留完整，不合并作品身份。 |
| `classclef:5dbf9b23f699c3da85fc2f13` | [Canticum](https://www.classclef.com/canticum-by-leo-brouwer/) / Leo Brouwer | 45 | `trinity_diploma_2026` | Trinity ATCL列出Brouwer Canticum。 |
| `classclef:03c1b5de7823bb57f9e08c0e` | [Koyunbaba I moderato](https://www.classclef.com/koyunbaba-i-moderato-by-carlo-domeniconi/) / Carlo Domeniconi | 45 | `trinity_diploma_2026` | Trinity LTCL列出Domeniconi Koyunbaba；此记录仅第I乐章，不声称已包含全曲。 |
| `classclef:e502db8ab792431aa94b21fb` | [Campanas Del Alba](https://www.classclef.com/campanas-del-alba-by-eduardo-sainz-de-la-maza/) / Eduardo Sainz De La Maza | 45 | `trinity_diploma_2026` | Trinity ATCL列出Eduardo Sáinz de la Maza的Campanas del Alba。 |
| `classclef:6779d9fad98025a6efe7ba32` | [Sevilla](https://www.classclef.com/sevilla-by-isaac-albeniz/) / Isaac Albeniz | 50 | `rcm_2018` | RCM ARCT曲目使用Albéniz Sevilla；不借考试等级比较名气。 |
| `cglib:1088` | [Op. 47 Suite Espanola No. 1 5. Asturias (Leyenda)](https://www.cglib.org/op-47-suite-espanola-no-1-5-asturias-leyenda/) / Albeniz. Isaac | 70 | `trinity_diploma_2026`, `rcm_2018` | 官方目录明确涉及Albéniz Asturias/Leyenda；源title和composer双guard防止同名错误归属。 |
| `1333398` | [Scherzo Vals](https://imslp.org/wiki/Scherzo_Vals_(Llobet,_Miguel)) / Llobet, Miguel | 40 | `rcm_2018` | RCM Level10列出Llobet Scherzo Waltz；当前source title Scherzo Vals。 |
| `cglib:49250` | [Sonata III](https://www.cglib.org/sonata-iii-2/) / Ponce. Manuel Maria | 45 | `trinity_diploma_2026`, `rcm_2018` | 官方选曲涉及Ponce Sonata III的指定乐章；此原记录不拆分、不判断版次相同。 |

合集与改编须保留边界。Carulli的Op.34与Op.96条目各为合集，公开录音只明确涉及其中曲目，故合集奖励设为40。Bach与Villa-Lobos等合集由所涉及乐章支持较小奖励，不声称其中每个乐章同等常演。Mutopia的Lágrima、Adelita条目是独立双重奏来源记录；独奏考纲只能支持作品熟悉度，不证明该改编版本符合考纲或与独奏谱相同。

## 核查与页面体积

本资产生成前核查：151个署名键全部逐字存在于当前 `composer_en`；40个稳定ID全部存在，所有曲名/署名守卫与目录一致；10个证据ID无空值、无悬空引用。整数范围分别落在8–20与40–70。总源资产约59KB，包含长理由和来源，属于可审计维护文件；页面只应取得编译后的数值或稀疏映射，不能向每条目录记录重复灌入整段理由、源标题与网页内容。

加载优化与此基线相互独立。保留统一搜索、原分类与同分类成员过滤；通过检索索引、延迟/增量渲染和避免全量DOM生成改善速度。未测浏览器前不报告加载耗时或性能百分比。
