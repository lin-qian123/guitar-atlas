"""PDF labels are evidence; staff groups are never performer counts."""
from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from score_pdf_evidence import (
    extract_label_candidates, group_staff_geometry, read_pdf_evidence,
)


def pdf_fixture(path: Path, pages):
    writer = PdfWriter()
    for text_rows, lines in pages:
        page = writer.add_blank_page(width=600, height=800)
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                                 NameObject('/Subtype'): NameObject('/Type1'),
                                 NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({
            NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
        commands = []
        for x, y, text in text_rows:
            escaped = text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
            commands.append(f'BT /F1 12 Tf {x} {800-y} Td ({escaped}) Tj ET')
        for x0,y0,x1,y1 in lines:
            commands.append(f'{x0} {800-y0} m {x1} {800-y1} l S')
        stream = DecodedStreamObject()
        stream.set_data('\n'.join(commands).encode('latin-1'))
        page[NameObject('/Contents')] = writer._add_object(stream)
    with path.open('wb') as target:
        writer.write(target)
    return path


def test_known_instruments_require_whole_labels_and_preserve_positions():
    lines = [
        {'text': 'Guitar 1', 'bbox': [28, 120, 80, 134]},
        {'text': 'Guitar 2', 'bbox': [28, 180, 80, 194]},
        {'text': 'Piano', 'bbox': [28, 245, 65, 260]},
        {'text': 'A piece for Guitar and Piano', 'bbox': [170, 40, 400, 60]},
        {'text': 'Allegro', 'bbox': [90, 100, 140, 115]},
        {'text': 'pp', 'bbox': [28, 265, 40, 277]},
    ]
    evidence = extract_label_candidates(lines, 600, 800)
    assert [row['text'] for row in evidence['instrument_labels']] == ['Guitar 1', 'Guitar 2', 'Piano']
    assert evidence['instrument_labels'][1]['bbox'] == [28, 180, 80, 194]
    assert not any(row['text'] == 'pp' for row in evidence['margin_labels'])
    assert 'performers' not in evidence


def test_staff_group_geometry_connects_staves_but_does_not_count_players():
    horizontal = []
    for top in [120, 180, 245, 280, 410, 470, 535, 570]:
        horizontal.extend([[90, 570, top+i*5] for i in range(5)])
    vertical = [[90, 120, 200], [90, 180, 265], [90,245,300],
                [90,410,490], [90,470,555], [90,535,590]]
    actual = group_staff_geometry(horizontal, vertical, 600)
    assert len(actual['staff_bands']) == 8
    assert len(actual['system_groups']) == 2
    assert len(actual['system_groups'][0]['staff_band_indices']) == 4
    assert actual['first_system_span'] == [120, 300]
    assert actual['interpretation'] == 'notation_geometry_only_not_performer_counts'


def test_all_pages_read_and_first_system_labels_keep_duplicate_roles(tmp_path):
    pytest.importorskip('pymupdf')
    lines=[]
    for top in [120, 180, 245, 280]:
        lines.extend([(90,top+i*5,570,top+i*5) for i in range(5)])
    lines.extend([(90,120,90,200),(90,180,90,265),(90,245,90,300)])
    path = pdf_fixture(tmp_path/'score.pdf', [
        ([(180,50,'Title'), (28,133,'Guitar 1'), (28,193,'Guitar 2'), (28,263,'Piano')], lines),
        ([(280,40,'Page Two'), (28,130,'Guit.')], []),
    ])
    actual = read_pdf_evidence(path)
    assert actual['pages'] == 2
    assert actual['text_readable']
    assert 'Page Two' in actual['page_evidence'][1]['text']
    assert [row['text'] for row in actual['first_system_instrument_labels']] == ['Guitar 1','Guitar 2','Piano']
    assert len(actual['page_evidence'][0]['geometry']['staff_bands']) == 4
    assert actual['limitations']
    assert 'performer_count' not in actual


def test_blank_pdf_is_not_given_invented_instruments(tmp_path):
    actual = read_pdf_evidence(pdf_fixture(tmp_path/'blank.pdf', [([], [])]))
    assert actual['pages'] == 1
    assert not actual['text_readable']
    assert actual['instrument_labels'] == []
    assert 'no_readable_text' in actual['flags']
    assert 'no_explicit_instrument_labels' in actual['flags']


def test_reject_non_pdf(tmp_path):
    path = tmp_path/'not.pdf'
    path.write_text('<html>score unavailable</html>')
    with pytest.raises(ValueError, match='PDF header'):
        read_pdf_evidence(path)


def test_optional_pypdf_fallback_does_not_fabricate_geometry(tmp_path, monkeypatch):
    import score_pdf_evidence
    real_import = score_pdf_evidence.importlib.import_module
    def no_optional_engine(name):
        if name == 'pymupdf':
            raise ImportError('optional layout engine absent')
        return real_import(name)
    monkeypatch.setattr(score_pdf_evidence.importlib, 'import_module', no_optional_engine)
    path = pdf_fixture(tmp_path/'score.pdf', [([(28,130,'Guitar 1')], [])])
    actual = read_pdf_evidence(path)
    assert actual['engine']['name'] == 'pypdf'
    assert actual['instrument_labels'] == [{'page':1,'text':'Guitar 1','bbox':None}]
    assert actual['first_system_instrument_labels'] == []
    assert 'first_system_geometry_unavailable' in actual['flags']


def test_fragmented_per_measure_staff_lines_are_joined():
    horizontal=[]
    for y in [120,125,130,135,140]:
        horizontal.extend([[90+i*60,150+i*60,y] for i in range(8)])
    actual=group_staff_geometry(horizontal,[],600)
    assert len(actual['staff_bands']) == 1
    assert actual['first_system_span'] == [120,140]


def test_cover_page_is_not_mistaken_for_the_first_music_system(tmp_path):
    pytest.importorskip('pymupdf')
    lines=[(90,120+i*5,570,120+i*5) for i in range(5)]
    path=pdf_fixture(tmp_path/'cover.pdf', [
        ([(180,50,'Cover title')],[]),
        ([(28,133,'Guitar')],lines),
    ])
    actual=read_pdf_evidence(path)
    assert actual['first_system_page'] == 2
    assert [row['text'] for row in actual['first_system_instrument_labels']] == ['Guitar']
    assert 'first_system_geometry_unavailable' not in actual['flags']
