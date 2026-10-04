"use strict";

const PAGE_SIZE = 18;
const FAMILY_LABELS = {
  pure: "纯吉他", strings: "弦乐", woodwinds: "木管", brass: "铜管",
  keyboard_reed: "键盘 / 自由簧", plucked: "拨弦乐器", percussion: "打击乐", mixed_chamber: "室内乐",
  classclef: "ClassClef 目录",
};
const elements = {
  search: document.querySelector("#search"),
  source: document.querySelector("#source-filter"),
  family: document.querySelector("#family-filter"),
  kind: document.querySelector("#kind-filter"),
  category: document.querySelector("#category-filter"),
  topic: document.querySelector("#topic-filter"),
  clear: document.querySelector("#clear"),
  share: document.querySelector("#share"),
  status: document.querySelector("#status"),
  results: document.querySelector("#results"),
  loadMore: document.querySelector("#load-more"),
  error: document.querySelector("#error"),
  familyShortcuts: document.querySelector("#family-shortcuts"),
  options: document.querySelector("#search-options"),
  hint: document.querySelector("#search-hint"),
  directory: document.querySelector("#category-directory"),
  back: document.querySelector("#back-to-categories"),
  title: document.querySelector("#catalog-title"),
  description: document.querySelector("#catalog-description"),
};

const state = {
  data: null,
  categoryById: new Map(),
  sourceById: new Map(),
  topicById: new Map(),
  workById: new Map(),
  relatedById: new Map(),
  engine: null,
  matches: [],
  visible: PAGE_SIZE,
  suggestions: [],
  activeSuggestion: -1,
  composing: false,
  aliasesAvailable: true,
  inputTimer: null,
  openFamilies: new Set(),
};

function makeElement(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function addOption(select, value, label) {
  const option = document.createElement("option");
  option.value = String(value);
  option.textContent = label;
  select.append(option);
}

function addFamilyShortcut(value, label) {
  const button = makeElement("button", "family-shortcut", label);
  button.type = "button";
  button.dataset.family = value;
  button.setAttribute("aria-pressed", "false");
  button.addEventListener("click", () => {
    elements.family.value = value;
    elements.topic.value = "all";
    elements.category.value = "all";
    state.visible = PAGE_SIZE;
    update();
  });
  elements.familyShortcuts.append(button);
}

function compactNumber(value) {
  return new Intl.NumberFormat("zh-CN").format(value);
}

function populateFilters() {
  for (const work of state.data.works) state.workById.set(work.id, work);
  for (const edge of state.data.relationships || []) {
    for (const [identity, target] of [[edge.from_id, edge.to_id], [edge.to_id, edge.from_id]]) {
      if (!state.relatedById.has(identity)) state.relatedById.set(identity, []);
      state.relatedById.get(identity).push({target, type:edge.type});
    }
  }
  for (const topic of state.data.topics || []) {
    state.topicById.set(topic.id, topic);
    addOption(elements.topic, topic.id, topic.name_zh);
  }
  for (const source of Array.isArray(state.data.sources) ? state.data.sources : [{id:"imslp", name:"IMSLP"}]) {
    state.sourceById.set(source.id, source);
    addOption(elements.source, source.id, source.name);
    const sourceIndex = document.querySelector("#source-index");
    if (sourceIndex) {
      const entry = makeElement("button", "", source.name);
      entry.type = "button";
      entry.setAttribute("aria-label", `浏览 ${source.name} 来源目录`);
      entry.addEventListener("click", () => {
        elements.source.value = source.id;
        elements.family.value = elements.kind.value = elements.category.value = elements.topic.value = "all";
        document.querySelector("#filter-drawer").open = true;
        state.visible = PAGE_SIZE;
        update({push:true});
        elements.title.scrollIntoView({behavior:scrollBehavior(), block:"start"});
      });
      sourceIndex.append(entry);
    }
  }
  addFamilyShortcut("all", "全部分类");
  for (const family of state.data.families) {
    addOption(elements.family, family.id, `${family.name_zh} / ${family.name_en}`);
    if (!state.data.topics?.length) addFamilyShortcut(family.id, FAMILY_LABELS[family.id] || family.name_zh);
  }
  for (const category of state.data.categories) {
    state.categoryById.set(String(category.id), category);
    addOption(elements.category, category.id, `${sourceName(category)} · ${category.name_zh || category.name}`);
  }
  for (const topic of state.data.topics || []) {
    if (!topic.work_count) continue;
    const button = makeElement("button", "family-shortcut", topic.name_zh);
    button.type = "button";
    button.dataset.topic = topic.id;
    button.setAttribute("aria-label", topic.name_zh);
    button.addEventListener("click", () => {
      elements.topic.value = topic.id;
      elements.category.value = elements.family.value = "all";
      state.visible = PAGE_SIZE;
      update({push:true});
    });
    elements.familyShortcuts.append(button);
  }
}

function updateFamilyShortcuts() {
  let selected = elements.family.value;
  if (elements.category.value !== "all") {
    selected = state.categoryById.get(elements.category.value)?.family || selected;
  }
  const available = new Set(state.engine.browse({source:elements.source.value}).categories.map(category => category.family));
  for (const button of elements.familyShortcuts.querySelectorAll("button")) {
    if (button.dataset.topic) {
      button.setAttribute("aria-pressed", String(button.dataset.topic === elements.topic.value));
      continue;
    }
    button.setAttribute("aria-pressed", String(button.dataset.family === selected && elements.topic.value === "all"));
    button.hidden = button.dataset.family !== "all" && !available.has(button.dataset.family);
  }
}

function sourceName(item) {
  const id = GuitarSearch.sourceId(item);
  return item.source_name || state.sourceById.get(id)?.name || (id === "imslp" ? "IMSLP" : id);
}

function appendTranslationNote(parent, evidence, field) {
  const labels = {
    title: {machine:"曲名待复核", retained:"保留原题", untranslated:"曲名未译"},
    composer: {machine:"姓名待复核", retained:"保留原名", untranslated:"姓名未译"},
    category: {machine:"分类译名待复核", retained:"分类保留原名", untranslated:"分类未译"},
  };
  const label = labels[field]?.[evidence?.status];
  if (!label) return;
  const note = makeElement("span", "translation-note", label);
  if (evidence.reason) note.title = evidence.reason;
  parent.append(note);
}

function readUrlState() {
  const params = new URLSearchParams(window.GuitarCatalogAdapter?.readQuery?.() ?? window.location.search);
  elements.search.value = params.get("q") || "";
  const source = params.get("source") || "all";
  const family = params.get("family") || "all";
  const kind = params.get("kind") || "all";
  const category = params.get("category") || "all";
  elements.topic.value = state.topicById.has(params.get("topic")) ? params.get("topic") : "all";
  for (const [select, value] of [[elements.source, source], [elements.family, family], [elements.kind, kind], [elements.category, category]]) {
    select.value = [...select.options].some((option) => option.value === value) ? value : "all";
  }
  document.querySelector("#filter-drawer").open = [source, family, kind, category].some((value) => value !== "all");
}

function writeUrlState(push = false) {
  const params = new URLSearchParams();
  const query = elements.search.value.trim();
  if (query) params.set("q", query);
  if (elements.source.value !== "all") params.set("source", elements.source.value);
  if (elements.family.value !== "all") params.set("family", elements.family.value);
  if (elements.kind.value !== "all") params.set("kind", elements.kind.value);
  if (elements.category.value !== "all") params.set("category", elements.category.value);
  if (elements.topic.value !== "all") params.set("topic", elements.topic.value);
  const suffix = params.toString();
  if (window.GuitarCatalogAdapter?.writeQuery) {
    window.GuitarCatalogAdapter.writeQuery(suffix, push);
    return;
  }
  const url = `${window.location.pathname}${suffix ? `?${suffix}` : ""}${window.location.hash}`;
  if (push && url !== `${window.location.pathname}${window.location.search}${window.location.hash}`) history.pushState(null, "", url);
  else history.replaceState(null, "", url);
}

function currentFilters() {
  return {source: elements.source.value, family: elements.family.value, kind: elements.kind.value, category: elements.category.value, topic:elements.topic.value};
}

function closeSuggestions() {
  elements.options.hidden = true;
  elements.search.setAttribute("aria-expanded", "false");
  elements.search.removeAttribute("aria-activedescendant");
  state.activeSuggestion = -1;
}

function chooseSuggestion(index) {
  const suggestion = state.suggestions[index];
  if (!suggestion) return;
  elements.search.value = suggestion.query;
  state.visible = PAGE_SIZE;
  update();
  elements.search.focus();
  closeSuggestions();
  elements.status.scrollIntoView({behavior: scrollBehavior(), block: "start"});
}

function showSuggestions() {
  if (!state.engine || state.composing || document.activeElement !== elements.search) return;
  state.suggestions = state.engine.suggest(elements.search.value, currentFilters());
  elements.options.replaceChildren();
  closeSuggestions();
  if (!state.suggestions.length) return;
  state.suggestions.forEach((suggestion, index) => {
    const option = makeElement("li", "search-option");
    option.id = `search-option-${index}`;
    option.setAttribute("role", "option");
    option.setAttribute("aria-selected", "false");
    const text = makeElement("span", "option-copy");
    text.append(makeElement("strong", "", suggestion.label), makeElement("small", "", suggestion.detail));
    option.append(text, makeElement("span", "option-kind", suggestion.kind === "composer" ? "音乐家" : suggestion.resource_type === "reference" ? "参考资料" : "曲目"));
    // Keep focus on the combobox so both pointer and keyboard selection work.
    option.addEventListener("pointerdown", event => event.preventDefault());
    option.addEventListener("click", () => chooseSuggestion(index));
    elements.options.append(option);
  });
  elements.options.hidden = false;
  elements.search.setAttribute("aria-expanded", "true");
}

function openCategory(category, clearQuery = false) {
  if (clearQuery) elements.search.value = "";
  elements.source.value = GuitarSearch.sourceId(category);
  elements.family.value = "all";
  elements.kind.value = "all";
  elements.category.value = String(category.id);
  elements.topic.value = "all";
  document.querySelector("#filter-drawer").open = true;
  state.visible = PAGE_SIZE;
  update({push: true});
  elements.title.scrollIntoView({behavior: scrollBehavior()});
}

function renderSourceDirectory(target = elements.directory, updateStatus = true) {
  const directory = state.engine.browse(currentFilters());
  target.replaceChildren();
  if (updateStatus) elements.status.textContent = `${compactNumber(directory.categories.length)} 个分类 · ${compactNumber(directory.workCount)} 条作品记录`;
  for (const family of state.data.families) {
    const categories = directory.categories.filter(category => category.family === family.id);
    if (!categories.length) continue;
    const group = makeElement("details", "category-group");
    group.dataset.family = family.id;
    group.open = state.openFamilies.has(family.id) || elements.family.value === family.id;
    group.addEventListener("toggle", () => {
      if (group.open) state.openFamilies.add(family.id);
      else state.openFamilies.delete(family.id);
    });
    const summary = makeElement("summary", "");
    const label = makeElement("span", "group-label", family.name_zh);
    label.append(makeElement("small", "", family.name_en));
    summary.append(label, makeElement("span", "group-count", `${categories.length} 个分类`));
    group.append(summary);
    const grid = makeElement("div", "category-grid");
    for (const category of categories) {
      const card = makeElement("a", "category-card");
      card.href = window.GuitarCatalogAdapter?.categoryHref?.(category) ?? `?category=${encodeURIComponent(category.id)}#catalog`;
      card.dataset.category = String(category.id);
      card.setAttribute("aria-label", `${sourceName(category)}：${category.name_zh || category.name}，${compactNumber(category.work_count)} 条作品记录`);
      const meta = makeElement("div", "category-card-meta");
      meta.append(makeElement("span", "source-badge", sourceName(category)),
        makeElement("span", "result-kind", GuitarSearch.kindLabel(category.kind)));
      const title = (category.name_zh || category.name).replace(/[·.]?(?:原作|改编)$/, "");
      card.append(meta, makeElement("h3", "", title), makeElement("p", "category-source-name", category.name));
      appendTranslationNote(card, category.translation, "category");
      card.append(makeElement("span", "category-enter", `${compactNumber(category.work_count)} 条作品记录 · 查看 →`));
      card.addEventListener("click", event => {
        if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        openCategory(category, true);
      });
      grid.append(card);
    }
    group.append(grid);
    target.append(group);
  }
  if (!directory.categories.length) target.append(makeElement("p", "empty", "当前筛选条件下没有分类。请调整筛选条件。"));
}

function renderDirectory() {
  if (!state.data.topics?.length || elements.family.value !== "all" || elements.kind.value !== "all") {
    renderSourceDirectory();
    return;
  }
  elements.directory.replaceChildren();
  const topics = state.engine.browseTopics(currentFilters());
  const grid = makeElement("div", "category-grid topic-grid");
  for (const [index, topic] of topics.entries()) {
    const card = makeElement("a", "category-card topic-card");
    card.dataset.topic = topic.id;
    const topicParams = new URLSearchParams({topic:topic.id});
    if (elements.source.value !== "all") topicParams.set("source", elements.source.value);
    card.href = `?${topicParams}#catalog`;
    const number = makeElement("span", "topic-index", String(index + 1).padStart(2, "0"));
    number.setAttribute("aria-hidden", "true");
    const enter = makeElement("span", "category-enter");
    const arrow = makeElement("span", "card-arrow", "↗");
    arrow.setAttribute("aria-hidden", "true");
    enter.append(makeElement("span", "", `${compactNumber(topic.work_count)} 条记录 · ${topic.source_count} 个来源`), arrow);
    card.append(number, makeElement("h3", "", topic.name_zh), makeElement("p", "category-source-name", topic.name_en), enter);
    card.addEventListener("click", event => {
      if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      elements.topic.value = topic.id;
      state.visible = PAGE_SIZE;
      update({push:true});
      elements.title.scrollIntoView({behavior:scrollBehavior(), block:"start"});
    });
    grid.append(card);
  }
  elements.directory.append(grid);
  const originals = makeElement("details", "category-group");
  originals.append(makeElement("summary", "", "来源原分类与目录"));
  const container = makeElement("div", "");
  originals.append(container);
  originals.addEventListener("toggle", () => {
    if (originals.open && !container.childElementCount) renderSourceDirectory(container, false);
  });
  elements.directory.append(originals);
  const directoryWorks = state.engine.search("", currentFilters()).matches;
  const sourceCount = new Set(directoryWorks.map(match => GuitarSearch.sourceId(match.item))).size;
  elements.status.textContent = `${compactNumber(directoryWorks.length)} 条记录 · ${topics.length} 个共同分类 · ${sourceCount} 个来源`;
}

function categoryChip(category) {
  const button = makeElement("button", "category-chip", category.name_zh || category.name);
  button.type = "button";
  button.title = category.name;
  button.setAttribute("aria-label", `查看 ${category.name_zh || category.name}（${sourceName(category)}）`);
  button.addEventListener("click", () => openCategory(category));
  return button;
}

function resultCard(match, index) {
  const item = match.item;
  const article = makeElement("article", "result");
  article.style.animationDelay = `${Math.min(index, 10) * 24}ms`;

  const header = makeElement("div", "result-header");
  header.append(makeElement("span", "result-number", String(index + 1).padStart(2, "0")));
  header.append(makeElement("span", "source-badge", sourceName(item)));
  const kinds = [...new Set(match.categories.map((category) => GuitarSearch.kindLabel(category.kind === "unspecified" && item.declared_kind !== "unspecified" ? item.declared_kind : category.kind)))];
  header.append(makeElement("span", "result-kind", GuitarSearch.resourceLabel(item) || kinds.join(" / ")));
  article.append(header);

  const title = makeElement("div", "result-title");
  title.append(makeElement("h3", "", GuitarSearch.titleLabel(item)));
  const englishTitle = item.display_title_en || item.title_en;
  if (item.translation?.title?.status === "machine" && item.title_zh) {
    const draft = makeElement("details", "category-extra");
    draft.append(makeElement("summary", "", "中文参考草稿（待复核）"));
    draft.append(makeElement("p", "result-title-en", (item.display_title_zh || item.title_zh).replace(/^《|》$/g, "")));
    title.append(draft);
  } else if (item.title_zh && GuitarSearch.titleLabel(item) !== englishTitle) {
    title.append(makeElement("p", "result-title-en", englishTitle));
  }
  appendTranslationNote(title, item.translation?.title, "title");
  article.append(title);

  const meta = makeElement("div", "result-meta");
  const attributionRole = {source_unspecified:"来源署名", author:"作者", performer:"演奏者", editor:"编辑", arranger:"编曲者", transcriber:"转写者", compiler:"编纂者", composer:"作曲者", unverified_name:"署名字段待核"}[item.details?.attribution_role];
  const composer = makeElement("p", "result-composer", (attributionRole ? attributionRole + "：" : "") + GuitarSearch.composerLabel(item));
  const englishComposer = item.display_composer_en || item.composer_en;
  if (item.composer_zh && GuitarSearch.composerLabel(item) !== englishComposer) composer.append(makeElement("span", "", englishComposer));
  appendTranslationNote(composer, item.translation?.composer, "composer");
  meta.append(composer);
  if (item.formats?.length) meta.append(makeElement("p", "result-formats", `来源格式：${item.formats.join(" · ")}`));
  const labels = {instrumentation:"编制", arranger:"编曲", editor:"编辑", transcriber:"转写／移谱", opus:"作品号", source_edition:"版本", difficulty:"来源难度标记", publisher:"出版", publication_date:"年代", pages:"页数／原始页册描述", license:"使用条件", source_call:"馆藏编号", record_level:"条目层级", component_count:"来源所列组件数", contributors:"来源其他署名", isbn:"ISBN", description:"版本说明", original_arrangement_status:"原作／改编声明", institution:"馆藏机构", language:"语言", key:"调性", period:"时期", catalogue_number:"目录编号", collection:"来源曲目集", license_note:"使用条件说明", availability:"来源可用性说明", source_type:"来源载体标注", material_type:"资料载体", title_annotations:"来源题名注记", responsibility_statement:"来源责任说明", source_title_transcription:"来源完整题名转录", translated_title_transcription:"完整中文参考转录", source_attribution_note:"来源完整署名", dimensions:"尺寸", physical_description:"来源册页／载体描述", text_quality_note:"来源文字质量说明", attribution_role:"来源署名角色"};
  const sourceTypes = {Handskrift:"手稿", "music transcription":"音乐转录", "sound recording":"录音", "Manuscript copy":"手稿抄本", "Autograph manuscript":"亲笔手稿", "Printed music":"印刷乐谱"};
  const languageNames = {deutsch:"德语", Deutsch:"德语", ger:"德语", englisch:"英语", Englisch:"英语", eng:"英语", spanisch:"西班牙语", Spanisch:"西班牙语", spa:"西班牙语", italienisch:"意大利语", Italienisch:"意大利语", ita:"意大利语", "französisch":"法语", fre:"法语", lat:"拉丁语", pol:"波兰语", Russisch:"俄语", schwedisch:"瑞典语", sonstiges:"其他语种", zxx:"非语言内容", "In Italian.":"意大利语", "In French.":"法语", "Words in German.":"德语歌词"};
  const information = Object.entries(item.details || {}).filter(([key]) => labels[key]);
  if (information.length) {
    const details = makeElement("details", "category-extra");
    details.append(makeElement("summary", "", "乐谱与版本信息"));
    for (const [key, value] of information) {
      const text = key === "record_level" ? ({collection:"合集", Collection:"合集", score:"乐谱版本", edition:"乐谱版本", work:"作品", item:"条目", Item:"条目", "Single item":"单个条目", Composite:"复合条目", reference:"参考资料", bibliographic_reference:"书目参考", "native shelfmark with preserved indexed components":"按来源馆藏号整理，保留所列组件"}[value] || value)
        : key === "original_arrangement_status" ? GuitarSearch.kindLabel(value)
        : key === "material_type" ? ({recording:"录音", journal:"期刊", reference_text:"文字参考资料"}[value] || value)
        : key === "attribution_role" ? ({source_unspecified:"来源未明确角色", author:"作者", performer:"演奏者", editor:"编辑", arranger:"编曲者", transcriber:"转写者", compiler:"编纂者", composer:"作曲者", unverified_name:"署名字段不是可靠人名"}[value] || value)
        : key === "source_type" ? (sourceTypes[value] ? sourceTypes[value] + "（" + value + "）" : value)
        : key === "language" && value.split(/[,;]\s*|\s+/).every(part => languageNames[part]) ? value.split(/[,;]\s*|\s+/).map(part => languageNames[part]).join("、") + "（" + value + "）"
        : key === "language" && languageNames[value] ? languageNames[value] + "（" + value + "）"
        : key === "key" && value.split(";").every(part => /^[A-G](?:♭|♯|b|#)?\s+(?:major|minor)$/.test(part.trim())) ? value.split(";").map(part => part.trim().replace(/\s+major$/, "大调").replace(/\s+minor$/, "小调")).join("、") + "（" + value + "）"
        : value;
      details.append(makeElement("p", "result-formats", `${labels[key]}：${text}`));
    }
    meta.append(details);
  }
  if (item.contents?.length) {
    const contents = makeElement("details", "category-extra");
    contents.append(makeElement("summary", "", `来源所列曲集内容（${item.contents.length}）`));
    for (const entry of item.contents) contents.append(makeElement("p", "result-formats", entry));
    meta.append(contents);
  }
  const categories = makeElement("div", "category-list");
  match.categories.slice(0, 4).forEach((category) => categories.append(categoryChip(category)));
  meta.append(categories);
  if (match.categories.length > 4) {
    const extra = makeElement("details", "category-extra");
    extra.append(makeElement("summary", "", `其他 ${match.categories.length - 4} 个分类`));
    const list = makeElement("div", "category-list");
    match.categories.slice(4).forEach((category) => list.append(categoryChip(category)));
    extra.append(list);
    meta.append(extra);
  }
  article.append(meta);

  const link = makeElement("a", "source-link", `${sourceName(item)} 来源页面`);
  link.href = item.source_url || item.imslp_url;
  link.setAttribute("aria-label", `${GuitarSearch.titleLabel(item)}：${sourceName(item)} 来源页面（新窗口）`);
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  article.append(link);
  const related = state.relatedById.get(item.id) || [];
  if (related.length) {
    const group = makeElement("details", "category-extra");
    group.append(makeElement("summary", "", `有证据的跨来源关联（${related.length}）`));
    for (const edge of related) {
      const other = state.workById.get(edge.target);
      if (!other) continue;
      const relationLabel = {identical_pdf:"已验证同一 PDF", shared_source_file:"来源引用同一文件", holding_record:"机构与馆藏号对应", collection_membership:"来源合集与子条目"};
      const relatedLink = makeElement("a", "source-link", `${sourceName(other)} · ${GuitarSearch.titleLabel(other)} · ${relationLabel[edge.type]}`);
      relatedLink.href = other.source_url || other.imslp_url;
      relatedLink.target = "_blank";
      relatedLink.rel = "noopener noreferrer";
      group.append(relatedLink);
    }
    article.append(group);
  }
  window.GuitarCatalogAdapter?.decorateCard?.(article, match);
  return article;
}

function renderResults() {
  elements.results.replaceChildren();
  if (!state.matches.length) {
    const empty = makeElement("div", "empty");
    empty.append(makeElement("strong", "", "未找到匹配作品"));
    empty.append(makeElement("span", "", "请检查关键词，或调整来源与分类筛选条件。"));
    if (Object.values(currentFilters()).some(value => value !== "all")) {
      const relax = makeElement("button", "relax-filters", "保留关键词，清除筛选");
      relax.type = "button";
      relax.addEventListener("click", () => {
        elements.source.value = elements.family.value = elements.kind.value = elements.category.value = elements.topic.value = "all";
        state.visible = PAGE_SIZE;
        update();
      });
      empty.append(relax);
    }
    elements.results.append(empty);
    elements.loadMore.hidden = true;
    return;
  }
  const fragment = document.createDocumentFragment();
  state.matches.slice(0, state.visible).forEach((match, index) => fragment.append(resultCard(match, index)));
  elements.results.append(fragment);
  elements.loadMore.hidden = state.visible >= state.matches.length;
}

function update({push = false} = {}) {
  window.clearTimeout(state.inputTimer);
  closeSuggestions();
  writeUrlState(push);
  updateFamilyShortcuts();
  const browsing = GuitarSearch.catalogView(elements.search.value, currentFilters()) === "categories";
  document.querySelector("#catalog").dataset.view = browsing ? "categories" : "works";
  elements.directory.hidden = !browsing;
  elements.results.hidden = browsing;
  elements.back.hidden = browsing;
  const category = state.categoryById.get(elements.category.value);
  const topic = state.topicById.get(elements.topic.value);
  elements.title.textContent = browsing ? "乐谱分类库" : category ? category.name_zh || category.name : topic ? topic.name_zh : "作品检索";
  elements.description.textContent = browsing ? "按共同编制与用途浏览，保留每个来源的原分类。"
    : category ? `${sourceName(category)} · ${category.name}` : topic ? `${topic.name_en} · 全部匹配来源` : "统一搜索曲名、音乐家、编制与版本资料。";
  if (browsing) {
    state.matches = [];
    elements.results.replaceChildren();
    elements.loadMore.hidden = true;
    elements.hint.hidden = true;
    renderDirectory();
    elements.directory.setAttribute("aria-busy", "false");
    elements.results.setAttribute("aria-busy", "false");
    return;
  }
  const response = state.engine.search(elements.search.value, currentFilters());
  state.matches = response.matches;
  const shown = Math.min(state.visible, state.matches.length);
  elements.status.textContent = `${compactNumber(state.matches.length)} 条${response.mode === "fuzzy" ? "近似" : ""}作品记录${shown < state.matches.length ? ` · 已显示 ${shown} 条` : ""}`;
  elements.hint.hidden = response.mode !== "fuzzy" && state.aliasesAvailable;
  elements.hint.textContent = response.mode === "fuzzy" ? "未找到精确结果，以下为近似匹配。"
    : state.aliasesAvailable ? "" : "别名表暂未载入，曲名搜索和拼写容错仍然可用。";
  renderResults();
  elements.directory.setAttribute("aria-busy", "false");
  elements.results.setAttribute("aria-busy", "false");
}

function clearSearch() {
  elements.search.value = "";
  elements.source.value = "all";
  elements.family.value = "all";
  elements.kind.value = "all";
  elements.category.value = "all";
  elements.topic.value = "all";
  document.querySelector("#filter-drawer").open = false;
  state.visible = PAGE_SIZE;
  update();
  elements.search.focus();
}

async function copySearchLink() {
  writeUrlState();
  try {
    await navigator.clipboard.writeText(window.location.href);
    elements.share.textContent = "链接已复制 ✓";
  } catch (_error) {
    elements.share.textContent = "复制地址栏即可分享";
  }
  window.setTimeout(() => { elements.share.textContent = "复制链接 ↗"; }, 1800);
}

function scrollBehavior() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth";
}

function bindEvents() {
  let timer;
  document.querySelector("#search-form").addEventListener("submit", (event) => {
    event.preventDefault();
    if (state.composing) return;
    window.clearTimeout(timer);
    state.visible = PAGE_SIZE;
    update();
    elements.status.scrollIntoView({ behavior: scrollBehavior(), block: "start" });
  });
  elements.back.addEventListener("click", () => {
    elements.search.value = "";
    elements.category.value = "all";
    elements.topic.value = "all";
    document.querySelector("#filter-drawer").open = false;
    state.visible = PAGE_SIZE;
    update({push:true});
    elements.title.scrollIntoView({behavior:scrollBehavior()});
  });
  function scheduleSearch() {
    window.clearTimeout(timer);
    closeSuggestions();
    if (state.composing) return;
    timer = state.inputTimer = window.setTimeout(() => { state.visible = PAGE_SIZE; update(); showSuggestions(); }, 130);
  }
  elements.search.addEventListener("input", scheduleSearch);
  elements.search.addEventListener("compositionstart", () => {
    state.composing = true;
    window.clearTimeout(timer);
    closeSuggestions();
  });
  elements.search.addEventListener("compositionend", () => { state.composing = false; scheduleSearch(); });
  elements.search.addEventListener("focus", showSuggestions);
  elements.search.addEventListener("blur", closeSuggestions);
  elements.search.addEventListener("keydown", event => {
    if (event.isComposing || state.composing) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      if (elements.options.hidden) showSuggestions();
      if (elements.options.hidden) return;
      event.preventDefault();
      window.clearTimeout(timer);
      const count = state.suggestions.length;
      state.activeSuggestion = state.activeSuggestion < 0
        ? (event.key === "ArrowDown" ? 0 : count - 1)
        : (state.activeSuggestion + (event.key === "ArrowDown" ? 1 : count - 1)) % count;
      [...elements.options.children].forEach((option, index) => option.setAttribute("aria-selected", String(index === state.activeSuggestion)));
      const active = elements.options.children[state.activeSuggestion];
      elements.search.setAttribute("aria-activedescendant", active.id);
      active.scrollIntoView({block: "nearest"});
    } else if (event.key === "Enter" && !elements.options.hidden && state.activeSuggestion >= 0) {
      event.preventDefault();
      window.clearTimeout(timer);
      chooseSuggestion(state.activeSuggestion);
    } else if (event.key === "Escape" && !elements.options.hidden) {
      event.preventDefault();
      event.stopPropagation();
      window.clearTimeout(timer);
      closeSuggestions();
    }
  });
  [elements.family, elements.kind, elements.category, elements.topic].forEach((select) => {
    select.addEventListener("change", () => { state.visible = PAGE_SIZE; update(); });
  });
  elements.source.addEventListener("change", () => {
    elements.family.value = elements.kind.value = elements.category.value = elements.topic.value = "all";
    state.visible = PAGE_SIZE;
    update();
  });
  elements.clear.addEventListener("click", () => { window.clearTimeout(timer); clearSearch(); });
  elements.share.addEventListener("click", copySearchLink);
  elements.loadMore.addEventListener("click", () => {
    state.visible += PAGE_SIZE;
    update();
  });
  document.addEventListener("keydown", (event) => {
    if (event.isComposing || state.composing) return;
    const editing = event.target.closest("input, textarea, select, [contenteditable]");
    if (event.key === "/" && !editing && !event.ctrlKey && !event.metaKey && !event.altKey) {
      event.preventDefault();
      elements.search.focus();
    }
    if (event.key === "Escape" && document.activeElement === elements.search) {
      window.clearTimeout(timer);
      clearSearch();
    }
  });
  window.addEventListener("popstate", () => {
    readUrlState();
    state.visible = PAGE_SIZE;
    update();
  });
}

async function loadCatalog() {
  const plainCatalog = async () => {
    const response = await fetch("data/catalog.json", { cache: "no-cache" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  };
  const compactCatalog = async () => {
    if (!window.GuitarCatalogCodec || typeof DecompressionStream === "undefined") return plainCatalog();
    try {
      const response = await fetch("data/catalog.compact.json", { cache: "no-cache" });
      if (!response.ok) return plainCatalog();
      return await window.GuitarCatalogCodec.decode(await response.json());
    } catch {
      return plainCatalog();
    }
  };
  const [data, aliases, ranking] = await Promise.all([
    compactCatalog(),
    fetch("data/search-aliases.json", { cache: "no-cache", signal: AbortSignal.timeout(5000) })
      .then(result => result.ok ? result.json() : null).catch(() => null),
    fetch("data/ranking.json", { cache: "no-cache", signal: AbortSignal.timeout(5000) })
      .then(result => result.ok ? result.json() : null).catch(() => null),
  ]);
  return {data, aliases, ranking: ranking || {}};
}

async function start() {
  performance.mark("guitar-catalog-load-start");
  try {
    const {data, aliases, ranking} = await (window.GuitarCatalogAdapter?.load() ?? loadCatalog());
    performance.mark("guitar-catalog-data-ready");
    state.data = data;
    if (![1, 2].includes(state.data.schema_version)) throw new Error("unsupported catalog schema");
    populateFilters();
    state.aliasesAvailable = aliases !== null;
    state.engine = GuitarSearch.createIndex(state.data, aliases || {}, ranking || {});
    document.querySelector("#stat-works").textContent = compactNumber(state.data.summary.unique_work_count);
    document.querySelector("#stat-categories").textContent = compactNumber(state.data.summary.category_count);
    const sourceCount = document.querySelector("#stat-sources");
    if (sourceCount) sourceCount.textContent = compactNumber(state.sourceById.size);
    readUrlState();
    bindEvents();
    update();
    performance.mark("guitar-catalog-interactive");
    performance.measure("guitar-catalog-startup", "guitar-catalog-load-start", "guitar-catalog-interactive");
  } catch (error) {
    elements.status.textContent = "目录载入失败";
    elements.error.hidden = false;
    elements.error.textContent = /^当前浏览器不支持压缩目录|^压缩目录解码器未载入/.test(error.message || "")
      ? error.message : "无法载入目录数据，请稍后刷新页面。";
    elements.directory.setAttribute("aria-busy", "false");
    elements.results.setAttribute("aria-busy", "false");
    console.error("Catalogue loading failed", error);
  }
}

start();
