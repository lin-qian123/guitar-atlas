#!/usr/bin/env python
"""Complete read-only MXL archive recall audit, independent of old metadata scope.

All ZIP members have CRC/path/type/expansion checks. Complete C XML parsers
validate notation without external resources and release each bounded tree. Only part-list,
instrument, TAB-clef and playback-program signals are retained as candidates;
they do not establish acoustic construction or the number of performers.
"""
from __future__ import annotations

import argparse
from collections import Counter, deque
from concurrent.futures import ProcessPoolExecutor
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import tarfile
import zipfile
import zlib

from audit_pdmx_metadata_scope import GUITAR
from review_musescore_instrumentation import kind_from_label

ABBREVIATED_GUITAR = re.compile(r"guit|gitarr|gitar|chitar|acnylonguit|\bgtr\.?|gt\.ar\.", re.I)
from build_musescore_library import atomic_json
from source_adapters.pdmx import _metadata_locator, _stream_members
from source_adapters.pdmx_formats import MXL_LIMITS, _locator, _tag, _xml, _zip_name, validate_config


def fingerprint(path):
    v = Path(path).stat()
    return [v.st_dev, v.st_ino, v.st_size, v.st_mtime_ns, v.st_ctime_ns]


def local_tag(value):
    return value.rsplit("}", 1)[-1].rsplit(":", 1)[-1]


def musicxml_scope(body: bytes) -> dict:
    """Complete C XML validation/tree parse; inspect only score-level structures.

    The shared parser rejects entities/internal DTDs and never requests external
    resources. Complete trees are released per bounded MXL, not retained across
    the corpus. Inner note children are not walked in Python.
    """
    root = _xml(body, "full-corpus MusicXML")
    root_name = _tag(root)
    if root_name not in {"score-partwise", "score-timewise"}:
        raise ValueError("not a MusicXML notation root")
    prefix = root.tag.rsplit("}", 1)[0] + "}" if "}" in root.tag else ""
    q = lambda name: prefix + name
    lists = root.findall(q("part-list"))
    if len(lists) != 1: raise ValueError("MusicXML must have one part-list")
    declarations, warnings = {}, []
    for part in lists[0].findall(q("score-part")):
        part_id = part.get("id")
        if not part_id or part_id in declarations: raise ValueError("absent/duplicate score-part identifier")
        row = {"id": part_id, "part_names": [], "instrument_names": [], "instrument_sounds": [],
               "instrument_ids": [], "midi_programs_1based": [], "note_count": 0, "rest_count": 0,
               "harmony_count": 0, "frame_count": 0, "slash_count": 0}
        for name in ("part-name", "part-abbreviation"):
            for node in part.findall(q(name)):
                value = "".join(node.itertext()).strip()
                if value and value not in row["part_names"]: row["part_names"].append(value)
        for node in part.findall(q("score-instrument")) + part.findall(q("midi-instrument")):
            value = node.get("id")
            if value and value not in row["instrument_ids"]: row["instrument_ids"].append(value)
            for name, field in (("instrument-name", "instrument_names"), ("instrument-abbreviation", "instrument_names"),
                                ("instrument-sound", "instrument_sounds"), ("instrument-id", "instrument_ids")):
                for child in node.findall(q(name)):
                    value = "".join(child.itertext()).strip()
                    if value and value not in row[field]: row[field].append(value)
            for child in node.findall(q("midi-program")):
                value = (child.text or "").strip()
                if re.fullmatch(r"[1-9][0-9]*", value) and 1 <= int(value) <= 128:
                    if int(value) not in row["midi_programs_1based"]: row["midi_programs_1based"].append(int(value))
                else: warnings.append({"part_id": part_id, "reason": "invalid_midi_program", "value": value})
        declarations[part_id] = row
    if not declarations: raise ValueError("MusicXML has no declared parts")
    ids, tab_parts, tuning_parts = set(declarations), set(), set()
    def measure(part_id, node):
        row = declarations[part_id]
        notes, rests = len(node.findall(q("note"))), len(node.findall(q("note") + "/" + q("rest")))
        row["note_count"] += max(0, notes - rests)
        row["rest_count"] += rests
        row["harmony_count"] += len(node.findall(q("harmony")))
        row["frame_count"] += len(node.findall(q("harmony") + "/" + q("frame")))
        row["slash_count"] += len(node.findall(q("attributes") + "/" + q("measure-style") + "/" + q("slash")))
        for attributes in node.findall(q("attributes")):
            for clef in attributes.findall(q("clef")):
                if (clef.findtext(q("sign"), "").strip().upper() == "TAB"): tab_parts.add(part_id)
            if attributes.find(q("staff-details") + "/" + q("staff-tuning") + "/" + q("tuning-step")) is not None:
                tuning_parts.add(part_id)
    if root_name == "score-partwise":
        actual = root.findall(q("part"))
        if len(actual) != len(ids) or {p.get("id") for p in actual} != ids:
            raise ValueError("MusicXML part-list/actual parts disagree")
        for part in actual:
            measures = part.findall(q("measure"))
            if not measures: raise ValueError("MusicXML part has no measures")
            for node in measures: measure(part.get("id"), node)
    else:
        measures = root.findall(q("measure"))
        if not measures: raise ValueError("MusicXML timewise score has no measures")
        for node in measures:
            parts = node.findall(q("part"))
            if len(parts) != len(ids) or {p.get("id") for p in parts} != ids:
                raise ValueError("MusicXML timewise measures/part-list disagree")
            for part in parts: measure(part.get("id"), part)
    labels = [{"part_id": p["id"], "field": field, "text": value}
              for p in declarations.values() for field in ("part_names", "instrument_names", "instrument_sounds", "instrument_ids")
              for value in p[field] if GUITAR.search(value) or ABBREVIATED_GUITAR.search(value) or kind_from_label(value) == "guitar"]
    programs = sorted({v - 1 for p in declarations.values() for v in p["midi_programs_1based"]})
    signals = []
    if labels: signals.append("guitar_in_written_part_or_instrument_label")
    if tab_parts: signals.append("tab_clef")
    if any(24 <= v <= 31 for v in programs): signals.append("guitar_playback_program")
    title_fields = {}
    for label, path in (("work-title", q("work") + "/" + q("work-title")), ("movement-title", q("movement-title"))):
        values = ["".join(n.itertext()).strip() for n in root.findall(path)]
        if values: title_fields[label] = values
    return {"score_root": root_name, "written_part_count": len(declarations), "parts": list(declarations.values()),
            "guitar_label_evidence": labels, "tab_part_ids": sorted(tab_parts), "staff_tuning_part_ids": sorted(tuning_parts),
            "gm_programs_0based": programs, "file_title_fields": title_fields, "recall_signals": signals,
            "semantic_warnings": warnings, "complete_musicxml_parse": True, "external_resources_requested": 0}


def inspect_mxl(body: bytes) -> dict:
    """Memory-only strict ZIP/container/CRC checks and bounded notation parse."""
    if body[:4] != b"PK\x03\x04":
        raise ValueError("MXL ZIP local header absent or prefixed")
    tail = body[-65557:]
    end = tail.rfind(b"PK\x05\x06")
    if end < 0 or end + 22 > len(tail): raise ValueError("MXL ZIP directory absent")
    disk, central_disk, disk_count, count, central_size, central_offset, comment = struct.unpack("<HHHHIIH", tail[end+4:end+22])
    end_offset = len(body) - len(tail) + end
    if (end+22+comment != len(tail) or disk or central_disk or disk_count != count or not count
            or count == 0xffff or central_size == 0xffffffff or central_offset == 0xffffffff
            or central_offset+central_size != end_offset):
        raise ValueError("invalid/trailing/multipart/ZIP64 MXL ZIP directory")
    try:
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            infos = archive.infolist()
            if len(infos) != count or len(infos) > MXL_LIMITS["members"] or min(i.header_offset for i in infos) != 0:
                raise ValueError("MXL ZIP member count/header bounds")
            names, bodies, total = {}, {}, 0
            for info in infos:
                name = _zip_name(info.filename)
                if name in names: raise ValueError("duplicate MXL ZIP path")
                names[name] = info
                kind = (info.external_attr >> 16) & 0o170000
                if kind not in {0, stat.S_IFREG, stat.S_IFDIR} or info.flag_bits & 1:
                    raise ValueError("MXL ZIP link/special/encrypted member")
                if info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                    raise ValueError("unapproved MXL compression")
                if (info.file_size > MXL_LIMITS["member_bytes"] or
                        info.file_size > max(1, info.compress_size)*MXL_LIMITS["expansion_ratio"]):
                    raise ValueError("MXL ZIP member expansion bound")
                total += info.file_size
                if total > MXL_LIMITS["total_bytes"]: raise ValueError("MXL ZIP total expansion bound")
                data = archive.read(info)  # Every member, including unreferenced ones, checks CRC.
                if len(data) != info.file_size: raise ValueError("MXL ZIP member size mismatch")
                if info.is_dir():
                    if data: raise ValueError("MXL ZIP directory has data")
                elif kind == stat.S_IFDIR: raise ValueError("MXL ZIP directory attribute mismatch")
                elif name == "META-INF/container.xml" or name.lower().endswith((".xml", ".musicxml")):
                    bodies[name] = data
            if "META-INF/container.xml" not in bodies: raise ValueError("MXL container absent")
            container = _xml(bodies["META-INF/container.xml"], "MXL audit container")
            if _tag(container) != "container": raise ValueError("invalid MXL container root")
            roots = [i for p in container if _tag(p) == "rootfiles" for i in p if _tag(i) == "rootfile"]
            types = {None, "application/vnd.recordare.musicxml+xml"}
            if not roots or roots[0].get("media-type") not in types or any(i.get("media-type") in types for i in roots[1:]):
                raise ValueError("MXL must declare one primary score root")
            score_name = _zip_name(roots[0].get("full-path", ""))
            if score_name not in names or names[score_name].is_dir(): raise ValueError("MXL root does not name score member")
            score = bodies.get(score_name)
            if score is None: score = archive.read(names[score_name])
            result = musicxml_scope(score)
            result.update(score_member=score_name, zip_members=len(infos), uncompressed_bytes=total,
                          crc_status="all_members_verified")
            return result
    except (zipfile.BadZipFile, RuntimeError, EOFError, NotImplementedError, zlib.error) as error:
        raise ValueError("corrupt MXL ZIP") from error


def csv_members(path):
    by_member, ids = {}, set()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        if not reader.fieldnames or not {"metadata", "mxl"}.issubset(reader.fieldnames): raise ValueError("CSV missing locators")
        for row in reader:
            if None in row or any(v is None for v in row.values()): raise ValueError("malformed authoritative CSV")
            identity, _ = _metadata_locator(row["metadata"])
            if identity in ids: raise ValueError("duplicate authoritative native ID")
            ids.add(identity)
            if row["mxl"] not in {"", "NA"}:
                member = _locator(row["mxl"], "MUSICXML")
                by_member.setdefault(member, []).append(identity)
    return by_member, ids


def bind_integrity(report, integrity, current_stat):
    if integrity.get("status") != "complete" or not isinstance(integrity.get("files"), dict):
        raise ValueError("fresh archive integrity report is incomplete")
    item = integrity["files"].get("mxl.tar.gz", {})
    expected = report["archive_input"]
    if (item.get("stat") != current_stat or current_stat != expected["stat"]
            or item.get("bytes") != expected["bytes"] or item.get("md5") != expected["md5"]
            or item.get("sha256") != expected["sha256"]):
        raise ValueError("fresh archive integrity proof does not match scanned bytes/stat")
    report["fresh_archive_integrity"] = dict(item)
    report["archive_checksum_freshly_reverified"] = True
    report["status"] = "complete" if report["coverage_complete"] else "complete_with_parse_or_missing_boundaries"
    return report


def audit(root, output, *, integrity_path=None, workers=4):
    root, output = Path(root).resolve(), Path(output).resolve()
    if not output.is_relative_to(root / "sources/musescore/expansion"):
        raise ValueError("MXL audit output must remain private")
    base = root / "sources/musescore/pdmx"
    config = json.loads((root / "config/musescore_pdmx_formats.json").read_text())
    limits = validate_config(config)
    receipt = json.loads((base / "mxl-receipt.json").read_text())
    archive_path = base / "mxl.tar.gz"
    archive_stat, csv_stat = fingerprint(archive_path), fingerprint(base / "PDMX.csv")
    expected = config["files"]["mxl.tar.gz"]
    if (archive_path.is_symlink() or archive_stat[2] != expected["size"] or receipt.get("bytes") != expected["size"]
            or receipt.get("upstream_checksum_verified") is not True or receipt.get("upstream_checksum") != "md5:" + expected["md5"]
            or not re.fullmatch(r"[0-9a-f]{64}", str(receipt.get("sha256", "")))):
        raise ValueError("MXL archive size/config/receipt mismatch")
    members, all_ids = csv_members(base / "PDMX.csv")
    counts, signals, candidates, failures, seen = Counter(), Counter(), {}, [], {}
    sequence = hashlib.sha256()
    def finish(job):
        future, name, native_ids, member_bytes, sha = job
        try:
            result = future.result()
        except (ValueError, OSError, OverflowError, RecursionError) as error:
            failures.append({"member": name, "source_record_ids": native_ids, "bytes": member_bytes, "sha256": sha,
                             "error_type": type(error).__name__, "reason": str(error)})
            counts["parse_failures"] += 1
        else:
            counts["validated_mxl_members"] += 1
            counts["parsed_musicxml_bytes"] += result["uncompressed_bytes"]
            counts["written_parts"] += result["written_part_count"]
            if result["semantic_warnings"]: counts["files_with_semantic_warnings"] += 1
            signals.update(result["recall_signals"])
            if result["recall_signals"]:
                counts["candidate_mxl_members"] += 1
                for identity in native_ids:
                    candidates[identity] = {"source_record_id": identity, "mxl_member": name,
                        "bytes": member_bytes, "sha256": sha, **result}
        counts["inspected_mxl_members"] += 1
        if counts["inspected_mxl_members"] % 10000 == 0:
            print(json.dumps({"checked": counts["inspected_mxl_members"], "candidates": len(candidates), "failures": len(failures)}), flush=True)
    if type(workers) is not int or workers < 1 or workers > 8:
        raise ValueError("worker count must be from one through eight")
    pending = deque()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        with tarfile.open(archive_path, "r|gz") as archive:
            for info in _stream_members(archive):
                counts["archive_members"] += 1
                if counts["archive_members"] > limits["max_members"]: raise ValueError("MXL TAR member bound")
                path = PurePosixPath(info.name)
                if (path.is_absolute() or ".." in path.parts or "\\" in info.name or "\x00" in info.name
                        or re.match(r"^[A-Za-z]:", info.name)):
                    raise ValueError("unsafe MXL TAR member")
                name = str(path)
                if info.isdir():
                    if not re.fullmatch(r"mxl(?:/[0-9]+){0,2}", name): raise ValueError("unexpected MXL TAR directory")
                    counts["directories"] += 1
                    continue
                if not info.isfile(): raise ValueError("MXL TAR contains non-regular member")
                name = _locator(name, "MUSICXML")
                if info.size < 0 or info.size > limits["max_member_bytes"]: raise ValueError("MXL TAR member size bound")
                counts["regular_bytes"] += info.size
                if counts["regular_bytes"] > limits["max_total_bytes"]: raise ValueError("MXL TAR expansion bound")
                stream = archive.extractfile(info)
                if stream is None: raise ValueError("unreadable MXL TAR member")
                with stream: body = stream.read(info.size + 1)
                if len(body) != info.size: raise ValueError("MXL TAR member size mismatch")
                sha = hashlib.sha256(body).hexdigest()
                if name in seen:
                    if seen[name] != sha: raise ValueError("conflicting duplicate MXL TAR member")
                    counts["equal_duplicate_members"] += 1
                    continue
                seen[name] = sha
                sequence.update(name.encode() + b"\0" + bytes.fromhex(sha))
                native_ids = members.get(name, [])
                counts["unique_mxl_members"] += 1
                if not native_ids: counts["mxl_members_not_declared_by_csv"] += 1
                pending.append((pool.submit(inspect_mxl, body), name, native_ids, len(body), sha))
                if len(pending) >= workers * 4:
                    finish(pending.popleft())
        while pending:
            finish(pending.popleft())
    if fingerprint(archive_path) != archive_stat or fingerprint(base / "PDMX.csv") != csv_stat:
        raise ValueError("MXL archive or CSV changed during full scan")
    missing = sorted(set(members) - seen.keys())
    counts["csv_native_records"] = len(all_ids)
    counts["csv_mxl_locators"] = len(members)
    counts["csv_mxl_members_missing_archive"] = len(missing)
    counts["candidate_native_records"] = len(candidates)
    report = {"schema_version": 1, "status": "pending_fresh_archive_integrity", "checked_at": datetime.now(timezone.utc).isoformat(),
              "publication": config["publication"], "scope": "All MXL TAR members; no metadata/GM/known-record prefilter",
              "coverage_complete": not failures and not missing, "archive_checksum_freshly_reverified": False,
              "archive_input": {"bytes": archive_stat[2], "md5": expected["md5"], "sha256": receipt["sha256"], "stat": archive_stat},
              "csv_input_stat": csv_stat, "counts": dict(counts), "recall_signal_counts": dict(signals),
              "member_sequence_sha256": sequence.hexdigest(), "missing_mxl_members": missing, "parse_failures": failures,
              "candidates": candidates, "method_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "recall_dependency_sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in
                  ("scripts/audit_pdmx_metadata_scope.py", "scripts/review_musescore_instrumentation.py")},
              "limits": {"tar": limits, "mxl": MXL_LIMITS},
              "limitations": ["Recall signals establish candidates, not a final guitar arrangement or performing-role count.",
                 "TAB may represent ukulele, bass, banjo or another fretted instrument.",
                 "GM programs are playback settings; retain explicit source/file evidence and separate exclusions.",
                 "The complete XML was parsed but musical notes, playback fidelity and title identity were not semantically certified."]}
    if integrity_path and Path(integrity_path).is_file():
        bind_integrity(report, json.loads(Path(integrity_path).read_text()), archive_stat)
    atomic_json(output, report)
    return {key: report[key] for key in ("status", "coverage_complete", "counts", "recall_signal_counts")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--integrity-report", type=Path)
    parser.add_argument("--bind-integrity", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    output = args.output or args.root / "sources/musescore/expansion/mxl-scope.json"
    integrity = args.integrity_report or args.root / "sources/musescore/expansion/archive-integrity.json"
    if args.bind_integrity:
        report = json.loads(output.read_text())
        bind_integrity(report, json.loads(integrity.read_text()), fingerprint(args.root / "sources/musescore/pdmx/mxl.tar.gz"))
        atomic_json(output, report)
        print(json.dumps({"status": report["status"], "counts": report["counts"]}, indent=2))
    else:
        print(json.dumps(audit(args.root, output, integrity_path=integrity, workers=args.workers), indent=2))


if __name__ == "__main__":
    main()
