#!/usr/bin/env python
"""Resume permitted PDF acquisition; atomic receipts and immutable SHA-256 objects.

Only adapter-reviewed `pending` PDF assets are eligible. Restricted assets and
other formats remain in catalogs. Raw receipts/logs/files never enter public_site.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import threading
import urllib.robotparser
import zipfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import requests

from catalog_sources import load_registry
from render_offline_site import checked_source_asset, validate_readable_pdf
from source_adapters.additional import robots_allows


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    with part.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(part, path)


class StopSource(RuntimeError):
    pass


class PendingAcquisition(RuntimeError):
    """A queued job did not request its asset because the source already stopped."""


class PDFClient:
    def __init__(self, root: Path, config: dict):
        self.root, self.config = root, config
        self.base = root / "sources" / config["id"]
        self.base.mkdir(parents=True, exist_ok=True)
        self.allowed = set(config.get("asset_hosts", []))
        self.delay = max(0.8, config.get("acquisition_settings", {}).get("delay", 1))
        self.last_request = 0
        self.robots = {}
        self.network_lock = threading.RLock()
        self.robots_lock = threading.RLock()
        self.object_lock = threading.RLock()
        self.stopped = ""
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "GuitarAtlas/1.0 (source-attributed personal offline guitar score library)"

    def log(self, event, **fields):
        with (self.base / "acquisition_log.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"at": now(), "source_id": self.config["id"], "event": event, **fields}, ensure_ascii=False) + "\n")

    def approved(self, url):
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.hostname not in self.allowed
                or parsed.username or parsed.password or parsed.fragment or parsed.port not in (None, 443)):
            raise ValueError("unapproved asset endpoint")
        return parsed

    def request(self, url, *, stream=False):
        self.approved(url)
        for _ in range(6):
            with self.network_lock:
                if self.stopped:
                    raise StopSource(self.stopped)
                remaining = self.delay - (time.monotonic() - self.last_request)
                if remaining > 0:
                    time.sleep(remaining)
                if self.stopped:
                    raise PendingAcquisition(self.stopped)
                self.last_request = time.monotonic()
                response = self.session.get(url, timeout=(15, 90), allow_redirects=False, stream=stream)
            if response.status_code in {301, 302, 303, 307, 308}:
                from urllib.parse import urljoin
                target = urljoin(url, response.headers.get("Location", ""))
                response.close()
                self.approved(target)
                url = target
                continue
            return response
        raise ValueError("asset redirect loop")

    def check_robots(self, url):
        with self.robots_lock:
            self._check_robots(url)

    def _check_robots(self, url):
        host = self.approved(url).hostname
        if host not in self.robots:
            response = self.request(f"https://{host}/robots.txt")
            if response.status_code in {401, 403, 429} or response.status_code >= 500:
                raise StopSource(f"robots unavailable: HTTP {response.status_code}")
            text = response.text if response.status_code == 200 else ""
            atomic_json(self.base / "snapshots" / f"asset-robots-{host}.json", {
                "at": now(), "status_code": response.status_code, "text": text})
            parser = urllib.robotparser.RobotFileParser()
            parser.parse(text.splitlines())
            self.robots[host] = (parser, text)
            self.delay = max(self.delay, parser.crawl_delay("GuitarAtlas") or parser.crawl_delay("*") or 0)
        if not robots_allows(self.robots[host][1], "GuitarAtlas", url):
            raise StopSource("robots disallows asset acquisition")

    def store_pdf(self, part, sha):
        with self.object_lock:
            return self._store_pdf(part, sha)

    def _store_pdf(self, part, sha):
        pool = self.root / "sources" / "objects" / "sha256" / sha[:2] / f"{sha}.pdf"
        pool.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(part, pool)
        except FileExistsError:
            validate_readable_pdf(pool)
            with pool.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != sha:
                    raise ValueError("immutable object pool is corrupted")
        part.unlink()
        local = self.base / "objects" / f"{sha}.pdf"
        local.parent.mkdir(parents=True, exist_ok=True)
        if not local.exists():
            temporary = local.with_name(local.name + ".part")
            if temporary.exists():
                temporary.unlink()
            os.link(pool, temporary)
            os.replace(temporary, local)
        else:
            with local.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != sha:
                    raise ValueError("immutable source object is corrupted")
        return str(local.relative_to(self.root))

    def unpack_pdf_zip(self, part, sha):
        members, total = [], 0
        with zipfile.ZipFile(part) as archive:
            for info in archive.infolist():
                name = Path(info.filename)
                if name.is_absolute() or ".." in name.parts or "\\" in info.filename or info.flag_bits & 1:
                    raise ValueError("unsafe or encrypted ZIP member")
                if info.is_dir() or name.suffix.casefold() != ".pdf":
                    continue
                total += info.file_size
                if total > 512 * 1024 * 1024 or info.file_size > 200 * max(info.compress_size, 1):
                    raise ValueError("ZIP expansion limit exceeded")
                temporary = part.with_name(hashlib.sha256(info.filename.encode()).hexdigest()+".pdf.part")
                with archive.open(info) as source, temporary.open("wb") as destination:
                    digest = hashlib.sha256()
                    size = 0
                    while block := source.read(1024 * 1024):
                        destination.write(block); digest.update(block); size += len(block)
                    destination.flush(); os.fsync(destination.fileno())
                if size != info.file_size:
                    raise ValueError("ZIP member size mismatch")
                validate_readable_pdf(temporary)
                pdf_hash = digest.hexdigest()
                local = self.store_pdf(temporary, pdf_hash)
                members.append({"name":info.filename, "format":"PDF", "status":"verified", "size":size,
                                "sha256":pdf_hash, "local_path":local, "verified_at":now()})
        if not members:
            raise ValueError("ZIP contains no parseable PDFs")
        size = part.stat().st_size
        part.unlink()
        return {"status":"verified", "members":members, "container_sha256":sha, "container_size":size,
                "verified_at":now(), "upstream_checksum_status":"not_supplied"}

    def acquire(self, asset):
        url = asset["source_url"]
        is_zip = asset.get("container") == "ZIP"
        self.check_robots(url)
        key = hashlib.sha256(url.encode()).hexdigest()
        part = self.base / "partials" / f"{key}.pdf.part"
        part.parent.mkdir(parents=True, exist_ok=True)
        response = self.request(url, stream=True)
        with response:
            if response.status_code in {401, 403, 429}:
                raise StopSource(f"asset access stopped: HTTP {response.status_code}")
            if response.status_code != 200:
                raise ValueError(f"expected full PDF response, HTTP {response.status_code}")
            digest = hashlib.sha256()
            upstream_sha1 = hashlib.sha1() if asset.get("sha1_upstream") else None
            size = 0
            with part.open("wb") as stream:
                for block in response.iter_content(1024 * 1024):
                    if not block:
                        continue
                    if size == 0 and not (block.startswith(b"PK\x03\x04") if is_zip else block.startswith(b"%PDF-")):
                        if any(marker in block.lower() for marker in (b'verify you are human', b'cf-chl-', b'hcaptcha', b'g-recaptcha')):
                            raise StopSource("human verification required")
                        raise ValueError("response is not a PDF/declared ZIP (HTML/error)")
                    size += len(block)
                    if size > 512 * 1024 * 1024:
                        raise ValueError("PDF exceeds per-object size limit")
                    digest.update(block)
                    if upstream_sha1:
                        upstream_sha1.update(block)
                    stream.write(block)
                stream.flush()
                os.fsync(stream.fileno())
            expected = response.headers.get("Content-Length")
            if expected and not response.headers.get("Content-Encoding") and size != int(expected):
                raise ValueError("truncated response: Content-Length mismatch")
            if asset.get("expected_size") and size != asset["expected_size"]:
                raise ValueError("upstream expected byte size mismatch")
            sha = digest.hexdigest()
            if asset.get("sha256_upstream") and sha != asset["sha256_upstream"]:
                raise ValueError("upstream SHA-256 mismatch")
            if upstream_sha1 and upstream_sha1.hexdigest() != asset["sha1_upstream"]:
                raise ValueError("upstream SHA-1 mismatch")
            if is_zip:
                return self.unpack_pdf_zip(part, sha)
            validate_readable_pdf(part)
            local = self.store_pdf(part, sha)
            return {"status": "verified", "local_path": local, "sha256": sha,
                    "size": size, "verified_at": now(), "final_asset_url": response.url,
                    "upstream_checksum_status": "verified" if upstream_sha1 or asset.get("sha256_upstream") else "not_supplied"}

    def acquire_guarded(self, asset):
        if self.stopped:
            raise PendingAcquisition(self.stopped)
        try:
            return self.acquire(asset)
        except StopSource as exc:
            # Establish the barrier in the worker before it can take another job.
            self.stopped = str(exc)
            raise


def acquire_source(root: Path, config: dict, *, retry_failed=False, workers=2):
    path = root / config["catalog"]
    catalog = json.loads(path.read_text(encoding="utf-8"))
    client = PDFClient(root, config)
    started, count, stopped = now(), 0, ""
    jobs = []
    for work in catalog["works"]:
        for asset in work.get("assets", []):
            if asset.get("format", "").upper() != "PDF":
                continue
            if asset.get("status") == "verified":
                candidates = [{**asset, **member} for member in asset.get("members", [])] if asset.get("container") == "ZIP" else [asset]
                if candidates and all(checked_source_asset(root, config["id"], item) is not None for item in candidates):
                    continue
                asset.update(status="failed", last_error="existing local PDF failed fresh integrity validation")
            eligible = asset.get("status") == "pending" or (retry_failed and asset.get("status") == "failed")
            if not eligible or stopped:
                continue
            jobs.append((work["id"], asset))
    executor = ThreadPoolExecutor(max_workers=max(1, min(workers, 2)))
    futures = {executor.submit(client.acquire_guarded, asset):(identity, asset) for identity, asset in jobs}
    try:
        for future in as_completed(futures):
            identity, asset = futures[future]
            if future.cancelled():
                continue
            if isinstance(future.exception(), PendingAcquisition):
                continue
            asset["attempts"] = asset.get("attempts", 0) + 1
            try:
                asset.update(future.result())
                asset.pop("last_error", None)
                count += 1
                client.log("verified", record_id=identity, **{key: asset[key] for key in ("source_url", "sha256", "size", "local_path", "container_sha256", "container_size", "upstream_checksum_status") if key in asset})
            except Exception as exc:
                asset.update(status="blocked" if isinstance(exc, StopSource) else "failed", last_error=str(exc), attempted_at=now())
                client.log("blocked" if isinstance(exc, StopSource) else "failed", record_id=identity, source_url=asset.get("source_url"), error=str(exc))
                if isinstance(exc, StopSource):
                    stopped = str(exc)
                    client.stopped = stopped
                    for pending in futures:
                        pending.cancel()
            atomic_json(path, catalog)
            if count % 25 == 0 and count:
                print(json.dumps({"source": config["id"], "new_verified": count}, ensure_ascii=False), flush=True)
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
    statuses = Counter(asset.get("status", "unspecified") for work in catalog["works"] for asset in work.get("assets", []) if asset.get("format", "").upper() == "PDF")
    report = {"source_id": config["id"], "started_at": started, "finished_at": now(), "new_verified": count,
              "pdf_asset_statuses": dict(statuses), "stopped_reason": stopped, "frozen_snapshot": catalog.get("snapshot", {})}
    atomic_json(client.base / "acquisition_report.json", report)
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--source", action="append", required=True)
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--workers", type=int, choices=[1,2], default=2, help="At most two streamed responses, with one shared per-host request clock")
    args = parser.parse_args()
    root = args.root.resolve()
    registered = {source["id"]: source for source in load_registry(root)}
    for identity in args.source:
        config = registered[identity]
        if config["adapter"] != "normalized_catalog" or not config.get("asset_hosts"):
            raise ValueError("source has no approved PDF acquisition endpoints")
        acquire_source(root, config, retry_failed=args.retry_failed, workers=args.workers)


if __name__ == "__main__":
    main()
