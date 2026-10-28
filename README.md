<p align="center">
  <img src="public_site/assets/archive-cover.webp" alt="六弦漫行｜Guitar Atlas — 吉他乐谱与作品目录" width="100%">
</p>

<p align="center">
  <a href="https://lin-qian123.github.io/guitar-atlas/"><strong>在线检索</strong></a>
  · <a href="README.en.md">English</a>
  · <a href="#快速开始">快速开始</a>
  · <a href="#整理与检索方法">整理方法</a>
</p>

<p align="center">
  <img alt="Python 3.12+" src="https://img.shields.io/badge/Python-3.12%2B-17283b?style=flat-square">
  <img alt="22 catalog sources" src="https://img.shields.io/badge/sources-22-bd452f?style=flat-square">
  <img alt="Public site excludes score files" src="https://img.shields.io/badge/public_site-score_files_excluded-a67542?style=flat-square">
  <img alt="License MIT and CC BY-SA 4.0" src="https://img.shields.io/badge/license-MIT_%2B_CC_BY--SA_4.0-17283b?style=flat-square">
</p>

**六弦漫行｜Guitar Atlas** 是多来源吉他乐谱目录与本地离线库。共同目录按编制和用途组织，统一检索中英文曲名、音乐家、来源、作品号、格式和版本信息；原站分类与来源身份完整保留。

中文名为“六弦漫行”，英文名仍为“Guitar Atlas”；网页左上角显示英文名。仓库、目录和 Python 包名均为 `guitar-atlas`。

## 当前范围与进展

当前统一目录包含 **22个来源、50,498条来源记录**（50,406条乐谱、92条参考资料）、2,337个原生分类、59,111条分类成员关系、18个共同分类和710条有证据的记录关联。记录可代表作品、版本、合集或馆藏，不能当作跨站唯一乐曲数；Cantorion分页等范围缺口保留。远端仓库与[网页](https://lin-qian123.github.io/guitar-atlas/)已同步。

此前冻结的17来源范围中，47,495条题名采用参考译法或有据惯用名，2,297条有理由保留原名；这些历史统计不含本轮新增来源。新增来源已有独立的精确原题守卫与译名决定，完整原题和署名始终保留，参考译名不等于唯一权威中文定名。

此前冻结范围逐条审查了35,802条原未细分记录及296条MuseScore候选，宽泛确认有证据的吉他相关性、独奏／重奏或混合器乐家族；来源声明与谱面核对分开显示。该次历史审查记录“编制尚未核明”15,235条、“吉他相关·编制未细分”16,885条。加入本轮新来源后的当前topic计数分别为15,236条和17,362条；这是新增来源后的现值，不改写历史审查统计。Delcamp的2,890份可用PDF共40,662页完成全文筛查；IMSLP原528份文件级疑点及301份扫描谱OCR均有结果和边界。误挂的Byrd铜管谱仅移除吉他文件链接，原件保留。完整方法与逐源统计见[统一核验日志](docs/research/2026-10-01-integration-log.md#全库宽泛编制核验2026-10-17)。

本轮新增5个来源、706条记录：CSUN 424、Yawnoc 5、Maikstrings 112、Derek Hasted 23、Guitar Classroom 142（135条乐谱、7条参考资料）。PDF获取已停止：CSUN 424份全部验证通过（首轮421份成功、3份失败；在同一获准地址重试后3份成功），另外三份教学来源共286份验证通过。新来源合计710条PDF关系、710个不同SHA-256内容，共1,707,045,956字节；当前失败、缺失、待取得均为0。Yawnoc的9份PDF虽标明CC0，但GitHub release下载路由被robots拒绝，未发起PDF请求，也未换路；5份LilyPond源文本只用于元数据核验。来源元数据、个人离线获取许可与公开再分发许可分别记录；公开站仍只提供来源页，不放乐谱文件。

新增来源译名审读已完成：96条人工题名参考译名、103条人工分类译名，108个新原生分类逐项审查；新来源题名、音乐家和分类草稿已刷新，原17来源已发布决定保持不变。CSUN的1,145个候选原生ID均完成完整metadata核验，其中424收录、8排除、713待证。6条谱面文件差异说明均有精确guard：原4条、CSUN 1071条谱页提供一把或两把吉他的选项但人数未定、CSUN 1024第10页可见合唱与吉他而其他曲目编制及人数未核。候选研究清单现有47项，含13项新增补查。新增来源PDF去重已处理7,215个对象；10组、20条路径共44,365,593B已共享，最终dry-run为`already_shared=32`、`would_link=0`、`failed=0`。ClassClef已共享169项，原有2项安全拒绝保留不变。公开导出已完成；完整离线重建、保全核验和全部审计已通过，40,162条本地链接零失败；清理与远端同步已完成，发布回执见[发布记录](docs/research/publication.md)。研究见[选源研究](docs/research/2026-10-01-source-expansion.md)、[候选清单](docs/research/2026-10-01-source-candidates.json)；本轮私有规范回执为`sources/source-expansion/verification.json`，相关证据还包括`acquisition-summary.json`、`csun-acquisition-phases.json`、`new-pdf-evidence.json.gz`、`file-note-runtime-check.json`和`file-note-binding-corrections.json`。

MuseScore的原924条是历史筛选子集。检查PDMX v9全部254,077条元数据及254,035份已声明MXL后，当前正式纳入**1,343条来源记录**，统一分类、搜索和离线PDF／MXL／MIDI入口。1,641追加候选累计419接纳、1,008排除、214保留具体疑点；原已发布记录及旧review值继承。最新61条复用已验证文件，没有新增下载；明确的吉他择一版本可进入“吉他相关·编制未细分”，不推算同时演奏人数。42条未声明格式和3份结构异常仍保留边界；这不是实时MuseScore全库，也没有原生MSCZ。

| 格式 | 已验证记录 | 失败／缺失／待取得 | 不同内容对象 | 不同内容字节 |
| --- | ---: | ---: | ---: | ---: |
| PDF | 1,343 | 0／0／0 | 1,343 | 104,613,229B |
| MXL | 1,343 | 0／0／0 | 1,343 | 18,945,773B |
| MIDI | 1,343 | 0／0／0 | 1,335 | 12,119,419B |

三格式合计4,029条关系、4,021份不同内容／135,678,421B；重复MIDI只复用存储，不合并作品或版本。MuseScore的1,190条原编制明确结论保留，153条保留具体限制；标准谱／TAB、空置模板和辅助层不直接计人。缺失597条来源作曲署名与编制疑点分别处理，不猜作者。

最终代码与公开数据已通过独立干净检出的2,974项Python测试、83项Node测试及公开边界／译名／文本审计。压缩目录6,122,972B，比原版增加约1.98%；10项实际引用静态资产284,265B保持原字节。

页面保留圆角收藏目录、自托管拉丁字体、系统中文字体及模型插图。首批显示18条，全文与模糊索引按需建立；本轮未增加前端依赖或插图，完整审读账本留在私有压缩回执，浏览器继续使用去重压缩目录，乐谱字节不嵌入HTML。完整离线核验、性能与远端部署证据见[发布记录](docs/research/publication.md)，待补证据集中在[TODO](TODO.md)。

## 两种版本

| 版本 | 用途 | 乐谱入口 |
| --- | --- | --- |
| `public_site/` | 在线检索与来源导航，GitHub Pages仅部署此目录 | 各来源作品页或确认的目录页 |
| 根 `index.html` | 私有离线库，嵌入目录、别名和排名 | 当前分类中已验证的本地总谱、分谱、MXL／MIDI及来源页 |

公开版不包含PDF、MXL／MusicXML、MIDI、MSCZ、GPX等乐谱文件，也不包含下载端点、本地路径、哈希或私有库存。格式元数据与来源页可供检索。克隆仓库可直接使用公开目录；不会取得离线乐谱库。离线使用需保留现有相对目录结构。

## 整理与检索方法

- 使用 `source_id + source_record_id` 标识来源记录；同名或相似音乐家不触发跨站身份合并。原分类成员关系保留，共同分类独立于网站栏目。
- 跨来源关联仅来自明确文件引用、实核PDF内容、机构馆藏号或有类型的合集关系；内容相同也保留各来源归属。
- 搜索先按匹配度，完整姓名／明确别名及姓名边界优先于包含匹配。例如“索尔”先列费尔南多·索尔。无查询时按维护的曲目熟悉度参考排序；权重不是流量统计。
- 题名、署名和分类分别记录审读状态。合适意译缺乏依据时保留原文；编辑责任、档案位置和审读说明放入版本信息，原题全文仍可检索。
- 文件清单关系、不同路径、各格式SHA-256内容与inode分别统计。MIDI／MXL的内容复用不建立PDF同版关联；元数据刷新不会重新证明文件完整性或编制纯度。

方法与证据集中在以下固定入口，不再在README逐次追加实施日志：

| 记录 | 内容 |
| --- | --- |
| [选源研究](docs/research/2026-10-01-source-expansion.md)与[候选清单](docs/research/2026-10-01-source-candidates.json) | 候选价值、接口、版权与自动获取边界；候选不是已批准来源 |
| [冻结接入记录](docs/research/2026-10-01-integration-log.md) | 逐源范围、失败、文件取得／去重统计、验证边界 |
| [题名与字段审读](docs/research/title-review.md) | 完整题名决定、旧资产修正、名称约定、参考资料和精确守卫 |
| [排序依据](docs/research/2026-10-01-ranking-evidence.md)与[性能验收](docs/research/2026-10-01-search-ranking-speed.md) | 熟悉度权重、搜索优先级与历史性能测量 |
| [网页与插图](docs/research/presentation.md) | 当前设计、参考网站、图像提示词／出处、字体许可与验收 |
| [发布与维护记录](docs/research/publication.md) | 有效发布提交、工作流、线上字节核对与本次清理结果 |

## 快速开始

### 浏览公开目录

访问[在线网页](https://lin-qian123.github.io/guitar-atlas/)，或在项目根目录运行：

```bash
python -m http.server 8000 --directory public_site
```

打开 `http://127.0.0.1:8000/`。目录默认按共同分类浏览，选择分类或输入查询后显示作品。

公开网页直接提供来源页面链接；本地离线网页优先列出当前分类下的本地乐谱文件，没有本地文件时使用来源链接。卡片与版本详情不显示PDF获取状态、未就绪数量或缺失格式提示；相关记录保留在私有核验与获取回执中。

### 安装与验证

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
python -m pytest -q
node --test tests/*.test.cjs  # Node.js 22+，无需npm依赖
python scripts/validate_public_site.py public_site
python scripts/audit_translations.py
python scripts/audit_catalog_text.py
```

测试依赖包含PyMuPDF，用于核验PDF谱表与文字的位置；基础目录依赖仍保留pypdf文本读取回退。

### 来源与文件流程

批准范围由 `config/sources.json` 和各来源配置定义；候选政策不是获取许可。各生产入口支持续传，挑战／认证／限速需停止并保留状态。

```bash
python scripts/discover_open_sources.py --help
python scripts/discover_archive_sources.py --help
python scripts/discover_additional_sources.py --help
python scripts/discover_supplement_sources.py --help  # CSUN及本轮4个作者／教学来源
python scripts/build_classclef_library.py --root . discover
python scripts/build_classclef_library.py --root . download
python scripts/build_classclef_library.py --root . verify
```

本轮补充入口支持按来源续传发现；重新发现会保留相同文件的获取回执，但不是扩大冻结范围或改写已发布记录的许可。新题名以 `append_source_translations.py --source 来源ID --apply` 追加；文件获取使用已获准的 `acquire_source_assets.py`，遇访问拒绝保留状态。完整导出与离线重建后，用 `verify_source_supplement.py --source 来源ID --full-render-report 回执路径` 对照单一发布基线核验旧记录、原译名、本地文件入口及新记录。完整私有快照与证据包是这些本地生产命令的输入；干净仓库仅运行公开目录与自包含测试。

MuseScore使用已许可的PDMX v9出版入口。下列初次元数据、PDF和MXL／MIDI获取命令仅适用于原924条历史范围；追加后均受防覆盖护栏限制，当前补充使用“全库复查与追加”路线。题名整理只追加新的精确决定，保留旧条目：

```bash
python scripts/build_musescore_library.py --root . --acquire-metadata
python scripts/build_musescore_library.py --root .  # 使用已核验缓存
python scripts/review_musescore_translations.py --root . --apply
```

原始924条历史记录的PDF按原生编号和出版包内精确路径获取，不访问MuseScore下载接口。出版包支持原子下载／适用的断点续传；完整包通过大小与MD5检查后流式选取目标PDF，每份独立解析并按SHA-256存储、硬链接复用。源站的历史文件限制与独立出版档案分别保留：

```bash
python scripts/acquire_musescore_pdfs.py --root . --acquire-archive
python scripts/acquire_musescore_pdfs.py --root . --parallel-archive  # 批准的出版文件页，最多两段续传
python scripts/acquire_musescore_pdfs.py --root . --cached-archive  # 使用完整核验的出版包续传／重验
```

若第一段已完整而后段缓慢，可在下载进程全部退出后运行 `--consolidate-prefix`，核验并合并连续已收字节，再以 `--parallel-archive` 重分剩余两段。该步骤只操作本地字节，不代表整包校验通过；来源拒绝或存在缺口时不允许重分。

PDF的成功、失败、缺失和未尝试条目记录在私有 `sources/musescore/acquisition_report.json`，恢复journal在 `sources/musescore/pdmx/pdf-extraction.json`。取得的是PDMX导出PDF；归档MD5通过不等于上游提供了每份文件的校验和。

同一924条原生记录的MXL和MIDI使用独立配置与获取流程，绑定权威CSV中的精确成员路径，与已有PDF关联。以下两种格式依次执行；来源拒绝时停止，不切换入口：

```bash
python scripts/acquire_musescore_formats.py --root . --format MIDI --parallel-archive
python scripts/acquire_musescore_formats.py --root . --format MUSICXML --parallel-archive
python scripts/acquire_musescore_formats.py --root . --format MIDI --cached-archive
python scripts/acquire_musescore_formats.py --root . --format MUSICXML --cached-archive
```

若低位分段中断而高位分段已完整，先退出所有下载进程，再对该格式运行 `--rebalance-ranges`。此步骤只在本地核验并保留连续前缀与完整尾段，把缺口分为64 MiB小段；随后用 `--parallel-archive` 从同一入口续传，始终最多两路。已拒绝的来源不能重排或重试，重排本身不代表整包验收通过。

结果集中在 `sources/musescore/formats-acquisition-report.json`，逐曲目恢复与验证证据在 `pdmx/mid-extraction.json` 和 `pdmx/mxl-extraction.json`。完整出版包经大小、MD5与内部SHA-256验证后，检查所有TAR成员，再独立检查MXL的ZIP／CRC／MusicXML和MIDI的轨道、事件及结束标记，按格式存入不可变内容对象池。只有验收通过的文件生成离线入口；完整性检查不代表逐音一致、导入保真或声学播放验收，也不产生原生MSCZ。公开网页继续只发布目录和来源页。

在下载停止后，先dry-run再按已核验候选执行去重，随后重新验证。ClassClef与新增来源工具各自保留独立journal：

```bash
python scripts/deduplicate_source_pdfs.py --root .
python scripts/deduplicate_added_pdfs.py --root .
```

只有本次摘要、适用的上游摘要、大小、解析和路径检查全部通过才允许 `--apply`。保留原件、来源清单和全部访问路径。

### 实际编制核验

最初924条的底层提取器为 `score_instrumentation.py`（MXL／MIDI）、`score_pdf_evidence.py` 和 `score_midi_crosscheck.py`。实际视觉／题名判断冻结保存在私有verification目录，精确异常决定在 `metadata/instrumentation/`。原924条producer与verifier仅用于该历史基线；扩展后的目录使用下面的追加路线，不能重放初次导入或获取命令覆盖现有文件。机械TAB比对不能覆盖已有视觉结论。

中文编制、按谱面统计的人数、来源旧声明、完整文件分部原标注、冲突实际谱题均进入同一搜索；分部原标注包含TAB视图与辅助层，不直接用来计人数。27条保留边界的记录已逐条处理，不需要用户逐项审校；有新证据时再更新具体决定。

### 全库复查与追加

924是初次筛选的历史子集。全库审计分别检查254,077条CSV／metadata和254,035份已声明MXL，保留42条未声明MXL及3份结构异常的边界。实际谱面召回与来源身份、许可和最终编制分开判断；不用GM、歌词元素或题名关键词直接决定是否收录，也不把近似曲名合并为同一版本。

新增范围固定在 `config/musescore_pdmx_expansion.json`；全量审计、原始候选补齐、追加plan、格式取得、编制与谱题审读和恢复事务集中在私有 `sources/musescore/expansion/`。所有出版包必须保持配置中的大小、MD5和SHA-256；该路线只读取本地冻结档案，不访问MuseScore接口。初次924条的来源对象、获取journal和review entries保留，新的三格式对象按格式复用。

在已保存全量审计及任务前保全基线的环境中，追加入口依次为：

```bash
python scripts/expand_musescore_library.py verify-archives --root .
python scripts/expand_musescore_library.py recall --root .
python scripts/expand_musescore_library.py prepare --root . --selection sources/musescore/expansion/selected-records.json
python scripts/expand_musescore_library.py extract --root . --format MUSICXML
python scripts/review_musescore_expansion.py --root . --phase scope
python scripts/expand_musescore_library.py extract --root . --format PDF
python scripts/expand_musescore_library.py extract --root . --format MIDI
python scripts/review_musescore_expansion.py --root . --phase final
python scripts/expand_musescore_library.py commit --root .
python scripts/review_musescore_translations.py --root . --apply
```

格式提取可保留整批候选，只有最终获准的原生记录进入目录；候选取得成功不等于已经收录。新发现的标注歧义在精确审读资产处理，不能靠放宽全局器种规则补齐。需要扩充尚处MXL阶段的plan时，先退出所有写入者，再显式使用 `prepare --extend-plan`；它只接受旧entries完全不变的超集，并保留恢复证据。完成公开导出后先运行 `python scripts/verify_musescore_expansion.py --root . --precheck`；完整离线重建后去掉 `--precheck` 再核对全部文件入口和旧记录保全。

759条续核的 `capture-continuation` 基线固定于已发布的1,220条；完整全页文本、实际MXL／MIDI、提案和当时去向保存在私有 `remaining-review.json.gz`，该历史证据不重写。

本次549条深入复核先运行 `python scripts/expand_musescore_library.py capture-deep-continuation --root .`，以 `deep-continuation-baseline.zip` 冻结任务前已发布的1,248条及有效证据。复用原1,641条plan和三格式journal，不重放初次获取、prepare或旧924条producer；新收录只能来自精确 `deep-review-scope.json`，每条旧native、编制、译名及文件关系直接继承。`verify-continuation` 可只读检查当前阶段保全。

更新精确case后依次重跑scope和final，再用 `python scripts/review_musescore_deep.py --root . --consolidate` 将全部549条、5,709页PDF文字、实际MXL／MIDI及完整原始提案无损合并到单一私有 `deep-review.json.gz`。默认 `--verify` 不依赖已清理的提案或临时producer，重新核对实际文件；`--refresh-outcomes` 只更新最终去向而保留原证据语义。完成压缩读回及新鲜文件守卫后，才清理合并副本。后续精确补审可用 `--refresh-outcomes --supplement PATH` 无损嵌入补充决定，校对当前exact case、原生身份和三格式守卫，保留全部旧提案；默认验证无需已清理的补充文件。之后执行commit、追加译名、公开导出及完整离线重建。下一轮必须先冻结届时最新发布范围，不能用本次1,248条基线覆盖后续已发布决定。

人数按独立谱面角色判断，普通谱／TAB视图、集合、兼奏及模板冲突单列。有限的反复、连音和颤音攻击点核对可解释具体MIDI导出冲突，仍保留原文件及可见播放限制；这不认证音长、力度、音色、逐音导入或声学保真。

### 导出与离线更新

正式重新导出需要私有冻结来源元数据；导出只读元数据，不复制乐谱：

```bash
python scripts/export_public_site.py --root . --output public_site/data/catalog.json
python scripts/render_master_index.py .
```

完整离线重建核验文件内容与清单关系：PDF重新散列并解析，MXL重新散列并检查ZIP、CRC、容器与MusicXML结构，MIDI重新散列并检查轨道、事件及结束标记。仅当文件／来源快照未变、只是显示修订时，可运行 `python scripts/render_master_index.py . --metadata-only`；它核对指纹、分类、全部现有链接及大小，保留先前文件验收结果，不重新散列或执行格式解析／结构验证。

## 项目结构与保留规则

```text
guitar-atlas/
├── config/                       来源、范围、政策与精确排除
├── scripts/                      生产入口、共享目录和各来源适配器
├── tests/                        Python与Node回归测试
├── metadata/translations/        持久译名、精确守卫与复现规则
├── metadata/ranking/             有原文守卫的熟悉度参考
├── metadata/instrumentation/     精确异常编制审读决定
├── docs/research/                有效来源、审读、设计及发布说明
├── public_site/                  可部署的公开目录与有效网页资源
├── sources/                     私有冻结来源、续传状态、对象与清单
├── For */、for3guitars/           原生分类目录、当前视图与谱文件
├── metadata/.cache/pages/        固定修订原文；不是可随意删除的缓存
├── work/                        仍被复现流程读取的语料、journal与最终证据
├── backups/offline-ui/            一个最近的离线入口回退副本
└── index.html                   私有离线入口
```

`work/title-review/.../before/metadata/translations/` 是应用守卫所需原始资产，不能当成过时页面备份删除。源快照、当前清单、内容对象、编译审读输入与有效最终报告长期保留；无依赖的旧视图、试验检出、重复导出、过程截图和字节码可清。后续补充优先更新对应说明及最终报告，避免按轮次累计副本。

来源与本地库存、生成离线页、日志和乐谱文件均不进入Git。公开部署始终仅含 `public_site/`。

## 数据与版权边界

项目为独立整理目录，不代表来源网站。开放元数据、可免费下载或保存在本地均不自动授予乐谱再分发权，各来源和每份文件的许可分别保留。

- 程序代码：[MIT](LICENSE)
- 项目原创目录结构、参考译名、文档和视觉资产：[CC BY-SA 4.0](DATA_LICENSE.md)
- 逐来源与第三方说明：[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)
