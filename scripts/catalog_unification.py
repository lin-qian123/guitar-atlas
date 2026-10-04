"""Shared browsing vocabulary and evidence-backed edges, without identity merging."""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

TOPICS = [
    ("solo", "吉他独奏", "Guitar solo"), ("duo", "吉他二重奏", "Guitar duo"),
    ("trio", "吉他三重奏", "Guitar trio"), ("quartet", "吉他四重奏", "Guitar quartet"),
    ("guitar_ensemble", "吉他合奏", "Guitar ensemble"),
    ("strings", "吉他与弦乐", "Guitar and strings"), ("woodwinds", "吉他与木管", "Guitar and woodwinds"),
    ("brass", "吉他与铜管", "Guitar and brass"), ("keyboard_reed", "吉他与键盘／自由簧", "Guitar and keyboard"),
    ("plucked", "吉他与其他拨弦", "Guitar and plucked instruments"),
    ("percussion", "吉他与打击乐", "Guitar and percussion"), ("mixed_chamber", "吉他室内乐", "Guitar chamber music"),
    ("studies", "练习曲与教学", "Studies and methods"), ("historical", "历史谱与馆藏", "Historical collections"),
    ("reference", "参考资料", "Reference material"), ("unspecified", "编制尚未核明", "Instrumentation unspecified"),
    ("guitar_unspecified", "吉他·人数未明", "Guitar, player count unspecified"),
]
FORM_PATTERN = re.compile(r"\b(etude[s]?|étude[s]?|stud(?:y|ies)|method|méthode|schule|exercise[s]?|exercice[s]?|leçon[s]?|lesson[s]?)\b", re.I)
ARCHIVES = {"boije", "rism", "dga", "loc", "gallica", "rischel", "riam_hudleston"}


def instrumentation_topic(text: str) -> str | None:
    """Use an explicit instrumentation label, never the website's reputation."""
    value = re.sub(r"\s+", " ", text.casefold()).strip()
    if value in {"guitar", "classical guitar", "guit"}:
        return "guitar_unspecified"
    if match := re.fullmatch(r"guit\s*\(([1-9][0-9]*)\)", value):
        count = int(match.group(1))
        return {1:"solo", 2:"duo", 3:"trio", 4:"quartet"}.get(count, "guitar_ensemble")
    patterns = {
        "solo": r"(?:for )?(?:solo guitar|guitar solo|classical guitar|guitar|1 guitar|guitare seule|guitarra sola)(?: \(arr\))?",
        "duo": r"(?:for )?(?:2 guitars|two guitars|guitar duo|guitar duet|duo guitars|guitar duo/duet)(?: \(arr\))?",
        "trio": r"(?:for )?(?:3 guitars|three guitars|guitar trio)(?: \(arr\))?",
        "quartet": r"(?:for )?(?:4 guitars|four guitars|guitar quartet)(?: \(arr\))?",
        "guitar_ensemble": r"(?:for )?(?:[5-9]\d* guitars|guitar ensemble|guitar orchestra)(?: \(arr\))?",
    }
    for topic, pattern in patterns.items():
        if re.fullmatch(pattern, value):
            return topic
    parts = re.split(r"\s*(?:,| and | & )\s*", value.removeprefix("for "))
    groups = {"strings":{"violin", "viola", "cello", "violoncello", "double bass"},
              "woodwinds":{"flute", "recorder", "clarinet", "oboe", "bassoon"},
              "brass":{"trumpet", "horn", "trombone", "tuba"},
              "keyboard_reed":{"piano", "organ", "harpsichord", "accordion"},
              "plucked":{"harp", "mandolin", "lute", "vihuela"},
              "percussion":{"marimba", "vibraphone", "percussion"}}
    if "guitar" in parts and len(parts) > 1:
        others = [part for part in parts if part != "guitar"]
        selected = {key for key, names in groups.items() if any(part in names for part in others)}
        if selected and all(any(part in groups[key] for key in selected) for part in others):
            return next(iter(selected)) if len(selected) == 1 else "mixed_chamber"
    return None


def file_key(value: str) -> str:
    try:
        url = urlsplit(value)
        hostname = url.hostname
    except (ValueError, TypeError, AttributeError):
        return ""
    urns = parse_qs(url.query, keep_blank_values=True).get("urn", [])
    urn_file = (hostname == "urn.kb.se" and url.path == "/resolve" and len(urns) == 1 and urns[0].startswith("urn:nbn:se:"))
    if (url.scheme not in {"http", "https"} or not url.hostname
            or not (re.search(r"\.(?:pdf|zip)$", unquote(url.path), re.I)
                    or urn_file)):
        return ""
    # Scheme upgrades do not change which published file a source cites.
    return (url.hostname or "").casefold() + unquote(url.path) + ("?" + url.query if url.query else "")


def unify_catalog(root: Path, data: dict, registry: list[dict]) -> None:
    private = {}
    for source in registry:
        if source.get("catalog"):
            payload = json.loads((root / source["catalog"]).read_text(encoding="utf-8"))
            private.update((work["id"], work) for work in payload["works"])
    categories = {row["id"]: row for row in data["categories"]}
    counts, sources = Counter(), defaultdict(set)
    files, hashes = defaultdict(set), defaultdict(set)
    known = {row["id"] for row in data["works"]}
    for work in data["works"]:
        raw = private.get(work["id"], {})
        topics, basis, topic_memberships = set(), {}, {}
        for category_id in work["category_ids"]:
            category = categories[category_id]
            topic = None
            if work["source_id"] == "imslp":
                if category["family"] == "pure":
                    topic = instrumentation_topic(category["name"])
                else:
                    topic = category["family"]
            if topic:
                topics.add(topic)
                basis[topic] = "approved_source_category"
                topic_memberships.setdefault(topic, []).append(category_id)
        metadata = raw.get("metadata", {})
        instrument = metadata.get("instrumentation", "")
        if isinstance(instrument, str) and instrument and metadata.get("scope_status") != "pending_review":
            topic = instrumentation_topic(instrument)
            if topic:
                topics.add(topic)
                basis[topic] = "explicit_source_instrumentation"
        if not topics:
            topics.add("unspecified")
            basis["unspecified"] = "no_exact_instrumentation_evidence"
        if work.get("resource_type") == "reference":
            topics.add("reference")
            basis["reference"] = "source_resource_type"
        if FORM_PATTERN.search(work["title_en"]):
            topics.add("studies")
            basis["studies"] = "title_keyword"
        if work["source_id"] in ARCHIVES:
            topics.add("historical")
            basis["historical"] = "archival_source"
        work["topic_ids"] = sorted(topics)
        work["topic_evidence"] = basis
        work["topic_category_ids"] = {topic: sorted(topic_memberships.get(topic, work["category_ids"])) for topic in sorted(topics)}
        counts.update(topics)
        for topic in topics:
            sources[topic].add(work["source_id"])
        for asset in raw.get("assets", []):
            if asset.get("source_url") and (key := file_key(asset["source_url"])):
                files[key].add(work["id"])
            if asset.get("status") == "verified" and asset.get("sha256"):
                hashes[asset["sha256"]].add(work["id"])
            if asset.get("status") == "verified":
                for member in asset.get("members", []):
                    if member.get("status") == "verified" and member.get("sha256"):
                        hashes[member["sha256"]].add(work["id"])
        # Upstream explicit cross-references, never a guessed title match.
        for url in raw.get("file_references", []):
            if isinstance(url, str) and (key := file_key(url)):
                files[key].add(work["id"])
        for key in ("digital_file", "digital_url"):
            if isinstance(metadata.get(key), str) and (value := file_key(metadata[key])):
                files[value].add(work["id"])
    edges = set()
    from verified_source_relations import verified_identical_pdf_pairs
    for left, right in verified_identical_pdf_pairs(root, known):
        edges.add((left, right, "identical_pdf"))
    for identity, raw in private.items():
        metadata = raw.get("metadata", {})
        for target in (metadata.get("related_source_ids", []) if raw.get("id", "").startswith("dga:")
                       and metadata.get("related_source_basis") == "exact source siglum and native shelfmark" else []):
            if identity in known and target in known and identity != target:
                left, right = sorted((identity, target))
                edges.add((left, right, "holding_record"))
        for relation in metadata.get("related_source_relations", []):
            target = relation.get("target_id")
            if (relation.get("type") == "collection_membership" and relation.get("basis") == "explicit_source_collection_structure"
                    and identity in known and target in known and identity != target):
                left, right = sorted((identity, target))
                edges.add((left, right, "collection_membership"))
    for groups, relation in ((files, "shared_source_file"), (hashes, "identical_pdf")):
        for identities in groups.values():
            if len(identities) < 2:
                continue
            ordered = sorted(identities)
            # Star edges avoid quadratic growth for anthology/file mirrors.
            for other in ordered[1:]:
                if other in known and ordered[0] in known:
                    edges.add((ordered[0], other, relation))
    data["topics"] = [{"id": key, "name_zh": zh, "name_en": en, "work_count": counts[key],
                       "source_count": len(sources[key])} for key, zh, en in TOPICS]
    data["relationships"] = [{"from_id": left, "to_id": right, "type": kind,
                               "basis": {"identical_pdf":"verified_file_content", "shared_source_file":"explicit_upstream_file_reference", "holding_record":"explicit_institution_and_call_number", "collection_membership":"explicit_source_collection_structure"}[kind]}
                              for left, right, kind in sorted(edges)]
    data["unification_schema_version"] = 1
    data["summary"].update(topic_count=len(TOPICS), relationship_count=len(edges),
                           score_record_count=sum(work.get("resource_type") == "score" for work in data["works"]),
                           reference_record_count=sum(work.get("resource_type") == "reference" for work in data["works"]))
