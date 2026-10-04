# 2026-10-03 全库题名审读资产

本目录保存固定16来源、48,449条记录的题名决定与可复现的审读规则。原题、来源内ID和完整原署名是守卫，不因译文相近合并记录。研究与最终验收见 [`docs/research/2026-10-03-complete-title-review.md`](../../../docs/research/2026-10-03-complete-title-review.md)。

最终应用入口为 `python scripts/apply_title_review.py`，默认只检查；`--apply` 同时检查完整覆盖、原文、署名及主标题边界，并要求已有本轮备份。生产显示仍由上级目录四份持久译名资产提供。

| 文件组 | 用途 |
| --- | --- |
| `legacy_decisions.json` | IMSLP 与 ClassClef，共18,133条 |
| `cglib_decisions.json` | Classical Guitar Library，共16,544条 |
| `archive_decisions.json` | DGA、Boije、RISM，共9,307条 |
| `root_decisions.json` | 其余10来源，共4,465条 |
| `root_cross_source_botanical_supplement.json` | 全量守卫校验之后应用的32条Mertz植物题一致性补充；不合并来源ID |
| `root_cross_source_consistency_supplement.json` | 26组同原题/署名的译文一致性，以及有首演机构证据的斗篷语义修正，共63条 |
| `root_final_naturalness_supplement.json` | 完整主题关系、缩写及中文语序的最后75条精确补审；含1条历史符号原题保留 |
| `root_final_credit_display_supplement.json` | 前述全部语义决定之后的完整主标题补审：责任字段、来源标记、编号残片和有据歌剧对应；绑定完整中文与主标题旧值 |
| `display_spacing_guard_rebase.json`、`rebase_display_spacing_guards.py` | 861条精确英文显示边界仅归一化空白（其中620条有显式主标题守卫）；原题、署名、中文语义与状态不变，发布仍逐字符严格检查 |
| `final_projection_decisions.json`、`final_projection_expanded_decisions.json` | 实际生成中被通用书目拆分清空的1,614条中文主标题完整补审；分区819/795，绑定前一阶段的双中文前值，不采用全局回退 |
| `final_latin_semantic_review.json`、`final_context_root_decisions.json` | 完整重读277条较长Latin引文，修正186条，其余91条合法引文保留；另30条音乐/责任/分册语境精确决定。未知专名可保原文，明确音乐结构完整意译 |
| `final_actual_headline_decisions.json`、`final_actual_toponym_decisions.json` | 生成后的页面读回补审213条（199条主标题、14条地域曲名）：整理说明及叶码移入完整转录、真实曲集序号/音乐编号恢复、明确歌剧中文对应与地域题名自然译法；按第五阶段的双中文前值严格应用 |
| `*_supplement.json`、`*_readings.tsv`、`*_titles.tsv` | 精确题名补审及人工读解输入；由对应编译器汇入最终决定 |
| `*_rules.py`、`*_semantics.py`、`*_manual*.py`、词典与短语文件 | 有明确完整适用范围的音乐句法、参考意译与原文保留决定 |
| `build_*.py`、`*_build_*.py`、`*_validate_*.py`、`test_*.py` | 编译、原文守卫、编号、语义回归检查 |

`reviewed` 为有资料支持的惯用名；`reference` 为对照完整题名核对的参考译法；`retained` 为因具体歧义、专名构词或来源缺损保留原题。保留Latin专名的完整中文音乐题名也可以是参考译文，不靠生硬音译凑覆盖率。

全量Corpus、前后备份、临时分片、运行日志和机器验收保存在Git忽略的 `work/title-review/2026-10-03/`。这些资产不随浏览器载荷加载，亦不构成PDF或乐器编制认证。
