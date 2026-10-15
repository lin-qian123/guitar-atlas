#!/usr/bin/env python
"""Append exact raw metadata for newly recalled whole-MXL candidates.

Only the private expansion snapshot changes. The existing 924-record native
catalog, selected-metadata snapshot, acquisition journals and score bytes remain
untouched. New records bind to authoritative CSV locators, not matching titles.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from build_musescore_library import atomic_json
from source_adapters.pdmx import _metadata_locator
from audit_pdmx_metadata_scope import scan_metadata_archive
from audit_pdmx_mxl_scope import fingerprint


def append_candidates(snapshot: dict, selected: dict, metadata: dict) -> tuple[dict, list[str]]:
    """No old entry changes; additions require exact requested member identity."""
    if snapshot.get("status") != "complete" or metadata.get("complete") is not True:
        raise ValueError("complete frozen input snapshots are required")
    records = snapshot.get("records")
    if not isinstance(records, dict): raise ValueError("candidate records must be an object")
    if set(metadata.get("records", {})) != set(selected):
        raise ValueError("supplement does not cover exact selected native IDs")
    added = []
    for native_id, candidate in selected.items():
        expected_id, member = _metadata_locator(candidate["csv"]["metadata"])
        if expected_id != native_id or candidate["metadata_member"] != member:
            raise ValueError("supplement native ID and CSV locator disagree")
        if metadata["member_paths"].get(native_id) != member:
            raise ValueError("supplement metadata member and authoritative CSV disagree")
        if native_id in records:
            raise ValueError("supplement must not replace an existing candidate")
        added.append(native_id)
    for native_id in added:
        records[native_id] = {**selected[native_id], "metadata": metadata["records"][native_id],
            "recall_basis": "complete_mxl_archive_actual_part_instrument_or_tab_signal"}
    return snapshot, sorted(added, key=int)


def augment(root: Path) -> dict:
    root = root.resolve()
    base = root / "sources/musescore"
    target = base / "expansion/candidate-metadata.json"
    snapshot_bytes = target.read_bytes()
    snapshot = json.loads(snapshot_bytes)
    mxl_path = base / "expansion/mxl-scope.json"
    mxl_bytes = mxl_path.read_bytes()
    mxl = json.loads(mxl_bytes)
    if (mxl.get("status") not in {"complete", "complete_with_parse_or_missing_boundaries"}
            or mxl.get("archive_checksum_freshly_reverified") is not True
            or mxl["counts"].get("inspected_mxl_members") != mxl["counts"].get("unique_mxl_members")
            or mxl["counts"].get("validated_mxl_members", 0) + mxl["counts"].get("parse_failures", 0) != mxl["counts"].get("inspected_mxl_members")):
        raise ValueError("complete freshly bound full MXL scan is required before metadata supplement")
    failed_ids = {native_id for row in mxl.get("parse_failures", []) for native_id in row["source_record_ids"]}
    requested = (set(mxl["candidates"]) | failed_ids) - set(snapshot["records"])
    prior = snapshot.get("mxl_recall_supplement", {})
    if not requested and prior.get("mxl_scope_sha256") == hashlib.sha256(mxl_bytes).hexdigest():
        return {"status": "complete", "cached": True, "added_metadata_records": 0,
                "total_candidate_metadata_records": len(snapshot["records"])}
    selected = {}
    with (base / "pdmx/PDMX.csv").open(encoding="utf-8-sig", newline="") as stream:
        for line, row in enumerate(csv.DictReader(stream, strict=True), 2):
            native_id, member = _metadata_locator(row["metadata"])
            if native_id in requested:
                if native_id in selected: raise ValueError("duplicate authoritative supplement native ID")
                selected[native_id] = {"metadata_member": member, "csv_line": line, "csv": row,
                    "mxl_recall_status": "parse_failure_pending" if native_id in failed_ids else "candidate_signal"}
    if set(selected) != requested:
        raise ValueError("MXL recalled native ID absent from authoritative CSV")
    integrity = json.loads((base / "expansion/archive-integrity.json").read_text())
    if integrity.get("status") != "complete": raise ValueError("fresh archive proof required")
    metadata_path, csv_path = base / "pdmx/metadata.tar.gz", base / "pdmx/PDMX.csv"
    metadata_guard, csv_guard = integrity["files"]["metadata.tar.gz"], integrity["files"]["PDMX.csv"]
    for name, path, guard in (("metadata.tar.gz", metadata_path, metadata_guard), ("PDMX.csv", csv_path, csv_guard)):
        if fingerprint(path) != guard["stat"] or any(snapshot["input_files"][name][k] != guard[k] for k in ("bytes", "md5", "sha256")):
            raise ValueError("frozen supplement input does not match fresh checksum/stat proof")
    payloads, member_paths = {}, {}
    def visit(native_id, member, digest, payload):
        if native_id not in selected: return
        if selected[native_id]["metadata_member"] != member: raise ValueError("metadata supplement locator drift")
        selected[native_id]["metadata_member_sha256"] = digest
        payloads[native_id], member_paths[native_id] = payload, member
    scan = scan_metadata_archive(metadata_path, visit)
    if fingerprint(metadata_path) != metadata_guard["stat"] or fingerprint(csv_path) != csv_guard["stat"]:
        raise ValueError("frozen supplement inputs changed while streaming")
    metadata = {"complete": set(payloads) == requested, "records": payloads, "member_paths": member_paths,
                "counts": scan["counts"], "archive_integrity": metadata_guard}
    # Complete JSON/path/type/dup safety checks run for every archive member.
    # Native metadata payload and mirror IDs stay raw; the source adapter will
    # independently validate these fields before considering import.
    snapshot, added = append_candidates(snapshot, selected, metadata)
    snapshot["mxl_recall_supplement"] = {"status": "complete", "added_native_ids": added,
        "metadata_archive_integrity": metadata["archive_integrity"], "metadata_scan_counts": metadata["counts"],
        "mxl_scope_sha256": hashlib.sha256(mxl_bytes).hexdigest(), "mxl_archive_input": mxl["archive_input"],
        "previous_snapshot_sha256": hashlib.sha256(snapshot_bytes).hexdigest(),
        "pending_parse_failure_native_ids": sorted(failed_ids, key=int)}
    if target.read_bytes() != snapshot_bytes or mxl_path.read_bytes() != mxl_bytes:
        raise ValueError("candidate/MXL inputs changed during metadata supplementation")
    atomic_json(target, snapshot)
    return {"status": "complete", "added_metadata_records": len(added),
            "total_candidate_metadata_records": len(snapshot["records"]), "added_native_ids": added}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(augment(args.root), ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
