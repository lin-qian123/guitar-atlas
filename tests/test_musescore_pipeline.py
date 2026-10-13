"""Exercise the frozen MuseScore import with real small CSV/tar bytes, offline."""
from copy import deepcopy
import csv
import hashlib
import io
import json
from pathlib import Path
import tarfile

import pytest
import requests
from pypdf import PdfWriter

import build_musescore_library as pipeline
from catalog_sources import load_registry
from export_public_site import build_public_catalog
from tests.test_public_site import make_library, write_json
from validate_public_site import validate_payload


ROOT = Path(__file__).resolve().parents[1]
OLD_CATALOG = b'{"previous":"approved frozen catalog"}\n'


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    calls = []
    def forbidden_request(self, url, **kwargs):
        calls.append(url)
        raise AssertionError("pipeline must use freshly checked cached fixture bytes")
    monkeypatch.setattr(requests.sessions.Session, "get", forbidden_request)
    yield calls


def pair(identity, *, instrument="Guitar", tracks="24", conflict="False"):
    title, composer = f"Guitar Study No. {identity}", "F. Sor"
    url = f"https://musescore.com/user/321/scores/{identity}"
    row = {"path": f"./data/1/private-{identity}.json", "metadata": f"./metadata/1/{identity}.json",
           "title": title, "composer_name": composer, "license": "cc-zero",
           "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
           "license_conflict": conflict, "subset:no_license_conflict": "True" if conflict == "False" else "False",
           "tracks": tracks, "n_tracks": str(len(tracks.split("-"))), "n_lyrics": "0", "has_lyrics": "False",
           "has_paywall": "False", "pdf": f"./pdf/1/private-{identity}.pdf",
           "mxl": f"./mxl/1/private-{identity}.mxl", "mid": f"./mid/1/private-{identity}.mid"}
    user = {"id": 321, "name": "Historical uploader", "url": "https://musescore.com/user/321",
            "email": "PRIVATE_EMAIL@example.com", "auth_key": "PRIVATE_AUTH_KEY"}
    score = {"id": identity, "title": title, "composer_name": composer, "url": url,
             "share": {"publicUrl": url}, "user": user, "parts": 1, "parts_names": [instrument],
             "instruments": [{"name": instrument, "count": 1}],
             "instrumentations": [{"name": "Solo", "is_auto": 1}], "license": "cc-zero",
             "is_private": 0, "is_draft": False, "is_official": False, "is_blocked": False}
    metadata = {"status_code": 200, "data": {"score": score, "license_url": row["license_url"],
                "is_download_limited": False, "paywall": {"has_instant_paywall": False},
                "download_url": "https://private.example.org/score.pdf", "secret_token": "PRIVATE_TOKEN"},
                "score": {"id": identity, "title": title, "url": url, "user": deepcopy(user), "isPublic": True}}
    return row, metadata


def fixture_library(root, pairs=None, *, archive_records=None):
    pairs = pairs or [pair(100)]
    cache = root / "sources/musescore/pdmx"
    cache.mkdir(parents=True)
    csv_path = cache / "PDMX.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(pairs[0][0]))
        writer.writeheader()
        writer.writerows(row for row, _ in pairs)
    if archive_records is None:
        archive_records = [(row["metadata"], json.dumps(meta).encode()) for row, meta in pairs]
    with tarfile.open(cache / "metadata.tar.gz", "w:gz") as archive:
        for name, body in archive_records:
            info = tarfile.TarInfo(name)
            info.size = len(body)
            archive.addfile(info, io.BytesIO(body))
    config = json.loads((ROOT / "config/musescore_pdmx.json").read_text())
    for name in config["files"]:
        body = (cache / name).read_bytes()
        config["files"][name] = {"size": len(body), "md5": hashlib.md5(body).hexdigest()}
    write_json(root / "config/musescore_pdmx.json", config)
    return config


def preserve_catalog(root):
    path = root / "sources/musescore/catalog.json"
    path.write_bytes(OLD_CATALOG)
    return path


def test_real_pipeline_closes_statistics_and_preserves_historical_scope(tmp_path, no_network):
    accepted, electric = pair(100), pair(101, instrument="Electric Guitar")
    conflict, nonguitar, bad = pair(102, conflict="True"), pair(103, tracks="0"), pair(104, tracks="24-129")
    mixed = pair(105, tracks="24-73")
    mixed[1]["data"]["score"]["instruments"].append({"name": "Flute", "count": 1})
    mixed[1]["data"]["score"].update(parts=2, parts_names=["Guitar", "Flute"])
    fixture_library(tmp_path, [accepted, electric, conflict, nonguitar, bad, mixed])
    report = pipeline.build(tmp_path)
    catalog = json.loads((tmp_path / "sources/musescore/catalog.json").read_text())
    assert no_network == []
    assert report["selection_counts"]["dataset_rows"] == 6
    assert report["selection_counts"]["candidates"] == 3
    assert report["accepted_records"] == 2
    assert report["excluded_candidates"] == 1
    assert report["accepted_records"] + report["excluded_candidates"] == report["selection_counts"]["candidates"]
    assert sum(report["selection_exclusions"].values()) + report["selection_counts"]["candidates"] == 6
    assert sum(report["exclusion_counts"].values()) == report["excluded_candidates"]
    assert report["score_files_acquired"] == report["live_source_requests"] == 0
    assert report["metadata_complete"] is True
    assert report["pending_metadata_ids"] == []
    assert catalog["snapshot"]["live_source_coverage_complete"] is False
    assert "historical" in catalog["snapshot"]["snapshot_basis"] or "live MuseScore availability unverified" in catalog["snapshot"]["snapshot_basis"]
    assert {row["id"] for row in catalog["works"]} == {"musescore:100", "musescore:105"}
    assert {row["metadata"]["instrumentation"] for row in catalog["works"]} == {"Guitar", "Guitar and flute"}
    assert all(row["metadata"]["guitar_player_count"] is None for row in catalog["works"])
    assert all(asset["status"] == "metadata_only" for row in catalog["works"] for asset in row["assets"])


@pytest.mark.parametrize("format", ["PDF", "MUSICXML", "MIDI"])
def test_metadata_rebuild_refuses_verified_pdf_before_any_write_or_network(tmp_path, no_network, format):
    fixture_library(tmp_path)
    pipeline.build(tmp_path)
    path = tmp_path / "sources/musescore/catalog.json"
    catalog = json.loads(path.read_text())
    writer = PdfWriter()
    writer.add_blank_page(width=120, height=140)
    output = io.BytesIO()
    writer.write(output)
    body = output.getvalue()
    sha = hashlib.sha256(body).hexdigest()
    relative = f"sources/musescore/objects/{sha}.pdf"
    pdf = tmp_path / relative
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(body)
    pdf_asset = next(asset for asset in catalog["works"][0]["assets"] if asset["format"] == format)
    pdf_asset.update(status="verified", local_path=relative, sha256=sha, size=len(body))
    catalog["works"][0]["composer_en"] = "Reviewed responsibility preserved"
    write_json(path, catalog)
    # The guard must run even before an acquisition request or cached receipt update.
    (tmp_path / "sources/musescore/pdmx/PDMX.csv").unlink()
    before = {file.relative_to(tmp_path): file.read_bytes() for file in tmp_path.rglob("*") if file.is_file()}
    with pytest.raises(ValueError, match="acquire_musescore_pdfs\\.py"):
        pipeline.build(tmp_path, acquire_metadata=True)
    assert {file.relative_to(tmp_path): file.read_bytes() for file in tmp_path.rglob("*") if file.is_file()} == before
    assert no_network == []


@pytest.mark.parametrize("journal_state", ["running", "complete", "interrupted", "invalid_json"])
@pytest.mark.parametrize("filename", ["pdf-extraction.json", "mxl-extraction.json", "mid-extraction.json"])
def test_metadata_rebuild_preserves_active_or_unreadable_pdf_journal(tmp_path, no_network, journal_state, filename):
    fixture_library(tmp_path)
    pipeline.build(tmp_path)
    path = tmp_path / "sources/musescore/catalog.json"
    catalog = json.loads(path.read_text())
    catalog["works"][0]["composer_en"] = "Reviewed responsibility preserved"
    write_json(path, catalog)
    journal = tmp_path / "sources/musescore/pdmx" / filename
    if journal_state == "invalid_json":
        journal.write_bytes(b'{"interrupted write":')
    else:
        write_json(journal, {"schema_version": 1, "source_id": "musescore",
                            "status": journal_state, "records": [{"id": "musescore:100", "status": "pending"}]})
    (tmp_path / "sources/musescore/pdmx/PDMX.csv").unlink()
    before = {file.relative_to(tmp_path): file.read_bytes() for file in tmp_path.rglob("*") if file.is_file()}
    with pytest.raises(ValueError, match="acquire_musescore_pdfs\\.py"):
        pipeline.build(tmp_path, acquire_metadata=True)
    assert {file.relative_to(tmp_path): file.read_bytes() for file in tmp_path.rglob("*") if file.is_file()} == before
    assert no_network == []


@pytest.mark.parametrize("name", ["PDMX.csv", "metadata.tar.gz"])
@pytest.mark.parametrize("failure", ["missing", "corrupt"])
def test_missing_or_corrupt_cache_fails_offline_and_preserves_catalog(tmp_path, no_network, name, failure):
    fixture_library(tmp_path)
    catalog = preserve_catalog(tmp_path)
    path = tmp_path / "sources/musescore/pdmx" / name
    if failure == "missing":
        path.unlink()
    else:
        body = bytearray(path.read_bytes())
        body[len(body)//2] ^= 1
        path.write_bytes(body)
    with pytest.raises(ValueError, match="missing metadata|cached metadata integrity"):
        pipeline.build(tmp_path, acquire_metadata=False)
    assert no_network == []
    assert catalog.read_bytes() == OLD_CATALOG


def test_incomplete_metadata_writes_pending_receipt_and_preserves_catalog(tmp_path, no_network):
    first, second = pair(100), pair(101)
    fixture_library(tmp_path, [first, second], archive_records=[(first[0]["metadata"], json.dumps(first[1]).encode())])
    catalog = preserve_catalog(tmp_path)
    with pytest.raises(ValueError, match="incomplete frozen metadata"):
        pipeline.build(tmp_path)
    report = json.loads((tmp_path / "sources/musescore/import-report.json").read_text())
    assert report["metadata_complete"] is False
    assert report["pending_metadata_ids"] == ["101"]
    assert catalog.read_bytes() == OLD_CATALOG
    assert no_network == []


def test_cache_parent_symlink_cannot_create_receipts_outside_library(tmp_path, no_network):
    fixture_library(tmp_path)
    catalog = preserve_catalog(tmp_path)
    cache = tmp_path / "sources/musescore/pdmx"
    outside = tmp_path.parent / (tmp_path.name + "-external-cache")
    cache.rename(outside)
    cache.symlink_to(outside, target_is_directory=True)
    before = {path.name: path.read_bytes() for path in outside.iterdir()}
    with pytest.raises(ValueError, match="root|library|cache|symlink|outside"):
        pipeline.build(tmp_path)
    assert {path.name: path.read_bytes() for path in outside.iterdir()} == before
    assert catalog.read_bytes() == OLD_CATALOG
    assert no_network == []


@pytest.mark.parametrize("failure", ["invalid_json", "conflicting_member", "duplicate_csv", "empty_accepted_scope"])
def test_bad_candidate_metadata_never_replaces_approved_catalog(tmp_path, no_network, failure):
    first = pair(100, instrument="Electric Guitar" if failure == "empty_accepted_scope" else "Guitar")
    pairs, members = [first], None
    if failure == "invalid_json":
        members = [(first[0]["metadata"], b"{")]
    elif failure == "conflicting_member":
        changed = deepcopy(first[1])
        changed["score"]["title"] = "Conflicting source title"
        members = [(first[0]["metadata"], json.dumps(first[1]).encode()),
                   (first[0]["metadata"], json.dumps(changed).encode())]
    elif failure == "duplicate_csv":
        pairs.append(deepcopy(first))
    fixture_library(tmp_path, pairs, archive_records=members)
    catalog = preserve_catalog(tmp_path)
    with pytest.raises(ValueError):
        pipeline.build(tmp_path)
    assert catalog.read_bytes() == OLD_CATALOG
    assert no_network == []


def project_library(root):
    make_library(root)
    registry = json.loads((ROOT / "config/sources.json").read_text())
    registry["sources"] = [row for row in registry["sources"] if row["id"] == "imslp"]
    registry["sources"].append({"id": "musescore", "name": "MuseScore", "homepage": "https://musescore.com/",
        "allowed_hosts": ["musescore.com"], "adapter": "normalized_catalog", "catalog": "sources/musescore/catalog.json",
        "family": "musescore", "family_name_zh": "MuseScore 来源目录", "family_name_en": "MuseScore collections",
        "page_url_rules": [{"path": "/sheetmusic/guitar", "human_page": True},
                           {"path": "/user/[1-9][0-9]*/scores/[1-9][0-9]*", "human_page": True}]})
    write_json(root / "config/sources.json", registry)
    public = build_public_catalog(root)
    validate_payload(public, registry=load_registry(root))
    return public


def test_private_source_snapshot_is_removed_by_actual_unified_public_projection(tmp_path, no_network):
    fixture_library(tmp_path)
    pipeline.build(tmp_path)
    public = project_library(tmp_path)
    serialized = json.dumps(public)
    for private in ("PRIVATE_AUTH_KEY", "PRIVATE_EMAIL", "PRIVATE_TOKEN", "private.example.org",
                    "./pdf/", "./mxl/", "./mid/", "source_uploader", "pdmx_csv_transcription", "auth_key"):
        assert private not in serialized
    native = next(row for row in public["works"] if row["id"] == "musescore:100")
    assert native["source_record_id"] == "100"
    assert native["source_id"] == "musescore"
    assert native["source_url"] == "https://musescore.com/user/321/scores/100"
    assert "guitar_unspecified" in native["topic_ids"]
    assert no_network == []


def test_uploader_contact_or_download_url_remains_private_in_actual_projection(tmp_path, no_network):
    row, meta = pair(100)
    private_url = "https://musescore.com/api/download?token=PRIVATE_UPLOADER_TOKEN"
    meta["data"]["score"]["user"]["name"] = private_url
    meta["score"]["user"]["name"] = private_url
    fixture_library(tmp_path, [(row, meta)])
    pipeline.build(tmp_path)
    public = project_library(tmp_path)
    assert private_url not in json.dumps(public)
    assert "PRIVATE_UPLOADER_TOKEN" not in json.dumps(public)
    assert no_network == []


@pytest.mark.parametrize("field,value", [("name", "Another dataset"), ("version", "v8"),
    ("page", "https://zenodo.org/records/999"), ("doi", "10.5281/zenodo.999")])
def test_config_cannot_disagree_with_frozen_publication_identity(field, value):
    config = json.loads((ROOT / "config/musescore_pdmx.json").read_text())
    config["publication"][field] = value
    with pytest.raises(ValueError, match="publication|configuration"):
        pipeline.validate_config(config)


@pytest.mark.parametrize("field,value", [("scope", ""), ("scope_version", ""), ("scope", None)])
def test_config_requires_an_explicit_frozen_scope(field, value):
    config = json.loads((ROOT / "config/musescore_pdmx.json").read_text())
    config[field] = value
    with pytest.raises(ValueError, match="scope|configuration"):
        pipeline.validate_config(config)


def test_config_checksum_is_hexadecimal_not_merely_thirty_two_characters():
    config = json.loads((ROOT / "config/musescore_pdmx.json").read_text())
    config["files"]["PDMX.csv"]["md5"] = "g" * 32
    with pytest.raises(ValueError, match="checksum|configuration"):
        pipeline.validate_config(config)
