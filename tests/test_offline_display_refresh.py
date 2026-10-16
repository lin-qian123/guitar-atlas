from __future__ import annotations

from copy import deepcopy
import json
import hashlib
import os
from pathlib import Path

import pytest

from catalog_payload import pack_payload
from catalog_sources import MUSESCORE_SYNTHETIC_SOURCE_INSTRUMENTATION
from offline_display_refresh import (
    BOUNDARY,
    build_display_refresh_receipt,
    require_fresh_full_render_report,
    validate_display_refresh,
)


def _write_index(path: Path, wrapper: dict) -> None:
    payload = json.dumps(pack_payload(wrapper), ensure_ascii=False, separators=(",", ":"))
    path.write_text(
        '<!doctype html><html><body><script type="application/json" id="offline-data">'
        + payload + '</script></body></html>',
        encoding="utf-8",
    )


def _fixture(tmp_path: Path, *, native_instrumentation=None, current_mutation=None,
             native_declarations=None, report_summary=None, report_mtime=None,
             backup_symlink=False, fingerprint_native_mismatch=False):
    (tmp_path / "backups/offline-ui").mkdir(parents=True)
    (tmp_path / "sources/musescore").mkdir(parents=True)
    summary = {"records": 2, "local_pdf_records": 1}
    native_value = (MUSESCORE_SYNTHETIC_SOURCE_INSTRUMENTATION
                    if native_instrumentation is None else native_instrumentation)
    native = {
        "schema_version": 1,
        "source_id": "musescore",
        "works": [{
            "id": "musescore:123",
            "metadata": {
                "instrumentation": native_value,
                "source_instruments": (native_declarations if native_declarations is not None else
                                        [{"name": "Guitar", "count": 1}, {"name": "Piano", "count": 1}]),
            },
        }],
    }
    native_path = tmp_path / "sources/musescore/catalog.json"
    native_path.write_text(json.dumps(native, ensure_ascii=False), encoding="utf-8")
    native_sha = hashlib.sha256(native_path.read_bytes()).hexdigest()
    backup_wrapper = {
        "data": {
            "works": [
                {"id": "musescore:123", "source_id": "musescore", "source_record_id": "123",
                 "details": {"source_instrumentation": MUSESCORE_SYNTHETIC_SOURCE_INSTRUMENTATION,
                             "instrumentation": "2 guitars"},
                 "topic_ids": ["guitar_unspecified"], "local_editions": [{"files": [{"href": "x.pdf"}]}]},
                {"id": "classclef:1", "source_id": "classclef", "source_record_id": "1",
                 "details": {"source_instrumentation": "Guitar"}, "topic_ids": ["solo"],
                 "local_editions": [{"files": []}]},
            ],
            "offline_summary": summary,
            "offline_inputs": {"fingerprint": "stable", "inputs": {
                "sources/musescore/catalog.json": "0" * 64 if fingerprint_native_mismatch else native_sha,
            }},
        },
        "aliases": {"Guitar": ["guitar"]},
        "ranking": {"guitar": ["musescore:123"]},
    }
    current_wrapper = deepcopy(backup_wrapper)
    current_wrapper["data"]["works"][0]["details"]["source_instrumentation"] = "Guitar；Piano"
    if current_mutation:
        current_mutation(current_wrapper)

    backup_actual = tmp_path / "backups/offline-ui/full.html"
    backup_actual.write_bytes(b"placeholder")
    backup = backup_actual
    current_index = tmp_path / "index.html"
    _write_index(backup_actual, backup_wrapper)
    _write_index(current_index, current_wrapper)
    if backup_symlink:
        linked = tmp_path / "backups/offline-ui/link.html"
        linked.symlink_to(backup_actual)
        backup = linked

    report = {"records": 2, "local_pdf_records": 1, "index": str(tmp_path / "index.html")}
    if report_summary is not None:
        report = {**report_summary, "index": str(tmp_path / "index.html")}
    report_path = tmp_path / "sources/musescore/expansion-full-report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    # Preserve the original full-render time on the backup, then place the
    # report at or after it and the refreshed current index after both.
    base = 1_700_000_000_000_000_000
    os.utime(backup_actual, ns=(base, base))
    os.utime(report_path, ns=(base + 1000, base + 1000))
    os.utime(current_index, ns=(base + 2000, base + 2000))
    if report_mtime is not None:
        os.utime(report_path, ns=(report_mtime, report_mtime))

    receipt_path = tmp_path / "sources/classification/display-refresh.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt = build_display_refresh_receipt(tmp_path, report_path, backup, current_index)
    # Use a timestamp safely later than the fixture's synthetic index mtime.
    receipt["created_at"] = "2026-10-17T00:00:00+00:00"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    return tmp_path, report_path, receipt_path, backup_actual, current_index, receipt


def test_valid_exact_source_declaration_display_refresh(tmp_path):
    root, report, receipt, _, _, _ = _fixture(tmp_path)

    result = validate_display_refresh(root, report, receipt)

    assert result["status"] == "display_refresh_verified"
    assert result["boundary"] == BOUNDARY
    assert result["source_declaration_fields_changed"] == 1
    assert result["generic_native_records"] == 1
    assert result["report_summary_matches_both_payloads"] is True


@pytest.mark.parametrize("mutation", [
    lambda wrapper: wrapper["data"]["works"][0]["local_editions"][0]["files"][0].update(href="evil.pdf"),
    lambda wrapper: wrapper["data"]["works"][0].update(topic_ids=["solo"]),
    lambda wrapper: wrapper["data"]["works"][0].update(source_record_id="999"),
    lambda wrapper: wrapper["data"]["works"][0].update(source_id="classclef"),
    lambda wrapper: wrapper["aliases"].update({"other": []}),
    lambda wrapper: wrapper["data"].update(offline_inputs={"fingerprint": "changed"}),
    lambda wrapper: wrapper["data"].update(offline_summary={"records": 999}),
])
def test_rejects_any_change_outside_the_exact_display_field(tmp_path, mutation):
    root, report, receipt, *_ = _fixture(tmp_path, current_mutation=mutation)

    with pytest.raises(ValueError, match="outside exact generic MuseScore|summary|fingerprint"):
        validate_display_refresh(root, report, receipt)


def test_rejects_native_generic_mismatch(tmp_path):
    root, report, receipt, *_ = _fixture(tmp_path, native_instrumentation="Guitar (1)")

    with pytest.raises(ValueError, match="native generic-ID mapping differs|public generic MuseScore IDs"):
        validate_display_refresh(root, report, receipt)


def test_rejects_offline_fingerprint_not_bound_to_guarded_native_catalog(tmp_path):
    root, report, receipt, *_ = _fixture(tmp_path, fingerprint_native_mismatch=True)

    with pytest.raises(ValueError, match="fingerprint does not bind"):
        validate_display_refresh(root, report, receipt)


def test_rejects_changed_backup_sha_after_receipt(tmp_path):
    root, report, receipt, backup, *_ = _fixture(tmp_path)
    backup.write_bytes(backup.read_bytes() + b"changed")

    with pytest.raises(ValueError, match="offline backup SHA/size/mtime guard is stale"):
        validate_display_refresh(root, report, receipt)


def test_rejects_symlink_backup(tmp_path):
    root, report, receipt, backup, *_ = _fixture(tmp_path)
    linked = root / "backups/offline-ui/link.html"
    linked.symlink_to(backup)
    receipt_value = json.loads(receipt.read_text())
    receipt_value["backup_html"]["path"] = "backups/offline-ui/link.html"
    # Rebuild the guard through the symlink so path validation is the failing check.
    from offline_display_refresh import _guard
    receipt_value["backup_html"].update(_guard(root / receipt_value["backup_html"]["path"]))
    receipt.write_text(json.dumps(receipt_value))

    with pytest.raises(ValueError, match="must not use symlinks"):
        validate_display_refresh(root, report, receipt)


def test_rejects_full_report_older_than_preserved_backup(tmp_path):
    root, report, receipt, *_ = _fixture(tmp_path, report_mtime=1_699_999_999_000_000_000)

    with pytest.raises(ValueError, match="full-render report predates"):
        validate_display_refresh(root, report, receipt)


def test_rejects_summary_mismatch_with_full_report(tmp_path):
    root, report, receipt, *_ = _fixture(tmp_path, report_summary={"records": 999})

    with pytest.raises(ValueError, match="summary does not match"):
        validate_display_refresh(root, report, receipt)


def test_allows_exact_placeholder_removal_when_native_has_no_named_source(tmp_path):
    root, report, receipt, *_ = _fixture(
        tmp_path, native_declarations=[{"count": 3}, {"name": " "}],
        current_mutation=lambda wrapper: wrapper["data"]["works"][0]["details"].pop("source_instrumentation"),
    )

    result = validate_display_refresh(root, report, receipt)

    assert result["source_declaration_fields_omitted"] == 1
    assert result["omitted_record_ids"] == ["musescore:123"]


def test_rejects_receipt_timestamp_older_than_current_index(tmp_path):
    root, report, receipt, *_ = _fixture(tmp_path)
    value = json.loads(receipt.read_text())
    value["created_at"] = "2020-01-01T00:00:00+00:00"
    receipt.write_text(json.dumps(value))

    with pytest.raises(ValueError, match="receipt predates"):
        validate_display_refresh(root, report, receipt)


def test_default_full_render_path_keeps_strict_mtime_rule(tmp_path):
    report = tmp_path / "report.json"
    index = tmp_path / "index.html"
    report.write_text("{}")
    index.write_text("index")
    os.utime(report, ns=(1000, 1000))
    os.utime(index, ns=(2000, 2000))

    with pytest.raises(ValueError, match="predates the final offline entry"):
        require_fresh_full_render_report(report, index)
