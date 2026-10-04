"use strict";

// Shared by the browser and Node regression tests. No network or DOM access.
const GuitarSearch = (() => {
  // Search folding only: source names and reviewed display titles stay intact.
  // Deliberately limited to common music/name characters, not a translation engine.
  const variants = Object.fromEntries([
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
  ].map(pair => [...pair]));
  const variantPattern = new RegExp(`[${Object.keys(variants).join('')}]`, 'gu');

  function normalize(value) {
    return String(value || '').normalize("NFKD").replace(/\p{Diacritic}/gu, '')
      .toLowerCase().replace(variantPattern, char => variants[char])
      .replace(/[æœøłß]/g, char => ({æ:'ae', œ:'oe', ø:'o', ł:'l', ß:'ss'})[char])
      .replace(/([\p{L}])(\d)/gu, '$1 $2').replace(/(\d)([\p{L}])/gu, '$1 $2')
      .replace(/[^\p{L}\p{N}]+/gu, ' ').trim().replace(/\s+/g, ' ');
  }

  function fieldSet(values) {
    return normalizedFieldSet(values.map(normalize).filter(Boolean));
  }

  function normalizedFieldSet(fields) {
    fields = [...new Set(fields)];
    const blob = fields.join(' ');
    const tokens = new Set(blob.match(/[a-z]+|\p{Script=Han}+|\d+/gu) || []);
    return {fields, blob, tokens};
  }

  function contains(fields, term) {
    if (fields.groups) return fields.groups.some(group => contains(group, term));
    // Op.2 must not accidentally match Op.27 or a fragment of a work ID.
    return /^\d+$/.test(term) ? fields.tokens.has(term) : fields.blob.includes(term);
  }

  function termStrength(fields, term, costs) {
    if (fields.groups) return Math.min(...fields.groups.map(group => termStrength(group, term, costs)));
    if (fields.fields.includes(term)) return costs[0];
    if (fields.tokens.has(term)) return costs[1];
    if (/^\d+$/.test(term)) return Infinity;
    for (const token of fields.tokens) if (token.startsWith(term)) return costs[2];
    return fields.blob.includes(term) ? costs[3] : Infinity;
  }

  function hasToken(fields, token) {
    return fields.groups ? fields.groups.some(group => hasToken(group, token)) : fields.tokens.has(token);
  }

  function* tokensOf(fields) {
    if (fields.groups) for (const group of fields.groups) yield* tokensOf(group);
    else yield* fields.tokens;
  }

  function fieldContainsPhrase(fields, phrase) {
    return fields.groups ? fields.groups.some(group => fieldContainsPhrase(group, phrase))
      : fields.fields.some(field => ` ${field} `.includes(phrase));
  }

  function relevance(scope, query, terms) {
    // A surname bounded by a name separator (·, comma or space) is stronger
    // than characters embedded in a different name. Each query term is kept.
    let score = 0;
    for (const term of terms) score += Math.min(
      termStrength(scope.composer, term, [0, 1, 2, 6]),
      termStrength(scope.title, term, [2, 3, 4, 7]),
      termStrength(scope.metadata, term, [8, 9, 10, 11]),
    );
    if (scope.composer.fields.includes(query)) score -= 0.75;
    else if (scope.title.fields.includes(query)) score -= 0.5;
    return score;
  }

  function tolerance(term) {
    if (/^[a-z]{4,40}$/.test(term)) return term.length >= 8 ? 2 : 1;
    if (/^\p{Script=Han}{3,24}$/u.test(term)) return term.length >= 7 ? 2 : 1;
    return 0;
  }

  // Optimal-string-alignment distance, including adjacent transpositions.
  // Chinese titles are unsegmented, so compare against substrings of a Han run.
  function distance(query, word, limit, substring) {
    if (!substring && Math.abs(query.length - word.length) > limit) return limit + 1;
    let previous = Array.from({length: word.length + 1}, (_, j) => substring ? 0 : j);
    let beforePrevious;
    for (let i = 1; i <= query.length; i++) {
      const row = [i];
      let minimum = i;
      for (let j = 1; j <= word.length; j++) {
        row[j] = Math.min(previous[j] + 1, row[j - 1] + 1, previous[j - 1] + (query[i - 1] !== word[j - 1]));
        if (i > 1 && j > 1 && query[i - 1] === word[j - 2] && query[i - 2] === word[j - 1]) {
          row[j] = Math.min(row[j], beforePrevious[j - 2] + 1);
        }
        minimum = Math.min(minimum, row[j]);
      }
      if (minimum > limit) return limit + 1;
      beforePrevious = previous;
      previous = row;
    }
    return substring ? Math.min(...previous) : previous[word.length];
  }

  function tokenCost(term, token, limit) {
    const han = /^\p{Script=Han}+$/u.test(term);
    if (han !== /^\p{Script=Han}+$/u.test(token)) return limit + 1;
    if (!han && Math.abs(term.length - token.length) > limit) return limit + 1;
    if (han && token.length < term.length - limit) return limit + 1;
    // Cheap rejection before allocating edit-distance rows.
    let absent = 0;
    for (const char of term) if (!token.includes(char)) absent++;
    if (absent > limit) return limit + 1;
    return distance(term, token, limit, han);
  }

  function passes(category, filters, item = null) {
    const kind = category.kind === 'unspecified' && item?.declared_kind && item.declared_kind !== 'unspecified' ? item.declared_kind : category.kind;
    return (!filters.source || filters.source === 'all' || sourceId(category) === filters.source)
      && (!filters.family || filters.family === 'all' || category.family === filters.family)
      && (!filters.kind || filters.kind === 'all' || kind === filters.kind)
      && (filters.category === undefined || filters.category === 'all' || String(category.id) === String(filters.category));
  }

  function catalogView(input, filters = {}) {
    return !normalize(input) && (filters.category === undefined || filters.category === 'all')
      && (filters.topic === undefined || filters.topic === 'all') ? 'categories' : 'works';
  }

  function sourceId(item) { return item.source_id || 'imslp'; }
  function titleLabel(item) {
    const translated = Object.prototype.hasOwnProperty.call(item, 'display_title_zh') ? item.display_title_zh : item.title_zh;
    if (item.translation?.title?.status === 'machine') return item.display_title_en || item.title_en || '';
    return (translated || item.display_title_en || item.title_en || '').replace(/^《|》$/g, '');
  }
  function composerLabel(item) {
    const translated = Object.prototype.hasOwnProperty.call(item, 'display_composer_zh') ? item.display_composer_zh : item.composer_zh;
    return translated || item.display_composer_en || item.composer_en || '作者未标注';
  }
  function kindLabel(kind) { return ({original:'原作', arrangement:'改编'})[kind] || '来源未标注'; }
  function resourceLabel(item, details = item.details || {}) {
    return ({recording:'录音资料', journal:'期刊资料', reference_text:'文字资料'})[details.material_type]
      || (String(details.source_type || '').toLowerCase() === 'sound recording' ? '录音资料' : '')
      || (item.resource_type === 'reference' ? '参考资料' : '');
  }

  // Only an exact, accent-folded full name (with comma order normalized) shares
  // curated aliases across sources. The original attribution is never rewritten.
  function composerKey(name) {
    const parts = String(name || '').split(/,|\.(?=\s+[A-Z])/);
    return normalize(parts.length === 2 ? `${parts[1]} ${parts[0]}` : name);
  }

  function createIndex(data, aliases = {}, ranking = {}) {
    const byCategory = new Map(data.categories.map(category => [String(category.id), category]));
    const byTopic = new Map((data.topics || []).map(topic => [topic.id, topic]));
    const sources = new Map((Array.isArray(data.sources) ? data.sources : []).map(source => [source.id, source.name]));
    const nameKeys = new Map();
    const nameKey = name => {
      if (!nameKeys.has(name)) nameKeys.set(name, composerKey(name));
      return nameKeys.get(name);
    };
    const aliasesByName = new Map();
    function addComposerAliases(name, values) {
      const key = nameKey(name);
      if (!key) return;
      if (!aliasesByName.has(key)) aliasesByName.set(key, new Set());
      for (const value of values) if (typeof value === 'string' && value.trim()) aliasesByName.get(key).add(value);
    }
    for (const [name, values] of Object.entries(aliases.composers || {})) addComposerAliases(name, values);
    for (const item of data.works) addComposerAliases(item.composer_en, [item.composer_zh]);
    const aliasesByCheckedChinese = new Map();
    for (const item of data.works) {
      if (!item.composer_zh || !['reviewed', 'reference'].includes(item.translation?.composer?.status)) continue;
      if (!aliasesByCheckedChinese.has(item.composer_zh)) aliasesByCheckedChinese.set(item.composer_zh, new Set());
      for (const value of aliasesByName.get(nameKey(item.composer_en)) || []) aliasesByCheckedChinese.get(item.composer_zh).add(value);
    }
    const numericWeight = value => typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : 0;
    const composerWeights = new Map();
    for (const [name, weight] of Object.entries(ranking.composers || {})) {
      const key = nameKey(name);
      if (key) composerWeights.set(key, Math.max(composerWeights.get(key) || 0, numericWeight(weight)));
    }
    // Reused category/name fields are folded once. Full score metadata and the
    // fuzzy vocabulary stay unbuilt during the common empty-query browse path.
    const categoryBase = new Map();
    const categoryFields = category => {
      if (!categoryBase.has(category.id)) categoryBase.set(category.id,
        fieldSet([category.name, category.name_zh, sourceId(category), sources.get(sourceId(category))]));
      return categoryBase.get(category.id);
    };
    const topicBase = new Map();
    const topicFields = id => {
      if (!topicBase.has(id)) topicBase.set(id, fieldSet([byTopic.get(id)?.name_zh, byTopic.get(id)?.name_en]));
      return topicBase.get(id);
    };
    const kindFields = new Map(['original', 'arrangement', 'unspecified'].map(kind => [kind, fieldSet([kindLabel(kind)])]));
    const composerProfiles = new Map();
    const composers = new Map();
    const documents = data.works.map(item => {
      const categories = item.category_ids.map(id => byCategory.get(String(id))).filter(Boolean);
      const checkedChinese = ['reviewed', 'reference'].includes(item.translation?.composer?.status) ? item.composer_zh : '';
      const composerIdentity = nameKey(item.composer_en);
      // A lazy metadata getter must not run during category-only startup.
      // JSON projections expose this small role scalar as a plain own value.
      const role = Object.getOwnPropertyDescriptor(item, 'details')?.value?.attribution_role;
      const nonComposerRole = ['performer', 'editor', 'transcriber', 'arranger', 'compiler', 'author', 'unverified_name'].includes(role);
      const profileKey = `${composerIdentity}\0${item.composer_zh || ''}\0${checkedChinese}\0${nonComposerRole}`;
      if (!composerProfiles.has(profileKey)) composerProfiles.set(profileKey, () => {
        const composerAliases = [...(aliasesByName.get(composerIdentity) || []),
          ...(checkedChinese ? aliasesByCheckedChinese.get(checkedChinese) || [] : [])];
        const sourceComposer = fieldSet(nonComposerRole ? [] : [item.display_composer_en || item.composer_en, item.display_composer_zh || item.composer_zh]);
        // Unicode calls the Chinese name separator · a diacritic; the generic
        // accent folder removes it. Preserve its boundary in a ranking-only
        // projection while retaining the existing full-name search folding.
        const boundaryNames = [item.composer_en, item.composer_zh, ...composerAliases]
          .map(name => typeof name === 'string' ? name.replace(/[·・‧]/g, ' ') : '');
        const composer = normalizedFieldSet([...sourceComposer.fields,
          ...fieldSet(nonComposerRole ? [] : [composerIdentity, ...composerAliases, ...boundaryNames]).fields]);
        return {sourceComposer, composer};
      });
      const composerProfile = () => {
        let profile = composerProfiles.get(profileKey);
        if (typeof profile === 'function') {
          profile = profile();
          composerProfiles.set(profileKey, profile);
        }
        return profile;
      };
      if (!composers.has(item.composer_en)) composers.set(item.composer_en, {
        get fields() { return composerProfile().composer; },
        label: composerLabel(item), detail: item.composer_en, query: item.composer_en, kind: 'composer',
      });
      let title;
      let sourceTitle;
      let primaryMetadata;
      let fullScope;
      let previousScope;
      let previousScopeKey;
      const weight = (composerWeights.get(composerIdentity) || 0) + numericWeight(ranking.works?.[item.id]);
      function scoped(eligible) {
        if (eligible.length === categories.length && fullScope) return fullScope;
        const scopeKey = eligible.map(category => category.id).join('\0');
        if (scopeKey === previousScopeKey) return previousScope;
        const profile = composerProfile();
        if (!sourceTitle) sourceTitle = fieldSet([item.display_title_en || item.title_en, item.translation?.title?.status === 'machine' ? '' : (Object.prototype.hasOwnProperty.call(item, 'display_title_zh') ? item.display_title_zh : item.title_zh)]);
        if (!title) {
          const workAliases = [...(aliases.works?.[item.id] || []), ...(item.title_aliases || [])];
          title = workAliases.length ? normalizedFieldSet([...sourceTitle.fields, ...fieldSet(workAliases).fields]) : sourceTitle;
        }
        if (!primaryMetadata) {
          const details = item.details || {};
          const originalTitles = [
            item.display_title_en && item.display_title_en !== item.title_en ? item.title_en : '',
            item.translation?.title?.status === 'machine' || (Object.prototype.hasOwnProperty.call(item, 'display_title_zh') && item.display_title_zh !== item.title_zh) ? item.title_zh : '',
          ];
          const originalAttribution = nonComposerRole || item.display_composer_en ? [item.composer_en, item.composer_zh] : [];
          primaryMetadata = fieldSet([item.id, sourceId(item), item.source_name || sources.get(sourceId(item)), ...originalTitles, ...originalAttribution,
            ...(item.formats || []), resourceLabel(item, details), item.resource_type, ...Object.values(details),
            ...(item.contents || []), item.declared_kind && item.declared_kind !== 'unspecified' ? kindLabel(item.declared_kind) : '']);
        }
        const scopedCategories = [...eligible.flatMap(category => [categoryFields(category),
          kindFields.get(category.kind === 'unspecified' && item.declared_kind !== 'unspecified' && item.declared_kind ? item.declared_kind : category.kind)
            || kindFields.get('unspecified')]),
          ...(item.topic_ids || []).filter(topic => !item.topic_category_ids || item.topic_category_ids[topic]?.some(id => eligible.some(category => category.id === id)))
            .flatMap(topicFields)];
        const metadata = {groups:[primaryMetadata, ...scopedCategories]};
        const source = {groups:[sourceTitle, profile.sourceComposer, metadata]};
        const expanded = {groups:[title, profile.composer, metadata]};
        previousScopeKey = scopeKey;
        previousScope = {source, expanded, title, composer:profile.composer, metadata};
        if (eligible.length === categories.length) fullScope = previousScope;
        return previousScope;
      }
      return {item, categories, weight, scoped, sortComposer:String(item.composer_en || ''), sortTitle:String(item.title_en || ''), sortId:String(item.id)};
    });
    let vocabulary;
    function fuzzyVocabulary() {
      if (vocabulary) return vocabulary;
      vocabulary = new Map();
      documents.forEach((doc, index) => {
        for (const token of new Set(tokensOf(doc.scoped(doc.categories).expanded))) {
          if (!vocabulary.has(token)) vocabulary.set(token, []);
          vocabulary.get(token).push(index);
        }
      });
      return vocabulary;
    }
    let lastKey;
    let lastResponse;
    const compareMatches = (a, b) => a.score - b.score || b.doc.weight - a.doc.weight
      || a.doc.sortComposer.localeCompare(b.doc.sortComposer) || a.doc.sortTitle.localeCompare(b.doc.sortTitle)
      || a.doc.sortId.localeCompare(b.doc.sortId);

    function search(input, filters = {}) {
      const query = normalize(input);
      const key = JSON.stringify([query, filters.source, filters.family, filters.kind, filters.category, filters.topic]);
      if (key === lastKey) return lastResponse;
      const terms = query.split(' ').filter(Boolean);
      const numericPhrases = terms.flatMap((term, index) => /^(?:op|opus|no|nr)$/.test(term) && /^\d+$/.test(terms[index + 1] || '')
        ? [` ${term} ${terms[index + 1]} `] : []);
      const numericPhrasesMatch = fields => numericPhrases.every(phrase => fieldContainsPhrase(fields, phrase));
      const eligible = documents.map(doc => doc.categories.filter(category => passes(category, filters, doc.item)
        && (!filters.topic || filters.topic === 'all' || (doc.item.topic_ids || []).includes(filters.topic)
          && (!doc.item.topic_category_ids || doc.item.topic_category_ids[filters.topic]?.includes(category.id)))));
      const scoped = query ? documents.map((doc, index) => eligible[index].length ? doc.scoped(eligible[index]) : null) : null;
      let matches = [];
      documents.forEach((doc, index) => {
        if (!eligible[index].length) return;
        if (!query) {
          matches.push({item:doc.item, categories:eligible[index], score:0, matchType:'exact', doc});
          return;
        }
        const direct = terms.every(term => contains(scoped[index].source, term)) && numericPhrasesMatch(scoped[index].source);
        const expanded = terms.every(term => contains(scoped[index].expanded, term)) && numericPhrasesMatch(scoped[index].expanded);
        if (direct || expanded) matches.push({
          item:doc.item, categories:eligible[index], score:relevance(scoped[index], query, terms),
          matchType:direct ? 'exact' : 'alias', doc,
        });
      });
      let mode = 'exact';
      // Never dilute exact/alias hits. Only use fuzzy recovery for a genuine miss.
      if (!matches.length && terms.length && terms.length <= 12 && query.length <= 160) {
        const costs = terms.map(term => {
          const found = new Map();
          documents.forEach((doc, index) => {
            if (eligible[index].length && contains(scoped[index].expanded, term)) found.set(index, 0);
          });
          const limit = tolerance(term);
          if (limit) for (const [token, indices] of fuzzyVocabulary()) {
            const cost = tokenCost(term, token, limit);
            if (cost <= limit) for (const index of indices) {
              if (eligible[index].length && hasToken(scoped[index].expanded, token)
                && (!found.has(index) || cost < found.get(index))) found.set(index, cost);
            }
          }
          return found;
        });
        const smallest = [...costs].sort((a, b) => a.size - b.size)[0];
        for (const [index] of smallest) {
          if (!costs.every(cost => cost.has(index)) || !numericPhrasesMatch(scoped[index].expanded)) continue;
          const total = costs.reduce((sum, cost) => sum + cost.get(index), 0);
          if (total > 2) continue;
          matches.push({item:documents[index].item, categories:eligible[index], score:total, matchType:'fuzzy', doc:documents[index]});
        }
        if (matches.length) mode = 'fuzzy';
      }
      matches.sort(compareMatches);
      // Keep internal indexing structures out of the browser adapter contract.
      for (const match of matches) delete match.doc;
      lastKey = key;
      lastResponse = {matches, mode};
      return lastResponse;
    }

    function suggest(input, filters = {}) {
      const query = normalize(input);
      if (query.length < 2) return [];
      const terms = query.split(' ').filter(Boolean);
      const response = search(input, filters);
      const suggestions = [];
      const seen = new Set();
      for (const match of response.matches) {
        const composer = composers.get(match.item.composer_en);
        const identity = composerKey(composer.query);
        if (!composer.query || seen.has(identity)) continue;
        seen.add(identity);
        const relevant = terms.every(term => contains(composer.fields, term)
          || (response.mode === 'fuzzy' && tolerance(term) > 0
            && [...composer.fields.tokens].some(token => tokenCost(term, token, tolerance(term)) <= tolerance(term))));
        if (relevant) {
          suggestions.push({label: composer.label, detail: composer.detail, query: composer.query, kind: 'composer'});
          if (suggestions.length === 3) break;
        }
      }
      for (const match of response.matches) {
        if (suggestions.length === 6) break;
        const item = match.item;
        const canonical = `${item.title_en} ${item.composer_en || ''}`.trim();
        const metadata = fieldSet([sourceId(item), item.source_name || sources.get(sourceId(item)), ...(item.formats || []), resourceLabel(item), item.resource_type,
          ...Object.values(item.details || {}), ...(item.contents || []), item.declared_kind && item.declared_kind !== 'unspecified' ? kindLabel(item.declared_kind) : '',
          ...(item.topic_ids || []).filter(topic => !item.topic_category_ids || item.topic_category_ids[topic]?.some(id => match.categories.some(c => c.id === id)))
            .flatMap(id => [byTopic.get(id)?.name_zh, byTopic.get(id)?.name_en]),
          ...match.categories.flatMap(category => [category.name, category.name_zh, kindLabel(category.kind)])]);
        const primary = fieldSet([canonical]);
        const retained = terms.filter(term => !contains(primary, term) && contains(metadata, term));
        const selectedQuery = [canonical, ...retained].join(' ');
        if (seen.has(selectedQuery)) continue;
        seen.add(selectedQuery);
        suggestions.push({label: titleLabel(item), detail: composerLabel(item), query: selectedQuery, kind: 'work', resource_type: item.resource_type || 'score'});
      }
      return suggestions;
    }
    function browse(filters = {}) {
      const order = new Intl.Collator('en', {numeric:true, sensitivity:'base'});
      const nameKey = category => category.name.replace(/^For guitar(?= |$)/, 'For 1 guitar');
      const memberships = new Map();
      for (const doc of documents) for (const category of doc.categories) if (passes(category, filters, doc.item)) memberships.set(category.id, (memberships.get(category.id) || 0) + 1);
      const categories = data.categories.filter(category => passes(category, {...filters, kind:'all'})
        && (!filters.kind || filters.kind === 'all' || category.kind === filters.kind || memberships.has(category.id))).sort((a, b) =>
        Number(a.kind === 'arrangement') - Number(b.kind === 'arrangement') || order.compare(nameKey(a), nameKey(b)));
      const ids = new Set(categories.map(category => String(category.id)));
      const workCount = documents.filter(doc => doc.categories.some(category => ids.has(String(category.id)) && passes(category, filters, doc.item))).length;
      return {categories:filters.kind && filters.kind !== 'all' ? categories.map(category => ({...category, work_count:memberships.get(category.id) || 0})) : categories, workCount};
    }
    function browseTopics(filters = {}) {
      const response = search('', {...filters, topic:'all'});
      return (data.topics || []).map(topic => {
        const records = response.matches.filter(match => (match.item.topic_ids || []).includes(topic.id)
          && (!match.item.topic_category_ids || match.item.topic_category_ids[topic.id]?.some(id => match.categories.some(c => c.id === id))));
        return {...topic, work_count:records.length, source_count:new Set(records.map(match => sourceId(match.item))).size};
      }).filter(topic => topic.work_count);
    }
    return {search, suggest, browse, browseTopics};
  }
  return {normalize, createIndex, catalogView, sourceId, titleLabel, composerLabel, kindLabel, resourceLabel};
})();

if (typeof module !== 'undefined' && module.exports) module.exports = GuitarSearch;
