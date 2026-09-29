"""Translation review persistence and music-specific draft safeguards."""
import json

import pytest

from build_classclef_translations import assemble, flags, translate_formula, write_json


@pytest.mark.parametrize(('original', 'expected'), [
    ('Prelude in C# Minor', '前奏曲 升C小调'),
    ('Prelude in C#', '前奏曲 升C调'),
    ('Minuet in D', '小步舞曲 D调'),
    ('Sonata In Am (D14) 2 Allegro', '奏鸣曲 A小调 (D14) 2 快板'),
    ('Prelude in Fmin', '前奏曲 F小调'),
    ('Etude in Bb minor', '练习曲 降B小调'),
    ('Prelude (Arranged by Julián Bream)', '前奏曲 (Julián Bream 改编)'),
    ('Poco Allegretto', '稍快板'),
    ('Rain by the Window', None),
])
def test_formula_requires_known_music_terms_and_preserves_explicit_details(original, expected):
    assert translate_formula(original) == expected


def fixture_paths(root, original='Lagrima', ident='classclef:one'):
    workspace = root / 'work/classclef-translation-review'
    source = root / 'sources/classclef/catalog.json'
    asset = root / 'metadata/translations/classclef_titles_zh.json'
    write_json(source, {'works': [{'id': ident, 'title_en': original}]})
    return workspace, source, asset


def reviewed_entry():
    return {'original': 'Lagrima', 'zh': '《泪》', 'status': 'reference',
            'basis': 'individual_review', 'reason': '按原题含义译为泪。',
            'aliases_zh': ['眼泪']}


def test_committed_review_survives_without_private_corrections_and_beats_machine_and_formula(tmp_path):
    workspace, _, asset = fixture_paths(tmp_path)
    curated = reviewed_entry()
    write_json(asset, {'entries': {'classclef:one': curated}})
    write_json(workspace / 'machine-cache.json',
               {'entries': {'Lagrima': {'translation': '未经核验的机器草稿'}}})
    write_json(workspace / 'corrections-formulas.json',
               {'entries': {'classclef:one': {**curated, 'zh': '《低优先级公式》'}}})
    assemble(tmp_path, workspace)
    assert json.loads(asset.read_text())['entries']['classclef:one'] == curated


@pytest.mark.parametrize(('new_id', 'new_title'), [
    ('classclef:new', 'Lagrima'),
    ('classclef:one', 'Changed title'),
])
def test_source_identity_or_title_drift_fails_before_overwriting_review(tmp_path, new_id, new_title):
    workspace, source, asset = fixture_paths(tmp_path)
    write_json(asset, {'entries': {'classclef:one': reviewed_entry()}})
    before = asset.read_bytes()
    write_json(source, {'works': [{'id': new_id, 'title_en': new_title}]})
    with pytest.raises(ValueError):
        assemble(tmp_path, workspace)
    assert asset.read_bytes() == before


def test_failed_draft_is_empty_untranslated_and_cannot_masquerade_as_retained(tmp_path):
    workspace, _, asset = fixture_paths(tmp_path, 'UnknownName')
    assemble(tmp_path, workspace)
    entry = json.loads(asset.read_text())['entries']['classclef:one']
    assert entry['status'] == 'untranslated'
    assert entry['zh'] == ''
    write_json(workspace / 'corrections-invalid.json',
               {'entries': {'classclef:one': {**entry, 'zh': '《UnknownName》'}}})
    before = asset.read_bytes()
    with pytest.raises(ValueError, match='empty Chinese field'):
        assemble(tmp_path, workspace)
    assert asset.read_bytes() == before


def test_conflicting_reviews_fail_before_overwriting_asset(tmp_path):
    workspace, _, asset = fixture_paths(tmp_path)
    write_json(asset, {'entries': {'classclef:one': reviewed_entry()}})
    for filename, text in [('one', '《泪》'), ('two', '《眼泪》')]:
        write_json(workspace / f'corrections-{filename}.json',
                   {'entries': {'classclef:one': {**reviewed_entry(), 'zh': text}}})
    before = asset.read_bytes()
    with pytest.raises(ValueError, match='conflicting independent corrections'):
        assemble(tmp_path, workspace)
    assert asset.read_bytes() == before


def test_diagnostic_accepts_equivalent_keyboard_count_but_flags_lost_work_number():
    assert 'numeric_tokens_changed' not in flags(
        'BWV 988 Goldberg Variation 5 a 1 ô vero 2 Clav',
        '《BWV 988 哥德堡变奏曲第5变奏（单层或双层键盘）》')
    assert 'numeric_tokens_changed' in flags('Prelude Opus 24 No 5', '《前奏曲 作品24》')
    assert 'catalog_identifier_needs_review' not in flags('Sonata Opus 24', '《奏鸣曲 作品24》')
