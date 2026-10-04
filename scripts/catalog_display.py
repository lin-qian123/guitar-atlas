"""Separate explicit catalogue annotations from display titles, preserving source text.

This is a presentation projection, never source correction or identity evidence.
Only labelled fields and unambiguous bibliographic boundaries are moved. Editorial
supplied titles, uncertainty, musical subtitles and movement numbers stay intact.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field


SLASH = re.compile(r"\s+/\s*")
RESPONSIBILITY = re.compile(
    r"\s+/\s+(?=\[?(?:by|par|por|von)\b|musique\b|paroles\b|compos(?:[ée]e?s?\s+(?:par\b|et dédié)|ed\s+by\b)|"
    r"\[arranged\]\s+by\b|arrang(?:[ée]|ed)|edited\b|transcribed\b|mis(?:e)? en musique\b|music\s+(?:by\b|composed\b)|"
    r"words\b|written\b|bearbeitet\b|ausgewählt\b|a cura\b|accomp(?:an|agn|t|\.)|"
    r"dedic|dédi|published\b|copyright\b)", re.I,
)
IMPRINT = re.compile(
    r"\s+/\s+(?=(?:A|À) Paris\b|Paris\s*[, ]|Philadelphia\b|New York\b|"
    r"London\s*[, ]|Published\b|Copyright\b|Firenze,? e Bologna\b)", re.I,
)
PHYSICAL_TAIL = re.compile(r"\s+(?=\[?[\d ,ivx]+\]?\s+(?:pp?\.|fol\.)(?:\s|$))", re.I)
KNOWN_FORMAT = re.compile(r"\s*\[(Handskrift|music transcription|sound recording)\]\s*", re.I)
ARRANGER = re.compile(r"\s*\[Arr\s*:\s*([^\]]+)\]\s*", re.I)
PARENTHESIZED_ARRANGER = re.compile(r"\s*,?\s*\(arr(?:anged)?\s*(?:[.:]\s*(?:by\s+)?|by\s+)([^()]+)\)\s*", re.I)
PARENTHESIZED_RESPONSIBILITY = re.compile(r"\s*,?\s*\(bearb\.\s+([^()]+)\)\s*", re.I)
CLASSCLEF_LITERAL_ARRANGER_CREDITS = {
    "Arranged Tarrega": "Tarrega", "Arr J K Mertz": "J K Mertz",
    "Arr Tarrega": "Tarrega", "Arr Roland Dyens": "Roland Dyens",
}
COLLECTION = re.compile(r"\s+\[from\s+([^\]]+)\]", re.I)
UNCLOSED_COLLECTION = re.compile(r"\s+\[from\s+([^\]]+)$", re.I)
# These literal, observed declarations follow the individual numbered song.
# The first states the named collection; the second explicitly says the songs
# form an album. They are not a rule for arbitrary bracketed musical subtitles.
DGA_COLLECTION_DECLARATIONS = (
    (" /[LES SEPT PÉCHÉS CAPITAUX / Esquises Morales, / Paroles de Mr. J. J. / Musique de / GUSTAVE CARULLI", " / Paroles de Mr. J. J."),
    (" / [Les douze Romances Chansonnettes & Nocturnes suivans forment / L'Abum [sic] Lyrique / Pour 1834 / Composée sur les Paroles de Mr. A\xa0: Betourné", " / Composée sur les Paroles de Mr. A\xa0: Betourné"),
)
DIMENSION = re.compile(r"\d+(?:[.,]\d+)?(?:\s*[x×]\s*\d+(?:[.,]\d+)?){0,2}\s*(?:cm|mm)\b", re.I)
COUNTED_PAGE = re.compile(r"(?:\d|\])\s*(?:pp?\.?|S\.?|Bl\.?|fol\.?)\b", re.I)
ATTRIBUTION_NOTE = re.compile(r"\s*<((?:[^<>]*\d{3,4}[^<>]*)|(?:\d{1,2}\.\s*Jh\.)|(?:Lebensdaten nicht ermittelt))>\s*", re.I)
UNPRINTABLE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ufffd]")
ATTRIBUTION_ROLE = re.compile(r"(?:,?\s+)(Performer|Editor|Transcriber|Arranger|Compiler|Author|Composer)\s*$", re.I)
AUTHORITY_DATE_UNIT = r"\d{3,4}(?:-\d{2}-\d{2})?"
AUTHORITY_DATE = re.compile(r"[,，]\s*(?:" + AUTHORITY_DATE_UNIT + r"(?:\s*[-–—]\s*(?:" + AUTHORITY_DATE_UNIT + r"|\?)?)?|\?\s*[-–—]\s*" + AUTHORITY_DATE_UNIT + r")\.?\s*$")
TRANSCRIPTION_ROLE = re.compile(r"\b(?:transcripci[oó]n(?:\s+para\s+[^;]+?\s+de\b)?|trascrizione(?:\s+per\s+[^;]+?\s+di\b)?|transcribed\s+by\b)", re.I)
# These are exact observed directory-parser contaminations, not fuzzy matching
# or a general surname registry. The complete original attribution stays below.
DELCAMP_ATTRIBUTION_LABELS = {
    "Ernest Shand, Study": "Ernest Shand",
    "Johann Kaspar Mertz Etudes 1": "Johann Kaspar Mertz",
    "Johann Kaspar Mertz Op. 14. Fantasie aus der Oper": "Johann Kaspar Mertz",
    "Johann Kaspar Mertz Op. 15. Divertissement aus der Oper": "Johann Kaspar Mertz",
    "Johann Kaspar Mertz Op. 28. Fantaisie über Motive aus der Oper": "Johann Kaspar Mertz",
    "Johann Kaspar Mertz Op. 30. Fantaisie Über Motive aus der Oper": "Johann Kaspar Mertz",
    "Johann Kaspar Mertz Op. 31. Fantaisie über Motive aus der Oper": "Johann Kaspar Mertz",
}
# Frozen-directory labels that include actual title text are not whole names.
DELCAMP_TITLE_CONTAMINATED_ATTRIBUTIONS = {
    "A toye": "来源未注明作曲者",
    "Dans les jardins de mon père": "来源未注明作曲者",
    "Danse d’Avila": "来源未注明作曲者",
    "Dos palomas": "来源未注明作曲者",
    "Pavane en La": "来源未注明作曲者",
    "Que ne suis-je la fougère": "来源未注明作曲者",
    "Un éléphant qui se balançait": "来源未注明作曲者",
    "Whiskey in the jar": "来源未注明作曲者",
    "Interlude": "来源未注明作曲者",
    "Malagueña": "来源未注明作曲者",
    "Soleares": "来源未注明作曲者",
    "Auld lang syne, Away in a manger": "来源未注明作曲者",
    "Ernest Shand, Study": "Ernest Shand",
    "Ernest Shand, Divertimento": "Ernest Shand",
    "Ernest Shand, Lieder ohne Worte No.1": "Ernest Shand",
    "Ernest Shand, Farewell": "Ernest Shand",
    "Ernest Shand, Lieder ohne Worte No.5": "Ernest Shand",
    "Ernest Shand, March of the Pixies": "Ernest Shand",
    "Ernest Shand, Mazurka Russe": "Ernest Shand",
    "Ernest Shand, Gaily the Troubadour": "Ernest Shand",
    "Ernest Shand, Danse Capriccio": "Ernest Shand",
    "Ernest Shand, Graceful Dance": "Ernest Shand",
    "Ernest Shand, Mazurka": "Ernest Shand",
    "Ernest Shand, Mélodie. Nocturne": "Ernest Shand",
    "Ernest Shand, Souvenir": "Ernest Shand",
    "Ernest Shand, An Evening Reverie": "Ernest Shand",
    "Ernest Shand, Songe d’amour": "Ernest Shand",
    "Ernest Shand, Fantaisie irlandaise": "Ernest Shand",
    "Ernest Shand, Andante Expressivo": "Ernest Shand",
    "Ernest Shand, Andante Caprice": "Ernest Shand",
    "Ernest Shand, Tsigane": "Ernest Shand",
    "Ernest Shand, Gavotte et Meditation": "Ernest Shand",
    "Ernest Shand, Scene de Ballet": "Ernest Shand",
    "Ernest Shand, Andante": "Ernest Shand",
    "Ernest Shand, Danse antique": "Ernest Shand",
    "Ernest Shand, Funeral March": "Ernest Shand",
    "Ernest Shand, March": "Ernest Shand",
    "Ernest Shand, Songes d’été": "Ernest Shand",
    "Ernest Shand, Hungarian Dance": "Ernest Shand",
    "Ernest Shand, Morceau lyrique": "Ernest Shand",
    "Ernest Shand, Cradle Song": "Ernest Shand",
    "Ernest Shand, Lyric Pieces No.2": "Ernest Shand",
    "Ernest Shand, Impromptu": "Ernest Shand",
    "Ernest Shand, Marche Triomphale": "Ernest Shand",
    "Ernest Shand, Vain Regrets": "Ernest Shand",
    "Ernest Shand, Varsovie Mazurka": "Ernest Shand",
    "Ernest Shand, La Danse des Nymphes": "Ernest Shand",
    "Ernest Shand, Introduction et chanson": "Ernest Shand"
}

IMSLP_DISAMBIGUATED_LABELS = {
    "Albert, Heinrich @guitarist^": "Albert, Heinrich (guitarist)",
    "Morris, William @composer^": "Morris, William (composer)",
    "Zimmermann, H. @guitar composer^": "Zimmermann, H. (guitar composer)",
}


def display_missing_characters(value: str) -> str:
    """A missing glyph is not an empty string or a confidently restored name."""
    return UNPRINTABLE.sub("□", value)


def source_transcription(value: str) -> str:
    """Render source damage visibly instead of reintroducing control bytes."""
    text = UNPRINTABLE.sub(lambda match: "\\u" + f"{ord(match[0]):04x}", value)
    # German library authority qualifications use angle brackets, not HTML.
    return re.sub(r"<([^<>]+)>", r"（\1）", text)


@dataclass
class TitleProjection:
    title: str
    details: dict[str, str] = field(default_factory=dict)
    rules: list[str] = field(default_factory=list)
    # A slash count is a positional correspondence only when the translated
    # source has exactly the same number of slash boundaries as the original.
    slash_head: int | None = None
    slash_total: int | None = None


def append_detail(details: dict, key: str, value: str) -> None:
    value = value.strip()
    existing = str(details.get(key, ""))
    if value and ("；" + value + "；") not in ("；" + existing + "；"):
        details[key] = (existing + "；" + value) if existing else value


def _tidy_title(value: str) -> str:
    # Slash boundaries in title-page transcriptions are line breaks. A single
    # space preserves the actual words without presenting line-break markers.
    return re.sub(r"\s+", " ", SLASH.sub(" ", value)).strip(" ;/")


def attribution_words(value: str) -> list[str]:
    value = ATTRIBUTION_NOTE.sub(" ", value)
    value = ATTRIBUTION_ROLE.sub("", value)
    value = re.sub(r"\b\d{3,4}\s*-\s*\d{0,4}\b", "", value)
    folded = unicodedata.normalize("NFKD", value).casefold()
    return sorted(re.findall(r"[^\W\d_]+", "".join(char for char in folded if not unicodedata.combining(char))))


def strip_authority_dates(value: str) -> str:
    """Only a comma-delimited terminal authority date is a date field."""
    return "; ".join(AUTHORITY_DATE.sub("", part).strip() for part in value.split(";"))


def initialled_source_attribution(label: str, original: str) -> bool:
    """Match local surname + given initials only in an explicit role statement.

    This is not exposed as a name alias, identity key or general title rule.
    A surname alone, a different initial or an uncommaed source name fails.
    """
    original = strip_authority_dates(ATTRIBUTION_NOTE.sub(" ", ATTRIBUTION_ROLE.sub("", original)))
    parts = original.split(",")
    if len(parts) != 2:
        return False
    surname, given = (attribution_words(part) for part in parts)
    labelled = attribution_words(label)
    initials = sorted(word[0] for word in given)
    return bool(given and surname) and labelled == sorted([*surname, *initials])


def same_attribution(label: str, original: str) -> bool:
    words = attribution_words(original)
    return len(words) >= 2 and (attribution_words(label) == words
        or attribution_words(re.sub(r"^(?:by|par|por|von)\s+", "", label.strip(), flags=re.I)) == words)


def project_title(original: str, source: str, source_attribution: str = "") -> TitleProjection:
    result = TitleProjection(original)
    text = original
    # These exact cover transcriptions begin with a dedication, followed
    # by the actual title. Generic slash parsing must not make the dedication
    # the headline or consume the title as a publication/credit statement.
    if source == "dga":
        # Titanic Records' own 1980 advertisement labels Paul Lolax's Ti-13
        # "Ragtime Guitar". This one incomplete source transcription has a
        # damaged [sound/material-credit tail; do not reconstruct its words.
        if (original == "Ragtime guitar [sound Joplin and Joseph Lamb / transcribed and arranged by Paul Lolax]"
                and source_attribution == "Joplin, Scott, 1868-1917"):
            return TitleProjection("Ragtime guitar", details={
                "title_annotations": "[sound Joplin and Joseph Lamb / transcribed and arranged by Paul Lolax]",
                "text_quality_note": "来源 [sound 后的载体或责任转录残缺，按原文字样保留；主标题由出版社原广告核定，未补猜缺词。",
            }, rules=["exact_evidence_title_boundary"])
        covers = {
            "Respectfully dedicated to / Mrs. Edward Field / New York / Eugenie / Waltz. / Arranged for / Guitar / by / Charles De Janon": "Eugenie — Waltz",
            "Respectfully dedicated to / Mrs. Edward Field / New York / Flow'ret, Forget Me Not. / Gavotte. / Arranged for / Guitar / by / Charles De Janon": "Flow'ret, Forget Me Not — Gavotte",
        }
        if original in covers:
            return TitleProjection(covers[original], details={
                "title_annotations": "Respectfully dedicated to / Mrs. Edward Field / New York",
                "responsibility_statement": "Arranged for / Guitar / by / Charles De Janon",
                "arranger": "Charles De Janon",
            }, rules=["exact_cover_title_after_dedication"])
        if original == "Dédiée À Miss C. Rust. / Pensées Nocturnes / Valse Sentimentale / for the / Spanish Guitar / Composed by / Frederick Buckley":
            return TitleProjection("Pensées Nocturnes — Valse Sentimentale for the Spanish Guitar", details={
                "title_annotations": "Dédiée À Miss C. Rust.",
                "responsibility_statement": "Composed by / Frederick Buckley",
            }, rules=["exact_cover_title_after_dedication"])
        if original == "DÉDIÉ AUX ESTUDIANTINAS DE FRANCE / Recueil progressif / pour / GUITARE / composé / de Quinze fantaisies faciles / par / A. Battle / Prix net: 3 f. / En Vente chez: / TIXADOR ET POMÉS / Pianos et Musique / 4 Rue Mailly et 1 Rue Alsace Lorraine / PERPIGNAN / Tous drioits réservés. / Imp. C.G. Röder, Paris PN 1 (19--). 10 pp. Lithography.":
            return TitleProjection("Recueil progressif pour guitare, composé de Quinze fantaisies faciles", details={
                "title_annotations": "DÉDIÉ AUX ESTUDIANTINAS DE FRANCE",
                "responsibility_statement": "par / A. Battle",
                "physical_description": "Prix net: 3 f. / En Vente chez: / TIXADOR ET POMÉS / Pianos et Musique / 4 Rue Mailly et 1 Rue Alsace Lorraine / PERPIGNAN / Tous drioits réservés. / Imp. C.G. Röder, Paris PN 1 (19--). 10 pp. Lithography.",
            }, rules=["exact_cover_title_after_dedication"])
    if source == "freeguitarmusic":
        # These source file labels append an explicit format suffix. It is
        # material description, not part of Romanza Deluxe/Yesterday's title.
        suffix = re.search(r"\s+-\s+Score(?:\.pdf)?$", text, re.I)
        if suffix:
            append_detail(result.details, "source_type", suffix[0].strip(" -"))
            text = text[:suffix.start()]
            result.rules.append("labelled_score_file")
    if source == "cglib":
        explicit = re.search(r"\s+(Transcribed|Arranged|Edited)\s+by\s+(.+)$", text, re.I)
        if explicit and text[:explicit.start()].strip():
            role = {"transcribed": "transcriber", "arranged": "arranger", "edited": "editor"}[explicit[1].lower()]
            contributor = re.search(r"\s+(?:poem|words|lyrics)\s+by\s+.+$", explicit[2], re.I)
            name = explicit[2][:contributor.start()] if contributor else explicit[2]
            append_detail(result.details, role, name)
            if contributor:
                append_detail(result.details, "contributors", explicit[2][contributor.start():])
            append_detail(result.details, "responsibility_statement", explicit[1] + " by " + explicit[2])
            text = text[:explicit.start()].strip()
            result.rules.append("explicit_role_statement")
    if source_attribution and not (source == "delcamp" and (source_attribution in DELCAMP_ATTRIBUTION_LABELS or source_attribution in DELCAMP_TITLE_CONTAMINATED_ATTRIBUTIONS)):
        suffix = re.search(r"\s*[\[(]([^\[\]()]+)[\])]\s*$", text)
        if suffix and same_attribution(suffix[1], source_attribution) and text[:suffix.start()].strip():
            append_detail(result.details, "responsibility_statement", suffix[1])
            text = text[:suffix.start()].strip()
            result.rules.append("exact_attribution_suffix")
        by = re.search(r"\s+by\s+(.+)$", text, re.I)
        if by and same_attribution(by[1], source_attribution) and text[:by.start()].strip():
            append_detail(result.details, "responsibility_statement", "by " + by[1])
            text = text[:by.start()].strip()
            result.rules.append("exact_by_statement")
        prefix = re.match(r"^(.+?)\s*(?::|–|—|\s-\s)\s+(.+)$", text)
        if prefix and same_attribution(prefix[1], source_attribution):
            append_detail(result.details, "responsibility_statement", prefix[1])
            text = prefix[2]
            result.rules.append("exact_attribution_prefix")
    # An explicit labelled credit supplies its role independently of the site.
    # A bare (Arrangement), actual musical subtitle or unlabelled name stays.
    def arranger(match: re.Match) -> str:
        append_detail(result.details, "arranger", match[1])
        result.rules.append("labelled_arranger")
        return " "
    text = ARRANGER.sub(arranger, text)
    text = PARENTHESIZED_ARRANGER.sub(arranger, text)
    if source == "classclef":
        # Observed source labels omit both punctuation and 'by'. Only these
        # literal credits are recognized; arbitrary parenthetical prose stays.
        for credit, name in CLASSCLEF_LITERAL_ARRANGER_CREDITS.items():
            marker = "(" + credit + ")"
            if marker in text:
                append_detail(result.details, "arranger", name)
                text = text.replace(marker, " ")
                result.rules.append("labelled_literal_arranger")

    def responsibility(match: re.Match) -> str:
        # German bearb. can mean editing or adaptation; retain that literal
        # credit without assigning an unsupported composer/arranger role.
        append_detail(result.details, "responsibility_statement", "bearb. " + match[1])
        result.rules.append("labelled_parenthetical_responsibility")
        return " "
    text = PARENTHESIZED_RESPONSIBILITY.sub(responsibility, text)

    if source in {"classclef", "boije", "loc", "dga"}:

        def material(match: re.Match) -> str:
            append_detail(result.details, "source_type", match[1])
            result.rules.append("labelled_material")
            return " "
        text = KNOWN_FORMAT.sub(material, text)
    if source == "delcamp":
        # A literal directory annotation is kept as such. It does not establish
        # guitar count, instrumentation purity or an original/arrangement role.
        if re.search(r"\s+\[duo\]\s*$", text, re.I):
            text = re.sub(r"\s+\[duo\]\s*$", "", text, flags=re.I)
            result.details["title_annotations"] = "duo（来源目录的编制标注）"
            result.rules.append("directory_instrument_label")
    if source == "rism" and ";" in text:
        # RISM fallback labels contain source type and holding signature. Split
        # only its explicit known source-type token; a semicolon by itself is
        # never a title boundary.
        match = re.search(r";\s*(Manuscript copy|Autograph manuscript|Printed music)\s*;\s*(.+)$", text, re.I)
        if match:
            result.details["source_type"] = match[1]
            result.details["title_annotations"] = match[2]
            text = text[:match.start()]
            result.rules.append("rism_label_fields")
    if source == "dga":
        for marker, responsibility_marker in DGA_COLLECTION_DECLARATIONS:
            start = text.find(marker)
            if start > 0:
                tail = text[start:]
                role_start = tail.find(responsibility_marker)
                append_detail(result.details, "collection", _tidy_title(tail[:role_start].lstrip(" /[")))
                append_detail(result.details, "responsibility_statement", tail[role_start+len(" / "):])
                text = text[:start]
                result.rules.append("explicit_collection_declaration")
                break
        # Explicit "[from …]" is collection provenance, not a musical nickname.
        def collection(match: re.Match) -> str:
            append_detail(result.details, "collection", match[1])
            result.rules.append("labelled_collection")
            return " "
        text = COLLECTION.sub(collection, text)
        unclosed_collection = UNCLOSED_COLLECTION.search(text)
        if unclosed_collection and text[:unclosed_collection.start()].strip():
            append_detail(result.details, "collection", unclosed_collection[1])
            append_detail(result.details, "text_quality_note", "来源曲目集注记未闭合，按原文完整转录保留；未补猜缺失文字。")
            text = text[:unclosed_collection.start()]
            result.rules.append("labelled_unclosed_collection")
        # Never replace a descriptive untitled manuscript with an invented work
        # name. A labelled quotation is a source-supplied title, however.
        if re.match(r"^Manuscript\b", text, re.I):
            quoted = re.search(r'\b(?:Title|Titel|Cover title),?(?: printed)?:\s*"([^"]+)"', text, re.I)
            if quoted:
                text = quoted[1]
                result.rules.append("quoted_source_title")
            else:
                boundary = re.search(r"\.\s+(?=Contemporary\b|The manuscript\b|Three different\b|Two different\b)", text)
                if boundary:
                    text = text[:boundary.start()+1]
                    result.rules.append("manuscript_catalogue_description")
        candidates = [match for match in (RESPONSIBILITY.search(text), IMPRINT.search(text)) if match]
        if source_attribution:
            words = attribution_words(source_attribution)
            # A complete source name reordered around a catalogue comma is an
            # explicit statement. Initials, partial names, fuzzy spelling and
            # a bare matching surname are insufficient.
            for match in SLASH.finditer(text):
                suffix = re.split(r";|\s+/\s+", text[match.end():], maxsplit=1)[0].strip(" .")
                if len(words) >= 2 and attribution_words(suffix) == words:
                    candidates.append(match)
                    break
                remainder = text[match.end():]
                # A short source name is accepted only with an explicit
                # following transcription declaration and exact local initials.
                if TRANSCRIPTION_ROLE.search(remainder) and initialled_source_attribution(suffix, source_attribution):
                    candidates.append(match)
                    result.rules.append("initialled_author_with_explicit_transcription")
                    break
                editor = re.search(r"\s*\(ed\.\)\s*$", suffix, re.I)
                if editor and initialled_source_attribution(suffix[:editor.start()], source_attribution):
                    candidates.append(match)
                    append_detail(result.details, "editor", suffix[:editor.start()])
                    result.details["attribution_role"] = "editor"
                    result.rules.append("initialled_author_with_explicit_editor")
                    break
        boundary = min(candidates, key=lambda match: match.start()) if candidates else None
        if boundary:
            result.slash_head = len(SLASH.split(text[:boundary.start()]))
            result.slash_total = len(SLASH.split(original))
            append_detail(result.details, "responsibility_statement", text[boundary.end():])
            text = text[:boundary.start()]
            result.rules.append("bibliographic_statement")
        contains = re.search(r"\.\s+Contains:\s+", text, re.I)
        if contains:
            append_detail(result.details, "title_annotations", text[contains.end():])
            text = text[:contains.start()+1]
            result.rules.append("labelled_contents")
        # A printed extent followed by engraving/printing terminology is a
        # bibliographic tail. Mere numbers, dates and bracketed music titles do
        # not trigger this rule.
        physical = PHYSICAL_TAIL.search(text)
        if physical and re.search(r"\b(?:Engraved|Lithograph|Manuscript|Stamp|Printed)\b", text[physical.start():], re.I):
            append_detail(result.details, "physical_description", text[physical.start():])
            text = text[:physical.start()]
            result.rules.append("bibliographic_physical_tail")
        if result.rules:
            text = _tidy_title(text)
    else:
        text = re.sub(r"\s+", " ", text).strip()
    if text and text != original:
        result.title = text
    else:
        # All fields are preserved if the rule would consume the whole title.
        result.title, result.details, result.rules = original, {}, []
    return result


def project_chinese_title(original: str, translated: str, source: str, projection: TitleProjection, translated_attribution: str = "", original_attribution: str = "") -> str:
    if not translated:
        return ""
    bare = translated.removeprefix("《").removesuffix("》")
    if bare == original:
        return "《" + projection.title + "》"
    if projection.slash_head is not None:
        chunks = SLASH.split(bare)
        if len(chunks) == projection.slash_total:
            bare = " ".join(chunks[:projection.slash_head])
        else:
            # A machine translation may have merged arbitrary source fields.
            # Keep its full text under the source transcription, using the
            # unambiguous original title as the main label until reviewed.
            return ""
    elif any(rule in projection.rules for rule in ("exact_attribution_suffix", "exact_by_statement", "exact_attribution_prefix")):
        suffix = re.search(r"\s*[\[（(]([^\[\]（）()]+)[\]）)]\s*$", bare)
        prefix = re.match(r"^(.+?)\s*[:：–—]\s*(.+)$", bare)
        if suffix and (same_attribution(suffix[1], original_attribution) or (translated_attribution and re.sub(r"[\W_]+", "", suffix[1]) == re.sub(r"[\W_]+", "", translated_attribution))):
            bare = bare[:suffix.start()].strip()
        elif prefix and (same_attribution(prefix[1], original_attribution) or (translated_attribution and re.sub(r"[\W_]+", "", prefix[1]) == re.sub(r"[\W_]+", "", translated_attribution))):
            bare = prefix[2]
        else:
            return ""
    elif any(rule in projection.rules for rule in ("quoted_source_title", "rism_label_fields", "manuscript_catalogue_description", "bibliographic_physical_tail", "labelled_contents", "labelled_unclosed_collection", "explicit_collection_declaration", "labelled_parenthetical_responsibility", "labelled_literal_arranger", "exact_evidence_title_boundary")):
        return ""
    if "explicit_role_statement" in projection.rules:
        marked = re.search(r"\s+(?:Transcribed|Arranged|Edited)\s+by\s+.+$", bare, re.I)
        if marked:
            bare = bare[:marked.start()].strip()
        else:
            return ""
    if "labelled_material" in projection.rules:
        bare = re.sub(r"\s*\[(?:手稿|音乐转录|音乐抄录|录音)\]\s*", " ", bare)
    if "labelled_arranger" in projection.rules:
        # Two checked ClassClef translations combine the credit and the
        # genuine HWV/suite reference in one bracket. Keep the music reference.
        bare = re.sub(r"[\[（(][^\[（(\]）)]*(?:改编|编曲)\s*[;；]\s*(HWV\s*\d+[^\[（(\]）)]*)[\]）)]", r"（\1）", bare, flags=re.I)
        bare = re.sub(r"\s*[，,]?\s*[\[（(](?:Arr(?:anged)?\s*(?:[.:]\s*(?:by\s+)?|by\s+)[^\]）)]+|(?:编曲|改编)\s*[:：][^\]）)]+|[^\[（(\]）)]*(?:编曲|改编))[\]）)]\s*", " ", bare, flags=re.I)
    if "directory_instrument_label" in projection.rules:
        bare = re.sub(r"\s*\[(?:duo|二重奏|双人)\]\s*$", "", bare, flags=re.I)
    if "labelled_collection" in projection.rules:
        bare = re.sub(r"\s*\[(?:from|来自|出自)\s*[^\]]+\]", " ", bare, flags=re.I)
    bare = _tidy_title(bare)
    return "《" + bare + "》" if bare else ""


def safe_transcription(value: str) -> bool:
    # Download URLs/paths in damaged CMS labels must remain private. Existing
    # public URL/privacy validation supplies an independent publication check.
    return not re.search(r"https?://|file://|/Volumes/|/Users/|\.(?:pdf|mid|midi|gpx|gp[3-8]|zip)(?:$|[?#])", value, re.I)


def apply_display_projection(work: dict) -> dict:
    """Attach lossless display fields and move explicit metadata to named fields."""
    for key in ("display_title_en", "display_title_zh", "display_composer_en", "display_composer_zh"):
        work.pop(key, None)
    details = work.setdefault("details", {})
    projection = project_title(work["title_en"], work["source_id"], work.get("composer_en", ""))
    if projection.rules:
        work["display_title_en"] = display_missing_characters(projection.title)
        work["display_title_zh"] = project_chinese_title(work["title_en"], work["title_zh"], work["source_id"], projection, work.get("composer_zh", ""), work.get("composer_en", ""))
        for key, value in projection.details.items():
            append_detail(details, key, value)
        if safe_transcription(work["title_en"]):
            details["source_title_transcription"] = source_transcription(work["title_en"])
        if work["title_zh"] and work["display_title_zh"] != work["title_zh"] and safe_transcription(work["title_zh"]):
            details["translated_title_transcription"] = source_transcription(work["title_zh"])
        work["source_title_note"] = "显示题名分离明确的来源书目字段；完整来源题名保留，未改变来源身份或翻译复核状态。"
    elif projection.title != work["title_en"]:
        # Normalized spacing is a display change even when no bibliographic
        # field was separated. Keep the exact source transcription as title_en
        # and use the same English boundary as the guarded semantic review.
        work["display_title_en"] = display_missing_characters(projection.title)
    composer = work.get("composer_en", "")
    if work["source_id"] == "imslp" and composer in IMSLP_DISAMBIGUATED_LABELS:
        work["display_composer_en"] = IMSLP_DISAMBIGUATED_LABELS[composer]
        append_detail(details, "source_attribution_note", composer)
        # These are source identity qualifiers, not edition role evidence.
        if work.get("composer_zh") == composer:
            work["display_composer_zh"] = IMSLP_DISAMBIGUATED_LABELS[composer]
    if work["source_id"] == "delcamp":
        if composer in DELCAMP_ATTRIBUTION_LABELS or composer in DELCAMP_TITLE_CONTAMINATED_ATTRIBUTIONS:
            label = {**DELCAMP_ATTRIBUTION_LABELS, **DELCAMP_TITLE_CONTAMINATED_ATTRIBUTIONS}[composer]
            work["display_composer_en"] = "Source attribution unspecified" if label == "来源未注明作曲者" else label
            if not (work.get("translation", {}).get("composer", {}).get("status") in {"reference", "reviewed"}
                    and re.search(r"[\u3400-\u9fff]", work.get("composer_zh", ""))):
                work["display_composer_zh"] = label
            details["source_attribution_note"] = composer
            details["attribution_role"] = "source_unspecified"
        elif composer == "Folger’s Dowland Lute Book":
            work["display_composer_en"] = "来源署名待核"
            work["display_composer_zh"] = "来源署名待核"
            details["source_attribution_note"] = composer
            details["attribution_role"] = "unverified_name"
            append_detail(details, "text_quality_note", "来源目录署名字段包含书名，不能据此确定作曲者。")
    if work["source_id"] == "dga":
        if composer:
            details.setdefault("attribution_role", "author" if work.get("resource_type") == "reference" else "source_unspecified")
        role = ATTRIBUTION_ROLE.search(composer)
        names = composer
        if role:
            details["attribution_role"] = role[1].lower()
            names = composer[:role.start()].rstrip(" ,")
        names = ATTRIBUTION_NOTE.sub(" ", names)
        names = strip_authority_dates(names)
        names = re.sub(r"\s+", " ", names).strip()
        names = re.sub(r"<([^<>]+)>", r"（\1）", names)
        if names and names != composer:
            work["display_composer_en"] = names
            details["source_attribution_note"] = source_transcription(composer)
            if work.get("composer_zh") == composer:
                work["display_composer_zh"] = names
        translated_name = work.get("composer_zh", "")
        if translated_name and AUTHORITY_DATE.search(translated_name):
            work["display_composer_zh"] = strip_authority_dates(translated_name)
            details["source_attribution_note"] = source_transcription(composer)
            append_detail(details, "source_attribution_note", "中文参考署名转录：" + source_transcription(translated_name))
        pages = details.get("pages", "")
        dimensions = list(dict.fromkeys(DIMENSION.findall(pages)))
        if dimensions:
            append_detail(details, "dimensions", "；".join(dimensions))
            append_detail(details, "physical_description", pages)
            remainder = DIMENSION.sub("", pages).strip(" ;.")
            if COUNTED_PAGE.search(remainder):
                details["pages"] = re.split(r"\s*;\s*", remainder)[0].strip()
            else:
                details.pop("pages", None)
        elif pages and not re.fullmatch(r"\d+", pages.strip()) and not COUNTED_PAGE.search(pages):
            append_detail(details, "physical_description", pages)
            details.pop("pages", None)
    if any(UNPRINTABLE.search(work.get(field_name, "")) for field_name in ("title_en", "title_zh", "composer_en", "composer_zh")):
        append_detail(details, "text_quality_note", "来源文字存在缺失字形；□ 表示未恢复的字符，保留原文转录中的 Unicode 缺字符证据。")
    for field_name in ("title_en", "title_zh", "composer_en", "composer_zh"):
        text = work.get("display_" + field_name, work.get(field_name, ""))
        if UNPRINTABLE.search(text):
            work["display_" + field_name] = display_missing_characters(text)
            append_detail(details, "text_quality_note", "来源文字存在缺失字形；□ 表示未恢复的字符，保留原文转录中的 Unicode 缺字符证据。")
            if field_name.startswith("title") and safe_transcription(work[field_name]):
                details["source_title_transcription" if field_name.endswith("en") else "translated_title_transcription"] = source_transcription(work[field_name])
            elif field_name.startswith("composer"):
                details["source_attribution_note"] = source_transcription(work["composer_en"])
    for key, text in list(details.items()):
        if isinstance(text, str) and UNPRINTABLE.search(text):
            details[key] = display_missing_characters(text)
            append_detail(details, "text_quality_note", "来源字段存在缺失字形；□ 表示未恢复的字符，未推测替换字。")
    return work
