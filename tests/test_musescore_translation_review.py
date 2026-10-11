from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from catalog_display import project_title
from catalog_translations import apply_translations
from review_musescore_translations import build, reconcile_responsibilities


ASSETS = ("source_titles_zh.json", "musicians_zh.json", "categories_zh.json")


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def reviewed(original: str, zh: str, **extra) -> dict:
    return {"original": original, "zh": zh, "status": "reference",
            "basis": "existing_exact_review", "reason": "已核对的参考对应。", **extra}


def fixture(root: Path, works: list[dict] | None = None) -> dict:
    catalog = {"schema_version": 1, "source_id": "musescore",
               "categories": [{"id": "solo", "name": "Guitar solo"}],
               "works": works or [{"id": "musescore:42", "title_en": "Lágrima",
                                   "composer_en": "Francisco Tárrega", "category_ids": ["solo"]}]}
    write_json(root / "sources/musescore/catalog.json", catalog)
    payloads = {
        "source_titles_zh.json": {"schema_version": 1, "policy": "preserve this header",
            "entries": {"cglib:1": reviewed("Lágrima", "《泪》", original_composer="Francisco Tárrega",
                display_original="Lágrima", display_zh="《泪》", source_refs=["https://example.org/score/1"]) }},
        "musicians_zh.json": {"schema_version": 1, "entries": {
            "cglib": {"Francisco Tárrega": reviewed("Francisco Tárrega", "弗朗西斯科·塔雷加")}}},
        "categories_zh.json": {"schema_version": 1, "entries": {
            "cglib": {"old": reviewed("Existing collection", "既有曲集")}}},
        "expansion_terminology_zh.json": {"schema_version": 1, "entries": []},
    }
    for name, payload in payloads.items():
        write_json(root / "metadata/translations" / name, payload)
    return catalog


def read_asset(root: Path, name: str) -> dict:
    return json.loads((root / "metadata/translations" / name).read_text())


def test_appending_musescore_preserves_other_entries_and_asset_headers(tmp_path):
    catalog = fixture(tmp_path)
    before = {name: read_asset(tmp_path, name) for name in ASSETS}
    source_bytes = (tmp_path / "sources/musescore/catalog.json").read_bytes()
    report = build(tmp_path, apply=True)
    for name in ASSETS:
        after = read_asset(tmp_path, name)
        for key, value in before[name].items():
            if key != "entries":
                assert after[key] == value
        for key, value in before[name]["entries"].items():
            assert after["entries"][key] == value
    entry = read_asset(tmp_path, ASSETS[0])["entries"]["musescore:42"]
    assert entry["zh"] == entry["display_zh"] == "《泪》"
    assert entry["status"] == "reference"
    assert entry["original"] == catalog["works"][0]["title_en"]
    assert entry["original_composer"] == catalog["works"][0]["composer_en"]
    assert entry["display_original"] == "Lágrima"
    assert (tmp_path / "sources/musescore/catalog.json").read_bytes() == source_bytes
    assert report["records"] == 1
    assert report["new_entries"] == {"title": 1, "composer": 1, "category": 1}
    assert json.loads((tmp_path / "sources/musescore/translation-review.json").read_text())["applied"]


def test_closed_grammar_translates_whole_title_but_retains_unknown_proper_name(tmp_path):
    works = [
        {"id": "musescore:42", "title_en": "Waltz in A minor, Op. 12 No. 2", "composer_en": "", "category_ids": ["solo"]},
        {"id": "musescore:43", "title_en": "Waltz of Zorbax (Version 2)", "composer_en": "stage_fox", "category_ids": ["solo"]},
    ]
    fixture(tmp_path, works)
    build(tmp_path, apply=True)
    entries = read_asset(tmp_path, ASSETS[0])["entries"]
    assert entries["musescore:42"]["status"] == "reference"
    assert entries["musescore:42"]["display_zh"] == "《A小调圆舞曲，作品12 第2号》"
    assert entries["musescore:43"]["status"] == "retained"
    assert entries["musescore:43"]["display_zh"] == "《Waltz of Zorbax (Version 2)》"
    assert entries["musescore:43"]["reason"]
    names = read_asset(tmp_path, ASSETS[1])["entries"]["musescore"]
    assert names[""]["status"] == "not_applicable"
    assert names[""]["zh"] == ""
    assert names["stage_fox"]["status"] == "retained"


@pytest.mark.parametrize("original", ["Traditional", "Trad."])
def test_generic_attribution_labels_preserve_the_existing_description_wording(tmp_path, original):
    fixture(tmp_path, [{"id": "musescore:42", "title_en": "Waltz", "composer_en": original,
                        "category_ids": ["solo"]}])
    build(tmp_path, apply=True)
    row = read_asset(tmp_path, ASSETS[1])["entries"]["musescore"][original]
    assert row["original"] == original
    assert row["zh"] == "传统音乐"
    assert row["status"] == "reference"
    assert row["basis"] == "exact_source_attribution_label"
    assert "不推断" in row["reason"]


def test_full_name_reordering_and_explicit_dates_are_reference_not_identity(tmp_path):
    fixture(tmp_path, [{"id": "musescore:42", "title_en": "Francisco Tárrega - Lágrima",
                        "composer_en": "Tárrega, Francisco, 1852-1909", "category_ids": ["solo"]}])
    build(tmp_path, apply=True)
    title = read_asset(tmp_path, ASSETS[0])["entries"]["musescore:42"]
    name = read_asset(tmp_path, ASSETS[1])["entries"]["musescore"]["Tárrega, Francisco, 1852-1909"]
    assert title["original"] == "Francisco Tárrega - Lágrima"
    assert title["display_original"] == project_title(title["original"], "musescore", title["original_composer"]).title
    assert title["display_zh"] == "《泪》"
    assert name["status"] == "reference"
    assert name["zh"] == "弗朗西斯科·塔雷加"
    assert "不" in name["reason"]
    assert "relations" not in title


@pytest.mark.parametrize("composer", ["Tárrega", "F. Tárrega", "Francisco Tárrega Arr. Mary Jones", "Francisco Tárrega 😀"])
def test_surname_initials_and_role_mixed_attribution_do_not_expand_name(tmp_path, composer):
    fixture(tmp_path, [{"id": "musescore:42", "title_en": "Lágrima", "composer_en": composer, "category_ids": ["solo"]}])
    build(tmp_path, apply=True)
    title = read_asset(tmp_path, ASSETS[0])["entries"]["musescore:42"]
    name = read_asset(tmp_path, ASSETS[1])["entries"]["musescore"][composer]
    assert title["status"] == name["status"] == "retained"
    assert title["display_zh"] == "《Lágrima》"
    assert name["zh"] == composer


def test_native_chinese_title_and_name_remain_source_text_without_false_review(tmp_path):
    fixture(tmp_path, [{"id": "musescore:42", "title_en": "山水，第二曲", "composer_en": "云中客", "category_ids": ["solo"]}])
    build(tmp_path, apply=True)
    title = read_asset(tmp_path, ASSETS[0])["entries"]["musescore:42"]
    name = read_asset(tmp_path, ASSETS[1])["entries"]["musescore"]["云中客"]
    assert title["status"] == name["status"] == "retained"
    assert title["display_zh"] == "《山水，第二曲》"
    assert name["zh"] == "云中客"
    assert "来源" in title["reason"] and "中文" in title["reason"]
    assert "来源" in name["reason"] and "中文" in name["reason"]


def test_reversible_source_encoding_keeps_native_guards_and_reuses_full_name(tmp_path):
    original_title = "Francisco Tárrega – Lágrima".encode("utf-8").decode("latin-1")
    original_composer = "Francisco Tárrega (1852 – 1909)".encode("utf-8").decode("latin-1")
    fixture(tmp_path, [{"id": "musescore:42", "title_en": original_title,
                        "composer_en": original_composer, "category_ids": ["solo"]}])
    build(tmp_path, apply=True)
    title = read_asset(tmp_path, ASSETS[0])["entries"]["musescore:42"]
    name = read_asset(tmp_path, ASSETS[1])["entries"]["musescore"][original_composer]
    assert title["original"] == original_title
    assert title["original_composer"] == original_composer
    assert title["display_original"] == "Lágrima"
    assert title["display_zh"] == "《泪》"
    assert title["status"] == name["status"] == "reference"
    assert name["original"] == original_composer
    assert name["zh"] == "弗朗西斯科·塔雷加"


def test_decoded_chinese_source_title_is_retained_without_semantic_upgrade(tmp_path):
    original = "山水，第二曲".encode("utf-8").decode("latin-1")
    fixture(tmp_path, [{"id": "musescore:42", "title_en": original, "composer_en": "", "category_ids": ["solo"]}])
    build(tmp_path, apply=True)
    title = read_asset(tmp_path, ASSETS[0])["entries"]["musescore:42"]
    assert title["original"] == original
    assert title["display_original"] == "山水，第二曲"
    assert title["display_zh"] == "《山水，第二曲》"
    assert title["status"] == "retained"


def test_numbered_guitar_lessons_have_natural_grammar_and_keep_every_source_number(tmp_path):
    fixture(tmp_path, [{"id": "musescore:42", "title_en": "60 Lessons for 2 Guitars, Op.168/56",
                        "composer_en": "Joseph Küffner", "category_ids": ["solo"]}])
    build(tmp_path, apply=True)
    title = read_asset(tmp_path, ASSETS[0])["entries"]["musescore:42"]
    assert title["status"] == "reference"
    assert title["display_zh"] == "《60首吉他课题（2把吉他），作品168/56》"
    assert title["original"] == "60 Lessons for 2 Guitars, Op.168/56"


def test_exact_title_is_not_reused_for_another_full_attribution(tmp_path):
    fixture(tmp_path, [{"id": "musescore:42", "title_en": "Lágrima", "composer_en": "Another Person", "category_ids": ["solo"]}])
    build(tmp_path, apply=True)
    title = read_asset(tmp_path, ASSETS[0])["entries"]["musescore:42"]
    assert title["status"] == "retained"
    assert title["display_zh"] == "《Lágrima》"


@pytest.mark.parametrize("field,value", [
    ("title_en", "Lágrima No. 2"), ("composer_en", "Another Person"),
])
def test_existing_musescore_exact_guards_fail_before_writing(tmp_path, field, value):
    catalog = fixture(tmp_path)
    build(tmp_path, apply=True)
    catalog["works"][0][field] = value
    write_json(tmp_path / "sources/musescore/catalog.json", catalog)
    before = {name: (tmp_path / "metadata/translations" / name).read_bytes() for name in ASSETS}
    with pytest.raises(ValueError, match="drift"):
        build(tmp_path, apply=True)
    assert {name: (tmp_path / "metadata/translations" / name).read_bytes() for name in ASSETS} == before


def test_existing_display_boundary_and_stale_ids_fail_before_writing(tmp_path):
    fixture(tmp_path)
    build(tmp_path, apply=True)
    path = tmp_path / "metadata/translations" / ASSETS[0]
    data = read_asset(tmp_path, ASSETS[0])
    data["entries"]["musescore:42"]["display_original"] = "Lagrima"
    write_json(path, data)
    with pytest.raises(ValueError, match="display.*drift"):
        build(tmp_path, apply=True)
    data["entries"]["musescore:42"]["display_original"] = "Lágrima"
    data["entries"]["musescore:99"] = copy.deepcopy(data["entries"]["musescore:42"])
    write_json(path, data)
    with pytest.raises(ValueError, match="absent"):
        build(tmp_path, apply=True)


def test_dry_run_is_non_mutating_and_repeated_apply_is_idempotent(tmp_path):
    fixture(tmp_path)
    before = {name: (tmp_path / "metadata/translations" / name).read_bytes() for name in ASSETS}
    report = build(tmp_path)
    assert report["applied"] is False
    assert {name: (tmp_path / "metadata/translations" / name).read_bytes() for name in ASSETS} == before
    assert not (tmp_path / "sources/musescore/translation-review.json").exists()
    build(tmp_path, apply=True)
    after = {name: (tmp_path / "metadata/translations" / name).read_bytes() for name in ASSETS}
    report = build(tmp_path, apply=True)
    assert report["new_entries"] == {"title": 0, "composer": 0, "category": 0}
    assert {name: (tmp_path / "metadata/translations" / name).read_bytes() for name in ASSETS} == after


def test_machine_and_conflicting_reference_text_cannot_be_promoted(tmp_path):
    fixture(tmp_path)
    path = tmp_path / "metadata/translations" / ASSETS[0]
    data = read_asset(tmp_path, ASSETS[0])
    data["entries"]["cglib:1"]["status"] = "machine"
    write_json(path, data)
    build(tmp_path, apply=True)
    assert read_asset(tmp_path, ASSETS[0])["entries"]["musescore:42"]["status"] == "retained"


def test_conflicting_exact_title_and_name_references_are_retained(tmp_path):
    fixture(tmp_path)
    titles = read_asset(tmp_path, ASSETS[0])
    titles["entries"]["boije:2"] = reviewed("Lágrima", "《另一题意》", original_composer="Francisco Tárrega")
    write_json(tmp_path / "metadata/translations" / ASSETS[0], titles)
    names = read_asset(tmp_path, ASSETS[1])
    names["entries"]["boije"] = {"Tárrega, Francisco": reviewed("Tárrega, Francisco", "另一中文姓名")}
    write_json(tmp_path / "metadata/translations" / ASSETS[1], names)
    build(tmp_path, apply=True)
    assert read_asset(tmp_path, ASSETS[0])["entries"]["musescore:42"]["status"] == "retained"
    assert read_asset(tmp_path, ASSETS[1])["entries"]["musescore"]["Francisco Tárrega"]["status"] == "retained"


def test_terminal_parenthesized_authority_dates_can_reuse_a_full_name(tmp_path):
    fixture(tmp_path, [{"id": "musescore:42", "title_en": "Lágrima",
                        "composer_en": "Francisco Tárrega\n(1852 - 1909)", "category_ids": ["solo"]}])
    build(tmp_path, apply=True)
    name = read_asset(tmp_path, ASSETS[1])["entries"]["musescore"]["Francisco Tárrega\n(1852 - 1909)"]
    assert name["original"] == "Francisco Tárrega\n(1852 - 1909)"
    assert name["status"] == "reference"
    assert name["zh"] == "弗朗西斯科·塔雷加"
    assert read_asset(tmp_path, ASSETS[0])["entries"]["musescore:42"]["display_zh"] == "《泪》"


def test_reference_chinese_authority_dates_are_metadata_not_a_conflicting_name(tmp_path):
    fixture(tmp_path)
    names = read_asset(tmp_path, ASSETS[1])
    names["entries"]["dga"] = {"Tárrega, Francisco, 1852-1909": reviewed(
        "Tárrega, Francisco, 1852-1909", "弗朗西斯科·塔雷加，1852-1909")}
    write_json(tmp_path / "metadata/translations" / ASSETS[1], names)
    build(tmp_path, apply=True)
    after = read_asset(tmp_path, ASSETS[1])["entries"]
    assert after["dga"] == names["entries"]["dga"]
    assert after["musescore"]["Francisco Tárrega"]["status"] == "reference"
    assert after["musescore"]["Francisco Tárrega"]["zh"] == "弗朗西斯科·塔雷加"


def test_complete_grammar_can_resolve_differing_genre_reference_wordings(tmp_path):
    fixture(tmp_path, [{"id": "musescore:42", "title_en": "Waltz", "composer_en": "Francisco Tárrega", "category_ids": ["solo"]}])
    titles = read_asset(tmp_path, ASSETS[0])
    titles["entries"]["cglib:2"] = reviewed("Waltz", "《圆舞曲》", original_composer="Francisco Tárrega")
    titles["entries"]["boije:2"] = reviewed("Waltz", "《华尔兹》", original_composer="Francisco Tárrega")
    write_json(tmp_path / "metadata/translations" / ASSETS[0], titles)
    build(tmp_path, apply=True)
    title = read_asset(tmp_path, ASSETS[0])["entries"]["musescore:42"]
    assert title["status"] == "reference"
    assert title["display_zh"] == "《圆舞曲》"
    assert title["basis"] == "complete_musical_title_grammar"


def test_scoped_terms_and_exact_title_context_do_not_translate_partial_words(tmp_path):
    fixture(tmp_path, [{"id": "musescore:42", "title_en": "Krypton Suite", "composer_en": "", "category_ids": ["solo"]}])
    write_json(tmp_path / "metadata/translations/expansion_terminology_zh.json", {"schema_version": 1, "entries": [
        {"original": "Krypton", "zh": "虚构名", "status": "reference", "context": "title_term", "sources": ["dga"]},
        {"original": "Krypton", "zh": "虚构名", "status": "reference", "context": "exact_title"},
    ]})
    build(tmp_path, apply=True)
    title = read_asset(tmp_path, ASSETS[0])["entries"]["musescore:42"]
    assert title["status"] == "retained"
    assert title["display_zh"] == "《Krypton Suite》"


def test_existing_category_native_guard_does_not_accept_changed_label(tmp_path):
    catalog = fixture(tmp_path)
    build(tmp_path, apply=True)
    catalog["categories"][0]["name"] = "Two guitars"
    write_json(tmp_path / "sources/musescore/catalog.json", catalog)
    with pytest.raises(ValueError, match="original drift"):
        build(tmp_path, apply=True)


def test_existing_exact_decision_is_kept_when_reference_assets_later_conflict(tmp_path):
    fixture(tmp_path)
    build(tmp_path, apply=True)
    titles = read_asset(tmp_path, ASSETS[0])
    prior = copy.deepcopy(titles["entries"]["musescore:42"])
    titles["entries"]["boije:2"] = reviewed("Lágrima", "《另一题意》", original_composer="Francisco Tárrega")
    write_json(tmp_path / "metadata/translations" / ASSETS[0], titles)
    build(tmp_path, apply=True)
    assert read_asset(tmp_path, ASSETS[0])["entries"]["musescore:42"] == prior


def test_empty_or_other_source_catalog_is_rejected(tmp_path):
    fixture(tmp_path)
    catalog = json.loads((tmp_path / "sources/musescore/catalog.json").read_text())
    catalog["works"] = []
    write_json(tmp_path / "sources/musescore/catalog.json", catalog)
    with pytest.raises(ValueError, match="empty"):
        build(tmp_path, apply=True)
    catalog["source_id"] = "another_source"
    write_json(tmp_path / "sources/musescore/catalog.json", catalog)
    with pytest.raises(ValueError, match="accepted"):
        build(tmp_path, apply=True)


def test_new_primary_guard_is_used_by_shared_translation_projection(tmp_path):
    catalog = fixture(tmp_path, [{"id": "musescore:42", "title_en": "Francisco Tárrega - Lágrima [Arr: Mary Jones]",
                                "composer_en": "Francisco Tárrega", "category_ids": ["solo"]}])
    build(tmp_path, apply=True)
    isolated = tmp_path / "projection"
    for name in ASSETS:
        data = read_asset(tmp_path, name)
        data["entries"] = ({key: value for key, value in data["entries"].items() if key.startswith("musescore:")}
                           if name == ASSETS[0] else {"musescore": data["entries"]["musescore"]})
        write_json(isolated / "metadata/translations" / name, data)
    work = {**catalog["works"][0], "source_id": "musescore", "title_zh": "", "composer_zh": "", "details": {}}
    data = {"schema_version": 2, "sources": [{"id": "musescore"}], "works": [work], "categories": [
        {"id": 0, "source_id": "musescore", "source_category_id": "solo", "name": "Guitar solo", "name_zh": ""}]}
    apply_translations(isolated, data)
    assert work["title_en"] == catalog["works"][0]["title_en"]
    assert work["display_title_en"] == "Lágrima"
    assert work["display_title_zh"] == "《泪》"
    assert work["details"]["arranger"] == "Mary Jones"
    assert work["details"]["source_title_transcription"] == catalog["works"][0]["title_en"]


def responsibility_fixture(root: Path) -> tuple[dict, str]:
    catalog = fixture(root, [
        {"id": "musescore:42", "title_en": "Lágrima", "composer_en": "Artist: Francisco Tárrega", "category_ids": ["solo"]},
        {"id": "musescore:43", "title_en": "Waltz", "composer_en": "Francisco Tárrega", "category_ids": ["solo"]},
        {"id": "musescore:44", "title_en": "Lágrima", "composer_en": "", "category_ids": ["solo"]},
    ])
    build(root, apply=True)
    originals = {"42": "Artist: Francisco Tárrega", "43": "Francisco Tárrega",
                 "44": "Composer: Francisco Tárrega\nArr for guitar: Mary Jones\n"}
    frozen = {"schema_version": 1, "complete": True, "records": {}}
    from source_adapters.musescore import _composer
    for work in catalog["works"]:
        native = work["id"].split(":", 1)[1]
        raw = originals[native]
        composer, role, note, fields = _composer(raw)
        work["composer_en"] = composer
        work["metadata"] = {"source_composer_attribution": raw, "source_title": work["title_en"],
                            "attribution_role": role, "source_attribution_note": note, **fields}
        frozen["records"][native] = {"data": {"score": {
            "id": int(native), "title": work["title_en"], "composer_name": raw}}}
    write_json(root / "sources/musescore/catalog.json", catalog)
    write_json(root / "sources/musescore/pdmx/selected-metadata.json", frozen)
    digest = hashlib.sha256((root / "sources/musescore/catalog.json").read_bytes()).hexdigest()
    return catalog, digest


def test_explicit_responsibility_reconciliation_only_changes_affected_musescore_entries(tmp_path):
    catalog, digest = responsibility_fixture(tmp_path)
    before = {name: read_asset(tmp_path, name) for name in ASSETS}
    report_path = tmp_path / "sources/musescore/translation-review.json"
    preceding = json.loads(report_path.read_text())
    preceding["preservation_verification"] = {"prior_assets": {"existing": "keep this evidence"}}
    preceding["attribution_label_review"] = [{"reason": "preserve prior exact label decision"}]
    write_json(report_path, preceding)
    report = reconcile_responsibilities(tmp_path, catalog_sha256=digest, apply=True)
    for name in ASSETS:
        after = read_asset(tmp_path, name)
        assert {k: v for k, v in after.items() if k != "entries"} == {k: v for k, v in before[name].items() if k != "entries"}
        for key, value in before[name]["entries"].items():
            if (not key.startswith("musescore:")) and key != "musescore":
                assert after["entries"][key] == value
    titles = read_asset(tmp_path, ASSETS[0])["entries"]
    assert titles["musescore:43"] == before[ASSETS[0]]["entries"]["musescore:43"]
    assert titles["musescore:42"]["original_composer"] == ""
    assert titles["musescore:42"]["status"] == "retained"
    assert titles["musescore:44"]["original_composer"] == "Francisco Tárrega"
    assert titles["musescore:44"]["display_zh"] == "《泪》"
    musicians = read_asset(tmp_path, ASSETS[1])["entries"]["musescore"]
    assert "Artist: Francisco Tárrega" not in musicians
    assert musicians["Francisco Tárrega"] == before[ASSETS[1]]["entries"]["musescore"]["Francisco Tárrega"]
    assert musicians[""]["status"] == "not_applicable"
    assert report["preservation_verification"] == preceding["preservation_verification"]
    stage = report["responsibility_reconciliation"][-1]
    assert stage["changed_title_count"] == 2
    assert set(stage["decisions"]) == {"musescore:42", "musescore:44"}
    assert stage["decisions"]["musescore:42"]["before"] == before[ASSETS[0]]["entries"]["musescore:42"]
    assert stage["decisions"]["musescore:44"]["after"] == titles["musescore:44"]
    assert stage["decisions"]["musescore:42"]["before_composer_decision"] == before[ASSETS[1]]["entries"]["musescore"]["Artist: Francisco Tárrega"]
    assert stage["decisions"]["musescore:42"]["after_composer_decision"] == musicians[""]
    assert stage["decisions"]["musescore:42"]["reason"]
    assert stage["retired_musician_entries"]["Artist: Francisco Tárrega"]["decision"] == before[ASSETS[1]]["entries"]["musescore"]["Artist: Francisco Tárrega"]
    assert all(row["asset_header_unchanged"] and row["other_source_entries_unchanged"] for row in stage["preservation"].values())
    assert hashlib.sha256((tmp_path / "sources/musescore/catalog.json").read_bytes()).hexdigest() == digest
    assert report["records"] == len(catalog["works"])
    assert report["new_entries"] == {"title": 0, "composer": 0, "category": 0}
    build(tmp_path, apply=True)
    after_append = json.loads(report_path.read_text())
    assert after_append["responsibility_reconciliation"] == report["responsibility_reconciliation"]
    assert after_append["preservation_verification"] == preceding["preservation_verification"]
    assert after_append["attribution_label_review"] == preceding["attribution_label_review"]


def test_responsibility_reconciliation_preview_and_repeated_apply_are_non_mutating(tmp_path):
    _, digest = responsibility_fixture(tmp_path)
    paths = [tmp_path / "metadata/translations" / name for name in ASSETS]
    paths.append(tmp_path / "sources/musescore/translation-review.json")
    before = {path: path.read_bytes() for path in paths}
    preview = reconcile_responsibilities(tmp_path, catalog_sha256=digest)
    assert preview["applied"] is False
    assert {path: path.read_bytes() for path in paths} == before
    reconcile_responsibilities(tmp_path, catalog_sha256=digest, apply=True)
    before = {path: path.read_bytes() for path in paths}
    repeated = reconcile_responsibilities(tmp_path, catalog_sha256=digest, apply=True)
    assert repeated["new_entries"] == {"title": 0, "composer": 0, "category": 0}
    assert {path: path.read_bytes() for path in paths} == before


@pytest.mark.parametrize("defect", ["catalog_checksum", "native_title", "stale_id", "display_guard", "raw_attribution", "invented_composer", "changed_category"])
def test_responsibility_reconciliation_rejects_unrelated_or_unguarded_drift(tmp_path, defect):
    catalog, digest = responsibility_fixture(tmp_path)
    if defect == "catalog_checksum":
        digest = "0" * 64
    elif defect == "native_title":
        catalog["works"][0]["title_en"] = "Different title"
    elif defect == "stale_id":
        catalog["works"][0]["id"] = "musescore:99"
    elif defect == "display_guard":
        titles = read_asset(tmp_path, ASSETS[0])
        titles["entries"]["musescore:42"]["display_original"] = "Wrong boundary"
        write_json(tmp_path / "metadata/translations" / ASSETS[0], titles)
    elif defect == "raw_attribution":
        catalog["works"][0]["metadata"]["source_composer_attribution"] = "Artist: Another Person"
    elif defect == "invented_composer":
        catalog["works"][0]["composer_en"] = "Another Person"
    elif defect == "changed_category":
        catalog["categories"][0]["name"] = "A new category"
    if defect not in {"catalog_checksum", "display_guard"}:
        write_json(tmp_path / "sources/musescore/catalog.json", catalog)
        digest = hashlib.sha256((tmp_path / "sources/musescore/catalog.json").read_bytes()).hexdigest()
    paths = [tmp_path / "metadata/translations" / name for name in ASSETS]
    paths.append(tmp_path / "sources/musescore/translation-review.json")
    before = {path: path.read_bytes() for path in paths}
    with pytest.raises(ValueError):
        reconcile_responsibilities(tmp_path, catalog_sha256=digest, apply=True)
    assert {path: path.read_bytes() for path in paths} == before
