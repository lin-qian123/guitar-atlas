import struct
from xml.etree import ElementTree as ET
import zipfile

import pytest

from score_mxl_playback_correspondence import match_pitched_attacks, repeat_order


def vlq(value):
    output = [value & 127]
    while value > 127:
        value >>= 7
        output.insert(0, (value & 127) | 128)
    return bytes(output)


def files(tmp_path, measures, attacks, *, name="Flute", extra_xml=""):
    score = ('<score-partwise version="3.1"><part-list><score-part id="P1">'
             '<part-name>Flute</part-name></score-part></part-list><part id="P1">'
             + measures + '</part></score-partwise>')
    mxl = tmp_path / "score.mxl"
    with zipfile.ZipFile(mxl, "w") as archive:
        archive.writestr("META-INF/container.xml", '<container><rootfiles><rootfile full-path="score.xml" '
                         'media-type="application/vnd.recordare.musicxml+xml"/></rootfiles></container>')
        archive.writestr("score.xml", score)
    track = b"\0\xff\x03" + vlq(len(name.encode())) + name.encode()
    events = []
    for tick, pitch in attacks:
        events.extend([(tick, b"\x90" + bytes([pitch, 80])), (tick + 20, b"\x80" + bytes([pitch, 0]))])
    previous = 0
    for tick, payload in sorted(events, key=lambda event: event[0]):
        track += vlq(tick - previous) + payload
        previous = tick
    track += b"\0\xff\x2f\0"
    midi = tmp_path / "score.mid"
    midi.write_bytes(b"MThd" + struct.pack(">IHHH", 6, 1, 1, 480)
                     + b"MTrk" + struct.pack(">I", len(track)) + track)
    return mxl, midi


ATTR = '<attributes><divisions>1</divisions><key><fifths>0</fifths></key></attributes>'


def note(step="C", extra="", duration=1):
    return f'<note><pitch><step>{step}</step><octave>5</octave></pitch><duration>{duration}</duration>{extra}</note>'


def match(paths):
    return match_pitched_attacks(*paths, part_id="P1", track_index=0, track_name="Flute")


def test_plain_attacks_and_ties_are_matched_without_extra_rearticulation(tmp_path):
    measures = '<measure number="1">' + ATTR + note(extra='<tie type="start"/>') + '</measure>'
    measures += '<measure number="2">' + note(extra='<tie type="stop"/>') + note('D') + '</measure>'
    result = match(files(tmp_path, measures, [(0, 72), (960, 74)]))
    assert result["normal_attacks_matched"] == result["midi_attacks_matched"] == 2
    assert result["unmatched_attacks"] == 0


def test_repeats_and_two_endings_expand_exactly_once(tmp_path):
    measures = '<measure number="1">' + ATTR + '<barline location="left"><repeat direction="forward"/></barline>' + note() + '</measure>'
    measures += '<measure number="2"><barline location="left"><ending number="1" type="start"/></barline>' + note('D')
    measures += '<barline location="right"><ending number="1" type="stop"/><repeat direction="backward"/></barline></measure>'
    measures += '<measure number="3"><barline location="left"><ending number="2" type="start"/></barline>' + note('E')
    measures += '<barline location="right"><ending number="2" type="discontinue"/></barline></measure>'
    result = match(files(tmp_path, measures, [(0, 72), (480, 74), (960, 72), (1440, 76)]))
    assert result["expanded_measure_indices"] == [0, 1, 0, 2]
    assert result["midi_attacks_matched"] == 4


def test_only_printed_trill_window_accepts_alternating_extra_attacks(tmp_path):
    measures = '<measure number="1">' + ATTR + note(extra='<notations><ornaments><trill-mark/></ornaments></notations>') + note('E') + '</measure>'
    result = match(files(tmp_path, measures, [(0, 72), (120, 74), (240, 72), (360, 74), (480, 76)]))
    assert result["expanded_notation_attacks_before_ornament_realization"] == 2
    assert result["midi_attacks_matched"] == 5
    assert len(result["trill_occurrences"]) == 1


@pytest.mark.parametrize("attacks", [[(0, 73)], [(1, 72)], [(0, 72), (120, 72)]])
def test_wrong_pitch_wrong_tick_or_unwritten_extra_attack_fails(tmp_path, attacks):
    measures = '<measure number="1">' + ATTR + note() + '</measure>'
    with pytest.raises(ValueError):
        match(files(tmp_path, measures, attacks))


@pytest.mark.parametrize("attacks", [[(0, 72), (120, 76)], [(0, 72), (120, 72)], [(0, 72)]])
def test_unexplained_trill_pitch_or_absent_realization_fails(tmp_path, attacks):
    measures = '<measure number="1">' + ATTR + note(extra='<notations><ornaments><trill-mark/></ornaments></notations>') + '</measure>'
    with pytest.raises(ValueError):
        match(files(tmp_path, measures, attacks))


@pytest.mark.parametrize("extra", ['<grace/>', '<chord/>', '<notations><ornaments><turn/></ornaments></notations>'])
def test_unsupported_notation_never_silently_qualifies(tmp_path, extra):
    with pytest.raises(ValueError):
        match(files(tmp_path, '<measure number="1">' + ATTR + note(extra=extra) + '</measure>', [(0, 72)]))


def test_track_name_is_literal_and_guarded(tmp_path):
    with pytest.raises(ValueError, match="track name"):
        match(files(tmp_path, '<measure number="1">' + ATTR + note() + '</measure>', [(0, 72)], name="flute"))


@pytest.mark.parametrize('notes,attacks', [
    (note() + note('D', '<tie type="stop"/>'), [(0, 72)]),
    (note(extra='<tie type="start"/>') + note('D', '<tie type="stop"/>'), [(0, 72)]),
    (note(extra='<tie type="start"/><voice>1</voice>') + note(extra='<tie type="stop"/><voice>2</voice>'), [(0, 72)]),
    (note(extra='<tie type="start"/>') + '<note><rest/><duration>1</duration></note>'
        + note(extra='<tie type="stop"/>'), [(0, 72)]),
    (note(extra='<tie type="start"/>'), [(0, 72)]),
    (note(extra='<notations><tied type="stop"/></notations>'), [(0, 72)]),
])
def test_tie_labels_cannot_hide_unmatched_notes_without_a_complete_chain(tmp_path, notes, attacks):
    with pytest.raises(ValueError, match='tie'):
        match(files(tmp_path, '<measure number="1">' + ATTR + notes + '</measure>', attacks))


def test_complete_three_segment_tie_chain_has_exactly_one_attack(tmp_path):
    measures = '<measure number="1">' + ATTR + note(extra='<tie type="start"/>') + '</measure>'
    measures += '<measure number="2">' + note(extra='<tie type="stop"/><tie type="start"/>') + '</measure>'
    measures += '<measure number="3">' + note(extra='<tie type="stop"/>') + note('D') + '</measure>'
    proof = match(files(tmp_path, measures, [(0, 72), (1440, 74)]))
    assert proof['normal_attacks_matched'] == 2


def test_printed_trill_respects_the_same_measure_upper_note_accidental(tmp_path):
    upper = note('F').replace('<step>F</step>', '<step>F</step><alter>1</alter>')
    trill = note('E', '<notations><ornaments><trill-mark/></ornaments></notations>')
    measures = '<measure number="1">' + ATTR + upper + trill + '</measure>'
    proof = match(files(tmp_path, measures, [(0, 78), (480, 76), (600, 78), (720, 76)]))
    assert proof['trill_occurrences'][0]['upper_pitch'] == 78
    with pytest.raises(ValueError, match='trill pitches'):
        match(files(tmp_path, measures, [(0, 78), (480, 76), (600, 77), (720, 76)]))


@pytest.mark.parametrize('body', [
    note() + ATTR + note('D'),
    ATTR + ATTR + note(),
])
def test_unhandled_mid_measure_or_multiple_attribute_changes_fail(tmp_path, body):
    with pytest.raises(ValueError, match='attribute changes'):
        match(files(tmp_path, '<measure number="1">' + body + '</measure>', [(0, 72)]))


def test_numbered_key_scope_remains_guarded_in_later_ornament_measures(tmp_path):
    measures = '<measure number="1">' + ATTR.replace('<key>', '<key number="1">') + note() + '</measure>'
    measures += '<measure number="2">' + note('E', '<notations><ornaments><trill-mark/></ornaments></notations>') + '</measure>'
    with pytest.raises(ValueError, match='numbered-key ornament'):
        match(files(tmp_path, measures, [(0, 72), (480, 76), (600, 77)]))


def test_rest_voice_and_cursor_rewind_do_not_add_performers_or_shift_attacks(tmp_path):
    measures = '<measure number="1">' + ATTR + '<note><rest/><duration>2</duration><voice>1</voice></note>'
    measures += '<backup><duration>2</duration></backup>' + note(extra='<voice>2</voice>') + '<forward><duration>1</duration></forward></measure>'
    result = match(files(tmp_path, measures, [(0, 72)]))
    assert result["midi_attacks_matched"] == 1


@pytest.mark.parametrize("measure", [
    '<measure><barline location="right"><repeat direction="backward"/></barline></measure>',
    '<measure><direction><sound dacapo="yes"/></direction></measure>',
    '<measure><barline location="left"><ending number="3" type="start"/></barline></measure>',
    '<measure><barline location="left"><ending number="2" type="start"/></barline></measure>',
    '<measure><barline location="right"><ending number="1" type="stop"/></barline></measure>',
    '<measure><barline location="right"><ending number="2" type="discontinue"/></barline></measure>',
    '<measure><barline location="left"><ending number="1" type="continue"/></barline></measure>',
    '<measure><attributes><measure-style><measure-repeat type="start">2</measure-repeat></measure-style></attributes></measure>',
])
def test_ambiguous_or_unsupported_repeat_navigation_fails(measure):
    with pytest.raises(ValueError):
        repeat_order([ET.fromstring(measure)])
