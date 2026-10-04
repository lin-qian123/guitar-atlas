"""Compile guarded repertoire familiarity references into small display weights."""
from __future__ import annotations

import json
from pathlib import Path

METHOD = "curated_repertoire_familiarity"


def weight(value: object, context: str) -> int:
    if type(value) is not int or not 0 <= value <= 100:
        raise ValueError(f"{context}: weight must be an integer from 0 to 100")
    return value


def validate_ranking(payload: dict, catalog: dict) -> None:
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("unsupported ranking schema")
    if set(payload) != {"schema_version", "method", "version", "composers", "works"}:
        raise ValueError("unsupported public ranking fields")
    if payload["method"] != METHOD or not isinstance(payload["version"], str):
        raise ValueError("unsupported ranking method/version")
    names = {row["composer_en"] for row in catalog["works"] if row["composer_en"]}
    ids = {row["id"] for row in catalog["works"]}
    for field, known in (("composers", names), ("works", ids)):
        entries = payload[field]
        if not isinstance(entries, dict):
            raise ValueError(f"ranking {field} must be a mapping")
        for key, value in entries.items():
            if key not in known:
                raise ValueError(f"ranking {field}: unknown identity {key}")
            weight(value, f"ranking {field} {key}")


def build_ranking(root: Path, catalog: dict) -> dict:
    path = root / "metadata/ranking/recognition.json"
    result = {"schema_version": 1, "method": METHOD, "version": "", "composers": {}, "works": {}}
    if not path.exists():
        return result
    source = json.loads(path.read_text(encoding="utf-8"))
    if source.get("schema_version") != 1:
        raise ValueError("unsupported recognition source schema")
    result["version"] = source.get("version", "")
    references = source.get("evidence", {})
    if isinstance(references, list):
        references = {entry["id"]: entry for entry in references}
    if not isinstance(references, dict) or not references:
        raise ValueError("recognition source needs evidence references")
    names = {row["composer_en"] for row in catalog["works"] if row["composer_en"]}
    works = {row["id"]: row for row in catalog["works"]}
    for field in ("composers", "works"):
        for key, entry in source.get(field, {}).items():
            if not isinstance(entry, dict) or not entry.get("reason"):
                raise ValueError(f"recognition {key}: missing reason")
            evidence = entry.get("evidence")
            if not isinstance(evidence, list) or not evidence or any(ref not in references for ref in evidence):
                raise ValueError(f"recognition {key}: missing or unknown evidence")
            if field == "composers":
                if key not in names:
                    raise ValueError(f"recognition composer absent from catalog: {key}")
            else:
                row = works.get(key)
                if row is None or entry.get("original_title") != row["title_en"] or entry.get("original_composer") != row["composer_en"]:
                    raise ValueError(f"recognition work guard changed: {key}")
            result[field][key] = weight(entry.get("weight"), f"recognition {key}")
    validate_ranking(result, catalog)
    return result
