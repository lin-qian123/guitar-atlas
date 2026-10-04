#!/usr/bin/env python
"""Freeze resumable official Boije/RISM/DGA metadata; never fetch score files.

Private products stay in sources/<source>/ (Git ignored).  A cached response
is reused verbatim unless --refresh is explicitly requested.  RISM resource
details are an independent resumable queue; complete search discovery does not
claim complete descriptive metadata or scoring review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlencode
from urllib.robotparser import RobotFileParser

import requests

from source_adapters import boije, dga, rism

USER_AGENT = "GuitarAtlas/1.0 (reproducible research catalog; official metadata APIs; polite source-attributed discovery)"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".part")
    partial.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partial.replace(path)


def catalog_reports(directory: Path, catalog: dict) -> None:
    works = catalog["works"]
    fields = ("instrumentation", "opus", "arranger", "editor", "source_call", "source_edition", "license",
              "publisher", "publication_date", "pages", "institution", "language", "related_source_ids", "authority_relations")
    coverage = {"source_id": catalog["source_id"], "measured_at": now(), "normalized_records": len(works),
                "categories": len(catalog["categories"]), "resource_types": dict(Counter(row["resource_type"] for row in works)),
                "instrumentation_status": dict(Counter(row["instrumentation_status"] for row in works)),
                "metadata_field_present": {key: sum(bool(row.get("metadata", {}).get(key)) for row in works) for key in fields},
                "composer_present": sum(bool(row["composer_en"]) for row in works),
                "title_placeholder": sum(row["metadata"].get("title_basis") == "missing_source_title_placeholder" for row in works),
                "unique_source_ids": len({row["id"] for row in works}),
                "asset_statuses": dict(Counter(asset["status"] for row in works for asset in row.get("assets", []))),
                "snapshot": catalog["snapshot"]}
    write_json(directory / "summary.json", catalog["summary"])
    write_json(directory / "field_coverage.json", coverage)
    write_json(directory / "discovery_status.json", {"at": now(), "discovery_complete": catalog["snapshot"]["discovery_complete"],
               "catalog_ready": True, "resource_details_complete": catalog["snapshot"].get("resource_details_complete"),
               "resource_details_pending": catalog["summary"].get("resource_details_pending", 0),
               "file_acquisition": catalog["summary"].get("file_acquisition", "not attempted")})


class FrozenClient:
    def __init__(self, directory: Path, interval: float, refresh=False):
        self.directory, self.interval, self.refresh = directory, interval, refresh
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.last_request = 0
        directory.mkdir(parents=True, exist_ok=True)

    def get(self, url: str, *, json_ld=False, allow_error=False) -> dict:
        key = hashlib.sha256((url + str(json_ld)).encode()).hexdigest()
        path = self.directory / "responses" / (key + ".json")
        if path.exists() and not self.refresh:
            return json.loads(path.read_text(encoding="utf-8"))
        for attempt in range(3):
            delay = self.interval - (time.monotonic() - self.last_request)
            if delay > 0:
                time.sleep(delay)
            started = now()
            self.last_request = time.monotonic()
            try:
                response = self.session.get(url, headers={"Accept": "application/ld+json"} if json_ld else {}, timeout=60)
                if response.status_code == 429:
                    self.log({"at": started, "url": url, "status": 429,
                              "retry_after": response.headers.get("Retry-After", ""),
                              "action": "stop resumable discovery at server rate limit"})
                    raise RuntimeError(f"server rate limit stopped metadata discovery: {url}; Retry-After={response.headers.get('Retry-After', '')}")
                if response.status_code in {500, 502, 503, 504} and attempt < 2:
                    self.log({"at": started, "url": url, "status": response.status_code, "retry": attempt + 1})
                    retry_after = response.headers.get("Retry-After", "")
                    if retry_after and not retry_after.isdigit():
                        raise RuntimeError(f"server asks to retry later; resumable discovery stopped: {retry_after}: {url}")
                    delay = max(self.interval, 5 * (attempt + 1), int(retry_after or 0))
                    if delay > 60:
                        raise RuntimeError(f"server asks for long retry delay; resumable discovery stopped: {delay}s: {url}")
                    time.sleep(delay)
                    continue
                payload = {"requested_url": url, "url": response.url, "fetched_at": started,
                           "http_status": response.status_code,
                           "content_type": response.headers.get("Content-Type", ""),
                           "retry_after": response.headers.get("Retry-After", ""),
                           "body_sha256": hashlib.sha256(response.content).hexdigest(),
                           "text": response.text}
                self.log({key: payload[key] for key in ("fetched_at", "requested_url", "url", "http_status", "content_type", "body_sha256")})
                if response.status_code != 200 and not allow_error:
                    raise RuntimeError(f"metadata request stopped: HTTP {response.status_code}: {url}")
                if any(marker in response.text[:20000].lower() for marker in ("verify you are human", "cf-chl-", "checking your browser")):
                    raise RuntimeError(f"metadata discovery stopped for human verification: {url}")
                write_json(path, payload)
                return payload
            except requests.RequestException as error:
                self.log({"at": started, "url": url, "error": type(error).__name__, "message": str(error), "attempt": attempt + 1})
                if attempt == 2:
                    raise
        raise RuntimeError("metadata request retry exhausted")

    def log(self, row: dict) -> None:
        with (self.directory / "requests.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def policy(client: FrozenClient, source_id: str) -> dict:
    policies = {
        "boije": ["https://old.capricemusic.se/robots.txt", boije.HOMEPAGE],
        "rism": ["https://rism.online/robots.txt", "https://rism.online/docs/api/api/",
                 "https://rism.online/docs/api/search-api/", rism.LICENSE_URL],
        "dga": ["https://digitalguitararchive.com/robots.txt", dga.ANNOUNCEMENT_URL,
                dga.TERMS_URL, dga.HOMEPAGE, dga.API_BASE + "/openapi.json"],
    }
    responses = [client.get(url) for url in policies[source_id]]
    result = {"checked_at": now(), "source_id": source_id,
              "evidence": [{key: row[key] for key in ("requested_url", "url", "http_status", "fetched_at", "body_sha256")} for row in responses]}
    if source_id == "rism":
        if "application/ld+json" not in responses[1]["text"] or "Creative Commons Attribution 3.0" not in responses[3]["text"]:
            raise RuntimeError("RISM official API or metadata licence evidence changed; review before continuing")
        result.update(metadata_permission="official API explicitly offered; metadata CC BY 3.0",
                      robots_scope="Search HTML crawler routes restricted; use documented JSON-LD API only",
                      request_interval_seconds=max(5, client.interval), file_acquisition="not attempted")
    else:
        robot = RobotFileParser()
        robot.parse(responses[0]["text"].splitlines())
        target = boije.HOMEPAGE if source_id == "boije" else dga.API_BASE + "/search"
        if not robot.can_fetch(USER_AGENT, target):
            raise RuntimeError(f"{source_id} robots disallows production endpoint")
        result.update(metadata_permission="official catalog" if source_id == "boije" else "advertised official legacy API; database reuse license unspecified",
                      file_acquisition="not attempted by metadata discovery",
                      request_interval_seconds=client.interval)
    if source_id == "boije":
        probes = [client.get("https://urn.kb.se/robots.txt", allow_error=True),
                  client.get("https://boijefiles.musikverket.se/robots.txt", allow_error=True)]
        result["asset_policy_probes"] = [{key: row[key] for key in ("url", "http_status", "body_sha256", "fetched_at")} for row in probes]
        result["file_acquisition"] = "blocked_by_robots_or_policy_probe"
        result["file_acquisition_reason"] = "URN robots Disallow:/; target file-host robots probe HTTP 403; no bulk PDF requests"
    write_json(client.directory / "policy.json", result)
    return result


def discover_boije(client: FrozenClient) -> dict:
    homepage = client.get(boije.HOMEPAGE)
    categories = boije.index_pages(homepage["text"])
    if not categories:
        raise ValueError("Boije homepage no longer exposes its alphabetical index")
    rows = []
    page_evidence = []
    for category in categories:
        reply = client.get(category["source_url"])
        extracted = boije.page_rows(reply["text"], category)
        if not extracted:
            raise ValueError("Boije index page has no native-ID score rows: " + category["source_url"])
        rows.extend(extracted)
        page_evidence.append({"source_url": category["source_url"], "row_count": len(extracted),
                              "fetched_at": reply["fetched_at"], "body_sha256": reply["body_sha256"]})
    write_json(client.directory / "discovery.json", {"pages": page_evidence, "entries": rows})
    catalog = boije.normalize(categories, rows, {"frozen_at": homepage["fetched_at"], "discovery_complete": True,
                              "page_count": len(categories) + 1, "scope_version": 1,
                              "scope": "official complete alphabetical collection index; explicit scoring exclusions retained",
                              "instrumentation_review_complete": False})
    write_json(client.directory / "excluded_entries.json", catalog["excluded_entries"])
    return catalog


def discover_rism(client: FrozenClient, detail_limit: int, sru_client: FrozenClient | None = None) -> dict:
    url, seen_pages, items, totals = rism.SEARCH_URL, set(), [], set()
    frozen_at = ""
    while url:
        if url in seen_pages or not re.fullmatch(r"https://rism\.online/search\?[^#]+", url):
            raise ValueError("invalid RISM pagination")
        response = client.get(url, json_ld=True)
        frozen_at = frozen_at or response["fetched_at"]
        payload = json.loads(response["text"])
        totals.add(payload["totalItems"])
        if len(totals) != 1:
            raise ValueError("RISM upstream total drifted during frozen search acquisition")
        items.extend(payload["items"])
        seen_pages.add(url)
        url = payload.get("view", {}).get("next")
    if len({row["id"] for row in items}) != next(iter(totals)):
        raise ValueError("RISM unique source IDs do not match frozen totalItems")
    write_json(client.directory / "discovery.json", {"frozen_at": frozen_at, "pages": list(seen_pages),
                                                    "reported_total": next(iter(totals)), "items": items})
    detail_path = client.directory / "resource_details.json"
    details = json.loads(detail_path.read_text(encoding="utf-8")) if detail_path.exists() else {}
    current_ids = {row["id"] for row in items}
    if set(details) - current_ids:
        raise ValueError("RISM cached detail IDs no longer belong to the frozen discovery scope")
    snapshot = {"frozen_at": frozen_at, "discovery_complete": True, "page_count": len(seen_pages),
                "scope_version": 1, "scope": "official q=guitar full-text keyword discovery; scoring not approved",
                "instrumentation_review_complete": False, "reported_total": next(iter(totals))}

    def checkpoint():
        write_json(detail_path, details)
        catalog = rism.normalize(items, details, snapshot)
        catalog["snapshot"]["resource_details_complete"] = len(details) == len(items)
        write_json(client.directory / "catalog.json", catalog)
        write_json(client.directory / "excluded_entries.json", catalog["excluded_entries"])
        catalog_reports(client.directory, catalog)
        write_json(client.directory / "detail_queue.json", {"updated_at": now(), "completed": len(details),
                                                           "pending": [row["id"] for row in items if row["id"] not in details]})
        return catalog

    checkpoint()
    if sru_client is not None:
        robot_response = sru_client.get("https://muscat.rism.info/robots.txt")
        robot = RobotFileParser()
        robot.parse(robot_response["text"].splitlines())
        if not robot.can_fetch(USER_AGENT, rism.SRU_BASE):
            raise RuntimeError("RISM Muscat robots does not allow its official SRU endpoint")
        documentation = sru_client.get("https://github.com/rism-digital/muscat/wiki/SRU")
        if "maximumRecords" not in documentation["text"]:
            raise RuntimeError("RISM SRU batch-access documentation changed")
        write_json(client.directory / "sru_policy.json", {"checked_at": now(),
            "official_recommendation": rism.LICENSE_URL,
            "evidence": [{key: response[key] for key in ("url", "http_status", "fetched_at", "body_sha256")} for response in (robot_response, documentation)],
            "request_interval_seconds": sru_client.interval, "batch_size": 50,
            "scope": "one-off exact frozen source-ID metadata retrieval; no institution files or database-wide query",
            "metadata_license": "RISM CC BY 3.0", "rism_online_crawl_delay_seconds": 5})
        pending_numeric = [item["id"] for item in items if item["id"] not in details
                           and re.fullmatch(r"https://rism\.online/sources/\d+", item["id"])]
        item_map = {item["id"]: item for item in items}
        for offset in range(0, len(pending_numeric), 50):
            if (client.directory / "stop_after_checkpoint").exists():
                print("RISM SRU queue stopped at requested checkpoint", flush=True)
                break
            batch = pending_numeric[offset:offset + 50]
            query = " OR ".join("id=" + url.rsplit("/", 1)[-1] for url in batch)
            sru_url = rism.SRU_BASE + "?" + urlencode({"operation": "searchRetrieve", "version": "1.1",
                        "query": query, "recordSchema": "marc", "maximumRecords": len(batch)})
            try:
                response = sru_client.get(sru_url)
                parsed = rism.parse_sru(response["text"], item_map, sru_url)
                if set(parsed) - set(batch):
                    raise ValueError("SRU returned a source outside the exact requested batch")
                details.update(parsed)
                checkpoint()
                print(f"RISM SRU resource metadata {len(details)}/{len(items)}; batch matched {len(parsed)}/{len(batch)}", flush=True)
            except BaseException:
                checkpoint()
                raise
    done = 0
    for item in items:
        if item["id"] in details:
            continue
        if detail_limit >= 0 and done >= detail_limit:
            break
        if (client.directory / "stop_after_checkpoint").exists():
            print("RISM queue stopped at requested checkpoint; frozen search catalog retained", flush=True)
            break
        try:
            response = client.get(item["id"], json_ld=True)
            detail = json.loads(response["text"])
            if detail.get("id") != item["id"]:
                raise ValueError("RISM resource detail identity mismatch")
            details[item["id"]] = detail
            done += 1
            if done % 10 == 0:
                checkpoint()
                print(f"RISM resource metadata {len(details)}/{len(items)}", flush=True)
        except BaseException:
            checkpoint()
            raise
    return checkpoint()


def discover_dga(client: FrozenClient) -> dict:
    library_response = client.get(dga.API_BASE + "/sources")
    libraries = json.loads(library_response["text"])["sources"]
    records, pages, query_counts = {}, [], {}
    # The API's `total` is the current page length, not a dataset total.
    for keyword in dga.DISCOVERY_KEYWORDS:
        offset, seen = 0, set()
        while True:
            response = client.get(dga.search_url(offset=offset, query=keyword))
            payload = json.loads(response["text"])
            batch = payload.get("results")
            if not isinstance(batch, list):
                raise ValueError("DGA API response has no results list")
            pages.append({"url": response["requested_url"], "keyword": keyword, "returned_records": len(batch),
                          "fetched_at": response["fetched_at"], "body_sha256": response["body_sha256"]})
            if not batch:
                break
            for raw in batch:
                native = raw["id"]
                if native in seen:
                    raise ValueError("DGA pagination repeated a native ID within one keyword")
                seen.add(native)
                if native in records and records[native]["record"] != raw:
                    raise ValueError("DGA record changed across frozen keyword requests")
                records.setdefault(native, {"record": raw, "matched_keywords": []})["matched_keywords"].append(keyword)
            offset += len(batch)
        query_counts[keyword] = len(seen)
        print(f"DGA keyword {keyword}: {len(seen)} records; union {len(records)}", flush=True)
    write_json(client.directory / "discovery.json", {"libraries": libraries, "pages": pages,
                "query_counts": query_counts, "records": list(records.values())})
    catalog = dga.normalize([row["record"] for row in records.values()], libraries, {"frozen_at": library_response["fetched_at"], "discovery_complete": True,
                        "page_count": len(pages) + 1, "scope_version": 1,
                        "scope": "advertised official legacy API multilingual full-text keyword union; keyword discovery only",
                        "keywords": list(dga.DISCOVERY_KEYWORDS), "query_counts": query_counts,
                        "upstream_drift": "legacy sources sum and homepage advertised record count differ; not comparable",
                        "instrumentation_review_complete": False, "new_omeka_scope": "not acquired or equated to legacy IDs"})
    for row in catalog["works"]:
        row["metadata"]["matched_discovery_keywords"] = records[int(row["id"].split(":")[1])]["matched_keywords"]
    write_json(client.directory / "excluded_entries.json", catalog["excluded_entries"])
    return catalog


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--source", choices=("boije", "rism", "dga", "all"), default="all")
    parser.add_argument("--refresh", action="store_true", help="fetch a new response snapshot; explicitly discards cache reuse")
    parser.add_argument("--interval", type=float, default=1.0, help="minimum seconds between requests (RISM is always at least 5)")
    parser.add_argument("--rism-details", type=int, default=0, help="resource metadata requests this run; -1 processes the entire resumable queue")
    parser.add_argument("--rism-sru", action="store_true", help="retrieve remaining frozen numeric IDs in official Muscat SRU batches, then resume JSON-LD-only leftovers")
    args = parser.parse_args(argv)
    if args.interval < 0.5 or args.rism_details < -1:
        parser.error("polite interval must be >= 0.5; RISM detail limit is >= -1")
    modules = {"boije": boije, "rism": rism, "dga": dga}
    selected = list(modules) if args.source == "all" else [args.source]
    results = {}
    for source_id in selected:
        directory = args.root.resolve() / "sources" / source_id
        client = FrozenClient(directory, max(args.interval, 5.0 if source_id == "rism" else 0.5), args.refresh)
        write_json(directory / "registry_proposal.json", modules[source_id].registry_proposal())
        policy(client, source_id)
        try:
            catalog = (discover_rism(client, args.rism_details, FrozenClient(directory, max(args.interval, 1), args.refresh) if args.rism_sru else None) if source_id == "rism"
                       else discover_boije(client) if source_id == "boije" else discover_dga(client))
            write_json(directory / "catalog.json", catalog)
            catalog_reports(directory, catalog)
            results[source_id] = catalog["summary"]
            print(json.dumps({source_id: catalog["summary"]}, ensure_ascii=False), flush=True)
        except BaseException as error:
            write_json(directory / "discovery_failure.json", {"at": now(), "error": type(error).__name__, "message": str(error)})
            raise
    return results


if __name__ == "__main__":
    main()
