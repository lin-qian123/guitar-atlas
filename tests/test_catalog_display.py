from __future__ import annotations

import copy
import json

import pytest

from catalog_display import apply_display_projection, project_title
from catalog_translations import wrap_display_title
from catalog_sources import load_registry
from export_public_site import build_public_catalog
from validate_public_site import validate_payload, PublicSiteValidationError
from tests.test_public_site import make_library, write_json
from tests.test_catalog_sources import add_source


def item(title, source="dga", zh="", composer=""):
    return {"id": source + ":7", "source_id": source, "title_en": title,
            "title_zh": zh, "composer_en": composer, "composer_zh": composer,
            "resource_type": "score", "details": {}}


@pytest.mark.parametrize("title", [
    "[18 pieces for guitar]", "[No title]", "Study No.4, Op.40 [Moonlight]",
    "Acalanto das nonas [berceuse]", "Apollo No. [3-4]",
    "Minuetto. [Andante - Allegretto]", "Suite No. 2: 1895",
    "No. 28 Malbroug[h s’en va-t-en guerre]", "Title; Musical subtitle",
])
def test_editorial_music_title_brackets_and_numbers_are_not_dirty_fields(title):
    assert project_title(title, "dga").title == title


@pytest.mark.parametrize("raw, expected", [
    ("《题名》", "《题名》"), ("《题名》副标题", "《〈题名〉副标题》"),
    ("题名《副题》", "《题名〈副题〉》"),
    ("《题名《内层》》", "《题名〈内层〉》"),
    ("《题名〈内层〉》", "《题名〈内层〉》"),
])
def test_title_wrapper_preserves_whole_text_and_inner_pairs(raw, expected):
    assert wrap_display_title(raw) == expected
    assert wrap_display_title(expected) == expected


def test_labelled_arranger_moves_without_changing_raw_guard_or_native_identity():
    work = item("BWV 528 Andante (Organ Sonata No. 4) [Arr: Edson Lopes]", "classclef",
                "《BWV 528 行板（第4号管风琴奏鸣曲）[Edson Lopes改编]》")
    original = copy.deepcopy(work)
    apply_display_projection(work)
    assert work["id"] == original["id"]
    assert work["title_en"] == original["title_en"]
    assert work["title_zh"] == original["title_zh"]
    assert work["display_title_en"] == "BWV 528 Andante (Organ Sonata No. 4)"
    assert work["display_title_zh"] == "《BWV 528 行板（第4号管风琴奏鸣曲）》"
    assert work["details"]["arranger"] == "Edson Lopes"
    assert work["details"]["source_title_transcription"] == original["title_en"]
    once = copy.deepcopy(work)
    assert apply_display_projection(work) == once


@pytest.mark.parametrize("spacing", ["\u00a0", "  ", "\t"])
def test_spacing_only_projection_keeps_exact_source_and_review_boundary(spacing):
    original = "Variations sur un thême favori de l’opera" + spacing + "Amazilla"
    work = item(original, "delcamp", "《歌剧〈Amazilla〉主题变奏曲》")
    expected = "Variations sur un thême favori de l’opera Amazilla"
    assert project_title(original, "delcamp").rules == []
    apply_display_projection(work)
    assert work["display_title_en"] == expected
    assert work["title_en"] == original
    assert work["title_zh"] == "《歌剧〈Amazilla〉主题变奏曲》"
    assert "source_title_note" not in work
    once = copy.deepcopy(work)
    assert apply_display_projection(work) == once


def test_parenthesized_arranger_preserves_the_real_musical_subtitle():
    original = "Asturias (Leyenda), (arr. Santiago Navascués)"
    work = item(original, "dga", "《阿斯图里亚斯（传奇），（Santiago Navascués编曲）》")
    apply_display_projection(work)
    assert work['display_title_en'] == 'Asturias (Leyenda)'
    assert work['display_title_zh'] == '《阿斯图里亚斯（传奇）》'
    assert work['details']['arranger'] == 'Santiago Navascués'
    assert work['title_en'] == work['details']['source_title_transcription'] == original


def test_exact_ragtime_guitar_publisher_boundary_preserves_damaged_source_credit():
    raw = 'Ragtime guitar [sound Joplin and Joseph Lamb / transcribed and arranged by Paul Lolax]'
    source_name = 'Joplin, Scott, 1868-1917'
    row = item(raw, 'dga', '《拉格泰姆吉他》', source_name)
    apply_display_projection(row)
    assert row['display_title_en'] == 'Ragtime guitar'
    assert row['title_en'] == row['details']['source_title_transcription'] == raw
    assert row['composer_en'] == source_name
    assert row['title_zh'] == '《拉格泰姆吉他》'
    assert row['details']['title_annotations'] == raw[len('Ragtime guitar '):]
    assert '载体或责任转录残缺' in row['details']['text_quality_note']
    assert 'resource_type' in row and row['resource_type'] == 'score'
    assert 'arranger' not in row['details']
    assert 'sound' not in row['display_title_en']
    assert 'exact_evidence_title_boundary' not in project_title(raw, 'dga', 'Joseph Lamb').rules
    assert 'exact_evidence_title_boundary' not in project_title(raw, 'cglib', source_name).rules
    assert 'exact_evidence_title_boundary' not in project_title(raw.replace('[sound', '[sound recording'), 'dga', source_name).rules
    once = copy.deepcopy(row)
    assert apply_display_projection(row) == once


@pytest.mark.parametrize('source,credit', [
    ('classclef', 'Arranged by Jubing Kristianto'), ('classclef', 'Arr by Roland Dyens'),
    ('classclef', 'Arr: by Tarrega'), ('cglib', 'arr. Emilio Pujol'),
    ('werner', 'arr. Tarrega'), ('delcamp', 'Arr. J. Mertz'),
])
def test_explicit_parenthesized_arranger_across_sources(source, credit):
    row = item('Title (real musical subtitle) (' + credit + ')', source)
    apply_display_projection(row)
    assert row['display_title_en'] == 'Title (real musical subtitle)'
    assert row['details']['arranger']
    assert row['title_en'].endswith('(' + credit + ')')


def test_bearb_preserves_ambiguous_editing_adaptation_role_as_source_credit():
    row = item('Méthode complète pour la guitare, (bearb. N. Coste)', 'dga')
    apply_display_projection(row)
    assert row['display_title_en'] == 'Méthode complète pour la guitare'
    assert row['details']['responsibility_statement'] == 'bearb. N. Coste'
    assert 'arranger' not in row['details']


@pytest.mark.parametrize('credit', ['Arranged Tarrega', 'Arr J K Mertz', 'Arr Tarrega', 'Arr Roland Dyens'])
def test_observed_literal_classclef_arranger_labels(credit):
    row = item('Song (' + credit + ')', 'classclef')
    apply_display_projection(row)
    assert row['display_title_en'] == 'Song'
    assert row['details']['arranger']
    unverified = item('Song (Arranged differently)', 'classclef')
    apply_display_projection(unverified)
    assert 'display_title_en' not in unverified


def test_editor_initials_require_exact_local_source_attribution():
    row = item('Aria: La gazza ladra / A. Diabelli (ed.)', 'dga', composer='Diabelli, Anton')
    apply_display_projection(row)
    assert row['display_title_en'] == 'Aria: La gazza ladra'
    assert row['details']['editor'] == 'A. Diabelli'
    assert row['details']['attribution_role'] == 'editor'
    other = item('Aria: La gazza ladra / A. Diabelli (ed.)', 'dga', composer='Other, Composer')
    apply_display_projection(other)
    assert 'display_title_en' not in other


def test_chinese_credit_prefix_and_combined_catalogue_reference_stay_separate():
    row = item('Libertango (Arr: Dyens)', 'classclef', '《自由探戈（编曲：迪恩斯）》')
    apply_display_projection(row)
    assert row['display_title_zh'] == '《自由探戈》'
    merged = item('Passacaglia (Arr: David Russell) (HWV 432 Suite No 7)', 'classclef',
                  '《帕萨卡利亚（戴维·拉塞尔改编；HWV432，第7组曲）》')
    apply_display_projection(merged)
    assert merged['display_title_zh'] == '《帕萨卡利亚（HWV432，第7组曲）》'
    assert merged['display_title_en'] == 'Passacaglia (HWV 432 Suite No 7)'
    assert merged['details']['arranger'] == 'David Russell'


@pytest.mark.parametrize("source, title, expected, material", [
    ("boije", '"Du gamla, du friska." [Handskrift]', '"Du gamla, du friska."', "Handskrift"),
    ("loc", "Cluck Old Hen [music transcription]", "Cluck Old Hen", "music transcription"),
    ("dga", "Famous guitar music [sound recording]", "Famous guitar music", "sound recording"),
])
def test_only_known_explicit_material_annotations_are_separated(source, title, expected, material):
    work = item(title, source)
    apply_display_projection(work)
    assert work["display_title_en"] == expected
    assert work["details"]["source_type"] == material
    assert work["title_en"] == title


def test_rism_fallback_label_retains_missing_title_and_moves_holding_information():
    work = item("[No title]; Manuscript copy; I-Mt 55", "rism", "《[无题名]；手稿抄本；I-Mt 55》")
    apply_display_projection(work)
    assert work["display_title_en"] == "[No title]"
    assert work["details"]["source_type"] == "Manuscript copy"
    assert "I-Mt 55" in work["details"]["source_title_transcription"]
    assert work["display_title_zh"] == ""  # No positional guess in the translation.


def test_dga_bibliographic_statement_preserves_genre_and_moves_publisher_tail():
    title = "CAN I FORGET TO LOVE THEE MARY! / Ballad / MUSIC COMPOSED BY / William R. Dempster. / 2 pp. Lithography."
    work = item(title, zh="《我可以忘记爱你吗玛丽！ / 民谣 / 音乐作曲 / 威廉·邓普斯特。 / 2页。平版印刷。》")
    apply_display_projection(work)
    assert work["display_title_en"] == "CAN I FORGET TO LOVE THEE MARY! Ballad"
    assert work["display_title_zh"] == "《我可以忘记爱你吗玛丽！ 民谣》"
    assert work["details"]["responsibility_statement"].startswith("MUSIC COMPOSED BY")
    assert work["details"]["source_title_transcription"] == title


def test_dga_misaligned_translation_keeps_complete_draft_without_guessing_title_words():
    work = item("Title / by A. Example", zh="《题名，作者A.Example》")
    apply_display_projection(work)
    assert work["display_title_en"] == "Title"
    assert work["display_title_zh"] == ""
    assert work["details"]["translated_title_transcription"] == "《题名，作者A.Example》"


def test_dga_full_name_statement_is_strictly_guarded_and_does_not_accept_a_surname():
    title = "Solo guitar work / Jean Dupont; guitar"
    work = item(title, composer="Dupont, Jean")
    apply_display_projection(work)
    assert work["display_title_en"] == "Solo guitar work"
    assert work["details"]["responsibility_statement"] == "Jean Dupont; guitar"
    ambiguous = item("Solo guitar work / Dupont", composer="Dupont, Jean")
    apply_display_projection(ambiguous)
    assert "display_title_en" not in ambiguous


@pytest.mark.parametrize("title, expected", [
    ("Op.31Etude n18 (Sor,Fernando)", "Op.31Etude n18"),
    ("Study by Fernando Sor", "Study"), ("Fernando Sor : Study", "Study"),
])
def test_generic_author_field_requires_a_complete_source_name_correspondence(title, expected):
    work = item(title, "cglib", composer="Sor, Fernando")
    apply_display_projection(work)
    assert work["display_title_en"] == expected
    assert work["title_en"] == title
    assert work["details"]["responsibility_statement"]
    subtitle = item("Study (Moonlight)", "cglib", composer="Sor, Fernando")
    apply_display_projection(subtitle)
    assert "display_title_en" not in subtitle


def test_chinese_author_postfix_uses_exact_checked_name_without_trimming_real_subtitle():
    work = item("Op.31 Etude n18 (Sor,Fernando)", "cglib", zh="《作品31第18号练习曲（费尔南多·索尔）》", composer="Sor, Fernando")
    work["composer_zh"] = "费尔南多·索尔"
    apply_display_projection(work)
    assert work["display_title_zh"] == "《作品31第18号练习曲》"


def test_library_source_authority_dates_are_notes_not_rewritten_person_keys():
    work = item("Solo", composer="Sor, Fernando <1778-1839>")
    apply_display_projection(work)
    assert work["composer_en"] == "Sor, Fernando <1778-1839>"
    assert work["display_composer_en"] == "Sor, Fernando"
    assert work["details"]["source_attribution_note"] == "Sor, Fernando （1778-1839）"
    assert work["details"]["attribution_role"] == "source_unspecified"


@pytest.mark.parametrize("name, display", [
    ("Albert, Heinrich @guitarist^", "Albert, Heinrich (guitarist)"),
    ("Morris, William @composer^", "Morris, William (composer)"),
    ("Zimmermann, H. @guitar composer^", "Zimmermann, H. (guitar composer)"),
])
def test_exact_source_identity_disambiguation_is_readable_without_changing_identity_or_claiming_a_role(name, display):
    work = item("Title", "imslp", composer=name)
    apply_display_projection(work)
    assert work["display_composer_en"] == display
    assert work["composer_en"] == name
    assert work["details"]["source_attribution_note"] == name
    assert "attribution_role" not in work["details"]


@pytest.mark.parametrize("original, expected", [
    ("Albéniz, Isaac, 1860-1909", "Albéniz, Isaac"),
    ("Person, Name, 1956-", "Person, Name"),
    ("Person, Name, 1870", "Person, Name"),
    ("Person, Name, 1784-1849. ", "Person, Name"),
    ("Person, Name, 1860-05-29–1909-05-18", "Person, Name"),
    ("Person, Name, ?-1895", "Person, Name"),
    ("Band 1900", "Band 1900"), ("Number No. 1860", "Number No. 1860"),
])
def test_comma_authority_date_is_a_display_annotation_not_part_of_the_name(original, expected):
    work = item("Title", composer=original)
    apply_display_projection(work)
    assert work.get("display_composer_en", original) == expected
    assert work["composer_en"] == original


def test_chinese_authority_date_is_moved_with_exact_full_transcription_preserved():
    work = item("Title", composer="Albéniz, Isaac, 1860-1909")
    work["composer_zh"] = "伊萨克·阿尔贝尼斯，1860-1909"
    apply_display_projection(work)
    assert work["display_composer_zh"] == "伊萨克·阿尔贝尼斯"
    assert "伊萨克·阿尔贝尼斯，1860-1909" in work["details"]["source_attribution_note"]
    assert work["composer_zh"] == "伊萨克·阿尔贝尼斯，1860-1909"


@pytest.mark.parametrize("statement, accepted", [
    ("I. Albéniz; transcripcion para guitarra de A. Sinopoli.", True),
    ("I. Albéniz; transcripción para guitarra de A. Sinopoli.", True),
    ("I. Albéniz; trascrizione per chitarra di A. Sinopoli.", True),
    ("I. Albéniz; musical subtitle", False),
    ("R. Albéniz; transcripcion para guitarra de A. Sinopoli.", False),
    ("Albéniz; transcripcion para guitarra de A. Sinopoli.", False),
])
def test_abbreviated_source_name_needs_matching_initials_and_an_explicit_transcription_role(statement, accepted):
    title = "Asturias-leyenda: preludio / " + statement
    work = item(title, composer="Albéniz, Isaac, 1860-1909")
    apply_display_projection(work)
    assert (work.get("display_title_en") == "Asturias-leyenda: preludio") is accepted
    assert work["title_en"] == title


def test_cglib_explicit_transcriber_is_a_field_and_never_invented_as_the_composer():
    title = "Asturias (Leyenda) Transcribed by Andres Segovia"
    work = item(title, "cglib", zh="《阿斯图里亚斯（传奇） Transcribed by Andres Segovia》", composer="Albeniz. Isaac")
    apply_display_projection(work)
    assert work["display_title_en"] == "Asturias (Leyenda)"
    assert work["display_title_zh"] == "《阿斯图里亚斯（传奇）》"
    assert work["details"]["transcriber"] == "Andres Segovia"
    assert work["composer_en"] == "Albeniz. Isaac"
    assert work["title_en"] == title


def test_explicit_secondary_poem_credit_is_not_part_of_the_arranger_name():
    title = "Home sweet home guitar solo varied arranged by Wm. Foden poem by J.H. Payne"
    work = item(title, "cglib")
    apply_display_projection(work)
    assert work["display_title_en"] == "Home sweet home guitar solo varied"
    assert work["details"]["arranger"] == "Wm. Foden"
    assert work["details"]["contributors"] == "poem by J.H. Payne"
    assert work["details"]["responsibility_statement"] == "arranged by Wm. Foden poem by J.H. Payne"
    assert work["title_en"] == title


def test_explicit_bracketed_arranged_role_is_a_bibliographic_boundary():
    title = "Mel Bay's classic guitar duets: in 1st & 2nd position / [arranged] by Walt Lawry."
    work = item(title, zh="《" + title + "》")
    apply_display_projection(work)
    assert work["display_title_en"] == "Mel Bay's classic guitar duets: in 1st & 2nd position"
    assert work["details"]["responsibility_statement"] == "[arranged] by Walt Lawry."
    assert work["title_en"] == title


def test_unclosed_explicit_collection_preserves_music_brackets_and_source_truncation():
    title = 'Minuetto. [Andante - Allegretto] [from "Journal de Pièces de Musique pour la Guitare ... tous les trois'
    work = item(title, zh="《" + title + "》")
    apply_display_projection(work)
    assert work["display_title_en"] == "Minuetto. [Andante - Allegretto]"
    assert work["display_title_zh"] == "《Minuetto. [Andante - Allegretto]》"
    assert work["details"]["collection"] == '"Journal de Pièces de Musique pour la Guitare ... tous les trois'
    assert "未闭合" in work["details"]["text_quality_note"]
    assert work["details"]["source_title_transcription"] == title


@pytest.mark.parametrize("head, collection_tail, expected_collection", [
    ("No. 4 Le Juif / Nouvelle /Voyez, messieurs mes demoiselles...",
     " /[LES SEPT PÉCHÉS CAPITAUX / Esquises Morales, / Paroles de Mr. J. J. / Musique de / GUSTAVE CARULLI / Arrangée pour la Guitare par F. Carulli.",
     "LES SEPT PÉCHÉS CAPITAUX Esquises Morales,"),
    ("No. 10 Les Pécheurs des Lagunes / Barcarolle / Le soleil se léve...",
     " / [Les douze Romances Chansonnettes & Nocturnes suivans forment / L'Abum [sic] Lyrique / Pour 1834 / Composée sur les Paroles de Mr. A\xa0: Betourné / PAR / THEODORE LABARRE",
     "Les douze Romances Chansonnettes & Nocturnes suivans forment L'Abum [sic] Lyrique Pour 1834"),
])
def test_exact_source_collection_declarations_keep_the_individual_number_genre_and_incipit(head, collection_tail, expected_collection):
    title = head + collection_tail
    work = item(title, zh="《" + title + "》")
    apply_display_projection(work)
    assert work["display_title_en"] == head.replace(" / ", " ").replace(" /", " ")
    assert work["details"]["collection"] == expected_collection
    assert "Paroles" in work["details"]["responsibility_statement"]
    assert work["details"]["source_title_transcription"] == title
    unrelated = item("No. 1 [LES SEPT PÉCHÉS CAPITAUX]", zh="《第一号[七宗罪]》")
    apply_display_projection(unrelated)
    assert "display_title_en" not in unrelated


def test_directory_book_is_not_invented_as_the_composer_named_in_its_title():
    work = item("From the lute book", "delcamp", composer="Folger’s Dowland Lute Book")
    apply_display_projection(work)
    assert work["display_composer_en"] == "来源署名待核"
    assert work["details"]["attribution_role"] == "unverified_name"
    assert work["composer_en"] == "Folger’s Dowland Lute Book"


def test_directory_exact_polluted_author_label_keeps_title_and_native_id():
    original = "Johann Kaspar Mertz Op. 14. Fantasie aus der Oper"
    work = item("Opera Fantasia", "delcamp", composer=original)
    apply_display_projection(work)
    assert work["display_composer_en"] == "Johann Kaspar Mertz"
    assert work["details"]["source_attribution_note"] == original
    assert work["title_en"] == "Opera Fantasia"
    checked = item("Opera Fantasia", "delcamp", composer=original)
    checked["composer_zh"] = "约翰·卡斯帕·默茨"
    checked["translation"] = {"composer": {"status": "reference"}}
    apply_display_projection(checked)
    assert "display_composer_zh" not in checked
    assert checked["composer_zh"] == "约翰·卡斯帕·默茨"


def test_explicit_performer_never_becomes_a_composer_assertion():
    work = item("Romantic guitar", composer="Hole\x1aek, Josef, 1939- Performer")
    apply_display_projection(work)
    assert work["details"]["attribution_role"] == "performer"
    assert work["display_composer_en"] == "Hole□ek, Josef"
    assert "\\u001a" in work["details"]["source_attribution_note"]
    assert "未恢复" in work["details"]["text_quality_note"]
    assert "\x1a" in work["composer_en"]  # Exact source spelling remains guarded.


def test_source_extent_dimensions_and_part_descriptions_are_not_page_counts():
    dimension_only = item("Manuscript")
    dimension_only["details"]["pages"] = "30 x 24 cm. 12 staffs lined by hand."
    apply_display_projection(dimension_only)
    assert "pages" not in dimension_only["details"]
    assert dimension_only["details"]["dimensions"] == "30 x 24 cm"
    assert "12 staffs" in dimension_only["details"]["physical_description"]
    counted = item("Printed source")
    counted["details"]["pages"] = "47 p. of ms. music ; 10 x 16 cm."
    apply_display_projection(counted)
    assert counted["details"]["pages"] == "47 p. of ms. music"
    assert counted["details"]["dimensions"] == "10 x 16 cm"
    parts = item("Parts")
    parts["details"]["pages"] = "3 St."
    apply_display_projection(parts)
    assert "pages" not in parts["details"]
    assert parts["details"]["physical_description"] == "3 St."


def test_download_locator_cannot_be_reintroduced_as_public_title_transcription():
    work = item('Title [Arr: Player] a href="https://example.test/private.pdf">PDF', "classclef")
    apply_display_projection(work)
    assert "source_title_transcription" not in work["details"]


def dga_fixture(tmp_path, raw_format, notes=""):
    make_library(tmp_path)
    raw = add_source(tmp_path)
    registry = json.loads((tmp_path / "config/sources.json").read_text())
    source = registry["sources"][1]
    source["id"] = raw["source_id"] = "dga"
    raw["works"][0].update(id="dga:42", metadata={"source_fields": {"format": raw_format, "source_notes1": notes}})
    write_json(tmp_path / "config/sources.json", registry)
    write_json(tmp_path / source["catalog"], raw)
    data = build_public_catalog(tmp_path)
    validate_payload(data, registry=load_registry(tmp_path))
    return data, next(row for row in data["works"] if row["source_id"] == "dga")


@pytest.mark.parametrize("raw_format, notes, material", [
    ("Audio CD", "", "recording"),
    ("1 sound disc: 33 1/3 rpm, stereo.; 12 in.", "", "recording"),
    ("", "Zeitschrift", "journal"), ("", "Sekundärliteratur", "reference_text"),
    ("2 v.: ill., music, ports.; 30 cm + 2 sound discs", "", None),
    ("", "Periodical amusements mentioned in catalogue note", None),
])
def test_material_type_requires_an_explicit_main_carrier_not_a_keyword(tmp_path, raw_format, notes, material):
    _, projected = dga_fixture(tmp_path, raw_format, notes)
    assert projected["details"].get("material_type") == material


def test_new_display_field_and_material_enums_fail_closed(tmp_path):
    data, projected = dga_fixture(tmp_path, "Audio CD")
    projected["display_title_en"] = ["not a string"]
    with pytest.raises(PublicSiteValidationError, match="display_title_en"):
        validate_payload(data, registry=load_registry(tmp_path))
    projected["display_title_en"] = "Title"
    projected["details"]["material_type"] = "guessed_recording"
    with pytest.raises(PublicSiteValidationError, match="material type"):
        validate_payload(data, registry=load_registry(tmp_path))
