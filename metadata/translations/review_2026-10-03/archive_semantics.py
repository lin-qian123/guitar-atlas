"""Exclusive archive-title review helper; never edits production assets.

Only complete closed phrases/structures and exact reviewed titles are translated.
Retained decisions are separately logged with the unresolved source wording.
"""
from __future__ import annotations
import json,re,sys,unicodedata,hashlib
from functools import lru_cache
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts'))
import title_translation_quality as tq
HERE=Path(__file__).resolve().parent
PRIVATE=ROOT/'work/title-review/2026-10-03/archive-review'
SOURCE_REFS={
 'rism_rules':'https://guidelines.rism.info/masks.html',
 'intavolatura':'https://www.treccani.it/enciclopedia/intavolatura_%28Enciclopedia-Italiana%29/',
 'folia':'https://www.treccani.it/enciclopedia/follia_%28Enciclopedia-Italiana%29/',
 'fantaisie':'https://www.cnrtl.fr/definition/fantasie',
 'potpourri':'https://www.dictionnaire-academie.fr/article/A9P3698',
 'branle':'https://mediatheque.cnd.fr/ressources/ressourcesEnLigne/aid/aid/AID34_06/AID34_06.pdf',
 'mertz':'https://www.naxos.com/CatalogueDetail/?id=8.554556',
 'boije':'https://old.capricemusic.se/musikochteaterbiblioteket/ladda-ner-noter/boijes-samling/',
 'noce':'https://www.treccani.it/vocabolario/noce2/',
}
def norm(s):
 return re.sub(r'\s+',' ',unicodedata.normalize('NFC',s)).strip()
def marked(s):
 s=s.strip()
 if s.startswith('《') and s.endswith('》'):
  depth=0;valid=True
  for i,c in enumerate(s):
   if c=='《':depth+=1
   elif c=='》':depth-=1
   if depth==0 and i<len(s)-1:valid=False;break
   if depth<0:valid=False;break
  if valid and depth==0:s=s[1:-1]
 return '《'+s+'》'
def table(s):
 return {norm(a).casefold():b for a,b in (x.split('\t',1) for x in s.strip().splitlines() if '\t' in x)}

# Complete title readings, not dictionary substitutions inside unfamiliar prose.
EXACT=table('''
Rossiniana No. 3	罗西尼主题幻想曲第3号
Rossiniana Nr. 3	罗西尼主题幻想曲第3号
L'italiana in Algeri	阿尔及尔的意大利女郎
2 Opernarien und verschiedene Lieder mit Gitarrenbegleitung	2首歌剧咏叹调及各类歌曲（吉他伴奏）
Tête de Cuvée, für drei Gitarren	Tête de Cuvée（为三把吉他而作）
La paloma	鸽子
Didon	狄多
Livre de guiterre, 5; Print	吉他曲集，第5册
3 Libros de musica	3册音乐曲集
Angelus	三钟经
Il Sentimentale	感伤者
La Risoluzione	决心
Lo Scherzo	谐谑曲
L'Amoroso	多情者
L'Armonia	和谐
La Melanconia	忧郁
L'Allegria	欢乐
The mountaineers	山民
Wir schwelgen in rauschenden Freuden	我们沉醉于欢腾的喜悦
Szkoła na gitarę hiszpańską	西班牙吉他教程
Die kleine Diebin	小女贼
Jean de Paris	巴黎的 Jean
Die Festung an der Elbe	易北河畔的堡垒
Palmira regina di Persia	波斯女王 Palmira
Das ländliche Fest im Wäldchen bei Kisber	Kisber 小树林中的乡间节庆
Die Hochzeit der Thetis und des Peleus	忒提斯与珀琉斯的婚礼
Ballade du fou	疯人的叙事曲
Andantino mosso	稍活跃的小行板
Allegro vivace	活泼的快板
Giocoso	诙谐地
Maestoso	庄严地
Tempo di Valzer	圆舞曲速度
Souvenir de Munic	慕尼黑的回忆
Didone abbandonata	被遗弃的狄多
Neue Wald-Ländler	新森林兰德勒舞曲
La lira notturna	夜间的里拉琴
Vero e facil modo d'imparare a sonare et accordare da se medesimo la chitarra spagnola	自学西班牙吉他演奏与调弦的可靠简易方法
New and compleat instruction book	新编完整教程
Favorit Walzer der Königin Louise von Preußen	普鲁士路易丝王后喜爱的圆舞曲
Ginevra di Scozia	苏格兰的 Ginevra
Die Schweizer Familie	瑞士家庭
Österreichische National-Ländler	奥地利民族兰德勒舞曲
Rossiniana	罗西尼主题幻想曲
Sonate di chitarra spagniola	西班牙吉他奏鸣曲
Fuggi fuggi fuggi da questo cielo	逃离，逃离，逃离这片天空
Azul metálico	金属蓝
Suoni notturni	夜间之声
Per Armando	献给 Armando
Les Pêcheurs de perles	采珠人
Les adieux d'Oscar à Malvina	Oscar 向 Malvina 告别
Kosender Walzer	温柔的圆舞曲
Ni jamais ni toujours	既非从不，也非永远
Les Adieux	告别
Le souvenir	回忆
Gastarbeiter	外来劳工
Silhuetas de uma dança imaginária	想象之舞的剪影
No me mires que miran	别看我，有人在看
Au vallon tout est sombre	山谷中一片幽暗
Variations on a Rhythmic Line	节奏线条变奏曲
Sammlung verschiedener Musikstücke für Violin Prim u. Guitar Second [sic!]	第一小提琴与第二吉他的各类乐曲集〔原文如此〕
Washington Square	华盛顿广场
The Woodman	樵夫
Henry and Emma	Henry 与 Emma
The Poor Soldier	可怜的士兵
The Pirates	海盗
Begone dull care	忧愁，退散吧
The crusade	十字军东征
The Farmer	农夫
The prize	奖赏
Miss Margaret Hamilton's quickstep	Margaret Hamilton 小姐的快步舞曲
Livre de guitare dédié au roi	献给国王的吉他曲集
The Wedding day	婚礼之日
Le Jeune Henri	年轻的 Henri
Recueil des pièces faciles	简易乐曲集
Sacred songs	圣歌
Gramatica di musica	音乐基础法则
Mazur na gitarę	吉他玛祖尔舞曲
Space : 6 x 5	空间：6 x 5
Già la notte si avvicina	夜幕已渐近
Der treue Tod	忠实的死神
Lieblings-Walzer	心爱的圆舞曲
Un momento	一瞬间
En el campo	在乡间
L'assedio di Corinto	科林斯围城
Three Waltzes and Quick Step	三首圆舞曲与快步舞曲
The trip to Portsmouth	朴次茅斯之旅
Tu y yo	你和我
Zamacueca y la Gueya	萨马库埃卡舞曲与 Gueya
Estilo criollo	克里奥尔风格
God save great George our king	上帝保佑我们伟大的乔治国王
The Jubilee	庆典
The nunnery	女修道院
Robin Hood	罗宾汉
Fontainbleau	枫丹白露
Love in a camp	军营中的爱情
The Duenna	女监护人
Le nozze di Figaro	费加罗的婚礼
Richard Cœur-de-Lion	狮心王理查
Blue Beard	蓝胡子
The art of playing the guitar	吉他演奏艺术
Je pense à vous	我思念你
Don Giovanni	唐璜
La clemenza di Tito	提托的仁慈
Folies d'Espagne	西班牙福利亚
Les Vendanges de Suresnes	叙雷讷的葡萄采收
Siège de Compiègne	贡比涅围城
La Belle	美人
Pavane d'Espagne	西班牙帕凡舞曲
Le Double en Double	变奏之变奏
Noël	圣诞歌曲
Cavalier	骑士
Rondo Savoyard	萨伏依回旋曲
Grandes Variations sur la Romance favorite Partant pour la Syrie	以浪漫曲〈出发去叙利亚〉为主题的大型变奏曲
Josephchen Polka	Josephchen 波尔卡
Russische Polka	俄罗斯波尔卡
Emser Favorit-Polka	Ems 精选波尔卡
Speyerer-Polka	施派尔波尔卡
Carnevals-Galopp	狂欢节加洛普舞曲
Böhmische Polka	波希米亚波尔卡
Alpenhorn Polka	阿尔卑斯号角波尔卡
Scherz und Laune	诙谐与兴致
L'Ukrainienne	乌克兰女郎
Pariser Polka	巴黎波尔卡
Böhmische Mazurka	波希米亚玛祖卡
Creuznacher Polka	克罗伊茨纳赫波尔卡
La canción del Pierrot	Pierrot 之歌
The Quaker	贵格会教徒
Thomas and Sally	Thomas 与 Sally
The Ladies Frolick	女士们的嬉戏
Inkle and Yarico	Inkle 与 Yarico
Villanelle accomodate con l'intavolatura	附指法谱的维拉内拉歌曲
Nuova corona d'intavolatura di chitarra spagnola	西班牙吉他指法谱新冠集
Vago fior di virtù	美好的德行之花
La Ginevra	Ginevra
Love in a Village	乡村中的爱情
La biondina	金发少女
The Beggar Girl	乞女
La Caccia	狩猎
Herbstrosen	秋日玫瑰
Lesson for the guitar	吉他课题
Les Variétés amusantes	趣味小品集
Il barbiere di Siviglia	塞维利亚的理发师
Prost Neujahr Polka	新年干杯波尔卡
Choix de mes fleurs chéries	珍爱之花选集
Neptuns Galopp	海神加洛普舞曲
Olga-Polka	Olga 波尔卡
Ein Lebens-Funken	生命的火花
Léonien-Polka	Léonien 波尔卡
Charlotten-Polka	Charlotten 波尔卡
Minuè	小步舞曲
Floating Down the Mississippi	沿密西西比河漂流
Blue Monday	忧郁的星期一
Lunar loops	月球环
La italiana en Argel - Obertura	〈阿尔及尔的意大利女郎〉序曲
Baile inglés	英国舞曲
El tío y la tía - Obertura	〈叔叔与阿姨〉序曲
El tío y la tía - Aria de Colás	〈叔叔与阿姨〉中的 Colás 咏叹调
Huldigungs-Walzer	致敬圆舞曲
Cespuglio di varii fiori	各色花丛
Loin de toi	远离你
Pasa Calle	帕萨卡列
Melange dell'Opera Othello	歌剧〈Othello〉主题杂集
Ma dernière Fantaisie	我最后的幻想曲
El Barbero de Sevilla - Obertura	〈塞维利亚的理发师〉序曲
Tancredi - Obertura	〈Tancredi〉序曲
La navegación	航行
Fantaisie sur un motif favori de Bellini	以 Bellini 的精选主题写成的幻想曲
Intrata	入场曲
Ma Brunette Polka	我的褐发姑娘波尔卡
La Tranquillità	宁静
Bonne humeur	好心情
Nachtwandler Polka	梦游者波尔卡
Auswahl der beliebtesten Deutschen vom Apollosaal	阿波罗舞厅精选德国舞曲
Escuela completa de guitarra	完整吉他教程
Lecciones teórico-prácticas de Guitarra	吉他理论与实践课程
[No title]	来源未记题名
The Tyrolese Melodies, Arranged in an easy style for the spanish Guitar.	蒂罗尔旋律（西班牙吉他简易改编）
Romance of the Guitar	吉他的故事
Fun With Fretted Instruments	有品乐器的乐趣
The Classic Guitar	古典吉他
The Plectrum Guitar	拨片吉他
The Banjo	班卓琴
Right Hand Technic for the Classic Guitar	古典吉他右手技巧
Preparing a Concert Program	音乐会曲目的准备
The Tremolo on Fretted Instruments	有品乐器的震音奏法
A Fresh Start for Teacher and Pupil	师生的新起点
Electrical Instruments	电气乐器
The Guitar in Chamber Music	室内乐中的吉他
Fundamental Guitar Technic	吉他基础技巧
The Care of Instruments	乐器的保养
The Guitar - Fingers or Plectrum	吉他：手指或拨片
The Guitar and Modern Music	吉他与现代音乐
Tone Production	发音方法
Ensembles of Fretted Instruments	有品乐器合奏
Artistic Effects on the Guitar	吉他的艺术表现手法
Playing and Teaching the Fretted Instrument as a Profession	以有品乐器演奏与教学为业
World Artists on the Classic Guitar	世界古典吉他艺术家
Some Tips on Strings	琴弦使用提示
Scale Practice for Guitarists	吉他演奏者的音阶练习
The Orchestra Guitarist	乐团中的吉他演奏者
Teacher or Salesman?	教师还是推销员？
The Mandolin and Banjo	曼陀林与班卓琴
Getting Ready for the Fall Season	为秋季演出季做准备
The Carcassi Guitar Method	Carcassi 吉他教程
Practice Hints for Guitarists	吉他练习提示
The Future of Fretted Instruments	有品乐器的未来
Special Exercises for Guitar	吉他专项练习
What the Great Masters Thought of the Mandolin and Guitar	音乐大师眼中的曼陀林与吉他
Guitar Recordings and Flamenco	吉他录音与弗拉门戈
Personal Glimpses	人物速写
Will the Banjo Stage a Comeback?	班卓琴会重返舞台吗？
The Guitar - Classic, Plectrum, Hawaiian?	吉他：古典、拨片还是夏威夷式？
Guitar Music	吉他音乐
Legato Playing for Guitarists	吉他连奏技巧
Mandolin Music	曼陀林音乐
The Tarrega Guitar Method	Tarrega 吉他教程
The Electric Hawaiian Guitar	夏威夷电吉他
Guitar Chords	吉他和弦
Classic Guitar Chords	古典吉他和弦
Guitar Ensembles	吉他合奏
Guitar News	吉他新闻
Tambourin	坦布兰舞曲
Théme Styrien	施蒂利亚主题
Positions-Øvelser for Guitarre	吉他把位练习
Romersk Dans : Allegretto con moto	罗马舞曲：流动的小快板
Romersk Dans	罗马舞曲
Snedkerens Vise	木匠之歌
Cachucha	卡丘恰舞曲
Gubben Noah	老诺亚
Menuet u. Trio	小步舞曲与中段
Air Polonais	波兰曲调
Der Concertmeister	乐团首席
Valz	圆舞曲
Pria che l'Impegno / Carcassi	Pria che l'Impegno（Carcassi）
Di Tanti Palpiti / Carcassi	〈Di Tanti Palpiti〉（Carcassi）
Compositions choisies guitare	吉他作品精选
Oeuvres pour guitare	吉他作品集
Oeuvres nouvelles pour guitare	新吉他作品集
Opern=Revue. Ausgewählte Melodien für die Guitare. Übertragen	歌剧荟萃：吉他精选旋律（改编）
Trentasei ariette nazionali con accompagnamento di chitarra	36首民族小咏叹调（吉他伴奏）
Potpourris pour une Guitare sur des Operas favoris	吉他精选歌剧主题集成曲
Récréations musicales collection de morceaux faciles pour guitare et flûte ou violon sur des motifs d'opéras favoris ; op. 321	音乐消遣：吉他与长笛或小提琴的简易歌剧主题乐曲集，作品321
Walzer für die Guitarre	吉他圆舞曲
Barden-Klänge. Original-Compositionen für die Guitarre	吟游诗人的歌声：吉他原创作品集
Periodical amusements for the spanish guitar	西班牙吉他定期消遣曲集
Auswal der beliebtesten Tänze	热门舞曲精选
Guitare et musique revue mensuelle	〈吉他与音乐〉月刊
Guitare et musique, chansons, poesie	吉他与音乐、歌曲、诗歌
Flowers of song arranged ; with an accompaniment for the spanish guitar	歌曲之花（西班牙吉他伴奏改编）
Armonia bimonthly for guitar	〈Armonia〉吉他双月刊
Guitar news official organ of the International Classic Guitar Association	〈吉他新闻〉：国际古典吉他协会会刊
NOTTURNO A DUE VOCI	二声部夜曲
Six fantaisies pour la guitare sur des motifs des opéras nouveaux	六首新歌剧主题吉他幻想曲
NOTBOK	乐谱册
[NOTBOK]	乐谱册
NOT-BOK	乐谱册
''')

# Closed lexical grammar. Multiword collocations take priority and every word
# must be consumed; unknown names/incipits never become generic music terms.
TERMS=table('''
fantaisie	幻想曲
fantasie	幻想曲
fantasia	幻想曲
fantasi	幻想曲
fantaisies	幻想曲
fantasien	幻想曲
variations	变奏曲
variazioni	变奏曲
variationer	变奏曲
variationen	变奏曲
etude	练习曲
étude	练习曲
etuder	练习曲
etudes	练习曲
études	练习曲
seconde	第二
première	第一
premiere	第一
deuxième	第二
deuxieme	第二
troisième	第三
quatrième	第四
quatrieme	第四
cinquième	第五
grosse sonate	大型奏鸣曲
größere	大型
grosse	大型
grande fantaisie	大型幻想曲
grande fantasie	大型幻想曲
fantaisie brillante	华丽幻想曲
freies fantasie	自由幻想曲
freies fantaisie	自由幻想曲
freies	自由
freier	自由
freie	自由
fantaisie variée	变奏幻想曲
fantasies	幻想曲
andante cantabile	如歌的行板
andante espressivo	富于表情的行板
allegro cantabile	如歌的快板
allegretto scherzando	诙谐的小快板
moderato	中板
adagio	柔板
largo	广板
guitarre-album	吉他曲集
oeuvres pour guitare	吉他作品集
original-compositionen	原创作品
national airs	民族曲调
monferines	蒙费里纳舞曲
laendlers	兰德勒舞曲
laendler	兰德勒舞曲
landlers	兰德勒舞曲
walzes	圆舞曲
walses	圆舞曲
waltzes	圆舞曲
valtzes	圆舞曲
walz	圆舞曲
valses	圆舞曲
valzer	圆舞曲
ecossaiser	苏格兰舞曲
ecossoises	苏格兰舞曲
galopes	加洛普舞曲
polonoises	波兰舞曲
capricetti	小随想曲
minués	小步舞曲
minuetos	小步舞曲
concert-solo	音乐会独奏曲
grand solo	大型独奏曲
étude mélodique	旋律性练习曲
etudes instructives	教学练习曲
exercises instructifs	教学练习
exercices instructifs	教学练习
etudes mélodiques et progressives	旋律性渐进练习曲
petites leçons progressives	渐进小课题
petites pieces instructives	教学小品
pièces instructives	教学小品
pièces de société	社交小品
pieces de société	社交小品
pieces progressives	渐进乐曲
diverses pièces	各类乐曲
morceaux de concert	音乐会乐曲
caprice	随想曲
bravour variationen	炫技变奏曲
instruction	教程
méthodhe complète	完整教程
metodhe complète	完整教程
second edition of instructions	教程第二版
schule für die guitare	吉他教程
schule	教程
schul	教程
leçons	课题
prime lezioni	初级课题
6-string	6弦
esercizio	练习
essercizi	练习
erato	ERATO
heugel	Heugel
simrock	Simrock
romanza	浪漫曲
romance sans paroles	无词浪漫曲
romance utan ord	无词浪漫曲
lied ohne worte	无词歌
liebeslied	情歌
capricho árabe	阿拉伯随想曲
choro	肖罗
habanera	哈巴涅拉舞曲
preludj	前奏曲
preludes	前奏曲
préludes	前奏曲
serenata	小夜曲
serenate	小夜曲
introduzione	引子
introduction	引子
tema	主题
thême	主题
thème	主题
theme	主题
thema	主题
finale	终曲
coda	尾声
ricercario	里切尔卡尔
duo nocturne	二重奏夜曲
gran sonata eroica	大型英雄奏鸣曲
lyra	LYRA
le rossiniane	罗西尼主题幻想曲
rossiniana	罗西尼主题幻想曲
heimath	故乡
souvenir	回忆
pensée fugitive	浮动的思绪
improvisation	即兴曲
impromptu	即兴曲
tarantella	塔兰泰拉舞曲
sarabanda	萨拉班德舞曲
thema	主题
marcia funebre	葬礼进行曲
the last compositions	最后的作品
rudiments	基础教程
fröhliche jagd	欢乐的狩猎
enjoyment	消遣
four	四
två	二
sex	六
sexton	十六
zwölf	十二
seize	十六
cinque	五
cinq	五
guitarre-album	吉他曲集
guitare-album	吉他曲集
2me	第2
1re	第1
1er	第1
del	部分
heft	册
liv	册
opus posthume	遗作
op posthume	遗作
''') | table('''
barden-klänge	吟游诗人的歌声
bardenklänge	吟游诗人的歌声
barden-klange	吟游诗人的歌声
les variétés amusantes	趣味小品集
les variétés amusantes ou dépot di pieces faciles	趣味小品集，或简易乐曲合集
guitar instruction book	吉他教程
for 6-string guitar	6弦吉他
for 6 string guitar	6弦吉他
grazioso	优美地
marches	进行曲
fantasies	幻想曲
gitarrenmusik	吉他音乐
choros	肖罗
presto	急板
ständchen	小夜曲
polonaise	波兰舞曲
ballads	歌谣
serenatas	小夜曲
operas	歌剧
gavottes	加沃特舞曲
chaconnes	恰空
polka	波尔卡
variation	变奏曲
minuets	小步舞曲
sonatas	奏鸣曲
caprices	随想曲
method for the guitar	吉他教程
method for guitar	吉他教程
method of classical guitar playing	古典吉他演奏教程
méthode compléte pour la guitare	完整吉他教程
méthode complète pour la guitare	完整吉他教程
nuevo método para guitarra	新吉他教程
guitar exercises	吉他练习
pour la guitare	吉他
for solo guitar	吉他独奏
instruction book	教程
exercices pour la guitare	吉他练习
etuden für die gitarre	吉他练习曲
étuden für die gitarre	吉他练习曲
study for guitar	吉他练习曲
livre	册
concertos	协奏曲
fugues	赋格曲
hornpipes	霍恩派普舞曲
tutors	教程
quadrilles	四对方舞曲
quadrille	四对方舞曲
branles	布朗勒舞曲
bourrées	布列舞曲
gigues	吉格舞曲
doubles	变奏
movements	乐章
anglaise	英国舞曲
allemandes	阿勒曼德舞曲
folies d'espagne	西班牙福利亚
galoppade	加洛普舞曲
galops	加洛普舞曲
galopp	加洛普舞曲
krakowiak	克拉科维亚克舞曲
kozachok	科扎乔克舞曲
mazur	玛祖尔舞曲
jarabe	哈拉贝舞曲
cotillions	科蒂永舞曲
monferrine	蒙费里纳舞曲
eccossaise	苏格兰舞曲
rigaudons	里戈东舞曲
sarabandes	萨拉班德舞曲
polkas	波尔卡
intavolatura di chitarra spagnola	西班牙吉他指法谱
intavolatura della chitarra spagnola	西班牙吉他指法谱
intavolatura	指法谱
corona d'intavolatura di chitarra spagnola	西班牙吉他指法谱冠集
musikalischer fruchtgarten	音乐果园
chansons	歌曲
vocal pieces	声乐曲
folk songs	民歌
elegant ballads	典雅歌谣
canzonette musicali e moderne	现代歌曲
canzonette musicali	歌曲
impromptus	即兴曲
trios	三重奏
quartets	四重奏
quintets	五重奏
quartett	四重奏
boleros	波莱罗舞曲
guitar exercises	吉他练习
guitar music	吉他音乐
guitar chords	吉他和弦
compositions and arrangements	创作与改编作品
chitarra	吉他
chitarre	吉他
gitarre	吉他
guitar solos	吉他独奏曲
solos	独奏曲
capricen	随想曲
capricci	随想曲
duettino	小二重奏
duett	二重奏
duos	二重奏
duetto	二重奏
quintetti	五重奏
concerto	协奏曲
conzert	协奏曲
guitarr	吉他
guitarrer	吉他
gitarren	吉他
etuden	练习曲
étuden	练习曲
studien	练习曲
studios	练习曲
studio	练习曲
studio per chitarra	吉他练习曲
for mandolin and guitar	曼陀林与吉他
for guitar and piano	吉他与钢琴
pour guitare et piano	吉他与钢琴
per chitarra sola	吉他独奏
per chitarra solo	吉他独奏
pour la guitarre	吉他
für die guitarre	吉他
für die gitarre	吉他
pour guitare	吉他
para guitarra	吉他
per chitarra	吉他
for guitar	吉他
for the guitar	吉他
for the spanish guitar	西班牙吉他
pour guitare et flûte	吉他与长笛
pour la guitare seule	吉他独奏
pour la guitarre seule	吉他独奏
flauto e chitarra	长笛与吉他
violino e chitarra	小提琴与吉他
guitare et flûte	吉他与长笛
guitare et violon	吉他与小提琴
violin and guitar	小提琴与吉他
flute and guitar	长笛与吉他
violon et guitare	小提琴与吉他
flûte ou violon	长笛或小提琴
flauto o violino	长笛或小提琴
pianoforte	钢琴
piano-forte	钢琴
piano forte	钢琴
violine	小提琴
guitarre	吉他
guitarra	吉他
violino	小提琴
alto	中提琴
lyre	里拉琴
harpe	竖琴
fagot	巴松管
clarinette	单簧管
string quartet	弦乐四重奏
quartetto d'archi	弦乐四重奏
quartette d'archi	弦乐四重奏
concertant	协奏性
concertante	协奏性
concertantes	协奏性
concertants	协奏性
favoris	精选
favori	精选
favoured	精选
facil	简易
très faciles	极简易
très facile	极简易
très utiles	实用
soigneusement doigtés	精心标注指法
soigneusement doigtées	精心标注指法
doigtés	标注指法
melodious	旋律优美的
recreation pieces	消遣小品
recreations	消遣曲
récréations musicales	音乐消遣
récréations	消遣曲
progressive lessons	渐进课题
classical guitar playing	古典吉他演奏
guitar playing	吉他演奏
méthode pour la guitare	吉他教程
metodo per chitarra	吉他教程
complete method	完整教程
modern method	现代教程
modern chord method	现代和弦教程
new revised edition	新修订版
engraved plate edition	雕版印刷版
musique	音乐
music	音乐
valzer	圆舞曲
valse	圆舞曲
vals	圆舞曲
walzer	圆舞曲
walz	圆舞曲
valse caprice	圆舞随想曲
thèmes variés	主题变奏
thêmes variés	主题变奏
themes varies	主题变奏
tema con variazioni	主题与变奏
theme and variations	主题与变奏
thema varié	主题变奏
tema con variaciones	主题与变奏
air suisse varié	瑞士曲调变奏
air polonais	波兰曲调
thème russe varié	俄罗斯主题变奏
theme russe	俄罗斯主题
thema russe	俄罗斯主题
variato	变奏
varié	变奏
variés	变奏
variazioni	变奏曲
variationen	变奏曲
variaz	变奏曲
pot-pourri	集成曲
pot pourri	集成曲
potpourri	集成曲
potpourris	集成曲
rondeaux	回旋曲
rondeau	回旋曲
ariette	小咏叹调
arietta	小咏叹调
arioso	咏叙调
cavatine	卡瓦蒂纳
cavatina	卡瓦蒂纳
sonates	奏鸣曲
sonate	奏鸣曲
sonata	奏鸣曲
notturno	夜曲
notturino	夜曲
notturni	夜曲
preludio	前奏曲
marcia	进行曲
marcha	进行曲
marches funèbres	葬礼进行曲
marche funèbre	葬礼进行曲
marche	进行曲
march	进行曲
divertissemens	嬉游曲
divertiment	嬉游曲
duets	二重奏
symphonies	交响曲
singing	歌唱
vocal	声乐
book	册
livro	册
libro	册
le livre	曲集
cah	册
band	卷
partie	部分
part	部分
parte	部分
stimm	声部
aus	选自
för	为
och	与
ou	或
or	或
o	或
sola	独奏
solo	独奏
seule	独奏
seul	独奏
con	与
mit	与
accompagnamento	伴奏
original	原创
original-compositionen	原创作品
composta	作曲
composte	作曲
composées	作曲
composée	作曲
composé	作曲
composés	作曲
composed	作曲
grand valse	大型圆舞曲
grande sonate	大型奏鸣曲
grand rondo	大型回旋曲
grand rondeau	大型回旋曲
grand potpourri	大型集成曲
grand pot-pourri	大型集成曲
grande sérénade	大型小夜曲
grand serenade	大型小夜曲
grande serenade	大型小夜曲
grande serenata	大型小夜曲
grand duo	大型二重奏
grand duetto	大型二重奏
grand nocturne	大型夜曲
grand concerto	大型协奏曲
grande concerto	大型协奏曲
grands	大型
grand	大型
grande	大型
easy	简易
brillante	华丽
brillant	华丽
brillande	华丽
six	六
sept	七
dix	十
douze	十二
quatre	四
trois	三
trois	三
vingt quatre	二十四
vingt-quatre	二十四
vingt	二十
otto	八
due	二
two	二
three	三
four	四
five	五
seven	七
eight	八
ten	十
twelve	十二
twenty	二十
thirty	三十
thirty-six	三十六
trentasei	三十六
primo	第一
secondo	第二
second	第二
two voices	二声部
a due voci	二声部
print	印本
arrangement	改编
''')

def load_rows():
 return sum((json.load(open(ROOT/f'work/title-review/2026-10-03/{s}.json')) for s in ('dga','boije','rism')),[])

@lru_cache(maxsize=1)
def vocabulary():
 vocab={e['original'].casefold():e['zh'] for e in json.load(open(ROOT/'metadata/translations/expansion_terminology_zh.json'))['entries'] if e['context']=='title_term'}
 vocab.update(tq.EXTRA_TERMS)
 # Parent's complete semantic phrases are readings, not work identity aliases.
 parent=json.load(open(HERE/'root_semantic_phrases.json'))
 vocab.update({norm(k).casefold():v for k,v in parent.items()})
 vocab.update(TERMS)
 vocab.update(table((HERE/"archive_extra_terms.tsv").read_text()))
 for w in ('major','minor','dur','moll','maggiore','minore','sharp','flat','i','ii','iii','iv','v','vi','vii','viii','ix','x'):vocab.pop(w,None)
 return vocab

def grammar(text):
 """Whole-title closed semantic grammar; numbers and source brackets preserved."""
 source=norm(text)
 if len(source)>400 or '|' in source or '{' in source or '}' in source:return None
 if re.search(r'(?<!\w)[BH]\s*-?\s*(?:dur|moll)\b',source,re.I):return None
 source=re.sub(r'^A\s+(?!(?:major|minor|dur|moll|and|in)\b)(?=[A-Za-z])','',source)
 vocab=vocabulary()
 slots=[]
 def slot(v):slots.append(v);return '\ue000'+str(len(slots)-1)+'\ue001'
 t=re.sub(r'"([^"\n]+)"|“([^”\n]+)”',lambda m:slot('〈'+(m[1] or m[2])+'〉'),source)
 t=tq.KEY_RE.sub(lambda m:slot(tq.key_zh(m)),t)
 t=re.sub(r'(?<!\w)(?:en|in)\s+(do|ut|re|ré|mi|fa|sol|la|si|ti)(?=\s*(?:$|[,.;:/]|(?:op[.]|opus|oeuv|pour|per|para|for|für|et\s+passac|e\s+passac)\b))',lambda m:slot({'do':'C','ut':'C','re':'D','ré':'D','mi':'E','fa':'F','sol':'G','la':'A','si':'B','ti':'B'}[m[1].casefold()]+'调'),t,flags=re.I)
 t=tq.NOTE_ONLY_RE.sub(lambda m:slot(('降' if m.group(2) in {'flat','♭'} else '升' if m.group(2) else '')+m.group(1).upper()+'调'),t)
 t=tq.OPUS.sub(lambda m:slot('作品'+m.group(1)),t)
 t=re.sub(r'(?<!\w)(?:opera|opus|oper)\s*[:.]?\s*([IVXLCDM]+)(?!\w)',lambda m:slot('作品'+m[1]),t,flags=re.I)
 t=re.sub(r'(?<!\w)(?:opera|oper|opa|opa\.|oeuvr|oeuvre)\s*[:.]?\s*(\d+[a-z]?)',lambda m:slot('作品'+m[1]),t,flags=re.I)
 t=re.sub(r'(?<!\w)(\d+)(?:tes|ter|te|ième|eme|me|er|mo|ma|do)\s*(?:Werk|Wærk)',lambda m:slot('作品'+m[1]),t,flags=re.I)
 t=re.sub(r'(?<!\w)(\d+)(?:tes|ter|te|ième|eme|me|er|mo|ma|do)(?!\w)',lambda m:slot('第'+m[1]),t,flags=re.I)
 t=tq.SERIAL.sub(lambda m:slot('第'+m.group(1)+'号'),t)
 t=re.sub(r'(?<!\w)(?:BWV|RV|KV|K|Hob|D|SWV|HWV|WoO|MWV|S)\s*\.?\s*\d+(?:[/:.-]\d+)*(?:[a-z])?',lambda m:slot(m.group()),t,flags=re.I)
 t=re.sub(r'(?<!\w)[IVXLCDM]+(?!\w)',lambda m:slot(m.group()),t)
 vocab,pat=tq.vocabulary_pattern(tuple(sorted(vocab.items())))
 t=pat.sub(lambda m:slot(vocab[m.group().casefold()]),t)
 for name in ('Rossini','Bellini','Verdi','Mozart','Weber','Donizetti','Carulli','Giuliani','Carcassi','Mertz','Beethoven','Schubert','Chopin','Cramer','Auber','Meyerbeer','Hummel','Kreutzer','Tárrega','Tarrega','Cipriani','Picchianti','Diabelli','Nava','Küffner','Kuffner','Sor','Rainer','Paër','Paer'):
  t=re.sub(r'(?<!\w)'+re.escape(name)+r'(?!\w)',lambda m:slot(m.group()),t,flags=re.I)
 t=re.sub(r'(?<!\w)[A-G](?!\w)',lambda m:slot(m.group()),t)
 articles=tq.ARTICLES|{'un','una','uno','une','ein','eine','einer','einen','einem','eines','die','der','das','den','dem','of','on','im','am','zu','zur','zum','u','pr','e'}
 residual=[w for w in re.findall(r'[^\W\d_]+',t) if w.casefold() not in articles]
 if residual:return None
 t=re.sub(r"(?<!\w)(?:"+'|'.join(sorted(articles,key=len,reverse=True))+r")(?!\w)'?",'',t,flags=re.I)
 t=re.sub(r'\ue000(\d+)\ue001',lambda m:slots[int(m.group(1))],t)
 if not tq.HAN.search(t):return None
 t=polish(t)
 if Counter(re.findall(r'\d+',source))!=Counter(re.findall(r'\d+',t)):return None
 return t

def polish(t):
 # Closed musical constructions use Chinese punctuation and explicitly group
 # the complete instrumentation rather than swapping only its first item.
 t=t.replace('&','与')
 t=re.sub(r'(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])','',t)
 t=re.sub(r'\s*[,，;；]\s*','，',t)
 t=re.sub(r'\s*[:：]\s*','：',t)
 t=re.sub(r'\s*\.\.\.\s*|\s*…\s*','…',t)
 t=re.sub(r'(?<=[\u3400-\u9fff\d])\s*\.\s*(?=[\u3400-\u9fff])','，',t)
 t=re.sub(r'\s+',' ',t).strip(' .。,:;')
 t=re.sub(r'([\u3400-\u9fff])\s+([A-Z\d])',r'\1\2',t)
 t=re.sub(r'([A-Z\d])\s+([\u3400-\u9fff])',r'\1\2',t)
 t=re.sub(r'(作品\d+[a-z]?(?:\s*bis)?)\s*[.]?\s*',r'\1：',t).rstrip('：')
 t=t.replace('：，','，').replace('：)',')').replace('：]',' ]')
 t=re.sub(r'第(\d+)号\s*\.',r'第\1号：',t)
 genres=r'(?:独奏曲|田园曲|集锦|组曲|小赋格|教程|波兰舞曲|塔兰泰拉舞曲|帕萨卡莱亚|萨拉班德舞曲|哈巴涅拉舞曲|塞吉迪亚舞曲|小奏鸣曲|小二重奏|声乐曲|器乐曲|歌谣|歌曲|旋律|乐曲|小品|练习随想曲|练习曲|课题|圆舞曲|前奏曲|奏鸣曲|协奏曲|随想曲|幻想曲|二重奏|三重奏|四重奏|五重奏|夜曲|小步舞曲|曲调|玛祖卡|兰德勒舞曲|蒙费里纳舞曲|波尔卡|舞曲|回旋曲|变奏曲|小夜曲|嬉游曲|主题变奏|序曲|音乐|作品集)'
 inst=r'(?:古典吉他|低音吉他|吉他独奏|西班牙吉他|法式吉他|双吉他|吉他|钢琴|长笛|小提琴|中提琴|大提琴|低音提琴|单簧管|竖笛|竖琴|曼陀林|曼陀铃|曼多拉|巴松管|鲁特琴|里拉琴|声乐|声部|管弦乐队|室内乐合奏|弦乐队|弦乐四重奏)'
 # Genre suffix adjectives apply to that musical form, not the following
 # composer or instrument. No unknown word is consumed by these rules.
 t=re.sub(r'('+genres+r')(华丽|简易|渐进|精选|协奏性|协奏式|交响性的)',r'\2\1',t)
 t=t.replace('小简易奏鸣曲','简易小奏鸣曲').replace('小吉他独奏奏鸣曲','吉他独奏小奏鸣曲')
 t=t.replace('二重奏协奏性','协奏二重奏').replace('二重奏协奏式','协奏二重奏').replace('协奏性二重奏','协奏二重奏').replace('大型协奏二重奏','大协奏二重奏')
 # Preserve complete instrument alternatives as one phrase in parentheses.
 t=re.sub(r'('+genres+r')[:：]?(?:为)?((?:二|两把|两支|两|双|2|1)?'+inst+r'(?:[，与或及]+(?:二|两|两把|两支|双|2|1)?'+inst+r')*)',r'\1（\2）',t)
 t=re.sub(r'('+genres+r')（(吉他独奏|吉他|西班牙吉他)）',r'\2\1',t)
 t=re.sub(r'(完整|新|大型|现代)?教程(吉他|西班牙吉他)',r'\2\1教程',t)
 t=t.replace('完整教程为吉他而作','完整吉他教程').replace('练习为吉他而作','吉他练习')
 t=re.sub(r'(?<![\d作品第])([一二三四五六七八九十百]+|\d+)\s*(?=(?:小|大型|简易|渐进|华丽|精选|典雅|原创|民族|风格|旋律优美的|吉他|西班牙吉他)*'+genres+r')',r'\1首',t)
 t=re.sub(r'(作品\d+)首',r'\1',t)
 t=re.sub(r'(?P<g>'+genres+r')\s*(?P<k>[升降]?[A-G](?:大调|小调|调))',r'\g<k>\g<g>',t)
 t=re.sub(r'('+genres+r')作曲$',r'\1',t)
 t=re.sub(r'('+genres+r')创作(?:与)?$',r'\1',t)
 t=t.replace('小小奏鸣曲','小奏鸣曲').replace('创作与改编作品吉他','吉他创作与改编作品').replace('创作与改编作品（吉他）','吉他创作与改编作品').replace('首圆舞曲为与二吉他','首圆舞曲（单吉他与双吉他）')
 t=t.replace('：：','：')
 t=t.replace('集成曲','集锦').replace('歌剧-荟萃','歌剧巡览').replace('首首','首')
 t=re.sub(r'作品(\d+)：([a-z])(?=$|[，、])',r'作品\1\2',t)
 return t.strip(' ，.：')

if __name__=='__main__':
 rows=load_rows()
 for s in ('rism','boije','dga'):
  src=[r for r in rows if r['source_id']==s]
  unresolved=[];seen=set();done=[]
  for r in src:
   t=norm(r['display_original'])
   z=EXACT.get(t.casefold()) or grammar(t)
   if z:done.append({'id':r['id'],'original':r['display_original'],'zh':z})
   elif t not in seen:unresolved.append(r);seen.add(t)
  (PRIVATE/f'{s}-grammar.json').write_text(json.dumps(done,ensure_ascii=False,indent=2)+'\n')
  (PRIVATE/f'{s}-unresolved.json').write_text(json.dumps(unresolved,ensure_ascii=False,indent=2)+'\n')
  print(s,len(src),len(done),'unresolved unique',len(unresolved))
