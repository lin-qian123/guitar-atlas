"""Validate the one permitted offline metadata-only source-display refresh.

The refresh chain pins the original full-render report and its copied HTML,
then proves that the current embedded payload differs only by replacing an
exact generic MuseScore source-instrumentation placeholder with the protected
native source declaration (or omitting the field when no declaration exists).
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from catalog_payload import unpack_payload
from catalog_sources import (MUSESCORE_SYNTHETIC_SOURCE_INSTRUMENTATION,
                             public_source_instrumentation)

BOUNDARY = "retained full score integrity, exact source declaration display refresh"
RECEIPT_SCHEMA = 1
_OFFLINE_DATA = re.compile(
    rb'<script type="application/json" id="offline-data">(.*?)</script>', re.S
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_sha(value) -> str:
    return _sha(json.dumps(value, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"), allow_nan=False).encode())


def _repo_path(root: Path, value, *, label: str, required_prefix: str | None = None) -> tuple[Path, str]:
    _require(isinstance(value, str) and value, label + " path is missing")
    supplied = Path(value)
    if supplied.is_absolute():
        try:
            relative = supplied.relative_to(root)
        except ValueError:
            raise ValueError(label + " must be inside the repository") from None
    else:
        _require(".." not in supplied.parts, label + " path must not traverse outside the repository")
        relative = supplied
    path = root / relative
    _require(path.exists() and path.is_file(), label + " is missing")
    # Refuse symlinks at every component, including links that resolve back in.
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        _require(not cursor.is_symlink(), label + " path must not use symlinks")
    _require(path.resolve(strict=True).is_relative_to(root), label + " must stay inside the repository")
    normalized = relative.as_posix()
    if required_prefix is not None:
        _require(normalized.startswith(required_prefix.rstrip("/") + "/"),
                 label + " must be inside " + required_prefix)
    return path, normalized


def _guard(path: Path) -> dict:
    before = path.stat()
    body = path.read_bytes()
    after = path.stat()
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    _require(all(getattr(before, field) == getattr(after, field) for field in fields),
             "file changed while its display-refresh guard was read: " + str(path))
    _require(len(body) == after.st_size,
             "file byte count differs from its display-refresh stat: " + str(path))
    return {"sha256": _sha(body), "size": len(body), "mtime_ns": after.st_mtime_ns}


def _decode_html(path: Path) -> dict:
    raw = path.read_bytes()
    matches = _OFFLINE_DATA.findall(raw)
    _require(len(matches) == 1, "offline HTML must contain exactly one offline-data payload")
    try:
        wrapper = unpack_payload(json.loads(matches[0]))
    except Exception as exc:
        raise ValueError("offline HTML payload cannot be decoded: " + str(exc)) from exc
    _require(isinstance(wrapper, dict) and isinstance(wrapper.get("data"), dict),
             "offline HTML contains an invalid payload wrapper")
    return wrapper


def _native_generic_ids(native: dict) -> list[str]:
    _require(native.get("source_id") == "musescore" and isinstance(native.get("works"), list),
             "current MuseScore native catalog is invalid")
    rows = {}
    for work in native["works"]:
        identity = work.get("id")
        _require(isinstance(identity, str) and identity.startswith("musescore:")
                 and identity not in rows, "native MuseScore IDs are invalid or duplicated")
        rows[identity] = work
    return sorted(identity for identity, work in rows.items()
                  if work.get("metadata", {}).get("instrumentation")
                  == MUSESCORE_SYNTHETIC_SOURCE_INSTRUMENTATION)


def _validate_exact_projection(backup_wrapper: dict, current_wrapper: dict,
                               native: dict) -> dict:
    """Return exact change counts or reject any unrelated payload mutation."""
    expected = json.loads(json.dumps(backup_wrapper, ensure_ascii=False))
    before_data = backup_wrapper["data"]
    expected_works = expected["data"].get("works")
    current_works = current_wrapper["data"].get("works")
    _require(isinstance(expected_works, list) and isinstance(current_works, list),
             "offline payload work lists are missing")
    before_rows = {row.get("id"): row for row in before_data["works"]}
    current_rows = {row.get("id"): row for row in current_works}
    _require(None not in before_rows and len(before_rows) == len(before_data["works"]),
             "backup offline IDs are invalid or duplicated")
    _require(None not in current_rows and len(current_rows) == len(current_works),
             "current offline IDs are invalid or duplicated")
    _require(set(before_rows) == set(current_rows),
             "display refresh changed offline record identities")
    native_rows = {row["id"]: row for row in native["works"]}
    public_generic_ids = sorted(
        row["id"] for row in before_data["works"]
        if row.get("source_id") == "musescore"
        and row.get("details", {}).get("source_instrumentation")
        == MUSESCORE_SYNTHETIC_SOURCE_INSTRUMENTATION
    )
    _require(public_generic_ids == _native_generic_ids(native),
             "public generic MuseScore IDs do not map exactly to native generic records")
    changed = []
    skipped_no_native_value = []
    for row in expected_works:
        identity = row["id"]
        before = before_rows[identity]
        actual = current_rows[identity]
        details = before.get("details", {})
        old = details.get("source_instrumentation")
        if old != MUSESCORE_SYNTHETIC_SOURCE_INSTRUMENTATION:
            continue
        _require(before.get("source_id") == "musescore",
                 "generic source declaration is attached to a non-MuseScore record")
        native_row = native_rows.get(identity)
        _require(native_row is not None,
                 "generic public placeholder has no exact native MuseScore identity: " + identity)
        _require(native_row.get("id") == identity
                 and native_row.get("metadata", {}).get("instrumentation")
                 == MUSESCORE_SYNTHETIC_SOURCE_INSTRUMENTATION,
                 "native exact-generic declaration does not match public identity: " + identity)
        source_record_id = before.get("source_record_id")
        _require(source_record_id == identity.split(":", 1)[1],
                 "public MuseScore native ID mapping differs: " + identity)
        projected = public_source_instrumentation(
            native_row, current=MUSESCORE_SYNTHETIC_SOURCE_INSTRUMENTATION)
        if projected is None:
            row["details"].pop("source_instrumentation", None)
            skipped_no_native_value.append(identity)
        else:
            row["details"]["source_instrumentation"] = projected
        if actual.get("details", {}).get("source_instrumentation") != old:
            changed.append(identity)
    _require(current_wrapper == expected,
             "offline payload changed outside exact generic MuseScore source declaration projection")
    return {"generic_native_records": len(_native_generic_ids(native)),
            "source_declaration_fields_changed": len(changed),
            "source_declaration_fields_omitted": len(skipped_no_native_value),
            "changed_record_ids": changed,
            "omitted_record_ids": skipped_no_native_value}


def _report_summary(report: dict, root: Path) -> dict:
    _require(isinstance(report, dict) and "index" in report,
             "full-render report lacks its index locator")
    _require("mode" not in report and "input_guard" not in report,
             "metadata-only or guarded partial report cannot replace a full-render report")
    report_index = Path(report["index"])
    if report_index.is_absolute():
        _require(report_index.resolve() == (root / "index.html").resolve(),
                 "full-render report does not identify the repository offline index")
    else:
        _require(report_index.as_posix() == "index.html",
                 "full-render report does not identify index.html")
    return {key: value for key, value in report.items() if key != "index"}


def require_fresh_full_render_report(full_report: Path, current_index: Path) -> None:
    """Preserve the strict default chronology when no refresh receipt is supplied."""
    _require(Path(full_report).stat().st_mtime_ns >= Path(current_index).stat().st_mtime_ns,
             "full-render receipt predates the final offline entry")


def build_display_refresh_receipt(root: Path, full_report: Path, backup_html: Path,
                                  current_index: Path = Path("index.html")) -> dict:
    """Build the root-owned, content-guarded receipt after the refresh completes."""
    root = Path(root).resolve()
    report_path, report_rel = _repo_path(root, str(full_report), label="full-render report")
    backup_path, backup_rel = _repo_path(root, str(backup_html), label="offline backup",
                                          required_prefix="backups/offline-ui")
    index_path, index_rel = _repo_path(root, str(current_index), label="current offline index")
    _require(index_rel == "index.html", "current offline index must be the repository index.html")
    native_path, native_rel = _repo_path(root, "sources/musescore/catalog.json",
                                          label="MuseScore native catalog")
    native = json.loads(native_path.read_bytes())
    generic_ids = _native_generic_ids(native)
    return {
        "schema_version": RECEIPT_SCHEMA,
        "status": "display_refresh_verified",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "boundary": BOUNDARY,
        "full_render_report": {"path": report_rel, **_guard(report_path)},
        "backup_html": {"path": backup_rel, **_guard(backup_path)},
        "current_index": {"path": index_rel, **_guard(index_path)},
        "native_catalog": {"path": native_rel, **_guard(native_path),
                           "generic_placeholder": MUSESCORE_SYNTHETIC_SOURCE_INSTRUMENTATION,
                           "generic_native_ids": generic_ids,
                           "generic_native_ids_sha256": _canonical_sha(generic_ids)},
    }


def validate_display_refresh(root: Path, full_report: Path, receipt_path: Path | dict) -> dict:
    """Validate a display-only refresh while retaining the original full audit."""
    root = Path(root).resolve()
    report_path, report_rel = _repo_path(root, str(full_report), label="full-render report")
    if isinstance(receipt_path, dict):
        receipt = receipt_path
    else:
        receipt_file, _ = _repo_path(root, str(receipt_path), label="display-refresh receipt")
        receipt = json.loads(receipt_file.read_bytes())
    _require(receipt.get("schema_version") == RECEIPT_SCHEMA
             and receipt.get("status") == "display_refresh_verified"
             and receipt.get("boundary") == BOUNDARY,
             "unsupported or incomplete display-refresh receipt")

    backup_guard = receipt.get("backup_html", {})
    backup_path, backup_rel = _repo_path(root, backup_guard.get("path"),
                                          label="offline backup",
                                          required_prefix="backups/offline-ui")
    index_guard = receipt.get("current_index", {})
    index_path, index_rel = _repo_path(root, index_guard.get("path"), label="current offline index")
    _require(index_rel == "index.html", "pinned current offline index must be index.html")
    native_guard = receipt.get("native_catalog", {})
    native_path, native_rel = _repo_path(root, native_guard.get("path"), label="MuseScore native catalog")
    _require(native_rel == "sources/musescore/catalog.json",
             "native generic declarations must be read from the canonical MuseScore catalog")
    _require(report_rel == receipt.get("full_render_report", {}).get("path"),
             "full-render report path differs from the pinned receipt")
    _require(report_path == _repo_path(root, receipt["full_render_report"]["path"],
                                        label="pinned full-render report")[0],
             "full-render report path mismatch")

    for label, path, guard in (("full-render report", report_path, receipt["full_render_report"]),
                               ("offline backup", backup_path, backup_guard),
                               ("current offline index", index_path, index_guard),
                               ("MuseScore native catalog", native_path, native_guard)):
        actual = _guard(path)
        _require(all(actual.get(key) == guard.get(key) for key in ("sha256", "size", "mtime_ns")),
                 label + " SHA/size/mtime guard is stale")

    _require(backup_rel.startswith("backups/offline-ui/")
             and backup_path.resolve().is_relative_to((root / "backups/offline-ui").resolve()),
             "offline backup must remain inside backups/offline-ui")
    _require(report_path.stat().st_mtime_ns >= backup_path.stat().st_mtime_ns,
             "full-render report predates the preserved full-render HTML")
    try:
        created = datetime.fromisoformat(receipt["created_at"].replace("Z", "+00:00"))
        _require(created.tzinfo is not None, "display-refresh receipt timestamp must include a timezone")
    except (KeyError, TypeError, ValueError):
        raise ValueError("display-refresh receipt timestamp is invalid") from None
    _require(int(created.timestamp() * 1_000_000_000) >= index_path.stat().st_mtime_ns,
             "display-refresh receipt predates the current offline index")

    report = json.loads(report_path.read_bytes())
    backup_wrapper = _decode_html(backup_path)
    current_wrapper = _decode_html(index_path)
    backup_summary = backup_wrapper["data"].get("offline_summary")
    current_summary = current_wrapper["data"].get("offline_summary")
    full_summary = _report_summary(report, root)
    _require(backup_summary == current_summary == full_summary,
             "full-render summary does not match both preserved and refreshed offline payloads")

    native = json.loads(native_path.read_bytes())
    _require(native_guard.get("generic_placeholder") == MUSESCORE_SYNTHETIC_SOURCE_INSTRUMENTATION,
             "receipt generic placeholder literal differs")
    native_sha = native_guard.get("sha256")
    for label, wrapper in (("preserved backup", backup_wrapper), ("current", current_wrapper)):
        inputs = wrapper["data"].get("offline_inputs", {}).get("inputs")
        _require(isinstance(inputs, dict)
                 and inputs.get("sources/musescore/catalog.json") == native_sha,
                 label + " offline fingerprint does not bind the guarded MuseScore native catalog")
    generic_ids = _native_generic_ids(native)
    _require(native_guard.get("generic_native_ids") == generic_ids
             and native_guard.get("generic_native_ids_sha256") == _canonical_sha(generic_ids),
             "receipt native generic-ID mapping differs from current guarded source")
    changes = _validate_exact_projection(backup_wrapper, current_wrapper, native)
    return {"status": "display_refresh_verified", "boundary": BOUNDARY,
            "full_render_report": report_rel, "backup_html": backup_rel,
            "current_index": index_rel, "report_summary_matches_both_payloads": True,
            "guards_fresh": True, **changes}
