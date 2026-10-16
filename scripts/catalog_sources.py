"""Source registry and strict public projection of normalized source catalogs.

Adapters own discovery and files. This layer only joins source-scoped records;
it never merges a work from two sites based on a title or a fuzzy name.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlparse

REGISTRY_PATH = Path(__file__).resolve().parents[1] / "config/sources.json"
PUBLIC_FORMATS = {"PDF", "GPX", "MIDI", "GP3", "GP4", "GP5", "GP6", "GP7", "GP8", "GP", "MUSICXML", "LILYPOND", "IMAGE", "ONLINE", "UNSPECIFIED"}
SOURCE_PUBLIC_METADATA = {"instrumentation", "arranger", "editor", "transcriber", "opus", "license", "source_edition", "difficulty", "publisher", "publication_date", "pages", "record_level", "collection", "language", "key", "period", "catalogue_number", "source_call", "institution", "license_note", "availability", "description", "component_count", "contributors", "isbn", "original_arrangement_status", "source_type", "title_annotations", "responsibility_statement", "source_title_transcription", "translated_title_transcription", "source_attribution_note", "dimensions", "physical_description", "text_quality_note", "attribution_role", "material_type"}
NEW_DETAIL_FIELDS = frozenset({"instrumentation_zh", "source_instrumentation", "instrumentation_review",
                        "guitar_player_count", "ensemble_player_count", "file_title", "file_identity_note",
                        "written_guitar_part_count", "ensemble_size_note", "file_part_labels"})
# The public schema includes guarded file-review descriptions. Their availability
# is source scoped; a historical adapter's same-named private field is unrelated.
PUBLIC_METADATA = SOURCE_PUBLIC_METADATA | NEW_DETAIL_FIELDS
from catalog_classification import (APPLIED_CLASSIFICATIONS, PUBLIC_FIELDS as CLASSIFICATION_FIELDS,
                                    apply_classification_reviews, public_details)
PUBLIC_METADATA |= CLASSIFICATION_FIELDS
MUSESCORE_RESERVED_OWNERS = frozenset({"api", "download", "static", "score", "scores", "sheetmusic", "groups", "user", "users", "s", "editor"})
MUSESCORE_SYNTHETIC_SOURCE_INSTRUMENTATION = "Guitar-related source declaration; file scope pending"
_MUSESCORE_RECORD_PATH = re.compile(r"/(?:(?:user/[1-9][0-9]*)|(?P<owner>[A-Za-z0-9][A-Za-z0-9_.-]*))/scores/(?P<record>[1-9][0-9]*)")


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
    rules = source.get("page_url_rules", [])
    matched_rule = next((rule for rule in rules if re.fullmatch(rule["path"], url.path)), None)
    pairs = parse_qsl(url.query, keep_blank_values=True)
    query_ok = not url.query
    if matched_rule and url.query:
        approved = matched_rule.get("query", {})
        query_ok = (len(pairs) == len(approved) and len({key for key, _ in pairs}) == len(pairs)
                    and all(key in approved and re.fullmatch(approved[key], val) for key, val in pairs))
    dedicated_page = bool(matched_rule and matched_rule.get("human_page"))
    if rules and not homepage and not matched_rule and value != source["homepage"]:
        raise ValueError(f"unapproved {source_id} source page path: {value!r}")
    if (url.scheme != "https" or url.hostname not in source["allowed_hosts"]
            or url.username or url.password or url.port not in (None, 443)
            or not query_ok or url.fragment or "\\" in value
            or re.search(r"\.(?:pdf|mid|midi|gpx|gp[3-8]|zip|mxl|musicxml|mscz|mscx|xml|ly)(?:$|/)", decoded)
            or any(segment in decoded for segment in ("/wp-content/", "/special:", "/wiki/file:"))
            or ("/download/" in decoded and not dedicated_page)):
        raise ValueError(f"invalid {source_id} source page URL: {value!r}")
    if source_id == "imslp" and not homepage and not url.path.startswith("/wiki/"):
        raise ValueError(f"invalid IMSLP source page URL: {value!r}")
    if source_id == "musescore":
        record = _MUSESCORE_RECORD_PATH.fullmatch(url.path)
        if record and (record["owner"] or "").casefold() in MUSESCORE_RESERVED_OWNERS:
            raise ValueError(f"reserved MuseScore source page route: {value!r}")
    return value


def validate_record_source_url(value: str, source_id: str, native_id: str,
                               registry: list[dict] | None = None) -> str:
    """Validate one record page and any source-specific native-ID contract."""
    validate_source_url(value, source_id, registry)
    if source_id == "musescore":
        record = _MUSESCORE_RECORD_PATH.fullmatch(urlparse(value).path)
        if (not isinstance(native_id, str) or not re.fullmatch(r"[1-9][0-9]*", native_id)
                or record is None or record["record"] != native_id):
            raise ValueError(f"MuseScore native record ID and source page disagree: {native_id!r}, {value!r}")
    return value


def public_source_instrumentation(native: dict, current: str | None = None) -> str | None:
    """Return the public source declaration, repairing one exact MuseScore placeholder.

    ``current`` is the source-instrumentation value being projected. The native
    metadata instrumentation is the default for independent verifier callers.
    """
    metadata = native.get("metadata", {})
    value = current if current is not None else metadata.get("instrumentation")
    if (not str(native.get("id", "")).startswith("musescore:")
            or value != MUSESCORE_SYNTHETIC_SOURCE_INSTRUMENTATION):
        return value
    declarations = metadata.get("source_instruments", [])
    names = [row["name"] for row in declarations
             if isinstance(row, dict) and isinstance(row.get("name"), str) and row["name"].strip()]
    return "；".join(names) if names else None


def source_catalog(root: Path, source: dict) -> dict:
    relative = Path(source["catalog"])
    path = root / relative
    if relative.is_absolute() or ".." in relative.parts or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("source catalog must stay inside the library")
    source_bytes = path.read_bytes()
    payload = json.loads(source_bytes)
    if payload.get("schema_version") != 1 or payload.get("source_id") != source["id"]:
        raise ValueError(f"invalid normalized source catalog: {source['id']}")
    if not isinstance(payload.get("categories"), list) or not isinstance(payload.get("works"), list):
        raise ValueError("normalized catalog requires categories and works")
    from catalog_instrumentation import APPLIED_REVIEW_IDS, apply_instrumentation_review
    if APPLIED_REVIEW_IDS in payload:
        raise ValueError("native catalog cannot supply the controlled runtime review marker")
    effective = apply_instrumentation_review(root, payload, catalog_bytes=source_bytes)
    return apply_classification_reviews(root, effective, payload)


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
            classification_reviews = catalog.get(APPLIED_CLASSIFICATIONS, {})
            from catalog_instrumentation import APPLIED_REVIEW_IDS, REVIEW_STATUSES
            file_review_ids = set(catalog.get(APPLIED_REVIEW_IDS, [])) if source["id"] == "musescore" else set()
            snapshot = catalog.get("snapshot", {})
            public_source["snapshot"] = {
                key: snapshot[key] for key in ("frozen_at", "discovery_complete", "page_count", "scope", "record_count", "detail_complete", "metadata_license") if key in snapshot
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
                if (source["id"] == "musescore" and identity not in file_review_ids
                        and raw.get("instrumentation_status") in REVIEW_STATUSES):
                    raise ValueError("uncontrolled MuseScore file review status: " + identity)
                all_ids.add(identity)
                memberships = raw["category_ids"]
                if not memberships or len(memberships) != len(set(memberships)):
                    raise ValueError("invalid source work memberships")
                category_ids = sorted(category_map[key] for key in memberships)
                formats = sorted(set(str(value).upper() for value in raw.get("formats", [])))
                if any(value not in PUBLIC_FORMATS for value in formats):
                    raise ValueError("unsupported source format label")
                work = {
                    "id": identity, "source_record_id": identity.split(":", 1)[1],
                    "source_id": source["id"], "source_name": source["name"],
                    "source_url": validate_record_source_url(raw["source_url"], source["id"], identity.split(":", 1)[1], registry),
                    "title_en": raw["title_en"], "title_zh": raw.get("title_zh", ""),
                    "composer_en": raw["composer_en"], "composer_zh": raw.get("composer_zh", ""),
                    "category_ids": category_ids, "formats": formats,
                    "translation_status": raw.get("translation_status", "unreviewed"),
                    "instrumentation_status": raw.get("instrumentation_status", "unverified"),
                    "resource_type": raw.get("resource_type", "score"),
                    "title_aliases": raw.get("title_aliases", []),
                }
                metadata = raw.get("metadata", {})
                file_review_applied = (raw["id"] in file_review_ids
                    and raw.get("instrumentation_status") in REVIEW_STATUSES
                    and metadata.get("file_instrumentation_basis") == "file_crosscheck")
                detail_fields = PUBLIC_METADATA if file_review_applied else SOURCE_PUBLIC_METADATA
                work["details"] = {key: str(metadata[key]) for key in detail_fields
                                   if key in metadata and isinstance(metadata[key], (str, int, float)) and str(metadata[key]).strip()}
                if source["id"] == "musescore" and "source_instrumentation" in work["details"]:
                    projected_declaration = public_source_instrumentation(
                        raw, current=work["details"]["source_instrumentation"])
                    if projected_declaration is None:
                        work["details"].pop("source_instrumentation", None)
                    else:
                        work["details"]["source_instrumentation"] = projected_declaration
                # These fields come only from the checked compiler input, never
                # from a same-named field in an unreviewed native source record.
                for key in CLASSIFICATION_FIELDS:
                    work['details'].pop(key, None)
                if identity in classification_reviews:
                    work['details'].update(public_details(classification_reviews[identity]))
                if source["id"] == "dga":
                    fields = metadata.get("source_fields", {})
                    raw_format = str(fields.get("format") or "").strip()
                    notes = str(fields.get("source_notes1") or "").strip()
                    if (raw_format in {"LP", "Audio CD", "Audio Kassette"}
                            or re.match(r"^\d+\s+sound discs?\b", raw_format, re.I)
                            or notes == "Tonaufnahme"):
                        work["details"]["material_type"] = "recording"
                    elif notes == "Zeitschrift":
                        work["details"]["material_type"] = "journal"
                    elif raw_format == "Broschüre" or notes == "Sekundärliteratur":
                        work["details"]["material_type"] = "reference_text"
                    if raw_format and ("material_type" in work["details"] or re.search(r"\bscore\b|\d\s*(?:cm|mm)\b", raw_format, re.I)):
                        previous = work["details"].get("physical_description", "")
                        work["details"]["physical_description"] = (previous + "；" if previous else "") + raw_format
                for original, display in (("source_pages", "pages"), ("year", "publication_date"), ("date", "publication_date"), ("instruments", "instrumentation"), ("information", "description")):
                    if display not in work["details"] and isinstance(metadata.get(original), (str, int, float)):
                        if not re.search(r"https?://", str(metadata[original])):
                            work["details"][display] = str(metadata[original])
                declared_kind = metadata.get("original_arrangement_status", "unspecified")
                work["declared_kind"] = declared_kind if declared_kind in {"original", "arrangement"} else "unspecified"
                contents = metadata.get("collection_contents", [])
                if isinstance(contents, list):
                    work["contents"] = [value for value in contents if isinstance(value, str) and not re.search(r"https?://|\.(?:pdf|zip|mid|gpx)\b", value, re.I)]
                contributors = metadata.get("contributors_original")
                if isinstance(contributors, list):
                    names = [value for value in contributors if isinstance(value, str)]
                    if names:
                        work["details"]["contributors"] = "；".join(names)
                # The catalog site's editor is not necessarily an edition's editor.
                if source["id"] in {"delcamp", "werner"} and not metadata.get("editor_evidence"):
                    work["details"].pop("editor", None)
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
    from catalog_unification import unify_catalog
    unify_catalog(root, data, registry)
    return data
