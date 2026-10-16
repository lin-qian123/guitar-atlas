from copy import deepcopy
import hashlib
import json

import pytest

from catalog_instrumentation import per_record_guard
from review_musescore_expansion_final import apply_midi_channel_collision_review, make_projection


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def evidence():
    work = {"id": "musescore:123", "title_en": "Piece", "composer_en": "",
        "source_url": "https://musescore.com/user/7/scores/123", "metadata": {"instrumentation": "Guitar"}}
    mxl = {"file_sha256": "c" * 64, "parts": [
        {"part_id": "P1", "name": "Piano", "note_count": 9},
        {"part_id": "P2", "name": "Cello", "note_count": 6}]}
    classification = {"status": "mxl_scope_verified", "topic_id": "keyboard_reed",
        "instrumentation": "guitar, piano and cello", "instrumentation_zh": "吉他、钢琴、大提琴",
        "guitar_player_count": 1, "ensemble_player_count": 3, "omitted_empty_parts": [],
        "roles": [{"part_id": "P1", "kind": "piano", "sounding": True},
                  {"part_id": "P2", "kind": "cello", "sounding": True}]}
    group = {"track": 0, "port": 0, "channel_1based": 1, "program_0based": 44,
        "note_on_count": 9, "track_names": ["Piano"], "MXL_part_ids": ["P1"],
        "MXL_programs": [0], "matching_basis": "exact_track_name_and_MXL_channel",
        "program_origin_tracks": [{"track": 2, "port": 0, "channel_1based": 1,
            "program_0based": 44, "tick": 0, "sequence": 3, "track_names": ["Cello"]}],
        "status": "unresolved_conflict", "reason": "sounding_program_differs_from_notation_without_an_explained_articulation"}
    playback = {"status": "unresolved_conflict", "sounding_groups": [group,
        {"track": 2, "port": 0, "channel_1based": 15, "program_0based": 48,
         "note_on_count": 6, "track_names": ["Cello"], "MXL_part_ids": ["P2"], "status": "consistent"}],
        "conflicts": [deepcopy(group)], "explanations": []}
    case = {**{key: work[key] for key in ("id", "title_en", "composer_en", "source_url")},
        "native_record_sha256": per_record_guard(work), "mxl_sha256": "c" * 64,
        "pdf_sha256": "d" * 64, "midi_sha256": "e" * 64,
        "part_names": ["Piano", "Cello"], "note": "Exact playback setup collides on one channel.",
        "basis": ["Actual guarded PDF, complete MXL and MIDI event order."],
        "midi_channel_collision_review": [{"part_id": "P1", "origin_part_id": "P2",
                                           "group_sha256": digest(group)}]}
    return work, mxl, classification, playback, case


def apply(work, mxl, classification, playback, case):
    return apply_midi_channel_collision_review(case, work, mxl, classification, playback,
        midi_sha256="e" * 64, pdf_sha256="d" * 64)


def test_exact_collision_preserves_raw_conflict_and_reports_export_defect():
    work, mxl, classification, playback, case = evidence()
    before = deepcopy(playback)
    result = apply(work, mxl, classification, playback, case)
    assert result["status"] == "explained_playback_export_defect"
    assert result["automatic_review"] == before
    assert result["conflicts"] == []
    assert result["sounding_groups"][0]["status"] == "explained_channel_collision"
    assert playback == before


def test_absent_review_never_waives_a_channel_conflict():
    work, mxl, classification, playback, _ = evidence()
    assert apply(work, mxl, classification, playback, None) == playback


@pytest.mark.parametrize("value", [[], None, "proof", [{"part_id": "P1", "track_index": 0,
    "track_name": "Piano", "proof_sha256": "a" * 64}]])
def test_attack_count_exception_requires_a_fresh_guarded_actual_file_match(value):
    work, mxl, classification, playback, case = evidence()
    case["midi_attack_correspondence_review"] = value
    with pytest.raises(ValueError):
        apply(work, mxl, classification, playback, case)


def test_different_origin_name_never_qualifies_without_complete_attack_proof():
    work, mxl, classification, playback, case = evidence()
    case["midi_channel_collision_review"][0]["origin_track_names"] = ["Other Cello"]
    with pytest.raises(ValueError):
        apply(work, mxl, classification, playback, case)


@pytest.mark.parametrize("mutation", ["native", "mxl", "pdf", "midi", "conflict", "count", "origin", "extra", "duplicate", "shared"])
def test_collision_review_fails_closed_for_stale_unmatched_or_unrelated_evidence(mutation):
    work, mxl, classification, playback, case = evidence()
    if mutation == "native": work["title_en"] += " changed"
    elif mutation == "mxl": mxl["file_sha256"] = "a" * 64
    elif mutation == "pdf": case["pdf_sha256"] = "a" * 64
    elif mutation == "midi": case["midi_sha256"] = "a" * 64
    elif mutation == "conflict": case["midi_channel_collision_review"][0]["group_sha256"] = "a" * 64
    elif mutation == "count": mxl["parts"][0]["note_count"] += 1
    elif mutation == "origin": case["midi_channel_collision_review"][0]["origin_part_id"] = "P1"
    elif mutation == "extra": playback["conflicts"].append({"reason": "unrelated_unassigned_part"})
    elif mutation == "duplicate": case["midi_channel_collision_review"] *= 2
    elif mutation == "shared": playback["sounding_groups"].append({"MXL_part_ids": ["P1", "P2"], "note_on_count": 1})
    with pytest.raises(ValueError):
        apply(work, mxl, classification, playback, case)


def test_known_export_defect_stays_visible_without_reinterpreting_known_written_roles():
    work, mxl, classification, playback, case = evidence()
    result = apply(work, mxl, classification, playback, case)
    projection = make_projection(work, classification, mxl,
        {"status": "consistent", "actual_pdf_titles": ["Piece"]},
        {label: {"sha256": "a" * 64, "size": 10} for label in ("PDF", "MUSICXML", "MIDI")}, playback=result)
    review = projection["review"]
    assert review["status"] == "file_reviewed_uncertain"
    assert "MIDI" in review["summary"] and "通道" in review["summary"]
    assert review["guitar_player_count"] == 1
    assert review["ensemble_player_count"] == 3
