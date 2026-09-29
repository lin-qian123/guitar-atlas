"""Build the offline entry from the public template and shared search assets."""

from __future__ import annotations

import hashlib
import copy
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path, PurePosixPath

from export_public_site import PROJECT_ROOT, build_public_catalog, configured_categories, read_json
from imslp_library.storage import _validate_pdf
from catalog_sources import load_registry, source_catalog


def validate_readable_pdf(path: Path) -> None:
    with path.open("rb") as handle:
        if handle.read(5) != b"%PDF-":
            raise ValueError("source is not a PDF")
    try:
        _validate_pdf(path)
    except ValueError:
        # Some legacy PDFs use /Encrypt null, which pypdf cannot handle.
        # A second real parser may verify them; no bytes or permissions change.
        pdfinfo = shutil.which("pdfinfo")
        if not pdfinfo:
            raise
        result = subprocess.run([pdfinfo, str(path)], capture_output=True, text=True,
                                timeout=30, env={**os.environ, "LC_ALL": "C"})
        pages = re.search(r"^Pages:\s+([1-9][0-9]*)\s*$", result.stdout, re.MULTILINE)
        unencrypted = re.search(r"^Encrypted:\s+no\s*$", result.stdout, re.MULTILINE)
        if result.returncode or not pages or not unencrypted:
            raise ValueError("PDF structure is invalid")


def checked_score(root: Path, category: str, record: dict, *, metadata_only: bool = False) -> dict | None:
    """Expose only category-local, structurally valid, source-matching scores."""
    relative = record.get("relative_path", "")
    parts = PurePosixPath(relative)
    if not relative or parts.is_absolute() or ".." in parts.parts or "\\" in relative:
        return None
    if not parts.parts or parts.parts[0] != "scores":
        return None
    path = root / category / relative
    try:
        if not path.resolve().is_relative_to(root) or not path.is_file():
            return None
        before = path.stat()
        size = record.get("download_expected_size") or record.get("expected_size")
        if size and before.st_size != int(size):
            return None
        content_hash = ""
        if metadata_only:
            if not before.st_size:
                return None
        else:
            validate_readable_pdf(path)
            expected = record.get("download_sha1") or record.get("sha1_imslp")
            sha1, sha256 = hashlib.sha1(), hashlib.sha256()
            with path.open("rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    sha1.update(block)
                    sha256.update(block)
            if expected and sha1.hexdigest() != expected:
                return None
            content_hash = sha256.hexdigest()
        after = path.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            return None
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
        return None
    return {
        "label": record.get("description") or record.get("filename") or parts.name,
        "href": urllib.parse.quote(f"{category}/{relative}", safe="/._-~()"),
        "_sha256": content_hash,
    }


def checked_reused_imslp_asset(root: Path, asset: dict, *, metadata_only: bool = False) -> dict | None:
    """Reuse an approved existing score only with exact manifest evidence."""
    reference = asset.get("reused_from_manifest", "")
    if not isinstance(reference, str):
        return None
    parts = PurePosixPath(reference)
    if len(parts.parts) != 3 or parts.parts[1:] != ("metadata", "score_manifest.json"):
        return None
    category = parts.parts[0]
    try:
        if category not in {row["name"] for row in configured_categories(root)}:
            return None
        records = read_json(root / reference)
        matches = [row for row in records if str(row.get("file_id")) == asset.get("imslp_file_id")
                   and str(row.get("work_id")) == asset.get("imslp_work_id")]
        if len(matches) != 1:
            return None
        record = matches[0]
        expected_sha1 = record.get("download_sha1") or record.get("sha1_imslp")
        if (not expected_sha1 or expected_sha1 != asset.get("sha1")
                or expected_sha1 != asset.get("source_sha1")
                or asset.get("local_path") != f'{category}/{record["relative_path"]}'):
            return None
        review_path = root / "config/score_exclusions.json"
        if review_path.is_file() and any(
            row["category"] == category and str(row["work_id"]) == asset["imslp_work_id"]
            and row["filename"] == record.get("filename")
            for row in read_json(review_path)["entries"]
        ):
            return None
        score = checked_score(root, category, record, metadata_only=metadata_only)
        if (score is None or (not metadata_only and score["_sha256"] != asset.get("sha256"))
                or (root / asset["local_path"]).stat().st_size != asset.get("size")):
            return None
        score["label"] = asset.get("label") or score["label"]
        return score
    except (OSError, ValueError, KeyError, TypeError):
        return None


def checked_source_asset(root: Path, source_id: str, asset: dict, *, metadata_only: bool = False) -> dict | None:
    """Validate a new adapter's immutable object before exposing a local link."""
    if asset.get("status") != "verified" or asset.get("format") != "PDF":
        return None
    if asset.get("storage_source") == "imslp":
        return checked_reused_imslp_asset(root, asset, metadata_only=metadata_only)
    relative = asset.get("local_path", "")
    parts = PurePosixPath(relative)
    if (asset.get("status") != "verified" or asset.get("format") != "PDF"
            or not relative or parts.is_absolute() or ".." in parts.parts or "\\" in relative
            or parts.parts[:2] != ("sources", source_id)):
        return None
    expected = asset.get("sha256", "")
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        return None
    path = root / relative
    try:
        if not path.resolve().is_relative_to((root / "sources" / source_id).resolve()) or not path.is_file():
            return None
        before = path.stat()
        if not before.st_size or before.st_size != asset.get("size"):
            return None
        if not metadata_only:
            validate_readable_pdf(path)
            with path.open("rb") as handle:
                if hashlib.file_digest(handle, "sha256").hexdigest() != expected:
                    return None
        after = path.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            return None
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
        return None
    return {"label": asset.get("label") or "PDF", "href": urllib.parse.quote(relative, safe="/._-~()"),
            "_sha256": "" if metadata_only else expected}


def offline_input_fingerprint(root: Path) -> dict:
    """Hash small source/configuration inputs, never score-file contents."""
    paths = {Path("config") / name for name in
             ("categories.json", "mixed_categories.json", "sources.json", "score_exclusions.json")}
    paths.update(Path(row["name"]) / "metadata/score_manifest.json" for row in configured_categories(root))
    if (root / "config/sources.json").is_file():
        paths.update(Path(row["catalog"]) for row in load_registry(root) if row["adapter"] == "normalized_catalog")
    inputs = {}
    for relative in sorted(paths):
        path = root / relative
        if relative.is_absolute() or ".." in relative.parts or not path.resolve().is_relative_to(root):
            raise ValueError("offline input must remain inside the library")
        inputs[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return {"schema_version": 1, "inputs": inputs}


def build_offline_catalog(root: Path, *, _metadata_only: bool = False, _data: dict | None = None) -> tuple[dict, dict]:
    """Build editions; the private fast mode is only for comparing an old snapshot."""
    root = root.resolve()
    fingerprint = offline_input_fingerprint(root)
    data = build_public_catalog(root) if _data is None else _data
    works = {work["id"]: work for work in data["works"]}
    editions = {}
    jobs = []
    exclusions_path = root / "config/score_exclusions.json"
    exclusions = {}
    if exclusions_path.is_file():
        review = read_json(exclusions_path)
        if review.get("schema_version") != 1:
            raise ValueError("invalid score membership review")
        exclusions = {(row["category"], row["work_id"], row["filename"]): row["reason"] for row in review["entries"]}
    excluded_categories = {key[0] for key in exclusions}
    for work in works.values():
        work["local_editions"] = []
    for category in data["categories"]:
        category_id, name = category["id"], category["name"]
        if category.get("source_id", "imslp") != "imslp":
            continue
        if name not in excluded_categories and (root / name / "index.html").is_file():
            category["local_href"] = urllib.parse.quote(f"{name}/index.html", safe="/._-~()")
        for work in works.values():
            if category_id in work["category_ids"]:
                edition = {"category_id": category_id, "files": [], "unavailable_count": 0}
                editions[(category_id, work["id"])] = edition
                work["local_editions"].append(edition)
        manifest = read_json(root / name / "metadata/score_manifest.json")
        if not isinstance(manifest, list):
            raise ValueError(f"invalid score manifest: {name}")
        for record in manifest:
            key = (category_id, str(record["work_id"]))
            if key not in editions:
                raise ValueError(f"manifest work not in category: {name}, {key[1]}")
            reason = exclusions.get((name, str(record["work_id"]), record.get("filename", "")))
            jobs.append((key, name, record, reason))
    downloaded = 0
    unique_hashes = set()
    source_hashes = {"imslp": set()}
    source_records = {"imslp": {"pdf_records": len(jobs), "verified_records": 0}}
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = pool.map(lambda job: None if job[3] else checked_score(root, job[1], job[2], metadata_only=_metadata_only), jobs)
        for index, (job, score) in enumerate(zip(jobs, results, strict=True), 1):
            edition = editions[job[0]]
            if score is None:
                edition["unavailable_count"] += 1
                if job[3]:
                    edition["excluded_count"] = edition.get("excluded_count", 0) + 1
                    edition["exclusion_reason"] = job[3]
            else:
                content_hash = score.pop("_sha256")
                if content_hash:
                    unique_hashes.add(content_hash)
                    source_hashes["imslp"].add(content_hash)
                edition["files"].append(score)
                downloaded += 1
                source_records["imslp"]["verified_records"] += 1
            if len(jobs) > 1000 and index % 2000 == 0:
                print(f"Checked {index}/{len(jobs)} score records", file=sys.stderr, flush=True)
    total_records = len(jobs)
    if (root / "config/sources.json").is_file():
        for source in load_registry(root):
            if source["adapter"] != "normalized_catalog":
                continue
            raw = source_catalog(root, source)
            asset_jobs = []
            for row in raw["works"]:
                for asset in row.get("assets", []):
                    if asset.get("format") != "PDF":
                        continue
                    members = asset.get("members", [])
                    if asset.get("container") == "ZIP" and members:
                        asset_jobs.extend((row["id"], {**asset, **member, "label": member.get("name") or asset.get("label") or "PDF"}) for member in members)
                    else:
                        asset_jobs.append((row["id"], asset))
            source_records[source["id"]] = {"pdf_records": len(asset_jobs), "verified_records": 0}
            source_hashes[source["id"]] = set()
            total_records += len(asset_jobs)
            for row in raw["works"]:
                for category_id in works[row["id"]]["category_ids"]:
                    edition = {"category_id": category_id, "files": [], "unavailable_count": 0}
                    editions[(category_id, row["id"])] = edition
                    works[row["id"]]["local_editions"].append(edition)
            with ThreadPoolExecutor(max_workers=8) as pool:
                scores = pool.map(lambda job: checked_source_asset(root, source["id"], job[1], metadata_only=_metadata_only), asset_jobs)
                for (work_id, asset), score in zip(asset_jobs, scores, strict=True):
                    if score:
                        content_hash = score.pop("_sha256")
                        if content_hash:
                            unique_hashes.add(content_hash)
                            source_hashes[source["id"]].add(content_hash)
                        downloaded += 1
                        source_records[source["id"]]["verified_records"] += 1
                    for category_id in works[work_id]["category_ids"]:
                        edition = editions[(category_id, work_id)]
                        if score:
                            edition["files"].append(score)
                        else:
                            edition["unavailable_count"] += 1
    # This payload is never written into public_site/.
    data.pop("integrity", None)
    if not _metadata_only:
        for source_id, hashes in source_hashes.items():
            source_records[source_id]["unique_pdf_contents"] = len(hashes)
    report = {
        "categories": len(data["categories"]),
        "works": data["summary"]["category_record_count"],
        "unique_works": len(works),
        "pdf_records": total_records,
        "downloaded": downloaded,
        "unavailable": total_records - downloaded,
        "by_source": source_records,
        "excluded_memberships": sum(bool(job[3]) for job in jobs),
    }
    if not _metadata_only:
        report["unique_pdf_contents"] = len(unique_hashes)
    if offline_input_fingerprint(root) != fingerprint:
        raise ValueError("offline source/configuration inputs changed during validation; retry the render")
    data["offline_inputs"] = fingerprint
    data["offline_summary"] = report
    return data, report


def write_offline_page(root: Path, data: dict, report: dict) -> dict:
    """Render an already checked snapshot without reopening every score."""
    root = root.resolve()
    payload = {"data": data, "aliases": read_json(PROJECT_ROOT / "public_site/data/search-aliases.json")}
    embedded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    page = (PROJECT_ROOT / "public_site/index.html").read_text(encoding="utf-8")
    page = page.replace('href="assets/', 'href="public_site/assets/').replace('src="assets/', 'src="public_site/assets/')
    page = page.replace('href="./"', 'href="index.html"')
    page = page.replace("<title>Guitar Atlas｜", "<title>Guitar Atlas 离线版｜")
    page = page.replace("<title>IMSLP Guitar｜", "<title>Guitar Atlas 离线版｜")
    page = page.replace('lang="en">IMSLP GUITAR CATALOG', 'lang="en">IMSLP GUITAR · OFFLINE')
    page = page.replace("基于 IMSLP 的吉他曲目目录。", "基于 IMSLP 的吉他曲目目录 · 离线版。")
    page = page.replace("乐谱下载与使用条件以各来源原页说明为准。", "本地已验证 PDF 可直接打开，未就绪文件可查看来源原页。使用条件以原页说明为准。")
    page = page.replace("乐谱与使用条件请查看各来源页面。", "已验证的本地 PDF 可直接打开；未就绪文件保留提示。使用条件请查看各来源页面。")
    page = page.replace('</head>', '<link rel="stylesheet" href="scripts/assets/offline-catalog.css">\n</head>')
    page = page.replace('<script src="public_site/assets/app.js" defer>', '<script src="scripts/assets/offline-catalog.js" defer></script>\n  <script src="public_site/assets/app.js" defer>')
    page = page.replace('</body>', f'<script type="application/json" id="offline-data">{embedded}</script>\n</body>')
    destination = root / "index.html"
    if destination.exists() and destination.read_text(encoding="utf-8") != page:
        backup = root / "backups/offline-ui" / f'index-{datetime.now().strftime("%Y%m%d-%H%M%S-%f")}.html'
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(destination, backup)
    descriptor, temporary = tempfile.mkstemp(prefix=".index-", suffix=".tmp", dir=root)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(page)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        destination.chmod(0o644)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {**report, "index": str(destination)}


def render(root: Path) -> dict:
    data, report = build_offline_catalog(root)
    return write_offline_page(root, data, report)


def refresh_display_metadata(root: Path) -> dict:
    """Refresh translations/UI while retaining the previous verified file snapshot.

    This is intentionally not a PDF integrity check. Source identities, original
    titles, memberships and formats must be unchanged. A full render is required
    after acquisition, file, manifest or instrumentation changes.
    """
    root = root.resolve()
    page = (root / "index.html").read_text(encoding="utf-8")
    matches = re.findall(r'<script type="application/json" id="offline-data">(.*?)</script>', page, re.S)
    if len(matches) != 1:
        raise ValueError("metadata refresh requires one previously verified offline snapshot")
    previous = json.loads(matches[0])["data"]
    inputs = offline_input_fingerprint(root)
    if "offline_inputs" in previous and previous["offline_inputs"] != inputs:
        raise ValueError("offline manifest/configuration inputs changed; run a full offline render")
    current = build_public_catalog(root)
    from validate_public_site import validate_payload
    validate_payload(current)
    for collection, fields in (("works", ("id", "source_id", "source_record_id", "title_en", "composer_en", "category_ids", "formats", "resource_type", "source_url")),
                               ("categories", ("id", "source_id", "source_category_id", "name", "kind", "family", "source_url"))):
        old = {row["id"]: row for row in previous[collection]}
        if len(old) != len(previous[collection]) or set(old) != {row["id"] for row in current[collection]}:
            raise ValueError(f"{collection} identities changed; run a full offline render")
        for row in current[collection]:
            before = old[row["id"]]
            if collection == "works":
                from catalog_translations import display_source_title
                before = {**before, "title_en": display_source_title(before["title_en"])}
            if any(before.get(key) != row.get(key) for key in fields):
                raise ValueError(f"{collection} source metadata changed: {row['id']}; run a full offline render")
    # Reuse the production membership/exclusion/archive logic without reading
    # score bytes. This also bootstraps legacy pages that lack input fingerprints:
    # every old part, unavailable count and legacy-page link must agree exactly.
    current, mapping_report = build_offline_catalog(root, _metadata_only=True, _data=current)
    if current["offline_inputs"] != inputs:
        raise ValueError("offline inputs changed during metadata refresh; retry the render")
    for collection, key in (("works", "local_editions"), ("categories", "local_href")):
        old = {row["id"]: row for row in previous[collection]}
        for row in current[collection]:
            if row.get(key) != old[row["id"]].get(key):
                raise ValueError(f"offline links/availability or exclusions changed: {row['id']}; run a full offline render")
    old_report = previous["offline_summary"]
    for key, value in mapping_report.items():
        if key == "by_source":
            prior = old_report.get(key, {})
            if set(prior) != set(value) or any(prior[source].get(field) != count
                    for source, counts in value.items() for field, count in counts.items()):
                raise ValueError("offline source availability counts changed; run a full offline render")
        elif old_report.get(key) != value:
            raise ValueError("offline availability counts changed; run a full offline render")
    # Check every retained link stays within the library and still exists.
    hrefs = {file["href"] for work in current["works"] for edition in work["local_editions"] for file in edition["files"]}
    hrefs.update(category["local_href"] for category in current["categories"] if category.get("local_href"))
    for href in hrefs:
        parsed = urllib.parse.urlsplit(href)
        relative = urllib.parse.unquote(parsed.path)
        parts = PurePosixPath(relative)
        path = root / relative
        if (parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or "\\" in relative
                or parts.is_absolute() or ".." in parts.parts or not path.resolve().is_relative_to(root)
                or not path.is_file() or not path.stat().st_size):
            raise ValueError("retained offline link is unsafe or unavailable; run a full offline render")
    current.pop("integrity", None)
    report = copy.deepcopy(previous["offline_summary"])
    current["offline_summary"] = report
    if offline_input_fingerprint(root) != inputs:
        raise ValueError("offline inputs changed during metadata refresh; retry the render")
    result = write_offline_page(root, current, report)
    result["refresh_method"] = "display metadata, manifest/exclusion mapping and file existence/size only; preceding PDF integrity checks retained"
    result["input_guard"] = "checked existing fingerprint" if "offline_inputs" in previous else "bootstrapped from matching legacy link/availability mapping"
    result["checked_local_paths"] = len(hrefs)
    return result
