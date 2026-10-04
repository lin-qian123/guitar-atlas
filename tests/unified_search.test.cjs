const test = require('node:test');
const assert = require('node:assert/strict');
const engine = require('../public_site/assets/search.js');

const data = {
  sources: [{id: 'imslp', name: 'IMSLP'}, {id: 'werner', name: 'Werner'}],
  topics: [
    {id: 'solo', name_en: 'Guitar solo', name_zh: '吉他独奏'},
    {id: 'woodwinds', name_en: 'Guitar and woodwinds', name_zh: '吉他与木管'},
    {id: 'guitar_unspecified', name_en: 'Guitar, player count unspecified', name_zh: '吉他·人数未明'},
  ],
  categories: [
    {id: 0, source_id: 'imslp', name: 'Original editions', name_zh: '原作目录', family: 'pure', kind: 'original'},
    {id: 1, source_id: 'werner', name: 'Teaching editions', name_zh: '教学目录', family: 'werner', kind: 'unspecified'},
    {id: 2, source_id: 'imslp', name: 'Chamber editions', name_zh: '室内乐目录', family: 'woodwinds', kind: 'arrangement'},
  ],
  works: [
    {id: '42', source_id: 'imslp', source_record_id: '42', title_en: 'Prelude', title_zh: '前奏曲',
      composer_en: 'Example composer', composer_zh: '', category_ids: [0, 2], formats: ['PDF'], resource_type: 'score',
      topic_ids: ['solo', 'woodwinds'], topic_category_ids: {solo: [0], woodwinds: [2]},
      details: {editor: 'First editor'}},
    {id: 'werner:42', source_id: 'werner', source_record_id: '42', title_en: 'Prelude', title_zh: '前奏曲',
      composer_en: 'Example composer', composer_zh: '', category_ids: [1], formats: [], resource_type: 'score',
      topic_ids: ['solo'], topic_category_ids: {solo: [1]},
      details: {editor: 'Bradford Werner', difficulty: 'Grade 7'}},
    {id: 'werner:43', source_id: 'werner', source_record_id: '43', title_en: 'Study', title_zh: '练习曲',
      composer_en: 'Another composer', composer_zh: '', category_ids: [1], formats: [], resource_type: 'score',
      topic_ids: ['guitar_unspecified'], topic_category_ids: {guitar_unspecified: [1]},
      details: {instrumentation: 'Guitar'}},
  ],
};

const createIndex = () => engine.createIndex(data);
const ids = response => response.matches.map(match => match.item.id);

test('work suggestions retain collection contents and explicit arrangement terms', () => {
  const item = structuredClone(data.works[1]);
  item.declared_kind = 'arrangement';
  item.contents = ['Sarabande'];
  const index = engine.createIndex({...data, works: [item]});
  const suggestions = index.suggest('Sarabande 改编').filter(s => s.kind === 'work');
  assert.equal(suggestions.length, 1);
  assert.ok(engine.normalize(suggestions[0].query).includes('sarabande'));
  assert.ok(suggestions[0].query.includes('改编'));
  assert.deepEqual(ids(index.search(suggestions[0].query)), ['werner:42']);
});

test('a unified solo topic finds distinct records across sources', () => {
  const index = createIndex();
  assert.deepEqual(new Set(ids(index.search('', {topic: 'solo'}))), new Set(['42', 'werner:42']));
  assert.deepEqual(ids(index.search('Prelude', {source: 'werner', topic: 'solo'})), ['werner:42']);
  assert.deepEqual(ids(index.search('Prelude', {source: 'imslp', topic: 'solo'})), ['42']);
  assert.deepEqual(index.search('', {source: 'imslp', topic: 'solo'}).matches[0].categories.map(c => c.id), [0]);
});

test('topic and original/arrangement filters must match the same category membership', () => {
  const index = createIndex();
  assert.deepEqual(ids(index.search('Prelude', {topic: 'solo', category: '2'})), []);
  assert.deepEqual(ids(index.search('Prelude', {topic: 'solo', kind: 'arrangement'})), []);
  const mixed = index.search('Prelude', {topic: 'woodwinds', category: '2', kind: 'arrangement'});
  assert.deepEqual(ids(mixed), ['42']);
  assert.deepEqual(mixed.matches[0].categories.map(c => c.id), [2]);
  assert.deepEqual(ids(index.search('woodwinds', {category: '0'})), []);
  assert.deepEqual(ids(index.search('woodwinds', {category: '2'})), ['42']);
});

test('topic counts are unique records and obey source and category filters', () => {
  const index = createIndex();
  const all = new Map(index.browseTopics().map(topic => [topic.id, topic]));
  assert.equal(all.get('solo').work_count, 2);
  assert.equal(all.get('solo').source_count, 2);
  assert.equal(all.get('woodwinds').work_count, 1);
  const chamber = index.browseTopics({category: '2'});
  assert.deepEqual(chamber.map(topic => topic.id), ['woodwinds']);
  assert.equal(chamber[0].work_count, 1);
  assert.deepEqual(index.browseTopics({source: 'werner'}).map(topic => topic.id), ['solo', 'guitar_unspecified']);
});

test('unspecified guitar player count never passes the solo topic filter', () => {
  const index = createIndex();
  assert.deepEqual(ids(index.search('', {topic: 'guitar_unspecified'})), ['werner:43']);
  assert.deepEqual(ids(index.search('Study', {topic: 'solo'})), []);
});

test('unknown score formats stay searchable without a PDF classification', () => {
  const index = createIndex();
  const match = index.search('Prelude', {source: 'werner'}).matches[0];
  assert.deepEqual(match.item.formats, []);
  assert.deepEqual(ids(index.search('PDF', {source: 'werner'})), []);
});

test('work suggestions retain editor and difficulty query terms', () => {
  const index = createIndex();
  const filters = {topic: 'solo'};
  const suggestions = index.suggest('Bradford 7', filters).filter(s => s.kind === 'work');
  assert.equal(suggestions.length, 1);
  for (const suggestion of suggestions) {
    const query = engine.normalize(suggestion.query);
    assert.ok(query.includes('bradford'));
    assert.ok(query.split(' ').includes('7'));
    assert.deepEqual(ids(index.search(suggestion.query, filters)), ['werner:42']);
  }
});

test('work suggestions retain scoped topic terms and replay the same edition', () => {
  const index = createIndex();
  const filters = {category: '2', kind: 'arrangement'};
  const suggestions = index.suggest('Prelude woodwinds', filters).filter(s => s.kind === 'work');
  assert.equal(suggestions.length, 1);
  assert.ok(engine.normalize(suggestions[0].query).includes('woodwinds'));
  assert.deepEqual(ids(index.search(suggestions[0].query, filters)), ['42']);
  assert.deepEqual(ids(index.search(suggestions[0].query, {category: '0'})), []);
});

test('topic suggestions do not drop a topic term shared with another source', () => {
  const index = createIndex();
  const suggestions = index.suggest('Prelude 独奏', {topic: 'solo'}).filter(s => s.kind === 'work');
  assert.ok(suggestions.length > 0);
  for (const suggestion of suggestions) {
    assert.ok(engine.normalize(suggestion.query).includes('独奏'));
    assert.deepEqual(new Set(ids(index.search(suggestion.query, {topic: 'solo'}))), new Set(['42', 'werner:42']));
  }
});

function declarationFixture() {
  const fixture = structuredClone(data);
  fixture.categories.push({id: 3, source_id: 'werner', name: 'Chamber teaching editions', name_zh: '室内乐教学目录', family: 'werner', kind: 'unspecified'});
  fixture.works = [
    {...fixture.works[1], id: 'werner:44', source_record_id: '44', title_en: 'Arranged Prelude',
      declared_kind: 'arrangement', details: {original_arrangement_status: 'arrangement'}},
    {...fixture.works[1], id: 'werner:45', source_record_id: '45', title_en: 'Edited Prelude',
      declared_kind: 'unspecified', details: {editor: 'Bradford Werner', source_roles: 'editor'}},
    {...fixture.works[1], id: 'werner:46', source_record_id: '46', title_en: 'Chamber Prelude',
      category_ids: [1, 3], declared_kind: 'arrangement', topic_ids: ['solo', 'woodwinds'],
      topic_category_ids: {solo: [1], woodwinds: [3]}, details: {original_arrangement_status: 'arrangement'}},
    {...fixture.works[0], id: '43', source_record_id: '43', title_en: 'Original Prelude',
      category_ids: [0], declared_kind: 'arrangement', topic_ids: ['solo'], topic_category_ids: {solo: [0]}},
  ];
  return fixture;
}

test('an explicit record arrangement declaration enables filtering in an unspecified source category', () => {
  const fixture = declarationFixture();
  const index = engine.createIndex(fixture);
  const response = index.search('Arranged', {source: 'werner', kind: 'arrangement'});
  assert.deepEqual(ids(response), ['werner:44']);
  assert.deepEqual(response.matches[0].categories.map(category => category.id), [1]);
  assert.equal(response.matches[0].categories[0].kind, 'unspecified');
  assert.equal(response.matches[0].item.declared_kind, 'arrangement');
  assert.deepEqual(ids(index.search('Arranged', {source: 'werner', kind: 'original'})), []);
});

test('an editor attribution alone never turns an unspecified record into an arrangement', () => {
  const index = engine.createIndex(declarationFixture());
  assert.deepEqual(ids(index.search('Edited', {source: 'werner', kind: 'arrangement'})), []);
  assert.deepEqual(ids(index.search('Edited', {source: 'werner', kind: 'original'})), []);
  assert.deepEqual(ids(index.search('Edited', {source: 'werner', kind: 'unspecified'})), ['werner:45']);
});

test('a native original category retains precedence over a record arrangement declaration', () => {
  const fixture = declarationFixture();
  const before = structuredClone(fixture);
  const index = engine.createIndex(fixture);
  const response = index.search('Original', {source: 'imslp', kind: 'original'});
  assert.deepEqual(ids(response), ['43']);
  assert.equal(response.matches[0].categories[0].kind, 'original');
  assert.equal(response.matches[0].item.declared_kind, 'arrangement');
  assert.deepEqual(ids(index.search('Original', {source: 'imslp', kind: 'arrangement'})), []);
  index.browse({kind: 'arrangement'});
  assert.deepEqual(fixture, before);
});

test('record declarations still require topic and category filters to match one membership', () => {
  const index = engine.createIndex(declarationFixture());
  assert.deepEqual(ids(index.search('Chamber', {kind: 'arrangement', topic: 'solo', category: '3'})), []);
  const response = index.search('Chamber', {kind: 'arrangement', topic: 'woodwinds', category: '3'});
  assert.deepEqual(ids(response), ['werner:46']);
  assert.deepEqual(response.matches[0].categories.map(category => category.id), [3]);
  assert.deepEqual(ids(index.search('Chamber', {kind: 'unspecified', category: '3'})), []);
});

test('directory browsing counts record declarations once and reports filtered membership counts', () => {
  const index = engine.createIndex(declarationFixture());
  const arranged = index.browse({source: 'werner', kind: 'arrangement'});
  assert.deepEqual(new Set(arranged.categories.map(category => category.id)), new Set([1, 3]));
  assert.equal(arranged.workCount, 2);
  assert.equal(arranged.categories.find(category => category.id === 1).work_count, 2);
  assert.equal(arranged.categories.find(category => category.id === 3).work_count, 1);
  assert.ok(arranged.categories.every(category => category.kind === 'unspecified'));
  const unknown = index.browse({source: 'werner', kind: 'unspecified'});
  assert.equal(unknown.workCount, 1);
  assert.equal(unknown.categories.find(category => category.id === 1).work_count, 1);
  assert.equal(unknown.categories.find(category => category.id === 3).work_count, 0);
  assert.equal(index.browse({source: 'werner', kind: 'original'}).workCount, 0);
  assert.equal(index.browse({source: 'imslp', kind: 'original'}).workCount, 1);
});

function checkedComposerFixture() {
  const fixture = structuredClone(data);
  fixture.sources.push({id: 'cglib', name: 'Classical Guitar Library'});
  fixture.categories.push({id: 3, source_id: 'cglib', name: 'Tarrega composer directory', name_zh: '泰雷加作品目录', family: 'cglib', kind: 'unspecified'});
  const work = (id, source_id, source_record_id, composer_en, status, category) => ({
    id, source_id, source_record_id, title_en: 'Lagrima', title_zh: '泪', composer_en,
    composer_zh: '弗朗西斯科·泰雷加', translation: {composer: {status}}, category_ids: [category],
    resource_type: 'score', formats: [], topic_ids: ['solo'], topic_category_ids: {solo: [category]},
  });
  fixture.works = [
    work('33377', 'imslp', '33377', 'Tárrega, Francisco', 'reviewed', 0),
    work('cglib:10', 'cglib', '10', 'Tarrega. Francisco', 'reference', 3),
    work('cglib:11', 'cglib', '11', 'Francisco de Asís Tárrega', 'reference', 3),
    work('cglib:12', 'cglib', '12', 'Tarrega. Carlos', 'machine', 3),
  ];
  return fixture;
}

test('checked composer aliases support full-name punctuation and order across sources without changing native identities', () => {
  const fixture = checkedComposerFixture();
  const before = structuredClone(fixture);
  const index = engine.createIndex(fixture, {composers: {'Tárrega, Francisco': ['塔瑞加']}});
  const response = index.search('塔瑞加');
  assert.deepEqual(new Set(ids(response)), new Set(['33377', 'cglib:10', 'cglib:11']));
  assert.ok(response.matches.every(match => match.matchType === 'alias'));
  assert.deepEqual(new Set(ids(index.search('塔瑞加', {source: 'cglib'}))), new Set(['cglib:10', 'cglib:11']));
  assert.ok(ids(index.search('Francisco Tarrega', {source: 'cglib'})).includes('cglib:10'));
  const dotted = response.matches.find(match => match.item.id === 'cglib:10').item;
  assert.equal(dotted.composer_en, 'Tarrega. Francisco');
  assert.equal(dotted.source_record_id, '10');
  assert.deepEqual(fixture, before);
});

test('composer suggestions preserve the source full name and machine Chinese names do not inherit checked aliases', () => {
  const index = engine.createIndex(checkedComposerFixture(), {composers: {'Tárrega, Francisco': ['塔瑞加']}});
  const suggestions = index.suggest('塔瑞加', {source: 'cglib'});
  assert.ok(suggestions.some(suggestion => suggestion.kind === 'composer' && suggestion.query === 'Tarrega. Francisco'));
  assert.deepEqual(ids(index.search('塔瑞加 Carlos', {source: 'cglib'})), []);
  assert.deepEqual(ids(index.search('Carlos', {source: 'cglib'})), ['cglib:12']);
});
