"""Display-only refreshes must not silently reuse stale score memberships."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import render_offline_site as offline
from tests.basic_helpers import write_json, write_minimal_pdf
from tests.test_catalog_sources import add_source
from tests.test_master_index import manifest_record, offline_library, render


def payload(root: Path) -> dict:
    html = (root / "index.html").read_text()
    return json.loads(re.search(r'<script type="application/json" id="offline-data">(.*?)</script>', html, re.S)[1])


def legacy_snapshot(root: Path) -> tuple[str, dict]:
    """Emulate the deployed offline page created before fingerprints existed."""
    page = root / "index.html"
    data = payload(root)
    data["data"].pop("offline_inputs", None)
    embedded = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    text = re.sub(r'(<script type="application/json" id="offline-data">).*?(</script>)',
                  lambda match: match[1] + embedded + match[2], page.read_text(), flags=re.S)
    page.write_text(text)
    return text, data["data"]


def reject_without_replacing(root: Path, before: str) -> None:
    with pytest.raises(ValueError, match="changed|unavailable"):
        offline.refresh_display_metadata(root)
    assert (root / "index.html").read_text() == before


def test_legacy_refresh_bootstraps_exact_mapping_without_reading_pdf_bytes(tmp_path, monkeypatch):
    offline_library(tmp_path)
    raw = add_source(tmp_path)
    member = raw["works"][0]["assets"][0]
    raw["works"][0]["assets"] = [{"format": "PDF", "container": "ZIP", "status": "verified", "members": [
        {**member, "name": "Part 1.pdf"},
        {**member, "name": "Part 2.pdf"},
        {**member, "name": "Missing part.pdf", "local_path": "sources/classclef/objects/missing.pdf"},
    ]}]
    write_json(tmp_path / "sources/classclef/catalog.json", raw)
    render(tmp_path)
    old_html, old_data = legacy_snapshot(tmp_path)
    original_open = Path.open

    def guarded_open(path, *args, **kwargs):
        assert path.suffix != ".pdf", "metadata refresh must not read PDF contents"
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    monkeypatch.setattr(offline, "validate_readable_pdf", lambda path: pytest.fail("PDF parsing in metadata refresh"))
    result = offline.refresh_display_metadata(tmp_path)
    fresh = payload(tmp_path)["data"]
    assert "bootstrapped" in result["input_guard"]
    assert fresh["offline_inputs"]["schema_version"] == 1
    assert fresh["offline_summary"] == old_data["offline_summary"]
    assert [w["local_editions"] for w in fresh["works"]] == [w["local_editions"] for w in old_data["works"]]
    assert any(p.read_text() == old_html for p in (tmp_path / "backups/offline-ui").glob("*.html"))
    assert offline.refresh_display_metadata(tmp_path)["input_guard"] == "checked existing fingerprint"


@pytest.mark.parametrize("change", ["exclusion", "new_part", "missing", "size", "legacy_page", "newly_available"])
def test_legacy_bootstrap_rejects_changed_links_availability_and_exclusions(tmp_path, change):
    offline_library(tmp_path)
    manifest = tmp_path / "For guitar/metadata/score_manifest.json"
    rows = json.loads(manifest.read_text())
    score = tmp_path / "For guitar" / rows[0]["relative_path"]
    old_bytes = score.read_bytes()
    if change == "newly_available":
        score.unlink()
    render(tmp_path)
    old_html, _ = legacy_snapshot(tmp_path)
    if change == "exclusion":
        write_json(tmp_path / "config/score_exclusions.json", {"schema_version": 1, "entries": [{
            "category": "For guitar", "work_id": "42", "filename": rows[0]["filename"], "reason": "extra bass",
        }]})
    elif change == "new_part":
        rows.append(manifest_record(tmp_path, "For guitar", "scores/new part.pdf"))
        write_json(manifest, rows)
    elif change == "missing":
        score.unlink()
    elif change == "size":
        score.write_bytes(old_bytes + b"changed")
    elif change == "legacy_page":
        (tmp_path / "For guitar/index.html").unlink()
    else:
        score.write_bytes(old_bytes)
    reject_without_replacing(tmp_path, old_html)


@pytest.mark.parametrize("change", ["source_status", "archive_member", "source_size", "source_path"])
def test_legacy_bootstrap_rejects_changed_normalized_source_assets(tmp_path, change):
    offline_library(tmp_path)
    raw = add_source(tmp_path)
    render(tmp_path)
    old_html, _ = legacy_snapshot(tmp_path)
    asset = raw["works"][0]["assets"][0]
    if change == "source_status":
        asset["status"] = "not_found"
    elif change == "archive_member":
        raw["works"][0]["assets"] = [{"format": "PDF", "status": "verified", "container": "ZIP", "members": [
            {**asset, "name": "Guitar 1.pdf"}, {**asset, "name": "Guitar 2.pdf"},
        ]}]
    elif change == "source_size":
        asset["size"] += 1
    else:
        new_file = write_minimal_pdf(tmp_path / "sources/classclef/objects/other.pdf")
        asset["local_path"] = new_file.relative_to(tmp_path).as_posix()
    write_json(tmp_path / "sources/classclef/catalog.json", raw)
    reject_without_replacing(tmp_path, old_html)


@pytest.mark.parametrize("change", ["imslp_checksum", "source_checksum", "unused_exclusion"])
def test_bootstrapped_fingerprint_rejects_input_drift_even_if_links_would_match(tmp_path, change):
    offline_library(tmp_path)
    raw = add_source(tmp_path)
    render(tmp_path)
    legacy_snapshot(tmp_path)
    offline.refresh_display_metadata(tmp_path)
    before = (tmp_path / "index.html").read_text()
    if change == "imslp_checksum":
        path = tmp_path / "For guitar/metadata/score_manifest.json"
        rows = json.loads(path.read_text())
        rows[0]["sha1_imslp"] = "0" * 40
        write_json(path, rows)
    elif change == "source_checksum":
        raw["works"][0]["assets"][0]["sha256"] = "0" * 64
        write_json(tmp_path / "sources/classclef/catalog.json", raw)
    else:
        write_json(tmp_path / "config/score_exclusions.json", {"schema_version": 1, "entries": [{
            "category": "For guitar", "work_id": "absent", "filename": "absent.pdf", "reason": "reviewed exclusion",
        }]})
    reject_without_replacing(tmp_path, before)


def test_full_render_records_inputs_and_keeps_existing_exclusions_in_refresh(tmp_path):
    offline_library(tmp_path)
    rows = json.loads((tmp_path / "For guitar/metadata/score_manifest.json").read_text())
    write_json(tmp_path / "config/score_exclusions.json", {"schema_version": 1, "entries": [{
        "category": "For guitar", "work_id": "42", "filename": rows[0]["filename"], "reason": "extra bass",
    }]})
    render(tmp_path)
    before = payload(tmp_path)["data"]
    assert before["offline_inputs"]["schema_version"] == 1
    offline.refresh_display_metadata(tmp_path)
    after = payload(tmp_path)["data"]
    assert after["works"][0]["local_editions"][0] == before["works"][0]["local_editions"][0]
    assert after["works"][0]["local_editions"][0]["excluded_count"] == 1
    assert "local_href" not in after["categories"][0]
    assert (tmp_path / "For guitar" / rows[0]["relative_path"]).is_file()
