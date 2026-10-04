import json
from pathlib import Path

ROWS = {r['id']: r for r in json.loads((Path(__file__).parent / 'cglib_retained_root_supplement.json').read_text())['entries']}


def test_optional_second_guitar_is_not_relabelled_a_required_duet():
    title = ROWS['cglib:3880']['zh']
    assert '第二把吉他伴奏任选' in title and '二重奏' not in title
    assert '作品9' in title and '六首' in title


def test_bass_part_is_not_certified_as_a_different_instrument():
    assert '吉他低音声部' in ROWS['cglib:37812']['zh']
    assert '二重奏' in ROWS['cglib:37812']['zh']
    assert '低音吉他' not in ROWS['cglib:37812']['zh']


def test_two_independently_named_waltzes_remain_present():
    title = ROWS['cglib:3819']['zh']
    assert 'Chopin圆舞曲' in title and 'Timmermann蒂罗尔圆舞曲' in title
    assert '七弦吉他' in title and '作品5' in title


def test_catalogue_numbers_do_not_invent_a_sonata():
    row = ROWS['cglib:3821']
    assert row['status'] == 'retained'
    assert '11' in row['zh'] and '352' in row['zh']
    assert '奏鸣曲' not in row['zh']


def test_written_source_ordinals_and_source_opus_are_preserved():
    assert '第4号' in ROWS['cglib:3893']['zh'] and '作品12' in ROWS['cglib:3893']['zh']
    assert '第6号' in ROWS['cglib:3906']['zh'] and '作品21' in ROWS['cglib:3906']['zh']


def test_ambiguous_geographical_and_religious_name_stays_original():
    row = ROWS['cglib:38939']
    assert row['status'] == 'retained'
    assert row['zh'] == '《Espirito Santo》'
