from __future__ import annotations

from source_adapters import csun


def item_detail(*, title="Aida-fantasie", series="Guitar Solos", rights="Public domain.",
                filename="338.pdf", download_uri="/digital/api/collection/IGRA-scores/id/1144/download",
                content_type="application/pdf"):
    return {
        "contentType": content_type,
        "filename": filename,
        "downloadUri": download_uri,
        "fields": [
            {"key": "title", "label": "Title", "value": title},
            {"key": "series", "label": "Series Title", "value": series},
            {"key": "creato", "label": "Composer", "value": "Verdi, Giuseppe, 1813-1901"},
            {"key": "rights", "label": "Rights Note", "value": rights},
            {"key": "docume", "label": "Genre", "value": "scores"},
        ],
    }


def test_parse_search_page_preserves_native_ids_and_checks_scope():
    payload = {
        "totalResults": 12,
        "items": [{"collectionAlias": "IGRA-scores", "itemId": "1144", "filetype": "pdf",
                   "title": "Aida-fantasie", "metadataFields": []}],
    }
    total, rows = csun.parse_search_page(payload)
    assert total == 12
    assert rows[0]["native_item_id"] == "1144"
    assert rows[0]["source_url"].endswith("/id/1144")
    assert rows[0]["api_url"].endswith("/id/1144")


def test_parse_search_page_rejects_non_native_or_out_of_scope_results():
    payload = {"totalResults": 1, "items": [{"collectionAlias": "other", "itemId": "1144",
                "filetype": "pdf", "title": "Aida-fantasie"}]}
    try:
        csun.parse_search_page(payload)
    except ValueError as exc:
        assert "escaped the frozen collection" in str(exc)
    else:
        raise AssertionError("out-of-scope collection was accepted")


def test_dmquery_parser_keeps_zero_as_a_valid_native_pointer():
    payload = {"pager": {"start": "1", "maxrecs": "1024", "total": 1},
               "records": [{"collection": "/IGRA-scores", "pointer": 0, "filetype": "pdf",
                            "find": "27.pdf", "title": "A guitar score", "series": "Guitar Solos",
                            "creato": "Composer", "arrang": "", "rights": "Public domain."}]}
    total, start, rows = csun.parse_dmquery_page(payload, expected_start=1)
    assert (total, start) == (1, 1)
    assert rows[0]["native_item_id"] == "0"
    assert rows[0]["source_url"].endswith("/id/0")
    assert csun.classify_item(csun.dmquery_record_as_detail(rows[0]))["outcome"] == "accepted"


def test_documented_dmquery_url_pins_fields_and_offset():
    url = csun.dmquery_url(1025)
    assert "?q=dmQuery/IGRA-scores/" in url
    assert "CISOSEARCHALL^guitar^all^and" in url
    assert "title!series!creato!arrang!rights/nosort/1024/1025/" in url


def test_query_value_prefix_is_only_accepted_at_the_documented_100_byte_limit():
    full = "x" * 100 + " full title"
    assert csun._identity_field_matches("x" * 100, full)
    assert not csun._identity_field_matches("x" * 99, "x" * 99 + " altered")


def test_exact_guitar_solos_and_item_public_domain_note_create_pending_pdf():
    decision = csun.classify_item(item_detail())
    assert decision["outcome"] == "accepted"
    assert decision["instrumentation_evidence"] == "Guitar Solos"
    assert decision["normalized_instrumentation"] == "solo guitar"
    assert decision["rights_note"] == "Public domain."
    assert decision["download_url"] == (
        "https://digital-collections.csun.edu/digital/api/collection/IGRA-scores/id/1144/download")


def test_complete_guitar_declaration_can_qualify_without_guitar_solos_series():
    decision = csun.classify_item(item_detail(title="Etude for two guitars", series="Studies"))
    assert decision["outcome"] == "accepted"
    assert decision["instrumentation_evidence"] == "for two guitars"
    assert decision["normalized_instrumentation"] == "2 guitars"


def test_twenty_four_guitar_solos_does_not_infer_four_performers():
    decision = csun.classify_item(item_detail(
        title="Twenty-four guitar solos", series="The Half Dollar Music Series"))
    assert decision["outcome"] == "accepted"
    assert decision["normalized_instrumentation"] == "solo guitar"


def test_explicit_small_instrumental_ensemble_is_in_scope():
    decision = csun.classify_item(item_detail(title="Serenade for guitar and flute", series="Chamber music"))
    assert decision["outcome"] == "accepted"
    assert decision["normalized_instrumentation"] == "guitar, flute"


def test_other_plucked_strings_voice_and_unknown_instrument_remain_out_of_scope():
    mandolin = csun.classify_item(item_detail(title="Mandolin solo", series="Guitar Solos"))
    voice = csun.classify_item(item_detail(title="Song for voice and guitar", series="Guitar Solos"))
    vocal_accompaniment = csun.classify_item(item_detail(
        title="Goodbye my love goodbye", series="Songs With Guitar Acc."))
    songs_for_guitar = csun.classify_item(item_detail(
        title="Song for guitar", series="Instrumental Music"))
    unknown = csun.classify_item(item_detail(title="Aida-fantasie", series="Classical selections"))
    assert mandolin["outcome"] == "excluded"
    assert voice["outcome"] == "excluded"
    assert vocal_accompaniment["outcome"] == "excluded"
    assert songs_for_guitar["outcome"] == "accepted"
    assert unknown["outcome"] == "pending"


def test_work_title_chorus_and_mixed_vocal_series_do_not_prove_a_voice_part():
    chorus_title = csun.classify_item(item_detail(
        title="The Pilgrims' Chorus from Tannhauser",
        series="Select Solos Arranged For The Guitar"))
    mixed_anthology = csun.classify_item(item_detail(
        title="Gavotte", series="Pastimes. Collection Of Vocal And Instrumental Music For The Guitar"))
    explicit_singer = csun.classify_item(item_detail(
        title="Aria for soprano and guitar", series="Guitar Music"))
    assert chorus_title["outcome"] == "accepted"
    assert chorus_title["normalized_instrumentation"] == "solo guitar"
    assert mixed_anthology["outcome"] == "accepted"
    assert mixed_anthology["normalized_instrumentation"] == "guitar"
    assert explicit_singer["outcome"] == "excluded"


def test_full_metadata_genre_can_support_guitar_relevance_without_player_count():
    detail = item_detail(title="Gavotte", series="Classical Selections")
    detail["fields"].append({"key": "genre", "label": "Period/Style", "value": "Guitar music"})
    decision = csun.classify_item(detail)
    assert decision["outcome"] == "accepted"
    assert decision["normalized_instrumentation"] == "guitar"


def test_bass_electric_and_large_orchestra_are_explicit_exclusions():
    bass = csun.classify_item(item_detail(title="Duet for guitar and bass guitar", series="Chamber music"))
    electric = csun.classify_item(item_detail(title="Solo for electric guitar", series="Guitar Solos"))
    orchestra = csun.classify_item(item_detail(title="Concerto for guitar and full orchestra", series="Concertos"))
    assert bass["outcome"] == electric["outcome"] == orchestra["outcome"] == "excluded"


def test_bare_bass_role_stays_pending_but_double_bass_is_distinguished():
    bare = csun.classify_item(item_detail(title="Concerto for guitar and bass", series="Concertos"))
    double_bass = csun.classify_item(item_detail(
        title="Duet for guitar and double bass", series="Chamber music"))
    assert bare["outcome"] == "pending"
    assert double_bass["outcome"] == "accepted"
    assert double_bass["normalized_instrumentation"] == "guitar, double bass"


def test_unresolved_orchestra_and_alternative_role_remain_pending():
    orchestra = csun.classify_item(item_detail(
        title="Concerto for guitar and orchestra", series="Concertos"))
    alternative = csun.classify_item(item_detail(
        title="For guitar or mandolin", series="Instrumental Scores"))
    assert orchestra["outcome"] == "pending"
    assert alternative["outcome"] == "pending"


def test_missing_or_non_public_domain_rights_never_create_an_asset():
    missing = csun.classify_item(item_detail(rights=""))
    other = csun.classify_item(item_detail(rights="Consult library for reproduction rights."))
    assert missing["outcome"] == other["outcome"] == "pending"
    assert "download_url" not in missing
    assert "download_url" not in other


def test_download_link_must_remain_on_approved_official_host():
    try:
        csun.classify_item(item_detail(download_uri="https://example.org/score.pdf"))
    except ValueError as exc:
        assert "escaped the approved official host" in str(exc)
    else:
        raise AssertionError("external download URL was accepted")


def test_singleitem_relative_download_uri_receives_only_the_digital_mount():
    raw = "/api/collection/IGRA-scores/id/0/download"
    corrected, evidence = csun.resolve_download_uri(raw, "0")
    assert corrected == "https://digital-collections.csun.edu/digital/api/collection/IGRA-scores/id/0/download"
    assert evidence["raw_download_uri"] == raw
    assert evidence["applied_digital_mount"] is True


def test_already_mounted_relative_and_absolute_download_uris_stay_unchanged():
    path = "/digital/api/collection/IGRA-scores/id/0/download"
    expected = "https://digital-collections.csun.edu" + path
    relative, rel_evidence = csun.resolve_download_uri(path, "0")
    absolute, abs_evidence = csun.resolve_download_uri(expected, "0")
    assert relative == absolute == expected
    assert rel_evidence["applied_digital_mount"] is False
    assert abs_evidence["applied_digital_mount"] is False


def test_download_uri_rejects_cross_id_host_and_noncanonical_routes():
    for raw, native_id in [
        ("/api/collection/IGRA-scores/id/1/download", "0"),
        ("https://example.org/api/collection/IGRA-scores/id/0/download", "0"),
        ("/api/collection/IGRA-scores/id/0/file", "0"),
    ]:
        try:
            csun.resolve_download_uri(raw, native_id)
        except ValueError:
            pass
        else:
            raise AssertionError(f"unsafe/noncanonical download route was accepted: {raw}")


def test_registry_proposal_keeps_exact_source_identity_and_human_page_rule():
    proposal = csun.registry_proposal()
    assert proposal["id"] == "csun"
    assert proposal["name"] == "CSUN · IGRA"
    assert proposal["catalog"] == "sources/csun/catalog.json"
    assert "digital-library.csun.edu" in proposal["allowed_hosts"]
    assert proposal["page_url_rules"][0]["path"].endswith("[0-9]+")
    assert proposal["page_url_rules"][0]["human_page"] is True
