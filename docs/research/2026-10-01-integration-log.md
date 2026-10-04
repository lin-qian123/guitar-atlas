# Guitar Atlas 多来源接入日志：2026-10-01

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
