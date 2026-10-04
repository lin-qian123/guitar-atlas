const test = require('node:test');
const assert = require('node:assert/strict');
const {normalize} = require('../public_site/assets/search.js');

test('every supported traditional character preserves its simplified search correspondence', () => {
  const correspondences = [
    '蕭萧','爾尔','羅罗','馬马','亞亚','維维','納纳','貝贝','魯鲁','茲兹','裡里',
    '裏里','葉叶','華华','薩萨','蘇苏','喬乔','奧奥','費费','德德','達达','漢汉',
    '謝谢','馮冯','賽赛','寧宁','賈贾','倫伦','萊莱','門门','蘭兰','諾诺','齊齐',
    '樂乐','鋼钢','練练','習习','變变','圓圆','詠咏','嘆叹','調调',
    '諧谐','謔谑','夢梦','愛爱','憶忆','淚泪','敘叙','獻献','給给','詩诗','聲声',
    '長长','風风','與与','豎竖','簫箫','號号','單单','雙双','協协',
    '麗丽','蓮莲','聖圣','誕诞','莊庄','國国','歐欧','鄉乡','謠谣',
    '來来','歸归','別别','離离','歡欢','鳥鸟','鵝鹅','鵑鹃','鶴鹤','飛飞','龍龙',
    '鄧邓','慶庆','後后','黃黄','紅红','綠绿','藍蓝','銀银','滿满','無无','為为',
    '從从','這这','幾几','歲岁','時时','間间','廣广','場场','邊边','遠远',
    '選选','節节','組组','編编','絃弦','絲丝','紡纺','織织','線线','終终','續续',
  ];
  for (const [traditional, simplified] of correspondences.map(pair => [...pair])) {
    assert.equal(normalize(traditional), simplified, traditional);
    assert.equal(normalize(`Prelude ${traditional} Op.27`), `prelude ${simplified} op 27`, traditional);
  }
});

test('ASCII, accented names, separators and empty values retain existing folding', () => {
  assert.equal(normalize('ÉTUDE, Tárrega; æ œ ø ł ß Op.27 No.2'), 'etude tarrega ae oe o l ss op 27 no 2');
  assert.equal(normalize('ISBN: 978-9935-452-84-9'), 'isbn 978 9935 452 84 9');
  assert.equal(normalize('费尔南多·索尔'), '费尔南多索尔');
  assert.equal(normalize('ＡＢＣ１２３\n索爾'), 'abc 123 索尔');
  for (const value of [null, undefined, '', 0, false, NaN]) assert.equal(normalize(value), '');
});
