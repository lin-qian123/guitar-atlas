from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import struct
import zipfile

import pytest

from review_musescore_expansion_final import (
    review_file_title, review_midi_name_correspondence, public_part_labels, make_projection, apply_identity_review,
    validate_extraction_journal,
)


def pdf(title, *, readable=True):
    return {"text_readable": readable, "pages": 1, "first_system_instrument_labels": [],
            "page_evidence": [{"page": 1, "size": [600, 800],
                "text": title, "text_lines": [{"text": title, "bbox": [150, 40, 450, 70]}],
                "geometry": {"first_system_span": [120, 220]}}]}


def test_exact_and_source_credit_title_variants_keep_actual_transcriptions():
    result = review_file_title("Sailor's Hat & Guitar", {"work_titles": ["Template"]}, pdf("Sailor’s Hat & Guitar"))
    assert result["status"] == "consistent"
    result = review_file_title("A Small Guitar Piece — F. Sor", {"work_titles": []}, pdf("A Small Guitar Piece"))
    assert result["status"] == "compatible_title_variant"
    assert result["actual_pdf_titles"] == ["A Small Guitar Piece"]


def test_mxl_template_conflict_alone_cannot_override_matching_printed_pdf():
    result = review_file_title("Actual Piece", {"work_titles": ["Unrelated Template"]}, pdf("Actual Piece"))
    assert result["status"] == "consistent"
    assert "MXL_internal_title_differs_from_printed_PDF" in result["notes"]


def test_printed_pdf_conflict_is_preserved_and_not_guessed_as_the_same_work():
    result = review_file_title("Op.29 No.1", {"work_titles": ["Op.20 No.1"]}, pdf("Op.20 No.1"))
    assert result["status"] == "identity_conflict"
    assert result["actual_pdf_titles"] == ["Op.20 No.1"]


def test_no_printed_heading_remains_insufficient_without_invented_identity():
    result = review_file_title("Actual Piece", {"work_titles": ["Actual Piece"]},
        {"text_readable": False, "page_evidence": [], "first_system_instrument_labels": []})
    assert result["status"] == "insufficient_file_title"


def test_private_printed_title_conflict_is_recorded_privately_before_public_redaction():
    result = review_file_title("Actual Piece", {"work_titles": []}, pdf("contact@example.com"))
    assert result["status"] == "identity_conflict"
    assert result["actual_pdf_titles"] == ["contact@example.com"]


def test_track_named_voice_on_guitar_channel_is_a_name_conflict_even_when_patch_matches():
    classification = {"roles": [{"part_id": "P1", "kind": "guitar", "sounding": True}]}
    playback = {"sounding_groups": [{"track_names": ["Voice"], "MXL_part_ids": ["P1"], "note_on_count": 5}]}
    result = review_midi_name_correspondence(classification, playback)
    assert result["status"] == "unresolved_conflict"
    assert result["conflicts"][0]["track_names"] == ["Voice"]


def test_unrecognized_track_label_is_not_mistaken_for_a_different_instrument():
    classification = {"roles": [{"part_id": "P1", "kind": "guitar", "sounding": True}]}
    playback = {"sounding_groups": [{"track_names": ["Part 1"], "MXL_part_ids": ["P1"], "note_on_count": 5}]}
    assert review_midi_name_correspondence(classification, playback)["status"] == "consistent"


def test_new_typed_plucked_track_names_match_the_real_role_and_voice_template_stays_pending():
    classification = {"roles": [{"part_id": "P2", "kind": "laud", "sounding": True}]}
    playback = {"sounding_groups": [{"track_names": ["Laúd"], "MXL_part_ids": ["P2"], "note_on_count": 5}]}
    assert review_midi_name_correspondence(classification, playback)["status"] == "consistent"
    playback["sounding_groups"][0]["track_names"] = ["Voice"]
    assert review_midi_name_correspondence(classification, playback)["status"] == "unresolved_conflict"


@pytest.mark.parametrize("label", ["contact@example.com", "email: Somebody", "https://example.com/score", "/Users/name/file", "x.pdf", "a" * 64])
def test_unsafe_part_transcriptions_stay_private(label):
    original = {"parts": [{"name": "Guitar"}, {"name": label}]}
    before = deepcopy(original)
    result = public_part_labels(original)
    assert label not in result["text"]
    assert result["omitted_private_labels"] == 1
    assert original == before


def work():
    return {"id": "musescore:654", "title_en": "Source Work", "composer_en": "F. Sor", "source_url": "https://musescore.com/user/321/scores/654",
            "metadata": {"scope_status": "pending_review", "instrumentation": "Guitar"}}


def classification(status="mxl_scope_verified"):
    return {"status": status, "topic_id": "solo" if status == "mxl_scope_verified" else "guitar_unspecified",
            "instrumentation": "Guitar solo", "instrumentation_zh": "吉他独奏", "guitar_player_count": 1 if status == "mxl_scope_verified" else None,
            "ensemble_player_count": 1 if status == "mxl_scope_verified" else None, "issues": [], "omitted_empty_parts": []}


def test_file_title_conflict_downgrades_native_topic_and_keeps_visible_warning():
    decision = {"status": "identity_conflict", "actual_pdf_titles": ["Different Work"], "source_title": "Source Work"}
    result = make_projection(work(), classification(), {"parts": [{"name": "Guitar"}]}, decision,
        {name: {"sha256": "a" * 64, "size": 10} for name in ("PDF", "MUSICXML", "MIDI")})
    assert result["review"]["status"] == "file_reviewed_uncertain"
    assert result["review"]["topic_id"] == "guitar_unspecified"
    assert result["review"]["file_title"] == "Different Work"
    assert "谱题" in result["review"]["file_identity_note"]


def test_unsafe_actual_file_title_preserves_conflict_without_exposing_contact_text():
    decision = {"status": "identity_conflict", "actual_pdf_titles": ["contact@example.com"], "source_title": "Source Work"}
    result = make_projection(work(), classification(), {"parts": [{"name": "Guitar"}]}, decision,
        {name: {"sha256": "a" * 64, "size": 10} for name in ("PDF", "MUSICXML", "MIDI")})
    assert "contact@example.com" not in str(result)
    assert result["review"]["file_identity_note"]


def test_scope_uncertain_remains_uncertain_after_all_formats_are_present():
    result = make_projection(work(), classification("mxl_scope_uncertain"), {"parts": [{"name": "Guitar"}]},
        {"status": "consistent", "actual_pdf_titles": ["Source Work"]},
        {name: {"sha256": "a" * 64, "size": 10} for name in ("PDF", "MUSICXML", "MIDI")})
    assert result["review"]["status"] == "file_reviewed_uncertain"
    assert result["review"]["guitar_player_count"] is None


def project_with_case(case):
    actual = classification()
    if case is not None:
        actual["reviewed_case"] = case
    return make_projection(work(), actual, {"parts": [{"name": "Guitar"}]},
        {"status": "consistent", "actual_pdf_titles": ["Source Work"]},
        {name: {"sha256": "a" * 64, "size": 10} for name in ("PDF", "MUSICXML", "MIDI")})


def test_only_explicit_public_note_from_reviewed_part_decision_enters_summary():
    case = {"part_decisions": {"P1": {"kind": "guitar", "resolved": True}},
            "note": "Full private evidence, archive path x.pdf and " + "a" * 64,
            "basis": ["Private detailed ledger."],
            "public_note": "PDF与MXL分部不同，保留格式差异。"}
    before = deepcopy(case)
    result = project_with_case(case)
    assert result["review"]["summary"].endswith(" " + case["public_note"])
    assert case["note"] not in str(result)
    assert case["basis"][0] not in str(result)
    assert case == before


@pytest.mark.parametrize("case", [None, {}, {"note": "Private note."},
    {"public_note": "Uncontrolled note."}, {"part_decisions": {}, "public_note": "Uncontrolled note."},
    {"part_decisions": {"P1": {}}, "public_note": None}, {"part_decisions": {"P1": {}}, "public_note": ""}])
def test_absent_or_ineligible_public_note_leaves_default_summary_unchanged(case):
    assert project_with_case(case) == project_with_case(None)


@pytest.mark.parametrize("note", [" ", "contact@example.com", "email: Somebody", "https://example.com/score",
    "/Users/name/file", "x.pdf", "a" * 64, "x" * 1801, "line\x00break", ["note"], {}, True, 0])
def test_invalid_nonempty_reviewed_public_note_fails_closed(note):
    with pytest.raises(ValueError, match="public instrumentation"):
        project_with_case({"part_decisions": {"P1": {"kind": "guitar", "resolved": True}}, "public_note": note})


def test_exact_file_title_semantic_override_keeps_automatic_conflict_and_all_original_fields():
    native = work()
    actual = {"file_sha256": "a" * 64, "parts": [{"part_id": "P1", "name": "Guitar"}]}
    case = {**{key: native[key] for key in ("id", "title_en", "composer_en", "source_url")},
        "mxl_sha256": "a" * 64, "pdf_sha256": "b" * 64, "part_names": ["Guitar"],
        "identity_review_override": {"status": "compatible_title_variant", "actual_pdf_titles": ["Reviewed Title"]},
        "note": "Printed heading is the shortened native title.", "basis": "Actual PDF heading reviewed."}
    automatic = {"status": "identity_conflict", "actual_pdf_titles": ["Heuristic title"], "source_title": native["title_en"]}
    before = deepcopy((case, native, actual, automatic))
    result = apply_identity_review(case, native, actual, "b" * 64, automatic)
    assert result["status"] == "compatible_title_variant"
    assert result["automatic_review"]["status"] == "identity_conflict"
    assert result["actual_pdf_titles"] == ["Reviewed Title"]
    assert (case, native, actual, automatic) == before
    with pytest.raises(ValueError, match="PDF"):
        apply_identity_review(case, native, actual, "c" * 64, automatic)


@pytest.mark.parametrize("label", ["PDF", "MIDI", "MUSICXML"])
@pytest.mark.parametrize("scope_ids,valid", [
    (["musescore:1"], True),
    (["musescore:1", "musescore:2", "musescore:3"], True),
    (["musescore:1", "musescore:2"], False),
    (["musescore:1", "musescore:999"], False),
    (["musescore:2", "musescore:3"], False),
    (["musescore:1", "musescore:1"], False),
])
def test_format_journal_scope_is_exact_accepted_or_exact_plan(label, scope_ids, valid):
    journal = {"status": "complete", "format": label, "plan_sha256": "plan", "configuration_sha256": "config",
        "scope_ids": scope_ids, "records": {identity: {"status": "missing"} for identity in scope_ids}}
    valid = valid and (label != "MUSICXML" or len(scope_ids) == 3)
    arguments = {"plan_ids": ["musescore:1", "musescore:2", "musescore:3"],
        "accepted_ids": ["musescore:1"], "plan_sha256": "plan", "configuration_sha256": "config"}
    if valid:
        validate_extraction_journal(journal, label, **arguments)
        journal["records"]["musescore:999"] = {"status": "missing"}
    with pytest.raises(ValueError, match="scope/plan incomplete"):
        validate_extraction_journal(journal, label, **arguments)


@pytest.mark.parametrize("workers", [0, -1, 9, True, 1.5])
def test_scope_workers_are_controlled_before_any_file_is_read(tmp_path, workers):
    from review_musescore_expansion import review_scope
    with pytest.raises(ValueError, match="workers"):
        review_scope(tmp_path, workers=workers)


@pytest.mark.parametrize("workers", [0, -1, 5, True, 1.5])
def test_final_workers_are_controlled_before_any_file_is_read(tmp_path, workers):
    from review_musescore_expansion_final import review_final
    with pytest.raises(ValueError, match="workers"):
        review_final(tmp_path, workers=workers)


@pytest.mark.parametrize("extra_private_formats", [False, True])
@pytest.mark.parametrize("inherited_midi_template", [False, True, "instrument_name", "lyric_text"])
def test_real_three_format_review_binds_plan_scope_assets_and_native_projection(tmp_path, extra_private_formats, inherited_midi_template):
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    from review_musescore_expansion import review_scope
    from review_musescore_expansion_final import review_final

    repo = Path(__file__).resolve().parents[1]
    methods = ["scripts/review_musescore_expansion_final.py", "scripts/review_musescore_expansion.py",
        "scripts/score_instrumentation.py", "scripts/score_pdf_evidence.py", "scripts/score_midi_crosscheck.py",
        "scripts/review_musescore_instrumentation.py", "scripts/source_adapters/pdmx_formats.py", "scripts/catalog_instrumentation.py"]
    for name in methods:
        destination = tmp_path / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(repo / name, destination)
    base = tmp_path / "sources/musescore/expansion"
    base.mkdir(parents=True)
    config_path = tmp_path / "config/musescore_pdmx_expansion.json"
    config_path.parent.mkdir()
    config_path.write_text(json.dumps({"files": {code + ".tar.gz": {"sha256": "c" * 64} for code in ("pdf", "mxl", "mid")}}))
    config_sha = hashlib.sha256(config_path.read_bytes()).hexdigest()
    mxl_path, pdf_path, midi_path = (tmp_path / "fixture.mxl", tmp_path / "fixture.pdf", tmp_path / "fixture.mid")
    part_name = "Steel Guitar" if inherited_midi_template is True else "Guitar"
    instrument_name = "" if inherited_midi_template is True else "Voice" if inherited_midi_template == "instrument_name" else "Classical Guitar"
    with zipfile.ZipFile(mxl_path, "w") as archive:
        archive.writestr("META-INF/container.xml", '<container><rootfiles><rootfile full-path="score.xml"/></rootfiles></container>')
        archive.writestr("score.xml", f'''<score-partwise version="4.0"><work><work-title>Actual Piece</work-title></work><part-list><score-part id="P1"><part-name>{part_name}</part-name><score-instrument id="I1"><instrument-name>{instrument_name}</instrument-name></score-instrument><midi-instrument id="I1"><midi-channel>1</midi-channel><midi-program>25</midi-program></midi-instrument></score-part></part-list><part id="P1"><measure number="1"><attributes><divisions>1</divisions><clef><sign>G</sign><line>2</line></clef></attributes><note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration></note></measure></part></score-partwise>''')
    writer = PdfWriter()
    page = writer.add_blank_page(width=600, height=800)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    stream = DecodedStreamObject()
    content = b"BT /F1 24 Tf 180 740 Td (Actual Piece) Tj ET"
    if inherited_midi_template == "lyric_text":
        content += b"\n100 520 m 500 520 l S\n100 525 m 500 525 l S\n100 530 m 500 530 l S\n100 535 m 500 535 l S\n100 540 m 500 540 l S\n100 520 m 100 540 l S\nBT /F1 12 Tf 250 505 Td (Drum) Tj ET"
    stream.set_data(content)
    page[NameObject("/Contents")] = writer._add_object(stream)
    with pdf_path.open("wb") as handle:
        writer.write(handle)
    track_name = ("Voice" if inherited_midi_template == "instrument_name" else part_name).encode("utf-8")
    track = b"\x00\xff\x03" + bytes([len(track_name)]) + track_name + b"\x00\xc0\x18\x00\x90\x3c\x64\x01\x80\x3c\x00\x00\xff\x2f\x00"
    midi_path.write_bytes(b"MThd" + struct.pack(">IHHH", 6, 0, 1, 480) + b"MTrk" + struct.pack(">I", len(track)) + track)
    native = work()
    native["title_en"] = "Actual Piece"
    native["metadata"]["pdmx_csv_transcription"] = {code: f"./{code}/1/fixture.{extension}" for code, extension in (("pdf", "pdf"), ("mxl", "mxl"), ("mid", "mid"))}
    pending = deepcopy(native)
    pending["id"] = "musescore:655"
    second = deepcopy(native)
    second["id"] = "musescore:656"
    second["source_url"] = "https://musescore.com/user/321/scores/656"
    plan = {"status": "prepared", "configuration_sha256": config_sha, "works": [native, pending, second]}
    plan_path = base / "plan.json"
    plan_path.write_text(json.dumps(plan))
    plan_sha = hashlib.sha256(plan_path.read_bytes()).hexdigest()
    assets = {}
    for label, code, extension, path in (("PDF", "pdf", "pdf", pdf_path), ("MUSICXML", "mxl", "mxl", mxl_path), ("MIDI", "mid", "mid", midi_path)):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        relative = f"sources/musescore/objects/{digest}.{extension}"
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
        asset = {"format": label, "status": "verified", "size": path.stat().st_size, "sha256": digest,
                 "local_path": relative, "archive_member": f"{code}/1/fixture.{extension}", "archive_sha256": "c" * 64}
        assets[label] = asset
        journal = {"status": "complete", "format": label, "plan_sha256": plan_sha, "configuration_sha256": config_sha,
                   "scope_ids": [native["id"], second["id"]], "records": {
                       identity: {"status": "verified", "asset": asset} for identity in (native["id"], second["id"])}}
        if label == "MUSICXML" or extra_private_formats:
            journal["scope_ids"].append(pending["id"])
            journal["records"][pending["id"]] = {"status": "missing", "reason": "fixture_missing_member"}
        (base / (code + "-extraction.json")).write_text(json.dumps(journal))
    if inherited_midi_template:
        from catalog_instrumentation import per_record_guard
        from score_pdf_evidence import read_pdf_evidence
        reviewed = []
        for original in (native, second):
            entry = {**{key: original[key] for key in ("id", "title_en", "composer_en", "source_url")},
                "native_record_sha256": per_record_guard(original),
                "mxl_sha256": assets["MUSICXML"]["sha256"], "part_names": [part_name],
                "pdf_sha256": assets["PDF"]["sha256"], "midi_sha256": assets["MIDI"]["sha256"],
                "part_decisions": {"P1": {"kind": "guitar", "resolved": True}},
                "public_note": "谱面与播放模板名称不同，保留实际分部核对结论。",
                "note": "Actual fixture PDF and notation confirm a guitar; MIDI retains the original template name.",
                "basis": ["Actual PDF/MXL/MIDI fixture bytes, not a GM program inference."]}
            if inherited_midi_template is True:
                entry["midi_part_name_corrections"] = ["P1"]
            elif inherited_midi_template == "instrument_name":
                entry["midi_instrument_name_corrections"] = ["P1"]
            else:
                label = next(row for row in read_pdf_evidence(pdf_path)["first_system_instrument_labels"] if row["text"] == "Drum")
                entry["pdf_noninstrument_labels"] = [{**label, "note": "Exact fixture lyric under the staff, not an instrument label."}]
            reviewed.append(entry)
        review_path = tmp_path / "metadata/instrumentation/musescore_expansion_reviewed.json"
        review_path.parent.mkdir(parents=True)
        review_path.write_text(json.dumps({"schema_version": 1, "entries": reviewed}))
    scope = review_scope(tmp_path, workers=1)
    assert scope["accepted_ids"] == [native["id"], second["id"]]
    parallel_scope = review_scope(tmp_path, workers=2)
    assert {key: value for key, value in scope.items() if key != "checked_at"} == {
        key: value for key, value in parallel_scope.items() if key != "checked_at"}
    final = review_final(tmp_path, workers=1)
    parallel_final = review_final(tmp_path, workers=2)
    assert {key: value for key, value in final.items() if key != "checked_at"} == {
        key: value for key, value in parallel_final.items() if key != "checked_at"}
    assert final["status"] == "complete"
    assert final["summary"]["new_three_format_records"] == 2
    assert final["works"][0]["review"]["topic_id"] == "solo"
    assert final["works"][0]["review"]["status"] == "file_verified"
    summary = final["works"][0]["review"]["summary"]
    assert ("谱面与播放模板名称不同，保留实际分部核对结论。" in summary) == bool(inherited_midi_template)
    assert "Actual fixture PDF" not in summary
    assert final["works"][0]["title_en"] == "Actual Piece"
    assert final["works"][0]["assets"] == {label: {key: asset[key] for key in ("sha256", "size")} for label, asset in assets.items()}
    if inherited_midi_template is True or inherited_midi_template == "instrument_name":
        actual_record = final["records"][native["id"]]
        assert actual_record["midi_crosscheck"]["status"] == "consistent"
        assert actual_record["midi_name_review"]["status"] == "explained_name_difference"
        assert actual_record["midi_name_review"]["automatic_review"]["status"] == "unresolved_conflict"
        assert actual_record["midi_name_review"]["observations"][0]["track_names"] == [track_name.decode("utf-8")]
    elif inherited_midi_template == "lyric_text":
        labels = final["records"][native["id"]]["pdf_instrument_review"]
        assert labels["status"] == "explained_noninstrument_text"
        assert labels["observations"][0]["status"] == "explained_lyric_text"
        assert labels["automatic_review"]["status"] == "unresolved_conflict"
    assert set(final["records"]) == {native["id"], second["id"]}
    assert pending["id"] not in {row["id"] for row in final["works"]}
    assert json.loads(plan_path.read_text()) == plan
