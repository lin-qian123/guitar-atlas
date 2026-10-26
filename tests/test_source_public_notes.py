from __future__ import annotations

import copy

import pytest

from catalog_sources import project_source_public_notes


def test_maikstrings_projects_real_credit_and_compact_rights_facts_without_mutation() -> None:
    native = {
        "id": "maikstrings:pdf:example",
        "composer_en": "Matteo Carcassi (1792–1853)",
        "metadata": {
            "source_attribution_note": ".nt-c source credit is retained verbatim as composer_en because filters were checked.",
            "source_credit_line": "Matteo Carcassi (1792–1853)",
            "engraver_credit": "Maikstrings, per source directory page",
            "contributors": "Maikstrings (engraving, directory-level source claim)",
            "license_note": (
                "The source explicitly permits free individual download, printing, teaching use, and group copies. "
                "This supports acquisition into the user's private offline cache. The directory also credits "
                "Maikstrings with the engraving and the footer states all rights reserved; public digital "
                "redistribution of the PDF is not established. Do not publish, mirror, or expose the PDF."
            ),
        },
    }
    details = {
        "source_attribution_note": native["metadata"]["source_attribution_note"],
        "contributors": native["metadata"]["contributors"],
        "license": "Public Domain (source directory claim; modern engraving reuse scope unclear)",
        "license_note": native["metadata"]["license_note"],
    }
    native_before = copy.deepcopy(native)
    details_before = copy.deepcopy(details)

    public = project_source_public_notes("maikstrings", native, details)

    assert public is not details
    assert native == native_before
    assert details == details_before
    assert "source_attribution_note" not in public
    assert public["contributors"] == "Maikstrings (engraving)"
    assert public["license"] == details["license"]
    rights = public["license_note"]
    for factual_claim in ("Public Domain", "现代刻版", "个人下载", "打印", "教学", "群体复印",
                          "All rights reserved", "公开数字再分发", "未获确认"):
        assert factual_claim.casefold() in rights.casefold()
    for internal_phrase in (".nt-c", "offline cache", "Do not publish", "directory-level source claim",
                            "acquisition into", "engraver_credit"):
        assert internal_phrase.casefold() not in rights.casefold() + public["contributors"].casefold()


def test_yawnoc_hides_crawl_and_attribution_processing_notes_but_keeps_rights_and_unknown_count() -> None:
    native = {
        "id": "yawnoc:dowland-fantasia-7",
        "metadata": {
            "availability": "PDF release-download access blocked by robots before request; no alternate route was attempted.",
            "source_attribution_note": "Composer and arranger fields transcribed from the LilyPond header at the frozen tag commit.",
            "license_note": (
                "At this release tag commit, README says the original compositions are public domain and the author's "
                "edits/arrangements are released under CC0; the matching LICENSE is CC0 1.0. Composition lineage is not independently audited."
            ),
        },
    }
    details = {
        "availability": native["metadata"]["availability"],
        "source_attribution_note": native["metadata"]["source_attribution_note"],
        "license": "CC0-1.0 (score edition); Public Domain composition (repository claim)",
        "license_note": native["metadata"]["license_note"],
        "description": "The fixed LilyPond source supports the guitar family; performer count is not stated.",
        "instrumentation": "guitar",
    }
    native_before = copy.deepcopy(native)
    details_before = copy.deepcopy(details)

    public = project_source_public_notes("yawnoc", native, details)

    assert "availability" not in public
    assert "source_attribution_note" not in public
    assert public["license"] == details["license"]
    assert "原作属公有领域" in public["license_note"]
    assert "CC0" in public["license_note"] and "CC0 1.0" in public["license_note"]
    assert public["description"] == details["description"]
    assert public["instrumentation"] == "guitar"
    for internal_phrase in ("robots", "frozen tag", "transcribed", "not independently audited", "private"):
        assert internal_phrase.casefold() not in str(public).casefold()
    assert native == native_before
    assert details == details_before


def test_other_sources_keep_their_existing_projection_byte_for_byte() -> None:
    for source_id in ("classclef", "csun", "guitarclassroom", "derekhasted"):
        native = {"id": f"{source_id}:example", "metadata": {}}
        details = {
            "source_attribution_note": "Source note remains as projected for this source.",
            "license_note": "Existing source rights note.",
            "availability": "Existing availability note.",
            "description": "Guitar scope; performer count is unknown.",
        }
        before = copy.deepcopy(details)
        assert project_source_public_notes(source_id, native, details) == before
        assert details == before


def test_unreviewed_maikstrings_rights_note_fails_closed() -> None:
    native = {"id": "maikstrings:pdf:example", "metadata": {"license_note": "Changed rights text."}}
    with pytest.raises(ValueError, match="unreviewed Maikstrings public license note"):
        project_source_public_notes("maikstrings", native, {"license_note": "Changed rights text."})
