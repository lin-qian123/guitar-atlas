#!/usr/bin/env python
"""Reuse approved IMSLP PDFs for added-source objects; dry-run by default.

Collectors must be stopped before --apply. Fresh added-object SHA-1 and size
select candidates against approved IMSLP upstream metadata. All canonical pool
and added-source paths then require fresh SHA-256/SHA-1/size/PDF verification.
Every pathname is retained; catalogs, receipts and manifests are never edited.
ClassClef paths belong to its separate existing deduplication tool.
"""
from __future__ import annotations

import argparse
import collections
import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
from pathlib import Path, PurePosixPath

from deduplicate_source_pdfs import (
    digest_key, regular_state, replace_with_hardlink, safe_path, state,
    timestamp, verify_pdf, write_report,
)

SHA256 = re.compile(r"[0-9a-f]{64}")
ERRORS = (OSError, ValueError, RuntimeError, subprocess.SubprocessError)


class MetadataChanged(ValueError):
    pass


class Inputs:
    def __init__(self, root: Path):
        self.root, self.files = root, {}

    def read(self, relative: str):
        path = safe_path(self.root, relative)
        before = regular_state(path)
        body = path.read_bytes()
        if regular_state(path) != before:
            raise MetadataChanged(f"metadata changed while reading: {relative}")
        self.files[relative] = {"state": before, "sha256": hashlib.sha256(body).hexdigest()}
        return json.loads(body)

    def check(self):
        for relative, entry in self.files.items():
            if regular_state(safe_path(self.root, relative)) != entry["state"]:
                raise MetadataChanged(f"metadata changed; stop collectors before --apply: {relative}")

    def unchanged(self):
        try:
            self.check()
            return all(hashlib.sha256(safe_path(self.root, p).read_bytes()).hexdigest() == entry["sha256"]
                       for p, entry in self.files.items())
        except ERRORS:
            return False


def approved_imslp(inputs: Inputs, counts: collections.Counter, errors: list) -> dict:
    categories = [row for filename in ("categories.json", "mixed_categories.json")
                  for row in inputs.read(f"config/{filename}")["categories"]]
    review = inputs.read("config/score_exclusions.json")
    if review.get("schema_version") != 1:
        raise ValueError("invalid score exclusions schema")
    excluded = {(row["category"], str(row["work_id"]), row["filename"])
                for row in review["entries"]}
    counts["approved_categories"] = len(categories)
    candidates, seen = collections.defaultdict(list), set()
    for category in categories:
        name = category["name"]
        if (not isinstance(name, str) or len(PurePosixPath(name).parts) != 1
                or name in (".", "..") or "\\" in name or name in seen):
            raise ValueError("invalid or repeated approved IMSLP category")
        seen.add(name)
        for row in inputs.read(f"{name}/metadata/score_manifest.json"):
            counts["imslp_manifest_records"] += 1
            if (name, str(row["work_id"]), row["filename"]) in excluded:
                counts["excluded_imslp_records"] += 1
                continue
            try:
                key = digest_key(row.get("download_sha1") or row.get("sha1_imslp"),
                                 row.get("download_expected_size") or row.get("expected_size"))
                relative = row["relative_path"]
                if PurePosixPath(relative).parts[0] != "scores":
                    raise ValueError("IMSLP candidate is not a category score")
                path = f"{name}/{relative}"
                safe_path(inputs.root, path)
            except (ValueError, KeyError, TypeError, IndexError) as exc:
                errors.append({"source_id": "imslp", "category": name,
                               "filename": row.get("filename"), "error": str(exc)})
                continue
            candidates[key].append({"path": path, "category": name,
                                    "work_id": str(row["work_id"]),
                                    "filename": row["filename"], "file_id": row.get("file_id")})
    return candidates


def added_groups(inputs: Inputs, counts: collections.Counter, errors: list) -> dict:
    registry = inputs.read("config/sources.json")
    if registry.get("schema_version") != 1:
        raise ValueError("invalid source registry schema")
    sources, seen = [], set()
    for source in registry["sources"]:
        identity = source["id"]
        if not isinstance(identity, str) or not re.fullmatch(r"[a-z][a-z0-9_-]*", identity) or identity in seen:
            raise ValueError("invalid or repeated registered source identity")
        seen.add(identity)
        if identity in {"imslp", "classclef"} or source.get("adapter") != "normalized_catalog":
            continue
        if identity == "objects" or source.get("catalog") != f"sources/{identity}/catalog.json":
            raise ValueError("added source requires its canonical private catalog")
        sources.append(source)
    counts["approved_added_sources"] = len(sources)
    groups, blocked = {}, set()
    for source in sources:
        identity = source["id"]
        try:
            catalog = inputs.read(source["catalog"])
            if catalog.get("schema_version") != 1 or catalog.get("source_id") != identity:
                raise ValueError("invalid added catalog identity")
        except ERRORS as exc:
            errors.append({"source_id": identity, "path": source["catalog"], "error": str(exc)})
            continue
        for work in catalog["works"]:
            for asset in work.get("assets", []):
                if asset.get("status") != "verified" or asset.get("format", "").upper() != "PDF":
                    continue
                members = asset.get("members", []) if asset.get("container") == "ZIP" else [asset]
                for member in members:
                    sha = member.get("sha256")
                    try:
                        if not isinstance(sha, str) or not SHA256.fullmatch(sha):
                            raise ValueError("missing or malformed recorded SHA-256")
                        size, relative = member.get("size"), member["local_path"]
                        if type(size) is not int or size < 5:
                            raise ValueError("missing or malformed recorded size")
                        if relative != f"sources/{identity}/objects/{sha}.pdf":
                            raise ValueError("not a canonical added-source object path")
                        safe_path(inputs.root, relative)
                        group = groups.setdefault(sha, {"sha256": sha, "size": size, "memberships": []})
                        if size != group["size"]:
                            raise ValueError("same recorded SHA-256 has inconsistent sizes")
                        group["memberships"].append({
                            "source_id": identity, "work_id": work["id"], "path": relative,
                            "member_name": member.get("name"),
                            "recorded_sha1": member.get("sha1"),
                            "upstream_sha1": member.get("sha1_upstream") or member.get("source_sha1"),
                            "upstream_sha256": member.get("sha256_upstream"),
                            "upstream_expected_size": member.get("expected_size"),
                        })
                        counts["verified_added_asset_members"] += 1
                    except (ValueError, KeyError, TypeError) as exc:
                        if isinstance(sha, str) and SHA256.fullmatch(sha):
                            blocked.add(sha)
                        errors.append({"source_id": identity, "work_id": work.get("id"),
                                       "path": member.get("local_path"), "error": str(exc)})
    # A ZIP extraction interrupted before its catalog checkpoint can leave
    # valid objects without verified memberships. Scan the physical namespaces
    # as well; their SHA filenames are still checked against fresh bytes before
    # any replacement, and they never acquire invented manifest memberships.
    discovered = collections.defaultdict(set)

    def scan_directory(relative: str, prefix: str | None = None):
        try:
            directory = safe_path(inputs.root, relative)
            if not directory.exists():
                return
            if not stat.S_ISDIR(directory.lstat().st_mode):
                raise ValueError("object directory is not a regular directory")
            for path in sorted(directory.iterdir()):
                if path.suffix != ".pdf":
                    continue
                sha = path.stem
                try:
                    if not SHA256.fullmatch(sha) or prefix is not None and sha[:2] != prefix:
                        raise ValueError("noncanonical object hash filename or pool prefix")
                    local = path.relative_to(inputs.root).as_posix()
                    regular_state(safe_path(inputs.root, local))
                    discovered[sha].add(local)
                except ERRORS as exc:
                    if SHA256.fullmatch(sha):
                        blocked.add(sha)
                    errors.append({"source_id": "added", "path": str(path.relative_to(inputs.root)), "error": str(exc)})
        except ERRORS as exc:
            errors.append({"source_id": "added", "path": relative, "error": str(exc)})

    pool_directory = safe_path(inputs.root, "sources/objects/sha256")
    if pool_directory.exists():
        for prefix_directory in sorted(pool_directory.iterdir()):
            try:
                relative = prefix_directory.relative_to(inputs.root).as_posix()
                safe_path(inputs.root, relative)
                if not re.fullmatch(r"[0-9a-f]{2}", prefix_directory.name):
                    if prefix_directory.is_dir():
                        raise ValueError("noncanonical object-pool prefix directory")
                    continue
                scan_directory(relative, prefix_directory.name)
            except ERRORS as exc:
                errors.append({"source_id": "added", "path": str(prefix_directory.relative_to(inputs.root)), "error": str(exc)})
    for source in sources:
        scan_directory(f"sources/{source['id']}/objects")
    for sha, paths in discovered.items():
        if sha not in groups and sha not in blocked:
            pool = f"sources/objects/sha256/{sha[:2]}/{sha}.pdf"
            try:
                observed = regular_state(safe_path(inputs.root, pool))
                groups[sha] = {"sha256": sha, "size": observed["size"], "memberships": [],
                               "size_basis": "canonical_object_stat"}
                counts["unreferenced_content_groups"] += 1
            except ERRORS as exc:
                blocked.add(sha)
                errors.append({"source_id": "added", "sha256": sha, "error": str(exc)})
    result = {}
    for sha, group in sorted(groups.items()):
        if sha in blocked:
            continue
        pool = f"sources/objects/sha256/{sha[:2]}/{sha}.pdf"
        paths = {pool, *discovered[sha], *(row["path"] for row in group["memberships"])}
        try:
            # Include every existing canonical alias on an approved added source,
            # even if a catalog repeats it or currently has no asset membership.
            for source in sources:
                relative = f"sources/{source['id']}/objects/{sha}.pdf"
                path = safe_path(inputs.root, relative)
                if path.exists():
                    paths.add(relative)
            for relative in paths:
                regular_state(safe_path(inputs.root, relative))
        except ERRORS as exc:
            errors.append({"source_id": "added", "sha256": sha, "error": str(exc)})
            continue
        result[sha] = {**group, "size_basis": group.get("size_basis", "verified_asset_receipt"),
                       "pool": pool, "paths": sorted(paths)}
    counts["added_content_groups"] = len(result)
    counts["added_object_paths"] = sum(len(group["paths"]) for group in result.values())
    return result


def fresh_sha1(root: Path, relative: str) -> tuple[str, int]:
    path = safe_path(root, relative)
    before = regular_state(path)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        if state(os.fstat(descriptor)) != before:
            raise ValueError("object changed before SHA-1 candidate scan")
        with os.fdopen(os.dup(descriptor), "rb") as stream:
            digest = hashlib.file_digest(stream, "sha1").hexdigest()
        if regular_state(safe_path(root, relative)) != before or state(os.fstat(descriptor)) != before:
            raise ValueError("object changed during SHA-1 candidate scan")
        return digest_key(digest, before["size"])
    finally:
        os.close(descriptor)


def inode_key(verified: dict) -> tuple[int, int]:
    return verified["state"]["device"], verified["state"]["inode"]


def reclaimable(targets: list[dict], source: dict) -> list[dict]:
    objects = {}
    for target in targets:
        key = inode_key(target)
        if key == inode_key(source):
            continue
        entry = objects.setdefault(key, {"state": target["state"], "paths": []})
        if entry["state"] != target["state"]:
            raise ValueError("same old inode changed during group verification")
        entry["paths"].append(target["path"])
    for entry in objects.values():
        entry["unrepresented_links"] = entry["state"]["links"] - len(entry["paths"])
        if entry["unrepresented_links"] < 0:
            raise ValueError("old inode link count is inconsistent with its target paths")
    return list(objects.values())


def verify_group(root: Path, candidate: dict, action: dict) -> None:
    sha1, size, sha = candidate["sha1"], candidate["size"], candidate["sha256"]
    for membership in candidate["memberships"]:
        for field in ("recorded_sha1", "upstream_sha1"):
            if membership.get(field) is not None and membership[field] != sha1:
                raise ValueError(f"{field} disagrees with fresh added-object SHA-1")
        if membership.get("upstream_sha256") not in (None, sha):
            raise ValueError("published SHA-256 disagrees with recorded object identity")
        if membership.get("upstream_expected_size") not in (None, size):
            raise ValueError("published size disagrees with fresh added-object size")
    if size != candidate["recorded_size"]:
        raise ValueError("fresh added-object size disagrees with its discovery snapshot")
    targets = [verify_pdf(root, relative, sha1, size, sha) for relative in candidate["paths"]]
    action["targets"] = targets
    if len({row["state"]["device"] for row in targets}) != 1:
        raise ValueError("added target paths are on different devices")
    for record in candidate["imslp_candidates"]:
        try:
            source = verify_pdf(root, record["path"], sha1, size, sha)
            if source["state"]["device"] != targets[0]["state"]["device"]:
                raise ValueError("IMSLP and added objects are on different devices")
            action["source"], action["imslp_membership"] = source, record
            break
        except ERRORS as exc:
            action["source_failures"].append({"path": record["path"], "error": str(exc)})
    else:
        raise ValueError("no approved IMSLP file passed fresh PDF and hash verification")
    action["old_inodes"] = reclaimable(targets, action["source"])
    action["verified_reclaimable_bytes"] = sum(row["state"]["size"] for row in action["old_inodes"]
                                               if row["unrepresented_links"] == 0)


def apply_group(root: Path, action: dict, inputs: Inputs, save) -> None:
    """Each replacement is atomic; a partial group is journaled and resumable."""
    candidate, source = action["candidate"], action["source"]
    expected_source = source["state"]
    expected_targets = {row["path"]: row["state"] for row in action["targets"]}
    originals = {row["path"]: row["state"] for row in action["targets"]}
    removed = collections.Counter()
    for original in action["targets"]:
        relative = original["path"]
        inputs.check()
        if regular_state(safe_path(root, source["path"])) != expected_source:
            raise ValueError("IMSLP source changed between group replacements")
        if inode_key(original) == inode_key(source):
            action["path_actions"].append({"target": original, "status": "already_shared"})
            continue
        if regular_state(safe_path(root, relative)) != expected_targets[relative]:
            raise ValueError("added target changed between group replacements")
        fresh_source = verify_pdf(root, source["path"], candidate["sha1"], candidate["size"], candidate["sha256"])
        target = verify_pdf(root, relative, candidate["sha1"], candidate["size"], candidate["sha256"])
        if fresh_source["state"] != expected_source or target["state"] != expected_targets[relative]:
            raise ValueError("file changed before group replacement")
        path_action = {"source": fresh_source, "target": target, "status": "verified"}
        action["path_actions"].append(path_action)
        inputs.check()
        def guarded_save():
            save()
            # The existing atomic-link helper journals immediately before its
            # final replace. Revalidate approval after every journal checkpoint,
            # including ready_to_replace, rather than only before staging.
            inputs.check()
        replace_with_hardlink(root, path_action, guarded_save)
        expected_source = path_action["source_after"]
        old_key = inode_key(original)
        removed[old_key] += 1
        # Our unlink changes the remaining old inode's ctime/link count. Capture
        # only that allowed transition; bytes, mode, mtime and identity must stay.
        done = {row["target"]["path"] for row in action["path_actions"] if row["status"] == "linked"}
        for pending in action["targets"]:
            path = pending["path"]
            if path in done or inode_key(pending) == inode_key(source):
                continue
            current, before = regular_state(safe_path(root, path)), originals[path]
            for key in ("device", "inode", "size", "mtime_ns", "mode"):
                if current[key] != before[key]:
                    raise ValueError("remaining old object changed during group replacement")
            if current["links"] != before["links"] - removed[inode_key(pending)]:
                raise ValueError("remaining old inode has an unexpected link count")
            expected_targets[path] = current
    inputs.check()
    source_after = verify_pdf(root, source["path"], candidate["sha1"], candidate["size"], candidate["sha256"])
    if source_after["state"] != expected_source:
        raise ValueError("IMSLP source changed after group replacement")
    for row in action["targets"]:
        final = verify_pdf(root, row["path"], candidate["sha1"], candidate["size"], candidate["sha256"])
        if inode_key(final) != inode_key(source_after) or final["state"] != expected_source:
            raise ValueError("group did not finish on the verified IMSLP inode")
    action["source_after"] = source_after


def completed_inode_bytes(root: Path, action: dict) -> int:
    """Count an old inode once only after all its links finish and revalidate.

    Different old inodes may complete before another inode in the same content
    group fails. A partially replaced shared inode and outside links save zero.
    These are file-content bytes, not a measurement of filesystem free blocks.
    """
    linked = {row["target"]["path"]: row for row in action["path_actions"]
              if row.get("status") == "linked" and row.get("source_after") and row.get("target_after")
              and (row["source_after"]["device"], row["source_after"]["inode"])
              == (row["target_after"]["device"], row["target_after"]["inode"])}
    completed = []
    candidate = action["candidate"]
    for entry in action.get("old_inodes", []):
        if entry["unrepresented_links"] or not set(entry["paths"]) <= set(linked):
            continue
        try:
            for relative in entry["paths"]:
                final = verify_pdf(root, relative, candidate["sha1"], candidate["size"], candidate["sha256"])
                if inode_key(final) != inode_key(action["source"]):
                    raise ValueError("completed target no longer shares the verified IMSLP inode")
            completed.append(entry)
        except ERRORS as exc:
            action.setdefault("savings_verification_errors", []).append({"paths": entry["paths"], "error": str(exc)})
    action["completed_old_inodes"] = completed
    return sum(entry["state"]["size"] for entry in completed)


def run(root: Path, *, apply: bool = False) -> dict:
    root = root.absolute()
    if root.is_symlink() or root.resolve() != root:
        raise ValueError("library root must not contain symlinks")
    directory = safe_path(root, "sources/objects")
    directory.mkdir(parents=True, exist_ok=True)
    report_path = safe_path(root, "sources/objects/deduplication_report.json")
    lock_path = safe_path(root, "sources/objects/.deduplication.lock")
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        report = json.loads(report_path.read_text()) if report_path.exists() else {"schema_version": 1, "runs": []}
        if report.get("schema_version") != 1 or not isinstance(report.get("runs"), list):
            raise ValueError("invalid existing private deduplication journal")
        inputs, counts, errors = Inputs(root), collections.Counter({
            key: 0 for key in (
                "candidate_content_groups", "candidate_object_paths", "fresh_sha1_scanned_objects",
                "unmatched_added_objects", "unreferenced_content_groups", "verified_added_asset_members",
                "linked", "would_link", "already_shared", "rejected", "partial",
            )
        }), []
        legacy = approved_imslp(inputs, counts, errors)
        groups = added_groups(inputs, counts, errors)
        result = {"started_at": timestamp(), "mode": "apply" if apply else "dry-run",
                  "method": "Fresh added-object SHA-1/size selects approved IMSLP upstream candidates; all pool/source aliases require fresh SHA-256/SHA-1/size/PDF checks. No source metadata is rewritten.",
                  "counts": counts, "metadata_errors": errors, "scan_errors": [],
                  "metadata_inputs": inputs.files, "actions": [], "status": "running"}
        report["runs"].append(result)
        save = lambda: write_report(report_path, report)
        save()
        for sha, group in groups.items():
            try:
                key = fresh_sha1(root, group["pool"])
                counts["fresh_sha1_scanned_objects"] += 1
            except ERRORS as exc:
                result["scan_errors"].append({"sha256": sha, "path": group["pool"], "error": str(exc)})
                continue
            if key not in legacy:
                counts["unmatched_added_objects"] += 1
                continue
            candidate = {**group, "sha1": key[0], "size": key[1], "recorded_size": group["size"],
                         "imslp_candidates": legacy[key]}
            counts["candidate_content_groups"] += 1
            counts["candidate_object_paths"] += len(group["paths"])
            action = {"candidate": candidate, "status": "checking", "source_failures": [],
                      "path_actions": [], "saved_bytes": 0}
            result["actions"].append(action)
            stop = False
            try:
                verify_group(root, candidate, action)
                distinct = [row for row in action["targets"] if inode_key(row) != inode_key(action["source"])]
                if not distinct:
                    action["status"] = "already_shared"
                    action["path_actions"] = [{"target": row, "status": "already_shared"} for row in action["targets"]]
                elif not apply:
                    action["status"] = "would_link"
                    action["path_actions"] = [{"target": row, "status": "already_shared" if inode_key(row) == inode_key(action["source"]) else "would_link"} for row in action["targets"]]
                else:
                    apply_group(root, action, inputs, save)
                    action["status"] = "linked"
                    action["saved_bytes"] = action["verified_reclaimable_bytes"]
            except ERRORS as exc:
                action["status"] = "partial" if any(row.get("status") == "linked" for row in action["path_actions"]) else "rejected"
                action["error"] = str(exc)
                if isinstance(exc, MetadataChanged):
                    result["status"], stop = "stopped_metadata_change", True
            save()
            if stop:
                break
        counts.update(collections.Counter(action["status"] for action in result["actions"]))
        counts["completed_path_replacements"] = sum(row.get("status") == "linked" for a in result["actions"] for row in a["path_actions"])
        counts["already_shared_paths"] = sum(row.get("status") == "already_shared" for a in result["actions"] for row in a["path_actions"])
        counts["would_link_paths"] = sum(row.get("status") == "would_link" for a in result["actions"] for row in a["path_actions"])
        if apply:
            for action in result["actions"]:
                action["saved_bytes"] = completed_inode_bytes(root, action)
        counts["savings_verification_errors"] = sum(len(a.get("savings_verification_errors", [])) for a in result["actions"])
        counts["failed_groups"] = sum(a["status"] in {"rejected", "partial"} or bool(a.get("savings_verification_errors"))
                                      for a in result["actions"])
        counts["saved_bytes"] = sum(a["saved_bytes"] for a in result["actions"])
        counts["verified_reclaimable_bytes"] = sum(a.get("verified_reclaimable_bytes", 0) for a in result["actions"])
        result["input_content_unchanged"] = inputs.unchanged()
        result["savings_basis"] = "Freshly revalidated, fully replaced old inodes without unrepresented hardlinks; content bytes, not measured filesystem free blocks."
        result["finished_at"] = timestamp()
        if result["status"] == "running":
            result["status"] = "finished"
        save()
        return result
    finally:
        os.close(descriptor)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--apply", action="store_true", help="Atomically hardlink verified added-source pool/aliases to approved IMSLP files")
    args = parser.parse_args()
    result = run(args.root, apply=args.apply)
    print(json.dumps({"mode": result["mode"], "counts": result["counts"],
                      "report": str(args.root / "sources/objects/deduplication_report.json")}, ensure_ascii=False, indent=2))
    return int(bool(result["counts"]["failed_groups"] or result["metadata_errors"]
                    or result["scan_errors"] or not result["input_content_unchanged"]))


if __name__ == "__main__":
    raise SystemExit(main())
