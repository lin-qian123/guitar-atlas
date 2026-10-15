"""Read notation/playback evidence without assigning instruments or performers.

MXL parts, staves, MIDI tracks and channels are different entities. This module
keeps them separate, preserves native labels, and supplies conservative note
fingerprints; it never converts a structural count into a player count. Inputs
are read only and receive the production structural validator first.
"""
from __future__ import annotations

import hashlib
import json
import struct
import zipfile
from collections import Counter, defaultdict, deque
from fractions import Fraction
from pathlib import Path

from source_adapters.pdmx_formats import _tag, _vlq, _xml, validate_source_format


SCHEMA_VERSION = 1


def _children(element, tag):
    return [entry for entry in element if _tag(entry) == tag]


def _child(element, tag):
    return next(iter(_children(element, tag)), None)


def _text(element, tag, default=''):
    child = _child(element, tag)
    return ''.join(child.itertext()) if child is not None else default


def _int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _fraction(value):
    try:
        return Fraction(value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _digest(value):
    body = json.dumps(value, ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode()
    return hashlib.sha256(body).hexdigest()


def _file_before(path, asset_format):
    path = Path(path)
    stat = path.stat()
    guard = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    validation = validate_source_format(path, asset_format)
    raw = path.read_bytes()
    return path, guard, raw, validation


def _file_after(path, guard):
    stat = path.stat()
    if (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns) != guard:
        raise ValueError('score file changed during evidence extraction')


def _summarize_notes(rows):
    # Each row contains measure/timeline, rational onset, rational duration and
    # sounding MIDI pitch. Staff/voice labels are deliberately not hashed, so a
    # TAB and notation view can be compared without equating staves to people.
    rows = sorted(rows, key=lambda row: (row[0], Fraction(row[1]), Fraction(row[2]), str(row[3])))
    pitches = [row[3] for row in rows if isinstance(row[3], int)]
    return {'normalized_notes_sha256': _digest(rows),
            'normalized_notes_preview': rows[:12],
            'normalized_note_count': len(rows),
            'pitch_range': [min(pitches), max(pitches)] if pitches else None,
            'pitch_histogram': dict(sorted(Counter(map(str, (row[3] for row in rows))).items()))}


def _raw_tree(element):
    return {'tag': _tag(element), 'attributes': dict(element.attrib),
            'text': element.text or '', 'children': [_raw_tree(row) for row in element]}


def _part_groups(part_list):
    groups, active, seen_parts = [], {}, []
    for entry in part_list:
        tag = _tag(entry)
        if tag == 'score-part':
            seen_parts.append(entry.get('id'))
        elif tag == 'part-group':
            row = {'number': entry.get('number', '1'), 'type': entry.get('type', ''),
                   'name': _text(entry, 'group-name'), 'abbreviation': _text(entry, 'group-abbreviation'),
                   'symbol': _text(entry, 'group-symbol'), 'barline': _text(entry, 'group-barline'),
                   'raw': _raw_tree(entry)}
            groups.append(row)
            if row['type'] == 'start':
                active[row['number']] = (row, len(seen_parts))
            elif row['type'] == 'stop' and row['number'] in active:
                opening, offset = active.pop(row['number'])
                opening['member_part_ids'] = seen_parts[offset:]
                opening['closed'] = True
    for opening, offset in active.values():
        opening['member_part_ids'] = seen_parts[offset:]
        opening['closed'] = False
    return groups


def _mxl_part(declaration, measures, note_sink=None):
    result = {'part_id': declaration.get('id'), 'name': _text(declaration, 'part-name'),
              'abbreviation': _text(declaration, 'part-abbreviation'),
              'name_display': _raw_tree(_child(declaration, 'part-name-display')) if _child(declaration, 'part-name-display') is not None else None,
              'score_instruments': [], 'midi_instruments': [], 'measure_count': len(measures),
              'note_count': 0, 'rest_count': 0, 'grace_note_count': 0, 'unpitched_note_count': 0,
              'lyric_count': 0, 'harmony_count': 0, 'frame_count': 0, 'slash_count': 0,
              'harmonies': [], 'measure_styles': [], 'staves_max': 1, 'declared_staves': [], 'clefs': [],
              'staff_details': [], 'transpose_changes': [], 'directions': [], 'used_instrument_ids': [],
              'measure_evidence': [], 'normalization_issues': [], 'part_symbols': [],
              'note_instrument_counts': {}, 'notehead_counts': {}}
    for item in _children(declaration, 'score-instrument'):
        result['score_instruments'].append({'id': item.get('id'), 'name': _text(item, 'instrument-name'),
            'abbreviation': _text(item, 'instrument-abbreviation'), 'solo': _child(item, 'solo') is not None,
            'ensemble': _text(item, 'ensemble', None), 'raw': _raw_tree(item)})
    for item in _children(declaration, 'midi-instrument'):
        program = _int(_text(item, 'midi-program'))
        result['midi_instruments'].append({'id': item.get('id'), 'channel_1based': _int(_text(item, 'midi-channel')),
            'program_0based': program - 1 if program is not None else None,
            'program_musicxml_1based': program, 'bank_musicxml_1based': _int(_text(item, 'midi-bank')),
            'unpitched_musicxml_1based': _int(_text(item, 'midi-unpitched')), 'raw': _raw_tree(item)})
    notes, staff_notes, divisions, transpositions = [], defaultdict(list), None, {0: Fraction(0)}
    issues, used_instruments, instrument_counts, noteheads = set(), set(), Counter(), Counter()
    staff_counts, voice_counts, chord_count, tie_count = Counter(), Counter(), 0, 0
    pitch_steps = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
    for mi, measure in enumerate(measures):
        cursor, maximum, last_onset = Fraction(0), Fraction(0), None
        note_total, rest_total = 0, 0
        for item in measure:
            kind = _tag(item)
            if kind == 'attributes':
                value = _text(item, 'divisions', None)
                if value is not None:
                    divisions = _fraction(value)
                    if divisions is None or divisions <= 0:
                        issues.add('invalid_divisions')
                        divisions = None
                for staves in _children(item, 'staves'):
                    value = _int(staves.text)
                    result['declared_staves'].append({'measure_index': mi, 'staves': value, 'raw': staves.text})
                    if value is not None:
                        result['staves_max'] = max(result['staves_max'], value)
                for clef in _children(item, 'clef'):
                    result['clefs'].append({'measure_index': mi, 'staff_number': _int(clef.get('number'), 1),
                        'sign': _text(clef, 'sign'), 'line': _int(_text(clef, 'line')),
                        'octave_change': _int(_text(clef, 'clef-octave-change'), 0), 'raw': _raw_tree(clef)})
                for details in _children(item, 'staff-details'):
                    row = {'measure_index': mi, 'staff_number': _int(details.get('number'), 1),
                        'staff_type': _text(details, 'staff-type'), 'staff_lines': _int(_text(details, 'staff-lines')),
                        'capo': _int(_text(details, 'capo')), 'tunings': [], 'raw': _raw_tree(details)}
                    for tuning in _children(details, 'staff-tuning'):
                        row['tunings'].append({'line': _int(tuning.get('line')), 'step': _text(tuning, 'tuning-step'),
                            'alter': _text(tuning, 'tuning-alter', '0'), 'octave': _int(_text(tuning, 'tuning-octave'))})
                    result['staff_details'].append(row)
                for transpose in _children(item, 'transpose'):
                    chromatic = _fraction(_text(transpose, 'chromatic', '0'))
                    octave = _int(_text(transpose, 'octave-change'), 0)
                    number = _int(transpose.get('number'), 0)
                    row = {'measure_index': mi, 'staff_number': number or None,
                        'diatonic': _int(_text(transpose, 'diatonic')), 'chromatic': str(chromatic) if chromatic is not None else None,
                        'octave_change': octave, 'double': _child(transpose, 'double') is not None,
                        'raw': _raw_tree(transpose)}
                    result['transpose_changes'].append(row)
                    if chromatic is None or octave is None:
                        issues.add('invalid_transposition')
                        transpositions[number] = None
                    else:
                        transpositions[number] = chromatic + octave*12
                    if row['double']:
                        issues.add('doubling_transposition_not_expanded')
                for symbol in _children(item, 'part-symbol'):
                    result['part_symbols'].append({'measure_index': mi, 'symbol': symbol.text, 'attributes': dict(symbol.attrib)})
                for style in _children(item, 'measure-style'):
                    issues.add('measure_style_not_expanded')
                    result['slash_count'] += sum(_tag(child) == 'slash' for child in style)
                    result['measure_styles'].append({'measure_index': mi, 'staff_number': _int(style.get('number')),
                        'raw': _raw_tree(style)})
            elif kind in {'backup', 'forward'}:
                duration = _fraction(_text(item, 'duration', None))
                if duration is None or duration < 0 or divisions is None:
                    issues.add('invalid_or_unresolved_cursor_duration')
                else:
                    cursor += duration/divisions * (-1 if kind == 'backup' else 1)
                    if cursor < 0:
                        issues.add('negative_measure_cursor')
                    maximum = max(maximum, cursor)
                last_onset = None
            elif kind == 'direction':
                for direction in item.iter():
                    if _tag(direction) in {'words', 'rehearsal', 'instrument-change'}:
                        result['directions'].append({'measure_index': mi, 'type': _tag(direction),
                            'text': ''.join(direction.itertext()), 'attributes': dict(direction.attrib)})
            elif kind == 'harmony':
                result['harmony_count'] += 1
                frame = _child(item, 'frame')
                result['frame_count'] += len(_children(item, 'frame'))
                root, bass, chord_kind = _child(item, 'root'), _child(item, 'bass'), _child(item, 'kind')
                result['harmonies'].append({'measure_index': mi, 'measure_number': measure.get('number'),
                    'cursor_quarters': str(cursor), 'offset_raw': _text(item, 'offset', None),
                    'root_step': _text(root, 'root-step') if root is not None else None,
                    'root_alter': _text(root, 'root-alter', '0') if root is not None else None,
                    'kind': ''.join(chord_kind.itertext()) if chord_kind is not None else None,
                    'kind_attributes': dict(chord_kind.attrib) if chord_kind is not None else {},
                    'bass_step': _text(bass, 'bass-step') if bass is not None else None,
                    'bass_alter': _text(bass, 'bass-alter', '0') if bass is not None else None,
                    'frame': _raw_tree(frame) if frame is not None else None, 'raw': _raw_tree(item)})
            elif kind == 'note':
                rest = _child(item, 'rest') is not None
                grace = _child(item, 'grace') is not None
                chord = _child(item, 'chord') is not None
                staff = _int(_text(item, 'staff'), 1)
                voice = _text(item, 'voice', '')
                result['staves_max'] = max(result['staves_max'], staff)
                voice_counts[voice] += 1
                instrument = _child(item, 'instrument')
                if instrument is not None:
                    identity = instrument.get('id', '')
                    used_instruments.add(identity)
                    instrument_counts[identity] += 1
                head = _text(item, 'notehead')
                if head:
                    noteheads[head] += 1
                result['lyric_count'] += len(_children(item, 'lyric'))
                if rest:
                    result['rest_count'] += 1
                    rest_total += 1
                else:
                    result['note_count'] += 1
                    note_total += 1
                    staff_counts[staff] += 1
                if grace:
                    result['grace_note_count'] += 1
                    issues.add('grace_timing_not_expanded')
                chord_count += chord
                ties = _children(item, 'tie')
                tie_count += bool(ties)
                if ties:
                    issues.add('ties_kept_as_notated_segments')
                if _child(item, 'notations') is not None and any(_tag(x) in {'ornaments', 'articulations'} for x in item.iter()):
                    issues.add('ornaments_and_articulations_not_rendered')
                duration = _fraction(_text(item, 'duration', None))
                if grace and duration is None:
                    duration_q = Fraction(0)
                elif duration is None or duration < 0:
                    issues.add('missing_or_invalid_note_duration')
                    duration_q = None
                elif divisions is None:
                    issues.add('missing_or_invalid_divisions')
                    duration_q = None
                else:
                    duration_q = duration/divisions
                onset = last_onset if chord else cursor
                if chord and last_onset is None:
                    issues.add('chord_without_preceding_note')
                pitch = _child(item, 'pitch')
                sounding = None
                if pitch is not None:
                    step = pitch_steps.get(_text(pitch, 'step'))
                    octave = _int(_text(pitch, 'octave'))
                    alter = _fraction(_text(pitch, 'alter', '0'))
                    transpose = transpositions.get(staff, transpositions.get(0))
                    if step is not None and octave is not None and alter is not None and transpose is not None:
                        pitch_value = (octave+1)*12 + step + alter + transpose
                        if pitch_value.denominator == 1:
                            sounding = int(pitch_value)
                        else:
                            issues.add('non_integral_pitch_or_transposition')
                    else:
                        issues.add('unresolved_pitch_or_transposition')
                elif _child(item, 'unpitched') is not None:
                    result['unpitched_note_count'] += 1
                    issues.add('unpitched_notes_not_in_pitched_fingerprint')
                elif not rest:
                    issues.add('absent_note_pitch')
                if note_sink is not None and not rest:
                    note_sink.append({'measure_index': mi, 'onset': str(onset) if onset is not None else None,
                        'duration': str(duration_q) if duration_q is not None else None, 'pitch': sounding,
                        'staff': staff, 'voice': voice, 'grace': grace,
                        'grace_attributes': dict(_child(item, 'grace').attrib) if grace else {},
                        'unpitched': _child(item, 'unpitched') is not None})
                if not rest and not grace and onset is not None and duration_q is not None and sounding is not None:
                    row = [mi, str(onset), str(duration_q), sounding]
                    notes.append(row)
                    staff_notes[staff].append(row)
                if not chord:
                    last_onset = cursor
                    if duration_q is not None:
                        cursor += duration_q
                if duration_q is not None and onset is not None:
                    maximum = max(maximum, onset+duration_q, cursor)
        result['measure_evidence'].append({'index': mi, 'number': measure.get('number'),
            'implicit': measure.get('implicit'), 'non_controlling': measure.get('non-controlling'),
            'measured_extent_quarters': str(maximum), 'notes': note_total, 'rests': rest_total})
    result.update(_summarize_notes(notes))
    result['staff_note_summaries'] = [{'staff_number': staff, 'note_count': staff_counts[staff],
        **_summarize_notes(staff_notes[staff])} for staff in sorted(staff_counts)]
    result['voice_note_counts'] = dict(sorted(voice_counts.items()))
    result['used_instrument_ids'] = sorted(used_instruments)
    result['note_instrument_counts'] = dict(sorted(instrument_counts.items()))
    result['notehead_counts'] = dict(sorted(noteheads.items()))
    result['chord_member_count'], result['tied_segment_count'] = chord_count, tie_count
    result['normalization_issues'] = sorted(issues)
    # Ties/ornaments are explicit musical limitations but do not invalidate the
    # exact notated-note representation. Unknown pitch or timing does.
    partial = issues - {'ties_kept_as_notated_segments', 'ornaments_and_articulations_not_rendered'}
    result['normalization_status'] = 'partial' if partial else 'complete'
    return result


def read_mxl_evidence(path):
    """Return all declared/actual notation parts and conservative note summaries."""
    path, guard, raw, validation = _file_before(path, 'MUSICXML')
    with zipfile.ZipFile(path) as archive:
        root = _xml(archive.read(validation['score_member']), 'MusicXML evidence')
    part_list = _child(root, 'part-list')
    declarations = _children(part_list, 'score-part')
    measures = defaultdict(list)
    if _tag(root) == 'score-partwise':
        for part in _children(root, 'part'):
            measures[part.get('id')] = _children(part, 'measure')
    else:
        for measure in _children(root, 'measure'):
            for part in _children(measure, 'part'):
                # Use a new local wrapper for timewise attributes, never mutate
                # the score tree or original bytes.
                import xml.etree.ElementTree as ET
                wrapper = ET.Element('measure', dict(measure.attrib))
                wrapper.extend(list(part))
                measures[part.get('id')].append(wrapper)
    result = {'schema_version': SCHEMA_VERSION, 'format': 'MUSICXML', 'file_sha256': hashlib.sha256(raw).hexdigest(),
        'file_bytes': len(raw), 'validation': validation, 'score_root': _tag(root),
        'part_groups': _part_groups(part_list),
        'parts': [_mxl_part(row, measures[row.get('id')]) for row in declarations],
        'limitations': ['Parts and staves do not by themselves establish performers.',
            'Fingerprints describe rational per-measure notated events; repeats, ornaments, expressive timing and ties are not rendered.',
            'Clef octave changes are retained as notation evidence; only explicit transpose changes sounding pitch.',
            'Names and MIDI program declarations are preserved as file evidence, not independently certified instrument identities.']}
    _file_after(path, guard)
    return result


def _midi_text(raw):
    try:
        return raw.decode('utf-8'), 'utf-8'
    except UnicodeDecodeError:
        return raw.decode('latin-1'), 'latin-1-byte-preserving'


def _midi_track(body, index):
    track = {'index': index, 'track_names': [], 'instrument_names': [], 'text_events': [],
        'program_changes': [], 'controllers': [], 'note_events': [], 'note_on_count': 0,
        'note_off_count': 0, 'end_tick': 0, 'channel_1based': [], 'ports': []}
    offset, running, tick, ordinal, port = 0, None, 0, 0, 0
    events = []
    while offset < len(body):
        delta, offset = _vlq(body, offset)
        tick += delta
        status = body[offset]
        if status >= 0x80:
            offset += 1
        else:
            status = running
        ordinal += 1
        if status <= 0xef:
            running = status
            count = 1 if status >> 4 in {0xc, 0xd} else 2
            data, offset = body[offset:offset+count], offset+count
            channel = (status & 15)+1
            track['channel_1based'].append(channel)
            track['ports'].append(port)
            kind = status >> 4
            if kind == 0xc:
                track['program_changes'].append({'tick': tick, 'channel_1based': channel,
                    'program_0based': data[0], **({'port': port} if port else {})})
            elif kind == 0xb:
                track['controllers'].append({'tick': tick, 'channel_1based': channel,
                    'controller': data[0], 'value': data[1], 'port': port})
            elif kind in {0x8, 0x9}:
                on = kind == 0x9 and data[1] > 0
                label = 'on' if on else 'off'
                track['note_on_count' if on else 'note_off_count'] += 1
                track['note_events'].append([tick, label, channel, data[0], data[1], port])
                events.append({'tick': tick, 'on': on, 'channel': channel, 'pitch': data[0],
                    'velocity': data[1], 'port': port, 'track': index, 'ordinal': ordinal})
        elif status == 0xff:
            running = None
            kind = body[offset]
            length, offset = _vlq(body, offset+1)
            data, offset = body[offset:offset+length], offset+length
            if kind in {1, 2, 3, 4, 5, 6, 7, 8, 9}:
                text, encoding = _midi_text(data)
                track['text_events'].append({'tick': tick, 'type': kind, 'text': text,
                    'encoding': encoding, 'bytes_hex': data.hex()})
                if kind in {3, 4}:
                    track['track_names' if kind == 3 else 'instrument_names'].append(text)
            if kind == 0x21:
                port = data[0]
        else:
            running = None
            length, offset = _vlq(body, offset)
            offset += length
    track['end_tick'] = tick
    track['channel_1based'] = sorted(set(track['channel_1based']))
    track['ports'] = sorted(set(track['ports']))
    track['note_events_sha256'] = _digest(track['note_events'])
    return track, events


def read_midi_evidence(path):
    """Return SMF track/channel evidence; track and channel counts are not players."""
    path, guard, raw, validation = _file_before(path, 'MIDI')
    _, fmt, ntracks, division = struct.unpack('>IHHH', raw[4:14])
    offset, tracks, events = 14, [], []
    for index in range(ntracks):
        length = int.from_bytes(raw[offset+4:offset+8], 'big')
        offset += 8
        track, notes = _midi_track(raw[offset:offset+length], index)
        tracks.append(track)
        events.extend(notes)
        offset += length
    independent = fmt == 2
    channels = defaultdict(list)
    for event in events:
        key = (event['track'] if independent else None, event['port'], event['channel'])
        channels[key].append(event)
    result = {'schema_version': SCHEMA_VERSION, 'format': 'MIDI', 'file_sha256': hashlib.sha256(raw).hexdigest(),
        'file_bytes': len(raw), 'validation': validation, 'midi_format': fmt,
        'timeline_mode': 'independent_tracks' if independent else 'synchronized_tracks',
        'division': division, 'ticks_per_quarter': division if not division & 0x8000 else None,
        'tracks': tracks, 'channels': [], 'unmatched_note_on_count': 0, 'unmatched_note_off_count': 0,
        'note_pairing_issues': [], 'limitations': ['Tracks and channels do not establish performer counts.',
            'Program changes are playback evidence; channel 10 is only a conventional GM percussion-channel marker.',
            'Note durations end at note-off; sustain, pedals, controller effects and synthesis are not rendered.',
            'No alignment with MXL/PDF, acoustic playback or note-by-note fidelity is asserted.']}
    issues = set()
    if division & 0x8000:
        issues.add('smpte_time_not_normalized_to_quarters')
    for key in sorted(channels, key=lambda key: (-1 if key[0] is None else key[0], key[1], key[2])):
        pattern, port, channel = key
        channel_events = sorted(channels[key], key=lambda event: (event['tick'], event['track'], event['ordinal']))
        pending, notes, unmatched_off, overlapping = defaultdict(deque), [], 0, False
        for event in channel_events:
            pitch = event['pitch']
            if event['on']:
                if pending[pitch]:
                    overlapping = True
                    issues.add('overlapping_same_channel_pitch')
                pending[pitch].append(event)
            elif pending[pitch]:
                start = pending[pitch].popleft()
                notes.append([start['tick'], event['tick']-start['tick'], pitch])
            else:
                unmatched_off += 1
        unmatched_on = sum(map(len, pending.values()))
        result['unmatched_note_on_count'] += unmatched_on
        result['unmatched_note_off_count'] += unmatched_off
        if unmatched_on:
            issues.add('unmatched_note_on')
        if unmatched_off:
            issues.add('unmatched_note_off')
        rows = [[str(Fraction(onset, division)), str(Fraction(duration, division)), pitch]
            for onset, duration, pitch in sorted(notes)] if not division & 0x8000 else []
        pitches = [event['pitch'] for event in channel_events if event['on']]
        track_indices = sorted({event['track'] for event in channel_events})
        programs = [dict(row, track_index=track['index']) for track in tracks
            for row in track['program_changes'] if row['channel_1based'] == channel
            and row.get('port', 0) == port and (pattern is None or track['index'] == pattern)]
        result['channels'].append({'channel_1based': channel, 'port': port,
            **({'pattern_track_index': pattern} if independent else {}),
            'percussion_channel': channel == 10, 'source_track_indices': track_indices,
            'program_changes': programs, 'note_count': len(pitches), 'paired_note_count': len(notes),
            'unmatched_note_on_count': unmatched_on, 'unmatched_note_off_count': unmatched_off,
            'overlapping_same_pitch': overlapping, 'note_duration_ticks': {
                'minimum': min((row[1] for row in notes), default=None),
                'maximum': max((row[1] for row in notes), default=None),
                'sum': sum(row[1] for row in notes)},
            'pitch_range': [min(pitches), max(pitches)] if pitches else None,
            'pitch_histogram': dict(sorted(Counter(map(str, pitches)).items())),
            'normalized_notes_sha256': _digest(rows), 'normalized_notes_preview': rows[:12],
            'normalized_note_count': len(rows)})
    result['note_pairing_issues'] = sorted(issues)
    result['note_pairing_status'] = 'partial' if issues else 'complete'
    _file_after(path, guard)
    return result


def build_catalog_evidence(root):
    """Reproduce private evidence for the exact current MuseScore file manifest.

    This acquires no files and changes no catalog. A caller decides where to
    save the returned receipt; private paths and hashes must stay private.
    """
    root = Path(root).resolve()
    catalog_path = root / 'sources/musescore/catalog.json'
    raw = catalog_path.read_bytes()
    catalog = json.loads(raw)
    if catalog.get('source_id') != 'musescore' or len(catalog.get('works', [])) != 924:
        raise ValueError('expected the frozen 924-record MuseScore scope')
    result = {'schema_version': SCHEMA_VERSION, 'source_id': 'musescore',
        'scope': 'existing frozen 924 native records only; file evidence without performer assignment',
        'catalog_sha256': hashlib.sha256(raw).hexdigest(), 'catalog_bytes': len(raw),
        'method_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'records': [], 'failures': [], 'summary': {}}
    caches = {'MUSICXML': {}, 'MIDI': {}}
    for work in catalog['works']:
        entry = {'id': work['id'], 'title': work['title_en'], 'source_url': work['source_url'],
                 'evidence': {}}
        for fmt, reader in [('MUSICXML', read_mxl_evidence), ('MIDI', read_midi_evidence)]:
            try:
                assets = [asset for asset in work['assets'] if asset['format'] == fmt]
                if len(assets) != 1 or assets[0]['status'] != 'verified':
                    raise ValueError('one verified existing format asset is required')
                asset = assets[0]
                target = root / asset['local_path']
                resolved = target.resolve(strict=True)
                if root not in resolved.parents:
                    raise ValueError('score path leaves private library root')
                cache_key = (asset['sha256'], str(resolved))
                evidence = caches[fmt].get(cache_key)
                if evidence is None:
                    evidence = reader(target)
                    if evidence['file_sha256'] != asset['sha256'] or evidence['file_bytes'] != asset['size']:
                        raise ValueError('file bytes disagree with acquired manifest')
                    caches[fmt][cache_key] = evidence
                entry['evidence'][fmt] = {'local_path': asset['local_path'], **evidence}
            except (ValueError, OSError, KeyError) as error:
                result['failures'].append({'id': work['id'], 'format': fmt, 'error': str(error)})
        result['records'].append(entry)
    if catalog_path.read_bytes() != raw:
        raise ValueError('source catalog changed during file evidence extraction')
    summary = result['summary']
    summary['source_records'] = len(result['records'])
    summary['successful_format_records'] = {fmt: sum(fmt in row['evidence'] for row in result['records']) for fmt in caches}
    summary['unique_format_hashes'] = {fmt: len({row['evidence'][fmt]['file_sha256'] for row in result['records'] if fmt in row['evidence']}) for fmt in caches}
    summary['failed_format_records'] = len(result['failures'])
    counters = {key: Counter() for key in ['mxl_part_counts', 'mxl_part_name_occurrences',
        'mxl_instrument_name_occurrences', 'mxl_staves_per_part', 'mxl_normalization_issues',
        'midi_track_counts', 'midi_sounding_channel_counts', 'midi_program_record_occurrences',
        'midi_note_pairing_issues']}
    for row in result['records']:
        if 'MUSICXML' in row['evidence']:
            score = row['evidence']['MUSICXML']
            counters['mxl_part_counts'][str(len(score['parts']))] += 1
            for part in score['parts']:
                counters['mxl_part_name_occurrences'][part['name']] += 1
                counters['mxl_staves_per_part'][str(part['staves_max'])] += 1
                counters['mxl_normalization_issues'].update(part['normalization_issues'])
                for instrument in part['score_instruments']:
                    counters['mxl_instrument_name_occurrences'][instrument['name']] += 1
        if 'MIDI' in row['evidence']:
            score = row['evidence']['MIDI']
            counters['midi_track_counts'][str(len(score['tracks']))] += 1
            counters['midi_sounding_channel_counts'][str(sum(channel['note_count'] > 0 for channel in score['channels']))] += 1
            counters['midi_note_pairing_issues'].update(score['note_pairing_issues'])
            programs = {change['program_0based'] for track in score['tracks'] for change in track['program_changes']}
            counters['midi_program_record_occurrences'].update(map(str, programs))
    summary.update({key: dict(sorted(value.items(), key=lambda item: (-item[1], item[0]))) for key, value in counters.items()})
    result['status'] = 'complete' if not result['failures'] else 'complete_with_failures'
    return result


def main():
    import argparse
    import os
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--output', type=Path,
        default=Path('sources/musescore/verification/instrumentation-mxl-midi.json'))
    args = parser.parse_args()
    result = build_catalog_evidence(args.root)
    output = args.output if args.output.is_absolute() else args.root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix+'.part')
    try:
        temporary.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':'))+'\n')
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    print(json.dumps({'status': result['status'], 'output': str(output), 'summary': result['summary']}, ensure_ascii=False, indent=2))
    return int(bool(result['failures']))


def _view_rows(events):
    rows = [[row['measure_index'], row['onset'], row['duration'], row['pitch'], row['grace']]
            for row in events]
    return sorted(rows, key=lambda row: (row[0], Fraction(row[1] or '0'), row[4],
        Fraction(row[2] or '0'), str(row[3])))


def read_mxl_view_sequences(path):
    """Full pitched note/grace sequences for TAB-view comparison only.

    These additional sequences do not change the existing read_mxl_evidence
    schema. Unknown timing/pitch and unpitched notes block correspondence.
    """
    path, guard, raw, validation = _file_before(path, 'MUSICXML')
    with zipfile.ZipFile(path) as archive:
        root = _xml(archive.read(validation['score_member']), 'MusicXML TAB evidence')
    measures = defaultdict(list)
    if _tag(root) == 'score-partwise':
        for part in _children(root, 'part'):
            measures[part.get('id')] = _children(part, 'measure')
    else:
        import xml.etree.ElementTree as ET
        for measure in _children(root, 'measure'):
            for part in _children(measure, 'part'):
                wrapper = ET.Element('measure', dict(measure.attrib))
                wrapper.extend(list(part))
                measures[part.get('id')].append(wrapper)
    result = {'file_sha256': hashlib.sha256(raw).hexdigest(), 'parts': []}
    for declaration in _children(_child(root, 'part-list'), 'score-part'):
        notes = []
        part = _mxl_part(declaration, measures[declaration.get('id')], note_sink=notes)
        rows = _view_rows(notes)
        incomplete = any(row['pitch'] is None or row['onset'] is None or row['duration'] is None for row in notes)
        blocking = set(part['normalization_issues']) & {'negative_measure_cursor', 'invalid_divisions',
            'invalid_or_unresolved_cursor_duration', 'chord_without_preceding_note', 'measure_style_not_expanded',
            'doubling_transposition_not_expanded'}
        part.update({'all_events': rows, 'event_count': len(rows), 'signature_sha256': _digest(rows),
            'view_sequence_complete': not incomplete and not blocking,
            'view_sequence_blockers': sorted(blocking),
            'staff_views': [{'staff_number': staff, 'all_events': _view_rows([note for note in notes if note['staff'] == staff]),
                'event_count': sum(note['staff'] == staff for note in notes),
                'view_sequence_complete': not any(note['pitch'] is None or note['onset'] is None or note['duration'] is None
                    for note in notes if note['staff'] == staff) and not blocking}
                for staff in sorted({note['staff'] for note in notes})]})
        result['parts'].append(part)
    _file_after(path, guard)
    return result


def compare_view_sequences(left, right):
    """Compare every event; a match is evidence, never performer assignment."""
    a, b = left['all_events'], right['all_events']
    result = {'left_event_count': len(a), 'right_event_count': len(b),
        'all_events_correspond': False, 'left_sha256': _digest(a), 'right_sha256': _digest(b)}
    if not a or not b:
        return {**result, 'kind': 'empty_view_not_identity_evidence'}
    if not left['view_sequence_complete'] or not right['view_sequence_complete']:
        return {**result, 'kind': 'incomplete_sequence_not_identity_evidence'}
    if a == b:
        return {**result, 'kind': 'exact_pitch_onset_duration_grace', 'all_events_correspond': True,
            'left_minus_right_semitones': 0}
    # Sort by pitch numerically, retaining note multiplicity. This permits a
    # constant octave translation while requiring every timing/grace event.
    key = lambda row: (row[0], Fraction(row[1]), row[4], Fraction(row[2]), row[3])
    aa, bb = sorted(a, key=key), sorted(b, key=key)
    if len(aa) == len(bb) and all(x[:3]+x[4:] == y[:3]+y[4:] for x,y in zip(aa,bb)):
        offsets = {x[3]-y[3] for x,y in zip(aa,bb)}
        if len(offsets) == 1:
            offset = offsets.pop()
            if offset and offset % 12 == 0:
                return {**result, 'kind': 'constant_octave_offset', 'all_events_correspond': True,
                    'left_minus_right_semitones': offset}
    a_set, b_set = Counter(tuple(row) for row in a), Counter(tuple(row) for row in b)
    common = sum((a_set & b_set).values())
    return {**result, 'kind': 'different_content', 'exact_common_event_count': common,
        'left_exact_common_fraction': common/len(a), 'right_exact_common_fraction': common/len(b)}


def _instrument_family(part):
    import re
    import unicodedata
    text = ' '.join([part['name']] + [item['name'] for item in part['score_instruments']])
    folded = ''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c))
    if re.search(r'guitar|guitarr|gitarr|gitaar|gitara|chitarr|violao|kytar|гитар|гитар|κιθαρ|吉他|ギター', folded):
        return 'guitar_named_in_file'
    if re.search(r'mandolin|mandoli|bandolim', folded):
        return 'mandolin_named_in_file'
    if re.search(r'ukulele', folded):
        return 'ukulele_named_in_file'
    return None


def _view_role_conflict(left, right):
    import re
    names = [part['name'].casefold() for part in (left, right)]
    roles = [set(re.findall(r'\b(?:melody|background|accompaniment|chords|bass|counter|tapping|percussion)\b', name)) for name in names]
    if any(roles) and roles[0] != roles[1]:
        return True
    numbers = [re.search(r'(?:\s|^)([1-9]|i{1,3}|iv|v|vi{1,3})\s*$', name) for name in names]
    return bool(all(numbers) and numbers[0].group(1) != numbers[1].group(1))


def build_tab_review(root):
    """Audit every existing TAB-bearing record; never merge ordinary parts."""
    root = Path(root).resolve()
    source_path = root / 'sources/musescore/verification/instrumentation-mxl-midi.json'
    pdf_path = root / 'sources/musescore/verification/instrumentation-pdf.json'
    source_raw, pdf_raw = source_path.read_bytes(), pdf_path.read_bytes()
    source, pdf = json.loads(source_raw), json.loads(pdf_raw)
    records, failures = [], []
    for original in source['records']:
        evidence = original['evidence']['MUSICXML']
        if not any(any(clef['sign'] == 'TAB' for clef in part['clefs']) for part in evidence['parts']):
            continue
        try:
            full = read_mxl_view_sequences(root/evidence['local_path'])
            if full['file_sha256'] != evidence['file_sha256']:
                raise ValueError('MXL changed since initial extraction')
            parts = full['parts']
            row = {'id': original['id'], 'mxl_sha256': full['file_sha256'],
                'normal_part_ids': [], 'tab_part_ids': [], 'tab_only_part_ids': [],
                'same_part_views': [], 'cross_part_candidates': [], 'confirmed_pairs': [],
                'unconfirmed_candidates': [], 'unresolved_tab_part_ids': [],
                'part_evidence': []}
            pdf_record = pdf['records'].get(original['id'], {})
            page = next(iter(pdf_record.get('evidence', {}).get('page_evidence', [])), {})
            row['pdf_support'] = {'sha256': pdf_record.get('pdf', {}).get('sha256'),
                'first_system_labels': pdf_record.get('evidence', {}).get('first_system_instrument_labels', []),
                'first_page_staff_line_counts': [band['line_count'] for band in page.get('geometry', {}).get('staff_bands', [])],
                'interpretation': 'printed labels/geometry support view context, not note identity or octave certification'}
            normal_views, tab_views = {}, {}
            for part in parts:
                identity = part['part_id']
                tab_staff = {clef['staff_number'] for clef in part['clefs'] if clef['sign'] == 'TAB'}
                normal_staff = {clef['staff_number'] for clef in part['clefs'] if clef['sign'] != 'TAB'}
                if tab_staff:
                    row['tab_part_ids'].append(identity)
                if not tab_staff or normal_staff:
                    row['normal_part_ids'].append(identity)
                if tab_staff and not normal_staff:
                    row['tab_only_part_ids'].append(identity)
                    tab_views[identity] = part
                if normal_staff or not tab_staff:
                    if tab_staff:
                        staff_views = [view for view in part['staff_views'] if view['staff_number'] in normal_staff]
                        normal_views[identity] = {'all_events': sorted([event for view in staff_views for event in view['all_events']], key=lambda e:(e[0],Fraction(e[1] or '0'),e[4],Fraction(e[2] or '0'),str(e[3]))),
                            'view_sequence_complete': all(view['view_sequence_complete'] for view in staff_views)}
                    else:
                        normal_views[identity] = part
                row['part_evidence'].append({key: part[key] for key in ['part_id','name','score_instruments',
                    'midi_instruments','clefs','transpose_changes','staff_details','note_count',
                    'event_count','signature_sha256','view_sequence_complete','view_sequence_blockers']})
                if tab_staff and normal_staff:
                    inner = {'part_id': identity, 'normal_staff_numbers': sorted(normal_staff),
                        'tab_staff_numbers': sorted(tab_staff), 'comparisons': [],
                        'interpretation': 'one declared actual part contains notation/TAB staves; no extra performer inferred'}
                    for normal in part['staff_views']:
                        if normal['staff_number'] not in normal_staff: continue
                        for tab in part['staff_views']:
                            if tab['staff_number'] not in tab_staff: continue
                            inner['comparisons'].append({'normal_staff_number': normal['staff_number'],
                                'tab_staff_number': tab['staff_number'], **compare_view_sequences(normal,tab)})
                    row['same_part_views'].append(inner)
            by_id = {part['part_id']: part for part in parts}
            for tab_id, tab in tab_views.items():
                candidates = []
                for normal_id, normal in normal_views.items():
                    if normal_id == tab_id: continue
                    left, right = by_id[normal_id], by_id[tab_id]
                    same_family = _instrument_family(left) is not None and _instrument_family(left) == _instrument_family(right)
                    if not same_family: continue
                    conflict = _view_role_conflict(left,right)
                    comparison = compare_view_sequences(normal,tab)
                    item = {'normal_part_id': normal_id, 'tab_part_id': tab_id,
                        'normal_name': left['name'], 'tab_name': right['name'],
                        'instrument_family_evidence': _instrument_family(left),
                        'distinct_named_roles': conflict, **comparison,
                        'normal_clef_octave_changes': sorted({clef['octave_change'] for clef in left['clefs'] if clef['sign'] != 'TAB'}),
                        'decision': 'unconfirmed'}
                    if comparison['kind'] == 'exact_pitch_onset_duration_grace' and not conflict:
                        item['decision'] = 'confirmed_duplicate_view'
                        item['basis'] = 'actual TAB clef plus same named instrument family and every pitched/grace event has equal measure/onset/duration/explicit-transpose pitch; no distinct named role'
                    elif comparison['kind'] == 'constant_octave_offset':
                        item['basis'] = 'complete event timing and constant octave difference; requires separate PDF/clef/transpose review before merge'
                    elif conflict:
                        item['basis'] = 'distinct functional or numbered names; do not merge from content/program similarity'
                    else:
                        item['basis'] = 'full correspondence not established; retain separate role or explicit uncertainty'
                    candidates.append(item)
                    row['cross_part_candidates'].append(item)
                confirmed = [item for item in candidates if item['decision']=='confirmed_duplicate_view']
                if len(confirmed) == 1:
                    row['confirmed_pairs'].extend(confirmed)
                else:
                    if len(confirmed) > 1:
                        for item in confirmed:
                            item['decision']='unconfirmed_multiple_identical_normal_parts'
                            item['basis']='more than one complete normal-part match; TAB cannot establish which independent role it represents'
                    row['unresolved_tab_part_ids'].append(tab_id)
                row['unconfirmed_candidates'].extend(item for item in candidates if item['decision']!='confirmed_duplicate_view')
            records.append(row)
        except (ValueError,OSError,KeyError) as error:
            failures.append({'id': original['id'], 'error': str(error)})
    summary = {'tab_records': len(records), 'extraction_failures': len(failures),
        'tab_parts': sum(len(row['tab_part_ids']) for row in records),
        'same_part_normal_tab_parts': sum(len(row['same_part_views']) for row in records),
        'tab_only_parts': sum(len(row['tab_only_part_ids']) for row in records),
        'confirmed_cross_part_pairs': sum(len(row['confirmed_pairs']) for row in records),
        'records_with_confirmed_cross_part_pairs': sum(bool(row['confirmed_pairs']) for row in records),
        'unresolved_tab_only_parts': sum(len(row['unresolved_tab_part_ids']) for row in records),
        'unresolved_record_ids': [row['id'] for row in records if row['unresolved_tab_part_ids']],
        'comparison_kind_counts': dict(Counter(item['kind'] for row in records for item in row['cross_part_candidates']))}
    if len(records)+len(failures) != 260:
        raise ValueError('TAB scope differs from the frozen 260-record initial extraction')
    return {'schema_version':1, 'status':'complete' if not failures else 'complete_with_failures',
        'scope':'all 260 records with actual MusicXML TAB clefs',
        'method_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'mxl_midi_proof_sha256': hashlib.sha256(source_raw).hexdigest(),
        'pdf_proof_sha256': hashlib.sha256(pdf_raw).hexdigest(),
        'summary':summary, 'records':records, 'failures':failures,
        'limitations':['No ordinary pair is merged solely from equal notes or a common MIDI program.',
            'Octave-offset pairs remain unconfirmed until independent printed/transpose evidence supports them.',
            'Within-part notation/TAB staves do not automatically establish performers or resolve missing notes.',
            'Different or incomplete view content remains separate pending a specific evidence-based decision.']}


if __name__ == '__main__':
    raise SystemExit(main())
