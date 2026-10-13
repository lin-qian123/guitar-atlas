"""Two resumable ranges for fixed, reviewed PDMX v9 publication pages.

Original prefixes and segment bytes remain private until whole-archive upstream
MD5 verification. This route never follows redirects or requests MuseScore.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import requests

from source_adapters.additional import robots_allows
from source_adapters.pdmx import AccessStopped, _atomic_json, _digests
from source_adapters.pdmx_assets import source_lock


PAGE_URL = "https://zenodo.org/records/15571083/files/pdf.tar.gz"
PAGE_URLS = frozenset("https://zenodo.org/records/15571083/files/" + name + ".tar.gz"
                      for name in ("pdf", "mxl", "mid"))


def _page_stem(url):
    if url not in PAGE_URLS:
        raise ValueError("unapproved fixed Zenodo publication endpoint")
    return url.rsplit("/", 1)[1].split(".", 1)[0]
ROBOTS_URL = "https://zenodo.org/robots.txt"
AGENT = "GuitarAtlas/1.0 (source-attributed personal offline guitar score library)"
GAP_CHUNK_BYTES = 64*1024*1024
MAX_GAP_SEGMENTS = 32


def now():
    return datetime.now(timezone.utc).isoformat()


def _safe(path):
    path = Path(path).absolute()
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise ValueError("archive/segment path cannot follow symlinks")
    return path


def _fingerprint(path):
    value = path.stat()
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


class RangeClient:
    def __init__(self, *, session=None, clock=None, sleep=None, delay=10, page_url=PAGE_URL):
        _page_stem(page_url)
        self.page_url = page_url
        self.session = session if session is not None else requests.Session()
        self.clock, self.sleep = clock or time.monotonic, sleep or time.sleep
        self.delay = max(10, delay)
        self.last_request = None
        self.lock = threading.Lock()
        self.stopped = ""

    def stop(self, reason):
        self.stopped = reason
        raise AccessStopped(reason)

    def request(self, url, *, headers=None, stream=True):
        if url not in {self.page_url, ROBOTS_URL}:
            raise ValueError("unapproved fixed Zenodo publication endpoint")
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
            response = self.session.get(url, headers={"User-Agent": AGENT, "Accept-Encoding": "identity", **(headers or {})},
                                        stream=stream, allow_redirects=False, timeout=(15, 90))
            if response.status_code in {401, 403, 429}:
                self.stopped = f"Zenodo range access stopped: HTTP {response.status_code}"
                response.close()
                raise AccessStopped(self.stopped)
            if url == self.page_url and "text/html" in str(response.headers.get("Content-Type", "")).lower():
                self.stopped = "Zenodo range returned HTML; human verification/access stop"
                response.close()
                raise AccessStopped(self.stopped)
        try:
            if response.url != url or response.status_code in {301, 302, 303, 307, 308}:
                raise ValueError("unapproved Zenodo publication page redirect/response URL")
            return response
        except BaseException:
            response.close()
            raise

    def check_robots(self, receipt_path):
        response = self.request(ROBOTS_URL, stream=False)
        try:
            if response.status_code != 200:
                self.stop(f"Zenodo robots unavailable: HTTP {response.status_code}")
            text = response.text
            if any(value in text.lower() for value in ("verify you are human", "cf-chl-", "hcaptcha", "g-recaptcha")):
                self.stop("Zenodo robots human verification required")
            _atomic_json(receipt_path, {"checked_at": now(), "url": ROBOTS_URL, "status_code": 200, "text": text})
            if not robots_allows(text, "GuitarAtlas", self.page_url):
                self.stop("Zenodo robots disallows the approved publication page endpoint")
            import urllib.robotparser
            parser = urllib.robotparser.RobotFileParser()
            parser.parse(text.splitlines())
            self.delay = max(self.delay, parser.crawl_delay("GuitarAtlas") or parser.crawl_delay("*") or 0)
        finally:
            response.close()


def download_file(url, destination, *, expected_size, expected_md5, client=None, chunk_bytes=1024*1024,
                  plan_path=None, receipt_path=None):
    stem = _page_stem(url)
    if client is not None and client.page_url != url:
        raise ValueError("range client endpoint disagrees with requested publication")
    if (type(expected_size) is not int or expected_size <= 0
            or not re.fullmatch(r"[0-9a-f]{32}", str(expected_md5))
            or type(chunk_bytes) is not int or chunk_bytes <= 0):
        raise ValueError("positive frozen size, checksum and chunk size required")
    destination = _safe(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    plan_path = _safe(plan_path or destination.parent / (stem + "-range-plan.json"))
    receipt_path = _safe(receipt_path or destination.parent / (stem + "-receipt.json"))
    with source_lock(_safe(destination.parent / ".publication-range.lock")), source_lock(_safe(destination.parent / ("." + stem + "-range.lock"))):
        return _download_locked(destination, expected_size=expected_size, expected_md5=expected_md5,
                                client=client or RangeClient(page_url=url), chunk_bytes=chunk_bytes,
                                plan_path=plan_path, receipt_path=receipt_path)


def _download_locked(destination, *, expected_size, expected_md5, client, chunk_bytes, plan_path, receipt_path):
    page_url = client.page_url
    stem = _page_stem(page_url)
    prefix = _safe(destination.with_name(destination.name + ".part"))
    assembly = _safe(destination.with_name(destination.name + ".complete.part"))
    if destination.is_file():
        before = _fingerprint(destination)
        size, md5, sha = _digests(destination)
        if before != _fingerprint(destination):
            raise ValueError("cached final publication archive changed during checksum validation")
        if size != expected_size or md5 != expected_md5:
            raise ValueError("existing final publication archive integrity failure; original bytes preserved")
        previous = json.loads(receipt_path.read_text()) if receipt_path.is_file() else {}
        approved_origins = {page_url, "https://zenodo.org/api/records/15571083/files/" + page_url.rsplit("/", 1)[1] + "/content"}
        preserve = (previous.get("url") in approved_origins and previous.get("bytes") == size
                    and previous.get("sha256") == sha and previous.get("upstream_checksum") == "md5:" + md5
                    and previous.get("upstream_checksum_verified") is True)
        receipt = {**(previous if preserve else {}), "url": previous["url"] if preserve else page_url,
                   "final_url": previous.get("final_url", previous["url"]) if preserve else page_url,
                   "bytes": size, "sha256": sha, "upstream_checksum": "md5:" + md5,
                   "upstream_checksum_verified": True, "cached": True, "checked_at": now()}
        if not preserve:
            receipt.update(completed_at=now(), segment_count=0, prefix_bytes=0)
        _atomic_json(receipt_path, receipt)
        return receipt
    _refuse_any_publication_access(destination.parent)
    if not prefix.exists():
        prefix.touch()
    before = _fingerprint(prefix)
    prefix_size, _, prefix_sha = _digests(prefix)
    if before != _fingerprint(prefix):
        raise ValueError("original prefix changed during acquisition planning")
    if prefix_size > expected_size:
        raise ValueError("original prefix exceeds frozen archive size")
    if plan_path.is_file():
        plan = json.loads(plan_path.read_text())
        if _source_refused(plan):
            raise AccessStopped("range source access refusal cannot be silently retried")
        if plan.get("consolidation", {}).get("status") == "prepared":
            raise ValueError("pending local consolidation must finish before HTTP range resume")
        if plan.get("rebalance", {}).get("status") == "prepared":
            raise ValueError("pending local rebalance must finish before HTTP range resume")
        if (plan.get("schema_version") != 1 or plan.get("url") != page_url
                or plan.get("expected_size") != expected_size or plan.get("expected_md5") != expected_md5
                or plan.get("prefix") != {"bytes": prefix_size, "sha256": prefix_sha}):
            raise ValueError("range plan no longer agrees with the untouched original prefix/publication")
        tail = _validate_retained_tail(destination,plan) if "retained_tail" in plan else None
        expected_segments = _planned_offsets(prefix_size,expected_size,plan)
        if (len(plan.get("segments", [])) != len(expected_segments)
                or any((row.get("start"), row.get("end")) != offsets
                       or row.get("filename") != _segment_filename(destination, index, plan)
                       or row.get("length") != offsets[1]-offsets[0]+1
                       for index, (row, offsets) in enumerate(zip(plan["segments"], expected_segments)))):
            raise ValueError("range plan offsets or segment filenames changed")
    else:
        tail = None
        remaining = expected_size - prefix_size
        midpoint = prefix_size + (remaining + 1)//2
        offsets = [(prefix_size, midpoint-1), (midpoint, expected_size-1)] if remaining > 1 else [(prefix_size, expected_size-1)] if remaining else []
        plan = {"schema_version": 1, "url": page_url, "expected_size": expected_size, "expected_md5": expected_md5,
                "prefix": {"bytes": prefix_size, "sha256": prefix_sha}, "created_at": now(),
                "segments": [{"start": start, "end": end, "length": end-start+1,
                              "filename": destination.name + f".range-{index}.part", "received": 0, "status": "pending"}
                             for index, (start, end) in enumerate(offsets)]}
    plan_lock = threading.Lock()
    def checkpoint():
        plan["updated_at"] = now()
        _atomic_json(plan_path, plan)
    for row in plan["segments"]:
        path = _safe(destination.parent / row["filename"])
        if not path.exists():
            path.touch()
        size = path.stat().st_size
        if size > row["length"]:
            raise ValueError("range fragment exceeds its approved exact offsets")
        row.update(received=size, status="complete" if size == row["length"] else "pending")
    plan.update(status="downloading", error="")
    checkpoint()
    def fetch(row):
        path = _safe(destination.parent / row["filename"])
        received = path.stat().st_size
        if received == row["length"]:
            return
        offset = row["start"] + received
        response = client.request(page_url, headers={"Range": f"bytes={offset}-{row['end']}"})
        try:
            headers = {key.lower(): value for key, value in response.headers.items()}
            if response.status_code != 206:
                raise ValueError(f"exact HTTP Range response required; received {response.status_code}")
            if headers.get("content-encoding", "identity").lower() != "identity":
                raise ValueError("encoded HTTP Range response cannot preserve byte offsets")
            if headers.get("content-range") != f"bytes {offset}-{row['end']}/{expected_size}":
                raise ValueError("inconsistent resumed Content-Range")
            if headers.get("content-length") != str(row["length"]-received):
                raise ValueError("range Content-Length mismatch")
            if "text/html" in str(headers.get("content-type", "")).lower():
                client.stop("Zenodo range returned HTML; human verification/access stop")
            last_checkpoint = received
            first = True
            with path.open("ab") as output:
                try:
                    for block in response.iter_content(chunk_size=chunk_bytes):
                        if client.stopped:
                            raise AccessStopped(client.stopped)
                        if not block:
                            continue
                        if first:
                            sample = block[:8192].lstrip().lower()
                            if any(value in sample for value in (b"verify you are human", b"cf-chl-", b"hcaptcha", b"g-recaptcha")) or sample.startswith((b"<!doctype html", b"<html")):
                                client.stop("Zenodo range human verification required")
                            first = False
                        if received + len(block) > row["length"]:
                            raise ValueError("range response exceeds its exact segment")
                        output.write(block)
                        received += len(block)
                        if received - last_checkpoint >= 32*1024*1024:
                            output.flush(); os.fsync(output.fileno())
                            with plan_lock:
                                row.update(received=received, status="downloading")
                                checkpoint()
                            last_checkpoint = received
                finally:
                    output.flush(); os.fsync(output.fileno())
            if received != row["length"]:
                raise ValueError("interrupted range response size mismatch")
            with plan_lock:
                row.update(received=received, status="complete")
                checkpoint()
        finally:
            response.close()
    failures = []
    try:
        incomplete = [row for row in plan["segments"] if row["status"] != "complete"]
        if incomplete:
            client.check_robots(_safe(destination.parent / (stem + "-range-robots.json")))
            with ThreadPoolExecutor(max_workers=2) as workers:
                futures = {workers.submit(fetch, row): row for row in incomplete}
                try:
                    for future in as_completed(futures):
                        row = futures[future]
                        try:
                            future.result()
                        except Exception as error:
                            failures.append(error)
                            with plan_lock:
                                row.update(received=(destination.parent / row["filename"]).stat().st_size,
                                           status="stopped" if isinstance(error, AccessStopped) else "interrupted", error=str(error))
                                checkpoint()
                except BaseException:
                    client.stopped = "range transfer interrupted; remaining requests cancelled"
                    for future in futures:
                        future.cancel()
                    raise
            if failures:
                if client.stopped:
                    raise AccessStopped(client.stopped)
                raise RuntimeError("range transfer interrupted; original prefix and fragment bytes retained: " + str(failures[0]))
        if before != _fingerprint(prefix):
            raise ValueError("original prefix changed during range transfer")
        if tail:
            _validate_retained_tail(destination,plan)
        plan.update(status="assembling")
        checkpoint()
        size, sha, md5 = 0, hashlib.sha256(), hashlib.md5(usedforsecurity=False)
        paths = [prefix, *(_safe(destination.parent / row["filename"]) for row in plan["segments"])]
        if tail:
            paths.append(_safe(destination.parent / tail["filename"]))
        input_fingerprints = {path: _fingerprint(path) for path in paths}
        with assembly.open("wb") as output:
            for path in paths:
                with path.open("rb") as stream:
                    for block in iter(lambda: stream.read(1024*1024), b""):
                        output.write(block); md5.update(block); sha.update(block); size += len(block)
            output.flush(); os.fsync(output.fileno())
        if any(_fingerprint(path) != fingerprint for path, fingerprint in input_fingerprints.items()):
            raise ValueError("range fragment/prefix changed during archive assembly")
        if size != expected_size or md5.hexdigest() != expected_md5:
            raise ValueError("whole archive size/upstream checksum mismatch; original prefix preserved")
        assembly_before = _fingerprint(assembly)
        verified_size, verified_md5, verified_sha = _digests(assembly)
        if assembly_before != _fingerprint(assembly) or (verified_size, verified_md5, verified_sha) != (size, md5.hexdigest(), sha.hexdigest()):
            raise ValueError("assembled archive changed before publication")
        os.replace(assembly, destination)
        receipt = {"url": page_url, "final_url": page_url, "bytes": size, "sha256": sha.hexdigest(),
                   "upstream_checksum": "md5:" + md5.hexdigest(), "upstream_checksum_verified": True,
                   "cached": False, "completed_at": now(), "prefix_bytes": prefix_size,
                   "segment_count": len(plan["segments"]), "range_plan": plan_path.name}
        if tail:
            receipt.update(retained_tail_bytes=tail["length"],retained_tail_sha256=tail["sha256"],
                           gap_chunk_bytes=GAP_CHUNK_BYTES)
        _atomic_json(receipt_path, receipt)
        plan.update(status="complete", completed_at=now(), final_sha256=sha.hexdigest(), upstream_checksum_verified=True)
        checkpoint()
        for path in paths:
            path.unlink()
        return receipt
    except BaseException as error:
        if assembly.exists():
            assembly.unlink()
        plan.update(status="stopped_access" if isinstance(error, AccessStopped) else "interrupted",
                    error=str(error), updated_at=now())
        checkpoint()
        raise


def _segment_filename(destination, index, plan):
    generation = plan.get("fragment_generation", "")
    if generation and (not re.fullmatch(r"[0-9a-f]{64}", str(generation)) or generation != plan.get("prefix", {}).get("sha256")):
        raise ValueError("range fragment generation disagrees with frozen prefix")
    return destination.name + f".range-{generation+'-' if generation else ''}{index}.part"


def _copy_prefix(paths, destination):
    digest, size = hashlib.sha256(), 0
    with destination.open("wb") as output:
        for path in paths:
            with path.open("rb") as source:
                for block in iter(lambda: source.read(1024*1024), b""):
                    output.write(block); digest.update(block); size += len(block)
        output.flush(); os.fsync(output.fileno())
    return {"bytes": size, "sha256": digest.hexdigest()}


def _source_refused(plan):
    status = str(plan.get("status", "")).casefold()
    errors = " ".join(str(row.get("error", "")) for row in [plan, *plan.get("segments", [])]).lower()
    refused = {"blocked", "stopped_access", "accessstopped", "access_stopped", "stopped"}
    return status in refused or any(str(row.get("status", "")).casefold() in refused for row in plan.get("segments", [])) or any(
        marker in errors for marker in ("http 401", "http 403", "http 429", "human verification", "robots disallows"))


def _ordinary_offsets(start,end):
    remaining = end-start
    midpoint = start+(remaining+1)//2
    return [(start,midpoint-1),(midpoint,end-1)] if remaining > 1 else [(start,end-1)] if remaining else []


def _planned_offsets(start,expected_size,plan):
    if "retained_tail" not in plan:
        return _ordinary_offsets(start,expected_size)
    tail = plan["retained_tail"]
    if (plan.get("range_mode") != "retained_tail_v1" or plan.get("gap_chunk_bytes") != GAP_CHUNK_BYTES
            or type(tail.get("start")) is not int or not start < tail["start"] < expected_size):
        raise ValueError("retained-tail fixed gap configuration/boundaries are invalid")
    offsets = [(left,min(left+GAP_CHUNK_BYTES,tail["start"])-1) for left in range(start,tail["start"],GAP_CHUNK_BYTES)]
    if not offsets or len(offsets) > MAX_GAP_SEGMENTS:
        raise ValueError("retained-tail gap job limit exceeded")
    return offsets


def _tail_filename(destination,digest):
    if not re.fullmatch(r"[0-9a-f]{64}",str(digest)):
        raise ValueError("invalid retained-tail SHA-256 guard")
    return destination.name+f".tail-{digest}.part"


def _checked_identity(path,guard,context):
    before = _fingerprint(path)
    size,_,sha = _digests(path)
    if before != _fingerprint(path) or {"bytes":size,"sha256":sha} != {"bytes":guard.get("bytes"),"sha256":guard.get("sha256")}:
        raise ValueError(f"{context} checksum/size identity changed")
    return before


def _rebalance_shape(destination,plan):
    """Validate stored tail offset evidence against exact old two-half slots."""
    intent = plan.get("rebalance",{})
    old = intent.get("old_plan_summary",{})
    if (intent.get("version") != 1 or intent.get("status") not in {"prepared","complete"}
            or old.get("schema_version") != 1 or old.get("url") != plan.get("url")
            or old.get("expected_size") != plan.get("expected_size") or old.get("expected_md5") != plan.get("expected_md5")
            or _source_refused(old) or "retained_tail" in old or "rebalance" in old):
        raise ValueError("retained-tail prepared publication/access evidence drift")
    _page_stem(old.get("url"))
    old_prefix = old.get("prefix",{})
    new_prefix = intent.get("new_prefix",{})
    guards = intent.get("input_guards",[])
    if (type(old_prefix.get("bytes")) is not int or old_prefix["bytes"] < 0
            or not re.fullmatch(r"[0-9a-f]{64}",str(old_prefix.get("sha256","")))
            or type(new_prefix.get("bytes")) is not int
            or not re.fullmatch(r"[0-9a-f]{64}",str(new_prefix.get("sha256","")))
            or len(guards) != 3):
        raise ValueError("retained-tail original input guards are invalid")
    offsets = _ordinary_offsets(old_prefix["bytes"],plan["expected_size"])
    if len(offsets) != 2 or len(old.get("segments",[])) != 2:
        raise ValueError("retained-tail requires exactly two old half-range boundaries")
    if (guards[0] != {"filename":destination.name+".part",**old_prefix}
            or any((row.get("start"),row.get("end")) != interval or row.get("length") != interval[1]-interval[0]+1
                or row.get("filename") != _segment_filename(destination,index,old)
                or guard.get("filename") != row.get("filename") or type(guard.get("bytes")) is not int
                or not 0 <= guard["bytes"] <= row["length"]
                or not re.fullmatch(r"[0-9a-f]{64}",str(guard.get("sha256","")))
                for index,(row,interval,guard) in enumerate(zip(old["segments"],offsets,guards[1:])))
            or not 0 < guards[1]["bytes"] < old["segments"][0]["length"]
            or guards[2]["bytes"] != old["segments"][1]["length"]
            or new_prefix["bytes"] != guards[0]["bytes"]+guards[1]["bytes"]):
        raise ValueError("retained-tail input guards/offsets disagree with exact old plan")
    tail = intent.get("retained_tail",{})
    second = old["segments"][1]
    expected_tail = {"start":second["start"],"end":second["end"],"length":second["length"],
        "bytes":guards[2]["bytes"],"sha256":guards[2]["sha256"],
        "filename":_tail_filename(destination,guards[2]["sha256"]),"status":"complete"}
    if tail != expected_tail or not old_prefix["bytes"] < new_prefix["bytes"] < tail["start"]:
        raise ValueError("retained-tail extent/filename does not preserve exact old upper range")
    return intent,old,guards,new_prefix,tail


def _validate_retained_tail(destination,plan):
    intent,_,guards,new_prefix,tail = _rebalance_shape(destination,plan)
    if (intent.get("status") != "complete" or plan.get("prefix") != new_prefix
            or plan.get("retained_tail") != tail or plan.get("fragment_generation") != new_prefix["sha256"]):
        raise ValueError("retained-tail active plan does not equal completed local transaction")
    _planned_offsets(new_prefix["bytes"],plan["expected_size"],plan)
    prefix = _safe(destination.with_name(destination.name+".part"))
    _check_original_prefix_slices(prefix,guards[:2])
    _checked_identity(_safe(destination.parent / tail["filename"]),tail,"retained tail")
    return tail


def _refuse_any_publication_access(directory):
    for stem in ("pdf","mxl","mid"):
        for kind in ("range-plan","extraction"):
            path = _safe(directory / f"{stem}-{kind}.json")
            if path.is_file():
                value = json.loads(path.read_text())
                if not isinstance(value,dict):
                    raise ValueError("malformed publication access journal")
                if _source_refused(value):
                    raise AccessStopped("publication source access refusal cannot be rebalanced or retried")


def rebalance_received_ranges(destination,*,page_url,expected_size,expected_md5,source_lock_path=None,plan_path=None):
    """Pure local recovery: retain complete upper bytes and chunk only the gap.

    No network request or catalog publication occurs. Both old fragments remain
    recoverable until an exact prepared transaction has committed its new plan.
    """
    stem = _page_stem(page_url)
    if type(expected_size) is not int or expected_size <= 0 or not re.fullmatch(r"[0-9a-f]{32}",str(expected_md5)):
        raise ValueError("positive frozen publication size/upstream checksum required")
    destination = _safe(destination)
    source_lock_path = _safe(source_lock_path or destination.parent.parent / ".pdf-acquisition.lock")
    plan_path = _safe(plan_path or destination.parent / (stem+"-range-plan.json"))
    with source_lock(source_lock_path),source_lock(_safe(destination.parent / ".publication-range.lock")),source_lock(_safe(destination.parent / ("."+stem+"-range.lock"))):
        _refuse_any_publication_access(destination.parent)
        original_bytes = plan_path.read_bytes()
        plan = json.loads(original_bytes)
        if (plan.get("schema_version") != 1 or plan.get("url") != page_url or plan.get("expected_size") != expected_size
                or plan.get("expected_md5") != expected_md5 or _source_refused(plan)):
            raise ValueError("rebalance plan disagrees with frozen publication/access scope")
        if destination.exists():
            raise ValueError("rebalance is only for an incomplete publication archive")
        prefix = _safe(destination.with_name(destination.name+".part"))
        staging = _safe(destination.with_name(destination.name+".prefix-rebalance.part"))
        if plan.get("consolidation",{}).get("status") == "prepared":
            raise ValueError("finish the pending ordinary consolidation before rebalance")
        if plan.get("rebalance",{}).get("status") == "prepared":
            return _finish_rebalance(destination,prefix,staging,plan_path,plan)
        if "retained_tail" in plan:
            _validate_retained_tail(destination,plan)
            _clean_rebalance_inputs(destination,plan)
            return {"status":"unchanged","reason":"retained_tail_plan_already_committed","archive_verified":False,"catalog_committed":False}
        before = _fingerprint(prefix)
        prefix_size,_,prefix_sha = _digests(prefix)
        if before != _fingerprint(prefix) or plan.get("prefix") != {"bytes":prefix_size,"sha256":prefix_sha}:
            raise ValueError("rebalance original prefix drift")
        offsets = _ordinary_offsets(prefix_size,expected_size)
        if (len(offsets) != 2 or len(plan.get("segments",[])) != 2
                or any((row.get("start"),row.get("end")) != interval or row.get("length") != interval[1]-interval[0]+1
                    or row.get("filename") != _segment_filename(destination,index,plan)
                    for index,(row,interval) in enumerate(zip(plan["segments"],offsets)))):
            raise ValueError("rebalance old range offsets/filenames changed")
        fragments = [_safe(destination.parent / row["filename"]) for row in plan["segments"]]
        if any(not path.is_file() for path in fragments):
            return {"status":"unchanged","reason":"missing_original_fragment"}
        sizes = [path.stat().st_size for path in fragments]
        if any(size > row["length"] for size,row in zip(sizes,plan["segments"])):
            raise ValueError("rebalance fragment exceeds approved exact offsets")
        if sizes[1] != plan["segments"][1]["length"] or not 0 < sizes[0] < plan["segments"][0]["length"]:
            return {"status":"unchanged","reason":"requires_partial_lower_and_complete_upper_range"}
        _planned_offsets(prefix_size+sizes[0],expected_size,{"retained_tail":{"start":plan["segments"][1]["start"]},
                         "range_mode":"retained_tail_v1","gap_chunk_bytes":GAP_CHUNK_BYTES})
        paths = [prefix,*fragments]
        fingerprints,guards = {},[]
        for path in paths:
            stamp = _fingerprint(path)
            size,_,sha = _digests(path)
            if stamp != _fingerprint(path):
                raise ValueError("rebalance input changed during fresh hashing")
            fingerprints[path] = stamp
            guards.append({"filename":path.name,"bytes":size,"sha256":sha})
        try:
            new_prefix = _copy_prefix([prefix,fragments[0]],staging)
            if any(_fingerprint(path) != stamp for path,stamp in fingerprints.items()):
                raise ValueError("rebalance input changed during prefix copy")
            _checked_identity(staging,new_prefix,"rebalance staged prefix")
            if plan_path.read_bytes() != original_bytes:
                raise ValueError("rebalance range plan changed during local copy")
            second = plan["segments"][1]
            tail = {"start":second["start"],"end":second["end"],"length":second["length"],
                    "bytes":guards[2]["bytes"],"sha256":guards[2]["sha256"],
                    "filename":_tail_filename(destination,guards[2]["sha256"]),"status":"complete"}
            old = {key:plan[key] for key in ("schema_version","url","expected_size","expected_md5","prefix","segments","status")}
            if plan.get("fragment_generation"):
                old["fragment_generation"] = plan["fragment_generation"]
            plan["rebalance"] = {"version":1,"status":"prepared","prepared_at":now(),"old_plan_summary":old,
                "old_plan_sha256":hashlib.sha256(original_bytes).hexdigest(),"input_guards":guards,
                "new_prefix":new_prefix,"retained_tail":tail}
            _rebalance_shape(destination,plan)
            _atomic_json(plan_path,plan)
            return _finish_rebalance(destination,prefix,staging,plan_path,plan)
        except BaseException:
            if staging.exists() and plan.get("rebalance",{}).get("status") != "prepared":
                staging.unlink()
            raise


def _finish_rebalance(destination,prefix,staging,plan_path,plan):
    prepared_bytes = plan_path.read_bytes()
    if json.loads(prepared_bytes) != plan:
        raise ValueError("prepared rebalance plan changed before recovery")
    intent,old,guards,new_prefix,tail = _rebalance_shape(destination,plan)
    if plan.get("prefix") != old["prefix"] or plan.get("segments") != old["segments"] or "retained_tail" in plan:
        raise ValueError("prepared rebalance outer plan disagrees with original boundaries")
    first = _safe(destination.parent / guards[1]["filename"])
    original_tail = _safe(destination.parent / guards[2]["filename"])
    _checked_identity(first,guards[1],"original lower fragment")
    _checked_identity(original_tail,guards[2],"original upper fragment")
    tail_path = _safe(destination.parent / tail["filename"])
    if not tail_path.exists():
        os.link(original_tail,tail_path)
    _checked_identity(tail_path,tail,"retained tail")
    tail_path.chmod(0o444)
    stamp = _fingerprint(prefix)
    size,_,sha = _digests(prefix)
    if stamp != _fingerprint(prefix):
        raise ValueError("rebalance prefix changed during recovery")
    current = {"bytes":size,"sha256":sha}
    if current == old["prefix"]:
        if _concatenation_identity([prefix,first]) != new_prefix:
            raise ValueError("rebalance new prefix disagrees with original concatenation identity")
        if not staging.exists() and _copy_prefix([prefix,first],staging) != new_prefix:
            raise ValueError("recovered rebalance prefix identity mismatch")
        _checked_identity(staging,new_prefix,"prepared rebalance prefix")
        _checked_identity(prefix,guards[0],"original prefix")
        if plan_path.read_bytes() != prepared_bytes:
            raise ValueError("prepared rebalance plan changed before prefix replacement")
        staging.chmod(0o444)
        os.replace(staging,prefix)
    elif current != new_prefix:
        raise ValueError("rebalance prefix is neither original nor prepared version")
    _check_original_prefix_slices(prefix,guards[:2])
    _checked_identity(prefix,new_prefix,"rebalance published prefix")
    plan.update(prefix=new_prefix,fragment_generation=new_prefix["sha256"],retained_tail=tail,
                range_mode="retained_tail_v1",gap_chunk_bytes=GAP_CHUNK_BYTES,status="pending",error="",upstream_checksum_verified=False)
    offsets = _planned_offsets(new_prefix["bytes"],plan["expected_size"],plan)
    plan["segments"] = [{"start":left,"end":right,"length":right-left+1,
                         "filename":_segment_filename(destination,index,plan),"received":0,"status":"pending"}
                        for index,(left,right) in enumerate(offsets)]
    intent.update(status="complete",completed_at=now())
    if plan_path.read_bytes() != prepared_bytes:
        raise ValueError("prepared rebalance plan changed before final plan publication")
    _atomic_json(plan_path,plan)
    _clean_rebalance_inputs(destination,plan)
    if staging.exists():
        staging.unlink()
    return {"status":"rebalanced","prefix_bytes":new_prefix["bytes"],"retained_tail_bytes":tail["length"],
            "pending_bytes":tail["start"]-new_prefix["bytes"],"gap_segments":len(offsets),
            "gap_chunk_bytes":GAP_CHUNK_BYTES,"archive_verified":False,"catalog_committed":False}


def _clean_rebalance_inputs(destination,plan):
    _,_,guards,_,tail = _rebalance_shape(destination,plan)
    _validate_retained_tail(destination,plan)
    for guard in guards[1:]:
        path = _safe(destination.parent / guard["filename"])
        if path.name == tail["filename"] or path.name in {row["filename"] for row in plan["segments"]}:
            raise ValueError("rebalance cleanup cannot target an active fragment")
        if path.exists():
            _checked_identity(path,guard,"retired rebalance input")
            path.unlink()


def consolidate_received_prefix(destination, *, expected_size, expected_md5, source_lock_path=None, plan_path=None):
    """Purely local, explicit replanning after every transfer writer has exited.

    Only a complete first range permits merging its following partial range.
    No missing gap is crossed and no source refusal is converted into a retry.
    """
    destination = _safe(destination)
    plan_path = _safe(plan_path or destination.parent / "pdf-range-plan.json")
    source_lock_path = _safe(source_lock_path or destination.parent / ".pdf-acquisition.lock")
    with source_lock(source_lock_path), source_lock(_safe(destination.parent / ".publication-range.lock")), source_lock(_safe(destination.parent / ".pdf-range.lock")):
        original_plan_bytes = plan_path.read_bytes()
        plan = json.loads(original_plan_bytes)
        if "retained_tail" in plan or "rebalance" in plan:
            raise ValueError("retained-tail plans require the explicit rebalance helper, not PDF consolidation")
        if _source_refused(plan):
            raise AccessStopped("range source access refusal cannot be consolidated or retried")
        if (plan.get("schema_version") != 1 or plan.get("url") != PAGE_URL
                or plan.get("expected_size") != expected_size or plan.get("expected_md5") != expected_md5):
            raise ValueError("consolidation plan disagrees with frozen publication")
        prefix = _safe(destination.with_name(destination.name + ".part"))
        staging = _safe(destination.with_name(destination.name + ".prefix-consolidation.part"))
        intent = plan.get("consolidation", {})
        if intent.get("status") == "prepared":
            return _finish_consolidation(destination, prefix, staging, plan_path, plan)
        prefix_before = _fingerprint(prefix)
        prefix_size, _, prefix_sha = _digests(prefix)
        if prefix_before != _fingerprint(prefix) or plan.get("prefix") != {"bytes": prefix_size, "sha256": prefix_sha}:
            raise ValueError("consolidation original prefix changed or disagrees with range plan")
        remaining = expected_size-prefix_size
        midpoint = prefix_size+(remaining+1)//2
        offsets = [(prefix_size, midpoint-1), (midpoint, expected_size-1)] if remaining > 1 else [(prefix_size, expected_size-1)] if remaining else []
        if (len(plan.get("segments", [])) != len(offsets)
                or any((row.get("start"), row.get("end")) != interval
                       or row.get("length") != interval[1]-interval[0]+1
                       or row.get("filename") != _segment_filename(destination, index, plan)
                       for index, (row, interval) in enumerate(zip(plan["segments"], offsets)))):
            raise ValueError("consolidation range plan offsets or filenames changed")
        sizes = []
        for row in plan["segments"]:
            path = _safe(destination.parent / row["filename"])
            size = path.stat().st_size if path.exists() else 0
            if size > row["length"]:
                raise ValueError("consolidation fragment exceeds approved exact offsets")
            sizes.append(size)
        if all(size == row["length"] for size, row in zip(sizes, plan["segments"])):
            return {"status": "unchanged", "reason": "all_segments_received_finalize_existing_plan"}
        if not sizes or sizes[0] != plan["segments"][0]["length"]:
            return {"status": "unchanged", "reason": "first_segment_incomplete"}
        if any(not (destination.parent / row["filename"]).is_file() for row in plan["segments"]):
            return {"status": "unchanged", "reason": "missing_fragment_leave_existing_plan"}
        paths = [prefix, *(_safe(destination.parent / row["filename"]) for row in plan["segments"])]
        guards, fingerprints = [], {}
        for path in paths:
            before = _fingerprint(path)
            size, _, sha = _digests(path)
            if before != _fingerprint(path):
                raise ValueError("consolidation input changed during checksum validation")
            fingerprints[path] = before
            guards.append({"filename": path.name, "bytes": size, "sha256": sha})
        try:
            new_prefix = _copy_prefix(paths, staging)
            if any(_fingerprint(path) != value for path, value in fingerprints.items()):
                raise ValueError("consolidation input changed during prefix copy")
            staged_before = _fingerprint(staging)
            size, _, sha = _digests(staging)
            if staged_before != _fingerprint(staging) or new_prefix != {"bytes": size, "sha256": sha}:
                raise ValueError("consolidation staged prefix changed during validation")
            if size != prefix_size + sum(sizes) or size >= expected_size:
                raise ValueError("consolidation cannot imply complete archive verification")
            if plan_path.read_bytes() != original_plan_bytes:
                raise ValueError("consolidation range plan changed during local prefix copy")
            old_summary = {key: plan[key] for key in ("url", "expected_size", "expected_md5", "prefix", "segments", "status")}
            if plan.get("fragment_generation"):
                old_summary["fragment_generation"] = plan["fragment_generation"]
            intent = {"status": "prepared", "prepared_at": now(), "old_plan_summary": old_summary,
                      "input_guards": guards, "new_prefix": new_prefix,
                      "input_stat_fingerprints": {path.name: list(value) for path, value in fingerprints.items()},
                      "old_plan_sha256": hashlib.sha256(original_plan_bytes).hexdigest()}
            plan["consolidation"] = intent
            _atomic_json(plan_path, plan)
            return _finish_consolidation(destination, prefix, staging, plan_path, plan)
        except BaseException:
            if staging.exists() and plan.get("consolidation", {}).get("status") != "prepared":
                staging.unlink()
            raise


def _concatenation_identity(paths):
    fingerprints = {path: _fingerprint(path) for path in paths}
    digest, size = hashlib.sha256(), 0
    for path in paths:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024*1024), b""):
                digest.update(block); size += len(block)
    if any(_fingerprint(path) != value for path, value in fingerprints.items()):
        raise ValueError("original concatenation inputs changed during identity verification")
    return {"bytes": size, "sha256": digest.hexdigest()}


def _check_original_prefix_slices(prefix, guards):
    before = _fingerprint(prefix)
    with prefix.open("rb") as stream:
        for guard in guards:
            digest, remaining = hashlib.sha256(), guard["bytes"]
            while remaining:
                block = stream.read(min(1024*1024, remaining))
                if not block:
                    raise ValueError("consolidated prefix original slice is truncated")
                digest.update(block); remaining -= len(block)
            if digest.hexdigest() != guard["sha256"]:
                raise ValueError("consolidated prefix original slice identity mismatch")
        if stream.read(1):
            raise ValueError("consolidated prefix has bytes beyond original guarded slices")
    if before != _fingerprint(prefix):
        raise ValueError("consolidated prefix changed during original slice verification")


def _finish_consolidation(destination, prefix, staging, plan_path, plan):
    prepared_plan_bytes = plan_path.read_bytes()
    if json.loads(prepared_plan_bytes) != plan:
        raise ValueError("prepared consolidation plan changed before transaction validation")
    intent = plan["consolidation"]
    old = intent["old_plan_summary"]
    if plan.get("prefix") != old.get("prefix") or plan.get("segments") != old.get("segments"):
        raise ValueError("prepared outer plan and original input boundaries disagree")
    if (old.get("url") != PAGE_URL or old.get("expected_size") != plan["expected_size"]
            or old.get("expected_md5") != plan["expected_md5"] or _source_refused(old)):
        raise ValueError("pending consolidation changed frozen publication/access evidence")
    guards = intent["input_guards"]
    new_prefix = intent["new_prefix"]
    old_prefix = old.get("prefix", {})
    if (type(old_prefix.get("bytes")) is not int or old_prefix["bytes"] < 0
            or not re.fullmatch(r"[0-9a-f]{64}", str(old_prefix.get("sha256", "")))
            or type(new_prefix.get("bytes")) is not int or not re.fullmatch(r"[0-9a-f]{64}", str(new_prefix.get("sha256", "")))):
        raise ValueError("invalid prepared consolidation prefix guards")
    start = old_prefix["bytes"]
    remaining = plan["expected_size"]-start
    midpoint = start+(remaining+1)//2
    offsets = [(start, midpoint-1), (midpoint, plan["expected_size"]-1)] if remaining > 1 else [(start, plan["expected_size"]-1)]
    if (len(old.get("segments", [])) != len(offsets) or len(guards) != len(offsets)+1
            or guards[0] != {"filename": prefix.name, **old_prefix}
            or any((row.get("start"), row.get("end")) != interval
                   or row.get("length") != interval[1]-interval[0]+1
                   or row.get("filename") != _segment_filename(destination, index, old)
                   or guard.get("filename") != row.get("filename")
                   or type(guard.get("bytes")) is not int or not 0 <= guard["bytes"] <= row["length"]
                   or not re.fullmatch(r"[0-9a-f]{64}", str(guard.get("sha256", "")))
                   for index, (row, interval, guard) in enumerate(zip(old["segments"], offsets, guards[1:])))
            or guards[1]["bytes"] != old["segments"][0]["length"]
            or new_prefix["bytes"] != sum(row["bytes"] for row in guards)
            or not old_prefix["bytes"] < new_prefix["bytes"] < plan["expected_size"]):
        raise ValueError("prepared consolidation offsets/input guards disagree with exact old plan")
    def checked(path, expected):
        before = _fingerprint(path)
        size, _, sha = _digests(path)
        if before != _fingerprint(path) or {"bytes": size, "sha256": sha} != {"bytes": expected["bytes"], "sha256": expected["sha256"]}:
            raise ValueError("consolidation input/prefix changed during prepared transaction")
    before = _fingerprint(prefix)
    size, _, sha = _digests(prefix)
    if before != _fingerprint(prefix):
        raise ValueError("consolidation prefix changed during transaction recovery")
    current = {"bytes": size, "sha256": sha}
    fragments = [_safe(destination.parent / row["filename"]) for row in guards[1:]]
    for path, guard in zip(fragments, guards[1:]):
        checked(path, guard)
    if current == old["prefix"]:
        if _concatenation_identity([prefix, *fragments]) != new_prefix:
            raise ValueError("prepared prefix disagrees with original guarded concatenation identity")
        if not staging.exists():
            computed = _copy_prefix([prefix, *fragments], staging)
            if computed != new_prefix:
                raise ValueError("recovered consolidation bytes disagree with prepared prefix")
        checked(staging, new_prefix)
        checked(prefix, guards[0])
        if plan_path.read_bytes() != prepared_plan_bytes:
            raise ValueError("prepared consolidation plan changed before prefix replacement")
        staging.chmod(0o444)
        os.replace(staging, prefix)
    elif current != new_prefix:
        raise ValueError("consolidation prefix is neither its original nor prepared version")
    _check_original_prefix_slices(prefix, guards)
    checked(prefix, new_prefix)
    remaining = plan["expected_size"]-new_prefix["bytes"]
    if remaining <= 0:
        raise ValueError("consolidation must leave unreceived archive bytes pending")
    start = new_prefix["bytes"]
    midpoint = start+(remaining+1)//2
    offsets = [(start, midpoint-1), (midpoint, plan["expected_size"]-1)] if remaining > 1 else [(start, plan["expected_size"]-1)]
    plan.update(prefix=new_prefix, fragment_generation=new_prefix["sha256"], status="pending", error="",
                upstream_checksum_verified=False)
    plan["segments"] = [{"start": left, "end": right, "length": right-left+1,
                         "filename": _segment_filename(destination, index, plan), "received": 0, "status": "pending"}
                        for index, (left, right) in enumerate(offsets)]
    intent.update(status="complete", completed_at=now())
    if plan_path.read_bytes() != prepared_plan_bytes:
        raise ValueError("prepared consolidation plan changed before final plan publication")
    _atomic_json(plan_path, plan)
    for path, guard in zip(fragments, guards[1:]):
        checked(path, guard)
        path.unlink()
    if staging.exists():
        staging.unlink()
    return {"status": "consolidated", "prefix_bytes": new_prefix["bytes"], "pending_bytes": remaining,
            "prefix_sha256": new_prefix["sha256"], "archive_verified": False, "catalog_committed": False}
