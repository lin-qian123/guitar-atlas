#!/usr/bin/env python
"""Audit actual note-on MIDI programs against guarded MuseScore MXL roles.

Playback sound changes, inactive program declarations and silent exports are
not extra performers. This is a format/role cross-check, not note fidelity or
acoustic instrument recognition. All output is private acquisition evidence.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import struct
import unicodedata
import zipfile
from xml.etree import ElementTree as ET

from source_adapters.pdmx_formats import validate_source_format
import review_musescore_instrumentation as label_methods
from review_musescore_instrumentation import kind_from_label, LABELS


def _vlq(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    for _ in range(4):
        byte = data[offset]
        offset += 1
        value = value * 128 + (byte & 127)
        if byte < 128:
            return value, offset
    raise ValueError("MIDI VLQ exceeds four bytes")


def read_sounding_midi(path: Path) -> dict:
    """Retain source event order, including program changes at the same tick."""
    validation = validate_source_format(path, "MIDI")
    data = path.read_bytes()
    header_size = int.from_bytes(data[4:8], "big")
    midi_format, track_count, division = struct.unpack(">HHH", data[8:14])
    offset = 8 + header_size
    all_events, tracks = [], []
    for track_index in range(track_count):
        length = int.from_bytes(data[offset + 4:offset + 8], "big")
        chunk = data[offset + 8:offset + 8 + length]
        offset += 8 + length
        position = tick = sequence = port = 0
        running = None
        names, programs, note_ons = [], [], 0
        while position < len(chunk):
            delta, position = _vlq(chunk, position)
            tick += delta
            status = chunk[position]
            if status >= 128:
                position += 1
            elif running is not None:
                status = running
            else:
                raise ValueError("MIDI running status without a preceding event")
            event = {"tick": tick, "track": track_index, "sequence": sequence, "port": port}
            sequence += 1
            if status == 255:
                kind = chunk[position]
                size, position = _vlq(chunk, position + 1)
                payload = chunk[position:position + size]
                position += size
                if kind in (3, 4):
                    names.append(payload.decode("utf-8", "replace").rstrip("\x00").strip())
                if kind == 33:
                    port = payload[0]
                continue
            if status in (240, 247):
                size, position = _vlq(chunk, position)
                payload = chunk[position:position + size]
                position += size
                # Standard General MIDI on/off resets the program defaults.
                if len(payload) >= 4 and payload[:1] == b"\x7e" and payload[2] == 9:
                    all_events.append({**event, "kind": "gm_reset"})
                continue
            running = status
            kind, channel = status >> 4, (status & 15) + 1
            count = 1 if kind in (12, 13) else 2
            payload = chunk[position:position + count]
            position += count
            if kind == 12:
                event.update(kind="program", channel_1based=channel, program_0based=payload[0])
                programs.append({"tick": tick, "sequence": event["sequence"], "port": port,
                                 "channel_1based": channel, "program_0based": payload[0]})
                all_events.append(event)
            elif kind == 9 and payload[1]:
                event.update(kind="note", channel_1based=channel, pitch=payload[0], velocity=payload[1])
                note_ons += 1
                all_events.append(event)
        tracks.append({"index": track_index, "names": list(dict.fromkeys(names)),
                       "declared_programs": programs, "note_on_count": note_ons, "end_tick": tick})
    states, groups = {}, {}
    same_tick = defaultdict(lambda: {"program": set(), "note": set()})
    for event in sorted(all_events, key=lambda item: (item["tick"], item["track"], item["sequence"])):
        if event["kind"] == "gm_reset":
            states.clear()
            continue
        timeline = event["track"] if midi_format == 2 else 0
        key = (timeline, event["port"], event["channel_1based"])
        tie_key = (timeline, event["tick"], event["port"], event["channel_1based"])
        same_tick[tie_key][event["kind"]].add(event["track"])
        if event["kind"] == "program":
            states[key] = {"program_0based": event["program_0based"], "track": event["track"],
                           "tick": event["tick"], "sequence": event["sequence"],
                           "port": event["port"], "channel_1based": event["channel_1based"]}
            continue
        explicit = key in states
        origin = states.get(key)
        program = origin["program_0based"] if origin else 0
        group_key = (event["track"], event["port"], event["channel_1based"], program)
        if group_key not in groups:
            groups[group_key] = {"track": event["track"], "port": event["port"],
                "channel_1based": event["channel_1based"], "program_0based": program,
                "note_on_count": 0, "default_program_note_count": 0,
                "first_tick": event["tick"], "last_tick": event["tick"], "pitch_range": [127, 0],
                "program_origins": []}
        group = groups[group_key]
        group["note_on_count"] += 1
        group["default_program_note_count"] += not explicit
        group["last_tick"] = event["tick"]
        group["pitch_range"][0] = min(group["pitch_range"][0], event["pitch"])
        group["pitch_range"][1] = max(group["pitch_range"][1], event["pitch"])
        if origin and origin not in group["program_origins"]:
            group["program_origins"].append(origin)
    ambiguities = [list(key) for key, item in same_tick.items()
                   if item["program"] and item["note"] and len(item["program"] | item["note"]) > 1]
    return {"validation": validation, "midi_format": midi_format, "division": division,
            "tracks": tracks, "sounding_groups": list(groups.values()),
            "cross_track_same_tick_program_order": ambiguities,
            "timeline_order": "tick, track index, original within-track event sequence; format-2 tracks independent"}


def _name(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", value).replace("\x00", "")).strip().casefold()


def _mxl_ports(path: Path, evidence: dict) -> dict:
    # pdmx_formats has already verified safe ZIP members, XML and no external
    # entities. ElementTree does not fetch MusicXML's external DTD.
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read(evidence["validation"]["score_member"]))
    for element in root.iter():
        element.tag = element.tag.rsplit("}", 1)[-1]
    ports = {}
    for part in root.findall("./part-list/score-part"):
        defaults, explicit = 0, {}
        for device in part.findall("midi-device"):
            if device.get("port"):
                number = int(device.get("port")) - 1
                if device.get("id"):
                    explicit[device.get("id")] = number
                else:
                    defaults = number
        ports[part.get("id")] = (defaults, explicit)
    return ports


def mxl_roles(evidence: dict, ports: dict | None = None) -> list[dict]:
    result = []
    for part in evidence["parts"]:
        instruments = part.get("score_instruments", [])
        selected = set(part.get("used_instrument_ids", []))
        explicit_notes = sum(part.get("note_instrument_counts", {}).values())
        unassigned_notes = part.get("note_count", 0) - explicit_notes
        ambiguous_assignment = len(instruments) > 1 and unassigned_notes > 0
        if len(instruments) == 1 and (not selected or unassigned_notes > 0):
            selected.add(instruments[0]["id"])
        elif ambiguous_assignment or not selected:
            # With multiple declarations the MusicXML instrument element should
            # distinguish every note. Do not silently choose its first entry.
            selected.update(item["id"] for item in instruments)
        active = [item for item in instruments if item["id"] in selected]
        default_port, port_ids = (ports or {}).get(part["part_id"], (0, {}))
        declarations = [dict(item, port=port_ids.get(item.get("id"), default_port))
                        for item in part.get("midi_instruments", []) if item.get("id") in selected]
        labels = [part.get("name", ""), part.get("abbreviation", "")] + [item["name"] for item in active]
        raw_kinds = {kind for label in labels if (kind := kind_from_label(label))}
        kinds = sorted({"percussion" if LABELS.get(kind, (None, None, None))[2] == "percussion" else kind
                        for kind in raw_kinds})
        result.append({"part_id": part["part_id"], "name": part["name"], "labels": labels,
                       "kinds": kinds, "detailed_kinds": sorted(raw_kinds), "note_count": part.get("note_count", 0),
                       "used_instrument_ids": sorted(selected),
                       "default_instrument_included": bool(len(instruments) == 1 and instruments[0]["id"] in selected
                           and instruments[0]["id"] not in part.get("used_instrument_ids", [])),
                       "ambiguous_missing_note_instrument_ids": ambiguous_assignment,
                       "instrument_ids_explicit_on_notes": part.get("used_instrument_ids", []),
                       "harmony_count": part.get("harmony_count", 0),
                       "frame_count": part.get("frame_count", 0),
                       "declarations": declarations,
                       "tab_only": any(item.get("sign") == "TAB" for item in part.get("clefs", []))
                           and not any(item.get("sign") not in {"TAB", "none"} for item in part.get("clefs", []))})
    return result


def _matches(group: dict, track: dict, roles: list[dict]) -> tuple[list[dict], str]:
    names = {_name(item) for item in track["names"] if item.strip()}
    by_name = [role for role in roles if names & {_name(item) for item in role["labels"] if item.strip()}]
    by_channel = [role for role in roles if any(item.get("channel_1based") == group["channel_1based"]
                    and item["port"] == group["port"] for item in role["declarations"])]
    overlap = [role for role in by_name if role in by_channel]
    if overlap:
        return overlap, "exact_track_name_and_MXL_channel"
    if by_name:
        return by_name, "exact_track_name"
    if by_channel:
        return by_channel, "MXL_port_and_channel"
    kinds = {kind for name in track["names"] if (kind := kind_from_label(name))}
    by_kind = [role for role in roles if kinds and kinds.intersection(role["kinds"])]
    if len(by_kind) == 1:
        return by_kind, "unique_named_instrument_role"
    return [], "no_corresponding_notation_role"


def _program_explanation(group: dict, roles: list[dict], basis: str) -> tuple[str, str]:
    program = group["program_0based"]
    expected = {item.get("program_0based") for role in roles for item in role["declarations"]}
    kinds = {kind for role in roles for kind in role["kinds"]}
    if not roles:
        return "unresolved_conflict", "sounding_MIDI_group_has_no_corresponding_MXL_role"
    if program in expected:
        return "consistent", "sounding_program_matches_MXL_declaration"
    if group["channel_1based"] == 10 and "percussion" in kinds:
        return "explained_playback_difference", "percussion_channel_program_is_not_a_pitched_instrument"
    if program == 0 and group["default_program_note_count"] == group["note_on_count"]:
        return "explained_playback_difference", "default_program_on_corresponding_named_notation_role"
    if kinds.intersection({"guitar", "electric_guitar", "bass_guitar", "lute", "mandolin", "ukulele", "cobza"}) and program in range(24, 32):
        return "explained_playback_difference", "guitar_family_articulation_or_sound_substitution_on_same_notated_role"
    if kinds.intersection({"violin", "viola", "cello", "double_bass", "dan_nhi"}) and program in {40, 41, 42, 43, 44, 45, 48, 49}:
        return "explained_playback_difference", "string_articulation_or_ensemble_patch_on_same_notated_role"
    if "double_bass" in kinds and program in {32, 33, 34}:
        return "explained_playback_difference", "double_bass_plucked_playback_patch_on_same_notated_role"
    if kinds.intersection({"trumpet", "flugelhorn", "horn", "trombone", "tuba"}) and program in range(56, 64):
        return "explained_playback_difference", "brass_mute_or_sound_substitution_on_same_notated_role"
    if "harp" in kinds and program in {45, 46, 47}:
        return "explained_playback_difference", "harp_plucked_or_harmonic_playback_patch_on_same_notated_role"
    if "percussion" in kinds and program in {8, 9, 10, 11, 12, 13, 14, 15, 48}:
        return "explained_playback_difference", "pitched_percussion_sound_substitution_on_same_notated_role"
    return "unresolved_conflict", "sounding_program_differs_from_notation_without_an_explained_articulation"


def crosscheck(mxl: dict, midi: dict, *, ports: dict | None = None, source_instrumentation: str = "") -> dict:
    roles = mxl_roles(mxl, ports)
    groups, mentioned = [], set()
    explanations, conflicts = [], []
    for role in roles:
        if role["ambiguous_missing_note_instrument_ids"]:
            conflicts.append({"part_id": role["part_id"], "name": role["name"],
                              "reason": "multiple_score_instruments_have_unassigned_notated_notes"})
    track_roles = defaultdict(set)
    for group in midi["sounding_groups"]:
        matches, _ = _matches(group, midi["tracks"][group["track"]], roles)
        track_roles[group["track"]].update(role["part_id"] for role in matches)
    for group in midi["sounding_groups"]:
        track = midi["tracks"][group["track"]]
        matches, basis = _matches(group, track, roles)
        if not matches and len(track_roles[group["track"]]) == 1:
            same_track = [role for role in roles if role["part_id"] in track_roles[group["track"]]]
            if "percussion" in same_track[0]["kinds"]:
                matches, basis = same_track, "same_track_as_corresponding_notated_percussion_role"
        status, reason = _program_explanation(group, matches, basis)
        if status == "unresolved_conflict" and matches:
            if (group["program_0based"] == 0 and all("guitar" in role["kinds"] for role in matches)
                    and any(role["harmony_count"] or role["frame_count"] for role in matches)
                    and any(other["track"] == group["track"] and other["program_0based"] in {24, 25}
                            for other in midi["sounding_groups"])):
                status, reason = "explained_playback_difference", "MXL_harmony_symbols_add_default_sound_chord_playback_on_same_guitar_track"
            else:
                origins = group.get("program_origins", [])
                origin_roles = set()
                for origin in origins:
                    if origin["track"] == group["track"]:
                        break
                    source_matches, _ = _matches(group, midi["tracks"][origin["track"]], roles)
                    if not source_matches or {role["part_id"] for role in source_matches} & {role["part_id"] for role in matches}:
                        break
                    origin_status, _ = _program_explanation(group, source_matches, "program_origin_track")
                    if (origin_status == "unresolved_conflict" and group["program_0based"] == 0
                            and any(role["harmony_count"] or role["frame_count"] for role in source_matches)):
                        origin_status = "explained_playback_difference"
                    if origin_status == "unresolved_conflict":
                        break
                    origin_roles.update(role["part_id"] for role in source_matches)
                else:
                    if origins and origin_roles:
                        status, reason = "explained_playback_difference", "program_from_other_named_track_reuses_same_port_and_channel"
        ids = [role["part_id"] for role in matches]
        mentioned.update(ids)
        item = {**group, "track_names": track["names"], "MXL_part_ids": ids, "matching_basis": basis,
                "program_origin_tracks": [{**origin, "track_names": midi["tracks"][origin["track"]]["names"]}
                                           for origin in group.get("program_origins", [])],
                "MXL_programs": sorted({entry["program_0based"] for role in matches
                    for entry in role["declarations"] if entry.get("program_0based") is not None}),
                "status": status, "reason": reason}
        groups.append(item)
        if status == "unresolved_conflict":
            conflicts.append(item)
        elif status == "explained_playback_difference":
            explanations.append(reason)
    silent = []
    for role in roles:
        if role["part_id"] not in mentioned:
            names = {_name(value) for value in role["labels"] if value.strip()}
            silent_tracks = [track["index"] for track in midi["tracks"] if not track["note_on_count"]
                             and names & {_name(value) for value in track["names"] if value.strip()}]
            reason = ("empty_notation_part_without_sounding_MIDI" if not role["note_count"] else
                      "notated_part_is_silent_in_corresponding_MIDI_track" if silent_tracks else
                      "notated_part_has_no_separate_sounding_MIDI_group")
            item = {"part_id": role["part_id"], "name": role["name"], "notated_notes": role["note_count"],
                    "matching_silent_track_indices": silent_tracks, "reason": reason}
            silent.append(item)
            if role["note_count"] and not silent_tracks and not role["tab_only"]:
                conflicts.append(item)
            else:
                explanations.append(reason)
    active_programs = {group["program_0based"] for group in midi["sounding_groups"]}
    declared_programs = {item["program_0based"] for track in midi["tracks"] for item in track["declared_programs"]}
    inactive = sorted(declared_programs - active_programs)
    if inactive:
        explanations.append("declared_MIDI_programs_without_any_note_on_do_not_add_instruments")
    scope_names = []
    for role in roles:
        flags = sorted(set(role["kinds"]) & {"voice", "electric_guitar", "bass_guitar", "synthesizer"})
        if flags:
            scope_names.append({"part_id": role["part_id"], "name": role["name"], "named_instruments": flags,
                                "source_instrumentation": source_instrumentation,
                                "notated_notes": role["note_count"],
                                "MIDI_note_on_count": sum(group["note_on_count"] for group in groups if role["part_id"] in group["MXL_part_ids"])})
    if midi["cross_track_same_tick_program_order"]:
        explanations.append("same_tick_across_track_program_order_is_explicitly_recorded_not_a_player_count")
    return {"status": "unresolved_conflict" if conflicts else "explained_playback_difference" if explanations else "consistent",
            "sounding_groups": groups, "MXL_roles": roles, "silent_notation_roles": silent,
            "inactive_MIDI_programs": inactive, "named_scope_exceptions": scope_names,
            "explanations": sorted(set(explanations)), "conflicts": conflicts,
            "cross_track_same_tick_program_order": midi["cross_track_same_tick_program_order"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    root = args.root.resolve()
    method_bytes = Path(__file__).read_bytes()
    label_method_bytes = Path(label_methods.__file__).read_bytes()
    catalog_path = root / "sources/musescore/catalog.json"
    raw = catalog_path.read_bytes()
    catalog = json.loads(raw)
    evidence_path = root / "sources/musescore/verification/instrumentation-mxl-midi.json"
    evidence_bytes = evidence_path.read_bytes()
    evidence = json.loads(evidence_bytes)
    digest = hashlib.sha256(raw).hexdigest()
    if evidence.get("status") != "complete" or evidence.get("catalog_sha256") != digest:
        raise ValueError("complete current MXL/MIDI evidence is required")
    natives = {work["id"]: work for work in catalog["works"]}
    rows = {row["id"]: row for row in evidence["records"]}
    if len(rows) != len(evidence["records"]) or set(rows) != set(natives):
        raise ValueError("file evidence must cover each native record exactly once")
    results = []
    for identity, native in natives.items():
        row = rows[identity]
        if row["title"] != native["title_en"] or row["source_url"] != native["source_url"]:
            raise ValueError("native identity evidence changed")
        guards, paths = {}, {}
        for label in ("MUSICXML", "MIDI"):
            assets = [asset for asset in native["assets"] if asset["format"] == label and asset["status"] == "verified"]
            if len(assets) != 1:
                raise ValueError("exactly one verified asset of each format is required")
            asset, previous = assets[0], row["evidence"][label]
            relative = Path(asset["local_path"])
            path = root / relative
            if relative.is_absolute() or ".." in relative.parts or not path.resolve().is_relative_to(root):
                raise ValueError("unsafe score evidence path")
            content = path.read_bytes()
            actual_sha = hashlib.sha256(content).hexdigest()
            if (actual_sha != asset["sha256"] or actual_sha != previous["file_sha256"]
                    or len(content) != asset["size"] or len(content) != previous["file_bytes"]):
                raise ValueError("actual score bytes no longer match the evidence")
            guards[label] = {"sha256": actual_sha, "size": len(content)}
            paths[label] = path
        midi = read_sounding_midi(paths["MIDI"])
        if sum(item["note_on_count"] for item in midi["sounding_groups"]) != sum(
                track["note_on_count"] for track in row["evidence"]["MIDI"]["tracks"]):
            raise ValueError("independent MIDI parsers disagree on sounding note-on coverage")
        mxl = row["evidence"]["MUSICXML"]
        result = crosscheck(mxl, midi, ports=_mxl_ports(paths["MUSICXML"], mxl),
                            source_instrumentation=native["metadata"].get("instrumentation", ""))
        result.update(id=identity, title_en=native["title_en"], source_url=native["source_url"], assets=guards,
                      MIDI_structural_validation=midi["validation"],
                      MIDI_note_pairing_issues=row["evidence"]["MIDI"].get("note_pairing_issues", []))
        results.append(result)
    if (Path(__file__).read_bytes() != method_bytes
            or Path(label_methods.__file__).read_bytes() != label_method_bytes):
        raise ValueError("crosscheck or naming methods changed during the audit; rerun against stable inputs")
    output = {"schema_version": 1, "source_id": "musescore", "status": "complete",
              "catalog_sha256": digest, "MXL_MIDI_evidence_sha256": hashlib.sha256(evidence_bytes).hexdigest(),
              "method_sha256": hashlib.sha256(method_bytes).hexdigest(),
              "instrument_name_method_sha256": hashlib.sha256(label_method_bytes).hexdigest(),
              "works": results, "summary": {"records": len(results),
              "statuses": dict(Counter(row["status"] for row in results)),
              "explanations": dict(Counter(reason for row in results for reason in row["explanations"])),
              "unresolved_ids": [row["id"] for row in results if row["status"] == "unresolved_conflict"],
              "named_scope_exception_ids": [row["id"] for row in results if row["named_scope_exceptions"]]},
              "limits": ["Instrument names and MusicXML notation establish written roles; MIDI programs are playback evidence.",
                         "Track, channel, staff and voice counts do not establish performer counts.",
                         "Note pairing warnings concern playback semantics and do not invalidate structurally verified MIDI.",
                         "No note-by-note fidelity or acoustic rendering claim is made."]}
    target = root / "sources/musescore/verification/instrumentation-midi-crosscheck.json"
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(output["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
