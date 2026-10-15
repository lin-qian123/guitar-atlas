"""Full-corpus recall must retain hidden guitars without conflating TAB/GM."""
import hashlib
import io
import stat
import zipfile

import pytest

from audit_pdmx_mxl_scope import bind_integrity, inspect_mxl, musicxml_scope


CONTAINER = b'''<?xml version="1.0"?><container><rootfiles><rootfile full-path="score.xml" media-type="application/vnd.recordare.musicxml+xml"/></rootfiles></container>'''


def score(name="Piano", instrument="Piano", program=1, tab=False):
    return ('''<?xml version="1.0"?><!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">
    <score-partwise version="3.1"><work><work-title>Study</work-title></work><part-list><score-part id="P1">
    <part-name>%s</part-name><part-abbreviation>Pno.</part-abbreviation><score-instrument id="I1"><instrument-name>%s</instrument-name></score-instrument>
    <midi-instrument id="I1"><midi-program>%d</midi-program></midi-instrument></score-part></part-list>
    <part id="P1"><measure number="1"><attributes><divisions>1</divisions><clef><sign>%s</sign><line>2</line></clef></attributes>
    <note><rest/><duration>1</duration></note></measure></part></score-partwise>''' % (name, instrument, program, "TAB" if tab else "G")).encode()


def mxl(xml=None, extras=()):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as out:
        out.writestr("META-INF/container.xml", CONTAINER)
        out.writestr("score.xml", xml or score())
        for name, body in extras: out.writestr(name, body)
    return buf.getvalue()


@pytest.mark.parametrize("label", ["Nylon String Guit.", "AcNylonGuit", "Klassische Gitarre", "Gtr. 1", "原聲吉他", "κλασσική κιθάρα"])
def test_hidden_guitar_recalled_with_piano_program(label):
    result = inspect_mxl(mxl(score(name=label, instrument="Piano", program=1)))
    assert result["guitar_label_evidence"]
    assert "guitar_in_written_part_or_instrument_label" in result["recall_signals"]
    assert result["gm_programs_0based"] == [0]
    assert result["written_part_count"] == 1
    assert result["complete_musicxml_parse"] is True
    assert result["crc_status"] == "all_members_verified"


def test_tab_ukulele_remains_candidate_not_an_acoustic_guitar_conclusion():
    result = inspect_mxl(mxl(score(name="Ukulele", instrument="Ukulele", program=1, tab=True)))
    assert result["tab_part_ids"] == ["P1"]
    assert result["recall_signals"] == ["tab_clef"]
    assert result["guitar_label_evidence"] == []
    assert "guitar_player_count" not in result


def test_musicxml_program_is_one_based_and_all_guitar_programs_are_candidates():
    for program in (25, 26, 27, 28, 29, 30, 31, 32):
        result = musicxml_scope(score(program=program))
        assert result["gm_programs_0based"] == [program - 1]
        assert "guitar_playback_program" in result["recall_signals"]


def test_non_guitar_score_is_still_fully_validated():
    result = inspect_mxl(mxl())
    assert result["recall_signals"] == []
    assert result["parts"][0]["part_names"] == ["Piano", "Pno."]
    assert result["complete_musicxml_parse"] is True


@pytest.mark.parametrize("suffix", [b"trailing bytes", b"PK\x05\x06"])
def test_trailing_payload_rejected(suffix):
    with pytest.raises(ValueError): inspect_mxl(mxl() + suffix)


def test_unreferenced_zip_member_crc_is_checked():
    body = bytearray(mxl(extras=[("unused.txt", b"a random payload for unused file")]))
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        info = archive.getinfo("unused.txt")
        offset = info.header_offset + 30 + len(info.filename.encode()) + len(info.extra)
    body[offset] ^= 0xff
    with pytest.raises(ValueError, match="corrupt MXL ZIP"): inspect_mxl(bytes(body))


def test_unsafe_path_or_link_rejected_even_when_unused():
    with pytest.raises(ValueError, match="path"): inspect_mxl(mxl(extras=[("../unused", b"x")]))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr("META-INF/container.xml", CONTAINER)
        archive.writestr("score.xml", score())
        link = zipfile.ZipInfo("unused")
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(link, "score.xml")
    with pytest.raises(ValueError, match="link"): inspect_mxl(out.getvalue())


def test_internal_entities_and_truncated_musicxml_fail_closed():
    unsafe = b'<!DOCTYPE score-partwise [<!ENTITY x "Guitar">]><score-partwise>&x;</score-partwise>'
    with pytest.raises(ValueError): musicxml_scope(unsafe)
    with pytest.raises(ValueError): musicxml_scope(score()[:-12])


def test_score_part_and_actual_parts_must_agree():
    with pytest.raises(ValueError, match="part-list"): musicxml_scope(score().replace(b'<part id="P1">', b'<part id="P2">'))


def test_timewise_musicxml_has_complete_part_coverage():
    xml = b'<score-timewise><part-list><score-part id="P1"><part-name>Guitar</part-name></score-part></part-list><measure number="1"><part id="P1"><attributes><clef><sign>TAB</sign></clef></attributes><note><rest/></note></part></measure></score-timewise>'
    result = musicxml_scope(xml)
    assert result["score_root"] == "score-timewise"
    assert result["tab_part_ids"] == ["P1"]
    with pytest.raises(ValueError, match="timewise"): musicxml_scope(xml.replace(b'<part id="P1">', b'<part id="P2">'))


def test_fresh_integrity_binding_requires_same_scanned_file_stat_and_checksum():
    stat_guard = [1, 2, 3, 4, 5]
    item = {"bytes": 3, "md5": "a" * 32, "sha256": "b" * 64, "stat": stat_guard}
    report = {"archive_input": item, "coverage_complete": True}
    proof = {"status": "complete", "files": {"mxl.tar.gz": dict(item)}}
    assert bind_integrity(report, proof, stat_guard)["status"] == "complete"
    with pytest.raises(ValueError, match="stat"): bind_integrity(report, proof, [1, 3, 3, 4, 5])


def test_harmony_only_and_slash_accompaniment_activity_is_retained():
    xml = score(name="Guitar", instrument="Guitar").replace(
        b'<note><rest/><duration>1</duration></note>',
        b'<harmony><root><root-step>C</root-step></root><kind>major</kind><frame><frame-note/></frame></harmony>')
    xml = xml.replace(b'<divisions>1</divisions>', b'<divisions>1</divisions><measure-style><slash type="start"/></measure-style>')
    part = musicxml_scope(xml)["parts"][0]
    assert part["note_count"] == 0
    assert part["harmony_count"] == 1
    assert part["frame_count"] == 1
    assert part["slash_count"] == 1


def test_all_rest_and_pitched_note_activity_are_distinguished():
    rest = musicxml_scope(score())["parts"][0]
    sounding = musicxml_scope(score().replace(b'<rest/>', b'<pitch><step>E</step><octave>4</octave></pitch>'))["parts"][0]
    assert rest["note_count"] == 0 and rest["rest_count"] == 1
    assert sounding["note_count"] == 1 and sounding["rest_count"] == 0
