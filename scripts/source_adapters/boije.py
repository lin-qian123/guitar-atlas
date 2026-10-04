"""Boije's official alphabetical catalog: identity is the native shelfmark.

An indexed component is not a separate PDF edition.  Several components may
share a Boije number and URN; all original rows survive in ``source_entries``.
Title keywords provide exclusion evidence, never positive purity verification.
"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

SOURCE_ID = "boije"
BASE = "https://old.capricemusic.se"
HOMEPAGE = BASE + "/musikochteaterbiblioteket/ladda-ner-noter/boijes-samling/"
LICENSE_STATEMENT = (
    "Free PDF access; publication with attribution to Musik- och "
    "teaterbiblioteket - The Music and Theatre Library of Sweden; "
    "two published copies must be sent to the library."
)


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def index_pages(html: str) -> list[dict]:
    result = {}
    for anchor in BeautifulSoup(html, "html.parser").find_all("a", href=True):
        url = urljoin(HOMEPAGE, anchor["href"])
        if (urlparse(url).hostname == "old.capricemusic.se"
                and re.fullmatch(re.escape(urlparse(HOMEPAGE).path)
                                 + r"boijes-samling-(?:[a-z]|v-w|a-2)/", urlparse(url).path)):
            label = clean_text(anchor.get_text(" ", strip=True))
            result[url] = {"id": "index:" + urlparse(url).path.rstrip("/").split("-")[-1],
                           "name": "Boije alphabetical index — " + label,
                           "kind": "unspecified", "source_url": url}
    # Ä's slug ends a-2, and must not collide with A's id.
    for item in result.values():
        item["id"] = "index:" + urlparse(item["source_url"]).path.rstrip("/").split("boijes-samling-")[-1]
    return list(result.values())


def page_rows(html: str, category: dict) -> list[dict]:
    rows = []
    soup = BeautifulSoup(html, "html.parser")
    for tr in soup.find_all("tr"):
        cells = tr.find_all(["td", "th"], recursive=False)
        if len(cells) < 2:
            continue
        call = clean_text(cells[-1].get_text(" ", strip=True))
        match = re.fullmatch(r"\[?Boije\s+(\d+(?::\d+)?(?:[a-z])?(?:-\d+)?)\]?", call, re.I)
        if not match:
            continue
        title_cell = cells[-2]
        anchor = title_cell.find("a", href=True)
        asset = urljoin(category["source_url"], anchor["href"]) if anchor else ""
        if asset and urlparse(asset).hostname not in {"urn.kb.se", "boijefiles.musikverket.se"}:
            raise ValueError("unapproved Boije asset host")
        rows.append({"native_id": match.group(1), "composer": clean_text(cells[0].get_text(" ", strip=True)) if len(cells) > 2 else "",
                     "title": clean_text(title_cell.get_text(" ", strip=True)), "source_call": call,
                     "urn": asset, "category_id": category["id"], "source_url": category["source_url"]})
    return rows


def exclusion_reason(title: str) -> str | None:
    """Require explicit wording, not an opera/theme or genre inference."""
    text = unicodedata.normalize("NFKC", title).casefold()
    if re.search(r"\b(?:electric|elektrische|bass|basse|kontrabass|contrabass|steel|hawaiian|slide)\s+(?:guitar|guitare|gitarre)|\b(?:kontrabass|contrabass|basso continuo)\b", text):
        return "explicit excluded instrument in source title"
    if re.search(r"\b(?:gesang|gesangstücke|gesangstucke|singstimme|singstimmen|vocal|voice|voices|chorus|chor|röst|röster|sangstemme|sångstycken)\b|\b(?:voix|canto|chant)\s+(?:et|e|und|avec|con)\b", text):
        return "explicit vocal scoring in source title"
    if re.search(r"\b(?:guitar|guitare|guitarra|gitarre|gitarr|guitarr)\w*\s+(?:ou|oder|or|eller)\s+(?:lyre|lyra|piano|harp|harpe|klavier)", text):
        return "explicit alternative solo instrument in source title"
    if re.search(r"\b(?:grand|grande|large|grosses)\s+(?:orchestra|orchester)\b|\b(?:electronic|electronics|tape)\b", text):
        return "explicit orchestra or electronic scoring in source title"
    return None


def normalize(categories: list[dict], rows: list[dict], snapshot: dict) -> dict:
    included = defaultdict(list)
    excluded = []
    excluded_calls = set()
    for row in rows:
        reason = exclusion_reason(row["title"])
        if reason:
            excluded.append({**row, "reason": reason})
            excluded_calls.add(row["native_id"])
        else:
            included[row["native_id"]].append(row)
    works = []
    for native, entries in included.items():
        # Repeated catalog rows are preserved once with all category memberships.
        unique = list({(row["title"], row["composer"], row["urn"], row["source_url"]): row for row in entries}.values())
        titles = list(dict.fromkeys(row["title"] for row in unique))
        composers = list(dict.fromkeys(row["composer"] for row in unique if row["composer"]))
        asset_urls = list(dict.fromkeys(row["urn"] for row in unique if row["urn"]))
        reference = all(re.search(r"katalog|bibliograph|verzeichnis|directory", title, re.I) for title in titles)
        assets = [{"source_url": url, "format": "PDF", "filename": "Boije_" + native.replace(":", "_") + ".pdf",
                   "status": "restricted", "acquisition_status": "blocked_by_robots_or_policy_probe",
                   "restriction_reason": "URN resolver robots disallows automated access; file-host policy probe returned 403" +
                       ("; shared shelfmark also indexes excluded scoring" if native in excluded_calls else ""),
                   "upstream_checksum_status": "not_supplied"} for url in asset_urls]
        works.append({"id": "boije:" + native, "title_en": " | ".join(titles),
                      "composer_en": "; ".join(composers), "source_url": unique[0]["source_url"],
                      "category_ids": sorted({row["category_id"] for row in unique}),
                      "formats": ["PDF"] if assets else [], "resource_type": "reference" if reference else "score",
                      "instrumentation_status": "unknown", "assets": assets,
                      "metadata": {"source_call": "Boije " + native, "source_entries": unique,
                                   "component_count": len(titles), "instrumentation": "",
                                   "arranger": "; ".join(dict.fromkeys(
                                       match.strip() for title in titles for match in re.findall(r"Arr\. von (.+?)(?:\.\s+Se:|$)", title))),
                                   "source_edition": "; ".join(dict.fromkeys(
                                       title.split("Se:", 1)[1].strip() for title in titles if "Se:" in title)),
                                   "collection": "Boije Collection", "record_level": "native shelfmark with preserved indexed components",
                                   "institution": "The Music and Theatre Library of Sweden", "catalogue_number": "Boije " + native,
                                   "instrumentation_review": "catalog titles only; file-level scoring unverified",
                                   "opus": "; ".join(dict.fromkeys(re.findall(r"\bOp\.\s*\d+(?:bis)?", " | ".join(titles), re.I))),
                                   "license": LICENSE_STATEMENT, "license_url": HOMEPAGE,
                                   "file_acquisition": "blocked_by_robots_or_policy_probe",
                                   "source_attribution": "Musik- och teaterbiblioteket - The Music and Theatre Library of Sweden",
                                   "related_source_ids": [], "publication_status": "unspecified"}})
    used = {member for row in works for member in row["category_ids"]}
    return {"schema_version": 1, "source_id": "boije", "snapshot": snapshot,
            "categories": [category for category in categories if category["id"] in used], "works": works,
            "excluded_entries": excluded,
            "summary": {"raw_index_rows": len(rows), "record_count": len(works),
                        "category_membership_count": sum(len(row["category_ids"]) for row in works),
                        "excluded_index_rows": len(excluded), "indexed_components": sum(row["metadata"]["component_count"] for row in works),
                        "asset_manifest_records": sum(len(row["assets"]) for row in works),
                        "unique_asset_urls": len({a["source_url"] for row in works for a in row["assets"]}),
                        "pdf_integrity_verified": 0, "instrumentation_verified": 0,
                        "file_acquisition": "blocked_by_robots_or_policy_probe"}}


def registry_proposal() -> dict:
    return {"id": "boije", "name": "Boije Collection", "homepage": HOMEPAGE,
            "allowed_hosts": ["old.capricemusic.se"], "adapter": "normalized_catalog",
            "catalog": "sources/boije/catalog.json", "family": "boije",
            "family_name_zh": "布瓦耶历史馆藏", "family_name_en": "Boije historical collection",
            "page_rules": [{"path_regex": r"/musikochteaterbiblioteket/ladda-ner-noter/boijes-samling/(?:boijes-samling-(?:[a-z]|v-w|a-2)/)?"}],
            "asset_hosts": ["urn.kb.se", "boijefiles.musikverket.se"],
            "metadata_basis": "official alphabetical index",
            "file_acquisition": "free PDFs advertised; automated access blocked by asset robots/policy probe"}
