#!/usr/bin/env python
"""Audit every catalog text field; separate detectable defects from review clues.

This is a reproducible text/notation check, not a certification of translations,
source identity, instrumentation or PDF integrity. Brackets in bibliographic
transcriptions and editorial supplied titles are not errors in themselves.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from imslp_library.title_review import title_quality_flags

CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ufffd]")
MARKUP = re.compile(r"</?[A-Za-z][^>]*>|\[/?(?:caption|vc_[a-z_]+|url|img|audio|video)(?:\s[^]]*)?\]|\ba\s+href\s*=", re.I)
OP = re.compile(r"(?<!\w)(?:op(?:us)?\.?|作品号)\s*[:：]?\s*(\d+)", re.I)
NUMBER = re.compile(r"(?<!\w)(?:no(?:s)?\.?|nr\.?|n[º°])\s*(\d+)", re.I)
AIR = re.compile(r"(?<!\w)airs?(?!\w)", re.I)
SUITE = re.compile(r"(?<!\w)suites?(?!\w)", re.I)
MINOR_KEY = re.compile(r"(?<!\w)[A-G](?:[ -](?:flat|sharp))?[- ]+(?:minor|moll)(?!\w)", re.I)
MAJOR_KEY = re.compile(r"(?<!\w)[A-G](?:[ -](?:flat|sharp))?[- ]+(?:major|dur)(?!\w)", re.I)
DATE_NOTE = re.compile(r"<\s*(?:\d{3,4}|\?)[^<>]*>")
BOOK_NOTES = re.compile(r"\[(?:Handskrift|Manuscript|Ms\.?|Arr\.?|Bearb\.?|Transcription|Ed\.?|手稿|编曲|改编|扫描|馆藏)[^]]*\]", re.I)
REVIEW_LABEL = re.compile(r"[（(](?:(?:原|源)目录标记[:：]|调性标记[:：]|歌剧题名含补入标记|册号及作品号依此来源)")


def title_number_defects(original: str, translated: str) -> list[tuple[str, str]]:
    """Only flag lost explicit digits for Op and No, not every source digit.

    Bibliographic years/page sizes need not appear in the displayed title, and
    Chinese written-out numbers are reviewed separately rather than rejected.
    """
    if not re.search(r"[\u3400-\u9fff]", translated):
        return []
    result = []
    for label, pattern in (("opus", OP), ("number", NUMBER)):
        for value in pattern.findall(original):
            if not re.search(r"(?<!\d)" + re.escape(value) + r"(?!\d)", translated, re.I):
                result.append((f"{label}_digit_review", value))
    return result


def audit(data: dict) -> dict:
    findings: list[dict] = []
    field_counts, source_counts = Counter(), Counter()
    review_states = Counter()

    def finding(row, field, value, rule, severity, note, original=""):
        findings.append({"source_id": row["source_id"], "id": row["id"],
                         "field": field, "rule": rule, "severity": severity,
                         "text": value, "original": original, "note": note})

    def inspect(row, field, value, original="", proof=None):
        if not isinstance(value, str):
            finding(row, field, str(value), "non_text_value", "error", "Expected a text field.", original)
            return
        field_counts[field] += 1
        source_counts[row["source_id"]] += 1
        if CONTROL.search(value):
            finding(row, field, value, "control_or_replacement_character", "error", "Display contains control/replacement characters.", original)
        if MARKUP.search(value):
            finding(row, field, value, "rendered_markup", "error", "HTML/CMS/link syntax must not appear as title/attribution text.", original)
        if field.endswith("_zh") and (value.count("《") != value.count("》")):
            finding(row, field, value, "unbalanced_chinese_title_marks", "error", "Chinese title marks are unbalanced.", original)
        if field.startswith("title") or field.startswith("display_title"):
            if "[" in value or "]" in value:
                if value.count("[") != value.count("]"):
                    finding(row, field, value, "unbalanced_source_brackets", "review", "May be literal catalog transcription; inspect display separation, never strip all brackets.", original)
                elif BOOK_NOTES.search(value):
                    finding(row, field, value, "bibliographic_title_annotation", "info", "An explicit manuscript/edition annotation may be separated from primary title.", original)
            if field.endswith("_zh"):
                if REVIEW_LABEL.search(value):
                    finding(row, field, value, "review_label_in_primary_title", "error", "Review labels belong in edition details, not the primary title.", original)
                if OP.search(original) and re.search(r"操作|手术|运算|作品\s*[。．]\s*\d", value):
                    finding(row, field, value, "opus_mistranslation", "error", "Op. is the musical opus abbreviation.", original)
                if NUMBER.search(original) and re.search(r"第\s*\d+\s*名", value) and not re.search(r"prize|award|winner", original, re.I):
                    finding(row, field, value, "number_as_rank", "error", "Musical No. must not become a competition rank.", original)
                if AIR.search(original) and "空气" in value:
                    finding(row, field, value, "air_music_sense", "review", "Air often means a tune/aria; a literal descriptive work title requires exact review.", original)
                if SUITE.search(original) and "套房" in value:
                    finding(row, field, value, "suite_music_sense", "error", "Suite in musical title means a suite, not accommodation.", original)
                if MINOR_KEY.search(original) and re.search(r"未成年|未成年人", value):
                    finding(row, field, value, "minor_key_music_sense", "error", "Minor key is not an age description.", original)
                if MAJOR_KEY.search(original) and re.search(r"专业|少校", value):
                    finding(row, field, value, "major_key_music_sense", "error", "Major key is not a military rank/degree.", original)
                for rule, number in title_number_defects(original, value):
                    finding(row, field, value, rule, "review", f"Explicit source number {number} absent as a digit; check Chinese-written numerals or separated metadata.", original)
                for rule in title_quality_flags(original, value):
                    finding(row, field, value, f"music_terminology_{rule}", "review", "Music-domain sense needs exact title/context review; this clue alone is not a semantic verdict.", original)
        if field.startswith("composer") and DATE_NOTE.search(value):
            finding(row, field, value, "attribution_date_annotation", "info", "A source authority date annotation is not part of the person's name.", original)
        if proof:
            review_states[f"{field}:{proof.get('status', 'missing')}"] += 1

    for row in data["works"]:
        for field in ("title_en", "title_zh", "composer_en", "composer_zh"):
            # Assess the effective primary text; raw bibliographic originals stay
            # searchable and available as provenance after display separation.
            effective_field = f"display_{field}" if row.get(f"display_{field}") else field
            original = row["title_en"] if "title" in field else row.get("composer_en", "")
            proof = row.get("translation", {}).get("title" if "title" in field else "composer") if field.endswith("_zh") else None
            inspect(row, effective_field, row.get(effective_field, ""), original, proof)
        for field, value in row.get("details", {}).items():
            inspect(row, f"details.{field}", value)
        for index, value in enumerate(row.get("contents", [])):
            inspect(row, f"contents.{index}", value)
    for row in data["categories"]:
        for field in ("name", "name_zh"):
            inspect(row, field, row.get(field, ""), row.get("name", ""), row.get("translation") if field.endswith("_zh") else None)
    counts = Counter((item["severity"], item["rule"]) for item in findings)
    return {"schema_version": 1,
            "scope": "All published record title/attribution, category, edition-details and collection-content text. Detection rules and review clues; not individual authoritative-name certification.",
            "record_count": len(data["works"]), "category_count": len(data["categories"]),
            "source_count": len(data["sources"]), "text_field_count": sum(field_counts.values()),
            "field_counts": dict(sorted(field_counts.items())), "source_text_counts": dict(sorted(source_counts.items())),
            "translation_states": dict(sorted(review_states.items())),
            "counts": {severity: {rule: count for (kind, rule), count in sorted(counts.items()) if kind == severity}
                       for severity in ("error", "review", "info")},
            "ready_for_detected_defects": not any(item["severity"] == "error" for item in findings),
            "findings": findings}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", nargs="?", type=Path, default=Path("public_site/data/catalog.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit(json.loads(args.catalog.read_text(encoding="utf-8")))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "findings"}, ensure_ascii=False, indent=2))
    return 0 if report["ready_for_detected_defects"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
