"""Guarded, private file-review overlay for the frozen MuseScore identities.

The source catalog remains a native transcription. A complete review may change
its runtime display and common topics only while every identity and score byte
still agrees with the reviewed inputs. No paths or digest evidence is projected.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

REVIEW_PATH = Path("sources/musescore/instrumentation-review.json")
REVIEW_FORMATS = frozenset({"PDF", "MUSICXML", "MIDI"})
REVIEW_STATUSES = frozenset({"file_verified", "file_reviewed_uncertain"})
PLAYER_TOPICS = {"solo": 1, "duo": 2, "trio": 3, "quartet": 4}
PRECISE_TOPICS = frozenset({*PLAYER_TOPICS, "guitar_ensemble"})
INSTRUMENT_TOPICS = frozenset({*PRECISE_TOPICS, "strings", "woodwinds", "brass",
    "keyboard_reed", "plucked", "percussion", "mixed_chamber", "unspecified", "guitar_unspecified", "other_instrumentation"})
_SHA256 = re.compile(r"[0-9a-f]{64}")
_PRIVATE_TEXT = re.compile(
    r"(?:[a-z][a-z0-9+.-]*://|(?:^|\s)[A-Za-z]:[\\/]|(?:^|\s)/[A-Za-z]|"
    r"\b(?:sources|objects|metadata|private|backups)/|\bsha(?:256|1)\b|\b[0-9a-f]{64}\b|"
    r"[\w.-]+\.(?:pdf|mxl|musicxml|mid|midi|mscz|mscx)(?:\b|$))", re.I)


def _fail(reason: str) -> None:
    raise ValueError("invalid instrumentation review: " + reason)


def _public_text(value: object, field: str, *, optional: bool = False) -> str:
    if optional and value in (None, ""):
        return ""
    if (not isinstance(value, str) or not value.strip() or len(value) > 2000
            or any(ord(char) < 32 and char not in "\n\t" for char in value)
            or _PRIVATE_TEXT.search(value)):
        _fail(f"{field} must be public descriptive text")
    return value


def _count(value: object, field: str) -> int | None:
    if value is None:
        return None
    if type(value) is not int or not 0 <= value <= 128:
        _fail(f"{field} must be an explicit player count or null")
    return value


def _check_asset(root: Path, work: dict, label: str, guard: object) -> None:
    if (not isinstance(guard, dict) or not _SHA256.fullmatch(str(guard.get("sha256", "")))
            or type(guard.get("size")) is not int or guard["size"] <= 0):
        _fail(f"{work['id']} {label} has an invalid asset guard")
    matches = [asset for asset in work.get("assets", []) if asset.get("format") == label]
    if len(matches) != 1:
        _fail(f"{work['id']} {label} requires exactly one current asset")
    asset = matches[0]
    if (asset.get("status") != "verified" or asset.get("sha256") != guard["sha256"]
            or type(asset.get("size")) is not int or asset["size"] != guard["size"]):
        _fail(f"{work['id']} {label} asset guard disagrees with the current manifest")
    value = asset.get("local_path")
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        _fail(f"{work['id']} {label} has an unsafe local asset path")
    relative = Path(value)
    path = root / relative
    if (relative.is_absolute() or ".." in relative.parts
            or not path.resolve().is_relative_to(root.resolve())):
        _fail(f"{work['id']} {label} has an unsafe local asset path")
    try:
        before = path.stat()
        if not path.is_file() or before.st_size != guard["size"]:
            _fail(f"{work['id']} {label} actual file size disagrees")
        with path.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        after = path.stat()
    except OSError as error:
        _fail(f"{work['id']} {label} actual file is unavailable: {error.__class__.__name__}")
    if (digest != guard["sha256"] or (before.st_size, before.st_mtime_ns, before.st_ctime_ns)
            != (after.st_size, after.st_mtime_ns, after.st_ctime_ns)):
        _fail(f"{work['id']} {label} actual file bytes changed")


def _check_review(work: dict, review: object) -> dict:
    if not isinstance(review, dict) or review.get("status") not in REVIEW_STATUSES:
        _fail(f"{work['id']} requires a completed file review status")
    topic = review.get("topic_id")
    if not isinstance(topic, str) or topic not in INSTRUMENT_TOPICS:
        _fail(f"{work['id']} has an invalid instrumentation topic")
    unnumbered_ensemble = (topic == "guitar_ensemble"
        and review.get("ensemble_size_unspecified") is True
        and type(review.get("written_guitar_part_count")) is int
        and review["written_guitar_part_count"] >= 5
        and review.get("guitar_player_count") is None
        and review.get("ensemble_player_count") is None)
    if topic in PRECISE_TOPICS and not unnumbered_ensemble and (review["status"] != "file_verified"
            or work.get("metadata", {}).get("scope_status") == "pending_review"):
        _fail(f"{work['id']} uncertain instrumentation cannot establish a precise player topic")
    guitar = _count(review.get("guitar_player_count"), "guitar_player_count")
    ensemble = _count(review.get("ensemble_player_count"), "ensemble_player_count")
    if guitar is not None and ensemble is not None and guitar > ensemble:
        _fail(f"{work['id']} guitar players exceed all ensemble players")
    if topic in PLAYER_TOPICS and (guitar != PLAYER_TOPICS[topic] or ensemble != guitar):
        _fail(f"{work['id']} precise guitar topic and performing-player counts disagree")
    if topic == "guitar_ensemble" and not unnumbered_ensemble and (guitar is None or guitar < 5 or ensemble != guitar):
        _fail(f"{work['id']} guitar ensemble requires at least five verified guitar players")
    return {"status": review["status"], "topic_id": topic,
            "guitar_player_count": guitar, "ensemble_player_count": ensemble,
            **{key: _public_text(review.get(key), key) for key in
               ("instrumentation", "instrumentation_zh", "summary")},
            **{key: _public_text(review.get(key), key, optional=True) for key in
               ("file_title", "file_identity_note", "file_part_labels")},
            **({"written_guitar_part_count": review["written_guitar_part_count"],
                "ensemble_size_note": "分部人数未标"} if unnumbered_ensemble else {}),
            "source_difference": _public_text(review.get("source_difference"), "source_difference", optional=True)}


def apply_instrumentation_review(root: Path, catalog: dict, *, catalog_bytes: bytes) -> dict:
    """Return a fresh effective catalog, or unchanged data when no review exists.

    A present incomplete/stale review is always an error. Each call checks file
    bytes afresh; a previous export cannot stand in for current file evidence.
    """
    if catalog.get("source_id") != "musescore":
        return catalog
    path = root / REVIEW_PATH
    if not path.exists() and not path.is_symlink():
        return catalog
    if not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
        _fail("review file must stay inside the library")
    try:
        payload = json.loads(path.read_bytes())
    except (OSError, ValueError) as error:
        _fail(f"review cannot be read: {error.__class__.__name__}")
    if (not isinstance(payload, dict) or type(payload.get("schema_version")) is not int
            or payload["schema_version"] != 1 or payload.get("source_id") != "musescore"
            or payload.get("status") != "complete"
            or payload.get("catalog_sha256") != hashlib.sha256(catalog_bytes).hexdigest()
            or not isinstance(payload.get("works"), list)):
        _fail("schema, completion status or native catalog digest disagrees")
    originals = {work["id"]: work for work in catalog["works"]}
    if len(originals) != len(catalog["works"]):
        _fail("native catalog contains duplicate identities")
    entries = {}
    for entry in payload["works"]:
        if (not isinstance(entry, dict) or not isinstance(entry.get("id"), str)
                or entry["id"] not in originals or entry["id"] in entries):
            _fail("unknown or duplicate reviewed identity")
        work = originals[entry["id"]]
        if any(entry.get(key) != work.get(key) for key in ("title_en", "composer_en", "source_url")):
            _fail(f"{work['id']} exact native title, attribution or source URL changed")
        guards = entry.get("assets")
        if not isinstance(guards, dict) or set(guards) != REVIEW_FORMATS:
            _fail(f"{work['id']} requires every PDF, MXL and MIDI asset guard")
        review = _check_review(work, entry.get("review"))
        for label in sorted(REVIEW_FORMATS):
            _check_asset(root, work, label, guards[label])
        entries[entry["id"]] = review
    if set(entries) != set(originals):
        _fail("review must cover every native catalog identity exactly once")
    result = copy.deepcopy(catalog)
    for work in result["works"]:
        review = entries[work["id"]]
        metadata = work.setdefault("metadata", {})
        source_instrumentation = metadata.get("instrumentation")
        if isinstance(source_instrumentation, str):
            metadata["source_instrumentation"] = source_instrumentation
        metadata.update(instrumentation=review["instrumentation"],
                        instrumentation_zh=review["instrumentation_zh"],
                        guitar_player_count=review["guitar_player_count"],
                        ensemble_player_count=review["ensemble_player_count"],
                        instrumentation_review=review["summary"] + (
                            "；来源差异：" + review["source_difference"] if review["source_difference"] else ""),
                        file_instrumentation_topic_id=review["topic_id"],
                        file_instrumentation_basis="file_crosscheck")
        for key in ("file_title", "file_identity_note", "file_part_labels", "written_guitar_part_count", "ensemble_size_note"):
            if review.get(key):
                metadata[key] = review[key]
        work["instrumentation_status"] = review["status"]
    return result
