"""Apply persistent, source-scoped display translations without altering identity.

Acquisition snapshots deliberately do not own reviewed display text. Every entry
is guarded by its exact original value, so upstream title changes require review.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from catalog_display import apply_display_projection, safe_transcription, source_transcription

STATES = {"reviewed", "reference", "retained", "machine", "untranslated", "not_applicable"}
HAN = re.compile(r"[\u3400-\u9fff]")


def wrap_display_title(value: str) -> str:
    """Wrap the whole title once without stripping inner title punctuation.

    A leading book-title mark belongs to the whole string only when its matching
    closing mark is the final character. Inner marks use the conventional 〈〉.
    Source text/translation asset guards are unaffected by this presentation.
    """
    text = value.strip()
    if text.startswith("《") and text.endswith("》"):
        depth, whole = 0, True
        for index, character in enumerate(text):
            if character == "《":
                depth += 1
            elif character == "》":
                depth -= 1
            if depth == 0 and index != len(text)-1:
                whole = False
                break
        if whole and depth == 0:
            text = text[1:-1]
    return "《" + text.replace("《", "〈").replace("》", "〉") + "》"


def display_source_title(original: str) -> str:
    """Remove a broken inline link suffix, leaving the title wording intact.

    The untouched input stays in the private source snapshot and review asset.
    Some source tables contain `title a href=…>MIDI` as visible text.
    """
    text = re.sub(r'''\s+a\s+href\s*=\s*["“”']https?://[^>]+>.*$''', "", original, flags=re.I).strip()
    # Some directories use a filename as their label. The extension is format
    # metadata; the exact raw label remains in the snapshot/review asset.
    return re.sub(r"\.(?:pdf|mid|midi|gpx|gp[3-8]|zip)$", "", text, flags=re.I).strip()


def aggregate_status(fields: dict) -> str:
    states = {field["status"] for field in fields.values()}
    return next((status for status in ("untranslated", "machine", "reference", "reviewed")
                 if status in states), "retained")


def evidence(status: str, basis: str = "", reason: str = "") -> dict:
    return {"status": status, "basis": basis, "reason": reason}


def read_asset(root: Path, name: str) -> dict:
    path = root / "metadata/translations" / name
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or not isinstance(payload.get("entries"), dict):
        raise ValueError(f"invalid translation asset: {name}")
    return payload["entries"]


def checked_entry(entry: dict, original: str, context: str) -> tuple[str, dict]:
    if not isinstance(entry, dict) or entry.get("original") != original:
        raise ValueError(f"translation original drift: {context}")
    if any(not isinstance(entry.get(key), str) for key in ("zh", "status", "basis", "reason")):
        raise ValueError(f"invalid translation entry: {context}")
    status, zh = entry["status"], entry["zh"]
    if status not in STATES:
        raise ValueError(f"unknown translation status: {context}")
    if status in {"reviewed", "reference", "machine"} and (not HAN.search(zh) or not entry["basis"].strip()):
        raise ValueError(f"translation needs Chinese text and basis: {context}")
    if status == "retained" and (not zh.strip() or not entry["reason"].strip() or not entry["basis"].strip()):
        raise ValueError(f"retained translation needs a reason: {context}")
    if status == "untranslated" and zh:
        raise ValueError(f"untranslated field has display text: {context}")
    if status == "not_applicable" and (original or zh):
        raise ValueError(f"not_applicable field has source text: {context}")
    return zh, evidence(status, entry["basis"], entry["reason"])


def fallback(original: str, zh: str) -> tuple[str, dict]:
    if not original:
        return "", evidence("not_applicable", reason="来源未提供署名。")
    if not zh or not HAN.search(zh):
        # Keeping an original spelling is a review decision, not an import default.
        return "", evidence("untranslated")
    return zh, evidence("machine", "legacy_import", "既有参考文本，尚无逐字段复核记录。")


def apply_translations(root: Path, data: dict) -> dict:
    """Keep source IDs and original fields untouched; attach field-level evidence."""
    if data.get("schema_version") != 2:
        return data
    titles = read_asset(root, "classclef_titles_zh.json")
    extra_titles = read_asset(root, "source_titles_zh.json")
    if set(titles) & set(extra_titles):
        raise ValueError("duplicate title translation identities")
    titles = {**titles, **extra_titles}
    musicians = read_asset(root, "musicians_zh.json")
    categories = read_asset(root, "categories_zh.json")
    reviewed_path = root / "metadata/translations/title_overrides_reviewed_zh.json"
    reviewed = {}
    if reviewed_path.exists():
        payload = json.loads(reviewed_path.read_text(encoding="utf-8"))
        reviewed = {str(row["work_id"]): row for row in payload["entries"]}
    composer_review = read_asset(root, "composer_overrides_reviewed_zh.json")
    seen_titles, seen_musicians, seen_categories, seen_reviewed = set(), set(), set(), set()
    for work in data["works"]:
        source, identity = work["source_id"], work["id"]
        title_review = None
        original = work["title_en"]
        title, title_evidence = fallback(original, work["title_zh"])
        if source == "imslp" and identity in reviewed:
            row = reviewed[identity]
            title_review = row
            if row["title_en"] != original:
                raise ValueError(f"reviewed IMSLP title original drift: {identity}")
            title = row["title_zh"]
            # A historical corpus/terminology pass establishes a reference
            # translation, not an authoritative conventional Chinese title.
            retention_reason = row.get("retention_reason", "")
            if not isinstance(retention_reason, str):
                raise ValueError(f"invalid IMSLP title retention reason: {identity}")
            # Translating a number or arrangement note does not resolve an
            # explicitly retained title. Its concrete disposition takes
            # precedence over the mere presence of Chinese characters.
            status = "retained" if retention_reason.strip() or not HAN.search(title) else (
                "reviewed" if row["basis"] == "common_name" else "reference")
            reason = retention_reason.strip() or row["reason"] if status == "retained" else row["reason"]
            title_evidence = evidence(status, str(row["basis"]), str(reason))
            seen_reviewed.add(identity)
        if source != "imslp" and identity in titles:
            row = titles[identity]
            title_review = row
            title, title_evidence = checked_entry(row, original, identity)
            aliases = row.get("aliases_zh", [])
            if not isinstance(aliases, list) or any(not isinstance(alias, str) or not alias.strip() for alias in aliases):
                raise ValueError(f"invalid translated title aliases: {identity}")
            work["title_aliases"] = list(dict.fromkeys([*work.get("title_aliases", []), *aliases]))
            seen_titles.add(identity)
        if title_review and "original_composer" in title_review and title_review["original_composer"] != work["composer_en"]:
            raise ValueError(f"reviewed title attribution drift: {identity}")
        original = work["composer_en"]
        composer, composer_evidence = fallback(original, work["composer_zh"])
        if source == "imslp" and original in composer_review:
            composer = composer_review[original]
            composer_evidence = evidence("reviewed", "reviewed_composer_override", "既有音乐家译名复核表。")
        if original in musicians.get(source, {}):
            composer, composer_evidence = checked_entry(musicians[source][original], original, f"{source}: {original}")
            seen_musicians.add((source, original))
        work.update(title_zh=title, composer_zh=composer,
                    translation={"title": title_evidence, "composer": composer_evidence})
        work["translation_status"] = aggregate_status(work["translation"])
        cleaned = display_source_title(work["title_en"])
        if cleaned != work["title_en"]:
            work["title_en"] = cleaned
            work["source_title_note"] = "显示时移除来源标题中的损坏链接标记或文件格式后缀；原始来源记录保留。"
        if work["title_zh"]:
            work["title_zh"] = wrap_display_title(display_source_title(work["title_zh"]))
        apply_display_projection(work)
        # An exact semantic review can translate just the primary title after
        # bibliographic responsibility/material fields have been separated.
        # Guard that reviewed boundary as well as the untouched source title.
        if title_review and "display_zh" in title_review:
            expected = title_review.get("display_original")
            current = work.get("display_title_en", work["title_en"])
            if not isinstance(expected, str) or expected != current:
                raise ValueError(f"reviewed display title original drift: {identity}")
            display = title_review["display_zh"]
            if not isinstance(display, str) or not display.strip():
                raise ValueError(f"invalid reviewed display title: {identity}")
            if title_evidence["status"] not in {"reference", "reviewed", "retained"}:
                raise ValueError(f"unreviewed primary display title: {identity}")
            work["display_title_zh"] = wrap_display_title(display_source_title(display))
            # The exact reviewed primary title is applied after generic display
            # projection. Preserve the complete reference transcription against
            # this final boundary as well, including source credit/reading notes.
            if work["display_title_zh"] != work["title_zh"] and safe_transcription(work["title_zh"]):
                work.setdefault("details", {})["translated_title_transcription"] = source_transcription(work["title_zh"])
            else:
                work.get("details", {}).pop("translated_title_transcription", None)
    for category in data["categories"]:
        source = category["source_id"]
        key = str(category.get("source_category_id", category["name"]))
        zh, proof = fallback(category["name"], category["name_zh"])
        if source == "imslp":
            proof = evidence("reviewed", "configured_instrumentation", "按批准的编制配置翻译。")
        if key in categories.get(source, {}):
            zh, proof = checked_entry(categories[source][key], category["name"], f"{source} category {key}")
            seen_categories.add((source, key))
        category.update(name_zh=zh, translation=proof)
    # Catch a silently stale asset or mistyped identity instead of dropping it.
    expected_musicians = {(source, key) for source, rows in musicians.items() for key in rows}
    expected_categories = {(source, key) for source, rows in categories.items() for key in rows}
    for name, missing in (("titles", set(titles) - seen_titles),
                          ("IMSLP titles", set(reviewed) - seen_reviewed),
                          ("musicians", expected_musicians - seen_musicians),
                          ("categories", expected_categories - seen_categories)):
        if missing:
            raise ValueError(f"translation {name} absent from current snapshot: {sorted(missing)[0]}")
    data["translation_schema_version"] = 1
    data["translation_summary"] = translation_summary(data)
    data["works"].sort(key=lambda row: (row["composer_en"].casefold(), row["title_en"].casefold(), row["id"]))
    return data


def translation_summary(data: dict) -> dict:
    result = {}
    for source in data["sources"]:
        identity = source["id"]
        works = [row for row in data["works"] if row["source_id"] == identity]
        categories = [row for row in data["categories"] if row["source_id"] == identity]
        result[identity] = {
            field: dict(sorted(Counter(row["translation"][field]["status"] for row in works).items()))
            for field in ("title", "composer")
        }
        result[identity]["category"] = dict(sorted(Counter(row["translation"]["status"] for row in categories).items()))
    return result
