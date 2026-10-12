"""Current integration receipts must never replay historical human logs."""
import hashlib
import json
import subprocess
import sys

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
