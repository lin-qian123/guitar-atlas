"""Digital Guitar Archive's advertised legacy API, metadata only.

Legacy record IDs are not Omeka IDs.  Keep unlicensed metadata provenance and
all library/source/publisher fields; never treat the API software ISC licence
as a database licence or an institutional file acquisition permission.
"""
from __future__ import annotations

import re
from urllib.parse import urlencode

SOURCE_ID = "dga"
HOMEPAGE = "https://digitalguitararchive.com/archive/"
API_BASE = "https://digitalguitararchive.com/archive/api"
ANNOUNCEMENT_URL = "https://www.digitalguitararchive.com/digital-guitar-archive-search-api-and-mcp-server/"
TERMS_URL = "https://www.digitalguitararchive.com/terms_conditions/"


DISCOVERY_KEYWORDS = ("guitar", "guitare", "guitarra", "gitarr", "chitarra")


def exclusion_reason(record: dict) -> str | None:
    """Only actual scoring fields justify excluding keyword discovery records."""
    instruments = (record.get("instruments") or "").casefold()
    if re.search(r"\b(?:voice|voices|vocal|vocals|chorus|chant|gesang|singstimme|röst|sangstemme|songs)\b", instruments):
        return "explicit vocal scoring in source instruments field"
    if re.search(r"\b(?:electric|elektrisch|elektrische|bass|steel|hawaiian|slide)\s+(?:guitar|guitare|gitarre)|\b(?:contrabass|kontrabass|basso continuo|electronics|tape)\b", instruments):
        return "explicit excluded instrument in source instruments field"
    if re.search(r"(?:guitar|guitare|guitarra|gitarr|gitarre|chitarra)\s+(?:or|ou|oder|eller)\s+(?:piano|lyre|lyra|harp|harpe|klavier)", instruments):
        return "explicit alternative solo guitar in source instruments field"
    if re.search(r"\b(?:full|large|grand|grande|symphony)\s+(?:orchestra|orchester)\b", instruments):
        return "explicit large orchestra in source instruments field"
    return None


def resource_type(record: dict) -> str:
    # The periodical is explicit in its source content header; source is absent.
    contents = record.get("contents") or ""
    if not record.get("source") and re.search(r"\bETUDE\b", contents[:1000]):
        return "reference"
    return "score"


def search_url(offset=0, limit=200, query="guitar") -> str:
    if query not in DISCOVERY_KEYWORDS:
        raise ValueError("DGA query is outside the frozen keyword scope")
    return API_BASE + "/search?" + urlencode({"q": query, "limit": limit, "offset": offset})


def normalize_record(record: dict, library: dict | None = None) -> dict:
    native = str(record.get("id", ""))
    if not native.isdigit():
        raise ValueError("DGA record needs its native numeric ID")
    library = library or {}
    source = record.get("source") or "unspecified"
    # Public navigation is the tested HTTPS directory; API is internal provenance.
    # The legacy HTML site has no independently verified per-record permalink.
    instruments = record.get("instruments") or ""
    call = record.get("source_call") or ""
    related = []
    boije = re.fullmatch(r"Boije\s+(\d+(?::\d+)?[a-z]?)", call, re.I)
    if source == "S:Skma" and boije:
        related.append("boije:" + boije.group(1))
    raw = dict(record)
    metadata = {"instrumentation": instruments, "opus": record.get("opus") or "",
                "source_call": call, "source_edition": record.get("edition") or "",
                "source_library": source, "source_library_name": library.get("name", ""),
                "source_country": library.get("country", ""), "source_library_url": library.get("url", ""),
                "publisher": record.get("publisher") or "", "publish_location": record.get("publish_location") or "",
                "publish_date": record.get("publish_date") or "", "plate_number": record.get("plate_number") or "",
                "publication_date": record.get("publish_date") or "", "pages": record.get("pages") or "",
                "collection": record.get("series_title") or record.get("volume_title") or "",
                "institution": library.get("name", ""), "language": record.get("language") or "",
                "related_source_ids": related, "related_source_basis": "exact source siglum and native shelfmark" if related else "",
                "digital_file": record.get("digital_file") or "", "source_page_kind": "directory",
                "source_fields": raw, "api_record_url": API_BASE + "/record/" + native,
                "license": "unspecified; official API access offered, database redistribution licence not declared",
                "license_url": ANNOUNCEMENT_URL, "file_acquisition": "restricted; original institutional files require independent approval",
                "discovery_scope": "official multilingual full-text keyword union; not approved guitar scoring",
                "instrumentation_review": "source declaration only; keyword in any field does not verify scoring"}
    title = record.get("title") or "[Untitled source record — DGA " + native + "]"
    metadata.update(source_title_original=record.get("title") or "", title_basis="source_title" if record.get("title") else "missing_source_title_placeholder")
    metadata["attribution_roles"] = [{"name": record.get("author") or "", "role": "author" if resource_type(record) == "reference" else "source_author_unspecified"}]
    return {"id": "dga:" + native, "title_en": title, "composer_en": record.get("author") or "",
            "source_url": HOMEPAGE, "category_ids": ["library:" + source], "formats": [],
            "resource_type": resource_type(record), "instrumentation_status": "source_declared" if instruments else "unknown",
            "assets": [], "metadata": metadata}


def normalize(records: list[dict], libraries: list[dict], snapshot: dict) -> dict:
    library_map = {row["source"]: row for row in libraries}
    included, excluded = [], []
    for record in records:
        reason = exclusion_reason(record)
        if reason:
            excluded.append({"source_record_id": str(record["id"]), "reason": reason, "source_fields": record})
        else:
            included.append(record)
    works = [normalize_record(record, library_map.get(record.get("source"))) for record in included]
    if len({row["id"] for row in works}) != len(works):
        raise ValueError("duplicate DGA IDs across pagination; snapshot is inconsistent")
    used = {row["metadata"]["source_library"] for row in works}
    categories = [{"id": "library:" + native,
                   "name": library_map.get(native, {}).get("name") or native,
                   "kind": "unspecified", "source_url": HOMEPAGE} for native in sorted(used)]
    return {"schema_version": 1, "source_id": "dga", "snapshot": snapshot,
            "categories": categories, "works": works, "excluded_entries": excluded,
            "summary": {"record_count": len(works), "raw_discovery_records": len(records),
                        "excluded_scoring_records": len(excluded), "library_group_count": len(categories),
                        "score_records": sum(row["resource_type"] == "score" for row in works),
                        "reference_records": sum(row["resource_type"] == "reference" for row in works),
                        "advertised_legacy_library_groups": len(libraries),
                        "advertised_legacy_group_record_sum": sum(row["record_count"] for row in libraries),
                        "source_declared_instrumentation": sum(row["instrumentation_status"] == "source_declared" for row in works),
                        "records_with_institutional_digital_reference": sum(bool(row.get("digital_file")) for row in included),
                        "exact_boije_shelfmark_relations": sum(bool(row["metadata"]["related_source_ids"]) for row in works),
                        "instrumentation_verified": 0, "pdf_integrity_verified": 0,
                        "file_acquisition": "not attempted; DGA does not host the institutional files"}}


def registry_proposal() -> dict:
    return {"id": "dga", "name": "Digital Guitar Archive", "homepage": HOMEPAGE,
            "allowed_hosts": ["digitalguitararchive.com", "www.digitalguitararchive.com"],
            "adapter": "normalized_catalog", "catalog": "sources/dga/catalog.json", "family": "dga",
            "family_name_zh": "DGA历史书目", "family_name_en": "DGA historical bibliography",
            "page_rules": [{"path_regex": "/archive/"}],
            "metadata_basis": "advertised official legacy API; database reuse licence unspecified",
            "file_acquisition": "not approved; source navigation only"}
