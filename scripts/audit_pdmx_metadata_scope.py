#!/usr/bin/env python
"""Read-only, complete PDMX metadata scope audit independent of GM 24/25.

Every archive member and JSON object is checked. Source instrument/part labels,
GM programs and title-only mentions remain separate evidence. No production
catalog, acquisition journal, score, translation or instrumentation review is
modified, and this command makes no network requests.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import tarfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from build_musescore_library import atomic_json, validate_config
from source_adapters.musescore import LICENSES, _id, _page, csv_serialization, convert_record
from source_adapters.pdmx import _digests, _metadata_locator, _stream_members, _unique_json_object

GUITAR = re.compile(
    r"(?<![\w])(?:guitars?|guitarras?|guitares?|guitarres?|guitarren?|guitarr[ae]?|"
    r"gitaar|gitar[ae]?|gitarren?|gitarrer|gitár|chitarr[ae]|chitară|kytar[ay]|kitara|"
    r"viol[aã]o|violões|gtr|gtrs|gtar)(?![\w])|"
    r"吉他|吉它|結他|结他|結它|结它|ギター|기타|гитар[а-яё]*|гітар[а-яіїє]*|"
    r"κιθάρ[αες]*|קיטרה|גיטרה|غيتار|گیتار", re.I)

ELECTRIC = re.compile(
    r"\b(?:electric(?:al)?|elektrisch\w*|électrique|eléctrica|electrica|elettric\w*|"
    r"distortion|distorted|overdrive|synth(?:esizer)?)\b|电吉他|電吉他|エレキ|электрогитар", re.I)
BASS_GUITAR = re.compile(
    r"\b(?:bass\s+guitar|guitar\s+bass|electric\s+bass|acoustic\s+bass|"
    r"fingered\s+bass|slap\s+bass|guitarra\s+bajo|guitare\s+basse)\b|"
    r"(?<!\w)(?:bajo|basse)(?!\w)|贝斯|貝斯|ベース|бас[- ]?гитар", re.I)
OTHER_GUITAR = re.compile(r"\b(?:hawaiian|slide\s+guitar|steel\s+guitar|pedal\s+steel)\b", re.I)
VOICE = re.compile(r"\b(?:vocals?|voices?|choir|chorus|soprano|alto|tenor|baritone|"
                   r"gesang|chant|voix|canto|voces|voce)\b|声乐|聲樂|合唱|人声|人聲", re.I)
LARGE = re.compile(r"orchestra|\b(?:band|bands|choir|choral|satb|a capella|drum corps)\b", re.I)
CSV_FIELDS = ("metadata", "tracks", "n_tracks", "license", "license_url", "license_conflict",
              "subset:no_license_conflict", "title", "composer_name", "has_lyrics", "n_lyrics",
              "mxl", "pdf", "mid", "has_paywall")


def file_guard(path: Path, *, expected_size: int, expected_md5: str, receipt: dict) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError("input must be a regular non-symlink file")
    before = path.stat()
    size, md5, sha = _digests(path)
    if (size != expected_size or md5 != expected_md5 or receipt.get("bytes") != size
            or receipt.get("upstream_checksum") != "md5:" + md5
            or receipt.get("sha256") != sha or receipt.get("upstream_checksum_verified") is not True):
        raise ValueError("frozen input checksum/receipt mismatch")
    return {"bytes": size, "md5": md5, "sha256": sha,
            "stat": (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)}


def unchanged(path: Path, guard: dict) -> None:
    now = path.stat()
    if (now.st_dev, now.st_ino, now.st_size, now.st_mtime_ns, now.st_ctime_ns) != guard["stat"]:
        raise ValueError("frozen input changed while auditing")


def read_csv_index(path: Path) -> tuple[dict, dict]:
    """Compact full-row index; no GM or licensing prefilter is applied."""
    index, counts = {}, Counter()
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        if not reader.fieldnames or not set(CSV_FIELDS).issubset(reader.fieldnames) or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError("invalid CSV columns")
        for line, row in enumerate(reader, 2):
            counts["csv_rows"] += 1
            if None in row or any(v is None for v in row.values()):
                raise ValueError("malformed CSV row")
            identity, member = _metadata_locator(row["metadata"])
            if identity in index:
                raise ValueError("duplicate native ID in authoritative CSV")
            index[identity] = (line, tuple(row[key] for key in CSV_FIELDS))
    counts["unique_csv_native_ids"] = len(index)
    return index, dict(counts)


def scan_metadata_archive(path: Path, visit, *, max_member_bytes=8*1024*1024,
                          max_total_bytes=4*1024*1024*1024, max_members=300000) -> dict:
    """Validate and parse every metadata JSON, never extract or follow links."""
    if any(type(v) is not int or v <= 0 for v in (max_member_bytes, max_total_bytes, max_members)):
        raise ValueError("positive archive bounds required")
    seen, native_members, counts = {}, {}, Counter()
    with tarfile.open(path, "r|gz") as archive:
        for info in _stream_members(archive):
            counts["archive_members"] += 1
            if counts["archive_members"] > max_members:
                raise ValueError("archive member limit exceeded")
            p = PurePosixPath(info.name)
            if (p.is_absolute() or ".." in p.parts or "\\" in info.name or "\x00" in info.name
                    or re.match(r"^[A-Za-z]:", info.name)):
                raise ValueError("unsafe archive member path")
            normalized = str(p)
            if info.isdir():
                if normalized != "metadata" and not re.fullmatch(r"metadata/[0-9]+", normalized):
                    raise ValueError("unexpected metadata archive directory")
                counts["directory_members"] += 1
                continue
            if not info.isfile():
                raise ValueError("archive contains a non-regular member")
            if info.size < 0 or info.size > max_member_bytes:
                raise ValueError("archive member size limit exceeded")
            counts["regular_bytes"] += info.size
            if counts["regular_bytes"] > max_total_bytes:
                raise ValueError("archive total size limit exceeded")
            identity, expected = _metadata_locator(normalized)
            if expected != normalized:
                raise ValueError("non-canonical metadata member")
            handle = archive.extractfile(info)
            if handle is None:
                raise ValueError("unreadable metadata member")
            with handle:
                raw = handle.read(info.size + 1)
            if len(raw) != info.size:
                raise ValueError("metadata member size mismatch")
            digest = hashlib.sha256(raw).hexdigest()
            if normalized in seen:
                if seen[normalized] != digest:
                    raise ValueError("conflicting duplicate metadata member")
                counts["equal_duplicate_members"] += 1
                continue
            if identity in native_members:
                raise ValueError("native ID has multiple metadata locators")
            seen[normalized] = digest
            native_members[identity] = normalized
            payload = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique_json_object)
            if not isinstance(payload, dict):
                raise ValueError("metadata JSON must be an object")
            visit(identity, normalized, digest, payload)
            counts["unique_metadata_records"] += 1
            if counts["unique_metadata_records"] % 25000 == 0:
                print(json.dumps({"progress_metadata_records": counts["unique_metadata_records"]}), flush=True)
    return {"counts": dict(counts), "native_members": native_members}


def source_evidence(metadata: dict, csv_row: dict) -> dict:
    data = metadata.get("data", {})
    score = data.get("score", {}) if isinstance(data, dict) else {}
    mirror = metadata.get("score", {})
    if not isinstance(score, dict): score = {}
    if not isinstance(mirror, dict): mirror = {}
    labels = []
    for instrument in score.get("instruments", []) if isinstance(score.get("instruments"), list) else []:
        if isinstance(instrument, dict) and isinstance(instrument.get("name"), str):
            labels.append(("source_instrument", instrument["name"]))
    for field, values in (("source_part", score.get("parts_names", [])), ("mirror_part", mirror.get("partNames", []))):
        if isinstance(values, list):
            labels.extend((field, value) for value in values if isinstance(value, str))
    for item in score.get("instrumentations", []) if isinstance(score.get("instrumentations"), list) else []:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            labels.append(("source_instrumentation", item["name"]))
    guitar_labels = [{"field": field, "text": value} for field, value in labels if GUITAR.search(value)]
    programs = []
    tracks = csv_row.get("tracks", "")
    valid_programs = bool(re.fullmatch(r"(?:0|[1-9][0-9]*)(?:-(?:0|[1-9][0-9]*))*", tracks))
    if valid_programs:
        programs = [int(v) for v in tracks.split("-")]
        valid_programs = all(v <= 127 for v in programs) and csv_row.get("n_tracks") == str(len(programs))
    flags = []
    for flag, pattern in (("electric_or_synth", ELECTRIC), ("bass_guitar_or_ambiguous_bass", BASS_GUITAR),
                          ("hawaiian_steel_slide", OTHER_GUITAR)):
        if any(pattern.search(value) for _, value in labels): flags.append(flag)
    # A tenor saxophone/alto flute is not a singing part. Dedicated voice terms
    # or bare SATB labels establish a voice concern; the complete raw labels stay.
    if any(VOICE.search(value) and not re.search(r"sax|flute|clarinet|recorder|trombone|horn|tuba|viola", value, re.I)
           for _, value in labels): flags.append("voice_or_chorus")
    if any(LARGE.search(value) for field, value in labels if field == "source_instrumentation"):
        flags.append("large_ensemble_label")
    if csv_row.get("has_lyrics") == "True" or csv_row.get("n_lyrics") not in {"0", "NA", ""}:
        flags.append("lyric_annotations")
    if not valid_programs: flags.append("invalid_gm_csv")
    old_gm = valid_programs and any(v in {24, 25} for v in programs)
    any_gm = valid_programs and any(24 <= v <= 31 for v in programs)
    title = score.get("title", "")
    title_mention = isinstance(title, str) and bool(GUITAR.search(title))
    basis = ("explicit_source_instrument" if any(x["field"] == "source_instrument" for x in guitar_labels)
             else "explicit_source_part" if any(x["field"] in {"source_part", "mirror_part"} for x in guitar_labels)
             else "source_instrumentation_label" if guitar_labels else "gm_guitar_candidate" if any_gm
             else "title_only" if title_mention else "not_guitar_candidate")
    return {"basis": basis, "guitar_labels": guitar_labels, "gm_programs": programs,
            "old_acoustic_gm_gate": old_gm, "any_guitar_gm": any_gm,
            "title_mentions_guitar": title_mention, "scope_flags": flags}


def identity_license_checks(metadata: dict, row: dict, expected_id: str) -> dict:
    """Independent native transcription/URL and published licensing diagnostics."""
    from urllib.parse import unquote
    data = metadata.get("data", {})
    score = data.get("score", {}) if isinstance(data, dict) else {}
    mirror = metadata.get("score", {})
    issues = []
    if not isinstance(score, dict) or not isinstance(mirror, dict):
        return {"identity_issues": ["missing_source_score"], "license_issues": ["missing_source_score"]}
    if metadata.get("status_code") != 200: issues.append("unsuccessful_metadata_snapshot")
    if _id(score.get("id")) != expected_id or _id(mirror.get("id")) != expected_id:
        issues.append("native_id_mismatch")
    title, composer = score.get("title"), score.get("composer_name")
    if not isinstance(title, str) or not title.strip() or mirror.get("title") != title:
        issues.append("missing_or_conflicting_title")
    elif csv_serialization(title) != ("" if row.get("title") == "NA" else row.get("title")):
        issues.append("csv_title_mismatch")
    if composer is not None and not isinstance(composer, str): issues.append("invalid_composer_type")
    if csv_serialization(composer) != ("" if row.get("composer_name") == "NA" else row.get("composer_name")):
        issues.append("csv_composer_mismatch")
    user = score.get("user", {})
    if not isinstance(user, dict): user = {}
    uid = _id(user.get("id"))
    url = score.get("url")
    if not uid or not _page(url, expected_id, uid, user.get("url", "")):
        issues.append("invalid_source_url_or_uploader")
    urls = [mirror.get("url")]
    for node in (score, mirror):
        share = node.get("share")
        if isinstance(share, dict):
            if "publicUrl" in share: urls.append(share["publicUrl"])
            if "url" in share:
                v = share["url"]
                urls.append(unquote(v) if isinstance(v, str) else None)
        links = node.get("_links")
        if isinstance(links, dict) and isinstance(links.get("self"), dict): urls.append(links["self"].get("href"))
    if any(v != url for v in urls): issues.append("source_url_mismatch")
    if isinstance(mirror.get("user"), dict) and _id(mirror["user"].get("id")) != uid:
        issues.append("uploader_identity_mismatch")
    lic = score.get("license")
    license_issues = []
    if row.get("license_conflict") != "False": license_issues.append("license_conflict")
    if row.get("subset:no_license_conflict") != "True": license_issues.append("no_conflict_subset_excluded")
    if not isinstance(lic, str) or lic not in LICENSES: license_issues.append("license_outside_approved_scope")
    if lic != row.get("license"): license_issues.append("license_mismatch")
    if data.get("license_url") != row.get("license_url"): license_issues.append("license_url_mismatch")
    if lic in LICENSES and data.get("license_url") != LICENSES[lic][0]: license_issues.append("unsupported_license_url")
    return {"identity_issues": issues, "license_issues": license_issues}



def reconciled_source_checks(metadata: dict, strict: dict) -> dict:
    """Exact reversible representations; never fuzzy or title-based identities."""
    from audit_pdmx_scope import metadata_identity_evidence
    evidence = metadata_identity_evidence(metadata)
    issues = list(strict["identity_issues"])
    if evidence["title"]["equivalent"] and "missing_or_conflicting_title" in issues:
        issues.remove("missing_or_conflicting_title")
    if evidence["pages"]["equivalent"] and "source_url_mismatch" in issues:
        issues.remove("source_url_mismatch")
    data = metadata.get("data", {})
    score = data.get("score", {}) if isinstance(data, dict) else {}
    mirror = metadata.get("score", {})
    if not isinstance(score, dict): score = {}
    if not isinstance(mirror, dict): mirror = {}
    from source_adapters.musescore import _true
    access = []
    for key in ("is_private", "is_draft", "is_official", "is_blocked"):
        if _true(score.get(key)): access.append("score_" + key)
    if mirror.get("isPublic") is False or _true(mirror.get("isBlocked")):
        access.append("private_or_blocked_snapshot")
    for key in ("hidden", "is_blocked", "score_blocked_by_country"):
        if _true(data.get(key)): access.append("data_" + key)
    return {"reconciled_identity_issues": issues, "metadata_access_issues": access,
            "identity_equivalence": evidence}

def audit(root: Path, output_dir: Path) -> dict:
    root = root.resolve()
    output_dir = output_dir.resolve()
    if not output_dir.is_relative_to(root / "sources/musescore/expansion"):
        raise ValueError("audit output must remain in private MuseScore expansion directory")
    config_path = root / "config/musescore_pdmx.json"
    config = json.loads(config_path.read_text())
    validate_config(config)
    base = root / "sources/musescore/pdmx"
    guards = {}
    for filename, receipt_name in (("PDMX.csv", "csv-receipt.json"), ("metadata.tar.gz", "metadata-receipt.json")):
        guards[filename] = file_guard(base / filename, expected_size=config["files"][filename]["size"],
                                     expected_md5=config["files"][filename]["md5"],
                                     receipt=json.loads((base / receipt_name).read_text()))
    existing_path = root / "sources/musescore/catalog.json"
    existing = json.loads(existing_path.read_text())
    existing_ids = {work["id"].split(":", 1)[1] for work in existing["works"]}
    existing_sha = hashlib.sha256(existing_path.read_bytes()).hexdigest()
    csv_index, csv_counts = read_csv_index(base / "PDMX.csv")
    existing_selection = json.loads((base / "selection.json").read_text())
    old_candidate_ids = {row["source_record_id"] for row in existing_selection["candidates"]}
    counts, scope_flags, bases, strict_outcomes, licenses = Counter(csv_counts), Counter(), Counter(), Counter(), Counter()
    labels, records, snapshots, seen_ids = Counter(), [], {}, set()

    def visit(identity, member, digest, metadata):
        seen_ids.add(identity)
        if identity not in csv_index:
            counts["metadata_not_in_csv"] += 1
            return
        line, values = csv_index[identity]
        row = dict(zip(CSV_FIELDS, values))
        if _metadata_locator(row["metadata"])[1] != member:
            raise ValueError("metadata archive path and authoritative CSV locator disagree")
        evidence = source_evidence(metadata, row)
        bases[evidence["basis"]] += 1
        if evidence["basis"] == "not_guitar_candidate": return
        counts["broad_guitar_related_rows"] += 1
        for label in evidence["guitar_labels"]: labels[(label["field"], label["text"])] += 1
        scope_flags.update(evidence["scope_flags"])
        checks = identity_license_checks(metadata, row, identity)
        reconciled = reconciled_source_checks(metadata, checks)
        _, strict_reason = convert_record(row, metadata)
        strict_outcomes[strict_reason] += 1
        licenses[row["license"]] += 1
        if identity in existing_ids: counts["existing_924_related"] += 1
        if strict_reason == "accepted":
            counts["strict_adapter_accepted_without_gm_gate"] += 1
            if identity not in existing_ids: counts["strict_adapter_new_records"] += 1
            if not evidence["old_acoustic_gm_gate"]: counts["strict_adapter_missed_by_gm_gate"] += 1
        safe_instrument_candidate = bool(evidence["guitar_labels"]) and evidence["basis"] != "title_only"
        clean_scope = not any(v in evidence["scope_flags"] for v in
                              ("electric_or_synth", "bass_guitar_or_ambiguous_bass", "hawaiian_steel_slide", "voice_or_chorus", "large_ensemble_label"))
        if not checks["identity_issues"] and not checks["license_issues"] and safe_instrument_candidate:
            counts["identity_license_valid_explicit_guitar"] += 1
            if clean_scope:
                counts["clean_scope_explicit_guitar_candidates"] += 1
                if identity not in existing_ids: counts["new_clean_scope_candidates"] += 1
                if not evidence["old_acoustic_gm_gate"]: counts["clean_scope_missed_by_gm_gate"] += 1
        if not reconciled["reconciled_identity_issues"] and not checks["license_issues"] and not reconciled["metadata_access_issues"]:
            counts["reconciled_identity_license_access_valid_related"] += 1
            if safe_instrument_candidate:
                counts["reconciled_identity_license_access_valid_explicit"] += 1
                if clean_scope:
                    counts["reconciled_clean_scope_explicit_candidates"] += 1
                    if identity not in existing_ids: counts["reconciled_new_clean_scope_explicit_candidates"] += 1
                    if not evidence["old_acoustic_gm_gate"]: counts["reconciled_clean_scope_missing_old_gm"] += 1
            elif clean_scope:
                counts["reconciled_clean_no_explicit_" + evidence["basis"]] += 1
        score = metadata.get("data", {}).get("score", {})
        if not isinstance(score, dict): score = {}
        summary = {"source_record_id": identity, "csv_line": line, "metadata_member": member,
                   "metadata_member_sha256": digest, "source_title": score.get("title"),
                   "source_composer_attribution": score.get("composer_name"), "source_url": score.get("url"),
                   "source_instruments": score.get("instruments"), "source_parts_names": score.get("parts_names"),
                   "source_instrumentations": score.get("instrumentations"), "source_part_count": score.get("parts"),
                   "source_license": score.get("license"), "license_url": metadata.get("data", {}).get("license_url"),
                   "existing_record": identity in existing_ids, "old_csv_candidate": identity in old_candidate_ids,
                   "strict_adapter_outcome": strict_reason, "evidence": evidence, **checks, **reconciled}
        records.append(summary)
        # Snapshot every broad candidate, including excluded and title-only rows.
        # Neither snapshot membership nor a title establishes accepted scope.
        if evidence["basis"] != "not_guitar_candidate":
            snapshots[identity] = {"metadata_member": member, "metadata_member_sha256": digest,
                                   "metadata": metadata, "csv_line": line}

    archive = scan_metadata_archive(base / "metadata.tar.gz", visit)
    counts.update(archive["counts"])
    missing_ids = sorted(set(csv_index) - seen_ids, key=int)
    counts["csv_rows_missing_metadata"] = len(missing_ids)
    counts["existing_records_in_full_metadata"] = len(existing_ids & seen_ids)
    # Recover complete exact rows only for retained snapshots, without keeping
    # all 254k complete CSV rows in memory.
    with (base / "PDMX.csv").open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream, strict=True):
            identity, _ = _metadata_locator(row["metadata"])
            if identity in snapshots: snapshots[identity]["csv"] = row
    for filename, guard in guards.items(): unchanged(base / filename, guard)
    if hashlib.sha256(existing_path.read_bytes()).hexdigest() != existing_sha:
        raise ValueError("existing catalog changed during read-only audit")
    report = {"schema_version": 1, "status": "complete", "checked_at": datetime.now(timezone.utc).isoformat(),
              "source_id": "musescore", "publication": config["publication"],
              "scope": "All frozen PDMX v9 metadata and authoritative CSV rows; no GM 24/25 prefilter",
              "counts": dict(counts), "evidence_basis_counts": dict(bases), "scope_flag_counts": dict(scope_flags),
              "strict_adapter_outcomes": dict(strict_outcomes), "license_counts": dict(licenses),
              "missing_metadata_ids": missing_ids,
              "source_instrument_label_inventory": [{"field": k[0], "text": k[1], "count": v} for k,v in sorted(labels.items())],
              "input_files": {name: {k:v for k,v in g.items() if k != "stat"} for name,g in guards.items()},
              "existing_catalog_sha256": existing_sha, "existing_record_count": len(existing_ids),
              "method_files": {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in
                               ("scripts/audit_pdmx_metadata_scope.py", "scripts/audit_pdmx_scope.py", "scripts/source_adapters/musescore.py")},
              "records": sorted(records, key=lambda x: int(x["source_record_id"])),
              "limitations": ["Source instrument and part labels establish candidate scope, not file-level player counts.",
                 "Title-only mentions do not establish guitar instrumentation.",
                 "GM programs are independent playback candidates, not acoustic construction or performer evidence.",
                 "Historical public-domain/CC0 labels and dataset metadata reuse remain separate from live source access.",
                 "Excluded electric, bass, voice and large-ensemble candidates are retained for scope evidence."]}
    clean_ids = [r["source_record_id"] for r in report["records"]
                 if not r["reconciled_identity_issues"] and not r["license_issues"] and not r["metadata_access_issues"]
                 and r["evidence"]["guitar_labels"]
                 and not any(x in r["evidence"]["scope_flags"] for x in
                             ("electric_or_synth", "bass_guitar_or_ambiguous_bass", "hawaiian_steel_slide", "voice_or_chorus", "large_ensemble_label"))]
    atomic_json(output_dir / "metadata-selection.json", {"schema_version":1, "status":"complete",
        "publication":config["publication"], "input_files":report["input_files"], "method_files":report["method_files"],
        "candidate_ids": clean_ids, "new_candidate_ids": [identity for identity in clean_ids if identity not in existing_ids],
        "pending_file_instrumentation_review": True})
    atomic_json(output_dir / "full-metadata-audit.json", report)
    atomic_json(output_dir / "candidate-metadata.json", {"schema_version": 1, "status": "complete",
        "publication": config["publication"], "input_files": report["input_files"], "records": snapshots})
    return {key: report[key] for key in ("status", "counts", "evidence_basis_counts", "scope_flag_counts", "strict_adapter_outcomes")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    output = args.output_dir or args.root / "sources/musescore/expansion"
    print(json.dumps(audit(args.root, output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
