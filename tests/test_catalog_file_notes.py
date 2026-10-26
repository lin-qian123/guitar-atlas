import copy
import json
from pathlib import Path

import pytest

import catalog_file_notes
from catalog_file_notes import (APPLIED_FILE_CLASSIFICATIONS, APPLIED_FILE_NOTE_IDS,
                                REVIEW_PATH, apply_file_notes, digest)


ROOT = Path(__file__).resolve().parents[1]


def _native(source_id: str, work: dict) -> dict:
    return {"schema_version": 1, "source_id": source_id, "categories": [], "works": [work]}


def _work(tmp_path: Path, *, identity="demo:one", title="Original title",
          composer="Composer", instrumentation="guitar", bytes_=b"%PDF-fixture") -> dict:
    relative = "sources/demo/one.pdf"
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes_)
    import hashlib
    sha = hashlib.sha256(bytes_).hexdigest()
    return {
        "id": identity, "title_en": title, "composer_en": composer,
        "category_ids": ["guitar"], "title_aliases": ["Existing alias"],
        "assets": [{"format": "PDF", "status": "verified", "local_path": relative,
                    "sha256": sha, "size": len(bytes_)}],
        "metadata": {"instrumentation": instrumentation, "description": "Native description."},
    }


def _ensure_packet(root: Path, packet_name="sources/source-expansion/new-pdf-evidence.json.gz") -> tuple[str, int]:
    import hashlib
    relative = packet_name
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = b"test evidence packet\n"
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest(), len(payload)


def _entry(root: Path, work: dict, *, patch=None, path=None,
           packet_name="sources/source-expansion/new-pdf-evidence.json.gz", page=1, actual_pages=1) -> dict:
    import hashlib
    file_path = root / work["assets"][0]["local_path"]
    data = file_path.read_bytes()
    packet_sha, packet_size = _ensure_packet(root, packet_name)
    entry = {
        "native_record_sha256": digest(work),
        "native_identity": {"id": work["id"], "title_en": work["title_en"],
                            "composer_en": work["composer_en"],
                            "instrumentation": work["metadata"]["instrumentation"]},
        "asset": {"local_path": path or work["assets"][0]["local_path"],
                  "sha256": hashlib.sha256(data).hexdigest(), "size": len(data),
                  "format": "PDF", "status": "verified"},
        "evidence": {"packet": packet_name,
                     "packet_sha256": packet_sha, "packet_size": packet_size,
                     "page": page, "actual_pages": actual_pages,
                     "printed_excerpt": "Printed title and instrument labels"},
        "public": {"description_note": "Checked against the printed score page.",
                    "title_aliases": ["Printed title"]},
    }
    entry["public"].update(patch or {})
    return entry


def _write_review(root: Path, entries: dict) -> None:
    path = root / REVIEW_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": 1, "status": "complete",
                                "entries": entries}, ensure_ascii=False), encoding="utf-8")


def test_real_reviewed_records_apply_as_source_preserving_runtime_overlay(tmp_path):
    # The four review decisions are versioned, public inputs. Rebuild only their
    # exact native identities and byte guards in an isolated tree so clean CI
    # does not depend on ignored private source catalogs or score objects.
    import gzip
    import hashlib

    approved = json.loads((ROOT / REVIEW_PATH).read_text(encoding="utf-8"))
    packet_guards = {}
    for packet_name in {entry["evidence"]["packet"] for entry in approved["entries"].values()}:
        packet = gzip.compress(("independent fixture for " + packet_name + "\n").encode(), mtime=0)
        packet_path = tmp_path / packet_name
        packet_path.parent.mkdir(parents=True, exist_ok=True)
        packet_path.write_bytes(packet)
        packet_guards[packet_name] = (hashlib.sha256(packet).hexdigest(), len(packet))
    review_entries = {}
    catalogs = {}
    native_snapshots = {}
    for identity, approved_entry in approved["entries"].items():
        native_identity = approved_entry["native_identity"]
        source_id = identity.split(":", 1)[0]
        relative = f"sources/{source_id}/test-fixtures/{hashlib.sha256(identity.encode()).hexdigest()}.pdf"
        pdf = b"%PDF-1.4\nfixture bytes for " + identity.encode("utf-8") + b"\n%%EOF\n"
        pdf_path = tmp_path / relative
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_bytes(pdf)
        pdf_sha = hashlib.sha256(pdf).hexdigest()
        work = {
            "id": identity,
            "title_en": native_identity["title_en"],
            "composer_en": native_identity["composer_en"],
            "category_ids": ["guitar"],
            "title_aliases": [],
            "assets": [{"format": "PDF", "status": "verified", "local_path": relative,
                        "sha256": pdf_sha, "size": len(pdf)}],
            "metadata": {"instrumentation": native_identity["instrumentation"],
                         "description": "Native description.", "arranger": None},
        }
        entry = copy.deepcopy(approved_entry)
        entry["native_record_sha256"] = digest(work)
        entry["asset"] = {"local_path": relative, "sha256": pdf_sha,
                          "size": len(pdf), "format": "PDF", "status": "verified"}
        entry["evidence"]["packet_sha256"], entry["evidence"]["packet_size"] = packet_guards[
            entry["evidence"]["packet"]]
        review_entries[identity] = entry
        catalogs.setdefault(source_id, {"schema_version": 1, "source_id": source_id,
                                         "categories": [], "works": []})
        catalogs[source_id]["works"].append(work)
    _write_review(tmp_path, review_entries)

    results = {}
    classifications_by_source = {}
    for source_id, native in catalogs.items():
        native_snapshots[source_id] = copy.deepcopy(native)
        result = apply_file_notes(tmp_path, copy.deepcopy(native), native)
        assert APPLIED_FILE_NOTE_IDS in result
        assert APPLIED_FILE_CLASSIFICATIONS in result
        classifications_by_source[source_id] = result[APPLIED_FILE_CLASSIFICATIONS]
        results.update({work["id"]: work for work in result["works"]})
        assert native == native_snapshots[source_id]

    sor = results["guitarclassroom:pdf:d929010899e2291f34810fc4fe6f7af4e65aa0a3f527b01ae885090b4fd6c7e5"]
    assert sor["title_en"] == "Study No. 19, op. 60 (Carulli)"
    assert sor["composer_en"] == "Carulli"
    assert sor["metadata"]["file_title"] == "Study No. 19"
    assert "Fernando Sor" in sor["title_aliases"]
    assert "Fernando Sor" in sor["metadata"]["file_identity_note"]

    carneirunho = results["guitarclassroom:pdf:798e2fd5bd8ee3e7d8414fd8e0497b34a5a21a6a9d18b8fe71bc87cbf7150aac"]
    assert carneirunho["title_en"] == "Carneirunho"
    assert "Carneirinho" in carneirunho["title_aliases"]
    assert "不据谱表标签推定演奏人数" in carneirunho["metadata"]["description"]
    assert "instrumentation" not in carneirunho["metadata"] or carneirunho["metadata"]["instrumentation"] == "guitar ensemble"

    adelita = results[next(identity for identity in results if identity.startswith("maikstrings:pdf:bbdea8"))]
    assert adelita["metadata"]["instrumentation"] == "2 guitars"
    assert adelita["metadata"]["arranger"] is None
    assert "双吉他" in adelita["metadata"]["description"]
    assert classifications_by_source["guitarclassroom"] == {}
    classifications = classifications_by_source["maikstrings"]
    assert classifications == {
        "maikstrings:pdf:bbdea8bba406cb3eb62392f3f784b05f57495ee1819e19096ded38a7fe4d114c": {
            "topic_id": "duo", "basis": "reviewed_score_evidence",
            "instrumentation": "双吉他编配（据谱面明确标注）", "player_count": 2,
            "note": adelita["metadata"]["description"].split("\n\n")[-1],
        }
    }

    csun = results["csun:1071"]
    assert csun["metadata"]["instrumentation"] == "one or two guitars"
    assert csun["metadata"]["source_instrumentation"] == "2 guitars"
    assert csun["title_en"] == "Freischutz"
    assert "人数" in csun["metadata"]["description"]
    anthology = results["csun:1024"]
    assert anthology["metadata"]["instrumentation"] == "guitar"
    assert "声乐与吉他" in anthology["metadata"]["description"]
    assert "Guitar" in anthology["metadata"]["description"]
    assert classifications_by_source["csun"] == {
        "csun:1071": {
            "topic_id": "guitar_unspecified", "basis": "reviewed_score_evidence",
            "instrumentation": "吉他；谱页列明一把或两把的选项，具体演奏人数未定",
            "player_count": None,
            "note": csun["metadata"]["description"].split("\n\n")[-1],
        },
        "csun:1024": {
            "topic_id": "other_instrumentation", "basis": "reviewed_score_evidence",
            "instrumentation": "声乐与吉他（合集内已核见合唱声部及吉他；其他曲目未逐页核实）",
            "player_count": None,
            "note": anthology["metadata"]["description"].split("\n\n")[-1],
        },
    }

    recuerdos = results[next(identity for identity in results if identity.startswith("maikstrings:pdf:0a60f"))]
    assert recuerdos["composer_en"] == "Francisco Tárrega (1852–1909)"
    assert recuerdos["metadata"]["arranger"] is None
    assert "Ł. Slawianowska" in recuerdos["metadata"]["description"]


def test_overlay_copies_effective_catalog_and_leaves_out_of_scope_source_unchanged(tmp_path):
    native = _native("unrelated", {"id": "unrelated:1", "title_en": "T", "composer_en": "C"})
    effective = copy.deepcopy(native)
    result = apply_file_notes(tmp_path, effective, native)
    assert result is effective
    assert result == native


def test_target_source_requires_review_asset(tmp_path):
    native = _native("guitarclassroom", {"id": "guitarclassroom:one"})
    with pytest.raises(ValueError, match="review asset"):
        apply_file_notes(tmp_path, copy.deepcopy(native), native)


def test_guards_native_digest_and_asset_bytes(tmp_path, monkeypatch):
    work = _work(tmp_path, identity="guitarclassroom:one")
    monkeypatch.setitem(catalog_file_notes.REVIEWED_IDS_BY_SOURCE,
                        "guitarclassroom", frozenset({work["id"]}))
    native = _native("guitarclassroom", work)
    effective = copy.deepcopy(native)
    _write_review(tmp_path, {work["id"]: _entry(tmp_path, work)})
    result = apply_file_notes(tmp_path, effective, native)
    assert result is not effective
    assert effective["works"][0]["metadata"]["description"] == "Native description."
    assert result["works"][0]["metadata"]["description"].startswith("Native description.")
    assert result["works"][0]["title_aliases"] == ["Existing alias", "Printed title"]

    changed = copy.deepcopy(native)
    changed["works"][0]["composer_en"] = "Changed composer"
    with pytest.raises(ValueError, match="native record changed"):
        apply_file_notes(tmp_path, copy.deepcopy(changed), changed)

    (tmp_path / work["assets"][0]["local_path"]).write_bytes(b"changed bytes")
    with pytest.raises(ValueError, match="asset"):
        apply_file_notes(tmp_path, copy.deepcopy(native), native)


def test_rejects_unsafe_paths_and_forged_markers(tmp_path, monkeypatch):
    work = _work(tmp_path, identity="guitarclassroom:one")
    monkeypatch.setitem(catalog_file_notes.REVIEWED_IDS_BY_SOURCE,
                        "guitarclassroom", frozenset({work["id"]}))
    native = _native("guitarclassroom", work)
    _write_review(tmp_path, {work["id"]: _entry(tmp_path, work, path="../outside.pdf")})
    with pytest.raises(ValueError, match="unsafe reviewed asset path"):
        apply_file_notes(tmp_path, copy.deepcopy(native), native)

    forged = copy.deepcopy(native)
    forged[APPLIED_FILE_NOTE_IDS] = [work["id"]]
    with pytest.raises(ValueError, match="cannot forge"):
        apply_file_notes(tmp_path, copy.deepcopy(forged), forged)

    forged = copy.deepcopy(native)
    forged[APPLIED_FILE_CLASSIFICATIONS] = {work["id"]: {"topic_id": "duo"}}
    with pytest.raises(ValueError, match="cannot forge"):
        apply_file_notes(tmp_path, copy.deepcopy(forged), forged)

    forged_effective = copy.deepcopy(native)
    forged_effective[APPLIED_FILE_CLASSIFICATIONS] = {}
    with pytest.raises(ValueError, match="already contains"):
        apply_file_notes(tmp_path, forged_effective, native)


def test_instrumentation_override_is_exactly_scoped(tmp_path, monkeypatch):
    work = _work(tmp_path, identity="maikstrings:pdf:bbdea8bba406cb3eb62392f3f784b05f57495ee1819e19096ded38a7fe4d114c")
    monkeypatch.setitem(catalog_file_notes.REVIEWED_IDS_BY_SOURCE,
                        "maikstrings", frozenset({work["id"]}))
    native = _native("maikstrings", work)
    patch = {"instrumentation": "2 guitars"}
    _write_review(tmp_path, {work["id"]: _entry(tmp_path, work, patch=patch)})
    result = apply_file_notes(tmp_path, copy.deepcopy(native), native)
    assert result["works"][0]["metadata"]["instrumentation"] == "2 guitars"

    other = _work(tmp_path, identity="maikstrings:pdf:not-the-reviewed-identity")
    native_other = _native("maikstrings", other)
    monkeypatch.setitem(catalog_file_notes.REVIEWED_IDS_BY_SOURCE,
                        "maikstrings", frozenset({other["id"]}))
    _write_review(tmp_path, {other["id"]: _entry(tmp_path, other, patch=patch)})
    with pytest.raises(ValueError, match="unsupported file instrumentation"):
        apply_file_notes(tmp_path, copy.deepcopy(native_other), native_other)

    option_id = "csun:1071"
    option_work = _work(tmp_path, identity=option_id, instrumentation="2 guitars")
    option_native = _native("csun", option_work)
    monkeypatch.setitem(catalog_file_notes.REVIEWED_IDS_BY_SOURCE, "csun", frozenset({option_id}))
    option_patch = {"instrumentation": "one or two guitars"}
    _write_review(tmp_path, {option_id: _entry(
        tmp_path, option_work, patch=option_patch,
        packet_name="sources/source-expansion/csun-score-samples.json", page=2, actual_pages=8)})
    option_result = apply_file_notes(tmp_path, copy.deepcopy(option_native), option_native)
    assert option_result["works"][0]["metadata"]["instrumentation"] == "one or two guitars"
    assert option_result["works"][0]["metadata"]["source_instrumentation"] == "2 guitars"
    assert option_result[APPLIED_FILE_CLASSIFICATIONS][option_id]["topic_id"] == "guitar_unspecified"
    assert option_result[APPLIED_FILE_CLASSIFICATIONS][option_id]["basis"] == "reviewed_score_evidence"
    assert option_result[APPLIED_FILE_CLASSIFICATIONS][option_id]["player_count"] is None

    # The fixed score classification is valid only when its exact reviewed
    # instrumentation option is present. Omitting the public patch must fail
    # closed instead of silently applying the classification anyway.
    _write_review(tmp_path, {option_id: _entry(
        tmp_path, option_work, patch={"description_note": "Reviewed note.",
                                      "title_aliases": ["Reviewed title"]},
        packet_name="sources/source-expansion/csun-score-samples.json", page=2, actual_pages=8)})
    with pytest.raises(ValueError, match="file instrumentation note is missing or differs"):
        apply_file_notes(tmp_path, copy.deepcopy(option_native), option_native)

    other_option = _work(tmp_path, identity="csun:999", instrumentation="2 guitars")
    other_native = _native("csun", other_option)
    monkeypatch.setitem(catalog_file_notes.REVIEWED_IDS_BY_SOURCE,
                        "csun", frozenset({other_option["id"]}))
    _write_review(tmp_path, {other_option["id"]: _entry(tmp_path, other_option, patch=option_patch)})
    with pytest.raises(ValueError, match="unsupported file instrumentation"):
        apply_file_notes(tmp_path, copy.deepcopy(other_native), other_native)


def test_target_source_requires_packet_and_rejects_stale_packet_guard(tmp_path, monkeypatch):
    work = _work(tmp_path, identity="guitarclassroom:one")
    monkeypatch.setitem(catalog_file_notes.REVIEWED_IDS_BY_SOURCE,
                        "guitarclassroom", frozenset({work["id"]}))
    native = _native("guitarclassroom", work)
    _write_review(tmp_path, {work["id"]: _entry(tmp_path, work)})
    packet = tmp_path / "sources/source-expansion/new-pdf-evidence.json.gz"
    packet.write_bytes(b"different packet bytes")
    with pytest.raises(ValueError, match="evidence packet"):
        apply_file_notes(tmp_path, copy.deepcopy(native), native)
