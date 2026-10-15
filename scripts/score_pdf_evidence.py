"""Read score PDF text and notation geometry without inferring performers.

The immutable PDF remains the primary evidence.  Extracted text omits private-use
music glyphs, which have no textual instrument meaning; their counts and the raw
page-text digest are retained.  Labels and vector staff groups are observations,
not a claim about the number of musicians.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


# Anchor the complete visible line: a title merely mentioning guitar is not a
# part label.  Keep the source spelling and bounding box, never this vocabulary,
# as the evidence returned to the classification reviewer.
_INSTRUMENT = re.compile(
    r"^(?:(?:I{1,4}|V?I{0,3}|[1-9]\d*|first|second|third|fourth)\s*[.:-]?\s*)?"
    r"(?:classical\s+guitar|acoustic\s+guitar|nylon(?:\s+string)?\s+guitar|"
    r"steel(?:\s+string)?\s+guitar|electric\s+guitar|bass\s+guitar|"
    r"guitars?|guit\.?|gtr\.?|gt\.?|guitarra|guitare|chitarra|gitarre|gitar|吉他|六弦琴|"
    r"piano|pianoforte|pno\.?|harpsichord|organ|accordion|keyboard|celesta|"
    r"violins?|vln\.?|viola|vla\.?|violoncellos?|violoncelle|cello|vlc\.?|"
    r"contrabass|double\s+bass|bass|cb\.?|"
    r"(?:alto\s+|bass\s+|soprano\s+|tenor\s+)?(?:recorder|flute|flûte|flauto|"
    r"saxophone|sax\.?|clarinet|clarinette|clarinetto|oboe|bassoon)|"
    r"piccolo|fl\.?|cl\.?|ob\.?|bsn\.?|fagotto|"
    r"trumpet|trombone|tuba|(?:french\s+)?horn|cornet|flugelhorn|"
    r"harp|mandolin|mandoline|banjo|ukulele|lute|theorbo|"
    r"percussion|drums?|drumset|drum\s+set|bongos?|congas?|tambourine|"
    r"cymbals?|castanets?|triangle|marimba|vibraphone|xylophone|timpani|"
    r"voice|vocals?|soprano|mezzo.soprano|alto|tenor|baritone|"
    r"吉他[一二三四五六七八九十]?|小提琴|中提琴|大提琴|钢琴|鋼琴|长笛|長笛)"
    r"(?:\s*(?:\([^\n]{0,35}\)|[1-9]\d*|I{1,4}|V?I{0,3}|[A-D]|[一二三四五六七八九十])\.?)?$",
    re.I,
)
_NON_LABEL = re.compile(
    r"^(?:[a-g](?:[#♯♭b])?|[pimac]+|[mpfsrz]+|"
    r"allegro|allegretto|andante|andantino|largo|lento|adagio|moderato|presto|"
    r"a tempo|tempo|rit\.?|rall\.?|dim\.?|cresc\.?|fine|d\.?c\.?|d\.?s\.?|"
    r"sim\.?|sempre|poco|dolce|legato|cantabile|con moto|tutti|solo|soli)$", re.I,
)


def _round_bbox(box):
    return [round(float(value), 3) for value in box]


def _is_private_use(char):
    value = ord(char)
    return (0xE000 <= value <= 0xF8FF or
            0xF0000 <= value <= 0xFFFFD or 0x100000 <= value <= 0x10FFFD)


def _readable_text(text):
    return ''.join(char for char in text
                   if not _is_private_use(char) and
                   (char in '\n\t' or unicodedata.category(char) != 'Cc'))


def extract_label_candidates(lines, width, height):
    """Return exact instrument labels and broader, explicitly untyped margin clues."""
    instrument_labels = []
    margin_labels = []
    for row in lines:
        text = row.get('text', '')
        check = unicodedata.normalize('NFKC', text).strip()
        if not check or not any(char.isalpha() for char in check):
            continue
        bbox = row.get('bbox')
        source_row = {'text': text, 'bbox': bbox}
        if _INSTRUMENT.fullmatch(check):
            instrument_labels.append(source_row)
        # These can contain unknown/localized part labels, but also ordinary
        # score directions.  They are never silently promoted to instruments.
        if (bbox and len(check) <= 80 and bbox[0] <= width * .28 and
                bbox[2] <= width * .42 and 0 <= bbox[1] < height * .96 and
                not _NON_LABEL.fullmatch(check)):
            margin_labels.append(source_row)
    return {'instrument_labels': instrument_labels, 'margin_labels': margin_labels}


def group_staff_geometry(horizontal, vertical, width):
    """Recognize regular long staff lines and their initial-barline connections.

    Five/six lines describe standard/TAB notation.  Two connected staves may be
    a piano grand staff, a notation/TAB pair, or different parts: no performer
    inference is made.  Incomplete/irregular line runs are reported separately.
    """
    segments = {}
    for x0, x1, y in horizontal:
        if x1-x0 < width*.04:
            continue
        segments.setdefault(round(y*4)/4, []).append((float(x0),float(x1)))
    ys = {}
    for key, spans in segments.items():
        # MuseScore may draw a staff separately for every measure.  Sum the
        # union of those segments rather than rejecting a short first measure.
        merged = []
        for left,right in sorted(spans):
            if merged and left <= merged[-1][1]+.5:
                merged[-1][1] = max(merged[-1][1],right)
            else:
                merged.append([left,right])
        coverage = sum(right-left for left,right in merged)
        if coverage >= width*.35:
            ys[key] = [merged[0][0],merged[-1][1]]
    positions = sorted(ys)
    runs = []
    current = []
    for y in positions:
        if not current:
            current = [y]
        elif 1.25 <= y-current[-1] <= 10 and (
                len(current) == 1 or abs((y-current[-1])-(current[-1]-current[-2])) <= .55):
            current.append(y)
        else:
            runs.append(current)
            current = [y]
    if current:
        runs.append(current)
    bands = []
    irregular = []
    for run in runs:
        if len(run) in (5, 6):
            bands.append({'top': run[0], 'bottom': run[-1], 'line_count': len(run),
                          'left': round(min(ys[y][0] for y in run), 3),
                          'right': round(max(ys[y][1] for y in run), 3),
                          'spacing': round((run[-1]-run[0])/(len(run)-1), 3)})
        elif len(run) >= 3:
            irregular.append(run)
    groups = []
    for index, band in enumerate(bands):
        join = False
        if index:
            previous = bands[index-1]
            left = max(previous['left'], band['left'])
            if abs(previous['left']-band['left']) <= 2:
                join = any(abs(x-left) <= 2 and y0 <= previous['bottom']+1 and
                           y1 >= band['top']-1
                           for x,y0,y1 in vertical)
        if groups and join:
            groups[-1]['staff_band_indices'].append(index)
            groups[-1]['span'][1] = band['bottom']
        else:
            groups.append({'staff_band_indices': [index],
                           'span': [band['top'],band['bottom']]})
    return {'staff_bands': bands, 'system_groups': groups,
            'first_system_span': groups[0]['span'] if groups else None,
            'irregular_staff_line_runs': irregular,
            'interpretation': 'notation_geometry_only_not_performer_counts'}


def _geometry(page):
    horizontal = []
    vertical = []
    for drawing in page.get_drawings():
        for item in drawing['items']:
            if item[0] != 'l':
                continue
            first, second = item[1:3]
            if abs(first.y-second.y) < .2:
                horizontal.append([min(first.x,second.x),max(first.x,second.x),first.y])
            if abs(first.x-second.x) < .2 and abs(first.y-second.y) > 8:
                vertical.append([first.x,min(first.y,second.y),max(first.y,second.y)])
    return group_staff_geometry(horizontal, vertical, page.rect.width)


def _read_pymupdf(path, module):
    page_evidence = []
    score_system_seen = False
    with module.open(path) as document:
        if document.needs_pass:
            raise ValueError('Encrypted PDF requires password')
        if document.page_count < 1:
            raise ValueError('PDF contains no pages')
        for number, page in enumerate(document):
            raw_text = page.get_text()
            lines = []
            for block in page.get_text('dict')['blocks']:
                for line in block.get('lines', []):
                    text = ''.join(span['text'] for span in line['spans'])
                    readable = _readable_text(text)
                    if readable.strip():
                        lines.append({'text': readable, 'bbox': _round_bbox(line['bbox'])})
            labels = extract_label_candidates(lines, page.rect.width, page.rect.height)
            result = {'page': number+1, 'size': _round_bbox([page.rect.width,page.rect.height]),
                      'text': _readable_text(raw_text),
                      'raw_text_sha256': hashlib.sha256(raw_text.encode('utf-8')).hexdigest(),
                      'omitted_music_glyphs': sum(_is_private_use(c) for c in raw_text),
                      **labels}
            if number == 0 or not score_system_seen:
                result['text_lines'] = [row for row in lines
                                        if any(char.isalpha() for char in row['text'])]
                result['geometry'] = _geometry(page)
                score_system_seen = bool(result['geometry']['staff_bands'])
            page_evidence.append(result)
    return page_evidence, {'name': 'PyMuPDF', 'version': str(module.VersionBind),
                           'coordinates': 'points; top-left origin; PDF page coordinates'}


def _read_pypdf(path):
    from pypdf import PdfReader
    import pypdf
    reader = PdfReader(path, strict=True)
    if reader.is_encrypted:
        raise ValueError('Encrypted PDF requires password')
    if not reader.pages:
        raise ValueError('PDF contains no pages')
    pages = []
    for number,page in enumerate(reader.pages):
        raw_text = page.extract_text() or ''
        lines = [{'text': row,'bbox':None} for row in raw_text.splitlines()]
        labels = extract_label_candidates(lines, float(page.mediabox.width),float(page.mediabox.height))
        pages.append({'page':number+1, 'size':[float(page.mediabox.width),float(page.mediabox.height)],
                      'text':_readable_text(raw_text),
                      'raw_text_sha256':hashlib.sha256(raw_text.encode('utf-8')).hexdigest(),
                      'omitted_music_glyphs':sum(_is_private_use(c) for c in raw_text), **labels})
    return pages, {'name':'pypdf','version':pypdf.__version__,
                   'coordinates':'unavailable; geometry not extracted'}


def read_pdf_evidence(path):
    """Extract all-page text, exact label candidates and first music-system geometry."""
    path = Path(path)
    with path.open('rb') as source:
        if source.read(5) != b'%PDF-':
            raise ValueError('PDF header missing')
    try:
        module = importlib.import_module('pymupdf')
    except ImportError:
        pages, engine = _read_pypdf(path)
    else:
        pages, engine = _read_pymupdf(path, module)
    all_labels = [{'page':page['page'],**row} for page in pages for row in page['instrument_labels']]
    score_page = next((page for page in pages
                       if page.get('geometry',{}).get('first_system_span')), None)
    span = score_page['geometry']['first_system_span'] if score_page else None
    first_labels = []
    if span:
        first_labels = [row for row in score_page['instrument_labels']
                        if row['bbox'] and row['bbox'][3] >= span[0]-20 and
                        row['bbox'][1] <= span[1]+20]
        first_labels.sort(key=lambda row:(row['bbox'][1],row['bbox'][0]))
    readable = any(any(c.isalpha() for c in page['text']) for page in pages)
    flags = []
    if not readable:
        flags.append('no_readable_text')
    if not all_labels:
        flags.append('no_explicit_instrument_labels')
    if not span:
        flags.append('first_system_geometry_unavailable')
    return {'schema_version':1, 'pages':len(pages), 'engine':engine,
            'text_readable':readable, 'instrument_labels':all_labels,
            'first_system_page':score_page['page'] if score_page else None,
            'first_system_instrument_labels':first_labels,
            'page_evidence':pages, 'flags':flags,
            'limitations':[
                'Extracted text and vector geometry do not constitute manual visual review.',
                'A missing printed instrument label does not establish a missing instrument.',
                'Staff lines, connected systems and repeated labels do not establish performer counts.',
                'Private-use music glyphs are omitted only from extracted readable text; PDF bytes remain unchanged.',
                'Instrument vocabulary matches complete lines; unrecognized names remain untyped margin clues.',
            ]}


def _hash(path):
    result=hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda:source.read(1024*1024),b''):
            result.update(chunk)
    return result.hexdigest()


def extract_catalog(root, output):
    root=Path(root).resolve()
    catalog_path=root/'sources/musescore/catalog.json'
    catalog=json.loads(catalog_path.read_text())
    records={}
    labels=Counter()
    flags=Counter()
    page_counts=Counter()
    for work in catalog['works']:
        row={'id':work['id'],'title_en':work['title_en'],'status':'failed'}
        try:
            assets=[a for a in work['assets'] if a.get('format')=='PDF']
            if len(assets)!=1 or assets[0].get('status')!='verified':
                raise ValueError('Expected one verified PDF asset')
            asset=assets[0]
            path=(root/asset['local_path']).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                raise ValueError('PDF path absent or outside root')
            size=path.stat().st_size
            digest=_hash(path)
            if size!=asset['size'] or digest!=asset['sha256']:
                raise ValueError('PDF size or SHA-256 differs from acquired manifest')
            row['pdf']={'local_path':asset['local_path'],'size':size,'sha256':digest}
            row['evidence']=read_pdf_evidence(path)
            row['status']='ok'
            page_counts[row['evidence']['pages']]+=1
            flags.update(row['evidence']['flags'])
            labels.update(label['text'] for label in row['evidence']['first_system_instrument_labels'])
        except Exception as error:
            row['error']=f'{type(error).__name__}: {error}'
        records[work['id']]=row
    result={'schema_version':1, 'source_id':'musescore',
            'generated_at':datetime.now(timezone.utc).isoformat(),
            'catalog_sha256':_hash(catalog_path),
            'extractor_sha256':_hash(Path(__file__)),
            'summary':{'records':len(records),'ok':sum(row['status']=='ok' for row in records.values()),
                       'failed':sum(row['status']!='ok' for row in records.values()),
                       'pages':sum(count*number for number,count in page_counts.items()),
                       'page_count_distribution':dict(sorted(page_counts.items())),
                       'flags':dict(flags),'first_system_label_counts':dict(labels.most_common())},
            'records':records}
    result['complete']=not result['summary']['failed']
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    temporary=output.with_suffix(output.suffix+'.tmp')
    temporary.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    temporary.replace(output)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('.'))
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    output=args.output or args.root/'sources/musescore/verification/instrumentation-pdf.json'
    result=extract_catalog(args.root,output)
    print(json.dumps({'complete':result['complete'],**result['summary']},ensure_ascii=False,indent=2))
    return 0 if result['complete'] else 1


if __name__=='__main__':
    raise SystemExit(main())
