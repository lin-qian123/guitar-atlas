const test = require('node:test');
const assert = require('node:assert/strict');
const search = require('../public_site/assets/search.js');

const categories = [{id:0, name:'Native library', name_zh:'来源资料', source_id:'dga', family:'dga', kind:'unspecified'}];
const item = (id, extra={}) => ({id, source_id:'dga', source_name:'Archive', title_en:'Title / by Artist; ISBN 1234567', title_zh:'《题名／作者／ISBN1234567》', composer_en:'Artist, Person', composer_zh:'', category_ids:[0], ...extra});
const ids = result => result.matches.map(match => match.item.id);

test('machine drafts are searchable but the clean original is the primary display title', () => {
  const draft = item('draft', {display_title_en:'Title', display_title_zh:'《题名》', translation:{title:{status:'machine'}}});
  assert.equal(search.titleLabel(draft), 'Title');
  const index = search.createIndex({categories, works:[draft]});
  assert.deepEqual(ids(index.search('题名')), ['draft']);
  assert.deepEqual(ids(index.search('ISBN 1234567')), ['draft']);
});

test('reviewed/reference translations and legacy snapshots retain dual-language display', () => {
  const base = item('reviewed', {display_title_en:'Title', display_title_zh:'《题名》', translation:{title:{status:'reference'}}});
  assert.equal(search.titleLabel(base), '题名');
  assert.equal(search.titleLabel(item('legacy', {title_zh:'《旧译名》'})), '旧译名');
  assert.equal(search.titleLabel(item('untranslated', {display_title_en:'Title', display_title_zh:''})), 'Title');
});

test('source/translation titles, shelfmarks, and annotations remain searchable after presentation separation', () => {
  const separated = item('separated', {display_title_en:'Title', display_title_zh:'《题名》',
    details:{source_title_transcription:'Title / by Artist; ISBN 1234567', source_call:'I-Mt 55', source_type:'Manuscript copy'}});
  const before = structuredClone(separated);
  const index = search.createIndex({categories, works:[separated]});
  for (const query of ['Artist', 'ISBN 1234567', 'I-Mt 55', 'Manuscript copy']) {
    assert.deepEqual(ids(index.search(query)), ['separated'], query);
  }
  assert.deepEqual(separated, before, 'Search may not rewrite source identities or raw guarded fields');
});

test('an explicit performer name is not treated as the strongest composer match', () => {
  const works = [
    item('performer', {composer_en:'Sor, Fernando', details:{attribution_role:'performer'}}),
    item('composer', {composer_en:'Sor, Fernando', title_en:'Different piece', title_zh:'', details:{attribution_role:'composer'}}),
  ];
  const index = search.createIndex({categories, works}, {}, {works:{performer:100}});
  assert.deepEqual(ids(index.search('Sor')), ['composer', 'performer']);
});

test('display name cleanup and explicit carrier labels keep full source fields intact', () => {
  const work = item('recording', {composer_en:'Person <1800-1870>', composer_zh:'Person <1800-1870>',
    display_composer_en:'Person', display_composer_zh:'Person', details:{material_type:'recording'}});
  assert.equal(search.composerLabel(work), 'Person');
  assert.equal(search.resourceLabel(work), '录音资料');
  assert.equal(search.resourceLabel(item('journal', {details:{material_type:'journal'}})), '期刊资料');
  assert.equal(search.resourceLabel(item('source-mark', {details:{source_type:'sound recording'}})), '录音资料');
  assert.equal(search.resourceLabel(item('unknown', {title_en:'A song about sound recording'})), '');
});
