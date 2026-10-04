import json

import pytest

from catalog_ranking import build_ranking, validate_ranking


CATALOG = {"works": [{"id": "42", "composer_en": "Sor, Fernando", "title_en": "L'Encouragement, Op.34"}]}


def source(root):
    payload = {
        "schema_version": 1, "version": "2026-10-01.1", "evidence": {"recital": {"url": "https://example.org/recital"}},
        "composers": {"Sor, Fernando": {"weight": 20, "evidence": ["recital"], "reason": "Documented repertoire"}},
        "works": {"42": {"weight": 60, "original_title": "L'Encouragement, Op.34", "original_composer": "Sor, Fernando", "evidence": ["recital"], "reason": "Documented performance"}},
    }
    path = root / "metadata/ranking/recognition.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(payload))
    return payload, path


def test_compile_contains_only_weights_and_known_identities(tmp_path):
    source(tmp_path)
    result = build_ranking(tmp_path, CATALOG)
    assert result["composers"] == {"Sor, Fernando": 20}
    assert result["works"] == {"42": 60}
    assert "evidence" not in result
    validate_ranking(result, CATALOG)


@pytest.mark.parametrize("field,value", [("original_title", "Different edition"), ("original_composer", "Soriano, Other")])
def test_source_text_changes_fail_without_fuzzy_reassignment(tmp_path, field, value):
    payload, path = source(tmp_path)
    payload["works"]["42"][field] = value
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="guard changed"):
        build_ranking(tmp_path, CATALOG)


@pytest.mark.parametrize("change", ["name", "id", "evidence", "weight", "bool"])
def test_unknown_or_unreviewable_weights_are_rejected(tmp_path, change):
    payload, path = source(tmp_path)
    if change == "name":
        payload["composers"]["Sor"] = payload["composers"].pop("Sor, Fernando")
    elif change == "id":
        payload["works"]["missing"] = payload["works"].pop("42")
    elif change == "evidence":
        payload["works"]["42"]["evidence"] = ["unknown"]
    else:
        payload["works"]["42"]["weight"] = True if change == "bool" else 500
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        build_ranking(tmp_path, CATALOG)


def test_absent_source_has_neutral_weights(tmp_path):
    result = build_ranking(tmp_path, CATALOG)
    assert result["composers"] == result["works"] == {}


def test_failed_ranking_guard_preserves_existing_export_files(tmp_path):
    from export_public_site import export_public_catalog
    from tests.test_public_site import make_library

    make_library(tmp_path)
    payload, path = source(tmp_path)
    payload["composers"] = {}
    path.write_text(json.dumps(payload))
    output = tmp_path / "public_site/data/catalog.json"
    output.parent.mkdir(parents=True)
    existing = [output, output.with_name("catalog.compact.json"), output.with_name("ranking.json")]
    for target in existing:
        target.write_text('{"previous":"snapshot"}\n')
    before = {target: target.read_bytes() for target in existing}
    with pytest.raises(ValueError, match="guard changed"):
        export_public_catalog(tmp_path, output)
    assert {target: target.read_bytes() for target in existing} == before
