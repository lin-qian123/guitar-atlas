import copy
import json

import pytest

from append_source_translations import append


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False))


def set_source_composer(root, composer):
    path = root/'sources/sample/catalog.json'
    catalog = json.loads(path.read_text())
    catalog['works'][0]['composer_en'] = composer
    write(path, catalog)


def add_name_reference(root, source, original, zh):
    path = root/'metadata/translations/musicians_zh.json'
    document = json.loads(path.read_text())
    document['entries'].setdefault(source, {})[original] = {
        'original': original, 'zh': zh, 'status': 'reference',
        'basis': 'checked_name', 'reason': 'reviewed exact spelling'}
    write(path, document)


@pytest.fixture
def library(tmp_path):
    write(tmp_path/'config/sources.json', {'schema_version': 1, 'sources': [
        {'id': 'imslp', 'name': 'IMSLP', 'homepage': 'https://imslp.org/',
         'allowed_hosts': ['imslp.org'], 'adapter': 'imslp_categories'},
        {'id': 'sample', 'name': 'Sample', 'homepage': 'https://sample.example/',
         'allowed_hosts': ['sample.example'], 'adapter': 'normalized_catalog',
         'catalog': 'sources/sample/catalog.json'},
    ]})
    write(tmp_path/'sources/sample/catalog.json', {'schema_version': 1, 'source_id': 'sample',
        'categories': [{'id': 'guitar', 'name': 'Guitar'}], 'works': [
            {'id': 'sample:one', 'title_en': 'Étude No. 2', 'composer_en': 'Matteo Carcassi',
             'category_ids': ['guitar']},
            {'id': 'sample:two', 'title_en': 'Unknown proper name [book 2]',
             'composer_en': 'Carcassi', 'category_ids': ['guitar']},
            {'id': 'sample:three', 'title_en': 'A private tune', 'composer_en': '',
             'category_ids': ['guitar']},
        ]})
    base = {'original': 'Carcassi, Matteo', 'zh': '马泰奥·卡尔卡西', 'status': 'reference',
            'basis': 'checked_name', 'reason': 'checked complete name'}
    docs = {
        'source_titles_zh.json': {'schema_version': 1, 'entries': {'other:old': {
            'original': 'Earlier native title', 'zh': 'Earlier native title',
            'status': 'retained', 'basis': 'frozen', 'reason': 'frozen prior decision'}}},
        'musicians_zh.json': {'schema_version': 1, 'entries': {'other': {'Carcassi, Matteo': base}}},
        'categories_zh.json': {'schema_version': 1, 'entries': {'other': {'old': {
            'original': 'Earlier', 'zh': 'Earlier', 'status': 'retained', 'basis': 'frozen',
            'reason': 'frozen prior decision'}}}},
    }
    for name, doc in docs.items():
        write(tmp_path/'metadata/translations'/name, doc)
    return tmp_path, copy.deepcopy(docs)


def test_append_preserves_frozen_entries_and_distinguishes_missing_attribution(library):
    root, before = library
    result = append(root, ['sample'], apply=True)
    assert result['sources']['sample']['added'] == {'composer': 3, 'category': 1, 'title': 3}
    for name, doc in before.items():
        current = json.loads((root/'metadata/translations'/name).read_text())
        assert all(current['entries'][key] == value for key, value in doc['entries'].items())
    names = json.loads((root/'metadata/translations/musicians_zh.json').read_text())['entries']['sample']
    assert names['Matteo Carcassi']['status'] == 'reference'
    assert names['Carcassi']['status'] == 'retained'  # A surname never supplies a full identity.
    assert names['']['status'] == 'not_applicable'
    titles = json.loads((root/'metadata/translations/source_titles_zh.json').read_text())['entries']
    assert titles['sample:one']['status'] == 'reference'
    assert titles['sample:two']['status'] == 'retained'
    assert '[book 2]' in titles['sample:two']['display_zh']


def test_append_is_idempotent_and_preview_does_not_write(library):
    root, _ = library
    paths = list((root/'metadata/translations').iterdir())
    before = {path: path.read_bytes() for path in paths}
    assert append(root, ['sample'])['applied'] is False
    assert all(path.read_bytes() == body for path, body in before.items())
    append(root, ['sample'], apply=True)
    before = {path: path.read_bytes() for path in paths}
    assert append(root, ['sample'], apply=True)['sources']['sample']['added'] == {}
    assert all(path.read_bytes() == body for path, body in before.items())


def test_exact_original_name_reference_wins_and_keeps_authority_dates(library):
    root, _ = library
    name = 'Giuliani, Mauro, 1781-1829'
    set_source_composer(root, name)
    add_name_reference(root, 'dga', name, '毛罗·朱利亚尼，1781-1829')
    # The normalized full-name fallback is unique after stripping dates, but
    # the exact reviewed spelling must retain the complete checked display.
    add_name_reference(root, 'other', 'Mauro Giuliani', '毛罗·朱利亚尼')

    append(root, ['sample'], apply=True)

    names = json.loads((root/'metadata/translations/musicians_zh.json').read_text())['entries']['sample']
    assert names[name]['zh'] == '毛罗·朱利亚尼，1781-1829'
    assert names[name]['basis'] == 'existing_exact_source_name_reference'
    assert names[name]['reference_entries'] == [f'musicians_zh.json:dga:{name}']


def test_conflicting_exact_name_references_do_not_choose_a_translation(library):
    root, _ = library
    name = 'Frey, E. H.'
    set_source_composer(root, name)
    add_name_reference(root, 'dga', name, 'E.H.·弗雷')
    add_name_reference(root, 'werner', name, '弗雷·E.H.')

    append(root, ['sample'], apply=True)

    names = json.loads((root/'metadata/translations/musicians_zh.json').read_text())['entries']['sample']
    assert names[name]['status'] == 'retained'


def test_normalized_full_name_ambiguity_without_exact_match_is_retained(library):
    root, _ = library
    name = 'Giuliani, Mauro'
    set_source_composer(root, name)
    add_name_reference(root, 'dga', 'Giuliani, Mauro, 1781-1829', '毛罗·朱利亚尼')
    add_name_reference(root, 'werner', 'Mauro Giuliani', '毛罗·朱利亚尼（另一译法）')

    append(root, ['sample'], apply=True)

    names = json.loads((root/'metadata/translations/musicians_zh.json').read_text())['entries']['sample']
    assert names[name]['status'] == 'retained'


def test_initials_only_name_requires_verbatim_match(library):
    root, _ = library
    set_source_composer(root, 'J.S. Bach')
    add_name_reference(root, 'guitardownunder', 'J.S. Bach', '约翰·塞巴斯蒂安·巴赫')
    # This source attribution differs in initials and has no complete-name
    # token match; a surname or partial-initial inference must not fill it.
    catalog_path = root/'sources/sample/catalog.json'
    catalog = json.loads(catalog_path.read_text())
    catalog['works'][1]['composer_en'] = 'J.S. B.'
    write(catalog_path, catalog)

    append(root, ['sample'], apply=True)

    names = json.loads((root/'metadata/translations/musicians_zh.json').read_text())['entries']['sample']
    assert names['J.S. Bach']['zh'] == '约翰·塞巴斯蒂安·巴赫'
    assert names['J.S. Bach']['basis'] == 'existing_exact_source_name_reference'
    assert names['J.S. B.']['status'] == 'retained'


def test_exact_surname_is_display_only_and_never_expands_to_full_name(library):
    root, _ = library
    catalog_path = root/'sources/sample/catalog.json'
    catalog = json.loads(catalog_path.read_text())
    catalog['works'][0]['composer_en'] = 'Carcassi, Matteo'
    catalog['works'][1]['composer_en'] = 'Carcassi'
    write(catalog_path, catalog)
    names_path = root/'metadata/translations/musicians_zh.json'
    write(names_path, {'schema_version': 1, 'entries': {'dga': {
        'Carcassi': {'original': 'Carcassi', 'zh': '卡尔卡西', 'status': 'reference',
                     'basis': 'checked_surname_display', 'reason': 'exact surname display'}}}})

    append(root, ['sample'], apply=True)

    names = json.loads(names_path.read_text())['entries']['sample']
    assert names['Carcassi']['zh'] == '卡尔卡西'
    assert names['Carcassi']['basis'] == 'existing_exact_source_name_reference'
    assert '不推断跨站人物身份' in names['Carcassi']['reason']
    assert names['Carcassi, Matteo']['status'] == 'retained'


def test_exact_category_supplement_requires_native_text_and_human_page_guards(library):
    root, _ = library
    path = root/'metadata/translations/source_supplement_reviewed_zh.json'
    write(path, {'schema_version': 1, 'entries': {}, 'category_entries': {'sample': {
        'guitar': {'original': 'Guitar', 'zh': '吉他', 'reason': '栏目原文直译。',
                   'evidence_url': 'https://sample.example/categories/guitar'}}}})

    append(root, ['sample'], apply=True)

    categories = json.loads((root/'metadata/translations/categories_zh.json').read_text())['entries']['sample']
    assert categories['guitar']['zh'] == '吉他'
    assert categories['guitar']['basis'] == 'checked_exact_source_supplement_category'
    assert categories['guitar']['reference_entries'] == [
        'metadata/translations/source_supplement_reviewed_zh.json:sample:guitar']


@pytest.mark.parametrize('changes,match', [
    ({'original': 'Guitars'}, 'source-text guard drift'),
    ({'evidence_url': 'https://unapproved.example/page'}, 'approved human source page'),
    ({'evidence_url': 'https://sample.example/api/item/1'}, 'approved human source page'),
    ({'zh': ''}, 'must contain checked Chinese text'),
    ({'reason': ''}, 'needs a reason'),
])
def test_manual_category_translation_fails_closed_on_bad_guard_or_evidence(library, changes, match):
    root, _ = library
    path = root/'metadata/translations/source_supplement_reviewed_zh.json'
    entry = {'original': 'Guitar', 'zh': '吉他', 'reason': '栏目原文直译。',
             'evidence_url': 'https://sample.example/categories/guitar'}
    entry.update(changes)
    write(path, {'schema_version': 1, 'entries': {}, 'category_entries': {'sample': {'guitar': entry}}})
    with pytest.raises(ValueError, match=match):
        append(root, ['sample'])


def test_category_translation_does_not_reclassify_native_instrumentation_or_infer_players(library):
    root, _ = library
    native_path = root/'sources/sample/catalog.json'
    catalog = json.loads(native_path.read_text())
    catalog['categories'] = [{'id': 'flexible', 'name': '24 Guitars (source says flexible group size)'}]
    catalog['works'][0]['category_ids'] = ['flexible']
    catalog['works'][0]['instrumentation_status'] = 'source_declared'
    catalog['works'][0]['metadata'] = {
        'instrumentation': 'guitar ensemble', 'player_count': None,
        'instrumentation_source_text': '24 Guitars; group size flexible'}
    write(native_path, catalog)
    original_native = native_path.read_bytes()
    supplement_path = root/'metadata/translations/source_supplement_reviewed_zh.json'
    write(supplement_path, {'schema_version': 1, 'entries': {}, 'category_entries': {'sample': {
        'flexible': {'original': '24 Guitars (source says flexible group size)',
                     'zh': '24把吉他（来源注明人数可调整）',
                     'reason': '保留栏目原文中的示例数及人数可变说明；不将其归一为演奏人数。',
                     'evidence_url': 'https://sample.example/categories/flexible'}}}})

    append(root, ['sample'], apply=True)

    translated = json.loads((root/'metadata/translations/categories_zh.json').read_text())['entries']['sample']['flexible']
    assert translated['zh'] == '24把吉他（来源注明人数可调整）'
    assert native_path.read_bytes() == original_native


@pytest.mark.parametrize('field,value', [('title_en', 'Changed title'), ('composer_en', 'Another Name')])
def test_append_rejects_drift_before_any_assets_are_written(library, field, value):
    root, _ = library
    append(root, ['sample'], apply=True)
    paths = list((root/'metadata/translations').iterdir())
    before = {path: path.read_bytes() for path in paths}
    native = root/'sources/sample/catalog.json'
    catalog = json.loads(native.read_text())
    catalog['works'][0][field] = value
    write(native, catalog)
    with pytest.raises(ValueError, match='drift'):
        append(root, ['sample'], apply=True)
    assert all(path.read_bytes() == body for path, body in before.items())


@pytest.mark.parametrize('original,zh', [
    ('Spanish Traditional', '西班牙传统音乐'),
    ('Russian Traditional', '俄罗斯传统音乐'),
    ('[Various]', '多位作曲家'),
])
def test_literal_attribution_labels_do_not_invent_a_person(library, original, zh):
    root, _ = library
    path = root/'sources/sample/catalog.json'
    doc = json.loads(path.read_text())
    doc['works'][0]['composer_en'] = original
    write(path, doc)
    append(root, ['sample'], apply=True)
    names = json.loads((root/'metadata/translations/musicians_zh.json').read_text())['entries']['sample']
    assert names[original]['original'] == original
    assert names[original]['zh'] == zh
    assert names[original]['basis'] == 'exact_source_attribution_label'
    from review_musescore_translations import ATTRIBUTION_LABELS as legacy
    assert original not in legacy  # Historical producer rules remain frozen.
