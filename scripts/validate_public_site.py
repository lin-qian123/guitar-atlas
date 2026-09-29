#!/usr/bin/env python
"""Validate the deployable Guitar Atlas site without network access."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Mapping

from export_public_site import validate_imslp_url
from catalog_sources import load_registry, validate_source_url


FORBIDDEN_KEYS = {
    "download_url",
    "verified_download_url",
    "relative_path",
    "relative_directory",
    "filename",
    "sha1_imslp",
    "sha256",
    "local_path",
    "assets",
    "sha1",
    "object_path",
}
FORBIDDEN_TEXT = (
    re.compile(r'''https?://[^\s<>"'“”]*\.(?:pdf|mid|midi|gpx|gp[3-8]|zip)(?=[\s<>"'“”?#/]|$)''', re.IGNORECASE),
    re.compile(r"file://", re.IGNORECASE),
    re.compile(r"/Volumes/", re.IGNORECASE),
    re.compile(r"(?:^|[/\\])scores[/\\]", re.IGNORECASE),
    re.compile(r"\.pdf(?:$|[?#])", re.IGNORECASE),
    re.compile(r"\.(?:mid|midi|gpx|gp[3-8]|zip)(?:$|[?#])", re.IGNORECASE),
    re.compile(r"/Users/", re.IGNORECASE),
)
TRANSLATION_STATUSES = {"reviewed", "reference", "retained", "machine", "untranslated", "not_applicable"}
HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\U00020000-\U0002ffff]")


class PublicSiteValidationError(ValueError):
    """Raised when a public catalog or static asset is unsafe to deploy."""


def fail(message: str) -> None:
    raise PublicSiteValidationError(message)


def check_forbidden(value: object, context: str = "catalog") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_KEYS:
                fail(f"{context}: forbidden field {key!r}")
            check_forbidden(child, f"{context}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            check_forbidden(child, f"{context}[{index}]")
    elif isinstance(value, str):
        for pattern in FORBIDDEN_TEXT:
            if pattern.search(value):
                fail(f"{context}: forbidden public value {value!r}")


def require_list(payload: Mapping[str, object], name: str) -> list[object]:
    value = payload.get(name)
    if not isinstance(value, list):
        fail(f"{name} must be a list")
    return value


def validate_translation(evidence: object, original: str, translated: str, context: str) -> str:
    """Check field-level claims; Han presence is coverage, not semantic review."""
    if not isinstance(evidence, dict):
        fail(f"{context}: translation evidence must be an object")
    status = evidence.get("status")
    if not isinstance(status, str) or status not in TRANSLATION_STATUSES:
        fail(f"{context}: invalid translation status")
    for field in ("basis", "reason"):
        if not isinstance(evidence.get(field), str):
            fail(f"{context}: translation {field} must be a string")
    if status not in {"untranslated", "not_applicable"} and not evidence["basis"].strip():
        fail(f"{context}: translation basis is required")
    if status in {"reviewed", "reference", "machine"}:
        if not translated.strip() or not HAN.search(translated):
            fail(f"{context}: translated status requires a Chinese display value")
    elif status == "retained":
        if not (translated or original).strip() or not evidence["reason"].strip():
            fail(f"{context}: retained text requires a display value and reason")
    elif status == "untranslated":
        if translated != "":
            fail(f"{context}: untranslated field must have an empty Chinese value")
    elif original != "" or translated != "":
        fail(f"{context}: not_applicable requires empty original and Chinese values")
    return status


def aggregate_translation_status(statuses: list[str]) -> str:
    for status in ("untranslated", "machine", "reference", "reviewed"):
        if status in statuses:
            return status
    return "retained"


def validate_payload(payload: object) -> dict[str, int]:
    if not isinstance(payload, dict) or payload.get("schema_version") not in {1, 2}:
        fail("catalog must use schema_version 1 or 2")
    multisource = payload["schema_version"] == 2
    translation_contract = "translation_schema_version" in payload
    if translation_contract and (not multisource or type(payload["translation_schema_version"]) is not int
                                 or payload["translation_schema_version"] != 1):
        fail("translation_schema_version must be 1 in public schema 2")
    check_forbidden(payload)
    source_ids = set()
    if multisource:
        registry = load_registry()
        configured = {row["id"]: row for row in registry}
        for source in require_list(payload, "sources"):
            if not isinstance(source, dict) or source.get("id") not in configured or source["id"] in source_ids:
                fail("unknown or duplicate public source")
            expected = configured[source["id"]]
            if any(source.get(key) != expected[key] for key in ("name", "homepage")):
                fail("public source identity differs from registry")
            source_ids.add(source["id"])
        if source_ids != set(configured):
            fail("public catalog is missing a configured source")

    def validate_row_url(row: dict, context: str) -> None:
        if multisource:
            source = row.get("source_id")
            if source not in source_ids:
                fail(f"{context}: unknown source")
            validate_source_url(row.get("source_url"), source)
            if row.get("source_name") != configured[source]["name"]:
                fail(f"{context}: invalid source name")
            if source == "imslp" and row.get("imslp_url") != row["source_url"]:
                fail(f"{context}: inconsistent IMSLP source URL")
        else:
            url = row.get("imslp_url")
            if not isinstance(url, str):
                fail(f"{context} has no IMSLP URL")
            validate_imslp_url(url, context)
    categories = require_list(payload, "categories")
    works = require_list(payload, "works")
    if not translation_contract and any(isinstance(row, dict) and "translation" in row for row in categories + works):
        fail("field-level translation evidence requires translation_schema_version")
    families = require_list(payload, "families")
    for family in families:
        if not isinstance(family, dict) or any(
            not isinstance(family.get(field), str) or not family[field].strip()
            for field in ("id", "name_zh", "name_en")
        ):
            fail("family identity and display names must be non-empty strings")
    family_ids = {family["id"] for family in families}
    if len(family_ids) != len(families):
        fail("family IDs must be unique and non-empty")

    category_ids: set[int] = set()
    category_work_counts: dict[int, int] = {}
    source_links = 0
    for expected_id, raw in enumerate(categories):
        if not isinstance(raw, dict):
            fail("category rows must be objects")
        category_id = raw.get("id")
        if category_id != expected_id:
            fail("category IDs must be contiguous and ordered")
        if not isinstance(raw.get("name"), str) or not raw["name"].strip():
            fail(f"category {category_id} has an invalid name")
        if not isinstance(raw.get("name_zh"), str):
            fail(f"category {category_id} has an invalid name_zh")
        if translation_contract:
            validate_translation(raw.get("translation"), raw["name"], raw["name_zh"], f"category {category_id}")
        family = raw.get("family")
        if family not in family_ids:
            fail(f"category {category_id} references an unknown family")
        if raw.get("kind") not in ({"original", "arrangement", "unspecified"} if multisource else {"original", "arrangement"}):
            fail(f"category {category_id} has an invalid kind")
        work_count = raw.get("work_count")
        if type(work_count) is not int or work_count < 0:
            fail(f"category {category_id} has an invalid work_count")
        try:
            validate_row_url(raw, f"category {category_id}")
        except ValueError as exc:
            raise PublicSiteValidationError(str(exc)) from exc
        category_ids.add(category_id)
        category_work_counts[category_id] = work_count
        source_links += 1

    seen_work_ids: set[str] = set()
    observed_memberships: Counter[int] = Counter()
    previous_sort_key: tuple[str, str, str] | None = None
    for raw in works:
        if not isinstance(raw, dict):
            fail("work rows must be objects")
        work_id = raw.get("id")
        if not isinstance(work_id, str) or not work_id:
            fail("work IDs must be non-empty strings")
        if work_id in seen_work_ids:
            fail(f"duplicate work ID: {work_id}")
        seen_work_ids.add(work_id)
        required = ("title_en",) if translation_contract or (multisource and raw.get("source_id") != "imslp") else ("title_en", "title_zh", "composer_en", "composer_zh")
        for field in required:
            if not isinstance(raw.get(field), str) or not str(raw[field]).strip():
                fail(f"work {work_id} has an invalid {field}")
        for field in ("title_en", "title_zh", "composer_en", "composer_zh"):
            if not isinstance(raw.get(field), str):
                fail(f"work {work_id} has a non-string {field}")
        if raw.get("title_zh") and (not str(raw["title_zh"]).startswith("《") or not str(raw["title_zh"]).endswith("》")
                                    or not raw["title_zh"][1:-1].strip()):
            fail(f"work {work_id} has an invalid Chinese display title")
        if translation_contract:
            evidence = raw.get("translation")
            if not isinstance(evidence, dict) or set(evidence) != {"title", "composer"}:
                fail(f"work {work_id}: title and composer translation evidence is required")
            statuses = [validate_translation(evidence[field], raw[f"{field}_en"], raw[f"{field}_zh"],
                                             f"work {work_id} {field}") for field in ("title", "composer")]
            if raw.get("translation_status") != aggregate_translation_status(statuses):
                fail(f"work {work_id}: aggregate translation_status disagrees with field evidence")
        try:
            validate_row_url(raw, f"work {work_id}")
        except ValueError as exc:
            raise PublicSiteValidationError(str(exc)) from exc
        memberships = raw.get("category_ids")
        if (
            not isinstance(memberships, list)
            or not memberships
            or any(type(value) is not int for value in memberships)
            or len(set(memberships)) != len(memberships)
            or memberships != sorted(memberships)
            or any(value not in category_ids for value in memberships)
        ):
            fail(f"work {work_id} has invalid category memberships")
        observed_memberships.update(memberships)
        if multisource:
            resource_type = raw.get("resource_type", "score")
            if not isinstance(resource_type, str) or resource_type not in {"score", "reference"}:
                fail(f"work {work_id} has an invalid resource type")
            native_id = raw.get("source_record_id")
            expected_id = work_id if raw["source_id"] == "imslp" else work_id.split(":", 1)[-1]
            if not isinstance(native_id, str) or not native_id or native_id != expected_id:
                fail(f"work {work_id} has inconsistent source identity")
            formats = raw.get("formats")
            if (not isinstance(formats, list) or not formats
                    or any(not isinstance(value, str) or value not in {"PDF", "MIDI", "GPX", "GP3", "GP4", "GP5"} for value in formats)
                    or len(formats) != len(set(formats))):
                fail(f"work {work_id} has invalid format labels")
            aliases = raw.get("title_aliases", [])
            if not isinstance(aliases, list) or any(not isinstance(value, str) or not value.strip() for value in aliases):
                fail(f"work {work_id} has invalid title aliases")
            if any(categories[value]["source_id"] != raw["source_id"] for value in memberships):
                fail(f"work {work_id} crosses source category identities")
            if raw["source_id"] != "imslp" and not work_id.startswith(raw["source_id"] + ":"):
                fail(f"work {work_id} must use a source namespace")
        sort_key = (
            str(raw["composer_en"]).casefold(),
            str(raw["title_en"]).casefold(),
            work_id,
        )
        if previous_sort_key is not None and sort_key < previous_sort_key:
            fail("works must use deterministic composer/title ordering")
        previous_sort_key = sort_key
        source_links += 1

    if any(observed_memberships[key] != count for key, count in category_work_counts.items()):
        fail("category work counts do not equal work memberships")
    if multisource:
        for source in payload["sources"]:
            if source.get("record_count") != sum(row["source_id"] == source["id"] for row in works):
                fail("source record count does not match catalog")
            if source.get("category_count") != sum(row["source_id"] == source["id"] for row in categories):
                fail("source category count does not match catalog")
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        fail("summary must be an object")
    expected_summary = {
        "category_count": len(categories),
        "category_record_count": sum(observed_memberships.values()),
        "unique_work_count": len(works),
    }
    for key, expected in expected_summary.items():
        if summary.get(key) != expected:
            fail(f"summary {key} does not match catalog contents")
    if multisource and summary.get("source_count") != len(source_ids):
        fail("summary source_count does not match registry")
    integrity = payload.get("integrity")
    if isinstance(integrity, dict) and integrity.get("public_score_file_links") != 0:
        fail("public score-file link count must be zero")
    return {
        "categories": len(categories),
        "category_records": sum(observed_memberships.values()),
        "unique_works": len(works),
        "source_links": source_links,
        "score_file_links": 0,
    }


def validate_search_aliases(aliases: object, catalog: Mapping[str, object]) -> None:
    if not isinstance(aliases, dict) or aliases.get("schema_version") != 1:
        fail("search aliases must use schema_version 1")
    check_forbidden(aliases, "search aliases")
    works = catalog["works"]
    known = {
        "composers": {work["composer_en"] for work in works},
        "works": {work["id"] for work in works},
    }
    for field, identities in known.items():
        groups = aliases.get(field)
        if not isinstance(groups, dict):
            fail(f"search aliases {field} must be an object")
        for identity, values in groups.items():
            if identity not in identities:
                label = "composer" if field == "composers" else "work"
                fail(f"search aliases reference unknown {label}: {identity}")
            if (not isinstance(values, list) or not values
                or any(not isinstance(value, str) or not value.strip() for value in values)
                or len(set(values)) != len(values)):
                fail(f"invalid search aliases for {identity}")


def validate_public_site(root: Path) -> dict[str, int]:
    root = root.resolve()
    entries = list(root.rglob("*"))
    if any(path.is_symlink() for path in entries):
        fail("public site must not contain symbolic links")
    files = [path for path in entries if path.is_file()]
    score_files = [path for path in files if path.suffix.casefold() in {".pdf", ".mid", ".midi", ".gpx", ".gp3", ".gp4", ".gp5", ".gp6", ".gp7", ".gp8", ".zip"}]
    if score_files:
        fail(f"public site contains score files: {score_files[0]}")
    catalog_path = root / "data/catalog.json"
    try:
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PublicSiteValidationError(f"cannot read {catalog_path}") from exc
    report = validate_payload(payload)
    try:
        aliases = json.loads((root / "data/search-aliases.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PublicSiteValidationError("cannot read public search aliases") from exc
    validate_search_aliases(aliases, payload)
    for path in files:
        if path.suffix.casefold() != ".json" or path in {catalog_path, root / "data/search-aliases.json"}:
            continue
        try:
            extra = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise PublicSiteValidationError(f"cannot read public JSON: {path}") from exc
        check_forbidden(extra, path.relative_to(root).as_posix())
    for required in ("index.html", "assets/app.js", "assets/search.js", "assets/site.css"):
        if not (root / required).is_file():
            fail(f"missing public asset: {required}")
    asset_paths = [path for path in files if path.suffix.casefold() in {".html", ".js", ".css", ".svg"}]
    for path in asset_paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise PublicSiteValidationError(f"cannot read public asset: {path}") from exc
        for pattern in FORBIDDEN_TEXT:
            if pattern.search(text):
                fail(f"public asset contains a forbidden value: {path}")
        if path.suffix == ".js" and "innerHTML" in text:
            fail(f"public script must not inject catalog data with innerHTML: {path}")
    script = (root / "assets/app.js").read_text(encoding="utf-8")
    if "innerHTML" in script:
        fail("public script must not inject catalog data with innerHTML")
    if 'fetch("data/catalog.json"' not in script:
        fail("public script does not load the versioned catalog")
    hero_path = root / "assets/archive-hero.webp"
    try:
        hero_header = hero_path.read_bytes()[:12]
    except OSError as exc:
        raise PublicSiteValidationError("public hero artwork is missing") from exc
    if not (hero_header.startswith(b"RIFF") and hero_header[8:12] == b"WEBP"):
        fail("public hero artwork is not a valid WebP asset")
    favicon_path = root / "assets/favicon.png"
    try:
        favicon_header = favicon_path.read_bytes()[:8]
    except OSError as exc:
        raise PublicSiteValidationError("public favicon is missing") from exc
    if favicon_header != b"\x89PNG\r\n\x1a\n":
        fail("public favicon is not a valid PNG asset")
    report["site_bytes"] = sum(path.stat().st_size for path in files)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path("public_site"))
    args = parser.parse_args()
    print(json.dumps(validate_public_site(args.root), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
