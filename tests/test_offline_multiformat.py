"""Offline format entries must use verified content and existing memberships."""
from __future__ import annotations

import copy
import hashlib
import io
import zipfile
from pathlib import Path

import pytest

import render_offline_site as offline
from tests.basic_helpers import write_json, write_minimal_pdf
from tests.test_catalog_sources import add_source
from tests.test_master_index import offline_library, render
from tests.test_public_site import make_musescore_library


def format_bytes(format: str) -> bytes:
    if format == "MIDI":
        return b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x00\x60MTrk\x00\x00\x00\x04\x00\xff\x2f\x00"
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("META-INF/container.xml", '<container><rootfiles><rootfile full-path="score.xml" media-type="application/vnd.recordare.musicxml+xml"/></rootfiles></container>')
        archive.writestr("score.xml", '<score-partwise version="4.0"><part-list><score-part id="P1"><part-name>Guitar</part-name></score-part></part-list><part id="P1"><measure number="1"><note><rest/><duration>1</duration></note></measure></part></score-partwise>')
    return output.getvalue()


def asset(root: Path, format: str, content: bytes | None = None, source="classclef") -> dict:
    content = format_bytes(format) if content is None else content
    suffix = ".mxl" if format == "MUSICXML" else ".mid"
    relative = f"sources/{source}/objects/" + hashlib.sha256(content).hexdigest() + suffix
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return {"format": format, "status": "verified", "label": "PDMX exported " + format,
            "local_path": relative, "size": len(content), "sha256": hashlib.sha256(content).hexdigest()}


def add_musescore(root):
    raw = make_musescore_library(root)
    path = write_minimal_pdf(root / "sources/musescore/objects/score.pdf")
    raw["works"][0]["assets"] = [{"format": "PDF", "status": "verified", "label": "PDF",
        "local_path": path.relative_to(root).as_posix(), "size": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}]
    raw["works"][0]["formats"] = ["PDF"]
    write_json(root / "sources/musescore/catalog.json", raw)
    return raw


@pytest.mark.parametrize("format", ["MUSICXML", "MIDI"])
def test_checked_format_assets_have_explicit_format_and_safe_local_links(tmp_path, format):
    row = asset(tmp_path, format)
    score = offline.checked_source_asset(tmp_path.resolve(), "classclef", row)
    assert score == {"label": row["label"], "href": row["local_path"], "format": format, "_sha256": row["sha256"]}


@pytest.mark.parametrize("format", ["MUSICXML", "MIDI"])
@pytest.mark.parametrize("fault", ["sha", "size", "extension", "html", "wrong_format", "traversal", "symlink", "source_symlink", "pending"])
def test_no_format_link_is_emitted_for_invalid_or_unverified_bytes(tmp_path, format, fault):
    row = asset(tmp_path, format)
    path = tmp_path / row["local_path"]
    if fault == "sha":
        row["sha256"] = "0" * 64
    elif fault == "size":
        row["size"] += 1
    elif fault == "extension":
        other = path.with_suffix(".pdf")
        path.rename(other)
        row["local_path"] = other.relative_to(tmp_path).as_posix()
    elif fault in {"html", "wrong_format"}:
        content = b"<html>log in</html>" if fault == "html" else format_bytes("MIDI" if format == "MUSICXML" else "MUSICXML")
        path.write_bytes(content)
        row.update(size=len(content), sha256=hashlib.sha256(content).hexdigest())
    elif fault == "traversal":
        row["local_path"] = "sources/classclef/objects/../objects/" + path.name
    elif fault == "symlink":
        outside = tmp_path.parent / (tmp_path.name + path.suffix)
        outside.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(outside)
    elif fault == "source_symlink":
        outside = tmp_path.parent / (tmp_path.name + "-source")
        source_root = tmp_path / "sources/classclef"
        source_root.rename(outside)
        source_root.symlink_to(outside, target_is_directory=True)
    else:
        row["status"] = "pending"
    assert offline.checked_source_asset(tmp_path.resolve(), "classclef", row) is None


@pytest.mark.parametrize("fault", ["extra_traversal", "entity", "external_rootfile", "missing_rootfile"])
def test_mxl_rejects_unsafe_archive_or_xml_contents(tmp_path, fault):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        rootfile = "https://example.test/score.xml" if fault == "external_rootfile" else "score.xml"
        archive.writestr("META-INF/container.xml", f'<container><rootfiles><rootfile full-path="{rootfile}" media-type="application/vnd.recordare.musicxml+xml"/></rootfiles></container>')
        if fault != "missing_rootfile":
            xml = '<score-partwise><part-list/></score-partwise>'
            if fault == "entity":
                xml = '<!DOCTYPE score-partwise [<!ENTITY file SYSTEM "file:///etc/passwd">]><score-partwise><movement-title>&file;</movement-title><part-list/></score-partwise>'
            archive.writestr("score.xml", xml)
        if fault == "extra_traversal":
            archive.writestr("../unselected.xml", "outside")
    row = asset(tmp_path, "MUSICXML", output.getvalue())
    assert offline.checked_source_asset(tmp_path.resolve(), "classclef", row) is None


def test_unrelated_metadata_formats_keep_the_previous_pdf_only_mapping(tmp_path):
    offline_library(tmp_path)
    raw = add_source(tmp_path)
    before, report_before = offline.build_offline_catalog(tmp_path)
    raw["works"][0]["assets"].append({"format": "MIDI", "status": "metadata_only"})
    write_json(tmp_path / "sources/classclef/catalog.json", raw)
    after, report_after = offline.build_offline_catalog(tmp_path)
    assert [work["local_editions"] for work in before["works"]] == [work["local_editions"] for work in after["works"]]
    assert report_before == report_after


def test_format_config_drift_is_part_of_the_offline_fingerprint(tmp_path):
    offline_library(tmp_path)
    config = tmp_path / "config/musescore_pdmx_formats.json"
    write_json(config, {"scope": "one"})
    first = offline.offline_input_fingerprint(tmp_path)
    write_json(config, {"scope": "two"})
    assert offline.offline_input_fingerprint(tmp_path) != first


def test_multiformat_entries_preserve_pdf_counts_and_identity_and_memberships(tmp_path):
    offline_library(tmp_path)
    raw = add_musescore(tmp_path)
    before, old_report = offline.build_offline_catalog(tmp_path)
    old_work = next(work for work in before["works"] if work["source_id"] == "musescore")
    raw["works"][0]["assets"] += [asset(tmp_path, "MUSICXML", source="musescore"), asset(tmp_path, "MIDI", source="musescore")]
    raw["works"][0]["formats"] = ["PDF", "MUSICXML", "MIDI"]
    write_json(tmp_path / "sources/musescore/catalog.json", raw)
    after, report = offline.build_offline_catalog(tmp_path)
    work = next(work for work in after["works"] if work["source_id"] == "musescore")
    assert work["id"] == old_work["id"] and work["category_ids"] == old_work["category_ids"]
    assert work["local_editions"][0]["files"][0] == old_work["local_editions"][0]["files"][0]
    assert "format" not in work["local_editions"][0]["files"][0]
    assert [row.get("format", "PDF") for row in work["local_editions"][0]["files"]] == ["PDF", "MUSICXML", "MIDI"]
    for key in ("pdf_records", "downloaded", "unavailable", "unique_pdf_contents"):
        assert report[key] == old_report[key]
    assert report["by_format"]["MUSICXML"] == {"records": 1, "verified_records": 1, "unavailable": 0, "unique_contents": 1}
    assert report["by_format"]["MIDI"] == {"records": 1, "verified_records": 1, "unavailable": 0, "unique_contents": 1}
    assert report["by_format"]["PDF"]["verified_records"] == report["downloaded"]


def test_invalid_extra_format_is_reported_separately_without_pdf_unavailability(tmp_path):
    offline_library(tmp_path)
    raw = add_musescore(tmp_path)
    row = asset(tmp_path, "MIDI", b"<html>failure</html>", source="musescore")
    raw["works"][0]["assets"].append(row)
    write_json(tmp_path / "sources/musescore/catalog.json", raw)
    data, report = offline.build_offline_catalog(tmp_path)
    edition = next(work for work in data["works"] if work["source_id"] == "musescore")["local_editions"][0]
    assert len(edition["files"]) == 1 and edition["unavailable_count"] == 0
    assert edition["format_unavailable"] == {"MIDI": 1}
    assert report["unavailable"] == 0 and report["by_format"]["MIDI"]["unavailable"] == 1


def test_formats_keep_category_views_without_inflating_physical_or_record_counts(tmp_path):
    offline_library(tmp_path)
    raw = add_musescore(tmp_path)
    raw["categories"].append({**raw["categories"][0], "id": "second", "name": "Second guitar collection"})
    raw["works"][0]["category_ids"].append("second")
    raw["works"][0]["assets"] += [asset(tmp_path, "MUSICXML", source="musescore"), asset(tmp_path, "MIDI", source="musescore")]
    second = copy.deepcopy(raw["works"][0])
    second.update(id="musescore:101", source_url="https://musescore.com/user/321/scores/101")
    raw["works"].append(second)
    write_json(tmp_path / "sources/musescore/catalog.json", raw)
    data, report = offline.build_offline_catalog(tmp_path)
    works = [work for work in data["works"] if work["source_id"] == "musescore"]
    assert [work["id"] for work in works] == ["musescore:100", "musescore:101"]
    for work in works:
        assert len(work["local_editions"]) == 2
        assert work["local_editions"][0]["files"] == work["local_editions"][1]["files"]
    for format in ("MUSICXML", "MIDI"):
        assert report["by_format"][format] == {"records": 2, "verified_records": 2, "unavailable": 0, "unique_contents": 1}
    assert report["by_source"]["musescore"]["pdf_records"] == 2
    assert report["by_source"]["musescore"]["unique_pdf_contents"] == 1


def test_nonpdf_asset_changes_require_full_render_and_metadata_refresh_does_not_read_bytes(tmp_path, monkeypatch):
    offline_library(tmp_path)
    raw = add_musescore(tmp_path)
    raw["works"][0]["assets"] += [asset(tmp_path, "MUSICXML", source="musescore"), asset(tmp_path, "MIDI", source="musescore")]
    write_json(tmp_path / "sources/musescore/catalog.json", raw)
    render(tmp_path)
    original_open = Path.open
    def guarded(path, *args, **kwargs):
        assert path.suffix not in {".mxl", ".mid"}, "metadata-only refresh may not read score bytes"
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", guarded)
    offline.refresh_display_metadata(tmp_path)
    raw["works"][0]["assets"][-1]["sha256"] = "0" * 64
    write_json(tmp_path / "sources/musescore/catalog.json", raw)
    before = (tmp_path / "index.html").read_text()
    with pytest.raises(ValueError, match="inputs changed"):
        offline.refresh_display_metadata(tmp_path)
    assert (tmp_path / "index.html").read_text() == before
