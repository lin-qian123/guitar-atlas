"""Real tar/PDF acquisition checks for the frozen PDMX guitar subset."""
import copy
import csv
import hashlib
import io
import json
import tarfile
from pathlib import Path

import pytest
from pypdf import PdfWriter

from source_adapters import pdmx_assets


PUBLICATION = {"name": "PDMX", "version": "v9", "record_id": "15571083",
               "page": "https://zenodo.org/records/15571083", "doi": "10.5281/zenodo.15571083",
               "dataset_license": "CC-BY-4.0"}
URL = "https://zenodo.org/api/records/15571083/files/pdf.tar.gz/content"


def pdf_bytes(text="native score"):
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=400)
    writer.add_metadata({"/Title": text})
    stream = io.BytesIO()
    writer.write(stream)
    return stream.getvalue()


def work(identity, member=None):
    member = member or f"./pdf/1/2/native{identity}.pdf"
    return {"id": f"musescore:{identity}", "title_en": "Native title", "title_zh": "中文参考题名",
            "composer_en": "Native Composer", "source_url": f"https://musescore.com/user/3/scores/{identity}", "category_ids": ["guitar"], "formats": ["PDF", "MIDI"],
            "assets": [{"format": "PDF", "status": "metadata_only"}, {"format": "MIDI", "status": "metadata_only"}],
            "metadata": {"attribution_role": "composer", "license": "CC0", "source_license": "cc-zero",
                         "license_url": "https://creativecommons.org/publicdomain/zero/1.0/", "pdmx_csv_transcription": {
                "path": f"./data/1/2/native{identity}.json", "pdf": member, "metadata": f"./metadata/0/{identity}.json", "license": "cc-zero",
                "license_url": "https://creativecommons.org/publicdomain/zero/1.0/", "license_conflict": "False",
                "subset:no_license_conflict": "True", "subset:all_valid": "True"}}}


def setup_root(tmp_path, members, works=None, **limit_overrides):
    base = tmp_path / "sources/musescore/pdmx"
    base.mkdir(parents=True)
    archive = base / "pdf.tar.gz"
    with tarfile.open(archive, "w:gz") as target:
        for name, body, kind in members:
            info = tarfile.TarInfo(name)
            info.type = kind
            info.size = len(body) if kind == tarfile.REGTYPE else 0
            if kind in {tarfile.SYMTYPE, tarfile.LNKTYPE}:
                info.linkname = "../../outside"
            target.addfile(info, io.BytesIO(body) if kind == tarfile.REGTYPE else None)
    raw = archive.read_bytes()
    config = {"schema_version": 1, "source_id": "musescore", "scope_version": "test",
              "publication": PUBLICATION, "scope": "approved frozen guitar subset",
              "files": {"pdf.tar.gz": {"size": len(raw), "md5": hashlib.md5(raw).hexdigest()}},
              "limits": {"max_members": 100, "max_member_bytes": 1024*1024,
                         "max_total_bytes": 20*1024*1024, "max_selected_bytes": 10*1024*1024,
                         "max_expansion_ratio": 100, **limit_overrides}}
    (tmp_path / "config").mkdir()
    source_registry = Path(__file__).resolve().parents[1] / "config/sources.json"
    (tmp_path / "config/sources.json").write_bytes(source_registry.read_bytes())
    (tmp_path / "config/musescore_pdmx_assets.json").write_text(json.dumps(config))
    catalog = {"schema_version": 1, "source_id": "musescore", "snapshot": {"frozen_at": "unchanged", "publication": PUBLICATION},
               "categories": [{"id": "guitar", "name": "Guitar"}], "works": works or [work("1")],
               "summary": {"source_records": len(works or [1]), "verified_local_pdfs": 0}}
    csv_path = base / "PDMX.csv"
    csv_rows = [row["metadata"]["pdmx_csv_transcription"] for row in catalog["works"]]
    with csv_path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=sorted(set().union(*(set(row) for row in csv_rows))))
        writer.writeheader()
        writer.writerows(csv_rows)
    csv_raw = csv_path.read_bytes()
    metadata_config = {"schema_version": 1, "source_id": "musescore", "scope_version": "test",
                       "publication": PUBLICATION, "scope": "frozen metadata fixture",
                       "files": {"PDMX.csv": {"size": len(csv_raw), "md5": hashlib.md5(csv_raw).hexdigest()},
                                 "metadata.tar.gz": {"size": 1, "md5": "0"*32}}}
    metadata_config_path = tmp_path / "config/musescore_pdmx.json"
    metadata_config_path.write_text(json.dumps(metadata_config))
    catalog["snapshot"]["configuration_sha256"] = hashlib.sha256(metadata_config_path.read_bytes()).hexdigest()
    catalog["snapshot"]["metadata_checksums"] = {"PDMX.csv": hashlib.sha256(csv_raw).hexdigest()}
    (tmp_path / "sources/musescore/catalog.json").write_text(json.dumps(catalog, ensure_ascii=False))
    return archive, catalog


def read_catalog(root):
    return json.loads((root / "sources/musescore/catalog.json").read_text())


def test_streamed_selected_pdfs_share_objects_keep_metadata_and_report_missing_failure(tmp_path):
    body = pdf_bytes()
    original = [work("1"), work("2"), work("3"), work("4")]
    original[1]["metadata"]["pdmx_csv_transcription"]["pdf"] = "./pdf/1/2/native1.pdf"
    archive, catalog = setup_root(tmp_path, [("./pdf/", b"", tarfile.DIRTYPE),
        ("./pdf/1/2/native1.pdf", body, tarfile.REGTYPE),
        ("./pdf/1/2/native4.pdf", b"<html>not a score</html>", tarfile.REGTYPE),
        ("./pdf/9/9/unselected.pdf", b"unselected is not parsed", tarfile.REGTYPE)], original)
    report = pdmx_assets.acquire(tmp_path, cached_archive=True, batch_size=1)
    current = read_catalog(tmp_path)
    assert report["status"] == "complete"
    assert report["counts"] == {"source_records": 4, "verified_records": 2, "failed_records": 1,
                                "missing_records": 1, "pending_records": 0, "unique_pdf_objects": 1}
    assert current["snapshot"] == catalog["snapshot"]
    assert current["categories"] == catalog["categories"]
    for before, after in zip(original, current["works"]):
        assert {key: value for key, value in after.items() if key != "assets"} == {key: value for key, value in before.items() if key != "assets"}
        assert after["assets"][1] == before["assets"][1]
    assets = [row["assets"][0] for row in current["works"]]
    assert [row["status"] for row in assets] == ["verified", "verified", "missing", "failed"]
    assert assets[0]["archive_member"] == "pdf/1/2/native1.pdf"
    assert assets[0]["upstream_checksum_status"] == "not_supplied"
    assert assets[0]["archive_checksum_status"] == "md5_verified"
    assert assets[0]["publication"] == PUBLICATION
    local = tmp_path / assets[0]["local_path"]
    pool = tmp_path / "sources/objects/sha256" / assets[0]["sha256"][:2] / (assets[0]["sha256"] + ".pdf")
    assert local.read_bytes() == body
    assert local.stat().st_ino == pool.stat().st_ino
    assert not list((tmp_path / "sources/musescore/partials").glob("*.part"))
    assert len(report["records"]) == 4
    assert report["live_source_requests"] == 0


@pytest.mark.parametrize("name,kind", [("../unselected.pdf", tarfile.REGTYPE),
    ("/unselected.pdf", tarfile.REGTYPE), ("pdf\\unselected.pdf", tarfile.REGTYPE),
    ("pdf/link", tarfile.SYMTYPE), ("pdf/link", tarfile.LNKTYPE), ("pdf/fifo", tarfile.FIFOTYPE)])
def test_unsafe_late_unselected_member_never_commits_partial_catalog(tmp_path, name, kind):
    _, catalog = setup_root(tmp_path, [("pdf/1/2/native1.pdf", pdf_bytes(), tarfile.REGTYPE), (name, b"unsafe", kind)])
    with pytest.raises(ValueError, match="unsafe|regular"):
        pdmx_assets.acquire(tmp_path, cached_archive=True, batch_size=1)
    assert read_catalog(tmp_path) == catalog
    report = json.loads((tmp_path / "sources/musescore/acquisition_report.json").read_text())
    assert report["status"] == "failed_archive"
    assert report["catalog_committed"] is False
    assert not (tmp_path / "outside").exists()


@pytest.mark.parametrize("second", ["pdf/1/2/native1.pdf", "./pdf/1/2/native1.pdf"])
def test_duplicate_archive_paths_are_rejected_even_when_equal(tmp_path, second):
    body = pdf_bytes()
    _, catalog = setup_root(tmp_path, [("pdf/1/2/native1.pdf", body, tarfile.REGTYPE), (second, body, tarfile.REGTYPE)])
    with pytest.raises(ValueError, match="duplicate"):
        pdmx_assets.acquire(tmp_path, cached_archive=True)
    assert read_catalog(tmp_path) == catalog


def test_cached_archive_md5_is_rechecked_and_network_never_used(tmp_path):
    archive, catalog = setup_root(tmp_path, [("pdf/1/2/native1.pdf", pdf_bytes(), tarfile.REGTYPE)])
    archive.write_bytes(archive.read_bytes()[:-1] + b"X")
    with pytest.raises(ValueError, match="checksum|integrity"):
        pdmx_assets.acquire(tmp_path, cached_archive=True)
    assert read_catalog(tmp_path) == catalog


def test_unselected_member_and_actual_decompression_limits_are_enforced(tmp_path):
    _, catalog = setup_root(tmp_path, [("pdf/1/2/native1.pdf", pdf_bytes(), tarfile.REGTYPE),
        ("unselected", b"x"*2048, tarfile.REGTYPE)], max_member_bytes=1024)
    with pytest.raises(ValueError, match="size"):
        pdmx_assets.acquire(tmp_path, cached_archive=True)
    assert read_catalog(tmp_path) == catalog


def test_fresh_repeat_validates_existing_immutable_object_and_reuses_inode(tmp_path):
    body = pdf_bytes()
    setup_root(tmp_path, [("pdf/1/2/native1.pdf", body, tarfile.REGTYPE)])
    first = pdmx_assets.acquire(tmp_path, cached_archive=True)
    asset = read_catalog(tmp_path)["works"][0]["assets"][0]
    path = tmp_path / asset["local_path"]
    inode = path.stat().st_ino
    second = pdmx_assets.acquire(tmp_path, cached_archive=True)
    assert second["counts"] == first["counts"]
    assert second["fresh_verified_prior_records"] == 1
    assert path.stat().st_ino == inode
    assert second["records"][0]["status"] == "verified"


def test_corrupted_immutable_object_is_failed_never_overwritten(tmp_path):
    setup_root(tmp_path, [("pdf/1/2/native1.pdf", pdf_bytes(), tarfile.REGTYPE)])
    pdmx_assets.acquire(tmp_path, cached_archive=True)
    asset = read_catalog(tmp_path)["works"][0]["assets"][0]
    path = tmp_path / asset["local_path"]
    path.write_bytes(b"broken immutable object")
    report = pdmx_assets.acquire(tmp_path, cached_archive=True)
    assert report["counts"]["failed_records"] == 1
    assert read_catalog(tmp_path)["works"][0]["assets"][0]["status"] == "failed"
    assert path.read_bytes() == b"broken immutable object"


@pytest.mark.parametrize("value", ["../outside.pdf", "./pdf/1/2/mismatch.mid", "https://musescore.com/score.pdf", "./pdf/../native1.pdf"])
def test_only_exact_safe_frozen_pdf_locators_are_admitted(tmp_path, value):
    _, catalog = setup_root(tmp_path, [("pdf/1/2/native1.pdf", pdf_bytes(), tarfile.REGTYPE)], [work("1", value)])
    with pytest.raises(ValueError, match="locator"):
        pdmx_assets.acquire(tmp_path, cached_archive=True)
    assert read_catalog(tmp_path) == catalog


def test_conflicting_or_invalid_frozen_license_flags_are_not_acquisition_permission(tmp_path):
    row = work("1")
    row["metadata"]["pdmx_csv_transcription"]["license_conflict"] = "True"
    _, catalog = setup_root(tmp_path, [("pdf/1/2/native1.pdf", pdf_bytes(), tarfile.REGTYPE)], [row])
    with pytest.raises(ValueError, match="license|scope"):
        pdmx_assets.acquire(tmp_path, cached_archive=True)
    assert read_catalog(tmp_path) == catalog


def test_existing_lock_prevents_parallel_catalog_mutation(tmp_path):
    setup_root(tmp_path, [("pdf/1/2/native1.pdf", pdf_bytes(), tarfile.REGTYPE)])
    with pdmx_assets.source_lock(tmp_path / "sources/musescore/.pdf-acquisition.lock"):
        with pytest.raises(RuntimeError, match="running|lock"):
            pdmx_assets.acquire(tmp_path, cached_archive=True)


def test_exact_guarded_history_copy_changes_preserve_all_other_metadata(tmp_path):
    row = work("1")
    row["metadata"].update(availability="来源页面现状未核；尚无本地谱文件。",
                           license_note="按 PDMX 逐条历史许可和无冲突标记整理；本次仅纳入元数据。")
    setup_root(tmp_path, [("pdf/1/2/native1.pdf", pdf_bytes(), tarfile.REGTYPE)], [row])
    translations = tmp_path / "metadata/translations"
    translations.mkdir(parents=True)
    (translations / "guard.json").write_text('{"original":"Native title","zh":"中文参考题名"}')
    original = (translations / "guard.json").read_bytes()
    report = pdmx_assets.acquire(tmp_path, cached_archive=True)
    current = read_catalog(tmp_path)["works"][0]
    assert current["metadata"]["availability"] == "PDMX 历史出版记录；来源页面现状未核。"
    assert current["metadata"]["license_note"] == "按 PDMX 逐条历史许可和无冲突标记整理；具体条件参见出版页与原站标注。"
    assert report["protected_non_asset_catalog_sha256"] == report["protected_non_asset_catalog_after_sha256"]
    assert report["translation_bytes_unchanged"] is True
    assert (translations / "guard.json").read_bytes() == original
    assert report["translation_input_sha256"]["metadata/translations/guard.json"] == hashlib.sha256(original).hexdigest()
    assert len(report["allowed_metadata_differences"]) == 2
    assert current["assets"][0]["label"] == "PDMX 出版 PDF"


def test_staged_members_resume_only_after_fresh_object_and_archive_checks(tmp_path, monkeypatch):
    setup_root(tmp_path, [("pdf/1/2/native1.pdf", pdf_bytes(), tarfile.REGTYPE),
                         ("pdf/1/2/native2.pdf", pdf_bytes("second"), tarfile.REGTYPE)], [work("1"), work("2")])
    original = pdmx_assets._stream_members
    def interrupt(tar):
        for count, member in enumerate(original(tar)):
            if count == 1:
                raise KeyboardInterrupt("controlled real archive interruption")
            yield member
    monkeypatch.setattr(pdmx_assets, "_stream_members", interrupt)
    with pytest.raises(KeyboardInterrupt):
        pdmx_assets.acquire(tmp_path, cached_archive=True, batch_size=1)
    assert read_catalog(tmp_path)["works"][0]["assets"][0]["status"] == "metadata_only"
    journal = json.loads((tmp_path / "sources/musescore/pdmx/pdf-extraction.json").read_text())
    assert journal["staged_members"]["pdf/1/2/native1.pdf"]["status"] == "verified"
    monkeypatch.setattr(pdmx_assets, "_stream_members", original)
    report = pdmx_assets.acquire(tmp_path, cached_archive=True)
    assert report["fresh_verified_staged_members"] == 1
    assert report["counts"]["verified_records"] == 2
    assert report["archive_counts"]["reused_verified_members"] == 1


def test_symlinked_object_storage_is_never_followed(tmp_path):
    setup_root(tmp_path, [("pdf/1/2/native1.pdf", pdf_bytes(), tarfile.REGTYPE)])
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "sources/musescore/objects").symlink_to(outside, target_is_directory=True)
    report = pdmx_assets.acquire(tmp_path, cached_archive=True)
    assert report["counts"]["failed_records"] == 1
    assert list(outside.iterdir()) == []


def test_gzip_crc_error_cannot_upgrade_an_otherwise_parseable_selected_pdf(tmp_path):
    archive, catalog = setup_root(tmp_path, [("pdf/1/2/native1.pdf", pdf_bytes(), tarfile.REGTYPE)])
    raw = archive.read_bytes()
    broken = raw[:-8] + bytes([raw[-8] ^ 1]) + raw[-7:]
    archive.write_bytes(broken)
    config_path = tmp_path / "config/musescore_pdmx_assets.json"
    config = json.loads(config_path.read_text())
    config["files"]["pdf.tar.gz"]["md5"] = hashlib.md5(broken).hexdigest()
    config_path.write_text(json.dumps(config))
    with pytest.raises((ValueError, OSError), match="CRC|gzip|archive"):
        pdmx_assets.acquire(tmp_path, cached_archive=True)
    assert read_catalog(tmp_path) == catalog


class Response:
    def __init__(self, body, *, url, status=200, headers=None):
        self.body, self.url, self.status_code = body, url, status
        self.headers = headers or {"Content-Length": str(len(body))}
        self.closed = False

    @property
    def text(self):
        return self.body.decode()

    def iter_content(self, chunk_size):
        yield self.body

    def close(self):
        self.closed = True


class Transport:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


def client(transport):
    clock = [100.0]
    pauses = []
    def pause(seconds):
        pauses.append(seconds)
        clock[0] += seconds
    result = pdmx_assets.PDMXArchiveClient(session=transport, clock=lambda: clock[0], sleep=pause)
    result.test_pauses = pauses
    return result


def test_online_route_checks_wildcard_robots_same_clock_and_only_fixed_archive_endpoint(tmp_path):
    archive, _ = setup_root(tmp_path, [("pdf/1/2/native1.pdf", pdf_bytes(), tarfile.REGTYPE)])
    raw = archive.read_bytes()
    archive.unlink()
    robots = b"User-agent: *\nDisallow: /api\nAllow: /api/records/*/files\nCrawl-delay: 12\n"
    transport = Transport([Response(robots, url="https://zenodo.org/robots.txt"), Response(raw, url=URL)])
    connection = client(transport)
    report = pdmx_assets.acquire(tmp_path, cached_archive=False, client=connection)
    assert report["counts"]["verified_records"] == 1
    assert [url for url, _ in transport.calls] == ["https://zenodo.org/robots.txt", URL]
    assert connection.test_pauses == [12.0]
    assert not any("musescore.com" in url for url, _ in transport.calls)


@pytest.mark.parametrize("status", [401, 403, 429])
def test_robots_access_stop_leaves_every_record_pending_and_never_downloads(tmp_path, status):
    archive, catalog = setup_root(tmp_path, [("pdf/1/2/native1.pdf", pdf_bytes(), tarfile.REGTYPE)])
    archive.unlink()
    transport = Transport([Response(b"access restricted", url="https://zenodo.org/robots.txt", status=status)])
    connection = client(transport)
    with pytest.raises(pdmx_assets.AccessStopped):
        pdmx_assets.acquire(tmp_path, cached_archive=False, client=connection)
    assert len(transport.calls) == 1
    assert read_catalog(tmp_path) == catalog
    assert connection.stopped
    report = json.loads((tmp_path / "sources/musescore/acquisition_report.json").read_text())
    assert report["status"] == "stopped_access"
    assert report["counts"]["pending_records"] == 1


def test_html_human_challenge_stops_client_and_retains_pending_catalog(tmp_path):
    archive, catalog = setup_root(tmp_path, [("pdf/1/2/native1.pdf", pdf_bytes(), tarfile.REGTYPE)])
    archive.unlink()
    html = b"<!doctype html><html>Verify you are human cf-chl-</html>"
    transport = Transport([Response(b"User-agent: *\nAllow: /\n", url="https://zenodo.org/robots.txt"),
                           Response(html, url=URL, headers={})])
    connection = client(transport)
    with pytest.raises(pdmx_assets.AccessStopped, match="human"):
        pdmx_assets.acquire(tmp_path, cached_archive=False, client=connection)
    assert len(transport.calls) == 2
    assert read_catalog(tmp_path) == catalog
    assert connection.stopped


def test_disallowed_wildcard_robots_route_is_not_an_acquisition_permission(tmp_path):
    archive, catalog = setup_root(tmp_path, [("pdf/1/2/native1.pdf", pdf_bytes(), tarfile.REGTYPE)])
    archive.unlink()
    transport = Transport([Response(b"User-agent: *\nDisallow: /api/records/*/files\n", url="https://zenodo.org/robots.txt")])
    with pytest.raises(pdmx_assets.AccessStopped, match="disallows"):
        pdmx_assets.acquire(tmp_path, cached_archive=False, client=client(transport))
    assert len(transport.calls) == 1
    assert read_catalog(tmp_path) == catalog


@pytest.mark.parametrize("identity", ["2330946", "2770766", "5766408"])
def test_exact_historically_restricted_record_copy_keeps_restriction_evidence(tmp_path, identity):
    row = work(identity)
    row["metadata"].update(availability="来源页面现状未核；尚无本地谱文件。源站历史文件访问受限。",
                           historical_file_access_restrictions=["Source historical access restricted"])
    setup_root(tmp_path, [(f"pdf/1/2/native{identity}.pdf", pdf_bytes(), tarfile.REGTYPE)], [row])
    report = pdmx_assets.acquire(tmp_path, cached_archive=True)
    current = read_catalog(tmp_path)["works"][0]
    assert current["metadata"]["availability"] == "PDMX 历史出版记录；来源页面现状未核。源站历史文件访问受限。"
    assert current["metadata"]["historical_file_access_restrictions"] == row["metadata"]["historical_file_access_restrictions"]
    assert report["counts"]["verified_records"] == 1
    assert report["protected_non_asset_catalog_sha256"] == report["protected_non_asset_catalog_after_sha256"]


@pytest.mark.parametrize("tail_bytes", [0, 512])
def test_even_checksum_frozen_tar_without_two_zero_end_blocks_is_rejected(tmp_path, tail_bytes):
    archive, catalog = setup_root(tmp_path, [("pdf/1/2/native1.pdf", pdf_bytes(), tarfile.REGTYPE)])
    import gzip
    raw = gzip.decompress(archive.read_bytes())
    member_size = len(pdf_bytes())
    member_end = 512 + ((member_size + 511) // 512)*512
    truncated = gzip.compress(raw[:member_end + tail_bytes])
    archive.write_bytes(truncated)
    config_path = tmp_path / "config/musescore_pdmx_assets.json"
    config = json.loads(config_path.read_text())
    config["files"]["pdf.tar.gz"] = {"size": len(truncated), "md5": hashlib.md5(truncated).hexdigest()}
    config_path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="truncated.*marker"):
        pdmx_assets.acquire(tmp_path, cached_archive=True)
    assert read_catalog(tmp_path) == catalog


@pytest.mark.parametrize("limit", [{"max_selected_bytes": 1}, {"max_members": 1}, {"max_expansion_ratio": 1}, {"max_total_bytes": 1024}])
def test_resource_limits_never_commit_a_partial_subset(tmp_path, limit):
    _, catalog = setup_root(tmp_path, [("pdf/1/2/native1.pdf", pdf_bytes(), tarfile.REGTYPE),
                                     ("unselected.pdf", b"unselected", tarfile.REGTYPE)], **limit)
    with pytest.raises(ValueError, match="limit|size|member"):
        pdmx_assets.acquire(tmp_path, cached_archive=True)
    assert read_catalog(tmp_path) == catalog


def test_concurrent_frozen_catalog_change_is_preserved_instead_of_overwritten(tmp_path, monkeypatch):
    setup_root(tmp_path, [("pdf/1/2/native1.pdf", pdf_bytes(), tarfile.REGTYPE)])
    path = tmp_path / "sources/musescore/catalog.json"
    original = pdmx_assets._store_pdf
    def concurrently_edit(*args):
        result = original(*args)
        content = json.loads(path.read_text())
        content["works"][0]["title_zh"] = "同时修改的中文标题"
        path.write_text(json.dumps(content, ensure_ascii=False))
        return result
    monkeypatch.setattr(pdmx_assets, "_store_pdf", concurrently_edit)
    with pytest.raises(ValueError, match="concurrently"):
        pdmx_assets.acquire(tmp_path, cached_archive=True)
    assert read_catalog(tmp_path)["works"][0]["title_zh"] == "同时修改的中文标题"
    assert read_catalog(tmp_path)["works"][0]["assets"][0]["status"] == "metadata_only"


def test_archive_redirect_is_rejected_before_any_other_endpoint_request(tmp_path):
    archive, catalog = setup_root(tmp_path, [("pdf/1/2/native1.pdf", pdf_bytes(), tarfile.REGTYPE)])
    archive.unlink()
    transport = Transport([Response(b"User-agent: *\nAllow: /\n", url="https://zenodo.org/robots.txt"),
                           Response(b"", url=URL, status=302, headers={"Location": "https://zenodo.org/api/records/15571083/files/other/content"})])
    with pytest.raises(ValueError, match="redirect"):
        pdmx_assets.acquire(tmp_path, cached_archive=False, client=client(transport))
    assert [url for url, _ in transport.calls] == ["https://zenodo.org/robots.txt", URL]
    assert read_catalog(tmp_path) == catalog


def test_archive_replacement_between_digest_and_stream_does_not_publish_false_provenance(tmp_path, monkeypatch):
    archive, catalog = setup_root(tmp_path, [("pdf/1/2/native1.pdf", pdf_bytes("original"), tarfile.REGTYPE)])
    other = io.BytesIO()
    with tarfile.open(fileobj=other, mode="w:gz") as target:
        replacement = pdf_bytes("changed after validation")
        info = tarfile.TarInfo("pdf/1/2/native1.pdf")
        info.size = len(replacement)
        target.addfile(info, io.BytesIO(replacement))
    original = pdmx_assets._digests
    def replace_after_hash(path):
        result = original(path)
        if path.name == "pdf.tar.gz":
            path.write_bytes(other.getvalue())
        return result
    monkeypatch.setattr(pdmx_assets, "_digests", replace_after_hash)
    with pytest.raises(ValueError, match="archive.*changed"):
        pdmx_assets.acquire(tmp_path, cached_archive=True)
    assert read_catalog(tmp_path) == catalog


def test_pending_journal_exists_before_archive_acquisition_and_survives_access_stop(tmp_path):
    archive, _ = setup_root(tmp_path, [("pdf/1/2/native1.pdf", pdf_bytes(), tarfile.REGTYPE)])
    archive.unlink()
    journal = tmp_path / "sources/musescore/pdmx/pdf-extraction.json"
    class CheckedTransport(Transport):
        def get(self, url, **kwargs):
            assert journal.is_file()
            pending = json.loads(journal.read_text())
            assert pending["archive_checked_this_run"] is False
            assert pending["catalog_committed"] is False
            assert pending["records"][0]["status"] == "pending"
            return super().get(url, **kwargs)
    transport = CheckedTransport([Response(b"no access", url="https://zenodo.org/robots.txt", status=403)])
    with pytest.raises(pdmx_assets.AccessStopped):
        pdmx_assets.acquire(tmp_path, cached_archive=False, client=client(transport))
    assert journal.is_file()


@pytest.mark.parametrize("change", ["native_page_id", "metadata_native_id", "source_license", "csv_license_url", "metadata_license_url"])
def test_record_identity_and_license_evidence_crossguards_reject_misassigned_assets(tmp_path, change):
    row = work("1")
    if change == "native_page_id":
        row["id"] = "musescore:2"
    elif change == "metadata_native_id":
        row["metadata"]["pdmx_csv_transcription"]["metadata"] = "./metadata/0/2.json"
    elif change == "source_license":
        row["metadata"]["source_license"] = "publicdomain"
    elif change == "csv_license_url":
        row["metadata"]["pdmx_csv_transcription"]["license_url"] = "https://creativecommons.org/publicdomain/mark/1.0/"
    else:
        row["metadata"]["license_url"] = "https://creativecommons.org/licenses/by/4.0/"
    _, catalog = setup_root(tmp_path, [("pdf/1/2/native1.pdf", pdf_bytes(), tarfile.REGTYPE)], [row])
    with pytest.raises(ValueError, match="identity|record|license|ID"):
        pdmx_assets.acquire(tmp_path, cached_archive=True)
    assert read_catalog(tmp_path) == catalog


def test_pending_initialization_protects_scope_without_archive_or_network(tmp_path):
    archive, catalog = setup_root(tmp_path, [("pdf/1/2/native1.pdf", pdf_bytes(), tarfile.REGTYPE)])
    archive.unlink()
    report = pdmx_assets.initialize_pending_journal(tmp_path)
    assert report["status"] == "pending_archive"
    assert report["counts"]["pending_records"] == 1
    assert report["counts"]["verified_records"] == 0
    assert report["archive_checked_this_run"] is False
    assert "archive_integrity" not in report
    assert read_catalog(tmp_path) == catalog
    path = tmp_path / "sources/musescore/pdmx/pdf-extraction.json"
    before = path.read_bytes()
    assert pdmx_assets.initialize_pending_journal(tmp_path) == report
    assert path.read_bytes() == before


@pytest.mark.parametrize("field,value", [("status", "metadata_only"), ("format", "MIDI"),
                                         ("publication", {"name": "invented source"})])
def test_resume_rebuilds_invalid_staged_asset_fields_from_real_archive(tmp_path, monkeypatch, field, value):
    setup_root(tmp_path, [("pdf/1/2/native1.pdf", pdf_bytes(), tarfile.REGTYPE),
                         ("pdf/1/2/native2.pdf", pdf_bytes("second"), tarfile.REGTYPE)], [work("1"), work("2")])
    original = pdmx_assets._stream_members
    def interrupt(tar):
        for count, member in enumerate(original(tar)):
            if count == 1:
                raise KeyboardInterrupt("controlled interruption")
            yield member
    monkeypatch.setattr(pdmx_assets, "_stream_members", interrupt)
    with pytest.raises(KeyboardInterrupt):
        pdmx_assets.acquire(tmp_path, cached_archive=True, batch_size=1)
    path = tmp_path / "sources/musescore/pdmx/pdf-extraction.json"
    journal = json.loads(path.read_text())
    journal["staged_members"]["pdf/1/2/native1.pdf"]["asset"][field] = value
    path.write_text(json.dumps(journal))
    monkeypatch.setattr(pdmx_assets, "_stream_members", original)
    report = pdmx_assets.acquire(tmp_path, cached_archive=True)
    assert report["counts"]["verified_records"] == 2
    assert report["fresh_verified_staged_members"] == 0
    for row in read_catalog(tmp_path)["works"]:
        asset = row["assets"][0]
        assert asset["status"] == "verified"
        assert asset["format"] == "PDF"
        assert asset["publication"] == PUBLICATION


def test_resume_cannot_copy_a_fabricated_member_checksum_claim(tmp_path):
    setup_root(tmp_path, [("pdf/1/2/native1.pdf", pdf_bytes(), tarfile.REGTYPE)])
    pdmx_assets.acquire(tmp_path, cached_archive=True)
    catalog = read_catalog(tmp_path)
    catalog["works"][0]["assets"][0]["upstream_member_checksum_verified"] = True
    (tmp_path / "sources/musescore/catalog.json").write_text(json.dumps(catalog))
    report = pdmx_assets.acquire(tmp_path, cached_archive=True)
    assert report["counts"]["verified_records"] == 1
    asset = read_catalog(tmp_path)["works"][0]["assets"][0]
    assert "upstream_member_checksum_verified" not in asset
    assert asset["upstream_checksum_status"] == "not_supplied"


def test_catalog_cannot_reassign_another_valid_native_record_pdf_locator(tmp_path):
    _, catalog = setup_root(tmp_path, [("pdf/1/2/native1.pdf", pdf_bytes("first"), tarfile.REGTYPE),
                                     ("pdf/1/2/native2.pdf", pdf_bytes("second"), tarfile.REGTYPE)], [work("1"), work("2")])
    changed = copy.deepcopy(catalog)
    changed["works"][0]["metadata"]["pdmx_csv_transcription"]["pdf"] = changed["works"][1]["metadata"]["pdmx_csv_transcription"]["pdf"]
    (tmp_path / "sources/musescore/catalog.json").write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="CSV.*binding|frozen.*CSV"):
        pdmx_assets.acquire(tmp_path, cached_archive=True)
    assert read_catalog(tmp_path) == changed
    assert not (tmp_path / "sources/musescore/objects").exists()


def test_authoritative_csv_checksum_is_fresh_before_any_pdf_member_extraction(tmp_path):
    _, catalog = setup_root(tmp_path, [("pdf/1/2/native1.pdf", pdf_bytes(), tarfile.REGTYPE)])
    path = tmp_path / "sources/musescore/pdmx/PDMX.csv"
    path.write_bytes(path.read_bytes().replace(b"cc-zero", b"cc-wrong"))
    with pytest.raises(ValueError, match="CSV.*checksum|CSV.*integrity"):
        pdmx_assets.acquire(tmp_path, cached_archive=True)
    assert read_catalog(tmp_path) == catalog
    assert not (tmp_path / "sources/musescore/objects").exists()


def test_authoritative_csv_replacement_after_hash_cannot_change_record_locator(tmp_path, monkeypatch):
    _, catalog = setup_root(tmp_path, [("pdf/1/2/native1.pdf", pdf_bytes(), tarfile.REGTYPE)])
    original = pdmx_assets._digests
    def replace_csv_after_hash(path):
        result = original(path)
        if path.name == "PDMX.csv":
            path.write_bytes(path.read_bytes() + b"changed after hash")
        return result
    monkeypatch.setattr(pdmx_assets, "_digests", replace_csv_after_hash)
    with pytest.raises(ValueError, match="CSV.*changed"):
        pdmx_assets.acquire(tmp_path, cached_archive=True)
    assert read_catalog(tmp_path) == catalog


def test_previous_pending_journal_remains_guarded_while_csv_binding_is_upgraded(tmp_path):
    setup_root(tmp_path, [("pdf/1/2/native1.pdf", pdf_bytes(), tarfile.REGTYPE)])
    previous = pdmx_assets.initialize_pending_journal(tmp_path)
    path = tmp_path / "sources/musescore/pdmx/pdf-extraction.json"
    previous.pop("csv_binding", None)
    path.write_text(json.dumps(previous))
    report = pdmx_assets.acquire(tmp_path, cached_archive=True)
    assert report["counts"]["verified_records"] == 1
    assert report["csv_binding"]["bound_records"] == 1


def test_authoritative_csv_change_during_pdf_selection_prevents_final_catalog_commit(tmp_path, monkeypatch):
    _, catalog = setup_root(tmp_path, [("pdf/1/2/native1.pdf", pdf_bytes(), tarfile.REGTYPE)])
    path = tmp_path / "sources/musescore/pdmx/PDMX.csv"
    original = pdmx_assets._store_pdf
    def change_csv_after_extract(*args):
        result = original(*args)
        path.write_bytes(path.read_bytes() + b"\n")
        return result
    monkeypatch.setattr(pdmx_assets, "_store_pdf", change_csv_after_extract)
    with pytest.raises(ValueError, match="CSV/configuration changed before catalog commit"):
        pdmx_assets.acquire(tmp_path, cached_archive=True)
    assert read_catalog(tmp_path) == catalog
