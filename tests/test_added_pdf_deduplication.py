import hashlib
import io
import json
import os
import stat
import sys

import pytest
from pypdf import PdfWriter

import deduplicate_added_pdfs as dedup


def write_json(root, relative, value):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def fixture(root, *, body=None, separate_alias=False, excluded=False, zip_members=False):
    if body is None:
        writer = PdfWriter()
        writer.add_blank_page(width=120, height=140)
        stream = io.BytesIO()
        writer.write(stream)
        body = stream.getvalue()
    sha1, sha = hashlib.sha1(body).hexdigest(), hashlib.sha256(body).hexdigest()
    source = root / "For guitar/scores/score.pdf"
    pool = root / f"sources/objects/sha256/{sha[:2]}/{sha}.pdf"
    aliases = [root / f"sources/{identity}/objects/{sha}.pdf" for identity in ("alpha", "beta")]
    untouched = root / f"sources/classclef/objects/{sha[:2]}/{sha}.pdf"
    for path in (source, pool, untouched):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        path.chmod(0o644)
    for path in aliases:
        path.parent.mkdir(parents=True, exist_ok=True)
        if separate_alias:
            path.write_bytes(body)
        else:
            os.link(pool, path)
    manifest = [{"work_id": "42", "filename": "score.pdf", "file_id": "123",
                 "relative_path": "scores/score.pdf", "download_sha1": sha1,
                 "download_expected_size": len(body)}]
    for identity, path in zip(("alpha", "beta"), aliases):
        member = {"format": "PDF", "status": "verified", "size": len(body), "sha256": sha,
                  "local_path": path.relative_to(root).as_posix()}
        asset = {"format": "PDF", "status": "verified", "container": "ZIP",
                 "members": [{**member, "name": "one.pdf"}, {**member, "name": "two.pdf"}]} if zip_members else member
        write_json(root, f"sources/{identity}/catalog.json", {"schema_version": 1, "source_id": identity,
                   "works": [{"id": f"{identity}:1", "assets": [asset]}]})
    write_json(root, "config/sources.json", {"schema_version": 1, "sources": [
        {"id": "imslp", "adapter": "imslp_categories"},
        {"id": "classclef", "adapter": "normalized_catalog", "catalog": "sources/classclef/catalog.json"},
        *[{"id": identity, "adapter": "normalized_catalog", "catalog": f"sources/{identity}/catalog.json"}
          for identity in ("alpha", "beta")],
    ]})
    write_json(root, "config/categories.json", {"categories": [{"name": "For guitar"}]})
    write_json(root, "config/mixed_categories.json", {"categories": []})
    write_json(root, "config/score_exclusions.json", {"schema_version": 1, "entries": [
        {"category": "For guitar", "work_id": "42", "filename": "score.pdf"}
    ] if excluded else []})
    write_json(root, "For guitar/metadata/score_manifest.json", manifest)
    return source, pool, aliases, untouched, body


def metadata_bytes(root):
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*.json") if path.name != "deduplication_report.json"}


def file_snapshot(paths):
    return [(path.read_bytes(), path.stat().st_ino, stat.S_IMODE(path.stat().st_mode)) for path in paths]


def test_dry_run_uses_fresh_sha1_and_keeps_bytes_modes_paths_and_metadata(tmp_path):
    source, pool, aliases, untouched, body = fixture(tmp_path)
    paths, before_metadata = [source, pool, *aliases, untouched], metadata_bytes(tmp_path)
    before = file_snapshot(paths)
    result = dedup.run(tmp_path)
    assert result["counts"]["candidate_content_groups"] == 1
    assert result["counts"]["would_link_paths"] == 3
    assert result["counts"]["verified_reclaimable_bytes"] == len(body)
    assert result["counts"]["saved_bytes"] == 0
    assert file_snapshot(paths) == before
    assert metadata_bytes(tmp_path) == before_metadata
    assert result["input_content_unchanged"]
    assert all("classclef" not in path for action in result["actions"] for path in action["candidate"]["paths"])
    assert "sources/classclef/catalog.json" not in result["metadata_inputs"]


@pytest.mark.parametrize("zip_members", [False, True])
def test_apply_replaces_pool_and_every_alias_once_and_rerun_keeps_history(tmp_path, zip_members):
    source, pool, aliases, untouched, body = fixture(tmp_path, zip_members=zip_members)
    before_metadata, untouched_before = metadata_bytes(tmp_path), file_snapshot([untouched])
    result = dedup.run(tmp_path, apply=True)
    assert result["counts"]["linked"] == 1
    assert result["counts"]["completed_path_replacements"] == 3
    assert result["counts"]["saved_bytes"] == len(body)
    assert len({p.stat().st_ino for p in [source, pool, *aliases]}) == 1
    assert all(p.read_bytes() == body for p in [source, pool, *aliases])
    assert stat.S_IMODE(source.stat().st_mode) == 0o444
    assert metadata_bytes(tmp_path) == before_metadata
    assert file_snapshot([untouched]) == untouched_before
    again = dedup.run(tmp_path, apply=True)
    assert again["counts"]["already_shared"] == 1
    assert again["counts"]["already_shared_paths"] == 3
    assert again["counts"]["saved_bytes"] == 0
    report = json.loads((tmp_path / "sources/objects/deduplication_report.json").read_text())
    assert len(report["runs"]) == 2
    assert not list(tmp_path.rglob("*.dedup-link"))


def test_distinct_old_inodes_are_counted_once_each(tmp_path):
    source, pool, aliases, _, body = fixture(tmp_path, separate_alias=True)
    assert len({p.stat().st_ino for p in [pool, *aliases]}) == 3
    result = dedup.run(tmp_path, apply=True)
    assert result["counts"]["saved_bytes"] == 3 * len(body)
    assert len({p.stat().st_ino for p in [source, pool, *aliases]}) == 1


def test_unrepresented_hardlink_never_counts_as_reclaimed_bytes(tmp_path):
    source, pool, aliases, _, body = fixture(tmp_path)
    outsider = tmp_path / "retained-extra.pdf"
    os.link(pool, outsider)
    original_inode = outsider.stat().st_ino
    result = dedup.run(tmp_path, apply=True)
    assert result["counts"]["linked"] == 1
    assert result["counts"]["saved_bytes"] == result["counts"]["verified_reclaimable_bytes"] == 0
    assert outsider.stat().st_ino == original_inode != source.stat().st_ino
    assert outsider.read_bytes() == body


@pytest.mark.parametrize("separate_alias", [False, True])
def test_second_replace_failure_is_journaled_and_counts_only_completed_old_inodes(tmp_path, monkeypatch, separate_alias):
    source, pool, aliases, _, body = fixture(tmp_path, separate_alias=separate_alias)
    original_inode = pool.stat().st_ino
    real_replace, replacements = os.replace, []

    def fail_second(src, dst):
        if str(src).endswith(".dedup-link"):
            replacements.append(dst)
            if len(replacements) == 2:
                raise OSError("injected second replacement failure")
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", fail_second)
    result = dedup.run(tmp_path, apply=True)
    assert result["counts"]["partial"] == 1
    assert result["counts"]["completed_path_replacements"] == 1
    assert result["counts"]["saved_bytes"] == (len(body) if separate_alias else 0)
    assert any(p.stat().st_ino == original_inode for p in [pool, *aliases])
    assert all(p.read_bytes() == body for p in [source, pool, *aliases])
    assert not list(tmp_path.rglob("*.dedup-link"))
    monkeypatch.setattr(os, "replace", real_replace)
    again = dedup.run(tmp_path, apply=True)
    assert again["counts"]["linked"] == 1
    assert again["counts"]["completed_path_replacements"] == 2
    assert again["counts"]["saved_bytes"] == (2 * len(body) if separate_alias else len(body))
    assert len({p.stat().st_ino for p in [source, pool, *aliases]}) == 1


@pytest.mark.parametrize("changed", ["imslp", "alias"])
def test_same_size_changed_content_rejects_whole_group_before_mutation(tmp_path, changed):
    source, pool, aliases, untouched, body = fixture(tmp_path, separate_alias=changed == "alias")
    path = source if changed == "imslp" else aliases[0]
    path.write_bytes(body.replace(b"120", b"121"))
    paths = [source, pool, *aliases, untouched]
    before = file_snapshot(paths)
    result = dedup.run(tmp_path, apply=True)
    assert result["counts"]["rejected"] == 1
    assert result["counts"]["completed_path_replacements"] == 0
    assert file_snapshot(paths) == before


@pytest.mark.parametrize("body", [b"<html>not a score</html>", b"%PDF-1.4\nnot parseable\n%%EOF\n"])
def test_matching_hashes_do_not_make_nonparseable_content_a_pdf(tmp_path, body):
    source, pool, aliases, _, _ = fixture(tmp_path, body=body)
    before = file_snapshot([source, pool, *aliases])
    result = dedup.run(tmp_path, apply=True)
    assert result["counts"]["rejected"] == 1
    assert file_snapshot([source, pool, *aliases]) == before


def test_exact_exclusion_can_use_another_approved_version_with_identical_bytes(tmp_path):
    source, pool, aliases, _, body = fixture(tmp_path, excluded=True)
    first = dedup.run(tmp_path, apply=True)
    assert first["counts"]["excluded_imslp_records"] == 1
    assert first["counts"]["candidate_content_groups"] == 0
    alternate = source.with_name("other.pdf")
    alternate.write_bytes(body)
    manifest_path = tmp_path / "For guitar/metadata/score_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest.append({**manifest[0], "work_id": "43", "filename": "other.pdf",
                     "relative_path": "scores/other.pdf"})
    write_json(tmp_path, "For guitar/metadata/score_manifest.json", manifest)
    before_source = file_snapshot([source])
    result = dedup.run(tmp_path, apply=True)
    assert result["counts"]["linked"] == 1
    assert result["actions"][0]["imslp_membership"]["work_id"] == "43"
    assert file_snapshot([source]) == before_source
    assert pool.stat().st_ino == alternate.stat().st_ino


@pytest.mark.parametrize("which", ["source", "pool", "alias", "alias_parent"])
def test_leaf_and_parent_symlinks_are_never_replaced(tmp_path, which):
    source, pool, aliases, untouched, body = fixture(tmp_path)
    path = {"source": source, "pool": pool, "alias": aliases[0],
            "alias_parent": aliases[0].parent}[which]
    destination = tmp_path / "untouched-symlink-destination"
    path.rename(destination)
    path.symlink_to(destination, target_is_directory=destination.is_dir())
    result = dedup.run(tmp_path, apply=True)
    assert result["metadata_errors"]
    assert result["counts"]["candidate_content_groups"] == 0
    assert path.is_symlink()
    assert untouched.read_bytes() == body
    assert stat.S_IMODE(source.stat().st_mode) == 0o644


def test_metadata_change_before_apply_stops_without_changing_pdfs(tmp_path, monkeypatch):
    source, pool, aliases, _, _ = fixture(tmp_path)
    before, original = file_snapshot([source, pool, *aliases]), dedup.verify_group

    def mutate_after_validation(root, candidate, action):
        original(root, candidate, action)
        path = root / "config/score_exclusions.json"
        review = json.loads(path.read_text())
        review["entries"].append({"category": "For guitar", "work_id": "42", "filename": "score.pdf"})
        write_json(root, "config/score_exclusions.json", review)

    monkeypatch.setattr(dedup, "verify_group", mutate_after_validation)
    result = dedup.run(tmp_path, apply=True)
    assert result["status"] == "stopped_metadata_change"
    assert result["counts"]["failed_groups"] == 1
    assert not result["input_content_unchanged"]
    assert file_snapshot([source, pool, *aliases]) == before


def test_alias_without_manifest_membership_is_still_replaced(tmp_path):
    source, pool, aliases, _, _ = fixture(tmp_path)
    write_json(tmp_path, "sources/beta/catalog.json", {"schema_version": 1, "source_id": "beta", "works": []})
    before_metadata = metadata_bytes(tmp_path)
    result = dedup.run(tmp_path, apply=True)
    assert result["counts"]["verified_added_asset_members"] == 1
    assert result["counts"]["completed_path_replacements"] == 3
    assert aliases[1].stat().st_ino == source.stat().st_ino
    assert metadata_bytes(tmp_path) == before_metadata


def test_canonical_pool_and_aliases_without_any_verified_membership_are_in_scope(tmp_path):
    source, pool, aliases, _, body = fixture(tmp_path)
    for identity in ("alpha", "beta"):
        write_json(tmp_path, f"sources/{identity}/catalog.json",
                   {"schema_version": 1, "source_id": identity, "works": []})
    before_metadata = metadata_bytes(tmp_path)
    result = dedup.run(tmp_path, apply=True)
    assert result["counts"]["unreferenced_content_groups"] == 1
    assert result["counts"]["verified_added_asset_members"] == 0
    assert result["counts"]["completed_path_replacements"] == 3
    assert result["counts"]["saved_bytes"] == len(body)
    assert result["actions"][0]["candidate"]["size_basis"] == "canonical_object_stat"
    assert len({p.stat().st_ino for p in [source, pool, *aliases]}) == 1
    assert metadata_bytes(tmp_path) == before_metadata


def test_wrong_pool_prefix_is_reported_and_never_used(tmp_path):
    source, pool, aliases, _, body = fixture(tmp_path)
    wrong_prefix = "ff" if pool.parent.name != "ff" else "00"
    wrong = pool.parent.parent / wrong_prefix / pool.name
    wrong.parent.mkdir()
    pool.rename(wrong)
    before = file_snapshot([source, wrong, *aliases])
    result = dedup.run(tmp_path, apply=True)
    assert result["metadata_errors"]
    assert result["counts"]["candidate_content_groups"] == 0
    assert file_snapshot([source, wrong, *aliases]) == before


def test_new_exact_exclusion_at_final_journal_checkpoint_prevents_replace(tmp_path, monkeypatch):
    source, pool, aliases, _, _ = fixture(tmp_path)
    before, original_write = file_snapshot([source, pool, *aliases]), dedup.write_report
    injected = False

    def change_exclusion_when_ready(path, report):
        nonlocal injected
        original_write(path, report)
        actions = report["runs"][-1]["actions"]
        if actions and actions[-1]["path_actions"] and actions[-1]["path_actions"][-1]["status"] == "ready_to_replace" and not injected:
            injected = True
            write_json(tmp_path, "config/score_exclusions.json", {"schema_version": 1, "entries": [
                {"category": "For guitar", "work_id": "42", "filename": "score.pdf"}
            ]})

    monkeypatch.setattr(dedup, "write_report", change_exclusion_when_ready)
    result = dedup.run(tmp_path, apply=True)
    assert injected
    assert result["status"] == "stopped_metadata_change"
    assert result["counts"]["completed_path_replacements"] == 0
    assert file_snapshot([source, pool, *aliases]) == before
    assert not list(tmp_path.rglob("*.dedup-link"))


def test_final_savings_validation_error_is_reported_and_exits_unsuccessfully(tmp_path, monkeypatch):
    source, _, _, _, body = fixture(tmp_path)
    original = dedup.completed_inode_bytes

    def corrupt_before_final_validation(root, action):
        source.chmod(0o644)
        source.write_bytes(body.replace(b"120", b"121"))
        return original(root, action)

    monkeypatch.setattr(dedup, "completed_inode_bytes", corrupt_before_final_validation)
    result = dedup.run(tmp_path, apply=True)
    assert result["counts"]["completed_path_replacements"] == 3
    assert result["counts"]["savings_verification_errors"] == 1
    assert result["counts"]["failed_groups"] == 1
    assert result["counts"]["saved_bytes"] == 0
    monkeypatch.setattr(dedup, "run", lambda root, apply=False: result)
    monkeypatch.setattr(sys, "argv", ["deduplicate_added_pdfs.py", "--root", str(tmp_path), "--apply"])
    assert dedup.main() == 1
