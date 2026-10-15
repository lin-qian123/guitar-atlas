"""Read-only full PDMX CSV recall audit; signals never establish inclusion.

GM values below are zero-based programs, not instrument/player counts. The
legacy license predicate is reported separately from discovery signals and is
not an expansion acquisition permission. No source catalog is written.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import csv
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import re
import unicodedata
from urllib.parse import unquote


TITLE_FIELDS = ("song_name", "title", "subtitle")
CONTEXT_FIELDS = ("genres", "groups", "tags")
GUITAR = re.compile(
    r"\b(?:guitar\w*|guitarr\w*|guitare\w*|chitarr\w*|gitar\w*|gitarr\w*|"
    r"violao|violoes|guitalele)\b|吉他|結他|结他|吉它|ギター|기타|гитар", re.I)
TABLATURE = re.compile(r"\b(?:tablature\w*|tablatura\w*|tabulatur\w*|tabs?)\b|六线谱|六線譜", re.I)
RELATED = re.compile(r"\b(?:ukulele\w*|lute\w*|luth\w*|liuto|vihuela\w*)\b|尤克里里|乌克丽丽|烏克麗麗|鲁特|魯特", re.I)
PROGRAMS = re.compile(r"(?:0|[1-9][0-9]*)(?:-(?:0|[1-9][0-9]*))*")
LOCATOR = re.compile(r"\./metadata/[0-9]+/([1-9][0-9]*)\.json")


def fold(value: str) -> str:
    """Accent folding affects recall evidence only; raw CSV fields are retained."""
    return "".join(char for char in unicodedata.normalize("NFKD", value)
                   if not unicodedata.combining(char)).casefold()


def programs(row: dict) -> tuple[list[int], str | None]:
    raw, count = row.get("tracks", ""), row.get("n_tracks", "")
    if not PROGRAMS.fullmatch(raw):
        return [], "invalid_program_tokens"
    values = [int(value) for value in raw.split("-")]
    if any(value > 127 for value in values):
        return values, "invalid_program_range"
    if not re.fullmatch(r"[1-9][0-9]*", count):
        return values, "invalid_track_count"
    if len(values) != int(count):
        return values, "track_count_mismatch"
    return values, None


def legacy_license(row: dict) -> bool:
    return (row.get("license") in {"publicdomain", "cc-zero"}
            and row.get("license_conflict") == "False"
            and row.get("subset:no_license_conflict") == "True")


def title_identity_evidence(source_title, mirror_title) -> dict:
    """Allow only an exact title or one HTML entity decode of the mirror.

    Raw source transcriptions remain separate. This is representation equality,
    not fuzzy matching, title correction or a certificate of actual file identity.
    """
    valid = (isinstance(source_title, str) and bool(source_title.strip())
             and isinstance(mirror_title, str) and bool(mirror_title.strip()))
    decoded = html.unescape(mirror_title) if isinstance(mirror_title, str) else None
    status = ("invalid" if not valid else "exact" if source_title == mirror_title else
              "html_entity_equivalent" if source_title == decoded else "conflict")
    return {"source_title": source_title, "mirror_title": mirror_title,
            "decoded_mirror_title": decoded, "status": status,
            "equivalent": status in {"exact", "html_entity_equivalent"}}


def score_page_identity_evidence(source_url, observed_urls, *, native_id, uploader_id,
                                 uploader_home) -> dict:
    """Validate each native page separately before accepting a username alias.

    ``observed_urls`` is a nonempty list of ``{field, value, percent_encoded}``
    observations. Only a share.url observation explicitly marked encoded is
    percent-decoded once. Caller-owned fields are never changed. Every URL must
    pass the legacy adapter's exact HTTPS/host/native-ID/uploader guard; a title,
    suffix ID or a homepage alone cannot establish identity.
    """
    from source_adapters.musescore import _page

    if not isinstance(observed_urls, list):
        raise ValueError("observed URLs must be a list")
    seen, observations = set(), []
    valid_ids = (isinstance(native_id, str) and bool(re.fullmatch(r"[1-9][0-9]*", native_id))
                 and isinstance(uploader_id, str) and bool(re.fullmatch(r"[1-9][0-9]*", uploader_id)))
    source_valid = valid_ids and _page(source_url, native_id, uploader_id, uploader_home)
    for observed in observed_urls:
        if (not isinstance(observed, dict) or not isinstance(observed.get("field"), str)
                or not observed["field"] or observed["field"] in seen
                or type(observed.get("percent_encoded", False)) is not bool or "value" not in observed):
            raise ValueError("invalid or duplicate URL observation")
        seen.add(observed["field"])
        raw = observed["value"]
        encoded = observed.get("percent_encoded", False)
        decoded = unquote(raw) if encoded and isinstance(raw, str) else raw
        valid = bool(source_valid and _page(decoded, native_id, uploader_id, uploader_home))
        status = ("invalid" if not valid else "exact_source_url" if decoded == source_url else
                  "same_native_id_uploader_alias")
        observations.append({"field": observed["field"], "original": deepcopy(raw),
                             "percent_encoded": encoded, "decoded": deepcopy(decoded),
                             "status": status, "equivalent": valid})
    equivalent = bool(source_valid and observations and all(item["equivalent"] for item in observations))
    return {"source_url": deepcopy(source_url), "native_id": native_id,
            "uploader_id": uploader_id, "uploader_home": deepcopy(uploader_home),
            "source_url_valid": bool(source_valid), "observations": observations,
            "equivalent": equivalent,
            "status": ("invalid" if not equivalent else "verified_native_alias" if any(
                item["status"] == "same_native_id_uploader_alias" for item in observations) else "exact")}


def metadata_identity_evidence(metadata: dict) -> dict:
    """Collect all supplied source/mirror/share/self page observations verbatim."""
    data = metadata.get("data", {}) if isinstance(metadata, dict) else {}
    score = data.get("score", {}) if isinstance(data, dict) else {}
    mirror = metadata.get("score", {}) if isinstance(metadata, dict) else {}
    if not isinstance(score, dict) or not isinstance(mirror, dict):
        raise ValueError("source and mirror score objects required")
    user = score.get("user", {})
    if not isinstance(user, dict):
        user = {}
    observations = [{"field": "score.url", "value": mirror.get("url"), "percent_encoded": False}]
    for label, node in (("data.score", score), ("score", mirror)):
        share = node.get("share")
        if isinstance(share, dict):
            for key in ("publicUrl", "url"):
                if key in share:
                    observations.append({"field": f"{label}.share.{key}", "value": share[key],
                                         "percent_encoded": key == "url"})
        links = node.get("_links")
        link = links.get("self") if isinstance(links, dict) else None
        if isinstance(link, dict) and "href" in link:
            observations.append({"field": f"{label}._links.self.href", "value": link["href"],
                                 "percent_encoded": False})
    source_id, mirror_id = str(score.get("id")), str(mirror.get("id"))
    native_ids_agree = bool(re.fullmatch(r"[1-9][0-9]*", source_id) and source_id == mirror_id)
    uploader_id = str(user.get("id"))
    mirror_user = mirror.get("user")
    uploader_ids_agree = (not isinstance(mirror_user, dict)
                          or str(mirror_user.get("id")) == uploader_id)
    return {"title": title_identity_evidence(score.get("title"), mirror.get("title")),
            "pages": score_page_identity_evidence(score.get("url"), observations,
                native_id=source_id, uploader_id=uploader_id, uploader_home=user.get("url", "")),
            "native_ids_agree": native_ids_agree, "uploader_ids_agree": uploader_ids_agree}


def legacy_recovery_audit(selection: dict, records: dict, previous_exclusions) -> dict:
    """Counterfactual only: quantify representational false exclusions.

    Even a successful strict conversion here is not a file-level review or
    permission to append. The lyrics counterfactual expressly keeps file review
    pending; it does not conclude that a lyric-bearing score has no vocal role.
    """
    from source_adapters.musescore import convert_record

    excluded = {str(item["source_record_id"]): item["reason"] for item in previous_exclusions}
    counts, recovered_outcomes, lyrics_outcomes = Counter(), Counter(), Counter()
    rows = []
    for candidate in selection["candidates"]:
        native_id = candidate["source_record_id"]
        original = records[native_id]
        guards = metadata_identity_evidence(original)
        metadata, csv_row = deepcopy(original), deepcopy(candidate["csv"])
        repairs = []
        # All native and uploader identities must remain consistent before any
        # counterfactual representation repair is allowed.
        if guards["native_ids_agree"] and guards["uploader_ids_agree"]:
            if guards["title"]["status"] == "html_entity_equivalent":
                metadata["score"]["title"] = metadata["data"]["score"]["title"]
                repairs.append("html_entity_title_only")
            if guards["pages"]["status"] == "verified_native_alias":
                source_url = metadata["data"]["score"]["url"]
                metadata["score"]["url"] = source_url
                for node in (metadata["data"]["score"], metadata["score"]):
                    share = node.get("share")
                    if isinstance(share, dict):
                        for key in ("publicUrl", "url"):
                            if key in share:
                                share[key] = source_url
                    links = node.get("_links")
                    link = links.get("self") if isinstance(links, dict) else None
                    if isinstance(link, dict) and "href" in link:
                        link["href"] = source_url
                repairs.append("same_native_id_uploader_url_alias")
        value, reason = convert_record(csv_row, metadata)
        if repairs:
            for repair in repairs:
                counts[repair] += 1
            recovered_outcomes[reason] += 1
        recovered = value is not None and native_id in excluded
        if recovered:
            counts["new_acceptances_without_lyrics_override"] += 1
        lyric_flag = csv_row.get("has_lyrics") == "True" or csv_row.get("n_lyrics") != "0"
        lyrics_reason, lyrics_recovered = None, False
        if lyric_flag:
            csv_row["has_lyrics"], csv_row["n_lyrics"] = "False", "0"
            lyrics_value, lyrics_reason = convert_record(csv_row, metadata)
            lyrics_outcomes[lyrics_reason] += 1
            lyrics_recovered = lyrics_value is not None and native_id in excluded
            if lyrics_recovered:
                counts["potential_guitar_records_lyrics_manual_review"] += 1
        if repairs or lyric_flag:
            rows.append({"source_record_id": native_id, "csv_line": candidate["csv_line"],
                         "previous_reason": excluded.get(native_id, "accepted"),
                         "representation_repairs": repairs, "identity_evidence": guards,
                         "strict_outcome_after_representation_repair": reason,
                         "new_acceptance_without_lyrics_override": recovered,
                         "lyrics_counterfactual_outcome": lyrics_reason,
                         "lyrics_manual_file_review_candidate": lyrics_recovered})
    return {"status": "complete", "candidate_count": len(selection["candidates"]),
            "counts": dict(counts), "after_representation_repair_outcomes": dict(recovered_outcomes),
            "lyrics_counterfactual_outcomes": dict(lyrics_outcomes),
            "boundary": "Read-only counterfactual on deep copies; original native fields and old selection are unchanged. Lyrics acceptance requires actual file review.",
            "rows": rows}


def classify(row: dict) -> dict:
    values, invalid = programs(row)
    signals, matches = [], {}
    if not invalid and set(values) & {24, 25}:
        signals.append("gm_acoustic_24_25")
    if not invalid and set(values) & set(range(26, 32)):
        signals.append("gm_other_guitar_26_31")
    for group, fields in (("title", TITLE_FIELDS), ("context", CONTEXT_FIELDS)):
        for name, pattern in (("guitar", GUITAR), ("tablature", TABLATURE), ("related_plucked", RELATED)):
            found = {field: sorted(set(pattern.findall(fold(row.get(field, "")))))
                     for field in fields if pattern.search(fold(row.get(field, "")))}
            if found:
                signal = f"{group}_{name}_keyword"
                signals.append(signal)
                matches[signal] = found
    return {"gm_programs": values, "program_validation_error": invalid,
            "signals": signals, "keyword_matches": matches,
            "legacy_license_eligible": legacy_license(row)}


def digest(path: Path) -> dict:
    sha, md5 = hashlib.sha256(), hashlib.md5(usedforsecurity=False)
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(block)
            md5.update(block)
            size += len(block)
    return {"bytes": size, "sha256": sha.hexdigest(), "md5": md5.hexdigest()}


def audit(csv_path: Path, *, accepted_ids=(), previous_exclusions=()) -> dict:
    """Complete mutually exclusive tier census plus overlapping signal census."""
    before = digest(csv_path)
    accepted = set(accepted_ids)
    previous = {str(item["source_record_id"]): item["reason"] for item in previous_exclusions}
    counts, signals, eligible_signals, tiers, eligible_tiers = (Counter() for _ in range(5))
    program_counts, eligible_program_counts, license_distribution = (Counter() for _ in range(3))
    candidate_licenses, seen_ids, seen_locators = Counter(), Counter(), Counter()
    rows, malformed, old_statuses = [], [], Counter()
    required = {"metadata", "tracks", "n_tracks", "license", "license_conflict", "subset:no_license_conflict", *TITLE_FIELDS, *CONTEXT_FIELDS}
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        if not reader.fieldnames or not required.issubset(reader.fieldnames) or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError("incomplete or duplicate CSV columns")
        for line, row in enumerate(reader, 2):
            counts["dataset_rows"] += 1
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"invalid CSV columns at line {line}")
            match = LOCATOR.fullmatch(row["metadata"])
            native_id = match[1] if match else None
            seen_locators[row["metadata"]] += 1
            if native_id:
                seen_ids[native_id] += 1
            else:
                counts["invalid_metadata_locator"] += 1
            observation = classify(row)
            eligible, flags = observation["legacy_license_eligible"], set(observation["signals"])
            counts["legacy_license_eligible_rows"] += eligible
            counts["empty_program_rows"] += not row["tracks"]
            counts["program_zero_only_rows"] += not observation["program_validation_error"] and set(observation["gm_programs"]) == {0}
            license_key = json.dumps([row["license"], row["license_conflict"], row["subset:no_license_conflict"]], separators=(",", ":"))
            license_distribution[license_key] += 1
            if observation["program_validation_error"]:
                malformed.append({"csv_line": line, "source_record_id": native_id, "csv": dict(row), "reason": observation["program_validation_error"]})
            else:
                for value in set(observation["gm_programs"]):
                    program_counts[str(value)] += 1
                    eligible_program_counts[str(value)] += eligible
            for flag in flags:
                signals[flag] += 1
                eligible_signals[flag] += eligible
            # These tiers partition the complete CSV. Their ordering makes
            # overlaps explicit and permits exact new-recall counts.
            if "gm_acoustic_24_25" in flags:
                tier = "gm_24_25"
            elif "gm_other_guitar_26_31" in flags:
                tier = "gm_26_31_without_24_25"
            elif flags & {"title_guitar_keyword", "context_guitar_keyword"}:
                tier = "guitar_text_without_gm_24_31"
            elif flags & {"title_tablature_keyword", "context_tablature_keyword"}:
                tier = "tablature_text_without_gm_or_guitar_text"
            elif flags & {"title_related_plucked_keyword", "context_related_plucked_keyword"}:
                tier = "related_plucked_text_only"
            else:
                tier = "no_csv_recall_signal"
            tiers[tier] += 1
            eligible_tiers[tier] += eligible
            if flags or observation["program_validation_error"]:
                status = ("existing_924" if native_id in accepted else
                          "previous_metadata_excluded:" + previous[native_id] if native_id in previous else
                          "outside_previous_metadata_candidates")
                old_statuses[status] += 1
                candidate_licenses[license_key] += 1
                rows.append({"csv_line": line, "source_record_id": native_id, "tier": tier,
                             "previous_status": status, **observation, "csv": dict(row)})
    if before != digest(csv_path):
        raise ValueError("CSV changed during full audit")
    if sum(tiers.values()) != counts["dataset_rows"] or sum(eligible_tiers.values()) != counts["legacy_license_eligible_rows"]:
        raise AssertionError("tier partition invariant failed")
    if len(accepted) != len(accepted & seen_ids.keys()):
        raise ValueError("an existing identity is absent from the full CSV")
    return {
        "schema_version": 1, "status": "complete", "checked_at": datetime.now(timezone.utc).isoformat(),
        "input": {"file": "PDMX.csv", **before}, "method": digest(Path(__file__)),
        "scope": "All frozen PDMX v9 CSV rows; recall audit only, not acceptance, player classification or acquisition permission",
        "boundaries": [
            "GM programs are zero-based instrument patches, not tracks or player counts.",
            "GM 26-31 includes electric, muted, overdriven, distorted and harmonic guitar candidates; it is not acoustic inclusion evidence.",
            "Guitar and tablature text may describe another instrument, a title, group or contextual tag; all need source/file review.",
            "Related plucked instruments are separately retained as recall clues, not asserted to be guitars.",
            "Names/attributions are not scanned for keywords; explicit source metadata still needs a complete archive census.",
            "Legacy license eligibility only repeats the previous CSV predicate and does not certify legal status or authorize file acquisition.",
        ],
        "counts": dict(counts), "mutually_exclusive_tiers": dict(tiers),
        "legacy_license_eligible_tiers": dict(eligible_tiers),
        "overlapping_signals": dict(signals), "eligible_overlapping_signals": dict(eligible_signals),
        "gm_program_row_counts": dict(program_counts), "eligible_gm_program_row_counts": dict(eligible_program_counts),
        "license_distribution": [{"license": json.loads(key)[0], "license_conflict": json.loads(key)[1],
                                  "no_conflict_subset": json.loads(key)[2], "count": count}
                                 for key, count in sorted(license_distribution.items())],
        "candidate_license_distribution": [{"license": json.loads(key)[0], "license_conflict": json.loads(key)[1],
                                            "no_conflict_subset": json.loads(key)[2], "count": count}
                                           for key, count in sorted(candidate_licenses.items())],
        "unique_native_ids": len(seen_ids), "unique_metadata_locators": len(seen_locators),
        "duplicate_native_ids": {key: count for key, count in seen_ids.items() if count > 1},
        "duplicate_metadata_locators": {key: count for key, count in seen_locators.items() if count > 1},
        "existing_native_count": len(accepted), "previous_status_counts": dict(old_statuses),
        "malformed_rows": malformed, "recall_rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    catalog = json.loads((root / "sources/musescore/catalog.json").read_text())
    previous = json.loads((root / "sources/musescore/import-report.json").read_text())
    result = audit(root / "sources/musescore/pdmx/PDMX.csv",
                   accepted_ids=[row["id"].split(":", 1)[1] for row in catalog["works"]],
                   previous_exclusions=previous["exclusions"])
    selection_path = root / "sources/musescore/pdmx/selection.json"
    records_path = root / "sources/musescore/pdmx/selected-metadata.json"
    recovery_inputs = {name: digest(path) for name, path in (
        ("selection.json", selection_path), ("selected-metadata.json", records_path),
        ("import-report.json", root / "sources/musescore/import-report.json"),
        ("source_adapters/musescore.py", root / "scripts/source_adapters/musescore.py"))}
    result["legacy_filter_recovery"] = legacy_recovery_audit(
        json.loads(selection_path.read_text()), json.loads(records_path.read_text())["records"], previous["exclusions"])
    result["legacy_filter_recovery"]["inputs"] = recovery_inputs
    for name, path in (("selection.json", selection_path), ("selected-metadata.json", records_path),
                       ("import-report.json", root / "sources/musescore/import-report.json"),
                       ("source_adapters/musescore.py", root / "scripts/source_adapters/musescore.py")):
        if digest(path) != recovery_inputs[name]:
            raise ValueError("legacy recovery input changed during audit: " + name)
    destination = root / "sources/musescore/expansion/full-csv-audit.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_name(destination.name + ".part")
    if destination.is_symlink() or part.is_symlink():
        raise ValueError("audit destination cannot be a symlink")
    with part.open("w", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(part, destination)
    summary = {key: result[key] for key in ("input", "counts", "mutually_exclusive_tiers", "legacy_license_eligible_tiers", "overlapping_signals", "eligible_overlapping_signals", "previous_status_counts")}
    summary["legacy_filter_recovery_counts"] = result["legacy_filter_recovery"]["counts"]
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
