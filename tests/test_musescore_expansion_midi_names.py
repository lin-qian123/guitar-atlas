from copy import deepcopy

import pytest

import review_musescore_expansion_final as final
from catalog_instrumentation import per_record_guard


def exact_name_case():
    work = {"id": "musescore:4917609", "title_en": "Russian Folk Song", "composer_en": "",
            "source_url": "https://musescore.com/user/19141156/scores/4917609"}
    mxl = {"file_sha256": "a" * 64, "parts": [{"part_id": "P1", "name": "Steel Guitar"}]}
    classification = {"roles": [{"part_id": "P1", "kind": "guitar", "sounding": True}]}
    playback = {"status": "consistent", "sounding_groups": [{"track_names": ["Steel Guitar"],
        "MXL_part_ids": ["P1"], "program_0based": 24, "note_on_count": 137}]}
    case = {**work, "mxl_sha256": mxl["file_sha256"], "part_names": ["Steel Guitar"],
        "pdf_sha256": "b" * 64, "midi_sha256": "c" * 64, "midi_part_name_corrections": ["P1"],
        "part_decisions": {"P1": {"kind": "guitar", "resolved": True}},
        "note": "Actual PDF confirms a guitar role; the MIDI repeats the original MXL template name.",
        "basis": ["Exact actual PDF/MXL/MIDI evidence."]}
    return case, work, mxl, classification, playback


def apply(case, work, mxl, classification, playback):
    automatic = final.review_midi_name_correspondence(classification, playback)
    return final.apply_midi_part_name_corrections(case, work, mxl, classification, automatic,
        midi_sha256="c" * 64, pdf_sha256="b" * 64)


def test_exact_inherited_midi_name_is_explained_without_changing_any_original_evidence():
    arguments = exact_name_case()
    before = deepcopy(arguments)
    automatic = final.review_midi_name_correspondence(arguments[3], arguments[4])
    result = apply(*arguments)
    assert automatic["status"] == "unresolved_conflict"
    assert result["status"] == "explained_name_difference"
    assert result["conflicts"] == []
    assert result["automatic_review"] == automatic
    row = result["observations"][0]
    assert row["status"] == "explained_inherited_template_name"
    assert row["automatic_observation"] == automatic["observations"][0]
    assert row["track_names"] == ["Steel Guitar"]
    assert row["named_kinds"] == ["electric_guitar"]
    assert row["MXL_role_kinds"] == ["guitar"]
    assert arguments == before


@pytest.mark.parametrize("case_value", [None, {}])
def test_no_explicit_correction_keeps_the_automatic_result_exact(case_value):
    _, work, mxl, classification, playback = exact_name_case()
    automatic = final.review_midi_name_correspondence(classification, playback)
    result = final.apply_midi_part_name_corrections(case_value, work, mxl, classification, automatic,
        midi_sha256="c" * 64, pdf_sha256="b" * 64)
    assert result == automatic
    assert result is not automatic


def test_other_name_and_playback_conflicts_remain_unresolved_and_unchanged():
    case, work, mxl, classification, playback = exact_name_case()
    mxl["parts"].append({"part_id": "P2", "name": "Guitar"})
    case["part_names"].append("Guitar")
    classification["roles"].append({"part_id": "P2", "kind": "guitar", "sounding": True})
    playback["status"] = "unresolved_conflict"
    playback["sounding_groups"].append({"track_names": ["Voice"], "MXL_part_ids": ["P2"], "program_0based": 52})
    before = deepcopy(playback)
    automatic = final.review_midi_name_correspondence(classification, playback)
    result = apply(case, work, mxl, classification, playback)
    assert result["status"] == "unresolved_conflict"
    assert result["conflicts"] == [automatic["observations"][1]]
    assert result["observations"][1] == automatic["observations"][1]
    assert result["automatic_review"] == automatic
    assert playback == before


@pytest.mark.parametrize("key,value", [
    ("midi_sha256", "d" * 64), ("midi_sha256", None), ("midi_sha256", "bad"),
    ("pdf_sha256", "d" * 64), ("pdf_sha256", None),
    ("midi_part_name_corrections", []), ("midi_part_name_corrections", ["P1", "P1"]),
    ("midi_part_name_corrections", ["P2"]), ("midi_part_name_corrections", ["P1", 1]),
    ("midi_part_name_corrections", "P1"), ("midi_part_name_corrections", None),
])
def test_stale_or_invalid_correction_envelope_fails(key, value):
    case, *rest = exact_name_case()
    case[key] = value
    with pytest.raises(ValueError):
        apply(case, *rest)


@pytest.mark.parametrize("decision", [{}, {"kind": "guitar"}, {"resolved": True},
    {"resolved": False, "kind": "guitar"}, {"resolved": 1, "kind": "guitar"},
    {"resolved": True, "kind": "unknown"}, {"resolved": True, "kind": "piano"},
    {"resolved": True, "kind": "guitar", "role_active": False}])
def test_only_an_exact_resolved_actual_part_kind_can_explain_a_template_name(decision):
    case, *rest = exact_name_case()
    case["part_decisions"]["P1"] = decision
    with pytest.raises(ValueError):
        apply(case, *rest)


@pytest.mark.parametrize("names", [[], [""], [" "], ["steel guitar"], ["Steel Guitar "],
    ["Steel Guitar", "Voice"], ["Steel Guitar", None], ["Guitar"]])
def test_every_track_name_must_equal_the_full_original_mxl_part_name(names):
    case, work, mxl, classification, playback = exact_name_case()
    playback["sounding_groups"][0]["track_names"] = names
    with pytest.raises(ValueError):
        apply(case, work, mxl, classification, playback)


@pytest.mark.parametrize("part_ids", [[], ["P2"], ["P1", "P2"], ["P1", "P1"]])
def test_a_template_correction_requires_an_exact_single_part_observation(part_ids):
    case, work, mxl, classification, playback = exact_name_case()
    playback["sounding_groups"][0]["MXL_part_ids"] = part_ids
    with pytest.raises(ValueError):
        apply(case, work, mxl, classification, playback)


def test_every_matching_group_is_checked_instead_of_clearing_a_whole_part():
    case, work, mxl, classification, playback = exact_name_case()
    playback["sounding_groups"].append({"track_names": ["Voice"], "MXL_part_ids": ["P1"]})
    with pytest.raises(ValueError):
        apply(case, work, mxl, classification, playback)


def test_unused_correction_and_changed_native_or_mxl_guards_fail():
    for key, value in (("id", "musescore:1"), ("mxl_sha256", "e" * 64), ("part_names", ["Guitar"])):
        case, *rest = exact_name_case()
        case[key] = value
        with pytest.raises(ValueError):
            apply(case, *rest)
    case, work, mxl, classification, playback = exact_name_case()
    classification["roles"][0]["kind"] = "electric_guitar"
    case["part_decisions"]["P1"]["kind"] = "electric_guitar"
    with pytest.raises(ValueError):
        apply(case, work, mxl, classification, playback)


def instrument_case():
    case, work, mxl, classification, playback = exact_name_case()
    mxl["parts"][0].update(name="Laud", note_count=309, score_instruments=[{"id": "I1", "name": "Voice"}],
        used_instrument_ids=[], note_instrument_counts={})
    classification["roles"][0]["kind"] = "laud"
    playback["sounding_groups"][0]["track_names"] = ["Voice"]
    case.update(part_names=["Laud"], native_record_sha256=per_record_guard(work),
        part_decisions={"P1": {"kind": "laud", "resolved": True}}, midi_instrument_name_corrections=case.pop("midi_part_name_corrections"))
    return case, work, mxl, classification, playback


def apply_instrument(case, work, mxl, classification, playback):
    return final.apply_midi_instrument_name_corrections(case, work, mxl, classification,
        final.review_midi_name_correspondence(classification, playback), midi_sha256="c" * 64, pdf_sha256="b" * 64)


def test_unique_used_score_instrument_name_has_its_own_explicit_explanation():
    args = instrument_case()
    before = deepcopy(args)
    result = apply_instrument(*args)
    assert result["status"] == "explained_name_difference"
    assert result["observations"][0]["status"] == "explained_inherited_instrument_name"
    assert result["observations"][0]["track_names"] == ["Voice"]
    assert result["observations"][0]["automatic_observation"]["status"] == "conflict"
    assert result["automatic_review"]["status"] == "unresolved_conflict"
    assert args == before


def test_unused_declaration_cannot_explain_a_track_name_but_one_fully_assigned_used_instrument_can():
    case, work, mxl, classification, playback = instrument_case()
    part = mxl["parts"][0]
    part["score_instruments"].append({"id": "I2", "name": "Piano"})
    with pytest.raises(ValueError):
        apply_instrument(case, work, mxl, classification, playback)
    part.update(used_instrument_ids=["I1"], note_instrument_counts={"I1": 309})
    assert apply_instrument(case, work, mxl, classification, playback)["status"] == "explained_name_difference"
    part.update(used_instrument_ids=["I2"], note_instrument_counts={"I2": 309})
    with pytest.raises(ValueError):
        apply_instrument(case, work, mxl, classification, playback)


@pytest.mark.parametrize("mutation", ["missing_native", "stale_native", "missing_midi", "missing_pdf", "duplicate_part",
    "foreign_part", "unresolved_kind", "empty_instrument", "foreign_used_id", "two_used_ids", "no_actual_notes", "different_literal_name"])
def test_instrument_name_corrections_require_every_exact_actual_guard(mutation):
    case, work, mxl, classification, playback = instrument_case()
    part = mxl["parts"][0]
    if mutation == "missing_native": case.pop("native_record_sha256")
    elif mutation == "stale_native": case["native_record_sha256"] = "d" * 64
    elif mutation == "missing_midi": case.pop("midi_sha256")
    elif mutation == "missing_pdf": case.pop("pdf_sha256")
    elif mutation == "duplicate_part": case["midi_instrument_name_corrections"] = ["P1", "P1"]
    elif mutation == "foreign_part": case["midi_instrument_name_corrections"] = ["P2"]
    elif mutation == "unresolved_kind": case["part_decisions"]["P1"]["resolved"] = False
    elif mutation == "empty_instrument": part["score_instruments"][0]["name"] = ""
    elif mutation == "foreign_used_id": part["used_instrument_ids"] = ["I2"]
    elif mutation == "two_used_ids":
        part["score_instruments"].append({"id": "I2", "name": "Voice"})
        part.update(used_instrument_ids=["I1", "I2"], note_instrument_counts={"I1": 300, "I2": 9})
    elif mutation == "no_actual_notes": part["note_count"] = 0
    elif mutation == "different_literal_name": part["score_instruments"][0]["name"] = "voice"
    with pytest.raises(ValueError):
        apply_instrument(case, work, mxl, classification, playback)


def pdf_lyric_case():
    case, work, mxl, _, _ = exact_name_case()
    case.pop("midi_part_name_corrections")
    case["native_record_sha256"] = per_record_guard(work)
    label = {"text": "Drum", "bbox": [304.529, 304.404, 328.263, 315.7], "note": "Exact word in the German lyric below part III, not a percussion label."}
    case["pdf_noninstrument_labels"] = [label]
    row = {"text": label["text"], "bbox": deepcopy(label["bbox"]), "kind": "drumset", "status": "unrepresented_named_instrument"}
    automatic = {"status": "unresolved_conflict", "observations": [row], "conflicts": [deepcopy(row)]}
    return case, work, mxl, automatic


def test_exact_pdf_lyric_observation_is_explained_with_its_raw_conflict_intact():
    args = pdf_lyric_case()
    before = deepcopy(args)
    result = final.apply_pdf_noninstrument_labels(*args, pdf_sha256="b" * 64)
    assert result["status"] == "explained_noninstrument_text"
    assert result["observations"][0]["status"] == "explained_lyric_text"
    assert result["observations"][0]["automatic_observation"] == args[3]["observations"][0]
    assert result["automatic_review"] == args[3]
    assert result["conflicts"] == []
    assert args == before


def test_pdf_lyric_explanation_keeps_every_other_instrument_conflict():
    case, work, mxl, automatic = pdf_lyric_case()
    other = {"text": "Trumpet", "bbox": [10, 20, 30, 40], "kind": "trumpet", "status": "unrepresented_named_instrument"}
    automatic["observations"].append(other)
    automatic["conflicts"].append(deepcopy(other))
    result = final.apply_pdf_noninstrument_labels(case, work, mxl, automatic, pdf_sha256="b" * 64)
    assert result["status"] == "unresolved_conflict"
    assert result["conflicts"] == [other]
    assert result["observations"][1] == other


@pytest.mark.parametrize("mutation", ["missing_native", "stale_native", "missing_pdf", "stale_pdf", "stale_mxl",
    "duplicate", "empty_labels", "different_text", "rounded_bbox", "empty_note", "extra_key", "nan_bbox",
    "boolean_bbox", "short_bbox", "no_match", "consistent_row", "duplicate_observation"])
def test_pdf_lyric_explanations_fail_on_stale_foreign_or_ambiguous_evidence(mutation):
    case, work, mxl, automatic = pdf_lyric_case()
    label = case["pdf_noninstrument_labels"][0]
    if mutation == "missing_native": case.pop("native_record_sha256")
    elif mutation == "stale_native": case["native_record_sha256"] = "d" * 64
    elif mutation == "missing_pdf": case.pop("pdf_sha256")
    elif mutation == "stale_pdf": case["pdf_sha256"] = "d" * 64
    elif mutation == "stale_mxl": case["mxl_sha256"] = "d" * 64
    elif mutation == "duplicate": case["pdf_noninstrument_labels"].append(deepcopy(label))
    elif mutation == "empty_labels": case["pdf_noninstrument_labels"] = []
    elif mutation == "different_text": label["text"] = "drum"
    elif mutation == "rounded_bbox": label["bbox"][0] = 304.53
    elif mutation == "empty_note": label["note"] = ""
    elif mutation == "extra_key": label["allow_other_conflicts"] = True
    elif mutation == "nan_bbox": label["bbox"][0] = float("nan")
    elif mutation == "boolean_bbox": label["bbox"][0] = True
    elif mutation == "short_bbox": label["bbox"].pop()
    elif mutation == "no_match": automatic["observations"] = []
    elif mutation == "consistent_row": automatic["observations"][0]["status"] = "consistent"
    elif mutation == "duplicate_observation": automatic["observations"].append(deepcopy(automatic["observations"][0]))
    with pytest.raises(ValueError):
        final.apply_pdf_noninstrument_labels(case, work, mxl, automatic, pdf_sha256="b" * 64)
