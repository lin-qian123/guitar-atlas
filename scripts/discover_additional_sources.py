#!/usr/bin/env python
"""Discover configured expansion directories and refresh the 34-source ledger."""
from __future__ import annotations
import argparse
import concurrent.futures
import json
from pathlib import Path
from source_adapters.additional import ADAPTERS, atomic_json, utcnow

DELEGATED = {"mutopia", "boije", "guitarschool", "dga", "rism"}
RESTRICTED = {
    "freescores": "Terms 10.3 require prior written permission for substantial/repeated automated database use",
    "musescore": "Terms restrict external automated systems; current robots also denies guitar directory",
    "musicnotes": "Terms prohibit scripts/codes for automated access",
    "musopen": "Reuse is limited to personal temporary single copies; mirrors/transfer restricted; robots 403",
    "bergmann": "Commercial publisher terms restrict copying/utilization; metadata reuse partnership unresolved",
    "riam_hudleston": "Substantial archive or whole-volume downloads require prior permission",
    "gallica": "Current robots disallows query-bearing and SRU search paths; official API documentation and robot permission need reconciliation",
    "sheetmusicplus": "Commercial metadata cooperation/API and automated reuse permission not established",
    "guitarworld_cn": "Public paid/login score metadata exists; third-party corpus reuse and approved non-vocal instrument scope unresolved",
    "jitashe": "Uploader and on-site publication permissions do not establish third-party corpus reuse; scope includes vocal/electric/bass",
    "ccguitar": "Current directory is reachable; external score/metadata reuse rights and approved non-vocal instrument scope unresolved",
    "nkoda": "Subscription/app library; stable edition IDs and public metadata reuse basis not established",
    "mysongbook": "Official scores available through player only; edition metadata cooperation unresolved",
    "songsterr": "Current directory returned HTTP 103 without a catalog; automation/AI policy unresolved",
    "ultimateguitar": "Large mixed user catalog; automation, metadata reuse and approved non-vocal instrument scope unresolved",
    "eightnotes": "Modern editions copying/sharing restricted; corpus metadata reuse and premium acquisition permission unresolved",
    "internetarchive": "Official API exists, but approved institutional uploader whitelist and independent-guitar edition scope remain unestablished",
    "rischel": "Institutional sheet-music collection page exists; current dedicated collection endpoint and item IDs unresolved",
    "classicalguitarshed": "Current robots returns 403; full production usage policy cannot be acquired without access clarification",
    "tecla": "Current robots returns 403; zero-price items require checkout; no automatic access or acquisition performed",
}

def refresh_policies(root: Path):
    inventory = json.loads((root / "docs/research/2026-10-01-source-candidates.json").read_text())
    rows = []
    for candidate in inventory["candidates"]:
        sid = candidate["candidate_id"]; location = root / "sources" / sid
        row = {"source_id": sid, "name": candidate["name"], "checked_at": utcnow(),
            "status": "requires_permission", "registered": False, "scope": "candidate only; no site-wide coverage claimed",
            "directory_url": candidate["directory_url"], "metadata_policy": "unverified",
            "file_policy": "no acquisition without explicit record/edition evidence",
            "research_rights_observation": candidate["rights_observation"],
            "evidence_urls": [url for url in [candidate["directory_url"], candidate.get("sample_or_evidence_url")] if url],
            "reason": RESTRICTED.get(sid, "Source-specific production adapter establishes scope and rights separately")}
        probe = location / "probe.json"
        if probe.exists():
            data = json.loads(probe.read_text()); row["robots"] = {key: data.get(key) for key in ("robots_status", "robots_url", "robots_allowed")}
            row["entry_probe"] = {key: data.get(key) for key in ("checked_at", "directory_status", "final_url", "error")}
            if data.get("robots_status") in {401, 403} or data.get("robots_allowed") is False:
                row["status"] = "blocked"
            elif data.get("directory_status") not in {None, 200}:
                row["status"] = "unavailable"
        catalog = location / "catalog.json"
        if catalog.exists():
            data = json.loads(catalog.read_text()); row.update(status="metadata_only", metadata_policy="source-attributed factual catalog navigation",
                scope=data["snapshot"].get("scope", "see source snapshot scope"), catalog=str(catalog.relative_to(root)),
                snapshot=data["snapshot"], source_record_count=len(data["works"]), category_count=len(data["categories"]),
                category_membership_count=sum(len(work["category_ids"]) for work in data["works"]),
                reason="Production catalog discovered; PDF permission/integrity and translation evidence remain independently recorded")
            assets = [asset for work in data["works"] for asset in work.get("assets", [])]
            row["asset_status_counts"] = {status: sum(asset.get("status") == status for asset in assets)
                for status in sorted({asset.get("status", "unspecified") for asset in assets})}
            row["verified_pdf_manifest_count"] = sum(asset.get("status") == "verified" and asset.get("format", "").upper() == "PDF" for asset in assets)
            row["pending_or_restricted_assets"] = sum(asset.get("status") != "verified" for asset in assets)
            row["discovery_complete"] = data["snapshot"].get("discovery_complete", False)
            if row["verified_pdf_manifest_count"]:
                row["status"] = "implemented"
                row["reason"] = "Catalog integration includes verified local PDF manifest entries; unique physical PDFs and category instrumentation require their separate verification reports"
            if sid == "cglib": row["metadata_policy"] = "site metadata attributed under stated CC BY-SA 4.0; PDF rights remain per edition"
            if sid == "delcamp": row["file_policy"] = "Explicit individual non-commercial use allowed; redistribution prohibited; shared verifier must validate each PDF"
            row["discovery_command"] = f"python scripts/discover_additional_sources.py --root . --source {sid}" if sid in ADAPTERS else "see source-owned production entrypoint"
        elif sid in DELEGATED:
            row["reason"] = "Handled by dedicated source adapter; no completed snapshot found during this ledger refresh"
        rows.append(row)
    registered = json.loads((root / "config/sources.json").read_text())["sources"]
    known = {source["id"] for source in registered}
    for row in rows: row["registered"] = row["source_id"] in known
    document = {"schema_version": 1, "updated_at": utcnow(), "candidate_count": len(rows),
        "purpose": "Per-source metadata/discovery/file-acquisition policy ledger; not a production source registry",
        "public_export": "Source pages and factual metadata only; never score files, assets, checkout links, local paths or hashes",
        "states": {status: sum(row["status"] == status for row in rows) for status in ["implemented", "metadata_only", "blocked", "requires_permission", "unavailable"]},
        "sources": rows}
    atomic_json(root / "config/source_acquisition_policies.json", document)
    return document["states"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--source", action="append", choices=sorted(ADAPTERS))
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--refresh-policies", action="store_true")
    args = parser.parse_args(); root = args.root.resolve()
    if args.refresh_policies and not args.source:
        print(json.dumps(refresh_policies(root), ensure_ascii=False)); return
    failures = []
    def run(sid):
        try:
            result = ADAPTERS[sid](root); print(json.dumps(result, ensure_ascii=False), flush=True); return None
        except Exception as exc:
            failure = {"source_id": sid, "failed_at": utcnow(), "error": str(exc)}
            atomic_json(root / "sources" / sid / "adapter_failure.json", failure)
            print(json.dumps(failure, ensure_ascii=False), flush=True); return failure
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        for result in pool.map(run, args.source or sorted(ADAPTERS)):
            if result: failures.append(result)
    print(json.dumps({"policy_states": refresh_policies(root), "failures": failures}, ensure_ascii=False))
    if failures: raise SystemExit(1)

if __name__ == "__main__": main()
