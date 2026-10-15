from copy import deepcopy

import pytest

from review_musescore_expansion import review_mxl_scope, classify_expansion_parts, LABELS


@pytest.mark.parametrize("label,kind,family", [
    ("Bagpipe", "bagpipe", "woodwinds"), ("Mandola", "mandola", "plucked"),
    ("Tenor Mandola", "mandola", "plucked"), ("Contra Guitar", "contra_guitar", "plucked"),
    ("Kontragitarre", "contra_guitar", "plucked"), ("Balalaika", "balalaika", "plucked"),
    ("Tin Whistle", "tin_whistle", "woodwinds"), ("D Tin Whistle", "tin_whistle", "woodwinds")])
def test_exact_additional_instrument_types_do_not_collapse_into_guitar_or_mandolin(label, kind, family):
    from review_musescore_expansion import expansion_kind
    assert expansion_kind(label) == kind
    assert LABELS[kind][2] == family
    assert kind not in {"guitar", "bass_guitar", "mandolin"}
    result = review_mxl_scope(evidence(part("P1"), part("P2", name=label, instrument=label)))
    assert result["status"] == "accepted"
    assert result["classification"]["topic_id"] == ("duo" if kind == "contra_guitar" else family)
    assert result["classification"]["guitar_player_count"] == (2 if kind == "contra_guitar" else 1)


def test_contra_guitar_stays_a_distinct_written_type_and_counts_in_the_guitar_family():
    result = review_mxl_scope(evidence(part("P1", name="Violin", instrument="Violin"),
        part("P2", name="Violin", instrument="Violin"), part("P3"),
        part("P4", name="Contra Guitar", instrument="Contra Guitar")))
    assert result["status"] == "accepted"
    review = result["classification"]
    assert review["topic_id"] == "strings"
    assert review["guitar_player_count"] == 2 and review["ensemble_player_count"] == 4
    assert review["roles"][3]["kind"] == "contra_guitar"


def part(identity="P1", name="Guitar", instrument="Classical Guitar", program=24, **extra):
    return {"part_id": identity, "name": name, "score_instruments": [{"id": "i", "name": instrument}],
            "midi_instruments": [{"id": "i", "program_0based": program}], "used_instrument_ids": [],
            "note_count": 5, "normalized_note_count": 5, "normalization_status": "complete",
            "normalized_notes_sha256": identity, "clefs": [{"sign": "G"}], "staff_details": [],
            "grace_note_count": 0, "harmony_count": 0, "frame_count": 0, "slash_count": 0, **extra}


def evidence(*parts):
    return {"file_sha256": "a" * 64, "file_bytes": 100, "parts": list(parts)}


def sequences(*pairs):
    return {"file_sha256": "a" * 64, "parts": [
        {"part_id": identity, "all_events": events, "view_sequence_complete": True, "view_sequence_blockers": [],
         "event_count": len(events), "signature_sha256": identity} for identity, events in pairs]}


def test_actual_mxl_solo_has_only_mxl_scope_status_and_original_labels():
    original = evidence(part())
    before = deepcopy(original)
    result = review_mxl_scope(original)
    assert result["status"] == "accepted"
    classification = result["classification"]
    assert classification["status"] == "mxl_scope_verified"
    assert classification["review_stage"] == "mxl_scope_only"
    assert classification["topic_id"] == "solo"
    assert classification["guitar_player_count"] == 1
    assert classification["roles"][0]["name"] == "Guitar"
    assert original == before


def test_harmony_only_guitar_is_active_but_all_rest_placeholder_is_not():
    result = review_mxl_scope(evidence(part(note_count=0, normalized_note_count=0, harmony_count=40),
                                      part("P2", "Guitar 2", note_count=0, normalized_note_count=0)))
    assert result["status"] == "accepted"
    assert result["classification"]["guitar_player_count"] == 1
    assert result["classification"]["omitted_empty_parts"][0]["part_id"] == "P2"


def test_multilingual_abbreviations_are_reviewed_names_not_gm_inferences():
    result = review_mxl_scope(evidence(part(name="Gtr.", instrument="Guitarra acústica")))
    assert result["status"] == "accepted"
    assert result["classification"]["part_decisions"]["P1"]["kind"] == "guitar"
    result = review_mxl_scope(evidence(part(name="Unidentified part", instrument="Unidentified instrument")))
    assert result["status"] == "pending"
    assert result["classification"]["guitar_player_count"] is None


def test_actual_instrument_conflict_is_pending_not_guitar_scope():
    result = review_mxl_scope(evidence(part(name="Violin", instrument="Classical Guitar")))
    assert result["status"] == "pending"
    assert "P1:part_instrument_name_conflict" in result["classification"]["issues"]


@pytest.mark.parametrize("name,instrument,program", [
    ("Electric Guitar", "Electric Guitar", 27), ("Bass Guitar", "Bass Guitar", 33),
    ("Voice", "Voice", 52), ("Synthesizer", "Synthesizer", 80), ("Slide Guitar", "Slide Guitar", 26),
])
def test_active_explicit_scope_exceptions_are_excluded(name, instrument, program):
    result = review_mxl_scope(evidence(part(), part("P2", name, instrument, program)))
    assert result["status"] == "excluded"
    assert result["reason"] == "active_excluded_instrument"


@pytest.mark.parametrize("name,program", [("Electric Guitar (jazz)", 26), ("Electric Guitar (clean)", 27),
    ("Electric Guitar (muted)", 28), ("Overdriven Guitar", 29), ("Distortion Guitar", 30),
    ("Bass Guitar (finger)", 33), ("Electric Bass (pick)", 34), ("Slap Bass 1", 36)])
def test_complete_standard_electric_and_bass_names_are_explicit_exclusions(name, program):
    result = review_mxl_scope(evidence(part(), part("P2", name, name, program)))
    assert result["status"] == "excluded"
    assert result["reason"] == "active_excluded_instrument"


def test_acoustic_patch_and_electric_name_conflict_requires_review():
    result = review_mxl_scope(evidence(part(name="Electric Guitar", instrument="Electric Guitar", program=24)))
    assert result["status"] == "pending"
    assert any("guitar_patch_label_conflict" in issue for issue in result["classification"]["issues"])
    result = review_mxl_scope(evidence(part(name="Guitar", instrument="Classical Guitar", program=27)))
    assert result["status"] == "accepted"
    assert result["classification"]["status"] == "mxl_scope_uncertain"
    assert result["classification"]["guitar_player_count"] is None


def test_plain_piano_patch_does_not_override_explicit_guitar_labels():
    assert review_mxl_scope(evidence(part(program=0)))["status"] == "accepted"


def test_no_named_guitar_is_excluded_and_unknown_extra_role_never_gets_forced_people():
    assert review_mxl_scope(evidence(part(name="Piano", instrument="Piano", program=0)))["status"] == "excluded"
    result = review_mxl_scope(evidence(part(), part("P2", "Melody", "Unknown", 0)))
    assert result["status"] == "pending"
    assert result["classification"]["guitar_player_count"] is None
    assert result["classification"]["ensemble_player_count"] is None


def test_standard_tab_view_needs_complete_exact_notes_including_grace():
    normal, tab = part(), part("P2", "Guitar TAB", clefs=[{"sign": "TAB"}])
    notes = [[0, "0", "1", 60, False]]
    result = review_mxl_scope(evidence(normal, tab), sequences(("P1", notes), ("P2", notes)))
    assert result["status"] == "accepted"
    assert result["classification"]["topic_id"] == "solo"
    assert result["classification"]["duplicate_views"][0]["part_id"] == "P2"
    grace = notes + [[0, "0", "0", 62, True]]
    result = review_mxl_scope(evidence(normal, tab), sequences(("P1", notes), ("P2", grace)))
    assert result["status"] == "accepted"
    assert result["classification"]["status"] == "mxl_scope_uncertain"
    assert result["classification"]["duplicate_views"] == []


def test_numbered_tab_identity_conflict_never_merges_equal_unison_content():
    normal, tab = part(name="Guitar 1"), part("P2", "Guitar 2 TAB", clefs=[{"sign": "TAB"}])
    notes = [[0, "0", "1", 60, False]]
    result = review_mxl_scope(evidence(normal, tab), sequences(("P1", notes), ("P2", notes)))
    assert result["status"] == "accepted"
    assert result["classification"]["status"] == "mxl_scope_uncertain"
    assert result["classification"]["duplicate_views"] == []
    assert any(row["identity_conflict"] for row in result["classification"]["tab_view_review"]["comparisons"])


def test_identical_standard_unison_parts_do_not_deduplicate_players():
    result = review_mxl_scope(evidence(part(name="Guitar 1", normalized_notes_sha256="same"),
        part("P2", "Guitar 2", normalized_notes_sha256="same")))
    assert result["status"] == "accepted"
    assert result["classification"]["topic_id"] == "duo"


def test_size_boundaries_count_written_roles_after_tab_review():
    pure = evidence(*[part(f"P{index}", f"Guitar {index}") for index in range(1, 18)])
    assert review_mxl_scope(pure)["reason"] == "large_ensemble"
    mixed = evidence(*[part(f"P{index}", f"Guitar {index}") for index in range(1, 9)],
                     part("P9", "Piano", "Piano", 0))
    assert review_mxl_scope(mixed)["reason"] == "large_ensemble"


def test_empty_excluded_placeholder_does_not_exclude_actual_guitar_solo():
    result = review_mxl_scope(evidence(part(), part("P2", "Voice", "Voice", 52, note_count=0, normalized_note_count=0)))
    assert result["status"] == "accepted"
    assert result["classification"]["topic_id"] == "solo"


def test_tab_sequence_guard_must_match_the_actual_mxl():
    seq = sequences(("P1", [[0, "0", "1", 60, False]]))
    seq["file_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="MXL"):
        review_mxl_scope(evidence(part()), seq)


def reviewed_case(parts):
    return {"id": "musescore:654", "title_en": "Work", "composer_en": "A Composer",
            "source_url": "https://musescore.com/user/321/scores/654", "mxl_sha256": "a" * 64,
            "part_names": [row["name"] for row in parts], "note": "Checked actual named notation.", "basis": "Literal MXL role evidence."}


def test_exact_reviewed_named_role_preserves_the_automatic_pending_decision():
    actual = evidence(part(name="Local named role", instrument="Unknown"))
    case = reviewed_case(actual["parts"])
    case["part_decisions"] = {"P1": {"kind": "guitar", "resolved": True}}
    source = {key: case[key] for key in ("id", "title_en", "composer_en", "source_url")}
    result = review_mxl_scope(actual, source_record=source, reviewed_case=case)
    assert result["status"] == "accepted"
    assert result["classification"]["automatic_review"]["status"] == "pending"
    assert result["classification"]["reviewed_case"] == case


def test_reviewed_auxiliary_layer_does_not_add_a_voice_role():
    actual = evidence(part(), part("P2", "Voice", "Voice", 52))
    case = reviewed_case(actual["parts"])
    case["part_decisions"] = {"P2": {"role_active": False}}
    source = {key: case[key] for key in ("id", "title_en", "composer_en", "source_url")}
    result = review_mxl_scope(actual, source_record=source, reviewed_case=case)
    assert result["status"] == "accepted"
    assert result["classification"]["guitar_player_count"] == 1
    assert result["classification"]["automatic_review"]["status"] == "excluded"


def test_exact_actual_scope_exclusion_preserves_conflict_without_invented_role_counts():
    actual = evidence(part(), part("P2", "Banjo", "Electric Bass", 33))
    case = reviewed_case(actual["parts"])
    case["scope_exclusion_note"] = "P2 has actual non-rest notes assigned to the declared Electric Bass instrument."
    source = {key: case[key] for key in ("id", "title_en", "composer_en", "source_url")}
    result = review_mxl_scope(actual, source_record=source, reviewed_case=case)
    assert result["status"] == "excluded"
    assert result["reason"] == "exact_reviewed_actual_scope_exclusion"
    assert result["classification"]["automatic_review"]["status"] == "pending"
    assert result["classification"]["scope_exclusion_note"] == case["scope_exclusion_note"]
    assert result["classification"]["guitar_player_count"] is None
    assert result["classification"]["ensemble_player_count"] is None
    case["scope_exclusion_note"] = ""
    with pytest.raises(ValueError, match="exclusion"):
        review_mxl_scope(actual, source_record=source, reviewed_case=case)


def test_guarded_scope_uncertainty_preserves_actual_guitar_roles_without_calling_them_voice():
    from catalog_instrumentation import per_record_guard
    actual = evidence(part(lyric_count=400))
    case = reviewed_case(actual["parts"])
    source = {key: case[key] for key in ("id", "title_en", "composer_en", "source_url")}
    case.update(native_record_sha256=per_record_guard(source), pdf_sha256="b" * 64,
        scope_pending_note="Printed tenor-part use and literal guitar declaration require semantic clarification.")
    result = review_mxl_scope(actual, source_record=source, reviewed_case=case)
    classification = result["classification"]
    assert result["status"] == "pending"
    assert result["reason"] == "exact_reviewed_actual_scope_uncertainty"
    assert classification["automatic_review"]["status"] == "accepted"
    assert classification["role_counts"] == {"guitar": 1}
    assert classification["roles"][0]["kind"] == "guitar"
    assert classification["guitar_player_count"] is None and classification["ensemble_player_count"] is None
    assert classification["topic_id"] == "guitar_unspecified"
    assert classification["scope_pending_note"] == case["scope_pending_note"]


@pytest.mark.parametrize("field,value", [("native_record_sha256", None), ("pdf_sha256", None),
    ("scope_pending_note", ""), ("scope_exclusion_note", "Conflicting decision")])
def test_exact_scope_uncertainty_requires_full_guards_and_has_no_exclusion_overlap(field, value):
    from catalog_instrumentation import per_record_guard
    actual = evidence(part())
    case = reviewed_case(actual["parts"])
    source = {key: case[key] for key in ("id", "title_en", "composer_en", "source_url")}
    case.update(native_record_sha256=per_record_guard(source), pdf_sha256="b" * 64,
        scope_pending_note="Actual intended use is uncertain.")
    if value is None:
        case.pop(field)
    else:
        case[field] = value
    with pytest.raises(ValueError, match="scope uncertainty"):
        review_mxl_scope(actual, source_record=source, reviewed_case=case)


@pytest.mark.parametrize("field,value", [("title_en", "Other"), ("mxl_sha256", "b" * 64), ("part_names", ["Wrong"])])
def test_semantic_case_never_uses_stale_native_or_file_guards(field, value):
    actual = evidence(part())
    case = reviewed_case(actual["parts"])
    source = {key: case[key] for key in ("id", "title_en", "composer_en", "source_url")}
    case[field] = value
    with pytest.raises(ValueError, match="guard"):
        review_mxl_scope(actual, source_record=source, reviewed_case=case)


def test_optional_complete_native_guard_rejects_changed_source_context():
    from catalog_instrumentation import per_record_guard
    actual = evidence(part())
    case = reviewed_case(actual["parts"])
    source = {key: case[key] for key in ("id", "title_en", "composer_en", "source_url")}
    source["metadata"] = {"instrumentation": "Guitar", "source_instruments": [{"name": "Guitar"}],
        "source_parts_names": ["Guitar"]}
    case["native_record_sha256"] = per_record_guard(source)
    assert review_mxl_scope(actual, source_record=source, reviewed_case=case)["status"] == "accepted"
    for field, value in [("instrumentation", "Voice and guitar"),
            ("source_instruments", [{"name": "Voice"}]), ("source_parts_names", ["Voice"])]:
        changed = deepcopy(source)
        changed["metadata"][field] = value
        with pytest.raises(ValueError, match="native record guard"):
            review_mxl_scope(actual, source_record=changed, reviewed_case=case)


@pytest.mark.parametrize("guard", [None, 123, "a" * 63, "A" * 64, "x" * 64, "a" * 64])
def test_supplied_complete_native_guard_must_be_exact_lowercase_sha256(guard):
    actual = evidence(part())
    case = reviewed_case(actual["parts"])
    case["native_record_sha256"] = guard
    source = {key: case[key] for key in ("id", "title_en", "composer_en", "source_url")}
    with pytest.raises(ValueError, match="native record guard"):
        review_mxl_scope(actual, source_record=source, reviewed_case=case)


@pytest.mark.parametrize("name,kind,zh", [("Banjo", "banjo", "班卓琴"),
    ("Bandurria", "bandurria", "Bandurria（拨弦乐器）"),
    ("Laúd", "laud", "Laúd（拨弦乐器）")])
def test_new_plucked_types_are_real_types_and_do_not_mutate_frozen_globals(name, kind, zh):
    import review_musescore_instrumentation as frozen
    old_labels, old_aliases = deepcopy(frozen.LABELS), deepcopy(frozen.ALIASES)
    result = review_mxl_scope(evidence(part(), part("P2", name, name, 105)))
    classification = result["classification"]
    assert result["status"] == "accepted"
    assert classification["topic_id"] == "plucked"
    assert classification["guitar_player_count"] == 1
    assert classification["ensemble_player_count"] == 2
    assert classification["role_counts"] == {"guitar": 1, kind: 1}
    assert zh in classification["instrumentation_zh"]
    assert classification["frozen_classifier_output"]["roles"][1]["kind"] == "unknown"
    assert "mandolin" not in classification["role_counts"]
    assert LABELS is not frozen.LABELS
    assert frozen.LABELS == old_labels and frozen.ALIASES == old_aliases


def test_new_plucked_voice_template_conflict_requires_exact_review():
    actual = evidence(part(), part("P2", "Laud", "Voice", 24))
    automatic = review_mxl_scope(actual)
    assert automatic["status"] == "pending"
    assert "P2:part_instrument_name_conflict" in automatic["classification"]["issues"]
    case = reviewed_case(actual["parts"])
    case["part_decisions"] = {"P2": {"kind": "laud", "resolved": True}}
    source = {key: case[key] for key in ("id", "title_en", "composer_en", "source_url")}
    result = review_mxl_scope(actual, source_record=source, reviewed_case=case)
    assert result["status"] == "accepted"
    assert result["classification"]["role_counts"] == {"guitar": 1, "laud": 1}
    assert result["classification"]["automatic_review"]["status"] == "pending"
    assert result["classification"]["frozen_classifier_output"]["roles"][1]["kind"] == "voice"


def test_new_type_tab_view_reuses_activity_and_complete_view_boundary():
    actual = evidence(part(), part("P2", "Banjo", "Banjo", 105),
        part("P3", "Banjo TAB", "Banjo", 105, clefs=[{"sign": "TAB"}]))
    notes = [[0, "0", "1", 60, False]]
    result = review_mxl_scope(actual, sequences(("P2", notes), ("P3", notes)))
    assert result["status"] == "accepted"
    assert result["classification"]["role_counts"] == {"guitar": 1, "banjo": 1}
    assert result["classification"]["ensemble_player_count"] == 2
    assert result["classification"]["duplicate_views"][0]["part_id"] == "P3"


def test_different_new_instruments_never_merge_their_identical_notes():
    actual = evidence(part(), part("P2", "Laud", "Laud", 24),
        part("P3", "Banjo TAB", "Banjo", 105, clefs=[{"sign": "TAB"}]))
    notes = [[0, "0", "1", 60, False]]
    result = review_mxl_scope(actual, sequences(("P2", notes), ("P3", notes)))
    assert result["status"] == "accepted"
    assert result["classification"]["role_counts"] == {"guitar": 1, "laud": 1, "banjo": 1}
    assert result["classification"]["ensemble_player_count"] == 3
    assert not result["classification"]["duplicate_views"]


def test_empty_new_instrument_keeps_its_type_without_adding_a_player():
    result = review_mxl_scope(evidence(part(), part("P2", "Banjo", "Banjo", 105, note_count=0, normalized_note_count=0)))
    assert result["status"] == "accepted"
    assert result["classification"]["topic_id"] == "solo"
    assert result["classification"]["roles"][1]["kind"] == "banjo"


@pytest.mark.parametrize("name,kind,family", [
    ("Clavichord", "clavichord", "keyboard_reed"), ("Celesta", "celesta", "keyboard_reed"),
    ("Vibraphone", "vibraphone", "percussion"), ("Euphonium", "euphonium", "brass"),
    ("Baritone Horn", "baritone_horn", "brass"), ("Mellophone", "mellophone", "brass"),
    ("English Horn", "english_horn", "woodwinds"), ("Contrabassoon", "contrabassoon", "woodwinds"),
    ("Viola da gamba", "viola_da_gamba", "strings"), ("Tambura", "tambura", "plucked"),
    ("Maracas", "maracas", "percussion"), ("Shaker", "shaker", "percussion"),
    ("Pan Flute", "pan_flute", "woodwinds"), ("Nyckelharpa", "nyckelharpa", "strings"),
    ("Bouzouki (4 chœurs)", "bouzouki", "plucked"), ("Hackbrett", "hammered_dulcimer", "percussion"),
])
def test_exact_additional_instruments_keep_their_real_type(name, kind, family):
    result = review_mxl_scope(evidence(part(), part("P2", name, name, 0)))
    assert result["status"] == "accepted"
    assert result["classification"]["role_counts"] == {"guitar": 1, kind: 1}
    assert result["classification"]["topic_id"] == family


@pytest.mark.parametrize("label", ["גיטרה אקוסטית", "גיטרה קלאסית", "어쿠스틱 기타 ",
    "Akustisk gitar I", "Akustisk guitar III", "Akoestische gitaar", "Klasik Gitar", "Kytara",
    "Chitară acustică", "Классическая гитара (табулатура)", "Violão Clássico (Tablatura)"])
def test_official_acoustic_names_and_view_suffixes_are_exact_instrument_evidence(label):
    result = review_mxl_scope(evidence(part(name=label, instrument=label)))
    assert result["status"] == "accepted"
    assert result["classification"]["guitar_player_count"] == 1


@pytest.mark.parametrize("label", ["Guitarra elèctrica", "Электрогитара", "Elektrische gitaar", "Bass Gitarre", "Saw Synthesizer"])
def test_official_explicit_forbidden_instrument_names_stay_excluded(label):
    result = review_mxl_scope(evidence(part(), part("P2", label, label, 80)))
    assert result["status"] == "excluded"


@pytest.mark.parametrize("label", ["Bass", "Acoustic Bass", "Alto", "Strings", "Primo", "Secondo", "Jazz Guitar", "Lead Guitar", "ベース"])
def test_ambiguous_register_or_template_labels_are_not_globally_acoustic(label):
    result = review_mxl_scope(evidence(part(name=label, instrument=label)))
    assert result["status"] == "pending"
    assert result["classification"]["guitar_player_count"] is None


@pytest.mark.parametrize("label,kind", [("Violins", "violin"), ("Violas", "viola"),
    ("Violoncellos", "cello"), ("Contrabasses", "double_bass")])
def test_plural_string_sections_have_known_types_and_unknown_player_counts(label, kind):
    result = review_mxl_scope(evidence(part(), part("P2", label, label, 40)))
    assert result["status"] == "accepted"
    assert result["classification"]["role_counts"] == {"guitar": 1, kind: 1}
    assert result["classification"]["guitar_player_count"] is None
    assert result["classification"]["ensemble_player_count"] is None
    assert "P2:collective_role_count_unknown" in result["classification"]["issues"]


@pytest.mark.parametrize("label,kind", [
    ("Poikkihuilu", "flute"), ("B♭ Bass Clarinet (Bass Clef)", "clarinet"),
    ("Tenor-saxofoon", "saxophone"), ("Grosse caisse de concert", "bass_drum"),
    ("Célesta", "celesta"), ("Clarinette\nBasse", "clarinet"),
    ("Marimba (Grand Staff)", "marimba"), ("マリンバ [単譜表]", "marimba"),
    ("Tenor Banjo", "banjo"), ("Tenorhorn", "baritone_horn"),
    ("Flûte Sopranino en Do", "recorder"), ("F ホルン", "horn"),
    ("Alaúde", "lute"),
    ("[Classical Guitar [notation]]", "guitar"),
    ("12-string Acoustic Guitar [notation]", "guitar"),
    ("Classical Guitar, Acoustic Guitar", "guitar"),
    ("Nylon Gtr., Guitar", "guitar"), ("古典吉他, guitar", "guitar"),
    ("Erhu", "erhu"), ("Cavaquinho", "cavaquinho"),
    ("Ocarina", "ocarina"), ("drum kit", "drumset"),
    ("cajón", "cajon"), ("đàn nhị", "dan_nhi"),
])
def test_final_finite_complete_instrument_names_keep_their_actual_types(label, kind):
    from review_musescore_expansion import expansion_kind
    assert expansion_kind(label) == kind


@pytest.mark.parametrize("label,kind,topic", [("Erhu", "erhu", "strings"),
    ("Cavaquinho", "cavaquinho", "plucked"), ("Ocarina", "ocarina", "woodwinds")])
def test_finite_new_types_do_not_masquerade_as_other_instruments(label, kind, topic):
    original = evidence(part(), part("P2", label, label, 0))
    before = deepcopy(original)
    result = review_mxl_scope(original)
    assert result["status"] == "accepted"
    assert result["classification"]["role_counts"] == {"guitar": 1, kind: 1}
    assert result["classification"]["topic_id"] == topic
    assert result["classification"]["ensemble_player_count"] == 2
    assert original == before


@pytest.mark.parametrize("label,kind", [("Viulut", "violin"), ("Sellot", "cello"),
    ("Kontrabassot", "double_bass"), ("Контрабас", "double_bass"),
    ("바이올린", "violin"), ("비올라", "viola"), ("비올론첼로", "cello"),
    ("Violoncelles", "cello"), ("Housle", "violin"), ("Vlns.", "violin"),
    ("Cbs.", "double_bass"), ("乐队小提琴", "violin")])
def test_official_singular_section_homonyms_keep_unknown_desk_sizes(label, kind):
    result = review_mxl_scope(evidence(part(), part("P2", label, label, 40)))
    assert result["status"] == "accepted"
    assert result["classification"]["role_counts"] == {"guitar": 1, kind: 1}
    assert result["classification"]["guitar_player_count"] is None
    assert result["classification"]["ensemble_player_count"] is None
    assert "P2:collective_role_count_unknown" in result["classification"]["issues"]


@pytest.mark.parametrize("label", ["Flauta Soprano", "Contrabaixo", "Contrabaixos", "Viole", "琴",
    "Guitar, Electric Guitar", "Guitar Steel Drums", "[Unreviewed Guitar]", "Classical Guitar [Unknown View]",
    "Tamborim", "Grup de percussió"])
def test_final_finite_supplement_does_not_generalize_ambiguous_or_wrapped_names(label):
    from review_musescore_expansion import expansion_kind
    assert expansion_kind(label) is None
    assert review_mxl_scope(evidence(part(name=label, instrument=label)))["status"] == "pending"


@pytest.mark.parametrize("label", ["[Voice]", "Şan", "Choir Synthesizer", "6-str. Electric Bass", "踏板电子吉他"])
def test_final_exact_scope_exception_aliases_remain_excluded(label):
    result = review_mxl_scope(evidence(part(), part("P2", label, label, 80)))
    assert result["status"] == "excluded"
    assert result["reason"] == "active_excluded_instrument"


def test_finite_percussion_aliases_preserve_cross_family_conflicts_and_true_kit_components():
    conflict = review_mxl_scope(evidence(part(), part("P2", "Vibraphon", "Tenor Banjo", 0)))
    assert conflict["status"] == "pending"
    assert "P2:part_instrument_name_conflict" in conflict["classification"]["issues"]
    kit = part("P2", "D. Set", "Acoustic Snare", 0,
        score_instruments=[{"id": "I1", "name": "Acoustic Snare"}, {"id": "I2", "name": "Closed Hi-Hat"}],
        clefs=[{"sign": "percussion"}], unpitched_note_count=5)
    result = review_mxl_scope(evidence(part(), kit))
    assert result["status"] == "accepted"
    assert result["classification"]["role_counts"] == {"guitar": 1, "drumset": 1}


def test_standard_drum_components_are_one_explicit_drum_role_and_unknown_sounds_still_block():
    drum = part("P2", "Drumset", "Acoustic Snare", 0,
        score_instruments=[{"id": "I1", "name": "Acoustic Snare"}, {"id": "I2", "name": "Closed Hi-Hat"}],
        unpitched_note_count=5, clefs=[{"sign": "percussion"}])
    result = review_mxl_scope(evidence(part(), drum))
    assert result["status"] == "accepted"
    assert result["classification"]["role_counts"] == {"guitar": 1, "drumset": 1}
    drum["score_instruments"][1]["name"] = "Unknown Instrument 40"
    assert review_mxl_scope(evidence(part(), drum))["status"] == "pending"


def test_recorder_and_classical_guitar_do_not_become_voice_from_register_words():
    result = review_mxl_scope(evidence(part(), part("P2", "Soprano Recorder", "Soprano Recorder", 74)))
    assert result["status"] == "accepted"
    assert result["classification"]["role_counts"] == {"guitar": 1, "recorder": 1}


@pytest.mark.parametrize("name,instrument", [("Hackbrett", "Banjo"),
    ("Vibraphone", "Voice"), ("Drumset", "Electric Bass"), ("Percussion", "Electric Guitar")])
def test_percussion_family_does_not_hide_cross_instrument_name_conflicts(name, instrument):
    result = review_mxl_scope(evidence(part(), part("P2", name, instrument, 0)))
    assert result["status"] == "pending"
    assert "P2:part_instrument_name_conflict" in result["classification"]["issues"]


def test_drum_role_cannot_hide_an_electric_bass_declaration_among_real_components():
    drum = part("P2", "Drumset", "Acoustic Snare", 0,
        score_instruments=[{"id": "I1", "name": "Acoustic Snare"}, {"id": "I2", "name": "Electric Bass"}])
    result = review_mxl_scope(evidence(part(), drum))
    assert result["status"] == "pending"
    assert "P2:part_instrument_name_conflict" in result["classification"]["issues"]


def test_uncertain_written_rows_never_display_as_confirmed_player_counts():
    classification = classify_expansion_parts([
        part("P1", name="Nylon Gtr.", instrument="Nylon Gtr."),
        part("P2", name="Nylon Gtr.", instrument="Nylon Gtr.", clefs=[{"sign": "F"}]),
        part("P3", name="Organ", instrument="Organ")],
        part_decisions={"P3": {"kind": "organ", "resolved": True, "role_active": None}})
    # Exact file review retains an unresolved view/doubling boundary. Row
    # multiplicity is evidence, while the displayed player numbers stay unknown.
    assert classification["guitar_player_count"] is None
    assert classification["ensemble_player_count"] is None
    assert "2 guitar" not in classification["instrumentation"]
    assert "2×" not in classification["instrumentation_zh"]
    assert "人数未定" in classification["instrumentation_zh"]
    assert classification["role_counts"]["guitar"] == 2
