"""Acquire the exact frozen PDMX MXL/MIDI exports without changing PDF evidence.

Whole publication checksums, structural format validation and local SHA-256
objects are separate evidence. No MuseScore endpoint or conversion is used.
"""
from __future__ import annotations

import copy
import csv
import gzip
import hashlib
import json
import os
import re
import stat
import struct
import tarfile
import zipfile
from collections import Counter
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET
from xml.parsers import expat

from catalog_sources import load_registry
from source_adapters.pdmx import AccessStopped, _atomic_json, _digests, _metadata_locator, _stream_members
from source_adapters.pdmx_assets import (PUBLICATION, DEFAULT_LIMITS, _BoundedReader, _bind_authoritative_csv,
    _canonical_hash, _jobs as pdf_jobs, _member_name, _safe_local, _stat_fingerprint, _translation_hashes,
    now, source_lock)


FORMATS = {
    "MUSICXML": {"code": "mxl", "extension": "mxl", "label": "PDMX 出版 MXL（MusicXML）",
                 "summary": "verified_local_mxl"},
    "MIDI": {"code": "mid", "extension": "mid", "label": "PDMX 出版 MIDI",
             "summary": "verified_local_midi"},
}
CONFIG_PATH = "config/musescore_pdmx_formats.json"
MXL_LIMITS = {"members": 512, "member_bytes": 128*1024*1024,
              "total_bytes": 256*1024*1024, "expansion_ratio": 500}
MIDI_MAX_BYTES = 128*1024*1024


def _format(asset_format):
    try:
        return FORMATS[asset_format]
    except (KeyError, TypeError) as error:
        raise ValueError("only the reviewed MUSICXML and MIDI formats are approved") from error


def publication_url(asset_format):
    return f"https://zenodo.org/records/15571083/files/{_format(asset_format)['code']}.tar.gz"


def validate_config(config):
    if (config.get("schema_version") != 1 or config.get("source_id") != "musescore"
            or config.get("publication") != PUBLICATION or set(config.get("files", {})) != {"mxl.tar.gz", "mid.tar.gz"}
            or not isinstance(config.get("scope"), str) or not config["scope"].strip()
            or not isinstance(config.get("scope_version"), str) or not config["scope_version"].strip()):
        raise ValueError("unreviewed frozen PDMX format publication/configuration")
    for file in config["files"].values():
        if (set(file) != {"size", "md5"} or type(file.get("size")) is not int or file["size"] <= 0
                or not re.fullmatch(r"[0-9a-f]{32}", str(file.get("md5", "")))):
            raise ValueError("frozen format archive size and upstream MD5 are required")
    if "expected_records" in config and (type(config["expected_records"]) is not int or config["expected_records"] <= 0):
        raise ValueError("positive frozen record count required")
    expected_urls = {f"{info['code']}.tar.gz": publication_url(key) for key, info in FORMATS.items()}
    if "download_page_urls" in config and config["download_page_urls"] != expected_urls:
        raise ValueError("unapproved format publication page endpoint")
    limits = {**DEFAULT_LIMITS, **config.get("limits", {})}
    if set(limits) != set(DEFAULT_LIMITS) or any(type(value) is not int or value <= 0 for value in limits.values()):
        raise ValueError("positive reviewed archive limits are required")
    return limits


def _locator(value, asset_format):
    code = _format(asset_format)["code"]
    if not isinstance(value, str):
        raise ValueError("missing frozen format locator")
    value = value[2:] if value.startswith("./") else value
    if not re.fullmatch(rf"{code}/(?:0|[1-9][0-9]*)/(?:0|[1-9][0-9]*)/[A-Za-z0-9_-]+\.{code}", value):
        raise ValueError("invalid frozen format locator")
    return value


def _xml(body, context):
    # ElementTree never fetches external DTDs. Ordinary MusicXML PUBLIC DTDs
    # are allowed, while entity declarations/internal subsets are refused.
    try:
        parser = expat.ParserCreate()
        def refuse_entity(*args):
            raise ValueError(f"{context} contains an unapproved XML entity")
        def check_doctype(name, system, public, internal):
            if internal:
                raise ValueError(f"{context} contains an unapproved internal DTD")
        parser.EntityDeclHandler = refuse_entity
        parser.ExternalEntityRefHandler = refuse_entity
        parser.StartDoctypeDeclHandler = check_doctype
        parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
        parser.Parse(body, True)
        return ET.fromstring(body)
    except (ET.ParseError, expat.ExpatError, ValueError) as error:
        raise ValueError(f"{context} is not complete parseable XML") from error


def _tag(element):
    return element.tag.rsplit("}", 1)[-1]


def _zip_name(name):
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or ".." in path.parts or "\\" in name or "\x00" in name
            or re.match(r"^[A-Za-z]:", name) or not path.parts):
        raise ValueError("unsafe MXL ZIP member path")
    return str(path)


def validate_mxl(path):
    try:
        with Path(path).open("rb") as stream:
            stream.seek(0, os.SEEK_END)
            size = stream.tell()
            stream.seek(0)
            if stream.read(4) != b"PK\x03\x04":
                raise ValueError("MXL ZIP has a prepended payload or absent local header")
            stream.seek(max(0,size-65557))
            tail = stream.read()
        end = tail.rfind(b"PK\x05\x06")
        if end < 0 or end+22 > len(tail):
            raise ValueError("MXL ZIP end-of-central-directory is absent")
        disk, central_disk, disk_count, count, central_size, central_offset, comment = struct.unpack("<HHHHIIH",tail[end+4:end+22])
        end_offset = max(0,size-65557)+end
        if (end+22+comment != len(tail) or disk or central_disk or disk_count != count or not count
                or count == 0xffff or central_size == 0xffffffff or central_offset == 0xffffffff
                or central_offset+central_size != end_offset):
            raise ValueError("MXL ZIP has trailing payload or invalid/multipart/ZIP64 directory")
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            if not members or len(members) != count or len(members) > MXL_LIMITS["members"] or min(entry.header_offset for entry in members) != 0:
                raise ValueError("MXL ZIP member limit exceeded or empty container")
            seen, bodies, infos, total = set(), {}, {}, 0
            for info in members:
                name = _zip_name(info.filename)
                if name in seen:
                    raise ValueError("duplicate MXL ZIP member path")
                seen.add(name)
                infos[name] = info
                kind = (info.external_attr >> 16) & 0o170000
                if kind not in {0, stat.S_IFREG, stat.S_IFDIR} or info.flag_bits & 1:
                    raise ValueError("MXL ZIP links/special files/encryption are not approved")
                if info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                    raise ValueError("unsupported MXL ZIP compression method")
                if info.is_dir():
                    if info.file_size:
                        raise ValueError("MXL ZIP directory must be empty")
                    if archive.read(info) != b"":
                        raise ValueError("MXL ZIP directory data/CRC is invalid")
                    continue
                if kind == stat.S_IFDIR or info.file_size > MXL_LIMITS["member_bytes"]:
                    raise ValueError("MXL ZIP member size/type limit exceeded")
                total += info.file_size
                if total > MXL_LIMITS["total_bytes"] or info.file_size > max(1, info.compress_size)*MXL_LIMITS["expansion_ratio"]:
                    raise ValueError("MXL ZIP expansion limit exceeded")
                body = archive.read(info)  # All members are read; ZipFile verifies CRC.
                if len(body) != info.file_size:
                    raise ValueError("MXL ZIP member actual size mismatch")
                if name == "META-INF/container.xml" or name.lower().endswith((".xml", ".musicxml")):
                    bodies[name] = body
            if "META-INF/container.xml" not in bodies:
                raise ValueError("MXL is missing META-INF/container.xml")
            container = _xml(bodies["META-INF/container.xml"], "MXL container")
            if _tag(container) != "container":
                raise ValueError("MXL container XML root is invalid")
            roots = [entry for parent in container if _tag(parent) == "rootfiles" for entry in parent if _tag(entry) == "rootfile"]
            musical_types = {None,"application/vnd.recordare.musicxml+xml"}
            if not roots or roots[0].get("media-type") not in musical_types or any(entry.get("media-type") in musical_types for entry in roots[1:]):
                raise ValueError("MXL container must name one primary MusicXML score root")
            declared = roots[0].get("full-path", "")
            score_name = _zip_name(declared)
            if score_name not in infos or infos[score_name].is_dir():
                raise ValueError("MXL container score root does not name a stored XML member")
            score_body = bodies[score_name] if score_name in bodies else archive.read(infos[score_name])
            score = _xml(score_body, "MusicXML score")
            root_tag = _tag(score)
            if root_tag not in {"score-partwise", "score-timewise"}:
                raise ValueError("MXL score root is not MusicXML notation")
            lists = [entry for entry in score if _tag(entry) == "part-list"]
            if len(lists) != 1:
                raise ValueError("MusicXML score must have one part-list")
            part_ids = [entry.get("id", "") for entry in lists[0] if _tag(entry) == "score-part"]
            if not part_ids or any(not value for value in part_ids) or len(set(part_ids)) != len(part_ids):
                raise ValueError("MusicXML score-part identifiers are absent/duplicate")
            if root_tag == "score-partwise":
                parts = [entry for entry in score if _tag(entry) == "part"]
                if not parts or {entry.get("id") for entry in parts} != set(part_ids) or len(parts) != len(part_ids):
                    raise ValueError("MusicXML parts and part-list disagree")
                if any(not any(_tag(entry) == "measure" for entry in part) for part in parts):
                    raise ValueError("MusicXML score part has no measures")
            else:
                measures = [entry for entry in score if _tag(entry) == "measure"]
                if not measures or any({entry.get("id") for entry in measure if _tag(entry) == "part"} != set(part_ids) for measure in measures):
                    raise ValueError("MusicXML timewise measures and part-list disagree")
            return {"format": "MUSICXML", "score_root": root_tag, "score_member": score_name,
                    "parts": len(part_ids), "zip_members": len(members), "uncompressed_bytes": total,
                    "crc_status": "all_members_verified", "external_dtd_fetched": False}
    except (zipfile.BadZipFile, RuntimeError, EOFError, NotImplementedError) as error:
        raise ValueError("invalid/corrupt MXL ZIP container") from error


def _vlq(body, offset):
    value = 0
    for _ in range(4):
        if offset >= len(body):
            raise ValueError("truncated MIDI variable-length quantity")
        byte = body[offset]
        offset += 1
        value = (value << 7) | (byte & 0x7f)
        if not byte & 0x80:
            return value, offset
    raise ValueError("MIDI variable-length quantity exceeds four bytes")


def _midi_track(body):
    offset, running, events, ticks, ended = 0, None, 0, 0, False
    while offset < len(body):
        delta, offset = _vlq(body, offset)
        ticks += delta
        if offset >= len(body):
            raise ValueError("truncated MIDI event status")
        status = body[offset]
        if status >= 0x80:
            offset += 1
        elif running is None:
            raise ValueError("MIDI running status has no channel predecessor")
        else:
            status = running
        events += 1
        if 0x80 <= status <= 0xef:
            running = status
            length = 1 if status >> 4 in {0xc, 0xd} else 2
            if offset+length > len(body) or any(value >= 0x80 for value in body[offset:offset+length]):
                raise ValueError("MIDI channel event data is truncated/out of range")
            offset += length
        elif status == 0xff:
            running = None
            if offset >= len(body) or body[offset] >= 0x80:
                raise ValueError("invalid MIDI meta event type")
            kind = body[offset]
            length, offset = _vlq(body, offset+1)
            if offset+length > len(body):
                raise ValueError("truncated MIDI meta event payload")
            data = body[offset:offset+length]
            fixed = {0x00: 2, 0x20: 1, 0x21: 1, 0x2f: 0, 0x51: 3, 0x54: 5, 0x58: 4, 0x59: 2}
            if kind in fixed and length != fixed[kind]:
                raise ValueError("MIDI fixed meta event has incorrect length")
            if kind == 0x20 and data[0] > 15 or kind == 0x21 and data[0] > 127:
                raise ValueError("MIDI channel/port meta event is out of range")
            if kind == 0x51 and int.from_bytes(data, "big") == 0:
                raise ValueError("MIDI tempo must be positive")
            if kind == 0x59 and (int.from_bytes(data[:1], "big", signed=True) not in range(-7, 8) or data[1] not in {0,1}):
                raise ValueError("MIDI key signature is out of range")
            offset += length
            if kind == 0x2f:
                if offset != len(body):
                    raise ValueError("MIDI bytes follow end-of-track")
                ended = True
        elif status in {0xf0, 0xf7}:
            running = None
            length, offset = _vlq(body, offset)
            if offset+length > len(body):
                raise ValueError("truncated MIDI sysex payload")
            offset += length
        else:
            raise ValueError("unsupported MIDI system event in standard MIDI file")
    if not ended:
        raise ValueError("MIDI track is missing end-of-track")
    return events, ticks


def validate_midi(path):
    size = path.stat().st_size
    if size > MIDI_MAX_BYTES:
        raise ValueError("MIDI file size limit exceeded")
    body = path.read_bytes()
    if len(body) != size or len(body) < 14 or body[:4] != b"MThd":
        raise ValueError("MIDI header is absent or truncated")
    length, fmt, tracks, division = struct.unpack(">IHHH", body[4:14])
    if length != 6 or fmt not in {0,1,2} or not tracks or fmt == 0 and tracks != 1:
        raise ValueError("MIDI header length/format/track count is invalid")
    if division & 0x8000:
        frames = int.from_bytes(bytes([division >> 8]), "big", signed=True)
        if frames not in {-24,-25,-29,-30} or not division & 0xff:
            raise ValueError("MIDI SMPTE division is invalid")
    elif division == 0:
        raise ValueError("MIDI ticks per quarter must be positive")
    offset, events, max_ticks = 14, 0, 0
    for _ in range(tracks):
        if offset+8 > len(body) or body[offset:offset+4] != b"MTrk":
            raise ValueError("MIDI declared track chunk is absent/truncated")
        track_length = int.from_bytes(body[offset+4:offset+8], "big")
        offset += 8
        if offset+track_length > len(body):
            raise ValueError("MIDI track chunk length exceeds file")
        count, ticks = _midi_track(body[offset:offset+track_length])
        events += count
        max_ticks = max(max_ticks, ticks)
        offset += track_length
    if offset != len(body):
        raise ValueError("MIDI file has trailing or undeclared chunks")
    return {"format": "MIDI", "midi_format": fmt, "tracks": tracks, "division": division,
            "events": events, "maximum_track_ticks": max_ticks, "end_of_track_status": "all_tracks_verified"}


def validate_source_format(path, asset_format):
    """Validate notation/archive or SMF bytes without claiming musical fidelity."""
    _format(asset_format)
    path = Path(path)
    before = _stat_fingerprint(path)
    if before[2] <= 0:
        raise ValueError("empty score format file")
    result = validate_mxl(path) if asset_format == "MUSICXML" else validate_midi(path)
    if _stat_fingerprint(path) != before:
        raise ValueError("score format file changed during structural verification")
    return result


@contextmanager
def _source_locks(root):
    # The legacy PDF lock is shared, so no old PDF writer can race this catalog.
    with source_lock(_safe_local(root, root / "sources/musescore/.pdf-acquisition.lock")):
        with source_lock(_safe_local(root, root / "sources/musescore/.formats-acquisition.lock")):
            yield


def _jobs(catalog, asset_format, registry):
    base = pdf_jobs(catalog, registry)
    code = _format(asset_format)["code"]
    jobs = {}
    for work in catalog["works"]:
        row = work["metadata"]["pdmx_csv_transcription"]
        # Both extra locators are protected independent author transcriptions.
        for key in FORMATS:
            _locator(row.get(_format(key)["code"]), key)
        assets = [(index, asset) for index, asset in enumerate(work["assets"]) if asset.get("format") == asset_format]
        if len(assets) != 1:
            raise ValueError("each frozen native record must retain exactly one target format asset")
        jobs[work["id"]] = {"member": _locator(row[code], asset_format), "asset_index": assets[0][0], "prior_asset": assets[0][1]}
    if set(jobs) != set(base):
        raise ValueError("format/PDF frozen native scope drift")
    return jobs


def _bind_csv(root, catalog, jobs):
    receipt, guard = _bind_authoritative_csv(root, catalog, jobs)
    wanted = {identity.split(":",1)[1] for identity in jobs}
    rows = {}
    with guard["csv"].open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        if not reader.fieldnames or not {"metadata", "mxl", "mid"}.issubset(reader.fieldnames):
            raise ValueError("authoritative CSV missing format binding fields")
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError("malformed authoritative CSV format row")
            try:
                native_id, _ = _metadata_locator(row["metadata"])
            except ValueError:
                continue
            if native_id not in wanted:
                continue
            if native_id in rows:
                raise ValueError("duplicate authoritative CSV native format row")
            rows[native_id] = {key: row[key] for key in ("mxl", "mid")}
    if wanted != set(rows) or _stat_fingerprint(guard["csv"]) != guard["fingerprint"]:
        raise ValueError("authoritative CSV format scope/integrity drift")
    for work in catalog["works"]:
        for key, value in rows[work["id"].split(":",1)[1]].items():
            if work["metadata"]["pdmx_csv_transcription"].get(key) != value:
                raise ValueError(f"authoritative CSV format binding mismatch: {work['id']} {key}")
    receipt.update(format_binding_fields=["mxl", "mid"], bound_format_rows_sha256=_canonical_hash(rows))
    return receipt, guard


def _protected(catalog, asset_format=None):
    result = copy.deepcopy(catalog)
    removed = {asset_format} if asset_format else set(FORMATS)
    for kind in removed:
        result.get("summary", {}).pop(_format(kind)["summary"], None)
    for work in result["works"]:
        work["assets"] = [asset for asset in work["assets"] if asset.get("format") not in removed]
    return result


def _summary(records):
    counts = Counter(row["status"] for row in records)
    return {"source_records": len(records), "verified_records": counts["verified"], "failed_records": counts["failed"],
            "missing_records": counts["missing"], "pending_records": counts["pending"],
            "unique_format_objects": len({row["asset"]["sha256"] for row in records if row["status"] == "verified"})}


def _prepare(root, asset_format):
    config_path = _safe_local(root, root / CONFIG_PATH)
    config_bytes = config_path.read_bytes()
    config = json.loads(config_bytes)
    limits = validate_config(config)
    catalog_path = _safe_local(root, root / "sources/musescore/catalog.json")
    original_bytes = catalog_path.read_bytes()
    catalog = json.loads(original_bytes)
    jobs = _jobs(catalog, asset_format, load_registry(root))
    if "expected_records" in config and len(jobs) != config["expected_records"]:
        raise ValueError("native format scope does not equal frozen approved record count")
    csv_receipt, csv_guard = _bind_csv(root, catalog, jobs)
    report = {"schema_version": 1, "source_id": "musescore", "publication": PUBLICATION, "format": asset_format,
        "status": "pending_archive", "started_at": now(), "scope": config["scope"], "scope_version": config["scope_version"],
        "configuration_sha256": hashlib.sha256(config_bytes).hexdigest(),
        "input_catalog_sha256": hashlib.sha256(original_bytes).hexdigest(),
        "protected_source_catalog_sha256": _canonical_hash(_protected(catalog)),
        "preserved_other_format_catalog_sha256": _canonical_hash(_protected(catalog, asset_format)),
        "translation_input_sha256": _translation_hashes(root), "snapshot_unchanged": True,
        "catalog_committed": False, "live_source_requests": 0, "archive_checked_this_run": False,
        "csv_binding": csv_receipt, "records": [{"id": identity, "archive_member": job["member"], "status": "pending"}
        for identity, job in jobs.items()]}
    report["counts"] = _summary(report["records"])
    return config, limits, catalog, jobs, report, (config_path, config_bytes, catalog_path, original_bytes, csv_guard)


def _journal_path(root, asset_format):
    return _safe_local(root, root / f"sources/musescore/pdmx/{_format(asset_format)['code']}-extraction.json")


def _check_previous(previous, report):
    if (previous.get("schema_version") != 1 or previous.get("publication") != PUBLICATION
            or previous.get("source_id") != "musescore" or previous.get("format") != report["format"]
            or previous.get("configuration_sha256") != report["configuration_sha256"]
            or previous.get("protected_source_catalog_sha256") != report["protected_source_catalog_sha256"]
            or previous.get("translation_input_sha256") != report["translation_input_sha256"]):
        raise ValueError("stale or malformed format acquisition journal/source/translation guard")
    expected = {row["id"]: row["archive_member"] for row in report["records"]}
    rows = previous.get("records", [])
    if not isinstance(rows, list) or len(rows) != len(expected) or {row.get("id"):row.get("archive_member") for row in rows} != expected:
        raise ValueError("prior format journal native scope/locator drift")


def initialize_pending_journal(root, *, asset_format):
    root = Path(root).resolve()
    _format(asset_format)
    with _source_locks(root):
        _, _, _, _, report, _ = _prepare(root, asset_format)
        path = _journal_path(root, asset_format)
        if path.is_file():
            previous = json.loads(path.read_text())
            _check_previous(previous, report)
            return previous
        _atomic_json(path, report)
        return report


def download_parallel_archive(root, *, asset_format, client=None):
    from source_adapters.zenodo_download import RangeClient, download_file
    root = Path(root).resolve()
    initialize_pending_journal(root, asset_format=asset_format)
    info = _format(asset_format)
    with _source_locks(root):
        _refuse_stopped_source(root)
        config, _, _, _, report, guards = _prepare(root, asset_format)
        _check_previous(json.loads(_journal_path(root, asset_format).read_text()), report)
        expected = config["files"][info["code"]+".tar.gz"]
        url = publication_url(asset_format)
        receipt = download_file(url, _safe_local(root, root / f"sources/musescore/pdmx/{info['code']}.tar.gz"),
            expected_size=expected["size"], expected_md5=expected["md5"], client=client or RangeClient(page_url=url),
            plan_path=_safe_local(root, root / f"sources/musescore/pdmx/{info['code']}-range-plan.json"),
            receipt_path=_safe_local(root, root / f"sources/musescore/pdmx/{info['code']}-receipt.json"))
        config_path, config_bytes, catalog_path, original_bytes, csv_guard = guards
        if config_path.read_bytes() != config_bytes or catalog_path.read_bytes() != original_bytes:
            raise ValueError("format source/configuration changed during archive transfer")
        if _stat_fingerprint(csv_guard["csv"]) != csv_guard["fingerprint"]:
            raise ValueError("authoritative CSV changed during archive transfer")
        return receipt


def rebalance_ranges(root, *, asset_format):
    """Explicit local range allocation; does not acquire or publish score files."""
    from source_adapters.zenodo_download import rebalance_received_ranges
    root = Path(root).resolve()
    info = _format(asset_format)
    config_path = _safe_local(root,root / CONFIG_PATH)
    config_bytes = config_path.read_bytes()
    config = json.loads(config_bytes)
    validate_config(config)
    _refuse_stopped_source(root)
    expected = config["files"][info["code"]+".tar.gz"]
    result = rebalance_received_ranges(_safe_local(root,root / f"sources/musescore/pdmx/{info['code']}.tar.gz"),
        page_url=publication_url(asset_format),expected_size=expected["size"],expected_md5=expected["md5"],
        source_lock_path=_safe_local(root,root / "sources/musescore/.pdf-acquisition.lock"),
        plan_path=_safe_local(root,root / f"sources/musescore/pdmx/{info['code']}-range-plan.json"))
    if config_path.read_bytes() != config_bytes:
        raise ValueError("format acquisition configuration changed during local rebalance")
    return result


def _refuse_stopped_source(root):
    """A refusal on any format stops this publication source before a new URL."""
    from source_adapters.zenodo_download import _source_refused
    base = _safe_local(root, root / "sources/musescore/pdmx")
    for code in ("pdf","mxl","mid"):
        for suffix in ("range-plan","extraction"):
            path = _safe_local(root,base / f"{code}-{suffix}.json")
            if not path.is_file():
                continue
            journal = json.loads(path.read_text())
            if not isinstance(journal,dict):
                raise ValueError("malformed source access journal; network acquisition stopped")
            if _source_refused(journal):
                raise AccessStopped(f"publication source access was refused in {code}-{suffix}; no new format request made")


def _validate_object(root, asset, asset_format, *, provenance=True):
    info = _format(asset_format)
    if provenance and (asset.get("status") != "verified" or asset.get("format") != asset_format
            or asset.get("publication") != PUBLICATION or _locator(asset.get("archive_member"), asset_format) != asset.get("archive_member")
            or not re.fullmatch(r"[0-9a-f]{64}", str(asset.get("archive_sha256", "")))
            or not re.fullmatch(r"md5:[0-9a-f]{32}", str(asset.get("archive_upstream_checksum", "")))
            or asset.get("archive_checksum_status") != "md5_verified" or asset.get("upstream_checksum_status") != "not_supplied"):
        raise ValueError("invalid verified format provenance")
    digest, size = asset.get("sha256", ""), asset.get("size")
    if not re.fullmatch(r"[0-9a-f]{64}", digest) or type(size) is not int or size <= 0:
        raise ValueError("invalid immutable format object receipt")
    path = _safe_local(root, root / f"sources/musescore/objects/{digest}.{info['extension']}")
    if asset.get("local_path") != str(path.relative_to(root)):
        raise ValueError("immutable format object locator drift")
    before = _stat_fingerprint(path)
    if before[2] != size:
        raise ValueError("immutable format object size mismatch")
    validation = validate_source_format(path, asset_format)
    with path.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
            raise ValueError("immutable format object checksum mismatch")
    if _stat_fingerprint(path) != before:
        raise ValueError("immutable format object changed during fresh verification")
    return validation


def _store(root, part, digest, size, asset_format):
    extension = _format(asset_format)["extension"]
    pool = _safe_local(root, root / f"sources/objects/sha256/{digest[:2]}/{digest}.{extension}")
    local = _safe_local(root, root / f"sources/musescore/objects/{digest}.{extension}")
    pool.parent.mkdir(parents=True, exist_ok=True)
    local.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(part, pool)
    except FileExistsError:
        before = _stat_fingerprint(pool)
        if before[2] != size:
            raise ValueError("immutable format pool size mismatch")
        validate_source_format(pool, asset_format)
        with pool.open("rb") as stream:
            if hashlib.file_digest(stream,"sha256").hexdigest() != digest:
                raise ValueError("immutable format pool checksum mismatch")
        if _stat_fingerprint(pool) != before:
            raise ValueError("immutable format pool changed during verification")
    if local.exists():
        _validate_object(root, {"sha256":digest,"size":size,"local_path":str(local.relative_to(root))}, asset_format, provenance=False)
        if (pool.stat().st_dev,pool.stat().st_ino) == (local.stat().st_dev,local.stat().st_ino):
            return str(local.relative_to(root))
    temporary = _safe_local(root, local.with_name(local.name+".part"))
    if temporary.exists():
        temporary.unlink()
    os.link(pool, temporary)
    os.replace(temporary, local)
    return str(local.relative_to(root))


def _verified_asset(size, digest, local, member, receipt, asset_format, validation):
    return {"format": asset_format, "status": "verified", "label": _format(asset_format)["label"], "size": size,
        "sha256": digest, "local_path": local, "archive_member": member, "archive_sha256": receipt["sha256"],
        "archive_upstream_checksum": receipt["upstream_checksum"], "archive_checksum_status": "md5_verified",
        "upstream_checksum_status": "not_supplied", "publication": PUBLICATION, "validation": validation, "verified_at": now()}


def _write_summary(root):
    formats = {}
    for key in FORMATS:
        path = _journal_path(root, key)
        if path.is_file():
            try:
                journal = json.loads(path.read_text())
                if not isinstance(journal,dict) or journal.get("format") != key:
                    raise ValueError("malformed format journal")
                formats[key] = {field: journal[field] for field in ("status","counts","archive_counts","completed_at","catalog_committed") if field in journal}
            except (ValueError,TypeError) as error:
                formats[key] = {"status":"invalid_journal","error":str(error),"catalog_committed":"unknown"}
    _atomic_json(_safe_local(root, root / "sources/musescore/formats-acquisition-report.json"),
                 {"schema_version":1,"source_id":"musescore","publication":PUBLICATION,"updated_at":now(),"formats":formats})


def acquire(root, *, asset_format, cached_archive=True, batch_size=25):
    if not cached_archive:
        download_parallel_archive(root, asset_format=asset_format)
    if type(batch_size) is not int or batch_size <= 0:
        raise ValueError("positive acquisition checkpoint batch size required")
    root = Path(root).resolve()
    _format(asset_format)
    with _source_locks(root):
        return _acquire_locked(root, asset_format, batch_size)


def _acquire_locked(root, asset_format, batch_size):
    config, limits, catalog, jobs, report, guards = _prepare(root, asset_format)
    config_path, config_bytes, catalog_path, original_bytes, csv_guard = guards
    info = _format(asset_format)
    base = root / "sources/musescore"
    journal_path = _journal_path(root, asset_format)
    previous = json.loads(journal_path.read_text()) if journal_path.is_file() else None
    if previous:
        _check_previous(previous, report)
    report.update(status="running", fresh_verified_prior_records=0, fresh_verified_staged_members=0)
    states = {row["id"]:row for row in report["records"]}
    archive = _safe_local(root, base / f"pdmx/{info['code']}.tar.gz")
    receipt_path = _safe_local(root, base / f"pdmx/{info['code']}-receipt.json")
    selected, counts = {}, Counter()
    _atomic_json(journal_path, report)
    try:
        if not archive.is_file():
            raise ValueError("cached format archive is missing; use --parallel-archive")
        fingerprint = _stat_fingerprint(archive)
        size, md5, sha = _digests(archive)
        expected = config["files"][info["code"]+".tar.gz"]
        if _stat_fingerprint(archive) != fingerprint or size != expected["size"] or md5 != expected["md5"]:
            raise ValueError("cached format archive checksum/integrity failed; no network request made")
        prior = json.loads(receipt_path.read_text()) if receipt_path.is_file() else {}
        url = publication_url(asset_format)
        preserve = (prior.get("url") == url and prior.get("bytes") == size and prior.get("sha256") == sha
                    and prior.get("upstream_checksum") == "md5:"+md5 and prior.get("upstream_checksum_verified") is True)
        receipt = {**(prior if preserve else {}), "url":url,"final_url":url,"bytes":size,"sha256":sha,
                   "upstream_checksum":"md5:"+md5,"upstream_checksum_verified":True,"cached":True,"checked_at":now()}
        _atomic_json(receipt_path, receipt)
        report.update(archive_integrity=receipt, archive_checked_this_run=True)
        fresh = {}
        for identity, job in jobs.items():
            prior = job["prior_asset"]
            if prior.get("status") == "verified":
                try:
                    validation = _validate_object(root, prior, asset_format)
                    if prior.get("archive_member") != job["member"] or prior.get("archive_sha256") != receipt["sha256"]:
                        raise ValueError("prior format publication/member evidence drift")
                    fresh[job["member"]] = (prior, validation)
                    report["fresh_verified_prior_records"] += 1
                except (OSError, ValueError, RuntimeError) as error:
                    states[identity]["prior_verification_error"] = str(error)
        candidates = previous.get("staged_members", {}) if previous else {}
        if previous and previous.get("archive_integrity",{}).get("sha256") == receipt["sha256"]:
            for name, staged in candidates.items():
                if name in fresh or name not in {job["member"] for job in jobs.values()} or staged.get("status") != "verified":
                    continue
                try:
                    asset = staged["asset"]
                    validation = _validate_object(root, asset, asset_format)
                    if asset.get("archive_member") != name or asset.get("archive_sha256") != receipt["sha256"]:
                        raise ValueError("staged format member evidence drift")
                    fresh[name] = (asset, validation)
                    report["fresh_verified_staged_members"] += 1
                except (OSError, ValueError, RuntimeError):
                    continue
        wanted = {job["member"] for job in jobs.values()}
        partials = _safe_local(root, base / "partials")
        partials.mkdir(parents=True, exist_ok=True)
        def checkpoint():
            report.update(archive_counts=dict(counts), staged_members=selected,
                          counts=_summary(report["records"]), updated_at=now())
            _atomic_json(journal_path, report)
        checkpoint()
        seen = set()
        with archive.open("rb") as compressed, gzip.GzipFile(fileobj=compressed) as decompressed:
            bounded = _BoundedReader(decompressed, min(limits["max_total_bytes"], receipt["bytes"]*limits["max_expansion_ratio"]))
            with tarfile.open(fileobj=bounded, mode="r|") as tar:
                for entry in _stream_members(tar):
                    counts["archive_members"] += 1
                    if counts["archive_members"] > limits["max_members"]:
                        raise ValueError("archive member limit exceeded")
                    name = _member_name(entry)
                    if name in seen:
                        raise ValueError("duplicate archive member path")
                    seen.add(name)
                    if entry.isdir():
                        if entry.size:
                            raise ValueError("archive directory size must be zero")
                        continue
                    if entry.size < 0 or entry.size > limits["max_member_bytes"]:
                        raise ValueError("archive member size limit exceeded")
                    counts["archive_regular_bytes"] += entry.size
                    if counts["archive_regular_bytes"] > limits["max_total_bytes"]:
                        raise ValueError("archive regular total size limit exceeded")
                    if name not in wanted:
                        continue
                    counts["selected_members"] += 1
                    counts["selected_bytes"] += entry.size
                    if counts["selected_bytes"] > limits["max_selected_bytes"]:
                        raise ValueError("selected format size limit exceeded")
                    result = {"status":"failed","archive_member":name}
                    part = _safe_local(root, partials / (hashlib.sha256(name.encode()).hexdigest()+f".{info['extension']}.part"))
                    try:
                        existing = fresh.get(name)
                        source = tar.extractfile(entry)
                        if source is None:
                            raise ValueError("selected format archive member cannot be read")
                        if existing and existing[0]["size"] == entry.size:
                            with source:
                                digest = hashlib.file_digest(source,"sha256").hexdigest()
                            if digest != existing[0]["sha256"]:
                                raise ValueError("archive member checksum disagrees with prior format object")
                            asset = _verified_asset(entry.size,digest,existing[0]["local_path"],name,receipt,asset_format,existing[1])
                            counts["reused_verified_members"] += 1
                        else:
                            digest, received = hashlib.sha256(), 0
                            with source, part.open("wb") as destination:
                                while block := source.read(1024*1024):
                                    received += len(block)
                                    if received > entry.size:
                                        raise ValueError("selected format member exceeds declared size")
                                    digest.update(block)
                                    destination.write(block)
                                destination.flush()
                                os.fsync(destination.fileno())
                            if received != entry.size:
                                raise ValueError("selected format member size mismatch")
                            validation = validate_source_format(part,asset_format)
                            digest = digest.hexdigest()
                            local = _store(root,part,digest,received,asset_format)
                            asset = _verified_asset(received,digest,local,name,receipt,asset_format,validation)
                        result = {"status":"verified","asset":asset}
                    except (OSError, ValueError, RuntimeError) as error:
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
                if tar.fileobj.tell()-tar.offset < tarfile.BLOCKSIZE:
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
        if _stat_fingerprint(archive) != fingerprint:
            raise ValueError("format archive changed during verification/stream scan")
        for identity, job in jobs.items():
            if job["member"] not in selected:
                states[identity].update(status="missing",reason="exact frozen format member absent from verified archive")
        checkpoint()
        updated = copy.deepcopy(catalog)
        for work in updated["works"]:
            state = states[work["id"]]
            asset = state.get("asset") if state["status"] == "verified" else {"format":asset_format,"status":state["status"],
                "label":info["label"],"publication":PUBLICATION,"archive_member":state["archive_member"],
                "reason":state["reason"],"checked_at":now()}
            work["assets"][jobs[work["id"]]["asset_index"]] = asset
        updated.setdefault("summary",{})[info["summary"]] = sum(state["status"] == "verified" for state in states.values())
        if _canonical_hash(_protected(updated,asset_format)) != report["preserved_other_format_catalog_sha256"]:
            raise ValueError("prior PDF/other format or nonasset source metadata changed")
        if _translation_hashes(root) != report["translation_input_sha256"]:
            raise ValueError("translation bytes changed during acquisition; catalog preserved")
        if (catalog_path.read_bytes() != original_bytes or config_path.read_bytes() != config_bytes
                or _stat_fingerprint(csv_guard["csv"]) != csv_guard["fingerprint"]
                or csv_guard["config"].read_bytes() != csv_guard["config_bytes"]):
            raise ValueError("catalog/source/configuration changed before atomic format commit")
        _atomic_json(catalog_path,updated)
        report.pop("staged_members",None)
        report.update(status="complete",completed_at=now(),catalog_committed=True,counts=_summary(report["records"]),
                      archive_counts=dict(counts),translation_bytes_unchanged=True,
                      output_catalog_sha256=hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
                      preserved_other_format_catalog_after_sha256=_canonical_hash(_protected(updated,asset_format)))
        _atomic_json(journal_path,report)
        _write_summary(root)
        return report
    except BaseException as error:
        report.update(status="committed_receipt_error" if report.get("catalog_committed") else "stopped_access" if isinstance(error,AccessStopped) else "interrupted" if isinstance(error,KeyboardInterrupt) else "failed_archive",
                      completed_at=now(),error=str(error),counts=_summary(report["records"]),staged_members=selected)
        _atomic_json(journal_path,report)
        _write_summary(root)
        raise
