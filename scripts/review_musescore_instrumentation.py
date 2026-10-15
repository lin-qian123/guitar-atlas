#!/usr/bin/env python
"""Cross-check the frozen MuseScore notation, playback and PDF evidence.

This writes a private, guarded overlay; native source declarations and score
bytes are never rewritten. A part is a written performing role, not a claim
about a particular performance. TAB views, playback layers, collective labels
and uncertain instrument substitutions require separate evidence.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import unicodedata


LABELS = {
    'guitar': ('guitar', '吉他', None),
    'violin': ('violin', '小提琴', 'strings'), 'viola': ('viola', '中提琴', 'strings'),
    'cello': ('cello', '大提琴', 'strings'), 'double_bass': ('double bass', '低音提琴', 'strings'),
    'flute': ('flute', '长笛', 'woodwinds'), 'piccolo': ('piccolo', '短笛', 'woodwinds'),
    'recorder': ('recorder', '竖笛', 'woodwinds'), 'ocarina': ('ocarina', '陶笛', 'woodwinds'),
    'clarinet': ('clarinet', '单簧管', 'woodwinds'), 'oboe': ('oboe', '双簧管', 'woodwinds'),
    'bassoon': ('bassoon', '巴松管', 'woodwinds'), 'saxophone': ('saxophone', '萨克斯管', 'woodwinds'),
    'trumpet': ('trumpet', '小号', 'brass'), 'flugelhorn': ('flugelhorn', '柔音号', 'brass'),
    'horn': ('horn', '圆号', 'brass'), 'trombone': ('trombone', '长号', 'brass'), 'tuba': ('tuba', '大号', 'brass'),
    'piano': ('piano', '钢琴', 'keyboard_reed'), 'organ': ('organ', '管风琴', 'keyboard_reed'),
    'harpsichord': ('harpsichord', '羽管键琴', 'keyboard_reed'), 'electric_piano': ('electric piano', '电钢琴', 'keyboard_reed'),
    'accordion': ('accordion', '手风琴', 'keyboard_reed'), 'bandoneon': ('bandoneon', '班多钮', 'keyboard_reed'),
    'harmonica': ('harmonica', '口琴', 'keyboard_reed'), 'melodica': ('melodica', '口风琴', 'keyboard_reed'),
    'harp': ('harp', '竖琴', 'plucked'), 'lute': ('lute', '鲁特琴', 'plucked'),
    'mandolin': ('mandolin', '曼陀林', 'plucked'), 'ukulele': ('ukulele', '尤克里里', 'plucked'),
    'brazilian_viola': ('Brazilian viola', '巴西维奥拉（拨弦）', 'plucked'),
    'koto': ('koto', '日本筝', 'plucked'), 'dan_tranh': ('đàn tranh', '越南筝', 'plucked'),
    'dan_bau': ('đàn bầu', '越南独弦琴', 'plucked'), 'dan_nhi': ('đàn nhị', '越南二胡', 'strings'),
    'vietnamese_lute': ('tỳ bà / đàn nguyệt', '越南琵琶／月琴', 'plucked'),
    'cobza': ('cobza', '罗马尼亚科布扎琴', 'plucked'),
    'percussion': ('percussion', '打击乐', 'percussion'),
    'voice': ('voice', '人声', None), 'electric_guitar': ('electric guitar', '电吉他', None),
    'bass_guitar': ('bass guitar', '贝司', None), 'synthesizer': ('synthesizer', '合成器', None),
    'unknown': ('unidentified instrument', '未核明乐器', None),
}
SCOPE_EXCEPTIONS = {'voice', 'electric_guitar', 'bass_guitar', 'synthesizer'}
ALIASES = {}
for kind, variants in {
    'guitar': 'guitar|classical guitar|acoustic guitar|steel string guitar|alto guitar|12-string guitar|11-string alto guitar|guitar (treble clef)|guitare|guitare classique|guitare acoustique|guitarra|guitarra clásica|guitarra clàssica|guitarra acústica|guitarra acustica|guitarra acústica (clau de sol)|guitarra clássica|chitarra|chitarra classica|chitarra acustica|chitarre acustiche|violão|violão acústico|klassische gitarre|gitarre|akustische gitarre|klassieke gitaar|klassisk gitarr|akustisk gitarr|akustik gitar|akustická kytara|klasická kytara|klasszikus gitár|klassinen kitara|chitară clasică|классическая гитара|акустическая гитара|гитара|nylon string guit.|acnylonguit|nylon guitar|nylon string guitar|原聲吉他|古典吉他|クラシックギター|アコースティックギター',
    'violin': 'violin|violino|violín|violine|violon|viulu|hegedű|скрипка|vioară|violí|βιολί|husle|keman|skrzypce',
    'viola': 'viola|bratsche|альт|violă',
    'cello': 'cello|violoncello|violonchelo|violoncelle|violoncelo|violoncell|viulusello|βιολοντσέλο',
    'double_bass': 'double bass|contrabass|contrabbasso|contrabajo|contrabas|kontrabasso',
    'flute': 'flute|flûte|flöte|flauto|flauta|flauta transversal|флейта|flüt|huilu|bass flute|sáo',
    'piccolo': 'piccolo', 'recorder': 'recorder|alto recorder|flauto dolce|flauto dolce contralto in fa|flauto soprano in sol|flauta dulce|zobcová flétna|zobcová flauta|flûte à bec|blockflöjt|flaut dulce|fluier',
    'clarinet': 'clarinet|b♭ clarinet|a clarinet|bass clarinet|clarinetto in b♭|clarnetto in b♭|klarinette|clarnet|clarinete em b♭|clarinete en si♭|clarinette en si♭|klarnetb',
    'oboe': 'oboe|oboé', 'bassoon': 'bassoon|basson',
    'saxophone': 'saxophone|alto saxophone|tenor saxophone|saxòfon contralt|altsaxophon|tenorsaxophon|saxophone alto|alto sax|sassofono tenore|альтовый саксофон|アルト サクソフォーン',
    'trumpet': 'trumpet|b♭ trumpet|c trumpet|tromba in b♭|trompette en si♭|trompeta en si♭|trumpetă si♭|trąbkab',
    'flugelhorn': 'flugelhorn', 'horn': 'horn|f-torvi', 'trombone': 'trombone', 'tuba': 'tuba',
    'piano': 'piano|grand piano|klavier|klavír|фортепиано|пианино|ピアノ|立式鋼琴|πιάνο|pian|klawisze',
    'electric_piano': 'electric piano', 'organ': 'organ|орган', 'harpsichord': 'harpsichord|clavicembalo|clavicémbalo',
    'accordion': 'accordion|harmonika|ακορντεόν|fisarmonica diatonica|akordeón|akordeon',
    'bandoneon': 'bandoneon', 'harmonica': 'harmonica|armónica|armonica a bocca|16 hole c chromatic harmonica',
    'melodica': 'melodica|мелодическая гармоника',
    'harp': 'harp|harpa|harppu', 'lute': 'lute', 'mandolin': 'mandolin|mandoline|mandolino|bandolim',
    'ukulele': 'ukulele', 'koto': 'koto', 'dan_tranh': 'tranh', 'dan_bau': 'bầu', 'dan_nhi': 'nhị',
    'vietnamese_lute': 'tỳ/nguyệt', 'cobza': 'cobză',
    'voice': 'voice|voz|sopran|cowboy/oliver|stan', 'bass_guitar': 'bass guitar',
    'electric_guitar': 'electric guitar', 'synthesizer': 'keyboard synthesizer',
    'percussion': 'percussion|percussions|drumset|drum|drums|batteria|batterie|bateria|набор ударных|schlagzeug|cajon|tapping|wood blocks|bongos|cymbal|grosse caisse|tambor militar|tambourine|castanets|glockenspiel|marimba|xylophone|tamburo|triangolo|piatto|bass drum|konzert bass drum|snare drum|concert snare drum|congas|bells|тарелка|μεταλλόφωνο|xylofón|trống',
}.items():
    for term in variants.split('|'):
        ALIASES[unicodedata.normalize('NFC', term).casefold()] = kind

for kind, en, zh, aliases in [
    ('drumset','drum kit','架子鼓','drumset|drum|drums|batteria|batterie|bateria|набор ударных|schlagzeug|percussions|trống'),
    ('glockenspiel','glockenspiel','钟琴','glockenspiel'),
    ('metallophone','metallophone','金属琴','μεταλλόφωνο'),
    ('marimba','marimba','马林巴','marimba|marimba (single staff)|marimba (great stave)'),
    ('xylophone','xylophone','木琴','xylophone|xylofón'),
    ('cajon','cajón','卡洪鼓','cajon'), ('bongos','bongos','邦戈鼓','bongos'),
    ('cymbal','cymbal','钹','cymbal|piatto|тарелка'),
    ('bass_drum','bass drum','大鼓','bass drum|grosse caisse|konzert bass drum'),
    ('snare_drum','snare drum','小鼓','concert snare drum|snare drum|tamburo|tambor militar'),
    ('triangle','triangle','三角铁','triangolo'), ('tambourine','tambourine','铃鼓','tambourine'),
    ('castanets','castanets','响板','castanets'), ('wood_blocks','wood blocks','木梆','wood blocks'),
    ('congas','congas','康加鼓','congas'), ('keyboard','keyboard','键盘','tastiera (violini)'),
]:
    LABELS[kind] = (en,zh,'keyboard_reed' if kind == 'keyboard' else 'percussion')
    for alias in aliases.split('|'):
        ALIASES[alias] = kind


def clean_label(value):
    value = unicodedata.normalize('NFC', value).casefold().strip()
    value = re.sub(r'\s+', ' ', value)
    value = re.sub(r'\s*[\[(](?:tablature|tabulatur|tablatura|tabulatura|tabulatuur|intavolatura|tab|staff)[\])]\s*', '', value)
    return value.strip()


def kind_from_label(value):
    value = clean_label(value)
    if value in ALIASES:
        return ALIASES[value]
    additions = {'κλασσική κιθάρα':'guitar', 'ακουστική κιθάρα':'guitar',
                 'nylon gtr.':'guitar', 'bb alto ocarina':'ocarina',
                 'baccidentalflat alto ocarina':'ocarina'}
    if value in additions:
        return additions[value]
    # Numbered desks/roles keep their instrument; the number itself never sets
    # the total count. Only complete labels are accepted.
    for pattern in (r'\s+(?:[1-9][0-9]*|[ivx]+|solo)$', r'^\d+\.\s*', r',\s*(?:pista de instrumento|staff(?:-\d+)?|bass|accordion)$'):
        reduced = re.sub(pattern, '', value).strip()
        if reduced in ALIASES:
            return ALIASES[reduced]
        if reduced in additions:
            return additions[reduced]
    if re.fullmatch(r'(?:accompaniment|percussion|nylon|alto|steel string) guitar|guitar(?: capo \d+| low d| dm| \(dadgad\) capo \d+| \((?:melody|background|alternate melody)\))', value):
        return 'guitar'
    if re.fullmatch(r'(?:first|second) viola', value):
        return 'viola'
    if value.startswith('violin solo'):
        return 'violin'
    if value in {'low tom 2', 'acoustic bass drum', 'crash cymbal 2', 'ride bell', 'side stick', 'high bongo', 'low bongo', 'high wood block', 'low wood block'}:
        return 'percussion'
    return None


def identify_part(part):
    named = kind_from_label(part['name'])
    instruments = part.get('score_instruments', [])
    used = set(part.get('used_instrument_ids', []))
    active = [item for item in instruments if not used or item['id'] in used]
    kinds = {kind_from_label(item['name']) for item in active if item['name'].strip()}
    kinds.discard(None)
    # Percussion kits contain many individual sounds. Their one named kit part
    # does not become one performer per score-instrument declaration.
    issues = []
    percussion_role = named and LABELS[named][2] == 'percussion'
    if named and kinds and kinds != {named} and not percussion_role:
        issues.append('part_instrument_name_conflict')
    if len(kinds) > 1 and not percussion_role:
        issues.append('multiple_instrument_types_in_one_part')
    kind = named or (next(iter(kinds)) if len(kinds) == 1 else 'unknown')
    if kind == 'unknown':
        issues.append('unidentified_named_role')
    label = clean_label(part['name'])
    if re.search(r'\b(?:ensemble|orchestra|choir|violins)\b', label) or any(item.get('ensemble') is not None for item in active):
        issues.append('collective_role_count_unknown')
    if re.search(r'\b(?:chords|melody line|bass line|arppegios|counter|sound only|notatie)\b', label):
        issues.append('possible_playback_or_notation_layer')
    tab = any(item['sign'] == 'TAB' for item in part.get('clefs', []))
    normal = any(item['sign'] not in {'TAB', 'none'} for item in part.get('clefs', []))
    # Harmony-only/slash accompaniment can be an active part without pitches.
    active_role = (part['note_count'] > 0 or part.get('harmony_count', 0) > 0
                   or part.get('frame_count', 0) > 0 or part.get('slash_count', 0) > 0)
    if not active_role:
        issues = []
    return {'part_id': part['part_id'], 'name': part['name'], 'kind': kind,
            'instrument_names': [item['name'] for item in active], 'issues': issues,
            'sounding': active_role, 'tab_only': tab and not normal,
            'tab_present': tab, 'evidence': part}


def classify_parts(parts, *, view_pairs=None, separate_tabs=(), part_decisions=None):
    roles = [identify_part(part) for part in parts]
    for role in roles:
        decision = (part_decisions or {}).get(role['part_id'], {})
        if decision:
            if decision.get('kind') is not None:
                if decision['kind'] not in LABELS:
                    raise ValueError('unknown reviewed instrument kind')
                role['kind'] = decision['kind']
            if 'role_active' in decision and decision['role_active'] is not None:
                role['sounding'] = decision['role_active']
            if decision.get('resolved'):
                role['issues'] = []
            if decision.get('role_active') is None and 'role_active' in decision:
                role['issues'].append('written_role_activity_uncertain')
    reviewed_pairs = {row['tab_part_id']: row for row in (view_pairs or [])}
    if len(reviewed_pairs) != len(view_pairs or []):
        raise ValueError('duplicate reviewed TAB view')
    role_index = {row['part_id']:row for row in roles}
    for tab_id,pair in reviewed_pairs.items():
        target=pair['normal_part_id']
        if (tab_id not in role_index or target not in role_index or tab_id == target
                or not role_index[tab_id]['tab_only'] or role_index[target]['tab_only']):
            raise ValueError('invalid reviewed TAB performing-role boundary')
    issues, duplicates, omitted = [], [], []
    for role in roles:
        issues.extend(f"{role['part_id']}:{item}" for item in role['issues'])
        if not role['sounding']:
            original=role['evidence']
            has_content=(original['note_count'] > 0 or any(original.get(key,0)>0 for key in ['harmony_count','frame_count','slash_count']))
            omitted.append({'part_id': role['part_id'], 'reason':
                'reviewed_auxiliary_layer_not_additional_performer' if has_content else 'no_notated_content'})
    sounding = [role for role in roles if role['sounding']]
    retained = []
    for role in sounding:
        if role['part_id'] in reviewed_pairs:
            pair = reviewed_pairs[role['part_id']]
            if pair['normal_part_id'] not in {item['part_id'] for item in sounding}:
                raise ValueError('reviewed TAB partner is not an active role')
            duplicates.append({'part_id':role['part_id'],'view_of':pair['normal_part_id'],'basis':pair['basis']})
            continue
        if role['tab_only']:
            evidence = role['evidence']
            candidates = [other for other in sounding if not other['tab_present'] and other['kind'] == role['kind']]
            exact = [other for other in candidates if evidence.get('normalized_note_count', 0) > 0
                     and evidence.get('normalization_status') == other['evidence'].get('normalization_status') == 'complete'
                     and evidence.get('normalized_notes_sha256') == other['evidence'].get('normalized_notes_sha256')]
            if view_pairs is None and len(exact) == 1:
                duplicates.append({'part_id': role['part_id'], 'view_of': exact[0]['part_id'],
                                   'basis': 'explicit_TAB_view_and_complete_exact_notated_notes'})
                continue
            if candidates and role['part_id'] not in separate_tabs:
                issues.append(f"{role['part_id']}:unresolved_cross_part_TAB_view")
        retained.append(role)
    counts = Counter(role['kind'] for role in retained)
    exceptions = sorted(set(counts) & SCOPE_EXCEPTIONS)
    count = counts.get('guitar', 0)
    uncertain = bool(issues)
    if exceptions:
        issues.append('scope_exception_in_actual_score')
    if not count:
        issues.append('no_acoustic_guitar_role_in_actual_score')
    groups = {LABELS[kind][2] for kind in counts if kind != 'guitar'}
    if exceptions or (not count and 'unknown' not in counts):
        topic = 'other_instrumentation'
    elif 'unknown' in counts:
        topic = 'unspecified'
    elif not groups:
        topic = 'guitar_unspecified' if uncertain else {1:'solo',2:'duo',3:'trio',4:'quartet'}.get(count,'guitar_ensemble')
    else:
        topic = next(iter(groups)) if len(groups) == 1 else 'mixed_chamber'
    if not groups and not uncertain:
        en = {1:'Guitar solo',2:'2 guitars',3:'3 guitars',4:'4 guitars'}.get(count,f'{count} guitars')
        zh = {1:'吉他独奏',2:'吉他二重奏',3:'吉他三重奏',4:'吉他四重奏'}.get(count,f'{count}把吉他合奏')
    else:
        keys = sorted(counts, key=lambda key: (key != 'guitar', LABELS[key][0]))
        en = ' and '.join((f'{counts[key]} ' if counts[key] > 1 else '') + LABELS[key][0] for key in keys)
        zh = '、'.join((f'{counts[key]}×' if counts[key] > 1 else '') + LABELS[key][1] for key in keys)
    return {'status': 'file_reviewed_uncertain' if uncertain else 'file_verified',
            'instrumentation': en, 'instrumentation_zh': zh, 'topic_id': topic,
            'guitar_player_count': count if not uncertain else None,
            'ensemble_player_count': len(retained) if not uncertain else None,
            'roles': [{key:value for key,value in role.items() if key != 'evidence'} for role in roles],
            'role_counts': dict(counts), 'duplicate_views': duplicates, 'omitted_empty_parts': omitted,
            'scope_exceptions': exceptions, 'issues': sorted(set(issues))}


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _index(rows):
    result = {row['id']:row for row in rows}
    if len(result) != len(rows):
        raise ValueError('duplicate file-review identity')
    return result


def _atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix+'.part')
    try:
        temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
        os.replace(temporary,path)
    finally:
        temporary.unlink(missing_ok=True)


def build_review(root):
    """Combine complete extraction and frozen semantic reviews, fail on drift."""
    from catalog_instrumentation import _check_asset, _check_review
    root = Path(root).resolve()
    catalog_path = root/'sources/musescore/catalog.json'
    raw = catalog_path.read_bytes()
    catalog = json.loads(raw)
    natives = _index(catalog['works'])
    if len(natives) != 924:
        raise ValueError('only the existing frozen 924 native records are approved')
    names = ['instrumentation-mxl-midi.json','instrumentation-pdf.json',
             'instrumentation-tab-review.json','instrumentation-pdf-cases.json',
             'instrumentation-midi-crosscheck.json','instrumentation-identity-review.json']
    paths = [root/'sources/musescore/verification'/name for name in names]
    paths.append(root/'metadata/instrumentation/musescore_reviewed.json')
    inputs = {path: path.read_bytes() for path in paths}
    mxl_midi, pdf, tab, cases, playback, identities, exact = [json.loads(inputs[path]) for path in paths]
    catalog_sha = _sha(raw)
    if (mxl_midi.get('status') != 'complete' or mxl_midi.get('catalog_sha256') != catalog_sha
            or not pdf.get('complete') or pdf.get('catalog_sha256') != catalog_sha
            or playback.get('status') != 'complete' or playback.get('catalog_sha256') != catalog_sha
            or tab.get('status') != 'complete' or tab.get('failures')):
        raise ValueError('complete current notation, PDF, TAB and playback evidence required')
    if (mxl_midi.get('method_sha256') != _sha((root/'scripts/score_instrumentation.py').read_bytes())
            or pdf.get('extractor_sha256') != _sha((root/'scripts/score_pdf_evidence.py').read_bytes())
            or playback.get('method_sha256') != _sha((root/'scripts/score_midi_crosscheck.py').read_bytes())):
        raise ValueError('file evidence extraction method changed; reproduce its evidence first')
    expected = _sha(inputs[paths[0]])
    if (tab.get('mxl_midi_proof_sha256') != expected
            or playback.get('MXL_MIDI_evidence_sha256') != expected
            or tab.get('pdf_proof_sha256') != _sha(inputs[paths[1]])
            or cases['input_guards']['pdf_evidence_sha256'] != _sha(inputs[paths[1]])
            or playback.get('instrument_name_method_sha256') != _sha(Path(__file__).read_bytes())):
        raise ValueError('cross-format review inputs or instrumentation method changed')
    evidence = _index(mxl_midi['records'])
    tabs = _index(tab['records'])
    playback_rows = _index(playback['works'])
    identity_rows = identities['records']
    if isinstance(identity_rows,list):
        identity_rows = _index(identity_rows)
    if (identities.get('status') != 'complete' or identities.get('catalog_sha256') != catalog_sha
            or identities.get('pdf_proof_sha256') != _sha(inputs[paths[1]])
            or set(identity_rows) != set(natives)):
        raise ValueError('complete current actual-file title review required')
    exceptions = _index(exact['entries'])
    if (set(evidence) != set(natives) or set(pdf['records']) != set(natives)
            or set(playback_rows) != set(natives) or not set(exceptions) <= set(natives)):
        raise ValueError('file-review coverage does not exactly match the frozen scope')
    results, projections = [], []
    for identity, native in natives.items():
        files = evidence[identity]['evidence']
        guards = {asset['format']:{key:asset[key] for key in ['sha256','size']}
                  for asset in native['assets']}
        if set(guards) != {'PDF','MUSICXML','MIDI'}:
            raise ValueError('every record requires the same three acquired formats')
        for fmt in ['MUSICXML','MIDI']:
            if (files[fmt]['file_sha256'] != guards[fmt]['sha256']
                    or files[fmt]['file_bytes'] != guards[fmt]['size']):
                raise ValueError('file evidence and current native manifest disagree')
        pdf_row = pdf['records'][identity]
        if pdf_row['status'] != 'ok' or pdf_row['pdf']['sha256'] != guards['PDF']['sha256']:
            raise ValueError('PDF evidence is stale or incomplete')
        parts = files['MUSICXML']['parts']
        tab_row = tabs.get(identity, {})
        if any(item['sign'] == 'TAB' for part in parts for item in part['clefs']) and not tab_row:
            raise ValueError('all TAB notation requires a complete view decision')
        if tab_row and tab_row['mxl_sha256'] != guards['MUSICXML']['sha256']:
            raise ValueError('TAB view decision no longer matches the score bytes')
        part_decisions = {}
        pdf_case = cases['records'].get(identity)
        if pdf_case:
            if (pdf_case['pdf_sha256'] != guards['PDF']['sha256']
                    or pdf_case['mxl_sha256'] != guards['MUSICXML']['sha256']):
                raise ValueError('visual review no longer matches score bytes')
            for part_id, reviewed in pdf_case['parts'].items():
                active = reviewed['activity_review']['role_active']
                kind = reviewed.get('role_kind_review',{}).get('kind')
                part_decisions[part_id] = {'role_active':active}
                if kind is not None:
                    part_decisions[part_id].update(kind=kind,resolved=True)
        exception = exceptions.get(identity)
        if exception:
            if (any(exception.get(key) != native.get(key) for key in ['title_en','composer_en','source_url'])
                    or exception['part_names'] != [part['name'] for part in parts]):
                raise ValueError('exact semantic decision guard changed: '+identity)
            for part_id, decision in exception.get('part_decisions',{}).items():
                if part_id not in {part['part_id'] for part in parts}:
                    raise ValueError('reviewed part identity is absent')
                part_decisions.setdefault(part_id,{}).update(decision)
        pairs = tab_row.get('performing_view_pairs',[])
        separate_tabs = tab_row.get('separate_role_parts',[])
        decision = classify_parts(parts,view_pairs=pairs,separate_tabs=separate_tabs,
                                  part_decisions=part_decisions)
        summary = 'MXL记谱角色与PDF、MIDI交叉核对；标准谱／TAB及播放音轨分别处理。'
        if decision['status'] == 'file_reviewed_uncertain':
            summary = '三种格式均已核对；文件存在未命名声部或器种／人数信息冲突，未强定演奏人数。'
        decision['summary'] = summary
        if exception:
            decision.update(exception.get('review_override',{}))
            if not exception.get('review_override',{}).get('summary'):
                decision['summary'] = exception['note']
        if (not exception and pdf_case
                and pdf_case.get('no_guitar_result') == 'confirmed_no_explicit_acoustic_guitar_role_in_actual_named_or_active_score'):
            decision['summary'] = '实际命名及完整谱面未写出活动吉他角色；保留为其他编制，原来源吉他声明仍可查看。'
        omitted = decision['omitted_empty_parts']
        if omitted:
            decision['summary'] += f' {len(omitted)}条全谱空置或辅助层未额外计人数。'
        playback_row = playback_rows[identity]
        if playback_row['status'] not in {'consistent','explained_playback_difference'}:
            raise ValueError('unresolved MIDI cross-format conflict: '+identity)
        if any(part['lyric_count'] for part in parts) and not any(role['kind']=='voice' for role in decision['roles']):
            decision['summary'] += ' 谱面含歌词字段，未另行假定歌者人数。'
        identity_review = identity_rows[identity]
        if (identity_review.get('source_title') != native['title_en']
                or identity_review['mxl']['sha256'] != guards['MUSICXML']['sha256']
                or identity_review['pdf']['sha256'] != guards['PDF']['sha256']):
            raise ValueError('actual-file title review no longer matches source/files')
        if identity_review['status'] not in {'consistent','compatible_title_variant','identity_conflict','insufficient_file_title'}:
            raise ValueError('unknown file identity decision')
        if identity_review['status'] == 'identity_conflict':
            decision['file_title'] = ' / '.join(identity_review['actual_file_titles'])
            decision['file_identity_note'] = identity_review['summary_zh']
            decision['status'] = 'file_reviewed_uncertain'
            if decision['topic_id'] in {'solo','duo','trio','quartet'}:
                # The written arrangement can be counted, but the frozen native
                # work identity must not advertise a confirmed solo/duet file.
                decision['topic_id'] = 'guitar_unspecified'
            decision['summary'] += ' 实际谱题与来源题名的关联存在冲突。'
        # Source descriptions remain exact and separately visible. The full
        # original source metadata never enters a title or a replacement ID.
        decision['source_difference'] = ('文件核验补全演奏角色与编制，原声明保留。'
            if native['metadata']['instrumentation'] != decision['instrumentation'] else '')
        decision['file_part_labels'] = '；'.join(part['name'] if part['name'].strip() else '〈未标名称〉' for part in parts)
        public_review = {key:decision[key] for key in [
            'status','instrumentation','instrumentation_zh','topic_id','guitar_player_count',
            'ensemble_player_count','summary','source_difference']}
        for key in ['ensemble_size_unspecified','written_guitar_part_count','file_title','file_identity_note','file_part_labels']:
            if key in decision:
                public_review[key] = decision[key]
        _check_review(native,public_review)
        for fmt, guard in guards.items():
            _check_asset(root,native,fmt,guard)
        projections.append({**{key:native[key] for key in ['id','title_en','composer_en','source_url']},
                            'assets':guards,'review':public_review})
        results.append({'id':identity,'title_en':native['title_en'],**decision,
            'source_instrumentation':native['metadata']['instrumentation'],
            'MIDI_crosscheck':playback_row['status'],
            'file_identity_review':identity_review,
            'PDF_visual_case':bool(pdf_case),'TAB_view_review':bool(tab_row),
            'overlaid_layers':tab_row.get('overlaid_layers',[])})
    if catalog_path.read_bytes() != raw or any(path.read_bytes() != value for path,value in inputs.items()):
        raise ValueError('review inputs changed during production cross-check')
    summary = {'records':len(results),'statuses':dict(Counter(row['status'] for row in results)),
               'topics':dict(Counter(row['topic_id'] for row in results)),
               'view_pairs':sum(len(row['duplicate_views']) for row in results),
               'omitted_empty_or_auxiliary_parts':sum(len(row['omitted_empty_parts']) for row in results),
               'guitar_count_unspecified_records':sum(row['guitar_player_count'] is None for row in results),
               'uncertain_ids':[row['id'] for row in results if row['status']=='file_reviewed_uncertain'],
               'other_instrumentation_ids':[row['id'] for row in results if row['topic_id']=='other_instrumentation']}
    envelope={'schema_version':1,'source_id':'musescore','status':'complete','catalog_sha256':catalog_sha}
    report={**envelope,'input_sha256':{str(path.relative_to(root)):_sha(value) for path,value in inputs.items()},
            'method_sha256':_sha(Path(__file__).read_bytes()),'summary':summary,'works':results}
    return {**envelope,'works':projections},report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('.'))
    args = parser.parse_args()
    overlay,report=build_review(args.root)
    _atomic(args.root/'sources/musescore/instrumentation-review.json',overlay)
    _atomic(args.root/'sources/musescore/verification/instrumentation-review.json',report)
    print(json.dumps(report['summary'],ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
