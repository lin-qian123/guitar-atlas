"""Translation claims must agree with field values and recorded evidence."""
import pytest

from catalog_sources import load_registry
from validate_public_site import PublicSiteValidationError, validate_payload


def evidence(status="reviewed", **changes):
    return {"status": status, "basis": "review", "reason": "参考译名审校", **changes}


@pytest.fixture
def catalog():
    sources = [{key: source[key] for key in ("id", "name", "homepage")}
               for source in load_registry()]
    for source in sources:
        source.update(record_count=1, category_count=1)
    imslp_url = "https://imslp.org/wiki/Study_(A,_Person)"
    data = {
        "schema_version": 2, "translation_schema_version": 1, "sources": sources,
        "families": [{"id": "pure", "name_en": "Guitar", "name_zh": "吉他"},
                     {"id": "classclef", "name_en": "ClassClef", "name_zh": "来源目录"}],
        "categories": [
            {"id": 0, "name": "For guitar", "name_zh": "吉他", "family": "pure", "kind": "original",
             "source_id": "imslp", "source_name": "IMSLP", "source_url": "https://imslp.org/wiki/Category:For_guitar",
             "imslp_url": "https://imslp.org/wiki/Category:For_guitar", "work_count": 1, "translation": evidence()},
            {"id": 1, "name": "Guitar Scores", "name_zh": "吉他乐谱", "family": "classclef", "kind": "unspecified",
             "source_id": "classclef", "source_name": "ClassClef", "source_url": "https://www.classclef.com/",
             "work_count": 1, "translation": evidence("reference")},
        ],
        "works": [
            {"id": "42", "source_record_id": "42", "source_id": "imslp", "source_name": "IMSLP",
             "source_url": imslp_url, "imslp_url": imslp_url, "title_en": "Study", "title_zh": "《练习曲》",
             "composer_en": "A, Person", "composer_zh": "甲某", "category_ids": [0], "formats": ["PDF"],
             "translation": {"title": evidence(), "composer": evidence()}, "translation_status": "reviewed"},
            {"id": "classclef:42", "source_record_id": "42", "source_id": "classclef", "source_name": "ClassClef",
             "source_url": "https://www.classclef.com/lagrima/", "title_en": "Lagrima", "title_zh": "",
             "composer_en": "B Person", "composer_zh": "", "category_ids": [1], "formats": ["PDF"],
             "translation": {"title": evidence("untranslated", basis="", reason=""),
                             "composer": evidence("untranslated", basis="", reason="")},
             "translation_status": "untranslated"},
        ],
        "summary": {"source_count": 2, "category_count": 2, "category_record_count": 2, "unique_work_count": 2},
    }
    return data


def test_translation_contract_accepts_evidenced_translations_and_honest_gaps(catalog):
    assert validate_payload(catalog)["unique_works"] == 2


@pytest.mark.parametrize("version", [None, 0, 2, True, "1", {}])
def test_translation_contract_version_is_explicit_and_typed(catalog, version):
    catalog["translation_schema_version"] = version
    with pytest.raises(PublicSiteValidationError, match="translation_schema_version"):
        validate_payload(catalog)


def test_legacy_fixture_without_translation_contract_still_works(catalog):
    catalog.pop("translation_schema_version")
    for row in catalog["categories"] + catalog["works"]:
        row.pop("translation")
    assert validate_payload(catalog)["unique_works"] == 2


def test_field_evidence_cannot_silently_omit_its_contract_version(catalog):
    catalog.pop("translation_schema_version")
    with pytest.raises(PublicSiteValidationError, match="translation_schema_version"):
        validate_payload(catalog)


@pytest.mark.parametrize("status", ["reviewed", "reference", "machine"])
@pytest.mark.parametrize("value", ["", "《Lagrima》"])
def test_translated_status_cannot_claim_empty_or_english_only_chinese_title(catalog, status, value):
    row = catalog["works"][1]
    row["title_zh"] = value
    row["translation"]["title"] = evidence(status)
    with pytest.raises(PublicSiteValidationError, match="Chinese display value"):
        validate_payload(catalog)


@pytest.mark.parametrize("collection,field", [("works", "composer"), ("categories", None)])
def test_english_musician_and_category_labels_are_not_chinese_translations(catalog, collection, field):
    row = catalog[collection][0]
    if field:
        row["composer_zh"] = row["composer_en"]
    else:
        row["name_zh"] = row["name"]
    with pytest.raises(PublicSiteValidationError, match="Chinese display value"):
        validate_payload(catalog)


@pytest.mark.parametrize("bad", [None, "reviewed", {}, {"title": evidence()},
                                  {"title": evidence(), "composer": evidence(), "other": evidence()}])
def test_every_work_requires_both_field_evidence_objects(catalog, bad):
    catalog["works"][0]["translation"] = bad
    with pytest.raises(PublicSiteValidationError, match="translation evidence"):
        validate_payload(catalog)


@pytest.mark.parametrize("bad", [None, [], "reviewed", {"status": {}}, {"status": "invented"},
                                  {"status": "reviewed", "reason": "checked"},
                                  {"status": "reviewed", "basis": "checked"},
                                  evidence(basis=None), evidence(reason=[]), evidence(basis=" ")])
def test_invalid_field_evidence_is_rejected(catalog, bad):
    catalog["works"][0]["translation"]["title"] = bad
    with pytest.raises(PublicSiteValidationError, match="translation"):
        validate_payload(catalog)


@pytest.mark.parametrize("bad", [None, "reference", {}, evidence("retained", reason="")])
def test_categories_require_field_evidence_too(catalog, bad):
    catalog["categories"][0]["translation"] = bad
    with pytest.raises(PublicSiteValidationError, match="category 0"):
        validate_payload(catalog)


def test_retained_title_allows_original_fallback_with_a_reason(catalog):
    row = catalog["works"][0]
    row["title_en"], row["title_zh"] = "K", ""
    row["translation"]["title"] = evidence("retained", reason="作者以单个字母作为原题。")
    assert validate_payload(catalog)["unique_works"] == 2
    row["translation"]["title"]["reason"] = ""
    with pytest.raises(PublicSiteValidationError, match="retained"):
        validate_payload(catalog)


def test_untranslated_must_not_hide_an_existing_chinese_value(catalog):
    catalog["works"][0]["translation"]["composer"] = evidence("untranslated")
    with pytest.raises(PublicSiteValidationError, match="untranslated"):
        validate_payload(catalog)


@pytest.mark.parametrize("status", ["untranslated", "retained", "not_applicable"])
def test_whitespace_cannot_mask_a_source_name_with_a_blank_display(catalog, status):
    row = catalog["works"][0]
    row["composer_zh"] = " "
    row["translation"]["composer"] = evidence(status)
    with pytest.raises(PublicSiteValidationError, match=status):
        validate_payload(catalog)


def test_retained_title_cannot_display_empty_book_title_marks(catalog):
    row = catalog["works"][0]
    row["title_zh"] = "《》"
    row["translation"]["title"] = evidence("retained")
    with pytest.raises(PublicSiteValidationError, match="display title"):
        validate_payload(catalog)


def test_not_applicable_only_for_absent_source_attribution(catalog):
    row = catalog["works"][0]
    row["translation"]["composer"] = evidence("not_applicable", basis="", reason="")
    with pytest.raises(PublicSiteValidationError, match="not_applicable"):
        validate_payload(catalog)
    row["composer_en"] = row["composer_zh"] = ""
    assert validate_payload(catalog)["unique_works"] == 2


@pytest.mark.parametrize("title_status,composer_status,aggregate", [
    ("reviewed", "reviewed", "reviewed"), ("retained", "reviewed", "reviewed"),
    ("reference", "reviewed", "reference"), ("machine", "reference", "machine"),
    ("machine", "untranslated", "untranslated"), ("retained", "not_applicable", "retained"),
])
def test_aggregate_uses_the_weakest_translated_field(catalog, title_status, composer_status, aggregate):
    row = catalog["works"][0]
    row["translation"] = {"title": evidence(title_status), "composer": evidence(composer_status)}
    if composer_status in {"untranslated", "not_applicable"}:
        row["composer_zh"] = ""
    if composer_status == "not_applicable":
        row["composer_en"] = ""
    row["translation_status"] = aggregate
    assert validate_payload(catalog)["unique_works"] == 2
    row["translation_status"] = "machine" if aggregate != "machine" else "reviewed"
    with pytest.raises(PublicSiteValidationError, match="aggregate"):
        validate_payload(catalog)


@pytest.mark.parametrize("status", [None, {}, [], True, "unreviewed"])
def test_aggregate_status_cannot_be_arbitrary(catalog, status):
    catalog["works"][0]["translation_status"] = status
    with pytest.raises(PublicSiteValidationError, match="aggregate"):
        validate_payload(catalog)
