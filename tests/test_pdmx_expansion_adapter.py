"""Exact identity guards for the append-only PDMX file-review route."""
from copy import deepcopy

import pytest

from source_adapters.pdmx_expansion import validate_candidate


def example():
    title, composer = "Étude, No. 1 & Guitar", "F. Sor"
    source_url = "https://musescore.com/performer/scores/654"
    row = {"metadata": "./metadata/1/654.json", "title": "Étude No. 1 & Guitar", "composer_name": composer,
           "license": "cc-zero", "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
           "license_conflict": "False", "subset:no_license_conflict": "True", "subset:all_valid": "True",
           "tracks": "0", "n_tracks": "1", "has_lyrics": "False", "n_lyrics": "0",
           "pdf": "./pdf/1/x.pdf", "mxl": "./mxl/1/x.mxl", "mid": "./mid/1/x.mid"}
    score = {"id": 654, "title": title, "composer_name": composer, "url": source_url,
             "user": {"id": 321, "name": "Uploader", "url": "https://musescore.com/performer"},
             "parts": 1, "parts_names": ["Guitar"], "instruments": [{"name": "Guitar", "count": 1}],
             "instrumentations": [{"name": "Solo Guitar"}], "license": "cc-zero",
             "pages_count": 2, "keysig": "C major, A minor"}
    metadata = {"status_code": 200, "data": {"score": score, "license_url": row["license_url"]},
                "score": {"id": 654, "title": title.replace("&", "&amp;"), "url": source_url,
                          "user": deepcopy(score["user"]), "isPublic": True,
                          "share": {"publicUrl": "https://musescore.com/user/321/scores/654"}}}
    return row, metadata


def test_append_candidate_has_exact_identity_but_no_claim_of_file_scope_or_players():
    row, metadata = example()
    before = deepcopy((row, metadata))
    record, reason, evidence = validate_candidate(row, metadata)
    assert reason == "pending_actual_file_review"
    assert record["id"] == "musescore:654"
    assert record["title_en"] == metadata["data"]["score"]["title"]
    assert record["source_url"] == metadata["data"]["score"]["url"]
    assert record["instrumentation_status"] == "unspecified"
    assert record["metadata"]["scope_status"] == "pending_review"
    assert record["metadata"]["instrumentation_basis"] == "pending_actual_file_review"
    assert record["metadata"]["guitar_player_count"] is None
    assert record["metadata"]["instrumentation"] == "Solo guitar"
    assert record["assets"] == [{"format": name, "status": "metadata_only"} for name in ("MIDI", "MUSICXML", "PDF")]
    assert record["metadata"]["pdmx_csv_transcription"] == row
    assert record["metadata"]["source_instruments"] == metadata["data"]["score"]["instruments"]
    assert evidence["identity"]["title"]["status"] == "html_entity_equivalent"
    assert evidence["identity"]["pages"]["status"] == "verified_native_alias"
    assert (row, metadata) == before


def test_gm_zero_unknown_instrument_and_lyrics_are_preserved_only_as_pending():
    row, metadata = example()
    row.update(has_lyrics="True", n_lyrics="10")
    metadata["data"]["score"]["instruments"] = [{"name": "Unclassified local name", "count": 5}]
    metadata["data"]["score"]["parts_names"] = ["Unknown role", "Electric Guitar", "Voice"]
    record, reason, evidence = validate_candidate(row, metadata)
    assert record and reason == "pending_actual_file_review"
    assert record["metadata"]["instrumentation"] == "Guitar-related source declaration; file scope pending"
    assert record["metadata"]["source_parts_names"] == ["Unknown role", "Electric Guitar", "Voice"]
    assert evidence["lyrics"] == {"has_lyrics": "True", "n_lyrics": "10", "review_required": True}
    assert evidence["source_instrumentation_outcome"] == "unknown_or_excluded_instrument"


@pytest.mark.parametrize("field,value,reason", [
    ("metadata", "./metadata/1/999.json", "native_id_mismatch"),
    ("title", "Changed", "csv_title_mismatch"),
    ("composer_name", "Other person", "csv_composer_mismatch"),
    ("license", "publicdomain", "license_mismatch"),
    ("license_url", "https://example.com/license", "license_url_mismatch"),
    ("license_conflict", "True", "license_conflict"),
    ("subset:no_license_conflict", "False", "license_conflict"),
    ("subset:all_valid", "False", "invalid_publication_subset"),
    ("subset:all_valid", "NA", "invalid_publication_subset"),
])
def test_csv_identity_license_and_valid_subset_guards_remain_strict(field, value, reason):
    row, metadata = example()
    row[field] = value
    record, actual, evidence = validate_candidate(row, metadata)
    assert record is None and actual == reason
    assert evidence["reason"] == reason


@pytest.mark.parametrize("location,field,value,reason", [
    ("mirror", "id", 999, "native_id_mismatch"),
    ("mirror", "title", "Another work", "metadata_title_mismatch"),
    ("mirror", "url", "https://musescore.com/user/999/scores/654", "source_url_mismatch"),
    ("score", "url", "https://musescore.com/another/scores/654", "invalid_source_url"),
    ("score", "is_private", 1, "is_private"),
    ("score", "is_draft", True, "is_draft"),
    ("score", "is_official", True, "is_official"),
    ("score", "is_blocked", 1, "is_blocked"),
    ("mirror", "isPublic", False, "private_or_blocked_snapshot"),
    ("mirror", "isBlocked", 1, "private_or_blocked_snapshot"),
    ("data", "hidden", True, "restricted_snapshot"),
    ("data", "is_blocked", True, "restricted_snapshot"),
    ("data", "score_blocked_by_country", True, "restricted_snapshot"),
])
def test_raw_metadata_conflicts_and_private_or_restricted_snapshots_are_not_reconciled(location, field, value, reason):
    row, metadata = example()
    target = metadata["data"]["score"] if location == "score" else metadata["score"] if location == "mirror" else metadata["data"]
    target[field] = value
    record, actual, _ = validate_candidate(row, metadata)
    assert record is None and actual == reason


def test_cannot_infer_guitar_scope_from_title_or_instrument_names():
    row, metadata = example()
    metadata["data"]["score"]["instruments"] = [{"name": "Piano", "count": 1}]
    metadata["data"]["score"]["parts_names"] = ["Piano"]
    record, reason, evidence = validate_candidate(row, metadata)
    assert record and reason == "pending_actual_file_review"
    assert record["metadata"]["scope_status"] == "pending_review"
    assert evidence["source_instrumentation_outcome"] == "no_explicit_guitar"


def test_responsibility_roles_download_restrictions_and_display_recovery_reuse_existing_rules():
    row, metadata = example()
    raw_composer = "Arranged by An Arranger"
    row["composer_name"] = raw_composer
    metadata["data"]["score"]["composer_name"] = raw_composer
    metadata["data"].update(is_download_limited=True, paywall={"has_instant_paywall": True})
    record, reason, _ = validate_candidate(row, metadata)
    assert reason == "pending_actual_file_review"
    assert record["composer_en"] == ""
    assert record["metadata"]["arranger"] == "An Arranger"
    assert record["metadata"]["source_composer_attribution"] == raw_composer
    assert record["metadata"]["historical_file_access_restrictions"] == ["download_limit", "paywall"]
    assert record["metadata"]["attribution_role"] == "arranger"


def test_actual_title_or_uploader_disagreement_never_uses_alias_recovery():
    row, metadata = example()
    metadata["score"]["user"]["id"] = 999
    record, reason, _ = validate_candidate(row, metadata)
    assert record is None and reason == "uploader_identity_mismatch"


def test_private_contact_title_is_rejected_and_contact_attribution_stays_private():
    row, metadata = example()
    metadata["data"]["score"]["composer_name"] = "contact@example.com"
    row["composer_name"] = "contactexample.com"
    record, _, _ = validate_candidate(row, metadata)
    assert record and record["composer_en"] == ""
    assert record["metadata"]["source_composer_attribution"] == "contact@example.com"
    for score in (metadata["score"], metadata["data"]["score"]):
        score["title"] = "contact@example.com"
    row["title"] = "contactexample.com"
    assert validate_candidate(row, metadata)[:2] == (None, "private_contact_or_url_in_title")
