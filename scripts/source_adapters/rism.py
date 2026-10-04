"""RISM official JSON-LD search/resource API projection.

The frozen q=guitar result set is a discovery scope, not a scoring whitelist.
Search labels are never silently promoted to standardized source titles; the
title basis and whether full resource metadata has been obtained are recorded.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

SOURCE_ID = "rism"
HOMEPAGE = "https://rism.online/"
SEARCH_URL = "https://rism.online/search?q=guitar&rows=100"
LICENSE_URL = "https://rism.info/community/data-services.html"
SRU_BASE = "https://muscat.rism.info/sru/sources"
SCORING_GUIDELINES_URL = "https://guidelines.rism.info/abbreviations.html"


def exclusion_reason(row: dict) -> str | None:
    """Use declared scoring and RISM's documented instrument vocabulary."""
    metadata = row.get("metadata", {})
    scoring = metadata.get("total_scoring") or metadata.get("scoring_summary") or ""
    if not scoring.strip() or re.fullmatch(r"(?:no (?:further )?indication|\?|i)(?:\s*\([Xx\d]+\))?", scoring.strip(), re.I):
        return None
    lower = scoring.casefold()
    # RISM explicitly documents uppercase parts as vocal, lowercase as instruments.
    if re.search(r"(?<![A-Za-z-])(?:V|S|A|T|B|Bar|Mez|Coro)(?![A-Za-z])", scoring) or re.search(r"\b(?:voice|voices|vocal|chorus|coro|soprano|contralto|tenor|gesang|chant)\b", lower):
        return "explicit vocal scoring in RISM declared total/scoring summary"
    if re.search(r"\b(?:guit(?:ar)?\s*(?:el\.?|electric)|electric guitar|bass guitar|b-guit|steel guitar|hawaiian guitar|slide guitar|cb|bc|kontrabass|contrabass|electronics|tape)\b", lower):
        return "explicit excluded instrument in RISM declared scoring"
    if re.search(r"\borch(?:estra)?\b", lower) and not re.fullmatch(r"(?:guit(?:ar)?\s+orch(?:estra)?|orch(?:estra)?\s+guit(?:ar)?)(?:\s*\([Xx\d]+\))?", lower):
        return "explicit orchestra in RISM declared scoring"
    guitar = r"(?:guit(?:ar)?|guitare|guitarra|gitarr|chitarra)"
    other = r"(?:pf|piano|cemb|hpcd|keyb|lyre|lyra|arp|harp|vl|fl)"
    if (re.search(r"\b" + guitar + r"\s*[\[(]\s*" + other + r"\b", lower)
            or re.search(r"\b" + other + r"\s*[\[(]\s*" + guitar + r"\b", lower)
            or re.search(r"\b" + guitar + r"\s+(?:or|ou|oder|eller|o)\s+" + other + r"\b", lower)):
        return "explicit alternative guitar scoring in RISM declared scoring"
    if not re.search(r"\b" + guitar + r"\b", lower):
        # Regional instruments or an entirely unspecified medium need review;
        # a positive, recognizable non-guitar scoring can be excluded explicitly.
        known = r"(?:vl|vla|vlc|cemb|hpcd|pf|org|fl|ob|cl|fag|cor|tr|trb|lute|theorbo|liuto|arp|lyre|lyra|keyb|strings|winds)"
        if re.fullmatch(r"(?:" + known + r"(?:\s*\([^)]*\))?\s*[,; ]*?)+", lower):
            return "explicit non-guitar scoring in RISM declared scoring"
    return None


def parse_sru(text: str, item_map: dict, api_url: str) -> dict:
    """Losslessly retain MARC records and project documented RISM fields.

    This creates a shared internal representation, not a claim that MARCXML
    is JSON-LD. The transport and exact raw fields remain explicit evidence.
    """
    ns = "{http://www.loc.gov/MARC21/slim}"
    root = ET.fromstring(text)
    result = {}
    role_labels = {"arr": "Arranger", "edt": "Editor", "cmp": "Composer", "cre": "Composer/Author",
                   "prf": "Performer", "scr": "Scribe", "ctb": "Contributor", "aut": "Author"}
    for element in root.findall(".//" + ns + "record"):
        control = [{"tag": field.attrib["tag"], "value": field.text or ""} for field in element.findall(ns + "controlfield")]
        native = next((field["value"] for field in control if field["tag"] == "001"), "")
        url = "https://rism.online/sources/" + native
        if not native.isdigit() or url not in item_map:
            raise ValueError("SRU returned a record outside the requested frozen RISM IDs")
        if url in result:
            raise ValueError("SRU repeated a native ID")
        fields = [{"tag": field.attrib["tag"], "ind1": field.attrib.get("ind1", ""), "ind2": field.attrib.get("ind2", ""),
                   "subfields": [{"code": sub.attrib["code"], "value": sub.text or ""} for sub in field.findall(ns + "subfield")]}
                  for field in element.findall(ns + "datafield")]

        def values(tag, code=None):
            return [sub["value"] for field in fields if field["tag"] == tag for sub in field["subfields"]
                    if code is None or sub["code"] == code]

        def subs(field, code):
            return [sub["value"] for sub in field["subfields"] if sub["code"] == code]

        summaries = []
        def summary(label, texts):
            if texts:
                summaries.append({"label": {"en": [label]}, "value": {"none": list(dict.fromkeys(texts))}})

        summary("Standardized title", values("240", "a"))
        summary("Title on source", values("245", "a"))
        summary("Opus number", values("383", "b"))
        summary("Scoring summary", values("594", "a") or values("240", "m"))
        scoring = []
        for field in fields:
            if field["tag"] == "594" and subs(field, "b"):
                scoring.append(" ".join(subs(field, "b")) + (" (" + "; ".join(subs(field, "c")) + ")" if subs(field, "c") else ""))
        summary("Total scoring", scoring)
        summary("Key or mode", values("240", "r"))
        summary("Source type", values("593", "a"))
        summary("Content type", values("593", "b"))
        summary("Format, extent", values("300", "a"))
        summary("Shelfmark", values("852", "c"))
        summary("Library siglum", values("852", "a"))
        summary("Institution", values("852", "e"))
        summary("Publisher", values("260", "b") + values("264", "b"))
        summary("Publication date", values("260", "c") + values("264", "c"))
        summary("Edition", values("250", "a"))
        summary("Language", values("041", "a"))
        summary("Source notes", values("500", "a"))
        summary("Cataloguing institution", [field["value"] for field in control if field["tag"] == "003"])
        summaries.extend({"label": {"en": ["MARC " + field["tag"]]},
                          "value": {"none": ["; ".join(sub["code"] + "=" + sub["value"] for sub in field["subfields"])]}}
                         for field in fields)
        people, institutions, parent_items, work_items = [], [], [], []
        for field in fields:
            if field["tag"] in {"100", "700"}:
                names, ids = subs(field, "a"), subs(field, "0")
                name = "; ".join(names) + (" (" + "; ".join(subs(field, "d")) + ")" if subs(field, "d") else "")
                roles = subs(field, "4") or (["cre"] if field["tag"] == "100" else ["ctb"])
                for identifier in ids:
                    if identifier.isdigit():
                        for role in roles:
                            people.append({"role": {"value": role, "label": {"en": [role_labels.get(role, role)]}},
                                           "relatedTo": {"id": "https://rism.online/people/" + identifier,
                                                         "type": "rism:Person", "label": {"none": [name]}}})
            elif field["tag"] == "852":
                for identifier in subs(field, "x"):
                    if identifier.isdigit():
                        institutions.append({"id": "https://rism.online/institutions/" + identifier,
                                             "type": "rism:Institution", "label": {"none": subs(field, "e") or subs(field, "a")}})
            elif field["tag"] in {"773", "774"}:
                for identifier in subs(field, "w"):
                    if identifier.isdigit():
                        parent_items.append({"relationshipType": "rism:PrimaryPartOf" if field["tag"] == "773" else "rism:HasPart",
                                             "relatedTo": {"id": "https://rism.online/sources/" + identifier,
                                                           "type": "rism:Source", "label": {"none": subs(field, "t")}}})
            elif field["tag"] == "240":
                for identifier in subs(field, "0"):
                    if identifier.isdigit():
                        work_items.append({"id": "https://rism.online/works/" + identifier,
                                           "type": "rism:Work", "label": {"none": subs(field, "a")}})
        creator = next((person for person in people if person["role"]["value"] in {"cre", "cmp"}), {})
        result[url] = {"id": url, "label": item_map[url].get("label", {}), "creator": creator,
                       "contributors": people, "institutions": institutions,
                       "partOf": {"items": parent_items}, "relatedWorks": work_items,
                       "sourceTypes": item_map[url].get("flags", {}), "contents": {"summary": summaries},
                       "_metadata_format": "MARCXML", "_source_api_url": api_url,
                       "_raw_marcxml": ET.tostring(element, encoding="unicode"),
                       "_marc_controlfields": control, "_marc_fields": fields,
                       "_scoring_basis": "RISM MARC 594 subfields; structured normalization, raw fields preserved"}
    return result


def language_text(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "; ".join(language_text(item) for item in value)
    if not isinstance(value, dict):
        return ""
    for key in ("none", "en", "de", "fr", "it", "es", "pl", "pt"):
        if key in value:
            return language_text(value[key])
    return ""


def summary_fields(record: dict) -> dict:
    """Keep every named summary in the full record, including holdings."""
    result = {}

    def walk(value):
        if isinstance(value, dict):
            if "label" in value and "value" in value:
                key, text = language_text(value["label"]), language_text(value["value"])
                if key and text:
                    result.setdefault(key, [])
                    if text not in result[key]:
                        result[key].append(text)
            for key, item in value.items():
                if key not in {"rendered", "data", "@context"}:
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
    walk(record)
    return result


def relations(record: dict) -> list[dict]:
    result = []

    def walk(value, field="", role="", relationship=""):
        if isinstance(value, dict):
            role_field = value.get("role", {})
            if isinstance(role_field, dict):
                role = language_text(role_field.get("label", {})) or role_field.get("value") or role
            relationship = value.get("relationshipType") or relationship
            identifier = value.get("id", "")
            if isinstance(identifier, str) and re.fullmatch(r"https://rism\.online/(?:sources|people|institutions|works)/[0-9]+", identifier):
                result.append({"id": identifier, "type": value.get("type", ""),
                               "label": language_text(value.get("label", {})), "field": field,
                               "role": role, "relationship_type": relationship})
            for key, item in value.items():
                if key not in {"rendered", "data", "@context"}:
                    walk(item, key, role, relationship)
        elif isinstance(value, list):
            for item in value:
                walk(item, field, role, relationship)
    walk(record)
    return list({(row["id"], row["field"], row["role"], row["relationship_type"]): row for row in result}.values())


def normalize_record(search_item: dict, detail: dict | None = None) -> dict:
    record = detail or search_item
    url = search_item["id"]
    if not re.fullmatch(r"https://rism\.online/(?:sources/\d+|external/diamm/source/\d+)", url):
        raise ValueError("RISM source must have its canonical resource URL")
    # A collection's child records carry their own titles and scoring. Do not
    # turn those into attributes of the parent source or into its scope decision.
    own_record = {key: value for key, value in record.items() if key not in {"sourceItems", "partOf", "relatedWorks"}}
    fields = summary_fields(own_record)
    content_fields = summary_fields(record.get("contents", {}))
    title = "; ".join(content_fields.get("Standardized title", [])) if detail else ""
    title_basis = "standardized_title" if title else "resource_label"
    title = title or language_text(record.get("label", {}))
    if not title:
        title = language_text(search_item.get("label", {}))
        if title:
            title_basis = "search_index_label"
    creator = record.get("creator", {})
    composer = language_text(creator.get("relatedTo", {}).get("label", {})) if isinstance(creator, dict) else ""
    if not composer:
        composer = language_text(search_item.get("summary", {}).get("sourceComposer", {}).get("value", {}))
    total_scoring = "; ".join(content_fields.get("Total scoring", []))
    scoring_summary = "; ".join(content_fields.get("Scoring summary", []))
    metadata = {"instrumentation": total_scoring or scoring_summary,
                "scoring_summary": scoring_summary, "total_scoring": total_scoring,
                "instrumentation_review": "source declaration; keyword discovery does not establish approved scoring",
                "opus": "; ".join(fields.get("Opus number", [])),
                "source_call": "; ".join(fields.get("Shelfmark", []) + fields.get("Shelf mark", [])),
                "title_on_source": "; ".join(fields.get("Title on source", [])),
                "source_edition": "; ".join(fields.get("Publication", []) + fields.get("Publisher", [])),
                "related_source_ids": [row["id"].replace("https://rism.online/sources/", "rism:")
                                       for row in relations(record) if row["id"].startswith("https://rism.online/sources/") and row["id"] != url],
                "authority_relations": relations(record), "source_fields": fields,
                "source_component_summary_fields": summary_fields(record.get("sourceItems", {})),
                "license": "CC BY 3.0 (RISM metadata only)", "license_url": LICENSE_URL,
                "title_basis": title_basis, "resource_metadata_complete": detail is not None,
                "discovery_scope": "official full-text keyword q=guitar; not approved guitar scoring",
                "source_attribution": "RISM, Répertoire International des Sources Musicales"}
    metadata["metadata_format"] = record.get("_metadata_format", "JSON-LD" if detail else "JSON-LD search index")
    if record.get("_marc_fields"):
        metadata["source_marc_fields"] = record["_marc_fields"]
        metadata["source_marc_controlfields"] = record["_marc_controlfields"]
        metadata["scoring_basis"] = record["_scoring_basis"]
    if "/external/" in url:
        metadata["external_record_provider"] = "DIAMM"
    metadata["institution"] = "; ".join(dict.fromkeys(row["label"] for row in metadata["authority_relations"] if "/institutions/" in row["id"])) or "; ".join(fields.get("Institution", []))
    metadata["publisher"] = "; ".join(fields.get("Publisher", []))
    metadata["publication_date"] = "; ".join(fields.get("Publication date", []))
    metadata["language"] = "; ".join(fields.get("Language", []))
    metadata["key"] = "; ".join(fields.get("Key or mode", []))
    metadata["source_edition"] = "; ".join(fields.get("Edition", [])) or metadata["source_edition"]
    metadata["record_level"] = language_text(record.get("sourceTypes", record.get("flags", {})).get("recordType", {}).get("typeLabel", {}))
    metadata["collection"] = "; ".join(row["label"] for row in metadata["authority_relations"] if row["relationship_type"] == "rism:PrimaryPartOf" and row["id"].startswith("https://rism.online/sources/"))
    metadata["related_source_relations"] = [{"target_id": relation["id"].replace("https://rism.online/sources/", "rism:"),
                    "type": "collection_membership", "basis": "explicit_source_collection_structure",
                    "source_relationship_type": relation["relationship_type"]}
                   for relation in metadata["authority_relations"]
                   if relation["relationship_type"] in {"rism:PrimaryPartOf", "rism:HasPart"}
                   and relation["id"].startswith("https://rism.online/sources/") and relation["id"] != url]
    for child in record.get("sourceItems", {}).get("items", []):
        child_url = child.get("id", "")
        if re.fullmatch(r"https://rism\.online/sources/\d+", child_url):
            metadata["related_source_relations"].append({"target_id": child_url.replace("https://rism.online/sources/", "rism:"),
                "type": "collection_membership", "basis": "explicit_source_collection_structure", "source_relationship_type": "rism:HasPart"})
    metadata["arranger"] = "; ".join(dict.fromkeys(row["label"] for row in metadata["authority_relations"] if "arrang" in row["role"].casefold()))
    metadata["editor"] = "; ".join(dict.fromkeys(row["label"] for row in metadata["authority_relations"] if "editor" in row["role"].casefold()))
    content_types = record.get("sourceTypes", record.get("flags", {})).get("contentTypes", [])
    reference = bool(content_types) and all(row.get("type") != "rism:MusicalContent" for row in content_types)
    native = url.removeprefix("https://rism.online/sources/") if "/sources/" in url else url.removeprefix("https://rism.online/")
    known_scoring = total_scoring or scoring_summary
    unspecified = re.fullmatch(r"(?:no (?:further )?indication|\?|i)(?:\s*\([Xx\d]+\))?", known_scoring.strip(), re.I)
    return {"id": "rism:" + native, "title_en": title, "composer_en": composer,
            "source_url": url, "category_ids": ["keyword:guitar"], "formats": [],
            "resource_type": "reference" if reference else "score", "assets": [],
            "instrumentation_status": "source_declared" if known_scoring and not unspecified else "unknown",
            "metadata": metadata}


def normalize(items: list[dict], details: dict, snapshot: dict) -> dict:
    seen = {}
    for item in items:
        seen[item["id"]] = normalize_record(item, details.get(item["id"]))
    excluded, works = [], []
    for row in seen.values():
        reason = exclusion_reason(row)
        if reason:
            excluded.append({"id": row["id"], "source_url": row["source_url"], "title_en": row["title_en"],
                             "composer_en": row["composer_en"], "reason": reason,
                             "total_scoring": row["metadata"]["total_scoring"], "scoring_summary": row["metadata"]["scoring_summary"],
                             "metadata_format": row["metadata"]["metadata_format"], "scope_evidence": SCORING_GUIDELINES_URL})
        else:
            works.append(row)
    return {"schema_version": 1, "source_id": "rism", "snapshot": snapshot,
            "categories": [{"id": "keyword:guitar", "name": "Guitar keyword discovery (scoring unverified)",
                            "kind": "unspecified", "source_url": SEARCH_URL}], "works": works, "excluded_entries": excluded,
            "summary": {"record_count": len(works), "raw_search_items": len(items),
                        "raw_discovery_records": len(seen), "excluded_scoring_records": len(excluded),
                        "resource_details_obtained": len(details),
                        "resource_details_pending": sum(not row["metadata"]["resource_metadata_complete"] for row in works),
                        "metadata_formats": {format_: sum(row["metadata"]["metadata_format"] == format_ for row in works)
                                             for format_ in sorted({row["metadata"]["metadata_format"] for row in works})},
                        "raw_metadata_formats": {format_: sum(detail.get("_metadata_format", "JSON-LD") == format_ for detail in details.values())
                                                 for format_ in sorted({detail.get("_metadata_format", "JSON-LD") for detail in details.values()})},
                        "source_declared_instrumentation": sum(row["instrumentation_status"] == "source_declared" for row in works),
                        "instrumentation_verified": 0, "pdf_integrity_verified": 0,
                        "file_acquisition": "not attempted; external resources require independent source approval"}}


def registry_proposal() -> dict:
    return {"id": "rism", "name": "RISM", "homepage": HOMEPAGE, "allowed_hosts": ["rism.online"],
            "adapter": "normalized_catalog", "catalog": "sources/rism/catalog.json", "family": "rism",
            "family_name_zh": "RISM音乐文献", "family_name_en": "RISM musical sources",
            "page_rules": [{"path_regex": r"/sources/\d+"}, {"path_regex": r"/external/diamm/source/\d+"},
                           {"path_regex": "/search", "query": {"q": "guitar", "rows": "100"}}],
            "metadata_basis": "official JSON-LD API and Muscat SRU metadata; CC BY 3.0", "file_acquisition": "not approved"}
