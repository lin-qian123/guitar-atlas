from __future__ import annotations

from pathlib import Path
import struct

from score_midi_crosscheck import crosscheck, mxl_roles, read_sounding_midi


def midi_file(path: Path, tracks: list[bytes], midi_format: int = 1) -> Path:
    path.write_bytes(b"MThd" + struct.pack(">IHHH", 6, midi_format, len(tracks), 480)
                     + b"".join(b"MTrk" + struct.pack(">I", len(track) + 4) + track + b"\x00\xff\x2f\x00" for track in tracks))
    return path


def test_same_tick_program_change_uses_original_event_order(tmp_path: Path) -> None:
    path = midi_file(tmp_path / "same-tick.mid", [
        b"\x00\xc0\x18\x00\x90\x3c\x64\x00\xc0\x1c\x00\x90\x40\x64"
        b"\x01\x80\x3c\x00\x00\x80\x40\x00"])
    result = read_sounding_midi(path)
    assert [(item["program_0based"], item["note_on_count"]) for item in result["sounding_groups"]] == [(24, 1), (28, 1)]
    assert result["validation"]["format"] == "MIDI"


def test_inactive_program_declarations_do_not_become_sounding_instruments(tmp_path: Path) -> None:
    path = midi_file(tmp_path / "unused.mid", [
        b"\x00\xc0\x18\x00\x90\x3c\x64\x01\x80\x3c\x00\x00\xc0\x34"])
    result = read_sounding_midi(path)
    assert {item["program_0based"] for item in result["sounding_groups"]} == {24}
    assert {item["program_0based"] for item in result["tracks"][0]["declared_programs"]} == {24, 52}


def test_ports_and_default_programs_are_independent(tmp_path: Path) -> None:
    path = midi_file(tmp_path / "ports.mid", [
        b"\x00\xc0\x18\x00\x90\x3c\x64\x01\x80\x3c\x00"
        b"\x00\xff\x21\x01\x01\x00\x90\x40\x64\x01\x80\x40\x00"])
    result = read_sounding_midi(path)
    assert [(item["port"], item["program_0based"], item["default_program_note_count"])
            for item in result["sounding_groups"]] == [(0, 24, 0), (1, 0, 1)]


def test_format_two_tracks_have_independent_program_state(tmp_path: Path) -> None:
    path = midi_file(tmp_path / "independent.mid", [b"\x00\xc0\x18", b"\x00\x90\x3c\x64\x01\x80\x3c\x00"], 2)
    assert read_sounding_midi(path)["sounding_groups"][0]["program_0based"] == 0


def part(name="Guitar", program=24, channel=1, notes=10, part_id="P1") -> dict:
    return {"part_id": part_id, "name": name, "note_count": notes, "abbreviation": "",
            "score_instruments": [{"id": part_id + "-I1", "name": name}],
            "midi_instruments": [{"id": part_id + "-I1", "program_0based": program, "channel_1based": channel}],
            "used_instrument_ids": [], "note_instrument_counts": {}, "clefs": [{"sign": "G"}]}


def sounding(name="Guitar", program=24, channel=1, default=0) -> dict:
    return {"tracks": [{"index": 0, "names": [name], "note_on_count": 10,
                        "declared_programs": [{"program_0based": program}]}],
            "sounding_groups": [{"track": 0, "port": 0, "channel_1based": channel,
                                 "program_0based": program, "note_on_count": 10,
                                 "default_program_note_count": default}],
            "cross_track_same_tick_program_order": []}


def test_default_musicxml_instrument_is_distinct_from_explicit_note_ids() -> None:
    role = mxl_roles({"parts": [part()]})[0]
    assert role["used_instrument_ids"] == ["P1-I1"]
    assert role["instrument_ids_explicit_on_notes"] == []
    assert role["default_instrument_included"] is True


def test_multiple_musicxml_instruments_without_note_ids_are_not_defaulted_to_first() -> None:
    source = part()
    source["score_instruments"].append({"id": "P1-I2", "name": "Voice"})
    source["midi_instruments"].append({"id": "P1-I2", "program_0based": 52, "channel_1based": 2})
    role = mxl_roles({"parts": [source]})[0]
    assert role["default_instrument_included"] is False
    assert role["ambiguous_missing_note_instrument_ids"] is True
    assert role["used_instrument_ids"] == ["P1-I1", "P1-I2"]
    assert crosscheck({"parts": [source]}, sounding())["status"] == "unresolved_conflict"


def test_exact_playback_sound_matches_notation_without_counting_tracks() -> None:
    result = crosscheck({"parts": [part()]}, sounding())
    assert result["status"] == "consistent"
    assert result["sounding_groups"][0]["MXL_part_ids"] == ["P1"]


def test_guitar_palm_mute_and_string_pizzicato_are_sound_variants() -> None:
    assert crosscheck({"parts": [part()]}, sounding(program=28))["status"] == "explained_playback_difference"
    assert crosscheck({"parts": [part("Violin", 40)]}, sounding("Violin", 45))["status"] == "explained_playback_difference"


def test_unprogrammed_default_zero_on_named_guitar_is_not_an_extra_piano() -> None:
    result = crosscheck({"parts": [part()]}, sounding(program=0, default=10))
    assert result["status"] == "explained_playback_difference"
    assert "default_program_on_corresponding_named_notation_role" in result["explanations"]


def test_voice_sound_on_guitar_without_a_notated_voice_is_unresolved() -> None:
    result = crosscheck({"parts": [part()]}, sounding(program=52))
    assert result["status"] == "unresolved_conflict"


def test_named_voice_in_notation_is_reported_as_scope_exception() -> None:
    result = crosscheck({"parts": [part("Voice", 52)]}, sounding("Voice", 52), source_instrumentation="Guitar")
    assert result["status"] == "consistent"
    assert result["named_scope_exceptions"][0]["named_instruments"] == ["voice"]
    assert result["named_scope_exceptions"][0]["source_instrumentation"] == "Guitar"


def test_empty_and_silent_notation_parts_are_explicit_playback_boundaries() -> None:
    midi = sounding()
    midi["tracks"].append({"index": 1, "names": ["Piano"], "note_on_count": 0, "declared_programs": []})
    result = crosscheck({"parts": [part(), part("Piano", 0, 2, notes=20, part_id="P2")]}, midi)
    assert result["status"] == "explained_playback_difference"
    assert result["silent_notation_roles"][0]["reason"] == "notated_part_is_silent_in_corresponding_MIDI_track"


def test_explicit_harmony_playback_layer_does_not_add_a_pianist() -> None:
    mxl = part()
    mxl["harmony_count"] = 3
    midi = sounding()
    midi["sounding_groups"].append({**midi["sounding_groups"][0], "program_0based": 0, "channel_1based": 3})
    result = crosscheck({"parts": [mxl]}, midi)
    assert result["status"] == "explained_playback_difference"
    assert "MXL_harmony_symbols_add_default_sound_chord_playback_on_same_guitar_track" in result["explanations"]
    assert len(result["MXL_roles"]) == 1
    del mxl["harmony_count"]
    assert crosscheck({"parts": [mxl]}, midi)["status"] == "unresolved_conflict"


def test_program_written_by_a_different_named_track_records_routing_collision() -> None:
    mxl = {"parts": [part("Violin", 40), part("Guitar", 24, 2, 0, "P2")]}
    midi = sounding("Violin", 24)
    midi["sounding_groups"][0]["program_origins"] = [{"track": 1, "port": 0, "channel_1based": 1,
                                                    "program_0based": 24, "tick": 0, "sequence": 1}]
    midi["tracks"].append({"index": 1, "names": ["Guitar"], "note_on_count": 0, "declared_programs": []})
    result = crosscheck(mxl, midi)
    assert result["status"] == "explained_playback_difference"
    assert "program_from_other_named_track_reuses_same_port_and_channel" in result["explanations"]
    assert result["sounding_groups"][0]["program_origin_tracks"][0]["track_names"] == ["Guitar"]


def test_percussion_auxiliary_channel_stays_with_the_matched_drum_track() -> None:
    mxl = {"parts": [part("Percussions", 0, 10)]}
    midi = sounding("Caisse Claire", 0, 10)
    midi["sounding_groups"].append({**midi["sounding_groups"][0], "program_0based": 14, "channel_1based": 1})
    result = crosscheck(mxl, midi)
    assert result["status"] == "explained_playback_difference"
    assert result["sounding_groups"][1]["MXL_part_ids"] == ["P1"]


def test_harmony_program_from_another_part_can_pollute_an_existing_channel() -> None:
    guitar = part("Guitar", 24, 2, 10, "P2")
    guitar["harmony_count"] = 2
    midi = sounding("Accordion", 0)
    midi["sounding_groups"][0]["program_origins"] = [{"track": 1, "port": 0, "channel_1based": 1,
                                                    "program_0based": 0, "tick": 0, "sequence": 1}]
    midi["tracks"].append({"index": 1, "names": ["Guitar"], "note_on_count": 0, "declared_programs": []})
    result = crosscheck({"parts": [part("Accordion", 21), guitar]}, midi)
    assert result["sounding_groups"][0]["status"] == "explained_playback_difference"
    assert result["sounding_groups"][0]["reason"] == "program_from_other_named_track_reuses_same_port_and_channel"
