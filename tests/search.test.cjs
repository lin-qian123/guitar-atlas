const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const enginePath = path.join(__dirname, '../public_site/assets/search.js');
const categories = [
  {id: 0, name: 'For guitar', name_zh: '1把吉他·原作', family: 'pure', kind: 'original'},
  {id: 1, name: 'For flute, guitar (arr)', name_zh: '长笛、吉他·改编', family: 'woodwinds', kind: 'arrangement'},
];
const work = (id, title_en, title_zh, composer_en, composer_zh, category_ids = [0]) => ({id, title_en, title_zh, composer_en, composer_zh, category_ids});
const data = {categories, works: [
  work('1', 'Recuerdos de la Alhambra', '《阿尔罕布拉宫的回忆》', 'Tárrega, Francisco', '弗朗西斯科·泰雷加'),
  work('2', 'The Seasons, Op.37a', '《四季，Op.37a》', 'Tchaikovsky, Pyotr', '彼得·柴可夫斯基', [0, 1]),
  work('3', 'Nocturne, Op.9 No.2', '《夜曲，Op.9之2》', 'Chopin, Frédéric', '弗雷德里克·肖邦', [1]),
  work('4', 'Fantaisie, Op.7', '《幻想曲，Op.7》', 'Sor, Fernando', '费尔南多·索尔'),
  work('5', 'Prelude', '《前奏曲》', 'Sor, Carlos', '卡洛斯·索尔'),
  work('6', 'Prelude', '《前奏曲》', 'Bach, Johann Sebastian', '约翰·塞巴斯蒂安·巴赫'),
  work('7', 'Nocturne, Op.9 No.3', '《夜曲，Op.9之3》', 'Chopin, Frédéric', '弗雷德里克·肖邦', [1]),
]};
const aliases = {composers: {
  'Tárrega, Francisco': ['塔雷加', '塔瑞加'],
  'Tchaikovsky, Pyotr': ['柴科夫斯基', 'Tschaikowsky'],
  'Chopin, Frédéric': ['萧邦'],
  'Sor, Fernando': ['费尔南多·梭尔'],
  'Bach, Johann Sebastian': ['巴哈'],
}, works: {'1': ['阿尔汉布拉宫的回忆', '阿尔罕布拉宫的追忆']}};
function createIndex() {
  assert.ok(fs.existsSync(enginePath), 'A browser/Node search engine must support aliases and typo recovery');
  return require(enginePath).createIndex(data, aliases);
}
const ids = response => response.matches.map(match => match.item.id);

test('composer alternate translation finds canonical works without changing source names', () => {
  const response = createIndex().search('塔雷加');
  assert.deepEqual(ids(response), ['1']);
  assert.equal(response.matches[0].matchType, 'alias');
  assert.equal(response.matches[0].item.composer_zh, '弗朗西斯科·泰雷加');
});
test('composer aliases are scoped to full identity, not a shared surname', () => {
  assert.deepEqual(ids(createIndex().search('费尔南多 梭尔')), ['4']);
});
test('an exact composer alias ranks before titles that only mention that name', () => {
  const extra = work('8', 'Variations on a theme by Tarrega', '《塔瑞加主题变奏曲》', 'Other, Author', '另一位作曲家');
  const index = require(enginePath).createIndex({...data, works: [...data.works, extra]}, aliases);
  assert.equal(index.search('塔瑞加').matches[0].item.id, '1');
});
test('work aliases are scoped by work ID', () => {
  assert.deepEqual(ids(createIndex().search('阿尔汉布拉宫的回忆')), ['1']);
});
test('common traditional characters and alternate romanization are searchable', () => {
  assert.deepEqual(ids(createIndex().search('蕭邦 夜曲')), ['3', '7']);
  assert.deepEqual(ids(createIndex().search('Tschaikowsky')), ['2']);
});
test('accent, punctuation and opus spacing variations retain exact numbers', () => {
  assert.deepEqual(ids(createIndex().search('CHOPIN op9 no2')), ['3']);
  assert.deepEqual(ids(createIndex().search('tarrega recuerdos')), ['1']);
  assert.deepEqual(ids(createIndex().search('Chopin op9 no4')), []);
});
test('missing letters and adjacent swapped letters find nearby composer names', () => {
  for (const query of ['Tchaikovky', 'Tchaikvosky', 'Chpo in']) {
    // A split misspelling is deliberately not guessed by dropping a word.
    if (query === 'Chpo in') assert.deepEqual(ids(createIndex().search(query)), []);
    else {
      const response = createIndex().search(query);
      assert.deepEqual(ids(response), ['2']);
      assert.equal(response.mode, 'fuzzy');
    }
  }
  assert.deepEqual(ids(createIndex().search('B cah')), []);
  assert.deepEqual(ids(createIndex().search('Bcah')), ['6']);
});
test('approximate Chinese title matches retain all search terms', () => {
  assert.deepEqual(ids(createIndex().search('阿尔罕布拉宫的回意')), ['1']);
  assert.deepEqual(ids(createIndex().search('柴可夫斯机 四季')), ['2']);
  assert.deepEqual(ids(createIndex().search('柴可夫斯机 夜曲')), []);
});
test('exact hits stay first and do not pull in unrelated fuzzy hits', () => {
  const response = createIndex().search('Sor');
  assert.deepEqual(new Set(ids(response)), new Set(['4', '5']));
  assert.equal(response.mode, 'exact');
});
test('short and numeric queries are never loosely corrected', () => {
  for (const query of ['99', 'zz', '曲子', '索拉']) assert.deepEqual(ids(createIndex().search(query)), []);
});
test('original/arrangement/family filters must match one category membership', () => {
  const index = createIndex();
  assert.deepEqual(ids(index.search('Tchaikovky', {family:'woodwinds', kind:'original'})), []);
  const response = index.search('Tchaikovky', {family:'woodwinds', kind:'arrangement'});
  assert.deepEqual(ids(response), ['2']);
  assert.deepEqual(response.matches[0].categories.map(c => c.id), [1]);
  assert.deepEqual(ids(index.search('Tchaikovky', {category:'0'})), ['2']);
});
test('empty query still lists the filtered catalog and does not recommend random corrections', () => {
  const index = createIndex();
  assert.equal(index.search('').matches.length, 7);
  assert.deepEqual(index.suggest(''), []);
});
test('recommendations include canonical composers for aliases and misspellings', () => {
  const index = createIndex();
  for (const query of ['塔雷', '塔瑞加', 'Tarrega', 'Tarega']) {
    const suggestions = index.suggest(query);
    assert.ok(suggestions.some(s => s.kind === 'composer' && s.query === 'Tárrega, Francisco'), query);
    assert.ok(suggestions.length <= 6);
    assert.equal(new Set(suggestions.map(s => s.query)).size, suggestions.length);
  }
});
test('title recommendations preserve the composer in the selected query', () => {
  const suggestions = createIndex().suggest('阿尔罕');
  assert.ok(suggestions.some(s => s.kind === 'work' && s.query.includes('Recuerdos de la Alhambra') && s.query.includes('Tárrega')));
});
test('recommendations respect filters rather than suggesting inaccessible matches', () => {
  assert.deepEqual(createIndex().suggest('塔雷加', {family:'woodwinds'}), []);
});

test('the landing view shows categories until a query or exact category is selected', () => {
  const engine = require(enginePath);
  assert.equal(typeof engine.catalogView, 'function');
  assert.equal(engine.catalogView(''), 'categories');
  assert.equal(engine.catalogView('  ', {family:'woodwinds', kind:'arrangement'}), 'categories');
  assert.equal(engine.catalogView('塔瑞加'), 'works');
  assert.equal(engine.catalogView('', {category:'0'}), 'works');
});

test('category browsing keeps source labels, separates types and counts unique works', () => {
  const index = createIndex();
  assert.equal(typeof index.browse, 'function');
  const all = index.browse();
  assert.deepEqual(all.categories.map(category => category.name), ['For guitar', 'For flute, guitar (arr)']);
  assert.equal(all.workCount, 7);
  const mixed = index.browse({family:'woodwinds',kind:'arrangement'});
  assert.deepEqual(mixed.categories.map(category => category.id), [1]);
  assert.equal(mixed.workCount, 3);
  assert.deepEqual(index.browse({family:'woodwinds',kind:'original'}), {categories:[], workCount:0});
});

test('every approved category is reachable through the landing directory', () => {
  const catalog = require('../public_site/data/catalog.json');
  const index = require(enginePath).createIndex(catalog);
  assert.equal(typeof index.browse, 'function');
  const directory = index.browse();
  assert.equal(directory.categories.length, catalog.summary.category_count);
  assert.equal(directory.workCount, catalog.summary.unique_work_count);
  assert.equal(new Set(directory.categories.map(category => category.id)).size, catalog.categories.length);
  const pureOriginal = index.browse({family:'pure',kind:'original'}).categories;
  assert.equal(pureOriginal[0].name, 'For guitar');
  assert.ok(pureOriginal.findIndex(c => c.name === 'For 2 guitars') < pureOriginal.findIndex(c => c.name === 'For 12 guitars'));
});

test('versioned aliases resolve to real canonical identities and work IDs', () => {
  const aliasPath = path.join(__dirname, '../public_site/data/search-aliases.json');
  assert.ok(fs.existsSync(aliasPath), 'Curated alternate search names must be versioned');
  const aliases = JSON.parse(fs.readFileSync(aliasPath, 'utf8'));
  const catalog = require('../public_site/data/catalog.json');
  const names = new Set(catalog.works.map(work => work.composer_en));
  const workIds = new Set(catalog.works.map(work => work.id));
  for (const [name, values] of Object.entries(aliases.composers)) {
    assert.ok(names.has(name), name);
    assert.ok(values.length > 0 && values.every(value => typeof value === 'string' && value.trim()));
    assert.equal(new Set(values).size, values.length);
  }
  for (const [id, values] of Object.entries(aliases.works)) {
    assert.ok(workIds.has(id), id);
    assert.ok(values.length > 0 && values.every(value => typeof value === 'string' && value.trim()));
  }
  const index = require(enginePath).createIndex(catalog, aliases);
  assert.ok(ids(index.search('塔雷加 阿尔汉布拉')).includes('33377'));
  assert.ok(ids(index.search('德布西 月光')).includes('2397'));
  assert.ok(ids(index.search('Moonlight Sonata')).includes('1458'));
  assert.equal(index.search('Tchaikovky').matches.filter(m => m.item.composer_en === 'Tchaikovsky, Pyotr').length, 8);
});

const multiSourceData = {
  schema_version: 2,
  sources: [{id:'imslp', name:'IMSLP'}, {id:'classclef', name:'ClassClef'}],
  categories: [
    ...categories,
    {id:'classclef:tarrega', name:'Francisco Tarrega', name_zh:'', source_id:'classclef', family:'classclef', kind:'unspecified'},
    {id:'classclef:other', name:'Other composers', name_zh:'', source_id:'classclef', family:'classclef', kind:'unspecified'},
  ],
  works: [
    ...data.works,
    {...work('classclef:1', 'Recuerdos de la Alhambra', null, 'Francisco Tarrega', null, ['classclef:tarrega']),
      source_id:'classclef', source_url:'https://www.classclef.com/francisco-tarrega/', formats:['PDF', 'GPX', 'MIDI']},
    {...work('classclef:2', 'Prelude', '', 'Carlos Tarrega', '', ['classclef:other']),
      source_id:'classclef', formats:['PDF']},
  ],
};
const multiSourceIndex = () => require(enginePath).createIndex(multiSourceData, aliases);

test('sources keep distinct work identities even when titles and local IDs overlap', () => {
  const index = multiSourceIndex();
  assert.deepEqual(new Set(ids(index.search('Recuerdos'))), new Set(['1', 'classclef:1']));
  assert.deepEqual(ids(index.search('Recuerdos', {source:'imslp'})), ['1']);
  assert.deepEqual(ids(index.search('Recuerdos', {source:'classclef'})), ['classclef:1']);
  assert.deepEqual(ids(index.search('阿尔汉布拉宫的回忆', {source:'classclef'})), []);
  assert.equal(index.browse().workCount, data.works.length + 2);
});

test('source filtering applies to browsing, fuzzy recovery and suggestions', () => {
  const index = multiSourceIndex();
  const browse = index.browse({source:'classclef'});
  assert.deepEqual(browse.categories.map(category => category.id), ['classclef:tarrega', 'classclef:other']);
  assert.equal(browse.workCount, 2);
  assert.deepEqual(index.browse({source:'classclef',kind:'original'}), {categories:[], workCount:0});
  assert.deepEqual(ids(index.search('Recuerods', {source:'classclef'})), ['classclef:1']);
  assert.deepEqual(index.suggest('Chpo in', {source:'classclef'}), []);
  assert.deepEqual(index.suggest('Chopin', {source:'classclef'}), []);
  assert.ok(index.suggest('Tarega', {source:'classclef'}).some(s => s.query === 'Francisco Tarrega'));
  assert.equal(require(enginePath).catalogView('', {source:'classclef'}), 'categories');
});

test('unknown source classification stays separate from original and arrangement', () => {
  const index = multiSourceIndex();
  assert.deepEqual(ids(index.search('Recuerdos', {source:'classclef', kind:'original'})), []);
  assert.deepEqual(ids(index.search('Recuerdos', {source:'classclef', kind:'arrangement'})), []);
  assert.deepEqual(ids(index.search('Recuerdos', {kind:'unspecified', category:'classclef:tarrega'})), ['classclef:1']);
  assert.equal(require(enginePath).kindLabel('unspecified'), '来源未标注');
  assert.equal(require(enginePath).kindLabel('future-unmapped-kind'), '来源未标注');
});

test('source names and available formats are searchable without exposing file links', () => {
  const index = multiSourceIndex();
  assert.deepEqual(ids(index.search('ClassClef MIDI')), ['classclef:1']);
  assert.deepEqual(ids(index.search('classclef gpx', {source:'imslp'})), []);
  assert.deepEqual(ids(index.search('IMSLP Recuerdos')), ['1']);
  assert.ok(index.suggest('ClassClef GPX').some(s => s.kind === 'work' && s.label === 'Recuerdos de la Alhambra'));
  const suggestion = index.suggest('ClassClef GPX').find(s => s.kind === 'work');
  assert.deepEqual(ids(index.search(suggestion.query)), ['classclef:1']);
  assert.match(suggestion.query, /classclef/);
  assert.match(suggestion.query, /gpx/);
});

test('source title aliases are searchable without replacing source titles or crossing work IDs', () => {
  const item = {...multiSourceData.works.find(item => item.id === 'classclef:1'), title_aliases:['Memories of the Alhambra']};
  const index = require(enginePath).createIndex({...multiSourceData, works:[...data.works, item]}, aliases);
  const response = index.search('Memories Alhambra');
  assert.deepEqual(ids(response), ['classclef:1']);
  assert.equal(response.matches[0].matchType, 'alias');
  assert.equal(response.matches[0].item.title_en, 'Recuerdos de la Alhambra');
  assert.deepEqual(ids(index.search('Memories Alhambra', {source:'imslp'})), []);
});

test('null and empty translations fall back to original titles and attributions', () => {
  const engine = require(enginePath);
  const item = multiSourceData.works.find(item => item.id === 'classclef:1');
  assert.equal(engine.titleLabel(item), 'Recuerdos de la Alhambra');
  assert.equal(engine.composerLabel(item), 'Francisco Tarrega');
  const suggestions = multiSourceIndex().suggest('Recuerdos', {source:'classclef'});
  assert.ok(suggestions.every(s => s.label && s.detail));
  assert.equal(item.title_zh, null);
  assert.equal(item.composer_zh, null);
});

test('unattributed works remain searchable without inventing a composer suggestion', () => {
  const item = {...multiSourceData.works.at(-1), title_en:'Anonymous dance', composer_en:'', composer_zh:''};
  const engine = require(enginePath);
  const index = engine.createIndex({...multiSourceData, works:[item]});
  assert.equal(engine.composerLabel(item), '作者未标注');
  assert.deepEqual(ids(index.search('Anonymous')), ['classclef:2']);
  assert.ok(index.suggest('Anonymous').every(s => s.kind === 'work' && s.detail === '作者未标注'));
  assert.equal(item.composer_en, '');
});

test('curated full-name aliases work across source name ordering without rewriting identities', () => {
  const response = multiSourceIndex().search('塔瑞加');
  assert.deepEqual(new Set(ids(response)), new Set(['1', 'classclef:1']));
  assert.equal(response.matches.find(match => match.item.id === '1').item.composer_en, 'Tárrega, Francisco');
  assert.equal(response.matches.find(match => match.item.id === 'classclef:1').item.composer_en, 'Francisco Tarrega');
  assert.ok(!ids(response).includes('classclef:2'));
});

test('existing Chinese composer labels are shared for exact full names as search aliases only', () => {
  const shared = {...work('classclef:42', 'Etude', '', 'Mauro Giuliani', '', ['classclef:other']), source_id:'classclef'};
  const works = [
    work('42', 'Etude', '《练习曲》', 'Giuliani, Mauro', '毛罗·朱利亚尼'), shared,
    {...shared, id:'classclef:43', composer_en:'Michele Giuliani'},
    {...shared, id:'classclef:44', composer_en:'M. Giuliani'},
    {...shared, id:'classclef:45', composer_en:'Mauro A. Giuliani'},
  ];
  const index = require(enginePath).createIndex({...multiSourceData, works}, {});
  assert.deepEqual(new Set(ids(index.search('毛罗 朱利亚尼'))), new Set(['42','classclef:42']));
  assert.deepEqual(ids(index.search('毛罗 朱利亚尼', {source:'classclef'})), ['classclef:42']);
  assert.ok(index.suggest('毛罗 朱利亚尼', {source:'classclef'}).some(s => s.kind === 'composer' && s.query === 'Mauro Giuliani'));
  assert.equal(shared.composer_en, 'Mauro Giuliani');
  assert.equal(shared.composer_zh, '');
});

test('category query terms must belong to the active membership in exact and fuzzy search', () => {
  const index = multiSourceIndex();
  assert.deepEqual(ids(index.search('Tchaikovsky flute', {family:'pure'})), []);
  assert.deepEqual(ids(index.search('Tchaikovky flute', {family:'pure'})), []);
  assert.deepEqual(ids(index.search('Tchaikovky flute', {family:'woodwinds',kind:'arrangement',source:'imslp'})), ['2']);
  assert.deepEqual(ids(index.search('Tarrega', {source:'classclef',category:'0'})), []);
});

function appContext() {
  class Element {
    constructor() { this.children = []; this.attributes = {}; this.style = {}; this.dataset = {}; this.value = 'all'; }
    append(...nodes) { this.children.push(...nodes); }
    setAttribute(name, value) { this.attributes[name] = value; }
    addEventListener() {}
  }
  const nodes = new Map();
  const querySelector = selector => {
    if (!nodes.has(selector)) nodes.set(selector, new Element());
    return nodes.get(selector);
  };
  for (const [selector, values] of Object.entries({
    '#source-filter':['all','imslp','classclef'], '#family-filter':['all','pure','classclef'],
    '#kind-filter':['all','original','arrangement','unspecified'], '#category-filter':['all','0','classclef:tarrega'],
  })) querySelector(selector).options = values.map(value => ({value}));
  const urls = [];
  const context = vm.createContext({
    document: {querySelector, createElement: () => new Element()},
    window: {location: {search:'', pathname:'/guitar-atlas/', hash:'#catalog'}},
    history: {replaceState: (_state, _unused, url) => urls.push(url), pushState: (_state, _unused, url) => urls.push(url)},
    URLSearchParams, GuitarSearch:require(enginePath), console,
  });
  // Load the real DOM functions without network-driven startup.
  const app = fs.readFileSync(path.join(__dirname, '../public_site/assets/app.js'), 'utf8');
  vm.runInContext(app.replace(/\bstart\(\);\s*$/, ''), context);
  return {context, nodes, urls};
}

test('public and offline URL state preserve source and namespaced category filters', () => {
  const {context, nodes, urls} = appContext();
  context.window.location.search = '?source=classclef&kind=unspecified&category=classclef%3Atarrega&q=GPX';
  context.readUrlState();
  assert.equal(nodes.get('#source-filter').value, 'classclef');
  assert.equal(nodes.get('#category-filter').value, 'classclef:tarrega');
  assert.equal(nodes.get('#filter-drawer').open, true);
  context.writeUrlState();
  const params = new URL(urls.at(-1), 'https://example.com').searchParams;
  assert.equal(params.get('source'), 'classclef');
  assert.equal(params.get('category'), 'classclef:tarrega');
  let offlineQuery;
  context.window.GuitarCatalogAdapter = {readQuery: () => '?source=imslp&q=Sor', writeQuery: query => { offlineQuery = query; }};
  context.readUrlState();
  context.writeUrlState();
  assert.equal(new URLSearchParams(offlineQuery).get('source'), 'imslp');
  assert.equal(new URLSearchParams(offlineQuery).get('q'), 'Sor');
});

test('result cards render original labels, unknown kind and source-page links while keeping the offline hook', () => {
  const {context} = appContext();
  let decorated;
  context.window.GuitarCatalogAdapter = {decorateCard: (article, match) => { decorated = match.item.id; }};
  const match = multiSourceIndex().search('GPX').matches[0];
  const card = context.resultCard(match, 0);
  const descendants = node => [node, ...node.children.flatMap(descendants)];
  const all = descendants(card);
  assert.ok(all.some(node => node.textContent === 'Recuerdos de la Alhambra'));
  assert.ok(all.some(node => node.textContent === 'Francisco Tarrega'));
  assert.ok(all.some(node => node.textContent === '来源未标注'));
  assert.equal(all.find(node => node.className === 'source-link').href, 'https://www.classclef.com/francisco-tarrega/');
  assert.equal(decorated, 'classclef:1');
  const legacy = createIndex().search('Recuerdos').matches[0];
  legacy.item.imslp_url = 'https://imslp.org/wiki/Recuerdos';
  const legacyCard = context.resultCard(legacy, 1);
  assert.equal(descendants(legacyCard).find(node => node.className === 'source-link').href, legacy.item.imslp_url);
});

test('reference resources have a searchable label and distinct card label without changing score defaults', () => {
  const item = {...multiSourceData.works.at(-1), id:'classclef:glossary', title_en:'Glossary', resource_type:'reference'};
  const engine = require(enginePath);
  const index = engine.createIndex({...multiSourceData, works:[...multiSourceData.works, item]});
  assert.deepEqual(ids(index.search('参考资料')), ['classclef:glossary']);
  assert.deepEqual(ids(index.search('reference', {source:'classclef'})), ['classclef:glossary']);
  const suggestion = index.suggest('参考资料')[0];
  assert.equal(suggestion.resource_type, 'reference');
  assert.deepEqual(ids(index.search(suggestion.query)), ['classclef:glossary']);
  assert.equal(engine.resourceLabel(multiSourceData.works[0]), '');
  const {context} = appContext();
  const card = context.resultCard(index.search('参考资料').matches[0], 0);
  const header = card.children.find(node => node.className === 'result-header');
  assert.equal(header.children.find(node => node.className === 'result-kind').textContent, '参考资料');
});
