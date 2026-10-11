"""Acquire a frozen PDMX release without requesting MuseScore or score downloads.

Dataset publication, record licensing and instrumentation review remain separate.
This module retrieves approved Zenodo file endpoints and reads private evidence;
it does not register a source or produce public/offline score links.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import tarfile
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

import requests


class AccessStopped(RuntimeError):
    """The upstream returned an access challenge or requested a source stop."""


def approved_file_url(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or parsed.hostname != "zenodo.org"
            or parsed.username or parsed.password or parsed.port not in (None, 443)
            or parsed.query or parsed.fragment or "\\" in value
            or not re.fullmatch(r"/api/records/[1-9][0-9]*/files/[A-Za-z0-9][A-Za-z0-9_.-]*/content", parsed.path)
            or any(part in {".", ".."} for part in parsed.path.split("/"))):
        raise ValueError("unapproved Zenodo file endpoint")
    return value


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    if path.is_symlink() or part.is_symlink():
        raise ValueError("receipt path cannot be a symlink")
    with part.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(part, path)


def _digests(path: Path) -> tuple[int, str, str]:
    md5, sha = hashlib.md5(usedforsecurity=False), hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            size += len(block)
            md5.update(block)
            sha.update(block)
    return size, md5.hexdigest(), sha.hexdigest()


class ZenodoFileClient:
    """One reusable host clock, conservative redirects and atomic verified files."""
    def __init__(self, *, session=None, delay=10.0, clock=None, sleep=None):
        self.session = session if session is not None else requests.Session()
        self.delay = max(10.0, delay)
        self.clock = clock or time.monotonic
        self.sleep = sleep or time.sleep
        self.last_request = None
        self.lock = threading.Lock()
        self.stopped = ""

    def _request(self, url: str, headers: dict):
        for _ in range(6):
            approved_file_url(url)
            with self.lock:
                if self.stopped:
                    raise AccessStopped(self.stopped)
                if self.last_request is not None:
                    remaining = self.delay - (self.clock() - self.last_request)
                    if remaining > 0:
                        self.sleep(remaining)
                if self.stopped:
                    raise AccessStopped(self.stopped)
                self.last_request = self.clock()
                response = self.session.get(url, headers=headers, stream=True,
                                            allow_redirects=False, timeout=(15, 90))
            if response.status_code in {401, 403, 429}:
                self.stopped = f"Zenodo file acquisition stopped: HTTP {response.status_code}"
                response.close()
                raise AccessStopped(self.stopped)
            if response.status_code in {301, 302, 303, 307, 308}:
                from urllib.parse import urljoin
                target = urljoin(url, response.headers.get("Location", ""))
                response.close()
                approved_file_url(target)
                url = target
                continue
            try:
                approved_file_url(response.url)
            except ValueError:
                response.close()
                raise
            return response, url
        raise ValueError("Zenodo file redirect loop")

    def download_file(self, url, destination, *, expected_size, expected_md5, receipt_path=None):
        approved_file_url(url)
        if (type(expected_size) is not int or expected_size <= 0
                or not isinstance(expected_md5, str) or not re.fullmatch(r"[0-9a-f]{32}", expected_md5)):
            raise ValueError("expected size and upstream MD5 are required")
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        part = destination.with_name(destination.name + ".part")
        if destination.is_symlink() or part.is_symlink():
            raise ValueError("download path cannot be a symlink")

        def receipt(path, resumed_from, *, cached=False, final_url=url):
            size, md5, sha = _digests(path)
            if size != expected_size:
                raise ValueError(f"incomplete download: expected {expected_size}, received {size}")
            if md5 != expected_md5:
                raise ValueError("upstream checksum mismatch")
            return {"url": url, "final_url": final_url, "bytes": size,
                    "upstream_checksum": "md5:" + md5, "upstream_checksum_verified": True,
                    "sha256": sha, "resumed_from": resumed_from, "cached": cached,
                    "completed_at": datetime.now(timezone.utc).isoformat()}

        if destination.is_file():
            size, md5, _ = _digests(destination)
            if size == expected_size and md5 == expected_md5:
                result = receipt(destination, 0, cached=True)
                if receipt_path:
                    _atomic_json(Path(receipt_path), result)
                return result
        offset = part.stat().st_size if part.exists() else 0
        if offset > expected_size:
            raise ValueError("partial download exceeds expected size")
        if offset == expected_size:
            result = receipt(part, offset)
            os.replace(part, destination)
            if receipt_path:
                _atomic_json(Path(receipt_path), result)
            return result
        headers = {"User-Agent": "GuitarAtlas/1.0 (source-attributed guitar score catalog)",
                   "Accept-Encoding": "identity"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        response, final_url = self._request(url, headers)
        try:
            observed = {key.lower(): value for key, value in response.headers.items()}
            if observed.get("content-encoding", "identity").lower() != "identity":
                raise ValueError("encoded response cannot preserve byte ranges")
            append = False
            if response.status_code == 206 and offset:
                match = re.fullmatch(r"bytes ([0-9]+)-([0-9]+)/([0-9]+)", observed.get("content-range", ""))
                if not match or tuple(map(int, match.groups())) != (offset, expected_size-1, expected_size):
                    raise ValueError("inconsistent resumed Content-Range")
                append = True
            elif response.status_code != 200:
                raise ValueError(f"expected complete file response, HTTP {response.status_code}")
            length = expected_size-offset if append else expected_size
            if "content-length" in observed and observed["content-length"] != str(length):
                raise ValueError("response length does not match the frozen size/range")
            received = offset if append else 0
            with part.open("ab" if append else "wb") as stream:
                for block in response.iter_content(chunk_size=1024*1024):
                    if not block:
                        continue
                    if received + len(block) > expected_size:
                        raise ValueError("response exceeds frozen file size")
                    stream.write(block)
                    received += len(block)
                stream.flush()
                os.fsync(stream.fileno())
            result = receipt(part, offset if append else 0, final_url=final_url)
            os.replace(part, destination)
            if receipt_path:
                _atomic_json(Path(receipt_path), result)
            return result
        finally:
            response.close()


_DEFAULT_CLIENT = ZenodoFileClient()


def download_file(url, destination, *, expected_size, expected_md5, receipt_path=None, session=None):
    """Use a shared production request clock; injectable transport for offline tests."""
    client = _DEFAULT_CLIENT if session is None else ZenodoFileClient(session=session)
    return client.download_file(url, destination, expected_size=expected_size,
                                expected_md5=expected_md5, receipt_path=receipt_path)


_METADATA_MEMBER = re.compile(r"metadata/[0-9]+/([1-9][0-9]*)\.json")


def _metadata_locator(value: str) -> tuple[str, str]:
    """The native score ID comes from the frozen metadata locator, not its title."""
    if not isinstance(value, str):
        raise ValueError("invalid metadata locator")
    normalized = value[2:] if value.startswith("./") else value
    match = _METADATA_MEMBER.fullmatch(normalized)
    if not match:
        raise ValueError("invalid metadata locator")
    return match.group(1), normalized


def select_guitar_candidates(csv_path) -> dict:
    """Read frozen rows, retaining mixed programs for exact instrument review.

    GM programs 24/25 establish candidates only. Neither their count nor a track
    count establishes player count, acoustic construction or a final score scope.
    Ordinary non-guitar rows are counted rather than duplicated in the receipt;
    malformed rows and all excluded guitar candidates retain individual reasons.
    """
    required = {"metadata", "tracks", "n_tracks", "license", "license_conflict", "subset:no_license_conflict"}
    candidates, exclusions = [], []
    counts, rejected = Counter(), Counter()
    with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        if (not reader.fieldnames or not required.issubset(reader.fieldnames)
                or len(reader.fieldnames) != len(set(reader.fieldnames))):
            raise ValueError("PDMX CSV is missing required or has duplicate columns")
        for line, row in enumerate(reader, 2):
            counts["dataset_rows"] += 1
            native_id, member, programs, reason = "", "", [], ""
            if None in row or any(value is None for value in row.values()):
                reason = "invalid_csv_columns"
            elif not re.fullmatch(r"(?:0|[1-9][0-9]*)(?:-(?:0|[1-9][0-9]*))*", row["tracks"]):
                reason = "invalid_program_tokens"
            else:
                tokens = row["tracks"].split("-")
                programs = [int(value) for value in tokens if len(value) <= 3]
                if len(programs) != len(tokens) or any(value > 127 for value in programs):
                    reason = "invalid_program_range"
                elif not re.fullmatch(r"[1-9][0-9]*", row["n_tracks"]):
                    reason = "invalid_track_count"
                elif str(len(programs)) != row["n_tracks"]:
                    reason = "track_count_mismatch"
            guitar_program = any(value in {24, 25} for value in programs)
            if guitar_program:
                counts["guitar_program_rows"] += 1
            if not reason and not guitar_program:
                reason = "no_acoustic_guitar_program"
            if not reason:
                try:
                    native_id, member = _metadata_locator(row["metadata"])
                except ValueError:
                    reason = "invalid_metadata_locator"
            if not reason:
                if row["license_conflict"] not in {"False", "True"}:
                    reason = "invalid_license_conflict"
                elif row["subset:no_license_conflict"] not in {"False", "True"}:
                    reason = "invalid_no_conflict_subset"
                elif row["license_conflict"] != "False":
                    reason = "license_conflict"
                elif row["subset:no_license_conflict"] != "True":
                    reason = "no_conflict_subset_excluded"
                elif row["license"] not in {"publicdomain", "cc-zero"}:
                    reason = "license_outside_approved_scope"
            if reason:
                rejected[reason] += 1
                if reason != "no_acoustic_guitar_program":
                    exclusions.append({"csv_line": line, "source_record_id": native_id,
                                       "metadata_locator": row.get("metadata", ""), "reason": reason})
                continue
            counts["candidates"] += 1
            if any(value not in {24, 25} for value in programs):
                counts["mixed_program_candidates"] += 1
            candidates.append({"csv_line": line, "source_record_id": native_id, "metadata_member": member,
                               "gm_programs": programs, "review_status": "pending_score_metadata_review",
                               "csv": dict(row)})
    return {"schema_version": 1, "scope": "Frozen PDMX rows; publicdomain/cc-zero, no license conflict, GM 24/25 candidate only",
            "counts": dict(counts), "exclusion_counts": dict(rejected),
            "candidates": candidates, "exclusions": exclusions}


def _unique_json_object(pairs):
    output = {}
    for key, value in pairs:
        if key in output:
            raise ValueError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def _stream_members(archive):
    # Python 3.12 otherwise retains every TarInfo even in r|gz mode. Regular
    # current members can be read without caching the entire release directory.
    while (member := archive.next()) is not None:
        archive.members.clear()
        yield member


def read_candidate_metadata(archive_path, candidates, *, receipt=None, max_member_bytes=8*1024*1024,
                            max_total_bytes=4*1024*1024*1024, max_selected_bytes=128*1024*1024,
                            max_members=300000) -> dict:
    """Stream selected JSON members; never extract files or follow archive links.

    Accept native ID strings, or candidate objects returned by the CSV selector.
    In the latter case, require each member to match its exact frozen locator.
    A verified download receipt is required and rechecked against current bytes.
    Every archive member is safety checked, including unselected files. Equal
    duplicate JSON members are counted; conflicting native records are rejected.
    """
    limits = (max_member_bytes, max_total_bytes, max_selected_bytes, max_members)
    if any(type(value) is not int or value <= 0 for value in limits):
        raise ValueError("positive archive size/member limits are required")
    archive_path = Path(archive_path)
    if isinstance(receipt, (str, Path)):
        receipt = json.loads(Path(receipt).read_text(encoding="utf-8"))
    if (not isinstance(receipt, dict) or receipt.get("upstream_checksum_verified") is not True
            or type(receipt.get("bytes")) is not int or receipt["bytes"] <= 0
            or not re.fullmatch(r"md5:[0-9a-f]{32}", str(receipt.get("upstream_checksum", "")))
            or not re.fullmatch(r"[0-9a-f]{64}", str(receipt.get("sha256", "")))):
        raise ValueError("verified metadata archive download receipt is required")
    receipt_url = approved_file_url(receipt.get("url", ""))
    if not urlsplit(receipt_url).path.endswith("/metadata.tar.gz/content"):
        raise ValueError("receipt does not identify the metadata archive endpoint")
    if archive_path.is_symlink():
        raise ValueError("metadata archive cannot be a symlink")
    before = archive_path.stat()
    fingerprint = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
    size, md5, sha = _digests(archive_path)
    if (size != receipt["bytes"] or "md5:" + md5 != receipt["upstream_checksum"]
            or sha != receipt["sha256"]):
        raise ValueError("metadata archive checksum/integrity no longer matches its receipt")
    wanted, expected_members = set(), {}
    for candidate in candidates:
        if isinstance(candidate, str):
            native_id = candidate
        elif isinstance(candidate, dict):
            native_id = candidate.get("source_record_id", "")
            member_id, member = _metadata_locator(candidate.get("metadata_member", ""))
            if member_id != native_id:
                raise ValueError("candidate ID and frozen metadata locator disagree")
            if native_id in expected_members and expected_members[native_id] != member:
                raise ValueError("candidate has conflicting metadata locators")
            expected_members[native_id] = member
        else:
            raise ValueError("candidate must have a native score ID")
        if not re.fullmatch(r"[1-9][0-9]*", native_id):
            raise ValueError("invalid candidate native score ID")
        wanted.add(native_id)
    records, member_paths = {}, {}
    counts = Counter()
    with tarfile.open(archive_path, "r|gz") as archive:
        for info in _stream_members(archive):
            counts["archive_members"] += 1
            if counts["archive_members"] > max_members:
                raise ValueError("archive member limit exceeded")
            path = PurePosixPath(info.name)
            if (path.is_absolute() or ".." in path.parts or "\\" in info.name
                    or "\x00" in info.name or re.match(r"^[A-Za-z]:", info.name)):
                raise ValueError("unsafe archive member path")
            if info.isdir():
                continue
            if not info.isfile():
                raise ValueError("archive member must be a regular file or directory")
            if info.size < 0 or info.size > max_member_bytes:
                raise ValueError("archive member size limit exceeded")
            counts["archive_regular_bytes"] += info.size
            if counts["archive_regular_bytes"] > max_total_bytes:
                raise ValueError("archive total size limit exceeded")
            normalized = str(path)
            match = _METADATA_MEMBER.fullmatch(normalized)
            if not match or match.group(1) not in wanted:
                continue
            native_id = match.group(1)
            if native_id in expected_members and expected_members[native_id] != normalized:
                raise ValueError("archive member disagrees with frozen metadata locator")
            counts["selected_bytes"] += info.size
            if counts["selected_bytes"] > max_selected_bytes:
                raise ValueError("selected metadata size limit exceeded")
            handle = archive.extractfile(info)
            if handle is None:
                raise ValueError("metadata archive member cannot be read")
            with handle:
                raw = handle.read(info.size + 1)
            if len(raw) != info.size:
                raise ValueError("metadata archive member size mismatch")
            payload = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique_json_object)
            if not isinstance(payload, dict):
                raise ValueError("score metadata JSON must be an object")
            if native_id in records:
                if records[native_id] != payload or member_paths[native_id] != normalized:
                    raise ValueError("conflicting duplicate native metadata record")
                counts["equal_duplicate_members"] += 1
                continue
            records[native_id] = payload
            member_paths[native_id] = normalized
    after = archive_path.stat()
    if (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) != fingerprint:
        raise ValueError("metadata archive changed during integrity validation/stream reading")
    pending = sorted(wanted - set(records), key=lambda value: (len(value), value))
    return {"schema_version": 1, "complete": not pending, "status": "pending_metadata" if pending else "complete",
            "records": records, "member_paths": member_paths, "missing_ids": pending,
            "pending_ids": pending, "counts": dict(counts),
            "archive_integrity": {"bytes": size, "md5": md5, "sha256": sha, "upstream_checksum_verified": True}}
