# 2026-10-02 既有题名、署名和栏目中文复核

本记录覆盖既有 IMSLP、ClassClef 题名，以及所有已登记来源的音乐家署名和栏目翻译。新增来源题名、题名中的网页字段拆分、公开目录及离线页面刷新由同日的整体修订记录汇总。本次只修改中文显示审查资产，原文、原生 ID、栏目成员关系、乐谱文件和下载状态均保留。

| 审查资产 | 扫描字段数 | 实际修改的不同条目数 |
| --- | ---: | ---: |
| IMSLP work-ID 题名 | 11,393 | 247 |
| ClassClef full-ID 题名 | 6,740 | 57 |
| source-scoped 音乐家署名 | 7,957 | 591 |
| source-scoped 栏目标签 | 2,228 | 154 |
| 合计 | 28,318 | 1,049 |

数字按审查资产中的不同字段条目计算，不是乐谱、PDF、作品实体或全来源记录数。多次补充修改同一条目只计一次。

## 检查及修订方法

- 对四份资产的全部条目检查损坏字符和控制字符；对全部题名检查书名号、内层书名号及中文括号配对。
- 从完整原题提取音乐体裁、乐器、调式及编号的上下文，扫描 Virginal、Orgel/Organo、Tabulature/Intabolatura、Consort、Tiento/Tento、Choro、Passamezzo、Op./Opus 等误作日常词义的候选；逐条决定修订或保留。标题中的 `Air` 不能统一译成咏叹调，例如 John Martyn 的歌名 `Solid Air` 不属于这一语境。
- 对序号、乐曲数量、罗马数字和原题内目录编号作候选扫描。115 条“中文出现而原题没有阿拉伯数字”的候选大多是合法的罗马数字、外语序数或日期转换；没有为消除扫描告警删除这些有效信息。实误 `LXXIII → 773` 已修复，保留原罗马数字。
- 核对完整原文署名、姓名顺序、明确姓氏的参考音译和原有首字母；不展开只有首字母的署名，不根据姓名相似度合并来源身份。同一来源栏目与完全相同原文署名明确对应时，中文显示同步。额外检查的 30 组相同完整原文在不同来源显示不一致问题已消除；这个检查不判定同名人物是否为同一人。
- 混入作品名的署名字段按原文的明确边界处理：6 条默茨署名和 `Ernest Shand, Study` 的中文只对应原字段中明确写出的人名，混入的作品号和题名仍保留在原始字段中。`Folger’s Dowland Lute Book` 是书名，保留原文并说明没有明确作曲者人名；不由书名推定约翰·道兰德的角色。
- DGA 有 5 条署名原文含 U+001A 损坏字符：3 条有完整姓名、年份及机构/出版社拼写支持的给参考音译；2 条 `Hole…ek, Josef, 1939-` 相关署名保留原文，用省略号标出损坏位置，并具体说明尚未确认完整拼写。受损原始值保持不变。
- 已确认为无依据字典翻译的专名撤回中文猜测，保留原文和具体原因，如 `Mall Simmes`、`Curro cuchares`、`Wascha mesa`、`Americano`。保留状态不算作规范中文专名已确认。真实原题中的括号、页码和目录编号不作一刀切删除。
- 独立末轮语义复核追加 31 条精确修订（IMSLP 30、ClassClef 1）：17 条规模修饰词 Grand/Grande/Gran/Große 改为音乐语境的大或大型；并修订卡廷姓氏、凯克沃克舞曲、微分音、维奥尔琴、引子、瓜希拉舞曲、加沃特舞曲、拉丁语乡村舞曲等明确词义错误。该批次只对应冻结的完整原题和 ID，没有全库替换形容词、语言或专名。

## 修订实例

| 原题 | 旧中文问题 | 修订后的参考中文 |
| --- | --- | --- |
| Fitzwilliam Virginal Book | 把键盘乐器译为处女 | 菲茨威廉维吉纳琴曲集 |
| Werken voor Orgel | 把管风琴译为器官 | 管风琴作品集 |
| Consort VIII / Consort VI | 把合奏译为王妃 | 合奏曲 VIII / 合奏曲 VI |
| Intabolatura de Lauto | 把指法谱译为制表、把鲁特琴误作琵琶 | 鲁特琴指法谱 |
| Tento do Segundo Tom | 把调式和体裁译为“汤姆第二次尝试” | 第二调式蒂恩托曲 |
| Pequeña Copla Sefardí | “小号西班牙裔科普拉” | 塞法迪小歌谣 |
| Clarines y Trompetas | 把号角译成单簧管 | 号角与小号 |
| Choro Teimoso, Op.12 | “再次偷窃” | 倔强的肖罗，作品12 |
| Pass'e mezzo a la villana | “距离别墅还有半小时” | 乡村风格帕萨梅佐舞曲 |
| Aloha Oe | “不客气” | 与你告别（Aloha Oe） |
| Cantio Lodomerica LXXIII | 编造 773 | 洛多梅里亚歌曲 LXXIII |
| Opus 211 No 10 Poco Allegretto | 丢失 Poco 的程度限定 | 作品211第10首：小快板（Poco Allegretto） |
| Cutting's Comfort | 把卡廷姓氏译为切割 | 卡廷的慰藉 |
| Prelúdio Microtonal No.1 | 微音调 | 微分音前奏曲第1号 |
| Viola da Gamba Sonata in G major, WK 157 | 把维奥尔琴当成中提琴 | G大调维奥尔琴奏鸣曲，WK157 |
| Gavota infantil | 儿童抽屉 | 儿童加沃特舞曲 |
| Chorea rustica, f.169r | 黄舞蹈病 | 乡村舞曲，f.169r |
| Grande Sérénade, Op.17 | 伟大的小夜曲 | 大型小夜曲，作品17 |
| Flaxy Cunninghams Cake Walk | 亚麻坎宁安蛋糕步行 | Flaxy Cunninghams凯克沃克舞曲 |
| Bribes No.1 | 无依据选定“贿赂”词义 | Bribes第1号（保留原词待核） |

书名号统一使用外层 `《》`、内层 `〈〉`；`Cello Suite No. 5` 的中文是“第5号大提琴组曲”，避免读成 5 把大提琴；明确复数乐曲的数量使用“首”。没有由乐谱所在网站或栏目补造演奏人数。

参考资料：菲茨威廉博物馆的 [Fitzwilliam Virginal Book 说明](https://www.fitzmuseum.cam.ac.uk/explore-our-collection/highlights/Music-MS-168)确认这是键盘曲集；美国国会图书馆的 [Aloha oe 条目](https://www.loc.gov/item/jukebox-21810/)列出另题 *Farewell to thee*。损坏姓名使用 [德沃夏克学会](https://www.dvorakantonin.com/about-us-in-english/)、[Naxos 的出版物后封](https://cdn.naxos.com/sharedfiles/pdf/rear/UP0118-2r.pdf)、[Schott 出版社条目](https://schottmusiclondon.com/the-russian-collection-vol-1-no441058.html)核对完整拼写。这些资料支持原文词义或姓名拼写，不代表机构审定了本项目的中文译名。

[CNRTL 的 bribes 词条](https://www.cnrtl.fr/definition/bribes)说明法语的零片、片段等词义，并区分英语词义；[来源作品页](https://imslp.org/wiki/Bribes_No.1_(Cooper,_Valiha_Nic%C3%A9phore))没有明确说明作者命名的语言或含义。因此保留 `Bribes`，只翻译作品序号，不凭作者国籍断言“片段”或“贿赂”。这里的 `retention_reason` 也必须使公共字段证据保持 `retained`，即使“第1号”包含汉字。法语歌曲主题 `L'or est une chimère` 也保留原词，不套用生物学“嵌合体”。

## 可复现记录及验证边界

精确修改计划保存在 `metadata/translations/review_2026-10-02/legacy_exact_corrections.json`。每条包含 exact 原文、资产路径、完整修改前后行和原因；补充复核接受的旧批次也必须是事先冻结的完整行。`scripts/apply_legacy_translation_review.py` 默认仅检查，在所有受影响资产通过原文、ID、完整行及结构校验之后才允许 `--apply`。不同或并发修改过的行会拒绝覆盖。

```sh
python scripts/apply_legacy_translation_review.py --root . \
  --report work/translation-review/2026-10-02/legacy-final-audit.json
python -m pytest -q tests/test_legacy_translation_review.py tests/test_catalog_translations.py
```

最终复查：1,049 条修改全部为已应用、28,318 字段指定结构与音乐语境检查 0 问题；测试 42 项通过，其中本次审查新增文件包含 18 项。原始资产备份、候选扫描、每批应用收据及最终审计在 Git 忽略的 `work/translation-review/2026-10-02/` 下保留。没有提交、部署或获取新的文件。

本次中文均按字段证据保留 `reference` 或有具体原因的 `retained`，没有因为中文非空而改成 `reviewed`。全字段扫描与对候选逐条复核，不等于每一条历史参考译名都经过独立权威专名考证，也不验证 PDF 内容、配器或版权。保留原文的古曲名、损坏署名及来源不明的角色仍是明确的待核边界。
