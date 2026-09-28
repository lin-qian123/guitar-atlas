import hashlib
import io
import json
import os
import stat

import pytest
from pypdf import PdfWriter

from deduplicate_source_pdfs import run


def make_fixture(root, *, zip_member=False, excluded=False):
    writer = PdfWriter()
    writer.add_blank_page(width=120, height=140)
    stream = io.BytesIO()
    writer.write(stream)
    body = stream.getvalue()
    sha1, sha256 = hashlib.sha1(body).hexdigest(), hashlib.sha256(body).hexdigest()
    source = root / "For guitar/scores/score.pdf"
    target = root / f"sources/classclef/objects/{sha256[:2]}/{sha256}.pdf"
    for path in (source, target):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        path.chmod(0o644)
    manifest = [{"work_id": "42", "filename": "score.pdf", "file_id": "123",
                 "relative_path": "scores/score.pdf", "expected_size": 1,
                 "sha1_imslp": "0" * 40, "download_expected_size": len(body),
                 "download_sha1": sha1}]
    member = {"local_path": target.relative_to(root).as_posix(), "sha1": sha1,
              "sha256": sha256, "size": len(body), "name": "Guitar.pdf"}
    asset = {"format": "PDF", "status": "verified"}
    asset.update({"container": "ZIP", "members": [member]} if zip_member else member)
    files = {
        "config/categories.json": {"categories": [{"name": "For guitar"}]},
        "config/mixed_categories.json": {"categories": []},
        "config/score_exclusions.json": {"schema_version": 1, "entries": [
            {"category": "For guitar", "work_id": "42", "filename": "score.pdf"}
        ] if excluded else []},
        "For guitar/metadata/score_manifest.json": manifest,
        "sources/classclef/catalog.json": {"schema_version": 1, "source_id": "classclef",
            "works": [{"id": "classclef:42", "assets": [asset]}]},
    }
    for relative, value in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
    return source, target, body


def test_dry_run_validates_without_changing_pdfs_or_modes(tmp_path):
    source, target, body = make_fixture(tmp_path)
    initial = [(p.stat().st_ino, p.stat().st_mode, p.stat().st_mtime_ns) for p in (source, target)]
    result = run(tmp_path)
    assert result["counts"]["would_link"] == 1
    assert result["counts"]["verified_reclaimable_bytes"] == len(body)
    assert initial == [(p.stat().st_ino, p.stat().st_mode, p.stat().st_mtime_ns) for p in (source, target)]
    assert source.read_bytes() == target.read_bytes() == body


@pytest.mark.parametrize("zip_member", [False, True])
def test_apply_hardlinks_both_paths_and_preserves_history_on_rerun(tmp_path, zip_member):
    source, target, body = make_fixture(tmp_path, zip_member=zip_member)
    source_inode, old_target_inode = source.stat().st_ino, target.stat().st_ino
    assert source_inode != old_target_inode
    result = run(tmp_path, apply=True)
    assert result["counts"]["linked"] == 1
    assert source.stat().st_ino == target.stat().st_ino == source_inode
    assert source.read_bytes() == target.read_bytes() == body
    assert stat.S_IMODE(source.stat().st_mode) == 0o444
    action = result["actions"][0]
    assert action["source"]["state"]["mode"] == action["target"]["state"]["mode"] == 0o644
    assert action["target"]["state"]["inode"] == old_target_inode
    again = run(tmp_path, apply=True)
    assert again["counts"]["already_shared"] == 1
    journal = json.loads((tmp_path / "work/cross-source-deduplication.json").read_text())
    assert len(journal["runs"]) == 2
    assert journal["runs"][0]["actions"][0]["target"]["state"]["mode"] == 0o644
    assert not list(target.parent.glob("*.dedup-link"))


@pytest.mark.parametrize("changed", ["source", "target"])
def test_same_size_different_content_is_rejected_without_modification(tmp_path, changed):
    source, target, body = make_fixture(tmp_path)
    path = source if changed == "source" else target
    path.write_bytes(body.replace(b"120", b"121"))
    initial = [(p.read_bytes(), p.stat().st_ino, p.stat().st_mode) for p in (source, target)]
    result = run(tmp_path, apply=True)
    assert result["counts"]["rejected"] == 1
    assert initial == [(p.read_bytes(), p.stat().st_ino, p.stat().st_mode) for p in (source, target)]


def test_non_pdf_matching_metadata_is_rejected(tmp_path):
    source, target, _ = make_fixture(tmp_path)
    body = b"<html>not a score</html>"
    sha1, sha256 = hashlib.sha1(body).hexdigest(), hashlib.sha256(body).hexdigest()
    source.write_bytes(body)
    target.unlink()
    target = tmp_path / f"sources/classclef/objects/{sha256[:2]}/{sha256}.pdf"
    target.parent.mkdir(exist_ok=True)
    target.write_bytes(body)
    manifest_path = tmp_path / "For guitar/metadata/score_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest[0].update(download_sha1=sha1, download_expected_size=len(body))
    manifest_path.write_text(json.dumps(manifest))
    catalog_path = tmp_path / "sources/classclef/catalog.json"
    catalog = json.loads(catalog_path.read_text())
    catalog["works"][0]["assets"][0].update(sha1=sha1, sha256=sha256, size=len(body),
                                            local_path=target.relative_to(tmp_path).as_posix())
    catalog_path.write_text(json.dumps(catalog))
    result = run(tmp_path, apply=True)
    assert result["counts"]["rejected"] == 1
    assert source.stat().st_ino != target.stat().st_ino


def test_reviewed_exclusion_is_not_reused(tmp_path):
    source, target, body = make_fixture(tmp_path, excluded=True)
    result = run(tmp_path, apply=True)
    assert result["counts"]["excluded_imslp_records"] == 1
    assert result["counts"]["candidate_object_paths"] == 0
    assert source.stat().st_ino != target.stat().st_ino
    assert source.read_bytes() == target.read_bytes() == body


@pytest.mark.parametrize("symlink_source", [False, True])
def test_symlinks_are_ineligible(tmp_path, symlink_source):
    source, target, _ = make_fixture(tmp_path)
    path = source if symlink_source else target
    alternate = tmp_path / "untouched.pdf"
    path.rename(alternate)
    path.symlink_to(alternate)
    result = run(tmp_path, apply=True)
    assert result["metadata_errors"]
    assert result["counts"]["candidate_object_paths"] == 0
    assert path.is_symlink()
    assert stat.S_IMODE(alternate.stat().st_mode) == 0o644


def test_replace_failure_restores_source_mode_and_keeps_target(tmp_path, monkeypatch):
    source, target, body = make_fixture(tmp_path)
    real_replace = os.replace
    old_inode = target.stat().st_ino

    def replace(src, dst):
        if dst == target:
            raise OSError("injected replace failure")
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", replace)
    result = run(tmp_path, apply=True)
    assert result["counts"]["rejected"] == 1
    assert target.stat().st_ino == old_inode
    assert source.read_bytes() == target.read_bytes() == body
    assert stat.S_IMODE(source.stat().st_mode) == 0o644
    assert not list(target.parent.glob("*.dedup-link"))
