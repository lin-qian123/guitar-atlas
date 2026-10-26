"""CSUN IGRA guitar-score discovery over the institution's CONTENTdm JSON API.

This adapter freezes a keyword-discovered candidate scope, then checks each
native item record for an explicit guitar declaration and its own public-domain
rights note. It never downloads score bytes. Raw API responses, review outcomes,
and excluded/pending identities are kept under the Git-ignored sources/csun/.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import re
import shutil
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

_SCRIPTS_DIR = str(Path(__file__).resolve().parents[1])
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from source_adapters.additional import DiscoveryClient, atomic_json, category, work

SOURCE_ID = "csun"
BASE = "https://digital-collections.csun.edu"
COLLECTION_ALIAS = "IGRA-scores"
COLLECTION_PAGE = "https://digital-library.csun.edu/IGRA-scores"
COLLECTION_API = f"{BASE}/digital/api/collections/{COLLECTION_ALIAS}"
SEARCH_TEMPLATE = f"{BASE}/digital/api/search/collection/{COLLECTION_ALIAS}/searchterm/guitar/page/{{page}}"
DETAIL_TEMPLATE = f"{BASE}/digital/api/singleitem/collection/{COLLECTION_ALIAS}/id/{{native_id}}"
FULL_ITEM_METADATA_TEMPLATE = f"{BASE}/digital/api/singleitem/collection/{COLLECTION_ALIAS}/id/{{native_id}}"
ITEM_TEMPLATE = f"{BASE}/digital/collection/{COLLECTION_ALIAS}/id/{{native_id}}"
DMQUERY_BASE = f"{BASE}/digital/bl/dmwebservices/index.php?q="
DMQUERY_FIELDS = ("title", "series", "creato", "arrang", "rights")
DMQUERY_PAGE_SIZE = 1024
HOSTS = {"digital-collections.csun.edu"}
HUMAN_HOSTS = {"digital-library.csun.edu", "digital-collections.csun.edu"}
REQUEST_DELAY = 1.0  # robots.txt for this host publishes Crawl-Delay: 1.
SCOPE_VERSION = "2026-10-26.2"
FULL_METADATA_SCOPE_VERSION = "2026-10-26.3"
SCHEMA_VERSION = 1

EXPLICIT_VOICE_ROLE_RE = re.compile(
    r"\b(?:vocal\s+score|choir\s+score|chorus\s+score)\b|"
    r"\b(?:for|with|accompanied\s+by)\s+(?:the\s+)?(?:voice|voices|soprano|contralto|alto|tenor|baritone|"
    r"bass\s+voice|choir|chorus)\b|"
    r"\b(?:voice|voices|soprano|contralto|alto|tenor|baritone|bass\s+voice|choir|chorus)\s+"
    r"(?:and|with)\s+(?:the\s+)?guitar\b|\bguitar\s+(?:and|with)\s+"
    r"(?:the\s+)?(?:voice|voices|soprano|contralto|alto|tenor|baritone|bass\s+voice|choir)\b|"
    r"\bsongs?\s+(?:with|for)\s+(?:the\s+)?guitar\s+(?:acc\.?|accompaniment)\b", re.I)
DISALLOWED_SCOPE_RE = re.compile(
    r"\b(?:electric|bass|steel|hawaiian|slide)\s+(?:classical\s+)?guitars?\b|"
    r"\b(?:electric|bass|steel|hawaiian|slide)\s+guitar\b|"
    r"\b(?:large|full|grand|symphony|symphonic)\s+orchestra\b", re.I)
GUITAR_DECLARATION_RE = re.compile(
    r"\b(?:for|pour|für|fur|para|per)\s+(?:(?:the|a|an|one|two|three|four|[1-9])\s+)?"
    r"(?:classical\s+)?guitars?\b|\bguitars?\s+(?:solo|solos|alone)\b|"
    r"\bsolo\s+(?:for|on)\s+(?:the\s+)?guitar\b", re.I)
INSTRUMENT_ALIASES = {
    "guitar": "guitar", "guitars": "guitar", "classical guitar": "guitar",
    "violin": "violin", "violins": "violin", "viola": "viola", "violas": "viola",
    "cello": "cello", "cellos": "cello", "violoncello": "cello", "double bass": "double bass",
    "flute": "flute", "flutes": "flute", "recorder": "recorder", "clarinet": "clarinet",
    "oboe": "oboe", "bassoon": "bassoon", "saxophone": "saxophone",
    "trumpet": "trumpet", "horn": "horn", "trombone": "trombone", "tuba": "tuba",
    "euphonium": "euphonium", "cornet": "cornet", "piano": "piano", "organ": "organ",
    "harpsichord": "harpsichord", "accordion": "accordion", "bandoneon": "bandoneon",
    "mandolin": "mandolin", "lute": "lute", "vihuela": "vihuela", "harp": "harp",
    "marimba": "marimba", "vibraphone": "vibraphone", "percussion": "percussion",
    "xylophone": "xylophone", "glockenspiel": "glockenspiel", "timpani": "timpani",
}
INSTRUMENT_TOKEN_RE = re.compile(r"\b(?:double\s+bass|violoncello|harpsichord|bandoneon|"
    r"guitars?|violins?|violas?|cellos?|viola|violin|cello|flutes?|recorders?|clarinet|"
    r"oboe|bassoon|saxophone|trumpet|horn|trombone|tuba|euphonium|cornet|piano|organ|"
    r"accordion|mandolin|lute|vihuela|harp|marimba|vibraphone|percussion|xylophone|"
    r"glockenspiel|timpani)\b", re.I)
OTHER_ROLE_RE = re.compile(
    r"\b(?:banjo|mandolin|ukulele|ukelele|lute|theorbo|vihuela|violin|viola|cello|"
    r"violoncello|double bass|flute|recorder|clarinet|oboe|bassoon|saxophone|trumpet|"
    r"horn|trombone|tuba|euphonium|cornet|piano|organ|harpsichord|accordion|bandoneon|"
    r"harp|marimba|vibraphone|percussion|xylophone|glockenspiel|timpani)\b", re.I)


def _text(value) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).split())


def _field_map(fields) -> dict[str, list[str]]:
    if not isinstance(fields, list):
        raise ValueError("CSUN item JSON fields must be a list")
    result: dict[str, list[str]] = {}
    for row in fields:
        if not isinstance(row, dict) or not isinstance(row.get("key"), str):
            raise ValueError("CSUN item JSON contains a malformed field")
        result.setdefault(row["key"], []).append(_text(row.get("value")))
    return result


def _first(fields: dict[str, list[str]], key: str) -> str:
    return next((value for value in fields.get(key, []) if value), "")


def resolve_download_uri(download_uri: str, native_id: str) -> tuple[str, dict]:
    """Resolve only the exact CONTENTdm `/digital`-mounted item download route.

    CSUN singleitem JSON reports `/api/collection/...`, relative to the site's
    `/digital` mount. Add that mount only for the exact same-item route. Already
    mounted URLs remain unchanged; all other paths and hosts fail closed.
    """
    raw = _text(download_uri)
    if not raw:
        raise ValueError("CSUN item has no download URI")
    parsed = urlsplit(raw)
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ValueError("CSUN download URI has unexpected query, fragment, or credentials")
    if parsed.scheme or parsed.netloc:
        if parsed.scheme != "https" or parsed.hostname not in HOSTS or parsed.port not in (None, 443):
            raise ValueError("CSUN download URI escaped the approved official host")
        origin = f"https://{parsed.netloc}"
    else:
        if raw.startswith("//") or not raw.startswith("/"):
            raise ValueError("CSUN relative download URI must be a root-relative path")
        origin = BASE
    unmounted = f"/api/collection/{COLLECTION_ALIAS}/id/{native_id}/download"
    mounted = f"/digital/api/collection/{COLLECTION_ALIAS}/id/{native_id}/download"
    if parsed.path == unmounted:
        path = "/digital" + parsed.path
        applied_mount = True
    elif parsed.path == mounted:
        path = parsed.path
        applied_mount = False
    else:
        raise ValueError("CSUN download URI did not match the exact native-item route")
    corrected = urlunsplit(("https", urlsplit(origin).netloc, path, "", ""))
    return corrected, {
        "raw_download_uri": raw,
        "native_item_id": str(native_id),
        "applied_digital_mount": applied_mount,
        "corrected_url": corrected,
        "route_rule": "only exact /api/collection/<alias>/id/<same-native-id>/download receives /digital prefix",
    }


def _instrumentation_declaration(title: str, series: str) -> tuple[str, str] | None:
    """Extract only explicit source phrases; keep unsupported vocab pending."""
    texts = [part for part in (title, series) if part]
    text = " ".join(texts)
    if not re.search(r"\bguitars?\b", text, re.I):
        return None
    # A clearly stated guitar-only phrase may identify relatedness while
    # leaving the number of performers unspecified.
    if GUITAR_DECLARATION_RE.search(text) and not re.search(r"\b(?:and|with|&|,|or)\b", text, re.I):
        if re.search(r"\bguitars?\s+solos?\b|\bsolos?\b.{0,35}\b(?:for|on)\s+(?:the\s+)?guitar\b|\bsolo\s+(?:for|on)\s+(?:the\s+)?guitar\b", text, re.I):
            return "solo guitar", GUITAR_DECLARATION_RE.search(text).group(0)
        # Counts must describe an explicit ensemble, not a number of pieces.
        # E.g. "Twenty-four guitar solos" means 24 solos, not four players.
        count = re.search(r"\bfor\s+(two|2)\s+guitars?\b|(?<![\w-])(2)\s+guitars\b", text, re.I)
        if count:
            return "2 guitars", count.group(0)
        count = re.search(r"\bfor\s+(three|3)\s+guitars?\b|(?<![\w-])(3)\s+guitars\b", text, re.I)
        if count:
            return "3 guitars", count.group(0)
        count = re.search(r"\bfor\s+(four|4)\s+guitars?\b|(?<![\w-])(4)\s+guitars\b", text, re.I)
        if count:
            return "4 guitars", count.group(0)
        return "guitar", GUITAR_DECLARATION_RE.search(text).group(0)

    # Accept a small-ensemble declaration only where the source phrase begins
    # as an instrumental scoring and every extracted role belongs to the
    # project's shared family vocabulary. "or" choices remain ambiguous.
    scoring = next((match for part in texts
                    if (match := re.search(r"\bfor\s+(?:the\s+)?([^.;:()]+)", part, re.I))), None)
    if not scoring:
        return None
    phrase = scoring.group(1).strip()
    if re.search(r"\bor\b|\b(?:electric|bass\s+guitar|steel|hawaiian|slide)\b", phrase, re.I):
        return None
    tokens = [INSTRUMENT_ALIASES[match.group(0).casefold()] for match in INSTRUMENT_TOKEN_RE.finditer(phrase)]
    remainder = INSTRUMENT_TOKEN_RE.sub(" ", phrase)
    remainder = re.sub(r"\b(?:and|with|the|a|an|one|two|three|four|[1-9]|classical|solo|guitar)\b|[,&/-]", " ", remainder, flags=re.I)
    if "guitar" not in tokens or not tokens or remainder.strip():
        return None
    if len(tokens) == 1:
        return "guitar", phrase
    return ", ".join(dict.fromkeys(tokens)), phrase


def parse_search_page(payload: dict, *, expected_total: int | None = None) -> tuple[int, list[dict]]:
    """Validate the current CONTENTdm search shape and preserve native IDs."""
    if not isinstance(payload, dict) or not isinstance(payload.get("totalResults"), int):
        raise ValueError("CSUN search JSON lacks integer totalResults")
    total = payload["totalResults"]
    if expected_total is not None and total != expected_total:
        raise ValueError("CSUN keyword total changed within the frozen search")
    rows = payload.get("items")
    if not isinstance(rows, list) or not rows:
        raise ValueError("CSUN search JSON has no item list")
    if len(rows) > 10:
        raise ValueError("CSUN search page exceeded the observed 10-item page size")
    result = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("CSUN search result is not an object")
        native = str(row.get("itemId") or "")
        if not native.isdigit() or native in seen:
            raise ValueError("CSUN search result has invalid or repeated native itemId")
        if row.get("collectionAlias") != COLLECTION_ALIAS:
            raise ValueError("CSUN search result escaped the frozen collection")
        if str(row.get("filetype", "")).casefold() != "pdf":
            raise ValueError("CSUN guitar keyword result is not a PDF item")
        seen.add(native)
        result.append({
            "native_item_id": native,
            "title": _text(row.get("title")),
            "source_url": ITEM_TEMPLATE.format(native_id=native),
            "api_url": DETAIL_TEMPLATE.format(native_id=native),
            "collection_alias": row["collectionAlias"],
            "filetype": row["filetype"],
            "listing_metadata": row.get("metadataFields", []),
        })
    return total, result


def dmquery_url(start: int) -> str:
    """Build the OCLC-documented dmQuery request with bounded 1024-row pages."""
    if not isinstance(start, int) or start < 1:
        raise ValueError("CSUN dmQuery start index must be a positive integer")
    fields = "!".join(DMQUERY_FIELDS)
    query = (f"dmQuery/{COLLECTION_ALIAS}/CISOSEARCHALL^guitar^all^and/{fields}/nosort/"
             f"{DMQUERY_PAGE_SIZE}/{start}/1/0/0/0/0/0/json")
    return DMQUERY_BASE + query


def parse_dmquery_page(payload: dict, *, expected_total: int | None = None,
                        expected_start: int | None = None) -> tuple[int, int, list[dict]]:
    """Parse OCLC's documented pager/records response and retain pointer 0."""
    pager = payload.get("pager") if isinstance(payload, dict) else None
    rows = payload.get("records") if isinstance(payload, dict) else None
    if not isinstance(pager, dict) or not isinstance(rows, list):
        raise ValueError("CSUN dmQuery JSON lacks pager or records")
    try:
        total, start = int(pager["total"]), int(pager["start"])
        maxrecs = int(pager["maxrecs"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("CSUN dmQuery pager values are malformed") from exc
    if expected_total is not None and total != expected_total:
        raise ValueError("CSUN dmQuery total changed within this frozen query")
    if expected_start is not None and start != expected_start:
        raise ValueError("CSUN dmQuery response start does not match requested offset")
    if maxrecs != DMQUERY_PAGE_SIZE or len(rows) > DMQUERY_PAGE_SIZE:
        raise ValueError("CSUN dmQuery did not honor the documented maxrecs request")
    result, seen = [], set()
    for row in rows:
        if not isinstance(row, dict) or row.get("collection") != "/" + COLLECTION_ALIAS:
            raise ValueError("CSUN dmQuery returned a malformed or out-of-scope record")
        pointer = row.get("pointer")
        if isinstance(pointer, bool) or not isinstance(pointer, int) or pointer < 0:
            raise ValueError("CSUN dmQuery returned an invalid native pointer")
        native = str(pointer)
        if native in seen:
            raise ValueError("CSUN dmQuery repeated a native pointer within a page")
        seen.add(native)
        if any(key not in row for key in ("filetype", "find")):
            raise ValueError("CSUN dmQuery item is missing format or native filename")
        result.append({
            "native_item_id": native,
            "title": _text(row.get("title")),
            "source_url": ITEM_TEMPLATE.format(native_id=native),
            "api_url": DETAIL_TEMPLATE.format(native_id=native),
            "collection_alias": COLLECTION_ALIAS,
            "filetype": str(row.get("filetype", "")),
            "filename": _text(row.get("find")),
            "listing_metadata": row,
        })
    return total, start, result


def dmquery_record_as_detail(candidate: dict) -> dict:
    """Adapt a full item row from dmQuery to the item's source-field shape."""
    row = candidate["listing_metadata"]
    fields = [{"key": key, "label": key, "value": row.get(key, "")} for key in DMQUERY_FIELDS]
    native = candidate["native_item_id"]
    return {
        "contentType": "application/pdf" if candidate["filetype"].casefold() == "pdf" else "",
        "filename": candidate["filename"],
        "downloadUri": f"/digital/api/collection/{COLLECTION_ALIAS}/id/{native}/download",
        "fields": fields,
    }


def classify_item(detail: dict, native_id: str | None = None) -> dict:
    """Return a guarded scope/rights decision without reading the PDF itself."""
    if not isinstance(detail, dict) or detail.get("contentType") != "application/pdf":
        return {"outcome": "pending", "reason": "item detail does not affirm application/pdf"}
    fields = _field_map(detail.get("fields"))
    title = _first(fields, "title")
    series = _first(fields, "series")
    rights = _first(fields, "rights")
    scope_fields = ("title", "series", "table", "descri", "genre", "type", "docume", "notes")
    scope_text = " ".join(value for key in scope_fields for value in fields.get(key, []) if value)
    if EXPLICIT_VOICE_ROLE_RE.search(scope_text):
        return {"outcome": "excluded", "reason": "explicit voice/instrument role or vocal-score declaration in source fields",
                "instrumentation_evidence": scope_text}
    if DISALLOWED_SCOPE_RE.search(scope_text):
        return {"outcome": "excluded", "reason": "explicit electric/bass/steel/slide guitar or large orchestra in source title/series",
                "instrumentation_evidence": scope_text}
    if re.search(r"\borchestra\b", scope_text, re.I):
        return {"outcome": "pending", "reason": "orchestra size and guitar role are not explicit in the source fields",
                "instrumentation_evidence": scope_text, "rights_note": rights}
    if (re.search(r"\bbass\b", scope_text, re.I)
            and not re.search(r"\b(?:bass guitar|double bass|contrabass|bass voice)\b", scope_text, re.I)):
        return {"outcome": "pending", "reason": "bare bass label has unresolved instrument/role meaning",
                "instrumentation_evidence": scope_text, "rights_note": rights}
    if re.search(r"\bor\b", scope_text, re.I) and re.search(r"\bguitars?\b", scope_text, re.I) and OTHER_ROLE_RE.search(scope_text):
        return {"outcome": "pending", "reason": "guitar is one of multiple alternative source instruments",
                "instrumentation_evidence": scope_text, "rights_note": rights}
    if (re.search(r"\b(?:banjo|mandolin|ukulele|ukelele|lute|theorbo|vihuela)\b", title, re.I)
            and not re.search(r"\bguitars?\b", title, re.I)):
        return {"outcome": "excluded", "reason": "explicit non-guitar plucked-instrument title",
                "instrumentation_evidence": title, "rights_note": rights}
    declaration = _instrumentation_declaration(title, series)
    if declaration is None:
        for key in ("table", "descri", "genre", "type", "docume", "notes"):
            declaration = _instrumentation_declaration(" ".join(fields.get(key, [])), "")
            if declaration:
                break
    if declaration is None:
        if re.search(r"\b(?:banjo|mandolin|ukulele|ukelele|lute|theorbo|vihuela)\b", scope_text, re.I) and not re.search(r"\bguitars?\b", scope_text, re.I):
            return {"outcome": "excluded", "reason": "explicit non-guitar plucked-instrument evidence",
                    "instrumentation_evidence": scope_text, "rights_note": rights}
        if re.search(r"\bguitar(?:s)?(?:\s+music)?\b", scope_text, re.I):
            declaration = ("guitar", next((value for key in scope_fields for value in fields.get(key, [])
                                              if re.search(r"\bguitar(?:s)?(?:\s+music)?\b", value, re.I)), "guitar"))
    if declaration is None:
        return {"outcome": "pending", "reason": "no source metadata field currently establishes guitar relevance and scoring",
                "instrumentation_evidence": scope_text, "rights_note": rights}

    if re.fullmatch(r"public\s+domain\.?", rights, re.I) is None:
        return {"outcome": "pending", "reason": "item rights note is not an exact public-domain declaration",
                "instrumentation_evidence": declaration[1], "normalized_instrumentation": declaration[0], "rights_note": rights}
    filename = _text(detail.get("filename"))
    download_uri = _text(detail.get("downloadUri"))
    if not filename.lower().endswith(".pdf") or not download_uri:
        return {"outcome": "pending", "reason": "PDF filename or official download URI is missing",
                "instrumentation_evidence": declaration[1], "normalized_instrumentation": declaration[0], "rights_note": rights}
    if native_id is None:
        uri_parts = urlsplit(download_uri)
        if (uri_parts.scheme or uri_parts.netloc) and (
                uri_parts.scheme != "https" or uri_parts.hostname not in HOSTS or uri_parts.port not in (None, 443)):
            raise ValueError("CSUN download URI escaped the approved official host")
        path = uri_parts.path
        route = re.fullmatch(r"/(?:digital/)?api/collection/IGRA-scores/id/([0-9]+)/download", path)
        if not route:
            raise ValueError("CSUN download URI lacks a native item ID")
        native_id = route.group(1)
    download_url, url_correction = resolve_download_uri(download_uri, str(native_id))
    return {"outcome": "accepted", "reason": "explicit guitar declaration and item-level Public domain note",
            "instrumentation_evidence": declaration[1], "normalized_instrumentation": declaration[0],
            "rights_note": "Public domain.",
            "filename": filename, "download_url": download_url,
            "raw_download_uri": download_uri, "download_url_correction": url_correction,
            "fields": fields}


def registry_proposal() -> dict:
    return {
        "id": SOURCE_ID,
        "name": "CSUN · IGRA",
        "homepage": COLLECTION_PAGE,
        "allowed_hosts": sorted(HUMAN_HOSTS),
        "adapter": "normalized_catalog",
        "catalog": "sources/csun/catalog.json",
        "family": SOURCE_ID,
        "family_name_zh": "CSUN IGRA 吉他谱",
        "family_name_en": "CSUN IGRA guitar scores",
        "asset_hosts": sorted(HOSTS),
        "metadata_basis": "frozen OCLC-documented dmQuery candidate IDs plus official CONTENTdm singleitem metadata JSON",
        "file_acquisition": "pending PDF only with exact item Public domain rights and source-field evidence of guitar relevance; player count may remain unspecified",
        "page_url_rules": [{"path": r"/digital/collection/IGRA-scores/id/[0-9]+",
                            "human_page": True}],
    }


def _scope_path(path: Path) -> Path:
    return path / "frozen_scope_dmquery.json"


def _scope_policy_path(path: Path) -> Path:
    return path / "scope_policy_dmquery.json"


def _fetch_candidates(client: DiscoveryClient) -> tuple[list[dict], list[dict], int]:
    first_url = dmquery_url(1)
    # Explicitly call allowed before any API read; this captures robots and
    # obeys the site's published Crawl-Delay: 1 using the shared request clock.
    if not client.allowed(first_url):
        raise PermissionError("CSUN robots disallows the official metadata search API")
    robot_status, robot_body = client.robots[BASE]
    delay_values = re.findall(r"(?im)^\s*crawl-delay\s*:\s*([0-9.]+)\s*$", robot_body)
    if robot_status != 200 or not delay_values or any(float(value) != REQUEST_DELAY for value in delay_values):
        raise RuntimeError("CSUN robots status or Crawl-Delay changed; review before discovery")
    atomic_json(client.path / "policy.json", {
        "schema_version": SCHEMA_VERSION, "source_id": SOURCE_ID,
        "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "robots_url": BASE + "/robots.txt", "robots_status": robot_status,
        "robots_sha256": hashlib.sha256(robot_body.encode("utf-8")).hexdigest(),
        "crawl_delay_seconds": REQUEST_DELAY,
        "api_path_allowed": True,
        "disallowed_html_search_path": "/digital/collection/IGRA-scores/search/",
        "api_route_used": "CONTENTdm dmQuery, documented by OCLC",
        "api_documentation": "https://help.oclc.org/Metadata_Services/CONTENTdm_classic_version/Advanced_website_customization/API_Reference/CONTENTdm_classic_version_API/CONTENTdm_classic_version_Server_API_Functions_dmwebservices",
        "pdf_requests_made": 0,
    })
    raw, request = client.get(first_url)
    first = json.loads(raw)
    total, start, first_rows = parse_dmquery_page(first, expected_start=1)
    if start != 1 or len(first_rows) != min(DMQUERY_PAGE_SIZE, total):
        raise ValueError("CSUN dmQuery first page does not match its advertised total/maxrecs")
    page_size = DMQUERY_PAGE_SIZE
    pages_total = math.ceil(total / page_size)
    pages = [{"page": 1, "start": start, "url": first_url, "request": request, "count": len(first_rows)}]
    candidates = list(first_rows)
    for page in range(2, pages_total + 1):
        expected_start = (page - 1) * page_size + 1
        url = dmquery_url(expected_start)
        raw, request = client.get(url)
        payload = json.loads(raw)
        page_total, actual_start, rows = parse_dmquery_page(payload, expected_total=total,
                                                            expected_start=expected_start)
        if page_total != total:
            raise ValueError("CSUN dmQuery total changed while paginating")
        expected_length = page_size if page < pages_total else total - page_size * (pages_total - 1)
        if len(rows) != expected_length:
            raise ValueError(f"CSUN dmQuery page {page} returned {len(rows)} entries; expected {expected_length}")
        pages.append({"page": page, "start": actual_start, "url": url, "request": request, "count": len(rows)})
        candidates.extend(rows)
        if len(candidates) != len({row["native_item_id"] for row in candidates}):
            raise ValueError("CSUN dmQuery pagination repeated a native pointer")
        if page % 10 == 0 or page == pages_total:
            atomic_json(client.path / "listing_progress.json", {
                "schema_version": SCHEMA_VERSION, "source_id": SOURCE_ID,
                "scope_version": SCOPE_VERSION, "pages_checked": page,
                "pages_expected": pages_total, "candidates_seen": len(candidates),
                "upstream_total_results": total,
            })
    if len(candidates) != total:
        raise ValueError("CSUN unique candidate count does not match dmQuery pager.total")
    return candidates, pages, page_size


def _record_route_comparison(client: DiscoveryClient, selected_candidates: list[dict]) -> None:
    """Preserve prior successful API variants and their observed count drift."""
    observations = []
    for url, request in client.state.get("requests", {}).items():
        if "/digital/api/search/" not in url and "/digital/bl/dmwebservices/" not in url:
            continue
        cache_path = client.path / request.get("cache", "")
        if request.get("status") != 200 or not cache_path.exists():
            continue
        try:
            payload = json.loads(cache_path.read_bytes())
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        rows = payload.get("records") if isinstance(payload, dict) else None
        if isinstance(rows, list):
            pager = payload.get("pager", {})
            ids = [str(row.get("pointer")) for row in rows if isinstance(row, dict)]
            observations.append({"url": url, "status": 200, "sha256": request["sha256"],
                "cache": request["cache"], "reported_total": pager.get("total"),
                "start": pager.get("start"), "maxrecs": pager.get("maxrecs"),
                "returned_records": len(rows), "native_ids": ids})
        elif isinstance(payload, dict) and isinstance(payload.get("items"), list):
            ids = [str(row.get("itemId")) for row in payload["items"] if isinstance(row, dict)]
            observations.append({"url": url, "status": 200, "sha256": request["sha256"],
                "cache": request["cache"], "reported_total": payload.get("totalResults"),
                "returned_records": len(payload["items"]), "native_ids": ids})
    dm_pages = [row for row in observations if "/digital/bl/dmwebservices/" in row["url"]
                and row.get("maxrecs") == str(DMQUERY_PAGE_SIZE)
                and f"/{'!'.join(DMQUERY_FIELDS)}/nosort/{DMQUERY_PAGE_SIZE}/" in row["url"]]
    dm_ids = {native for page in dm_pages for native in page["native_ids"]}
    zero = next((row for row in selected_candidates if row["native_item_id"] == "0"), None)
    item_api_url = DETAIL_TEMPLATE.format(native_id="0")
    item_page_url = ITEM_TEMPLATE.format(native_id="0")
    identity_evidence = {"native_item_id": "0", "in_frozen_candidate_scope": zero is not None}
    if zero:
        detail_state = client.state.get("requests", {}).get(item_api_url, {})
        page_state = client.state.get("requests", {}).get(item_page_url, {})
        if detail_state.get("status") != 200 or page_state.get("status") != 200:
            raise ValueError("CSUN pointer 0 did not resolve through both official detail and human routes")
        detail = json.loads((client.path / detail_state["cache"]).read_bytes())
        api_fields = _field_map(detail.get("fields"))
        differences = {key: {"dmquery": zero["listing_metadata"].get(key),
                             "singleitem": _first(api_fields, key)}
                      for key in DMQUERY_FIELDS
                      if _text(zero["listing_metadata"].get(key)) != _first(api_fields, key)}
        if differences:
            raise ValueError("CSUN selected dmQuery fields disagree with the singleitem sample: " + str(differences))
        identity_evidence.update({"singleitem_api_url": item_api_url, "singleitem_status": 200,
            "singleitem_sha256": detail_state["sha256"], "human_page_url": item_page_url,
            "human_page_status": 200, "human_page_sha256": page_state["sha256"],
            "field_equality": {key: True for key in DMQUERY_FIELDS}})
    atomic_json(client.path / "native_identity_validation.json", identity_evidence)
    atomic_json(client.path / "api_route_comparison.json", {
        "schema_version": SCHEMA_VERSION, "source_id": SOURCE_ID,
        "scope_version": SCOPE_VERSION,
        "selected_query": "OCLC-documented dmQuery with five selected candidate fields and maxrecs=1024",
        "selected_query_candidate_count": len(selected_candidates),
        "selected_query_unique_ids": len({row["native_item_id"] for row in selected_candidates}),
        "selected_query_native_ids_sha256": hashlib.sha256("\n".join(
            row["native_item_id"] for row in selected_candidates).encode()).hexdigest(),
        "selected_query_page_count": sum(1 for row in dm_pages if row["returned_records"] > 0),
        "selected_query_complete_id_union_count": len(dm_ids),
        "observations": observations,
        "limits": ["The legacy website search API returned different totals across page numbers.",
                   "OCLC dmQuery totals also differed for distinct query field/maxrecs variants.",
                   "This frozen scope is only the exact two-page, five-field dmQuery result set captured here.",
                   "No source-wide collection coverage is claimed; raw responses are preserved at each cache path."],
    })


def _category_for(series: str, categories: dict[str, dict]) -> str:
    name = series or "Series not specified"
    identity = "series:" + hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]
    categories.setdefault(identity, category(identity, name, COLLECTION_PAGE))
    return identity


def _normalize_work(candidate: dict, detail: dict, decision: dict, categories: dict) -> dict:
    fields = decision["fields"]
    native = candidate["native_item_id"]
    title = _first(fields, "title") or candidate["title"] or "[Untitled source score]"
    composer = _first(fields, "creato")
    series = _first(fields, "series")
    metadata = {
        "instrumentation": decision["normalized_instrumentation"],
        "license": "Public domain",
        "arranger": _first(fields, "arrang"),
        "publisher": _first(fields, "publis"),
        "publication_date": _first(fields, "date"),
        "catalogue_number": _first(fields, "source"),
        "period": _first(fields, "genre"),
        "language": _first(fields, "langua"),
        "institution": "California State University Northridge, University Library, International Guitar Research Archives",
        "source_edition": series,
        "collection": "IGRA Guitar Scores",
    }
    metadata = {key: value for key, value in metadata.items() if value}
    return work(
        SOURCE_ID, native, title, composer, candidate["source_url"],
        [_category_for(series, categories)], formats=["PDF"],
        assets=[{
            "source_url": decision["download_url"], "format": "PDF",
            "filename": decision["filename"], "status": "pending",
            "license": "Public domain", "license_url": candidate["source_url"],
            "acquisition_permission": "public_domain_item_rights_note",
            "acquisition_basis": "The source item's own Rights Note is exactly Public domain.",
            "upstream_checksum_available": False,
        }], metadata=metadata, instrumentation_status="source_declared")


def correct_catalog_download_endpoints(root: Path) -> dict:
    """Correct only CSUN's observed missing `/digital` mount; preserve old failures."""
    root = Path(root).resolve()
    directory = root / "sources" / SOURCE_ID
    catalog_path, reviews_path = directory / "catalog.json", directory / "full_item_reviews.json"
    log_path, receipt_path = directory / "acquisition_log.jsonl", directory / "endpoint_correction.json"
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt.get("state") == "applied":
            return {"state": "applied", "corrected_asset_count": receipt["corrected_asset_count"],
                    "prior_failed_asset_count": receipt["prior_failed_asset_count"],
                    "acquisition_log_entries_preserved": receipt["acquisition_log_entry_count"],
                    "idempotent_reuse": True}
        if receipt.get("state") != "prepared":
            raise ValueError("CSUN endpoint correction receipt has an unknown state")
    else:
        receipt = None
    original_catalog_bytes = catalog_path.read_bytes()
    catalog = json.loads(original_catalog_bytes)
    reviews = json.loads(reviews_path.read_text(encoding="utf-8"))
    if catalog.get("source_id") != SOURCE_ID:
        raise ValueError("CSUN endpoint correction received another source catalog")
    if receipt is None:
        log_rows = ([json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
                    if log_path.exists() else [])
        logs_by_id: dict[str, list[dict]] = {}
        for row in log_rows:
            if row.get("source_id") == SOURCE_ID:
                logs_by_id.setdefault(row.get("record_id", ""), []).append(row)
        entries = []
        for record in catalog["works"]:
            native = record["id"].removeprefix(SOURCE_ID + ":")
            if not native.isdigit() or native not in reviews or len(record.get("assets", [])) != 1:
                raise ValueError(f"CSUN catalog/native metadata relationship is incomplete: {record.get('id')}")
            asset = record["assets"][0]
            review = reviews[native]
            raw_uri = review["detail"].get("downloadUri", "")
            corrected_url, route = resolve_download_uri(raw_uri, native)
            prior_url = asset.get("source_url", "")
            parsed_raw = urlsplit(raw_uri)
            old_expected = BASE + parsed_raw.path if not parsed_raw.scheme and parsed_raw.path.startswith("/") else raw_uri
            if prior_url != old_expected or asset.get("filename") != review["detail"].get("filename"):
                raise ValueError(f"CSUN old endpoint/filename does not match frozen item metadata: {record['id']}")
            matching_logs = [row for row in logs_by_id.get(record["id"], [])
                             if row.get("event") == "failed" and row.get("source_url") == prior_url]
            entries.append({"record_id": record["id"], "native_item_id": native,
                "filename": asset["filename"], "item_metadata_sha256": review["item_metadata_sha256"],
                "raw_download_uri": raw_uri, "previous_source_url": prior_url,
                "corrected_source_url": corrected_url, "route_resolution": route,
                "previous_asset": dict(asset), "previous_failed_log_entries": matching_logs})
        receipt = {"schema_version": 1, "source_id": SOURCE_ID, "state": "prepared",
            "correction_id": "csun-digital-mount-2026-10-26-1",
            "catalog_before_sha256": hashlib.sha256(original_catalog_bytes).hexdigest(),
            "acquisition_log_sha256": hashlib.sha256(log_path.read_bytes()).hexdigest() if log_path.exists() else None,
            "correction_rule": "Add /digital only to exact /api/collection/IGRA-scores/id/<same-native-id>/download; preserve already mounted /digital/api paths.",
            "pdf_requests_made": 0, "corrections": entries}
        atomic_json(receipt_path, receipt)

    records = {row["id"]: row for row in catalog["works"]}
    reviews_updated = False
    for entry in receipt["corrections"]:
        record = records.get(entry["record_id"])
        if record is None or len(record.get("assets", [])) != 1:
            raise ValueError(f"CSUN correction receipt no longer matches catalog: {entry['record_id']}")
        asset = record["assets"][0]
        if asset.get("source_url") == entry["previous_source_url"]:
            if asset != entry["previous_asset"]:
                raise ValueError(f"CSUN asset state drifted since endpoint correction was prepared: {entry['record_id']}")
            asset["source_url"] = entry["corrected_source_url"]
            asset["status"] = "pending"
            asset["prior_error_url"] = entry["previous_source_url"]
            asset["endpoint_correction_receipt"] = "sources/csun/endpoint_correction.json"
            if entry["previous_asset"].get("status") == "failed":
                asset["prior_error"] = entry["previous_asset"].get("last_error")
                asset["prior_attempts"] = entry["previous_asset"].get("attempts")
                asset["prior_attempted_at"] = entry["previous_asset"].get("attempted_at")
            for key in ("last_error", "attempts", "attempted_at"):
                asset.pop(key, None)
        elif asset.get("source_url") != entry["corrected_source_url"] or asset.get("endpoint_correction_receipt") != "sources/csun/endpoint_correction.json":
            raise ValueError(f"CSUN asset URL is not guarded by the correction receipt: {entry['record_id']}")
        decision = reviews[entry["native_item_id"]].get("decision", {})
        if decision.get("outcome") == "accepted":
            decision["prior_download_url"] = entry["previous_source_url"]
            decision["download_url"] = entry["corrected_source_url"]
            decision["raw_download_uri"] = entry["raw_download_uri"]
            decision["download_url_correction"] = entry["route_resolution"]
            decision["endpoint_correction_receipt"] = "sources/csun/endpoint_correction.json"
            reviews_updated = True

    failed_count = sum(row["previous_asset"].get("status") == "failed" for row in receipt["corrections"])
    log_count = sum(len(row.get("previous_failed_log_entries", [])) for row in receipt["corrections"])
    catalog.setdefault("summary", {})["endpoint_correction"] = {
        "correction_id": receipt["correction_id"], "corrected_asset_count": len(receipt["corrections"]),
        "assets_returned_to_pending": len(receipt["corrections"]), "prior_failed_asset_count": failed_count,
        "acquisition_log_entries_preserved": log_count, "pdf_requests_made_by_correction": 0,
    }
    atomic_json(catalog_path, catalog)
    if reviews_updated:
        atomic_json(reviews_path, reviews)
    receipt.update({"state": "applied", "corrected_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "catalog_after_sha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
        "corrected_asset_count": len(receipt["corrections"]), "prior_failed_asset_count": failed_count,
        "acquisition_log_entry_count": log_count, "acquisition_log_preserved_without_rewrite": True})
    atomic_json(receipt_path, receipt)
    return {"state": "applied", "corrected_asset_count": len(receipt["corrections"]),
            "prior_failed_asset_count": failed_count, "acquisition_log_entries_preserved": log_count,
            "idempotent_reuse": False}


def _identity_field_matches(expected, actual) -> bool:
    expected, actual = _text(expected), _text(actual)
    if expected == actual:
        return True
    # OCLC documents a 100-byte ceiling for each dmQuery field. Permit only
    # an exact prefix when the selected-field query reached that ceiling.
    return len(expected.encode("utf-8")) >= 100 and actual.startswith(expected)


def fetch_full_item_metadata(root: Path, max_records: int | None = None) -> dict:
    """Fetch full singleitem JSON for every ID in the frozen candidate set.

    The DiscoveryClient cache makes this resumable and enforces robots plus the
    source's one-second request clock. Any access refusal is terminal.
    """
    root = Path(root).resolve()
    client = DiscoveryClient(root, SOURCE_ID, HOSTS, delay=REQUEST_DELAY)
    discovery = json.loads((client.path / "discovery.json").read_text(encoding="utf-8"))
    baseline = json.loads((client.path / "item_reviews.json").read_text(encoding="utf-8"))
    candidates = discovery["candidates"]
    by_id = {row["native_item_id"]: row for row in candidates}
    if len(by_id) != len(candidates):
        raise ValueError("CSUN frozen candidate list contains duplicate native IDs")
    full_path = client.path / "full_item_reviews.json"
    reviews = json.loads(full_path.read_text(encoding="utf-8")) if full_path.exists() else {}
    progress_path = client.path / "full_item_metadata_progress.json"
    prior_progress = json.loads(progress_path.read_text(encoding="utf-8")) if progress_path.exists() else {}
    if prior_progress.get("access_block"):
        return {"checked": len(reviews), "target": len(by_id), "complete": False,
                "blocked": prior_progress["access_block"], "stopped_without_retry": True}
    target_ids = set(by_id)
    if set(reviews) - target_ids:
        raise ValueError("CSUN full metadata receipt contains an ID outside the frozen scope")
    for native, review in reviews.items():
        if review.get("identity_validation", {}).get("matches_frozen_candidate"):
            review["decision"] = classify_item(review["detail"], native)
        else:
            review["decision"] = {"outcome": "pending",
                                  "reason": "full item metadata did not match the frozen dmQuery row",
                                  "identity_conflicts": review.get("identity_validation", {})}
    atomic_json(full_path, reviews)
    ordered_ids = [native for native in baseline
                   if baseline[native].get("decision", {}).get("outcome") == "accepted"]
    ordered_ids += [native for native in baseline
                    if baseline[native].get("decision", {}).get("outcome") == "pending"]
    ordered_ids += [native for native in baseline
                    if baseline[native].get("decision", {}).get("outcome") == "excluded"]
    ordered_ids += [native for native in by_id if native not in baseline]
    checked_this_run = 0
    blocked = None
    for native in ordered_ids:
        if native in reviews:
            continue
        candidate = by_id[native]
        url = FULL_ITEM_METADATA_TEMPLATE.format(native_id=native)
        try:
            raw, request = client.get(url)
        except (PermissionError, RuntimeError) as exc:
            status = client.state.get("requests", {}).get(url, {}).get("status")
            if status in {401, 403, 429} or isinstance(exc, PermissionError):
                blocked = f"singleitem request stopped after HTTP {status or 'access refusal'}"
                break
            raise
        try:
            detail = json.loads(raw)
            field_map = _field_map(detail.get("fields"))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"CSUN singleitem response malformed for native ID {native}") from exc
        expected_row = candidate["listing_metadata"]
        comparisons = {key: _identity_field_matches(expected_row.get(key, ""), _first(field_map, key))
                       for key in DMQUERY_FIELDS}
        filename_matches = _text(detail.get("filename")) == _text(candidate.get("filename"))
        identity_ok = all(comparisons.values()) and filename_matches
        decision = classify_item(detail, native)
        if not identity_ok:
            decision = {"outcome": "pending", "reason": "full item metadata did not match the frozen dmQuery row",
                        "identity_conflicts": {**{key: not value for key, value in comparisons.items()},
                                                "filename": not filename_matches}}
        detail_bytes = json.dumps(detail, ensure_ascii=False, sort_keys=True,
                                  separators=(",", ":")).encode("utf-8")
        reviews[native] = {
            "native_item_id": native, "source_url": candidate["source_url"],
            "item_metadata_source": "official singleitem JSON; complete returned item fields",
            "item_metadata_sha256": hashlib.sha256(detail_bytes).hexdigest(),
            "request": request, "identity_validation": {
                "matches_frozen_candidate": identity_ok, "dmquery_fields": comparisons,
                "filename_matches": filename_matches,
            },
            "decision": decision, "detail": detail,
        }
        checked_this_run += 1
        if checked_this_run % 20 == 0:
            atomic_json(full_path, reviews)
            atomic_json(progress_path, {
                "schema_version": 1, "source_id": SOURCE_ID,
                "scope_version": discovery["scope_version"],
                "full_item_metadata_checked": len(reviews),
                "candidate_count": len(target_ids),
                "remaining": len(target_ids) - len(reviews),
            })
            print(f"CSUN IGRA complete item metadata: {len(reviews)}/{len(target_ids)}", flush=True)
        if max_records is not None and checked_this_run >= max_records:
            break
    atomic_json(full_path, reviews)
    complete = len(reviews) == len(target_ids)
    atomic_json(progress_path, {
        "schema_version": 1, "source_id": SOURCE_ID,
        "scope_version": discovery["scope_version"],
        "full_item_metadata_checked": len(reviews),
        "candidate_count": len(target_ids),
        "remaining": len(target_ids) - len(reviews), "complete": complete,
        "access_block": blocked, "full_item_metadata_endpoint_requests": len(reviews),
        "pdf_requests": 0,
    })
    return {"checked": len(reviews), "target": len(target_ids),
            "complete": complete, "blocked": blocked}


def _save_products(client: DiscoveryClient, *, candidates: list[dict], pages: list[dict], page_size: int,
                   reviews: dict[str, dict], detail_complete: bool, blocker: str | None = None,
                   metadata_scope_version: str = SCOPE_VERSION,
                   full_item_metadata_count: int = 0) -> dict:
    categories: dict[str, dict] = {}
    works, excluded, pending = [], [], []
    for candidate in candidates:
        native = candidate["native_item_id"]
        result = reviews.get(native)
        if result is None:
            pending.append({"native_item_id": native, "source_url": candidate["source_url"],
                            "title": candidate["title"], "reason": "item detail not yet checked"})
        elif result["decision"]["outcome"] == "accepted":
            works.append(_normalize_work(candidate, result["detail"], result["decision"], categories))
        else:
            receipt = {"native_item_id": native, "source_url": candidate["source_url"],
                       "title": candidate["title"], "decision": result["decision"]}
            (excluded if result["decision"]["outcome"] == "excluded" else pending).append(receipt)
    total = len(candidates)
    accepted_count = len(works)
    summary = {
        "upstream_keyword_candidates": total,
        "source_candidate_count": total,
        "unique_native_item_ids": len({row["native_item_id"] for row in candidates}),
        "listing_page_count": len(pages),
        "listing_page_size_observed": page_size,
        "detail_checked_count": len(reviews),
        "individual_detail_endpoint_requests": full_item_metadata_count,
        "full_item_metadata_record_count": full_item_metadata_count,
        "selected_field_only_record_count": len(reviews) - full_item_metadata_count,
        "admitted_record_count": accepted_count,
        "excluded_record_count": len(excluded),
        "pending_record_count": len(pending),
        "pending_pdf_asset_count": sum(len(row["assets"]) for row in works),
        "verified_pdf_count": 0,
        "unique_physical_pdf_count": 0,
        "decision_outcomes": dict(Counter(row["decision"]["outcome"] for row in reviews.values())),
    }
    snapshot = {
        "frozen_at": client.state["started_at"],
        "completed_at": client.state.get("updated_at", client.state["started_at"]),
        "discovery_complete": detail_complete,
        "listing_complete": len(candidates) > 0 and len(pages) == math.ceil(len(candidates) / page_size),
        "detail_complete": detail_complete,
        "page_count": len(pages),
        "listing_page_count": len(pages),
        "detail_page_count": full_item_metadata_count,
        "item_metadata_record_count": len(reviews),
        "full_item_metadata_record_count": full_item_metadata_count,
        "full_item_metadata_complete": full_item_metadata_count == total,
        "selected_dmquery_fields_per_response_max": 5,
        "selected_dmquery_field_value_limit_bytes": 100,
        "scope_version": metadata_scope_version,
        "candidate_query_scope_version": SCOPE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "scope": ("Frozen official IGRA-scores guitar-keyword candidate IDs; metadata decisions use complete item JSON and source-field guitar relevance, with exact item-level Public domain required for pending PDF assets. Guitar player count remains unspecified unless explicitly declared."
                  if full_item_metadata_count else
                  "Frozen official IGRA-scores guitar-keyword candidate IDs; selected-field dmQuery rows are preliminary only."),
        "keyword": "guitar",
        "upstream_total_results": total,
        "coverage_boundary": "This is a keyword candidate scope, not all CSUN or IGRA holdings.",
        "instrumentation_review_complete": False,
        "source_metadata_scope_review_complete": detail_complete,
        "score_file_instrumentation_verified": False,
        "fresh_file_integrity_verification": False,
        "metadata_license": "Record metadata is factual attribution and source navigation; no blanket database reuse license asserted.",
        **({"blocked_reason": blocker} if blocker else {}),
    }
    catalog = {"schema_version": SCHEMA_VERSION, "source_id": SOURCE_ID, "snapshot": snapshot,
               "categories": list(categories.values()), "works": sorted(works, key=lambda row: row["id"]),
               "summary": summary}
    atomic_json(client.path / "catalog.json", catalog)
    atomic_json(client.path / "registry_proposal.json", registry_proposal())
    atomic_json(client.path / "excluded_entries.json", {"schema_version": 1, "source_id": SOURCE_ID,
                "scope_version": metadata_scope_version, "entries": excluded})
    atomic_json(client.path / "pending_entries.json", {"schema_version": 1, "source_id": SOURCE_ID,
                "scope_version": metadata_scope_version, "entries": pending})
    atomic_json(client.path / "discovery_report.json", {"schema_version": 1, "source_id": SOURCE_ID,
                "snapshot": snapshot, "summary": summary,
                "limits": ["Keyword results are candidates, not accepted score totals.",
                           "No PDF bytes were requested or verified.",
                           "Only exact per-item Public domain notes make PDF assets pending.",
                           "Unknown or mixed instrumentation remains excluded or pending."]})
    return catalog


def finalize_full_metadata_catalog(root: Path) -> dict:
    """Publish a normalized catalog only after every frozen candidate has full JSON."""
    root = Path(root).resolve()
    client = DiscoveryClient(root, SOURCE_ID, HOSTS, delay=REQUEST_DELAY)
    directory = client.path
    correction_path = directory / "endpoint_correction.json"
    current_catalog_path = directory / "catalog.json"
    if correction_path.exists() and current_catalog_path.exists():
        correction = json.loads(correction_path.read_text(encoding="utf-8"))
        if correction.get("state") == "applied":
            return json.loads(current_catalog_path.read_text(encoding="utf-8"))
    discovery = json.loads((directory / "discovery.json").read_text(encoding="utf-8"))
    full_path = directory / "full_item_reviews.json"
    full_reviews = json.loads(full_path.read_text(encoding="utf-8"))
    candidates = discovery["candidates"]
    candidate_ids = {row["native_item_id"] for row in candidates}
    if set(full_reviews) != candidate_ids:
        missing = sorted(candidate_ids - set(full_reviews), key=int)
        extra = sorted(set(full_reviews) - candidate_ids, key=int)
        raise ValueError(f"CSUN full metadata scope is incomplete or escaped: missing={missing[:5]}, extra={extra[:5]}")
    for review in full_reviews.values():
        if review.get("identity_validation", {}).get("matches_frozen_candidate"):
            review["decision"] = classify_item(review["detail"], review["native_item_id"])
        else:
            review["decision"] = {"outcome": "pending",
                                  "reason": "full item metadata did not match the frozen dmQuery row",
                                  "identity_conflicts": review.get("identity_validation", {})}
    atomic_json(full_path, full_reviews)
    if any(row.get("decision", {}).get("outcome") not in {"accepted", "excluded", "pending"}
           for row in full_reviews.values()):
        raise ValueError("CSUN full metadata catalog contains an invalid disposition")

    # Preserve the earlier selected-field result as a distinct, immutable
    # evidence layer before replacing the adapter's current normalized output.
    archives = {
        "catalog.json": "catalog_five_field_2026-10-26.2.json",
        "excluded_entries.json": "excluded_entries_five_field_2026-10-26.2.json",
        "pending_entries.json": "pending_entries_five_field_2026-10-26.2.json",
        "discovery_report.json": "discovery_report_five_field_2026-10-26.2.json",
        "registry_proposal.json": "registry_proposal_five_field_2026-10-26.2.json",
    }
    for current, archived in archives.items():
        source_path, archive_path = directory / current, directory / archived
        if source_path.exists() and not archive_path.exists():
            shutil.copy2(source_path, archive_path)

    pages = discovery.get("page_evidence", [])
    old_reviews = json.loads((directory / "item_reviews.json").read_text(encoding="utf-8"))
    old_outcomes = Counter(row.get("decision", {}).get("outcome") for row in old_reviews.values())
    client.state["started_at"] = discovery.get("frozen_at", client.state.get("started_at"))
    catalog = _save_products(client, candidates=candidates, pages=pages,
                             page_size=discovery.get("listing_page_size", DMQUERY_PAGE_SIZE),
                             reviews=full_reviews, detail_complete=True,
                             metadata_scope_version=FULL_METADATA_SCOPE_VERSION,
                             full_item_metadata_count=len(full_reviews))
    resulting = Counter(row["decision"]["outcome"] for row in full_reviews.values())
    prior_dispositions = {outcome: sum(1 for native in candidate_ids
                                       if old_reviews.get(native, {}).get("decision", {}).get("outcome") == outcome)
                          for outcome in ("accepted", "excluded", "pending")}
    disposition_transitions = Counter(
        (old_reviews.get(native, {}).get("decision", {}).get("outcome", "unreviewed"),
         full_reviews[native].get("decision", {}).get("outcome", "unreviewed"))
        for native in candidate_ids)
    changed = []
    for native, result in full_reviews.items():
        previous = old_reviews.get(native, {}).get("decision", {}).get("outcome")
        current = result.get("decision", {}).get("outcome")
        if previous != current:
            changed.append({"native_item_id": native, "previous": previous, "full_metadata": current,
                            "previous_reason": old_reviews.get(native, {}).get("decision", {}).get("reason"),
                            "full_metadata_reason": result.get("decision", {}).get("reason")})
    field_info_path = directory / "collection_field_info.json"
    field_map = json.loads(field_info_path.read_text(encoding="utf-8")) if field_info_path.exists() else []
    field_info_url = f"{BASE}/digital/bl/dmwebservices/index.php?q=dmGetCollectionFieldInfo/{COLLECTION_ALIAS}/json"
    field_info_request = client.state.get("requests", {}).get(field_info_url, {})
    field_use_counts = Counter(field["key"] for review in full_reviews.values()
                               for field in review["detail"].get("fields", []))
    scope_record = {
        "schema_version": 1, "source_id": SOURCE_ID,
        "metadata_scope_version": FULL_METADATA_SCOPE_VERSION,
        "candidate_query_scope_version": discovery["scope_version"],
        "candidate_query": {
            "collection_alias": discovery["collection_alias"],
            "method": discovery["search_method"], "fields": discovery["search_parameters"]["fields"],
            "max_fields_per_dmquery_response": 5,
            "max_value_bytes_per_dmquery_field": 100,
            "candidate_count": len(candidates),
            "native_item_ids_sha256": discovery["native_item_ids_sha256"],
            "listing_pages": discovery["page_evidence"],
        },
        "complete_item_metadata": {
            "endpoint": "official CONTENTdm singleitem JSON",
            "candidate_count": len(full_reviews),
            "identity_verified_count": sum(bool(r["identity_validation"]["matches_frozen_candidate"])
                                             for r in full_reviews.values()),
            "identity_conflict_count": sum(not bool(r["identity_validation"]["matches_frozen_candidate"])
                                            for r in full_reviews.values()),
            "full_field_responses_sha256": hashlib.sha256("\n".join(
                f"{native}:{full_reviews[native]['item_metadata_sha256']}" for native in sorted(full_reviews, key=int)
            ).encode()).hexdigest(),
            "pdf_requests": 0,
        },
        "official_collection_field_map": {
            "endpoint": field_info_url, "http_status": field_info_request.get("status"),
            "sha256": field_info_request.get("sha256"),
            "collection_field_count": sum(not row.get("admin") for row in field_map),
            "admin_field_count": sum(bool(row.get("admin")) for row in field_map),
            "field_nicknames": [{"nickname": row.get("nick"), "name": row.get("name"),
                                 "admin": bool(row.get("admin")), "hidden": bool(row.get("hide")),
                                 "dublin_core_map": row.get("dc")}
                                for row in field_map],
            "per_item_nonempty_field_record_counts": dict(field_use_counts),
            "no_subject_or_instrumentation_nickname_present": not any(
                row.get("nick") in {"subjec", "instru", "instrum"} for row in field_map),
        },
        "previous_five_field_dispositions": dict(old_outcomes),
        "full_metadata_dispositions": dict(resulting),
        "disposition_transition_counts": {f"{before}->{after}": count
                                          for (before, after), count in disposition_transitions.items()},
        "disposition_changes": changed,
        "limits": [
            "The 1,145 IDs are the exact frozen guitar-keyword dmQuery candidate set, not all IGRA/CSUN holdings.",
            "The dmQuery list request returned only five selected fields, each limited to 100 bytes; it is retained only as candidate identity and comparison evidence.",
            "Each candidate now has the official singleitem item's complete returned metadata fields; blank fields may be omitted by that endpoint.",
            "Only short factual metadata is projected; full descriptions and source text remain private evidence.",
            "Source metadata supports guitar relevance and explicit source-declared instrumentation; no PDF content or player-count audit has been performed.",
        ],
    }
    atomic_json(directory / "full_metadata_scope.json", scope_record)
    atomic_json(directory / "full_metadata_review_changes.json", {
        "schema_version": 1, "source_id": SOURCE_ID,
        "scope_version": FULL_METADATA_SCOPE_VERSION,
        "previous_counts": prior_dispositions,
        "full_metadata_counts": dict(resulting),
        "changed_dispositions": changed,
        "changed_disposition_count": len(changed),
    })
    return catalog


def discover(root: Path, max_details: int | None = None) -> dict:
    """Discover and resume CSUN IGRA candidates; never fetch PDF bytes."""
    root = Path(root).resolve()
    client = DiscoveryClient(root, SOURCE_ID, HOSTS, delay=REQUEST_DELAY)
    atomic_json(client.path / "registry_proposal.json", registry_proposal())
    scope_file = _scope_path(client.path)
    policy_file = _scope_policy_path(client.path)
    scope_guard = {"schema_version": SCHEMA_VERSION, "source_id": SOURCE_ID,
                   "scope_version": SCOPE_VERSION, "query": "guitar",
                   "collection_alias": COLLECTION_ALIAS, "search_method": "OCLC dmQuery",
                   "search_template": DMQUERY_BASE,
                   "search_parameters": {"query_field": "CISOSEARCHALL", "term": "guitar",
                       "mode": "all", "operator": "and", "fields": list(DMQUERY_FIELDS),
                       "sort": "nosort", "maxrecs": DMQUERY_PAGE_SIZE, "showunpub": 1},
                   "robots_policy": "official robots Crawl-Delay: 1; documented dmQuery API path allowed; HTML search route disallowed",
                   "detail_admission": "exact item-level Public domain and source-field evidence of guitar relevance; unknown player count is retained as guitar-related"}
    # Earlier development runs wrote only this static policy guard under the
    # frozen-scope filename. Preserve those exact bytes as policy evidence
    # before the filename begins carrying the actual ID/page snapshot.
    if scope_file.exists() and not policy_file.exists():
        prior_scope = json.loads(scope_file.read_text(encoding="utf-8"))
        if prior_scope == scope_guard:
            scope_file.replace(policy_file)
    if policy_file.exists() and json.loads(policy_file.read_text(encoding="utf-8")) != scope_guard:
        raise ValueError("CSUN frozen scope/schema changed; create a new reviewed scope version")
    atomic_json(policy_file, scope_guard)

    completed_full = client.path / "full_item_reviews.json"
    frozen_listing = client.path / "discovery.json"
    if completed_full.exists() and frozen_listing.exists():
        full_rows = json.loads(completed_full.read_text(encoding="utf-8"))
        listing_rows = json.loads(frozen_listing.read_text(encoding="utf-8"))["candidates"]
        if set(full_rows) == {row["native_item_id"] for row in listing_rows}:
            correction_path = client.path / "endpoint_correction.json"
            if correction_path.exists() and json.loads(correction_path.read_text(encoding="utf-8")).get("state") == "applied":
                return json.loads((client.path / "catalog.json").read_text(encoding="utf-8"))
            return finalize_full_metadata_catalog(root)

    # A refusal recorded by DiscoveryClient is terminal for this run and future
    # resumes. A human must explicitly review the access state before changing it.
    if client.state.get("blocked_status") in {401, 403, 429}:
        discovery_path = client.path / "discovery.json"
        review_path = client.path / "item_reviews.json"
        prior = json.loads(discovery_path.read_text(encoding="utf-8")) if discovery_path.exists() else {}
        prior_reviews = json.loads(review_path.read_text(encoding="utf-8")) if review_path.exists() else {}
        candidates = prior.get("candidates", [])
        pages = prior.get("page_evidence", [])
        return _save_products(client, candidates=candidates,
                              pages=pages, page_size=prior.get("listing_page_size", 10),
                              reviews=prior_reviews, detail_complete=False,
                              blocker=f"previous HTTP {client.state['blocked_status']}; source stopped")

    candidates, pages, page_size = _fetch_candidates(client)
    candidate_ids = [row["native_item_id"] for row in candidates]
    candidate_digest = hashlib.sha256("\n".join(candidate_ids).encode()).hexdigest()
    frozen = {**scope_guard, "frozen_at": client.state["started_at"],
              "candidate_count": len(candidates), "listing_page_count": len(pages),
              "listing_page_size": page_size, "native_item_ids_sha256": candidate_digest,
              "page_evidence": [{"page": row["page"], "url": row["url"],
                                 "sha256": row["request"]["sha256"], "count": row["count"]}
                                for row in pages]}
    snapshot_path = client.path / "discovery.json"
    if scope_file.exists():
        previous_scope = json.loads(scope_file.read_text(encoding="utf-8"))
        if previous_scope.get("native_item_ids_sha256") != candidate_digest:
            raise ValueError("CSUN candidate IDs drifted from frozen_scope_dmquery.json; preserve and review separately")
        previous_pages = previous_scope.get("page_evidence", [])
        current_pages = frozen["page_evidence"]
        if previous_pages != current_pages:
            raise ValueError("CSUN page evidence drifted from frozen_scope_dmquery.json; preserve and review separately")
    if snapshot_path.exists():
        previous = json.loads(snapshot_path.read_text(encoding="utf-8"))
        if previous.get("native_item_ids_sha256") != candidate_digest:
            raise ValueError("CSUN candidate IDs drifted from the frozen snapshot; preserve and review separately")
    atomic_json(scope_file, frozen)
    atomic_json(snapshot_path, {**frozen, "candidates": candidates})
    _record_route_comparison(client, candidates)

    review_path = client.path / "item_reviews.json"
    reviews = json.loads(review_path.read_text(encoding="utf-8")) if review_path.exists() else {}
    if set(reviews) - set(candidate_ids):
        raise ValueError("CSUN review receipt contains IDs outside the frozen keyword scope")
    checked_this_run = 0
    blocker = None
    for candidate in candidates:
        native = candidate["native_item_id"]
        if native in reviews:
            continue
        try:
            detail = dmquery_record_as_detail(candidate)
            decision = classify_item(detail, native)
            detail_bytes = json.dumps(candidate["listing_metadata"], ensure_ascii=False,
                                      sort_keys=True, separators=(",", ":")).encode("utf-8")
            reviews[native] = {"native_item_id": native, "source_url": candidate["source_url"],
            "item_metadata_source": "selected-field dmQuery record; full item metadata pending",
                               "item_metadata_sha256": hashlib.sha256(detail_bytes).hexdigest(),
                               "decision": decision,
                               "detail": detail,
                               "native_search_record": candidate["listing_metadata"]}
        except Exception as exc:
            if isinstance(exc, PermissionError):
                blocker = str(exc)
                break
            raise
        checked_this_run += 1
        if checked_this_run % 100 == 0:
            atomic_json(review_path, reviews)
            _save_products(client, candidates=candidates, pages=pages, page_size=page_size,
                           reviews=reviews, detail_complete=False)
            atomic_json(client.path / "detail_progress.json", {
                "schema_version": SCHEMA_VERSION, "source_id": SOURCE_ID,
                "scope_version": SCOPE_VERSION, "detail_checked": len(reviews),
                "candidate_count": len(candidates), "remaining": len(candidates) - len(reviews),
            })
            print(f"CSUN IGRA per-item metadata reviewed: {len(reviews)}/{len(candidates)}", flush=True)
        if max_details is not None and checked_this_run >= max_details:
            break
    atomic_json(review_path, reviews)
    atomic_json(client.state_path, client.state)
    complete = len(reviews) == len(candidates) and blocker is None
    catalog = _save_products(client, candidates=candidates, pages=pages, page_size=page_size,
                             reviews=reviews, detail_complete=complete, blocker=blocker)
    if max_details is not None:
        print(f"CSUN IGRA checkpoint: {len(reviews)}/{len(candidates)} item details", flush=True)
    return catalog


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--max-details", type=int, default=None)
    parser.add_argument("--fetch-full-metadata", action="store_true",
                        help="fetch complete item JSON for the full frozen candidate ID set")
    parser.add_argument("--finalize-full-metadata", action="store_true",
                        help="build the current normalized catalog from a complete frozen full-metadata run")
    parser.add_argument("--correct-download-endpoints", action="store_true",
                        help="apply the guarded CSUN /digital-mount correction to current assets")
    args = parser.parse_args(argv)
    if args.max_details is not None and args.max_details < 1:
        parser.error("--max-details must be >= 1")
    if args.finalize_full_metadata:
        result = finalize_full_metadata_catalog(args.root)
        print(json.dumps(result["summary"], ensure_ascii=False), flush=True)
        return result
    if args.correct_download_endpoints:
        result = correct_catalog_download_endpoints(args.root)
        print(json.dumps(result, ensure_ascii=False), flush=True)
        return result
    if args.fetch_full_metadata:
        result = fetch_full_item_metadata(args.root, max_records=args.max_details)
        print(json.dumps(result, ensure_ascii=False), flush=True)
        return result
    result = discover(args.root, args.max_details)
    print(json.dumps(result["summary"], ensure_ascii=False), flush=True)
    return result


if __name__ == "__main__":
    main()
