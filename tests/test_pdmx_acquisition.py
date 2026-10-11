"""PDMX byte acquisition, frozen CSV selection and safe metadata archive reading."""
import csv
import hashlib
import io
import json
import tarfile

import pytest

from source_adapters import pdmx


URL = "https://zenodo.org/api/records/15571083/files/metadata.tar.gz/content"


class Response:
    def __init__(self, body=b"", *, status=200, headers=None, url=URL, fail_after=False):
        self.body, self.status_code, self.url = body, status, url
        self.headers = headers or {"Content-Length": str(len(body))}
        self.fail_after = fail_after
        self.closed = False

    def iter_content(self, chunk_size):
        yield self.body
        if self.fail_after:
            raise OSError("interrupted stream")

    def close(self):
        self.closed = True


class Transport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


def download(tmp_path, body, transport, **kwargs):
    return pdmx.download_file(URL, tmp_path / "metadata.tar.gz", expected_size=len(body),
                              expected_md5=hashlib.md5(body).hexdigest(), session=transport, **kwargs)


def test_interruption_resumes_correct_range_and_publishes_only_verified_bytes(tmp_path):
    body = b"complete metadata archive"
    transport = Transport(Response(body[:7], headers={"Content-Length": str(len(body))}, fail_after=True))
    with pytest.raises(OSError, match="interrupted"):
        download(tmp_path, body, transport)
    assert not (tmp_path / "metadata.tar.gz").exists()
    assert (tmp_path / "metadata.tar.gz.part").read_bytes() == body[:7]
    response = Response(body[7:], status=206, headers={
        "Content-Length": str(len(body)-7), "Content-Range": f"bytes 7-{len(body)-1}/{len(body)}"})
    resumed = Transport(response)
    receipt = download(tmp_path, body, resumed, receipt_path=tmp_path / "receipt.json")
    assert resumed.calls[0][1]["headers"]["Range"] == "bytes=7-"
    assert (tmp_path / "metadata.tar.gz").read_bytes() == body
    assert receipt["sha256"] == hashlib.sha256(body).hexdigest()
    assert receipt["upstream_checksum_verified"] is True
    assert response.closed
    assert json.loads((tmp_path / "receipt.json").read_text()) == receipt
    assert not (tmp_path / "metadata.tar.gz.part").exists()


@pytest.mark.parametrize("content_range", ["bytes 0-9/10", "bytes 4-9/11", "bytes 4-8/10", "nonsense"])
def test_inconsistent_resume_range_preserves_previous_partial(tmp_path, content_range):
    body = b"0123456789"
    (tmp_path / "metadata.tar.gz.part").write_bytes(body[:4])
    response = Response(body[4:], status=206, headers={"Content-Length": "6", "Content-Range": content_range})
    with pytest.raises(ValueError, match="range|Range|length"):
        download(tmp_path, body, Transport(response))
    assert (tmp_path / "metadata.tar.gz.part").read_bytes() == body[:4]
    assert not (tmp_path / "metadata.tar.gz").exists()


def test_server_ignoring_range_restarts_instead_of_appending(tmp_path):
    body = b"0123456789"
    (tmp_path / "metadata.tar.gz.part").write_bytes(body[:4])
    download(tmp_path, body, Transport(Response(body)))
    assert (tmp_path / "metadata.tar.gz").read_bytes() == body


@pytest.mark.parametrize("status", [401, 403, 429])
def test_access_stop_keeps_partial_and_stops_client(tmp_path, status):
    body = b"0123456789"
    part = tmp_path / "metadata.tar.gz.part"
    part.write_bytes(body[:4])
    transport = Transport(Response(status=status))
    client = pdmx.ZenodoFileClient(session=transport)
    for _ in range(2):
        with pytest.raises(pdmx.AccessStopped):
            client.download_file(URL, tmp_path / "metadata.tar.gz", expected_size=len(body),
                                 expected_md5=hashlib.md5(body).hexdigest())
    assert len(transport.calls) == 1
    assert part.read_bytes() == body[:4]


@pytest.mark.parametrize("url", ["https://zenodo.org/api/records/15571083", "https://musescore.com/x",
    "https://zenodo.org.evil.test/api/records/15571083/files/x/content",
    "https://zenodo.org/api/records/15571083/files/../secret/content", URL + "?download=1",
    "http://zenodo.org/api/records/15571083/files/x/content"])
def test_unapproved_endpoint_never_requests(tmp_path, url):
    transport = Transport()
    with pytest.raises(ValueError, match="endpoint"):
        pdmx.download_file(url, tmp_path / "x", expected_size=10, expected_md5="0"*32, session=transport)
    assert transport.calls == []


def test_checksum_failure_does_not_replace_existing_destination(tmp_path):
    (tmp_path / "metadata.tar.gz").write_bytes(b"old approved bytes")
    with pytest.raises(ValueError, match="checksum"):
        download(tmp_path, b"correct", Transport(Response(b"invalid")))
    assert (tmp_path / "metadata.tar.gz").read_bytes() == b"old approved bytes"


def test_same_host_clock_spaces_requests_by_ten_seconds(tmp_path):
    clock = [100.0]
    sleeps = []
    def wait(seconds):
        sleeps.append(seconds)
        clock[0] += seconds
    client = pdmx.ZenodoFileClient(session=Transport(Response(b"a"), Response(b"b")),
                                   clock=lambda: clock[0], sleep=wait)
    client.download_file(URL, tmp_path / "a", expected_size=1, expected_md5=hashlib.md5(b"a").hexdigest())
    client.download_file(URL, tmp_path / "b", expected_size=1, expected_md5=hashlib.md5(b"b").hexdigest())
    assert sleeps == [10.0]


def test_source_stop_arriving_during_polite_wait_prevents_next_request(tmp_path):
    transport = Transport(Response(b"a"), Response(b"b"))
    client = pdmx.ZenodoFileClient(session=transport, clock=lambda: 100.0)
    client.download_file(URL, tmp_path / "a", expected_size=1, expected_md5=hashlib.md5(b"a").hexdigest())
    def stop_while_waiting(_):
        client.stopped = "upstream access stop"
    client.sleep = stop_while_waiting
    with pytest.raises(pdmx.AccessStopped):
        client.download_file(URL, tmp_path / "b", expected_size=1, expected_md5=hashlib.md5(b"b").hexdigest())
    assert len(transport.calls) == 1


def csv_file(tmp_path, rows):
    path = tmp_path / "PDMX.csv"
    fields = ["path", "metadata", "tracks", "n_tracks", "license", "license_conflict", "subset:no_license_conflict", "title"]
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for index, override in enumerate(rows, 1):
            writer.writerow({"path": f"./data/{index}.json", "metadata": f"./metadata/1/{index}.json",
                             "tracks": "24", "n_tracks": "1", "license": "cc-zero", "license_conflict": "False",
                             "subset:no_license_conflict": "True", "title": "Native title", **override})
    return path


def test_csv_keeps_mixed_guitar_candidates_without_assigning_player_counts(tmp_path):
    report = pdmx.select_guitar_candidates(csv_file(tmp_path, [
        {}, {"tracks": "24-0", "n_tracks": "2"}, {"tracks": "24-24", "n_tracks": "2"},
        {"tracks": "0"}, {"license_conflict": "True"}, {"subset:no_license_conflict": "False"},
        {"license": "cc-by"}, {"license": "publicdomain"}]))
    assert [row["source_record_id"] for row in report["candidates"]] == ["1", "2", "3", "8"]
    assert report["counts"]["dataset_rows"] == 8
    assert report["counts"]["mixed_program_candidates"] == 1
    assert all(row["review_status"] == "pending_score_metadata_review" for row in report["candidates"])
    assert all("instrumentation" not in row and "player_count" not in row for row in report["candidates"])
    assert report["candidates"][0]["csv"]["title"] == "Native title"


@pytest.mark.parametrize("override,reason", [
    ({"tracks": "24--25"}, "invalid_program_tokens"), ({"tracks": "24-128", "n_tracks": "2"}, "invalid_program_range"),
    ({"tracks": "24-24"}, "track_count_mismatch"), ({"license_conflict": "false"}, "invalid_license_conflict"),
    ({"subset:no_license_conflict": "1"}, "invalid_no_conflict_subset"),
    ({"metadata": "./metadata/1/../1.json"}, "invalid_metadata_locator")])
def test_candidate_lexical_errors_have_explicit_exclusion_reasons(tmp_path, override, reason):
    result = pdmx.select_guitar_candidates(csv_file(tmp_path, [override]))
    assert result["candidates"] == []
    assert result["exclusions"][0]["reason"] == reason


def test_huge_program_token_is_an_exclusion_instead_of_aborting_the_scan(tmp_path):
    result = pdmx.select_guitar_candidates(csv_file(tmp_path, [{"tracks": "24-" + "9"*5000, "n_tracks": "2"}, {}]))
    assert [row["source_record_id"] for row in result["candidates"]] == ["2"]
    assert result["exclusions"][0]["reason"] == "invalid_program_range"


def archive_file(tmp_path, members):
    path = tmp_path / "metadata.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        for name, body, kind in members:
            info = tarfile.TarInfo(name)
            info.type = kind
            info.size = len(body) if kind == tarfile.REGTYPE else 0
            if kind in {tarfile.SYMTYPE, tarfile.LNKTYPE}:
                info.linkname = "../../outside"
            archive.addfile(info, io.BytesIO(body) if kind == tarfile.REGTYPE else None)
    return path


def archive_receipt(path):
    body = path.read_bytes()
    return {"url": URL, "bytes": len(body), "upstream_checksum_verified": True,
            "upstream_checksum": "md5:" + hashlib.md5(body).hexdigest(),
            "sha256": hashlib.sha256(body).hexdigest()}


def read_metadata(path, candidates, **kwargs):
    return pdmx.read_candidate_metadata(path, candidates, receipt=archive_receipt(path), **kwargs)


def test_archive_stream_reads_only_selected_native_metadata_and_reports_missing(tmp_path):
    path = archive_file(tmp_path, [("./metadata/", b"", tarfile.DIRTYPE),
        ("./metadata/1/1.json", b'{"id":1,"title":"Original"}', tarfile.REGTYPE),
        ("./metadata/2/2.json", b"unselected JSON is never parsed", tarfile.REGTYPE)])
    result = read_metadata(path, {"1", "3"})
    assert result["records"] == {"1": {"id": 1, "title": "Original"}}
    assert result["missing_ids"] == ["3"]
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("name,kind", [("/metadata/1/1.json", tarfile.REGTYPE),
    ("metadata/../1.json", tarfile.REGTYPE), ("metadata/1/1.json", tarfile.SYMTYPE),
    ("metadata/1/1.json", tarfile.LNKTYPE), ("metadata/1/1.json", tarfile.FIFOTYPE)])
def test_unsafe_archive_member_is_rejected_without_extraction(tmp_path, name, kind):
    path = archive_file(tmp_path, [(name, b'{"id":1}', kind)])
    with pytest.raises(ValueError, match="unsafe|regular"):
        read_metadata(path, {"1"})
    assert list(tmp_path.iterdir()) == [path]


def test_archive_size_limit_and_conflicting_duplicate_native_ids_fail(tmp_path):
    path = archive_file(tmp_path, [("metadata/1/1.json", b'{"id":1}', tarfile.REGTYPE)])
    with pytest.raises(ValueError, match="size"):
        read_metadata(path, {"1"}, max_member_bytes=5)
    path = archive_file(tmp_path, [("metadata/1/1.json", b'{"id":1}', tarfile.REGTYPE),
        ("metadata/1/1.json", b'{"id":1,"title":"different"}', tarfile.REGTYPE)])
    with pytest.raises(ValueError, match="duplicate"):
        read_metadata(path, {"1"})


def test_archive_duplicate_json_keys_cannot_silently_change_licensing(tmp_path):
    path = archive_file(tmp_path, [("metadata/1/1.json", b'{"license":"cc-zero","license":"copyright"}', tarfile.REGTYPE)])
    with pytest.raises(ValueError, match="duplicate JSON"):
        read_metadata(path, {"1"})


def test_metadata_requires_fresh_archive_checksum_and_explicit_pending_state(tmp_path):
    path = archive_file(tmp_path, [("metadata/1/1.json", b'{"id":1}', tarfile.REGTYPE)])
    result = read_metadata(path, {"1", "2"})
    assert result["complete"] is False
    assert result["status"] == "pending_metadata"
    assert result["pending_ids"] == ["2"]
    assert result["archive_integrity"]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    receipt = archive_receipt(path)
    path.write_bytes(path.read_bytes() + b"unexpected bytes")
    with pytest.raises(ValueError, match="archive.*checksum|archive.*integrity"):
        pdmx.read_candidate_metadata(path, {"1"}, receipt=receipt)


def test_metadata_reader_rejects_absent_or_unverified_receipt(tmp_path):
    path = archive_file(tmp_path, [("metadata/1/1.json", b'{"id":1}', tarfile.REGTYPE)])
    with pytest.raises(ValueError, match="receipt"):
        pdmx.read_candidate_metadata(path, {"1"})
    receipt = archive_receipt(path)
    receipt["upstream_checksum_verified"] = False
    with pytest.raises(ValueError, match="receipt"):
        pdmx.read_candidate_metadata(path, {"1"}, receipt=receipt)
