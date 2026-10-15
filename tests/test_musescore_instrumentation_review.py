import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from review_musescore_instrumentation import identify_part, classify_parts


def part(name='Guitar', instrument='Classical Guitar', program=24, **extra):
    return {'part_id': name, 'name': name, 'score_instruments': [{'id': 'i', 'name': instrument}],
            'midi_instruments': [{'id': 'i', 'program_0based': program}],
            'note_count': 5, 'normalized_note_count': 5, 'normalization_status': 'complete',
            'normalized_notes_sha256': name, 'clefs': [{'sign': 'G'}], 'staff_details': [],
            'used_instrument_ids': [], **extra}


def test_complete_inverno_roles_repair_missing_cello():
    result = classify_parts([part('Violin','Violin',40),part('Guitar 1'),part('Guitar 2'),part('Violoncello','Violoncello',42)])
    assert result['guitar_player_count'] == 2
    assert result['ensemble_player_count'] == 4
    assert result['topic_id'] == 'strings'
    assert '大提琴' in result['instrumentation_zh']


def test_two_guitars_and_one_grand_staff_piano_are_three_roles():
    result = classify_parts([part('Guitar 1'),part('Guitar 2'),part('Piano','Piano',0,staves_max=2)])
    assert result['ensemble_player_count'] == 3
    assert result['guitar_player_count'] == 2
    assert result['topic_id'] == 'keyboard_reed'


def test_confirmed_tab_view_does_not_add_a_performer():
    score = part(normalized_notes_sha256='same')
    tab = part('Guitar [TAB]','Classical Guitar [Tablature]',normalized_notes_sha256='same',clefs=[{'sign':'TAB'}])
    result = classify_parts([score,tab])
    assert result['topic_id'] == 'solo'
    assert len(result['duplicate_views']) == 1


def test_identical_unison_parts_still_mean_two_roles():
    result = classify_parts([part('Guitar 1',normalized_notes_sha256='same'),part('Guitar 2',normalized_notes_sha256='same')])
    assert result['topic_id'] == 'duo'
    assert result['duplicate_views'] == []


def test_unequal_tab_parts_are_not_silently_merged_or_counted_as_duo():
    result = classify_parts([part('Guitar'),part('Guitar [TAB]',clefs=[{'sign':'TAB'}])])
    assert result['status'] == 'file_reviewed_uncertain'
    assert result['topic_id'] == 'guitar_unspecified'


def test_voice_and_electric_bass_are_explicit_scope_exceptions():
    result = classify_parts([part(),part('Bass Guitar','Bass Guitar',33),part('Voice','Voice',52)])
    assert result['topic_id'] == 'other_instrumentation'
    assert {'bass_guitar','voice'} <= set(result['scope_exceptions'])
    assert '人声' in result['instrumentation_zh']


def test_program_does_not_override_named_instrument():
    result = identify_part(part('Violin solo','Piano',0))
    assert 'part_instrument_name_conflict' in result['issues']
    assert result['kind'] == 'violin'


def test_empty_placeholder_and_collective_label_never_establish_player_count():
    result = classify_parts([part(),part('Guitar 2',note_count=0,normalized_note_count=0)])
    assert result['topic_id'] == 'solo'
    result = classify_parts([part('Guitar ensemble')])
    assert result['status'] == 'file_reviewed_uncertain'
    assert result['guitar_player_count'] is None


def test_harmony_only_accompaniment_is_still_an_active_written_role():
    result = classify_parts([part('Violin','Violin',40),part(note_count=0,normalized_note_count=0,harmony_count=20)])
    assert result['guitar_player_count'] == 1
    assert result['ensemble_player_count'] == 2
    assert result['topic_id'] == 'strings'
    slash = classify_parts([part(note_count=0,normalized_note_count=0,slash_count=2)])
    assert slash['guitar_player_count'] == 1
    assert slash['omitted_empty_parts'] == []


def test_unknown_named_instrument_is_not_inferred_from_guitar_program():
    result = identify_part(part('Tranh','Classical Guitar',24))
    assert result['kind'] == 'dan_tranh'
    assert 'part_instrument_name_conflict' in result['issues']


def test_reviewed_tab_pairs_must_not_overwrite_or_self_link():
    import pytest
    items=[part(),part('Guitar TAB',clefs=[{'sign':'TAB'}])]
    pair={'normal_part_id':'Guitar','tab_part_id':'Guitar TAB','basis':'actual PDF review'}
    with pytest.raises(ValueError,match='duplicate'):
        classify_parts(items,view_pairs=[pair,pair])
    pair['normal_part_id']='Guitar TAB'
    with pytest.raises(ValueError,match='boundary'):
        classify_parts(items,view_pairs=[pair])
