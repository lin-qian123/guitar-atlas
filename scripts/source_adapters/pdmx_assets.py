"""Acquire only the frozen PDMX PDF archive and select approved native records.

No MuseScore page, authentication, conversion or downloader endpoint is used.
Archive verification and per-PDF validation are separate evidence boundaries.
"""
from __future__ import annotations

import copy
import csv
import fcntl
import gzip
import hashlib
import json
import os
import re
import subprocess
import tarfile
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from build_musescore_library import validate_config as validate_metadata_config
from catalog_sources import load_registry, validate_record_source_url
from render_offline_site import validate_readable_pdf
from source_adapters.musescore import LICENSES
from source_adapters.additional import robots_allows
from source_adapters.pdmx import AccessStopped, ZenodoFileClient, _atomic_json, _digests, _stream_members, _metadata_locator


PUBLICATION = {"name": "PDMX", "version": "v9", "record_id": "15571083",
               "page": "https://zenodo.org/records/15571083", "doi": "10.5281/zenodo.15571083",
               "dataset_license": "CC-BY-4.0"}
ARCHIVE_URL = "https://zenodo.org/api/records/15571083/files/pdf.tar.gz/content"
AGENT = "GuitarAtlas/1.0 (source-attributed personal offline guitar score library)"
LOCATOR = re.compile(r"pdf/(?:0|[1-9][0-9]*)/(?:0|[1-9][0-9]*)/[A-Za-z0-9_-]+\.pdf")
DEFAULT_LIMITS = {"max_members": 300000, "max_member_bytes": 512*1024*1024,
                  "max_total_bytes": 32*1024*1024*1024, "max_selected_bytes": 4*1024*1024*1024,
                  "max_expansion_ratio": 100}
DISPLAY_UPDATES = {
    "availability": {
        "来源页面现状未核；尚无本地谱文件。": "PDMX 历史出版记录；来源页面现状未核。",
        "来源页面现状未核；尚无本地谱文件。源站历史文件访问受限。": "PDMX 历史出版记录；来源页面现状未核。源站历史文件访问受限。",
    },
    "license_note": {
        "按 PDMX 逐条历史许可和无冲突标记整理；本次仅纳入元数据。":
            "按 PDMX 逐条历史许可和无冲突标记整理；具体条件参见出版页与原站标注。",
    },
}
RESTRICTED_IDS = {"musescore:2330946", "musescore:2770766", "musescore:5766408"}


def now():
    return datetime.now(timezone.utc).isoformat()


def _canonical_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _safe_local(root: Path, path: Path) -> Path:
    if not path.is_absolute():
        path = root / path
    if not path.resolve().is_relative_to(root):
        raise ValueError("acquisition path escapes the project root")
    relative = path.relative_to(root)
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("acquisition path cannot follow symlinks")
    return path


@contextmanager
def source_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("MuseScore PDF acquisition is already running; source lock held") from error
        yield
    finally:
        os.close(descriptor)


def validate_config(config):
    if (config.get("schema_version") != 1 or config.get("source_id") != "musescore"
            or config.get("publication") != PUBLICATION or set(config.get("files", {})) != {"pdf.tar.gz"}
            or not isinstance(config.get("scope"), str) or not config["scope"].strip()
            or not isinstance(config.get("scope_version"), str) or not config["scope_version"].strip()):
        raise ValueError("unreviewed PDMX PDF publication/configuration")
    file = config["files"]["pdf.tar.gz"]
    if (set(file) - {"size", "md5"} or type(file.get("size")) is not int or file["size"] <= 0
            or not re.fullmatch(r"[0-9a-f]{32}", str(file.get("md5", "")))):
        raise ValueError("frozen archive size and upstream checksum are required")
    limits = {**DEFAULT_LIMITS, **config.get("limits", {})}
    if set(limits) != set(DEFAULT_LIMITS) or any(type(value) is not int or value <= 0 for value in limits.values()):
        raise ValueError("positive reviewed archive limits are required")
    return limits


def _locator(value):
    if not isinstance(value, str):
        raise ValueError("missing frozen PDF locator")
    normalized = value[2:] if value.startswith("./") else value
    if not LOCATOR.fullmatch(normalized):
        raise ValueError("invalid frozen PDF locator")
    return normalized


def _jobs(catalog, registry=None):
    if (catalog.get("source_id") != "musescore" or catalog.get("schema_version") != 1
            or catalog.get("snapshot", {}).get("publication") != PUBLICATION):
        raise ValueError("catalog is not the approved frozen PDMX publication")
    jobs, identities = {}, set()
    for work in catalog.get("works", []):
        identity = work.get("id", "")
        if not re.fullmatch(r"musescore:[1-9][0-9]*", identity) or identity in identities:
            raise ValueError("duplicate or invalid native MuseScore record identity")
        identities.add(identity)
        native_id = identity.split(":", 1)[1]
        validate_record_source_url(work.get("source_url", ""), "musescore", native_id, registry)
        row = work.get("metadata", {}).get("pdmx_csv_transcription", {})
        if (row.get("license") not in {"cc-zero", "publicdomain"} or row.get("license_conflict") != "False"
                or row.get("subset:no_license_conflict") != "True" or row.get("subset:all_valid") != "True"):
            raise ValueError("frozen record license/valid-export flags are outside approved acquisition scope")
        metadata_id, _ = _metadata_locator(row.get("metadata", ""))
        if metadata_id != native_id:
            raise ValueError("native record ID and frozen metadata locator identity disagree")
        license_url = LICENSES[row["license"]][0]
        if (row.get("license_url") != license_url or work["metadata"].get("source_license") != row["license"]
                or work["metadata"].get("license_url") != license_url):
            raise ValueError("frozen CSV and native record license evidence disagree")
        member = _locator(row.get("pdf"))
        pdf_assets = [(index, asset) for index, asset in enumerate(work.get("assets", [])) if asset.get("format") == "PDF"]
        if len(pdf_assets) != 1:
            raise ValueError("each frozen record must retain exactly one PDF asset")
        for key, pairs in DISPLAY_UPDATES.items():
            value = work.get("metadata", {}).get(key)
            if value is not None and value not in set(pairs) | set(pairs.values()):
                raise ValueError(f"changed guarded PDMX display field: {key}")
            if key == "availability" and value and value.endswith("源站历史文件访问受限。") and identity not in RESTRICTED_IDS:
                raise ValueError("historical restriction display guard disagrees with frozen native identity")
        jobs[identity] = {"member": member, "asset_index": pdf_assets[0][0], "prior_asset": pdf_assets[0][1]}
    if not jobs:
        raise ValueError("an empty source is not an acquisition scope")
    return jobs


CSV_BINDING_FIELDS = ("path", "metadata", "pdf", "license", "license_url", "license_conflict",
                      "subset:no_license_conflict", "subset:all_valid")


def _stat_fingerprint(path):
    value = path.stat()
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def _bind_authoritative_csv(root, catalog, jobs):
    """Bind each selected PDF to its checksum-pinned author CSV native record.

    A locator copied into the normalized catalog is not independent evidence.
    Never rebuild, rediscover or infer identities while validating this binding.
    """
    config_path = _safe_local(root, root / "config/musescore_pdmx.json")
    config_bytes = config_path.read_bytes()
    configuration = json.loads(config_bytes)
    validate_metadata_config(configuration)
    config_sha = hashlib.sha256(config_bytes).hexdigest()
    if catalog["snapshot"].get("configuration_sha256") != config_sha:
        raise ValueError("frozen metadata configuration and catalog snapshot disagree")
    path = _safe_local(root, root / "sources/musescore/pdmx/PDMX.csv")
    before = _stat_fingerprint(path)
    size, md5, sha = _digests(path)
    if _stat_fingerprint(path) != before:
        raise ValueError("authoritative CSV changed during checksum verification")
    expected = configuration["files"]["PDMX.csv"]
    if size != expected["size"] or md5 != expected["md5"]:
        raise ValueError("authoritative CSV checksum/integrity failed")
    if catalog["snapshot"].get("metadata_checksums", {}).get("PDMX.csv") != sha:
        raise ValueError("authoritative CSV and frozen catalog metadata checksum disagree")
    wanted = {identity.split(":", 1)[1] for identity in jobs}
    rows, row_count = {}, 0
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        if (not reader.fieldnames or not set(CSV_BINDING_FIELDS).issubset(reader.fieldnames)
                or len(reader.fieldnames) != len(set(reader.fieldnames))):
            raise ValueError("authoritative CSV missing binding fields or duplicate columns")
        for row in reader:
            row_count += 1
            if None in row or any(value is None for value in row.values()):
                raise ValueError("authoritative CSV has malformed row columns")
            try:
                native_id, _ = _metadata_locator(row["metadata"])
            except ValueError:
                continue  # Unselected invalid publisher exports are not this scope.
            if native_id not in wanted:
                continue
            if native_id in rows:
                raise ValueError("duplicate native record in authoritative CSV binding")
            rows[native_id] = {key: row[key] for key in CSV_BINDING_FIELDS}
    if _stat_fingerprint(path) != before or config_path.read_bytes() != config_bytes:
        raise ValueError("authoritative CSV/configuration changed during native row selection")
    if wanted != set(rows):
        raise ValueError("frozen source records missing from authoritative CSV binding")
    for work in catalog["works"]:
        native_id = work["id"].split(":", 1)[1]
        copied = work["metadata"]["pdmx_csv_transcription"]
        for key in CSV_BINDING_FIELDS:
            if copied.get(key) != rows[native_id][key]:
                raise ValueError(f"frozen record authoritative CSV binding mismatch: {work['id']} field {key}")
    receipt = {"publication": PUBLICATION, "file": "PDMX.csv", "bytes": size, "md5": md5, "sha256": sha,
               "upstream_checksum_verified": True, "metadata_configuration_sha256": config_sha,
               "bound_records": len(rows), "dataset_rows": row_count, "binding_fields": list(CSV_BINDING_FIELDS),
               "bound_rows_sha256": _canonical_hash(rows)}
    return receipt, {"csv": path, "fingerprint": before, "config": config_path, "config_bytes": config_bytes}


def _protected(catalog):
    result = copy.deepcopy(catalog)
    result.get("summary", {}).pop("verified_local_pdfs", None)
    for work in result["works"]:
        work["assets"] = [asset for asset in work["assets"] if asset.get("format") != "PDF"]
        for key in DISPLAY_UPDATES:
            if key in work.get("metadata", {}):
                work["metadata"][key] = "guarded historical display supplement"
    return result


def _translation_hashes(root):
    directory = root / "metadata/translations"
    if not directory.is_dir():
        return {}
    result = {}
    for path in sorted(directory.rglob("*.json")):
        _safe_local(root, path)
        with path.open("rb") as stream:
            result[str(path.relative_to(root))] = hashlib.file_digest(stream, "sha256").hexdigest()
    return result


class _ArchiveResponse:
    def __init__(self, response, client, *, resumed):
        self.response = response
        self.iterator = iter(response.iter_content(chunk_size=1024*1024))
        self.first = b""
        while len(self.first) < 2:
            block = next(self.iterator, b"")
            if not block:
                break
            self.first += block
        sample = self.first[:8192].lstrip().lower()
        content_type = next((str(value).lower() for key, value in response.headers.items()
                             if key.lower() == "content-type"), "")
        if any(marker in sample for marker in (b"verify you are human", b"cf-chl-", b"hcaptcha", b"g-recaptcha")):
            client.stopped = "Zenodo PDF archive human verification required"
            raise AccessStopped(client.stopped)
        if "text/html" in content_type or sample.startswith((b"<!doctype html", b"<html")):
            client.stopped = "Zenodo PDF archive returned HTML; source access stopped"
            raise AccessStopped(client.stopped)
        if not resumed and not self.first.startswith(b"\x1f\x8b"):
            raise ValueError("Zenodo response is not the declared gzip archive")

    def __getattr__(self, name):
        return getattr(self.response, name)

    def iter_content(self, chunk_size):
        if self.first:
            yield self.first
        yield from self.iterator


class PDMXArchiveClient(ZenodoFileClient):
    """Use the existing ranged downloader with one exact archive route/clock."""
    def _request(self, url, headers):
        if url != ARCHIVE_URL:
            raise ValueError("unapproved PDMX PDF archive endpoint")
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
        try:
            if response.status_code in {401, 403, 429}:
                self.stopped = f"Zenodo PDF archive acquisition stopped: HTTP {response.status_code}"
                raise AccessStopped(self.stopped)
            # This fixed API file route has no approved redirect target. Do not
            # follow even another Zenodo file or the old MuseScore live route.
            if response.status_code in {301, 302, 303, 307, 308} or response.url != ARCHIVE_URL:
                raise ValueError("unapproved PDMX PDF archive redirect/response URL")
            return _ArchiveResponse(response, self, resumed=response.status_code == 206 and "Range" in headers), url
        except BaseException:
            response.close()
            raise


def _check_robots(client, destination):
    # Reuse the same request clock as the archive client; only this fixed robots
    # URL is permitted in addition to its fixed file endpoint.
    with client.lock:
        if client.stopped:
            raise AccessStopped(client.stopped)
        if client.last_request is not None:
            remaining = client.delay - (client.clock() - client.last_request)
            if remaining > 0:
                client.sleep(remaining)
        if client.stopped:
            raise AccessStopped(client.stopped)
        client.last_request = client.clock()
        response = client.session.get("https://zenodo.org/robots.txt", headers={"User-Agent": AGENT},
                                      stream=False, allow_redirects=False, timeout=(15, 90))
    try:
        if response.status_code in {401, 403, 429}:
            client.stopped = f"Zenodo robots access stopped: HTTP {response.status_code}"
            raise AccessStopped(client.stopped)
        if response.status_code != 200 or response.url != "https://zenodo.org/robots.txt":
            raise AccessStopped("Zenodo robots unavailable; acquisition stopped")
        body = response.text
        if any(marker in body.lower() for marker in ("verify you are human", "cf-chl-", "hcaptcha", "g-recaptcha")):
            client.stopped = "Zenodo robots human verification required"
            raise AccessStopped(client.stopped)
        _atomic_json(destination, {"checked_at": now(), "url": response.url, "status_code": response.status_code, "text": body})
        if not robots_allows(body, "GuitarAtlas", ARCHIVE_URL):
            client.stopped = "Zenodo robots disallows the frozen PDF file endpoint"
            raise AccessStopped(client.stopped)
        import urllib.robotparser
        parser = urllib.robotparser.RobotFileParser()
        parser.parse(body.splitlines())
        client.delay = max(client.delay, parser.crawl_delay("GuitarAtlas") or parser.crawl_delay("*") or 0)
    finally:
        response.close()


class _BoundedReader:
    def __init__(self, source, limit):
        self.source, self.limit, self.bytes = source, limit, 0

    def read(self, size=-1):
        block = self.source.read(size)
        self.bytes += len(block)
        if self.bytes > self.limit:
            raise ValueError("archive actual decompression size/expansion limit exceeded")
        return block


def _member_name(info):
    name = info.name
    path = PurePosixPath(name)
    if (path.is_absolute() or ".." in path.parts or "\\" in name or "\x00" in name
            or re.match(r"^[A-Za-z]:", name) or not path.parts):
        raise ValueError("unsafe archive member path")
    if not info.isfile() and not info.isdir() or info.issparse():
        raise ValueError("archive member must be a nonsparse regular file or directory")
    return str(path)


def _validate_object(root, asset, *, require_provenance=True):
    if require_provenance and (asset.get("status") != "verified" or asset.get("format") != "PDF"
            or asset.get("publication") != PUBLICATION or not LOCATOR.fullmatch(str(asset.get("archive_member", "")))
            or not re.fullmatch(r"[0-9a-f]{64}", str(asset.get("archive_sha256", "")))
            or not re.fullmatch(r"md5:[0-9a-f]{32}", str(asset.get("archive_upstream_checksum", "")))
            or asset.get("archive_checksum_status") != "md5_verified"
            or asset.get("upstream_checksum_status") != "not_supplied"):
        raise ValueError("invalid verified PDF archive/member provenance")
    digest = asset.get("sha256", "")
    size = asset.get("size")
    if not re.fullmatch(r"[0-9a-f]{64}", digest) or type(size) is not int or size <= 0:
        raise ValueError("invalid immutable PDF receipt")
    expected = root / "sources/musescore/objects" / f"{digest}.pdf"
    if asset.get("local_path") != str(expected.relative_to(root)):
        raise ValueError("immutable source object locator drift")
    _safe_local(root, expected)
    before = expected.stat()
    if before.st_size != size:
        raise ValueError("immutable source object size mismatch")
    validate_readable_pdf(expected)
    with expected.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
            raise ValueError("immutable source object checksum mismatch")
    after = expected.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise ValueError("immutable source object changed during fresh verification")
    return True


def _store_pdf(root, part, digest, size):
    pool = _safe_local(root, root / "sources/objects/sha256" / digest[:2] / f"{digest}.pdf")
    local = _safe_local(root, root / "sources/musescore/objects" / f"{digest}.pdf")
    pool.parent.mkdir(parents=True, exist_ok=True)
    local.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(part, pool)
    except FileExistsError:
        if pool.stat().st_size != size:
            raise ValueError("immutable pool object size mismatch")
        validate_readable_pdf(pool)
        with pool.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
                raise ValueError("immutable pool object checksum mismatch")
    if local.exists():
        _validate_object(root, {"sha256": digest, "size": size, "local_path": str(local.relative_to(root))}, require_provenance=False)
        if (pool.stat().st_dev, pool.stat().st_ino) != (local.stat().st_dev, local.stat().st_ino):
            temporary = _safe_local(root, local.with_name(local.name + ".part"))
            if temporary.exists():
                temporary.unlink()
            os.link(pool, temporary)
            os.replace(temporary, local)
    else:
        temporary = _safe_local(root, local.with_name(local.name + ".part"))
        if temporary.exists():
            temporary.unlink()
        os.link(pool, temporary)
        os.replace(temporary, local)
    return str(local.relative_to(root))


def _verified_asset(size, digest, local, member, receipt):
    # Construct fresh evidence rather than copying untrusted optional claims
    # from a previous catalog or interrupted journal.
    return {"format": "PDF", "status": "verified", "label": "PDMX 出版 PDF", "size": size,
            "sha256": digest, "local_path": local, "archive_member": member,
            "archive_sha256": receipt["sha256"], "archive_upstream_checksum": receipt["upstream_checksum"],
            "archive_checksum_status": "md5_verified", "upstream_checksum_status": "not_supplied",
            "publication": PUBLICATION, "verified_at": now()}


def _summary(records):
    counts = Counter(row["status"] for row in records)
    return {"source_records": len(records), "verified_records": counts["verified"],
            "failed_records": counts["failed"], "missing_records": counts["missing"],
            "pending_records": counts["pending"],
            "unique_pdf_objects": len({row["asset"]["sha256"] for row in records if row["status"] == "verified"})}


def initialize_pending_journal(root):
    """Freeze the approved acquisition scope without requesting any archive.

    An existing canonical journal is preserved. This guard protects already
    reviewed metadata during a separate, resumable archive transfer.
    """
    root = Path(root).resolve()
    base = _safe_local(root, root / "sources/musescore")
    base.mkdir(parents=True, exist_ok=True)
    with source_lock(_safe_local(root, base / ".pdf-acquisition.lock")):
        path = _safe_local(root, base / "pdmx/pdf-extraction.json")
        if path.is_file():
            existing = json.loads(path.read_text())
            if existing.get("source_id") != "musescore" or existing.get("publication") != PUBLICATION:
                raise ValueError("existing acquisition journal has unapproved source/publication")
            return existing
        config_bytes = _safe_local(root, root / "config/musescore_pdmx_assets.json").read_bytes()
        config = json.loads(config_bytes)
        validate_config(config)
        original_bytes = _safe_local(root, base / "catalog.json").read_bytes()
        catalog = json.loads(original_bytes)
        jobs = _jobs(catalog, load_registry(root))
        csv_binding, _ = _bind_authoritative_csv(root, catalog, jobs)
        report = {"schema_version": 1, "source_id": "musescore", "publication": PUBLICATION,
                  "status": "pending_archive", "started_at": now(), "scope": config["scope"],
                  "scope_version": config["scope_version"], "configuration_sha256": hashlib.sha256(config_bytes).hexdigest(),
                  "input_catalog_sha256": hashlib.sha256(original_bytes).hexdigest(),
                  "protected_non_asset_catalog_sha256": _canonical_hash(_protected(catalog)),
                  "translation_input_sha256": _translation_hashes(root), "snapshot_unchanged": True,
                  "catalog_committed": False, "archive_checked_this_run": False, "live_source_requests": 0,
                  "csv_binding": csv_binding, "records": [{"id": identity, "archive_member": job["member"], "status": "pending"}
                              for identity, job in jobs.items()]}
        report["counts"] = _summary(report["records"])
        _atomic_json(path, report)
        _atomic_json(_safe_local(root, base / "acquisition_report.json"), report)
        return report


def consolidate_prefix(root):
    """Explicit local reallocation; never start a request or expose score links."""
    from source_adapters.zenodo_download import consolidate_received_prefix

    root = Path(root).resolve()
    base = _safe_local(root, root / "sources/musescore")
    config = json.loads(_safe_local(root, root / "config/musescore_pdmx_assets.json").read_bytes())
    validate_config(config)
    expected = config["files"]["pdf.tar.gz"]
    return consolidate_received_prefix(_safe_local(root, base / "pdmx/pdf.tar.gz"),
        expected_size=expected["size"], expected_md5=expected["md5"],
        source_lock_path=_safe_local(root, base / ".pdf-acquisition.lock"),
        plan_path=_safe_local(root, base / "pdmx/pdf-range-plan.json"))


def download_parallel_archive(root, *, client=None):
    """Download the separately approved page route without publishing PDF links."""
    from source_adapters.zenodo_download import PAGE_URL, download_file

    root = Path(root).resolve()
    initialize_pending_journal(root)
    base = _safe_local(root, root / "sources/musescore")
    with source_lock(_safe_local(root, base / ".pdf-acquisition.lock")):
        config_path = _safe_local(root, root / "config/musescore_pdmx_assets.json")
        config_bytes = config_path.read_bytes()
        config = json.loads(config_bytes)
        validate_config(config)
        if config.get("download_page_url") != PAGE_URL:
            raise ValueError("parallel archive download requires the exact approved publication page endpoint")
        catalog = json.loads(_safe_local(root, base / "catalog.json").read_bytes())
        _bind_authoritative_csv(root, catalog, _jobs(catalog, load_registry(root)))
        expected = config["files"]["pdf.tar.gz"]
        receipt = download_file(PAGE_URL, _safe_local(root, base / "pdmx/pdf.tar.gz"),
            expected_size=expected["size"], expected_md5=expected["md5"], client=client,
            plan_path=_safe_local(root, base / "pdmx/pdf-range-plan.json"),
            receipt_path=_safe_local(root, base / "pdmx/pdf-receipt.json"))
        if config_path.read_bytes() != config_bytes:
            raise ValueError("parallel archive configuration changed during transfer")
        return receipt


def acquire(root, *, cached_archive=True, batch_size=25, client=None):
    """Persist resumable private outcomes and atomically publish safe PDF assets.

    Partial archive extraction never upgrades catalog assets. A successful full
    stream validates every member, gzip integrity and the archive's frozen MD5;
    unchanged records retain all source identities, review fields and categories.
    """
    root = Path(root).resolve()
    if type(batch_size) is not int or batch_size <= 0:
        raise ValueError("positive acquisition batch size required")
    base = _safe_local(root, root / "sources/musescore")
    base.mkdir(parents=True, exist_ok=True)
    with source_lock(_safe_local(root, base / ".pdf-acquisition.lock")):
        return _acquire_locked(root, cached_archive=cached_archive, batch_size=batch_size, client=client)


def _acquire_locked(root, *, cached_archive, batch_size, client):
    base = root / "sources/musescore"
    config_path = _safe_local(root, root / "config/musescore_pdmx_assets.json")
    config_bytes = config_path.read_bytes()
    config = json.loads(config_bytes)
    limits = validate_config(config)
    catalog_path = _safe_local(root, base / "catalog.json")
    original_bytes = catalog_path.read_bytes()
    catalog = json.loads(original_bytes)
    jobs = _jobs(catalog, load_registry(root))
    archive = _safe_local(root, base / "pdmx/pdf.tar.gz")
    report_path = _safe_local(root, base / "acquisition_report.json")
    journal_path = _safe_local(root, base / "pdmx/pdf-extraction.json")
    receipt_path = _safe_local(root, base / "pdmx/pdf-receipt.json")
    protected_hash = _canonical_hash(_protected(catalog))
    translation_hashes = _translation_hashes(root)
    report = {"schema_version": 1, "started_at": now(), "status": "running", "source_id": "musescore",
              "publication": PUBLICATION, "scope": config["scope"], "scope_version": config["scope_version"],
              "configuration_sha256": hashlib.sha256(config_bytes).hexdigest(), "live_source_requests": 0,
              "catalog_committed": False, "input_catalog_sha256": hashlib.sha256(original_bytes).hexdigest(),
              "protected_non_asset_catalog_sha256": protected_hash, "translation_input_sha256": translation_hashes,
              "snapshot_unchanged": True, "fresh_verified_prior_records": 0, "archive_checked_this_run": False,
              "records": [{"id": identity, "archive_member": job["member"], "status": "pending"} for identity, job in jobs.items()]}
    states = {row["id"]: row for row in report["records"]}
    selected, fresh_assets = {}, {}
    preceding_journal = None
    if journal_path.is_file():
        preceding_journal = json.loads(journal_path.read_text())
        if not preceding_journal.get("staged_members") and preceding_journal.get("resume_candidates"):
            preceding_journal = preceding_journal["resume_candidates"]
        report["resume_candidates"] = {key: preceding_journal.get(key) for key in
            ("schema_version", "input_catalog_sha256", "configuration_sha256", "archive_integrity", "staged_members")}
    report["counts"] = _summary(report["records"])
    _atomic_json(journal_path, report)
    try:
        report["csv_binding"], csv_guard = _bind_authoritative_csv(root, catalog, jobs)
        _atomic_json(journal_path, report)
        if cached_archive:
            if not archive.is_file():
                raise ValueError("cached PDF archive missing; use --acquire-archive")
            before = archive.stat()
            fingerprint = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
            size, md5, sha = _digests(archive)
            after = archive.stat()
            if (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) != fingerprint:
                raise ValueError("PDF archive changed during checksum verification")
            expected = config["files"]["pdf.tar.gz"]
            if size != expected["size"] or md5 != expected["md5"]:
                raise ValueError("cached PDF archive checksum/integrity failed; no network request made")
            prior_receipt = json.loads(receipt_path.read_text()) if receipt_path.is_file() else {}
            download_page = "https://zenodo.org/records/15571083/files/pdf.tar.gz"
            preserve_origin = (prior_receipt.get("url") in {ARCHIVE_URL, download_page}
                and prior_receipt.get("bytes") == size and prior_receipt.get("sha256") == sha
                and prior_receipt.get("upstream_checksum") == "md5:" + md5
                and prior_receipt.get("upstream_checksum_verified") is True)
            receipt = {**(prior_receipt if preserve_origin else {}),
                       "url": prior_receipt["url"] if preserve_origin else ARCHIVE_URL,
                       "final_url": prior_receipt.get("final_url", prior_receipt["url"]) if preserve_origin else ARCHIVE_URL,
                       "bytes": size, "sha256": sha, "upstream_checksum": "md5:" + md5,
                       "upstream_checksum_verified": True, "cached": True, "resumed_from": 0, "checked_at": now()}
            if not preserve_origin:
                receipt["completed_at"] = now()
            _atomic_json(receipt_path, receipt)
        else:
            client = client or PDMXArchiveClient()
            _check_robots(client, _safe_local(root, base / "pdmx/pdf-robots.json"))
            expected = config["files"]["pdf.tar.gz"]
            receipt = client.download_file(ARCHIVE_URL, archive, expected_size=expected["size"],
                                           expected_md5=expected["md5"], receipt_path=receipt_path)
            before = archive.stat()
            fingerprint = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
            size, md5, sha = _digests(archive)
            after = archive.stat()
            if (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) != fingerprint:
                raise ValueError("PDF archive changed during checksum verification")
            if size != expected["size"] or md5 != expected["md5"] or sha != receipt["sha256"]:
                raise ValueError("downloaded PDF archive checksum/integrity failed")
        report["archive_integrity"] = receipt
        report["archive_checked_this_run"] = True
        for identity, job in jobs.items():
            prior = job["prior_asset"]
            if prior.get("status") == "verified":
                try:
                    _validate_object(root, prior)
                    if prior.get("archive_member") != job["member"] or prior.get("archive_sha256") != receipt["sha256"]:
                        raise ValueError("prior PDF publication/member evidence drift")
                    fresh_assets[job["member"]] = prior
                    report["fresh_verified_prior_records"] += 1
                except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
                    states[identity]["prior_verification_error"] = str(error)
        wanted = set(job["member"] for job in jobs.values())
        report["fresh_verified_staged_members"] = 0
        if (preceding_journal and preceding_journal.get("schema_version") == 1
                and preceding_journal.get("input_catalog_sha256") == report["input_catalog_sha256"]
                and preceding_journal.get("configuration_sha256") == report["configuration_sha256"]
                and preceding_journal.get("archive_integrity", {}).get("sha256") == receipt["sha256"]):
            for name, staged in preceding_journal.get("staged_members", {}).items():
                asset = staged.get("asset", {})
                if name not in wanted or staged.get("status") != "verified" or name in fresh_assets:
                    continue
                try:
                    _validate_object(root, asset)
                    if asset.get("archive_member") != name or asset.get("archive_sha256") != receipt["sha256"]:
                        raise ValueError("staged PDF publication/member evidence drift")
                    fresh_assets[name] = asset
                    report["fresh_verified_staged_members"] += 1
                except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
                    continue
        seen, counts = set(), Counter()
        partials = _safe_local(root, base / "partials")
        partials.mkdir(parents=True, exist_ok=True)
        def checkpoint():
            report["archive_counts"] = dict(counts)
            report["staged_members"] = selected
            report["counts"] = _summary(report["records"])
            report["updated_at"] = now()
            _atomic_json(journal_path, report)
        checkpoint()
        with archive.open("rb") as compressed, gzip.GzipFile(fileobj=compressed) as decompressed:
            bounded = _BoundedReader(decompressed, min(limits["max_total_bytes"], receipt["bytes"]*limits["max_expansion_ratio"]))
            with tarfile.open(fileobj=bounded, mode="r|") as tar:
                for info in _stream_members(tar):
                    counts["archive_members"] += 1
                    if counts["archive_members"] > limits["max_members"]:
                        raise ValueError("archive member limit exceeded")
                    name = _member_name(info)
                    if name in seen:
                        raise ValueError("duplicate archive member path")
                    seen.add(name)
                    if info.isdir():
                        if info.size:
                            raise ValueError("archive directory size must be zero")
                        continue
                    if info.size < 0 or info.size > limits["max_member_bytes"]:
                        raise ValueError("archive member size limit exceeded")
                    counts["archive_regular_bytes"] += info.size
                    if counts["archive_regular_bytes"] > limits["max_total_bytes"]:
                        raise ValueError("archive regular total size limit exceeded")
                    if name not in wanted:
                        continue
                    counts["selected_members"] += 1
                    counts["selected_bytes"] += info.size
                    if counts["selected_bytes"] > limits["max_selected_bytes"]:
                        raise ValueError("selected PDF size limit exceeded")
                    result = {"status": "failed", "archive_member": name}
                    part = _safe_local(root, partials / (hashlib.sha256(name.encode()).hexdigest() + ".pdf.part"))
                    try:
                        existing = fresh_assets.get(name)
                        if existing is not None and existing["size"] == info.size:
                            source = tar.extractfile(info)
                            if source is None:
                                raise ValueError("selected PDF member cannot be read")
                            with source:
                                member_sha = hashlib.file_digest(source, "sha256").hexdigest()
                            if member_sha != existing["sha256"]:
                                raise ValueError("fresh archive member checksum disagrees with prior PDF receipt")
                            result = {"status": "verified", "asset": _verified_asset(info.size, member_sha,
                                existing["local_path"], name, receipt)}
                            counts["reused_verified_members"] += 1
                        else:
                            source = tar.extractfile(info)
                            if source is None:
                                raise ValueError("selected PDF member cannot be read")
                            digest, received = hashlib.sha256(), 0
                            with source, part.open("wb") as destination:
                                while block := source.read(1024*1024):
                                    received += len(block)
                                    if received > info.size:
                                        raise ValueError("selected PDF member exceeds declared size")
                                    digest.update(block)
                                    destination.write(block)
                                destination.flush()
                                os.fsync(destination.fileno())
                            if received != info.size:
                                raise ValueError("selected PDF member size mismatch")
                            validate_readable_pdf(part)
                            sha = digest.hexdigest()
                            local = _store_pdf(root, part, sha, received)
                            asset = _verified_asset(received, sha, local, name, receipt)
                            result = {"status": "verified", "asset": asset}
                    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
                        result["reason"] = str(error)
                    finally:
                        if part.exists():
                            part.unlink()
                    selected[name] = result
                    for identity, job in jobs.items():
                        if job["member"] == name:
                            states[identity].update(result)
                    if counts["selected_members"] % batch_size == 0:
                        checkpoint()
                if tar.fileobj.tell() - tar.offset < tarfile.BLOCKSIZE:
                    raise ValueError("truncated archive: first tar end marker absent")
                trailing = tar.fileobj.buf
                tail_bytes = len(trailing)
                if any(trailing):
                    raise ValueError("nonzero data follows archive end marker")
            while block := bounded.read(1024*1024):
                tail_bytes += len(block)
                if any(block):
                    raise ValueError("nonzero data follows archive end marker")
            if tail_bytes < tarfile.BLOCKSIZE:
                raise ValueError("truncated archive: second tar end marker absent")
            counts["actual_decompressed_bytes"] = bounded.bytes
        after = archive.stat()
        if (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) != fingerprint:
            raise ValueError("PDF archive changed during verification/stream reading")
        for identity, job in jobs.items():
            if job["member"] not in selected:
                states[identity].update(status="missing", reason="exact frozen PDF member absent from the verified archive")
        checkpoint()
        updated = copy.deepcopy(catalog)
        allowed_diffs = []
        for work in updated["works"]:
            state = states[work["id"]]
            index = jobs[work["id"]]["asset_index"]
            if state["status"] == "verified":
                work["assets"][index] = state["asset"]
            else:
                work["assets"][index] = {"format": "PDF", "status": state["status"], "label": "PDMX 出版 PDF",
                                         "archive_member": state["archive_member"], "publication": PUBLICATION,
                                         "reason": state["reason"], "checked_at": now()}
            for key, pairs in DISPLAY_UPDATES.items():
                prior = work["metadata"].get(key)
                if prior in pairs:
                    current = pairs[prior]
                    allowed_diffs.append({"id": work["id"], "field": key, "before": prior, "after": current})
                    work["metadata"][key] = current
        updated.setdefault("summary", {})["verified_local_pdfs"] = sum(row["status"] == "verified" for row in states.values())
        if _canonical_hash(_protected(updated)) != protected_hash or updated["snapshot"] != catalog["snapshot"]:
            raise ValueError("non-asset record or frozen snapshot changed during PDF acquisition")
        if _translation_hashes(root) != translation_hashes:
            raise ValueError("translation bytes changed during PDF acquisition; catalog preserved")
        if (_stat_fingerprint(csv_guard["csv"]) != csv_guard["fingerprint"]
                or csv_guard["config"].read_bytes() != csv_guard["config_bytes"]):
            raise ValueError("authoritative CSV/configuration changed before catalog commit")
        if catalog_path.read_bytes() != original_bytes or config_path.read_bytes() != config_bytes:
            raise ValueError("catalog/configuration changed concurrently; catalog preserved")
        _atomic_json(catalog_path, updated)
        report.pop("staged_members", None)
        report.pop("resume_candidates", None)
        report.update(status="complete", completed_at=now(), catalog_committed=True,
                      counts=_summary(report["records"]), archive_counts=dict(counts),
                      output_catalog_sha256=hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
                      protected_non_asset_catalog_after_sha256=_canonical_hash(_protected(updated)),
                      translation_bytes_unchanged=True, allowed_metadata_differences=allowed_diffs)
        _atomic_json(report_path, report)
        _atomic_json(journal_path, report)
        return report
    except BaseException as error:
        staged_members = report.pop("staged_members", {})
        report.update(status="stopped_access" if isinstance(error, AccessStopped) else "interrupted" if isinstance(error, KeyboardInterrupt) else "failed_archive",
                      completed_at=now(), error=str(error), counts=_summary(report["records"]))
        _atomic_json(report_path, report)
        _atomic_json(journal_path, {**report, "staged_members": staged_members})
        raise
