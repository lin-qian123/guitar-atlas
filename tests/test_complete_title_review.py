import copy
import pytest

from apply_title_review import overlay_display_repairs, overlay_supplements, validate_decisions
from catalog_translations import apply_translations
from title_translation_quality import review_title_entry
from tests.test_catalog_translations import asset
from tests.test_public_site import make_library, write_json
from tests.test_catalog_sources import add_source
from export_public_site import build_public_catalog


def decision():
    return {'id': 'source:1', 'original': 'Suite / supplied bibliography',
            'original_composer': 'A Person', 'zh': '《组曲》', 'status': 'reference',
            'basis': 'exact_semantic_review', 'reason': '书目字段保留于原始转录。',
            'source_refs': [], 'display_original': 'Suite', 'display_zh': '《组曲》'}


def corpus():
    return [{'id': 'source:1', 'original': 'Suite / supplied bibliography',
             'composer': 'A Person', 'display_original': 'Suite'}]


@pytest.mark.parametrize('fault', ['original', 'original_composer', 'display_original', 'missing', 'duplicate', 'machine', 'reviewed_without_refs'])
def test_complete_review_cannot_skip_or_relabel_records(fault):
    row = decision()
    entries = [row]
    if fault in {'original', 'original_composer', 'display_original'}:
        row[fault] = 'different'
    elif fault == 'missing':
        entries = []
    elif fault == 'duplicate':
        entries.append(copy.deepcopy(row))
    elif fault == 'machine':
        row['status'] = 'machine'
    else:
        row['status'] = 'reviewed'
    with pytest.raises(ValueError):
        validate_decisions(corpus(), [{'schema_version': 1, 'entries': entries}])


def test_exact_review_preserves_clean_display_and_evidence_on_refresh():
    row = decision()
    output, _ = review_title_entry('source:1', row['original'], 'A Person',
        {'original': row['original'], 'zh': '《错误草稿》'}, {}, {'source:1': row})
    assert output['display_zh'] == '《组曲》'
    assert output['display_original'] == 'Suite'
    assert output['original_composer'] == 'A Person'


@pytest.mark.parametrize('fault', ['original', 'original_composer', 'display_original', 'unknown', 'duplicate'])
def test_final_research_supplement_cannot_bypass_source_guards(fault):
    row = decision()
    original = validate_decisions(corpus(), [{'schema_version': 1, 'entries': [row]}])
    supplement = copy.deepcopy(row)
    entries = [supplement]
    if fault in {'original', 'original_composer', 'display_original'}:
        supplement[fault] = 'Changed source'
    elif fault == 'unknown':
        supplement['id'] = 'other:1'
    else:
        entries.append(copy.deepcopy(supplement))
    with pytest.raises(ValueError):
        overlay_supplements(corpus(), original, [{'schema_version': 1, 'entries': entries}])


@pytest.mark.parametrize('fault', ['before_zh', 'before_display_zh', 'status', 'duplicate'])
def test_final_display_pass_cannot_overwrite_a_different_semantic_review(fault):
    original = validate_decisions(corpus(), [{'schema_version': 1, 'entries': [decision()]}])
    repair = dict(decision(), before_zh=decision()['zh'], before_display_zh=decision()['display_zh'])
    entries = [repair]
    if fault == 'duplicate':
        entries.append(copy.deepcopy(repair))
    else:
        repair[fault] = 'changed'
    with pytest.raises(ValueError):
        overlay_display_repairs(corpus(), original, {'schema_version': 1, 'entries': entries})


def test_final_display_pass_keeps_complete_translation_in_edition_details(tmp_path):
    make_library(tmp_path)
    raw = add_source(tmp_path)
    original = 'Evening'
    raw['works'][0]['title_en'] = original
    write_json(tmp_path/'sources/classclef/catalog.json', raw)
    full = '《傍晚（原题括注：A Person）》'
    asset(tmp_path, original=original, zh=full)
    import json
    path = tmp_path/'metadata/translations/classclef_titles_zh.json'
    data = json.loads(path.read_text())
    data['entries']['classclef:42'].update(display_original=original, display_zh='《傍晚》')
    write_json(path, data)
    work = next(w for w in build_public_catalog(tmp_path)['works'] if w['id']=='classclef:42')
    assert work['display_title_zh'] == '《傍晚》'
    assert work['title_zh'] == full
    assert work['details']['translated_title_transcription'] == full


def test_source_credit_cannot_supply_chinese_for_a_retained_proper_title():
    row = dict(decision(), original='Zampa (Herold)', original_composer='Herz',
               display_original='Zampa (Herold)', zh='《Zampa（原题署名Herold）》',
               display_zh='《Zampa（原题署名Herold）》')
    source = [{'id':row['id'], 'original':row['original'], 'composer':'Herz',
               'display_original':row['display_original']}]
    original = validate_decisions(source, [{'schema_version':1, 'entries':[row]}])
    repair = dict(row, before_zh=row['zh'], before_display_zh=row['display_zh'],
                  display_zh='《Zampa》', status='retained',
                  basis='explicit_original_title_retention_after_display_review',
                  state_change_basis='chinese_was_metadata_only',
                  reason='题名只有未确认中文的专名，原中文只是来源署名标签，保留原名。')
    result = overlay_display_repairs(source, original, {'schema_version':1, 'entries':[repair]})
    assert result[row['id']]['status'] == 'retained'
    assert result[row['id']]['display_zh'] == '《Zampa》'
    repair.pop('state_change_basis')
    with pytest.raises(ValueError):
        overlay_display_repairs(source, original, {'schema_version':1, 'entries':[repair]})


def test_public_reference_title_cannot_be_chinese_only_in_credit_notes(tmp_path):
    make_library(tmp_path)
    raw = add_source(tmp_path)
    raw['works'][0]['title_en'] = 'Zampa'
    write_json(tmp_path/'sources/classclef/catalog.json', raw)
    asset(tmp_path, original='Zampa', zh='《Zampa（原题署名Herold）》')
    import json
    path = tmp_path/'metadata/translations/classclef_titles_zh.json'
    data = json.loads(path.read_text())
    data['entries']['classclef:42'].update(display_original='Zampa', display_zh='《Zampa》')
    write_json(path, data)
    from validate_public_site import PublicSiteValidationError, validate_payload
    from catalog_sources import load_registry
    with pytest.raises(PublicSiteValidationError, match='primary title'):
        validate_payload(build_public_catalog(tmp_path), registry=load_registry(tmp_path))


def test_reviewed_name_requires_external_reference():
    row = decision()
    row['status'] = 'reviewed'
    with pytest.raises(ValueError, match='HTTPS references'):
        review_title_entry('source:1', row['original'], 'A Person', {'original': row['original']}, {}, {'source:1': row})
    row['source_refs'] = ['https://publisher.example/work']
    assert validate_decisions(corpus(), [{'schema_version': 1, 'entries': [row]}])['source:1']['status'] == 'reviewed'


@pytest.mark.parametrize('state_change_basis', ['unsupported_phonetic_title', 'source_title_ambiguity'])
def test_an_exact_review_can_retain_an_unsupported_or_ambiguous_name(state_change_basis):
    original = dict(decision(), original='Yamko Rambe Yamko', display_original='Yamko Rambe Yamko',
                    zh='《扬科·兰贝·扬科》', display_zh='《扬科·兰贝·扬科》')
    source = [{'id': original['id'], 'original': original['original'],
               'composer': original['original_composer'], 'display_original': original['display_original']}]
    base = validate_decisions(source, [{'schema_version': 1, 'entries': [original]}])
    repair = dict(original, before_zh=original['zh'], before_display_zh=original['display_zh'],
                  zh='《Yamko Rambe Yamko》', display_zh='《Yamko Rambe Yamko》', status='retained',
                  state_change_basis=state_change_basis,
                  basis='explicit_original_title_retention_after_whole_title_review',
                  reason='完整原题复核未取得可靠中文对应，旧音译或专名释义未获支持，采用原名。')
    assert overlay_display_repairs(source, base, {'schema_version': 1, 'entries': [repair]})[original['id']]['status'] == 'retained'
    repair.pop('state_change_basis')
    with pytest.raises(ValueError):
        overlay_display_repairs(source, base, {'schema_version': 1, 'entries': [repair]})


@pytest.mark.parametrize('fault', ['none', 'display', 'composer'])
def test_guarded_primary_translation_survives_projection(tmp_path, fault):
    make_library(tmp_path)
    raw = add_source(tmp_path)
    original = 'Lagrima [Arr: John Smith]'
    raw['works'][0]['title_en'] = original
    write_json(tmp_path/'sources/classclef/catalog.json', raw)
    asset(tmp_path, original=original, zh='《泪（John Smith改编）》')
    path = tmp_path/'metadata/translations/classclef_titles_zh.json'
    import json
    data = json.loads(path.read_text())
    row = data['entries']['classclef:42']
    row.update(display_original='Other' if fault == 'display' else 'Lagrima',
               display_zh='《泪》')
    if fault == 'composer':
        row['original_composer'] = 'Wrong person'
    write_json(path, data)
    if fault != 'none':
        with pytest.raises(ValueError, match='drift'):
            build_public_catalog(tmp_path)
    else:
        work = next(w for w in build_public_catalog(tmp_path)['works'] if w['id']=='classclef:42')
        assert work['display_title_en'] == 'Lagrima'
        assert work['display_title_zh'] == '《泪》'
        assert work['title_en'] == original


def test_nocturne_is_not_a_roman_number_prefix():
    from title_translation_quality import SERIAL
    assert not SERIAL.search('Nocturne')
    assert SERIAL.search('No. C').group(1) == 'C'


def test_explicit_score_filename_suffix_is_a_material_field():
    from catalog_display import project_title
    projected = project_title('45. Romanza Deluxe - Score.pdf', 'freeguitarmusic')
    assert projected.title == '45. Romanza Deluxe'
    assert projected.details == {'source_type': 'Score.pdf'}
    assert projected.rules == ['labelled_score_file']
    # A genuine title containing Score is not a format suffix.
    assert project_title('The Score of the Century', 'freeguitarmusic').title == 'The Score of the Century'


@pytest.mark.parametrize('body,heading', [
    ('Eugenie / Waltz.', 'Eugenie — Waltz'),
    ("Flow'ret, Forget Me Not. / Gavotte.", "Flow'ret, Forget Me Not — Gavotte"),
])
def test_exact_cover_dedication_does_not_replace_the_title(body, heading):
    from catalog_display import project_title
    original = 'Respectfully dedicated to / Mrs. Edward Field / New York / '+body+' / Arranged for / Guitar / by / Charles De Janon'
    result = project_title(original, 'dga', 'De Janon, Charles')
    assert result.title == heading
    assert result.details['arranger'] == 'Charles De Janon'
    assert result.details['title_annotations'].startswith('Respectfully dedicated')
    assert result.rules == ['exact_cover_title_after_dedication']


def test_cover_collection_keeps_extent_and_separates_dedication():
    from catalog_display import project_title
    original = 'DÉDIÉ AUX ESTUDIANTINAS DE FRANCE / Recueil progressif / pour / GUITARE / composé / de Quinze fantaisies faciles / par / A. Battle / Prix net: 3 f. / En Vente chez: / TIXADOR ET POMÉS / Pianos et Musique / 4 Rue Mailly et 1 Rue Alsace Lorraine / PERPIGNAN / Tous drioits réservés. / Imp. C.G. Röder, Paris PN 1 (19--). 10 pp. Lithography.'
    result = project_title(original, 'dga', 'BATTLE, A.')
    assert result.title == 'Recueil progressif pour guitare, composé de Quinze fantaisies faciles'
    assert result.details['title_annotations'] == 'DÉDIÉ AUX ESTUDIANTINAS DE FRANCE'
    assert result.details['responsibility_statement'] == 'par / A. Battle'
    assert '10 pp.' in result.details['physical_description']


@pytest.mark.parametrize('title,attribution', [
    ('Pavane en La – TAB', 'Pavane en La'),
    ('Ernest Shand, Lieder ohne Worte No.5, Op.14', 'Ernest Shand, Lieder ohne Worte No.5'),
    ('Johann Kaspar Mertz Op. 14. Fantasie aus der Oper: Linda von Chamounix, von G. Donizetti', 'Johann Kaspar Mertz Op. 14. Fantasie aus der Oper'),
])
def test_misparsed_attribution_never_consumes_a_real_title(title, attribution):
    from catalog_display import project_title
    assert project_title(title, 'delcamp', attribution).title == title
