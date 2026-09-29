"""Source registry and strict public projection of normalized source catalogs.

Adapters own discovery and files. This layer only joins source-scoped records;
it never merges a work from two sites based on a title or a fuzzy name.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

REGISTRY_PATH = Path(__file__).resolve().parents[1] / "config/sources.json"


def load_registry(root: Path | None = None) -> list[dict]:
    path = root / "config/sources.json" if root else REGISTRY_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or not isinstance(payload.get("sources"), list):
        raise ValueError("invalid source registry")
    result, seen = [], set()
    for row in payload["sources"]:
        identity = row.get("id", "")
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", identity) or identity in seen:
            raise ValueError("invalid or duplicate source identity")
        if not row.get("name") or not isinstance(row.get("allowed_hosts"), list) or not row["allowed_hosts"]:
            raise ValueError(f"invalid source configuration: {identity}")
        if row.get("adapter") not in {"imslp_categories", "normalized_catalog"}:
            raise ValueError(f"unknown source adapter: {identity}")
        validate_source_url(row["homepage"], identity, [row], homepage=True)
        seen.add(identity)
        result.append(row)
    if "imslp" not in seen:
        raise ValueError("registry must preserve the IMSLP adapter")
    return result


def validate_source_url(value: str, source_id: str, registry: list[dict] | None = None,
                        *, homepage: bool = False) -> str:
    registry = load_registry() if registry is None else registry
    source = next((row for row in registry if row["id"] == source_id), None)
    if source is None or not isinstance(value, str):
        raise ValueError(f"unknown source: {source_id}")
    url = urlparse(value)
    decoded = unquote(url.path).casefold()
    if (url.scheme != "https" or url.hostname not in source["allowed_hosts"]
            or url.username or url.password or url.port not in (None, 443)
            or url.query or url.fragment or "\\" in value
            or re.search(r"\.(?:pdf|mid|midi|gpx|gp[3-8]|zip)(?:$|/)", decoded)
            or any(segment in decoded for segment in ("/wp-content/", "/download/", "/special:", "/wiki/file:"))):
        raise ValueError(f"invalid {source_id} source page URL: {value!r}")
    if source_id == "imslp" and not homepage and not url.path.startswith("/wiki/"):
        raise ValueError(f"invalid IMSLP source page URL: {value!r}")
    return value


def source_catalog(root: Path, source: dict) -> dict:
    relative = Path(source["catalog"])
    path = root / relative
    if relative.is_absolute() or ".." in relative.parts or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("source catalog must stay inside the library")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or payload.get("source_id") != source["id"]:
        raise ValueError(f"invalid normalized source catalog: {source['id']}")
    if not isinstance(payload.get("categories"), list) or not isinstance(payload.get("works"), list):
        raise ValueError("normalized catalog requires categories and works")
    return payload


def merge_sources(root: Path, data: dict) -> dict:
    """Upgrade the IMSLP projection; a missing configured snapshot is an error."""
    if not (root / "config/sources.json").is_file():
        return data  # Existing standalone IMSLP libraries retain schema 1.
    registry = load_registry(root)
    data["schema_version"] = 2
    old_sources = data["sources"]
    data["sources"] = []
    for collection in (data["works"], data["categories"]):
        for row in collection:
            row.update(source_id="imslp", source_name="IMSLP", source_url=row["imslp_url"])
    for row in data["works"]:
        row["source_record_id"] = row["id"]
        row["formats"] = ["PDF"]
        # Field-level evidence is attached by catalog_translations after merging.
        row["translation_status"] = "untranslated"
        row["resource_type"] = "score"
    all_ids = {work["id"] for work in data["works"]}
    for source in registry:
        public_source = {key: source[key] for key in ("id", "name", "homepage")}
        if source["adapter"] == "imslp_categories":
            public_source["snapshots"] = {key: value for key, value in old_sources.items() if key != "imslp"}
        else:
            catalog = source_catalog(root, source)
            snapshot = catalog.get("snapshot", {})
            public_source["snapshot"] = {
                key: snapshot[key] for key in ("frozen_at", "discovery_complete", "page_count") if key in snapshot
            }
            family = source["family"]
            if any(row["id"] == family for row in data["families"]):
                raise ValueError("source family must be distinct from existing families")
            data["families"].append({"id": family, "name_zh": source["family_name_zh"], "name_en": source["family_name_en"]})
            category_map = {}
            for raw in catalog["categories"]:
                old_id = raw["id"]
                if old_id in category_map:
                    raise ValueError("duplicate source category")
                new_id = len(data["categories"])
                category_map[old_id] = new_id
                kind = raw.get("kind", "unspecified")
                if kind not in {"original", "arrangement", "unspecified"}:
                    raise ValueError("invalid source category kind")
                data["categories"].append({
                    "id": new_id, "source_category_id": old_id,
                    "name": raw["name"], "name_zh": raw.get("name_zh") or raw["name"],
                    "kind": kind, "family": family, "source_id": source["id"],
                    "source_name": source["name"], "work_count": 0,
                    "source_url": validate_source_url(raw["source_url"], source["id"], registry),
                })
            for raw in catalog["works"]:
                identity = raw["id"]
                if not identity.startswith(source["id"] + ":") or identity in all_ids:
                    raise ValueError("source work identity must be unique and namespaced")
                all_ids.add(identity)
                memberships = raw["category_ids"]
                if not memberships or len(memberships) != len(set(memberships)):
                    raise ValueError("invalid source work memberships")
                category_ids = sorted(category_map[key] for key in memberships)
                formats = sorted(set(str(value).upper() for value in raw.get("formats", [])))
                if any(value not in {"PDF", "GPX", "MIDI", "GP3", "GP4", "GP5"} for value in formats):
                    raise ValueError("unsupported source format label")
                work = {
                    "id": identity, "source_record_id": identity.split(":", 1)[1],
                    "source_id": source["id"], "source_name": source["name"],
                    "source_url": validate_source_url(raw["source_url"], source["id"], registry),
                    "title_en": raw["title_en"], "title_zh": raw.get("title_zh", ""),
                    "composer_en": raw["composer_en"], "composer_zh": raw.get("composer_zh", ""),
                    "category_ids": category_ids, "formats": formats,
                    "translation_status": raw.get("translation_status", "unreviewed"),
                    "instrumentation_status": raw.get("instrumentation_status", "unverified"),
                    "resource_type": raw.get("resource_type", "score"),
                    "title_aliases": raw.get("title_aliases", []),
                }
                # Project a closed list of public fields; no assets, hashes or paths.
                data["works"].append(work)
                for key in category_ids:
                    data["categories"][key]["work_count"] += 1
        selected = [work for work in data["works"] if work["source_id"] == source["id"]]
        public_source["record_count"] = len(selected)
        public_source["category_count"] = sum(row["source_id"] == source["id"] for row in data["categories"])
        data["sources"].append(public_source)
    data["works"].sort(key=lambda row: (row["composer_en"].casefold(), row["title_en"].casefold(), row["id"]))
    data["summary"].update(
        category_count=len(data["categories"]),
        category_record_count=sum(len(work["category_ids"]) for work in data["works"]),
        unique_work_count=len(data["works"]), source_count=len(data["sources"]),
    )
    data["integrity"]["composer_count"] = len({work["composer_en"] for work in data["works"]})
    data["integrity"]["works_in_multiple_categories"] = sum(len(row["category_ids"]) > 1 for row in data["works"])
    return data
