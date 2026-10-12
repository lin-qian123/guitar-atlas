#!/usr/bin/env python
"""Build the MuseScore catalog from one licensed, frozen PDMX publication.

Only Zenodo's two metadata files are acquired. MuseScore pages, score files,
private app storage and download/authentication services are never requested.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from source_adapters.pdmx import download_file, read_candidate_metadata, select_guitar_candidates


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    if path.is_symlink() or part.is_symlink():
        raise ValueError("catalog/receipt destination cannot be a symlink")
    with part.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(part, path)


def validate_config(value: dict) -> None:
    publication = {"name": "PDMX", "version": "v9", "record_id": "15571083",
                   "page": "https://zenodo.org/records/15571083", "doi": "10.5281/zenodo.15571083",
                   "dataset_license": "CC-BY-4.0"}
    if (value.get("schema_version") != 1 or value.get("source_id") != "musescore"
            or value.get("publication") != publication
            or not isinstance(value.get("scope"), str) or not value["scope"].strip()
            or not isinstance(value.get("scope_version"), str) or not value["scope_version"].strip()
            or set(value.get("files", {})) != {"PDMX.csv", "metadata.tar.gz"}):
        raise ValueError("unreviewed PDMX publication/configuration")
    for name, asset in value["files"].items():
        if type(asset.get("size")) is not int or asset["size"] <= 0:
            raise ValueError(f"invalid frozen size: {name}")
        if not isinstance(asset.get("md5"), str) or not re.fullmatch(r"[0-9a-f]{32}", asset["md5"]):
            raise ValueError(f"invalid frozen checksum: {name}")


def reject_acquired_catalog(root: Path) -> None:
    """An initial metadata import must never discard acquired PDF evidence."""
    message = ("metadata-only rebuild would discard MuseScore PDF acquisition evidence and reviewed metadata; "
               "existing files preserved. Use scripts/acquire_musescore_pdfs.py instead")
    journal = root / "sources/musescore/pdmx/pdf-extraction.json"
    # A journal can protect an interrupted scan even before the catalog contains
    # verified assets. Unreadable, partial or unsafe journals must also fail closed.
    if journal.exists() or journal.is_symlink():
        raise ValueError(message)
    path = root / "sources/musescore/catalog.json"
    if not path.is_file():
        return
    catalog = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(catalog, dict):
        raise ValueError("existing MuseScore catalog must be an object; preserved without changes")
    if any(isinstance(asset, dict) and str(asset.get("format", "")).upper() == "PDF"
           and asset.get("status") == "verified"
           for work in catalog.get("works", []) if isinstance(work, dict)
           for asset in work.get("assets", [])):
        raise ValueError(message)


def build(root: Path, *, acquire_metadata: bool = False) -> dict:
    from source_adapters.musescore import convert_record

    root = root.resolve()
    configuration = root / "config/musescore_pdmx.json"
    cache = root / "sources/musescore/pdmx"
    for path in (configuration, cache, root / "sources/musescore/catalog.json",
                 root / "sources/musescore/import-report.json"):
        if not path.resolve().is_relative_to(root):
            raise ValueError("PDMX inputs and outputs must remain inside the project root")
    reject_acquired_catalog(root)
    config_bytes = configuration.read_bytes()
    config = json.loads(config_bytes)
    validate_config(config)
    receipts = {}
    for name, asset in config["files"].items():
        path = cache / name
        if not acquire_metadata and not path.is_file():
            raise ValueError(f"missing metadata: {name}; use --acquire-metadata")
        if not acquire_metadata:
            digest = hashlib.md5(usedforsecurity=False)
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024*1024), b""):
                    digest.update(block)
            if path.stat().st_size != asset["size"] or digest.hexdigest() != asset["md5"]:
                raise ValueError(f"cached metadata integrity failed: {name}; no network request made")
        # A cached object is freshly checked by this same production verifier.
        receipts[name] = download_file(
            f"https://zenodo.org/api/records/{config['publication']['record_id']}/files/{name}/content",
            path, expected_size=asset["size"], expected_md5=asset["md5"],
            receipt_path=cache / ("csv-receipt.json" if name == "PDMX.csv" else "metadata-receipt.json"),
        )
    selection = select_guitar_candidates(cache / "PDMX.csv")
    atomic_json(cache / "selection.json", selection)
    metadata = read_candidate_metadata(cache / "metadata.tar.gz", selection["candidates"],
                                       receipt=receipts["metadata.tar.gz"])
    atomic_json(cache / "selected-metadata.json", metadata)
    report = {
        "schema_version": 1, "checked_at": datetime.now(timezone.utc).isoformat(),
        "publication": config["publication"], "scope": config["scope"],
        "selection_counts": selection["counts"], "selection_exclusions": selection["exclusion_counts"],
        "metadata_counts": metadata["counts"], "metadata_complete": metadata["complete"],
        "pending_metadata_ids": metadata["pending_ids"], "files": receipts,
        "live_source_requests": 0, "score_files_acquired": 0,
    }
    if not metadata["complete"]:
        atomic_json(root / "sources/musescore/import-report.json", report)
        raise ValueError("incomplete frozen metadata; existing catalog preserved")
    works, exclusions, seen = [], [], set()
    for candidate in selection["candidates"]:
        identity = candidate["source_record_id"]
        if identity in seen:
            raise ValueError("duplicate native score identity in candidate rows")
        seen.add(identity)
        record, reason = convert_record(candidate["csv"], metadata["records"][identity])
        if record is None:
            exclusions.append({"source_record_id": identity, "csv_line": candidate["csv_line"],
                               "metadata_member": candidate["metadata_member"], "reason": reason})
        else:
            if record["id"] != "musescore:" + identity:
                raise ValueError("converted native identity drift")
            works.append(record)
    if not works:
        raise ValueError("no accepted records; an empty source cannot be registered")
    report.update(accepted_records=len(works), excluded_candidates=len(exclusions),
                  exclusion_counts=dict(Counter(row["reason"] for row in exclusions)), exclusions=exclusions,
                  instrumentation_counts=dict(Counter(row["metadata"]["instrumentation"] for row in works)))
    catalog = {
        "schema_version": 1, "source_id": "musescore",
        "snapshot": {
            "frozen_at": receipts["PDMX.csv"]["completed_at"], "discovery_complete": True,
            "scope": config["scope"], "scope_version": config["scope_version"],
            "directory_url": "https://musescore.com/sheetmusic/guitar",
            "snapshot_basis": "PDMX v9 author-published metadata; live MuseScore availability unverified",
            "publication": config["publication"], "configuration_sha256": hashlib.sha256(config_bytes).hexdigest(),
            "metadata_license": "CC BY 4.0; PDMX v9, Long, Novack, McAuley and Berg-Kirkpatrick; DOI 10.5281/zenodo.15571083",
            "metadata_checksums": {name: receipt["sha256"] for name, receipt in receipts.items()},
            "frozen_dataset_row_count": selection["counts"]["dataset_rows"],
            "candidate_count": len(selection["candidates"]), "accepted_record_count": len(works),
            "excluded_candidate_count": len(exclusions), "live_source_coverage_complete": False,
        },
        "categories": [{"id": "guitar", "name": "Guitar", "kind": "unspecified",
                        "source_url": "https://musescore.com/sheetmusic/guitar"}],
        "works": sorted(works, key=lambda row: int(row["id"].split(":", 1)[1])),
        "summary": {"source_records": len(works), "verified_local_pdfs": 0,
                    "scope": "PDMX v9 reviewed guitar metadata subset"},
    }
    atomic_json(root / "sources/musescore/import-report.json", report)
    atomic_json(root / "sources/musescore/catalog.json", catalog)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--acquire-metadata", action="store_true")
    args = parser.parse_args()
    report = build(args.root, acquire_metadata=args.acquire_metadata)
    print(json.dumps({key: report[key] for key in ("selection_counts", "accepted_records",
                                                  "excluded_candidates", "exclusion_counts",
                                                  "instrumentation_counts", "score_files_acquired")},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
