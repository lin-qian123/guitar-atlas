from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from catalog_sources import load_registry, source_catalog
from export_public_site import build_public_catalog
from render_offline_site import offline_input_fingerprint
from tests.test_public_site import make_musescore_library, write_json
from validate_public_site import validate_payload


def reviewed_library(root: Path) -> tuple[dict, dict]:
    catalog = make_musescore_library(root)
    work = catalog["works"][0]
    work["instrumentation_status"] = "source_declared"
    work["metadata"]["source_parts_names"] = ["Violin", "Guitar 1", "Guitar 2", "Violoncello"]
    work["metadata"]["instrumentation"] = "Guitar and violin"
    work["metadata"]["guitar_player_count"] = None
    work["formats"] = ["PDF", "MUSICXML", "MIDI"]
    guards = {}
    for label, suffix in [("PDF", "pdf"), ("MUSICXML", "mxl"), ("MIDI", "mid")]:
        relative = f"sources/musescore/objects/100.{suffix}"
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        content = ("verified fixture " + label).encode()
        path.write_bytes(content)
        guard = {"sha256": hashlib.sha256(content).hexdigest(), "size": len(content)}
        guards[label] = guard
        work["assets"].append({"format": label, "status": "verified", "local_path": relative, **guard})
    write_json(root / "sources/musescore/catalog.json", catalog)
    overlay = {"schema_version": 1, "source_id": "musescore", "status": "complete",
               "catalog_sha256": hashlib.sha256((root / "sources/musescore/catalog.json").read_bytes()).hexdigest(),
               "works": [{key: work[key] for key in ["id", "title_en", "composer_en", "source_url"]}]}
    overlay["works"][0].update(assets=guards, review={
        "status": "file_verified", "instrumentation": "2 guitars, violin and cello",
        "instrumentation_zh": "两把吉他、小提琴、大提琴", "topic_id": "strings",
        "guitar_player_count": 2, "ensemble_player_count": 4,
        "summary": "MXL、MIDI与PDF交叉核验：两把吉他、小提琴和大提琴。",
        "source_difference": "来源摘要遗漏大提琴。"})
    write_json(root / "sources/musescore/instrumentation-review.json", overlay)
    return catalog, overlay


def read_source(root: Path) -> dict:
    return source_catalog(root, next(row for row in load_registry(root) if row["id"] == "musescore"))


def test_guitar_ensemble_can_be_confirmed_without_inventing_desk_sizes(tmp_path: Path) -> None:
    _, overlay = reviewed_library(tmp_path)
    review = overlay['works'][0]['review']
    review.update(status='file_reviewed_uncertain',topic_id='guitar_ensemble',
                  guitar_player_count=None,ensemble_player_count=None,
                  ensemble_size_unspecified=True,written_guitar_part_count=13)
    write_json(tmp_path/'sources/musescore/instrumentation-review.json',overlay)
    metadata = read_source(tmp_path)['works'][0]['metadata']
    assert metadata['file_instrumentation_topic_id']=='guitar_ensemble'
    assert metadata['written_guitar_part_count'] == 13
    assert metadata['ensemble_size_note'] == '分部人数未标'
    payload = build_public_catalog(tmp_path)
    public = next(row for row in payload['works'] if row['source_id'] == 'musescore')
    assert public['details']['written_guitar_part_count'] == '13'
    assert public['details']['ensemble_size_note'] == '分部人数未标'
    assert 'guitar_player_count' not in public['details']
    assert 'ensemble_player_count' not in public['details']
    validate_payload(payload, registry=load_registry(tmp_path))
    review['topic_id']='duo'
    write_json(tmp_path/'sources/musescore/instrumentation-review.json',overlay)
    with pytest.raises(ValueError,match='precise player topic'):
        read_source(tmp_path)


@pytest.mark.parametrize('mutation', [
    lambda details: details.update(written_guitar_part_count='4'),
    lambda details: details.update(written_guitar_part_count='thirteen'),
    lambda details: details.update(written_guitar_part_count='13.0'),
    lambda details: details.pop('written_guitar_part_count'),
    lambda details: details.update(ensemble_size_note='13人'),
    lambda details: details.pop('ensemble_size_note'),
    lambda details: details.update(guitar_player_count='13'),
    lambda details: details.update(ensemble_player_count='13'),
])
def test_public_validator_rejects_unguarded_uncertain_guitar_ensemble(tmp_path: Path, mutation) -> None:
    from validate_public_site import PublicSiteValidationError
    _, overlay = reviewed_library(tmp_path)
    overlay['works'][0]['review'].update(status='file_reviewed_uncertain',topic_id='guitar_ensemble',
        guitar_player_count=None,ensemble_player_count=None,ensemble_size_unspecified=True,written_guitar_part_count=13)
    write_json(tmp_path/'sources/musescore/instrumentation-review.json',overlay)
    payload = build_public_catalog(tmp_path)
    work = next(row for row in payload['works'] if row['source_id'] == 'musescore')
    mutation(work['details'])
    with pytest.raises(PublicSiteValidationError, match='uncertain file review'):
        validate_payload(payload,registry=load_registry(tmp_path))


def test_verified_file_review_corrects_omission_without_rewriting_source(tmp_path: Path) -> None:
    original, _ = reviewed_library(tmp_path)
    original_bytes = (tmp_path / "sources/musescore/catalog.json").read_bytes()
    result = read_source(tmp_path)
    effective = result["works"][0]
    assert effective["metadata"]["instrumentation"] == "2 guitars, violin and cello"
    assert effective["metadata"]["source_instrumentation"] == "Guitar and violin"
    assert effective["metadata"]["source_parts_names"] == original["works"][0]["metadata"]["source_parts_names"]
    assert effective["metadata"]["guitar_player_count"] == 2
    assert effective["instrumentation_status"] == "file_verified"
    assert (tmp_path / "sources/musescore/catalog.json").read_bytes() == original_bytes
    assert original["works"][0]["metadata"]["guitar_player_count"] is None


def test_public_projection_uses_typed_file_topic_and_searchable_chinese_details(tmp_path: Path) -> None:
    original, _ = reviewed_library(tmp_path)
    payload = build_public_catalog(tmp_path)
    result = next(row for row in payload["works"] if row["source_id"] == "musescore")
    assert result["topic_ids"] == ["strings", "studies"]
    assert result["topic_evidence"]["strings"] == "file_crosscheck"
    assert result["details"]["instrumentation_zh"] == "两把吉他、小提琴、大提琴"
    assert result["details"]["source_instrumentation"] == "Guitar and violin"
    assert result["details"]["guitar_player_count"] == "2"
    assert result["details"]["ensemble_player_count"] == "4"
    assert result["source_url"] == original["works"][0]["source_url"]
    assert result["topic_category_ids"]["strings"] == result["category_ids"]
    assert set(result["details"]).isdisjoint({"assets", "sha256", "local_path", "catalog_sha256"})
    validate_payload(payload, registry=load_registry(tmp_path))


def test_explicit_file_title_difference_keeps_the_native_identity_and_searchable_details(tmp_path: Path) -> None:
    original, overlay = reviewed_library(tmp_path)
    overlay["works"][0]["review"].update(file_title="TWO ITALIAN MELODIES FOR AN ORCHESTRA / LA PALOMA",
        file_identity_note="文件谱题为《鸽子》，与来源所列吉他二重奏练习曲题名不一致。")
    write_json(tmp_path / "sources/musescore/instrumentation-review.json", overlay)
    payload = build_public_catalog(tmp_path)
    work = next(row for row in payload["works"] if row["source_id"] == "musescore")
    assert work["title_en"] == original["works"][0]["title_en"]
    assert work["source_record_id"] == "100"
    assert work["source_url"] == original["works"][0]["source_url"]
    assert work["details"]["file_title"] == "TWO ITALIAN MELODIES FOR AN ORCHESTRA / LA PALOMA"
    assert "来源所列" in work["details"]["file_identity_note"]
    validate_payload(payload, registry=load_registry(tmp_path))


@pytest.mark.parametrize("field", ["file_title", "file_identity_note", "file_part_labels"])
@pytest.mark.parametrize("value", ["https://private.example/score.pdf", "sources/private/score.mxl", "/Volumes/private/score.mid", "a" * 64, [], 3])
def test_file_identity_descriptions_cannot_expose_private_or_invalid_fields(tmp_path: Path, field: str, value: object) -> None:
    _, overlay = reviewed_library(tmp_path)
    overlay["works"][0]["review"][field] = value
    write_json(tmp_path / "sources/musescore/instrumentation-review.json", overlay)
    with pytest.raises(ValueError, match="instrumentation review"):
        read_source(tmp_path)


def test_absent_file_identity_note_does_not_invent_a_title_conflict(tmp_path: Path) -> None:
    reviewed_library(tmp_path)
    work = read_source(tmp_path)["works"][0]
    assert "file_title" not in work["metadata"]
    assert "file_identity_note" not in work["metadata"]


def test_actual_part_labels_preserve_complete_notation_labels_without_replacing_native_metadata(tmp_path: Path) -> None:
    original, overlay = reviewed_library(tmp_path)
    labels = 'B♭ Clarinet; Alto Recorder; 12-string Guitar; Guitar [Tablature]'
    overlay['works'][0]['review']['file_part_labels'] = labels
    write_json(tmp_path/'sources/musescore/instrumentation-review.json',overlay)
    runtime = read_source(tmp_path)['works'][0]
    assert runtime['metadata']['file_part_labels'] == labels
    assert runtime['metadata']['source_parts_names'] == original['works'][0]['metadata']['source_parts_names']
    payload = build_public_catalog(tmp_path)
    public = next(row for row in payload['works'] if row['source_id'] == 'musescore')
    assert public['details']['file_part_labels'] == labels
    assert public['title_en'] == original['works'][0]['title_en']
    validate_payload(payload,registry=load_registry(tmp_path))


@pytest.mark.parametrize("kind", ["source", "status", "missing_summary"])
def test_public_validator_rejects_unsubstantiated_file_crosscheck(tmp_path: Path, kind: str) -> None:
    from validate_public_site import PublicSiteValidationError
    reviewed_library(tmp_path)
    payload = build_public_catalog(tmp_path)
    if kind == "source":
        work = next(row for row in payload["works"] if row["source_id"] == "imslp")
        work["topic_evidence"][work["topic_ids"][0]] = "file_crosscheck"
    else:
        work = next(row for row in payload["works"] if row["source_id"] == "musescore")
        if kind == "status":
            work["instrumentation_status"] = "source_declared"
        else:
            work["details"].pop("instrumentation_review")
    with pytest.raises(PublicSiteValidationError, match="file-crosschecked"):
        validate_payload(payload, registry=load_registry(tmp_path))


@pytest.mark.parametrize("mutation", [
    lambda value: value.update(schema_version=2),
    lambda value: value.update(source_id="another"),
    lambda value: value.update(status="running"),
    lambda value: value.update(catalog_sha256="a" * 64),
    lambda value: value.update(works=[]),
    lambda value: value["works"].append(copy.deepcopy(value["works"][0])),
    lambda value: value["works"][0].update(id="musescore:101"),
    lambda value: value["works"][0].update(title_en="Changed title"),
    lambda value: value["works"][0].update(composer_en="Changed composer"),
    lambda value: value["works"][0].update(source_url="https://musescore.com/user/321/scores/101"),
    lambda value: value["works"][0]["assets"]["MIDI"].update(sha256="b" * 64),
    lambda value: value["works"][0]["assets"]["PDF"].update(size=1),
    lambda value: value["works"][0]["assets"].pop("MUSICXML"),
    lambda value: value["works"][0]["review"].update(topic_id="invented"),
    lambda value: value["works"][0]["review"].update(status="machine"),
    lambda value: value["works"][0]["review"].update(guitar_player_count=True),
    lambda value: value["works"][0]["review"].update(ensemble_player_count=1),
    lambda value: value["works"][0]["review"].update(summary="/Volumes/private/score.mxl"),
    lambda value: value["works"][0]["review"].update(instrumentation="a" * 64),
    lambda value: value["works"][0]["review"].update(source_difference="sources/private/score.pdf"),
])
def test_present_review_fails_closed_on_stale_or_unsafe_evidence(tmp_path: Path, mutation) -> None:
    _, overlay = reviewed_library(tmp_path)
    mutation(overlay)
    write_json(tmp_path / "sources/musescore/instrumentation-review.json", overlay)
    with pytest.raises(ValueError, match="instrumentation review"):
        read_source(tmp_path)


@pytest.mark.parametrize("kind", ["changed_bytes", "missing", "unsafe_relative", "absolute", "outside_symlink", "unverified", "duplicate"])
def test_review_rechecks_actual_file_and_safe_local_manifest(tmp_path: Path, kind: str) -> None:
    catalog, overlay = reviewed_library(tmp_path)
    asset = catalog["works"][0]["assets"][0]
    path = tmp_path / asset["local_path"]
    if kind == "changed_bytes":
        content = path.read_bytes()
        path.write_bytes(bytes([content[0] ^ 1]) + content[1:])
    elif kind == "missing":
        path.unlink()
    elif kind == "unsafe_relative":
        asset["local_path"] = "../private.pdf"
    elif kind == "absolute":
        asset["local_path"] = str(path)
    elif kind == "outside_symlink":
        outside = tmp_path.parent / (tmp_path.name + "-outside.pdf")
        outside.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(outside)
    elif kind == "unverified":
        asset["status"] = "pending"
    else:
        catalog["works"][0]["assets"].append(copy.deepcopy(asset))
    write_json(tmp_path / "sources/musescore/catalog.json", catalog)
    overlay["catalog_sha256"] = hashlib.sha256((tmp_path / "sources/musescore/catalog.json").read_bytes()).hexdigest()
    write_json(tmp_path / "sources/musescore/instrumentation-review.json", overlay)
    with pytest.raises(ValueError, match="instrumentation review"):
        read_source(tmp_path)


def test_missing_review_preserves_legacy_metadata_and_other_sources(tmp_path: Path) -> None:
    catalog, _ = reviewed_library(tmp_path)
    (tmp_path / "sources/musescore/instrumentation-review.json").unlink()
    assert read_source(tmp_path) == catalog
    source = {"id": "example", "catalog": "sources/example/catalog.json"}
    another = {"schema_version": 1, "source_id": "example", "categories": [], "works": []}
    write_json(tmp_path / source["catalog"], another)
    write_json(tmp_path / "sources/musescore/instrumentation-review.json", {"status": "corrupt"})
    assert source_catalog(tmp_path, source) == another


def test_native_metadata_cannot_forge_a_file_crosschecked_topic(tmp_path: Path) -> None:
    catalog = make_musescore_library(tmp_path)
    work = catalog["works"][0]
    work["instrumentation_status"] = "file_verified"
    work["metadata"].update(file_instrumentation_topic_id="solo", file_instrumentation_basis="file_crosscheck")
    write_json(tmp_path / "sources/musescore/catalog.json", catalog)
    projected = next(row for row in build_public_catalog(tmp_path)["works"] if row["source_id"] == "musescore")
    assert projected["topic_evidence"]["guitar_unspecified"] == "explicit_source_instrumentation"
    assert "solo" not in projected["topic_ids"]


def test_other_sources_cannot_publish_same_named_internal_instrumentation_review_fields(tmp_path: Path) -> None:
    from catalog_sources import NEW_DETAIL_FIELDS
    from tests.test_catalog_sources import add_source
    reviewed_library(tmp_path)
    existing = json.loads((tmp_path/'config/sources.json').read_bytes())
    other = add_source(tmp_path)
    added = json.loads((tmp_path/'config/sources.json').read_bytes())['sources'][-1]
    existing['sources'].append(added)
    write_json(tmp_path/'config/sources.json',existing)
    other['works'][0]['metadata'] = {'instrumentation':'Guitar',
        **{key:'Internal source methodology, not a file review' for key in NEW_DETAIL_FIELDS}}
    write_json(tmp_path/'sources/classclef/catalog.json',other)
    public = build_public_catalog(tmp_path)
    record = next(row for row in public['works'] if row['source_id']=='classclef')
    assert record['details'] == {'instrumentation':'Guitar'}
    reviewed = next(row for row in public['works'] if row['source_id']=='musescore')
    assert reviewed['details']['instrumentation_review']


def test_musescore_without_guarded_overlay_cannot_publish_forged_review_details(tmp_path: Path) -> None:
    from catalog_sources import NEW_DETAIL_FIELDS
    catalog = make_musescore_library(tmp_path)
    record = catalog['works'][0]
    record['instrumentation_status'] = 'file_verified'
    record['metadata'].update({key:'Forged unchecked file review' for key in NEW_DETAIL_FIELDS},
        file_instrumentation_basis='file_crosscheck', file_instrumentation_topic_id='solo')
    write_json(tmp_path/'sources/musescore/catalog.json',catalog)
    projected = next(row for row in build_public_catalog(tmp_path)['works'] if row['source_id']=='musescore')
    assert projected['details'] == {'instrumentation':'Guitar'}
    assert projected['topic_evidence']['guitar_unspecified']=='explicit_source_instrumentation'


def test_uncertain_review_cannot_assert_a_precise_guitar_player_topic(tmp_path: Path) -> None:
    _, overlay = reviewed_library(tmp_path)
    review = overlay["works"][0]["review"]
    review.update(status="file_reviewed_uncertain", topic_id="duo")
    write_json(tmp_path / "sources/musescore/instrumentation-review.json", overlay)
    with pytest.raises(ValueError, match="instrumentation review"):
        read_source(tmp_path)
    review.update(topic_id="guitar_unspecified", guitar_player_count=None, ensemble_player_count=None)
    write_json(tmp_path / "sources/musescore/instrumentation-review.json", overlay)
    result = build_public_catalog(tmp_path)
    work = next(row for row in result["works"] if row["source_id"] == "musescore")
    assert work["topic_ids"] == ["guitar_unspecified", "studies"]
    assert "guitar_player_count" not in work["details"]


def test_actual_non_guitar_ensemble_keeps_native_scope_and_uses_other_instrumentation(tmp_path: Path) -> None:
    _, overlay = reviewed_library(tmp_path)
    review = overlay["works"][0]["review"]
    review.update(topic_id="other_instrumentation", instrumentation="Violin and cello",
                  instrumentation_zh="小提琴、大提琴", guitar_player_count=0, ensemble_player_count=2,
                  summary="文件核验为小提琴与大提琴；实际谱面未含吉他。")
    write_json(tmp_path / "sources/musescore/instrumentation-review.json", overlay)
    result = build_public_catalog(tmp_path)
    work = next(row for row in result["works"] if row["source_id"] == "musescore")
    assert work["topic_ids"] == ["other_instrumentation", "studies"]
    assert work["details"]["guitar_player_count"] == "0"
    category = result["categories"][work["category_ids"][0]]
    assert category["name"] == "Guitar"
    assert work["source_record_id"] == "100"
    assert work["formats"] == ["MIDI", "MUSICXML", "PDF"]


def test_offline_fingerprint_tracks_added_removed_and_modified_review(tmp_path: Path) -> None:
    reviewed_library(tmp_path)
    key = "sources/musescore/instrumentation-review.json"
    before = offline_input_fingerprint(tmp_path.resolve())
    path = tmp_path / key
    path.unlink()
    missing = offline_input_fingerprint(tmp_path.resolve())
    assert missing["inputs"][key] is None
    assert before != missing


def test_broken_review_symlink_is_a_present_invalid_review(tmp_path: Path) -> None:
    reviewed_library(tmp_path)
    path = tmp_path / "sources/musescore/instrumentation-review.json"
    path.unlink()
    path.symlink_to(tmp_path / "missing-review.json")
    with pytest.raises(ValueError, match="instrumentation review"):
        read_source(tmp_path)


def test_app_exposes_review_detail_labels_and_search_indexes_them() -> None:
    from tests.basic_helpers import ROOT
    script = (ROOT / "public_site/assets/app.js").read_text()
    for field in ("instrumentation_zh", "source_instrumentation", "instrumentation_review", "guitar_player_count", "ensemble_player_count"):
        assert field + ":" in script
    search = (ROOT / "public_site/assets/search.js").read_text()
    assert "Object.values(details)" in search
