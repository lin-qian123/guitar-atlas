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

冻结目录包含 **17个来源、49,373条来源记录**（49,288条乐谱、85条参考资料）、2,229个原分类、57,986条分类成员关系、17个共同分类、700条有证据的关联。记录可代表作品、版本、合集或馆藏，不能当作跨站唯一乐曲数；Cantorion分页等范围缺口保留。

全库题名已有精确原文守卫的处理决定：47,469条采用参考译法或有据惯用名，1,904条有理由保留原名；0条机器题名草稿或漏译。完整原题和署名始终保留，参考译名不等于唯一权威中文定名。

当前页面采用圆角收藏目录、自托管拉丁展示字体、系统中文字体及模型插图。结果首批18条，全文与模糊索引按需建立；实际引用静态资产283,302B，压缩目录5,767,964B，完整JSON用于审计与兼容回退。

2026-10-13版本已同步远端并部署，924份PDMX导出PDF加入原有离线入口。旧来源记录及全部译名决定保留；完整离线核验、链接保全和线上字节核对通过。最新验收与发布状态见[发布记录](docs/research/publication.md)，未完成项只维护在[TODO](TODO.md)。

MuseScore的924条PDMX v9历史记录参加同一搜索与分类。2026-10-12至13已取得并独立验收这924份出版PDF，0失败、0缺失；MusicXML和MIDI仍只保留格式信息。LibreScore是检索工具，这批数据来自作者许可发布的固定历史子集，未接入实时全库。范围、译名、排除与文件取得情况见[来源补记](docs/research/2026-10-01-integration-log.md#musescore--pdmx-补记2026-10-11)。

## 两种版本

| 版本 | 用途 | 乐谱入口 |
| --- | --- | --- |
| `public_site/` | 在线检索与来源导航，GitHub Pages仅部署此目录 | 各来源作品页或确认的目录页 |
| 根 `index.html` | 私有离线库，嵌入目录、别名和排名 | 当前分类中已验证的本地总谱、分谱及来源页 |

公开版不包含PDF、MIDI、GPX、下载端点、本地路径、哈希或私有库存。克隆仓库可直接使用公开目录；不会取得离线乐谱库。离线使用需保留现有相对目录结构。

## 整理与检索方法

- 使用 `source_id + source_record_id` 标识来源记录；同名或相似音乐家不触发跨站身份合并。原分类成员关系保留，共同分类独立于网站栏目。
- 跨来源关联仅来自明确文件引用、实核PDF内容、机构馆藏号或有类型的合集关系；内容相同也保留各来源归属。
- 搜索先按匹配度，完整姓名／明确别名及姓名边界优先于包含匹配。例如“索尔”先列费尔南多·索尔。无查询时按维护的曲目熟悉度参考排序；权重不是流量统计。
- 题名、署名和分类分别记录审读状态。合适意译缺乏依据时保留原文；编辑责任、档案位置和审读说明放入版本信息，原题全文仍可检索。
- PDF清单关系、不同路径、SHA-256内容与inode分别统计。元数据刷新不会重新证明PDF可解析性或编制纯度。

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

MuseScore使用已许可的PDMX v9出版入口。以下命令用于首次元数据接入和题名整理，保留其他来源的精确决定；已有PDF获取journal或已验证文件时，元数据重建会拒绝覆盖，改用下方独立获取流程：

```bash
python scripts/build_musescore_library.py --root . --acquire-metadata
python scripts/build_musescore_library.py --root .  # 使用已核验缓存
python scripts/review_musescore_translations.py --root . --apply
```

现有924条记录的PDF按原生编号和出版包内精确路径获取，不访问MuseScore下载接口。出版包支持原子下载／适用的断点续传；完整包通过大小与MD5检查后流式选取目标PDF，每份独立解析并按SHA-256存储、硬链接复用。源站的历史文件限制与独立出版档案分别保留：

```bash
python scripts/acquire_musescore_pdfs.py --root . --acquire-archive
python scripts/acquire_musescore_pdfs.py --root . --parallel-archive  # 批准的出版文件页，最多两段续传
python scripts/acquire_musescore_pdfs.py --root . --cached-archive  # 使用完整核验的出版包续传／重验
```

若第一段已完整而后段缓慢，可在下载进程全部退出后运行 `--consolidate-prefix`，核验并合并连续已收字节，再以 `--parallel-archive` 重分剩余两段。该步骤只操作本地字节，不代表整包校验通过；来源拒绝或存在缺口时不允许重分。

成功、失败、缺失和未尝试条目记录在私有 `sources/musescore/acquisition_report.json`，恢复journal在 `sources/musescore/pdmx/pdf-extraction.json`。取得的是PDMX导出PDF，未取得的MusicXML／MIDI仅保留格式信息；归档MD5通过不等于上游提供了每份PDF的校验和。仅在目标选取和最终文件核验完成后建立离线链接，公开网页继续只发布目录和来源页。

在下载停止后，先dry-run再按已核验候选执行去重，随后重新验证。ClassClef与新增来源工具各自保留独立journal：

```bash
python scripts/deduplicate_source_pdfs.py --root .
python scripts/deduplicate_added_pdfs.py --root .
```

只有本次摘要、适用的上游摘要、大小、解析和路径检查全部通过才允许 `--apply`。保留原件、来源清单和全部访问路径。

### 导出与离线更新

正式重新导出需要私有冻结来源元数据；导出只读元数据，不复制乐谱：

```bash
python scripts/export_public_site.py --root . --output public_site/data/catalog.json
python scripts/render_master_index.py .
```

完整离线重建核验PDF内容与清单关系。仅当文件／来源快照未变、只是显示修订时，可运行 `python scripts/render_master_index.py . --metadata-only`；它核对指纹、分类、全部现有链接及大小，保留先前PDF验收结果，不重新散列或解析PDF。

## 项目结构与保留规则

```text
guitar-atlas/
├── config/                       来源、范围、政策与精确排除
├── scripts/                      生产入口、共享目录和各来源适配器
├── tests/                        Python与Node回归测试
├── metadata/translations/        持久译名、精确守卫与复现规则
├── metadata/ranking/             有原文守卫的熟悉度参考
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
