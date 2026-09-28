"""Reuse approved IMSLP bytes for identical ClassClef objects; dry-run by default.

Only metadata SHA-1/size candidates are read. Every replacement additionally
requires fresh PDF parsing, SHA-1, size and SHA-256 agreement on both files.
No source metadata or legacy paths are rewritten. Run with collectors stopped.
The append-only run history is private and must stay outside public_site/.
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
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from render_offline_site import validate_readable_pdf


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def state(details: os.stat_result) -> dict:
    return {"device": details.st_dev, "inode": details.st_ino,
            "size": details.st_size, "mtime_ns": details.st_mtime_ns,
            "ctime_ns": details.st_ctime_ns, "mode": stat.S_IMODE(details.st_mode),
            "links": details.st_nlink}


def safe_path(root: Path, relative: str) -> Path:
    parts = PurePosixPath(relative)
    if not relative or parts.is_absolute() or ".." in parts.parts or "\\" in relative:
        raise ValueError("unsafe relative path")
    path = root
    for part in parts.parts:
        path /= part
        if path.is_symlink():
            raise ValueError(f"symlink is not eligible: {relative}")
    return path


def regular_state(path: Path) -> dict:
    details = path.lstat()
    if not stat.S_ISREG(details.st_mode):
        raise ValueError(f"not a regular file: {path}")
    return state(details)


def digest_key(sha1: object, size: object) -> tuple[str, int]:
    if not isinstance(sha1, str) or not re.fullmatch(r"[0-9a-f]{40}", sha1):
        raise ValueError("missing or malformed SHA-1")
    if type(size) is not int or size < 5:
        raise ValueError("missing or malformed expected size")
    return sha1, size


def load_candidates(root: Path) -> tuple[list[dict], dict, dict, list[dict]]:
    """Read approved metadata only; do not trust a prior candidate report."""
    inputs = {}

    def read(relative):
        path = safe_path(root, relative)
        before = regular_state(path)
        value = json.loads(path.read_text(encoding="utf-8"))
        if regular_state(path) != before:
            raise ValueError(f"metadata changed while reading: {relative}")
        inputs[relative] = before
        return value

    categories = [row for filename in ("categories.json", "mixed_categories.json")
                  for row in read(f"config/{filename}")["categories"]]
    review = read("config/score_exclusions.json")
    if review.get("schema_version") != 1:
        raise ValueError("invalid score exclusions schema")
    excluded = {(row["category"], str(row["work_id"]), row["filename"])
                for row in review["entries"]}
    legacy, newer = collections.defaultdict(list), collections.defaultdict(list)
    errors, seen_categories = [], set()
    counts = collections.Counter(approved_categories=len(categories))
    for category in categories:
        name = category["name"]
        if (not isinstance(name, str) or len(PurePosixPath(name).parts) != 1
                or name in (".", "..") or name in seen_categories):
            raise ValueError("invalid or repeated approved category")
        seen_categories.add(name)
        for row in read(f"{name}/metadata/score_manifest.json"):
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
                local_path = f"{name}/{relative}"
                safe_path(root, local_path)
            except (ValueError, KeyError, IndexError, TypeError) as exc:
                errors.append({"source": "imslp", "category": name,
                               "filename": row.get("filename"), "error": str(exc)})
                continue
            legacy[key].append({"path": local_path, "category": name,
                                "work_id": str(row["work_id"]), "filename": row["filename"],
                                "file_id": row.get("file_id")})
    catalog = read("sources/classclef/catalog.json")
    if catalog.get("schema_version") != 1 or catalog.get("source_id") != "classclef":
        raise ValueError("invalid ClassClef catalog identity")
    for work in catalog["works"]:
        for asset in work.get("assets", []):
            if asset.get("status") != "verified" or asset.get("format") != "PDF":
                continue
            members = asset.get("members", []) if asset.get("container") == "ZIP" else [asset]
            for member in members:
                if asset.get("storage_source") == "imslp":
                    counts["known_imslp_reuse_members"] += 1
                    continue
                try:
                    key = digest_key(member.get("sha1"), member.get("size"))
                    sha256 = member.get("sha256")
                    if not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
                        raise ValueError("missing or malformed recorded SHA-256")
                    relative = member["local_path"]
                    if relative != f"sources/classclef/objects/{sha256[:2]}/{sha256}.pdf":
                        raise ValueError("not a canonical ClassClef object path")
                    if member.get("source_sha1") not in (None, key[0]):
                        raise ValueError("published source SHA-1 disagrees with stored SHA-1")
                    safe_path(root, relative)
                except (ValueError, KeyError, TypeError) as exc:
                    errors.append({"source": "classclef", "work_id": work["id"],
                                   "path": member.get("local_path"), "error": str(exc)})
                    continue
                newer[key].append({"path": relative, "work_id": work["id"],
                                   "member_name": member.get("name"), "sha256": sha256})
    candidates = []
    for key in sorted(legacy.keys() & newer.keys()):
        targets = collections.defaultdict(list)
        for row in newer[key]:
            targets[row["path"]].append(row)
        for path, memberships in sorted(targets.items()):
            candidates.append({"sha1": key[0], "size": key[1], "target": path,
                               "recorded_sha256": memberships[0]["sha256"],
                               "classclef_memberships": memberships,
                               "imslp_candidates": legacy[key]})
    counts["candidate_content_keys"] = len(legacy.keys() & newer.keys())
    counts["candidate_object_paths"] = len(candidates)
    return candidates, dict(counts), inputs, errors


def verify_pdf(root: Path, relative: str, sha1: str, size: int,
               sha256: str | None = None) -> dict:
    path = safe_path(root, relative)
    before = regular_state(path)
    if before["size"] != size:
        raise ValueError("actual size does not match metadata")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        if state(os.fstat(descriptor)) != before:
            raise ValueError("file changed before hashing")
        digest1, digest256 = hashlib.sha1(), hashlib.sha256()
        with os.fdopen(os.dup(descriptor), "rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest1.update(block)
                digest256.update(block)
        if digest1.hexdigest() != sha1:
            raise ValueError("actual SHA-1 does not match metadata")
        actual = digest256.hexdigest()
        if sha256 is not None and actual != sha256:
            raise ValueError("actual SHA-256 does not match recorded ClassClef SHA-256")
        validate_readable_pdf(path)
        if (regular_state(safe_path(root, relative)) != before
                or state(os.fstat(descriptor)) != before):
            raise ValueError("file changed during validation")
        return {"path": relative, "sha1": sha1, "sha256": actual, "state": before}
    finally:
        os.close(descriptor)


def write_report(path: Path, report: dict) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def replace_with_hardlink(root: Path, action: dict, save) -> None:
    """Keep the target pathname; prepare and inspect a link before atomic replace."""
    source = safe_path(root, action["source"]["path"])
    target = safe_path(root, action["target"]["path"])
    source_before, target_before = action["source"]["state"], action["target"]["state"]
    if regular_state(source) != source_before or regular_state(target) != target_before:
        raise ValueError("file changed before linking")
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.dedup-link")
    action["temporary_path"] = temporary.relative_to(root).as_posix()
    action["status"] = "preparing_link"
    save()
    descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
    changed_mode, replaced = False, False
    try:
        if state(os.fstat(descriptor)) != source_before:
            raise ValueError("source changed before linking")
        os.link(source, temporary, follow_symlinks=False)
        linked = regular_state(temporary)
        # Creating a hardlink changes ctime and link count, but never bytes/mode.
        for key in ("device", "inode", "size", "mtime_ns", "mode"):
            if linked[key] != source_before[key]:
                raise ValueError("temporary link does not match the verified source")
        if (regular_state(safe_path(root, action["source"]["path"])) != linked
                or state(os.fstat(descriptor)) != linked):
            raise ValueError("source changed while linking")
        readonly = source_before["mode"] & ~0o222
        action["shared_mode"] = readonly
        action["status"] = "making_shared_inode_read_only"
        save()
        os.fchmod(descriptor, readonly)
        changed_mode = True
        ready = state(os.fstat(descriptor))
        if any(ready[key] != linked[key] for key in ("device", "inode", "size", "mtime_ns")):
            raise ValueError("source bytes changed before replace")
        if (regular_state(safe_path(root, action["source"]["path"])) != ready
                or regular_state(temporary) != ready
                or regular_state(safe_path(root, action["target"]["path"])) != target_before):
            raise ValueError("path changed before replace")
        action["status"] = "ready_to_replace"
        action["shared_state"] = ready
        save()
        # Recheck immediately after journaling, immediately before the mutation.
        if (regular_state(source) != ready or regular_state(temporary) != ready
                or regular_state(target) != target_before):
            raise ValueError("file changed immediately before replace")
        os.replace(temporary, target)
        replaced = True
        action["status"] = "linked"
        action["source_after"] = regular_state(source)
        action["target_after"] = regular_state(target)
        directory = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        save()
    except BaseException:
        if changed_mode and not replaced:
            os.fchmod(descriptor, source_before["mode"])
            action["source_mode_restored"] = True
        raise
    finally:
        os.close(descriptor)
        temporary.unlink(missing_ok=True)


def run(root: Path, *, apply: bool = False) -> dict:
    root = root.absolute()
    if root.is_symlink() or root.resolve() != root:
        raise ValueError("library root must not contain symlinks")
    work = safe_path(root, "work")
    work.mkdir(exist_ok=True)
    report_path = safe_path(root, "work/cross-source-deduplication.json")
    lock_path = safe_path(root, "work/.cross-source-deduplication.lock")
    lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        report = json.loads(report_path.read_text()) if report_path.exists() else {"schema_version": 1, "runs": []}
        if report.get("schema_version") != 1 or not isinstance(report.get("runs"), list):
            raise ValueError("invalid existing deduplication journal")
        candidates, counts, inputs, errors = load_candidates(root)
        result = {"started_at": timestamp(), "mode": "apply" if apply else "dry-run",
                  "method": "Fresh PDF parse, size, SHA-1 and SHA-256 on metadata candidates only; ClassClef SHA-1 is locally recorded unless the upstream publishes one.",
                  "counts": counts, "metadata_errors": errors, "actions": [],
                  "metadata_inputs": inputs, "status": "running"}
        report["runs"].append(result)
        save = lambda: write_report(report_path, report)
        save()
        for candidate in candidates:
            action = {"candidate": candidate, "status": "checking", "source_failures": []}
            result["actions"].append(action)
            try:
                target = verify_pdf(root, candidate["target"], candidate["sha1"],
                                    candidate["size"], candidate["recorded_sha256"])
                action["target"] = target
                for record in candidate["imslp_candidates"]:
                    try:
                        source = verify_pdf(root, record["path"], candidate["sha1"], candidate["size"])
                        if source["sha256"] != target["sha256"]:
                            raise ValueError("fresh SHA-256 differs across sources")
                        if source["state"]["device"] != target["state"]["device"]:
                            raise ValueError("files are on different devices")
                        action["source"] = source
                        break
                    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
                        action["source_failures"].append({"path": record["path"], "error": str(exc)})
                else:
                    raise ValueError("no eligible IMSLP file passed fresh verification")
                if source["state"]["inode"] == target["state"]["inode"]:
                    action["status"] = "already_shared"
                elif not apply:
                    action["status"] = "would_link"
                else:
                    category = PurePosixPath(source["path"]).parts[0]
                    relevant_inputs = ("config/categories.json", "config/mixed_categories.json",
                                       "config/score_exclusions.json", "sources/classclef/catalog.json",
                                       f"{category}/metadata/score_manifest.json")
                    for relative in relevant_inputs:
                        expected = inputs[relative]
                        if regular_state(safe_path(root, relative)) != expected:
                            raise ValueError(f"metadata changed; stop collectors before --apply: {relative}")
                    replace_with_hardlink(root, action, save)
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
                action["status"] = "linked_with_error" if action["status"] == "linked" else "rejected"
                action["error"] = str(exc)
            save()
        counts.update(collections.Counter(action["status"] for action in result["actions"]))
        counts["verified_reclaimable_bytes"] = sum(a["candidate"]["size"] for a in result["actions"]
                                                   if a["status"] in {"would_link", "linked", "linked_with_error"}
                                                   and a["target"]["state"]["links"] == 1)
        result["finished_at"] = timestamp()
        result["status"] = "finished"
        save()
        return result
    finally:
        os.close(lock_fd)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--apply", action="store_true", help="Atomically replace identical ClassClef objects with IMSLP hardlinks")
    args = parser.parse_args()
    result = run(args.root, apply=args.apply)
    print(json.dumps({"mode": result["mode"], "counts": result["counts"],
                      "report": str(args.root / "work/cross-source-deduplication.json")}, ensure_ascii=False, indent=2))
    return 1 if (result["counts"].get("rejected") or result["counts"].get("linked_with_error")
                 or result["metadata_errors"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
