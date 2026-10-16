from __future__ import annotations

import copy
import hashlib
import gzip
import json
import shutil
from pathlib import Path

import pytest

from verify_musescore_expansion import (
    AuditFailure, compare_existing_records, compare_offline_records,
    compare_review_scopes, compare_translation_asset, check_old_objects,
    compare_public_structure, check_new_offline_links,
    compare_new_source_fields, capture_offline_baseline, read_baseline, node_offline_adapter,
    check_final_input_guards, FINAL_INPUT_PATHS, FINAL_METHOD_PATHS, SCOPE_METHOD_PATHS, EXACT_CASE_PATH,
    check_expansion_statistics,
    check_public_source_fields,
)


def exact_file_guard(path):
    raw = path.read_bytes()
    return {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}


def final_guard_fixture(tmp_path, *, cases=True):
    for relative in FINAL_METHOD_PATHS | set(FINAL_INPUT_PATHS.values()):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Exact bytes for " + str(relative))
    case_guard = None
    if cases:
        path = tmp_path / EXACT_CASE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"schema_version":1,"entries":[]}')
        case_guard = exact_file_guard(path)
    scope = {"inputs": {"plan": exact_file_guard(tmp_path / FINAL_INPUT_PATHS["plan"]),
        "mxl_extraction": exact_file_guard(tmp_path / FINAL_INPUT_PATHS["MUSICXML"]),
        "methods": {relative: exact_file_guard(tmp_path / relative) for relative in SCOPE_METHOD_PATHS},
        "reviewed_cases": case_guard}}
    (tmp_path / FINAL_INPUT_PATHS["scope_review"]).write_text(json.dumps(scope))
    final = {"inputs": {name: exact_file_guard(tmp_path / relative) for name, relative in FINAL_INPUT_PATHS.items()},
        "methods": {relative: exact_file_guard(tmp_path / relative) for relative in FINAL_METHOD_PATHS},
        "reviewed_cases": copy.deepcopy(case_guard)}
    return final, scope


@pytest.mark.parametrize("cases", [False, True])
def test_final_semantic_inputs_methods_and_exact_case_bytes_are_independently_current(tmp_path, cases):
    final, scope = final_guard_fixture(tmp_path, cases=cases)
    before = copy.deepcopy((final, scope))
    assert check_final_input_guards(tmp_path, final, scope) == {
        "current_input_files": 6, "final_method_files": 9, "scope_method_files": 5,
        "exact_case_bytes_current": True}
    assert (final, scope) == before


@pytest.mark.parametrize("name", list(FINAL_INPUT_PATHS))
def test_any_final_input_byte_change_invalidates_the_completed_review(tmp_path, name):
    final, scope = final_guard_fixture(tmp_path)
    path = tmp_path / FINAL_INPUT_PATHS[name]
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(AuditFailure, match="final review input bytes changed"):
        check_final_input_guards(tmp_path, final, scope)


@pytest.mark.parametrize("relative", sorted(FINAL_METHOD_PATHS))
def test_every_semantic_method_must_still_match_its_recorded_digest(tmp_path, relative):
    final, scope = final_guard_fixture(tmp_path)
    (tmp_path / relative).write_text("Changed method")
    with pytest.raises(AuditFailure, match="review method bytes changed"):
        check_final_input_guards(tmp_path, final, scope)


@pytest.mark.parametrize("report", ["final", "scope"])
@pytest.mark.parametrize("mutation", ["missing", "foreign", "digest", "size"])
def test_missing_foreign_or_inexact_method_guards_cannot_weaken_the_boundary(tmp_path, report, mutation):
    final, scope = final_guard_fixture(tmp_path)
    methods = final["methods"] if report == "final" else scope["inputs"]["methods"]
    key = sorted(methods)[0]
    if mutation == "missing": methods.pop(key)
    elif mutation == "foreign": methods["../foreign.py"] = copy.deepcopy(methods[key])
    elif mutation == "digest": methods[key]["sha256"] = "a" * 64
    else: methods[key]["size"] += 1
    (tmp_path / FINAL_INPUT_PATHS["scope_review"]).write_text(json.dumps(scope))
    final["inputs"]["scope_review"] = exact_file_guard(tmp_path / FINAL_INPUT_PATHS["scope_review"])
    with pytest.raises(AuditFailure, match="review method"):
        check_final_input_guards(tmp_path, final, scope)


@pytest.mark.parametrize("mutation", ["changed", "missing", "new", "symlink", "final_guard", "scope_guard"])
def test_exact_case_asset_presence_bytes_and_both_review_guards_are_mandatory(tmp_path, mutation):
    final, scope = final_guard_fixture(tmp_path, cases=mutation != "new")
    path = tmp_path / EXACT_CASE_PATH
    if mutation == "changed": path.write_bytes(path.read_bytes() + b"\n")
    elif mutation == "missing": path.unlink()
    elif mutation == "new":
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text("New case asset")
    elif mutation == "symlink":
        target = path.with_name("actual.json"); path.rename(target); path.symlink_to(target.name)
    elif mutation == "final_guard": final["reviewed_cases"] = None
    else:
        scope["inputs"]["reviewed_cases"] = None
        (tmp_path / FINAL_INPUT_PATHS["scope_review"]).write_text(json.dumps(scope))
        final["inputs"]["scope_review"] = exact_file_guard(tmp_path / FINAL_INPUT_PATHS["scope_review"])
    with pytest.raises(AuditFailure, match="reviewed-case"):
        check_final_input_guards(tmp_path, final, scope)


@pytest.mark.parametrize("scope_key", ["plan", "mxl_extraction"])
def test_final_scope_file_binding_does_not_excuse_stale_inner_scope_inputs(tmp_path, scope_key):
    final, scope = final_guard_fixture(tmp_path)
    scope["inputs"][scope_key]["sha256"] = "a" * 64
    (tmp_path / FINAL_INPUT_PATHS["scope_review"]).write_text(json.dumps(scope))
    final["inputs"]["scope_review"] = exact_file_guard(tmp_path / FINAL_INPUT_PATHS["scope_review"])
    with pytest.raises(AuditFailure, match="scope review input bytes changed"):
        check_final_input_guards(tmp_path, final, scope)


@pytest.mark.parametrize("mutation", ["missing_input", "foreign_input", "scope_inputs", "missing_case_guard"])
def test_semantic_guard_scopes_cannot_omit_or_substitute_current_inputs(tmp_path, mutation):
    final, scope = final_guard_fixture(tmp_path)
    if mutation == "missing_input": final["inputs"].pop("MIDI")
    elif mutation == "foreign_input": final["inputs"]["elsewhere"] = final["inputs"].pop("MIDI")
    elif mutation == "scope_inputs": scope["inputs"] = None
    else: final.pop("reviewed_cases")
    with pytest.raises(AuditFailure, match="input guard scope"):
        check_final_input_guards(tmp_path, final, scope)


def test_later_method_hashing_cannot_hide_a_change_to_an_already_checked_input(tmp_path, monkeypatch):
    import verify_musescore_expansion as verifier
    final, scope = final_guard_fixture(tmp_path)
    original_hash = verifier.sha256
    changed = False

    def concurrent_hash(path):
        nonlocal changed
        result = original_hash(path)
        if not changed and path.relative_to(tmp_path).as_posix() in FINAL_METHOD_PATHS:
            changed = True
            plan = tmp_path / FINAL_INPUT_PATHS["plan"]
            plan.write_bytes(plan.read_bytes() + b"\n")
        return result

    monkeypatch.setattr(verifier, "sha256", concurrent_hash)
    with pytest.raises(AuditFailure, match="changed during guard verification"):
        check_final_input_guards(tmp_path, final, scope)
    assert changed


def record(identity="musescore:100"):
    return {"id": identity, "title_en": "Native title", "composer_en": "Native composer",
            "source_url": "https://musescore.com/user/1/scores/100",
            "metadata": {"license": "cc-zero"}, "assets": []}


@pytest.mark.parametrize('original,expected,changed', [
    ('The Breeze and I  ', 'The Breeze and I', True),
    ('Native title', 'Native title', False),
    ('Native title.pdf', 'Native title', True),
    ('Native title a href="https://example.com/file.mid">MIDI', 'Native title', True),
])
def test_public_source_title_uses_exact_shared_projection_and_retains_full_original_guard(original, expected, changed):
    native = record(); native['title_en'] = original
    public = {**native, 'title_en': expected}
    assert check_public_source_fields(native, public, {'original': original}) is changed
    assert native['title_en'] == original


@pytest.mark.parametrize('field', ['title_en', 'composer_en', 'source_url'])
def test_shared_title_projection_cannot_excuse_changed_title_words_attribution_or_page(field):
    native = record(); native['title_en'] += ' '
    public = {**native, 'title_en': native['title_en'].strip()}
    public[field] = 'Changed actual source value'
    with pytest.raises(AuditFailure, match='exact production projection'):
        check_public_source_fields(native, public, {'original': native['title_en']})


@pytest.mark.parametrize('entry', [None, {}, {'original': 'Native title'}])
def test_trimmed_or_missing_original_review_guard_cannot_replace_complete_native_source_text(entry):
    native = record(); native['title_en'] += ' '
    public = {**native, 'title_en': native['title_en'].strip()}
    with pytest.raises(AuditFailure, match='complete exact native transcription'):
        check_public_source_fields(native, public, entry)


def statistics_fixture():
    from catalog_instrumentation import per_record_guard
    old = {"works": [record()]}
    old["works"][0]["assets"] = [{"format": "PDF", "status": "verified", "sha256": "b" * 64, "size": 10}]
    added = [record("musescore:101"), record("musescore:102")]
    for index, work in enumerate(added):
        work["assets"] = [
            {"format": "PDF", "status": "verified", "sha256": "b" * 64, "size": 10},
            {"format": "MUSICXML", "status": "verified", "sha256": ("c" if index == 0 else "d") * 64, "size": 20 + 10 * index},
            {"format": "MIDI", "status": "verified", "sha256": "e" * 64, "size": 40}]
    projections = [{"id": work["id"], "review": {"topic_id": "solo" if index == 0 else "duo",
        "status": "file_verified" if index == 0 else "file_reviewed_uncertain"}} for index, work in enumerate(added)]
    overlay = {"works": copy.deepcopy(projections)}
    final_rows = {row["id"]: row for row in projections}
    config = {"scope_version": "fixed", "scope": "Frozen scope"}
    scan = {"metadata_records": 254077, "csv_native_records": 254077, "undeclared_mxl_records": 42,
        "mxl_records": 254035, "mxl_inspected_records": 254035, "mxl_validated_records": 254032,
        "mxl_parse_failures": 3, "mxl_missing_csv_members": 0}
    snapshot = {"scope": config["scope"], "expansion": {
        "scope_version": "fixed", "configuration_sha256": per_record_guard(config),
        "original_record_count": 1, "added_record_count": 2, "current_record_count": 3,
        "full_metadata_records_checked": 254077, "full_mxl_records_checked": 254035,
        "live_source_coverage_complete": False,
        **{key: scan[key] for key in ("mxl_inspected_records", "mxl_validated_records", "mxl_parse_failures",
            "mxl_missing_csv_members", "csv_native_records", "undeclared_mxl_records")}}}
    native = {"works": old["works"] + added, "snapshot": snapshot,
        "summary": {"scope": config["scope"], "records": 3, "source_records": 3,
            "verified_local_pdfs": 3, "verified_local_mxl": 2, "verified_local_midi": 2}}
    journals = {label: {"counts": {"verified": 2, "failed": 1}, "records": {
        "musescore:101": {"status": "verified"}, "musescore:102": {"status": "verified"},
        "musescore:103": {"status": "failed"}}} for label in ("PDF", "MUSICXML", "MIDI")}
    integration = {"new_topics": {"solo": 1, "duo": 1},
        "new_review_statuses": {"file_verified": 1, "file_reviewed_uncertain": 1},
        "new_formats": {label: {"verified_relations": 2, "unique_objects": objects, "unique_bytes": size,
            "extraction_counts": {"verified": 2, "failed": 1}}
            for label, objects, size in [("PDF", 1, 10), ("MUSICXML", 2, 50), ("MIDI", 1, 40)]}}
    return old, native, added, overlay, final_rows, integration, config, scan, journals


def test_independent_statistics_separate_record_associations_format_content_and_private_failures():
    args = statistics_fixture()
    before = copy.deepcopy(args)
    result = check_expansion_statistics(*args)
    assert result["formats"]["PDF"] == {"verified_relations": 2, "unique_objects": 1,
        "unique_bytes": 10, "extraction_counts": {"verified": 2, "failed": 1}}
    assert result["formats"]["MUSICXML"]["unique_objects"] == 2
    assert result["formats"]["MIDI"]["unique_objects"] == 1
    assert result["topics"] == {"solo": 1, "duo": 1}
    assert args == before


@pytest.mark.parametrize("field", ["new_topics", "new_review_statuses"])
def test_integration_review_statistics_are_recounted_instead_of_trusted(field):
    args = statistics_fixture(); args[5][field] = {}
    with pytest.raises(AuditFailure, match="topic/review-status statistics"):
        check_expansion_statistics(*args)


@pytest.mark.parametrize("label", ["PDF", "MUSICXML", "MIDI"])
@pytest.mark.parametrize("field", ["verified_relations", "unique_objects", "unique_bytes", "extraction_counts"])
def test_each_format_statistic_is_independently_recomputed(label, field):
    args = statistics_fixture(); args[5]["new_formats"][label][field] = {} if field == "extraction_counts" else 999
    with pytest.raises(AuditFailure, match="integration format statistics"):
        check_expansion_statistics(*args)


@pytest.mark.parametrize("field", ["counts", "record_status"])
def test_private_extraction_failure_counts_must_match_actual_journal_records(field):
    args = statistics_fixture()
    if field == "counts": args[8]["PDF"]["counts"] = {"verified": 3}
    else: args[8]["PDF"]["records"]["musescore:103"]["status"] = "missing"
    with pytest.raises(AuditFailure, match="extraction status statistics"):
        check_expansion_statistics(*args)


@pytest.mark.parametrize("field", ["scope_version", "configuration_sha256", "original_record_count", "added_record_count",
    "current_record_count", "full_metadata_records_checked", "full_mxl_records_checked", "live_source_coverage_complete",
    "mxl_inspected_records", "mxl_validated_records", "mxl_parse_failures", "mxl_missing_csv_members", "csv_native_records",
    "undeclared_mxl_records", "foreign_field"])
def test_native_expansion_snapshot_must_preserve_the_exact_independently_checked_statistics(field):
    args = statistics_fixture(); args[1]["snapshot"]["expansion"][field] = "Wrong"
    with pytest.raises(AuditFailure, match="native expansion snapshot statistics"):
        check_expansion_statistics(*args)


@pytest.mark.parametrize("field", ["records", "source_records", "verified_local_pdfs", "verified_local_mxl", "verified_local_midi", "scope"])
def test_native_summary_totals_and_scope_are_recounted(field):
    args = statistics_fixture(); args[1]["summary"][field] = 999
    with pytest.raises(AuditFailure, match="native (summary|source summary)"):
        check_expansion_statistics(*args)


def test_appended_overlay_cannot_disagree_with_the_completed_final_decisions():
    args = statistics_fixture(); args[3]["works"][0]["review"]["topic_id"] = "quartet"
    with pytest.raises(AuditFailure, match="review values differ"):
        check_expansion_statistics(*args)


def test_same_format_digest_with_inconsistent_sizes_cannot_be_silently_counted_once():
    args = statistics_fixture(); args[2][1]["assets"][0]["size"] += 1
    with pytest.raises(AuditFailure, match="conflicting sizes"):
        check_expansion_statistics(*args)


def test_append_preserves_every_old_record_and_checks_the_exact_new_scope():
    old = record(); new = record("musescore:101")
    result = compare_existing_records([old], [copy.deepcopy(old), new], "native", {new["id"]})
    assert result == {"preserved": 1, "added": 1}


@pytest.mark.parametrize("mutation", [
    lambda rows: rows.pop(0),
    lambda rows: rows[0]["metadata"].update(license="different"),
    lambda rows: rows[0]["assets"].append({"format": "MIDI"}),
    lambda rows: rows.append(copy.deepcopy(rows[0])),
    lambda rows: rows.append(record("musescore:102")),
])
def test_old_identity_field_asset_and_new_scope_drift_are_rejected(mutation):
    old = record(); new = record("musescore:101")
    rows = [copy.deepcopy(old), new]; mutation(rows)
    with pytest.raises(AuditFailure):
        compare_existing_records([old], rows, "native", {new["id"]})


def test_schema_two_envelope_can_change_without_replaying_prior_review_values():
    from catalog_instrumentation import per_record_guard
    native = record()
    entry = {"id": native["id"], "review": {"summary": "Exact prior decision"}, "assets": {"PDF": "guard"}}
    old = {"schema_version": 1, "works": [entry]}
    new = {"schema_version": 2, "source_id": "musescore", "status": "complete", "works": [copy.deepcopy(entry)],
           "native_record_sha256": {native["id"]: per_record_guard(native)}}
    assert compare_review_scopes(old, new, [native])["preserved_review_entries"] == 1
    new["works"][0]["review"]["summary"] = "Recomputed decision"
    with pytest.raises(AuditFailure, match="prior review"):
        compare_review_scopes(old, new, [native])


def test_schema_two_native_record_guard_cannot_be_rebased_to_a_changed_old_record():
    native = record(); old = {"works": [{"id": native["id"], "review": {}}]}
    new = {"schema_version": 2, "source_id": "musescore", "status": "complete", "works": copy.deepcopy(old["works"]),
           "native_record_sha256": {native["id"]: "a" * 64}}
    with pytest.raises(AuditFailure, match="native record"):
        compare_review_scopes(old, new, [native])


def test_new_titles_are_append_only_and_only_for_accepted_native_identities():
    relative = "metadata/translations/source_titles_zh.json"
    old = {"schema_version": 1, "entries": {"musescore:100": {"original": "Old"}, "imslp:1": {"original": "Other"}}}
    new = copy.deepcopy(old); new["entries"]["musescore:101"] = {"original": "New"}
    assert compare_translation_asset(relative, old, new, {"musescore:101"}, set(), set())["added_entries"] == 1
    new["entries"]["imslp:1"]["original"] = "Changed"
    with pytest.raises(AuditFailure, match="prior translation"):
        compare_translation_asset(relative, old, new, {"musescore:101"}, set(), set())


@pytest.mark.parametrize("relative", ["musicians_zh.json", "categories_zh.json"])
def test_source_scoped_translation_append_cannot_change_or_expand_other_sources(relative):
    old = {"schema_version": 1, "entries": {"musescore": {"Old": {"zh": "旧"}}, "other": {"A": {"zh": "甲"}}}}
    new = copy.deepcopy(old); new["entries"]["musescore"]["New"] = {"zh": "新"}
    name = "metadata/translations/" + relative
    assert compare_translation_asset(name, old, new, set(), {"New"}, {"New"})["added_entries"] == 1
    new["entries"]["other"]["B"] = {"zh": "乙"}
    with pytest.raises(AuditFailure, match="other-source translation"):
        compare_translation_asset(name, old, new, set(), {"New"}, {"New"})


def test_unknown_translation_asset_cannot_change_even_if_its_entries_look_musescore_scoped():
    old = {"entries": {"musescore": {}}}; new = {"entries": {"musescore": {"New": {}}}}
    with pytest.raises(AuditFailure, match="protected translation"):
        compare_translation_asset("metadata/translations/other.json", old, new, set(), {"New"}, set())


def test_every_previous_offline_edition_and_all_shared_fields_must_survive():
    public = {"id": "musescore:100", "title_en": "Old"}
    old = {**public, "local_editions": [{"category_id": 7, "files": [{"format": "MIDI", "href": "object.mid"}]}]}
    new_public = {"id": "musescore:101", "title_en": "New"}
    new = {**new_public, "local_editions": []}
    assert compare_offline_records([old], [copy.deepcopy(old), new], [public, new_public])["old_local_editions_exact"]
    changed = copy.deepcopy(old); changed["local_editions"][0]["files"][0]["href"] = "different.mid"
    with pytest.raises(AuditFailure, match="local editions"):
        compare_offline_records([old], [changed, new], [public, new_public])


@pytest.mark.parametrize("mutation", ["bytes", "inode", "size"])
def test_old_physical_score_bytes_size_and_inode_are_independently_protected(tmp_path: Path, mutation: str):
    path = tmp_path / "sources/musescore/objects/score.mid"
    path.parent.mkdir(parents=True); path.write_bytes(b"immutable score")
    stat = path.stat(); before = {str(path.relative_to(tmp_path)): {"size": stat.st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "device": stat.st_dev, "inode": stat.st_ino}}
    assert check_old_objects(tmp_path, before) == 1
    if mutation == "bytes":
        path.write_bytes(b"Immutable score")
    elif mutation == "size":
        path.write_bytes(b"short")
    else:
        temporary = path.with_suffix(".part"); temporary.write_bytes(path.read_bytes()); temporary.replace(path)
    with pytest.raises(AuditFailure):
        check_old_objects(tmp_path, before)


def public_structure():
    return {"schema_version": 2, "families": [{"id": "musescore"}], "unification_schema_version": 1,
        "translation_schema_version": 1,
        "sources": [{"id": "musescore", "record_count": 1, "snapshot": {"scope": "initial", "frozen_at": "fixed"}},
                    {"id": "other", "record_count": 1}],
        "categories": [{"id": 7, "name": "Guitar", "work_count": 1}],
        "topics": [{"id": "solo", "name_zh": "独奏", "work_count": 1, "source_count": 1}],
        "relationships": [{"from_id": "musescore:100", "to_id": "other:1", "type": "identical_pdf"}]}


def expanded_structure():
    value = public_structure()
    value["sources"][0]["record_count"] += 1
    value["sources"][0]["snapshot"]["scope"] = "expanded"
    value["categories"][0]["work_count"] += 1
    value["topics"][0]["work_count"] += 1
    value["relationships"].append({"from_id": "musescore:101", "to_id": "other:1", "type": "identical_pdf"})
    return value


def test_public_structure_preserves_vocabularies_while_accepting_exact_incremental_counts():
    result = compare_public_structure(public_structure(), expanded_structure(), {"musescore:101"})
    assert result["preserved_relationships"] == 1 and result["added_relationships"] == 1


@pytest.mark.parametrize("mutation", [
    lambda value: value["families"].append({"id": "new"}),
    lambda value: value["categories"][0].update(name="Renamed"),
    lambda value: value["topics"][0].update(name_zh="Changed"),
    lambda value: value["sources"][1].update(record_count=10),
    lambda value: value["sources"][0]["snapshot"].update(frozen_at="new publication"),
    lambda value: value["relationships"].pop(0),
    lambda value: value["relationships"].append({"from_id": "musescore:100", "to_id": "other:2", "type": "identical_pdf"}),
])
def test_public_structure_rejects_unrelated_edits_or_loss_of_old_relations(mutation):
    after = expanded_structure(); mutation(after)
    with pytest.raises(AuditFailure):
        compare_public_structure(public_structure(), after, {"musescore:101"})


def test_new_offline_format_links_match_acquired_objects_and_exact_category_memberships():
    native = {"id": "musescore:101", "assets": [{"local_path": "object." + suffix} for suffix in ("pdf", "mxl", "mid")]}
    row = {"category_ids": [7], "local_editions": [{"category_id": 7, "files": [
        {"href": "object.pdf"}, {"format": "MUSICXML", "href": "object.mxl"}, {"format": "MIDI", "href": "object.mid"}]}]}
    check_new_offline_links(native, row)
    row["local_editions"][0]["files"][1]["format"] = "MIDI"
    with pytest.raises(AuditFailure, match="three format links"):
        check_new_offline_links(native, row)
    row["local_editions"][0]["category_id"] = 8
    with pytest.raises(AuditFailure, match="category memberships"):
        check_new_offline_links(native, row)


def test_offline_capture_checks_the_exact_old_entry_and_reuses_one_baseline(tmp_path: Path):
    wrapper = {"data": {"works": [{"id": "musescore:100"}]}, "aliases": {}, "ranking": {}}
    page = '<script type="application/json" id="offline-data">' + json.dumps(wrapper) + '</script>'
    index = tmp_path / 'index.html'; index.write_text(page)
    baseline_path = tmp_path / 'baseline.json.gz'
    with gzip.open(baseline_path, 'wt') as stream:
        json.dump({'schema_version': 1, 'documents': {}, 'offline_sha256': hashlib.sha256(index.read_bytes()).hexdigest()}, stream)
    assert capture_offline_baseline(tmp_path, baseline_path)['status'] == 'captured'
    assert read_baseline(baseline_path)['offline_snapshot'] == wrapper
    assert capture_offline_baseline(tmp_path, baseline_path)['status'] == 'already_captured'
    before = baseline_path.read_bytes(); index.write_text(page + 'changed')
    with pytest.raises(AuditFailure, match='old offline entry changed'):
        capture_offline_baseline(tmp_path, baseline_path)
    assert baseline_path.read_bytes() == before
    assert not baseline_path.with_name(baseline_path.name + '.part').exists()


def test_verifier_reads_the_single_zip_continuation_baseline_without_a_duplicate_json_archive(tmp_path):
    import zipfile
    path = tmp_path / 'continuation-baseline.zip'
    value = {'schema_version': 1, 'documents': {'native': {'value': record()}},
        'continuation': {'schema_version': 1, 'status': 'captured'}}
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('baseline.json', json.dumps(value))
        archive.writestr('evidence/prior-final.json', '{"completed":true}')
    assert read_baseline(path) == value


def test_verifier_refuses_a_stale_explicit_baseline_after_deep_stage_capture(tmp_path):
    from expand_musescore_library import DEEP_CONTINUATION, CONTINUATION
    from verify_musescore_expansion import verify
    deep = tmp_path / DEEP_CONTINUATION
    deep.parent.mkdir(parents=True); deep.write_bytes(b'active captured stage')
    with pytest.raises(AuditFailure, match='latest published baseline'):
        verify(tmp_path, tmp_path / CONTINUATION, precheck=True)


@pytest.mark.parametrize('field', ['source_license', 'source_parts_names', 'source_uploader', 'source_title', 'pdmx_csv_transcription'])
def test_new_source_fields_are_rechecked_against_native_metadata_not_playback_guesses(field):
    from tests.test_pdmx_expansion_adapter import example
    from source_adapters.pdmx_expansion import validate_candidate
    row, metadata = example()
    work, _, _ = validate_candidate(row, metadata)
    work['metadata']['scope_status'] = 'accepted_actual_file_review'
    candidate = {'csv': row, 'metadata': metadata}
    compare_new_source_fields(work, candidate)
    work['metadata'][field] = 'Changed source evidence'
    with pytest.raises(AuditFailure, match='new source metadata transcription'):
        compare_new_source_fields(work, candidate)


def test_actual_production_offline_adapter_vm_uses_dynamic_scope_and_safe_download_names(tmp_path: Path):
    from tests.basic_helpers import ROOT
    for relative in ['public_site/assets/catalog-codec.js', 'public_site/assets/search.js', 'scripts/assets/offline-catalog.js']:
        target = tmp_path / relative; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(ROOT / relative, target)
    work = {'id': 'musescore:101', 'source_id': 'musescore', 'source_record_id': '101', 'title_en': 'Title / <with> "punctuation"',
            'instrumentation_status': 'file_verified', 'category_ids': [7],
            'local_editions': [{'category_id': 7, 'unavailable_count': 0, 'files': [
                {'href': 'object.pdf', 'label': 'PDF'}, {'format': 'MUSICXML', 'href': 'object.mxl', 'label': 'MXL'},
                {'format': 'MIDI', 'href': 'object.mid', 'label': 'MIDI'}]}]}
    wrapper = {'data': {'works': [work], 'categories': [{'id': 7, 'name': 'Guitar', 'name_zh': '吉他'}]}}
    (tmp_path / 'index.html').write_text('<script type="application/json" id="offline-data">' + json.dumps(wrapper) + '</script>')
    proof = node_offline_adapter(tmp_path, 1)
    assert proof['records'] == 1 and proof['controls'] == 3 and proof['downloads'] == 2 and proof['restricted'] == 1
    with pytest.raises(AuditFailure, match='appended native scope'):
        node_offline_adapter(tmp_path, 2)


def test_new_public_review_accepts_exact_source_instrumentation_projection_repair():
    from catalog_sources import MUSESCORE_SYNTHETIC_SOURCE_INSTRUMENTATION
    from verify_musescore_expansion import check_public_review

    native = {'id': 'musescore:6099968', 'metadata': {
        'instrumentation': MUSESCORE_SYNTHETIC_SOURCE_INSTRUMENTATION,
        'source_instruments': [{'name': 'Guitar', 'count': 1}, {'name': 'Piano', 'count': 1}],
    }}
    review = {'status': 'file_verified', 'topic_id': 'solo',
        'instrumentation': 'Guitar', 'instrumentation_zh': '吉他',
        'guitar_player_count': 1, 'ensemble_player_count': 1,
        'summary': 'Verified score review', 'source_difference': ''}
    entry = {'review': review}
    public = {'instrumentation_status': 'file_verified',
        'details': {'instrumentation': 'Guitar', 'instrumentation_zh': '吉他',
            'guitar_player_count': '1', 'ensemble_player_count': '1',
            'source_instrumentation': 'Guitar；Piano',
            'instrumentation_review': 'Verified score review'},
        'topic_evidence': {'solo': 'file_crosscheck'}}

    assert check_public_review(native, entry, public) is True
