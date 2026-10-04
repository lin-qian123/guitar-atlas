import fcntl
import hashlib
import json
import os

import pytest

from deduplicate_added_pdfs import run
from deduplicate_source_pdfs import regular_state
from tests.test_added_pdf_deduplication import fixture, metadata_bytes, write_json
from verified_source_relations import verified_identical_pdf_pairs

KNOWN = {"42", "alpha:1", "beta:1"}
PAIRS = [("42", "alpha:1"), ("42", "beta:1")]
REPORT = "sources/objects/deduplication_report.json"


def modify_report(root, change):
    path = root / REPORT
    report = json.loads(path.read_text())
    change(report)
    write_json(root, REPORT, report)


@pytest.mark.parametrize("apply,zip_members", [(False, False), (True, False), (True, True)])
def test_current_verified_report_returns_only_exact_public_ids_without_writing(tmp_path, apply, zip_members):
    fixture(tmp_path, zip_members=zip_members)
    run(tmp_path, apply=apply)
    before = metadata_bytes(tmp_path)
    report_before = (tmp_path / REPORT).read_bytes()
    assert verified_identical_pdf_pairs(tmp_path, KNOWN) == PAIRS
    assert verified_identical_pdf_pairs(tmp_path, {"42", "alpha:1"}) == [("42", "alpha:1")]
    assert verified_identical_pdf_pairs(tmp_path, {"imslp:42", "alpha:1"}) == []
    assert metadata_bytes(tmp_path) == before
    assert (tmp_path / REPORT).read_bytes() == report_before


def test_latest_already_shared_run_is_used_without_falling_back_to_old_states(tmp_path):
    fixture(tmp_path)
    run(tmp_path)
    run(tmp_path, apply=True)
    run(tmp_path)
    assert verified_identical_pdf_pairs(tmp_path, KNOWN) == PAIRS
    modify_report(tmp_path, lambda report: report["runs"].append({"status": "running"}))
    assert verified_identical_pdf_pairs(tmp_path, KNOWN) == []


@pytest.mark.parametrize("relative", ["config/score_exclusions.json", "sources/alpha/catalog.json",
                                     "For guitar/metadata/score_manifest.json"])
def test_any_changed_input_sha256_invalidates_all_journal_edges(tmp_path, relative):
    fixture(tmp_path)
    run(tmp_path)
    path = tmp_path / relative
    path.write_bytes(path.read_bytes() + b"\n")
    assert verified_identical_pdf_pairs(tmp_path, KNOWN) == []


@pytest.mark.parametrize("change", ["input_flag", "source_sha", "membership_id", "anchor_id"])
def test_failed_guards_or_forged_memberships_never_create_edges(tmp_path, change):
    fixture(tmp_path)
    run(tmp_path)

    def corrupt(report):
        latest = report["runs"][-1]
        if change == "input_flag":
            latest["input_content_unchanged"] = False
        elif change == "source_sha":
            latest["actions"][0]["source"]["sha256"] = "0" * 64
        elif change == "membership_id":
            latest["actions"][0]["candidate"]["memberships"][0]["work_id"] = "beta:1"
        else:
            latest["actions"][0]["imslp_membership"]["work_id"] = "43"

    modify_report(tmp_path, corrupt)
    assert verified_identical_pdf_pairs(tmp_path, KNOWN | {"43"}) == []


@pytest.mark.parametrize("which", ["source", "target", "symlink", "report_symlink"])
def test_pdf_drift_symlinks_and_report_symlinks_invalidate_evidence(tmp_path, which):
    source, pool, aliases, _, body = fixture(tmp_path, separate_alias=True)
    run(tmp_path)
    if which in {"source", "target"}:
        path = source if which == "source" else aliases[0]
        path.write_bytes(body.replace(b"120", b"121"))
    else:
        path = pool if which == "symlink" else tmp_path / REPORT
        destination = tmp_path / "retained-original"
        path.rename(destination)
        path.symlink_to(destination)
    assert verified_identical_pdf_pairs(tmp_path, KNOWN) == []


def test_active_writer_lock_yields_no_edges(tmp_path):
    fixture(tmp_path)
    run(tmp_path)
    descriptor = os.open(tmp_path / "sources/objects/.deduplication.lock", os.O_RDONLY)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert verified_identical_pdf_pairs(tmp_path, KNOWN) == []
    finally:
        os.close(descriptor)


def test_missing_journal_or_orphan_memberships_never_invent_endpoints(tmp_path):
    assert verified_identical_pdf_pairs(tmp_path, KNOWN) == []
    fixture(tmp_path)
    for identity in ("alpha", "beta"):
        write_json(tmp_path, f"sources/{identity}/catalog.json",
                   {"schema_version": 1, "source_id": identity, "works": []})
    run(tmp_path)
    assert verified_identical_pdf_pairs(tmp_path, KNOWN) == []


def test_even_forged_hash_matching_html_cannot_become_identical_pdf_evidence(tmp_path):
    source, pool, aliases, _, body = fixture(tmp_path, body=b"<html>not a PDF</html>")
    run(tmp_path)
    sha1, sha = hashlib.sha1(body).hexdigest(), hashlib.sha256(body).hexdigest()

    def forge_success(report):
        latest = report["runs"][-1]
        action = latest["actions"][0]
        action["status"] = "would_link"
        action["imslp_membership"] = action["candidate"]["imslp_candidates"][0]
        action["source"] = {"path": source.relative_to(tmp_path).as_posix(),
                            "sha1": sha1, "sha256": sha, "state": regular_state(source)}
        action["targets"] = [{"path": path.relative_to(tmp_path).as_posix(),
                               "sha1": sha1, "sha256": sha, "state": regular_state(path)}
                              for path in [pool, *aliases]]

    modify_report(tmp_path, forge_success)
    assert verified_identical_pdf_pairs(tmp_path, KNOWN) == []
