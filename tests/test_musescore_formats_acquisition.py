"""Real MXL/MIDI and safe TAR checks for frozen native PDMX records."""
import copy
import csv
import gzip
import hashlib
import io
import json
import struct
import tarfile
import zipfile
from pathlib import Path

import pytest

from source_adapters import pdmx_formats
from source_adapters.pdmx_assets import PUBLICATION


def work(identity):
    return {"id": f"musescore:{identity}", "title_en": "Native title", "title_zh": "中文参考题名",
            "composer_en": "Native Composer", "source_url": f"https://musescore.com/user/3/scores/{identity}",
            "category_ids": ["guitar"], "formats": ["PDF", "MIDI", "MUSICXML"],
            "assets": [{"format": "PDF", "status": "metadata_only"}, {"format": "MIDI", "status": "metadata_only"}],
            "metadata": {"attribution_role": "composer", "license": "CC0", "source_license": "cc-zero",
                         "license_url": "https://creativecommons.org/publicdomain/zero/1.0/", "pdmx_csv_transcription": {
                "path": f"./data/1/2/native{identity}.json", "pdf": f"./pdf/1/2/native{identity}.pdf",
                "metadata": f"./metadata/0/{identity}.json", "license": "cc-zero",
                "license_url": "https://creativecommons.org/publicdomain/zero/1.0/", "license_conflict": "False",
                "subset:no_license_conflict": "True", "subset:all_valid": "True"}}}


SCORE = b'''<?xml version="1.0"?><!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd"><score-partwise version="4.0"><part-list><score-part id="P1"><part-name>Guitar</part-name></score-part></part-list><part id="P1"><measure number="1"><note><rest/><duration>4</duration></note></measure></part></score-partwise>'''
CONTAINER = b'''<?xml version="1.0"?><container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="score.xml" media-type="application/vnd.recordare.musicxml+xml"/></rootfiles></container>'''


def mxl_bytes(entries=None):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as target:
        for name, body in entries or [("META-INF/container.xml", CONTAINER), ("score.xml", SCORE)]:
            target.writestr(name, body)
    return stream.getvalue()


def midi_bytes(track=b"\x00\xc0\x18\x00\x90\x3c\x40\x81\x00\x80\x3c\x00\x00\xff\x2f\x00", *, fmt=0, division=480, tracks=None):
    tracks = tracks or [track]
    return b"MThd" + struct.pack(">IHHH", 6, fmt, len(tracks), division) + b"".join(b"MTrk" + struct.pack(">I", len(row)) + row for row in tracks)


def setup_root(tmp_path, members, *, asset_format="MUSICXML", works=None, limits=None):
    code, suffix = ("mxl", "mxl") if asset_format == "MUSICXML" else ("mid", "mid")
    base = tmp_path / "sources/musescore/pdmx"
    base.mkdir(parents=True)
    archive = base / (code + ".tar.gz")
    with tarfile.open(archive, "w:gz") as target:
        for name, body, kind in members:
            info = tarfile.TarInfo(name)
            info.type = kind
            info.size = len(body) if kind == tarfile.REGTYPE else 0
            if kind in {tarfile.SYMTYPE, tarfile.LNKTYPE}:
                info.linkname = "../../outside"
            target.addfile(info, io.BytesIO(body) if kind == tarfile.REGTYPE else None)
    original = works or [work("1")]
    for row in original:
        native = row["id"].split(":")[1]
        row["metadata"]["pdmx_csv_transcription"].setdefault("mxl", f"./mxl/1/2/native{native}.mxl")
        row["metadata"]["pdmx_csv_transcription"].setdefault("mid", f"./mid/1/2/native{native}.mid")
        if not any(asset["format"] == "MUSICXML" for asset in row["assets"]):
            row["assets"].append({"format": "MUSICXML", "status": "metadata_only", "native_note": "preserve"})
    (tmp_path / "config").mkdir()
    registry = Path(__file__).resolve().parents[1] / "config/sources.json"
    (tmp_path / "config/sources.json").write_bytes(registry.read_bytes())
    config = {"schema_version": 1, "source_id": "musescore", "publication": PUBLICATION,
              "scope_version": "test", "scope": "approved exact native records", "expected_records": len(original),
              "files": {"mxl.tar.gz": {"size": 1, "md5": "0"*32}, "mid.tar.gz": {"size": 1, "md5": "0"*32}},
              "limits": {"max_members": 100, "max_member_bytes": 1024*1024, "max_total_bytes": 20*1024*1024,
                         "max_selected_bytes": 10*1024*1024, "max_expansion_ratio": 100, **(limits or {})}}
    raw = archive.read_bytes()
    config["files"][code + ".tar.gz"] = {"size": len(raw), "md5": hashlib.md5(raw).hexdigest()}
    (tmp_path / "config/musescore_pdmx_formats.json").write_text(json.dumps(config))
    csv_path = base / "PDMX.csv"
    rows = [row["metadata"]["pdmx_csv_transcription"] for row in original]
    with csv_path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=sorted(set().union(*(set(row) for row in rows))))
        writer.writeheader()
        writer.writerows(rows)
    csv_raw = csv_path.read_bytes()
    metadata_config = {"schema_version": 1, "source_id": "musescore", "scope_version": "test", "publication": PUBLICATION,
                       "scope": "frozen fixture", "files": {"PDMX.csv": {"size": len(csv_raw), "md5": hashlib.md5(csv_raw).hexdigest()},
                                                            "metadata.tar.gz": {"size": 1, "md5": "0"*32}}}
    config_path = tmp_path / "config/musescore_pdmx.json"
    config_path.write_text(json.dumps(metadata_config))
    catalog = {"schema_version": 1, "source_id": "musescore", "snapshot": {"publication": PUBLICATION,
               "configuration_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
               "metadata_checksums": {"PDMX.csv": hashlib.sha256(csv_raw).hexdigest()}},
               "categories": [{"id": "guitar", "name": "Guitar"}], "works": original,
               "summary": {"source_records": len(original), "verified_local_pdfs": 0}}
    (tmp_path / "sources/musescore/catalog.json").write_text(json.dumps(catalog, ensure_ascii=False))
    return archive, catalog


def read_catalog(root):
    return json.loads((root / "sources/musescore/catalog.json").read_text())


@pytest.mark.parametrize("asset_format,body,code", [("MUSICXML", mxl_bytes(), "mxl"), ("MIDI", midi_bytes(), "mid")])
def test_associate_same_native_records_preserve_pdf_and_metadata_and_deduplicate(tmp_path, asset_format, body, code):
    works = [work("1"), work("2"), work("3"), work("4")]
    works[1]["metadata"]["pdmx_csv_transcription"][code] = f"./{code}/1/2/native1.{code}"
    _, before = setup_root(tmp_path, [(f"{code}/1/2/native1.{code}", body, tarfile.REGTYPE),
        (f"{code}/1/2/native4.{code}", b"<html>error</html>", tarfile.REGTYPE)], asset_format=asset_format, works=works)
    report = pdmx_formats.acquire(tmp_path, asset_format=asset_format, cached_archive=True, batch_size=1)
    after = read_catalog(tmp_path)
    assert report["status"] == "complete" and report["catalog_committed"]
    assert report["counts"] == {"source_records": 4, "verified_records": 2, "failed_records": 1,
                                "missing_records": 1, "pending_records": 0, "unique_format_objects": 1}
    assert before["snapshot"] == after["snapshot"] and before["categories"] == after["categories"]
    for old, new in zip(before["works"], after["works"]):
        assert {k:v for k,v in old.items() if k != "assets"} == {k:v for k,v in new.items() if k != "assets"}
        assert [a for a in old["assets"] if a["format"] != asset_format] == [a for a in new["assets"] if a["format"] != asset_format]
    assets = [next(a for a in w["assets"] if a["format"] == asset_format) for w in after["works"]]
    assert [a["status"] for a in assets] == ["verified", "verified", "missing", "failed"]
    path = tmp_path / assets[0]["local_path"]
    pool = tmp_path / "sources/objects/sha256" / assets[0]["sha256"][:2] / (assets[0]["sha256"] + "." + code)
    assert path.read_bytes() == body and path.stat().st_ino == pool.stat().st_ino
    assert assets[0]["upstream_checksum_status"] == "not_supplied"
    assert assets[0]["archive_checksum_status"] == "md5_verified"
    assert report["live_source_requests"] == 0


@pytest.mark.parametrize("name,kind", [("../bad", tarfile.REGTYPE), ("/bad", tarfile.REGTYPE),
    ("x\\bad", tarfile.REGTYPE), ("x", tarfile.SYMTYPE), ("x", tarfile.LNKTYPE), ("x", tarfile.FIFOTYPE)])
def test_late_unsafe_unselected_tar_member_never_publishes(tmp_path, name, kind):
    _, before = setup_root(tmp_path, [("mxl/1/2/native1.mxl", mxl_bytes(), tarfile.REGTYPE), (name,b"x",kind)])
    with pytest.raises(ValueError):
        pdmx_formats.acquire(tmp_path, asset_format="MUSICXML")
    assert read_catalog(tmp_path) == before
    journal = json.loads((tmp_path / "sources/musescore/pdmx/mxl-extraction.json").read_text())
    assert journal["status"] == "failed_archive" and journal["catalog_committed"] is False


@pytest.mark.parametrize("entries", [
    [("META-INF/container.xml", CONTAINER), ("score.xml", SCORE), ("../evil", b"x")],
    [("META-INF/container.xml", CONTAINER), ("score.xml", SCORE), ("./score.xml", SCORE)],
    [("score.xml", SCORE)],
    [("META-INF/container.xml", CONTAINER.replace(b"score.xml", b"../score.xml")), ("score.xml", SCORE)],
    [("META-INF/container.xml", CONTAINER), ("score.xml", b"<html>wrong</html>")],
    [("META-INF/container.xml", CONTAINER), ("score.xml", b'<!DOCTYPE score-partwise [<!ENTITY x "bad">]><score-partwise/>')],
    [("META-INF/container.xml", CONTAINER), ("score.xml", b"<score-partwise/>")],
])
def test_mxl_container_members_score_and_entities_are_validated(tmp_path, entries):
    path = tmp_path / "score.mxl"
    path.write_bytes(mxl_bytes(entries))
    with pytest.raises(ValueError):
        pdmx_formats.validate_source_format(path, "MUSICXML")


@pytest.mark.parametrize("track", [b"\x00\x90\x3c", b"\x80\x80\x80\x80\x00\xff\x2f\x00",
    b"\x00\x3c\x40\x00\xff\x2f\x00", b"\x00\x90\x80\x40\x00\xff\x2f\x00",
    b"\x00\xff\x2f\x01\x00", b"\x00\xff\x2f\x00\x00", b"\x00\xc0\x18",
    b"\x00\xff\x51\x02\x01\x02\x00\xff\x2f\x00", b"\x00\xf1\x00\x00\xff\x2f\x00",
    b"\x00\xf0\x05\x01\x02\x00\xff\x2f\x00"])
def test_midi_truncated_invalid_vlq_running_status_event_and_end_are_rejected(tmp_path, track):
    path = tmp_path / "score.mid"
    path.write_bytes(midi_bytes(track))
    with pytest.raises(ValueError):
        pdmx_formats.validate_source_format(path, "MIDI")


@pytest.mark.parametrize("body", [midi_bytes() + b"garbage", midi_bytes(fmt=3), midi_bytes(division=0),
    midi_bytes(division=0x8001), b"MThd"+struct.pack(">IHHH",7,0,1,480)+b"x", midi_bytes()[:-1]])
def test_midi_header_division_track_lengths_and_trailing_bytes_are_rejected(tmp_path, body):
    path = tmp_path / "score.mid"
    path.write_bytes(body)
    with pytest.raises(ValueError):
        pdmx_formats.validate_source_format(path, "MIDI")


def test_ordinary_external_musicxml_doctype_and_valid_running_status_are_accepted(tmp_path):
    path = tmp_path / "score.mxl"
    path.write_bytes(mxl_bytes())
    assert pdmx_formats.validate_source_format(path, "MUSICXML")["score_root"] == "score-partwise"
    path = tmp_path / "score.mid"
    path.write_bytes(midi_bytes(b"\x00\x90\x3c\x40\x10\x3d\x40\x10\x3c\x00\x00\xff\x2f\x00"))
    assert pdmx_formats.validate_source_format(path, "MIDI")["tracks"] == 1


def test_archive_checksum_failure_keeps_catalog(tmp_path):
    archive, before = setup_root(tmp_path, [("mxl/1/2/native1.mxl", mxl_bytes(), tarfile.REGTYPE)])
    archive.write_bytes(archive.read_bytes()[:-1]+b"X")
    with pytest.raises(ValueError, match="checksum|integrity"):
        pdmx_formats.acquire(tmp_path, asset_format="MUSICXML")
    assert read_catalog(tmp_path) == before


def test_frozen_format_csv_binding_rejects_catalog_locator_edit(tmp_path):
    _, before = setup_root(tmp_path, [("mxl/1/2/native1.mxl", mxl_bytes(), tarfile.REGTYPE)])
    changed = copy.deepcopy(before)
    changed["works"][0]["metadata"]["pdmx_csv_transcription"]["mxl"] = "./mxl/1/2/different.mxl"
    path = tmp_path / "sources/musescore/catalog.json"
    path.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="binding"):
        pdmx_formats.acquire(tmp_path, asset_format="MUSICXML")
    assert read_catalog(tmp_path) == changed


def test_previous_pdf_journal_and_translation_bytes_are_preserved(tmp_path):
    setup_root(tmp_path, [("mxl/1/2/native1.mxl", mxl_bytes(), tarfile.REGTYPE)])
    previous = tmp_path / "sources/musescore/acquisition_report.json"
    previous.write_bytes(b'{"pdf":"previous effective receipt"}\n')
    journal = tmp_path / "sources/musescore/pdmx/pdf-extraction.json"
    journal.write_bytes(b'{"status":"complete"}\n')
    translations = tmp_path / "metadata/translations"
    translations.mkdir(parents=True)
    (translations / "review.json").write_bytes(b'{"native": "exact"}\n')
    pdmx_formats.acquire(tmp_path, asset_format="MUSICXML")
    assert previous.read_bytes() == b'{"pdf":"previous effective receipt"}\n'
    assert journal.read_bytes() == b'{"status":"complete"}\n'
    assert (translations / "review.json").read_bytes() == b'{"native": "exact"}\n'


def repin_archive(root, archive, code="mxl"):
    path = root / "config/musescore_pdmx_formats.json"
    config = json.loads(path.read_text())
    raw = archive.read_bytes()
    config["files"][code+".tar.gz"] = {"size":len(raw),"md5":hashlib.md5(raw).hexdigest()}
    path.write_text(json.dumps(config))


def test_unused_zip_member_crc_and_link_type_are_checked(tmp_path):
    path = tmp_path / "score.mxl"
    stream = io.BytesIO()
    with zipfile.ZipFile(stream,"w",zipfile.ZIP_STORED) as target:
        target.writestr("META-INF/container.xml",CONTAINER)
        target.writestr("score.xml",SCORE)
        target.writestr("unused.txt",b"unused-data-exact")
    raw = stream.getvalue().replace(b"unused-data-exact",b"broken-data-exact")
    path.write_bytes(raw)
    with pytest.raises(ValueError,match="corrupt|invalid"):
        pdmx_formats.validate_source_format(path,"MUSICXML")
    stream = io.BytesIO()
    with zipfile.ZipFile(stream,"w") as target:
        target.writestr("META-INF/container.xml",CONTAINER)
        target.writestr("score.xml",SCORE)
        info = zipfile.ZipInfo("link")
        info.create_system = 3
        info.external_attr = 0o120777 << 16
        target.writestr(info,"score.xml")
    path.write_bytes(stream.getvalue())
    with pytest.raises(ValueError,match="links|special"):
        pdmx_formats.validate_source_format(path,"MUSICXML")


def test_utf16_entity_declaration_is_rejected_and_normal_score_accepted(tmp_path):
    path = tmp_path / "score.mxl"
    body = '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE score-partwise [<!ENTITY x "bad">]><score-partwise>&x;</score-partwise>'.encode("utf-16")
    path.write_bytes(mxl_bytes([("META-INF/container.xml",CONTAINER),("score.xml",body)]))
    with pytest.raises(ValueError,match="parseable XML"):
        pdmx_formats.validate_source_format(path,"MUSICXML")
    body = SCORE.decode().replace('<?xml version="1.0"?>','<?xml version="1.0" encoding="UTF-16"?>').encode("utf-16")
    path.write_bytes(mxl_bytes([("META-INF/container.xml",CONTAINER),("score.xml",body)]))
    assert pdmx_formats.validate_source_format(path,"MUSICXML")["parts"] == 1


def test_musicxml_rootfile_may_have_no_filename_extension(tmp_path):
    path = tmp_path / "score.mxl"
    path.write_bytes(mxl_bytes([("META-INF/container.xml",CONTAINER.replace(b"score.xml",b"notation")),("notation",SCORE)]))
    assert pdmx_formats.validate_source_format(path,"MUSICXML")["score_member"] == "notation"


def test_repeat_fresh_verifies_and_keeps_immutable_inodes(tmp_path):
    setup_root(tmp_path,[("mxl/1/2/native1.mxl",mxl_bytes(),tarfile.REGTYPE)])
    first = pdmx_formats.acquire(tmp_path,asset_format="MUSICXML")
    asset = next(a for a in read_catalog(tmp_path)["works"][0]["assets"] if a["format"] == "MUSICXML")
    path = tmp_path / asset["local_path"]
    inode = path.stat().st_ino
    second = pdmx_formats.acquire(tmp_path,asset_format="MUSICXML")
    assert second["counts"] == first["counts"] and second["fresh_verified_prior_records"] == 1
    assert path.stat().st_ino == inode


def test_corrupted_immutable_format_object_is_never_replaced(tmp_path):
    setup_root(tmp_path,[("mxl/1/2/native1.mxl",mxl_bytes(),tarfile.REGTYPE)])
    pdmx_formats.acquire(tmp_path,asset_format="MUSICXML")
    asset = next(a for a in read_catalog(tmp_path)["works"][0]["assets"] if a["format"] == "MUSICXML")
    path = tmp_path / asset["local_path"]
    path.write_bytes(b"broken immutable")
    report = pdmx_formats.acquire(tmp_path,asset_format="MUSICXML")
    assert report["counts"]["failed_records"] == 1 and path.read_bytes() == b"broken immutable"


@pytest.mark.parametrize("corruption",["crc","tail","marker"])
def test_gzip_crc_tar_trailing_data_and_end_markers_block_commit(tmp_path,corruption):
    archive,before = setup_root(tmp_path,[("mxl/1/2/native1.mxl",mxl_bytes(),tarfile.REGTYPE)])
    raw = archive.read_bytes()
    if corruption == "crc":
        raw = raw[:-8]+bytes([raw[-8]^1])+raw[-7:]
    else:
        expanded = gzip.decompress(raw)
        if corruption == "tail":
            expanded += b"nonzero"
        else:
            header = tarfile.TarInfo("mxl/1/2/native1.mxl")
            header.size = len(mxl_bytes())
            end = 512+((header.size+511)//512)*512
            expanded = expanded[:end+512]  # Only first zero end marker survives.
        raw = gzip.compress(expanded)
    archive.write_bytes(raw)
    repin_archive(tmp_path,archive)
    with pytest.raises((ValueError,gzip.BadGzipFile),match="CRC|nonzero|marker|truncated"):
        pdmx_formats.acquire(tmp_path,asset_format="MUSICXML")
    assert read_catalog(tmp_path) == before


def test_interrupted_extraction_resumes_verified_staged_member(tmp_path,monkeypatch):
    setup_root(tmp_path,[("mxl/1/2/native1.mxl",mxl_bytes(),tarfile.REGTYPE),
                        ("mxl/1/2/native2.mxl",mxl_bytes(),tarfile.REGTYPE)],works=[work("1"),work("2")])
    original = pdmx_formats.validate_source_format
    calls = 0
    def interrupt(path,asset_format):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise KeyboardInterrupt("test interruption")
        return original(path,asset_format)
    monkeypatch.setattr(pdmx_formats,"validate_source_format",interrupt)
    with pytest.raises(KeyboardInterrupt):
        pdmx_formats.acquire(tmp_path,asset_format="MUSICXML",batch_size=1)
    assert all(a["status"] == "metadata_only" for w in read_catalog(tmp_path)["works"] for a in w["assets"])
    monkeypatch.setattr(pdmx_formats,"validate_source_format",original)
    report = pdmx_formats.acquire(tmp_path,asset_format="MUSICXML",batch_size=1)
    assert report["counts"]["verified_records"] == 2
    assert report["fresh_verified_staged_members"] == 1
    assert not list((tmp_path / "sources/musescore/partials").glob("*.part"))


def test_pending_source_guard_rejects_title_or_pdf_changes(tmp_path):
    setup_root(tmp_path,[("mxl/1/2/native1.mxl",mxl_bytes(),tarfile.REGTYPE)])
    pdmx_formats.initialize_pending_journal(tmp_path,asset_format="MUSICXML")
    changed = read_catalog(tmp_path)
    changed["works"][0]["title_en"] = "changed source"
    (tmp_path / "sources/musescore/catalog.json").write_text(json.dumps(changed))
    with pytest.raises(ValueError,match="stale|guard"):
        pdmx_formats.acquire(tmp_path,asset_format="MUSICXML")
    assert read_catalog(tmp_path) == changed


def test_source_lock_blocks_parallel_pdf_or_format_writer(tmp_path):
    setup_root(tmp_path,[("mxl/1/2/native1.mxl",mxl_bytes(),tarfile.REGTYPE)])
    with pdmx_formats.source_lock(tmp_path / "sources/musescore/.pdf-acquisition.lock"):
        with pytest.raises(RuntimeError,match="lock"):
            pdmx_formats.acquire(tmp_path,asset_format="MUSICXML")


def test_native_locator_and_approved_record_count_are_guarded(tmp_path):
    setup_root(tmp_path,[("mxl/1/2/native1.mxl",mxl_bytes(),tarfile.REGTYPE)])
    path = tmp_path / "config/musescore_pdmx_formats.json"
    config = json.loads(path.read_text())
    config["expected_records"] = 2
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError,match="record count"):
        pdmx_formats.acquire(tmp_path,asset_format="MUSICXML")


def test_midi_multitrack_and_smpte_are_valid_and_undeclared_track_rejected(tmp_path):
    path = tmp_path / "score.mid"
    path.write_bytes(midi_bytes(fmt=1,division=0xe728,tracks=[b"\x00\xff\x2f\x00",b"\x00\xff\x2f\x00"]))
    assert pdmx_formats.validate_source_format(path,"MIDI")["tracks"] == 2
    path.write_bytes(midi_bytes(fmt=0,tracks=[b"\x00\xff\x2f\x00",b"\x00\xff\x2f\x00"]))
    with pytest.raises(ValueError,match="track count"):
        pdmx_formats.validate_source_format(path,"MIDI")


@pytest.mark.parametrize("prefix,suffix",[(b"<html>error</html>",b""),(b"",b"<html>junk</html>")])
def test_mxl_zip_prepended_and_trailing_payload_are_rejected(tmp_path,prefix,suffix):
    path = tmp_path / "score.mxl"
    path.write_bytes(prefix+mxl_bytes()+suffix)
    with pytest.raises(ValueError,match="payload|header"):
        pdmx_formats.validate_source_format(path,"MUSICXML")


def test_mxl_optional_media_type_and_secondary_pdf_are_valid(tmp_path):
    path = tmp_path / "score.mxl"
    container = CONTAINER.replace(b' media-type="application/vnd.recordare.musicxml+xml"',b"")
    container = container.replace(b"</rootfiles>",b'<rootfile full-path="score.pdf" media-type="application/pdf"/></rootfiles>')
    path.write_bytes(mxl_bytes([("META-INF/container.xml",container),("score.xml",SCORE),("score.pdf",b"opaque secondary artifact")]))
    assert pdmx_formats.validate_source_format(path,"MUSICXML")["score_root"] == "score-partwise"


def test_zip_comment_is_valid_and_first_pdf_root_is_rejected(tmp_path):
    path = tmp_path / "score.mxl"
    stream = io.BytesIO(mxl_bytes())
    with zipfile.ZipFile(stream,"a") as archive:
        archive.comment = b"legitimate ZIP comment"
    path.write_bytes(stream.getvalue())
    assert pdmx_formats.validate_source_format(path,"MUSICXML")["parts"] == 1
    container = CONTAINER.replace(b"<rootfiles>",b'<rootfiles><rootfile full-path="score.pdf" media-type="application/pdf"/>')
    path.write_bytes(mxl_bytes([("META-INF/container.xml",container),("score.xml",SCORE),("score.pdf",b"artifact")]))
    with pytest.raises(ValueError,match="primary"):
        pdmx_formats.validate_source_format(path,"MUSICXML")


@pytest.mark.parametrize("code,suffix,status",[("mid","range-plan","stopped_access"),("pdf","extraction","stopped_access"),
                                               ("mxl","range-plan","interrupted")])
def test_refusal_on_any_format_prevents_a_new_publication_url(tmp_path,code,suffix,status):
    setup_root(tmp_path,[("mxl/1/2/native1.mxl",mxl_bytes(),tarfile.REGTYPE)])
    path = tmp_path / f"sources/musescore/pdmx/{code}-{suffix}.json"
    path.write_text(json.dumps({"status":status,"error":"Zenodo HTTP 403"}))
    with pytest.raises(pdmx_formats.AccessStopped,match="refused"):
        pdmx_formats._refuse_stopped_source(tmp_path)


def test_malformed_unrelated_journal_is_reported_without_false_archive_failure(tmp_path):
    setup_root(tmp_path,[("mxl/1/2/native1.mxl",mxl_bytes(),tarfile.REGTYPE)])
    (tmp_path / "sources/musescore/pdmx/mid-extraction.json").write_bytes(b"broken JSON")
    report = pdmx_formats.acquire(tmp_path,asset_format="MUSICXML")
    assert report["status"] == "complete" and report["catalog_committed"]
    summary = json.loads((tmp_path / "sources/musescore/formats-acquisition-report.json").read_text())
    assert summary["formats"]["MIDI"]["status"] == "invalid_journal"
