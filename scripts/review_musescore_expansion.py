"""Review actual MXL scope for the frozen append-only PDMX candidate plan.

The scope phase establishes written notation/instrument evidence only. PDF title
identity and independent MIDI playback review remain separate later stages.
Native metadata and physical score objects are never changed.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import unicodedata

from catalog_instrumentation import per_record_guard
from review_musescore_instrumentation import (
    LABELS as FROZEN_LABELS, classify_parts, clean_label, identify_part, kind_from_label,
)
from score_instrumentation import read_mxl_evidence, read_mxl_view_sequences, compare_view_sequences


BASE = Path("sources/musescore/expansion")
REVIEWED_CASES = Path("metadata/instrumentation/musescore_expansion_reviewed.json")
LABELS = {**FROZEN_LABELS,
    "banjo": ("banjo", "班卓琴", "plucked"),
    "bandurria": ("bandurria", "Bandurria（拨弦乐器）", "plucked"),
    "laud": ("laúd", "Laúd（拨弦乐器）", "plucked"),
    "tambura": ("tambura", "Tambura（拨弦乐器）", "plucked"),
    "clavichord": ("clavichord", "Clavichord（击弦键盘乐器）", "keyboard_reed"),
    "celesta": ("celesta", "钢片琴", "keyboard_reed"),
    "vibraphone": ("vibraphone", "颤音琴", "percussion"),
    "euphonium": ("euphonium", "Euphonium（铜管乐器）", "brass"),
    "baritone_horn": ("baritone horn", "Baritone horn（铜管乐器）", "brass"),
    "mellophone": ("mellophone", "Mellophone（行进铜管乐器）", "brass"),
    "english_horn": ("English horn", "英国管", "woodwinds"),
    "contrabassoon": ("contrabassoon", "低音巴松管", "woodwinds"),
    "viola_da_gamba": ("viola da gamba", "Viola da gamba（弓弦乐器）", "strings"),
    "maracas": ("maracas", "Maracas（摇响乐器）", "percussion"),
    "shaker": ("shaker", "Shaker（摇响乐器）", "percussion"),
    "pan_flute": ("pan flute", "排箫", "woodwinds"),
    "nyckelharpa": ("nyckelharpa", "键提琴", "strings"),
    "bouzouki": ("bouzouki", "布祖基琴", "plucked"),
    "hammered_dulcimer": ("hammered dulcimer", "Hackbrett（击弦乐器）", "percussion"),
    "erhu": ("erhu", "二胡", "strings"),
    "cavaquinho": ("cavaquinho", "Cavaquinho（拨弦乐器）", "plucked"),
    "bagpipe": ("bagpipe", "风笛", "woodwinds"),
    "mandola": ("mandola", "Mandola（拨弦乐器）", "plucked"),
    "contra_guitar": ("contra guitar", "Contra Guitar（吉他属拨弦乐器）", "plucked"),
    "balalaika": ("balalaika", "Balalaika（拨弦乐器）", "plucked"),
    "tin_whistle": ("tin whistle", "Tin Whistle（木管乐器）", "woodwinds"),
}
FALLBACK_EXCLUDED = {"voice", "electric_guitar", "bass_guitar", "synthesizer"}
ACOUSTIC_GUITAR_KINDS = {"guitar", "contra_guitar"}
NAME_ISSUES = {"part_instrument_name_conflict", "multiple_instrument_types_in_one_part", "unidentified_named_role"}
COUNT_OR_PLAYBACK_ISSUES = {"unresolved_cross_part_TAB_view", "TAB_numbered_role_identity_conflict",
    "collective_role_count_unknown", "multiple_normal_guitar_staves_role_count_uncertain",
    "possible_playback_or_notation_layer", "written_role_activity_uncertain", "guitar_patch_label_conflict"}
LOCAL_ALIASES = {}
for _term, _kind in {"Bagpipe": "bagpipe", "Bagpipes": "bagpipe", "Mandola": "mandola",
        "Tenor Mandola": "mandola", "Contra Guitar": "contra_guitar", "Contraguitar": "contra_guitar",
        "Kontragitarre": "contra_guitar", "Balalaika": "balalaika", "Tin Whistle": "tin_whistle",
        "D Tin Whistle": "tin_whistle", "B♭ Tin Whistle": "tin_whistle"}.items():
    LOCAL_ALIASES[clean_label(_term)] = _kind
for _kind, _names in {
    "banjo": "banjo|bánjo|バンジョー|班卓琴",
    "bandurria": "bandurria|bandurria española",
    "laud": "laud|laúd|laúd español|laud español",
    "guitar": "gtr|gtr.|gt.|guit.|guit|guitarra clasica|guitarra classica|guitarra acustica|guitarra ac.|guitarra (acústica)|guitarra de aço|guitarra de nylon|acoustic guitar (steel)|acoustic guitar (nylon)|guitar (nylon)|guitar (steel)|nylon str guitar|nylon-string guitar|steel-string guitar|klassik gitarre|gitaar|ak. gitaar|akustische gitarre|guitare acoustique|kitara|κιθάρα|κλασική κιθάρα|chitară|吉他|原声吉他|原聲結他|木吉他|ギター",
    "voice": "vocal|vocals|singing voice|gesang|canto|voce|voix|voz|soprano|mezzo-soprano|mezzo soprano|contralto|tenor|baritone|vocal soprano|vocal tenor|人声|人聲|歌声|歌聲",
    "electric_guitar": "electric guitar (jazz)|electric guitar (clean)|electric guitar (muted)|electric guitar - jazz|electric guitar - clean|electric guitar - muted|overdriven guitar|overdrive guitar|distortion guitar|distorted guitar|muted guitar|guitarra eléctrica|guitarra electrica|guitarra elétrica|guitarra elettrica|guitarra electrica limpia|guitare électrique|guitare electrique|chitarra elettrica|e-gitarre|elektrische gitarre|elektrische gitaar|electric guit.|elgitarr|elgitaar|電吉他|电吉他|エレキギター",
    "bass_guitar": "electric bass|electric bass guitar|acoustic bass guitar|bass guitar (finger)|bass guitar (pick)|bass guitar (slap)|electric bass (finger)|electric bass (pick)|electric bass (slap)|electric bass (fretless)|fretless bass guitar|bass électrique|basse électrique|basse electrique|bajo eléctrico|bajo electrico|contrabaixo elétrico|contrabaixo eletrico|elbas|båndløs elbas|fretless bass|fretless electric bass|fingered bass|slap bass|basse électrique sans frettes|エレキベース|貝斯|贝斯|電貝斯|电贝斯",
    "synthesizer": "synthesizer|synth|synthétiseur|sintetizador|synth strings|synth bass|synth brass|synth pad|polysynth|合成器",
    "violin": "violino solo|violon solo|violin i|violin ii|violin iii|vln.|vln",
    "cello": "vc.|vcl.|vcl|violoncello solo|violoncelo solo",
    "clarinet": "clarinet in b♭|b-flat clarinet|bb clarinet|clarinet in bb|clarinette|klarinette in b|clarinete|clarinete em sib|clarinete en sib|clarinetto",
    "flute": "flauto traverso|querflöte|flauta transversa|fl.|flûte traversière",
    "saxophone": "saxofón alto|saxofon alto|saxofone alto|saxofone tenor|saxophone ténor|saxo alto|saxo tenor",
    "horn": "french horn|cor|corno|waldhorn|cor en fa|horn in f",
    "trumpet": "trumpet in b♭|b-flat trumpet|bb trumpet|tromba|trompette|trompeta",
    "organ": "orgue|orgel|órgano|organo|órgão|orgão|orga",
    "accordion": "akkordeon|accordéon|acordeón|acordeon|fisarmonica",
    "harpsichord": "cembalo|clavecin|cravo",
    "percussion": "claves|cowbell|triangle|tambourin|pandeiro|clap|hand clap|handclap|woodblock|tubular bells|timpani|timbales|tom-tom|ride cymbal|crash cymbal",
}.items():
    for _term in _names.split("|"):
        LOCAL_ALIASES[unicodedata.normalize("NFC", _term).casefold()] = _kind

SLIDE_LABELS = {"slide guitar", "steel guitar", "hawaiian guitar", "lap steel guitar", "lap steel", "pedal steel guitar", "pedal steel", "bottleneck guitar"}

# Exact complete names; register/section words alone never establish an instrument.
COLLECTIVE_LABELS = {"violins", "violas", "violoncellos", "cellos", "contrabasses", "double basses"}
for _kind, _names in {
    "tambura": "tambura",
    "clavichord": "clavichord", "celesta": "celesta", "vibraphone": "vibraphone",
    "euphonium": "euphonium", "baritone_horn": "baritone horn", "mellophone": "mellophone",
    "english_horn": "english horn|cor anglais", "contrabassoon": "contrabassoon",
    "viola_da_gamba": "viola da gamba|viole de gambe",
    "maracas": "maracas", "shaker": "shaker",
    "pan_flute": "pan flute|flûte de pan|panflöte",
    "nyckelharpa": "nyckelharpa",
    "bouzouki": "bouzouki|bouzouki (4 chœurs)|bouzouki (3-course)",
    "hammered_dulcimer": "hammered dulcimer|hackbrett",
    "saxophone": "soprano saxophone|baritone saxophone|baritone sax|baritone sax.|bari sax|tenor sax|tenor saxophon|alto saxophon|saxophone baryton",
    "recorder": "soprano recorder|tenor recorder|bass recorder|sopranino recorder",
    "flute": "flétna|dwarsfluit",
    "violin": "violins|violino primo|violino secondo", "viola": "violas",
    "cello": "violoncellos|cellos", "double_bass": "contrabasses|double basses",
    "guitar": "violão clássico|classical guitar, nylon guitar|guitarra acústica, acoustic guitar",
}.items():
    for _term in _names.split("|"):
        LOCAL_ALIASES[clean_label(_term)] = _kind

# Finite sound names within an explicitly named drum set. They are component
# sounds of that one written role, never separate performers or arbitrary labels.
DRUM_COMPONENTS = {clean_label(value) for value in (
    "Acoustic Bass Drum|Bass Drum|Bass Drum 1|Side Stick|Acoustic Snare|Electric Snare|"
    "Low Floor Tom|Closed Hi-Hat|High Floor Tom|Pedal Hi-Hat|Low Tom|Open Hi-Hat|"
    "Low-Mid Tom|Hi-Mid Tom|Crash Cymbal 1|High Tom|Ride Cymbal 1|Chinese Cymbal|"
    "Ride Bell|Tambourine|Splash Cymbal|Cowbell|Crash Cymbal 2|Vibraslap|Ride Cymbal 2|"
    "Hi Bongo|Low Bongo|Mute Hi Conga|Open Hi Conga|Open High Conga|Low Conga|High Timbale|"
    "Low Timbale|High Agogo|Low Agogo|Cabasa|Maracas|Short Whistle|Long Whistle|"
    "Short Guiro|Long Guiro|Claves|Hi Wood Block|Low Wood Block|Mute Cuica|Open Cuica|"
    "Mute Triangle|Open Triangle|Hand Clap|Snare (Acoustic)|Snare (Electric)|"
    "Hi-Hat Closed|Hi-Hat Pedal|Hi-Hat Open|Tom|Tom 1|Tom 2|Tom 3|Tom 4|Tom 5|"
    "Crash 1|Ride|China|Ride (Bell)|Open high conga|Concert Bass Drum|Concert Cymbal"
).split("|")}


# Official MuseScore v3.6.2 instruments_*.ts exact source/translation matches.
# Full URL, language, original strings and SHA receipts are frozen in the private
# language-alias-proposal evidence and recorded in the integration receipt.
OFFICIAL_LANGUAGE_ALIASES = {
    "5 snarige elektrische bas": "bass_guitar",
    "5-str. Electric Bass": "bass_guitar",
    "5-стр. Электрическая бас-гитара": "bass_guitar",
    "Acoustic Guitar (Treble Clef)": "guitar",
    "Akoestische gitaar": "guitar",
    "Akoestische gitaar (Tablatuur)": "guitar",
    "Akustinen kitara": "guitar",
    "Akustisk gitar": "guitar",
    "Akustisk guitar": "guitar",
    "Akustisk guitar (Tabulatur)": "guitar",
    "Baix elèctric": "bass_guitar",
    "Baixo Elétrico": "bass_guitar",
    "Baixo elétrico de 5 cordas": "bass_guitar",
    "Bas Gitar": "bass_guitar",
    "Bas-gitaar": "bass_guitar",
    "Basguitar": "bass_guitar",
    "Basová kytara": "bass_guitar",
    "Bass Gitarre": "bass_guitar",
    "Bass Synthesizer": "synthesizer",
    "Basse électrique fretless": "bass_guitar",
    "Brass Synthesizer": "synthesizer",
    "Chitară acustică": "guitar",
    "Dwarsfluit": "flute",
    "Efektisyntetisaattori": "synthesizer",
    "Effect Synthesizer": "synthesizer",
    "Electric Guitar (Treble Clef)": "electric_guitar",
    "Elektrická basová kytara": "bass_guitar",
    "Elektrická kytara": "electric_guitar",
    "Elektrická kytara (tabulatura)": "electric_guitar",
    "Elektrische bas": "bass_guitar",
    "Elektrischer Bass": "bass_guitar",
    "Elektrisk bass": "bass_guitar",
    "Elektrisk gitar": "electric_guitar",
    "Elektrisk gitar (Tablatur)": "electric_guitar",
    "Elektro Gitar": "electric_guitar",
    "Flétna": "flute",
    "Fretloze elektrische bas-gitaar": "bass_guitar",
    "Guitare Basse": "bass_guitar",
    "Guitarra elèctrica": "electric_guitar",
    "Guitarra elèctrica (Clau de Sol)": "electric_guitar",
    "Guitarra elèctrica (Tabulatura)": "electric_guitar",
    "Klasik Gitar": "guitar",
    "Kytara": "guitar",
    "Moniääninen syntetisaattori": "synthesizer",
    "Pad Synthesizer": "synthesizer",
    "Poly Synthesizer": "synthesizer",
    "Saw Synthesizer": "synthesizer",
    "Sintetitzador Pad": "synthesizer",
    "Sintetitzador metalls": "synthesizer",
    "Sähköbasso": "bass_guitar",
    "Sähkökitara": "electric_guitar",
    "Бас-гитара": "bass_guitar",
    "Безладовая бас-гитара": "bass_guitar",
    "Класична гітара": "guitar",
    "Синтезатор медных духовых": "synthesizer",
    "Синтезатор педали": "synthesizer",
    "Синтезатор пилообразной волны": "synthesizer",
    "Электрическая бас-гитара": "bass_guitar",
    "Электрогитара": "electric_guitar",
    "Электрогитара (табулатура)": "electric_guitar",
    "בס חשמלית": "bass_guitar",
    "בס חשמלית 5 מיתרים": "bass_guitar",
    "גיטרה אקוסטית": "guitar",
    "גיטרה בס": "bass_guitar",
    "גיטרה חשמלית": "electric_guitar",
    "גיטרה קלאסית": "guitar",
    "エフェクト シンセサイザー": "synthesizer",
    "ノコギリ波": "synthesizer",
    "ベース＋リード シンセサイザー": "synthesizer",
    "低音吉他": "bass_guitar",
    "铜管乐合成器": "synthesizer",
    "锯声合成器": "synthesizer",
    "音效合成器": "synthesizer",
    "베이스 기타 ": "bass_guitar",
    "베이스 신디사이저": "synthesizer",
    "브라스 신디사이저": "synthesizer",
    "어쿠스틱 기타 ": "guitar",
    "어쿠스틱 기타(타브 악보)": "guitar",
    "일렉 기타 ": "electric_guitar",
    "일렉트릭 기타(타브 악보)": "electric_guitar",
    "일렉트릭 베이스": "bass_guitar",
    "클래식 기타": "guitar",
    "톱 신디사이저": "synthesizer",
    "프렛리스 일렉트릭 베이스": "bass_guitar",
    "효과 신디사이저": "synthesizer"
}
for _term, _kind in OFFICIAL_LANGUAGE_ALIASES.items():
    LOCAL_ALIASES[clean_label(_term)] = _kind


# Final finite exact-name supplement: 333 accepted labels from 335 researched
# labels, nine whole-label view/synonym forms, and two independent types. References,
# causal native IDs, original labels and count boundaries are retained in
# sources/musescore/expansion/pending-review-summary.json, SHA-256
# 84344f2ed66a4e70442f1ba15e299804dbc5488a32c84236523a1a86826b2dc8.
# These names establish types only, never an acoustic-guitar role or desk size.
# Tamborim is not a jingled tambourine, and Grup de percussió names a percussion
# group rather than one drum kit: both proposed aliases are withheld.
FINITE_REVIEWED_ALIASES = {
    'accordion': 'Accordeon|Acordeão|Acordió|Аккордеон|アコーディオン',
    'banjo': 'Tenor Banjo|Банджо',
    'baritone_horn': 'Tenorhorn',
    'bass_drum': 'Concert Bass Drum|Grosse caisse de concert|Konserttibassorumpu',
    'bass_guitar': '6-str. Electric Bass|6-струнная бас-гитара|E-Bass (Tabulatur)|Elektrisk bass (Tablatur)',
    'bassoon': 'Fagote',
    'bongos': 'Bongo',
    'brazilian_viola': 'Brazilian viola',
    'cajon': 'cajón',
    'cavaquinho': 'Cavaquinho',
    'celesta': 'Célesta',
    'cello': "Sellot|Violoncel|Violoncele|Violoncelles|Violoncelos|Viyolonsel|Виолончель|Віолончель|צ'לו|乐队大提琴|大提琴|비올론첼로",
    'clarinet': 'A调单簧管|B klarinet|Bassklarinette in A|B♭ Bass Clarinet\n|B♭ Bass Clarinet (Bass Clef)|B♭ クラリネット|Clarinet en Si♭|Clarinette\nBasse|Clarinette Basse|Contrabass Clarinet|E♭ Clarinet|E♭ クラリネット|E♭ 클라리넷|Klarinet i B|Klarinet in B♭|Klarinet in C|Klarinette in A|Si♭ Klarnet|Бас-кларнет|קלרינט|アルト クラリネット|バス クラリネット|降B调单簧管',
    'clavichord': 'Клавикорд|클라비코드',
    'cobza': 'cobza',
    'congas': "Conga's|コンガ",
    'cymbal': 'Bekken|Cymbale',
    'dan_bau': 'đàn bầu',
    'dan_nhi': 'đàn nhị',
    'dan_tranh': 'đàn tranh',
    'double_bass': 'Cbs.|Contrabasuri|Contrebasse|Dubbelbas|Kontrabas|Kontrabass|Kontrabassot|Kontrbas|Контрабас|コントラバス|ダブルベース|콘트라베이스',
    'drumset': 'Bicí souprava|D. Set|D. set|drum kit|Rumpusetti|Trommesett|Trommesæt|trommesæt|מערכת תופים|鼓组|드럼세트',
    'electric_guitar': '踏板电子吉他|일렉트릭 기타(타브 악보)|페달 스틸 기타',
    'electric_piano': 'Elektrische piano|Elektrisches Piano|Elektrisk piano|Piano électrique|פסנתר חשמלי|エレクトリックピアノ|전자 피아노 ',
    'english_horn': '잉글리시 호른',
    'erhu': 'Erhu',
    'euphonium': 'Euph.|Euphonium (Clef de sol)|Euphonium (Treble Clef)',
    'flute': 'Alt-fluit|Altflöte|Alto Flute|Flûte Irlandaise|G调高音长笛|Irish Flute|Poikkihuilu|Tvärflöjt|חליל',
    'glockenspiel': 'グロッケンシュピール',
    'guitar': ' Gitar|12-string Acoustic Guitar [notation]|[Classical Guitar [notation]]|Acoustic Guitar, Guitar|Chit.|Classical Guitar, Acoustic Guitar|Classical Guitar, Guitar|Nylon Gtr., Guitar|原聲吉他, Acoustic Guitar|古典吉他, guitar',
    'harmonica': 'ハーモニカ|口琴',
    'harp': 'Arp|Arpa|Harfe|Harpe|נבל',
    'harpsichord': 'Клавесин|ハープシーコード|하프시코드',
    'horn': 'F ホルン|F 호른|Hoorn in F|Horn in A♭|Horn in B♭ basso|Trompa em F|Trompa en Fa|Валторна Фа|Ми♭ Валторна',
    'koto': '日本筝',
    'lute': 'Alaúde|Laute|Laute (Tabulatur)|Laute 13-chörig|Lute 13-course|Lute 5-course|Lute 6-course|Lute 7-course|Lute 9-course|Luth|Luth à 13 chœurs|リュート 13コース',
    'mandolin': 'מנדולינה|マンドリン|만돌린 ',
    'maracas': 'マラカス',
    'marimba': 'Marimba (Einzelne Notenzeile)|Marimba (Grand Staff)|Marimba (simple portée)|マリンバ [単譜表]|马林巴琴（大谱表）|마림바|마림바 (큰 보표)',
    'melodica': 'Mélodica',
    'metallophone': 'Metallophone',
    'oboe': 'Obua',
    'ocarina': 'Ocarina',
    'organ': 'Orgão de tubos|Pipe Organ',
    'pan_flute': 'パンフルート|팬 플루트',
    'percussion': 'Aplaudiment|Claquement de mains|Perc.|Ride|Taputus|Triangel|Triângulo|Üçgen|Клавесы|Литавры|טימפאני|מחיאת כף|クラベス|ティンパニ|トライアングル|ハンドクラップ',
    'piano': 'Klaver|Piano droit|Piyano|Upright Piano|פסנתר|グランドピアノ|钢琴|그랜드 피아노 |피아노 ',
    'piccolo': 'Picc.|Piccoloflöte|ピッコロ',
    'recorder': 'Blockflöte|Blokfløjte|Flûte Sopranino en Do|Flûte à bec alto|Поздовжня флейта',
    'saxophone': 'Alt-saxofoon|Alto Saksafon|Altový saxofon|Altsaksofon|Altsaxofon|Bar. Sax.|Bariton-saxofoon|Baritonsaxophon|Barytonový saxofon|Barytonsaxofon|Saxofone Soprano|Saxophone Soprano|Sopraan-saxofoon|T. Sax.|Tenor Saksafon|Tenor-saxofoon|Теноровый саксофон|סקסופון אלט|סקסופון טנור|ソプラノ サクソフォーン|テナー サクソフォーン|バリトン サクソフォーン|中音萨克斯|高音萨克斯',
    'shaker': 'シェイカー',
    'snare_drum': 'Acoustic Snare|Caixa|Electric Snare|콘서트 스네어드럼',
    'synthesizer': "Atmosphere Synthesizer|Bowed Synthesizer|Brightness Synthesizer|Choir Synthesizer|Echoes Synthesizer|Goblins Synthesizer|Halo Synthesizer|Mallet Synthesizer|Metallic Synthesizer|New Age Synthesizer|Rain Synthesizer|Sci-fi Synthesizer|Sine Synthesizer|Sintetizador de cordas|Soundtrack Synthesizer|Square Synthesizer|String Synthesizer|Sweep Synthesizer|Synth.|Synthétiseur d'atmosphère|Synthétiseur métallique|Warm Synthesizer|Синтезатор квадратной волны|סינתיסייזר כלי קשת|アトムスフィア シンセサイザー|クリスタル シンセサイザー|レイン シンセサイザー|矩形波|나무망치 신디사이저|뉴에이지 신디사이저|사각 신디사이저",
    'tambourine': 'Pandereta|Tamburin|תוף-מרים',
    'trombone': 'Bass Trombone|Contrabass Trombone|Pasuuna|Posaune|Pozoun|Soprano Trombone|Tbn.|Tenor Trombone|Trombone (F-nøkkel)|Trombone (Treble Clef)|Trombone basse|Trombone ténor|Trombó|Тромбон',
    'trumpet': 'B trubka|B♭ trompet|B♭ トランペット|C Tpt.|C トランペット|C 트럼펫|F Trumpet|Trompet|Trompet in B♭|Trompet in C|Trompete em B♭|Trompete in B|Trompette en Do|Trumpet i B♭|Trumpetti|Си♭ Труба',
    'tuba': 'Bastuba in F|B♭ Tuba|C Tuba|F Tuba|Tuba en Si♭|Tuba en Si♭ |Tuba en Si♭ (Clef de Sol)|Tuba en Si♭ (Clef de sol)|Туба',
    'ukulele': 'Tenor Ukulele|Ukelele|Ukulele (Low G)|Ukulélé|Укулеле|ウクレレ',
    'vibraphone': 'Vibraphon|Вибрафон|ビブラフォン|颤音琴',
    'viola': 'Altviool|Viyola|Vla.|Альты|ויולה|ヴィオラ|비올라|비올라 ',
    'violin': 'Housle|Violinos|Viool|Viori|Viulut|Vlns.|Скрипки|ヴァイオリン|乐队小提琴|바이올린',
    'voice': '[Voice]|Mezzosopran|Ténor|Veu|Vo.|Zang\t|Zpěv|Şan|Голос|Тенор|סופרן|ボーカル|メゾソプラノ|女中音|女高音|목소리|소프라노',
    'wood_blocks': 'ウッドブロック',
    'xylophone': 'Xilofone|Xylophon|Ксилофон',
}
for _kind, _names in FINITE_REVIEWED_ALIASES.items():
    for _term in _names.split("|"):
        _normalized_term = clean_label(_term)
        if _normalized_term in LOCAL_ALIASES and LOCAL_ALIASES[_normalized_term] != _kind:
            raise ValueError("conflicting finite instrument alias")
        LOCAL_ALIASES[_normalized_term] = _kind

# Some official translations use one spelling for both a singular instrument
# and an orchestral section. Preserve that genuine player-count boundary even
# where a literal instrument type is now known.
COLLECTIVE_LABELS.update(clean_label(value) for value in (
    'Cbs.', 'Contrabasuri', 'Housle', 'Kontrabassot', 'Sellot',
    'Violinos', 'Violoncele', 'Violoncelles', 'Violoncelos', 'Viori',
    'Viulut', 'Vlns.', 'Альты', 'Віолончель', 'Контрабас',
    'Скрипки', 'コントラバス', 'ヴァイオリン', 'ヴィオラ', '乐队大提琴',
    '乐队小提琴', '바이올린', '비올라', '비올라 ', '비올론첼로',
    '콘트라베이스',
))


def _label(value):
    value = clean_label(value)
    value = re.sub(r"\s*[\[(](?:tablatuur|tabulatuur|tabulatur|табулатура|타브 악보|tab譜|notation)[\])]\s*$", "", value).strip()
    value = re.sub(r"(?:\s*[-,:]\s*|\s+)(?:tab|tablature|tablatura|tabulatur)$", "", value).strip()
    return value


def _unindexed(value):
    value = _label(value)
    value = re.sub(r"\s*(?:\(#?([1-9][0-9]*)\)|(?:\s|[._-])(?:no\.?\s*)?#?([1-9][0-9]*|[ivx]+))$", "", value).strip()
    return value


def expansion_kind(value):
    """Exact named aliases only; no MIDI-program or title-word inference."""
    direct = kind_from_label(value)
    if direct:
        return direct
    exact = LOCAL_ALIASES.get(clean_label(value))
    if exact:
        return exact
    reduced = _unindexed(value)
    if reduced in SLIDE_LABELS:
        return "electric_guitar"  # Public kind remains typed; slide reason is kept separately.
    return LOCAL_ALIASES.get(reduced) or kind_from_label(reduced)


def _role_number(value):
    value = _label(value)
    match = re.search(r"(?:\s|[._-]|\()(?:no\.?\s*)?#?([1-9][0-9]*|[ivx]+)\)?$", value)
    if not match:
        return None
    text = match[1]
    return text if text.isdigit() else {"i": "1", "ii": "2", "iii": "3", "iv": "4", "v": "5", "vi": "6", "vii": "7", "viii": "8", "ix": "9", "x": "10"}.get(text, text)


def _active_instruments(part):
    used = set(part.get("used_instrument_ids", []))
    return [item for item in part.get("score_instruments", []) if not used or item["id"] in used]


def _is_active(part):
    return any(part.get(key, 0) > 0 for key in ("note_count", "harmony_count", "frame_count", "slash_count"))


def _part_decisions(parts):
    decisions, additions, slides = {}, [], []
    for part in parts:
        if not _is_active(part):
            continue
        identity, named = part["part_id"], expansion_kind(part["name"])
        declarations = _active_instruments(part)
        instrument_kinds = {expansion_kind(item["name"]) for item in declarations if item["name"].strip()}
        unknown_declarations = None in instrument_kinds
        instrument_kinds.discard(None)
        original = identify_part(part)
        kind = named or (next(iter(instrument_kinds)) if len(instrument_kinds) == 1 else "unknown")
        drum_components = (kind in {"drumset", "percussion"} and bool(declarations)
            and all(clean_label(item["name"]) in DRUM_COMPONENTS for item in declarations))
        if drum_components:
            unknown_declarations = False
            instrument_kinds = {kind}
        conflict = bool(named and instrument_kinds and instrument_kinds != {named} and not drum_components)
        if conflict:
            additions.append(f"{identity}:part_instrument_name_conflict")
        if len(instrument_kinds) > 1 and not drum_components:
            additions.append(f"{identity}:multiple_instrument_types_in_one_part")
        if unknown_declarations and kind != "unknown":
            additions.append(f"{identity}:unreviewed_score_instrument_label")
        if kind != "unknown":
            safe_resolution = (not conflict and not unknown_declarations and len(instrument_kinds) <= 1
                               and set(original["issues"]) <= NAME_ISSUES | COUNT_OR_PLAYBACK_ISSUES)
            if safe_resolution:
                # Resolve the type only; keep every independent count/playback
                # limitation that the frozen classifier found for that role.
                additions.extend(f"{identity}:{issue}" for issue in original["issues"] if issue not in NAME_ISSUES)
            decisions[identity] = {"kind": kind, "resolved": safe_resolution,
                "basis": "exact_named_expansion_aliases", "part_name": part["name"],
                "instrument_names": [item["name"] for item in declarations]}
        named_texts = [part["name"], *[item["name"] for item in declarations]]
        if any(_unindexed(value) in COLLECTIVE_LABELS for value in named_texts):
            additions.append(f"{identity}:collective_role_count_unknown")
        if any(_unindexed(value) in SLIDE_LABELS for value in named_texts):
            slides.append(identity)
        used = set(part.get("used_instrument_ids", []))
        patches = {item["program_0based"] for item in part.get("midi_instruments", [])
                   if (not used or item["id"] in used) and item.get("program_0based") is not None}
        if ((kind == "electric_guitar" and patches & {24, 25})
                or (kind == "guitar" and patches & set(range(26, 31)))
                or (kind == "guitar" and patches & set(range(32, 40)))):
            additions.append(f"{identity}:guitar_patch_label_conflict")
        normal_staffs = {row.get("staff_number", 1) for row in part.get("clefs", []) if row.get("sign") not in {"TAB", "none"}}
        if kind == "guitar" and len(normal_staffs) > 1:
            additions.append(f"{identity}:multiple_normal_guitar_staves_role_count_uncertain")
        if re.search(r"\b(?:guitars|guitares|guitarras|chitarre|gitarren|ensemble|orchestra|choir)\b", _label(part["name"])):
            additions.append(f"{identity}:collective_role_count_unknown")
        for value in named_texts:
            segments = re.split(r"\s+(?:and|with|or|und|et|y|e|ou)\s+|[+/&]", _label(value))
            segment_kinds = {expansion_kind(segment) for segment in segments}
            segment_kinds.discard(None)
            if len(segment_kinds) > 1:
                additions.append(f"{identity}:combined_or_alternative_instrument_label")
    return decisions, sorted(set(additions)), slides


def _tab_review(parts, decisions, sequences):
    roles = [identify_part(part) for part in parts]
    for role in roles:
        if role["part_id"] in decisions:
            role["kind"] = decisions[role["part_id"]]["kind"]
    active = [role for role in roles if role["sounding"]]
    sequence_index = {row["part_id"]: row for row in (sequences or {}).get("parts", [])}
    if len(sequence_index) != len((sequences or {}).get("parts", [])):
        raise ValueError("duplicate MXL view sequence identity")
    pairs, comparisons, conflicts = [], [], []
    for tab in [role for role in active if role["tab_only"]]:
        candidates = [role for role in active if not role["tab_present"] and role["kind"] == tab["kind"] and role["kind"] != "unknown"]
        exact = []
        for normal in candidates:
            a, b = _role_number(tab["name"]), _role_number(normal["name"])
            identity_conflict = bool(a and b and a != b)
            if tab["part_id"] in sequence_index and normal["part_id"] in sequence_index:
                comparison = compare_view_sequences(sequence_index[tab["part_id"]], sequence_index[normal["part_id"]])
            else:
                comparison = {"kind": "full_view_sequence_not_supplied", "all_events_correspond": False}
            row = {"tab_part_id": tab["part_id"], "normal_part_id": normal["part_id"],
                   "tab_name": tab["name"], "normal_name": normal["name"],
                   "identity_conflict": identity_conflict, **comparison}
            comparisons.append(row)
            if identity_conflict:
                conflicts.append(f"{tab['part_id']}:TAB_numbered_role_identity_conflict")
            if not identity_conflict and comparison["kind"] == "exact_pitch_onset_duration_grace":
                exact.append(normal)
        if len(exact) == 1:
            pairs.append({"tab_part_id": tab["part_id"], "normal_part_id": exact[0]["part_id"],
                          "basis": "complete_exact_pitch_onset_duration_grace_and_compatible_named_role"})
    return {"performing_view_pairs": pairs, "comparisons": comparisons,
            "issues": sorted(set(conflicts)),
            "boundary": "Only complete exact pitched/grace sequences with unambiguous named-role boundaries establish an automatic TAB view."}


def classify_expansion_parts(parts, *, view_pairs=(), separate_tabs=(), part_decisions=None):
    """Extend types in a returned copy while reusing frozen activity/TAB logic.

    A new type is never encoded as another instrument for the old classifier.
    Its kind key is withheld from that call, its original result is preserved,
    and the exact named/reviewed type is restored only in this module's copy.
    """
    decisions = part_decisions or {}
    forwarded = deepcopy(decisions)
    for decision in forwarded.values():
        if decision.get("kind") not in FROZEN_LABELS:
            decision.pop("kind", None)
    frozen = classify_parts(parts, view_pairs=list(view_pairs), separate_tabs=separate_tabs, part_decisions=forwarded)
    result = deepcopy(frozen)
    part_index = {part["part_id"]: part for part in parts}
    for role in result["roles"]:
        kind = decisions.get(role["part_id"], {}).get("kind")
        if kind is None and not role["sounding"]:
            # Empty declarations retain their descriptive type for the PDF
            # label comparison, without adding an active performing role.
            kind = expansion_kind(part_index[role["part_id"]]["name"])
        if kind is not None:
            if kind not in LABELS:
                raise ValueError("unknown expansion instrument type")
            role["kind"] = kind
    omitted = {row["part_id"] for row in result["duplicate_views"]}
    retained = [role for role in result["roles"] if role["sounding"] and role["part_id"] not in omitted]
    counts = Counter(role["kind"] for role in retained)
    issues = [issue for issue in result["issues"] if issue not in {"scope_exception_in_actual_score", "no_acoustic_guitar_role_in_actual_score"}]
    role_index = {role["part_id"]: role for role in retained}
    for issue in list(issues):
        if issue.endswith(":unresolved_cross_part_TAB_view"):
            role = role_index.get(issue.split(":", 1)[0])
            if role and not any(other["kind"] == role["kind"] and not other["tab_present"] for other in retained):
                issues.remove(issue)
    uncertain = bool(issues)
    exceptions = sorted(set(counts) & FALLBACK_EXCLUDED)
    if exceptions:
        issues.append("scope_exception_in_actual_score")
    guitar = sum(counts.get(kind, 0) for kind in ACOUSTIC_GUITAR_KINDS)
    if not guitar:
        issues.append("no_acoustic_guitar_role_in_actual_score")
    groups = {LABELS[kind][2] for kind in counts if kind not in ACOUSTIC_GUITAR_KINDS}
    if exceptions or not guitar and "unknown" not in counts:
        topic = "other_instrumentation"
    elif "unknown" in counts:
        topic = "unspecified"
    elif not groups:
        topic = "guitar_unspecified" if uncertain else {1: "solo", 2: "duo", 3: "trio", 4: "quartet"}.get(guitar, "guitar_ensemble")
    else:
        topic = next(iter(groups)) if len(groups) == 1 else "mixed_chamber"
    if not groups and not uncertain:
        en = {1: "Guitar solo", 2: "2 guitars", 3: "3 guitars", 4: "4 guitars"}.get(guitar, f"{guitar} guitars")
        zh = {1: "吉他独奏", 2: "吉他二重奏", 3: "吉他三重奏", 4: "吉他四重奏"}.get(guitar, f"{guitar}把吉他合奏")
    else:
        keys = sorted(counts, key=lambda key: (key != "guitar", LABELS[key][0]))
        # Counts describe retained notation rows. An unresolved view/doubling or
        # collective boundary cannot turn those rows into displayed headcounts.
        en = " and ".join((f"{counts[key]} " if counts[key] > 1 and not uncertain else "") + LABELS[key][0] for key in keys)
        zh = "、".join((f"{counts[key]}×" if counts[key] > 1 and not uncertain else "") + LABELS[key][1] for key in keys)
        if uncertain:
            en += " (player counts unspecified)"
            zh += "（演奏人数未定）"
    result.update(status="file_reviewed_uncertain" if uncertain else "file_verified", instrumentation=en,
        instrumentation_zh=zh, topic_id=topic, guitar_player_count=guitar if not uncertain else None,
        ensemble_player_count=len(retained) if not uncertain else None, role_counts=dict(counts),
        scope_exceptions=exceptions, issues=sorted(set(issues)), frozen_classifier_output=frozen)
    return result


def validate_reviewed_case(case, work, mxl_evidence):
    if (not isinstance(case, dict) or not isinstance(work, dict)
            or any(case.get(key) != work.get(key) for key in ("id", "title_en", "composer_en", "source_url"))
            or case.get("mxl_sha256") != mxl_evidence.get("file_sha256")
            or case.get("part_names") != [row["name"] for row in mxl_evidence["parts"]]
            or not isinstance(case.get("note"), str) or not case["note"].strip() or not case.get("basis")):
        raise ValueError("exact expansion semantic review guard mismatch")
    if "native_record_sha256" in case:
        native_guard = case["native_record_sha256"]
        if (not isinstance(native_guard, str) or not re.fullmatch(r"[0-9a-f]{64}", native_guard)
                or native_guard != per_record_guard(work)):
            raise ValueError("exact expansion native record guard mismatch")
    if case.get("pdf_sha256") is not None and not re.fullmatch(r"[0-9a-f]{64}", str(case["pdf_sha256"])):
        raise ValueError("invalid reviewed PDF byte guard")
    if "identity_review_override" in case and not re.fullmatch(r"[0-9a-f]{64}", str(case.get("pdf_sha256", ""))):
        raise ValueError("file-title semantic decision requires exact PDF bytes")
    if "scope_exclusion_note" in case and (not isinstance(case["scope_exclusion_note"], str) or not case["scope_exclusion_note"].strip()):
        raise ValueError("exact scope exclusion requires a nonempty actual-file reason")
    if "scope_pending_note" in case:
        if (not isinstance(case["scope_pending_note"], str) or not case["scope_pending_note"].strip()
                or "scope_exclusion_note" in case):
            raise ValueError("exact scope uncertainty requires a nonempty reason and cannot also exclude")
        if ("native_record_sha256" not in case
                or not re.fullmatch(r"[0-9a-f]{64}", str(case.get("pdf_sha256", "")))):
            raise ValueError("exact scope uncertainty requires complete native and PDF byte guards")
    ids = {row["part_id"] for row in mxl_evidence["parts"]}
    decisions = case.get("part_decisions", {})
    if not isinstance(decisions, dict) or not set(decisions) <= ids:
        raise ValueError("reviewed expansion part ID absent from actual MXL")
    for decision in decisions.values():
        if (not isinstance(decision, dict) or not set(decision) <= {"kind", "resolved", "role_active"}
                or "kind" in decision and decision["kind"] not in LABELS
                or "resolved" in decision and type(decision["resolved"]) is not bool
                or "role_active" in decision and decision["role_active"] is not None and type(decision["role_active"]) is not bool):
            raise ValueError("invalid exact reviewed part decision")
    return deepcopy(case)


def reviewed_cases(root):
    path = Path(root) / REVIEWED_CASES
    if not path.exists():
        return {}, None
    if path.is_symlink() or not path.resolve().is_relative_to(Path(root).resolve()):
        raise ValueError("reviewed expansion asset must remain in the library")
    raw = path.read_bytes()
    payload = json.loads(raw)
    entries = payload.get("entries")
    if payload.get("schema_version") != 1 or not isinstance(entries, list):
        raise ValueError("invalid expansion semantic-review asset")
    indexed = {row.get("id"): row for row in entries if isinstance(row, dict)}
    if len(indexed) != len(entries) or any(not isinstance(key, str) or not re.fullmatch(r"musescore:[1-9][0-9]*", key) for key in indexed):
        raise ValueError("duplicate or invalid reviewed expansion native identity")
    return indexed, {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}


def review_mxl_scope(mxl_evidence, view_sequences=None, *, source_record=None, reviewed_case=None):
    """Pure written-role review; no PDF/MIDI completion or native-text mutation."""
    parts = mxl_evidence.get("parts")
    if not isinstance(parts, list) or not parts:
        raise ValueError("actual MXL parts required")
    if len({row["part_id"] for row in parts}) != len(parts):
        raise ValueError("duplicate MXL part ID")
    if view_sequences is not None and view_sequences.get("file_sha256") != mxl_evidence.get("file_sha256"):
        raise ValueError("MXL view sequence file guard mismatch")
    if reviewed_case is not None:
        reviewed_case = validate_reviewed_case(reviewed_case, source_record, mxl_evidence)
        if "scope_exclusion_note" in reviewed_case:
            automatic = review_mxl_scope(mxl_evidence, view_sequences, source_record=source_record)
            classification = deepcopy(automatic["classification"])
            classification.update(status="mxl_scope_excluded", topic_id="other_instrumentation",
                guitar_player_count=None, ensemble_player_count=None,
                automatic_review=automatic, reviewed_case=deepcopy(reviewed_case),
                scope_exclusion_note=reviewed_case["scope_exclusion_note"])
            return {"status": "excluded", "reason": "exact_reviewed_actual_scope_exclusion", "classification": classification}
        if "scope_pending_note" in reviewed_case:
            automatic = review_mxl_scope(mxl_evidence, view_sequences, source_record=source_record)
            classification = deepcopy(automatic["classification"])
            classification.update(status="mxl_scope_uncertain", guitar_player_count=None, ensemble_player_count=None,
                automatic_review=automatic, reviewed_case=deepcopy(reviewed_case),
                scope_pending_note=reviewed_case["scope_pending_note"])
            if classification["topic_id"] in {"solo", "duo", "trio", "quartet", "guitar_ensemble"}:
                classification["topic_id"] = "guitar_unspecified"
            return {"status": "pending", "reason": "exact_reviewed_actual_scope_uncertainty", "classification": classification}
    decisions, additions, slides = _part_decisions(parts)
    tab_review = _tab_review(parts, decisions, view_sequences)
    automatic = None
    if reviewed_case is not None and any(key in reviewed_case for key in ("part_decisions", "tab_view_pairs", "separate_tab_parts")):
        automatic = review_mxl_scope(mxl_evidence, view_sequences, source_record=source_record)
        for identity, decision in reviewed_case.get("part_decisions", {}).items():
            decisions.setdefault(identity, {}).update(decision)
            if decision.get("resolved") or decision.get("role_active") is False:
                additions = [issue for issue in additions if not issue.startswith(identity + ":")]
                if decision.get("role_active") is False or (decision.get("resolved") and decision.get("kind") not in {None, "electric_guitar"}):
                    slides = [value for value in slides if value != identity]
            if decision.get("role_active") is False:
                decisions[identity]["resolved"] = True
        if "tab_view_pairs" in reviewed_case:
            if not isinstance(reviewed_case["tab_view_pairs"], list):
                raise ValueError("reviewed TAB pairs must be an explicit list")
            tab_review["automatic_performing_view_pairs"] = tab_review["performing_view_pairs"]
            tab_review["performing_view_pairs"] = deepcopy(reviewed_case["tab_view_pairs"])
            # The exact visual decision explicitly resolves numbered-view limits.
            tabs = {row["tab_part_id"] for row in reviewed_case["tab_view_pairs"]}
            tab_review["issues"] = [issue for issue in tab_review["issues"] if issue.split(":", 1)[0] not in tabs]
    classification = classify_expansion_parts(parts, view_pairs=tab_review["performing_view_pairs"],
        separate_tabs=(reviewed_case or {}).get("separate_tab_parts", []), part_decisions=decisions)
    classification["notation_classification_status"] = classification["status"]
    classification["issues"] = sorted(set(classification["issues"] + additions + tab_review["issues"]))
    classification.update(basis="actual_mxl_written_roles", review_stage="mxl_scope_only",
                          part_decisions=decisions, tab_view_review=tab_review,
                          actual_slide_guitar_parts=slides)
    if automatic is not None:
        classification["automatic_review"] = automatic
        classification["reviewed_case"] = deepcopy(reviewed_case)
    if source_record is not None:
        classification["source_declaration"] = {"id": source_record.get("id"),
            "instrumentation": source_record.get("metadata", {}).get("instrumentation"),
            "source_instruments": deepcopy(source_record.get("metadata", {}).get("source_instruments")),
            "source_parts_names": deepcopy(source_record.get("metadata", {}).get("source_parts_names"))}
    # Scope exclusions do not hide conflicting evidence: a contradiction needs
    # semantic review before the file is considered either accepted or excluded.
    scope_only_issues = {"scope_exception_in_actual_score", "no_acoustic_guitar_role_in_actual_score"}
    unresolved = {issue for issue in classification["issues"]
                  if issue not in scope_only_issues and issue.rsplit(":", 1)[-1] not in COUNT_OR_PLAYBACK_ISSUES}
    retained = [role for role in classification["roles"] if role["sounding"]
                and role["part_id"] not in {row["part_id"] for row in classification["duplicate_views"]}]
    counts = Counter(role["kind"] for role in retained)
    electric_acoustic_conflict = any(role["kind"] == "electric_guitar" and
        f"{role['part_id']}:guitar_patch_label_conflict" in classification["issues"] for role in retained)
    if unresolved or "unknown" in counts or electric_acoustic_conflict:
        status, reason = "pending", "ambiguous_actual_instrumentation"
    elif set(counts) & FALLBACK_EXCLUDED or slides:
        status, reason = "excluded", "active_excluded_instrument"
    elif not any(counts.get(kind) for kind in ACOUSTIC_GUITAR_KINDS):
        status, reason = "excluded", "no_active_acoustic_guitar"
    elif len(retained) > (8 if set(counts) - ACOUSTIC_GUITAR_KINDS else 16):
        status, reason = "excluded", "large_ensemble"
    else:
        status, reason = "accepted", "actual_mxl_guitar_scope"
    uncertain_count = bool(classification["issues"])
    classification["scope_role_count_upper_bound"] = len(retained)
    classification["status"] = "mxl_scope_verified" if status == "accepted" and not uncertain_count else "mxl_scope_excluded" if status == "excluded" else "mxl_scope_uncertain"
    if status == "pending" or (status == "accepted" and uncertain_count):
        classification["guitar_player_count"] = None
        classification["ensemble_player_count"] = None
        if classification["topic_id"] in {"solo", "duo", "trio", "quartet"}:
            classification["topic_id"] = "guitar_unspecified"
        if status == "accepted":
            keys = sorted(counts, key=lambda key: (key != "guitar", LABELS[key][0]))
            classification["instrumentation"] = " and ".join(LABELS[key][0] for key in keys)
            classification["instrumentation_zh"] = "、".join(LABELS[key][1] for key in keys) + "（演奏人数未明）"
            reason = "actual_mxl_guitar_scope_player_count_uncertain"
    return {"status": status, "reason": reason, "classification": classification}


def _digest(path):
    digest, size = hashlib.sha256(), 0
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
            size += len(block)
    return {"sha256": digest.hexdigest(), "size": size}


def _guard_asset(root, asset):
    if (not isinstance(asset, dict) or asset.get("format") != "MUSICXML" or asset.get("status") != "verified"
            or type(asset.get("size")) is not int or asset["size"] <= 0
            or not isinstance(asset.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", asset["sha256"])):
        raise ValueError("verified expansion MUSICXML asset required")
    expected = f"sources/musescore/objects/{asset['sha256']}.mxl"
    if asset.get("local_path") != expected or PurePosixPath(asset["local_path"]).as_posix() != expected:
        raise ValueError("unapproved MXL object path")
    path = root / expected
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("MXL object path escapes library")
    if _digest(path) != {"sha256": asset["sha256"], "size": asset["size"]}:
        raise ValueError("MXL object hash/size guard mismatch")
    return path


def bounded_results(executor, function, jobs, *, limit):
    """Keep only a bounded number of independent read-only records in flight."""
    pending, iterator = {}, iter(enumerate(jobs))
    def submit_one():
        item = next(iterator, None)
        if item is None:
            return False
        index, job = item
        pending[executor.submit(function, job)] = index
        return True
    for _ in range(limit):
        if not submit_one():
            break
    while pending:
        completed, _ = wait(pending, return_when=FIRST_COMPLETED)
        for future in completed:
            index = pending.pop(future)
            yield index, future.result()
            submit_one()


def _review_scope_record(job):
    root, plan_sha, identity, work, acquired, case = job
    if acquired.get("status") != "verified":
        return {"status": "pending", "reason": "mxl_" + str(acquired.get("status", "missing")),
                             "classification": None, "mxl_evidence": None, "asset_guard": None,
                             "extraction_evidence": deepcopy(acquired)}
    asset = acquired.get("asset")
    path = _guard_asset(root, asset)
    try:
        actual = read_mxl_evidence(path)
        if actual["file_sha256"] != asset["sha256"] or actual["file_bytes"] != asset["size"]:
            raise ValueError("MXL evidence differs from verified object")
        has_tab = any(row.get("sign") == "TAB" for part in actual["parts"] for row in part.get("clefs", []))
        sequences = read_mxl_view_sequences(path) if has_tab else None
        if case is not None:
            validate_reviewed_case(case, work, actual)
            if case.get("pdf_sha256") and any(key in case for key in ("part_decisions", "tab_view_pairs", "separate_tab_parts", "scope_exclusion_note", "scope_pending_note")):
                pdf_path = root / f"sources/musescore/objects/{case['pdf_sha256']}.pdf"
                proof_path = root / BASE / "pdf-extraction.json"
                proof = json.loads(proof_path.read_bytes())
                pdf_asset = proof.get("records", {}).get(identity, {}).get("asset", {})
                if (proof.get("plan_sha256") != plan_sha or pdf_asset.get("status") != "verified"
                        or pdf_asset.get("sha256") != case["pdf_sha256"]
                        or _digest(pdf_path) != {"sha256": pdf_asset["sha256"], "size": pdf_asset["size"]}):
                    raise ValueError("reviewed expansion PDF evidence guard mismatch")
        result = review_mxl_scope(actual, sequences, source_record=work, reviewed_case=case)
        return {**result, "mxl_evidence": actual, "asset_guard": deepcopy(asset)}
    except (ValueError, RuntimeError, OSError) as error:
        return {"status": "pending", "reason": "actual_mxl_review_failed", "error": str(error),
                             "classification": None, "mxl_evidence": None, "asset_guard": deepcopy(asset)}


def review_scope(root, plan=None, extraction=None, *, workers=8):
    if type(workers) is not int or not 1 <= workers <= 8:
        raise ValueError("scope workers must be between 1 and 8")
    root = Path(root).resolve()
    plan_path, extraction_path = root / BASE / "plan.json", root / BASE / "mxl-extraction.json"
    plan_raw, extraction_raw = plan_path.read_bytes(), extraction_path.read_bytes()
    actual_plan, actual_extraction = json.loads(plan_raw), json.loads(extraction_raw)
    if plan is not None and plan != actual_plan or extraction is not None and extraction != actual_extraction:
        raise ValueError("scope supplied inputs differ from frozen files")
    plan, extraction = actual_plan, actual_extraction
    if plan.get("status") != "prepared" or extraction.get("status") != "complete":
        raise ValueError("prepared plan and completed MXL extraction required")
    plan_sha = hashlib.sha256(plan_raw).hexdigest()
    if extraction.get("plan_sha256") != plan_sha or extraction.get("format") != "MUSICXML":
        raise ValueError("MXL extraction plan identity mismatch")
    works = {work["id"]: work for work in plan.get("works", [])}
    if len(works) != len(plan.get("works", [])) or any(not re.fullmatch(r"musescore:[1-9][0-9]*", identity) for identity in works):
        raise ValueError("duplicate or invalid scope native identities")
    if set(extraction.get("scope_ids", [])) != set(works) or set(extraction.get("records", {})) != set(works):
        raise ValueError("MXL extraction does not cover exact plan scope")
    methods = ["scripts/review_musescore_expansion.py", "scripts/review_musescore_instrumentation.py",
               "scripts/score_instrumentation.py", "scripts/source_adapters/pdmx_formats.py",
               "scripts/catalog_instrumentation.py"]
    method_guards = {name: _digest(root / name) for name in methods}
    cases, case_guard = reviewed_cases(root)
    if not set(cases) <= set(works):
        raise ValueError("reviewed expansion case is outside the frozen append plan")
    identities = sorted(works, key=lambda value: int(value.split(":")[1]))
    jobs = ((root, plan_sha, identity, works[identity], extraction["records"][identity], cases.get(identity)) for identity in identities)
    records = {}
    if workers == 1:
        results = ((index, _review_scope_record(job)) for index, job in enumerate(jobs))
        for index, row in results:
            records[identities[index]] = row
            if len(records) % 100 == 0:
                print(json.dumps({"mxl_scope_reviewed": len(records), "total": len(works)}), flush=True)
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for index, row in bounded_results(executor, _review_scope_record, jobs, limit=workers * 2):
                records[identities[index]] = row
                if len(records) % 100 == 0:
                    print(json.dumps({"mxl_scope_reviewed": len(records), "total": len(works)}), flush=True)
    records = {identity: records[identity] for identity in identities}
    if plan_path.read_bytes() != plan_raw or extraction_path.read_bytes() != extraction_raw:
        raise ValueError("scope input files changed during review")
    if any(_digest(root / name) != guard for name, guard in method_guards.items()):
        raise ValueError("scope method changed during review")
    if reviewed_cases(root)[1] != case_guard:
        raise ValueError("reviewed expansion asset changed during scope review")
    accepted = [identity for identity, row in records.items() if row["status"] == "accepted"]
    report = {"schema_version": 1, "status": "complete", "review_stage": "mxl_scope_only",
              "checked_at": datetime.now(timezone.utc).isoformat(),
              "inputs": {"plan": {"sha256": plan_sha, "size": len(plan_raw)},
                         "mxl_extraction": {"sha256": hashlib.sha256(extraction_raw).hexdigest(), "size": len(extraction_raw)},
                         "methods": method_guards, "reviewed_cases": case_guard},
              "accepted_ids": accepted, "records": records,
              "summary": {"records": len(records), "statuses": dict(Counter(row["status"] for row in records.values())),
                          "reasons": dict(Counter(row["reason"] for row in records.values())),
                          "accepted_primary_topics": dict(Counter(records[identity]["classification"]["topic_id"] for identity in accepted))},
              "limitations": ["Accepted here means actual MXL written-role scope only; PDF identity and independent MIDI review are pending.",
                              "Unknown, conflicting, collective, alternative or unresolved TAB roles retain pending boundaries.",
                              "Original source declarations, assets and score bytes are unchanged."]}
    destination = root / BASE / "scope-review.json"
    temporary = destination.with_name(destination.name + ".part")
    if destination.is_symlink() or temporary.is_symlink():
        raise ValueError("scope review output cannot be a symlink")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, destination)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--phase", choices=("scope", "final"), default="scope")
    parser.add_argument("--workers", type=int, default=None)
    args = parser.parse_args()
    if args.phase == "final":
        from review_musescore_expansion_final import review_final
        result = review_final(args.root, workers=4 if args.workers is None else args.workers)
    else:
        result = review_scope(args.root, workers=8 if args.workers is None else args.workers)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
