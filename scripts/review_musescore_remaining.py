#!/usr/bin/env python
"""Losslessly consolidate and freshly verify the private remaining-759 review.

No native catalog, reviewed case, score object or publication is changed. The
compressed receipt retains the complete JSON values of both review cohorts and
the root follow-up. Current outcomes are separately bound to completed canonical
scope/final reviews. Verification does not need the temporary proposal files.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile

from catalog_instrumentation import per_record_guard
from review_musescore_expansion_final import validate_extraction_journal
from verify_musescore_expansion import check_final_input_guards

BASE = Path("sources/musescore/expansion")
DESTINATION = BASE / "remaining-review.json.gz"
SCOPE = BASE / "remaining-review-scope.json"
PROPOSALS = {"a": BASE / "remaining-review-a.json", "b": BASE / "remaining-review-b.json",
             "root": BASE / "remaining-review-root.json"}
OPTIONAL_PROPOSALS = {"a_followup": BASE / "remaining-review-a-followup.json",
                      "exclusion_crosscheck": BASE / "remaining-exclusion-crosscheck.json"}
FORMATS = {"PDF": "pdf", "MUSICXML": "mxl", "MIDI": "mid"}
EXPECTED_COUNT = 759
EXPECTED_COHORTS = {"a": 380, "b": 379}
EXPECTED_PAGES = 10621
MAX_JSON_BYTES = 512 * 1024 * 1024
MAX_GZIP_BYTES = 256 * 1024 * 1024
METHOD = Path("scripts/review_musescore_remaining.py")
_SHA = re.compile(r"[0-9a-f]{64}")
_ENCODER = json.JSONEncoder(ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical_sha256(value):
    digest = hashlib.sha256()
    for chunk in _ENCODER.iterencode(value):
        digest.update(chunk.encode("utf-8"))
    return digest.hexdigest()


def _pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "duplicate JSON object key: " + key)
        result[key] = value
    return result


def _constant(value):
    raise ValueError("non-finite JSON constant: " + value)


def _loads(raw):
    return json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)


def _stamp(path):
    value = path.stat()
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def _path(root, relative):
    require(isinstance(relative, (str, Path)), "invalid private path")
    relative = Path(relative)
    require(not relative.is_absolute() and ".." not in relative.parts and "\\" not in str(relative)
            and "\x00" not in str(relative), "unsafe private path")
    path = root / relative
    require(not path.is_symlink() and path.resolve().is_relative_to(root), "unsafe private path")
    return path


def _file_guard(root, relative, states):
    path = _path(root, relative)
    before = _stamp(path)
    require(path.is_file(), "private input is not a regular file")
    require(path not in states or states[path] == before, "private input changed during review")
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        require((opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns) == before,
                "private input changed while opening")
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    require(_stamp(path) == before, "private input changed while hashing")
    states[path] = before
    return {"sha256": digest, "size": before[2]}


def _read_json(root, relative, states):
    path = _path(root, relative)
    require(path.stat().st_size <= MAX_JSON_BYTES, "private JSON exceeds size bound")
    guard = _file_guard(root, relative, states)
    raw = path.read_bytes()
    require(_stamp(path) == states[path] and len(raw) == guard["size"]
            and hashlib.sha256(raw).hexdigest() == guard["sha256"], "private JSON changed while reading")
    return _loads(raw), guard


class _JSONCursor:
    """Read report records one at a time, rather than retaining full MXL trees."""
    def __init__(self, stream):
        self.stream, self.buffer, self.position, self.eof = stream, "", 0, False
        self.decoder = json.JSONDecoder(object_pairs_hook=_pairs, parse_constant=_constant)

    def more(self):
        self.buffer = self.buffer[self.position:]
        self.position = 0
        chunk = self.stream.read(65536)
        self.buffer += chunk
        self.eof = not chunk

    def whitespace(self):
        while True:
            while self.position < len(self.buffer) and self.buffer[self.position] in " \t\r\n":
                self.position += 1
            if self.position < len(self.buffer) or self.eof:
                return
            self.more()

    def token(self, expected):
        self.whitespace()
        require(self.buffer[self.position:self.position + 1] == expected, "invalid streamed JSON token")
        self.position += 1

    def value(self):
        self.whitespace()
        while True:
            try:
                value, end = self.decoder.raw_decode(self.buffer, self.position)
            except json.JSONDecodeError:
                require(not self.eof, "incomplete or invalid streamed JSON")
                require(len(self.buffer) - self.position < 256 * 1024 * 1024,
                        "individual report JSON value exceeds bound")
                self.more()
                continue
            if end == len(self.buffer) and not self.eof:
                self.more()
                continue
            self.position = end
            return value

    def object_pairs(self, special=None):
        self.token("{")
        self.whitespace()
        if self.buffer[self.position:self.position + 1] == "}":
            self.position += 1
            return
        seen = set()
        while True:
            key = self.value()
            require(isinstance(key, str) and key not in seen, "invalid or duplicate streamed JSON key")
            seen.add(key)
            self.token(":")
            yield key, special(key) if special is not None else self.value()
            self.whitespace()
            if self.buffer[self.position:self.position + 1] == "}":
                self.position += 1
                return
            self.token(",")


def _scope_outcome(row):
    classification = row.get("classification", {})
    issues = classification.get("issues", [])
    require(isinstance(issues, list), "invalid scope issues")
    return {"status": row.get("status"), "reason": row.get("reason"), "issues": issues,
            "classification_status": classification.get("status"),
            "instrumentation": classification.get("instrumentation"),
            "guitar_player_count": classification.get("guitar_player_count"),
            "ensemble_player_count": classification.get("ensemble_player_count")}


def _final_outcome(row):
    result = {key: row.get(key) for key in ("status", "reason")}
    for key in ("midi_crosscheck", "midi_name_review", "pdf_instrument_review", "file_title_review"):
        value = row.get(key)
        if isinstance(value, dict):
            result[key] = {field: value[field] for field in ("status", "conflicts", "actual_pdf_titles") if field in value}
    return result


def _read_report(root, relative, states, reducer):
    path = _path(root, relative)
    guard = _file_guard(root, relative, states)
    header, records = {}, {}
    with path.open("r", encoding="utf-8") as stream:
        cursor = _JSONCursor(stream)

        def section(key):
            if key != "records":
                return cursor.value()
            for identity, row in cursor.object_pairs():
                require(isinstance(row, dict), "review record must be an object")
                records[identity] = reducer(row)
            return None

        for key, value in cursor.object_pairs(section):
            if key != "records":
                header[key] = value
        cursor.whitespace()
        require(cursor.eof and cursor.position == len(cursor.buffer), "trailing report JSON content")
    require(_stamp(path) == states[path], "canonical review changed while reading")
    require(records, "canonical review records missing")
    return header, records, guard


def _load_context(root):
    root, states = Path(root).resolve(), {}
    scope_manifest, scope_guard = _read_json(root, SCOPE, states)
    ids = scope_manifest.get("ids")
    require(scope_manifest.get("schema_version") == 1 and isinstance(ids, list)
            and len(ids) == EXPECTED_COUNT and len(set(ids)) == len(ids)
            and all(re.fullmatch(r"musescore:[1-9][0-9]*", str(value)) for value in ids),
            "remaining scope must contain exactly 759 unique native identities")
    cohorts = scope_manifest.get("cohorts")
    require(isinstance(cohorts, dict) and set(cohorts) == set(EXPECTED_COHORTS), "remaining cohort names differ")
    for key, count in EXPECTED_COHORTS.items():
        require(isinstance(cohorts[key], list) and len(cohorts[key]) == count
                and len(set(cohorts[key])) == count, "remaining cohort coverage differs")
    require(set(cohorts["a"]).isdisjoint(cohorts["b"]) and set(cohorts["a"]) | set(cohorts["b"]) == set(ids),
            "remaining cohorts must be an exact disjoint partition")
    plan, plan_guard = _read_json(root, BASE / "plan.json", states)
    require(plan.get("status") == "prepared" and isinstance(plan.get("works"), list), "prepared native plan required")
    works = {work["id"]: work for work in plan["works"]}
    require(len(works) == len(plan["works"]) and set(ids) <= set(works), "remaining identities outside native plan")
    scope, scope_rows, scope_bytes = _read_report(root, BASE / "scope-review.json", states, _scope_outcome)
    final, final_rows, final_bytes = _read_report(root, BASE / "final-review.json", states, _final_outcome)
    require(scope.get("status") == final.get("status") == "complete"
            and scope.get("review_stage") == "mxl_scope_only"
            and final.get("review_stage") == "actual_pdf_mxl_midi", "completed canonical scope/final review required")
    require(set(scope_rows) == set(works), "canonical scope review does not cover complete plan")
    accepted = scope.get("accepted_ids")
    require(isinstance(accepted, list) and len(set(accepted)) == len(accepted)
            and set(accepted) == {identity for identity, row in scope_rows.items() if row["status"] == "accepted"}
            and set(final_rows) == set(accepted), "canonical final/scope identity coverage differs")
    check_final_input_guards(root, final, scope)
    journals, guards = {}, {"remaining_scope": scope_guard, "plan": plan_guard,
                           "scope_review": scope_bytes, "final_review": final_bytes}
    for label, suffix in FORMATS.items():
        journal, guard = _read_json(root, BASE / (suffix + "-extraction.json"), states)
        validate_extraction_journal(journal, label, plan_ids=works, accepted_ids=accepted,
            plan_sha256=plan_guard["sha256"], configuration_sha256=plan["configuration_sha256"])
        require(set(ids) <= set(journal["records"]), "remaining review requires all three formats for every identity")
        journals[label], guards[label] = journal, guard
    guards["method"] = _file_guard(root, METHOD, states)
    return {"root": root, "states": states, "scope_manifest": scope_manifest, "ids": ids, "works": works,
            "scope_rows": scope_rows, "final_rows": final_rows, "journals": journals, "guards": guards,
            "semantic_input_verification": {"scope_inputs": scope["inputs"], "final_inputs": final["inputs"],
                "final_methods": final["methods"], "reviewed_cases": final["reviewed_cases"]}}


def _pdf_pages(record):
    evidence = record.get("pdf_evidence")
    require(isinstance(evidence, dict), "missing full PDF evidence")
    if "page_count" in evidence:
        count, texts = evidence["page_count"], evidence.get("all_page_text")
        hashes = evidence.get("all_page_text_sha256")
        require(type(count) is int and count > 0 and isinstance(texts, list) and len(texts) == count
                and isinstance(hashes, list) and len(hashes) == count
                and all(isinstance(text, str) and hashlib.sha256(text.encode()).hexdigest() == digest
                        for text, digest in zip(texts, hashes)), "incomplete or changed all-page PDF text")
    else:
        count, pages = evidence.get("pages"), evidence.get("page_evidence")
        require(type(count) is int and count > 0 and isinstance(pages, list) and len(pages) == count
                and [page.get("page") for page in pages] == list(range(1, count + 1))
                and all(isinstance(page.get("text"), str) for page in pages), "incomplete PDF page evidence")
    return count


def _native(record, work):
    require(record.get("id") == work["id"] and record.get("native_record_sha256") == per_record_guard(work)
            and all(record.get(key) == work.get(key) for key in ("title_en", "composer_en", "source_url")),
            "remaining proposal native identity/licensing guard changed: " + work["id"])


def _artifact(record, label):
    guards = record.get("asset_guards", record.get("assets"))
    require(isinstance(guards, dict) and isinstance(guards.get(label), dict), "missing cohort format evidence")
    return guards[label]


def _asset(context, identity, label, evidence):
    row = context["journals"][label]["records"][identity]
    asset = row.get("asset", {})
    require(row.get("status") == asset.get("status") == "verified" and asset.get("format") == label
            and _SHA.fullmatch(str(asset.get("sha256", "")))
            and type(asset.get("size")) is int and asset["size"] > 0, "unverified canonical format asset")
    for key in ("sha256", "size", "archive_member", "archive_sha256"):
        require(evidence.get(key) == asset.get(key), "cohort/canonical format guard changed: " + identity + " " + label)
    if "local_path" in evidence:
        require(evidence["local_path"] == asset.get("local_path"), "cohort object path changed")
    expected_path = str(Path("sources/musescore/objects") / (asset["sha256"] + "." + FORMATS[label]))
    require(asset.get("local_path") == expected_path, "asset is not its canonical immutable format object")
    return {key: asset[key] for key in ("sha256", "size", "local_path", "archive_member", "archive_sha256")}


def _outcome(scope, final):
    require(scope["status"] in {"accepted", "excluded", "pending"} and isinstance(scope.get("reason"), str),
            "invalid canonical scope outcome")
    if scope["status"] == "accepted":
        require(isinstance(final, dict) and final.get("status") in {"accepted", "pending"}
                and isinstance(final.get("reason"), str), "accepted scope lacks final review outcome")
        status, reason = final["status"], final["reason"]
    else:
        require(final is None, "nonaccepted scope unexpectedly has final outcome")
        status, reason = scope["status"], scope["reason"]
    pending = []
    if status == "pending":
        pending = [{"stage": "scope" if final is None else "final", "reason": reason,
                    "scope_issues": scope["issues"]}]
        if final is not None:
            for key, value in final.items():
                if isinstance(value, dict) and value.get("status") == "unresolved_conflict":
                    pending.append({"stage": key, **value})
    return {"status": status, "reason": reason, "scope": scope, "final": final, "pending_reasons": pending}


def _complete_format_evidence(record, assets):
    mxl = record.get("mxl_evidence")
    require(isinstance(mxl, dict) and mxl.get("file_sha256") == assets["MUSICXML"]["sha256"]
            and mxl.get("file_bytes") == assets["MUSICXML"]["size"]
            and mxl.get("validation", {}).get("format") == "MUSICXML"
            and isinstance(mxl.get("parts"), list) and bool(mxl["parts"]),
            "missing or stale complete MXL part evidence")
    midi = record.get("midi_note_evidence", record.get("midi_evidence"))
    require(isinstance(midi, dict) and midi.get("validation", {}).get("format") == "MIDI"
            and midi["validation"].get("end_of_track_status") == "all_tracks_verified"
            and isinstance(midi.get("tracks"), list) and bool(midi["tracks"])
            and len(midi["tracks"]) == midi["validation"].get("tracks")
            and isinstance(record.get("midi_crosscheck"), dict)
            and isinstance(record["midi_crosscheck"].get("sounding_groups"), list),
            "missing complete MIDI track and correspondence evidence")
    if "midi_note_evidence" in record:
        require(midi.get("file_sha256") == assets["MIDI"]["sha256"]
                and midi.get("file_bytes") == assets["MIDI"]["size"], "stale actual MIDI note evidence")


def _derived(context, documents, original_bytes):
    require(isinstance(documents, dict) and set(PROPOSALS) <= set(documents)
            and set(documents) <= set(PROPOSALS) | set(OPTIONAL_PROPOSALS), "complete original proposal documents required")
    require(isinstance(original_bytes, dict) and set(original_bytes) == set(documents)
            and all(isinstance(value, dict) and set(value) == {"sha256", "size"}
                    and _SHA.fullmatch(str(value["sha256"])) and type(value["size"]) is int and value["size"] > 0
                    for value in original_bytes.values()), "original proposal byte guards missing")
    records, pages = {}, 0
    for cohort in ("a", "b"):
        document = documents[cohort]
        require(isinstance(document, dict) and document.get("cohort") == cohort
                and isinstance(document.get("records"), dict)
                and set(document["records"]) == set(context["scope_manifest"]["cohorts"][cohort]),
                "cohort proposal coverage differs")
        for identity, record in document["records"].items():
            _native(record, context["works"][identity])
            count = _pdf_pages(record)
            pages += count
            assets = {label: _asset(context, identity, label, _artifact(record, label)) for label in FORMATS}
            _complete_format_evidence(record, assets)
            records[identity] = {"native_record_sha256": per_record_guard(context["works"][identity]),
                "cohort": cohort, "pdf_pages": count, "assets": assets,
                "outcome": _outcome(context["scope_rows"][identity], context["final_rows"].get(identity))}
    require(set(records) == set(context["ids"]) and pages == EXPECTED_PAGES,
            "remaining review must cover exactly 759 records and 10621 PDF pages")
    followup = documents["root"]
    require(isinstance(followup, dict) and isinstance(followup.get("records"), dict)
            and set(followup["records"]) <= set(records), "root follow-up identity outside remaining scope")
    for identity, record in followup["records"].items():
        require(isinstance(record, dict) and isinstance(record.get("fresh_asset_guards"), dict), "root follow-up asset guards missing")
        for label in FORMATS:
            _asset(context, identity, label, record["fresh_asset_guards"].get(label, {}))
    if "a_followup" in documents:
        followup = documents["a_followup"]
        require(isinstance(followup, dict) and isinstance(followup.get("records"), dict)
                and set(followup["records"]) <= set(context["scope_manifest"]["cohorts"]["a"]), "A follow-up exceeds original A cohort")
        for identity, record in followup["records"].items():
            original = documents["a"]["records"][identity]
            reuse = record.get("complete_actual_evidence_reuse", {})
            require(record.get("native_record_sha256") == per_record_guard(context["works"][identity])
                    and reuse.get("report") == str(PROPOSALS["a"])
                    and reuse.get("sha256") == original_bytes["a"]["sha256"]
                    and reuse.get("record_id") == identity
                    and reuse.get("PDF_page_count") == original["pdf_evidence"]["page_count"]
                    and reuse.get("PDF_all_page_text_sha256") == original["pdf_evidence"]["all_page_text_sha256"],
                    "A follow-up no longer binds complete original evidence")
            for label in FORMATS:
                _asset(context, identity, label, _artifact(record, label))
        additional = followup.get("additional_MIDI_evidence", {})
        require(isinstance(additional, dict) and set(additional) <= set(context["scope_manifest"]["cohorts"]["a"]),
                "additional MIDI follow-up exceeds original A cohort")
        for identity, record in additional.items():
            require(record.get("native_record_sha256") == per_record_guard(context["works"][identity]),
                    "additional MIDI follow-up native guard changed")
            for label in FORMATS:
                _asset(context, identity, label, _artifact(record, label))
            if "actual_conflicting_group" in record or "group_sha256" in record:
                require(isinstance(record.get("actual_conflicting_group"), dict)
                        and record.get("group_sha256") == canonical_sha256(record["actual_conflicting_group"]),
                        "additional MIDI follow-up complete group digest changed")
    if "exclusion_crosscheck" in documents:
        crosscheck = documents["exclusion_crosscheck"]
        require(isinstance(crosscheck, dict) and isinstance(crosscheck.get("records"), dict)
                and set(crosscheck["records"]) <= set(records), "independent crosscheck exceeds remaining scope")
        for identity, record in crosscheck["records"].items():
            _native(record, context["works"][identity])
            require(all(record.get(field) == records[identity]["assets"][label]["sha256"]
                        for field, label in (("pdf_sha256", "PDF"), ("mxl_sha256", "MUSICXML"), ("midi_sha256", "MIDI"))),
                    "independent crosscheck format guard mismatch")
        inputs = crosscheck.get("inputs", {})
        require(isinstance(inputs, dict), "invalid independent crosscheck input guards")
        for cohort in ("a", "b"):
            source = str(PROPOSALS[cohort])
            if source in inputs:
                require(inputs[source] == original_bytes[cohort], "independent crosscheck frozen proposal bytes changed")
    for name, document in documents.items():
        if name == "exclusion_crosscheck" and "entries" not in document:
            continue
        entries = document.get("entries")
        require(isinstance(entries, list) and len({entry.get("id") for entry in entries}) == len(entries),
                "proposal entries must have unique identities within each document")
        for entry in entries:
            identity = entry.get("id")
            require(identity in records and identity in document["records"], "exact proposal outside its documented remaining evidence")
            _native(entry, context["works"][identity])
            require(all(entry.get(field) == records[identity]["assets"][label]["sha256"]
                        for field, label in (("pdf_sha256", "PDF"), ("mxl_sha256", "MUSICXML"), ("midi_sha256", "MIDI"))),
                    "exact proposal three-format guard mismatch")
    files = {}
    for record in records.values():
        for asset in record["assets"].values():
            path = asset["local_path"]
            if path not in files:
                guard = _file_guard(context["root"], path, context["states"])
                require(guard == {key: asset[key] for key in ("sha256", "size")}, "actual remaining score bytes changed")
                files[path] = guard
    summary = {"records": len(records), "pdf_pages": pages, "format_record_associations": {label: len(records) for label in FORMATS},
               "unique_physical_format_objects": {label: len({row["assets"][label]["sha256"] for row in records.values()}) for label in FORMATS},
               "statuses": dict(Counter(row["outcome"]["status"] for row in records.values())),
               "reasons": dict(Counter(row["outcome"]["reason"] for row in records.values())), "missing_records": 0,
               "boundary": "Complete actual-file evidence coverage is not complete instrumentation resolution, repaired MIDI, or note-for-note fidelity certification."}
    return records, summary


def _unchanged(context):
    require(all(_stamp(path) == stamp for path, stamp in context["states"].items()), "review input or score changed during verification")


def _verify_document(bundle, context, *, refresh=False):
    require(isinstance(bundle, dict) and bundle.get("schema_version") == 1 and bundle.get("status") == "complete"
            and bundle.get("scope_manifest") == context["scope_manifest"], "invalid or changed consolidated remaining scope")
    documents = bundle.get("original_proposals")
    require(isinstance(documents, dict) and set(PROPOSALS) <= set(documents)
            and set(documents) <= set(PROPOSALS) | set(OPTIONAL_PROPOSALS), "missing lossless original proposals")
    digests = {key: canonical_sha256(value) for key, value in documents.items()}
    require(bundle.get("proposal_semantic_sha256") == digests, "lossless proposal JSON semantic digest changed")
    records, summary = _derived(context, documents, bundle.get("proposal_original_bytes"))
    if not refresh:
        require(bundle.get("canonical_inputs") == context["guards"]
                and bundle.get("semantic_review_inputs") == context["semantic_input_verification"], "canonical scope/final inputs changed; refresh outcomes explicitly")
        require(bundle.get("records") == records and bundle.get("summary") == summary, "consolidated outcomes or coverage changed")
    else:
        require(bundle.get("canonical_inputs", {}).get("plan") == context["guards"]["plan"]
                and bundle.get("canonical_inputs", {}).get("remaining_scope") == context["guards"]["remaining_scope"]
                and all(bundle.get("canonical_inputs", {}).get(label) == context["guards"][label] for label in FORMATS),
                "refresh cannot replace frozen native scope or extraction bytes")
    _unchanged(context)
    return records, summary


def _read_gzip_json(path):
    require(path.stat().st_size <= MAX_GZIP_BYTES, "compressed receipt exceeds size bound")
    with gzip.open(path, "rb") as stream:
        raw = stream.read(MAX_JSON_BYTES + 1)
    require(len(raw) <= MAX_JSON_BYTES, "receipt decompression exceeds size bound")
    return _loads(raw)


def _load_bundle(context):
    path = _path(context["root"], DESTINATION)
    before = _stamp(path)
    value = _read_gzip_json(path)
    require(_stamp(path) == before, "consolidated receipt changed while reading")
    context["states"][path] = before
    return value


def _atomic_gzip(context, value):
    destination = _path(context["root"], DESTINATION)
    destination.parent.mkdir(parents=True, exist_ok=True)
    original = _stamp(destination) if destination.exists() else None
    expected = canonical_sha256(value)
    descriptor, name = tempfile.mkstemp(prefix="remaining-review-", suffix=".json.gz.part", dir=destination.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            with gzip.GzipFile(filename="", fileobj=output, mode="wb", compresslevel=6, mtime=0) as stream:
                with io.BufferedWriter(stream, buffer_size=256 * 1024) as buffered:
                    total = 0
                    for chunk in _ENCODER.iterencode(value):
                        raw = chunk.encode("utf-8")
                        total += len(raw)
                        require(total <= MAX_JSON_BYTES, "receipt serialization exceeds size bound")
                        buffered.write(raw)
            output.flush()
            os.fsync(output.fileno())
        recovered = _read_gzip_json(temporary)
        require(canonical_sha256(recovered) == expected, "compressed receipt semantic readback differs")
        require(all(canonical_sha256(recovered["original_proposals"][key]) == digest
                    for key, digest in value["proposal_semantic_sha256"].items()), "compressed proposal semantic readback differs")
        _unchanged(context)
        require((_stamp(destination) if destination.exists() else None) == original, "receipt changed before atomic replacement")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    # Only this authorized receipt replacement may change its original stamp.
    # Source inputs and score objects remain guarded through the final hash.
    context["states"].pop(destination, None)
    guard = _file_guard(context["root"], DESTINATION, context["states"])
    _unchanged(context)
    return {"path": str(DESTINATION), **guard, "semantic_sha256": expected}


def consolidate(root):
    context = _load_context(root)
    require(not _path(context["root"], DESTINATION).exists(), "consolidated receipt already exists; verify or refresh it")
    documents, source_bytes = {}, {}
    paths = {**PROPOSALS, **{key: relative for key, relative in OPTIONAL_PROPOSALS.items()
                            if _path(context["root"], relative).exists()}}
    for key, relative in paths.items():
        documents[key], source_bytes[key] = _read_json(context["root"], relative, context["states"])
    records, summary = _derived(context, documents, source_bytes)
    bundle = {"schema_version": 1, "status": "complete", "checked_at": datetime.now(timezone.utc).isoformat(),
              "scope_manifest": context["scope_manifest"], "original_proposals": documents,
              "proposal_original_bytes": source_bytes,
              "proposal_semantic_sha256": {key: canonical_sha256(value) for key, value in documents.items()},
              "canonical_inputs": context["guards"], "semantic_review_inputs": context["semantic_input_verification"],
              "records": records, "summary": summary}
    _verify_document(bundle, context)
    return {"status": "consolidated", **_atomic_gzip(context, bundle), "summary": summary}


def verify(root):
    context = _load_context(root)
    bundle = _load_bundle(context)
    _, summary = _verify_document(bundle, context)
    guard = _file_guard(context["root"], DESTINATION, context["states"])
    _unchanged(context)
    return {"status": "verified", "path": str(DESTINATION), **guard,
            "semantic_sha256": canonical_sha256(bundle), "proposal_semantic_sha256": bundle["proposal_semantic_sha256"], "summary": summary}


def refresh_outcomes(root):
    context = _load_context(root)
    bundle = _load_bundle(context)
    records, summary = _verify_document(bundle, context, refresh=True)
    bundle.update(checked_at=datetime.now(timezone.utc).isoformat(), canonical_inputs=context["guards"],
                  semantic_review_inputs=context["semantic_input_verification"], records=records, summary=summary)
    _verify_document(bundle, context)
    return {"status": "outcomes_refreshed", **_atomic_gzip(context, bundle), "summary": summary}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--consolidate", action="store_true")
    group.add_argument("--verify", action="store_true", help="default; original proposal files are not needed")
    group.add_argument("--refresh-outcomes", action="store_true")
    args = parser.parse_args()
    action = consolidate if args.consolidate else refresh_outcomes if args.refresh_outcomes else verify
    print(json.dumps(action(args.root), ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
