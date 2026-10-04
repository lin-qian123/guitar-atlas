from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from catalog_sources import load_registry, validate_source_url
from export_public_site import build_public_catalog, PublicExportError
from render_offline_site import build_offline_catalog, checked_source_asset
from validate_public_site import validate_payload, check_forbidden, PublicSiteValidationError
from tests.basic_helpers import ROOT, write_minimal_pdf
from tests.test_public_site import make_library, write_json
from tests.test_master_index import offline_library


def test_human_scores_url_is_distinct_from_a_local_score_path() -> None:
    check_forbidden("https://andrewyork.net/scores/4inAin4.html")
    validate_source_url("https://andrewyork.net/scores/4inAin4.html", "andrewyork")
    for value in ["For guitar/scores/work.pdf", "scores/private", "https://andrewyork.net/scores/work.pdf"]:
        with pytest.raises(PublicSiteValidationError):
            check_forbidden(value)


@pytest.mark.parametrize("source_id", ["werner", "delcamp"])
def test_site_compiler_is_not_an_edition_editor(tmp_path: Path, source_id: str) -> None:
    make_library(tmp_path)
    raw = add_source(tmp_path)
    registry = json.loads((tmp_path / "config/sources.json").read_text())
    source = registry["sources"][1]
    source["id"] = source_id
    raw["source_id"] = source_id
    item = raw["works"][0]
    item["id"] = source_id + ":42"
    item["metadata"] = {"editor": "Website compiler"}
    write_json(tmp_path / "config/sources.json", registry)
    write_json(tmp_path / source["catalog"], raw)
    projected = next(row for row in build_public_catalog(tmp_path)["works"] if row["source_id"] == source_id)
    assert "editor" not in projected["details"]
    item["metadata"]["editor_evidence"] = "Explicit edition title page attribution"
    write_json(tmp_path / source["catalog"], raw)
    projected = next(row for row in build_public_catalog(tmp_path)["works"] if row["source_id"] == source_id)
    assert projected["details"]["editor"] == "Website compiler"


def add_source(root: Path) -> dict:
    registry = json.loads((ROOT / "config/sources.json").read_text())
    registry["sources"] = [row for row in registry["sources"] if row["id"] in {"imslp", "classclef"}]
    write_json(root / "config/sources.json", registry)
    path = write_minimal_pdf(root / "sources/classclef/objects/example.pdf")
    asset = {"format": "PDF", "label": "TAB", "status": "verified", "size": path.stat().st_size,
             "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "local_path": str(path.relative_to(root)),
             "source_url": "https://www.classclef.com/pdf/private.pdf"}
    data = {"schema_version": 1, "source_id": "classclef", "snapshot": {"frozen_at": "2026-09-28", "discovery_complete": True},
            "categories": [{"id": "tarrega", "name": "Francisco Tarrega", "name_zh": "塔雷加作品", "kind": "unspecified",
                            "source_url": "https://www.classclef.com/francisco-tarrega/"}],
            "works": [{"id": "classclef:42", "title_en": "Lagrima", "composer_en": "Francisco Tarrega", "title_zh": "", "composer_zh": "",
                       "source_url": "https://www.classclef.com/lagrima/", "category_ids": ["tarrega"], "formats": ["PDF", "MIDI"], "assets": [asset]}]}
    write_json(root / "sources/classclef/catalog.json", data)
    return data


def test_public_projection_preserves_source_identity_and_removes_private_assets(tmp_path: Path) -> None:
    make_library(tmp_path)
    add_source(tmp_path)
    data = build_public_catalog(tmp_path)
    assert data["schema_version"] == 2
    assert {row["id"] for row in data["works"]} == {"42", "classclef:42"}
    assert data["summary"]["source_count"] == 2
    work = next(row for row in data["works"] if row["source_id"] == "classclef")
    assert work["category_ids"] == [2]
    assert work["title_zh"] == ""
    assert work["formats"] == ["MIDI", "PDF"]
    assert data["categories"][2]["kind"] == "unspecified"
    serialized = json.dumps(data)
    for private in ["assets", "local_path", "sha256", "private.pdf", "objects/example.pdf"]:
        assert private not in serialized
    assert validate_payload(data, registry=load_registry(tmp_path))["unique_works"] == 2


@pytest.mark.parametrize("url", ["https://www.classclef.com/pdf/test.pdf", "https://www.classclef.com/midi/test.mid",
                                  "https://www.classclef.com/wp-content/x", "http://www.classclef.com/x/",
                                  "https://classclef.com.evil.test/x/", "https://user@www.classclef.com/x/",
                                  "https://www.classclef.com/x/?download=yes"])
def test_public_source_urls_exclude_downloads_and_unregistered_hosts(url: str) -> None:
    with pytest.raises(ValueError):
        validate_source_url(url, "classclef")


def test_configured_source_cannot_silently_disappear(tmp_path: Path) -> None:
    make_library(tmp_path)
    add_source(tmp_path)
    (tmp_path / "sources/classclef/catalog.json").unlink()
    with pytest.raises(PublicExportError):
        build_public_catalog(tmp_path)


def test_validator_rejects_cross_source_membership(tmp_path: Path) -> None:
    make_library(tmp_path)
    add_source(tmp_path)
    data = build_public_catalog(tmp_path)
    next(row for row in data["works"] if row["source_id"] == "classclef")["category_ids"] = [0]
    with pytest.raises(PublicSiteValidationError, match="crosses source"):
        validate_payload(data, registry=load_registry(tmp_path))


@pytest.mark.parametrize("field,value", [("title_zh", {}), ("composer_zh", None), ("formats", {}), ("formats", ["EXE"]), ("formats", ["PDF", "PDF"]), ("source_record_id", "other"), ("resource_type", {})])
def test_validator_rejects_payloads_that_cannot_be_rendered(tmp_path: Path, field: str, value: object) -> None:
    make_library(tmp_path)
    add_source(tmp_path)
    data = build_public_catalog(tmp_path)
    next(row for row in data["works"] if row["source_id"] == "classclef")[field] = value
    with pytest.raises(PublicSiteValidationError):
        validate_payload(data, registry=load_registry(tmp_path))


def test_offline_multisource_assets_are_revalidated_and_shared_content_counted_once(tmp_path: Path) -> None:
    offline_library(tmp_path)
    add_source(tmp_path)
    data, report = build_offline_catalog(tmp_path)
    assert report["pdf_records"] == 3
    assert report["downloaded"] == 3
    assert report["unique_pdf_contents"] == 1
    work = next(row for row in data["works"] if row["source_id"] == "classclef")
    assert len(work["local_editions"][0]["files"]) == 1
    assert "local_href" not in data["categories"][2]
    (tmp_path / "sources/classclef/objects/example.pdf").write_bytes(b"<html>not a score</html>")
    data, report = build_offline_catalog(tmp_path)
    assert report["downloaded"] == 2
    assert report["unavailable"] == 1


def test_offline_archive_keeps_every_valid_part_and_marks_missing_parts(tmp_path: Path) -> None:
    offline_library(tmp_path)
    raw = add_source(tmp_path)
    old = raw["works"][0]["assets"][0]
    member = {key: old[key] for key in ("local_path", "sha256", "size")}
    raw["works"][0]["assets"] = [{"format": "PDF", "container": "ZIP", "status": "verified", "label": "PDF package", "members": [
        {**member, "name": "Guitar 1.pdf"},
        {**member, "name": "Guitar 2.pdf", "local_path": "sources/classclef/objects/missing.pdf"},
    ]}]
    write_json(tmp_path / "sources/classclef/catalog.json", raw)
    data, report = build_offline_catalog(tmp_path)
    work = next(row for row in data["works"] if row["source_id"] == "classclef")
    assert work["local_editions"][0]["files"][0]["label"] == "Guitar 1.pdf"
    assert work["local_editions"][0]["unavailable_count"] == 1
    assert report["pdf_records"] == 4
    assert report["downloaded"] == 3


@pytest.mark.parametrize("relative", ["../outside.pdf", "/tmp/outside.pdf", "For guitar/scores/x.pdf"])
def test_source_assets_cannot_escape_their_storage_scope(tmp_path: Path, relative: str) -> None:
    assert checked_source_asset(tmp_path, "classclef", {"status": "verified", "format": "PDF", "local_path": relative}) is None


def test_cross_source_pdf_reuse_requires_matching_approved_manifest(tmp_path: Path) -> None:
    offline_library(tmp_path)
    manifest = tmp_path / "For guitar/metadata/score_manifest.json"
    rows = json.loads(manifest.read_text())
    rows[0]["file_id"] = "220929"
    write_json(manifest, rows)
    row = rows[0]
    relative = "For guitar/" + row["relative_path"]
    asset = {"format": "PDF", "status": "verified", "storage_source": "imslp",
             "reused_from_manifest": "For guitar/metadata/score_manifest.json",
             "imslp_file_id": "220929", "imslp_work_id": "42", "local_path": relative,
             "sha1": row["sha1_imslp"], "source_sha1": row["sha1_imslp"],
             "sha256": hashlib.sha256((tmp_path / relative).read_bytes()).hexdigest(), "size": row["expected_size"]}
    assert checked_source_asset(tmp_path, "classclef", asset)["href"].startswith("For%20guitar/scores/")
    for field, value in [("imslp_file_id", "wrong"), ("imslp_work_id", "other"),
                         ("local_path", "For guitar, violin (arr)/" + row["relative_path"]),
                         ("sha256", "0" * 64), ("source_sha1", "0" * 40),
                         ("reused_from_manifest", "../metadata/score_manifest.json")]:
        assert checked_source_asset(tmp_path, "classclef", {**asset, field: value}) is None
    write_json(tmp_path / "config/score_exclusions.json", {"schema_version": 1, "entries": [
        {"category": "For guitar", "work_id": "42", "filename": row["filename"], "reason": "reviewed exclusion"}
    ]})
    assert checked_source_asset(tmp_path, "classclef", asset) is None
