from audit_catalog_text import audit, title_number_defects


def catalog(**overrides):
    row = {"id": "test:1", "source_id": "test", "title_en": "Air, Op.12 No.3", "title_zh": "《曲调，作品12，第3首》",
           "composer_en": "Composer, A.", "composer_zh": "A. Composer", "details": {"source_call": "Shelf 18"},
           "contents": [], "translation": {"title": {"status": "reference"}, "composer": {"status": "retained"}}}
    row.update(overrides)
    return {"works": [row], "categories": [{"id": 1, "source_id": "test", "name": "Guitar", "name_zh": "吉他", "translation": {"status": "reference"}}], "sources": [{"id": "test"}]}


def test_all_visible_fields_and_music_context_errors_are_checked():
    data = catalog(title_zh="《空气，操作。12，第3名》", details={"editor": "<b>Editor</b>"})
    report = audit(data)
    assert report["text_field_count"] == 7
    assert report["counts"]["error"] == {"number_as_rank": 1, "opus_mistranslation": 1, "rendered_markup": 1}
    assert report["counts"]["review"] == {"air_music_sense": 1, "music_terminology_air_as_substance": 1}
    assert not report["ready_for_detected_defects"]


def test_editorial_brackets_and_descriptive_air_are_not_certified_errors():
    report = audit(catalog(title_en="[Untitled] Air", title_zh="《[无题]空气》"))
    assert report["ready_for_detected_defects"]
    assert report["counts"]["review"] == {"air_music_sense": 1, "music_terminology_air_as_substance": 1}


def test_supplied_display_title_is_audited_without_losing_raw_provenance():
    report = audit(catalog(title_en="Op.12 Air [Manuscript]", display_title_zh="《曲调，作品12》"))
    assert report["ready_for_detected_defects"]
    assert report["field_counts"]["display_title_zh"] == 1


def test_catalog_years_and_page_numbers_are_not_title_number_errors():
    assert title_number_defects("Air 1820 [22 pages]", "《曲调》") == []
    assert title_number_defects("Air, Op.12 No.3", "《曲调，作品112，第33首》") == [("opus_digit_review", "12"), ("number_digit_review", "3")]
    assert title_number_defects("Air, Op.12 No.3", "《曲调，作品12，第3首》") == []
    assert title_number_defects("Op.31Etude n18", "《Op.31练习曲n18》") == []
    assert title_number_defects("Op.11bis Air", "《曲调，作品11bis》") == []


def test_unknown_proper_names_not_guessed_or_flagged_as_missing_chinese():
    report = audit(catalog(composer_zh="Composer, A."))
    assert report["ready_for_detected_defects"]
    assert report["translation_states"]["composer_zh:retained"] == 1


def test_review_labels_are_errors_in_headings_and_preserved_as_detail_text():
    report = audit(catalog(title_en="Gavotte, f.113", title_zh="《加沃特舞曲（原目录标记：f.113）》"))
    assert report["counts"]["error"] == {"review_label_in_primary_title": 1}
    assert not report["ready_for_detected_defects"]
    report = audit(catalog(title_en="Gavotte, f.113", title_zh="《加沃特舞曲（原目录标记：f.113）》",
                          display_title_zh="《加沃特舞曲》",
                          details={"translated_title_transcription": "《加沃特舞曲（原目录标记：f.113）》"}))
    assert report["ready_for_detected_defects"]
    assert report["field_counts"]["details.translated_title_transcription"] == 1
