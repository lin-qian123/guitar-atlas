# 六弦漫行：网页设计、插图出处与验收

设计研究及实现日期：2026-10-04；文档整合日期：2026-10-11。本文件合并当日视觉研究、初稿、圆角修订和分类插图接入记录，以最终圆角收藏界面为维护基线。保留有效参考、图像出处及验收边界，过程备份、重复日志和查看截图不作为长期资料。

## 当前展示

公开网页与离线总入口共用模板、CSS、应用和搜索实现。英文导航品牌为 **Guitar Atlas**，中文主标题为 **六弦漫行**，页面标题为 `六弦漫行｜Guitar Atlas`。设计采用琴谱出版物与馆藏索引的层次，图像、标识与构图独立制作；未复制参考网站商标、图片或完整页面。

| 项目 | 维护基线 |
| --- | --- |
| 色彩 | 纸底 `#f6f3ec`、卡片底 `#fffdf8`、深绿文字 `#26473e`、木红 `#a34f38`、细线 `#dce0d4`、次级文字 `#5f6c61`。2026-10-04修订验收中，次级文字与分类底色最低对比4.56:1，深绿按钮白字10.06:1。 |
| 字体 | 拉丁展示字为自托管 Instrument Serif Regular/Italic；中文标题和作品题名用系统宋体回退；界面控件用系统无衬线。两款展示字体均用 `font-display: swap`，运行时不请求远程字体。 |
| 首屏 | 紧凑的不等宽图文扉页、曲线裁切与叠放图版、目录规模及明确入口；手机图文并列，统计单独成行。 |
| 目录与作品 | 默认17个共同分类收藏卡，保留编号和准确统计，原来源分类可展开。桌面作品列表有分类侧栏，手机用横向分类条；中文题名、原题、署名、来源及动作分别分层，完整版本资料可展开。 |
| 圆角 | 桌面首屏28px、关于区24px、搜索和作品卡18px、手机分类卡15px、输入与主按钮10px；来源／编制标签、筛选开关、工具栏和加载更多同样保留边界。 |
| 控件与动效 | 搜索输入和提交是一组完整控件；展开筛选用原生选择框。保留键盘焦点、禁用状态及文字标签。按钮色变、箭头微移、卡片两像素悬停位移和首屏一次入场，常用过渡200–300ms；遵守 `prefers-reduced-motion`，无循环漂浮、轮播或重型动效库。作品列表更新不重复入场。 |
| 功能 | 不因展示变化改写来源身份、题名审读、分类、文件关系、搜索匹配度或参考知名度排序。结果首批18条、按需追加，全文与模糊索引按需建立。来源入口保留查询，浏览器返回恢复筛选。 |
| 同步 | CSS/app引用携带文件SHA-256前10位缓存版本；离线脚本注入兼容查询串。离线数据与适配器不进入公开站点。 |

## 设计参考

2026-10-04直接浏览以下10家官网的首页或目录，读取页面内容并在独立研究标签页观察实际渲染、DOM及部分计算样式，桌面视口1280×720。字号、圆角和过渡是当次所选元素样本，并非全站规范；过渡时间来自CSS声明，未将未测的悬停轨迹、移动端或滚动行为当成已验证事实。部分宣传弹窗、异步图像和视频没有完整呈现。

| 官网与观察页面 | 当次样本与采用理由 |
| --- | --- |
| [ECM Records](https://ecmrecords.com/) | 白底独立唱片图版与留白；Univers标题66px/300、导航18px，按钮圆角0px，链接0.3s、搜索0.5s。借鉴单一视觉焦点和出版物尺度差。 |
| [Letterform Archive](https://letterformarchive.org/)、[Online Archive](https://oa.letterformarchive.org/) | 黑白加单一红色，Duplicate Sans/Ionic分工；会员按钮14px硬边，菜单有圆弧，过渡0.2s；档案有People、Disciplines、Decades、Formats维度及维护提示。借鉴题名、署名、来源、版本的字级和明确加载状态。 |
| [Wigmore Hall](https://www.wigmore-hall.org.uk/) | 小字导航与细底线；Sohne12px、部分标签字距3px，常用圆角0px，黑色动作按钮。借鉴对齐、线条与足够点击面积，不照搬运营弹窗。 |
| [Apartamento](https://www.apartamentomagazine.com/) | 米白导航与内容图版；Futura PT导航20px、主标题63px，Times章节45px，链接0.3s；主要硬边，视频动作局部圆弧。借鉴字体职责，未推断当次黑底视频的完整内容。 |
| [The Modern House](https://themodernhouse.com/) | 大图配窄文字栏；衬线标题32px、无衬线导航12px，细线动作矩形，导航过渡0.5s。借鉴不等宽布局及留白秩序。 |
| [V&A](https://www.vam.ac.uk/)、[Collections](https://collections.vam.ac.uk/) | Spiller展览标题60px、介绍41px、章节31px；藏品搜索输入23px、字段选择17px，组合角2px，另有30px圆弧主题按钮，过渡0.2s。借鉴一体搜索与分层筛选。 |
| [minä perhonen](https://www.mina-perhonen.jp/en/)、[About](https://www.mina-perhonen.jp/en/about/) | 左导航右内容，Helvetica Neue导航14px、Adobe Garamond Pro英文标题24px，日文字体声明含游明朝，主要硬边，链接0.6s。借鉴工艺质感与清楚功能文字；部分图像未加载，不评价未见影像。 |
| [Schott Music](https://www.schott-music.com/en/)、[Catalogues](https://www.schott-music.com/en/catalogues) | 区分乐谱、书籍、教育、研究和演出资料；Composer、Editor、Instrumentation、Media Type分别标注。Libre Franklin控件14px、章节26px，圆角0–3px，过渡0.3–0.5s。只借鉴资料角色与详情层次。 |
| [Henle Verlag](https://www.henle.de/en/) | Fira Sans Condensed导航14–16px，部分字重100；Composer、Instrumentation、Level of Difficulty、Products独立入口，语言控件圆角3px、过渡0.15s。借鉴作品与版本定位；本库没有核验难度数据，不引入难度判断。 |
| [Rijksmuseum · Discover](https://www.rijksmuseum.nl/en/collection/discover) | RijksText标题100px、主题章节58px、功能文字约17px，先列章节跳转再展开入口；导航主要硬边，局部圆角2px、过渡0.5s。借鉴目录章节与编号，部分图版当次仍为异步低清预览。 |

另阅读[Lowden Guitars](https://lowdenguitars.com/)的工艺、琴体系列、演示和目录内容；浏览器导航超时，因此不计入10个实际视觉样本，也不引用未确认的样式。Bach Digital、Bärenreiter的当次内容提取不足，Frick读取被拒绝，均不作为已完成观察。这些研究未构成对参考站全部页面、无障碍、性能或版权的审核。

## 保留的图像与字体出处

### 主视觉

当前网页及中英文README共用 [`archive-cover.webp`](../../public_site/assets/archive-cover.webp)，1100×620、64,096B；原始来源为此前项目的模型生成“吉他与旧谱”图版。本次只优化尺寸与编码，没有语义编辑：

```bash
cwebp -q 78 -m 6 -resize 1100 0 archive-hero.webp -o archive-cover.webp
```

原输入1672×941、209,164B，SHA-256为 `24bdd3e9f035c9d7ba8a781eb6e69433bf3b0edd016910e541ba4d643cf76c8d`；当前图版SHA-256为 `19fe321d15e43c4a547adb084acd2ae6393d3d66e23c11f95758cd125cf4fc9d`。输入名用于记录当时编码步骤；原输入现保存在私有 `work/artwork/archive-cover-source.webp`，运行时只引用当前图版。此次合并的设计资料没有保留这张旧主图的完整原生成提示词，不能由另一幅弃用图版的提示词补作它的出处。

### 分类图集

使用内置 `image_gen.imagegen` 于2026-10-04一次生成4列×3行的透明图集，12组水彩与铅笔风格小图，包括古典吉他人数组合、其他乐器、历史谱册与练习谱页。完整[生成提示词](2026-10-04-generated-category-art-prompt.txt)原样保留，不用脚本重绘，也没有把界面文字烧入图像。

| 出处字段 | 记录 |
| --- | --- |
| 原生成PNG | 私有 `work/artwork/category-atlas-source.png`；1448×1086、1,756,055B；SHA-256 `09951212cc11bb996e5bef651c601f6af93fa099d9e7579755fceeebeec05695` |
| 当前公开资产 | [`category-atlas-v1.webp`](../../public_site/assets/illustrations/category-atlas-v1.webp)，640×480、58,108B，透明通道保留 |
| 当前SHA-256 | `0ffbb51b237b3069f7afd83e727f6e10e937ad8f42097573e42b982fc1217851` |
| 后处理 | 仅缩放和WebP编码；未裁切重绘，未作语义编辑 |
| 用途 | 目录装饰；不证明来源记录的乐器、演奏人数或实际谱面 |

```bash
cwebp -q 68 -alpha_q 60 -m 6 -resize 640 0 original.png -o category-atlas-v1.webp
```

17个共同分类共享一个图片URL；CSS只定位图格和布置尺寸，桌面80px、手机64px，标题保留完整行宽。未增加DOM、JavaScript、依赖、字体或每作品封面，原CSS琴弦渐变、音孔及二重奏叠圈已移除。放大镜、箭头等功能图形及小尺寸品牌标识继续使用原控件图形。

| 图格（行、列） | 共同分类 |
| --- | --- |
| 1、1 | `solo` |
| 1、2 | `duo` |
| 1、3 | `trio` |
| 1、4 | `quartet`、`guitar_ensemble` |
| 2、1 | `strings` |
| 2、2 | `woodwinds` |
| 2、3 | `brass` |
| 2、4 | `keyboard_reed` |
| 3、1 | `plucked` |
| 3、2 | `percussion` |
| 3、3 | `mixed_chamber`、`historical`、`reference`、`unspecified`、`guitar_unspecified` |
| 3、4 | `studies` |

室内乐及编制未核明类别使用中性谱册，避免图像暗示已有精确编制证据。插图是项目创作资产，与第三方乐谱和来源元数据的权利边界分开，见[第三方声明](../../THIRD_PARTY_NOTICES.md)及[数据许可](../../DATA_LICENSE.md)。

### 字体与标识

Instrument Serif来自[作者项目](https://github.com/Instrument/instrument-serif)及[Google Fonts官方分发](https://github.com/google/fonts/tree/main/ofl/instrumentserif)，版权为2022 The Instrument Serif Project Authors，许可SIL OFL 1.1。Regular/Italic WOFF共56,972B，各316 glyphs，保留拉丁字母及所需标点，中文回退系统字体。完整[字体说明](../../public_site/assets/fonts/README.md)与[OFL](../../public_site/assets/fonts/OFL.txt)随项目保留，不修改上游许可原文。六弦音孔标识为项目原创SVG，触屏图标180px。

## 体积与必要历史

仅保留以下演进结论：初稿为硬边出版物目录，用户反馈后改为现行圆角收藏界面并恢复“吉他与旧谱”主图；随后分类装饰改用模型图集。初稿单琴图版、旧大图、旧README代码横幅及过程截图不是当前运行时资产，清理它们不改变现行页面。

2026-10-04最终展示引用资产合计 **283,302B**，HTML/CSS引用的图、字体、图标和脚本各计一次，不含HTML与目录JSON，也不是网络计时。接入图集前为224,765B；增量58,537B包含图集58,108B和CSS429B。最终CSS26,810B、app36,100B，未增加运行时库。2026-10-04正式发布时压缩目录为5,629,656B，保留完整canonical JSON作审计和兼容回退；后者不算默认页面下载量。

图集接入没有改4份公开数据、应用／搜索／codec或来源、中文、排名与本地版本关系。离线HTML曾增加3,308B，仅由details字典键插入顺序影响表排序及gzip编码；两次解包对象、列表顺序和全部字段直接相等，未压缩载荷均26,486,542B。正式发布导出又使compact增加824B，仍经解码逐字段相等验证。不要由压缩字节变化推断乐谱记录变化。

有效原稿与编码记录集中于私有 `work/artwork/`，仅保留当前主图与分类图集各一个原稿及 `provenance.json`。旧页面截图、试验稿与重复UI备份已清理，记录中的旧路径是当时路径。

## 已有验收与明确边界

以下均为2026-10-04已完成记录，文档整合不将其冒充新一轮浏览器或PDF验收；后续项目清理与部署见[发布记录](publication.md)。

- 初次视觉重做的全量Python1,256项、Node66项通过；圆角及模型图集最后各轮相关Python46项、Node66项通过，圆角文案微调另有聚焦Python31项通过。正式发布再在工作区与独立干净检出运行全量Python1,256项、Node66项、公开验证及译名／文本审计，均通过；本机有一条既有Requests依赖兼容警告。
- 目录保留16来源、48,449条来源记录、2,228原分类、57,062条成员关系、17个共同分类，公开乐谱文件链接0。这是来源记录数，不是跨站唯一乐曲数。
- 独立保真检查确认canonical/compact解码一致，原题、中文字段、身份、分类、关系、权重、所有 `local_editions` 和分类 `local_href`、输入指纹及历史验证摘要保留。公开／离线29个既有DOM ID、ARIA目标、共享资源、缓存版本和适配器先于app且恰好注入一次的契约通过。
- 浏览器检查桌面1280/1440px、平板768px和手机390/320px：首页、17分类、长题名、作品及详情可读，无横向溢出。模型图格、透明边缘、小尺寸辨识和标题空间通过；无捕获到的控制台error/warn。视觉截图只能证明当时画面，不能替代身份、排序、链接和数据验证。
- 二重奏1,789条，首批18条；“索尔”加二重奏29条，《鼓励》作品34在前，追加可显示全部29条。斜杠聚焦，建议方向键和Enter选中Fernando Sor后959条；ClassClef切换保留“索尔”得197条，返回恢复二重奏条件。`MA ZÉTULBE`得到3条，极长原题在手机自然换行；空查询结果和重置目录正常。实际输入法合成未逐设备测试，保留既有保护代码和测试。
- 圆角阶段通过本机HTTP打开离线总入口，《鼓励》额外5份总谱／分谱展开后共9个PDF入口；这是链接与界面检查，没有在该轮打开PDF验收内容。模型图集阶段浏览器工具拒绝直接打开 `file://`，停止该动作，离线仅检查数据、链接、资源和模板契约；不能描述为该协议UI验收。
- 离线采用 `--metadata-only` 同步：核对既有来源指纹、清单／排除映射和35,433条本地路径／大小，保留先前PDF验证摘要；未重新散列或解析PDF，也未扩大来源取得范围。译名覆盖／文本规则审计不等于所有中文惯用名的权威认证。

维护时优先原位修改共享CSS，用一张主图和一张共用分类图集承担视觉层次，避免完整覆盖样式、重复图版和装饰库累积。修改CSS/app应刷新缓存版本并同步离线入口；新增字体保留许可，新增插图保留精确提示词、出处和编码参数，先核对实际引用体积。资料、文件、分类或编制变化按项目要求做完整重建，展示整理不能升级既有文件核验结论。
