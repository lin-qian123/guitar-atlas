"""Actual local HTTP Range transport for the fixed two-stream Zenodo route."""
import hashlib
import json
import socket
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import requests

from source_adapters import zenodo_download


URL = "https://zenodo.org/records/15571083/files/pdf.tar.gz"
ROBOTS = "https://zenodo.org/robots.txt"


@contextmanager
def range_server(body, *, mode="good", stop_after=None):
    state = {"calls": [], "active": 0, "max_active": 0, "lock": threading.Lock(), "interrupted": False,
             "concurrent": threading.Event()}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            with state["lock"]:
                state["calls"].append((self.path, self.headers.get("Range")))
            if self.path == "/robots.txt":
                text = b"User-agent: *\nAllow: /records/15571083/files/pdf.tar.gz\nCrawl-delay: 10\n"
                self.send_response(200); self.send_header("Content-Length", str(len(text))); self.end_headers(); self.wfile.write(text)
                return
            if mode.startswith("stop"):
                self.send_response(int(mode[4:]) if mode[4:] else 403); self.send_header("Content-Length", "0"); self.end_headers(); return
            start, end = map(int, self.headers["Range"].removeprefix("bytes=").split("-"))
            chunk = body[start:end+1]
            if mode == "challenge":
                message = b"<!doctype html><html>Verify you are human cf-chl-</html>"
                chunk = (message + b" "*len(chunk))[:len(chunk)]
            self.send_response(200 if mode == "ignored" else 206)
            self.send_header("Content-Range", f"bytes {start+1 if mode=='wrong' else start}-{end}/{len(body)}")
            self.send_header("Content-Length", str(len(chunk)))
            if mode == "encoded":
                self.send_header("Content-Encoding", "gzip")
            if mode == "challenge":
                self.send_header("Content-Type", "text/html")
            self.end_headers()
            with state["lock"]:
                state["active"] += 1
                state["max_active"] = max(state["active"], state["max_active"])
                interrupt = stop_after is not None and not state["interrupted"]
                if interrupt:
                    state["interrupted"] = True
                if state["active"] == 2:
                    state["concurrent"].set()
            try:
                if mode == "concurrent":
                    assert state["concurrent"].wait(timeout=5)
                if interrupt:
                    self.wfile.write(chunk[:stop_after]); self.wfile.flush()
                    self.connection.shutdown(socket.SHUT_RDWR)
                    self.connection.close()
                else:
                    self.wfile.write(chunk); self.wfile.flush()
            finally:
                with state["lock"]:
                    state["active"] -= 1
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", state
    finally:
        server.shutdown(); server.server_close(); thread.join()


class LocalTransport:
    """Map the one approved URL to a real local server, preserving response URLs."""
    def __init__(self, base):
        self.base = base
        self.session = requests.Session()
    def get(self, url, **kwargs):
        assert url in {URL, ROBOTS}
        path = "/robots.txt" if url == ROBOTS else "/records/15571083/files/pdf.tar.gz"
        response = self.session.get(self.base + path, **kwargs)
        response.url = url
        return response


def client(base):
    clock = [100.0]
    pauses = []
    clock_lock = threading.Lock()
    def pause(seconds):
        with clock_lock:
            pauses.append(seconds)
            clock[0] += seconds
    result = zenodo_download.RangeClient(session=LocalTransport(base), clock=lambda: clock[0], sleep=pause)
    result.pauses = pauses
    return result


def download(tmp_path, body, connection, **kwargs):
    return zenodo_download.download_file(URL, tmp_path / "pdf.tar.gz", expected_size=len(body),
        expected_md5=hashlib.md5(body).hexdigest(), client=connection, chunk_bytes=1024, **kwargs)


def test_two_ranges_preserve_existing_prefix_verify_whole_archive_and_clean_segments(tmp_path):
    body = b"\x1f\x8b" + bytes(range(256))*300
    prefix = tmp_path / "pdf.tar.gz.part"
    prefix.write_bytes(body[:1234])
    with range_server(body) as (base, state):
        connection = client(base)
        receipt = download(tmp_path, body, connection)
    assert (tmp_path / "pdf.tar.gz").read_bytes() == body
    assert receipt["upstream_checksum_verified"] is True
    assert receipt["sha256"] == hashlib.sha256(body).hexdigest()
    assert receipt["prefix_bytes"] == 1234
    assert receipt["segment_count"] == 2
    assert state["max_active"] <= 2
    assert len([call for call in state["calls"] if call[1]]) == 2
    assert all(value >= 10 for value in connection.pauses)
    assert not prefix.exists()
    assert not list(tmp_path.glob("*.range-*.part"))
    assert not (tmp_path / "pdf.tar.gz.complete.part").exists()


def test_interrupted_range_restarts_at_exact_received_offset_without_replacing_prefix(tmp_path):
    body = b"\x1f\x8b" + bytes(range(256))*300
    prefix = tmp_path / "pdf.tar.gz.part"
    saved = body[:2345]
    prefix.write_bytes(saved)
    with range_server(body, stop_after=5000) as (base, state):
        with pytest.raises(RuntimeError, match="interrupted"):
            download(tmp_path, body, client(base))
    assert prefix.read_bytes() == saved
    assert not (tmp_path / "pdf.tar.gz").exists()
    plan = json.loads((tmp_path / "pdf-range-plan.json").read_text())
    previous_sizes = [(tmp_path / row["filename"]).stat().st_size for row in plan["segments"]]
    assert any(0 < size < row["length"] for size, row in zip(previous_sizes, plan["segments"]))
    with range_server(body) as (base, state):
        receipt = download(tmp_path, body, client(base))
    expected = [f"bytes={row['start']+size}-{row['end']}" for size, row in zip(previous_sizes, plan["segments"]) if size < row["length"]]
    assert [value for _, value in state["calls"] if value] == expected
    assert receipt["upstream_checksum_verified"] is True
    assert (tmp_path / "pdf.tar.gz").read_bytes() == body


@pytest.mark.parametrize("mode", ["ignored", "wrong", "encoded"])
def test_wrong_range_or_encoding_never_appends_to_segments_or_prefix(tmp_path, mode):
    body = b"\x1f\x8b" + b"correct archive bytes"*500
    prefix = tmp_path / "pdf.tar.gz.part"
    saved = body[:100]
    prefix.write_bytes(saved)
    with range_server(body, mode=mode) as (base, state):
        with pytest.raises(RuntimeError, match="interrupted"):
            download(tmp_path, body, client(base))
    assert prefix.read_bytes() == saved
    assert not (tmp_path / "pdf.tar.gz").exists()
    assert all(path.stat().st_size == 0 for path in tmp_path.glob("*.range-*.part"))


def test_whole_checksum_failure_never_replaces_old_prefix_or_creates_final_archive(tmp_path):
    body = b"\x1f\x8b" + b"approved archive"*500
    wrong = b"\x1f\x8b" + b"different bytes!"*500
    assert len(body) == len(wrong)
    prefix = tmp_path / "pdf.tar.gz.part"
    prefix.write_bytes(body[:100])
    with range_server(wrong) as (base, state):
        with pytest.raises(ValueError, match="checksum"):
            download(tmp_path, body, client(base))
    assert prefix.read_bytes() == body[:100]
    assert not (tmp_path / "pdf.tar.gz").exists()
    assert not (tmp_path / "pdf.tar.gz.complete.part").exists()


def test_access_stop_halts_source_keeps_prefix_and_records_pending_segments(tmp_path):
    body = b"\x1f\x8b" + b"correct archive"*500
    prefix = tmp_path / "pdf.tar.gz.part"
    prefix.write_bytes(body[:100])
    with range_server(body, mode="stop") as (base, state):
        connection = client(base)
        with pytest.raises(zenodo_download.AccessStopped):
            download(tmp_path, body, connection)
    assert connection.stopped
    assert prefix.read_bytes() == body[:100]
    assert not (tmp_path / "pdf.tar.gz").exists()
    assert len([value for _, value in state["calls"] if value]) <= 2


@pytest.mark.parametrize("url", ["https://musescore.com/x", URL + "?download=1", "https://zenodo.org/records/15571083/files/other.tar.gz", "http://zenodo.org/records/15571083/files/pdf.tar.gz"])
def test_only_exact_approved_page_endpoint_can_be_requested(tmp_path, url):
    with pytest.raises(ValueError, match="endpoint"):
        zenodo_download.download_file(url, tmp_path / "pdf.tar.gz", expected_size=10, expected_md5="0"*32)
    assert list(tmp_path.iterdir()) == []


def test_exactly_two_concurrent_streams_share_the_polite_request_clock(tmp_path):
    body = b"\x1f\x8b" + bytes(range(256))*300
    with range_server(body, mode="concurrent") as (base, state):
        connection = client(base)
        download(tmp_path, body, connection)
    assert state["max_active"] == 2
    assert connection.pauses == [10.0, 10.0]


def test_parallel_pipeline_keeps_catalog_pending_until_archive_and_pdf_validation(tmp_path):
    import tarfile
    from tests.test_musescore_pdf_acquisition import setup_root, pdf_bytes, read_catalog
    from source_adapters import pdmx_assets
    archive, catalog = setup_root(tmp_path, [("pdf/1/2/native1.pdf", pdf_bytes(), tarfile.REGTYPE)])
    body = archive.read_bytes()
    archive.unlink()
    archive.with_name("pdf.tar.gz.part").write_bytes(body[:17])
    config_path = tmp_path / "config/musescore_pdmx_assets.json"
    config = json.loads(config_path.read_text())
    config["download_page_url"] = URL
    config_path.write_text(json.dumps(config))
    with range_server(body) as (base, state):
        receipt = pdmx_assets.download_parallel_archive(tmp_path, client=client(base))
    assert receipt["upstream_checksum_verified"] is True
    assert read_catalog(tmp_path) == catalog
    assert not (tmp_path / "sources/musescore/objects").exists()
    report = pdmx_assets.acquire(tmp_path, cached_archive=True)
    assert report["counts"]["verified_records"] == 1
    assert report["archive_integrity"]["url"] == URL
    assert read_catalog(tmp_path)["works"][0]["assets"][0]["status"] == "verified"


@pytest.mark.parametrize("mode", ["stop401", "stop429", "challenge"])
def test_all_access_challenges_stop_pending_requests_without_append(tmp_path, mode):
    body = b"\x1f\x8b" + b"source archive"*1000
    prefix = tmp_path / "pdf.tar.gz.part"
    prefix.write_bytes(body[:111])
    with range_server(body, mode=mode) as (base, state):
        connection = client(base)
        with pytest.raises(zenodo_download.AccessStopped):
            download(tmp_path, body, connection)
    assert connection.stopped
    assert len([row for row in state["calls"] if row[1]]) == 1
    assert prefix.read_bytes() == body[:111]
    assert not (tmp_path / "pdf.tar.gz").exists()
    assert all(path.stat().st_size == 0 for path in tmp_path.glob("*.range-*.part"))


def test_changed_prefix_on_resume_is_preserved_and_refused_before_any_request(tmp_path):
    body = b"\x1f\x8b" + bytes(range(256))*300
    prefix = tmp_path / "pdf.tar.gz.part"
    prefix.write_bytes(body[:2345])
    with range_server(body, stop_after=5000) as (base, state):
        with pytest.raises(RuntimeError):
            download(tmp_path, body, client(base))
    modified = b"X" + prefix.read_bytes()[1:]
    prefix.write_bytes(modified)
    with range_server(body) as (base, state):
        with pytest.raises(ValueError, match="prefix/publication"):
            download(tmp_path, body, client(base))
    assert prefix.read_bytes() == modified
    assert state["calls"] == []


def test_changed_plan_offsets_cannot_extend_an_unapproved_range(tmp_path):
    body = b"\x1f\x8b" + bytes(range(256))*300
    with range_server(body, stop_after=5000) as (base, state):
        with pytest.raises(RuntimeError):
            download(tmp_path, body, client(base))
    path = tmp_path / "pdf-range-plan.json"
    plan = json.loads(path.read_text())
    plan["segments"][0]["end"] += 1
    path.write_text(json.dumps(plan))
    with range_server(body) as (base, state):
        with pytest.raises(ValueError, match="offsets"):
            download(tmp_path, body, client(base))
    assert state["calls"] == []
    assert not (tmp_path / "pdf.tar.gz").exists()


def test_cached_final_archive_preserves_origin_receipt_and_makes_no_requests(tmp_path):
    body = b"\x1f\x8b" + bytes(range(256))*300
    with range_server(body) as (base, state):
        first = download(tmp_path, body, client(base))
    with range_server(body) as (base, state):
        second = download(tmp_path, body, client(base))
    assert state["calls"] == []
    assert second["cached"] is True
    assert second["completed_at"] == first["completed_at"]
    assert second["segment_count"] == 2


def test_range_download_lock_prevents_other_writer_and_prefix_overwrite(tmp_path):
    from source_adapters.pdmx_assets import source_lock
    body = b"\x1f\x8b" + bytes(range(256))*300
    prefix = tmp_path / "pdf.tar.gz.part"
    prefix.write_bytes(body[:100])
    with source_lock(tmp_path / ".pdf-range.lock"):
        with range_server(body) as (base, state):
            with pytest.raises(RuntimeError, match="lock|running"):
                download(tmp_path, body, client(base))
    assert prefix.read_bytes() == body[:100]
    assert state["calls"] == []


def local_partial_plan(tmp_path, body, *, prefix_size=100, first_complete=True, second_bytes=123):
    prefix = tmp_path / "pdf.tar.gz.part"
    prefix.write_bytes(body[:prefix_size])
    middle = prefix_size + (len(body)-prefix_size+1)//2
    segments = []
    for index, (start, end) in enumerate([(prefix_size, middle-1), (middle, len(body)-1)]):
        piece = tmp_path / f"pdf.tar.gz.range-{index}.part"
        length = end-start+1
        size = length if index == 0 and first_complete else min(second_bytes, length-1)
        piece.write_bytes(body[start:start+size])
        segments.append({"filename": piece.name, "start": start, "end": end, "length": length,
                         "received": size, "status": "complete" if size == length else "interrupted"})
    plan = {"schema_version": 1, "url": URL, "expected_size": len(body),
            "expected_md5": hashlib.md5(body).hexdigest(), "status": "interrupted", "error": "",
            "prefix": {"bytes": prefix_size, "sha256": hashlib.sha256(prefix.read_bytes()).hexdigest()},
            "segments": segments}
    (tmp_path / "pdf-range-plan.json").write_text(json.dumps(plan))
    return plan


def consolidate(tmp_path, body):
    return zenodo_download.consolidate_received_prefix(tmp_path / "pdf.tar.gz", expected_size=len(body),
                                                        expected_md5=hashlib.md5(body).hexdigest())


def test_local_consolidation_preserves_every_contiguous_received_byte_then_ranges_verify(tmp_path):
    body = b"\x1f\x8b" + bytes(range(256))*300
    plan = local_partial_plan(tmp_path, body)
    expected_prefix = body[:plan["segments"][1]["start"]+123]
    result = consolidate(tmp_path, body)
    assert result["status"] == "consolidated"
    assert (tmp_path / "pdf.tar.gz.part").read_bytes() == expected_prefix
    new = json.loads((tmp_path / "pdf-range-plan.json").read_text())
    assert new["prefix"] == {"bytes": len(expected_prefix), "sha256": hashlib.sha256(expected_prefix).hexdigest()}
    assert new["consolidation"]["status"] == "complete"
    assert new["consolidation"]["old_plan_summary"]["expected_md5"] == plan["expected_md5"]
    assert new.get("upstream_checksum_verified") is not True
    assert not (tmp_path / "pdf.tar.gz").exists()
    assert not list(tmp_path.glob("*.range-*.part"))
    with range_server(body) as (base, state):
        receipt = download(tmp_path, body, client(base))
    assert receipt["upstream_checksum_verified"] is True
    assert (tmp_path / "pdf.tar.gz").read_bytes() == body


def test_incomplete_first_fragment_cannot_merge_or_delete_later_bytes_across_a_gap(tmp_path):
    body = b"\x1f\x8b" + bytes(range(256))*300
    local_partial_plan(tmp_path, body, first_complete=False)
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir() if not path.name.startswith(".")}
    result = consolidate(tmp_path, body)
    assert result["status"] == "unchanged"
    assert result["reason"] == "first_segment_incomplete"
    after = {path.name: path.read_bytes() for path in tmp_path.iterdir() if not path.name.startswith(".")}
    assert after == before


def test_all_segments_already_received_are_left_for_existing_whole_archive_finalizer(tmp_path):
    body = b"\x1f\x8b" + bytes(range(256))*300
    plan = local_partial_plan(tmp_path, body)
    row = plan["segments"][1]
    (tmp_path / row["filename"]).write_bytes(body[row["start"]:])
    before = (tmp_path / "pdf-range-plan.json").read_bytes()
    result = consolidate(tmp_path, body)
    assert result == {"status": "unchanged", "reason": "all_segments_received_finalize_existing_plan"}
    assert (tmp_path / "pdf-range-plan.json").read_bytes() == before


@pytest.mark.parametrize("status", ["stopped_access", "blocked", "AccessStopped"])
def test_consolidation_never_replans_a_source_access_refusal(tmp_path, status):
    body = b"\x1f\x8b" + bytes(range(256))*300
    plan = local_partial_plan(tmp_path, body)
    plan["status"] = status
    path = tmp_path / "pdf-range-plan.json"
    path.write_text(json.dumps(plan))
    before = {file.name: file.read_bytes() for file in tmp_path.iterdir() if not file.name.startswith(".")}
    with pytest.raises(zenodo_download.AccessStopped):
        consolidate(tmp_path, body)
    after = {file.name: file.read_bytes() for file in tmp_path.iterdir() if not file.name.startswith(".")}
    assert after == before


def test_local_consolidation_refuses_prefix_or_offsets_tampering_without_replacing_bytes(tmp_path):
    body = b"\x1f\x8b" + bytes(range(256))*300
    plan = local_partial_plan(tmp_path, body)
    plan["segments"][1]["start"] += 1
    path = tmp_path / "pdf-range-plan.json"
    path.write_text(json.dumps(plan))
    before = (tmp_path / "pdf.tar.gz.part").read_bytes()
    with pytest.raises(ValueError, match="offsets|plan"):
        consolidate(tmp_path, body)
    assert (tmp_path / "pdf.tar.gz.part").read_bytes() == before


def test_consolidation_source_and_range_locks_prevent_changes_while_writer_active(tmp_path):
    from source_adapters.pdmx_assets import source_lock
    body = b"\x1f\x8b" + bytes(range(256))*300
    local_partial_plan(tmp_path, body)
    before = (tmp_path / "pdf.tar.gz.part").read_bytes()
    for filename in (".pdf-acquisition.lock", ".pdf-range.lock"):
        with source_lock(tmp_path / filename):
            with pytest.raises(RuntimeError, match="lock|running"):
                consolidate(tmp_path, body)
    assert (tmp_path / "pdf.tar.gz.part").read_bytes() == before


def test_mid_copy_input_modification_refuses_atomic_prefix_replacement(tmp_path, monkeypatch):
    body = b"\x1f\x8b" + bytes(range(256))*300
    plan = local_partial_plan(tmp_path, body)
    prefix = tmp_path / "pdf.tar.gz.part"
    original_prefix = prefix.read_bytes()
    original_plan = (tmp_path / "pdf-range-plan.json").read_bytes()
    original = zenodo_download._copy_prefix
    def change_after_copy(paths, destination):
        result = original(paths, destination)
        path = paths[1]
        path.write_bytes(b"X" + path.read_bytes()[1:])
        return result
    monkeypatch.setattr(zenodo_download, "_copy_prefix", change_after_copy)
    with pytest.raises(ValueError, match="input changed during prefix copy"):
        consolidate(tmp_path, body)
    assert prefix.read_bytes() == original_prefix
    assert (tmp_path / "pdf-range-plan.json").read_bytes() == original_plan
    assert not (tmp_path / "pdf.tar.gz.prefix-consolidation.part").exists()
    assert all((tmp_path / row["filename"]).exists() for row in plan["segments"])


def test_interruption_after_prefix_replace_recovers_same_canonical_plan_without_data_loss(tmp_path, monkeypatch):
    body = b"\x1f\x8b" + bytes(range(256))*300
    original_plan = local_partial_plan(tmp_path, body)
    original = zenodo_download._atomic_json
    def interrupt_final_plan(path, payload):
        if payload.get("consolidation", {}).get("status") == "complete":
            raise OSError("controlled crash after prefix replacement")
        return original(path, payload)
    monkeypatch.setattr(zenodo_download, "_atomic_json", interrupt_final_plan)
    with pytest.raises(OSError, match="controlled crash"):
        consolidate(tmp_path, body)
    path = tmp_path / "pdf-range-plan.json"
    assert json.loads(path.read_text())["consolidation"]["status"] == "prepared"
    assert all((tmp_path / row["filename"]).exists() for row in original_plan["segments"])
    with range_server(body) as (base, state):
        with pytest.raises(ValueError, match="pending local consolidation"):
            download(tmp_path, body, client(base))
    assert state["calls"] == []
    monkeypatch.setattr(zenodo_download, "_atomic_json", original)
    assert consolidate(tmp_path, body)["status"] == "consolidated"
    expected = body[:original_plan["segments"][1]["start"]+123]
    assert (tmp_path / "pdf.tar.gz.part").read_bytes() == expected
    assert not list(tmp_path.glob("*.range-*.part"))
    with range_server(body) as (base, state):
        receipt = download(tmp_path, body, client(base))
    assert receipt["upstream_checksum_verified"] is True


def test_prepared_transaction_cannot_delete_a_forged_unrelated_input_file(tmp_path, monkeypatch):
    body = b"\x1f\x8b" + bytes(range(256))*300
    local_partial_plan(tmp_path, body)
    original = zenodo_download._atomic_json
    def stop_before_final(path, payload):
        if payload.get("consolidation", {}).get("status") == "complete":
            raise OSError("prepared state fixture")
        return original(path, payload)
    monkeypatch.setattr(zenodo_download, "_atomic_json", stop_before_final)
    with pytest.raises(OSError):
        consolidate(tmp_path, body)
    monkeypatch.setattr(zenodo_download, "_atomic_json", original)
    unrelated = tmp_path / "unrelated.txt"
    unrelated.write_bytes(b"keep this file")
    path = tmp_path / "pdf-range-plan.json"
    plan = json.loads(path.read_text())
    plan["consolidation"]["input_guards"][1] = {"filename": unrelated.name, "bytes": unrelated.stat().st_size,
                                                 "sha256": hashlib.sha256(unrelated.read_bytes()).hexdigest()}
    path.write_text(json.dumps(plan))
    with pytest.raises(ValueError, match="guards.*exact old plan"):
        consolidate(tmp_path, body)
    assert unrelated.read_bytes() == b"keep this file"


def test_plan_change_during_prefix_copy_is_preserved_and_cannot_be_overwritten(tmp_path, monkeypatch):
    body = b"\x1f\x8b" + bytes(range(256))*300
    local_partial_plan(tmp_path, body)
    path = tmp_path / "pdf-range-plan.json"
    prefix = tmp_path / "pdf.tar.gz.part"
    original_prefix = prefix.read_bytes()
    original = zenodo_download._copy_prefix
    def block_source_during_copy(paths, destination):
        result = original(paths, destination)
        plan = json.loads(path.read_text())
        plan["status"] = "blocked"
        plan["error"] = "external source stop"
        path.write_text(json.dumps(plan))
        return result
    monkeypatch.setattr(zenodo_download, "_copy_prefix", block_source_during_copy)
    with pytest.raises(ValueError, match="range plan changed"):
        consolidate(tmp_path, body)
    assert json.loads(path.read_text())["status"] == "blocked"
    assert prefix.read_bytes() == original_prefix


def test_prepared_staging_and_its_self_reported_hash_cannot_replace_original_received_bytes(tmp_path, monkeypatch):
    body = b"\x1f\x8b" + bytes(range(256))*300
    original_plan = local_partial_plan(tmp_path, body)
    prefix = tmp_path / "pdf.tar.gz.part"
    prefix_before = prefix.read_bytes()
    original = zenodo_download._finish_consolidation
    def interrupt_before_replacement(*args):
        raise KeyboardInterrupt("prepared before replacement")
    monkeypatch.setattr(zenodo_download, "_finish_consolidation", interrupt_before_replacement)
    with pytest.raises(KeyboardInterrupt):
        consolidate(tmp_path, body)
    monkeypatch.setattr(zenodo_download, "_finish_consolidation", original)
    staging = tmp_path / "pdf.tar.gz.prefix-consolidation.part"
    staging.write_bytes(b"X" + staging.read_bytes()[1:])
    path = tmp_path / "pdf-range-plan.json"
    plan = json.loads(path.read_text())
    plan["consolidation"]["new_prefix"]["sha256"] = hashlib.sha256(staging.read_bytes()).hexdigest()
    path.write_text(json.dumps(plan))
    with pytest.raises(ValueError, match="concatenat|original.*identity"):
        consolidate(tmp_path, body)
    assert prefix.read_bytes() == prefix_before
    assert all((tmp_path / row["filename"]).exists() for row in original_plan["segments"])


def test_replaced_prefix_and_self_reported_hash_must_still_match_every_original_slice(tmp_path, monkeypatch):
    body = b"\x1f\x8b" + bytes(range(256))*300
    original_plan = local_partial_plan(tmp_path, body)
    original = zenodo_download._atomic_json
    def interrupt_final_plan(path, payload):
        if payload.get("consolidation", {}).get("status") == "complete":
            raise OSError("after replacement")
        return original(path, payload)
    monkeypatch.setattr(zenodo_download, "_atomic_json", interrupt_final_plan)
    with pytest.raises(OSError):
        consolidate(tmp_path, body)
    monkeypatch.setattr(zenodo_download, "_atomic_json", original)
    prefix = tmp_path / "pdf.tar.gz.part"
    prefix.chmod(0o644)
    prefix.write_bytes(b"X" + prefix.read_bytes()[1:])
    path = tmp_path / "pdf-range-plan.json"
    plan = json.loads(path.read_text())
    plan["consolidation"]["new_prefix"]["sha256"] = hashlib.sha256(prefix.read_bytes()).hexdigest()
    path.write_text(json.dumps(plan))
    with pytest.raises(ValueError, match="slice|original.*identity"):
        consolidate(tmp_path, body)
    assert all((tmp_path / row["filename"]).exists() for row in original_plan["segments"])
