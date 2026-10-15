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
  <img alt="17 catalog sources" src="https://img.shields.io/badge/sources-17-bd452f?style=flat-square">
  <img alt="Public site excludes score files" src="https://img.shields.io/badge/public_site-score_files_excluded-a67542?style=flat-square">
  <img alt="License MIT and CC BY-SA 4.0" src="https://img.shields.io/badge/license-MIT_%2B_CC_BY--SA_4.0-17283b?style=flat-square">
</p>

**六弦漫行｜Guitar Atlas** 是多来源吉他乐谱目录与本地离线库。共同目录按编制和用途组织，统一检索中英文曲名、音乐家、来源、作品号、格式和版本信息；原站分类与来源身份完整保留。

中文名为“六弦漫行”，英文名仍为“Guitar Atlas”；网页左上角显示英文名。仓库、目录和 Python 包名均为 `guitar-atlas`。

## 当前范围与进展

冻结目录包含 **17个来源、49,669条来源记录**（49,584条乐谱、85条参考资料）、2,229个原分类、58,282条分类成员关系及18个共同分类。记录可代表作品、版本、合集或馆藏，不能当作跨站唯一乐曲数；Cantorion分页等范围缺口保留。

全库题名都有精确原文守卫的处理决定：47,488条采用参考译法或有据惯用名，2,181条有理由保留原名，0条机器题名草稿或漏译。完整原题和署名始终保留，参考译名不等于唯一权威中文定名。

MuseScore的原924条是历史筛选子集。本次复查PDMX v9全部254,077条元数据及254,035份已声明MXL，正式补充296条，现为**1,220条来源记录**，全部融入现有分类、搜索及离线PDF／MXL／MIDI入口。42条未声明格式和3份结构异常保留明确边界；这不是实时MuseScore全库，也没有原生MSCZ。

| 格式 | 成功关联 | 失败／缺失／待取得 | 不同内容对象 | 不同内容字节 |
| --- | ---: | --- | ---: | ---: |
| PDF | 1,220 | 0／0／0 | 1,220 | 83,628,367B |
| MXL | 1,220 | 0／0／0 | 1,220 | 14,228,878B |
| MIDI | 1,220 | 0／0／0 | 1,212 | 8,970,785B |

新增888条格式文件关系，相对旧库新增883个内容对象／25,901,700B；重复MIDI复用存储，来源身份及版本关系全部保留。原924条完整记录、文件与审读决定保留。1,641条候选的文件取得成功，与最终296条正式收录分开统计；586条不符范围、759条编制或MIDI对应未定，以及前序许可排除，均保留逐条原因。完整筛选链见[全库复查日志](docs/research/2026-10-01-integration-log.md#pdmx全库复查与补充2026-10-15)。

当前MuseScore分类为独奏723、二重奏75、三重奏13、四重奏22、吉他合奏7、混合合奏334，另保留22条其他编制及24条器种／人数或来源关联边界。1,157条编制信息明确，63条保留具体限制；标准谱／TAB、琴体打击及辅助层不直接计为额外演奏者，跨格式差异在曲目详情中说明。

页面保留圆角收藏目录、自托管拉丁展示字体、系统中文字体及模型插图。首批显示18条，全文与模糊索引按需建立；本次没有新增前端依赖或插图，实际引用静态资产仍为284,048B。压缩目录5,853,476B，比补充前增加50,648B（约0.87%），用于浏览，完整JSON保留审计与兼容回退，乐谱字节不嵌入HTML。完整离线重建、保全、测试与远端部署状态见[发布记录](docs/research/publication.md)，未完成项只维护在[TODO](TODO.md)。

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

### 来源与文件流程

批准范围由 `config/sources.json` 和各来源配置定义；候选政策不是获取许可。各生产入口支持续传，挑战／认证／限速需停止并保留状态。

```bash
python scripts/discover_open_sources.py --help
python scripts/discover_archive_sources.py --help
python scripts/discover_additional_sources.py --help
python scripts/build_classclef_library.py --root . discover
python scripts/build_classclef_library.py --root . download
python scripts/build_classclef_library.py --root . verify
```

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
python scripts/review_musescore_translations.py --root .
```

格式提取可保留整批候选，只有最终获准的原生记录进入目录；候选取得成功不等于已经收录。新发现的标注歧义在精确审读资产处理，不能靠放宽全局器种规则补齐。需要扩充尚处MXL阶段的plan时，先退出所有写入者，再显式使用 `prepare --extend-plan`；它只接受旧entries完全不变的超集，并保留恢复证据。完成公开导出后先运行 `python scripts/verify_musescore_expansion.py --root . --precheck`；完整离线重建后去掉 `--precheck` 再核对全部文件入口和旧记录保全。

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
