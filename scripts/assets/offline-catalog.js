"use strict";

function localDownloadName(item, format) {
  const clean = value => String(value || "").replace(/[<>:"/\\|?*\u0000-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/g, " ").replace(/\s+/g, " ").trim().replace(/^[. ]+|[. ]+$/g, "");
  const title = typeof GuitarSearch === "undefined" ? (item.display_title_en || item.title_en) : GuitarSearch.titleLabel(item);
  const native = clean(item.source_record_id || item.id).replace(/\s+/g, "-").slice(0, 24);
  const suffix = `${native ? ` - ${native}` : ""}.${format === "MXL" ? "mxl" : "mid"}`;
  const characters = Array.from(clean(title) || "乐谱").slice(0, Math.max(1, 100 - suffix.length));
  const encoder = new TextEncoder();
  while (characters.length > 1 && encoder.encode(characters.join("") + suffix).length > 240) characters.pop();
  return characters.join("").replace(/[. ]+$/g, "") + suffix;
}

// Offline-only adapter: the public deployment does not contain this file.
window.GuitarCatalogAdapter = {
  async load() {
    const node = document.querySelector("#offline-data");
    const parsed = JSON.parse(node.textContent);
    if (parsed.codec && !window.GuitarCatalogCodec) throw new Error("压缩目录解码器未载入，请刷新页面。");
    const payload = window.GuitarCatalogCodec ? await window.GuitarCatalogCodec.decode(parsed) : parsed;
    // Release the encoded text after loading; search uses the decoded snapshot.
    node.textContent = "";
    return payload;
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
    const editions = (match.item.local_editions || []).filter(edition => allowed.has(edition.category_id) && edition.files.length);
    if (!editions.length) return;
    const section = makeElement("section", "local-scores");
    section.setAttribute("aria-label", "本地乐谱");
    section.append(makeElement("h4", "", "本地乐谱"));
    for (const edition of editions) {
      const category = allowed.get(edition.category_id);
      const group = makeElement("div", "local-edition");
      const label = makeElement("p", "local-instrumentation", category.name_zh);
      label.title = category.name;
      group.append(label);
      const addScore = (parent, score) => {
        const format = score.format === "MUSICXML" ? "MXL" : (score.format || "PDF");
        const link = makeElement("a", "local-score-link");
        link.append(makeElement("span", "local-format", format), makeElement("span", "", score.label));
        link.href = score.href;
        link.setAttribute("aria-label", `${format === "PDF" ? "" : "下载 "}${format}：${score.label}`);
        if (format === "PDF") link.target = "_blank";
        else link.setAttribute("download", localDownloadName(match.item, format));
        link.rel = "noopener";
        parent.append(link);
      };
      const filesByFormat = new Map();
      for (const score of edition.files) {
        const format = score.format || "PDF";
        if (!filesByFormat.has(format)) filesByFormat.set(format, []);
        filesByFormat.get(format).push(score);
      }
      for (const format of ["PDF", "MUSICXML", "MIDI"]) {
        const files = filesByFormat.get(format);
        if (!files) continue;
        files.slice(0, 4).forEach(score => addScore(group, score));
        if (files.length > 4) {
          const more = makeElement("details", "local-score-more");
          const description = format === "PDF" ? "总谱 / 分谱" : `${format === "MUSICXML" ? "MXL" : format} 文件`;
          more.append(makeElement("summary", "", `其他 ${files.length - 4} 份${description}`));
          files.slice(4).forEach(score => addScore(more, score));
          group.append(more);
        }
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
