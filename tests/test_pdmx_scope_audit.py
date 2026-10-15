import csv
from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest


SPEC = importlib.util.spec_from_file_location("audit_pdmx_scope", Path(__file__).resolve().parents[1] / "scripts/audit_pdmx_scope.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def row(**changes):
    result = {"metadata": "./metadata/1/101.json", "tracks": "0", "n_tracks": "1",
              "license": "cc-zero", "license_conflict": "False", "subset:no_license_conflict": "True",
              "song_name": "NA", "title": "Unnamed", "subtitle": "NA", "genres": "NA", "groups": "NA", "tags": "NA"}
    result.update(changes)
    return result


def test_zero_program_guitar_title_is_recall_not_gm_candidate():
    observation = MODULE.classify(row(title="Guitar Composition"))
    assert observation["signals"] == ["title_guitar_keyword"]
    assert observation["gm_programs"] == [0]


def test_multilingual_title_and_related_instruments_are_distinct():
    observation = MODULE.classify(row(title="Peça para violão / 吉他 / гитара", tags="ukulele lute"))
    assert set(observation["signals"]) == {"title_guitar_keyword", "context_related_plucked_keyword"}
    assert "violao" in observation["keyword_matches"]["title_guitar_keyword"]["title"]


def test_electric_and_acoustic_programs_are_distinct_overlapping_signals():
    observation = MODULE.classify(row(tracks="24-27-30", n_tracks="3"))
    assert set(observation["signals"]) == {"gm_acoustic_24_25", "gm_other_guitar_26_31"}


def test_invalid_program_does_not_create_approved_gm_signal():
    observation = MODULE.classify(row(tracks="24-139", n_tracks="2"))
    assert observation["program_validation_error"] == "invalid_program_range"
    assert observation["signals"] == []


def test_conflict_keeps_recall_but_not_legacy_eligibility():
    observation = MODULE.classify(row(title="Guitar", license_conflict="True"))
    assert observation["signals"] == ["title_guitar_keyword"]
    assert observation["legacy_license_eligible"] is False


def test_tiers_partition_csv_and_preserve_overlapping_signals(tmp_path):
    path = tmp_path / "PDMX.csv"
    source = [row(tracks="24", title="Guitar", metadata="./metadata/1/101.json"),
              row(tracks="27", metadata="./metadata/1/102.json"),
              row(title="Solo guitar tab", metadata="./metadata/1/103.json"),
              row(title="Lute tablature", metadata="./metadata/1/104.json"),
              row(title="Lute", metadata="./metadata/1/105.json"),
              row(title="Piano", metadata="./metadata/1/106.json")]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=source[0])
        writer.writeheader()
        writer.writerows(source)
    result = MODULE.audit(path, accepted_ids=["101"], previous_exclusions=[{"source_record_id": "103", "reason": "title_mismatch"}])
    assert result["counts"]["dataset_rows"] == 6
    assert sum(result["mutually_exclusive_tiers"].values()) == 6
    assert set(result["mutually_exclusive_tiers"].values()) == {1}
    assert result["overlapping_signals"]["title_guitar_keyword"] == 2
    assert result["overlapping_signals"]["title_tablature_keyword"] == 2
    assert result["unique_native_ids"] == 6
    assert len(result["recall_rows"]) == 5
    assert result["recall_rows"][0]["previous_status"] == "existing_924"
    assert result["recall_rows"][2]["previous_status"] == "previous_metadata_excluded:title_mismatch"


def test_title_entity_evidence_is_single_decode_and_preserves_native_fields():
    original = "Sailor's Hat & Guitar"
    mirror = "Sailor&#039;s Hat &amp; Guitar"
    evidence = MODULE.title_identity_evidence(original, mirror)
    assert evidence["equivalent"] is True
    assert evidence["status"] == "html_entity_equivalent"
    assert evidence["source_title"] == original
    assert evidence["mirror_title"] == mirror
    assert MODULE.title_identity_evidence("A & B", "A &amp;amp; B")["equivalent"] is False
    assert MODULE.title_identity_evidence("Étude", "Etude")["equivalent"] is False
    assert MODULE.title_identity_evidence("Guitar Solo", "Guitar solo")["equivalent"] is False


def test_named_and_numeric_native_pages_require_the_same_uploader_and_home():
    source = "https://musescore.com/performer/scores/654"
    observed = [{"field": "score.url", "value": "https://musescore.com/user/321/scores/654"},
                {"field": "score.share.url", "value": "https%3A%2F%2Fmusescore.com%2Fuser%2F321%2Fscores%2F654", "percent_encoded": True}]
    before = deepcopy(observed)
    evidence = MODULE.score_page_identity_evidence(source, observed, native_id="654", uploader_id="321", uploader_home="https://musescore.com/performer")
    assert evidence["equivalent"] is True
    assert evidence["status"] == "verified_native_alias"
    assert all(item["status"] == "same_native_id_uploader_alias" for item in evidence["observations"])
    assert observed == before
    assert not MODULE.score_page_identity_evidence(source, observed, native_id="654", uploader_id="321", uploader_home="https://musescore.com/another")["equivalent"]


@pytest.mark.parametrize("url", [
    "https://musescore.com/user/999/scores/654", "https://musescore.com/user/321/scores/999",
    "https://musescore.com/another/scores/654", "https://musescore.com/user/321/scores/654?secret=x",
    "https://musescore.com/user/321/scores/654/download", "https://musescore.com.evil.test/user/321/scores/654",
    "https://user:pass@musescore.com/user/321/scores/654", "http://musescore.com/user/321/scores/654",
    None,
])
def test_page_alias_evidence_rejects_changed_identity_and_non_page_urls(url):
    evidence = MODULE.score_page_identity_evidence("https://musescore.com/user/321/scores/654",
        [{"field": "score.url", "value": url}], native_id="654", uploader_id="321", uploader_home="https://musescore.com/performer")
    assert evidence["equivalent"] is False
    assert evidence["status"] == "invalid"


def test_url_evidence_rejects_vacuous_or_double_encoded_equivalence():
    source = "https://musescore.com/user/321/scores/654"
    assert not MODULE.score_page_identity_evidence(source, [], native_id="654", uploader_id="321", uploader_home="")["equivalent"]
    evidence = MODULE.score_page_identity_evidence(source,
        [{"field": "score.share.url", "value": "https%253A%252F%252Fmusescore.com%252Fuser%252F321%252Fscores%252F654", "percent_encoded": True}],
        native_id="654", uploader_id="321", uploader_home="")
    assert evidence["equivalent"] is False


def test_legacy_recovery_is_read_only_and_keeps_lyrics_as_a_review_boundary():
    csv_row = row(title="Hat & Guitar", metadata="./metadata/1/654.json", tracks="24", n_lyrics="1", has_lyrics="True",
                  composer_name="F. Sor", license_url="https://creativecommons.org/publicdomain/zero/1.0/", pdf="./pdf/1/x.pdf", mxl="./mxl/1/x.mxl", mid="./mid/1/x.mid")
    url = "https://musescore.com/performer/scores/654"
    score = {"id": 654, "title": "Hat & Guitar", "composer_name": "F. Sor", "url": url,
             "user": {"id": 321, "name": "Uploader", "url": "https://musescore.com/performer"},
             "parts": 1, "parts_names": ["Guitar"], "instruments": [{"name": "Guitar", "count": 1}], "instrumentations": [], "license": "cc-zero"}
    metadata = {"status_code": 200, "data": {"score": score, "license_url": csv_row["license_url"]},
                "score": {"id": 654, "title": "Hat &amp; Guitar", "url": "https://musescore.com/user/321/scores/654", "isPublic": True}}
    candidate = {"source_record_id": "654", "csv_line": 2, "csv": csv_row}
    selection, records = {"candidates": [candidate]}, {"654": metadata}
    before = deepcopy((selection, records))
    result = MODULE.legacy_recovery_audit(selection, records, [{"source_record_id": "654", "reason": "metadata_title_mismatch"}])
    assert (selection, records) == before
    assert result["counts"] == {"html_entity_title_only": 1, "same_native_id_uploader_url_alias": 1, "potential_guitar_records_lyrics_manual_review": 1}
    assert result["rows"][0]["strict_outcome_after_representation_repair"] == "lyrics"
    assert result["rows"][0]["lyrics_manual_file_review_candidate"] is True
