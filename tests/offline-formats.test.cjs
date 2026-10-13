const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

class Element {
  constructor(tag, className = '', text = '') { this.tag = tag; this.className = className; this.text = text; this.children = []; this.attributes = {}; }
  append(...children) { this.children.push(...children); }
  setAttribute(key, value) { this.attributes[key] = value; }
  querySelector() { return null; }
  insertBefore(child) { this.append(child); }
}
const descendants = node => [node, ...node.children.flatMap(descendants)];
function render(editions, categories = [{id:1, name:'Guitar', name_zh:'吉他'}], item = {}) {
  const context = {window:{}, TextEncoder, GuitarSearch:require('../public_site/assets/search.js'), makeElement:(...args) => new Element(...args)};
  vm.runInNewContext(fs.readFileSync(require.resolve('../scripts/assets/offline-catalog.js'), 'utf8'), context);
  const article = new Element('article');
  context.window.GuitarCatalogAdapter.decorateCard(article, {categories, item:{id:'musescore:100', source_record_id:'100', title_en:'Guitar Study', ...item, local_editions:editions}});
  return descendants(article);
}
const file = (format = 'PDF', number = 1) => ({href:`sources/musescore/objects/${number}.${format === 'PDF' ? 'pdf' : format === 'MUSICXML' ? 'mxl' : 'mid'}`, label:`Score ${number}`, ...(format === 'PDF' ? {} : {format})});

test('offline links label each format and offer editable/playback file downloads', () => {
  const nodes = render([{category_id:1, unavailable_count:0, files:[file(), file('MUSICXML'), file('MIDI')]}]);
  assert.ok(nodes.some(node => node.tag === 'h4' && node.text === '本地乐谱'));
  const links = nodes.filter(node => node.tag === 'a');
  assert.deepEqual(links.map(node => node.attributes['aria-label']), ['PDF：Score 1', '下载 MXL：Score 1', '下载 MIDI：Score 1']);
  assert.equal(links[0].target, '_blank');
  assert.equal(links[1].attributes.download, 'Guitar Study - 100.mxl');
  assert.equal(links[2].attributes.download, 'Guitar Study - 100.mid');
  assert.deepEqual(nodes.filter(node => node.className === 'local-format').map(node => node.text), ['PDF', 'MXL', 'MIDI']);
});

test('local files follow the active matched category membership', () => {
  const nodes = render([
    {category_id:1, unavailable_count:0, files:[file('MUSICXML')]},
    {category_id:2, unavailable_count:0, files:[file('MIDI', 2)]},
  ]);
  assert.deepEqual(nodes.filter(node => node.tag === 'a').map(node => node.href), ['sources/musescore/objects/1.mxl']);
});

test('new formats remain directly reachable when a work has many PDF parts', () => {
  const nodes = render([{category_id:1, unavailable_count:0, files:[...Array.from({length:8}, (_, i) => file('PDF', i + 1)), file('MUSICXML'), file('MIDI')]}]);
  const hidden = nodes.filter(node => node.tag === 'details').flatMap(descendants).filter(node => node.tag === 'a');
  assert.equal(hidden.length, 4);
  assert.ok(hidden.every(node => node.href.endsWith('.pdf')));
});

test('the established PDF entry appears first regardless of native asset order', () => {
  const nodes = render([{category_id:1, unavailable_count:0, files:[file('MIDI'), file('MUSICXML'), file()]}]);
  assert.deepEqual(nodes.filter(node => node.className === 'local-format').map(node => node.text), ['PDF', 'MXL', 'MIDI']);
});

test('missing extra formats are separate from PDF failures and do not invent links', () => {
  const nodes = render([{category_id:1, unavailable_count:0, files:[file()], format_unavailable:{MUSICXML:1, MIDI:2}}]);
  assert.equal(nodes.filter(node => node.tag === 'a').length, 1);
  const warnings = nodes.filter(node => node.className === 'local-pending').map(node => node.text);
  assert.deepEqual(warnings, ['1 份 MXL 文件未就绪，可查看来源原页。', '2 份 MIDI 文件未就绪，可查看来源原页。']);
});

test('download names use reviewed display titles and native IDs without changing paths', () => {
  const nodes = render([{category_id:1, unavailable_count:0, files:[file('MUSICXML'), file('MIDI')]}], undefined,
    {display_title_en:'Recuerdos de la Alhambra', display_title_zh:'《阿尔罕布拉宫的回忆》', translation:{title:{status:'reference'}}});
  const links = nodes.filter(node => node.tag === 'a');
  assert.deepEqual(links.map(node => node.attributes.download), ['阿尔罕布拉宫的回忆 - 100.mxl', '阿尔罕布拉宫的回忆 - 100.mid']);
  assert.deepEqual(links.map(node => node.href), ['sources/musescore/objects/1.mxl', 'sources/musescore/objects/1.mid']);
});

test('download names strip path/control characters and stay within safe name limits', () => {
  const nodes = render([{category_id:1, unavailable_count:0, files:[file('MUSICXML')]}], undefined,
    {title_en:'../A:<B>?/\\|*\u0000\u202e' + '🎸作品'.repeat(90), source_record_id:'123456789'});
  const name = nodes.find(node => node.tag === 'a').attributes.download;
  assert.ok(!/[<>:"/\\|?*\u0000\u202e]/.test(name));
  assert.ok(!name.startsWith('.'));
  assert.ok(Array.from(name).length <= 100);
  assert.ok(new TextEncoder().encode(name).length <= 240);
  assert.ok(name.endsWith(' - 123456789.mxl'));
});
