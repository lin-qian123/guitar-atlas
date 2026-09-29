#!/usr/bin/env python
"""Measure display coverage separately from reference and conventional names.

This gate detects missing/unreviewed fields and stale summary counts; it does
not prove that a reference translation is an authoritative or unique name.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from catalog_translations import translation_summary
from validate_public_site import validate_payload


def audit(data: dict) -> dict:
    validate_payload(data)
    if data.get("translation_schema_version") != 1:
        raise ValueError("field-level translation evidence is required")
    summary = translation_summary(data)
    if data.get("translation_summary") != summary:
        raise ValueError("translation summary is stale")
    pending, retained, chinese = [], [], {}
    for source in data["sources"]:
        works = [row for row in data["works"] if row["source_id"] == source["id"]]
        categories = [row for row in data["categories"] if row["source_id"] == source["id"]]
        chinese[source["id"]] = {"records": len(works), "categories": len(categories),
            "chinese_titles": sum(bool(re.search(r"[\u3400-\u9fff]", row["title_zh"])) for row in works),
            "attributed_records": sum(bool(row["composer_en"]) for row in works),
            "chinese_attributions": sum(bool(re.search(r"[\u3400-\u9fff]", row["composer_zh"])) for row in works),
            "chinese_categories": sum(bool(re.search(r"[\u3400-\u9fff]", row["name_zh"])) for row in categories)}
    for collection in ("works", "categories"):
        for row in data[collection]:
            fields = row["translation"] if collection == "works" else {"category": row["translation"]}
            for field, proof in fields.items():
                item = {"source_id": row["source_id"], "id": row["id"], "field": field,
                        "original": row.get({"title": "title_en", "composer": "composer_en", "category": "name"}[field]),
                        **proof}
                if proof["status"] in {"machine", "untranslated"}:
                    pending.append(item)
                elif proof["status"] == "retained":
                    retained.append(item)
    return {"schema_version": 1, "scope": "Published frozen catalog; text coverage and field-level review states, not authoritative-name certification or PDF validation.",
            "summary": summary, "coverage": chinese, "pending": pending, "retained": retained,
            "ready": not pending}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path, nargs="?", default=Path("public_site/data/catalog.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit(json.loads(args.catalog.read_text(encoding="utf-8")))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ready": report["ready"], "coverage": report["coverage"],
                      "pending_fields": len(report["pending"]), "retained_fields": len(report["retained"])}, ensure_ascii=False, indent=2))
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
