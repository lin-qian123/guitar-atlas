const test = require('node:test');
const assert = require('node:assert/strict');
const engine = require('../public_site/assets/search.js');
const fs = require('node:fs');
const vm = require('node:vm');

const data = {
  sources: [{id: 'musescore', name: 'MuseScore'}, {id: 'imslp', name: 'IMSLP'}],
  topics: [
    {id: 'solo', name_en: 'Guitar solo', name_zh: '吉他独奏'},
    {id: 'duo', name_en: 'Guitar duo', name_zh: '吉他二重奏'},
    {id: 'strings', name_en: 'Guitar and strings', name_zh: '吉他与弦乐'},
    {id: 'guitar_unspecified', name_en: 'Guitar, player count unspecified', name_zh: '吉他·人数未明'},
  ],
  categories: [
    {id: 0, source_id: 'musescore', name: 'Guitar', name_zh: '吉他', family: 'musescore', kind: 'unspecified'},
    {id: 1, source_id: 'imslp', name: 'For 2 guitars', name_zh: '吉他二重奏', family: 'pure', kind: 'original'},
  ],
  works: [
    {id: 'musescore:80344', source_id: 'musescore', title_en: 'Four Seasons - Inverno', composer_en: 'Antonio Vivaldi',
      category_ids: [0], topic_ids: ['strings'], topic_category_ids: {strings: [0]},
      details: {instrumentation: '2 guitars, violin and cello', instrumentation_zh: '两把吉他、小提琴、大提琴',
        source_instrumentation: 'Guitar and violin', instrumentation_review: '文件交叉核验，来源摘要遗漏大提琴。',
        guitar_player_count: '2', ensemble_player_count: '4'}},
    {id: 'musescore:1', source_id: 'musescore', title_en: 'Prelude', composer_en: 'Example composer',
      category_ids: [0], topic_ids: ['solo'], topic_category_ids: {solo: [0]},
      details: {instrumentation: 'Solo guitar', instrumentation_zh: '吉他独奏'}},
    {id: 'musescore:2', source_id: 'musescore', title_en: 'Guitar notation', composer_en: 'Example composer',
      category_ids: [0], topic_ids: ['guitar_unspecified'], topic_category_ids: {guitar_unspecified: [0]},
      details: {instrumentation: 'Guitar', instrumentation_zh: '吉他，演奏人数未明'}},
    {id: '42', source_id: 'imslp', title_en: 'Prelude', composer_en: 'Example composer',
      category_ids: [1], topic_ids: ['duo'], topic_category_ids: {duo: [1]}, details: {}},
  ],
};
const ids = response => response.matches.map(match => match.item.id);

test('file-reviewed Chinese instrumentation is searchable in the unified source category', () => {
  const index = engine.createIndex(data);
  assert.deepEqual(ids(index.search('大提琴', {source: 'musescore', category: '0'})), ['musescore:80344']);
  assert.deepEqual(ids(index.search('小提琴 大提琴', {topic: 'strings'})), ['musescore:80344']);
  assert.deepEqual(ids(index.search('violin cello', {source: 'musescore'})), ['musescore:80344']);
});

test('source instrumentation remains searchable after correcting the full ensemble', () => {
  const index = engine.createIndex(data);
  assert.deepEqual(ids(index.search('Guitar violin', {source: 'musescore'})), ['musescore:80344']);
  assert.deepEqual(ids(index.search('来源摘要遗漏', {source: 'musescore'})), ['musescore:80344']);
});

test('two guitars accompanied by strings do not enter the pure guitar duo topic', () => {
  const index = engine.createIndex(data);
  assert.deepEqual(ids(index.search('', {topic: 'duo'})), ['42']);
  assert.deepEqual(ids(index.search('', {topic: 'duo', source: 'musescore'})), []);
  assert.deepEqual(ids(index.search('', {topic: 'strings', category: '0'})), ['musescore:80344']);
});

test('verified solo and unresolved player count remain separate with shared native category', () => {
  const index = engine.createIndex(data);
  assert.deepEqual(ids(index.search('', {topic: 'solo', category: '0'})), ['musescore:1']);
  assert.deepEqual(ids(index.search('', {topic: 'guitar_unspecified', source: 'musescore'})), ['musescore:2']);
});

test('the actual file title is searchable while the source title and native record stay intact', () => {
  const row = {...data.works[0], id:'musescore:5989551', title_en:'60 Lessons for 2 Guitars, Op.168/59',
    details:{...data.works[0].details, file_title:'TWO ITALIAN MELODIES FOR AN ORCHESTRA / LA PALOMA',
      file_identity_note:'文件谱题与来源所列二重奏练习曲不一致。'}};
  const index = engine.createIndex({...data, works:[row]});
  assert.deepEqual(ids(index.search('La Paloma', {source:'musescore'})), ['musescore:5989551']);
  assert.deepEqual(ids(index.search('60 Lessons', {source:'musescore'})), ['musescore:5989551']);
  assert.deepEqual(ids(index.search('二重奏练习曲不一致', {source:'musescore'})), ['musescore:5989551']);
  assert.equal(row.title_en, '60 Lessons for 2 Guitars, Op.168/59');
});

test('complete original file-part labels remain searchable including instrument variants and TAB views', () => {
  const row = {...data.works[0], id:'musescore:100', title_en:'Chamber study',
    details:{...data.works[0].details, file_part_labels:'B♭ Clarinet; Alto Recorder; 12-string Guitar; Guitar [Tablature]'}};
  const index = engine.createIndex({...data,works:[row]});
  for (const query of ['B♭ Clarinet', 'Alto Recorder', '12-string Guitar', 'Tablature']) {
    assert.deepEqual(ids(index.search(query,{source:'musescore'})), ['musescore:100']);
  }
});

class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.style = {}; this.attributes = {}; this.textContent = ''; }
  append(...children) { this.children.push(...children); }
  setAttribute(key, value) { this.attributes[key] = value; }
  addEventListener() {}
  set innerHTML(value) { throw new Error('rendering metadata as HTML is unsafe'); }
}
const descendants = element => [element, ...element.children.flatMap(descendants)];
const escapeHTML = value => String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const serialize = node => `<${node.tag}>${escapeHTML(node.textContent)}${node.children.map(serialize).join('')}</${node.tag}>`;
function renderCard(details = {}, translation) {
  const context = {GuitarSearch:engine, window:{}, document:{querySelector:() => new Element('select'), createElement:tag => new Element(tag)}};
  const source = fs.readFileSync(require.resolve('../public_site/assets/app.js'), 'utf8').replace(/\nstart\(\);\s*$/, '');
  vm.runInNewContext(source, context);
  return context.resultCard({item:{...data.works[0], details, translation, source_url:'https://musescore.com/user/1/scores/80344'}, categories:[data.categories[0]]}, 0);
}

test('an explicit file identity note gets a visible compact warning with its full note in details only', () => {
  const note = '文件谱题为 LA PALOMA，与来源所列二重奏练习曲不一致。';
  const card = renderCard({file_title:'LA PALOMA', file_identity_note:note});
  const title = card.children.find(node => node.className === 'result-title');
  assert.ok(title.children.some(node => node.textContent === '文件题名与来源不一致'));
  assert.equal(descendants(card).filter(node => node.textContent.includes(note)).length, 1);
  assert.ok(descendants(card).some(node => node.textContent === '实际谱题：LA PALOMA'));
  assert.ok(descendants(card).some(node => node.textContent === `谱题与来源差异：${note}`));
});

test('a retained English title or actual file title alone does not invent an identity warning', () => {
  const card = renderCard({file_title:'Prelude'}, {title:{status:'retained', reason:'未找到可靠中文译名'}});
  const texts = descendants(card).map(node => node.textContent);
  assert.ok(texts.includes('保留原题'));
  assert.ok(!texts.includes('文件题名与来源不一致'));
});

test('file title and identity note are literal text and cannot create HTML elements', () => {
  const unsafe = '<img src=x onerror="alert(1)"><script>alert(2)</script>';
  const card = renderCard({file_title:unsafe, file_identity_note:unsafe});
  assert.ok(descendants(card).every(node => !['img', 'script'].includes(node.tag)));
  assert.ok(serialize(card).includes('&lt;img src=x onerror=&quot;alert(1)&quot;&gt;'));
  assert.ok(!serialize(card).includes('<img'));
});

test('file-part labels are folded details and performer counts are identified as written instrumentation', () => {
  const labels = 'B♭ Clarinet; 12-string Guitar; Guitar [Tablature]';
  const card = renderCard({file_part_labels:labels, guitar_player_count:'1', ensemble_player_count:'2'});
  const texts = descendants(card).map(node => node.textContent);
  assert.ok(texts.includes(`文件分部原标注（含记谱视图）：${labels}`));
  assert.ok(texts.includes('吉他人数（按谱面）：1'));
  assert.ok(texts.includes('总人数（按谱面）：2'));
  const title = card.children.find(node => node.className === 'result-title');
  assert.ok(!descendants(title).some(node => node.textContent.includes(labels)));
});
