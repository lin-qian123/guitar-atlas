"""Guarded, source-preserving notes from exact score-file observations.

This is a runtime overlay over normalized native catalogs. It does not edit
native records, and its private evidence is never projected to public output.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

REVIEW_PATH = Path("metadata/instrumentation/source_file_notes_reviewed.json")
APPLIED_FILE_NOTE_IDS = "_applied_source_file_note_ids"
APPLIED_FILE_CLASSIFICATIONS = "_applied_source_file_classifications"
CSUN_OPTION_ID = "csun:1071"
CSUN_VOCAL_ANTHOLOGY_ID = "csun:1024"
REVIEWED_SOURCES = frozenset({"guitarclassroom", "maikstrings", "csun"})
REVIEWED_IDS_BY_SOURCE = {
    "guitarclassroom": frozenset({
        "guitarclassroom:pdf:d929010899e2291f34810fc4fe6f7af4e65aa0a3f527b01ae885090b4fd6c7e5",
        "guitarclassroom:pdf:798e2fd5bd8ee3e7d8414fd8e0497b34a5a21a6a9d18b8fe71bc87cbf7150aac",
    }),
    "maikstrings": frozenset({
        "maikstrings:pdf:bbdea8bba406cb3eb62392f3f784b05f57495ee1819e19096ded38a7fe4d114c",
        "maikstrings:pdf:0a60f0910ebfe594c123411eea75422fb197c0236b0f92fdbe0bd48ceb418a69",
    }),
    "csun": frozenset({CSUN_OPTION_ID, CSUN_VOCAL_ANTHOLOGY_ID}),
}
INSTRUMENTATION_OVERRIDES = {
    "maikstrings:pdf:bbdea8bba406cb3eb62392f3f784b05f57495ee1819e19096ded38a7fe4d114c": "2 guitars",
    CSUN_OPTION_ID: "one or two guitars",
}
SCORE_CLASSIFICATIONS = {
    "maikstrings:pdf:bbdea8bba406cb3eb62392f3f784b05f57495ee1819e19096ded38a7fe4d114c": {
        "topic_id": "duo", "basis": "reviewed_score_evidence",
        "instrumentation": "双吉他编配（据谱面明确标注）", "player_count": 2,
    },
    CSUN_OPTION_ID: {
        "topic_id": "guitar_unspecified", "basis": "reviewed_score_evidence",
        "instrumentation": "吉他；谱页列明一把或两把的选项，具体演奏人数未定",
        "player_count": None,
    },
    CSUN_VOCAL_ANTHOLOGY_ID: {
        "topic_id": "other_instrumentation", "basis": "reviewed_score_evidence",
        "instrumentation": "声乐与吉他（合集内已核见合唱声部及吉他；其他曲目未逐页核实）",
        "player_count": None,
    },
}
CSUN_EVIDENCE_PAGES = {CSUN_OPTION_ID: 2, CSUN_VOCAL_ANTHOLOGY_ID: 10}
EVIDENCE_PACKET = "sources/source-expansion/new-pdf-evidence.json.gz"
CSUN_EVIDENCE_PACKET = "sources/source-expansion/csun-score-samples.json"


def digest(value: object) -> str:
    """Match catalog_classification.digest's canonical JSON representation."""
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _safe_public_text(value: object, *, limit: int = 600) -> bool:
    return (isinstance(value, str) and bool(value.strip()) and len(value) <= limit
            and not re.search(r"https?://|file:|(?:sources|objects|metadata)/|[a-f0-9]{64}|\.(?:pdf|mxl|mid)\b", value, re.I)
            and not re.search(r"(?:^|\s)(?:/(?:Users|Volumes|tmp|private|home|var)/|[A-Za-z]:[\\/])|\bprivate/", value, re.I)
            and not any(ord(c) < 32 and c not in "\n\t" for c in value))


def _read_review(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError("unsafe source file-notes review asset")
    before = path.stat()
    raw = path.read_bytes()
    after = path.stat()
    stamp = lambda st: (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
    if stamp(before) != stamp(after):
        raise ValueError("source file-notes review changed while reading")
    review = json.loads(raw)
    if (review.get("schema_version") != 1 or review.get("status") != "complete"
            or not isinstance(review.get("entries"), dict)):
        raise ValueError("incomplete source file-notes review")
    return review


def _stat_stamp(path: Path):
    st = path.stat()
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def _verify_evidence_packet(root: Path, entries: dict) -> tuple[Path, Path, tuple]:
    guards = set()
    for entry in entries.values():
        evidence = entry.get("evidence", {}) if isinstance(entry, dict) else {}
        guards.add((evidence.get("packet"), evidence.get("packet_sha256"), evidence.get("packet_size")))
    if len(guards) != 1:
        raise ValueError("source file-note entries disagree on evidence packet guard")
    packet_name, expected_sha, expected_size = next(iter(guards))
    if (packet_name not in {EVIDENCE_PACKET, CSUN_EVIDENCE_PACKET}
            or not re.fullmatch(r"[0-9a-f]{64}", str(expected_sha))
            or type(expected_size) is not int or expected_size <= 0):
        raise ValueError("source file-note evidence packet guard is invalid")
    root_real = root.resolve()
    relative = Path(packet_name)
    if relative.is_absolute() or ".." in relative.parts or "\\" in packet_name:
        raise ValueError("unsafe source file-note evidence packet path")
    packet = root / relative
    if packet.is_symlink() or not packet.resolve().is_relative_to(root_real):
        raise ValueError("source file-note evidence packet leaves the library")
    try:
        before = _stat_stamp(packet)
        resolved = packet.resolve()
        if not packet.is_file() or before[2] != expected_size:
            raise ValueError("source file-note evidence packet size differs")
        hasher = hashlib.sha256()
        with packet.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                hasher.update(block)
        after = _stat_stamp(packet)
    except OSError as error:
        raise ValueError("source file-note evidence packet unavailable") from error
    if (hasher.hexdigest() != expected_sha or before != after or packet.is_symlink()
            or packet.resolve() != resolved or not resolved.is_relative_to(root_real)):
        raise ValueError("source file-note evidence packet changed")
    return packet, resolved, before


def _recheck_path(path: Path, resolved: Path, stamp: tuple, root: Path, label: str) -> None:
    try:
        current = path.resolve()
        current_stamp = _stat_stamp(path)
    except OSError as error:
        raise ValueError(f"{label} changed during source file-note application") from error
    if (path.is_symlink() or current != resolved or not current.is_relative_to(root.resolve())
            or current_stamp != stamp):
        raise ValueError(f"{label} changed during source file-note application")


def _verify_asset(root: Path, work: dict, guard: dict) -> None:
    path_text = guard.get("local_path")
    if (not isinstance(path_text, str) or not path_text or "\\" in path_text
            or "\x00" in path_text or re.match(r"^[A-Za-z]:", path_text)):
        raise ValueError(f"{work.get('id')} has an unsafe reviewed asset path")
    relative = Path(path_text)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{work.get('id')} has an unsafe reviewed asset path")
    path = root / relative
    root_real = root.resolve()
    resolved_before = path.resolve()
    if not resolved_before.is_relative_to(root_real) or path.is_symlink():
        raise ValueError(f"{work.get('id')} reviewed asset leaves the library")

    matches = [asset for asset in work.get("assets", [])
               if asset.get("format") == "PDF" and asset.get("status") == "verified"
               and asset.get("local_path") == path_text]
    if len(matches) != 1:
        raise ValueError(f"{work.get('id')} reviewed asset is not a unique verified PDF")
    asset = matches[0]
    if (guard.get("format") != "PDF" or guard.get("status") != "verified"
            or asset.get("sha256") != guard.get("sha256")
            or type(asset.get("size")) is not int or asset["size"] != guard.get("size")
            or not re.fullmatch(r"[0-9a-f]{64}", str(guard.get("sha256", "")))
            or type(guard.get("size")) is not int or guard["size"] <= 0):
        raise ValueError(f"{work.get('id')} reviewed asset manifest guard differs")
    try:
        before = path.stat()
        if not path.is_file() or before.st_size != guard["size"]:
            raise ValueError(f"{work.get('id')} reviewed asset size differs")
        hasher = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                hasher.update(block)
        after = path.stat()
    except OSError as error:
        raise ValueError(f"{work.get('id')} reviewed asset unavailable") from error
    stamp = lambda st: (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
    resolved_after = path.resolve()
    if (hasher.hexdigest() != guard["sha256"] or stamp(before) != stamp(after)
            or path.is_symlink() or resolved_after != resolved_before
            or not resolved_after.is_relative_to(root_real)):
        raise ValueError(f"{work.get('id')} reviewed asset bytes changed")


def _validate_entry(root: Path, work: dict, entry: dict) -> dict:
    if entry.get("native_record_sha256") != digest(work):
        raise ValueError(f"{work.get('id')} native record changed since file review")
    identity = entry.get("native_identity")
    if not isinstance(identity, dict) or identity != {
            "id": work.get("id"), "title_en": work.get("title_en"),
            "composer_en": work.get("composer_en"),
            "instrumentation": work.get("metadata", {}).get("instrumentation")}:
        raise ValueError(f"{work.get('id')} native identity guard differs")
    evidence = entry.get("evidence")
    expected_packet = (CSUN_EVIDENCE_PACKET
                       if work.get("id") in CSUN_EVIDENCE_PAGES else EVIDENCE_PACKET)
    expected_page = (CSUN_EVIDENCE_PAGES[work["id"]]
                     if expected_packet == CSUN_EVIDENCE_PACKET else 1)
    if (not isinstance(evidence, dict) or evidence.get("page") != expected_page
            or type(evidence.get("actual_pages")) is not int or evidence["actual_pages"] < 1
            or evidence.get("packet") != expected_packet
            or type(evidence.get("packet_size")) is not int or evidence["packet_size"] <= 0
            or type(evidence.get("page")) is not int or evidence["page"] < 1
            or evidence["page"] > evidence.get("actual_pages", 0)
            or not re.fullmatch(r"[0-9a-f]{64}", str(evidence.get("packet_sha256", "")))
            or not _safe_public_text(evidence.get("printed_excerpt"), limit=300)):
        raise ValueError(f"{work.get('id')} file-note evidence receipt is invalid")
    public = entry.get("public")
    if not isinstance(public, dict) or not _safe_public_text(public.get("description_note")):
        raise ValueError(f"{work.get('id')} file-note text is invalid")
    aliases = public.get("title_aliases")
    if (not isinstance(aliases, list) or not aliases
            or any(not _safe_public_text(alias, limit=160) for alias in aliases)
            or len(aliases) != len(set(aliases))):
        raise ValueError(f"{work.get('id')} title aliases are invalid")
    if "file_title" in public:
        if (not _safe_public_text(public.get("file_title"), limit=160)
                or not _safe_public_text(public.get("file_identity_note"), limit=300)):
            raise ValueError(f"{work.get('id')} file identity note is invalid")
    identity = work.get("id")
    if identity in INSTRUMENTATION_OVERRIDES:
        if ("instrumentation" not in public
                or public["instrumentation"] != INSTRUMENTATION_OVERRIDES[identity]):
            raise ValueError(f"{identity} file instrumentation note is missing or differs")
    elif "instrumentation" in public:
        raise ValueError(f"{identity} unsupported file instrumentation note")
    _verify_asset(root, work, entry.get("asset", {}))
    return public


def apply_file_notes(root: Path, effective: dict, native: dict) -> dict:
    """Return a fresh effective catalog with guarded file notes applied.

    Exact source records outside this review's scope are left untouched. The
    returned top-level marker is emitted only after validating every scoped
    native record and its current local PDF bytes.
    """
    if APPLIED_FILE_NOTE_IDS in native or APPLIED_FILE_CLASSIFICATIONS in native:
        raise ValueError("native catalog cannot forge a source file-note marker")
    if APPLIED_FILE_NOTE_IDS in effective or APPLIED_FILE_CLASSIFICATIONS in effective:
        raise ValueError("effective catalog already contains a source file-note marker")
    source_id = native.get("source_id")
    if source_id not in REVIEWED_SOURCES:
        return effective
    review_path = root / REVIEW_PATH
    if not review_path.resolve().is_relative_to(root.resolve()):
        raise ValueError("source file-notes review leaves the library")
    review = _read_review(review_path)
    entries = {key: value for key, value in review["entries"].items()
               if key.startswith(source_id + ":")}
    if set(entries) != REVIEWED_IDS_BY_SOURCE[source_id]:
        raise ValueError("reviewed source is missing its complete file-note scope")
    packet_path, packet_resolved, packet_stamp = _verify_evidence_packet(root, entries)
    indexed = {work.get("id"): work for work in native.get("works", [])}
    effective_index = {work.get("id"): work for work in effective.get("works", [])}
    if set(entries) - set(indexed) or set(entries) - set(effective_index):
        raise ValueError("source file-notes review refers to a missing native identity")

    public_by_id = {identity: _validate_entry(root, indexed[identity], entry)
                    for identity, entry in entries.items()}
    result = copy.deepcopy(effective)
    cloned = {work.get("id"): work for work in result.get("works", [])}
    for identity, public in public_by_id.items():
        work = cloned[identity]
        metadata = work.get("metadata")
        if not isinstance(metadata, dict):
            raise ValueError(f"{identity} effective metadata is missing")
        native_work = indexed[identity]
        for key in ("title_en", "composer_en"):
            if work.get(key) != native_work.get(key):
                raise ValueError(f"{identity} effective {key} differs from native")
        if metadata.get("instrumentation") != native_work.get("metadata", {}).get("instrumentation"):
            raise ValueError(f"{identity} effective instrumentation differs from native")
        prefix = metadata.get("description", "")
        if not isinstance(prefix, str):
            raise ValueError(f"{identity} description is not text")
        note = public["description_note"]
        metadata["description"] = f"{prefix.rstrip()}\n\n{note}" if prefix.strip() else note
        aliases = work.get("title_aliases", [])
        if not isinstance(aliases, list) or any(not isinstance(alias, str) for alias in aliases):
            raise ValueError(f"{identity} existing title aliases are invalid")
        work["title_aliases"] = list(dict.fromkeys([*aliases, *public["title_aliases"]]))
        if "file_title" in public:
            metadata["file_title"] = public["file_title"]
            metadata["file_identity_note"] = public["file_identity_note"]
        if "instrumentation" in public:
            metadata["source_instrumentation"] = native_work.get("metadata", {}).get("instrumentation")
            metadata["instrumentation"] = public["instrumentation"]
    _recheck_path(packet_path, packet_resolved, packet_stamp, root.resolve(),
                  "source file-note evidence packet")
    result[APPLIED_FILE_NOTE_IDS] = sorted(public_by_id)
    score_classifications = {
        identity: {**SCORE_CLASSIFICATIONS[identity], "note": public["description_note"]}
        for identity, public in public_by_id.items() if identity in SCORE_CLASSIFICATIONS
    }
    result[APPLIED_FILE_CLASSIFICATIONS] = score_classifications
    return result
