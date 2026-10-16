"""Bounded notation/MIDI attack matching for exact reviewed playback defects.

This deliberately handles pitched notation without chords or grace notes, with
ordinary two-pass repeats, first/second endings, ties and plain trills. It fails
closed for unsupported notation. It never identifies an instrument or changes
files, and does not certify durations, expression, timbre or acoustic fidelity.
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import json
from pathlib import Path
import struct
import zipfile

from score_midi_crosscheck import _vlq
from source_adapters.pdmx_formats import _xml, validate_source_format


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def repeat_order(measures):
    """Expand disjoint explicit two-pass repeats; reject ambiguous navigation."""
    order, start, ending = [], None, None
    expected_second, second_open = None, False
    repeat_sections = []
    for index, measure in enumerate(measures):
        require(not measure.findall('.//measure-repeat') and not measure.findall('.//beat-repeat')
                and not measure.findall('.//direction-type/segno') and not measure.findall('.//direction-type/coda'),
                'unsupported written playback navigation')
        for sound in measure.findall(".//sound"):
            require(not set(sound.attrib) & {"dacapo", "dalsegno", "tocoda", "fine", "segno", "coda"},
                    "unsupported playback jump")
        for bar in measure.findall("barline"):
            require(len(bar.findall('repeat')) <= 1 and len(bar.findall('ending')) <= 1,
                    'multiple repeat or ending directives on one barline')
            forward = bar.find("repeat")
            if forward is not None:
                require(forward.get("direction") in {"forward", "backward"}, "unsupported repeat direction")
            if forward is not None and forward.get("direction") == "forward":
                require(start is None and not second_open and expected_second is None
                        and bar.get("location", "right") == "left", "nested or misplaced repeat")
                start = index
            for mark in bar.findall("ending"):
                require(mark.get("number") in {"1", "2"}, "unsupported ending number")
                require(mark.get('type') in {'start', 'stop', 'discontinue'}, 'unsupported ending type')
                if mark.get("number") == "1" and mark.get("type") == "start":
                    require(start is not None and ending is None and not second_open
                            and bar.get("location") == "left",
                            "unbound first ending")
                    ending = index
                elif mark.get('number') == '1':
                    require(mark.get('type') == 'stop' and ending is not None
                            and bar.get('location', 'right') == 'right'
                            and forward is not None and forward.get('direction') == 'backward',
                            'unbound first ending closure')
                elif mark.get('type') == 'start':
                    require(expected_second == index and start is None and not second_open
                            and bar.get('location') == 'left', 'unbound second ending')
                    expected_second, second_open = None, True
                else:
                    require(second_open and bar.get('location', 'right') == 'right',
                            'unbound second ending closure')
                    second_open = False
        require(expected_second != index, 'second ending missing at the expected measure')
        order.append(index)
        for bar in measure.findall("barline"):
            backward = bar.find("repeat")
            if backward is None or backward.get("direction") != "backward":
                continue
            require(start is not None and bar.get("location", "right") == "right"
                    and backward.get("times", "2") == "2", "unsupported backward repeat")
            if ending is not None:
                require(any(mark.get("number") == "1" and mark.get("type") == "stop"
                            for mark in bar.findall("ending")), "first ending does not close at repeat")
                require(index + 1 < len(measures) and any(mark.get("number") == "2" and mark.get("type") == "start"
                    for mark in measures[index + 1].findall("barline/ending")), "second ending missing")
                expected_second = index + 1
            stop = ending if ending is not None else index + 1
            require(stop > start, "empty repeated body")
            order.extend(range(start, stop))
            repeat_sections.append({"start_measure_index": start, "backward_measure_index": index,
                                    "first_ending_index": ending, "second_pass_indices": list(range(start, stop))})
            start = ending = None
    require(start is None and ending is None and expected_second is None and not second_open,
            "unclosed repeat or ending")
    return order, repeat_sections


def _midi_attacks(path, track_index):
    validation = validate_source_format(path, "MIDI")
    data = Path(path).read_bytes()
    midi_format, count, division = struct.unpack(">HHH", data[8:14])
    require(midi_format in (0, 1) and division and division < 32768 and 0 <= track_index < count,
            "unsupported MIDI timeline")
    offset = 8 + int.from_bytes(data[4:8], "big")
    for index in range(count):
        length = int.from_bytes(data[offset + 4:offset + 8], "big")
        chunk = data[offset + 8:offset + 8 + length]
        offset += 8 + length
        if index != track_index:
            continue
        position = tick = port = 0
        running, names, attacks = None, [], []
        while position < len(chunk):
            delta, position = _vlq(chunk, position)
            tick += delta
            status = chunk[position]
            if status >= 128:
                position += 1
            else:
                require(running is not None, "missing MIDI running status")
                status = running
            if status == 255:
                kind = chunk[position]
                size, position = _vlq(chunk, position + 1)
                payload = chunk[position:position + size]
                position += size
                if kind == 3:
                    names.append(payload.decode("utf-8", "strict").rstrip("\x00"))
                if kind == 33:
                    port = payload[0]
                continue
            if status in (240, 247):
                size, position = _vlq(chunk, position)
                position += size
                continue
            running = status
            kind = status >> 4
            count_bytes = 1 if kind in (12, 13) else 2
            payload = chunk[position:position + count_bytes]
            position += count_bytes
            if kind == 9 and payload[1]:
                attacks.append({"tick": tick, "pitch": payload[0], "channel_1based": (status & 15) + 1, "port": port})
        return division, names, attacks, validation
    raise ValueError("missing target MIDI track")


def match_pitched_attacks(mxl_path, midi_path, *, part_id, track_index, track_name):
    """Match every target attack, permitting alternation only at printed trills."""
    validation = validate_source_format(mxl_path, "MUSICXML")
    with zipfile.ZipFile(mxl_path) as archive:
        root = _xml(archive.read(validation["score_member"]), "bounded playback correspondence")
    for node in root.iter():
        node.tag = node.tag.rsplit("}", 1)[-1]
    parts = [part for part in root.findall("part") if part.get("id") == part_id]
    require(len(parts) == 1, "missing or ambiguous target part")
    measures = parts[0].findall("measure")
    require(measures and len(measures) <= 10000, "unbounded target notation")
    order, repeats = repeat_order(measures)
    division, names, attacks, midi_validation = _midi_attacks(midi_path, track_index)
    require(names == [track_name], "target MIDI track name differs")
    require(len({(row["channel_1based"], row["port"]) for row in attacks}) == 1,
            "target track uses multiple channels or ports")
    require(all(not part.findall(".//transpose") for part in parts), "transposing notation unsupported")
    state_divisions, fifths, numbered_key = None, 0, False
    templates = []
    steps = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    for measure in measures:
        require(len(measure.findall('attributes')) <= 1, 'multiple attribute changes unsupported')
        attributes = measure.find("attributes")
        if attributes is not None:
            require(not any(item.tag in {'note', 'backup', 'forward'}
                            for item in list(measure)[:list(measure).index(attributes)]),
                    'mid-measure attribute changes unsupported')
        if attributes is not None:
            value = attributes.findtext("divisions")
            if value is not None:
                state_divisions = int(value)
            key = attributes.findtext("key/fifths")
            require(len(attributes.findall('key')) <= 1 and all(
                node.tag in {'fifths', 'mode', 'cancel'} for node in attributes.findall('key/*')),
                'nontraditional or multiple key signatures unsupported')
            key_node = attributes.find('key')
            require(key_node is None or key is not None, 'key signature lacks fifths')
            if key_node is not None:
                numbered_key = key_node.get('number') is not None
            if key is not None:
                fifths = int(key)
        require(state_divisions is not None and state_divisions > 0 and -7 <= fifths <= 7,
                "unsupported divisions or key signature")
        cursor, extent, notes, accidentals = Fraction(0), Fraction(0), [], {}
        pitched_roles = {(item.findtext('staff', '1'), item.findtext('voice', '1'))
                         for item in measure.findall('note') if item.find('pitch') is not None}
        if measure.findall('.//ornaments'):
            require(len(pitched_roles) == 1 and not numbered_key, 'multivoice or numbered-key ornament unsupported')
        for item in measure:
            if item.tag in {"backup", "forward"}:
                shift = Fraction(int(item.findtext("duration", "0")), state_divisions)
                require(shift > 0, "missing cursor movement duration")
                cursor += shift if item.tag == "forward" else -shift
                require(cursor >= 0, "cursor moves before measure start")
                extent = max(extent, cursor)
                continue
            if item.tag != "note":
                continue
            require(item.find("grace") is None and item.find("chord") is None
                    and item.findtext("voice", "1").isdigit(), "grace, chord or unnamed voice unsupported")
            duration = Fraction(int(item.findtext("duration", "0")), state_divisions)
            require(duration > 0, "missing positive notation duration")
            pitch = item.find("pitch")
            ornaments = item.find("notations/ornaments")
            ties = [node.get('type') for node in item.findall('tie')]
            visible_ties = [node.get('type') for node in item.findall('notations/tied')]
            require(set(ties) <= {'start', 'stop'} and len(ties) == len(set(ties))
                    and (not visible_ties or set(visible_ties) == set(ties)),
                    'unsupported or inconsistent tie notation')
            if pitch is not None:
                step, octave = pitch.findtext("step"), int(pitch.findtext("octave"))
                alter = Fraction(pitch.findtext("alter", "0"))
                require(step in steps and alter.denominator == 1, "unsupported pitch")
                number = (octave + 1) * 12 + steps[step] + int(alter)
                staff = item.findtext('staff', '1')
                accidentals[(staff, step, octave)] = int(alter)
                trill = ornaments is not None
                upper = None
                if trill:
                    require([node.tag for node in ornaments] == ["trill-mark"] and not ties
                            and not ornaments[0].attrib,
                            "unsupported ornament or tied trill")
                    next_step = "CDEFGAB"[("CDEFGAB".index(step) + 1) % 7]
                    next_octave = octave + (step == 'B')
                    key_alter = (int(next_step in "FCGDAEB"[:max(fifths, 0)])
                                 - int(next_step in "BEADGCF"[:max(-fifths, 0)]))
                    upper = (next_octave + 1) * 12 + steps[next_step]
                    upper += accidentals.get((staff, next_step, next_octave), key_alter)
                notes.append({"offset": cursor, "duration": duration, "pitch": number,
                              "trill": trill, "upper_pitch": upper, 'ties': ties,
                              'voice': item.findtext('voice', '1'), 'staff': item.findtext('staff', '1')})
            else:
                require(item.find("rest") is not None, "unpitched target notation unsupported")
                require(not ties and not visible_ties and ornaments is None, 'rest ties or ornaments unsupported')
            cursor += duration
            extent = max(extent, cursor)
        require(extent > 0, "empty target measure")
        templates.append((extent, notes))
    expected, offset, open_ties = [], Fraction(0), {}
    for measure_index in order:
        duration, notes = templates[measure_index]
        for note in notes:
            tick, stop = (offset + note["offset"]) * division, (offset + note["offset"] + note["duration"]) * division
            require(tick.denominator == stop.denominator == 1, "nonintegral target attack window")
            tie_key = (note['staff'], note['voice'], note['pitch'])
            if 'stop' in note['ties']:
                require(open_ties.get(tie_key) == tick, 'orphaned, interrupted or wrong-pitch tie stop')
                del open_ties[tie_key]
            else:
                require(not any(key[:2] == tie_key[:2] for key in open_ties), 'unclosed tie before another attack')
                expected.append({**note, "tick": int(tick), "stop_tick": int(stop), "measure_index": measure_index})
            if 'start' in note['ties']:
                require(tie_key not in open_ties, 'duplicate open tie')
                open_ties[tie_key] = stop
        offset += duration
    require(not open_ties, 'unclosed target tie')
    used, normal_count, trills = set(), 0, []
    for note in expected:
        if note["trill"]:
            window = [(index, row) for index, row in enumerate(attacks) if note["tick"] <= row["tick"] < note["stop_tick"]]
            require(len(window) >= 2 and window[0][1]["tick"] == note["tick"], "printed trill has no corresponding attacks")
            require(all(row["pitch"] == (note["pitch"] if index % 2 == 0 else note["upper_pitch"])
                        for index, (_, row) in enumerate(window)), "trill pitches do not alternate as written")
            require(all(a[1]["tick"] < b[1]["tick"] for a, b in zip(window, window[1:])), "trill attack times overlap")
            indices = {index for index, _ in window}
            trills.append({"measure_number": measures[note["measure_index"]].get("number"),
                           "tick": note["tick"], "stop_tick": note["stop_tick"],
                           "principal_pitch": note["pitch"], "upper_pitch": note["upper_pitch"],
                           "attacks": [row for _, row in window]})
        else:
            matches = [index for index, row in enumerate(attacks) if row["tick"] == note["tick"] and row["pitch"] == note["pitch"]]
            require(len(matches) == 1, "notation attack lacks one exact MIDI tick/pitch")
            indices = set(matches)
            normal_count += 1
        require(not used & indices, "overlapping notation-to-MIDI attack assignment")
        used.update(indices)
    require(len(used) == len(attacks), "unmatched target MIDI attacks")
    compact_attacks = [[row["tick"], row["pitch"], row["port"], row["channel_1based"]] for row in attacks]
    return {"schema_version": 1, "status": "complete", "part_id": part_id, "track_index": track_index,
            "track_name": track_name, "mxl_sha256": hashlib.sha256(Path(mxl_path).read_bytes()).hexdigest(),
            "midi_sha256": hashlib.sha256(Path(midi_path).read_bytes()).hexdigest(), "ticks_per_quarter": division,
            "written_measures": len(measures), "expanded_measure_indices": order, "repeat_sections": repeats,
            "expanded_notation_attacks_before_ornament_realization": len(expected),
            "normal_attacks_matched": normal_count, "trill_occurrences": trills,
            "midi_attacks_matched": len(attacks), "unmatched_attacks": 0,
            "complete_midi_attack_sequence_sha256": _digest(compact_attacks),
            "boundary": "Exact target attack pitch/onset correspondence with explicit repeats, ties and printed trills; not duration, expression, timbre, other-part or acoustic fidelity certification."}
