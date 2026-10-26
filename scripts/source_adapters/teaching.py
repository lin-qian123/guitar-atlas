"""Metadata-discovery adapters for two author-maintained guitar teaching sites.

Discovery records metadata only. A separate, authorized pipeline may retrieve
PDFs for personal/educational offline use; neither adapter grants public PDF
redistribution rights.
"""
from __future__ import annotations

import json
import hashlib
import re
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from .additional import DiscoveryClient, atomic_json, category, save_catalog, text, work

DEREK_ID = "derekhasted"
DEREK_HOME = "https://www.derek-hasted.co.uk/"
DEREK_DIRECTORY = DEREK_HOME + "free/"
DEREK_HOSTS = {"www.derek-hasted.co.uk"}

CLASSROOM_ID = "guitarclassroom"
CLASSROOM_HOME = "https://www.theguitarclassroom.com/"
CLASSROOM_DIRECTORIES = {
    "classical": CLASSROOM_HOME + "classical",
    "guitar_ensemble": CLASSROOM_HOME + "gtr-ensemble",
}
CLASSROOM_HOSTS = {"www.theguitarclassroom.com"}

SCOPE_VERSION = "2026-10-26.3"
PARSER_VERSION = "teaching-adapters-1.2.0"
RESTRICTED_REASON = (
    "Discovery records metadata only. Eligible personal/educational offline retrieval is handled separately by the shared "
    "acquisition pipeline; this does not grant public PDF redistribution rights."
)
CLASSROOM_USE = (
    "Source permits download/printing and encourages performance, but prohibits reposting, publishing/distribution, "
    "sale, or receiving compensation from the music; commercial recordings/distribution require a license. "
    "Individual offline download/printing is permitted; public reposting/distribution is prohibited."
)
DEREK_USE = (
    "Source advertises free personal download; its directory does not state a blanket public redistribution license. "
    "Discovery records metadata only; eligible personal-offline retrieval is handled separately."
)
DEREK_ACQUISITION_PERMISSION = "offered_free_personal_download"
CLASSROOM_ACQUISITION_PERMISSION = "explicit_individual_noncommercial_use"
ACQUISITION_DELAY_SECONDS = 1.0
LISTING_PAGE_COUNT_METHOD = (
    "Count only exact configured directory URLs in cached discovery_state.requests with HTTP 200; "
    "auxiliary URLs and non-200 responses are excluded."
)


def _slug(value: str) -> str:
    value = unquote(value)
    value = re.sub(r"\.pdf$", "", value, flags=re.I)
    return value.strip()


def _locator_record_id(original_locator: str) -> str:
    """Opaque identity for a source exposing file locators instead of record IDs.

    Hash the literal source href value as captured from its HTML anchor. Do not
    unquote, case-fold, or otherwise canonicalize it before hashing.
    """
    if not isinstance(original_locator, str) or not original_locator:
        raise ValueError("source PDF anchor has no exact original locator")
    return "pdf:" + hashlib.sha256(original_locator.encode("utf-8")).hexdigest()


def _clean_source_url(url: str, allowed_hosts: set[str]) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in allowed_hosts or parsed.username or parsed.password:
        raise ValueError("source link escaped the approved HTTPS host: " + url)
    return urlunsplit(("https", parsed.netloc, parsed.path, parsed.query, ""))


def _asset(url: str, label: str, *, reason: str, source_id: str) -> dict:
    path = urlsplit(url).path
    is_classroom = source_id == CLASSROOM_ID
    return {
        "source_url": url,
        "format": "PDF",
        "filename": unquote(path.rsplit("/", 1)[-1]),
        "label": label or "PDF",
        "status": "pending",
        "license": ("free personal download/printing and educational/concert performance; public redistribution prohibited"
                    if is_classroom else "free personal download offered; public redistribution permission not established"),
        "license_status": ("personal_use_only_no_public_redistribution" if is_classroom
                           else "public_redistribution_not_confirmed"),
        "acquisition_permission": (CLASSROOM_ACQUISITION_PERMISSION if is_classroom
                                   else DEREK_ACQUISITION_PERMISSION),
        "acquisition_basis": ("Official source terms permit individual download/printing and performance; no public reposting or distribution."
                              if is_classroom else "Official directory explicitly offers free download; this route is for private offline use only."),
        "acquisition_reason": reason,
        "upstream_checksum_available": False,
    }


def _categories(source_id: str, labels: dict[str, str], urls: dict[str, str]) -> list[dict]:
    return [category(key, labels[key], urls[key]) for key in sorted(labels)]


def _attribution_from_parenthetical(value: str) -> tuple[str, str]:
    """Return an exact visible title plus composer only for explicit attribution."""
    match = re.search(r"\(([^()]{2,80})\)\s*$", value)
    if not match:
        return value.strip(), ""
    credit = match.group(1).strip()
    # Parentheses also carry scoring alternatives, place/tradition labels,
    # anonymity, editing roles, and dates. Keep those in the native title but
    # do not project them into the composer field.
    if (re.search(r"\b(?:duet|duo|trio|quartet|guitar|arr\.?|arranged|editor|ed\.?|edited|transcribed|"
                  r"trad(?:itional)?|anon(?:ymous)?|or|19\d{2}|20\d{2})\b", credit, re.I)
            or credit.casefold() in {"england", "wales", "scotland", "ireland", "irish", "welsh", "english", "scottish"}):
        return value.strip(), ""
    # Preserve the source title exactly. A separate role field records the
    # parenthetical attribution when it is an author/composer name.
    if re.fullmatch(r"[\wÀ-ž.'’ -]{2,80}", credit, re.UNICODE):
        return value.strip(), credit
    return value.strip(), ""


def parse_derekhasted(html: str) -> dict:
    """Parse every score link from the confirmed free ensemble directory."""
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.find("h1")
    if not heading or text(heading) != "Free Guitar Ensemble Sheet Music":
        raise ValueError("Derek Hasted did not return the confirmed free ensemble directory")

    category_labels = {
        "two-guitars": "2 Guitars",
        "three-guitars": "3 Guitars",
        "four-guitars": "4 Guitars",
        "flexible-guitar-ensemble": "24 Guitars (source says flexible group size)",
    }
    records: dict[str, dict] = {}
    occurrences: list[dict] = []
    section_context = "main repertoire"
    instrument_group = ""
    extra_context = False
    seen_urls: dict[str, str] = {}

    for node in soup.find_all(["h2", "p"]):
        label = text(node)
        if node.name == "h2":
            if label.startswith("Extras - Some Musical Curiosities"):
                extra_context = True
                section_context = "Extras - Some Musical Curiosities"
                instrument_group = ""
                continue
            if label.startswith("Extras - Free Christmas Music"):
                extra_context = True
                section_context = "Extras - Free Christmas Music!"
                instrument_group = ""
                continue
            if label.startswith("Extras - New Year Music"):
                extra_context = True
                section_context = "Extras - New Year Music"
                instrument_group = ""
                continue
            group = re.fullmatch(r"(2|3|4|24)\s+Guitars?", label, re.I)
            if group:
                instrument_group = group.group(1)
                continue
            if label == "LOTS MORE MUSIC - read on":
                instrument_group = ""
                continue
            # A heading such as "Hewlett" before the numbered directory is a
            # performance-video label, not an additional score locator.
            continue
        if not label:
            continue
        for anchor in node.select("a[href]"):
            href = anchor.get("href", "")
            if not re.search(r"\.pdf(?:$|[?#])", href, re.I):
                continue
            asset_url = _clean_source_url(urljoin(DEREK_DIRECTORY, href), DEREK_HOSTS)
            native_locator = urlsplit(asset_url).path
            native_slug = _slug(native_locator.rsplit("/", 1)[-1])
            if not native_slug:
                raise ValueError("Derek Hasted PDF link has no stable filename slug")
            display_title = text(anchor)
            line_text = label
            title, composer = _attribution_from_parenthetical(line_text)
            if not title or title.casefold() in {"pdf", "piece"}:
                title = display_title or line_text
            if display_title.casefold() not in {"pdf", "piece"} and display_title != title:
                title = display_title
            source_cat = {
                "2": "two-guitars", "3": "three-guitars", "4": "four-guitars",
                "24": "flexible-guitar-ensemble",
            }.get(instrument_group)
            if source_cat is None:
                raise ValueError("Derek Hasted score link appeared outside a recognized instrument section")
            section = section_context
            if extra_context and section == "main repertoire":
                section = "Extras"
            declared_player_count = None if instrument_group == "24" else int(instrument_group)
            instrumentation = "guitar ensemble" if declared_player_count is None else f"{declared_player_count} guitars"
            size_description = (
                "Source calls this ‘24 Guitars’ and explicitly allows 2, 5, or any other number; no fixed performer count is asserted."
                if declared_player_count is None else ""
            )
            source_record_id = _locator_record_id(href)
            record_id = DEREK_ID + ":" + source_record_id
            if asset_url in seen_urls and seen_urls[asset_url] != record_id:
                raise ValueError("Derek Hasted identical file locator produced conflicting native IDs")
            seen_urls[asset_url] = record_id
            occurrence = {
                "native_id": native_slug,
                "source_record_id": source_record_id,
                "original_source_locator": href,
                "native_locator": native_locator,
                "title_en": title,
                "directory_label": line_text,
                "composer_en": composer,
                "arranger": None,
                "arranger_status": "not_individually_stated_on_directory",
                "instrumentation": instrumentation,
                "player_count": declared_player_count,
                "source_section_label": instrument_group + " Guitars",
                "category_id": source_cat,
                "source_section": section,
                "source_url": DEREK_DIRECTORY,
                "asset_url": asset_url,
                "disposition": "accepted",
            }
            occurrences.append(occurrence)
            if record_id not in records:
                metadata = {
                    "native_record_locator": native_locator,
                    "original_source_locator": href,
                    "former_unpublished_slug": native_slug,
                    "source_title": title,
                    "directory_title_context": line_text,
                    "source_composer_attribution": composer or None,
                    "composer_attribution_basis": "explicit parenthetical in source directory" if composer else None,
                    "arranger": None,
                    "arranger_status": "not individually stated on directory",
                    "source_page_owner_and_cataloger": "Derek Hasted",
                    "source_section": section,
                    "instrumentation": instrumentation,
                    "instrumentation_source_text": (line_text if instrument_group == "24"
                                                     else instrument_group + " Guitars"),
                    "source_section_label": instrument_group + " Guitars",
                    "player_count": declared_player_count,
                    "player_count_status": "source_declared" if declared_player_count is not None else "variable_unknown",
                    **({"description": size_description} if size_description else {}),
                    "source_use_notice": DEREK_USE,
                    "score_access": "linked_pdf_not_requested",
                    "scope_version": SCOPE_VERSION,
                    "parser_version": PARSER_VERSION,
                }
                records[record_id] = work(
                    DEREK_ID, source_record_id, title, composer, DEREK_DIRECTORY, [source_cat],
                    formats=["PDF"], assets=[_asset(asset_url, display_title, reason=RESTRICTED_REASON, source_id=DEREK_ID)],
                    metadata=metadata, instrumentation_status="source_declared",
                )
            else:
                current = records[record_id]
                if current["metadata"]["native_record_locator"] != native_locator:
                    raise ValueError("Derek Hasted slug collision across different file locators")
                current["category_ids"] = sorted(set(current["category_ids"]) | {source_cat})
                if asset_url not in {a["source_url"] for a in current["assets"]}:
                    current["assets"].append(_asset(asset_url, display_title, reason=RESTRICTED_REASON, source_id=DEREK_ID))

    if len(records) != 23:
        raise ValueError(f"Derek Hasted free directory scope changed: expected 23 unique PDF locators, found {len(records)}")
    return {
        "works": sorted(records.values(), key=lambda row: row["id"]),
        "occurrences": occurrences,
        "categories": category_labels,
        "raw_pdf_link_count": len(occurrences),
        "unique_locator_count": len(records),
        "scope_correction": {
            "earlier_manual_estimate": 24,
            "current_distinct_pdf_locator_count": 23,
            "reason": "The earlier 24 count was a manual estimate; current source HTML contains 23 unique PDF links. No missing item is inferred.",
        },
    }


def _card_title(card) -> str:
    title = card.select_one(".accordion-item-title") if card else None
    return text(title)


def _header_credit(source_title: str) -> tuple[str, str]:
    title, composer = _attribution_from_parenthetical(source_title)
    return title, composer


def _role_credit(card, title: str) -> tuple[str | None, list[str]]:
    """Extract only explicit role and person labels from an item's HTML."""
    body = card.select_one(".accordion-item-body") if card else None
    raw = text(body)
    arranger = None
    for node in body.select(".text-option") if body else []:
        line = text(node)
        match = re.fullmatch(r"arr(?:anged)?\.?\s+(?:by\s+)?([A-ZÀ-Ž][\wÀ-ž.'’ -]{1,70})", line, re.I)
        if match:
            arranger = match.group(1).strip()
            break
    terms = [term for term in re.findall(r"[\wÀ-ž]+", re.sub(r"\([^)]*\)|\[[^]]*\]", "", title).casefold())
             if len(term) > 2]
    contributors = []
    for para in body.select("p") if body else []:
        line = text(para)
        match = re.match(r"^([A-ZÀ-Ž][\wÀ-ž.'’ -]{1,70})\s+-\s+(.+)$", line)
        if match and (not terms or any(term in line.casefold() for term in terms)):
            contributors.append(line)
    return arranger, contributors


def _classroom_section(page: str, section_title: str, title: str) -> tuple[str, str, int | None]:
    folded = re.sub(r"\s+", " ", section_title).casefold()
    if page == "classical":
        if re.search(r"\b(?:duet|duo)\b", (section_title + " " + title), re.I):
            return "classical", "2 guitars", 2
        return "classical", "guitar", None
    if any(word in folded for word in ("guitar quartet & violin", "guitar quartet and strings",
                                        "string symphony", "guitar ensemble & string")):
        return "guitar_ensemble", "guitar and strings", None
    if any(word in folded for word in ("strings", "violin", "cello", "flute", "chamber")):
        return "excluded", "mixed guitar and non-guitar chamber instrumentation not explicitly scoped", None
    if any(term in folded for term in ("quartet", "quartets")):
        return "guitar_ensemble", "4 guitars", 4
    if re.search(r"\bduet\b|\bduo\b", title, re.I):
        return "guitar_ensemble", "2 guitars", 2
    if re.search(r"\btrio\b", title, re.I):
        return "guitar_ensemble", "3 guitars", 3
    return "guitar_ensemble", "guitar ensemble", None


def parse_guitarclassroom_page(html: str, page_url: str, page: str) -> dict:
    """Parse source-linked score PDF anchors without opening any score file."""
    if page not in CLASSROOM_DIRECTORIES or page_url != CLASSROOM_DIRECTORIES[page]:
        raise ValueError("The Guitar Classroom URL is outside the frozen directory scope")
    soup = BeautifulSoup(html, "html.parser")
    expected_title = "Classical Guitar - The Guitar Classroom" if page == "classical" else None
    if page == "classical" and (not soup.title or text(soup.title) != expected_title):
        raise ValueError("The Guitar Classroom did not return the confirmed Classical directory")
    if page == "guitar_ensemble" and (not soup.title or "Free Guitar Ensemble Sheet Music" not in text(soup.title)):
        raise ValueError("The Guitar Classroom did not return the confirmed Guitar Ensemble directory")

    source_sections: dict[int, str] = {}
    current_section = "Classical Guitar" if page == "classical" else "Guitar Ensemble Library"
    section_markers = (
        "beginning quartets", "intermediate – advance duets & trios", "south american duets & trios",
        "guitar quartet arrangements", "guitar quartet and strings", "intermediate – advanced quartets",
    )
    records: dict[str, dict] = {}
    occurrences: list[dict] = []
    excluded: list[dict] = []
    anchor_seen = set()

    # In the accordion cards, multiple score/part/TAB files can be one work
    # edition. Treat only role-labelled files as assets of one record. Links
    # named as separate pieces or versions (for example "Ave Maria" and
    # "1st Position Version") retain their separate native locator IDs.
    asset_labels = {"pdf", "score", "score & parts", "score and parts", "parts", "guitar parts",
                    "string parts", "tabs", "parts w-tabs"}
    locator_to_bundle: dict[str, dict] = {}
    for card in soup.select(".accordion-item"):
        card_anchors = [a for a in card.select("a[href]") if re.search(r"\.pdf(?:$|[?#])", a.get("href", ""), re.I)]
        labels = [text(a).casefold() for a in card_anchors]
        if (len(card_anchors) < 2 or not all(label in asset_labels
                                              or re.fullmatch(r"part\s*\d+", label)
                                              or re.fullmatch(r".+\btabs", label)
                                              for label in labels)
                or not any(label != "pdf" for label in labels)):
            continue
        original_locators = [a.get("href", "") for a in card_anchors]
        locators = [_clean_source_url(urljoin(page_url, href), CLASSROOM_HOSTS)
                    for href in original_locators]
        slugs = [_slug(urlsplit(locator).path.rsplit("/", 1)[-1]) for locator in locators]
        bundle = {"identity_slug": slugs[0], "primary_locator": unquote(urlsplit(locators[0]).path),
                  "original_primary_locator": original_locators[0],
                  "locators": [unquote(urlsplit(locator).path) for locator in locators],
                  "original_locators": original_locators}
        for locator in locators:
            locator_to_bundle[locator] = bundle

    # Walk headings and anchors in document order, carrying the nearest
    # directory section label. Record cards retain their own title and text.
    for node in soup.find_all(["h1", "h2", "h3", "h4", "p", "a"]):
        if node.name in {"h1", "h2", "h3", "h4", "p"}:
            label = text(node)
            folded = re.sub(r"\s+", " ", label).casefold()
            if any(marker in folded for marker in section_markers):
                current_section = label
            elif page == "classical" and label and not node.find_parent(class_="accordion-item"):
                # Preserve the source's named method/repertoire headings as
                # groups while avoiding generic navigation and page headings.
                if node.name in {"h1", "h2", "h3", "h4"}:
                    current_section = label
        if node.name != "a":
            continue
        href = node.get("href", "")
        if not re.search(r"\.pdf(?:$|[?#])", href, re.I):
            continue
        absolute = _clean_source_url(urljoin(page_url, href), CLASSROOM_HOSTS)
        path = urlsplit(absolute).path
        locator = unquote(path)
        if absolute in anchor_seen:
            continue
        anchor_seen.add(absolute)
        filename = unquote(path.rsplit("/", 1)[-1])
        native_slug = _slug(filename)
        bundle = locator_to_bundle.get(absolute)
        identity_slug = bundle["identity_slug"] if bundle else native_slug
        original_source_locator = (bundle["original_primary_locator"] if bundle else href)
        source_record_id = _locator_record_id(original_source_locator)
        card = node.find_parent(class_="accordion-item")
        header = _card_title(card)
        body = card.select_one(".accordion-item-body") if card else None
        body_text = text(body)
        label = text(node)
        component = node.find_parent(class_="component")
        component_text = text(component)
        generic_link_labels = {"pdf", "i agree", "score", "score & parts", "score and parts", "parts",
                               "guitar parts", "string parts", "tabs", "parts w-tabs"}
        if label.casefold() not in generic_link_labels:
            header_is_item = bool(header and header.casefold() != current_section.casefold())
            is_version_label = bool(re.search(r"\b(?:version|position)\b", label, re.I))
            header_terms = set(re.findall(r"[\wÀ-ž]+", header.casefold()))
            label_terms = set(re.findall(r"[\wÀ-ž]+", label.casefold()))
            names_header_item = bool(header_terms & label_terms)
            if header_is_item and (is_version_label or names_header_item) and not re.match(r"^\d+\.", label):
                title = header
            else:
                title = label
        elif header and header.casefold() != current_section.casefold():
            title = header
        elif component_text and component_text.casefold() not in generic_link_labels:
            title = component_text
        else:
            title = header or filename
        title, composer = _header_credit(title)
        arranger, credit_lines = _role_credit(card, title)
        section = current_section
        disposition, source_instrumentation, declared_count = _classroom_section(page, section, title)
        if page == "guitar_ensemble":
            if label.casefold() == "pricing & licensing info" or "pricing & licensing" in title.casefold():
                candidate = {
                    "native_id": native_slug, "native_locator": locator,
                    "source_title": "Pricing & Licensing Info", "section_title": section,
                    "directory_label": label, "source_url": page_url,
                    "asset_url": absolute, "disposition": "excluded",
                    "reason": "source policy/reference PDF, not a score in the guitar ensemble repertoire directory",
                }
                excluded.append(candidate)
                occurrences.append(candidate)
                continue
            # The South-American subsection has work-specific duet/trio labels
            # in card titles, but no count is promoted to a measured player count.
            if disposition == "excluded":
                candidate = {
                    "native_id": native_slug, "native_locator": locator,
                    "source_title": title, "section_title": section,
                    "directory_label": label, "source_url": page_url,
                    "asset_url": absolute, "disposition": "excluded",
                    "reason": "mixed guitar and non-guitar chamber instrumentation explicitly appears in the section title",
                }
                excluded.append(candidate)
                occurrences.append(candidate)
                continue
            category_id = "guitar-ensemble"
            resource_type = "score"
            player_count = declared_count
            if source_instrumentation == "guitar and strings":
                size_description = (
                    f"The source title specifies {header}; guitar and string performer counts have not been verified."
                )
                source_instrumentation_text = header
            elif declared_count is None:
                size_description = (
                    f"The source directory section is {section}; no fixed guitar performer count is stated for this item."
                )
                source_instrumentation_text = section
            else:
                size_description = ""
                source_instrumentation_text = section
        else:
            disposition = "accepted"
            category_id = "classical-guitar"
            resource_marker = (filename + " " + header).casefold()
            resource_type = "reference" if any(term in resource_marker for term in (
                "book", "lesson", "method", "technique", "pattern")) else "score"
            source_instrumentation = "guitar"
            player_count = None
            if declared_count is not None:
                player_count = declared_count
                size_description = (
                    "The source text identifies a duet; distinct score parts have not been verified."
                )
            else:
                size_description = (
                    "The source places this in a Classical Guitar directory; solo/ensemble status and performer count have not been verified."
                )
            source_instrumentation_text = header or section

        # The source exposes file locators, not record IDs. Use the exact raw
        # primary href as opaque identity; retain the old slug privately only.
        identity = CLASSROOM_ID + ":" + source_record_id
        previous = records.get(identity)
        expected_locator = bundle["primary_locator"] if bundle else locator
        if previous and previous["metadata"]["native_record_locator"] != expected_locator:
            raise ValueError("The Guitar Classroom reused a native filename slug for different PDF locators")
        category_name = "Classical" if page == "classical" else "Guitar Ensemble"
        status = "excluded" if disposition == "excluded" else "accepted"
        occurrence = {
            "native_id": native_slug, "source_record_id": source_record_id,
            "former_unpublished_slug": identity_slug,
            "original_source_locator": original_source_locator, "native_locator": locator,
            "source_title": title, "composer_en": composer,
            "arranger": arranger, "contributor_credit_lines": credit_lines,
            "section_title": section, "directory_label": label,
            "page": page, "source_url": page_url, "asset_url": absolute,
            "instrumentation": source_instrumentation, "player_count": player_count,
            "resource_type": resource_type, "disposition": status,
        }
        occurrences.append(occurrence)
        if previous:
            previous["category_ids"] = sorted(set(previous["category_ids"]) | {category_id})
            prior_occurrences = previous["metadata"].setdefault("source_occurrences", [])
            prior_occurrences.append({"source_url": page_url, "section_title": section,
                                      "source_title": title, "directory_label": label})
            if previous["title_en"] != title:
                previous["metadata"].setdefault("title_variants", []).append({"page": page, "title": title})
            if absolute not in {asset["source_url"] for asset in previous["assets"]}:
                previous["assets"].append(_asset(absolute, label, reason=RESTRICTED_REASON, source_id=CLASSROOM_ID))
            native_locators = previous["metadata"].setdefault("native_record_locators", [expected_locator])
            if locator not in native_locators:
                native_locators.append(locator)
            continue
        metadata = {
            "native_record_locator": expected_locator,
            "native_record_locators": list(bundle["locators"]) if bundle else [locator],
            "original_source_locator": original_source_locator,
            "original_source_locators": list(bundle["original_locators"]) if bundle else [href],
            "former_unpublished_slug": identity_slug,
            "source_title": title,
            "directory_title_context": header,
            "directory_label": label,
            "source_composer_attribution": composer or None,
            "composer_attribution_basis": "explicit per-item title label" if composer else None,
            "arranger": arranger,
            "arranger_attribution_basis": "explicit item body text" if arranger else None,
            "contributor_credit_lines": credit_lines,
            "source_section": section,
            "source_directory_pages": [page_url],
            "instrumentation": source_instrumentation,
            "instrumentation_source_text": source_instrumentation_text,
            "source_instrumentation_text": source_instrumentation_text,
            "player_count": player_count,
            "player_count_status": "source_declared" if player_count is not None else "unknown_not_verified_from_score_file",
            **({"description": size_description} if size_description else {}),
            **({"source_attribution_note": (
                f"Source title names the guitar-and-strings scoring: {header}. No performer count is asserted."
            )} if source_instrumentation == "guitar and strings" else {}),
            "resource_type_basis": "filename and source card label" if resource_type == "reference" else "source directory listing",
            "source_use_notice": CLASSROOM_USE if page == "guitar_ensemble" else "Source permits free download/printing; no general public redistribution license confirmed.",
            "score_access": "linked_pdf_not_requested",
            "scope_version": SCOPE_VERSION,
            "parser_version": PARSER_VERSION,
            "source_occurrences": [{"source_url": page_url, "section_title": section,
                                    "source_title": title, "directory_label": label}],
        }
        records[identity] = work(
            CLASSROOM_ID, source_record_id, title, composer, page_url, [category_id],
            formats=["PDF"], assets=[_asset(absolute, label, reason=RESTRICTED_REASON, source_id=CLASSROOM_ID)],
            metadata=metadata, resource_type=resource_type,
            instrumentation_status="source_declared" if page == "guitar_ensemble" or declared_count is not None else "unverified",
        )

    return {
        "works": sorted(records.values(), key=lambda row: row["id"]),
        "occurrences": occurrences,
        "excluded": excluded,
        "category_id": "classical-guitar" if page == "classical" else "guitar-ensemble",
        "category_name": "Classical" if page == "classical" else "Guitar Ensemble",
        "raw_pdf_link_count": len(anchor_seen),
        "unique_locator_count": len(anchor_seen),
    }


def _proposal(source_id: str) -> dict:
    if source_id == DEREK_ID:
        return {
            "id": DEREK_ID, "name": "Derek Hasted", "homepage": DEREK_HOME,
            "allowed_hosts": sorted(DEREK_HOSTS), "adapter": "normalized_catalog",
            "catalog": "sources/derekhasted/catalog.json", "family": DEREK_ID,
            "family_name_zh": "Derek Hasted 合奏谱目录", "family_name_en": "Derek Hasted ensemble music",
            "metadata_only": True, "metadata_only_phase": "discovery_only",
            "asset_hosts": sorted(DEREK_HOSTS),
            "acquisition_settings": {
                "delay": ACQUISITION_DELAY_SECONDS, "formats": ["PDF"],
                "licensing": DEREK_ACQUISITION_PERMISSION,
                "scope": "personal_offline_only",
                "public_redistribution": "not_confirmed",
            },
            "file_acquisition_note": (
                "Official directory offers free personal download; acquisition is for private offline use. "
                "No public PDF redistribution permission is confirmed."
            ),
            "page_url_rules": [{"path": r"/free/", "human_page": True}],
        }
    return {
        "id": CLASSROOM_ID, "name": "The Guitar Classroom", "homepage": CLASSROOM_HOME,
        "allowed_hosts": sorted(CLASSROOM_HOSTS), "adapter": "normalized_catalog",
        "catalog": "sources/guitarclassroom/catalog.json", "family": CLASSROOM_ID,
        "family_name_zh": "The Guitar Classroom 吉他教学与合奏谱目录",
        "family_name_en": "The Guitar Classroom guitar repertoire",
        "metadata_only": True, "metadata_only_phase": "discovery_only",
        "asset_hosts": sorted(CLASSROOM_HOSTS),
        "acquisition_settings": {
            "delay": ACQUISITION_DELAY_SECONDS, "formats": ["PDF"],
            "licensing": CLASSROOM_ACQUISITION_PERMISSION,
            "scope": "personal_offline_only",
            "public_redistribution": "prohibited_by_source",
        },
        "file_acquisition_note": (
            "Official terms allow individual download/printing and educational or concert performance, "
            "but prohibit public reposting or distribution. Acquisition is for private offline use only."
        ),
        "page_url_rules": [{"path": r"/classical", "human_page": True},
                            {"path": r"/gtr-ensemble", "human_page": True}],
    }


def _apply_acquisition_policy(catalog_data: dict, source_id: str) -> dict[str, int]:
    """Enable eligible private-offline assets without erasing download receipts."""
    is_classroom = source_id == CLASSROOM_ID
    for row in catalog_data.get("works", []):
        for item in row.get("assets", []):
            item.update({
                "license": ("free personal download/printing and educational/concert performance; "
                            "public redistribution prohibited" if is_classroom else
                            "free personal download offered; public redistribution permission not established"),
                "license_status": ("personal_use_only_no_public_redistribution" if is_classroom else
                                   "public_redistribution_not_confirmed"),
                "acquisition_permission": (CLASSROOM_ACQUISITION_PERMISSION if is_classroom
                                           else DEREK_ACQUISITION_PERMISSION),
                "acquisition_basis": ("Official source terms permit individual download/printing and performance; "
                                      "no public reposting or distribution." if is_classroom else
                                      "Official directory explicitly offers free download; this route is for private offline use only."),
                "acquisition_reason": RESTRICTED_REASON,
            })
            if item.get("status") in {None, "restricted", "metadata_only", "unavailable"}:
                item["status"] = "pending"
    counts: dict[str, int] = {}
    for row in catalog_data.get("works", []):
        for item in row.get("assets", []):
            status = item.get("status", "unknown")
            counts[status] = counts.get(status, 0) + 1
    return counts


def registry_proposals() -> dict[str, dict]:
    """Return registry suggestions without modifying shared registry files."""
    return {DEREK_ID: _proposal(DEREK_ID), CLASSROOM_ID: _proposal(CLASSROOM_ID)}


def _listing_page_count(requests: dict, source_id: str) -> int:
    """Count successful configured directory pages from the cached request state."""
    urls = ({DEREK_DIRECTORY} if source_id == DEREK_ID
            else set(CLASSROOM_DIRECTORIES.values()) if source_id == CLASSROOM_ID
            else set())
    return sum(1 for url in urls
               if isinstance(requests.get(url), dict)
               and type(requests[url].get("status")) is int
               and requests[url]["status"] == 200)


def _write_discovery(root: Path, source_id: str, name: str, homepage: str, scope: str,
                     categories: list[dict], works: list[dict], report_extras: dict,
                     inventory: dict, *, complete: bool = True) -> dict:
    client = DiscoveryClient(root, source_id, DEREK_HOSTS if source_id == DEREK_ID else CLASSROOM_HOSTS,
                             delay=ACQUISITION_DELAY_SECONDS)
    # Preserve old acquisition receipts while moving only formerly restricted,
    # non-acquired assets into the newly authorized private-offline queue.
    report = save_catalog(
        client, name, homepage, categories, works, scope, complete=complete,
        extras={"scope_version": SCOPE_VERSION, "parser_version": PARSER_VERSION,
                "source_link_first": True, **report_extras},
    )
    catalog_path = client.path / "catalog.json"
    catalog_data = json.loads(catalog_path.read_text(encoding="utf-8"))
    listing_page_count = _listing_page_count(client.state.get("requests", {}), source_id)
    catalog_data["snapshot"].update({
        "page_count": listing_page_count,
        "listing_page_count": listing_page_count,
        "page_count_method": LISTING_PAGE_COUNT_METHOD,
    })
    status_counts = _apply_acquisition_policy(catalog_data, source_id)
    atomic_json(catalog_path, catalog_data)
    atomic_json(client.path / "registry_proposal.json", _proposal(source_id))
    atomic_json(client.path / "candidate_inventory.json", inventory)
    report.update(report_extras)
    report["accepted_record_count"] = len(works)
    report["excluded_candidate_count"] = len(inventory.get("excluded", []))
    report["pending_candidate_count"] = len(inventory.get("pending", []))
    report["candidate_inventory"] = "candidate_inventory.json"
    report["scope_version"] = SCOPE_VERSION
    report["parser_version"] = PARSER_VERSION
    report["asset_status_counts"] = status_counts
    report["page_count"] = listing_page_count
    report["listing_page_count"] = listing_page_count
    report["page_count_method"] = LISTING_PAGE_COUNT_METHOD
    report["metadata_only_phase"] = "discovery_only"
    report["acquisition_scope"] = "personal_offline_only"
    report["public_pdf_redistribution"] = (
        "prohibited_by_source" if source_id == CLASSROOM_ID else "not_confirmed"
    )
    atomic_json(client.path / "discovery_report.json", report)
    return {
        "source_id": source_id,
        "catalog": f"sources/{source_id}/catalog.json",
        "candidate_inventory": "candidate_inventory.json",
        "discovery_complete": complete,
        "scope_version": SCOPE_VERSION,
        "parser_version": PARSER_VERSION,
        "source_record_count": len(works),
        "listing_page_count": listing_page_count,
        "score_record_count": report["score_record_count"],
        "reference_record_count": report["reference_record_count"],
        "category_count": report["category_count"],
        "category_membership_count": report["category_membership_count"],
        "source_link_count": report_extras.get("source_link_count"),
        "excluded_candidate_count": len(inventory.get("excluded", [])),
        "pending_candidate_count": len(inventory.get("pending", [])),
    }


def discover_derekhasted(root: Path) -> dict:
    client = DiscoveryClient(root, DEREK_ID, DEREK_HOSTS, delay=ACQUISITION_DELAY_SECONDS)
    raw, request = client.get(DEREK_DIRECTORY)
    parsed = parse_derekhasted(raw.decode("utf-8", "replace"))
    categories = _categories(DEREK_ID, parsed["categories"], {
        "two-guitars": DEREK_DIRECTORY, "three-guitars": DEREK_DIRECTORY,
        "four-guitars": DEREK_DIRECTORY, "flexible-guitar-ensemble": DEREK_DIRECTORY,
    })
    inventory = {
        "schema_version": 1, "source_id": DEREK_ID, "scope_version": SCOPE_VERSION,
        "parser_version": PARSER_VERSION, "frozen_at": client.state["started_at"],
        "directory_url": DEREK_DIRECTORY, "directory_http_status": request["status"],
        "raw_pdf_link_count": parsed["raw_pdf_link_count"],
        "unique_locator_count": parsed["unique_locator_count"],
        "accepted": parsed["occurrences"], "excluded": [], "pending": [],
        "scope_correction": parsed["scope_correction"],
        "boundary": "Free ensemble directory only; paid shop, copyright-cleared paid catalogue, and mixed-instrument pages excluded.",
    }
    return _write_discovery(
        root, DEREK_ID, "Derek Hasted", DEREK_HOME,
        "Discovery phase: metadata only for all distinct PDF filename locators on the official free guitar ensemble directory; source headings give 2/3/4 guitars except the explicitly flexible 24-Guitars item. The source offers free personal downloads, which may be acquired separately for private offline use; public PDF redistribution permission is not confirmed.",
        categories, parsed["works"],
        {"source_link_count": parsed["raw_pdf_link_count"], "unique_native_locator_count": parsed["unique_locator_count"],
         "scope_correction": parsed["scope_correction"]}, inventory,
    )


def discover_guitarclassroom(root: Path) -> dict:
    client = DiscoveryClient(root, CLASSROOM_ID, CLASSROOM_HOSTS, delay=ACQUISITION_DELAY_SECONDS)
    combined: dict[str, dict] = {}
    all_occurrences: list[dict] = []
    excluded: list[dict] = []
    page_reports: dict[str, dict] = {}
    category_labels = {"classical-guitar": "Classical", "guitar-ensemble": "Guitar Ensemble"}
    category_urls = {"classical-guitar": CLASSROOM_DIRECTORIES["classical"],
                     "guitar-ensemble": CLASSROOM_DIRECTORIES["guitar_ensemble"]}
    for page, url in CLASSROOM_DIRECTORIES.items():
        raw, request = client.get(url)
        parsed = parse_guitarclassroom_page(raw.decode("utf-8", "replace"), url, page)
        page_reports[page] = {
            "directory_url": url, "http_status": request["status"],
            "raw_pdf_link_count": parsed["raw_pdf_link_count"],
            "accepted_occurrence_count": sum(item["disposition"] == "accepted" for item in parsed["occurrences"]),
            "excluded_occurrence_count": len(parsed["excluded"]),
        }
        all_occurrences.extend(item for item in parsed["occurrences"] if item.get("disposition") == "accepted")
        excluded.extend(parsed["excluded"])
        for row in parsed["works"]:
            old = combined.get(row["id"])
            if old is None:
                combined[row["id"]] = row
                continue
            if old["metadata"]["native_record_locator"] != row["metadata"]["native_record_locator"]:
                raise ValueError("The Guitar Classroom identity collision has different source PDF locators")
            old["category_ids"] = sorted(set(old["category_ids"]) | set(row["category_ids"]))
            if row["metadata"]["source_title"] != old["metadata"]["source_title"]:
                old["metadata"].setdefault("title_variants", []).append({
                    "page": page, "source_title": row["metadata"]["source_title"],
                })
            old["metadata"].setdefault("source_occurrences", []).extend(row["metadata"].get("source_occurrences", []))
            for a in row["assets"]:
                if a["source_url"] not in {item["source_url"] for item in old["assets"]}:
                    old["assets"].append(a)

    works = sorted(combined.values(), key=lambda row: row["id"])
    categories = _categories(CLASSROOM_ID, category_labels, category_urls)
    inventory = {
        "schema_version": 1, "source_id": CLASSROOM_ID, "scope_version": SCOPE_VERSION,
        "parser_version": PARSER_VERSION, "frozen_at": client.state["started_at"],
        "directories": page_reports, "accepted": all_occurrences,
        "excluded": excluded, "pending": [],
        "identity_basis": "native PDF filename slug; exact file path is guarded privately; same title on different filenames remains separate",
        "boundary": "Only the current Classical and Guitar Ensemble directories. Explicit guitar-plus-strings works in the ensemble directory are retained with unknown player counts; the pricing/licensing PDF is excluded from score records. Other site navigation (beginner guitar, rock/piano, chamber, stream, paid items) is outside scope.",
        "asset_policy": CLASSROOM_USE,
    }
    return _write_discovery(
        root, CLASSROOM_ID, "The Guitar Classroom", CLASSROOM_HOME,
        "Discovery phase: metadata only for current Classical and Guitar Ensemble directory links; native score locators define record identities, with role-labelled score/part/TAB PDFs grouped as assets of one work edition. Explicit guitar-plus-strings works are retained with unknown player counts. The policy PDF is excluded. Separate personal/educational offline download and printing are permitted; public reposting or distribution is prohibited.",
        categories, works,
        {"directories": page_reports, "source_link_count": sum(item["raw_pdf_link_count"] for item in page_reports.values()),
         "unique_native_locator_count": sum(item["raw_pdf_link_count"] for item in page_reports.values()),
         "excluded_reason_counts": {"non_score_policy_reference": len(excluded)}}, inventory,
    )
