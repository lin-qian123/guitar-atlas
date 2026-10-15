"""File evidence must retain notation and playback facts without assigning performers."""
import hashlib
import io
import json
import struct
import zipfile

import pytest

from score_instrumentation import read_midi_evidence, read_mxl_evidence


def mxl(tmp_path, parts, declared, *, groups='', root='score-partwise'):
    body = f'<{root} version="4.0"><part-list>{groups}{declared}</part-list>{parts}</{root}>'
    target = tmp_path / 'score.mxl'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('META-INF/container.xml', '<container><rootfiles><rootfile full-path="score.xml"/></rootfiles></container>')
        archive.writestr('score.xml', body)
    return target


def declared(identity='P1', name='Guitar', extra=''):
    return f'<score-part id="{identity}"><part-name>{name}</part-name><part-abbreviation>Gtr.</part-abbreviation>{extra}</score-part>'


def note(pitch='C', *, octave=4, duration=4, staff=1, extra=''):
    return f'<note>{extra}<pitch><step>{pitch}</step><octave>{octave}</octave></pitch><duration>{duration}</duration><staff>{staff}</staff></note>'


def test_tab_and_standard_staves_stay_in_one_part_with_all_instrument_names(tmp_path):
    attrs = '''<attributes><divisions>4</divisions><staves>2</staves><clef number="1"><sign>G</sign><line>2</line><clef-octave-change>-1</clef-octave-change></clef><clef number="2"><sign>TAB</sign><line>5</line></clef><staff-details number="2"><staff-type>tablature</staff-type><staff-lines>6</staff-lines><staff-tuning line="1"><tuning-step>E</tuning-step><tuning-octave>2</tuning-octave></staff-tuning></staff-details></attributes>'''
    d = declared(extra='<score-instrument id="I1"><instrument-name>Classical Guitar</instrument-name><instrument-abbreviation>Gtr.</instrument-abbreviation></score-instrument><midi-instrument id="I1"><midi-channel>1</midi-channel><midi-program>25</midi-program></midi-instrument>')
    p = mxl(tmp_path, f'<part id="P1"><measure number="1">{attrs}{note(extra="<instrument id=\"I1\"/>")}<backup><duration>4</duration></backup>{note(staff=2)}</measure></part>', d)
    before = p.read_bytes()
    result = read_mxl_evidence(p)
    assert result['file_sha256'] == hashlib.sha256(before).hexdigest()
    assert p.read_bytes() == before and 'player_count' not in result
    assert len(result['parts']) == 1
    part = result['parts'][0]
    assert part['name'] == 'Guitar' and part['abbreviation'] == 'Gtr.'
    assert part['score_instruments'][0]['name'] == 'Classical Guitar'
    assert part['midi_instruments'][0]['program_0based'] == 24
    assert part['staves_max'] == 2 and part['note_count'] == 2
    assert part['clefs'][1]['sign'] == 'TAB' and part['staff_details'][0]['tunings'][0]['step'] == 'E'
    assert part['used_instrument_ids'] == ['I1']
    assert part['staff_note_summaries'][0]['normalized_notes_sha256'] == part['staff_note_summaries'][1]['normalized_notes_sha256']
    assert result['validation']['external_dtd_fetched'] is False


def test_note_normalization_handles_divisions_chord_backup_forward_and_transpose(tmp_path):
    attrs = '<attributes><divisions>4</divisions><transpose><diatonic>0</diatonic><chromatic>0</chromatic><octave-change>-1</octave-change></transpose></attributes>'
    content = attrs + note() + note('E', extra='<chord/>') + '<forward><duration>4</duration></forward>' + note('G')
    p = mxl(tmp_path, f'<part id="P1"><measure number="1">{content}</measure><measure number="2"><attributes><divisions>8</divisions></attributes>{note(duration=8)}</measure></part>', declared())
    part = read_mxl_evidence(p)['parts'][0]
    assert part['normalized_notes_preview'] == [[0, '0', '1', 48], [0, '0', '1', 52], [0, '2', '1', 55], [1, '0', '1', 48]]
    assert part['normalization_status'] == 'complete'
    assert part['transpose_changes'][0]['octave_change'] == -1


def test_empty_parts_and_raw_part_groups_are_retained(tmp_path):
    d = '<part-group number="1" type="start"><group-name>Guitars</group-name><group-symbol>bracket</group-symbol></part-group>' + declared('P1') + declared('P2', 'Cello') + '<part-group number="1" type="stop"/>'
    p = mxl(tmp_path, '<part id="P1"><measure number="1"><attributes><divisions>1</divisions></attributes>' + note(duration=1) + '</measure></part><part id="P2"><measure number="1"><note><rest measure="yes"/><duration>4</duration></note></measure></part>', d)
    result = read_mxl_evidence(p)
    assert result['part_groups'][0]['member_part_ids'] == ['P1', 'P2']
    assert result['parts'][1]['rest_count'] == 1 and result['parts'][1]['note_count'] == 0
    assert result['parts'][1]['name'] == 'Cello'
    assert 'player_count' not in json.dumps(result)


def test_timewise_input_and_missing_duration_or_microtones_report_limits(tmp_path):
    content = '<note><pitch><step>C</step><alter>0.5</alter><octave>4</octave></pitch><type>quarter</type></note>'
    p = mxl(tmp_path, f'<measure number="1"><part id="P1">{content}</part></measure>', declared(), root='score-timewise')
    part = read_mxl_evidence(p)['parts'][0]
    assert part['note_count'] == 1 and part['normalization_status'] == 'partial'
    assert 'missing_or_invalid_note_duration' in part['normalization_issues']
    assert 'non_integral_pitch_or_transposition' in part['normalization_issues']


def test_invalid_mxl_and_xml_entity_fail_before_evidence(tmp_path):
    p = mxl(tmp_path, '<part id="P1"><measure number="1"/></part>', declared())
    p.write_bytes(b'not zip')
    with pytest.raises(ValueError):
        read_mxl_evidence(p)


def vlq(number):
    values = [number & 0x7f]
    while number >> 7:
        number >>= 7
        values.insert(0, (number & 0x7f) | 0x80)
    return bytes(values)


def midi(tmp_path, tracks, fmt=1):
    p = tmp_path / 'score.mid'
    p.write_bytes(b'MThd' + struct.pack('>IHHH', 6, fmt, len(tracks), 480) + b''.join(b'MTrk' + struct.pack('>I', len(t)) + t for t in tracks))
    return p


def test_midi_names_programs_percussion_and_running_status_are_file_evidence(tmp_path):
    named = b'\x00\xff\x03\x06Guitar\x00\xc0\x18\x00\x90\x3c\x40' + vlq(480) + b'\x3c\x00\x00\xff\x2f\x00'
    drum = b'\x00\x99\x24\x40' + vlq(240) + b'\x89\x24\x00\x00\xff\x2f\x00'
    p = midi(tmp_path, [named, drum])
    before = p.read_bytes()
    result = read_midi_evidence(p)
    assert result['file_sha256'] == hashlib.sha256(before).hexdigest() and p.read_bytes() == before
    assert result['tracks'][0]['track_names'] == ['Guitar']
    assert result['tracks'][0]['program_changes'] == [{'tick': 0, 'channel_1based': 1, 'program_0based': 24}]
    assert result['tracks'][0]['note_on_count'] == result['tracks'][0]['note_off_count'] == 1
    assert result['channels'][0]['normalized_notes_preview'] == [['0', '1', 60]]
    assert result['channels'][1]['percussion_channel'] is True
    assert result['channels'][0]['note_count'] == 1
    assert result['note_pairing_status'] == 'complete' and 'player_count' not in result


def test_midi_channel_pairing_crosses_track_boundary_but_never_counts_players(tmp_path):
    p = midi(tmp_path, [b'\x00\x90\x3c\x40\x00\xff\x2f\x00', vlq(480) + b'\x80\x3c\x00\x00\xff\x2f\x00'])
    result = read_midi_evidence(p)
    assert result['channels'][0]['normalized_notes_preview'] == [['0', '1', 60]]
    assert result['channels'][0]['source_track_indices'] == [0, 1]
    assert result['note_pairing_status'] == 'complete'


def test_midi_unmatched_and_overlapping_repeated_notes_are_explicitly_ambiguous(tmp_path):
    body = b'\x00\x90\x3c\x40\x00\x90\x3c\x40' + vlq(480) + b'\x80\x3c\x00\x00\xff\x2f\x00'
    result = read_midi_evidence(midi(tmp_path, [body]))
    assert result['note_pairing_status'] == 'partial'
    assert 'overlapping_same_channel_pitch' in result['note_pairing_issues']
    assert result['unmatched_note_on_count'] == 1


def test_midi_format_two_does_not_merge_independent_patterns(tmp_path):
    track = b'\x00\x90\x3c\x40' + vlq(480) + b'\x80\x3c\x00\x00\xff\x2f\x00'
    result = read_midi_evidence(midi(tmp_path, [track, track], fmt=2))
    assert result['timeline_mode'] == 'independent_tracks'
    assert len(result['channels']) == 2
    assert [r['pattern_track_index'] for r in result['channels']] == [0, 1]


def test_zero_duration_midi_preserves_same_tick_event_order(tmp_path):
    body = b'\x00\x90\x3c\x40\x00\x80\x3c\x00\x00\xff\x2f\x00'
    result = read_midi_evidence(midi(tmp_path, [body]))
    assert result['note_pairing_status'] == 'complete'
    assert result['channels'][0]['note_duration_ticks']['minimum'] == 0


def test_tab_full_signature_includes_grace_notes_that_ordinary_summary_omits(tmp_path):
    from score_instrumentation import read_mxl_view_sequences
    p = mxl(tmp_path, '<part id="P1"><measure number="1"><attributes><divisions>4</divisions></attributes>' + note('D', extra='<grace/>') + note() + '</measure></part><part id="P2"><measure number="1"><attributes><divisions>4</divisions><clef><sign>TAB</sign></clef></attributes>' + note() + '</measure></part>', declared('P1')+declared('P2'))
    views = read_mxl_view_sequences(p)
    assert views['parts'][0]['event_count'] == 2
    assert views['parts'][0]['signature_sha256'] != views['parts'][1]['signature_sha256']


def test_full_view_sequences_compare_all_rational_events_and_constant_octave_shift(tmp_path):
    from score_instrumentation import compare_view_sequences, read_mxl_view_sequences
    p = mxl(tmp_path, '<part id="P1"><measure number="1"><attributes><divisions>4</divisions></attributes>' + note() + '</measure></part><part id="P2"><measure number="1"><attributes><divisions>8</divisions><clef><sign>TAB</sign></clef></attributes>' + note(octave=3,duration=8) + '</measure></part>', declared('P1')+declared('P2'))
    a,b=read_mxl_view_sequences(p)['parts']
    comparison=compare_view_sequences(a,b)
    assert comparison['kind']=='constant_octave_offset'
    assert comparison['left_minus_right_semitones']==12
    assert comparison['all_events_correspond'] is True


def test_chord_symbol_accompaniment_is_preserved_despite_no_pitched_notes(tmp_path):
    content = '<attributes><divisions>1</divisions><measure-style><slash type="start" use-stems="no"/></measure-style></attributes><harmony><root><root-step>C</root-step></root><kind text="maj7">major-seventh</kind><bass><bass-step>E</bass-step></bass><offset>1</offset><frame><frame-strings>6</frame-strings><frame-frets>5</frame-frets><frame-note><string>1</string><fret>0</fret></frame-note></frame></harmony><note><rest/><duration>4</duration></note>'
    p=mxl(tmp_path,f'<part id="P1"><measure number="1">{content}</measure></part>',declared())
    part=read_mxl_evidence(p)['parts'][0]
    assert part['note_count']==0 and part['harmony_count']==1 and part['frame_count']==1 and part['slash_count']==1
    assert part['harmonies'][0]['root_step']=='C' and part['harmonies'][0]['kind']=='major-seventh'
    assert part['harmonies'][0]['bass_step']=='E' and part['harmonies'][0]['offset_raw']=='1'
    assert part['harmonies'][0]['frame']['tag']=='frame'
