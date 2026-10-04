# 六弦漫行：网页视觉重做与验收

日期：2026-10-04。范围为公开网页与本地离线总入口的版式、图像、字体、控件、响应式和微动效；当前目录仍为16来源、48,449条来源记录。此次为本地更新，未推送或部署。

## 参考与设计

实际浏览10家官网的首页或目录：ECM、Letterform Archive、Wigmore Hall、Apartamento、The Modern House、V&A、minä perhonen、Schott、Henle、Rijksmuseum。所选页面、字体、字号、按钮圆角与过渡样本见[视觉参考研究](2026-10-04-visual-reference-study.md)。采用出版物与馆藏索引的结构，图像、标识及页面构图独立制作，未复制外站商标、图片或完整页面。

| 项目 | 最终实现 |
| --- | --- |
| 色彩 | 纸底 `#f4efe5`、墨色 `#292d27`、木红 `#8e4633`、细线 `#d1ccbe`、次级文字 `#6b6c60`。次级文字与纸底对比4.65:1、与卡片底5.07:1。 |
| 字体 | 拉丁展示字用自托管 Instrument Serif Regular/Italic；中文主标题和作品题名用系统宋体回退；界面控制用系统无衬线。字体采用 `font-display: swap`。 |
| 首页 | 保留左上角 Guitar Atlas；“六弦／漫行”错位分行，原创制琴图版、不等宽留白、目录规模、明确的目录入口。 |
| 默认目录 | 17个编号章目、桌面三栏、手机两栏；目录状态隐藏重复侧栏，来源原分类可另行展开。 |
| 作品列表 | 桌面分类侧栏与两栏资料页，手机横向分类条与单栏结果。中文题名、原题、署名、来源、编制及动作各有字级。版本资料仍可展开。 |
| 控件 | 搜索输入与提交组成完整长条，筛选折叠后展开三栏／两栏原生选择框。常用圆角0–3px；圆形仅用于独立图标。按钮、链接、折叠及选择框有键盘焦点，图标不替代文字标签。 |
| 来源入口 | 页尾16来源取自正式目录，点击保留关键词、显示当前来源筛选、清除其他筛选、恢复首批18条并滚至目录；浏览器返回可恢复先前条件。 |
| 动效 | 大多数控件过渡200–300ms，标识旋转450ms；首屏短暂一次入场。按钮变色、箭头微移、目录底色响应；遵守 `prefers-reduced-motion`，无循环漂浮、轮播或重型动效库。 |
| 同步 | 公开与离线共用HTML模板、CSS、app和搜索。CSS/app引用携带文件SHA-256前10位，离线注入规则兼容版本查询串。 |

## 原创图版与字体

主视觉使用内置 **image_gen** 生成；最终工作区资产为 `public_site/assets/luthier-study.webp`，800×1200、71,006 bytes。原1024×1536 PNG在图像工具产物目录留存，随后仅以 `cwebp -q 82 -m 6 -resize 800 1200` 编码与缩放，没有额外图像语义编辑。完整工具模式、原产物路径与编码记录保存在私有 `work/visual-redesign/2026-10-04/image-provenance.json`。

最终采用的生成提示词：

> Use case: illustration-story. Asset type: original editorial illustration for a meticulously designed classical guitar score archive website. Make a refined, quiet copperplate etching and graphite study of ONE real classical Spanish nylon-string guitar, on clean very pale warm ivory uncoated paper (#f4efe5). Portrait composition, instrument body large in the lower center, the neck rising diagonally toward the upper right, elegant generous blank margins. Six distinct fine strings, six tuning machines on a slotted classical headstock, accurate classical bridge and ornate restrained circular rosette. Warm walnut and amber wood, charcoal-black fine lines, muted sepia wash, subtle hand-drawn irregularity and delicate crosshatching like a luthier's exceptional archival instrument study. The instrument is the sole subject. Visual character: cultured contemporary art-book illustration, precise craftsmanship, beautiful natural wood grain, crisp fine detail with sparse soft graphite marks, no plastic rendering, no artificial aging, no dramatic spotlight. Include the whole body; neck may approach upper edge. No words, no lettering, no numbers, no logos, no watermark, no frame, no musical notes, no sheet music, no landscape, no decorative objects. This is an authentic-looking instrument illustration, not a website mockup or stock photograph. Make the image suitable for elegant large-scale cropping on a cream page.

六弦音孔标识为原创SVG，另生成180px触屏图标。Instrument Serif取自[Google Fonts官方字体源](https://github.com/google/fonts/tree/main/ofl/instrumentserif)，采用SIL OFL 1.1；两款WOFF合计56,972 bytes，每款316 glyphs，保留拉丁字母及必要标点，中文不另下载大字体。[字体说明](../../public_site/assets/fonts/README.md)、完整OFL与[第三方声明](../../THIRD_PARTY_NOTICES.md)随项目保存。运行时无需远程字体、CDN或第三方框架。

## 体积与数据保真

下表为实际引用资源的文件原始大小，各文件只计一次，包括主插画、两字体、favicon、touch图标、CSS、app、search及codec；不包括目录JSON，不代表真实网络压缩传输量或加载时间。

| 口径 | 改造前 bytes | 改造后 bytes | 变化 |
| --- | ---: | ---: | ---: |
| 页面引用静态资源 | 358,126 | 228,773 | −36.12% |
| 公开HTML | 6,862 | 8,003 | +1,141 |
| 离线HTML入口 | 7,431,767 | 7,435,153 | +3,386（约0.046%） |
| 浏览器压缩目录 | 5,628,832 | 5,628,832 | 不变 |

旧主视觉与旧图标保留但不再引用，完整assets目录包含历史图、README图及许可证；不把目录总量下降作为本轮结论。默认目录仍不渲染全库作品，结果首批18条、按需追加，全文与模糊索引继续按需建立。

独立审查逐项核对改造前后：canonical目录、compact目录、aliases、ranking、search.js、codec、离线adapter七份原文件的SHA-256完全一致；compact解码等于canonical。完整离线载荷的语义哈希一致，包括中文字段、来源身份、分类、关系、权重、所有 `local_editions`、分类 `local_href`、输入指纹及历史验证汇总。公开/离线27个既有DOM ID均保留，无重复；ARIA目标、HTML/CSS资源、缓存哈希、离线adapter恰一次且先于app等检查通过。

## 验收记录

- 全量Python：**1,256通过**，保留一条既有Requests依赖兼容警告；全量Node：**66通过、0失败**。
- 最终来源抽屉微调后再跑公开/离线相关Python **31项**、`node --test tests/search.test.cjs` **34项**，均通过；此前较广的聚焦回归46项亦通过。公开目录验证通过，48,449记录、2,228分类、57,062成员关系，公共乐谱文件链接0。
- 浏览器桌面1280×720、1440×1000及手机390×844、320×740；目录17章目、无重复快捷条，手机页面宽度等于视口，没有横向溢出。独立审读桌面首页、二重奏页与390px首页截图，没有必须修复的版式缺陷。
- 无查询二重奏1,789记录、首批18；“索尔”＋二重奏29记录，首项为索尔《鼓励》作品34，追加后显示全部29条。斜杠聚焦搜索，建议用方向键与Enter选中Fernando Sor，得到959条；实际输入法合成没有逐设备实测，既有合成保护代码与测试保持。
- 不存在的查询显示0条与清晰空状态；重置回17分类目录。页尾ClassClef筛选保留“索尔”，展开当前来源，得到197条；浏览器返回恢复二重奏29条。
- `MA ZÉTULBE`查询得到3条；极长原文题名在桌面与390px单栏自然换行，版本资料展开保留完整题名转录与载体描述。
- 通过本机HTTP实际打开离线总入口，1,789条二重奏首批显示18条；《鼓励》额外5份总谱／分谱展开后保留9个PDF入口。公开与离线浏览器控制台没有捕获到error/warn。本轮没有打开PDF来重复验证内容，也没有把本机HTTP检查描述成实际 `file://` 渲染验收。
- 最终离线使用 `--metadata-only`，来源指纹、清单／排除映射、35,433条本地路径及大小核对通过；保留此前PDF完整性结果，未重新散列或解析PDF。原入口自动备份。

私有证据集中于 `work/visual-redesign/2026-10-04/`：原实现备份、生成提示词与出处、Python/Node/公开验证日志、最终离线渲染日志、截图及 `ui-contract/RECEIPT.md`、`final-verification.json`、`font-verification.json`。截图包括桌面首页、目录、二重奏、长题名、离线分谱及手机首页、长题名。私有目录不进入公开站点或Git提交。

## 维护

今后的展示修改继续复用公开模板与共享资产，保持宋体／拉丁衬线／功能无衬线的分工、细线与克制圆角。改CSS/app后同步缓存版本并重新生成离线入口；新增字体须保留完整许可，新增装饰资产先核对实际引用大小。真实数据或文件变化按项目规定做完整重建，视觉刷新不替代文件核验。
