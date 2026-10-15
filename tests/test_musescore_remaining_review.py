from __future__ import annotations

import gzip
import hashlib
import io
import json
from pathlib import Path

import pytest

import review_musescore_remaining as remaining
from catalog_instrumentation import per_record_guard
from verify_musescore_expansion import (
    AuditFailure, EXACT_CASE_PATH, FINAL_INPUT_PATHS, FINAL_METHOD_PATHS, SCOPE_METHOD_PATHS,
)


def write_json(root, relative, value):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def guard(path):
    raw = path.read_bytes()
    return {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(remaining, "EXPECTED_COUNT", 2)
    monkeypatch.setattr(remaining, "EXPECTED_COHORTS", {"a": 1, "b": 1})
    monkeypatch.setattr(remaining, "EXPECTED_PAGES", 3)
    ids = ["musescore:1", "musescore:2"]
    works = [{"id": identity, "title_en": "乐曲 " + identity, "composer_en": "Author",
              "source_url": "https://musescore.com/user/7/scores/" + identity.split(":")[1],
              "metadata": {"license": "CC0", "native": {"untouched": True}},
              "assets": [{"format": label, "status": "metadata_only"} for label in remaining.FORMATS]}
             for identity in ids]
    scope_manifest = {"schema_version": 1, "ids": ids, "cohorts": {"a": ids[:1], "b": ids[1:]},
                      "scope": "Remaining fixed scope", "base_commit": "1" * 40}
    write_json(tmp_path, remaining.SCOPE, scope_manifest)
    configuration = {"files": {}}
    write_json(tmp_path, FINAL_INPUT_PATHS["configuration"], configuration)
    plan = {"status": "prepared", "works": works,
            "configuration_sha256": guard(tmp_path / FINAL_INPUT_PATHS["configuration"])["sha256"]}
    write_json(tmp_path, FINAL_INPUT_PATHS["plan"], plan)
    assets = {identity: {} for identity in ids}
    for label, suffix in remaining.FORMATS.items():
        for identity in ids:
            raw = (identity + " actual " + label).encode()
            digest = hashlib.sha256(raw).hexdigest()
            relative = "sources/musescore/objects/" + digest + "." + suffix
            path = tmp_path / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            assets[identity][label] = {"format": label, "status": "verified", "sha256": digest,
                "size": len(raw), "local_path": relative, "archive_member": suffix + "/native/" + identity.split(":")[1],
                "archive_sha256": "a" * 64}
        journal = {"format": label, "status": "complete", "scope_ids": ids,
                   "plan_sha256": guard(tmp_path / FINAL_INPUT_PATHS["plan"])["sha256"],
                   "configuration_sha256": plan["configuration_sha256"],
                   "records": {identity: {"status": "verified", "asset": assets[identity][label]} for identity in ids}}
        write_json(tmp_path, FINAL_INPUT_PATHS[label], journal)
    for relative in FINAL_METHOD_PATHS | {str(remaining.METHOD)}:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Exact method bytes " + str(relative))
    write_json(tmp_path, EXACT_CASE_PATH, {"schema_version": 1, "entries": []})
    case_guard = guard(tmp_path / EXACT_CASE_PATH)
    scope = {"status": "complete", "review_stage": "mxl_scope_only", "accepted_ids": ids[:1],
             "records": {ids[0]: {"status": "accepted", "reason": "actual_mxl_guitar_scope", "classification": {"issues": []}},
                         ids[1]: {"status": "pending", "reason": "ambiguous_actual_instrumentation",
                                  "classification": {"issues": ["P1:unidentified_actual_label:Alto"]}}},
             "inputs": {"plan": guard(tmp_path / FINAL_INPUT_PATHS["plan"]),
                        "mxl_extraction": guard(tmp_path / FINAL_INPUT_PATHS["MUSICXML"]),
                        "methods": {relative: guard(tmp_path / relative) for relative in SCOPE_METHOD_PATHS},
                        "reviewed_cases": case_guard}}
    write_json(tmp_path, FINAL_INPUT_PATHS["scope_review"], scope)
    final = {"status": "complete", "review_stage": "actual_pdf_mxl_midi", "works": [],
             "records": {ids[0]: {"status": "accepted", "reason": "three_format_review_complete"}},
             "inputs": {name: guard(tmp_path / relative) for name, relative in FINAL_INPUT_PATHS.items()},
             "methods": {relative: guard(tmp_path / relative) for relative in FINAL_METHOD_PATHS},
             "reviewed_cases": case_guard}
    write_json(tmp_path, remaining.BASE / "final-review.json", final)
    documents = {}
    for index, name in enumerate(("a", "b")):
        work, identity = works[index], ids[index]
        if name == "a":
            texts = ["完整 PDF 原文，保留乐器与中文。"]
            pdf = {"page_count": 1, "all_page_text": texts,
                   "all_page_text_sha256": [hashlib.sha256(text.encode()).hexdigest() for text in texts]}
        else:
            pdf = {"pages": 2, "page_evidence": [{"page": 1, "text": "Guitarra"}, {"page": 2, "text": "第二页"}]}
        record = {key: work[key] for key in ("id", "title_en", "composer_en", "source_url")}
        record.update(native_record_sha256=per_record_guard(work), asset_guards=assets[identity], pdf_evidence=pdf,
                      mxl_evidence={"file_sha256": assets[identity]["MUSICXML"]["sha256"],
                                    "file_bytes": assets[identity]["MUSICXML"]["size"], "validation": {"format": "MUSICXML"},
                                    "parts": [{"name": "保留原文", "unknown": None}]},
                      midi_evidence={"validation": {"format": "MIDI", "tracks": 1, "end_of_track_status": "all_tracks_verified"},
                                     "tracks": [{"index": 0, "note_on_count": 1}]},
                      midi_crosscheck={"status": "consistent", "sounding_groups": []},
                      decision="pending", reason="Exact original reason", unicode_note="No replacement: ♭ / ע / 吉他",
                      arbitrary_evidence=[True, 1, 1.25, None, {"original": "x"}])
        documents[name] = {"schema_version": 1, "cohort": name, "records": {identity: record}, "entries": [],
                           "original_noncanonical_order": {"z": 1, "a": 2}}
    documents["root"] = {"schema_version": 1, "records": {}, "entries": [], "followup": "Unchanged root evidence"}
    for key, relative in remaining.PROPOSALS.items():
        write_json(tmp_path, relative, documents[key])
    return tmp_path, documents, final, assets


def read_bundle(root):
    with gzip.open(root / remaining.DESTINATION, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def write_bundle(root, bundle):
    with gzip.open(root / remaining.DESTINATION, "wt", encoding="utf-8") as stream:
        json.dump(bundle, stream, ensure_ascii=False)


def test_consolidate_is_lossless_and_verifies_without_temporary_proposals(fixture):
    root, original, _, _ = fixture
    result = remaining.consolidate(root)
    assert result["summary"]["statuses"] == {"accepted": 1, "pending": 1}
    assert result["summary"]["pdf_pages"] == 3
    bundle = read_bundle(root)
    assert bundle["original_proposals"] == original
    assert bundle["proposal_semantic_sha256"] == {key: remaining.canonical_sha256(value) for key, value in original.items()}
    assert bundle["records"]["musescore:2"]["outcome"]["pending_reasons"][0]["scope_issues"] == ["P1:unidentified_actual_label:Alto"]
    for relative in remaining.PROPOSALS.values():
        (root / relative).unlink()
    assert remaining.verify(root)["status"] == "verified"
    assert not list((root / remaining.BASE).glob("*.part"))


def test_explicit_refresh_preserves_original_semantics_after_new_final_review(fixture):
    root, _, final, _ = fixture
    remaining.consolidate(root)
    before = read_bundle(root)
    for relative in remaining.PROPOSALS.values():
        (root / relative).unlink()
    final["records"]["musescore:1"].update(status="pending", reason="unresolved_midi_correspondence",
        midi_crosscheck={"status": "unresolved_conflict", "conflicts": [{"track": 1, "reason": "concrete mismatch"}]})
    write_json(root, remaining.BASE / "final-review.json", final)
    with pytest.raises(ValueError, match="refresh outcomes explicitly"):
        remaining.verify(root)
    assert remaining.refresh_outcomes(root)["summary"]["statuses"] == {"pending": 2}
    after = read_bundle(root)
    assert after["original_proposals"] == before["original_proposals"]
    assert after["proposal_semantic_sha256"] == before["proposal_semantic_sha256"]
    assert len(after["records"]["musescore:1"]["outcome"]["pending_reasons"]) == 2
    assert remaining.verify(root)["status"] == "verified"


def test_verification_freshly_rehashes_actual_object_bytes(fixture):
    root, _, _, assets = fixture
    remaining.consolidate(root)
    path = root / assets["musescore:2"]["MIDI"]["local_path"]
    raw = path.read_bytes()
    path.write_bytes(b"!" + raw[1:])
    with pytest.raises(ValueError, match="actual remaining score bytes changed"):
        remaining.verify(root)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "overlap", "native", "asset", "PDF_page", "PDF_text", "MXL_evidence", "MIDI_evidence"])
def test_incomplete_or_stale_evidence_never_replaces_a_receipt(fixture, mutation):
    root, documents, _, _ = fixture
    if mutation in {"missing", "native", "asset", "PDF_page", "PDF_text", "MXL_evidence", "MIDI_evidence"}:
        record = documents["a"]["records"]["musescore:1"]
        if mutation == "missing": documents["a"]["records"].clear()
        elif mutation == "native": record["native_record_sha256"] = "0" * 64
        elif mutation == "asset": record["asset_guards"]["PDF"]["sha256"] = "0" * 64
        elif mutation == "PDF_page": record["pdf_evidence"]["page_count"] = 2
        elif mutation == "PDF_text": record["pdf_evidence"]["all_page_text"][0] += " changed"
        elif mutation == "MXL_evidence": record["mxl_evidence"]["file_sha256"] = "0" * 64
        else: record.pop("midi_evidence")
        write_json(root, remaining.PROPOSALS["a"], documents["a"])
    else:
        path = root / remaining.SCOPE
        manifest = json.loads(path.read_text())
        if mutation == "duplicate": manifest["ids"][1] = manifest["ids"][0]
        else: manifest["cohorts"]["b"] = manifest["cohorts"]["a"]
        write_json(root, remaining.SCOPE, manifest)
    with pytest.raises(ValueError):
        remaining.consolidate(root)
    assert not (root / remaining.DESTINATION).exists()


@pytest.mark.parametrize("field", ["original_proposals", "records", "summary"])
def test_gzip_semantic_or_outcome_corruption_is_detected(fixture, field):
    root, _, _, _ = fixture
    remaining.consolidate(root)
    bundle = read_bundle(root)
    if field == "original_proposals": bundle[field]["a"]["records"]["musescore:1"]["unicode_note"] += " changed"
    elif field == "records": bundle[field]["musescore:2"]["outcome"]["reason"] = "fabricated acceptance"
    else: bundle[field]["pdf_pages"] += 1
    write_bundle(root, bundle)
    with pytest.raises(ValueError):
        remaining.verify(root)


def test_native_licensing_changes_are_not_ignored(fixture):
    root, documents, _, _ = fixture
    work = json.loads((root / FINAL_INPUT_PATHS["plan"]).read_text())["works"][0]
    work["metadata"]["license"] = "restricted"
    with pytest.raises(ValueError, match="licensing guard changed"):
        remaining._native(documents["a"]["records"]["musescore:1"], work)


def test_score_symlink_and_unsafe_output_never_traverse_outside_root(fixture, tmp_path):
    root, _, _, assets = fixture
    remaining.consolidate(root)
    path = root / assets["musescore:1"]["PDF"]["local_path"]
    outside = root.parent / "outside-score.pdf"
    outside.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(outside)
    with pytest.raises(ValueError, match="unsafe private path"):
        remaining.verify(root)


def test_atomic_compression_failure_keeps_previous_receipt(fixture, monkeypatch):
    root, _, _, _ = fixture
    remaining.consolidate(root)
    path = root / remaining.DESTINATION
    before = path.read_bytes()
    context = remaining._load_context(root)
    bundle = read_bundle(root)
    real_replace = remaining.os.replace

    def fail_replace(source, destination):
        if Path(destination) == path:
            raise OSError("simulated write interruption")
        return real_replace(source, destination)

    monkeypatch.setattr(remaining.os, "replace", fail_replace)
    with pytest.raises(OSError, match="write interruption"):
        remaining._atomic_gzip(context, bundle)
    assert path.read_bytes() == before
    assert not list(path.parent.glob("*.part"))


def test_streamed_json_preserves_split_unicode_values_and_rejects_duplicates():
    raw = json.dumps({"records": {"one": {"text": "吉他" * 40000}}, "tail": 123456789}, ensure_ascii=False)
    cursor = remaining._JSONCursor(io.StringIO(raw))
    assert dict(cursor.object_pairs()) == json.loads(raw)
    cursor.whitespace()
    assert cursor.eof
    cursor = remaining._JSONCursor(io.StringIO('{"records":{"one":1,"one":2}}'))
    with pytest.raises(ValueError, match="duplicate"):
        dict(cursor.object_pairs())
    with pytest.raises(ValueError, match="non-finite"):
        remaining._loads('{"value":NaN}')
    with pytest.raises(ValueError, match="streamed JSON"):
        dict(remaining._JSONCursor(io.StringIO('{"one":1,\u00a0"two":2}')).object_pairs())


@pytest.mark.parametrize("mutation", ["reuse", "MIDIgroup"])
def test_optional_followup_reuses_exact_original_evidence_without_double_counting(fixture, mutation):
    root, original, _, assets = fixture
    evidence = original["a"]["records"]["musescore:1"]
    followup = {"schema_version": 1, "records": {"musescore:1": {
        "native_record_sha256": evidence["native_record_sha256"], "asset_guards": assets["musescore:1"],
        "complete_actual_evidence_reuse": {"report": str(remaining.PROPOSALS["a"]),
            "sha256": guard(root / remaining.PROPOSALS["a"])["sha256"], "record_id": "musescore:1",
            "PDF_page_count": 1, "PDF_all_page_text_sha256": evidence["pdf_evidence"]["all_page_text_sha256"]},
        "observation": "Actual follow-up observation"}}, "entries": []}
    group = {"track": 1, "note_on_count": 2, "program_origin_tracks": [{"track": 3}]}
    followup["additional_MIDI_evidence"] = {"musescore:1": {
        "native_record_sha256": evidence["native_record_sha256"], "asset_guards": assets["musescore:1"],
        "actual_conflicting_group": group, "group_sha256": remaining.canonical_sha256(group)}}
    write_json(root, remaining.OPTIONAL_PROPOSALS["a_followup"], followup)
    result = remaining.consolidate(root)
    assert result["summary"]["records"] == 2
    assert result["summary"]["pdf_pages"] == 3
    bundle = read_bundle(root)
    assert bundle["original_proposals"]["a_followup"] == followup
    (root / remaining.OPTIONAL_PROPOSALS["a_followup"]).unlink()
    assert remaining.verify(root)["status"] == "verified"
    if mutation == "reuse":
        bundle["original_proposals"]["a_followup"]["records"]["musescore:1"]["complete_actual_evidence_reuse"]["sha256"] = "0" * 64
    else:
        bundle["original_proposals"]["a_followup"]["additional_MIDI_evidence"]["musescore:1"]["group_sha256"] = "0" * 64
    bundle["proposal_semantic_sha256"]["a_followup"] = remaining.canonical_sha256(bundle["original_proposals"]["a_followup"])
    write_bundle(root, bundle)
    with pytest.raises(ValueError, match="binds complete original evidence" if mutation == "reuse" else "complete group digest changed"):
        remaining.verify(root)


def test_decompression_and_compressed_input_sizes_are_bounded(tmp_path, monkeypatch):
    path = tmp_path / "overlarge.json.gz"
    path.write_bytes(gzip.compress(b" " * 10000))
    monkeypatch.setattr(remaining, "MAX_JSON_BYTES", 1000)
    with pytest.raises(ValueError, match="decompression exceeds size bound"):
        remaining._read_gzip_json(path)
    monkeypatch.setattr(remaining, "MAX_GZIP_BYTES", 1)
    with pytest.raises(ValueError, match="compressed receipt exceeds size bound"):
        remaining._read_gzip_json(path)


def test_truncated_gzip_and_serialization_failure_preserve_previous_archive(fixture, monkeypatch):
    root, _, _, _ = fixture
    remaining.consolidate(root)
    path = root / remaining.DESTINATION
    before = path.read_bytes()
    partial = path.with_name("truncated.json.gz")
    partial.write_bytes(before[:-5])
    with pytest.raises((EOFError, OSError)):
        remaining._read_gzip_json(partial)
    context = remaining._load_context(root)
    bundle = read_bundle(root)
    monkeypatch.setattr(remaining, "MAX_JSON_BYTES", 10)
    with pytest.raises(ValueError, match="serialization exceeds size bound"):
        remaining._atomic_gzip(context, bundle)
    assert path.read_bytes() == before
    assert not list(path.parent.glob("*.part"))


def test_current_scope_final_method_fingerprints_are_not_optional(fixture):
    root, _, _, _ = fixture
    remaining.consolidate(root)
    path = root / "scripts/score_midi_crosscheck.py"
    path.write_text("Changed production method")
    with pytest.raises(AuditFailure, match="review method bytes changed"):
        remaining.verify(root)


def test_refresh_cannot_rebase_frozen_format_extraction_bytes(fixture):
    root, _, final, _ = fixture
    remaining.consolidate(root)
    path = root / FINAL_INPUT_PATHS["PDF"]
    path.write_bytes(path.read_bytes() + b"\n")
    final["inputs"]["PDF"] = guard(path)
    write_json(root, remaining.BASE / "final-review.json", final)
    with pytest.raises(ValueError, match="cannot replace frozen native scope or extraction bytes"):
        remaining.refresh_outcomes(root)


def test_independent_exclusion_crosscheck_is_preserved_without_overriding_final_outcomes(fixture):
    root, original, _, assets = fixture
    evidence = original["b"]["records"]["musescore:2"]
    row = {key: evidence[key] for key in ("id", "title_en", "composer_en", "source_url", "native_record_sha256")}
    row.update({field: assets["musescore:2"][label]["sha256"] for field, label in
                (("pdf_sha256", "PDF"), ("mxl_sha256", "MUSICXML"), ("midi_sha256", "MIDI"))})
    row["conclusion"] = "Former large-ensemble exclusion lacks a simultaneous independent-role witness"
    document = {"schema_version": 1, "records": {"musescore:2": row},
                "inputs": {str(remaining.PROPOSALS[key]): guard(root / remaining.PROPOSALS[key]) for key in ("a", "b")}}
    write_json(root, remaining.OPTIONAL_PROPOSALS["exclusion_crosscheck"], document)
    remaining.consolidate(root)
    bundle = read_bundle(root)
    assert bundle["original_proposals"]["exclusion_crosscheck"] == document
    assert bundle["records"]["musescore:2"]["outcome"]["status"] == "pending"
    (root / remaining.OPTIONAL_PROPOSALS["exclusion_crosscheck"]).unlink()
    assert remaining.verify(root)["summary"]["records"] == 2
