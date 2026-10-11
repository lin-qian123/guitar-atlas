"""Strict, metadata-only projection of the published PDMX v9 snapshot.

No MuseScore requests, file downloads or inferred performer counts are made.
CSV serialization follows pnlong/PDMX utils.py at commit
7abbd6d926d2df94129034eba81c10069c9dcbc4, not fuzzy title matching.
"""
from __future__ import annotations

from copy import deepcopy
import re
from urllib.parse import unquote, urlsplit

from catalog_display import musescore_display_text
from catalog_sources import MUSESCORE_RESERVED_OWNERS

SOURCE_ID = "musescore"
MAX_CHAMBER_PARTS = 8
MAX_GUITAR_PARTS = 16
CSV_UNSUPPORTED = re.compile(r"[^ \w0-9,.?!/;:()&_+='\\<>\[\]\{\}-]")
EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
CONTACT_LABEL = re.compile(r"\b(?:postal\s+address|address|e-?mail|phone|telephone|tel|contact)\s*:|(?:地址|电话|邮箱)\s*[：:]", re.I)
ROLE_BOUNDARY = re.compile(
    r"(?<!\w)(?:(?P<composer>Composers?\s*:|Composed\s+by\b|Music\s+by\b)|"
    r"(?P<arranger>Arr\s*:|Arr\.\s*:?(?:\s*by\b\s*:?)?|Arranged\s+by\b\s*:?|"
    r"Arrangement\s*(?::|by\b\s*:?)|Arreglo\s*:|Arreglista\s*:|arrangé\s+par\b)|"
    r"(?P<transcriber>Transcription\s*(?::|by\b\s*:?)|Transcriber\s*:|Transcribed\s+by\b|Transc(?:r)?[.:])|"
    r"(?P<editor>Editor\s*:|(?:TabEdited|Edited)\s+by\b)|"
    r"(?P<performer>Performed\s+by\b|Performer\s*:)|"
    r"(?P<author>Author\s*:)|"
    r"(?P<source_unspecified>(?:MuseScore\s+)?Transcription/Arrangement/TAB\s+by\b|"
    r"Edition\s*:|Artist\s*:|Encoded\s+by\b|Tabulated\s+by\b))", re.I)
# These are observed responsibility cues, not sufficient name/role boundaries.
# A missing colon/by, mixed construction or damaged foreign label must not turn
# its unlabelled context into a composer. Recovered cues are used only to reject
# that inference; native transcriptions remain untouched.
RESPONSIBILITY_CUE = re.compile(
    r"(?<!\w)(?:arr(?:\.|(?=\s|:))|arranged\b|arrangement\b|arragement\b|"
    r"arreglo\b|arreglista\b|arrangé\b|adatt\.|transc(?:r)?[.:]|trans\.|trnsc\.|"
    r"transcription\b|transcribed\b|tabedited\b|encoded\b|tabulated\b|performed\b|"
    r"performaned\b|edited\b|editor\b|edition\b|artist\b|author\b|аранж\.|\?prava\s*:)", re.I)
EMPTY_ROLE_LABEL = re.compile(r"(?:Composers?|Arranger|Editor|Author|Performer|Transcriber|Artist)\s*:?[\s.]*", re.I)
LICENSES = {
    "cc-zero": ("https://creativecommons.org/publicdomain/zero/1.0/", "CC0 1.0（来源历史标注）"),
    "publicdomain": ("https://creativecommons.org/publicdomain/mark/1.0/", "Public Domain Mark 1.0（来源历史标注）"),
}
RESERVED = MUSESCORE_RESERVED_OWNERS
INSTRUMENTS = {
    "guitar": "Guitar", "classical guitar": "Guitar", "acoustic guitar": "Guitar",
    "nylon string guitar": "Guitar", "steel string guitar": "Guitar",
    "violin": "violin", "viola": "viola", "cello": "cello", "violoncello": "cello",
    "contrabass": "double bass", "double bass": "double bass", "viol": "viol",
    "flute": "flute", "flute piccolo": "flute", "flute alto": "flute", "flute bass": "flute",
    "recorder": "recorder", "oboe": "oboe", "bassoon": "bassoon", "contrabassoon": "bassoon",
    "clarinet": "clarinet", "clarinet in b-flat": "clarinet", "clarinet in a": "clarinet",
    "clarinet in e-flat": "clarinet", "clarinet bass": "clarinet", "clarinet alto": "clarinet",
    "clarinet contrabass": "clarinet", "saxophone": "saxophone", "saxophone alto": "saxophone",
    "saxophone tenor": "saxophone", "saxophone soprano": "saxophone", "saxophone baritone": "saxophone",
    "trumpet": "trumpet", "trumpet in b-flat": "trumpet", "trumpet in c": "trumpet",
    "trumpet piccolo": "trumpet", "trombone": "trombone", "trombone tenor": "trombone",
    "trombone bass": "trombone", "french horn": "horn", "horn": "horn", "natural horn": "horn",
    "tuba": "tuba", "euphonium": "euphonium", "cornet": "cornet", "flugelhorn": "flugelhorn",
    "piano": "piano", "organ": "organ", "harpsichord": "harpsichord", "clavichord": "clavichord",
    "celesta": "celesta", "accordion": "accordion", "harmonica": "harmonica", "harmonium": "harmonium",
    "bandoneon": "bandoneon", "melodica": "melodica", "virginal": "virginal",
    "harp": "harp", "mandolin": "mandolin", "lute": "lute", "vihuela": "vihuela",
    "marimba": "marimba", "vibraphone": "vibraphone", "xylophone": "xylophone",
    "glockenspiel": "glockenspiel", "timpani": "timpani", "percussion": "percussion",
    "drum group": "percussion", "snare drum": "percussion", "bass drum": "percussion",
    "tambourine": "percussion", "triangle": "percussion", "tubular bells": "percussion",
    "claves": "percussion", "conga": "percussion", "bongo": "percussion", "woodblock": "percussion",
    "castanets": "percussion", "handbells": "percussion", "gong": "percussion", "crotales": "percussion",
    "maraca": "percussion", "hi-hat": "percussion", "crash": "percussion", "ride": "percussion",
}
EXCLUDED_PART = re.compile(
    r"\b(?:electric|electrical|elektrisch\w*|électrique|electrica|eléctrica|elettric\w*|"
    r"distortion|distorted|overdrive|synthesizer|synth|vocals?|voices?|chorus|choir|"
    r"gesang|chant|voix|canto|voces|voce|bajo|basse|bass guitar|acoustic bass|fingered bass|"
    r"slap bass|steel guitar|hawaiian|slide guitar)\b", re.I)
ENSEMBLE_EXCLUSION = re.compile(r"orchestra|\b(?:band|bands|choir|choral|satb|a capella|drum corps)\b|voice", re.I)


def csv_serialization(value):
    """The exact documented CSV transformation; native values stay untouched."""
    if value is None or value == "":
        return ""
    value = str(value).replace("\n", "").replace(",", "")
    return " ".join(CSV_UNSUPPORTED.sub("", value).split())


def _csv(value):
    return "" if value in (None, "", "NA") else str(value)


def _true(value):
    return value is True or value == 1 or value in ("True", "true", "1")


def _id(value):
    text = str(value)
    return text if re.fullmatch(r"[1-9][0-9]*", text) else None


def _page(value, native_id, user_id, user_url):
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        home = urlsplit(user_url)
        if (parsed.scheme != "https" or parsed.netloc != "musescore.com"
                or parsed.query or parsed.fragment or "\\" in value):
            return False
        numeric = re.fullmatch(r"/user/([1-9][0-9]*)/scores/([1-9][0-9]*)", parsed.path)
        if numeric:
            return numeric.groups() == (user_id, native_id)
        named = re.fullmatch(r"/([A-Za-z0-9][A-Za-z0-9_.-]*)/scores/([1-9][0-9]*)", parsed.path)
        return bool(named and named[1].casefold() not in RESERVED and named[2] == native_id
                    and home.scheme == "https" and home.netloc == "musescore.com"
                    and not home.query and not home.fragment and home.path == "/" + named[1])
    except (ValueError, TypeError):
        return False


def _composer(raw):
    """Separate a stated responsibility boundary; never invent an author."""
    if not raw or not raw.strip():
        return "", "source_unspecified", "来源未提供作曲署名。", {}
    if EMAIL.search(raw) or CONTACT_LABEL.search(raw) or re.search(r"https?://", raw, re.I):
        return "", "source_unspecified", "来源署名含联系信息，完整转录仅留私有档案。", {}
    if not any(char.isalpha() for char in raw):
        return "", "source_unspecified", "来源署名不可辨识，完整转录仅留私有档案。", {}
    boundaries = list(ROLE_BOUNDARY.finditer(raw))
    if boundaries:
        names = {}
        for index, boundary in enumerate(boundaries):
            if boundary.lastgroup == "source_unspecified":
                continue
            end = boundaries[index + 1].start() if index + 1 < len(boundaries) else len(raw)
            value = raw[boundary.end():end].strip().removesuffix(";").strip().removesuffix(",").strip()
            # A composer label can be followed by a separate, less structured
            # responsibility statement. The exact newline/token boundary is
            # sufficient to stop the composer credit; it does not identify the
            # named transcriber/editor inside that statement.
            if boundary.lastgroup == "composer":
                following_role = re.search(r"\n\s*(?:transcribed|arranged|edited|translated|arr(?:[.:]|\s)|arrangement)\b", value, re.I)
                if following_role:
                    value = value[:following_role.start()].strip()
            if value and any(char.isalpha() for char in value) and "\n" not in value:
                names.setdefault(boundary.lastgroup, []).append(value)
        # Unlabelled context can be a book, song or writer statement. Preserve
        # it in the responsibility note rather than infer a composer from it.
        unique = {role: list(dict.fromkeys(values)) for role, values in names.items()}
        fields = {role: values[0] for role, values in unique.items()
                  if role != "composer" and len(values) == 1}
        composers = unique.get("composer", [])
        composer = composers[0] if len(composers) == 1 else ""
        if composer:
            role = "composer"
        elif any(boundary.lastgroup == "composer" for boundary in boundaries):
            role = "source_unspecified"
        else:
            role = next((boundary.lastgroup for boundary in boundaries if boundary.lastgroup in fields), "source_unspecified")
        return composer, role, "来源责任说明：" + raw, fields
    if ("\n" in raw.strip() or EMPTY_ROLE_LABEL.fullmatch(raw.strip())
            or RESPONSIBILITY_CUE.search(musescore_display_text(raw))
            or re.match(r"\s*(?:translated|uploaded)\b", raw, re.I)):
        return "", "source_unspecified", "来源责任说明（作曲者未核）：" + raw, {}
    return raw, "composer", "历史来源的作曲署名；上传者另列。", {}


def _instrumentation(score, title):
    declared = score.get("instruments")
    if not isinstance(declared, list) or not declared:
        return None, "missing_source_instruments"
    names, total = [], 0
    for instrument in declared:
        if not isinstance(instrument, dict) or not isinstance(instrument.get("name"), str):
            return None, "unknown_instrument"
        text = re.sub(r"\s*\([1-9][0-9]*\)$", "", instrument["name"]).strip().casefold()
        name = INSTRUMENTS.get(text)
        if name is None:
            return None, "unknown_or_excluded_instrument"
        count = instrument.get("count", 1)
        if type(count) is not int or count < 1:
            return None, "invalid_instrument_count"
        total += count
        names.append(name)
    if "Guitar" not in names:
        return None, "no_explicit_guitar"
    parts = score.get("parts")
    if type(parts) is not int or parts < 1:
        return None, "invalid_part_count"
    others = list(dict.fromkeys(name for name in names if name != "Guitar"))
    if max(parts, total) > (MAX_CHAMBER_PARTS if others else MAX_GUITAR_PARTS):
        return None, "large_ensemble"
    part_names = score.get("parts_names", [])
    if not isinstance(part_names, list) or any(not isinstance(value, str) for value in part_names):
        return None, "invalid_part_names"
    for value in part_names:
        # Named wind/string bass instruments are approved; a generic bass or
        # acoustic/electric bass is not silently reclassified as double bass.
        stripped = value.strip().casefold()
        if EXCLUDED_PART.search(value) or stripped in {"bass", "soprano", "alto", "tenor", "baritone", "female", "male", "child"}:
            return None, "excluded_part_instrument"
    labels = score.get("instrumentations", [])
    if not isinstance(labels, list) or any(not isinstance(value, dict) for value in labels):
        return None, "invalid_instrumentation_labels"
    if any(ENSEMBLE_EXCLUSION.search(str(value.get("name", ""))) for value in labels):
        return None, "excluded_ensemble"
    player_labels = {"solo guitar": 1, "guitar solo": 1, "guitar duet": 2, "guitar duo": 2,
                     "guitar trio": 3, "guitar quartet": 4}
    players = {player_labels[text] for value in labels
               if (text := str(value.get("name", "")).strip().casefold()) in player_labels}
    player_count = next(iter(players)) if len(players) == 1 and not others else None
    note = "Instrument names declare scope; track, staff and source count fields do not establish performers."
    title_counts = {int(value) for value in re.findall(r"\b(?:for\s+)?([1-9][0-9]*)\s+guitars?\b", title, re.I)}
    if len(players) > 1 or (player_count and title_counts and title_counts != {player_count}):
        player_count = None
        note += " Conflicting title/source player labels retain an unknown player count."
    if others:
        instrumentation = "Guitar and " + " and ".join(others)
    elif player_count:
        instrumentation = "Solo guitar" if player_count == 1 else f"{player_count} guitars"
    else:
        instrumentation = "Guitar"
    return {"instrumentation": instrumentation, "guitar_player_count": player_count,
            "instrumentation_note": note, "instrumentation_basis": "explicit_source_instrument_names"}, "accepted"


def convert_record(csv_row, metadata):
    """Return a normalized record or a concrete exclusion reason, without I/O."""
    if not isinstance(csv_row, dict) or not isinstance(metadata, dict):
        return None, "invalid_metadata_shape"
    data, mirror = metadata.get("data"), metadata.get("score")
    if not isinstance(data, dict) or not isinstance(data.get("score"), dict) or not isinstance(mirror, dict):
        return None, "missing_source_score"
    score = data["score"]
    if metadata.get("status_code") != 200:
        return None, "unsuccessful_metadata_snapshot"
    native_id = _id(score.get("id"))
    match = re.fullmatch(r"\./metadata/[0-9]+/([1-9][0-9]*)\.json", _csv(csv_row.get("metadata")))
    if not native_id or not match or match[1] != native_id or _id(mirror.get("id")) != native_id:
        return None, "native_id_mismatch"
    title, raw_composer = score.get("title"), score.get("composer_name")
    if not isinstance(title, str) or not title.strip():
        return None, "missing_source_title"
    if raw_composer is not None and not isinstance(raw_composer, str):
        return None, "invalid_source_composer"
    if mirror.get("title") != title:
        return None, "metadata_title_mismatch"
    if csv_serialization(title) != _csv(csv_row.get("title")):
        return None, "csv_title_mismatch"
    if csv_serialization(raw_composer) != _csv(csv_row.get("composer_name")):
        return None, "csv_composer_mismatch"
    if EMAIL.search(title) or re.search(r"https?://", title, re.I):
        return None, "private_contact_or_url_in_title"
    user = score.get("user")
    if not isinstance(user, dict) or not (user_id := _id(user.get("id"))):
        return None, "missing_source_uploader_identity"
    source_url = score.get("url")
    if not _page(source_url, native_id, user_id, user.get("url", "")):
        return None, "invalid_source_url"
    urls = [mirror.get("url")]
    for node in (score, mirror):
        share = node.get("share")
        if isinstance(share, dict):
            if "publicUrl" in share:
                urls.append(share["publicUrl"])
            if "url" in share:
                value = share["url"]
                urls.append(unquote(value) if isinstance(value, str) else None)
        links = node.get("_links")
        if isinstance(links, dict) and isinstance(links.get("self"), dict):
            urls.append(links["self"].get("href"))
    if any(value != source_url for value in urls):
        return None, "source_url_mismatch"
    if isinstance(mirror.get("user"), dict) and _id(mirror["user"].get("id")) != user_id:
        return None, "uploader_identity_mismatch"
    if (csv_row.get("license_conflict") not in (False, "False")
            or csv_row.get("subset:no_license_conflict") not in (True, "True")):
        return None, "license_conflict"
    license_id = score.get("license")
    if not isinstance(license_id, str) or license_id not in LICENSES or _csv(csv_row.get("license")) != license_id:
        return None, "license_mismatch"
    license_url = data.get("license_url")
    if license_url != _csv(csv_row.get("license_url")):
        return None, "license_url_mismatch"
    if license_url != LICENSES[license_id][0]:
        return None, "unsupported_license_url"
    for name in ("is_private", "is_draft", "is_official", "is_blocked"):
        if _true(score.get(name)):
            return None, name
    if mirror.get("isPublic") is False or _true(mirror.get("isBlocked")):
        return None, "private_or_blocked_snapshot"
    if any(_true(data.get(name)) for name in ("hidden", "is_blocked", "score_blocked_by_country")):
        return None, "restricted_snapshot"
    paywall = data.get("paywall")
    file_access_restrictions = []
    if _true(data.get("is_download_limited")):
        file_access_restrictions.append("download_limit")
    if _true(csv_row.get("has_paywall")) or (isinstance(paywall, dict) and _true(paywall.get("has_instant_paywall"))):
        file_access_restrictions.append("paywall")
    if _true(csv_row.get("has_lyrics")) or _csv(csv_row.get("n_lyrics")) != "0":
        return None, "lyrics"
    instrument_score = dict(score)
    if isinstance(mirror.get("partNames"), list):
        instrument_score["parts_names"] = list(score.get("parts_names", [])) + mirror["partNames"]
    scope, reason = _instrumentation(instrument_score, title)
    if scope is None:
        return None, reason
    composer, role, note, responsibility_fields = _composer(raw_composer)
    uploader = user.get("name")
    contributor = ("上传者：" + musescore_display_text(uploader) if isinstance(uploader, str) and uploader.strip()
                   and not EMAIL.search(uploader) and not re.search(r"https?://", uploader, re.I) else "")
    formats = sorted(label for field, label in (("pdf", "PDF"), ("mxl", "MUSICXML"), ("mid", "MIDI"))
                     if _csv(csv_row.get(field)))
    normalized = {
        "id": SOURCE_ID + ":" + native_id, "title_en": title, "composer_en": composer,
        "source_url": source_url, "category_ids": ["guitar"], "formats": formats,
        "resource_type": "score", "instrumentation_status": "source_declared",
        "assets": [{"format": label, "status": "metadata_only"} for label in formats],
        "metadata": {**scope, **responsibility_fields, "license": LICENSES[license_id][1], "license_url": license_url,
                     "source_license": license_id, "source_composer_attribution": raw_composer or "",
                     "source_title": title, "source_instruments": deepcopy(score.get("instruments", [])),
                     "source_instrumentations": deepcopy(score.get("instrumentations", [])),
                     "source_parts_names": deepcopy(score.get("parts_names", [])),
                     "source_parts": score.get("parts"), "source_uploader": deepcopy(user),
                     "pdmx_csv_transcription": deepcopy(csv_row),
                     "source_edition": "PDMX v9 · MuseScore 历史目录",
                     "collection": "PDMX v9 无许可冲突子集",
                     "availability": "来源页面现状未核；尚无本地谱文件。",
                     "license_note": "按 PDMX 逐条历史许可和无冲突标记整理；本次仅纳入元数据。",
                     "source_attribution_note": note, "attribution_role": role,
                     "original_arrangement_status": "unspecified", "contributors": contributor,
                     "acquisition_status": "metadata_only", "detail_status": "historical_snapshot"},
    }
    normalized["metadata"]["historical_file_access_restrictions"] = file_access_restrictions
    if file_access_restrictions:
        normalized["metadata"]["availability"] += "源站历史文件访问受限。"
    if type(score.get("pages_count")) is int and score["pages_count"] > 0:
        normalized["metadata"]["pages"] = score["pages_count"]
    encoding_notes = []
    key = score.get("keysig")
    if isinstance(key, str) and key and not EMAIL.search(key) and not re.search(r"https?://", key, re.I):
        normalized["metadata"]["source_key"] = key
        normalized["metadata"]["key"] = musescore_display_text(key)
        if normalized["metadata"]["key"] != key:
            encoding_notes.append("来源调性显示按完整 UTF-8 字节序列从 Latin-1 错解可逆还原；原始转录保留私有档案。")
    if contributor and contributor != "上传者：" + uploader:
        encoding_notes.append("上传者名称显示按完整 UTF-8 字节序列从 Latin-1 错解可逆还原；来源上传者原文与原生身份保留私有档案。")
    if encoding_notes:
        normalized["metadata"]["text_quality_note"] = "；".join(encoding_notes)
    return normalized, "accepted"
