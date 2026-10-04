const test = require('node:test');
const assert = require('node:assert/strict');
const search = require('../public_site/assets/search.js');

const categories = [
  {id:0, name:'For 2 guitars', name_zh:'双重奏', source_id:'imslp', family:'pure', kind:'original'},
  {id:1, name:'For flute, guitar (arr)', name_zh:'长笛、吉他·改编', source_id:'imslp', family:'woodwinds', kind:'arrangement'},
];
const item = (id, composer_en, composer_zh, title_en='Etude, Op.2', title_zh='《练习曲，Op.2》', extra={}) =>
  ({id, composer_en, composer_zh, title_en, title_zh, category_ids:[0], ...extra});
const ids = response => response.matches.map(match => match.item.id);
const aliases = {composers:{'Sor, Fernando':['梭尔','费尔南多·梭尔']}};

test('bounded Chinese composer surnames precede embedded names and title-only mentions', () => {
  const works = [
    item('embedded','Esor, Example','埃索尔'),
    item('mention','Other, Author','其他作者','Theme by Sor','《索尔主题变奏曲》'),
    item('title','Other, Author','其他作者','Sor','《索尔》'),
    item('composer','Sor, Fernando','费尔南多·索尔'),
  ];
  const original = structuredClone(works);
  const index = search.createIndex({categories, works}, aliases, {works:{embedded:1000000, mention:1000000}});
  const result = index.search('索尔', {topic:'all', category:'0'});
  assert.equal(result.matches[0].item.id, 'composer');
  assert.ok(ids(result).indexOf('title') < ids(result).indexOf('embedded'));
  assert.deepEqual(works, original, 'Ranking must never rewrite attributions or titles');
  assert.equal(result.mode, 'exact');
});

test('Latin name tokens precede substrings and all terms remain mandatory', () => {
  const works = [
    item('embedded','Esor, Example','埃索尔'),
    item('sor','Sor, Fernando','费尔南多·索尔'),
    item('title','Other, Author','其他作者','Sor Theme, Op.2','《主题》'),
    item('missing-number','Sor, Fernando','费尔南多·索尔','Etude, Op.27','《练习曲，Op.27》'),
  ];
  const index = search.createIndex({categories, works}, aliases, {works:{embedded:1000000}});
  assert.equal(index.search('Sor').matches[0].item.id, 'sor');
  assert.equal(index.search('Sor op2').matches[0].item.id, 'sor');
  assert.ok(!ids(index.search('Sor op2')).includes('missing-number'));
  assert.deepEqual(ids(index.search('Sor op2 nonexistent')), []);
});

test('exact full composer aliases outrank another composer mentioning the alias in a title', () => {
  const works = [item('sor','Fernando Sor',''), item('title','Other, Author','其他作者','A theme by Sor','《梭尔》')];
  const index = search.createIndex({categories, works}, aliases, {works:{title:10000}});
  assert.deepEqual(ids(index.search('梭尔')), ['sor','title']);
  assert.equal(index.search('梭尔').matches[0].matchType, 'alias');
});

test('queryless browsing uses composer and stable-record weights before alphabetic ties', () => {
  const works = [
    item('unknown','A, Unknown','未知作者'),
    item('sor:2','Fernando Sor','费尔南多·索尔','Z duet','《Z 双重奏》'),
    item('sor:1','Sor, Fernando','费尔南多·索尔','A duet','《A 双重奏》'),
    item('other-sor','Sor, Carlos','卡洛斯·索尔'),
  ];
  const index = search.createIndex({categories, works}, aliases, {composers:{'Sor, Fernando':60}, works:{'sor:2':30}});
  assert.deepEqual(ids(index.search('', {category:0})), ['sor:2','sor:1','unknown','other-sor']);
  assert.equal(index.search('索尔').matches[0].item.id, 'sor:2', 'Popularity can break equal relevance');
  assert.deepEqual(index.suggest(''), []);
});

test('popularity never merges records or leaks through a shared surname', () => {
  const works = [item('sor','Sor, Fernando','费尔南多·索尔'), item('carlos','Sor, Carlos','卡洛斯·索尔'),
    item('anonymous','','','A duet','《双重奏》'), item('same-title','Other, Author','其他作者')];
  const index = search.createIndex({categories, works}, {}, {composers:{'Fernando Sor':60}, works:{anonymous:40}});
  const result = index.search('', {category:0});
  assert.equal(result.matches.length, 4);
  assert.deepEqual(ids(result).slice(0,2), ['sor','anonymous']);
  assert.equal(ids(result).at(-1), 'carlos');
});

test('invalid weights do not change baseline deterministic ordering', () => {
  const works = [item('b','B, Composer','B'), item('a','A, Composer','A')];
  const data = {categories, works};
  const baseline = ids(search.createIndex(data).search(''));
  const ranking = {composers:{'B, Composer':-1}, works:{b:'100', a:Infinity}};
  assert.deepEqual(ids(search.createIndex(data, {}, ranking).search('')), baseline);
});

test('relevance, weight and category/topic filters all use the same active membership', () => {
  const works = [
    item('sor','Sor, Fernando','费尔南多·索尔','Etude','《练习曲》',
      {category_ids:[0,1], topic_ids:['duo','woodwinds'], topic_category_ids:{duo:[0], woodwinds:[1]}}),
    item('wrong','Esor, Example','埃索尔','Etude','《练习曲》',
      {category_ids:[1], topic_ids:['woodwinds'], topic_category_ids:{woodwinds:[1]}}),
  ];
  const index = search.createIndex({categories, topics:[{id:'duo', name_zh:'双重奏'}, {id:'woodwinds', name_zh:'木管、吉他'}], works},
    {}, {works:{wrong:100000}});
  assert.deepEqual(ids(index.search('索尔', {topic:'duo'})), ['sor']);
  assert.deepEqual(index.search('', {topic:'duo'}).matches[0].categories.map(category => category.id), [0]);
  assert.deepEqual(ids(index.search('索尔 长笛', {topic:'duo'})), []);
  assert.deepEqual(ids(index.search('Sor flute', {family:'woodwinds', kind:'original'})), []);
});

test('empty-query browsing does not read or fold full searchable metadata', () => {
  let reads = 0;
  const row = item('sor','Sor, Fernando','费尔南多·索尔');
  Object.defineProperty(row, 'details', {get() { reads++; return {notes:'A detailed archive description'}; }});
  const index = search.createIndex({categories, works:[row]}, aliases, {composers:{'Fernando Sor':60}});
  assert.deepEqual(ids(index.search('', {category:0})), ['sor']);
  assert.equal(reads, 0);
  assert.deepEqual(ids(index.search('archive')), ['sor']);
  assert.equal(reads, 1);
  assert.deepEqual(ids(index.search('description')), ['sor']);
  assert.equal(reads, 1, 'Repeated searches reuse normalized fields');
});

test('the real duo catalog ranks Fernando Sor before source labels containing 索尔', () => {
  const catalog = require('../public_site/data/catalog.json');
  const aliases = require('../public_site/data/search-aliases.json');
  const index = search.createIndex(catalog, aliases);
  const result = index.search('索尔', {topic:'duo'});
  assert.ok(result.matches.length > 0);
  assert.equal(result.matches[0].item.composer_en, 'Sor, Fernando');
  // The RISM authority form includes source dates; those records are also
  // Fernando Sor, rather than embedded hits for a different source name.
  const sorNames = new Set(['Sor, Fernando', 'Sor, Fernando (1778-1839)']);
  const sor = result.matches.filter(match => sorNames.has(match.item.composer_en));
  const other = result.matches.filter(match => !sorNames.has(match.item.composer_en));
  assert.ok(sor.length > 0 && other.length > 0, 'This catalog retains both genuine and embedded-name hits');
  assert.ok(Math.max(...sor.map(match => match.score)) < Math.min(...other.map(match => match.score)));
  assert.ok(result.matches.every(match => (match.item.topic_ids || []).includes('duo')));
});
