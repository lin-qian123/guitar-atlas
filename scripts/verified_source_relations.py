"""Read-only public ID pairs from current, freshly verified PDF reuse evidence.

No paths, hashes or private acquisition fields are returned. A missing, active,
malformed or stale latest journal boundary produces no relationships. Native
IMSLP public work IDs remain unprefixed; added-source IDs remain source-scoped.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path, PurePosixPath


def verified_identical_pdf_pairs(root: Path, known_ids: set[str]) -> list[tuple[str, str]]:
    """Return exact known endpoints only, without changing files or evidence."""
    # Import at call time: the PDF parser uses the offline/export modules, and
    # this helper is also called while those modules build a public projection.
    from deduplicate_source_pdfs import regular_state, safe_path, state, verify_pdf

    root = root.absolute()
    lock_descriptor = None
    try:
        if root.is_symlink() or root.resolve() != root:
            return []
        known = {identity for identity in known_ids if isinstance(identity, str)}
        report_path = safe_path(root, "sources/objects/deduplication_report.json")
        if not report_path.exists():
            return []
        lock_path = safe_path(root, "sources/objects/.deduplication.lock")
        if lock_path.exists():
            regular_state(lock_path)
            lock_descriptor = os.open(lock_path, os.O_RDONLY | os.O_NOFOLLOW)
            # The writer holds an exclusive lock through its entire run.
            fcntl.flock(lock_descriptor, fcntl.LOCK_SH | fcntl.LOCK_NB)

        def stable_bytes(relative):
            path = safe_path(root, relative)
            before = regular_state(path)
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                if state(os.fstat(descriptor)) != before:
                    raise ValueError("evidence changed before reading")
                with os.fdopen(os.dup(descriptor), "rb") as stream:
                    body = stream.read()
                if regular_state(safe_path(root, relative)) != before or state(os.fstat(descriptor)) != before:
                    raise ValueError("evidence changed while reading")
                return body, before
            finally:
                os.close(descriptor)

        report_body, report_state = stable_bytes("sources/objects/deduplication_report.json")
        report = json.loads(report_body)
        if report.get("schema_version") != 1 or not report.get("runs"):
            return []
        run = report["runs"][-1]
        if run.get("status") != "finished" or not run.get("finished_at") or run.get("input_content_unchanged") is not True:
            return []
        inputs = run["metadata_inputs"]
        required = {"config/sources.json", "config/categories.json", "config/mixed_categories.json",
                    "config/score_exclusions.json"}
        if not isinstance(inputs, dict) or not required <= set(inputs):
            return []
        metadata, input_states = {}, {}
        for relative, entry in inputs.items():
            expected = entry["sha256"]
            if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
                return []
            body, before = stable_bytes(relative)
            if hashlib.sha256(body).hexdigest() != expected:
                return []
            metadata[relative], input_states[relative] = json.loads(body), before

        registry = metadata["config/sources.json"]
        if registry.get("schema_version") != 1:
            return []
        sources = {row["id"]: row for row in registry["sources"]}
        if len(sources) != len(registry["sources"]) or sources.get("imslp", {}).get("adapter") != "imslp_categories":
            return []
        approved_added = {identity: row for identity, row in sources.items()
                          if identity not in {"imslp", "classclef", "objects"}
                          and row.get("adapter") == "normalized_catalog"
                          and row.get("catalog") == f"sources/{identity}/catalog.json"}
        categories = [row["name"] for filename in ("categories.json", "mixed_categories.json")
                      for row in metadata[f"config/{filename}"]["categories"]]
        if len(set(categories)) != len(categories) or any(len(PurePosixPath(name).parts) != 1 or name in {".", ".."} for name in categories):
            return []
        exclusions = metadata["config/score_exclusions.json"]
        if exclusions.get("schema_version") != 1:
            return []
        excluded = {(row["category"], str(row["work_id"]), row["filename"]) for row in exclusions["entries"]}
        imslp = {}
        for category in categories:
            for row in metadata[f"{category}/metadata/score_manifest.json"]:
                identity = category, str(row["work_id"]), row["filename"]
                if identity in excluded:
                    continue
                path = f"{category}/{row['relative_path']}"
                if PurePosixPath(row["relative_path"]).parts[0] != "scores":
                    continue
                imslp[(*identity, path)] = (row.get("download_sha1") or row.get("sha1_imslp"),
                                          row.get("download_expected_size") or row.get("expected_size"))
        # Confirm journal source memberships against current, fingerprinted
        # catalogs. An orphan object supplies no invented work identity.
        members = set()
        for identity, source in approved_added.items():
            catalog = metadata[source["catalog"]]
            if catalog.get("schema_version") != 1 or catalog.get("source_id") != identity:
                return []
            for work in catalog["works"]:
                if not isinstance(work["id"], str) or not work["id"].startswith(identity + ":"):
                    return []
                for asset in work.get("assets", []):
                    if asset.get("status") != "verified" or asset.get("format", "").upper() != "PDF":
                        continue
                    entries = asset.get("members", []) if asset.get("container") == "ZIP" else [asset]
                    for member in entries:
                        if member.get("status", "verified") != "verified":
                            continue
                        members.add((identity, work["id"], member.get("local_path"), member.get("sha256"),
                                     member.get("size"), member.get("name")))

        pairs, file_states = set(), {}
        for action in run["actions"]:
            status = action.get("status")
            if status not in {"linked", "already_shared", "would_link"}:
                continue
            if action.get("savings_verification_errors"):
                return []
            candidate, source = action["candidate"], action["source"]
            sha, sha1, size = candidate["sha256"], candidate["sha1"], candidate["size"]
            if (not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha)
                    or not isinstance(sha1, str) or not re.fullmatch(r"[0-9a-f]{40}", sha1)
                    or type(size) is not int or size < 5 or source["sha256"] != sha
                    or source["sha1"] != sha1):
                return []
            membership = action["imslp_membership"]
            endpoint = str(membership["work_id"])
            key = membership["category"], endpoint, membership["filename"], source["path"]
            if imslp.get(key) != (sha1, size) or membership["path"] != source["path"]:
                return []
            expected_source = action["source_after"] if status == "linked" else source
            if expected_source["path"] != source["path"] or expected_source["sha256"] != sha or expected_source["sha1"] != sha1:
                return []
            fresh_source = verify_pdf(root, source["path"], sha1, size, sha)
            if fresh_source["state"] != expected_source["state"]:
                return []
            file_states[source["path"]] = fresh_source["state"]
            pool = f"sources/objects/sha256/{sha[:2]}/{sha}.pdf"
            paths = candidate["paths"]
            targets = {row["path"]: row for row in action["targets"]}
            if candidate["pool"] != pool or pool not in paths or len(set(paths)) != len(paths) or set(paths) != set(targets):
                return []
            for relative in paths:
                if relative != pool and not any(relative == f"sources/{identity}/objects/{sha}.pdf" for identity in approved_added):
                    return []
                target = targets[relative]
                if target["sha256"] != sha or target["sha1"] != sha1:
                    return []
                expected_state = expected_source["state"] if status == "linked" else target["state"]
                fresh = verify_pdf(root, relative, sha1, size, sha)
                if fresh["state"] != expected_state:
                    return []
                file_states[relative] = fresh["state"]
            for member in candidate["memberships"]:
                identity, work_id, relative = member["source_id"], member["work_id"], member["path"]
                if identity not in approved_added or relative not in paths:
                    return []
                if (identity, work_id, relative, sha, size, member.get("member_name")) not in members:
                    return []
                if endpoint in known and work_id in known and endpoint != work_id:
                    pairs.add(tuple(sorted((endpoint, work_id))))
        # Close the snapshot boundary after PDF parsing; reject concurrent drift.
        if regular_state(report_path) != report_state:
            return []
        for relative, expected in {**input_states, **file_states}.items():
            if regular_state(safe_path(root, relative)) != expected:
                return []
        return sorted(pairs)
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError, subprocess.SubprocessError):
        return []
    finally:
        if lock_descriptor is not None:
            os.close(lock_descriptor)
