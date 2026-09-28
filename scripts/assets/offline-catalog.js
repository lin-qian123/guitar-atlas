"use strict";

// Offline-only adapter: the public deployment does not contain this file.
window.GuitarCatalogAdapter = {
  async load() {
    return JSON.parse(document.querySelector("#offline-data").textContent);
  },
  readQuery() {
    const hash = window.location.hash;
    return hash.startsWith("#catalog?") ? hash.slice(9) : window.location.search;
  },
  writeQuery(query, push) {
    // File origins allow fragment navigation, but not History API query changes.
    const hash = query ? `#catalog?${query}` : "#catalog";
    if (push && hash !== window.location.hash) history.pushState(null, "", hash);
    else history.replaceState(null, "", hash);
  },
  categoryHref(category) {
    return `#catalog?category=${category.id}`;
  },
  decorateCard(article, match) {
    const allowed = new Map(match.categories.map(category => [category.id, category]));
    const editions = (match.item.local_editions || []).filter(edition => allowed.has(edition.category_id));
    const section = makeElement("section", "local-scores");
    section.setAttribute("aria-label", "本地 PDF");
    section.append(makeElement("h4", "", "本地 PDF"));
    for (const edition of editions) {
      const category = allowed.get(edition.category_id);
      const group = makeElement("div", "local-edition");
      const label = makeElement("p", "local-instrumentation", category.name_zh);
      label.title = category.name;
      group.append(label);
      const addScore = (parent, score) => {
        const link = makeElement("a", "local-score-link", score.label);
        link.href = score.href;
        link.target = "_blank";
        link.rel = "noopener";
        parent.append(link);
      };
      edition.files.slice(0, 4).forEach(score => addScore(group, score));
      if (edition.files.length > 4) {
        const more = makeElement("details", "local-score-more");
        more.append(makeElement("summary", "", `其他 ${edition.files.length - 4} 份总谱 / 分谱`));
        edition.files.slice(4).forEach(score => addScore(more, score));
        group.append(more);
      }
      const pending = edition.unavailable_count - (edition.excluded_count || 0);
      if (edition.excluded_count) {
        group.append(makeElement("p", "local-pending", `${edition.excluded_count} 份文件未列入当前编制：${edition.exclusion_reason}`));
      }
      if (pending || (!edition.files.length && !edition.excluded_count)) {
        group.append(makeElement("p", "local-pending", pending
          ? `${pending} 份文件未就绪，可查看来源原页。` : "暂无有效本地 PDF，可查看来源原页。"));
      }
      if (category.local_href) {
        const catalog = makeElement("a", "local-category-link", "分类完整目录 ↗");
        catalog.href = category.local_href;
        group.append(catalog);
      }
      section.append(group);
    }
    article.insertBefore(section, article.querySelector(".source-link"));
  },
};
