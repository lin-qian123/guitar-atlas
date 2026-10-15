"""Independent full-archive scope, native identity and byte-boundary checks."""
import hashlib
import io
import json
import tarfile
from copy import deepcopy

import pytest

from audit_pdmx_metadata_scope import (
    file_guard, identity_license_checks, scan_metadata_archive, source_evidence,
)


def fixture():
    url = "https://musescore.com/user/12/scores/123"
    score = {"id": 123, "title": "Study NA 4", "composer_name": "Example", "url": url,
             "user": {"id": 12, "url": "https://musescore.com/example"},
             "instruments": [{"name": "Guitarra clásica"}], "parts_names": ["Guitarra"],
             "instrumentations": [], "license": "publicdomain"}
    metadata = {"data": {"score": score, "license_url": "https://creativecommons.org/publicdomain/mark/1.0/"},
                "score": {"id": 123, "title": "Study NA 4", "url": url, "user": {"id": 12}}, "status_code": 200}
    row = {"tracks": "0", "n_tracks": "1", "title": "Study NA 4", "composer_name": "Example",
           "license": "publicdomain", "license_url": "https://creativecommons.org/publicdomain/mark/1.0/",
           "license_conflict": "False", "subset:no_license_conflict": "True", "has_lyrics": "False", "n_lyrics": "0"}
    return metadata, row


def archive(tmp_path, members):
    path = tmp_path / "metadata.tar.gz"
    with tarfile.open(path, "w:gz") as out:
        for name, content, kind in members:
            info = tarfile.TarInfo(name)
            info.type = kind
            info.size = len(content) if kind == tarfile.REGTYPE else 0
            out.addfile(info, io.BytesIO(content) if kind == tarfile.REGTYPE else None)
    return path


def test_all_members_parsed_including_non_guitar(tmp_path):
    path = archive(tmp_path, [("metadata/1/1.json", b'{"piano":true}', tarfile.REGTYPE),
                              ("metadata/2/2.json", b'{"guitar":true}', tarfile.REGTYPE)])
    visited = []
    result = scan_metadata_archive(path, lambda *args: visited.append(args))
    assert result["counts"]["unique_metadata_records"] == 2
    assert [x[0] for x in visited] == ["1", "2"]
    assert visited[0][3] == {"piano": True}


@pytest.mark.parametrize("name,kind", [("../metadata/1/1.json", tarfile.REGTYPE),
    ("/metadata/1/1.json", tarfile.REGTYPE), ("metadata/1/1.json", tarfile.SYMTYPE),
    ("other/1.json", tarfile.REGTYPE)])
def test_unsafe_or_unexpected_members_fail_closed(tmp_path, name, kind):
    path = archive(tmp_path, [(name, b"{}", kind)])
    with pytest.raises(ValueError): scan_metadata_archive(path, lambda *args: None)


def test_equal_duplicates_count_but_conflicting_duplicates_fail(tmp_path):
    path = archive(tmp_path, [("metadata/1/1.json", b"{}", tarfile.REGTYPE)] * 2)
    assert scan_metadata_archive(path, lambda *args: None)["counts"]["equal_duplicate_members"] == 1
    path = archive(tmp_path, [("metadata/1/1.json", b"{}", tarfile.REGTYPE),
                              ("metadata/1/1.json", b'{"changed":1}', tarfile.REGTYPE)])
    with pytest.raises(ValueError, match="duplicate"): scan_metadata_archive(path, lambda *args: None)


def test_duplicate_json_key_and_expansion_limit_fail(tmp_path):
    path = archive(tmp_path, [("metadata/1/1.json", b'{"id":1,"id":2}', tarfile.REGTYPE)])
    with pytest.raises(ValueError, match="duplicate JSON"): scan_metadata_archive(path, lambda *args: None)
    path = archive(tmp_path, [("metadata/1/1.json", b'{"large":"content"}', tarfile.REGTYPE)])
    with pytest.raises(ValueError, match="size limit"): scan_metadata_archive(path, lambda *args: None, max_member_bytes=2)


@pytest.mark.parametrize("label", ["Guitarra clásica", "Chitarra", "Violon et guitare", "Violão", "吉他", "Гитара", "ギター"])
def test_localized_instrument_declarations_find_gm_gate_omissions(label):
    metadata, row = fixture()
    metadata["data"]["score"]["instruments"] = [{"name": label}]
    evidence = source_evidence(metadata, row)
    assert evidence["basis"] == "explicit_source_instrument"
    assert not evidence["old_acoustic_gm_gate"]


def test_title_only_and_playback_candidates_do_not_become_instrument_evidence():
    metadata, row = fixture()
    metadata["data"]["score"].update(instruments=[{"name": "Piano"}], parts_names=["Piano"], title="Guitar concerto")
    assert source_evidence(metadata, row)["basis"] == "title_only"
    row.update(tracks="29", n_tracks="1")
    assert source_evidence(metadata, row)["basis"] == "gm_guitar_candidate"
    assert not source_evidence(metadata, row)["guitar_labels"]


def test_electric_voice_and_bass_remain_separate_flags_not_acoustic_scope():
    metadata, row = fixture()
    metadata["data"]["score"].update(instruments=[{"name": "Electric Guitar"}, {"name": "Bass Guitar"}, {"name": "Voice"}], parts_names=[])
    flags = source_evidence(metadata, row)["scope_flags"]
    assert {"electric_or_synth", "bass_guitar_or_ambiguous_bass", "voice_or_chorus"} <= set(flags)
    assert source_evidence(metadata, row)["basis"] == "explicit_source_instrument"


def test_tenor_sax_and_alto_flute_are_not_voices():
    metadata, row = fixture()
    metadata["data"]["score"]["parts_names"] = ["Guitar", "Tenor Saxophone", "Alto Flute"]
    assert "voice_or_chorus" not in source_evidence(metadata, row)["scope_flags"]


def test_identity_and_license_disagreement_retained_independently():
    metadata, row = fixture()
    assert identity_license_checks(metadata, row, "123") == {"identity_issues": [], "license_issues": []}
    changed = deepcopy(metadata)
    changed["score"]["id"] = 99
    row["license_conflict"] = "True"
    checks = identity_license_checks(changed, row, "123")
    assert "native_id_mismatch" in checks["identity_issues"]
    assert "license_conflict" in checks["license_issues"]


def test_input_checksum_guard_rejects_wrong_bytes(tmp_path):
    path = tmp_path / "input"
    raw = b"metadata"
    path.write_bytes(raw)
    md5 = hashlib.md5(raw).hexdigest()
    receipt = {"bytes": len(raw), "upstream_checksum": "md5:" + md5,
               "sha256": hashlib.sha256(raw).hexdigest(), "upstream_checksum_verified": True}
    assert file_guard(path, expected_size=len(raw), expected_md5=md5, receipt=receipt)["bytes"] == len(raw)
    path.write_bytes(b"wrong___")
    with pytest.raises(ValueError, match="checksum"): file_guard(path, expected_size=len(raw), expected_md5=md5, receipt=receipt)
