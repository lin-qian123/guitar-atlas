"""Resumable source-owned catalog adapters for the approved expansion scope.

The adapters retain native page/CMS/file identities.  Public factual catalog
navigation and permission to acquire score bytes are recorded independently.
No adapter downloads files, purchases items, logs in, or bypasses robots/access
challenges.  Raw responses and request journals remain under ignored sources/.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

USER_AGENT = "GuitarAtlas/1.0 (source-attributed guitar catalog; polite metadata discovery)"


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def atomic_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + ".part")
    pending.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pending.replace(path)


def text(value) -> str:
    return BeautifulSoup(str(value or ""), "html.parser").get_text(" ", strip=True)


def page_url(url: str) -> str | None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return None
    if re.search(r"\.(?:pdf|mid|midi|gpx|gp[3-8]|zip|jpe?g|png|webp|mp3|mp4)$", parsed.path, re.I):
        return None
    if "/wp-content/" in parsed.path:
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def robots_allows(body: str, agent: str, url: str) -> bool:
    """Match robots wildcards and longest Allow/Disallow rather than prefix only.

    urllib.robotparser does not implement wildcard paths.  Query-bearing API
    paths therefore need an explicit matcher to obey rules such as /*?.
    """
    groups, names, rules = [], [], []
    directives_started = False
    for line in body.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = [part.strip() for part in line.split(":", 1)]
        key = key.casefold()
        if key == "user-agent":
            if directives_started:
                groups.append((names, rules)); names, rules = [], []
                directives_started = False
            names.append(value.casefold())
        elif key in {"allow", "disallow"} and names:
            directives_started = True
            if value:
                rules.append((key, value))
    if names:
        groups.append((names, rules))
    matches = [(max((len(name) for name in names if name != "*" and name in agent.casefold()), default=0), rules)
               for names, rules in groups if "*" in names or any(name in agent.casefold() for name in names)]
    if not matches:
        return True
    specificity = max(value for value, _ in matches)
    parsed = urlsplit(url); target = parsed.path + (("?" + parsed.query) if parsed.query else "")
    selected = []
    for score, rows in matches:
        if score != specificity:
            continue
        for rule, pattern in rows:
            regex = "^" + re.escape(pattern).replace(r"\*", ".*")
            if pattern.endswith("$"):
                regex = regex[:-2] + "$"
            if re.search(regex, target):
                selected.append((len(pattern.replace("*", "").rstrip("$")), rule == "allow"))
    return max(selected, default=(0, True))[1]


class DiscoveryClient:
    def __init__(self, root: Path, source_id: str, hosts: set[str], *, delay: float = 0.6):
        self.root, self.source_id, self.hosts = root, source_id, hosts
        self.path = root / "sources" / source_id
        self.path.mkdir(parents=True, exist_ok=True)
        self.state_path = self.path / "discovery_state.json"
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {
            "schema_version": 1, "source_id": source_id, "started_at": utcnow(), "requests": {}, "failures": []}
        self.session = requests.Session(); self.session.headers["User-Agent"] = USER_AGENT
        self.delay, self.last_request = delay, 0.0
        self.robots = {}
        self.page_count = 0

    def _raw(self, url: str):
        wait = self.delay - (time.monotonic() - self.last_request)
        if wait > 0:
            time.sleep(wait)
        self.last_request = time.monotonic()
        response = self.session.get(url, timeout=(12, 40))
        if urlsplit(response.url).hostname not in self.hosts:
            raise ValueError("redirect left approved source hosts: " + response.url)
        return response

    def allowed(self, url: str) -> bool:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in self.hosts:
            raise ValueError("URL outside approved HTTPS source hosts: " + url)
        origin = parsed.scheme + "://" + parsed.netloc
        if origin not in self.robots:
            roboturl = origin + "/robots.txt"
            probe = self.path / "probe.json"
            initial = self.path / "pages/robots.txt"
            if probe.exists() and initial.exists() and json.loads(probe.read_text()).get("robots_url") == roboturl:
                status = json.loads(probe.read_text())["robots_status"]; body = initial.read_text()
            else:
                r = self._raw(roboturl); status, body = r.status_code, r.text
                atomic_json(self.path / "robots_check.json", {"checked_at": utcnow(), "url": roboturl, "status": status})
                (self.path / "robots.txt").write_text(body)
            self.robots[origin] = (status, body)
        status, body = self.robots[origin]
        return status == 404 or status == 200 and robots_allows(body, USER_AGENT, url)

    def get(self, url: str) -> tuple[bytes, dict]:
        if not self.allowed(url):
            raise PermissionError("robots or unavailable robots prevents discovery: " + url)
        key = hashlib.sha256(url.encode()).hexdigest()
        cache = self.path / "pages" / (key + ".response")
        cache.parent.mkdir(exist_ok=True)
        previous = self.state["requests"].get(url, {})
        if previous.get("human_verification_required"):
            raise PermissionError("human verification remains pending: " + url)
        if previous.get("status") == 200 and cache.exists():
            data = cache.read_bytes()
            if hashlib.sha256(data).hexdigest() != previous["sha256"]:
                raise ValueError("discovery cache checksum changed")
            self.page_count += 1
            return data, previous
        # Reuse the freshly checked directory from the scope probe.
        probe_path = self.path / "probe.json"
        if probe_path.exists():
            probe = json.loads(probe_path.read_text())
            initial = self.path / "pages/directory.html"
            if probe.get("directory_url") == url and probe.get("directory_status") == 200 and initial.exists():
                data = initial.read_bytes(); record = {"status": 200, "fetched_at": probe["checked_at"],
                    "final_url": probe["final_url"], "sha256": hashlib.sha256(data).hexdigest(),
                    "cache": str(cache.relative_to(self.path)), "attempts": 1, "headers": {}}
                cache.write_bytes(data); self.state["requests"][url] = record
                atomic_json(self.state_path, self.state); self.page_count += 1
                return data, record
        attempts = previous.get("attempts", 0) + 1
        try:
            r = self._raw(url); record = {"status": r.status_code, "fetched_at": utcnow(), "final_url": r.url,
                "attempts": attempts, "headers": {k: v for k, v in r.headers.items() if k.lower() in {
                    "content-type", "x-wp-total", "x-wp-totalpages", "etag", "last-modified"}}}
            if r.status_code == 200 and any(value in r.text[:10000].casefold() for value in (
                    "cf-chl-", "verify you are human", "captcha-container")):
                record["human_verification_required"] = True
                self.state["requests"][url] = record; atomic_json(self.state_path, self.state)
                raise PermissionError("human verification required: " + url)
            if r.status_code == 200:
                data = r.content; record["sha256"] = hashlib.sha256(data).hexdigest()
                record["cache"] = str(cache.relative_to(self.path)); cache.write_bytes(data)
            self.state["requests"][url] = record; atomic_json(self.state_path, self.state)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {url}")
            self.page_count += 1
            return data, record
        except Exception as exc:
            self.state["failures"].append({"url": url, "at": utcnow(), "error": str(exc)})
            atomic_json(self.state_path, self.state); raise

    def soup(self, url: str):
        data, record = self.get(url)
        return BeautifulSoup(data, "html.parser"), record


def category(identity: str, name: str, url: str, **kwargs) -> dict:
    return {"id": identity, "name": name, "kind": "unspecified", "source_url": url, **kwargs}


def work(sid: str, native: str, title: str, composer: str, url: str, cats: list[str], *, formats=None,
         assets=None, metadata=None, resource_type="score", instrumentation_status="unspecified") -> dict:
    return {"id": sid + ":" + native, "title_en": title, "composer_en": composer,
            "source_url": url, "category_ids": sorted(set(cats)), "formats": formats or [],
            "instrumentation_status": instrumentation_status, "resource_type": resource_type,
            "assets": assets or [], "metadata": metadata or {}}


def asset(url: str, *, permitted=False, license="unspecified") -> dict:
    filename = urlsplit(url).path.rsplit("/", 1)[-1]
    return {"source_url": url, "format": "PDF", "filename": filename,
            "status": "pending" if permitted else "restricted", "license": license,
            "acquisition_permission": "individual_noncommercial" if permitted else "unverified",
            "upstream_checksum_available": False}


def delcamp_record_id(native_path: str) -> str:
    """Opaque surrogate for a source that exposes PDF locators, not work IDs.

    The digest identifies the native locator string.  It is not a PDF-content
    checksum.  Keep the exact locator in the private source snapshot only.
    """
    return "pdf:" + hashlib.sha256(native_path.encode("utf-8")).hexdigest()


def guitardownunder_record_id(native_locator: str) -> str:
    """Preserve native page IDs; hide a file locator behind a stable surrogate."""
    if re.search(r"\.(?:pdf|mid|midi|gpx|gp[3-8]|zip)$", native_locator, re.I):
        return delcamp_record_id(native_locator)
    return native_locator


def restore_asset_receipts(path: Path, works: list[dict]) -> None:
    """Re-discovery must retain existing acquisition state for identical assets.

    An identical title is never a receipt match.  Matching uses source record
    identity (or an explicitly preserved legacy native locator) plus exact asset
    URL.  Source metadata and fresh acquisition restrictions remain adapter-owned.
    """
    if not path.exists():
        return
    old = json.loads(path.read_text(encoding="utf-8"))
    by_id = {row["id"]: row for row in old.get("works", [])}
    by_locator = {row.get("metadata", {}).get("native_record_locator", row["id"].split(":", 1)[-1]): row
                  for row in old.get("works", [])}
    receipt_fields = {"status", "local_path", "sha256", "size", "verified_at", "final_asset_url",
        "upstream_checksum_status", "attempts", "last_error", "attempted_at", "label",
        "sha1", "source_sha1", "reused_from_manifest", "imslp_file_id", "imslp_work_id"}
    for row in works:
        previous = by_id.get(row["id"]) or by_locator.get(row.get("metadata", {}).get("native_record_locator", ""))
        if not previous:
            continue
        old_assets = {item.get("source_url"): item for item in previous.get("assets", [])}
        for item in row.get("assets", []):
            saved = old_assets.get(item.get("source_url"))
            if not saved:
                continue
            if item.get("status") == "restricted" and saved.get("status") != "verified":
                # Newly restricted acquisition cannot inherit an old retry state.
                continue
            item.update({key: saved[key] for key in receipt_fields if key in saved})


def save_catalog(client: DiscoveryClient, name: str, homepage: str, categories: list, works: list,
                 scope: str, *, complete=True, extras=None) -> dict:
    restore_asset_receipts(client.path / "catalog.json", works)
    identities = {row["id"] for row in works}
    if len(identities) != len(works):
        raise ValueError("duplicate native source identity")
    used = {cid for row in works for cid in row["category_ids"]}
    categories = [row for row in categories if row["id"] in used]
    known = {row["id"] for row in categories}
    if used != known:
        raise ValueError("missing source category mapping")
    data = {"schema_version": 1, "source_id": client.source_id,
        "snapshot": {"frozen_at": client.state["started_at"], "completed_at": utcnow(),
            "discovery_complete": complete, "page_count": client.page_count, "scope": scope,
            "metadata_only": True, "fresh_file_integrity_verification": False,
            "fresh_instrumentation_verification": False, **(extras or {})},
        "categories": categories, "works": sorted(works, key=lambda row: row["id"])}
    atomic_json(client.path / "catalog.json", data)
    proposal = {"id": client.source_id, "name": name, "homepage": homepage,
        "allowed_hosts": sorted(client.hosts), "adapter": "normalized_catalog",
        "catalog": f"sources/{client.source_id}/catalog.json", "family": client.source_id,
        "family_name_zh": name + " 来源目录", "family_name_en": name + " collections"}
    atomic_json(client.path / "registry_proposal.json", proposal)
    report = {"schema_version": 1, "source_id": client.source_id, "completed_at": utcnow(),
        "scope": scope, "discovery_complete": complete, "source_record_count": len(works),
        "score_record_count": sum(row["resource_type"] == "score" for row in works),
        "reference_record_count": sum(row["resource_type"] == "reference" for row in works),
        "category_count": len(categories), "category_membership_count": sum(len(row["category_ids"]) for row in works),
        "manifest_record_count": sum(len(row["assets"]) for row in works), "verified_pdf_count": 0,
        "unique_physical_pdf_count": 0, "known_pdf_record_count": sum("PDF" in row["formats"] for row in works),
        "missing_composer_count": sum(not row["composer_en"] for row in works),
        "translation_status": "untranslated_pending_shared_translation_pipeline",
        "request_failures": client.state["failures"], "upstream_snapshot": extras or {}}
    atomic_json(client.path / "discovery_report.json", report)
    return report


def discover_cglib(root: Path) -> dict:
    client = DiscoveryClient(root, "cglib", {"www.cglib.org"}, delay=.6)
    homepage = "https://www.cglib.org/"
    index, _ = client.soup(homepage + "composers/")
    composer_links = {a["href"]: a.get_text(" ", strip=True) for a in index.select(".entry-content a[href]")
                      if "/category/" in a["href"]}
    base = homepage + "wp-json/wp/v2/"
    taxonomies = {}
    for taxonomy in ("categories", "tags"):
        records, page, totalpages = [], 1, 1
        while page <= totalpages:
            url = base + taxonomy + f"?per_page=100&page={page}&_fields=id,name,slug,parent,link,count"
            raw, request = client.get(url); rows = json.loads(raw)
            headers = {k.lower(): v for k, v in request["headers"].items()}
            totalpages = int(headers.get("x-wp-totalpages", 1)); records.extend(rows); page += 1
        taxonomies[taxonomy] = {row["id"]: row for row in records}
    cats, tags = taxonomies["categories"], taxonomies["tags"]
    atomic_json(client.path / "taxonomy.json", taxonomies)
    excluded_tags = {key for key, row in tags.items() if re.search(r"voice|nails|luthiers|tips", row["name"], re.I)}
    excluded_categories = {key for key, row in cats.items() if re.search(
        r"^(Accessories|Articles|Musicology|Video Tips|Videos|Uncategorized|Books)$", row["name"], re.I)}
    works, excluded, totalpages, total, page = {}, [], 1, None, 1
    # Ascending native IDs and a frozen total let resumptions preserve page order.
    while page <= totalpages:
        url = base + f"posts?per_page=100&page={page}&orderby=id&order=asc&_fields=id,link,title,categories,tags"
        raw, request = client.get(url); rows = json.loads(raw)
        headers = {k.lower(): v for k, v in request["headers"].items()}
        totalpages = int(headers.get("x-wp-totalpages", 1)); total = int(headers.get("x-wp-total", len(rows))) if total is None else total
        for item in rows:
            memberships = [cid for cid in item["categories"] if cid in cats]
            composers = [cats[cid]["name"] for cid in memberships if cats[cid]["link"] in composer_links]
            if (set(item["tags"]) & excluded_tags or set(memberships) & excluded_categories or not composers):
                excluded.append({"native_id": item["id"], "title": item["title"]["rendered"],
                    "category_ids": memberships, "tag_ids": item["tags"],
                    "reason": "non-score/composer index outside scope, voice, nails/luthier/tips"}); continue
            source_url = page_url(item["link"])
            if not source_url or urlsplit(source_url).hostname != "www.cglib.org":
                raise ValueError("invalid native CMS canonical link")
            tag_names = [tags[tag]["name"] for tag in item["tags"] if tag in tags]
            composer = "; ".join(composers)
            works[item["id"]] = work("cglib", str(item["id"]), text(item["title"]["rendered"]), composer,
                source_url, [str(cid) for cid in memberships], metadata={
                    "cms_post_id": item["id"], "original_title_markup": item["title"]["rendered"],
                    "original_composer_attributions": composers, "tags": tag_names,
                    "instrumentation": "; ".join(name for name in tag_names if "guitar" in name.casefold()) or None,
                    "license": "CC BY-SA 4.0 for site metadata; score-specific rights unspecified",
                    "file_acquisition": "requires_per_edition_rights_check", "identity_evidence": "native CMS ID and canonical link"})
        page += 1
        if page % 20 == 0:
            atomic_json(client.path / "partial_counts.json", {"pages_done": page - 1, "totalpages": totalpages, "records": len(works)})
            print(f"cglib: {page - 1}/{totalpages} pages; {len(works)} in-scope records", flush=True)
    atomic_json(client.path / "excluded_records.json", excluded)
    categories = [category(str(cid), row["name"], row["link"], parent_id=str(row["parent"])) for cid, row in cats.items()]
    return save_catalog(client, "Classical Guitar Library", homepage, categories, list(works.values()),
        "All publicly exposed CMS posts with composer-index category; exclude voice tags and non-score editorial/accessory categories; source instrumentation remains unverified",
        extras={"cms_total_posts": total, "cms_total_post_pages": totalpages, "excluded_record_count": len(excluded),
                "cms_returned_unique_post_count": len(works) + len(excluded), "composer_index_link_count": len(composer_links),
                "coverage_basis": "frozen CMS pagination; not a unique musical-work count"})


def discover_cantorion(root: Path) -> dict:
    client = DiscoveryClient(root, "cantorion", {"cantorion.org", "es.cantorion.org"}, delay=.65)
    base = "https://cantorion.org/"; directory = base + "musicsearch/instruments/Guitar"
    works, pages, expected = {}, 1, None
    complete, continuation_error = True, None
    exclusions = []
    for page in range(1, 1000):
        url = directory if page == 1 else directory + f"?page={page}&form_advanced__action="
        try:
            soup, request = client.soup(url)
        except PermissionError as exc:
            complete, continuation_error = False, str(exc)
            break
        if expected is None:
            content = soup.get_text(" ", strip=True)
            count = re.search(r"([\d,]+)\s+(?:pieces? found|pieces?|results found)", content, re.I)
            if count:
                expected = int(count[1].replace(",", "")); pages = (expected + 19) // 20
            numeric = [int(a.get_text(strip=True)) for a in soup.select('a[href*="page="]') if a.get_text(strip=True).isdigit()]
            pages = max([pages, *numeric])
        for entry in soup.select("li.music"):
            title_node = entry.select_one("li.title a[href]")
            if not title_node:
                continue
            href = title_node["href"]
            source_url = urljoin(base, href)
            native = re.search(r"/music/(\d+)/", source_url)
            if not native:
                continue
            fields = {}
            for label in entry.select("li.label"):
                value = label.find_next_sibling("li", class_="data")
                if value:
                    fields[label.get_text(" ", strip=True)] = value.get_text(" ", strip=True)
            instrumentation = fields.get("Instruments", fields.get("Instrument", ""))
            if re.search(r"voice|bass|electric|orchestra|choir|vocal", instrumentation, re.I):
                exclusions.append({"id": native[1], "fields": fields, "reason": "explicit excluded instrumentation"}); continue
            works[native[1]] = work("cantorion", native[1], title_node.get_text(" ", strip=True), fields.get("Composer", ""),
                source_url, ["guitar"], metadata={"instrumentation": instrumentation or None, "opus": fields.get("Opus"),
                    "source_fields": fields, "source_subtitle": text(entry.select_one(".subtitle")),
                    "license": fields.get("License", "unspecified"), "file_acquisition": "per_edition_rights_check_required",
                    "discovery_directory": directory})
        if page >= pages:
            break
    atomic_json(client.path / "excluded_records.json", exclusions)
    return save_catalog(client, "Cantorion", base, [category("guitar", "Guitar", directory)], list(works.values()),
        "Public Guitar instrument search pages allowed by current robots; pagination denials retained as an incomplete boundary; explicit voice/bass/electric/orchestra instrumentation excluded; mirrored editions preserve Cantorion IDs",
        complete=complete,
        extras={"source_search_stated_count": expected, "excluded_record_count": len(exclusions),
                "search_page_count": pages, "continuation_error": continuation_error, "no_cross_source_identity_merge": True})


def parse_classicalguitarorg(soup: BeautifulSoup, directory: str) -> tuple[list, list]:
    scope = soup.select_one(".singular-entry") or soup
    categories, works, current_category, composer = [], [], "", ""
    for node in scope.find_all(["h2", "h4", "a"]):
        if node.name == "h2":
            current_category = node.get_text(" ", strip=True)
            categories.append(category(current_category, current_category, directory)); composer = ""
        elif node.name == "h4":
            composer = node.get_text(" ", strip=True)
        elif node.name == "a" and any(c in node.get("class", []) for c in ["free-music", "free-exercise", "free-ebook"]):
            if not current_category:
                raise ValueError("score without section")
            native = node.get("id") or urlsplit(node["href"]).path.lstrip("/")
            href = urljoin(directory, node["href"]); title = node.get_text(" ", strip=True)
            resource_type = "reference" if "eBooks" in current_category else "score"
            assets = [asset(href)] if urlsplit(href).path.casefold().endswith(".pdf") else []
            works.append(work("classicalguitarorg", native, title, composer, directory, [current_category],
                formats=["PDF"] if assets else [], assets=assets, resource_type=resource_type,
                metadata={"composer": composer or None, "license": "score-specific policy; unspecified until edition checked",
                    "requires_email_subscription": native == "ebook-everynote",
                    "checkout_required": "gum.co" in href, "original_attribution_absent": not bool(composer)}))
    return categories, works


def discover_classicalguitarorg(root: Path) -> dict:
    client = DiscoveryClient(root, "classicalguitarorg", {"www.classicalguitar.org"}, delay=.65)
    homepage = "https://www.classicalguitar.org/"; directory = homepage + "free/"
    soup, _ = client.soup(directory); client.soup(homepage + "about/site-policies/")
    cats, works = parse_classicalguitarorg(soup, directory)
    return save_catalog(client, "ClassicalGuitar.org", homepage, cats, works,
        "Every explicitly labeled free-music, free-exercise and free-ebook entry in the Free Stuff directory; no newsletter subscription or checkout; books separately labeled references")


def discover_guitardownunder(root: Path) -> dict:
    client = DiscoveryClient(root, "guitardownunder", {"www.guitardownunder.com"}, delay=.65)
    homepage = "https://www.guitardownunder.com/"; categories, works, excluded = [], {}, []
    # The classical and guitar-ensemble/fingerstyle directories are explicitly selected.
    for path, name in (("classical.php", "Classical Guitar Music"), ("fingerstyle.php", "Fingerstyle Guitar Music"), ("ensemble.php", "Guitar Ensemble Music")):
        directory = homepage + path; soup, _ = client.soup(directory)
        categories.append(category(path, name, directory))
        for row in soup.select("table tr"):
            cells = row.find_all("td"); link = row.select_one('a[href*="_scores/"]')
            if not link or len(cells) < 2:
                continue
            href = urljoin(homepage, link["href"])
            native = urlsplit(href).path.split("/_scores/")[-1]
            title, composer = link.get_text(" ", strip=True), cells[0].get_text(" ", strip=True)
            source_url = page_url(href) or directory
            if native in works:
                if path not in works[native]["category_ids"]:
                    works[native]["category_ids"].append(path)
                # Responsive duplicate tables can disagree in their source wording.
                observed = works[native]["metadata"].setdefault("alternate_source_titles", [])
                if title != works[native]["title_en"] and title not in observed:
                    observed.append(title)
                continue
            if re.search(r"bass|voice|vocal|choir|orchestra|electric", title, re.I):
                excluded.append({"id": native, "title": title, "reason": "excluded explicit instrumentation"}); continue
            assets = [asset(href)] if href.casefold().endswith(".pdf") else []
            metadata = {"license": "All Rights Reserved; catalog navigation only", "discovery_directory": directory,
                        "native_record_locator": native,
                        "original_composer_attribution": composer}
            if source_url != directory:
                try:
                    detail, _ = client.soup(source_url)
                    for pdf in detail.select('a[href]'):
                        file_url = urljoin(source_url, pdf["href"])
                        if urlsplit(file_url).path.casefold().endswith(".pdf") and urlsplit(file_url).hostname in client.hosts:
                            if not any(a["source_url"] == file_url for a in assets): assets.append(asset(file_url))
                except Exception as exc:
                    metadata["detail_error"] = str(exc); metadata["unverified_detail_url"] = source_url; source_url = directory
            works[native] = work("guitardownunder", guitardownunder_record_id(native), title, composer, source_url, [path],
                formats=["PDF"] if assets else [], assets=assets, metadata=metadata)
    atomic_json(client.path / "excluded_records.json", excluded)
    mapping_path = client.path / "identity_map.json"
    existing_map = json.loads(mapping_path.read_text(encoding="utf-8")) if mapping_path.exists() else {}
    opaque = [row for row in works.values() if row["id"].startswith("guitardownunder:pdf:")]
    entries = dict(existing_map.get("entries", {}))
    entries.update({"guitardownunder:" + row["metadata"]["native_record_locator"]: row["id"] for row in opaque})
    atomic_json(mapping_path, {**existing_map, "schema_version": 1, "source_id": "guitardownunder", "entries": entries,
        "identity_basis": "SHA-256 of exact legacy native file locator string; not PDF content checksum",
        "records": {row["id"].split(":", 1)[1]: row["metadata"]["native_record_locator"] for row in opaque}})
    return save_catalog(client, "Guitar Downunder", homepage, categories, list(works.values()),
        "Complete classical, fingerstyle and ensemble tables; duplicate responsive tables merged by native score path; explicitly excluded instrument labels omitted",
        extras={"excluded_record_count": len(excluded)})


def discover_andrewyork(root: Path) -> dict:
    client = DiscoveryClient(root, "andrewyork", {"andrewyork.net"}, delay=.6)
    homepage = "https://andrewyork.net/"; directory = homepage + "sheetmusicdownloads.html"
    soup, _ = client.soup(directory)
    categories, works, excluded = {}, {}, []
    for link in soup.select("a.catalog-btn[href]"):
        row = link.find_parent("tr"); title_node = row.find("b") if row else None
        if not row or not title_node:
            continue
        heading = row.find_previous("h2")
        group = heading.get_text(" ", strip=True) if heading else "Unspecified"
        description = row.find("i"); context = description.get_text(" ", strip=True) if description else ""
        title = title_node.get_text(" ", strip=True); url = urljoin(directory, link["href"])
        native = urlsplit(url).path.split("/scores/")[-1]
        if group in {"Voice and Guitar", "Piano"} or re.search(r"contrabass|voice and|orchestra", context, re.I):
            excluded.append({"id": native, "title": title, "source_category": group, "reason": "explicit excluded/alternative instrumentation"}); continue
        categories[group] = category(group, group, directory)
        if native in works:
            if group not in works[native]["category_ids"]:
                works[native]["category_ids"].append(group)
            if title != works[native]["title_en"]:
                works[native]["metadata"].setdefault("alternate_source_titles", []).append(title)
            continue
        metadata = {"composer": "Andrew York", "original_catalog_section": group,
            "editor": None, "license": "copyrighted commercial edition; navigation only",
            "checkout_required": True, "record_level": "edition",
            "edition_context": context, "discovery_directory": directory}
        cells = row.find_all("td"); price = cells[1].get_text(" ", strip=True) if len(cells) > 1 else ""
        metadata["displayed_price"] = price
        if re.search(r"\b(?:collection|suite|pieces)\b", title, re.I):
            metadata["record_level"] = "collection"
        if source_url := page_url(url):
            try:
                client.soup(source_url)
            except Exception as exc:
                metadata.update(detail_error=str(exc), unverified_detail_url=source_url); source_url = directory
        else:
            source_url = directory
        works[native] = work("andrewyork", native, title, "Andrew York", source_url, [group], formats=["PDF"], metadata=metadata)
    atomic_json(client.path / "excluded_records.json", excluded)
    return save_catalog(client, "Andrew York", homepage, list(categories.values()), list(works.values()),
        "Every product in guitar solo, collection, duo, quartet and instrumental ensemble sections of the author catalog; voice, piano/harp alternatives, contrabass and orchestral descriptions excluded; no checkout",
        extras={"excluded_catalogue_occurrence_count": len(excluded)})


def werner_attribution(source_context: str) -> tuple[str, dict]:
    """Separate an explicit by-attribution from the directory's other labels.

    Keep the exact combined label as private provenance. A surname remains a
    surname, and an arranger's name does not replace the named composer.
    """
    combined = re.search(r"\bby\s+(.+?)(?:\s*[–—|:(]|$)", source_context)
    label = combined[1].strip() if combined else ""
    composer_by = [match for match in re.finditer(r"\bby\s+", source_context)
                   if not re.search(r"\b(?:edited|arranged|revised|fingered)\s+$", source_context[:match.start()], re.I)]
    composer = source_context[composer_by[-1].end():] if composer_by else ""
    composer = re.split(r"\s*[–—|:(]|,\s*(?:edited|arranged|revised|fingered)\s+by\b", composer,
                        maxsplit=1, flags=re.I)[0].strip()
    # A theme attribution can precede the actual edition attribution, as in
    # 'Variations on a Theme by Handel Op.107 by Giuliani'.
    later_by = list(re.finditer(r"\bby\s+", composer))
    if later_by:
        composer = composer[later_by[-1].end():]
    extra = {}
    for role in ("edited", "arranged"):
        declaration = re.search(r"\b" + role + r"\s+by\s+([^,–—|:(]+)", source_context, re.I)
        if declaration:
            key = "editor" if role == "edited" else "arranger"
            extra[key] = declaration[1].strip()
            extra[key + "_evidence"] = declaration[0]
            if role == "arranged":
                extra["original_arrangement_status"] = "arrangement"
    arranged = re.search(r",\s*arr\.?\s+([^,–—|:(]+)", composer, re.I)
    if arranged:
        extra.update(arranger=arranged[1].strip(), original_arrangement_status="arrangement",
                     source_arrangement_declaration=arranged[0].strip(" ,"))
        composer = composer[:arranged.start()]
    markers = (r"Grades?\b|(?:Early|Mid|Late)[-\s]Begin(?:ner|er)\b|Begin(?:ner|er)\b|"
               r"Intermediate\b|Advanced\b|Free\b|Classical\b|Duets?\b|"
               r"\d+\s+parts?\b|Sheet\s+Music\b|Tab\b|PDF\b")
    composer = re.split(r"(?:\s*,\s*|\s+\.\s+)(?=(?:" + markers + r"))", composer,
                        maxsplit=1, flags=re.I)[0]
    composer = re.sub(r"\s+for\s+(?:Easy|Classical|Solo)\s+Guitar\b.*$", "", composer, flags=re.I).strip()
    difficulty = re.search(r"\bGrades?\s*[\d–\-+]+", source_context, re.I)
    if not difficulty:
        difficulty = re.search(r"\b(?:(?:Early|Mid|Late)[-\s])?Begin(?:ner|er)\b|\bIntermediate\b|\bAdvanced\b",
                               source_context, re.I)
    extra.update(difficulty=difficulty[0] if difficulty else None,
                 directory_label=source_context, original_context=source_context,
                 source_attribution_combined_label=label or None,
                 original_composer_attribution=composer or None,
                 original_attribution_absent=not bool(composer),
                 attribution_extraction_basis="explicit directory by-attribution; non-name labels separated" if composer else "source attribution absent")
    return composer, extra


def parse_werner(soup: BeautifulSoup, directory: str) -> tuple[list, list]:
    main = soup.select_one(".entry-content") or soup
    categories, works = {}, {}
    for link in main.select("li a[href]"):
        href = page_url(urljoin(directory, link["href"]))
        if not href or urlsplit(href).hostname != urlsplit(directory).hostname:
            continue
        title = link.get_text(" ", strip=True)
        if not title:
            continue
        section = link.find_previous(["h2", "h3", "h4"])
        section_name = section.get_text(" ", strip=True) if section else "Sheet Music & Collections with Videos"
        # Navigation, membership and third-party shopping suggestions are outside the selected edition directory.
        if re.search(r"browsing|other publishers|support|explore|resource", section_name, re.I):
            continue
        item = link.find_parent("li"); source_context = item.get_text(" ", strip=True)
        if re.search(r"with (?:voice|vocal)|bass guitar|electric guitar|orchestra", source_context, re.I):
            continue
        identity = urlsplit(href).path.strip("/")
        if identity in {"what-are-grades-in-classical-guitar", "learn-classical-guitar-education-series"}:
            continue
        categories[section_name] = category(section_name, section_name, directory)
        # Only explicit source by-attributions become composer text; unknown remains empty.
        composer, attribution = werner_attribution(source_context)
        if identity in works:
            if section_name not in works[identity]["category_ids"]:
                works[identity]["category_ids"].append(section_name)
            continue
        works[identity] = work("werner", identity, title, composer, href, [section_name], metadata={
            "catalog_compiler": "Bradford Werner",
            "catalog_compiler_basis": "source website compiler; edition editor remains unspecified without an explicit edition declaration",
            "license": "All Rights Reserved; factual directory navigation only",
            **attribution,
            "record_level": "collection" if re.search(r"collection|repertoire|method|studies|pieces|etudes|exercises", title, re.I) else "edition",
            "file_acquisition": "per_edition_permission_required"})
    return list(categories.values()), list(works.values())


def discover_werner(root: Path) -> dict:
    client = DiscoveryClient(root, "werner", {"www.thisisclassicalguitar.com"}, delay=.6)
    homepage = "https://www.thisisclassicalguitar.com/"; directory = homepage + "sheet-music-for-classical-guitar/"
    soup, _ = client.soup(directory); cats, works = parse_werner(soup, directory)
    # Preserve every entry even when its detail page is unavailable; use the verified catalog as public navigation.
    for item in works:
        try:
            detail, _ = client.soup(item["source_url"])
            assets = []
            for link in detail.select('a[href]'):
                url = urljoin(item["source_url"], link["href"])
                if urlsplit(url).path.casefold().endswith(".pdf") and urlsplit(url).hostname in client.hosts:
                    if not any(existing["source_url"] == url for existing in assets): assets.append(asset(url))
            item["assets"] = assets; item["formats"] = ["PDF"] if assets else []
            item["metadata"]["native_cms_id"] = (detail.select_one('article[id]') or {}).get("id")
        except Exception as exc:
            item["metadata"].update(unverified_detail_url=item["source_url"], detail_error=str(exc)); item["source_url"] = directory
    return save_catalog(client, "This is Classical Guitar / Werner", homepage, cats, works,
        "Every same-site repertoire and collection entry in the canonical Sheet Music & Collections with Videos directory; linked editor shop not counted independently; edition PDFs remain restricted")


def parse_freeguitarmusic(soup: BeautifulSoup, directory: str) -> tuple[list, list]:
    works, composer = {}, ""
    for link in soup.select('a[href*="drive.google.com/file/d/"]'):
        label = link.get_text(" ", strip=True)
        if not label or not ("by " in label or "Arranged" in label or label.strip(' "') in {"Romanza De Amor", "Study in A Minor"}):
            continue
        native = re.search(r"/file/d/([^/]+)", link["href"])[1]
        arranged = re.search(r"\s*[-–—]?\s*Arranged by\s+", label, re.I)
        if arranged:
            title, arranger, composer = label[:arranged.start()], label[arranged.end():], ""
        else:
            title, _, composer = label.partition(" by "); arranger = ""
        title = title.strip(' "-–—')
        if native in works:
            continue
        works[native] = work("freeguitarmusic", native, title, composer.strip(), directory, ["modern-classical-solos"],
            metadata={"original_link_label": label, "native_drive_id": native, "arranger": arranger.strip() or None,
                "license": "unspecified; navigation only", "file_acquisition": "unverified",
                "file_reference": link["href"], "original_attribution_absent": not bool(composer)})
    for frame in soup.select('iframe[data-src*="drive.google.com/file/d/"]'):
        native = re.search(r"/file/d/([^/]+)", frame["data-src"])[1]
        label = frame.get("aria-label", "").removeprefix("Drive, ")
        if not label.casefold().endswith(".pdf"):
            continue
        parent = frame.find_parent("section")
        context = parent.get_text(" ", strip=True) if parent else ""
        if native not in works:
            works[native] = work("freeguitarmusic", native, label, "", directory, ["modern-classical-solos"],
                metadata={"title_origin": "source_pdf_filename", "original_composer_attribution": None,
                          "original_attribution_absent": True, "license": "unspecified; catalog navigation only"})
        works[native]["formats"] = ["PDF"]
        works[native]["assets"] = [asset(frame["data-src"])]
        works[native]["metadata"].update(source_pdf_filename=label, native_drive_id=native)
    return [category("modern-classical-solos", "Modern and Classical Fingerstyle Solos", directory)], list(works.values())


def discover_freeguitarmusic(root: Path) -> dict:
    client = DiscoveryClient(root, "freeguitarmusic", {"www.freeguitarmusic.net"}, delay=.65)
    homepage = "https://www.freeguitarmusic.net/"; directory = homepage + "fingerstyle/modern-and-classical-solos"
    soup, _ = client.soup(directory); cats, works = parse_freeguitarmusic(soup, directory)
    return save_catalog(client, "FreeGuitarMusic.Net", homepage, cats, works,
        "Every named score anchor and explicitly named PDF viewer in the Modern and Classical Fingerstyle Solos directory; lesson guide links excluded; no Drive-file acquisition",
        extras={"scope_boundary": "the selected modern/classical directory only; PDF filenames retained where composer attribution is absent"})


def parse_delcamp_page(soup: BeautifulSoup, directory: str, category_id: str, *, composer_hint="") -> list:
    works = {}
    content = soup.select_one(".single-entry-summary") or soup
    for link in content.select('a[href]'):
        href = urljoin(directory, link["href"])
        if not urlsplit(href).path.casefold().endswith(".pdf") or urlsplit(href).hostname != urlsplit(directory).hostname:
            continue
        native = urlsplit(href).path.lstrip("/")
        record_id = delcamp_record_id(native)
        title = link.get_text(" ", strip=True)
        title_origin = "source_anchor"
        if not title or re.fullmatch(r"download|pdf|score|tab|click here|here", title, re.I):
            figure = link.find_parent("figure"); caption = figure.find("figcaption") if figure else None
            heading = link.find_previous(["h2", "h3", "h4"])
            image = link.find("img")
            title = caption.get_text(" ", strip=True) if caption else image.get("alt", "") if image else heading.get_text(" ", strip=True) if heading else ""
            title_origin = "source_caption_or_alt_or_heading"
        if not title:
            title = native.rsplit("/", 1)[-1]; title_origin = "source_filename"
        if record_id in works:
            if title != works[record_id]["title_en"]:
                works[record_id]["metadata"].setdefault("alternate_source_titles", []).append(title)
            continue
        collection = bool(re.search(r"complete|collection|collected|compositions|\d+\s+(?:pieces|studies|works)|method|volume|anthology", title, re.I))
        count = re.search(r"\b(\d+)\s+(?:original\s+)?(?:compositions|pieces|works|studies)\b", title, re.I)
        paragraph = link.find_parent("p")
        first_pdf = next((a for a in paragraph.select('a[href]') if urlsplit(a['href']).path.casefold().endswith('.pdf')), None) if paragraph else None
        collection_context = paragraph.get_text(" ", strip=True).split("Content", 1)[0] if paragraph and first_pdf == link else ""
        if collection_context and re.search(r"\bcollection\b", collection_context, re.I):
            collection = True
            count = count or re.search(r"\b(\d+)\s+(?:original\s+)?(?:compositions|pieces|works|studies)\b", collection_context, re.I)
        composer = composer_hint
        separator = re.search(r"\s+[–—]\s+|\s*:\s*|,\s+(?=(?:[Oo]p\.?|[Nn]ouvelle|[Mm][eé]thode|[Nn]uevo|[Ee]lite|[Pp]remi|[Dd]euxi|[Tt]he\b|[Tt]utor|[0-9]))", title)
        if separator:
            attributed = title[:separator.start()].strip()
            if not re.search(r"method|grade|level|sheet|easy|guitar|beginner|advanced|intermediate", attributed, re.I):
                composer = attributed
        if not composer:
            paragraph = link.find_parent("p")
            if paragraph:
                for strong in reversed(list(link.find_all_previous("strong"))):
                    if strong.find_parent("p") != paragraph or strong.find("a"):
                        continue
                    name = strong.get_text(" ", strip=True).strip(" :")
                    if name and not re.search(r"\d|MB|pages|grade|level|content|collection|guitar|tab", name, re.I):
                        composer = name; break
        permitted = True
        file_asset = asset(href, permitted=permitted, license="Delcamp individual non-commercial use; redistribution forbidden")
        file_asset.update(acquisition_basis="Explicit current homepage terms allow individual non-commercial use",
            restriction="Do not redistribute native or converted copies")
        works[record_id] = work("delcamp", record_id, title, composer, directory, [category_id], formats=["PDF"], assets=[file_asset], metadata={
            "native_record_locator": native,
            "original_composer_attribution": composer or None, "title_origin": title_origin,
            "record_level": "collection" if collection else "edition", "contained_piece_count": int(count[1]) if count else None,
            "contained_piece_count_evidence": collection_context or title if count else None,
            "catalog_compiler": "Jean-François Delcamp",
            "catalog_compiler_basis": "source website compiler; edition editor remains unspecified without per-edition evidence",
            "license": "Scores, online guitar lessons, audio and/or video documents found on classical-guitar-sheet-music.com are free and royalty free and may be used for non-commercial and individual purpose.",
            "acquisition_basis": "Explicit current homepage terms permit individual non-commercial use",
            "restriction": "You are not authorized to distribute one or more copies, in native or converted format.",
            "license_evidence_url": "https://www.classical-guitar-sheet-music.com/"})
    return list(works.values())


def discover_delcamp(root: Path) -> dict:
    client = DiscoveryClient(root, "delcamp", {"www.classical-guitar-sheet-music.com"}, delay=.65)
    homepage = "https://www.classical-guitar-sheet-music.com/"; soup, _ = client.soup(homepage)
    pages = {homepage: ("Homepage", "")}
    menu = soup.select_one("#menu-menu-principal") or soup.select_one("nav") or soup
    for link in menu.select('a[href]'):
        url = page_url(link["href"])
        if not url or urlsplit(url).hostname not in client.hosts or url == homepage:
            continue
        label = link.get_text(" ", strip=True)
        if not label:
            continue
        composer = label if "," in label and not re.search(r"duets|trios|quartets|level|grade|collection|method", label, re.I) else ""
        pages.setdefault(url, (label, composer))
    # Include the canonical directory pages linked from the main content, not ancillary forum/news links.
    for link in soup.select('.single-entry-summary a[href]'):
        url = page_url(link["href"])
        if url and urlsplit(url).hostname in client.hosts and link.get_text(" ", strip=True):
            pages.setdefault(url, (link.get_text(" ", strip=True), ""))
    categories, works, failed = [], {}, []
    for directory, (label, composer) in pages.items():
        category_id = urlsplit(directory).path.strip("/") or "homepage"
        try:
            detail, _ = client.soup(directory)
        except Exception as exc:
            failed.append({"url": directory, "error": str(exc)}); continue
        categories.append(category(category_id, label, directory))
        for item in parse_delcamp_page(detail, directory, category_id, composer_hint=composer):
            if item["id"] in works:
                existing = works[item["id"]]
                if category_id not in existing["category_ids"]: existing["category_ids"].append(category_id)
                if item["title_en"] != existing["title_en"]:
                    existing["metadata"].setdefault("alternate_source_titles", []).append(item["title_en"])
                if not existing["composer_en"] and item["composer_en"]:
                    existing["composer_en"] = item["composer_en"]
            else:
                works[item["id"]] = item
    atomic_json(client.path / "failed_directories.json", failed)
    mapping_path = client.path / "identity_map.json"
    existing_map = json.loads(mapping_path.read_text(encoding="utf-8")) if mapping_path.exists() else {}
    entries = dict(existing_map.get("entries", {}))
    entries.update({"delcamp:" + row["metadata"]["native_record_locator"]: row["id"] for row in works.values()})
    atomic_json(mapping_path, {**existing_map, "schema_version": 1, "source_id": "delcamp", "entries": entries,
        "identity_basis": "SHA-256 of exact native source locator string; not PDF content checksum",
        "records": {row["id"].split(":", 1)[1]: row["metadata"]["native_record_locator"] for row in works.values()}})
    return save_catalog(client, "Delcamp", homepage, categories, list(works.values()),
        "All PDF edition/collection anchors on the homepage and directly linked site directory pages; same native PDF path merges memberships; collection internal works are not counted as separate records",
        complete=not failed, extras={"selected_directory_count": len(pages), "failed_directory_count": len(failed),
            "count_basis": "PDF edition or collection records, not the site's 18000-piece marketing total"})


def discover_loc(root: Path) -> dict:
    client = DiscoveryClient(root, "loc", {"www.loc.gov"}, delay=.7)
    homepage = "https://www.loc.gov/"; query_url = homepage + "notated-music/?fo=json&q=guitar&c=100"
    raw, _ = client.get(query_url); payload = json.loads(raw); works, omitted = [], []
    results = payload.get("results", [])
    for item in results:
        source_url = item.get("url", "")
        if source_url.startswith("//"): source_url = "https:" + source_url
        source_url = source_url.replace("http://www.loc.gov/", "https://www.loc.gov/")
        source_url = page_url(source_url)
        subject = item.get("subject") or []; formats = item.get("online_format", [])
        title = item.get("title", "")
        if not source_url or urlsplit(source_url).hostname not in client.hosts or "/item/" not in urlsplit(source_url).path:
            omitted.append({"title": title, "url": item.get("url"), "reason": "finding aid or no validated LoC item URL"}); continue
        if not re.search(r"guitar|guitarra|guitare|guitare?", " ".join(subject) + " " + title, re.I):
            omitted.append({"title": title, "url": source_url, "reason": "keyword match alone does not establish guitar score scope"}); continue
        if re.search(r"orchestra|\bband\b|guitar.*voice|voice.*guitar|electric guitar|bass guitar|vocal|songs", " ".join(subject) + " " + title, re.I):
            omitted.append({"title": title, "url": source_url, "reason": "explicit excluded instrumentation or songs"}); continue
        native = urlsplit(source_url).path.strip("/").removeprefix("item/")
        reference = "hlas-annotations" in item.get("group", [])
        works.append(work("loc", native, title, "", source_url, ["notated-guitar"],
            formats=["PDF"] if "pdf" in formats and not reference else [],
            resource_type="reference" if reference else "score", metadata={
                "date": item.get("date"), "subjects": subject, "license": "per item/collection rights; no blanket file reuse",
                "publisher": None, "instrumentation": None, "digitized": item.get("digitized"),
                "access_restricted": item.get("access_restricted"), "contributors_original": item.get("contributor", []),
                "original_composer_attribution": None, "original_attribution_absent": True,
                "record_level": "bibliographic_reference" if reference else "edition",
                "file_acquisition": "per_item_rights_and_resources_check_required"}))
    atomic_json(client.path / "omitted_results.json", omitted)
    if not works:
        raise RuntimeError("LoC scoped API returned no eligible notated score records")
    return save_catalog(client, "Library of Congress", homepage, [category("notated-guitar", "Notated music: guitar keyword", homepage + "notated-music/")], works,
        "Official notated-music JSON API keyword guitar; retained only LoC item pages, excluded finding aids and explicit songs/voice/bass/electric/orchestral subjects; keyword candidates are not instrumentation-verified",
        extras={"query": "notated-music?q=guitar", "query_returned_count": len(results), "omitted_count": len(omitted)})


ADAPTERS = {
    "cglib": discover_cglib, "cantorion": discover_cantorion, "classicalguitarorg": discover_classicalguitarorg,
    "guitardownunder": discover_guitardownunder, "andrewyork": discover_andrewyork,
    "werner": discover_werner, "freeguitarmusic": discover_freeguitarmusic, "delcamp": discover_delcamp,
    "loc": discover_loc,
}
