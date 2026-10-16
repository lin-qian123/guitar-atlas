#!/usr/bin/env python
"""Independently verify append-only PDMX expansion and every prior local mapping.

This audit never rebuilds a catalog, changes a score, or rewrites a historical
receipt. ``--capture-offline`` adds the unchanged entry's decoded snapshot to
the single expansion baseline before acquisition; final mode writes only the
current preservation receipt after checking actual source objects and links.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile
from urllib.parse import quote

from catalog_instrumentation import _check_asset, _check_review, per_record_guard
from catalog_payload import unpack_payload
from source_adapters.pdmx import _atomic_json, _metadata_locator
from source_adapters.pdmx_assets import _locator as pdf_locator, _stat_fingerprint
from source_adapters.pdmx_formats import _locator as format_locator
from verify_musescore_instrumentation import AuditFailure, require, _by_id, check_local_link, sha256

BASE = Path("sources/musescore/expansion")
SOURCE = "sources/musescore/catalog.json"
REVIEW = "sources/musescore/instrumentation-review.json"
PUBLIC = "public_site/data/catalog.json"
ALIASES = "public_site/data/search-aliases.json"
RANKING = "public_site/data/ranking.json"
APPEND_TRANSLATIONS = {"source_titles_zh.json", "musicians_zh.json", "categories_zh.json"}
FORMATS = {"PDF": "pdf", "MUSICXML": "mxl", "MIDI": "mid"}
FINAL_INPUT_PATHS = {
    "plan": BASE / "plan.json", "scope_review": BASE / "scope-review.json",
    "configuration": Path("config/musescore_pdmx_expansion.json"),
    **{label: BASE / (code + "-extraction.json") for label, code in FORMATS.items()},
}
SCOPE_METHOD_PATHS = frozenset({"scripts/review_musescore_expansion.py",
    "scripts/review_musescore_instrumentation.py", "scripts/score_instrumentation.py",
    "scripts/source_adapters/pdmx_formats.py", "scripts/catalog_instrumentation.py"})
FINAL_METHOD_PATHS = SCOPE_METHOD_PATHS | {"scripts/review_musescore_expansion_final.py",
    "scripts/score_pdf_evidence.py", "scripts/score_midi_crosscheck.py",
    "scripts/score_mxl_playback_correspondence.py"}
EXACT_CASE_PATH = Path("metadata/instrumentation/musescore_expansion_reviewed.json")
BROAD_INPUTS = {'policy': Path('config/library_classification.json'),
    'decisions': Path('metadata/instrumentation/musescore_broad_reviewed.json'),
    'method': Path('scripts/review_musescore_broad.py')}


def read_json(path):
    return json.loads(Path(path).read_bytes())


def read_baseline(path):
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            value = json.loads(archive.read('baseline.json'))
    else:
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            value = json.load(stream)
    require(value.get("schema_version") == 1 and isinstance(value.get("documents"), dict),
            "invalid expansion baseline")
    return value


def decode_offline(path):
    raw = Path(path).read_bytes()
    matches = re.findall(r'<script type="application/json" id="offline-data">(.*?)</script>', raw.decode(), re.S)
    require(len(matches) == 1, "offline embedded snapshot must occur exactly once")
    value = unpack_payload(json.loads(matches[0]))
    require(isinstance(value, dict) and isinstance(value.get("data"), dict), "invalid decoded offline wrapper")
    return value, hashlib.sha256(raw).hexdigest()


def capture_offline_baseline(root, path):
    root, path = Path(root).resolve(), Path(path)
    before = path.read_bytes()
    baseline = read_baseline(path)
    wrapper, digest = decode_offline(root / "index.html")
    require(digest == baseline["offline_sha256"], "old offline entry changed before baseline capture")
    if "offline_snapshot" in baseline:
        require(baseline["offline_snapshot"] == wrapper, "existing offline baseline differs")
        return {"status": "already_captured", "records": len(wrapper["data"]["works"])}
    baseline["offline_snapshot"] = wrapper
    require(path.read_bytes() == before and sha256(root / "index.html") == digest,
            "baseline or offline entry changed during capture")
    temporary = path.with_name(path.name + ".part")
    with temporary.open("wb") as output:
        with gzip.GzipFile(fileobj=output, mode="wb", compresslevel=3, mtime=0) as stream:
            stream.write(json.dumps(baseline, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode())
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)
    return {"status": "captured", "records": len(wrapper["data"]["works"])}


def compare_existing_records(before_rows, after_rows, context, expected_new_ids=None):
    before, after = _by_id(before_rows, context + " baseline"), _by_id(after_rows, context + " current")
    require(set(before) <= set(after), context + ": prior identities removed")
    for identity, original in before.items():
        require(after[identity] == original, context + ": prior record changed: " + identity)
    added = set(after) - set(before)
    if expected_new_ids is not None:
        require(added == set(expected_new_ids), context + ": appended identity scope differs")
    return {"preserved": len(before), "added": len(added)}


def compare_review_scopes(before, after, natives):
    old_entries, entries = _by_id(before["works"], "prior review"), _by_id(after["works"], "current review")
    require(after.get("schema_version") == 2 and after.get("source_id") == "musescore"
            and after.get("status") == "complete", "appended catalog requires complete schema-2 review guards")
    native = _by_id(natives, "native review scope")
    require(set(old_entries) <= set(entries) <= set(native), "prior review identities removed or unknown IDs added")
    guards = after.get("native_record_sha256")
    require(isinstance(guards, dict) and set(guards) == set(entries), "complete native record guard scope required")
    for identity, value in old_entries.items():
        require(entries[identity] == value, "prior review decision changed: " + identity)
    for identity, value in entries.items():
        require(guards[identity] == per_record_guard(native[identity]), "native record guard changed: " + identity)
    return {"preserved_review_entries": len(old_entries), "added_review_entries": len(entries) - len(old_entries)}


def compare_translation_asset(relative, before, after, new_ids, new_musicians, new_categories):
    name = Path(relative).name
    if name not in APPEND_TRANSLATIONS:
        require(before == after, "protected translation asset changed: " + relative)
        return {"added_entries": 0}
    require({k: v for k, v in before.items() if k != "entries"} ==
            {k: v for k, v in after.items() if k != "entries"}, "translation asset header changed: " + relative)
    previous, current = before["entries"], after["entries"]
    if name == "source_titles_zh.json":
        for key, value in previous.items():
            require(current.get(key) == value, "prior translation entry changed: " + key)
        added = set(current) - set(previous)
        require(added <= set(new_ids), "new title translation lacks an accepted native identity")
    else:
        require(set(current) - {"musescore"} == set(previous) - {"musescore"}, "other-source translation scope changed")
        for source, value in previous.items():
            if source != "musescore":
                require(current.get(source) == value, "other-source translation entries changed: " + source)
        old_source, new_source = previous.get("musescore", {}), current.get("musescore", {})
        for key, value in old_source.items():
            require(new_source.get(key) == value, "prior translation entry changed: " + key)
        added = set(new_source) - set(old_source)
        allowed = new_musicians if name == "musicians_zh.json" else new_categories
        require(added <= set(allowed), "new source translation lacks an accepted exact name/category")
    return {"added_entries": len(added)}


def compare_offline_records(before_rows, after_rows, public_rows):
    before, after = _by_id(before_rows, "baseline offline"), _by_id(after_rows, "current offline")
    public = _by_id(public_rows, "current public")
    require(set(after) == set(public) and set(before) <= set(after), "offline/public appended identity scope differs")
    for identity, original in before.items():
        require(after[identity].get("local_editions") == original.get("local_editions"),
                "prior local editions changed: " + identity)
    for identity, value in after.items():
        require({k: v for k, v in value.items() if k != "local_editions"} == public[identity],
                "offline/public shared work fields differ: " + identity)
    return {"preserved": len(before), "added": len(after) - len(before),
            "old_local_editions_exact": True, "all_shared_work_fields_exact": True}


def compare_public_structure(before, after, added, *, classification_update=False):
    """Only incremental counts, the MuseScore scope text and new edges may vary."""
    for field in ("schema_version", "unification_schema_version", "translation_schema_version", "families"):
        require(before.get(field) == after.get(field), "public catalog definition changed: " + field)
    require(len(before["categories"]) == len(after["categories"]), "native public category scope changed")
    for old, new in zip(before["categories"], after["categories"], strict=True):
        require({k: v for k, v in old.items() if k != "work_count"} ==
                {k: v for k, v in new.items() if k != "work_count"}, "native public category definition changed")
    topic_before = [{k: v for k, v in row.items() if k not in {'work_count', 'source_count'}} for row in before['topics']]
    if classification_update:
        for row in topic_before:
            if row['id'] == 'guitar_unspecified':
                row.update(name_zh='吉他相关·编制未细分', name_en='Guitar-related, instrumentation not fully specified')
    require(topic_before ==
            [{k: v for k, v in row.items() if k not in {"work_count", "source_count"}} for row in after["topics"]],
            "shared topic vocabulary changed")
    old_sources, sources = _by_id(before["sources"], "prior sources"), _by_id(after["sources"], "current sources")
    require(set(old_sources) == set(sources), "registered public source identities changed")
    for identity, old in old_sources.items():
        new = sources[identity]
        if identity != "musescore":
            require(old == new, "other public source changed: " + identity)
            continue
        old_copy = {k: v for k, v in old.items() if k not in {"record_count", "snapshot"}}
        new_copy = {k: v for k, v in new.items() if k not in {"record_count", "snapshot"}}
        require(old_copy == new_copy and new["record_count"] == old["record_count"] + len(added),
                "MuseScore public source identity or incremental count changed")
        require({k: v for k, v in old.get("snapshot", {}).items() if k not in {"scope", "record_count"}} ==
                {k: v for k, v in new.get("snapshot", {}).items() if k not in {"scope", "record_count"}}, "published frozen source evidence changed")
        require(new.get("snapshot", {}).get("record_count", new["record_count"]) == new["record_count"],
                "published expansion snapshot count differs")
    canonical = lambda edge: json.dumps(edge, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    old_edges = {canonical(edge) for edge in before["relationships"]}
    edges = {canonical(edge) for edge in after["relationships"]}
    require(old_edges <= edges, "prior typed relationships removed or changed")
    for edge in after["relationships"]:
        if canonical(edge) not in old_edges:
            require(edge.get("from_id") in added or edge.get("to_id") in added, "new relationship does not involve an appended record")
    return {"old_categories_exact_except_counts": True, "topic_vocabulary_exact": not classification_update,
            **({'reviewed_guitar_unspecified_label_update': True} if classification_update else {}),
            "preserved_relationships": len(old_edges), "added_relationships": len(edges) - len(old_edges)}


def check_new_offline_links(native, offline):
    editions = offline["local_editions"]
    require(len(editions) == len(offline["category_ids"]), "new offline category edition coverage differs")
    require({edition["category_id"] for edition in editions} == set(offline["category_ids"]),
            "new offline links cross category memberships")
    expected = {quote(asset["local_path"], safe="/._-~()") for asset in native["assets"]}
    for edition in editions:
        rows = edition["files"]
        require(Counter(file.get("format", "PDF") for file in rows) == Counter({label: 1 for label in FORMATS}),
                "new offline work lacks exactly three format links: " + native["id"])
        require({file["href"] for file in rows} == expected,
                "new offline links do not reference the exact acquired assets: " + native["id"])


def safe_path(root, relative):
    require(isinstance(relative, str) and relative and "\\" not in relative, "unsafe private object path")
    part = Path(relative)
    require(not part.is_absolute() and ".." not in part.parts, "unsafe private object path")
    path = root / part
    require(path.resolve().is_relative_to(root), "private object path leaves the project root")
    require(path.is_file(), "private object is missing: " + relative)
    return path


def final_guard_paths(root):
    paths = {Path(relative) for relative in FINAL_METHOD_PATHS} | set(FINAL_INPUT_PATHS.values())
    paths.add(BASE / "final-review.json")
    if (root / EXACT_CASE_PATH).exists() or (root / EXACT_CASE_PATH).is_symlink():
        paths.add(EXACT_CASE_PATH)
    if (root / BROAD_INPUTS['decisions']).is_file():
        paths.update(BROAD_INPUTS.values())
    return {root / relative for relative in paths}


def check_final_input_guards(root, final, scope):
    """Independently bind completed semantic reviews to current exact inputs."""
    root = Path(root).resolve()
    states = {}

    def digest(relative):
        path = safe_path(root, str(relative))
        before = _stat_fingerprint(path)
        require(path not in states or states[path] == before, "semantic review input changed between guard checks")
        states[path] = before
        value = {"sha256": sha256(path), "size": before[2]}
        require(_stat_fingerprint(path) == before, "final review input changed while hashing: " + str(relative))
        return value

    inputs = final.get("inputs")
    require(isinstance(inputs, dict) and set(inputs) == set(FINAL_INPUT_PATHS),
            "final review input guard scope differs")
    scope_inputs = scope.get("inputs")
    require(isinstance(scope_inputs, dict)
            and set(scope_inputs) == {"plan", "mxl_extraction", "methods", "reviewed_cases"}
            and "reviewed_cases" in final, "scope review input guard scope differs")
    current = {name: digest(relative) for name, relative in FINAL_INPUT_PATHS.items()}
    require(inputs == current, "final review input bytes changed")
    for report, names, context in ((final.get("methods"), FINAL_METHOD_PATHS, "final"),
            (scope_inputs["methods"], SCOPE_METHOD_PATHS, "scope")):
        require(isinstance(report, dict) and set(report) == names, context + " review method guard scope differs")
        require(report == {relative: digest(relative) for relative in names}, context + " review method bytes changed")
    case_path = root / EXACT_CASE_PATH
    require(not case_path.is_symlink(), "exact reviewed-case asset cannot be a symlink")
    case_guard = digest(EXACT_CASE_PATH) if case_path.exists() or case_path.is_symlink() else None
    require(final.get("reviewed_cases") == case_guard
            and scope_inputs["reviewed_cases"] == case_guard,
            "exact reviewed-case asset changed after semantic review")
    require(scope_inputs.get("plan") == current["plan"]
            and scope_inputs.get("mxl_extraction") == current["MUSICXML"],
            "scope review input bytes changed")
    broad = final.get('broad_review')
    if broad is not None or scope.get('broad_review') is not None:
        expected = {key: digest(path) for key, path in BROAD_INPUTS.items()}
        require(broad == expected and scope.get('broad_review') == expected,
                'broad guitar-related review inputs changed')
    require(all(_stat_fingerprint(path) == state for path, state in states.items())
            and (case_guard is not None) == (case_path.exists() or case_path.is_symlink()),
            "semantic review inputs changed during guard verification")
    return {"current_input_files": len(current), "final_method_files": len(FINAL_METHOD_PATHS),
            "scope_method_files": len(SCOPE_METHOD_PATHS), "exact_case_bytes_current": True}


def check_old_objects(root, files):
    root = Path(root).resolve()
    def check_one(item):
        relative, guard = item
        path = safe_path(root, relative)
        before = _stat_fingerprint(path)
        require((before[0], before[1], before[2]) == (guard["device"], guard["inode"], guard["size"]),
                "prior physical object size/inode changed: " + relative)
        require(sha256(path) == guard["sha256"] and _stat_fingerprint(path) == before,
                "prior physical object bytes changed: " + relative)
        return True
    with ThreadPoolExecutor(max_workers=8) as pool:
        require(all(pool.map(check_one, files.items())), "prior object validation failed")
    return len(files)


def check_review_assets(root, native, overlay):
    indexed = _by_id(native["works"], "fresh review asset native scope")
    entries = _by_id(overlay["works"], "fresh review asset scope")
    require(set(entries) == set(indexed), "every appended and inherited native identity requires a completed review")
    jobs = []
    for identity, entry in entries.items():
        work = indexed[identity]
        require(all(entry.get(field) == work.get(field) for field in ("title_en", "composer_en", "source_url")),
                "review native identity drift: " + identity)
        require(isinstance(entry.get("assets"), dict) and set(entry["assets"]) == set(FORMATS), "complete three-format review guards required")
        _check_review(work, entry.get("review"))
        jobs.extend((work, label, guard) for label, guard in entry["assets"].items())
    def check_one(job):
        _check_asset(root, *job)
        return True
    with ThreadPoolExecutor(max_workers=8) as pool:
        require(all(pool.map(check_one, jobs)), "fresh three-format review asset check failed")
    return len(jobs)


def node_offline_adapter(root, expected_records):
    """Exercise the production adapter on the real snapshot, without a UI claim."""
    source = r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),zlib=require('node:zlib');
const codec=require('./public_site/assets/catalog-codec.js'),search=require('./public_site/assets/search.js');
const page=fs.readFileSync('index.html','utf8'),envelope=JSON.parse(page.match(/<script type="application\/json" id="offline-data">([\s\S]*?)<\/script>/)[1]);
const wrapper=envelope.codec?codec.unpack(JSON.parse(zlib.gunzipSync(Buffer.from(envelope.payload,'base64')))):envelope;
class Element{constructor(tag,className='',text=''){this.tag=tag;this.className=className;this.text=text;this.children=[];this.attributes={};}append(...children){this.children.push(...children);}setAttribute(k,v){this.attributes[k]=v;}querySelector(){return null;}insertBefore(child){this.append(child);}}
const descend=node=>[node,...node.children.flatMap(descend)];
const context={window:{},TextEncoder,GuitarSearch:search,makeElement:(...args)=>new Element(...args)};
vm.runInNewContext(fs.readFileSync('scripts/assets/offline-catalog.js','utf8'),context);
const cats=new Map(wrapper.data.categories.map(r=>[r.id,r]));let records=0,controls=0,downloads=0,restricted=0;
for(const item of wrapper.data.works.filter(r=>r.source_id==='musescore')){
 assert.ok(['file_verified','file_reviewed_uncertain'].includes(item.instrumentation_status));
 const article=new Element('article');context.window.GuitarCatalogAdapter.decorateCard(article,{categories:item.category_ids.map(id=>cats.get(id)),item});
 const all=descend(article),links=all.filter(n=>n.className==='local-score-link');
 assert.deepEqual(links.map(n=>n.href).sort(),item.local_editions.flatMap(e=>e.files).map(f=>f.href).sort());
 assert.deepEqual(all.filter(n=>n.className==='local-format').map(n=>n.text),['PDF','MXL','MIDI']);
 for(const link of links){if(link.href.endsWith('.pdf')){assert.equal(link.target,'_blank');assert.equal(link.attributes.download,undefined);}else{const name=link.attributes.download;assert.ok(typeof name==='string'&&name.length);assert.ok(Array.from(name).length<=100);assert.ok(new TextEncoder().encode(name).length<=240);assert.ok(!/[<>:"/\\|?*\u0000-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/.test(name));assert.ok(name.endsWith(` - ${item.source_record_id}.${link.href.endsWith('.mxl')?'mxl':'mid'}`));downloads++;}}
 const filtered=new Element('article');context.window.GuitarCatalogAdapter.decorateCard(filtered,{categories:[],item});
 assert.equal(descend(filtered).filter(n=>n.className==='local-score-link').length,0);records++;controls+=links.length;restricted++;
}
console.log(JSON.stringify({records,controls,downloads,restricted,failures:0}));
'''
    completed = subprocess.run(["node", "-e", source], cwd=root, capture_output=True, text=True, timeout=180)
    require(completed.returncode == 0, "actual final offline adapter VM failed: " + completed.stderr[:3000])
    result = json.loads(completed.stdout)
    require(result == {"records": expected_records, "controls": expected_records * 3,
        "downloads": expected_records * 2, "restricted": expected_records, "failures": 0},
        "actual offline adapter format/category controls differ from the appended native scope")
    return {"method": "Actual final snapshot with production codec/search/adapter in Node VM; no browser/file-protocol UI claim", **result}


def bind_new_csv(root, works, integrity):
    """Independently read all authoritative rows; bind every copied CSV field."""
    expected = _by_id(works, "new native CSV scope")
    path = root / "sources/musescore/pdmx/PDMX.csv"
    proof = integrity["files"]["PDMX.csv"]
    require(list(_stat_fingerprint(path)) == proof["stat"], "authoritative CSV stat differs from fresh digest proof")
    rows, total = {}, 0
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        require(reader.fieldnames and "metadata" in reader.fieldnames and len(reader.fieldnames) == len(set(reader.fieldnames)), "missing or duplicate CSV columns")
        for row in reader:
            total += 1
            require(None not in row and all(value is not None for value in row.values()), "malformed authoritative CSV row")
            try:
                native_id, _ = _metadata_locator(row["metadata"])
            except ValueError:
                continue
            identity = "musescore:" + native_id
            if identity in expected:
                require(identity not in rows, "duplicate authoritative native CSV identity")
                rows[identity] = row
    require(set(rows) == set(expected), "new native identity missing from authoritative CSV")
    for identity, native in expected.items():
        require(native["metadata"]["pdmx_csv_transcription"] == rows[identity],
                "new native full CSV transcription changed: " + identity)
    require(list(_stat_fingerprint(path)) == proof["stat"], "CSV changed during full binding scan")
    return {"dataset_rows": total, "bound_records": len(rows)}


def compare_new_source_fields(work, candidate):
    from source_adapters.pdmx_expansion import validate_candidate
    original, reason, _ = validate_candidate(candidate["csv"], candidate["metadata"])
    require(original is not None, "new source metadata is not independently identity/license/access valid: " + reason)
    for field in ("id", "title_en", "composer_en", "source_url", "category_ids", "formats", "resource_type"):
        require(work.get(field) == original.get(field), "new native source field changed: " + field)
    changed = {"scope_status", "availability", "license_note", "acquisition_status"}
    for key, value in original["metadata"].items():
        if key not in changed:
            require(work["metadata"].get(key) == value, "new source metadata transcription changed: " + key)
    require(work["metadata"].get("scope_status") == "accepted_actual_file_review",
            "new native record has no actual-file acceptance status")


def check_public_review(native, entry, public):
    from catalog_sources import public_source_instrumentation

    review = _check_review(native, entry["review"])
    require(public["instrumentation_status"] == review["status"], "new public file-review status disagrees")
    details = public["details"]
    for key in ("instrumentation", "instrumentation_zh", "guitar_player_count", "ensemble_player_count",
                "file_title", "file_identity_note", "file_part_labels", "written_guitar_part_count", "ensemble_size_note"):
        value = review.get(key)
        expected = str(value) if value is not None and value != "" else None
        require(details.get(key) == expected, "new public file-review field disagrees: " + key)
    summary = review["summary"] + ("；来源差异：" + review["source_difference"] if review["source_difference"] else "")
    expected_source_instrumentation = public_source_instrumentation(native)
    require(details.get("source_instrumentation") == expected_source_instrumentation
            and details.get("instrumentation_review") == summary, "new public source/file instrumentation explanation disagrees")
    require(public["topic_evidence"].get(review["topic_id"]) == "file_crosscheck", "new public instrumentation topic lacks its exact file review")
    return expected_source_instrumentation != native["metadata"].get("instrumentation")


def check_public_source_fields(native, public, title_entry):
    from catalog_translations import display_source_title
    require(isinstance(title_entry, dict) and title_entry.get("original") == native["title_en"],
            "new title review does not retain the complete exact native transcription: " + native["id"])
    expected_title = display_source_title(native["title_en"])
    require(public.get("title_en") == expected_title
            and all(public.get(field) == native[field] for field in ("composer_en", "source_url")),
            "new public source title/attribution/page differs from its exact production projection: " + native["id"])
    return expected_title != native["title_en"]


def check_expansion_statistics(old, native, additions, overlay, final_rows, integration, config, scan_scope, extractions, *, root=None):
    """Recount records, format-local content groups and published summaries."""
    added_ids = {work["id"] for work in additions}
    reviewed = _by_id(overlay["works"], "statistical review scope")
    require(set(final_rows) == added_ids and all(reviewed.get(identity) == final_rows[identity] for identity in added_ids),
            "appended review values differ from completed final decisions")
    topics = dict(Counter(reviewed[identity]["review"]["topic_id"] for identity in added_ids))
    statuses = dict(Counter(reviewed[identity]["review"]["status"] for identity in added_ids))
    require(integration.get("new_topics") == topics and integration.get("new_review_statuses") == statuses,
            "integration topic/review-status statistics differ from appended reviews")
    expected_formats = {}
    for label in FORMATS:
        content = {}
        for work in additions:
            assets = [asset for asset in work["assets"] if asset["format"] == label and asset["status"] == "verified"]
            require(len(assets) == 1, "format statistics require exactly one verified association per added work")
            asset = assets[0]
            require(asset["sha256"] not in content or content[asset["sha256"]] == asset["size"],
                    "same format content digest has conflicting sizes")
            content[asset["sha256"]] = asset["size"]
        counts = dict(Counter(row["status"] for row in extractions[label]["records"].values()))
        require(extractions[label].get("counts") == counts, "extraction status statistics disagree with actual records: " + label)
        expected_formats[label] = {"verified_relations": len(additions), "unique_objects": len(content),
            "unique_bytes": sum(content.values()), "extraction_counts": counts}
    require(integration.get("new_formats") == expected_formats, "integration format statistics differ from acquired associations")
    expected_expansion = {
        "scope_version": config["scope_version"], "configuration_sha256": per_record_guard(config),
        "original_record_count": len(old["works"]), "added_record_count": len(additions),
        "current_record_count": len(native["works"]),
        "full_metadata_records_checked": scan_scope["metadata_records"],
        "full_mxl_records_checked": scan_scope["mxl_records"], "live_source_coverage_complete": False,
        **{key: scan_scope[key] for key in ("mxl_inspected_records", "mxl_validated_records", "mxl_parse_failures",
            "mxl_missing_csv_members", "csv_native_records", "undeclared_mxl_records")},
    }
    require(native.get("snapshot", {}).get("expansion") == expected_expansion,
            "native expansion snapshot statistics disagree with independently checked scope")
    scope_text = config['scope']
    if integration.get('classification_scope'):
        policy = read_json((Path(root) if root is not None else Path(__file__).resolve().parents[1]) / 'config/library_classification.json')
        require(integration['classification_scope'] == policy['new_musescore_scope'], 'unexpected broad classification scope')
        scope_text = policy['new_musescore_scope']
    require(native["snapshot"].get("scope") == scope_text
            and native.get("summary", {}).get("scope") == scope_text, "native source summary scope differs from configuration")
    summary = native["summary"]
    require(summary.get("records") == len(native["works"]) and summary.get("source_records") == len(native["works"]),
            "native summary record totals disagree")
    for label, field in (("PDF", "verified_local_pdfs"), ("MUSICXML", "verified_local_mxl"), ("MIDI", "verified_local_midi")):
        count = sum(any(asset["format"] == label and asset["status"] == "verified" for asset in work["assets"]) for work in native["works"])
        require(summary.get(field) == count, "native summary format totals disagree: " + label)
    return {"topics": topics, "review_statuses": statuses, "formats": expected_formats,
            "format_unique_count_scope": "Distinct content within appended records for each format; not incremental storage savings.",
            "native_expansion_snapshot_exact": True, "native_summary_totals_recounted": True}


def verify(root, baseline_path, *, precheck=False, full_report=None, display_refresh_report=None):
    from catalog_sources import load_registry
    from render_offline_site import offline_input_fingerprint
    from validate_public_site import validate_payload

    root = Path(root).resolve()
    require(precheck or full_report is not None, "final verification requires the actual full-render receipt")
    from expand_musescore_library import active_baseline_path, DEEP_CONTINUATION
    if (root / DEEP_CONTINUATION).exists() or (root / DEEP_CONTINUATION).is_symlink():
        require(Path(baseline_path).resolve() == active_baseline_path(root),
                "a captured deep stage requires its latest published baseline, not the historical continuation")
    before = read_baseline(baseline_path)
    from expand_musescore_library import (check_continuation_state, continuation_review_scope,
        continuation_paths, continuation_guard_paths)
    continuation = check_continuation_state(root, before)
    documents = before["documents"]
    native_bytes = (root / SOURCE).read_bytes()
    native = json.loads(native_bytes)
    old_native = documents[SOURCE]["value"]
    originals, current = _by_id(old_native["works"], "prior native"), _by_id(native["works"], "current native")
    added = set(current) - set(originals)
    require(added and all(re.fullmatch(r"musescore:[1-9][0-9]*", identity) for identity in added),
            "expected an actual append of native MuseScore identities")
    guarded = {Path(baseline_path), root / SOURCE, root / REVIEW, root / BASE / "integration.json"} | final_guard_paths(root)
    stamps = {Path(path): _stat_fingerprint(path) for path in guarded}
    if continuation:
        continuation_path, _ = continuation_paths(root, continuation)
        stamps.update({path: _stat_fingerprint(path) for path in continuation_guard_paths(root, continuation)})
    case_present = (root / EXACT_CASE_PATH).exists() or (root / EXACT_CASE_PATH).is_symlink()
    scope_raw = (root / BASE / "scope-review.json").read_bytes()
    final_raw = (root / BASE / "final-review.json").read_bytes()
    scope, final = json.loads(scope_raw), json.loads(final_raw)
    input_guard_result = check_final_input_guards(root, final, scope)
    require(final["inputs"]["scope_review"] == {"sha256": hashlib.sha256(scope_raw).hexdigest(), "size": len(scope_raw)},
            "parsed scope review differs from final input guard")
    all_final_ids = _by_id(final.get("works"), "final appended file review")
    final_ids = {identity: work for identity, work in all_final_ids.items() if identity not in originals}
    require(scope.get("status") == "complete" and final.get("status") == "complete"
            and set(final_ids) == added <= set(scope["accepted_ids"]),
            "new native scope disagrees with completed cross-format acceptance decisions")
    native_result = compare_existing_records(old_native["works"], native["works"], "native", added)
    require(native["categories"] == old_native["categories"], "native source categories changed")
    for key, value in old_native["snapshot"].items():
        if key not in {"scope", "record_count", "expansion"}:
            require(native["snapshot"].get(key) == value, "frozen native source evidence changed: " + key)
    require(native["snapshot"].get("record_count") == len(current)
            and native.get("summary", {}).get("source_records") == len(current), "current native source counts disagree")
    overlay = read_json(root / REVIEW)
    require({row["id"] for row in documents[REVIEW]["value"]["works"]} == set(originals), "baseline review coverage differs from prior native scope")
    review_result = compare_review_scopes(documents[REVIEW]["value"], overlay, native["works"])
    require(added <= {row["id"] for row in overlay["works"]}, "new records lack completed file-review entries")
    for relative, value in documents.items():
        if relative not in {SOURCE, REVIEW, PUBLIC, ALIASES, RANKING}:
            require(sha256(root / relative) == value["sha256"], "protected historical receipt changed: " + relative)
    new_works = [current[identity] for identity in sorted(added)]
    new_names = {work["composer_en"] for work in new_works}
    new_categories = {category["id"] for category in native["categories"]}
    translation_results = {}
    for relative, value in before["translations"].items():
        if "value" in value:
            translation_results[relative] = compare_translation_asset(relative, value["value"], read_json(root / relative),
                                                                      added, new_names, new_categories)
        else:
            require(Path(relative).name not in APPEND_TRANSLATIONS, "appendable translation baseline requires old entry values")
            translation_results[relative] = {"added_entries": 0}
        if "value" not in value or Path(relative).name not in APPEND_TRANSLATIONS:
            require(sha256(root / relative) == value["sha256"], "protected translation bytes changed: " + relative)
    old_objects = check_old_objects(root, before["files"])
    integrity = read_json(root / BASE / "archive-integrity.json")
    require(integrity.get("status") == "complete", "fresh full-publication verification required")
    config = read_json(root / "config/musescore_pdmx_expansion.json")
    for name, expected in config["files"].items():
        proof = integrity["files"][name]
        require((proof["bytes"], proof["md5"], proof["sha256"]) ==
                (expected["size"], expected["md5"], expected["sha256"])
                and list(_stat_fingerprint(root / "sources/musescore/pdmx" / name)) == proof["stat"],
                "current whole-publication digest/configuration/stat disagreement: " + name)
    csv_result = bind_new_csv(root, new_works, integrity)
    integration = read_json(root / BASE / "integration.json")
    from expand_musescore_library import require_complete_mxl_scan
    mxl_scan_path = root / BASE / "mxl-scope.json"
    mxl_scan = read_json(mxl_scan_path)
    scan_counts = require_complete_mxl_scan(mxl_scan)
    expected_scan_scope = {"metadata_records": csv_result["dataset_rows"], "csv_native_records": scan_counts["csv_native_records"],
        "undeclared_mxl_records": scan_counts["csv_native_records"] - scan_counts["csv_mxl_locators"],
        "mxl_records": scan_counts["unique_mxl_members"], "mxl_inspected_records": scan_counts["inspected_mxl_members"],
        "mxl_validated_records": scan_counts["validated_mxl_members"], "mxl_parse_failures": scan_counts.get("parse_failures", 0),
        "mxl_missing_csv_members": scan_counts["csv_mxl_members_missing_archive"]}
    plan_raw = (root / BASE / "plan.json").read_bytes()
    plan = json.loads(plan_raw)
    require(set(all_final_ids) <= {work['id'] for work in plan['works']},
            'completed final review includes identities outside the frozen candidate plan')
    if continuation:
        require(integration.get('continuation') == {
            'baseline_sha256': sha256(continuation_path),
            'initial_records': continuation['original_record_count'], 'inherited_records': len(originals),
            'earlier_added_records': len(originals) - continuation['original_record_count'],
            'ignored_regenerated_review_ids': sorted(set(all_final_ids) & set(originals)),
            'review_scope': continuation_review_scope(root, added, {work['id'] for work in plan['works']})},
            'continuation integration does not bind inherited publication decisions and explicit review scope')
    require(integration.get("status") == "complete" and integration.get("source_id") == "musescore"
            and integration.get("plan_sha256") == hashlib.sha256(plan_raw).hexdigest()
            and integration.get("configuration_sha256") == sha256(root / "config/musescore_pdmx_expansion.json")
            and integration.get("final_review_sha256") == hashlib.sha256(final_raw).hexdigest()
            and integration.get("output_catalog_sha256") == hashlib.sha256(native_bytes).hexdigest()
            and integration.get("output_overlay_sha256") == sha256(root / REVIEW)
            and integration.get("mxl_scan_sha256") == sha256(mxl_scan_path)
            and mxl_scan.get("fresh_archive_integrity") == integrity["files"]["mxl.tar.gz"]
            and mxl_scan.get("csv_input_stat") == integrity["files"]["PDMX.csv"]["stat"]
            and integration.get("mxl_parse_failure_details") == mxl_scan["parse_failures"]
            and integration.get("mxl_missing_members") == mxl_scan["missing_mxl_members"]
            and all(integration.get("scope", {}).get(key) == value for key, value in expected_scan_scope.items())
            and set(integration.get("added_native_ids", [])) == added
            and (integration.get("original_records"), integration.get("added_records"), integration.get("current_records")) ==
                (len(originals), len(added), len(current)), "completed integration ledger does not bind current source/review/scope")
    candidates_path = root / BASE / "candidate-metadata.json"
    candidate_raw = candidates_path.read_bytes()
    candidates = json.loads(candidate_raw)
    require(candidates.get("status") == "complete" and plan.get("candidate_snapshot_sha256") == hashlib.sha256(candidate_raw).hexdigest(),
            "complete frozen candidate metadata changed after preparation")
    for work in new_works:
        candidate = candidates["records"][work["id"].split(":", 1)[1]]
        compare_new_source_fields(work, candidate)
    del candidates, candidate_raw
    associations = Counter()
    extraction_records = {}
    for label, code in FORMATS.items():
        journal = read_json(root / BASE / (code + "-extraction.json"))
        extraction_records[label] = journal
        require(journal.get("status") == "complete" and journal.get("format") == label
                and journal.get("plan_sha256") == integration["plan_sha256"]
                and journal.get("configuration_sha256") == integration["configuration_sha256"],
                "new format extraction is incomplete: " + label)
        for work in new_works:
            assets = [asset for asset in work["assets"] if asset["format"] == label]
            require(len(assets) == 1 and assets[0].get("status") == "verified", "missing new verified format: " + work["id"])
            asset = assets[0]
            row = work["metadata"]["pdmx_csv_transcription"]
            member = pdf_locator(row[code]) if label == "PDF" else format_locator(row[code], label)
            require(asset.get("archive_member") == member and asset.get("archive_sha256") == integrity["files"][code + ".tar.gz"]["sha256"],
                    "new asset does not bind the exact authoritative archive member: " + work["id"])
            require(journal["records"].get(work["id"], {}).get("asset") == asset,
                    "new asset differs from completed extraction receipt: " + work["id"])
            associations[label] += 1
    statistics = check_expansion_statistics(old_native, native, new_works, overlay, final_ids, integration,
        config, expected_scan_scope, extraction_records, root=root)
    # Match the production reader's exact semantic/file guards in a bounded
    # pool; this audit checks content, not a second structural score import.
    review_assets = check_review_assets(root, native, overlay)
    result = {"schema_version": 1, "status": "precheck_passed_not_final" if precheck else "complete",
        "checked_at": datetime.now(timezone.utc).isoformat(), "baseline_sha256": sha256(baseline_path),
        "native_preservation": native_result, "review_preservation": review_result,
        "prior_fresh_physical_objects": old_objects, "old_translation_entries_exact": True,
        "translation_appends": translation_results, "new_csv_binding": csv_result,
        "new_format_associations": dict(associations), "old_historical_receipts_byte_exact": True,
        "fresh_review_format_guards": review_assets,
        "semantic_review_inputs": input_guard_result,
        "independent_expansion_statistics": statistics,
        "full_mxl_scan": {"inspected": scan_counts["inspected_mxl_members"], "validated": scan_counts["validated_mxl_members"],
            "csv_native_records": scan_counts["csv_native_records"], "undeclared_mxl_records": expected_scan_scope["undeclared_mxl_records"],
            "parse_failures": scan_counts.get("parse_failures", 0), "missing_csv_members": scan_counts["csv_mxl_members_missing_archive"]},
        "completed_final_verification": not precheck}
    if continuation:
        result['continuation_preservation'] = {
            'stage': continuation.get('stage', 'remaining-review'),
            'inherited_records': len(originals), 'original_records': continuation['original_record_count'],
            'baseline_path': continuation_path.relative_to(root).as_posix(),
            'review_scope': continuation_review_scope(root, added, {work['id'] for work in plan['works']}),
            'historical_parent_baselines': continuation.get('parent_baselines', {}),
            'historical_case_entries_outside_new_scope_exact': continuation.get('stage') in {'deep-pending-review', 'broad-pending-review'}}
    # Public/native parity is checked before a long full offline render as well.
    public = read_json(root / PUBLIC)
    validate_payload(public, registry=load_registry(root))
    if continuation and continuation.get('stage') == 'broad-pending-review' and (root / 'metadata/instrumentation/source_classification_reviewed.json').is_file():
        from verify_library_classification import compare_classified_public
        classifications = read_json(root / 'metadata/instrumentation/source_classification_reviewed.json')['entries']
        protected_old_native = {identity: current[identity] for identity in originals}
        result['public_preservation'] = compare_classified_public(
            documents[PUBLIC]['value'], public, classifications, protected_old_native)
        require({w['id'] for w in public['works']} - {w['id'] for w in documents[PUBLIC]['value']['works']} == added,
                'broad public append identity scope differs')
    else:
        result["public_preservation"] = compare_existing_records(documents[PUBLIC]["value"]["works"], public["works"], "public", added)
    result["public_structure"] = compare_public_structure(documents[PUBLIC]["value"], public, added,
        classification_update=bool(continuation and continuation.get('stage') == 'broad-pending-review'))
    public_ids = _by_id(public["works"], "new public identity binding")
    overlay_ids = _by_id(overlay["works"], "new public review binding")
    title_entries = read_json(root / "metadata/translations/source_titles_zh.json")["entries"]
    projected_title_count = 0
    source_declaration_repairs = 0
    for work in new_works:
        projected = public_ids[work["id"]]
        require(projected["source_id"] == "musescore" and projected["source_record_id"] == work["id"].split(":", 1)[1],
                "new public native source identity changed")
        projected_title_count += check_public_source_fields(work, projected, title_entries.get(work["id"]))
        source_declaration_repairs += check_public_review(work, overlay_ids[work["id"]], projected)
    result["public_source_identity"] = {"records": len(new_works), "exact_native_title_review_guards": True,
        "title_projection": "Exact shared display_source_title output; native/source review originals remain unchanged.",
        "projected_titles": projected_title_count, "composer_and_page_exact": True,
        "source_declaration_projection_repairs": source_declaration_repairs}
    result['source_declaration_projection_repairs'] = {
        'previously_published_records': result['public_preservation'].get('source_declaration_projection_repairs', 0),
        'newly_added_records': source_declaration_repairs,
    }
    require(unpack_payload(read_json(root / "public_site/data/catalog.compact.json")) == public, "compact catalog differs from canonical JSON")
    for relative in (ALIASES, RANKING):
        require(sha256(root / relative) == documents[relative]["sha256"], "search aliases or recognition ranking changed")
    result.update(compact_matches_canonical=True, search_aliases_ranking_exact=True)
    if not precheck:
        wrapper, offline_sha = decode_offline(root / "index.html")
        require(offline_sha != before["offline_sha256"], "offline entry has not been rebuilt after expansion")
        old_offline = before["offline_snapshot"]
        data = wrapper["data"]
        require(wrapper["aliases"] == old_offline["aliases"] and wrapper["ranking"] == old_offline["ranking"], "offline aliases/ranking changed")
        old_rows = old_offline['data']['works']
        removed = 0
        if continuation and continuation.get('stage') == 'broad-pending-review':
            from verify_library_classification import corrected_offline_baseline
            old_rows, removed = corrected_offline_baseline(root, old_rows)
        result["offline_preservation"] = compare_offline_records(old_rows, data["works"], public["works"])
        result['offline_preservation']['reviewed_mismatched_file_links_removed_originals_retained'] = removed
        require(data["offline_inputs"] == offline_input_fingerprint(root), "offline acquisition/configuration/review fingerprint is stale")
        require([{k: v for k, v in row.items() if k != "local_href"} for row in data["categories"]] == public["categories"],
                "offline/public category fields differ")
        for key, value in public.items():
            if key not in {"works", "categories", "integrity"}:
                require(data.get(key) == value, "offline/public top-level fields differ: " + key)
        links = set()
        offline_ids = _by_id(data["works"], "offline format links")
        for work in new_works:
            check_new_offline_links(work, offline_ids[work["id"]])
        for work in data["works"]:
            links.update(file["href"] for edition in work["local_editions"] for file in edition["files"])
        links.update(category["local_href"] for category in data["categories"] if category.get("local_href"))
        with ThreadPoolExecutor(max_workers=8) as pool:
            checked = list(pool.map(lambda href: check_local_link(root, href), sorted(links)))
        require(len(checked) == len(links), "local link scope differs")
        if full_report is not None:
            full = read_json(full_report)
            require({key: value for key, value in full.items() if key != "index"} == data["offline_summary"]
                    and "mode" not in full and "input_guard" not in full,
                    "fresh full-render receipt differs from the offline snapshot")
            if display_refresh_report is not None:
                from offline_display_refresh import validate_display_refresh
                refresh = validate_display_refresh(root, full_report, display_refresh_report)
                result["offline_display_refresh"] = refresh
            else:
                from offline_display_refresh import require_fresh_full_render_report
                require_fresh_full_render_report(full_report, root / "index.html")
        else:
            require(display_refresh_report is None,
                    "display-refresh evidence requires a full-render receipt")
        result.update(compact_matches_canonical=True, search_aliases_ranking_exact=True,
                      local_links_checked=len(links), local_links_failed=0,
                      offline_adapter=node_offline_adapter(root, len(current)))
    require(all(_stat_fingerprint(path) == stamp for path, stamp in stamps.items()), "verification inputs changed during audit")
    require(case_present == ((root / EXACT_CASE_PATH).exists() or (root / EXACT_CASE_PATH).is_symlink()),
            "exact reviewed-case asset presence changed during audit")
    require((root / SOURCE).read_bytes() == native_bytes, "native catalog changed during audit")
    require(sha256(root / BASE / "final-review.json") == hashlib.sha256(final_raw).hexdigest(),
            "completed final review changed during audit")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--full-render-report", type=Path)
    parser.add_argument("--display-refresh-report", type=Path,
                        help="guarded receipt for the exact metadata-only source declaration refresh")
    parser.add_argument("--precheck", action="store_true")
    parser.add_argument("--capture-offline", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    from expand_musescore_library import active_baseline_path
    baseline = args.baseline or active_baseline_path(root)
    if args.capture_offline:
        result = capture_offline_baseline(root, baseline)
    else:
        result = verify(root, baseline, precheck=args.precheck, full_report=args.full_render_report,
                        display_refresh_report=args.display_refresh_report)
        _atomic_json(args.output or root / BASE / "preservation.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
