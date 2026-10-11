"""Offline regression checks for the frozen PDMX -> MuseScore projection."""
from copy import deepcopy

import pytest

from source_adapters import musescore


def example(*, instrument="Guitar", count=1, arrangement="Solo"):
    url = "https://musescore.com/user/321/scores/654"
    raw_title = "Étude, No. 1  (guitar)"
    raw_composer = "F. Sor"
    row = {"metadata": "./metadata/1/654.json", "title": "Étude No. 1 (guitar)",
           "composer_name": raw_composer, "license": "cc-zero",
           "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
           "license_conflict": "False", "subset:no_license_conflict": "True",
           "tracks": "24-24", "n_tracks": "2", "n_lyrics": "0", "has_lyrics": "False",
           "pdf": "./pdf/1/score.pdf", "mxl": "./mxl/1/score.mxl", "mid": "./mid/1/score.mid"}
    score = {"id": 654, "title": raw_title, "composer_name": raw_composer,
             "url": url, "share": {"publicUrl": url},
             "user": {"id": 321, "name": "An uploader", "url": "https://musescore.com/user/321"},
             "parts": count, "parts_names": [instrument] * count,
             "pages_count": 2, "instruments": [{"name": instrument + (f" ({count})" if count > 1 else ""),
                                                   "url_to_search": "/sheetmusic/guitar", "count": count}],
             "instrumentations": [{"name": arrangement, "uri": "solo", "is_auto": 1}],
             "license": "cc-zero", "is_private": 0, "is_draft": False,
             "is_official": False, "is_original": True, "is_blocked": False,
             "keysig": "C major, A minor"}
    metadata = {"status_code": 200, "data": {"score": score, "license_url": row["license_url"],
                                            "is_download_limited": False,
                                            "paywall": {"has_instant_paywall": False}},
                "score": {"id": score["id"], "title": raw_title, "url": url,
                          "user": deepcopy(score["user"]), "isPublic": True}}
    return row, metadata


def test_generic_guitar_preserves_native_text_and_does_not_count_tracks_or_staves_as_players():
    row, meta = example(count=2, arrangement="Mixed Duet")
    record, reason = musescore.convert_record(row, meta)
    assert reason == "accepted"
    assert record["id"] == "musescore:654"
    assert record["source_url"] == meta["data"]["score"]["url"]
    assert record["title_en"] == "Étude, No. 1  (guitar)"
    assert record["composer_en"] == "F. Sor"
    assert record["category_ids"] == ["guitar"]
    assert record["metadata"]["instrumentation"] == "Guitar"
    assert record["metadata"]["guitar_player_count"] is None
    assert record["metadata"]["original_arrangement_status"] == "unspecified"
    assert record["metadata"]["source_composer_attribution"] == "F. Sor"


def test_blank_source_composer_keeps_missing_attribution_and_the_private_transcription():
    row, meta = example()
    meta["data"]["score"]["composer_name"] = "\n"
    row["composer_name"] = "NA"
    record, reason = musescore.convert_record(row, meta)
    assert reason == "accepted"
    assert record["composer_en"] == ""
    assert record["metadata"]["source_composer_attribution"] == "\n"
    assert record["metadata"]["attribution_role"] == "source_unspecified"


@pytest.mark.parametrize("label,expected,count", [
    ("Solo Guitar", "Solo guitar", 1), ("Guitar Solo", "Solo guitar", 1),
    ("Guitar Duet", "2 guitars", 2), ("Guitar Trio", "3 guitars", 3),
    ("Guitar Quartet", "4 guitars", 4),
])
def test_only_explicit_guitar_player_labels_establish_player_count(label, expected, count):
    row, meta = example(arrangement=label, count=count)
    record, reason = musescore.convert_record(row, meta)
    assert reason == "accepted"
    assert record["metadata"]["instrumentation"] == expected
    assert record["metadata"]["guitar_player_count"] == count


def test_contradictory_title_and_auto_solo_label_do_not_claim_solo():
    row, meta = example(arrangement="Solo Guitar", count=2)
    title = "60 Lessons for 2 Guitars, Op.168/56"
    meta["data"]["score"]["title"] = meta["score"]["title"] = title
    row["title"] = "60 Lessons for 2 Guitars Op.168/56"
    record, reason = musescore.convert_record(row, meta)
    assert reason == "accepted"
    assert record["metadata"]["instrumentation"] == "Guitar"
    assert record["metadata"]["guitar_player_count"] is None
    assert "conflict" in record["metadata"]["instrumentation_note"].lower()


def test_serialize_guard_uses_documented_csv_rules_without_rewriting_native_fields():
    row, meta = example()
    composer = "Bruce W. Robinson\ntranscribed for guitar 9/2019\n"
    meta["data"]["score"]["composer_name"] = composer
    row["composer_name"] = "Bruce W. Robinsontranscribed for guitar 9/2019"
    record, reason = musescore.convert_record(row, meta)
    assert reason == "accepted"
    assert record["metadata"]["source_composer_attribution"] == composer
    assert record["composer_en"] == ""
    assert record["metadata"]["attribution_role"] == "source_unspecified"
    assert "transcribed for guitar 9/2019" in record["metadata"]["source_attribution_note"]


@pytest.mark.parametrize("field,new,reason", [
    ("title", "Another score", "csv_title_mismatch"),
    ("composer_name", "Another composer", "csv_composer_mismatch"),
    ("license", "publicdomain", "license_mismatch"),
    ("license_url", "https://creativecommons.org/publicdomain/mark/1.0/", "license_url_mismatch"),
])
def test_csv_metadata_guard_rejects_actual_changed_fields(field, new, reason):
    row, meta = example()
    row[field] = new
    assert musescore.convert_record(row, meta) == (None, reason)


@pytest.mark.parametrize("mutation,reason", [
    (lambda r, m: r.update(metadata="./metadata/1/999.json"), "native_id_mismatch"),
    (lambda r, m: m["score"].update(id=999), "native_id_mismatch"),
    (lambda r, m: m["score"].update(title="Changed"), "metadata_title_mismatch"),
    (lambda r, m: m["score"].update(url="https://musescore.com/user/321/scores/999"), "source_url_mismatch"),
    (lambda r, m: m["data"]["score"]["share"].update(publicUrl="https://musescore.com/user/999/scores/654"), "source_url_mismatch"),
])
def test_conflicting_native_identity_title_and_urls_are_rejected(mutation, reason):
    row, meta = example()
    mutation(row, meta)
    assert musescore.convert_record(row, meta) == (None, reason)


@pytest.mark.parametrize("url", [
    "https://musescore.com.evil.test/user/321/scores/654", "http://musescore.com/user/321/scores/654",
    "https://musescore.com/user/321/scores/654?secret=x", "https://musescore.com/user/321/scores/654/download",
    "https://musescore.com/user/321/scores/654#pdf", "https://user:pass@musescore.com/user/321/scores/654",
])
def test_record_page_url_cannot_be_a_download_secret_or_unapproved_host(url):
    row, meta = example()
    meta["data"]["score"]["url"] = url
    assert musescore.convert_record(row, meta)[1] == "invalid_source_url"


def test_native_username_page_is_preserved_with_matching_uploader_homepage():
    row, meta = example()
    url = "https://musescore.com/smreks/scores/654"
    for node in (meta["data"]["score"], meta["score"]):
        node["url"] = url
        node["user"]["url"] = "https://musescore.com/smreks"
        node["share"] = {"publicUrl": url}
    record, reason = musescore.convert_record(row, meta)
    assert reason == "accepted" and record["source_url"] == url
    meta["data"]["score"]["user"]["url"] = "https://musescore.com/someone-else"
    assert musescore.convert_record(row, meta)[1] == "invalid_source_url"


@pytest.mark.parametrize("slug", ["download", "api", "static", "scores", "sheetmusic"])
def test_reserved_paths_cannot_be_presented_as_username_score_pages(slug):
    row, meta = example()
    url = f"https://musescore.com/{slug}/scores/654"
    meta["data"]["score"].update(url=url)
    meta["data"]["score"]["user"]["url"] = f"https://musescore.com/{slug}"
    assert musescore.convert_record(row, meta)[1] == "invalid_source_url"


@pytest.mark.parametrize("instrument", [
    "Electric Guitar", "Bass Guitar", "Steel Guitar", "Hawaiian Guitar", "Slide Guitar",
    "Voice", "Vocals", "Chorus", "Orchestra", "Synthesizer", "Unknown Instrument", "Banjo", "Piano",
])
def test_gm_acoustic_candidate_does_not_override_out_of_scope_source_instruments(instrument):
    row, meta = example(instrument=instrument)
    assert musescore.convert_record(row, meta)[0] is None


@pytest.mark.parametrize("instrument", ["Violin", "Flute", "Trumpet", "Piano", "Mandolin", "Marimba"])
def test_explicit_small_mixed_instrumentation_is_kept_for_shared_topics(instrument):
    row, meta = example()
    meta["data"]["score"]["instruments"].append({"name": instrument, "count": 1})
    meta["data"]["score"].update(parts=2, parts_names=["Guitar", instrument])
    record, reason = musescore.convert_record(row, meta)
    assert reason == "accepted"
    assert record["metadata"]["instrumentation"] == "Guitar and " + instrument.lower()
    assert record["metadata"]["guitar_player_count"] is None


def test_mixed_large_ensemble_is_excluded_even_when_every_instrument_is_familiar():
    row, meta = example()
    meta["data"]["score"]["instruments"].append({"name": "Violin (8)", "count": 8})
    meta["data"]["score"].update(parts=9, parts_names=["Guitar"] + ["Violin"] * 8)
    assert musescore.convert_record(row, meta) == (None, "large_ensemble")


def test_voice_or_bass_in_parts_cannot_hide_behind_guitar_only_instrument_directory():
    row, meta = example()
    meta["data"]["score"].update(parts=2, parts_names=["Guitar", "Vocals"])
    assert musescore.convert_record(row, meta)[1] == "excluded_part_instrument"


def test_mirror_part_transcription_cannot_hide_an_electric_guitar():
    row, meta = example()
    meta["score"]["partNames"] = ["Electric Guitar"]
    assert musescore.convert_record(row, meta)[1] == "excluded_part_instrument"


@pytest.mark.parametrize("field,value", [("license_conflict", "True"), ("subset:no_license_conflict", "False")])
def test_license_conflict_is_a_stop_even_for_cc_zero(field, value):
    row, meta = example()
    row[field] = value
    assert musescore.convert_record(row, meta) == (None, "license_conflict")


@pytest.mark.parametrize("field,value", [("n_lyrics", "1"), ("has_lyrics", "True")])
def test_lyric_evidence_is_excluded_without_guessing_voice_instrumentation(field, value):
    row, meta = example()
    row[field] = value
    assert musescore.convert_record(row, meta) == (None, "lyrics")


@pytest.mark.parametrize("field", ["is_private", "is_draft", "is_official", "is_blocked"])
def test_source_restriction_flags_stop_acceptance(field):
    row, meta = example()
    meta["data"]["score"][field] = True
    assert musescore.convert_record(row, meta)[0] is None


@pytest.mark.parametrize("restriction", ["download_limit", "paywall", "csv_paywall"])
def test_file_access_limits_do_not_authorize_files_or_exclude_reusable_metadata(restriction):
    row, meta = example()
    if restriction == "download_limit":
        meta["data"]["is_download_limited"] = True
    elif restriction == "paywall":
        meta["data"]["paywall"]["has_instant_paywall"] = True
    else:
        row["has_paywall"] = "True"
    record, reason = musescore.convert_record(row, meta)
    assert reason == "accepted"
    assert "源站历史文件访问受限" in record["metadata"]["availability"]
    assert record["metadata"]["historical_file_access_restrictions"]
    assert all(a["status"] == "metadata_only" and "source_url" not in a for a in record["assets"])


@pytest.mark.parametrize("restriction", ["hidden", "is_blocked", "score_blocked_by_country"])
def test_blocked_or_hidden_metadata_is_still_excluded(restriction):
    row, meta = example()
    meta["data"][restriction] = True
    assert musescore.convert_record(row, meta) == (None, "restricted_snapshot")


def test_uploader_is_a_contributor_not_a_fallback_composer():
    row, meta = example()
    row["composer_name"] = "NA"
    meta["data"]["score"]["composer_name"] = None
    record, reason = musescore.convert_record(row, meta)
    assert reason == "accepted"
    assert record["composer_en"] == ""
    assert record["metadata"]["contributors"] == "上传者：An uploader"
    assert record["metadata"]["attribution_role"] == "source_unspecified"


def test_third_party_email_in_composer_is_kept_private_without_public_name_invention():
    row, meta = example()
    original = "john.doe@example.com"
    row["composer_name"] = "john.doeexample.com"
    meta["data"]["score"]["composer_name"] = original
    record, reason = musescore.convert_record(row, meta)
    assert reason == "accepted"
    assert record["composer_en"] == ""
    assert record["metadata"]["source_composer_attribution"] == original
    assert record["metadata"]["attribution_role"] == "source_unspecified"
    assert original not in record["metadata"]["source_attribution_note"]


@pytest.mark.parametrize("raw,role,field,name", [
    ("Arr. Pietro Foti", "arranger", "arranger", "Pietro Foti"),
    ("Arr: Pietro Foti", "arranger", "arranger", "Pietro Foti"),
    ("Arranged by Pietro Foti", "arranger", "arranger", "Pietro Foti"),
    ("Arr. by Pietro Foti", "arranger", "arranger", "Pietro Foti"),
    ("Arr. by: Pietro Foti", "arranger", "arranger", "Pietro Foti"),
    ("Arrangement: Pietro Foti", "arranger", "arranger", "Pietro Foti"),
    ("Transcription: drBabus", "transcriber", "transcriber", "drBabus"),
    ("Transcribed by drBabus", "transcriber", "transcriber", "drBabus"),
    ("Edited by Jane Editor", "editor", "editor", "Jane Editor"),
    ("Editor: Jane Editor", "editor", "editor", "Jane Editor"),
])
def test_explicit_noncomposer_responsibility_does_not_become_a_composer(raw, role, field, name):
    row, meta = example()
    row["composer_name"] = raw
    meta["data"]["score"]["composer_name"] = raw
    record, reason = musescore.convert_record(row, meta)
    assert reason == "accepted"
    assert record["composer_en"] == ""
    assert record["metadata"]["attribution_role"] == role
    assert record["metadata"][field] == name
    assert record["metadata"]["source_composer_attribution"] == raw
    assert raw in record["metadata"]["source_attribution_note"]
    assert record["metadata"]["original_arrangement_status"] == "unspecified"


@pytest.mark.parametrize("raw,composer,field,name", [
    ("Composer: Matvei Blanter Arr: drBabus", "Matvei Blanter", "arranger", "drBabus"),
    ("Composed by Matvei Blanter; Arranged by drBabus", "Matvei Blanter", "arranger", "drBabus"),
    ("Music by Matvei Blanter; Transcription: drBabus", "Matvei Blanter", "transcriber", "drBabus"),
    ("Composer: Matvei Blanter; Editor: Jane Editor", "Matvei Blanter", "editor", "Jane Editor"),
    ("Composer: Matvei Blanter, Arr. Pietro Foti", "Matvei Blanter", "arranger", "Pietro Foti"),
])
def test_labelled_composer_and_separate_responsibility_keep_both_exact_names(raw, composer, field, name):
    row, meta = example()
    row["composer_name"] = {"Composer: Matvei Blanter, Arr. Pietro Foti": "Composer: Matvei Blanter Arr. Pietro Foti"}.get(raw, raw)
    meta["data"]["score"]["composer_name"] = raw
    record, reason = musescore.convert_record(row, meta)
    assert reason == "accepted"
    assert record["composer_en"] == composer
    assert record["metadata"]["attribution_role"] == "composer"
    assert record["metadata"][field] == name
    assert record["metadata"]["source_composer_attribution"] == raw
    assert raw in record["metadata"]["source_attribution_note"]


@pytest.mark.parametrize("raw", [
    "Soviet War Song\nArranged by Brett Vachon",
    "Vivaldi. Concerto for two mandolins. arr. G.Dempsey",
    "Tr. (Arr. by John Hurt, 1928)",
])
def test_unlabelled_context_before_arrangement_is_not_guessed_as_a_composer(raw):
    row, meta = example()
    row["composer_name"] = {
        "Soviet War Song\nArranged by Brett Vachon": "Soviet War SongArranged by Brett Vachon",
        "Tr. (Arr. by John Hurt, 1928)": "Tr. (Arr. by John Hurt 1928)",
    }.get(raw, raw)
    meta["data"]["score"]["composer_name"] = raw
    record, reason = musescore.convert_record(row, meta)
    assert reason == "accepted" and record["composer_en"] == ""
    assert record["metadata"]["source_composer_attribution"] == raw
    assert raw in record["metadata"]["source_attribution_note"]


def test_explicit_composer_after_a_writer_statement_does_not_become_the_writer():
    row, meta = example()
    raw = "Written by Ballard MacDonald, Composed by Harry Carroll"
    row["composer_name"] = "Written by Ballard MacDonald Composed by Harry Carroll"
    meta["data"]["score"]["composer_name"] = raw
    record, reason = musescore.convert_record(row, meta)
    assert reason == "accepted" and record["composer_en"] == "Harry Carroll"
    assert raw in record["metadata"]["source_attribution_note"]


def test_explicit_composer_stops_at_a_separate_transcription_statement():
    row, meta = example()
    raw = "Written by Ballard MacDonald, Composed by Harry Carroll\nTranscribed JSVDW from Laurel & Hardy 'Way Out West' (1937)"
    row["composer_name"] = "Written by Ballard MacDonald Composed by Harry CarrollTranscribed JSVDW from Laurel & Hardy 'Way Out West' (1937)"
    meta["data"]["score"]["composer_name"] = raw
    record, reason = musescore.convert_record(row, meta)
    assert reason == "accepted" and record["composer_en"] == "Harry Carroll"
    assert raw in record["metadata"]["source_attribution_note"]
    # An unlabelled transcription statement is preserved rather than guessed
    # into a separate person's canonical name.
    assert "transcriber" not in record["metadata"]


@pytest.mark.parametrize("raw", ["?. ?????", "12345", "???", "– … !"])
def test_non_name_symbols_remain_unknown_with_the_original_private_transcription(raw):
    row, meta = example()
    row["composer_name"] = {"– … !": "!"}.get(raw, raw)
    meta["data"]["score"]["composer_name"] = raw
    record, reason = musescore.convert_record(row, meta)
    assert reason == "accepted"
    assert record["composer_en"] == ""
    assert record["metadata"]["attribution_role"] == "source_unspecified"
    assert "不可辨识" in record["metadata"]["source_attribution_note"]
    assert record["metadata"]["source_composer_attribution"] == raw


@pytest.mark.parametrize("raw,csv_value", [
    ("Composer: Jane Arr: jane@example.com", "Composer: Jane Arr: janeexample.com"),
    ("Composer: Jane Address: 123 Main Street", "Composer: Jane Address: 123 Main Street"),
    ("Editor: Jane HTTPS://example.com/download/file.pdf", "Editor: Jane HTTPS://example.com/download/file.pdf"),
])
def test_explicit_contact_information_cannot_leak_through_parsed_role_fields(raw, csv_value):
    row, meta = example()
    row["composer_name"] = csv_value
    meta["data"]["score"]["composer_name"] = raw
    record, reason = musescore.convert_record(row, meta)
    assert reason == "accepted" and record["composer_en"] == ""
    assert record["metadata"]["source_composer_attribution"] == raw
    assert record["metadata"]["attribution_role"] == "source_unspecified"
    assert not ({"arranger", "transcriber", "editor"} & set(record["metadata"]))
    assert raw not in record["metadata"]["source_attribution_note"]


def test_no_local_file_or_live_availability_claim_is_created_from_dataset_format_columns():
    row, meta = example()
    before = deepcopy((row, meta))
    record, reason = musescore.convert_record(row, meta)
    assert reason == "accepted"
    assert record["formats"] == ["MIDI", "MUSICXML", "PDF"]
    assert {asset["status"] for asset in record["assets"]} == {"metadata_only"}
    assert all(not ({"source_url", "path", "relative_path", "sha256", "download_url"} & set(a)) for a in record["assets"])
    assert "PDMX v9" in record["metadata"]["source_edition"]
    assert record["metadata"]["availability"] == "来源页面现状未核；尚无本地谱文件。"
    assert record["metadata"]["pages"] == 2
    assert record["metadata"]["key"] == "C major, A minor"
    assert (row, meta) == before


@pytest.mark.parametrize("field", ["pdf", "mxl", "mid"])
def test_na_format_columns_do_not_create_fictitious_formats(field):
    row, meta = example()
    row[field] = "NA"
    record, reason = musescore.convert_record(row, meta)
    assert reason == "accepted"
    mapping = {"pdf": "PDF", "mxl": "MUSICXML", "mid": "MIDI"}
    assert mapping[field] not in record["formats"]


@pytest.mark.parametrize("raw,role,fields", [
    # Exact responsibility transcriptions from the accepted PDMX records.
    ("Arreglo: Víctor Domínguez", "arranger", {"arranger": "Víctor Domínguez"}),
    ("Arreglista: Reynaldo Martinez M.", "arranger", {"arranger": "Reynaldo Martinez M."}),
    ("Arreglo: César Amaro (para niños y niñas)", "arranger", {"arranger": "César Amaro (para niños y niñas)"}),
    ("Edition : Paul Kang", "source_unspecified", {}),
    ("Artist: LiSA", "source_unspecified", {}),
    ("François Campion (1686-1746) Arr.Marieh", "arranger", {"arranger": "Marieh"}),
    ("Anon. (XVIIe) Arr.Marieh", "arranger", {"arranger": "Marieh"}),
    ("Duke Ellington      arr.Dempsey", "arranger", {"arranger": "Dempsey"}),
    ("Alonso MUDARRA Transc. J-D PALMER", "transcriber", {"transcriber": "J-D PALMER"}),
    ("Alonzo MUDARRA Transcr: J-D PALMER", "transcriber", {"transcriber": "J-D PALMER"}),
    ("TabEdited by Gilles Clermont MuseScore Transcription/Arrangement/TAB by Leszko",
     "editor", {"editor": "Gilles Clermont"}),
    ("Fernando Sor (1778 - 1839) arrangé par Narciso Yepes en 1952", "arranger",
     {"arranger": "Narciso Yepes en 1952"}),
    ("Bach arr Dempsey", "source_unspecified", {}),
    ("N. Paganini adatt. simone", "source_unspecified", {}),
    ("?prava: Pavel Hrub?", "source_unspecified", {}),
    ("arrangement Ross Ingram", "source_unspecified", {}),
    ("Arragement by Ed Drow", "source_unspecified", {}),
    ("Traditional, Arranged Innocent Bystander", "source_unspecified", {}),
    ("Handel\nArranged for Guitar", "source_unspecified", {}),
    ("Ragtime Waltz. Scott Joplin.  Arr solo guitar G.Dempsey", "source_unspecified", {}),
    ("Author: Soda Stereo\nArranged by Juan J. Guáqueta Restrepo", "author",
     {"author": "Soda Stereo", "arranger": "Juan J. Guáqueta Restrepo"}),
    ("Composers: Joseph Mohr\nFranz Gruber\nArrangement: Laiane Farias\n", "source_unspecified",
     {"arranger": "Laiane Farias"}),
    ("Composer", "source_unspecified", {}),
    ("Ð°Ñ\x80Ð°Ð½Ð¶. Ð\x92Ñ\x96ÐºÑ\x82Ð¾Ñ\x80Ñ\x96Ñ\x97 Ð¢ÐºÐ°Ñ\x87Ñ\x83Ðº", "source_unspecified", {}),
])
def test_actual_unlabelled_context_or_noncomposer_credit_never_becomes_a_composer(raw, role, fields):
    row, meta = example()
    row["composer_name"] = musescore.csv_serialization(raw)
    meta["data"]["score"]["composer_name"] = raw
    before = deepcopy((row, meta))
    record, reason = musescore.convert_record(row, meta)
    assert reason == "accepted"
    assert record["composer_en"] == ""
    assert record["metadata"]["attribution_role"] == role
    assert record["metadata"]["source_composer_attribution"] == raw
    assert raw in record["metadata"]["source_attribution_note"]
    for key, value in fields.items():
        assert record["metadata"][key] == value
    assert (row, meta) == before


def test_actual_explicit_composer_label_stops_at_separate_incomplete_arrangement_credit():
    row, meta = example()
    raw = "Composer: Marcin PrzybyÅ\x82owicz\nArr for guitar: drBabus\n"
    row["composer_name"] = musescore.csv_serialization(raw)
    meta["data"]["score"]["composer_name"] = raw
    record, reason = musescore.convert_record(row, meta)
    assert reason == "accepted"
    assert record["composer_en"] == "Marcin PrzybyÅ\x82owicz"
    assert record["metadata"]["attribution_role"] == "composer"
    assert "arranger" not in record["metadata"]
    assert record["metadata"]["source_composer_attribution"] == raw
    assert raw in record["metadata"]["source_attribution_note"]


@pytest.mark.parametrize("native,display", [
    ("E major, Câ\x99¯ minor", "E major, C♯ minor"),
    ("Bâ\x99­ major, G minor", "B♭ major, G minor"),
    ("F♯ major, D♯ minor", "F♯ major, D♯ minor"),
    ("C major \x81", "C major \x81"),
])
def test_key_encoding_display_uses_strict_recovery_and_keeps_native_value_private(native, display):
    row, meta = example()
    meta["data"]["score"]["keysig"] = native
    before = deepcopy((row, meta))
    record, reason = musescore.convert_record(row, meta)
    assert reason == "accepted"
    assert record["metadata"]["key"] == display
    assert record["metadata"]["source_key"] == native
    if native != display:
        assert "调性" in record["metadata"]["text_quality_note"]
        assert "可逆" in record["metadata"]["text_quality_note"]
    assert (row, meta) == before


@pytest.mark.parametrize("native,display", [
    ("Mateusz LasoÅ\x84", "Mateusz Lasoń"),
    ("FranÃ§ois", "FranÃ§ois"),
    ("An uploader \x81", "An uploader \x81"),
])
def test_uploader_encoding_display_preserves_native_identity_and_does_not_invent_composer(native, display):
    row, meta = example()
    meta["data"]["score"]["user"]["name"] = native
    row["composer_name"] = "NA"
    meta["data"]["score"]["composer_name"] = None
    before = deepcopy((row, meta))
    record, reason = musescore.convert_record(row, meta)
    assert reason == "accepted"
    assert record["metadata"]["contributors"] == "上传者：" + display
    assert record["metadata"]["source_uploader"]["name"] == native
    assert record["composer_en"] == ""
    assert record["metadata"]["attribution_role"] == "source_unspecified"
    if native != display:
        assert "上传者" in record["metadata"]["text_quality_note"]
    assert (row, meta) == before
