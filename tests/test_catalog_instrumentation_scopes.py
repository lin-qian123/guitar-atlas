from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from catalog_sources import load_registry
from export_public_site import build_public_catalog
from tests.test_catalog_instrumentation import read_source, reviewed_library
from tests.test_public_site import write_json
from validate_public_site import validate_payload


def scoped_library(root: Path) -> tuple[dict, dict]:
    from catalog_instrumentation import per_record_guard

    catalog, overlay = reviewed_library(root)
    overlay.pop("catalog_sha256")
    overlay.update(schema_version=2, native_record_sha256={
        work["id"]: per_record_guard(work) for work in catalog["works"]})
    extra = copy.deepcopy(catalog["works"][0])
    extra.update(id="musescore:101", title_en="Additional Guitar Prelude",
                 source_url="https://musescore.com/user/321/scores/101",
                 formats=[], assets=[], instrumentation_status="source_declared")
    extra["metadata"] = {"instrumentation": "Guitar"}
    catalog["works"].append(extra)
    write_json(root / "sources/musescore/catalog.json", catalog)
    write_json(root / "sources/musescore/instrumentation-review.json", overlay)
    return catalog, overlay


def test_native_record_guard_is_complete_order_independent_canonical_json() -> None:
    from catalog_instrumentation import per_record_guard

    work = {"id": "musescore:100", "metadata": {"license": "cc-zero", "label": "吉他"},
            "assets": [{"format": "PDF", "verified_at": "2026-10-15"}]}
    expected = hashlib.sha256(json.dumps(work, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    assert per_record_guard(work) == expected
    assert per_record_guard(dict(reversed(list(work.items())))) == expected
    changed = copy.deepcopy(work)
    changed["assets"][0]["verified_at"] = "2026-10-16"
    assert per_record_guard(changed) != expected
    with pytest.raises(ValueError):
        per_record_guard({"bad": float("nan")})


def test_completed_review_scope_survives_exact_native_append_without_replaying_decisions(tmp_path: Path) -> None:
    from catalog_instrumentation import APPLIED_REVIEW_IDS

    catalog, overlay = scoped_library(tmp_path)
    native_bytes = (tmp_path / "sources/musescore/catalog.json").read_bytes()
    review_bytes = (tmp_path / "sources/musescore/instrumentation-review.json").read_bytes()
    runtime = read_source(tmp_path)
    assert runtime[APPLIED_REVIEW_IDS] == ["musescore:100"]
    assert runtime["works"][0]["metadata"]["instrumentation"] == "2 guitars, violin and cello"
    assert runtime["works"][1] == catalog["works"][1]
    assert (tmp_path / "sources/musescore/catalog.json").read_bytes() == native_bytes
    assert (tmp_path / "sources/musescore/instrumentation-review.json").read_bytes() == review_bytes
    payload = build_public_catalog(tmp_path)
    records = {row["id"]: row for row in payload["works"]}
    assert records["musescore:100"]["topic_evidence"]["strings"] == "file_crosscheck"
    assert records["musescore:101"]["topic_evidence"] == {"guitar_unspecified": "explicit_source_instrumentation"}
    assert APPLIED_REVIEW_IDS not in json.dumps(payload)
    assert overlay["works"][0]["review"]["summary"] in records["musescore:100"]["details"]["instrumentation_review"]
    validate_payload(payload, registry=load_registry(tmp_path))


@pytest.mark.parametrize("mutation", [
    lambda work: work["metadata"].update(source_license="different"),
    lambda work: work["metadata"]["source_parts_names"].append("Flute"),
    lambda work: work["assets"][0].update(verified_at="another receipt"),
    lambda work: work.update(category_ids=["different category"]),
    lambda work: work["formats"].append("GPX"),
    lambda work: work.update(title_en="Changed native title"),
    lambda work: work.update(composer_en="Changed native attribution"),
    lambda work: work.update(source_url="https://musescore.com/user/321/scores/102"),
])
def test_scoped_review_protects_every_original_native_field(tmp_path: Path, mutation) -> None:
    catalog, _ = scoped_library(tmp_path)
    mutation(catalog["works"][0])
    write_json(tmp_path / "sources/musescore/catalog.json", catalog)
    with pytest.raises(ValueError, match="instrumentation review"):
        read_source(tmp_path)


@pytest.mark.parametrize("mutation", [
    lambda value: value.pop("native_record_sha256"),
    lambda value: value.update(native_record_sha256=[]),
    lambda value: value.update(native_record_sha256={}),
    lambda value: value["native_record_sha256"].update({"musescore:101": "a" * 64}),
    lambda value: value["native_record_sha256"].update({"musescore:100": "a" * 64}),
    lambda value: value["native_record_sha256"].update({"musescore:100": True}),
    lambda value: value.update(works=[]),
    lambda value: value["works"].append(copy.deepcopy(value["works"][0])),
    lambda value: value["works"][0].update(id="musescore:999"),
    lambda value: value["works"][0]["assets"].pop("MIDI"),
])
def test_incomplete_or_stale_scoped_review_fails_closed(tmp_path: Path, mutation) -> None:
    _, overlay = scoped_library(tmp_path)
    mutation(overlay)
    write_json(tmp_path / "sources/musescore/instrumentation-review.json", overlay)
    with pytest.raises(ValueError, match="instrumentation review"):
        read_source(tmp_path)


@pytest.mark.parametrize("asset_format", ["PDF", "MUSICXML", "MIDI"])
def test_scoped_review_still_rechecks_all_three_actual_score_formats(tmp_path: Path, asset_format: str) -> None:
    catalog, _ = scoped_library(tmp_path)
    asset = next(row for row in catalog["works"][0]["assets"] if row["format"] == asset_format)
    path = tmp_path / asset["local_path"]
    content = path.read_bytes()
    path.write_bytes(bytes([content[0] ^ 1]) + content[1:])
    with pytest.raises(ValueError, match="actual file bytes changed"):
        read_source(tmp_path)


def test_unreviewed_appended_native_metadata_cannot_forge_file_topics_or_details(tmp_path: Path) -> None:
    from catalog_sources import NEW_DETAIL_FIELDS

    catalog, _ = scoped_library(tmp_path)
    extra = catalog["works"][1]
    extra["metadata"].update({key: "Forged unreviewed conclusion" for key in NEW_DETAIL_FIELDS},
        file_instrumentation_basis="file_crosscheck", file_instrumentation_topic_id="solo")
    write_json(tmp_path / "sources/musescore/catalog.json", catalog)
    records = {row["id"]: row for row in build_public_catalog(tmp_path)["works"]}
    assert records["musescore:101"]["details"] == {"instrumentation": "Guitar"}
    assert records["musescore:101"]["topic_evidence"] == {"guitar_unspecified": "explicit_source_instrumentation"}
    assert records["musescore:100"]["topic_evidence"]["strings"] == "file_crosscheck"


@pytest.mark.parametrize("status", ["file_verified", "file_reviewed_uncertain"])
@pytest.mark.parametrize("has_overlay", [True, False])
def test_unreviewed_musescore_cannot_publish_a_raw_file_review_status(tmp_path: Path, status: str, has_overlay: bool) -> None:
    catalog, _ = scoped_library(tmp_path)
    catalog["works"][1]["instrumentation_status"] = status
    write_json(tmp_path / "sources/musescore/catalog.json", catalog)
    if not has_overlay:
        (tmp_path / "sources/musescore/instrumentation-review.json").unlink()
    with pytest.raises(ValueError, match="uncontrolled MuseScore file review status"):
        build_public_catalog(tmp_path)


@pytest.mark.parametrize("has_overlay", [True, False])
def test_native_catalog_cannot_supply_the_controlled_runtime_review_marker(tmp_path: Path, has_overlay: bool) -> None:
    from catalog_instrumentation import APPLIED_REVIEW_IDS

    catalog, _ = reviewed_library(tmp_path)
    catalog[APPLIED_REVIEW_IDS] = ["musescore:100"]
    write_json(tmp_path / "sources/musescore/catalog.json", catalog)
    if not has_overlay:
        (tmp_path / "sources/musescore/instrumentation-review.json").unlink()
    with pytest.raises(ValueError, match="controlled.*review|review.*controlled"):
        read_source(tmp_path)


def test_legacy_schema_one_still_rejects_a_changed_complete_catalog(tmp_path: Path) -> None:
    catalog, _ = reviewed_library(tmp_path)
    extra = copy.deepcopy(catalog["works"][0])
    extra["id"] = "musescore:101"
    catalog["works"].append(extra)
    write_json(tmp_path / "sources/musescore/catalog.json", catalog)
    with pytest.raises(ValueError, match="native catalog digest"):
        read_source(tmp_path)


@pytest.mark.parametrize("relative", [
    "config/musescore_pdmx_expansion.json", "sources/musescore/expansion/integration.json",
    "metadata/instrumentation/musescore_expansion_reviewed.json"])
def test_offline_fingerprint_tracks_expansion_inputs_with_legacy_absence_compatibility(tmp_path: Path, relative: str) -> None:
    from render_offline_site import offline_input_fingerprint

    reviewed_library(tmp_path)
    before = offline_input_fingerprint(tmp_path.resolve())
    assert relative not in before["inputs"]
    path = tmp_path / relative
    write_json(path, {"status": "prepared"})
    prepared = offline_input_fingerprint(tmp_path.resolve())
    assert prepared != before
    assert prepared["inputs"][relative] == hashlib.sha256(path.read_bytes()).hexdigest()
    write_json(path, {"status": "complete"})
    assert offline_input_fingerprint(tmp_path.resolve()) != prepared
    path.unlink()
    assert offline_input_fingerprint(tmp_path.resolve()) == before
