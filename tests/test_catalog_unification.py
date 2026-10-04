from __future__ import annotations

import json
from pathlib import Path

import pytest

from catalog_sources import load_registry
from catalog_unification import instrumentation_topic, unify_catalog
from export_public_site import PublicExportError, build_public_catalog
from source_adapters.dga import normalize_record
from validate_public_site import validate_payload
from tests.basic_helpers import ROOT
from tests.test_public_site import make_library, write_json


def unified_fixture(root: Path, raw_works: list[dict]) -> dict:
    """Keep private acquisition evidence separate from the public projection."""
    registry, categories, public_works = [], [], []
    for source_id in sorted({row["id"].split(":", 1)[0] for row in raw_works}):
        rows = [row for row in raw_works if row["id"].startswith(source_id + ":")]
        catalog = f"sources/{source_id}/catalog.json"
        write_json(root / catalog, {"works": rows})
        registry.append({"id": source_id, "catalog": catalog})
        category_id = len(categories)
        categories.append({"id": category_id, "source_id": source_id,
                           "name": "Source directory", "family": source_id,
                           "kind": "unspecified"})
        public_works.extend({"id": row["id"], "source_id": source_id,
                             "source_record_id": row["id"].split(":", 1)[1],
                             "title_en": row.get("title_en", "Prelude"),
                             "composer_en": row.get("composer_en", "Example composer"),
                             "category_ids": [category_id], "formats": row.get("formats", []),
                             "resource_type": row.get("resource_type", "score")}
                            for row in rows)
    data = {"categories": categories, "works": public_works, "summary": {}}
    unify_catalog(root, data, registry)
    return data


@pytest.mark.parametrize("value", [None, "", " ", [], {}, "not a URL",
                                  "https://catalog.example/record/42", "https://catalog.example/",
                                  "javascript:download('same.pdf')", "https://[invalid]",
                                  "https://urn.kb.se/resolve?urn=",
                                  "https://urn.kb.se/resolve?noturn=urn:nbn:se:mus:1"])
def test_empty_or_invalid_digital_file_cannot_create_a_relation(tmp_path: Path, value: object) -> None:
    data = unified_fixture(tmp_path, [
        {"id": "dga:1", "metadata": {"digital_file": value}},
        {"id": "dga:2", "metadata": {"digital_file": value}},
    ])
    assert data["relationships"] == []
    assert data["summary"]["relationship_count"] == 0
    assert len(data["works"]) == 2


def test_explicit_shared_file_creates_an_edge_without_merging_records(tmp_path: Path) -> None:
    data = unified_fixture(tmp_path, [
        {"id": "dga:1", "metadata": {"digital_file": "http://archive.example/scores/a.pdf"}},
        {"id": "boije:2", "metadata": {"digital_url": "https://archive.example/scores/a.pdf"}},
    ])
    assert {work["id"] for work in data["works"]} == {"dga:1", "boije:2"}
    assert data["relationships"] == [{"from_id": "boije:2", "to_id": "dga:1",
                                        "type": "shared_source_file",
                                        "basis": "explicit_upstream_file_reference"}]


def test_verified_zip_members_participate_in_content_relations(tmp_path: Path) -> None:
    data = unified_fixture(tmp_path, [
        {"id": "mutopia:1", "assets": [{"status": "verified", "container": "ZIP", "members": [
            {"status": "verified", "sha256": "a" * 64}, {"status": "failed", "sha256": "b" * 64}]}]},
        {"id": "mutopia:2", "assets": [{"status": "verified", "sha256": "a" * 64}]},
        {"id": "mutopia:3", "assets": [{"status": "verified", "sha256": "b" * 64}]},
    ])
    assert data["relationships"] == [{"from_id": "mutopia:1", "to_id": "mutopia:2",
                                      "type": "identical_pdf", "basis": "verified_file_content"}]


@pytest.mark.parametrize("institution,call,has_relation", [
    ("S:Skma", "Boije 465", True),
    ("S:Skma", "Boije 465:2a", True),
    ("Another institution", "Boije 465", False),
    ("", "Boije 465", False),
    ("S:Skma", "465", False),
    ("S:Skma", "Boije 465 / another copy", False),
    ("S:Skma", "Not Boije 465", False),
])
def test_holding_relation_requires_exact_institution_and_native_call_number(
    tmp_path: Path, institution: str, call: str, has_relation: bool,
) -> None:
    raw = normalize_record({"id": 1, "source": institution, "source_call": call,
                            "title": "Prelude", "author": "Example composer"},
                           {"name": "Musik- och teaterbiblioteket"})
    native = "465:2a" if call == "Boije 465:2a" else "465"
    data = unified_fixture(tmp_path, [raw, {"id": "boije:" + native}])
    expected = [{"from_id": "boije:" + native, "to_id": "dga:1", "type": "holding_record",
                 "basis": "explicit_institution_and_call_number"}] if has_relation else []
    assert data["relationships"] == expected


def test_unresolved_holding_target_is_not_published_as_an_edge(tmp_path: Path) -> None:
    raw = normalize_record({"id": 1, "source": "S:Skma", "source_call": "Boije 465"})
    data = unified_fixture(tmp_path, [raw, {"id": "boije:466"}])
    assert data["relationships"] == []


def test_upstream_parent_relation_is_not_mislabeled_as_exact_institution_and_call(tmp_path: Path) -> None:
    data = unified_fixture(tmp_path, [
        {"id": "rism:1", "metadata": {"related_source_ids": ["rism:2"],
         "authority_relations": [{"id": "https://rism.online/sources/2",
                                  "relationshipType": "rism:PrimaryPartOf"}]}},
        {"id": "rism:2"},
    ])
    assert all(edge["type"] != "holding_record" for edge in data["relationships"])
    assert all(edge["basis"] != "explicit_institution_and_call_number" for edge in data["relationships"])


def test_same_title_and_composer_do_not_merge_distinct_source_editions(tmp_path: Path) -> None:
    rows = [
        {"id": "werner:7", "title_en": "Prelude", "composer_en": "Example composer",
         "assets": [{"source_url": "https://example.test/first.pdf", "status": "restricted"}],
         "metadata": {"arranger": "First arranger"}},
        {"id": "delcamp:7", "title_en": "Prelude", "composer_en": "Example composer",
         "assets": [{"source_url": "https://example.test/second.pdf", "status": "restricted"}],
         "metadata": {"arranger": "Second arranger"}},
    ]
    data = unified_fixture(tmp_path, rows)
    assert {work["id"] for work in data["works"]} == {"werner:7", "delcamp:7"}
    assert data["relationships"] == []
    assert all(work["title_en"] == "Prelude" and work["composer_en"] == "Example composer"
               for work in data["works"])


@pytest.mark.parametrize("label,topic", [("Guitar", "guitar_unspecified"),
                                         ("Classical guitar", "guitar_unspecified"),
                                         ("Guitar solo", "solo"), ("Solo guitar", "solo"),
                                         ("1 guitar", "solo"), ("Guitar and voice", None)])
def test_instrumentation_requires_explicit_solo_evidence(label: str, topic: str | None) -> None:
    assert instrumentation_topic(label) == topic


def test_bare_guitar_and_explicit_solo_remain_distinct_topics(tmp_path: Path) -> None:
    data = unified_fixture(tmp_path, [
        {"id": "cglib:1", "metadata": {"instrumentation": "Guitar"}},
        {"id": "cglib:2", "metadata": {"instrumentation": "Guitar solo"}},
    ])
    works = {work["id"]: work for work in data["works"]}
    assert works["cglib:1"]["topic_ids"] == ["guitar_unspecified"]
    assert works["cglib:2"]["topic_ids"] == ["solo"]
    assert works["cglib:1"]["topic_evidence"] == {"guitar_unspecified": "explicit_source_instrumentation"}


def test_topics_keep_their_exact_category_memberships(tmp_path: Path) -> None:
    data = {"categories": [
        {"id": 0, "source_id": "imslp", "name": "For guitar", "family": "pure", "kind": "original"},
        {"id": 1, "source_id": "imslp", "name": "For flute, guitar (arr)", "family": "woodwinds", "kind": "arrangement"},
    ], "works": [{"id": "42", "source_id": "imslp", "title_en": "Prelude",
                  "category_ids": [0, 1], "resource_type": "score"}], "summary": {}}
    unify_catalog(tmp_path, data, [])
    assert data["works"][0]["topic_category_ids"] == {"solo": [0], "woodwinds": [1]}
    assert data["works"][0]["category_ids"] == [0, 1]
    assert data["relationships"] == []


def metadata_only_public_fixture(root: Path, title: str = "Prelude") -> None:
    make_library(root)
    registry = json.loads((ROOT / "config/sources.json").read_text(encoding="utf-8"))
    registry["sources"] = [row for row in registry["sources"] if row["id"] in {"imslp", "classclef"}]
    write_json(root / "config/sources.json", registry)
    write_json(root / "sources/classclef/catalog.json", {
        "schema_version": 1, "source_id": "classclef",
        "snapshot": {"frozen_at": "2026-10-01", "discovery_complete": True},
        "categories": [{"id": "directory", "name": "Score directory", "kind": "unspecified",
                        "source_url": "https://www.classclef.com/francisco-tarrega/"}],
        "works": [{"id": "classclef:42", "title_en": title, "composer_en": "Example composer",
                   "source_url": "https://www.classclef.com/lagrima/", "category_ids": ["directory"],
                   "formats": [], "resource_type": "score", "assets": [], "metadata": {}}],
    })


def test_public_export_preserves_unknown_formats_without_inventing_pdf(tmp_path: Path) -> None:
    metadata_only_public_fixture(tmp_path)
    data = build_public_catalog(tmp_path)
    work = next(row for row in data["works"] if row["id"] == "classclef:42")
    assert work["formats"] == []
    assert work["topic_ids"] == ["unspecified"]
    assert work["resource_type"] == "score"
    assert validate_payload(data, registry=load_registry(tmp_path))["unique_works"] == 2


def test_filename_display_cleanup_preserves_private_title_and_exact_translation_guard(tmp_path: Path) -> None:
    original = "Prelude.pdf"
    metadata_only_public_fixture(tmp_path, title=original)
    asset_path = tmp_path / "metadata/translations/classclef_titles_zh.json"
    translations = {"schema_version": 1, "entries": {"classclef:42": {
        "original": original, "zh": "《前奏曲》", "status": "reference",
        "basis": "checked_title_reference", "reason": "显示用参考译文。",
    }}}
    write_json(asset_path, translations)
    data = build_public_catalog(tmp_path)
    work = next(row for row in data["works"] if row["id"] == "classclef:42")
    assert work["title_en"] == "Prelude"
    assert work["title_zh"] == "《前奏曲》"
    assert work["source_record_id"] == "42"
    assert "source_title_note" in work
    assert json.loads((tmp_path / "sources/classclef/catalog.json").read_text())["works"][0]["title_en"] == original
    assert json.loads(asset_path.read_text())["entries"]["classclef:42"]["original"] == original
    translations["entries"]["classclef:42"]["original"] = "Prelude"
    write_json(asset_path, translations)
    with pytest.raises(PublicExportError, match="translation original drift"):
        build_public_catalog(tmp_path)
