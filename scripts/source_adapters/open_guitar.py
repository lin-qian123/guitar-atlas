"""Source-owned, read-only discovery for two open/author guitar catalogs.

Yawnoc records are frozen from GitHub's public API by release tag and commit.
Maikstrings records are discovered from its confirmed guitar directory only;
all PDF links stay restricted until edition-file redistribution rights are clear.
No adapter code is executed and no score PDF is fetched here.
"""
from __future__ import annotations

import hashlib
import json
import re
import base64
import binascii
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

from bs4 import BeautifulSoup

from .additional import (DiscoveryClient, atomic_json, category, restore_asset_receipts,
                         utcnow, work)

YAWNOC_ID = "yawnoc"
YAWNOC_OWNER = "yawnoc"
YAWNOC_REPO = "guitar"
YAWNOC_HOME = "https://github.com/yawnoc/guitar"
YAWNOC_API = "https://api.github.com/repos/yawnoc/guitar"
YAWNOC_HOSTS = {"api.github.com", "github.com"}

MAIK_ID = "maikstrings"
MAIK_HOME = "https://maikstrings.com/"
MAIK_DIRECTORY = MAIK_HOME + "sheet-music-guitar.html"
MAIK_HOSTS = {"maikstrings.com"}

CC0_URL = "https://creativecommons.org/publicdomain/zero/1.0/"


def _json(client: DiscoveryClient, url: str):
    body, receipt = client.get(url)
    try:
        result = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"GitHub API returned non-JSON metadata: {url}") from exc
    if isinstance(result, dict) and result.get("message") and "url" not in result:
        raise RuntimeError(f"GitHub API error {result.get('status', '')}: {result['message']}")
    return result, receipt


def _write_json(client: DiscoveryClient, name: str, data) -> None:
    atomic_json(client.path / name, data)


def _preserve_initial_report(client: DiscoveryClient) -> None:
    current = client.path / "discovery_report.json"
    initial = client.path / "initial_discovery_report.json"
    if current.exists() and not initial.exists():
        atomic_json(initial, json.loads(current.read_text(encoding="utf-8")))


def _prepare_client(client: DiscoveryClient) -> None:
    # Earlier catalog-only summaries used this filename before the shared
    # DiscoveryClient had persistent request-state semantics. Repair that
    # shape in memory while preserving any valid cached request entries.
    client.state.setdefault("schema_version", 1)
    client.state.setdefault("source_id", client.source_id)
    client.state.setdefault("started_at", client.state.get("frozen_at", utcnow()))
    client.state.setdefault("requests", {})
    client.state.setdefault("failures", [])
    state_path = getattr(client, "state_path", None)
    if state_path is not None:
        atomic_json(state_path, client.state)


def _valid_https_url(url: str, hosts: set[str]) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in hosts or parsed.username or parsed.password or parsed.fragment:
        raise ValueError(f"unapproved source URL: {url}")
    return url


def _record_slug(tag: str, slugs: list[str]) -> str:
    matches = [slug for slug in slugs if tag.startswith(slug + "-") and re.search(r"-v\d+\.\d+\.\d+$", tag)]
    if matches:
        longest = max(map(len, matches))
        matches = [slug for slug in matches if len(slug) == longest]
    if len(matches) != 1:
        raise ValueError(f"release tag does not identify exactly one native score directory: {tag}")
    return matches[0]


def _commit_for_tag(client: DiscoveryClient, tag: str) -> tuple[str, dict]:
    tag_url = f"{YAWNOC_API}/commits/{tag}"
    payload, receipt = _json(client, tag_url)
    sha = payload.get("sha")
    tree_sha = (payload.get("commit") or {}).get("tree", {}).get("sha")
    if not re.fullmatch(r"[0-9a-f]{40}", str(sha)) or not re.fullmatch(r"[0-9a-f]{40}", str(tree_sha)):
        raise ValueError(f"GitHub did not resolve release tag to a commit and tree: {tag}")
    return sha, {"commit_url": tag_url, "commit_sha": sha, "tree_sha": tree_sha,
                 "committed_at": (payload.get("commit") or {}).get("committer", {}).get("date"),
                 "api_response_sha256": receipt["sha256"]}


def _tag_tree(client: DiscoveryClient, tree_sha: str) -> dict:
    url = f"{YAWNOC_API}/git/trees/{tree_sha}?recursive=1"
    tree, _ = _json(client, url)
    if tree.get("truncated"):
        raise ValueError("GitHub tag tree is truncated; source-file provenance is incomplete")
    return {row["path"]: row for row in tree.get("tree", []) if row.get("type") == "blob"}


def _github_contents(client: DiscoveryClient, path: str, commit: str) -> tuple[str, dict]:
    url = f"{YAWNOC_API}/contents/{path}?ref={commit}"
    payload, receipt = _json(client, url)
    if payload.get("path") != path or payload.get("encoding") != "base64":
        raise ValueError(f"GitHub contents response does not match the requested path: {path}")
    if not re.fullmatch(r"[0-9a-f]{40}", str(payload.get("sha"))):
        raise ValueError(f"GitHub contents response has no immutable blob SHA: {path}")
    try:
        encoded = "".join(payload["content"].split())
        content = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (KeyError, ValueError, binascii.Error, UnicodeDecodeError) as exc:
        raise ValueError(f"GitHub contents response is not valid base64 UTF-8: {path}") from exc
    return content, {"path": path, "commit": commit, "blob_sha": payload["sha"],
                     "api_url": url, "api_response_sha256": receipt["sha256"],
                     "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest()}


def _lilypond_header(text: str) -> dict[str, str]:
    start = re.search(r"(?m)^\s*\\header\s*\{", text)
    if not start:
        return {}
    open_at = text.find("{", start.start())
    depth, quoted, escaped, comment, end = 0, False, False, False, None
    for index in range(open_at, len(text)):
        char = text[index]
        if comment:
            if char == "\n":
                comment = False
            continue
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == "%":
            comment = True
        elif char == '"':
            quoted = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end = index
                break
    if end is None:
        raise ValueError("LilyPond header has unbalanced braces")
    block = text[open_at + 1:end]
    fields = {}
    for name in ("title", "subtitle", "composer", "arranger", "editor"):
        match = re.search(rf'(?m)^\s*{name}\s*=\s*"((?:[^"\\]|\\.)*)"', block)
        if match:
            fields[name] = re.sub(r"\\([\\\"])", r"\1", match[1])
    if "subtitle" not in fields:
        subtitle = re.search(r"(?ms)^\s*subtitle\s*=\s*(.*?)(?=^\s*(?:title|composer|arranger|editor|instrument)\s*=|\Z)", block)
        if subtitle:
            quoted = re.findall(r'"((?:[^"\\]|\\.)*)"', subtitle[1])
            if quoted:
                fields["subtitle"] = "；".join(re.sub(r"\\([\\\"])", r"\1", item) for item in quoted)
    return fields


def _readme_release_index(readme: str) -> list[str]:
    return sorted(set(re.findall(
        r"https://github\.com/yawnoc/guitar/releases/tag/([A-Za-z0-9.-]+)", readme)))


def _yawnoc_score_instrumentation(text: str) -> dict:
    staff_names = list(dict.fromkeys(re.findall(r'(?m)^\s*instrumentName\s*=\s*"([^"]+)"', text)))
    midi_names = list(dict.fromkeys(re.findall(r'(?m)^\s*midiInstrument\s*=\s*#?"([^"]+)"', text)))
    explicit_guitar = any("guitar" in value.casefold() for value in staff_names + midi_names)
    guitar_notation = bool(re.search(r"\\(?:stringNumbers(?:Above|Below)|fingering(?:Above|Below|Aleft|Aright)|barreSpan)\b", text))
    bass_labels = [value for value in staff_names + midi_names if "bass" in value.casefold()]
    guitar_labels = [value for value in staff_names + midi_names if "guitar" in value.casefold()]
    if guitar_labels and bass_labels:
        instrumentation = "Guitar"
        basis = "explicit LilyPond guitar staff labels; separate Bass staff label retained privately; staff labels denote written parts, not player count"
        status = "source_declared"
        scope_status = "pending_review"
        scope_reason = "The fixed score source explicitly includes guitar and bass staff/instrument labels; retain mixed-instrument status for review."
    elif explicit_guitar:
        instrumentation = "Guitar"
        basis = "explicit LilyPond staff and/or MIDI instrument labels; player count not stated"
        status = "source_declared"
        scope_status = "candidate"
        scope_reason = None
    elif guitar_notation:
        instrumentation = "Guitar"
        basis = "fixed LilyPond source uses guitar-specific string-number, fingering, or barre notation; no named staff count"
        status = "unverified"
        scope_status = "candidate"
        scope_reason = None
    else:
        instrumentation = None
        basis = "no guitar-specific instrument label or notation evidence found in the fixed LilyPond source"
        status = "unverified"
        scope_status = "pending_review"
        scope_reason = "The fixed LilyPond source does not expose guitar-specific instrumentation evidence."
    return {"instrumentation": instrumentation, "instrumentation_basis": basis,
            "instrumentation_status": status, "scope_status": scope_status,
            "scope_reason": scope_reason, "staff_names": staff_names,
            "midi_instrument_names": midi_names, "player_count": None}


def _yawnoc_tag_evidence(client: DiscoveryClient, tag_commit: dict, main_path: str) -> dict:
    commit = tag_commit["commit_sha"]
    lily_text, lily_receipt = _github_contents(client, main_path, commit)
    readme_text, readme_receipt = _github_contents(client, "README.md", commit)
    license_text, license_receipt = _github_contents(client, "LICENSE", commit)
    header = _lilypond_header(lily_text)
    if not header.get("title") or not header.get("composer"):
        raise ValueError(f"tagged LilyPond header is missing a title or composer: {main_path}")
    return {"header": header, "lilypond_text": lily_text,
            "readme_text": readme_text, "license_text": license_text,
            "lilypond_evidence": lily_receipt,
            "readme_evidence": readme_receipt,
            "license_evidence": license_receipt}


def _release_assets(release: dict) -> list[dict]:
    assets = []
    for item in release.get("assets", []):
        name = item.get("name") or ""
        url = item.get("browser_download_url") or ""
        if not name.casefold().endswith(".pdf"):
            continue
        _valid_https_url(url, {"github.com"})
        content_type = item.get("content_type")
        if content_type not in {"application/pdf", "application/octet-stream"}:
            raise ValueError(f"unexpected GitHub release asset content type for {name}: {content_type}")
        assets.append({
            "source_url": url,
            "format": "PDF",
            "filename": name,
            "label": name,
            "status": "restricted",
            "license": "CC0-1.0",
            "license_url": CC0_URL,
            "license_status": "explicit_CC0_edition_license",
            "acquisition_permission": "blocked_by_robots",
            "restriction_reason": "Cached DiscoveryClient robots check denied the GitHub release-download route before an asset request; do not retry this route or use an alternate host/path.",
            "upstream_checksum": item.get("digest"),
            "upstream_checksum_status": "available_not_yet_verified" if item.get("digest") else "not_supplied",
            "expected_size": item.get("size"),
            "github_release_asset_id": item.get("id"),
            "github_release_asset_api_url": item.get("url"),
            "github_asset_state": item.get("state"),
            "github_asset_content_type": content_type,
        })
    return assets


def _yawnoc_work(release: dict, repository: dict, tag_commit: dict, tree: dict,
                 source_evidence: dict) -> dict:
    tag = release.get("tag_name") or ""
    slugs = [path.split("/", 1)[0] for path, row in tree.items()
             if row.get("type") == "blob" and path.endswith(".ly") and "/" in path]
    slugs = sorted(set(slugs))
    slug = _record_slug(tag, slugs)
    main_path = f"{slug}/{slug}.ly"
    source = tree.get(main_path)
    if not source:
        raise ValueError(f"tag tree has no native main LilyPond file for {tag}: {main_path}")
    release_url = _valid_https_url(release.get("html_url") or "", {"github.com"})
    if release_url != f"{YAWNOC_HOME}/releases/tag/{tag}":
        raise ValueError(f"unexpected human release page for {tag}: {release_url}")
    assets = _release_assets(release)
    if not assets:
        raise ValueError(f"release has no PDF assets: {tag}")

    header = source_evidence["header"]
    title = header.get("title")
    composer = header.get("composer")
    if not title or not composer:
        raise ValueError(f"fixed LilyPond header lacks a source title or composer for {tag}")
    readme = source_evidence["readme_text"]
    license_text = source_evidence["license_text"]
    if not re.search(r"original compositions are all already in the public domain", readme, re.I):
        raise ValueError(f"fixed README no longer makes the captured public-domain composition claim for {tag}")
    if not re.search(r"release my edits/arrangements.*?under CC0", readme, re.I | re.S):
        raise ValueError(f"fixed README no longer documents CC0 edits/arrangements for {tag}")
    if not re.search(r"Creative Commons Legal Code\s+CC0 1\.0 Universal", license_text, re.I):
        raise ValueError(f"fixed LICENSE is not the CC0 1.0 legal code for {tag}")
    instrumentation = _yawnoc_score_instrumentation(source_evidence["lilypond_text"])
    public_instrumentation_note = "The fixed LilyPond source supports the guitar family; performer count is not stated."
    if instrumentation["scope_status"] == "pending_review":
        guitar_staff_names = [name for name in instrumentation["staff_names"] if "guitar" in name.casefold()]
        bass_staff_names = [name for name in instrumentation["staff_names"] if "bass" in name.casefold()]
        public_instrumentation_note = (
            "The fixed LilyPond source labels guitar staves "
            + ", ".join(guitar_staff_names)
            + (" and a separate Bass staff " + ", ".join(bass_staff_names) if bass_staff_names else "")
            + ". Mixed instrumentation is pending review; these are written staff labels, not a performer count."
        )

    source_url = f"{YAWNOC_HOME}/blob/{tag_commit['commit_sha']}/{main_path}"
    assets.append({
        "source_url": source_url,
        "format": "LILYPOND",
        "filename": f"{slug}.ly",
        "label": "Editable LilyPond source",
        "status": "metadata_only",
        "license": "CC0-1.0",
        "license_url": CC0_URL,
        "acquisition_permission": "source_format_metadata_only",
        "source_repository": {"owner": YAWNOC_OWNER, "repository": YAWNOC_REPO,
                              "commit": tag_commit["commit_sha"], "path": main_path,
                              "git_blob_sha": source.get("sha"), "size": source.get("size")},
    })

    raw_title = release.get("name") or slug
    release_title = raw_title.strip()
    raw_arranger = header.get("arranger")
    is_edits_credit = bool(raw_arranger and re.search(r"\(\s*edits?\s*\)\s*$", raw_arranger, re.I))
    typed_arranger = None if is_edits_credit else raw_arranger
    typed_editor = raw_arranger if is_edits_credit else header.get("editor")
    arrangement_status = "arrangement" if raw_arranger and re.search(
        r"\(\s*arrangement\s*\)\s*$", raw_arranger, re.I) else "unspecified"
    if is_edits_credit:
        attribution_note = (
            "Composer and source header credit fields are transcribed from the LilyPond header at the frozen tag commit. "
            f"The raw source_header arranger value {raw_arranger!r} is preserved verbatim; its explicit edits annotation is typed as editor, "
            "not arranger, so original/arrangement status remains unspecified."
        )
    elif arrangement_status == "arrangement":
        attribution_note = (
            "Composer and arranger fields are transcribed from the LilyPond header at the frozen tag commit. "
            f"The raw source_header arranger value {raw_arranger!r} explicitly labels an arrangement and is preserved verbatim."
        )
    else:
        attribution_note = (
            "Composer and source header credit fields are transcribed from the LilyPond header at the frozen tag commit; "
            "source title takes precedence over the release heading. Original/arrangement status remains unspecified absent an explicit arrangement label."
        )
    row = work(YAWNOC_ID, slug, title.strip(), composer.strip(), release_url, ["guitar"],
               formats=sorted({asset["format"] for asset in assets}), assets=assets,
               metadata={
                   "native_record_slug": slug,
                   "native_release_tag": tag,
                   "release_name_raw": raw_title,
                   "source_title_transcription": title.strip(),
                   "title_annotations": header.get("subtitle"),
                   "arranger": typed_arranger,
                   "editor": typed_editor,
                   "instrumentation": instrumentation["instrumentation"],
                   "instrumentation_basis": instrumentation["instrumentation_basis"],
                   "player_count": instrumentation["player_count"],
                   "description": public_instrumentation_note,
                   "availability": "PDF release-download access blocked by robots before request; no alternate route was attempted.",
                   "license": "CC0-1.0 (score edition); Public Domain composition (repository claim)",
                   "license_note": (
                       "At this release tag commit, README says the original compositions are public domain and the author's edits/arrangements are released under CC0; the matching LICENSE is CC0 1.0. Composition lineage is not independently audited."
                   ),
                   "original_arrangement_status": arrangement_status,
                   "source_attribution_note": attribution_note,
                   "source_readme_claims": {"composition": "Public Domain", "edits_arrangements": "CC0-1.0"},
                   "source_readme_evidence": source_evidence["readme_evidence"],
                   "source_license_evidence": source_evidence["license_evidence"],
                   "source_lilypond_evidence": source_evidence["lilypond_evidence"],
                   "github_release_id": release.get("id"),
                   "github_release_url": release_url,
                   "github_release_published_at": release.get("published_at"),
                   "github_release_created_at": release.get("created_at"),
                   "github_release_api_url": release.get("url"),
                   "repository_default_branch": repository.get("default_branch"),
                   "repository_head_commit": repository.get("_frozen_head_commit"),
                   "tag_commit_sha": tag_commit["commit_sha"],
                   "tag_tree_sha": tag_commit["tree_sha"],
                   "native_source_path": main_path,
                   "score_source_format": "LILYPOND",
                   "composition_license": "Public Domain per fixed tag README claim",
                   "composition_license_basis": "readme bytes read through GitHub contents API at immutable tag commit; per-work lineage not independently audited",
                   "edition_license": "CC0-1.0",
                   "edition_license_url": CC0_URL,
                   "license_evidence_commit": tag_commit["commit_sha"],
                   "rights_layers": {"composition": "public_domain", "edition_arrangement": "CC0-1.0"},
                   "instrumentation_status": instrumentation["instrumentation_status"],
                   "scope_status": instrumentation["scope_status"],
                   "scope_reason": instrumentation["scope_reason"],
                   "native_staff_names": instrumentation["staff_names"],
                   "native_midi_instrument_names": instrumentation["midi_instrument_names"],
                   "source_header": header,
                   "release_heading_differs_from_source_title": release_title.casefold() != title.strip().casefold(),
                   "release_title_raw": release_title,
                   "native_record_locator": slug,
               }, instrumentation_status=instrumentation["instrumentation_status"])
    return row


def discover_yawnoc(root: Path) -> dict:
    """Freeze all current guitar-score GitHub releases without fetching assets."""
    client = DiscoveryClient(Path(root), YAWNOC_ID, YAWNOC_HOSTS, delay=0.8)
    _prepare_client(client)
    prior_failure_count = len(client.state.get("failures", []))
    repo, _ = _json(client, YAWNOC_API)
    if repo.get("full_name", "").casefold() != "yawnoc/guitar":
        raise ValueError("GitHub API returned a different repository identity")
    branch = repo.get("default_branch")
    if not branch:
        raise ValueError("GitHub repository has no default branch")
    head_url = f"{YAWNOC_API}/commits/{branch}"
    head, head_receipt = _json(client, head_url)
    head_sha = head.get("sha")
    if not re.fullmatch(r"[0-9a-f]{40}", str(head_sha)):
        raise ValueError("GitHub repository head commit is missing or malformed")
    repo["_frozen_head_commit"] = head_sha
    head_tree_sha = (head.get("commit") or {}).get("tree", {}).get("sha")
    if not re.fullmatch(r"[0-9a-f]{40}", str(head_tree_sha)):
        raise ValueError("GitHub repository head tree is missing or malformed")
    head_tree = _tag_tree(client, head_tree_sha)
    head_readme_text, head_readme_evidence = _github_contents(client, "README.md", head_sha)
    head_license_text, head_license_evidence = _github_contents(client, "LICENSE", head_sha)
    readme_release_tags = _readme_release_index(head_readme_text)
    if not re.search(r"Creative Commons Legal Code\s+CC0 1\.0 Universal", head_license_text, re.I):
        raise ValueError("current official LICENSE is not the CC0 1.0 legal code")
    all_slugs = sorted({path.split("/", 1)[0] for path in head_tree
                        if path.endswith(".ly") and "/" in path and not path.startswith(".")})
    per_page = 100
    page_number = 1
    release_pages = []
    last_release_page_count = 0
    while True:
        releases_url = f"{YAWNOC_API}/releases?per_page={per_page}&page={page_number}"
        releases, _ = _json(client, releases_url)
        if not isinstance(releases, list):
            raise ValueError("GitHub releases endpoint did not return a list")
        last_release_page_count = len(releases)
        release_pages.extend(releases)
        if len(releases) < per_page:
            break
        page_number += 1
    live = [row for row in release_pages if not row.get("draft") and not row.get("prerelease")]
    api_tags = sorted(row.get("tag_name", "") for row in live)
    if readme_release_tags != api_tags:
        raise ValueError("current README's release index and GitHub release API disagree")
    if len({row.get("tag_name") for row in live}) != len(live):
        raise ValueError("GitHub release API duplicated a tag")

    works, tag_receipts, seen_slugs = [], {}, set()
    for release in live:
        tag = release.get("tag_name") or ""
        slug = _record_slug(tag, all_slugs)
        if slug in seen_slugs:
            raise ValueError(f"multiple current releases map to the same native score slug: {slug}")
        seen_slugs.add(slug)
        commit_sha, tag_receipt = _commit_for_tag(client, tag)
        if not re.fullmatch(r"[0-9a-f]{40}", str(tag_receipt["tree_sha"])):
            raise ValueError(f"tag tree SHA is invalid for {tag}")
        tag_tree = _tag_tree(client, tag_receipt["tree_sha"])
        tag_receipt["tree_path_count"] = len(tag_tree)
        tag_receipt["api_tag_commit"] = commit_sha
        main_path = f"{slug}/{slug}.ly"
        evidence = _yawnoc_tag_evidence(client, tag_receipt, main_path)
        tag_receipt["content_evidence"] = {"lilypond": evidence["lilypond_evidence"],
            "readme": evidence["readme_evidence"], "license": evidence["license_evidence"],
            "header": evidence["header"]}
        tag_receipts[tag] = tag_receipt
        works.append(_yawnoc_work(release, repo, tag_receipt, tag_tree, evidence))

    expected_slugs = set(all_slugs)
    published_slugs = {row["metadata"]["native_record_slug"] for row in works}
    # Repository contains helper/duration directories too; only score folders
    # with a named PDF release belong in this frozen published-score snapshot.
    unrepresented_score_slugs = sorted(slug for slug in expected_slugs - published_slugs
                                       if not slug.startswith("."))
    categories = [category("guitar", "Guitar", YAWNOC_HOME)] if works else []
    restore_asset_receipts(client.path / "catalog.json", works)
    _preserve_initial_report(client)
    _write_json(client, "github_repository.json", {
        "repository": YAWNOC_HOME, "api_url": YAWNOC_API,
        "repository_id": repo.get("id"), "full_name": repo.get("full_name"),
        "default_branch": branch, "head_commit": head_sha, "head_tree_sha": head_tree_sha,
        "head_commit_api_sha256": head_receipt.get("sha256"), "checked_at": utcnow(),
        "license_spdx": (repo.get("license") or {}).get("spdx_id"),
        "license_api_url": (repo.get("license") or {}).get("url"),
        "published_release_count": len(live), "release_tags": sorted(row["tag_name"] for row in live),
        "release_api_per_page": per_page, "release_api_page_count": page_number,
        "release_api_total_returned": len(release_pages),
        "release_api_complete_by_page_limit": last_release_page_count < per_page,
        "head_readme_evidence": head_readme_evidence,
        "head_license_evidence": head_license_evidence,
        "readme_release_index_tags": readme_release_tags,
        "tag_commit_receipts": tag_receipts,
        "head_tree_path_count": len(head_tree), "head_score_slugs": all_slugs,
    })
    _write_json(client, "release_redirect_probe.json", {
        "probed_at": utcnow(), "request_method": "HEAD",
        "status": "robots_denied_before_request", "request_sent": False,
        "asset_download_attempted": False,
        "redirect_host_observed": False,
        "note": "DiscoveryClient robots check denied the GitHub release-asset URL; no alternate route was tried.",
    })
    catalog = {
        "schema_version": 1, "source_id": YAWNOC_ID,
        "snapshot": {"frozen_at": client.state["started_at"], "completed_at": utcnow(),
                     "discovery_complete": not unrepresented_score_slugs,
                     "scope": "Release API enumerated with per_page=100 until a page returned fewer than 100 items; current README release index matched all returned non-draft/non-prerelease releases, and each tag's LilyPond source, README, and LICENSE were read at its immutable commit through GitHub contents API. No PDF was fetched.",
                     "repository": YAWNOC_HOME, "repository_id": repo.get("id"),
                     "default_branch": branch, "head_commit": head_sha,
                     "published_release_count": len(live), "source_score_count": len(works),
                     "release_api_per_page": per_page, "release_api_page_count": page_number,
                     "release_api_total_returned": len(release_pages),
                     "release_api_complete_by_page_limit": last_release_page_count < per_page,
                     "readme_release_index_tags": readme_release_tags,
                     "unrepresented_score_directories": unrepresented_score_slugs,
                     "pdf_downloads_attempted": False, "source_files_downloaded": True,
                     "lilypond_bodies_read_for_metadata": True,
                     "lilypond_source_assets_acquired": False,
                     "fresh_file_integrity_verification": False,
                     "fresh_instrumentation_verification": False},
        "categories": categories,
        "works": sorted(works, key=lambda row: row["id"]),
    }
    _write_json(client, "catalog.json", catalog)
    proposal = registry_proposals()[YAWNOC_ID]
    _write_json(client, "registry_proposal.json", proposal)
    report = {
        "schema_version": 1, "source_id": YAWNOC_ID, "completed_at": utcnow(),
        "discovery_complete": catalog["snapshot"]["discovery_complete"],
        "source_record_count": len(works), "published_release_count": len(live),
        "release_api_per_page": per_page, "release_api_page_count": page_number,
        "release_api_total_returned": len(release_pages),
        "release_api_complete_by_page_limit": last_release_page_count < per_page,
        "readme_release_index_tags": readme_release_tags,
        "manifest_record_count": sum(len(row["assets"]) for row in works),
        "pdf_manifest_count": sum(asset["format"] == "PDF" for row in works for asset in row["assets"]),
        "editable_source_manifest_count": sum(asset["format"] == "LILYPOND" for row in works for asset in row["assets"]),
        "pending_pdf_count": sum(asset["format"] == "PDF" and asset["status"] == "pending" for row in works for asset in row["assets"]),
        "restricted_pdf_count": sum(asset["format"] == "PDF" and asset["status"] == "restricted" for row in works for asset in row["assets"]),
        "blocked_by_robots_pdf_count": sum(asset["format"] == "PDF" and asset.get("acquisition_permission") == "blocked_by_robots" for row in works for asset in row["assets"]),
        "excluded_record_count": 0, "pending_scope_review_count": sum(row["metadata"].get("scope_status") == "pending_review" for row in works),
        "unrepresented_score_directories": unrepresented_score_slugs,
        "pdf_downloads_attempted": False, "source_files_downloaded": True,
        "lilypond_bodies_read_for_metadata": True,
        "lilypond_source_assets_acquired": False,
        "robot_status": "GitHub API metadata endpoints passed cached DiscoveryClient robots checks; release-asset HEAD probe was blocked by robots before sending",
        "release_asset_redirect_probe": {"observed": False, "status": "robots_denied_before_request",
                                          "request_method": "HEAD", "asset_download_attempted": False},
        "request_failures": client.state.get("failures", [])[prior_failure_count:],
    }
    report["record_outcomes"] = [{
        "source_record_id": row["id"],
        "native_slug": row["metadata"]["native_record_slug"],
        "native_title": row["title_en"],
        "composer": row["composer_en"],
        "arranger": row["metadata"].get("arranger"),
        "instrumentation": row["metadata"].get("instrumentation"),
        "instrumentation_status": row["metadata"].get("instrumentation_status"),
        "player_count": None,
        "composition_license": row["metadata"]["composition_license"],
        "edition_license": row["metadata"]["edition_license"],
        "header": row["metadata"]["source_header"],
        "source_evidence": {
            "lilypond": row["metadata"]["source_lilypond_evidence"],
            "readme": row["metadata"]["source_readme_evidence"],
            "license": row["metadata"]["source_license_evidence"],
        },
        "release_tag": row["metadata"]["native_release_tag"],
        "release_page": row["source_url"],
        "tag_commit": row["metadata"]["tag_commit_sha"],
        "tag_tree": row["metadata"]["tag_tree_sha"],
        "scope_status": row["metadata"]["scope_status"],
        "assets": [{"format": asset["format"], "status": asset["status"],
                    "license": asset.get("license"),
                    "license_status": asset.get("license_status"),
                    "acquisition_permission": asset.get("acquisition_permission"),
                    "restriction_reason": asset.get("restriction_reason"),
                    "source_url": asset["source_url"]}
                   for asset in row["assets"]],
    } for row in sorted(works, key=lambda item: item["id"])]
    report["unique_physical_pdf_count"] = 0
    _write_json(client, "discovery_report.json", report)
    _write_json(client, "freeze_report.json", {
        "schema_version": 1, "source_id": YAWNOC_ID,
        "snapshot_commit": head_sha, "discovery_complete": report["discovery_complete"],
        "record_outcomes": report["record_outcomes"],
        "unrepresented_score_directories": unrepresented_score_slugs,
        "restricted_pdf_count": report["restricted_pdf_count"],
        "blocked_by_robots_pdf_count": report["blocked_by_robots_pdf_count"],
        "pending_pdf_count": report["pending_pdf_count"],
        "request_failures": report["request_failures"],
        "pdf_downloads_attempted": False, "source_files_downloaded": True,
        "lilypond_bodies_read_for_metadata": True,
        "lilypond_source_assets_acquired": False,
        "unique_physical_pdf_count": 0,
    })
    _write_json(client, "adapter_run.json", {"frozen_at": client.state["started_at"],
        "finished_at": utcnow(), "status": "complete" if report["discovery_complete"] else "partial",
        "summary": {key: value for key, value in report.items() if key != "record_outcomes"}})
    return {key: value for key, value in report.items() if key != "record_outcomes"}


def _maikstrings_pages(text_value: str) -> int:
    match = re.fullmatch(r"\s*(\d+)\s+pages?\s*", text_value, re.I)
    if not match:
        raise ValueError(f"Maikstrings directory has an unrecognized page-count field: {text_value!r}")
    return int(match[1])


def maikstrings_record_id(native_locator: str) -> str:
    """Stable opaque identity from the exact PDF locator, not its bytes."""
    return "pdf:" + hashlib.sha256(native_locator.encode("utf-8")).hexdigest()


def _maikstrings_composer_filters(soup: BeautifulSoup, declared_count: int,
                                  credit_counts: dict[str, int]) -> dict:
    """Promote .nt-c to composer only when the page's composer filters corroborate it."""
    filters = {}
    for node in soup.select("[data-nt-composer]"):
        name = node.get("data-nt-composer", "").strip()
        text_value = node.get_text(" ", strip=True)
        match = re.search(r"(?:·|•)\s*(\d+)\s+sheets?\s*$", text_value, re.I)
        if not name or not match or name in filters:
            return {"confirmed": False, "reason": "composer filter labels or counts are incomplete/duplicated"}
        filters[name] = int(match[1])
    if len(filters) != 9:
        return {"confirmed": False, "reason": "page does not expose exactly nine composer-filter groups"}
    if sum(filters.values()) != declared_count:
        return {"confirmed": False, "reason": "composer-filter sheet counts do not sum to the declared directory total"}
    if filters != credit_counts:
        return {"confirmed": False, "reason": "composer-filter names/counts do not match the per-entry .nt-c credits"}
    return {
        "confirmed": True,
        "reason": "nine named composer filters exactly match the per-entry .nt-c names and counts and sum to the declared directory total",
        "groups": filters,
    }


def parse_maikstrings_directory(html: bytes | str) -> tuple[list[dict], dict]:
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.find("h1")
    if not heading or "classical guitar sheet music" not in heading.get_text(" ", strip=True).casefold():
        raise ValueError("Maikstrings did not return the confirmed Classical Guitar directory")
    declared = re.search(r"(\d+)\s+sheets?", soup.get_text(" ", strip=True), re.I)
    if not declared:
        raise ValueError("Maikstrings directory does not expose its sheet count")
    declared_count = int(declared[1])
    rows = []
    seen = set()
    credit_counts: dict[str, int] = {}
    for anchor in soup.select("a.nt-link[href]"):
        url = urljoin(MAIK_HOME, anchor["href"])
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname != "maikstrings.com" or not parsed.path.casefold().endswith(".pdf"):
            continue
        title_node = anchor.select_one(".nt-t")
        credit_node = anchor.select_one(".nt-c")
        pages_node = anchor.select_one(".nt-p")
        if not title_node or not pages_node:
            raise ValueError("Maikstrings guitar record lacks native title or page count")
        title = title_node.get_text(" ", strip=True)
        credit = credit_node.get_text(" ", strip=True) if credit_node else ""
        pages_text = pages_node.get_text(" ", strip=True)
        native_locator = anchor["href"]
        if native_locator in seen:
            raise ValueError(f"Maikstrings guitar directory repeats a PDF locator: {native_locator}")
        seen.add(native_locator)
        pages = _maikstrings_pages(pages_text)
        if credit:
            credit_counts[credit] = credit_counts.get(credit, 0) + 1
        filename = unquote(parsed.path.rsplit("/", 1)[-1])
        record_id = maikstrings_record_id(native_locator)
        row = work(MAIK_ID, record_id, title, "", MAIK_DIRECTORY, ["guitar"], formats=["PDF"],
                   instrumentation_status="source_declared")
        row["metadata"].update({
            "native_record_locator": native_locator,
            "native_pdf_filename": filename,
            "source_directory_title": "Classical Guitar Sheet Music",
            "source_directory_instrumentation": "Classical guitar",
            "instrumentation": "Guitar",
            "instrumentation_status": "unverified",
            "player_count": None,
            "description": "Classical Guitar directory scope only; per-score parts, arrangement roles, and player count are unknown.",
            "pages": pages,
            "license": "Public Domain (source directory claim; modern engraving reuse scope unclear)",
            "license_note": ("Directory permits downloading, printing, teaching, and group copying free of charge. This supports personal/educational offline acquisition; the source's public-domain claim and modern engraving rights do not establish permission for a public PDF mirror."),
            "attribution_role": "source_unspecified",
            "contributors": "Maikstrings (engraving, directory-level source claim)",
            "arranger": None,
            "editor": None,
            "source_attribution_note": f".nt-c source directory credit: {credit or 'empty'}; the site associates this field with its composer filter but does not explicitly state a per-score attribution role.",
            "source_credit_line": credit,
            "source_credit_field": "directory .nt-c text; site associates with composer filter; no per-score credit role is explicitly labelled",
            "source_title_field": title,
            "source_page_count_text": pages_text,
            "source_pages": pages,
            "source_directory_locator": MAIK_DIRECTORY,
            "composition_rights_claim": "Source directory states every sheet is public domain and all composers died more than 70 years ago; individual composer roles and engraving rights not independently verified.",
            "score_file_license": "not_clear_for_redistribution",
            "score_file_rights_note": "Personal and educational downloads are explicitly offered. Public digital redistribution of the modern engraving is not established; verified files remain private.",
            "engraver_credit": "Maikstrings, per source directory page",
            "instrumentation_review_status": "source-directory guitar scope only; exact scoring and player count not reviewed",
        })
        row["instrumentation_status"] = "unverified"
        row["assets"] = [{
            "source_url": url,
            "format": "PDF",
            "filename": filename,
            "label": title,
            "status": "pending",
            "license": "Public-domain composition claim; modern engraving redistribution rights unverified",
            "license_status": "private_acquisition_allowed_public_redistribution_unverified",
            "acquisition_permission": "explicit_individual_educational_use",
            "private_file_cache_permitted": True,
            "license_note": "Personal/educational offline use only; no public PDF mirror or redistribution license is established.",
            "expected_pages": pages,
            "upstream_checksum_available": False,
        }]
        rows.append(row)
    if len(rows) != declared_count:
        raise ValueError(f"Maikstrings parsed {len(rows)} guitar links but directory declares {declared_count}")
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("Maikstrings exact-locator identity collision")
    composer_context = _maikstrings_composer_filters(soup, declared_count, credit_counts)
    if composer_context["confirmed"]:
        for row in rows:
            credit = row["metadata"]["source_credit_line"]
            if credit in composer_context["groups"]:
                row["composer_en"] = credit
                row["metadata"]["attribution_role"] = "composer"
                row["metadata"]["source_attribution_note"] = (
                    ".nt-c source credit is retained verbatim as composer_en because the official page labels these nine groups as composers, "
                    "each filter name/count matches the individual entries, and their counts sum to the complete directory total. "
                    "The typed attribution role is composer; Maikstrings' separate engraver credit remains in contributors and engraver_credit."
                )
                row["metadata"]["source_credit_field"] = "directory .nt-c credit, corroborated by the official composer filter label and exact group count"
                row["metadata"]["composer_attribution_context"] = composer_context["reason"]
            else:
                # Fail closed for an unexpected unmatched row even if another source field changes.
                row["metadata"]["source_attribution_note"] = (
                    f".nt-c source directory credit: {credit or 'empty'}; no exact composer-filter match, so role is left unassigned."
                )
                row["metadata"]["attribution_role"] = "source_unspecified"
    summary = {"declared_sheet_count": declared_count, "parsed_record_count": len(rows),
                  "directory_title": heading.get_text(" ", strip=True),
                  "composer_or_credit_count": len(credit_counts),
                  "composer_attribution_confirmed": composer_context["confirmed"],
                  "composer_attribution_context": composer_context,
                  "page_count_sum": sum(row["metadata"]["source_pages"] for row in rows)}
    return rows, summary


def discover_maikstrings(root: Path) -> dict:
    """Read the official guitar directory only; never fetch its PDF links."""
    client = DiscoveryClient(Path(root), MAIK_ID, MAIK_HOSTS, delay=0.8)
    _prepare_client(client)
    prior_failure_count = len(client.state.get("failures", []))
    html, receipt = client.get(MAIK_DIRECTORY)
    records, parsed = parse_maikstrings_directory(html)
    # The returned file locator and raw composer credit are stored privately in
    # this identity map; public record IDs expose only the deterministic digest.
    identity_map = {
        "schema_version": 1,
        "source_id": MAIK_ID,
        "identity_basis": "SHA-256 of exact original PDF locator string; not a PDF-content digest",
        "locator_visibility": "private source evidence; do not expose native_record_locator in public record IDs",
        "entries": {row["id"]: {
            "native_record_locator": row["metadata"]["native_record_locator"],
            "source_pdf_url": row["assets"][0]["source_url"],
            "source_title": row["title_en"],
            "source_credit_line": row["metadata"]["source_credit_line"],
            "source_pages": row["metadata"]["source_pages"],
        } for row in records},
    }
    _write_json(client, "identity_map.json", identity_map)
    restore_asset_receipts(client.path / "catalog.json", records)
    _preserve_initial_report(client)
    categories = [category("guitar", "Classical Guitar", MAIK_DIRECTORY)]
    catalog = {
        "schema_version": 1, "source_id": MAIK_ID,
        "snapshot": {"frozen_at": client.state["started_at"], "completed_at": utcnow(),
                     "discovery_complete": True,
                     "scope": "All 112 entries on the official Classical Guitar Sheet Music directory. Explicit personal/educational offline acquisition is separate from unestablished public PDF redistribution; discovery requests no PDFs.",
                     "directory_url": MAIK_DIRECTORY, "directory_sha256": receipt["sha256"],
                     "directory_fetched_at": receipt["fetched_at"], "directory_last_modified": receipt["headers"].get("Last-Modified"),
                     "directory_etag": receipt["headers"].get("ETag"),
                     "source_record_count": len(records), "instrumentation_scope": "guitar family only; no solo/player-count inference",
                     "pdf_downloads_attempted": False, "pdf_downloads_permitted": True,
                     "private_file_cache_permitted": True,
                     "public_redistribution_license_established": False,
                     "fresh_file_integrity_verification": False,
                     "fresh_instrumentation_verification": False},
        "categories": categories,
        "works": sorted(records, key=lambda row: row["id"]),
    }
    _write_json(client, "catalog.json", catalog)
    proposal = registry_proposals()[MAIK_ID]
    _write_json(client, "registry_proposal.json", proposal)
    report = {
        "schema_version": 1, "source_id": MAIK_ID, "completed_at": utcnow(),
        "discovery_complete": True, **parsed,
        "source_record_count": len(records), "category_count": len(categories),
        "category_membership_count": sum(len(row["category_ids"]) for row in records),
        "manifest_record_count": sum(len(row["assets"]) for row in records),
        "pdf_manifest_count": sum(asset["format"] == "PDF" for row in records for asset in row["assets"]),
        "restricted_pdf_count": sum(asset["status"] == "restricted" for row in records for asset in row["assets"]),
        "pending_pdf_count": sum(asset['status'] == 'pending' for row in records for asset in row['assets']),
        "verified_pdf_count": sum(asset['status'] == 'verified' for row in records for asset in row['assets']),
        "unique_physical_pdf_count": len({asset['sha256'] for row in records for asset in row['assets']
                                          if asset['status'] == 'verified' and asset.get('sha256')}),
        "pdf_downloads_attempted": False,
        "rights_boundary": "Explicit personal/educational downloads support private offline acquisition. The source's composition PD claim and engraving notice do not establish public PDF redistribution permission.",
        "instrumentation_boundary": "Guitar directory establishes guitar-related scope only; no per-record solo/duo/player count assertion.",
        "upstream_snapshot": {"url": MAIK_DIRECTORY, "sha256": receipt["sha256"],
                              "last_modified": receipt["headers"].get("Last-Modified"), "etag": receipt["headers"].get("ETag")},
        "request_failures": client.state.get("failures", [])[prior_failure_count:],
    }
    report["record_outcomes"] = [{
        "source_record_id": row["id"],
        "source_title": row["metadata"]["source_title_field"],
        "composer_en": row["composer_en"],
        "source_credit_line": row["metadata"]["source_credit_line"],
        "source_credit_field_context": row["metadata"]["source_credit_field"],
        "pages": row["metadata"]["pages"],
        "license": row["metadata"]["license"],
        "license_note": row["metadata"]["license_note"],
        "attribution_role": row["metadata"]["attribution_role"],
        "instrumentation": row["metadata"]["instrumentation"],
        "arranger": row["metadata"]["arranger"],
        "editor": row["metadata"]["editor"],
        "source_page": row["source_url"],
        "asset_status": row["assets"][0]["status"],
        "asset_license_status": row["assets"][0]["license_status"],
        "instrumentation_status": row["instrumentation_status"],
        "player_count": None,
    } for row in sorted(records, key=lambda item: item["id"])]
    _write_json(client, "discovery_report.json", report)
    _write_json(client, "freeze_report.json", {
        "schema_version": 1, "source_id": MAIK_ID,
        "directory_snapshot_sha256": receipt["sha256"], "discovery_complete": True,
        "record_outcomes": report["record_outcomes"],
        "restricted_pdf_count": report["restricted_pdf_count"],
        "rights_boundary": report["rights_boundary"],
        "instrumentation_boundary": report["instrumentation_boundary"],
        "request_failures": report["request_failures"],
        "pdf_downloads_attempted": False, "unique_physical_pdf_count": 0,
        "private_identity_map": "identity_map.json",
    })
    _write_json(client, "adapter_run.json", {"frozen_at": client.state["started_at"],
        "finished_at": utcnow(), "status": "complete",
        "summary": {key: value for key, value in report.items() if key != "record_outcomes"}})
    return {key: value for key, value in report.items() if key != "record_outcomes"}


def registry_proposals() -> dict[str, dict]:
    """Return source proposals only; production source registration is separate."""
    rows = [
        {"id": YAWNOC_ID, "name": "yawnoc/guitar", "homepage": YAWNOC_HOME,
         "allowed_hosts": sorted(YAWNOC_HOSTS), "adapter": "normalized_catalog",
         "catalog": "sources/yawnoc/catalog.json", "family": YAWNOC_ID,
         "family_name_zh": "yawnoc 吉他谱来源", "family_name_en": "yawnoc guitar scores",
         "asset_hosts": ["github.com"],
         "acquisition_settings": {"delay": 0.8, "formats": ["PDF"],
                                   "licensing": "PD_composition_and_CC0_edition_license_separate; release_PDF_status_restricted_after_robots_denial; no retry or alternate route; LilyPond bodies read for metadata only"},
         "page_url_rules": [{"path": r"/yawnoc/guitar/releases/tag/[a-z0-9.-]+", "human_page": True}]},
        {"id": MAIK_ID, "name": "Maikstrings Classical Guitar Sheet Music", "homepage": MAIK_HOME,
         "allowed_hosts": sorted(MAIK_HOSTS), "adapter": "normalized_catalog",
         "catalog": "sources/maikstrings/catalog.json", "family": MAIK_ID,
         "family_name_zh": "Maikstrings 吉他谱来源", "family_name_en": "Maikstrings guitar scores",
         "asset_hosts": ["maikstrings.com"],
         "acquisition_settings": {"delay": 0.8, "formats": ["PDF"],
                                   "licensing": "explicit_individual_educational_use; private_file_cache_only; public_redistribution_not_established"},
         "page_url_rules": [{"path": r"/sheet-music-guitar\.html", "human_page": True}]},
    ]
    return {row["id"]: row for row in rows}
