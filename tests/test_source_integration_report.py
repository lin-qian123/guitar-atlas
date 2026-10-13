"""Current integration receipts must never replay historical human logs."""
import hashlib
import json
import subprocess
import sys
import os

import pytest

from export_public_site import build_public_catalog
import report_source_expansion as reporting
from tests.basic_helpers import ROOT
from tests.test_public_site import make_musescore_library, write_json


def fixture(root):
    make_musescore_library(root)
    catalog = build_public_catalog(root)
    write_json(root / "public_site/data/catalog.json", catalog)
    write_json(root / "config/source_acquisition_policies.json", {"schema_version": 1, "sources": []})
    human = root / "docs/research/2026-10-01-integration-log.md"
    human.parent.mkdir(parents=True)
    human.write_text("Original integration evidence\n\nMuseScore supplement retained.\n")
    directory = root / "sources/musescore/verification"
    inputs = {"offline_report": directory / "offline.json",
              "translation_audit": directory / "translation-audit.json",
              "catalog_parity": directory / "catalog-parity.json"}
    write_json(inputs["offline_report"], {"pdf_records": 7, "downloaded": 5, "unavailable": 2,
                                        "unique_pdf_contents": 4})
    write_json(inputs["translation_audit"], {"ready": True, "pending": [], "retained": [],
                                           "coverage": {"musescore": {"records": 1}}})
    write_json(inputs["catalog_parity"], {"ready": True, "current_marker": "fresh exact projection"})
    old = root / "work/source-expansion/2026-10-01"
    write_json(old / "offline-verification.json", {"pdf_records": 1, "downloaded": 0, "unavailable": 1})
    write_json(old / "translation-audit.json", {"ready": False, "pending": [{"old": True}],
                                               "retained": [], "coverage": {}})
    write_json(old / "catalog-parity.json", {"old_marker": "obsolete"})
    return human, inputs, root / "sources/musescore/source-integration-report.json"


def test_explicit_machine_receipt_uses_current_inputs_preserves_human_and_old_receipt(tmp_path):
    human, inputs, output = fixture(tmp_path)
    old_output = tmp_path / "work/source-expansion/2026-10-01/integration-report.json"
    write_json(old_output, {"historical_receipt": "preserve"})
    before_human, before_old = human.read_bytes(), old_output.read_bytes()
    result = reporting.report(tmp_path, machine_only=True, output_report=output, **inputs)
    assert result["offline_verification"]["pdf_records"] == 7
    assert result["translation_audit"]["ready"] is True
    assert result["catalog_parity"]["current_marker"] == "fresh exact projection"
    assert json.loads(output.read_text()) == result
    assert human.read_bytes() == before_human
    assert old_output.read_bytes() == before_old
    for key, path in inputs.items():
        assert result["input_reports"][key]["path"] == path.relative_to(tmp_path).as_posix()
        assert result["input_reports"][key]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert result["validation"] == {}


@pytest.mark.parametrize("missing", ["offline_report", "translation_audit", "catalog_parity", "output_report"])
def test_machine_mode_requires_all_explicit_paths_before_writing(tmp_path, missing):
    human, inputs, output = fixture(tmp_path)
    arguments = {**inputs, "output_report": output}
    arguments.pop(missing)
    before = human.read_bytes()
    with pytest.raises(ValueError, match="explicit|machine-only"):
        reporting.report(tmp_path, machine_only=True, **arguments)
    assert human.read_bytes() == before
    assert not output.exists()
    assert not (tmp_path / "work/source-expansion/2026-10-01/integration-report.json").exists()


@pytest.mark.parametrize("key", ["offline_report", "translation_audit", "catalog_parity"])
@pytest.mark.parametrize("defect", ["missing", "invalid_json", "wrong_type"])
def test_explicit_invalid_inputs_fail_before_any_report_or_human_write(tmp_path, key, defect):
    human, inputs, output = fixture(tmp_path)
    if defect == "missing":
        inputs[key].unlink()
    elif defect == "invalid_json":
        inputs[key].write_bytes(b'{"incomplete":')
    else:
        write_json(inputs[key], [])
    before = human.read_bytes()
    with pytest.raises(ValueError, match="report|audit|parity|input"):
        reporting.report(tmp_path, machine_only=True, output_report=output, **inputs)
    assert human.read_bytes() == before
    assert not output.exists()


def test_cli_accepts_current_machine_receipt_paths_without_touching_human_log(tmp_path):
    human, inputs, output = fixture(tmp_path)
    before = human.read_bytes()
    command = [sys.executable, str(ROOT / "scripts/report_source_expansion.py"), "--root", str(tmp_path),
               "--machine-only", "--output-report", str(output)]
    for key, path in inputs.items():
        command.extend(["--" + key.replace("_", "-"), str(path)])
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert output.is_file()
    assert human.read_bytes() == before


@pytest.mark.parametrize("destination", ["public_site/data/report.json", "docs/research/2026-10-01-integration-log.md"])
def test_machine_receipt_cannot_be_written_to_public_or_human_content(tmp_path, destination):
    human, inputs, _ = fixture(tmp_path)
    before = human.read_bytes()
    with pytest.raises(ValueError, match="private|JSON|json|machine-only"):
        reporting.report(tmp_path, machine_only=True, output_report=tmp_path / destination, **inputs)
    assert human.read_bytes() == before


def test_machine_receipt_cannot_overwrite_one_of_its_evidence_inputs(tmp_path):
    human, inputs, _ = fixture(tmp_path)
    before = inputs["offline_report"].read_bytes()
    with pytest.raises(ValueError, match="input|evidence"):
        reporting.report(tmp_path, machine_only=True, output_report=inputs["offline_report"], **inputs)
    assert inputs["offline_report"].read_bytes() == before


@pytest.mark.parametrize("key,field,value", [("offline_report", "downloaded", -1),
    ("offline_report", "unavailable", 99), ("translation_audit", "ready", "true"),
    ("translation_audit", "pending", {})])
def test_malformed_report_fields_are_rejected_before_output(tmp_path, key, field, value):
    human, inputs, output = fixture(tmp_path)
    contents = json.loads(inputs[key].read_text())
    contents[field] = value
    write_json(inputs[key], contents)
    before = human.read_bytes()
    with pytest.raises(ValueError, match="invalid .*report"):
        reporting.report(tmp_path, machine_only=True, output_report=output, **inputs)
    assert not output.exists()
    assert human.read_bytes() == before


def source_asset(root, format, relative, body=b"receipt inventory bytes"):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return {"format": format, "status": "verified", "local_path": relative,
            "sha256": hashlib.sha256(body).hexdigest(), "size": len(body)}


def test_format_inventory_counts_receipts_paths_and_inodes_separately_preserving_pdf_statistics(tmp_path):
    _, inputs, output = fixture(tmp_path)
    path = tmp_path / "sources/musescore/catalog.json"
    raw = json.loads(path.read_text())
    pdf = source_asset(tmp_path, "PDF", "sources/musescore/objects/score.pdf")
    raw["works"][0]["assets"] = [pdf]
    write_json(path, raw)
    before = reporting.report(tmp_path, machine_only=True, output_report=output, **inputs)
    mxl = source_asset(tmp_path, "MUSICXML", "sources/musescore/objects/score.mxl")
    mid = source_asset(tmp_path, "MIDI", "sources/musescore/objects/score.mid")
    alias = {**mid, "local_path": "sources/musescore/objects/alias.mid"}
    os.link(tmp_path / mid["local_path"], tmp_path / alias["local_path"])
    missing = {**mid, "local_path": "sources/musescore/objects/missing.mid", "sha256": "0" * 64}
    raw["works"][0]["assets"] += [mxl, {"format": "MIDI", "container": "ZIP", "status": "verified",
                                        "members": [mid, alias, missing]}, {"format": "MUSICXML", "status": "metadata_only"}]
    write_json(path, raw)
    after = reporting.report(tmp_path, machine_only=True, output_report=output, **inputs)
    old, current = before["sources"][0], after["sources"][0]
    for field in ("pdf_asset_statuses", "verified_pdf_member_records", "distinct_verified_pdf_sha256",
                  "source_object_paths", "source_object_inodes", "physical_bytes_for_source"):
        assert current[field] == old[field]
    assert after["new_object_pool"] == before["new_object_pool"]
    mxl_stats, mid_stats = current["by_format"]["MUSICXML"], current["by_format"]["MIDI"]
    assert mxl_stats["asset_statuses"] == {"verified": 1, "metadata_only": 1}
    assert mid_stats["asset_statuses"] == {"verified": 1}
    assert mid_stats["verified_member_records"] == 3
    assert mid_stats["distinct_receipt_sha256"] == 2
    assert mid_stats["source_object_paths"] == 3 and mid_stats["existing_source_object_paths"] == 2
    assert mid_stats["missing_source_object_paths"] == 1 and mid_stats["source_object_inodes"] == 1
    assert mid_stats["physical_bytes_for_source"] == mid["size"]
    assert mid_stats["content_integrity_rechecked"] is False
    assert "current filesystem stat" in mid_stats["method"]


@pytest.mark.parametrize("relative", ["../outside.mid", "/tmp/outside.mid", "sources/other/objects/score.mid", "sources/musescore/objects/../score.mid", "sources/musescore/objects\\score.mid"])
def test_format_receipts_do_not_count_unsafe_or_cross_source_paths_as_files(tmp_path, relative):
    _, inputs, output = fixture(tmp_path)
    path = tmp_path / "sources/musescore/catalog.json"
    raw = json.loads(path.read_text())
    raw["works"][0]["assets"] = [{"format": "MIDI", "status": "verified", "local_path": relative,
                                    "sha256": "0" * 64, "size": 99}]
    write_json(path, raw)
    current = reporting.report(tmp_path, machine_only=True, output_report=output, **inputs)["sources"][0]["by_format"]["MIDI"]
    assert current["verified_member_records"] == 1
    assert current["invalid_receipt_path_records"] == 1
    assert current["source_object_paths"] == current["source_object_inodes"] == current["physical_bytes_for_source"] == 0


def test_format_inventory_reports_size_drift_without_claiming_integrity_or_creating_links(tmp_path):
    _, inputs, output = fixture(tmp_path)
    path = tmp_path / "sources/musescore/catalog.json"
    raw = json.loads(path.read_text())
    row = source_asset(tmp_path, "MUSICXML", "sources/musescore/objects/score.mxl")
    row["size"] += 3
    row["sha256"] = "not a SHA"
    raw["works"][0]["assets"] = [row]
    write_json(path, raw)
    current = reporting.report(tmp_path, machine_only=True, output_report=output, **inputs)["sources"][0]["by_format"]["MUSICXML"]
    assert current["receipt_size_mismatch_records"] == 1
    assert current["invalid_receipt_sha256_records"] == 1 and current["distinct_receipt_sha256"] == 0
    assert current["content_integrity_rechecked"] is False
    assert "href" not in json.dumps(current)


def test_format_metadata_only_inventory_never_counts_existing_file_as_acquired(tmp_path):
    _, inputs, output = fixture(tmp_path)
    path = tmp_path / "sources/musescore/catalog.json"
    raw = json.loads(path.read_text())
    row = source_asset(tmp_path, "MIDI", "sources/musescore/objects/score.mid")
    row["status"] = "metadata_only"
    raw["works"][0]["assets"] = [row]
    write_json(path, raw)
    current = reporting.report(tmp_path, machine_only=True, output_report=output, **inputs)["sources"][0]["by_format"]["MIDI"]
    assert current["asset_statuses"] == current["member_statuses"] == {"metadata_only": 1}
    assert current["verified_member_records"] == current["existing_source_object_paths"] == current["physical_bytes_for_source"] == 0


def test_acquisition_journal_reference_is_separate_from_current_stat_inventory(tmp_path):
    _, inputs, output = fixture(tmp_path)
    path = tmp_path / "sources/musescore/catalog.json"
    raw = json.loads(path.read_text())
    raw["works"][0]["assets"] = [{"format": "MIDI", "status": "metadata_only"}]
    write_json(path, raw)
    journal = tmp_path / "sources/musescore/pdmx/mid-extraction.json"
    write_json(journal, {"status": "active", "counts": {"verified_records": 924}})
    current = reporting.report(tmp_path, machine_only=True, output_report=output, **inputs)["sources"][0]
    reference = current["format_acquisition_journal_references"]["MIDI"]
    assert reference["sha256"] == hashlib.sha256(journal.read_bytes()).hexdigest()
    assert "reference only" in reference["method"]
    assert current["by_format"]["MIDI"]["verified_member_records"] == 0


@pytest.mark.parametrize("defect", ["source_escape", "file_escape", "loop"])
def test_format_inventory_does_not_follow_external_or_looping_symlinks(tmp_path, defect):
    _, inputs, output = fixture(tmp_path)
    catalog = tmp_path / "sources/musescore/catalog.json"
    raw = json.loads(catalog.read_text())
    row = source_asset(tmp_path, "MIDI", "sources/musescore/objects/score.mid")
    raw["works"][0]["assets"] = [row]
    write_json(catalog, raw)
    path = tmp_path / row["local_path"]
    if defect == "source_escape":
        # The real catalog remains readable through a source directory symlink;
        # such bytes must not become in-root object-stat evidence.
        outside = tmp_path.parent / (tmp_path.name + "-source")
        catalog.parent.rename(outside)
        catalog.parent.symlink_to(outside, target_is_directory=True)
    else:
        body = path.read_bytes()
        path.unlink()
        outside = tmp_path.parent / (tmp_path.name + ".mid")
        outside.write_bytes(body)
        path.symlink_to(outside if defect == "file_escape" else path)
    current = reporting._format_inventory(tmp_path.resolve(), "musescore", [row])
    assert current["invalid_receipt_path_records"] == 1
    assert current["source_object_inodes"] == current["physical_bytes_for_source"] == 0
