from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from source_adapters import open_guitar


def yawnoc_release(tag="lagrima-v1.2.2", slug="lagrima", assets=None):
    return {
        "id": 123,
        "tag_name": tag,
        "name": "Lágrima v1.2.2",
        "html_url": f"https://github.com/yawnoc/guitar/releases/tag/{tag}",
        "url": f"https://api.github.com/repos/yawnoc/guitar/releases/123",
        "draft": False,
        "prerelease": False,
        "published_at": "2025-01-01T00:00:00Z",
        "assets": assets or [{
            "id": 900,
            "name": f"{slug}-v1.2.2.pdf",
            "browser_download_url": f"https://github.com/yawnoc/guitar/releases/download/{tag}/{slug}-v1.2.2.pdf",
            "content_type": "application/pdf",
            "size": 1234,
            "state": "uploaded",
            "digest": None,
            "url": "https://api.github.com/repos/yawnoc/guitar/releases/assets/900",
        }],
    }


def yawnoc_evidence(title="Lágrima", composer="Francisco Tárrega", lilypond_text=None):
    lilypond_text = lilypond_text or f'''\\header {{
  title = "{title}"
  composer = "{composer}"
  arranger = "Conway (edits)"
}}
\\new Staff \\with {{
  midiInstrument = #"acoustic guitar (nylon)"
}}
'''
    return {
        "header": open_guitar._lilypond_header(lilypond_text),
        "lilypond_text": lilypond_text,
        "readme_text": "The original compositions are all already in the Public Domain. I release my edits/arrangements of these compositions into the Public Domain under CC0; see LICENSE.",
        "license_text": "Creative Commons Legal Code\nCC0 1.0 Universal\n",
        "lilypond_evidence": {"path": "lagrima/lagrima.ly", "commit": "a" * 40, "blob_sha": "c" * 40},
        "readme_evidence": {"path": "README.md", "commit": "a" * 40, "blob_sha": "e" * 40},
        "license_evidence": {"path": "LICENSE", "commit": "a" * 40, "blob_sha": "d" * 40},
    }


def test_yawnoc_keeps_original_pd_and_arrangement_cc0_as_separate_rights_layers():
    commit = {"commit_sha": "a" * 40, "tree_sha": "b" * 40}
    tree = {"lagrima/lagrima.ly": {"sha": "c" * 40, "size": 5678, "type": "blob"}}
    row = open_guitar._yawnoc_work(yawnoc_release(), {"default_branch": "master", "_frozen_head_commit": "d" * 40}, commit, tree, yawnoc_evidence())
    assert row["id"] == "yawnoc:lagrima"
    assert row["source_url"] == "https://github.com/yawnoc/guitar/releases/tag/lagrima-v1.2.2"
    assert row["title_en"] == "Lágrima"
    assert row["composer_en"] == "Francisco Tárrega"
    assert row["metadata"]["release_name_raw"] == "Lágrima v1.2.2"
    assert row["metadata"]["release_heading_differs_from_source_title"] is True
    assert row["metadata"]["arranger"] is None
    assert row["metadata"]["editor"] == "Conway (edits)"
    assert row["metadata"]["original_arrangement_status"] == "unspecified"
    assert row["metadata"]["source_header"]["arranger"] == "Conway (edits)"
    assert "typed as editor" in row["metadata"]["source_attribution_note"]
    assert row["metadata"]["instrumentation"] == "Guitar"
    assert row["metadata"]["player_count"] is None
    assert "CC0-1.0" in row["metadata"]["license"]
    assert "public domain" in row["metadata"]["license_note"].casefold()
    assert row["metadata"]["composition_license"] == "Public Domain per fixed tag README claim"
    assert row["metadata"]["edition_license"] == "CC0-1.0"
    assert row["metadata"]["rights_layers"] == {"composition": "public_domain", "edition_arrangement": "CC0-1.0"}
    pdf = next(asset for asset in row["assets"] if asset["format"] == "PDF")
    ly = next(asset for asset in row["assets"] if asset["format"] == "LILYPOND")
    assert pdf["status"] == "restricted" and pdf["license"] == "CC0-1.0"
    assert pdf["license_status"] == "explicit_CC0_edition_license"
    assert pdf["acquisition_permission"] == "blocked_by_robots"
    assert "alternate host/path" in pdf["restriction_reason"]
    assert pdf["expected_size"] == 1234
    assert ly["status"] == "metadata_only"
    assert ly["source_repository"]["commit"] == "a" * 40
    assert ly["source_repository"]["path"] == "lagrima/lagrima.ly"


def test_yawnoc_explicit_arrangement_label_stays_typed_as_arranger():
    evidence = yawnoc_evidence()
    evidence["lilypond_text"] = evidence["lilypond_text"].replace("Conway (edits)", "Conway (arrangement)")
    evidence["header"] = open_guitar._lilypond_header(evidence["lilypond_text"])
    row = open_guitar._yawnoc_work(
        yawnoc_release(), {"default_branch": "master", "_frozen_head_commit": "d" * 40},
        {"commit_sha": "a" * 40, "tree_sha": "b" * 40},
        {"lagrima/lagrima.ly": {"sha": "c" * 40, "size": 100, "type": "blob"}}, evidence)
    assert row["metadata"]["arranger"] == "Conway (arrangement)"
    assert row["metadata"]["editor"] is None
    assert row["metadata"]["original_arrangement_status"] == "arrangement"
    assert row["metadata"]["source_header"]["arranger"] == "Conway (arrangement)"


def test_lilypond_header_parser_and_staff_labels_are_source_evidence_only():
    source = r'''\header {
      title = "Actual title"
      subtitle = \markup { { "Sub" } }
      composer = "Composer Name"
      arranger = "Arranger Name"
    }
    % instrumentName = "Ignored comment"
    \new Staff \with {
      instrumentName = "Guitar 1"
      midiInstrument = #"acoustic guitar (nylon)"
    }
    \new Staff \with {
      instrumentName = "Bass"
      midiInstrument = #"electric bass (pick)"
    }
    '''
    header = open_guitar._lilypond_header(source)
    assert header == {"title": "Actual title", "subtitle": "Sub", "composer": "Composer Name", "arranger": "Arranger Name"}
    found = open_guitar._yawnoc_score_instrumentation(source)
    assert found["staff_names"] == ["Guitar 1", "Bass"]
    assert found["instrumentation"] == "Guitar"
    assert found["scope_status"] == "pending_review"
    assert found["player_count"] is None
    no_evidence = open_guitar._yawnoc_score_instrumentation("\\score { c'4 d'4 } ")
    assert no_evidence["instrumentation"] is None
    assert no_evidence["scope_status"] == "pending_review"


def test_yawnoc_tetris_keeps_every_staff_and_bass_visible():
    text = r'''\header {
  title = "Tetris Theme Quartet Arrangement"
  composer = "Russian Traditional"
}
\new Staff \with {
  instrumentName = "Guitar 1"
  midiInstrument = #"acoustic guitar (nylon)"
}
\new Staff \with {
  instrumentName = "Guitar 2"
  midiInstrument = #"acoustic guitar (nylon)"
}
\new Staff \with {
  instrumentName = "Guitar 3"
  midiInstrument = #"acoustic guitar (nylon)"
}
\new Staff \with {
  instrumentName = "Bass"
  midiInstrument = #"electric bass (pick)"
}
'''
    found = open_guitar._yawnoc_score_instrumentation(text)
    assert found["instrumentation"] == "Guitar"
    assert found["staff_names"] == ["Guitar 1", "Guitar 2", "Guitar 3", "Bass"]
    assert found["scope_status"] == "pending_review"
    assert "bass" in found["scope_reason"].casefold()
    assert found["player_count"] is None
    evidence = yawnoc_evidence("Tetris Theme Quartet Arrangement", "Russian Traditional", text)
    row = open_guitar._yawnoc_work(
        yawnoc_release("tetris-quartet-v1.3.1", "tetris-quartet"),
        {"default_branch": "master", "_frozen_head_commit": "d" * 40},
        {"commit_sha": "a" * 40, "tree_sha": "b" * 40},
        {"tetris-quartet/tetris-quartet.ly": {"sha": "c" * 40, "size": 100, "type": "blob"}},
        evidence)
    assert row["metadata"]["instrumentation"] == "Guitar"
    assert row["metadata"]["scope_status"] == "pending_review"
    assert "Guitar 1, Guitar 2, Guitar 3" in row["metadata"]["description"]
    assert "Bass" in row["metadata"]["description"]


def test_yawnoc_readme_release_index_is_stable_and_explicit():
    readme = "\n".join(f"https://github.com/yawnoc/guitar/releases/tag/{tag}" for tag in [
        "dowland-fantasia-7-v1.0.0", "el-vito-v1.1.3", "lagrima-v1.2.2",
        "sor-c-major-35-13-v1.1.1", "tetris-quartet-v1.3.1"])
    assert len(open_guitar._readme_release_index(readme)) == 5
    assert open_guitar._readme_release_index("no release links") == []


def test_yawnoc_release_mapping_requires_exact_native_slug_and_fixed_tag():
    assert open_guitar._record_slug("sor-c-major-35-13-v1.1.1", ["sor-c-major-35-13", "sor-c-major"])
    assert open_guitar._record_slug("sor-c-major-35-13-v1.1.1", ["sor-c-major-35-13", "sor-c-major"]) == "sor-c-major-35-13"
    with pytest.raises(ValueError, match="exactly one"):
        open_guitar._record_slug("unknown-v1.0.0", ["lagrima", "el-vito"])
    with pytest.raises(ValueError, match="exactly one"):
        open_guitar._record_slug("lagrima-v1.0.0", ["lagrima-v1.0.0"])


def test_yawnoc_release_rejects_unapproved_asset_host_or_non_pdf_content_type():
    release = yawnoc_release(assets=[{
        "name": "lagrima.pdf", "browser_download_url": "https://outside.invalid/lagrima.pdf",
        "content_type": "application/pdf", "size": 10,
    }])
    with pytest.raises(ValueError, match="unapproved source URL"):
        open_guitar._release_assets(release)
    release = yawnoc_release(assets=[{
        "name": "lagrima.pdf", "browser_download_url": "https://github.com/yawnoc/guitar/releases/download/x/lagrima.pdf",
        "content_type": "text/html", "size": 10,
    }])
    with pytest.raises(ValueError, match="content type"):
        open_guitar._release_assets(release)


def maikstrings_html(count=112):
    links = []
    composers = [
        ("Felix Horetzky (1796–1870)", 30),
        ("Fernando Sor (1778–1839)", 23),
        ("Mauro Giuliani (1781–1829)", 18),
        ("Matteo Carcassi (1792–1853)", 13),
        ("Dionisio Aguado (1784–1849)", 8),
        ("Johann Kaspar Mertz (1806–1856)", 8),
        ("Ferdinando Carulli (1770–1841)", 6),
        ("Napoléon Coste (1805–1883)", 3),
        ("Francisco Tárrega (1852–1909)", 3),
    ]
    if count == 112:
        assignments = [name for name, amount in composers for _ in range(amount)]
        assignments.remove("Francisco Tárrega (1852–1909)")
        assignments.insert(0, "Francisco Tárrega (1852–1909)")
        filter_groups = composers
    else:
        assignments = ["Francisco Tárrega (1852–1909)"] * count
        filter_groups = [("Francisco Tárrega (1852–1909)", count)]
    for index in range(count):
        title = "Adelita" if index == 0 else f"Piece {index}"
        credit = assignments[index]
        pages = "2 pages" if index == 0 else "1 page"
        links.append(
            f'<a class="nt-link" data-titel="{title}" href="/noten/Gitarrennoten/{index}.pdf">'
            f'<span class="nt-t">{title}</span><span class="nt-c">{credit}</span>'
            f'<span class="nt-p">{pages}</span></a>'
        )
    filters = "".join(
        f'<button data-nt-composer="{name}">{name} · {amount} sheets</button>'
        for name, amount in filter_groups
    )
    return (f'<h1>Classical Guitar Sheet Music</h1><p>{count} sheets</p>{filters}' + "\n".join(links)).encode()


def test_maikstrings_parses_full_directory_and_keeps_unknown_player_count():
    from catalog_unification import instrumentation_topic
    rows, summary = open_guitar.parse_maikstrings_directory(maikstrings_html())
    assert summary["declared_sheet_count"] == summary["parsed_record_count"] == 112
    assert summary["composer_attribution_confirmed"] is True
    assert sum(summary["composer_attribution_context"]["groups"].values()) == 112
    first = rows[0]
    assert first["title_en"] == "Adelita"
    assert first["composer_en"] == "Francisco Tárrega (1852–1909)"
    assert first["metadata"]["source_credit_line"] == first["composer_en"]
    assert "official page labels these nine groups as composers" in first["metadata"]["source_attribution_note"]
    assert "composer filter" in first["metadata"]["source_credit_field"]
    assert first["metadata"]["pages"] == 2
    assert first["metadata"]["instrumentation"] == "Guitar"
    assert instrumentation_topic(first["metadata"]["instrumentation"]) == "guitar_unspecified"
    assert "player count are unknown" in first["metadata"]["description"]
    assert first["metadata"]["license"]
    assert first["metadata"]["license_note"]
    assert first["metadata"]["attribution_role"] == "composer"
    assert "Maikstrings" in first["metadata"]["contributors"]
    assert first["metadata"]["engraver_credit"] == "Maikstrings, per source directory page"
    assert first["instrumentation_status"] == "unverified"
    assert first["metadata"]["player_count"] is None
    assert first["metadata"]["editor"] is None and first["metadata"]["arranger"] is None
    assert first["source_url"] == open_guitar.MAIK_DIRECTORY
    assert first["assets"][0]["status"] == "pending"
    assert first["assets"][0]["license_status"] == "private_acquisition_allowed_public_redistribution_unverified"
    assert first["assets"][0]["private_file_cache_permitted"] is True
    assert 'public PDF mirror' in first["metadata"]["license_note"]
    assert first["assets"][0]["expected_pages"] == 2
    assert "solo" not in first["metadata"]["instrumentation"].casefold()


def test_maikstrings_only_promotes_credit_when_nine_composer_filters_sum_to_directory_total():
    html = maikstrings_html()
    rows, summary = open_guitar.parse_maikstrings_directory(html)
    assert len({row["composer_en"] for row in rows}) == 9
    assert summary["composer_attribution_confirmed"] is True

    # Remove every filter control while leaving all per-item .nt-c values intact.
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    for node in soup.select("[data-nt-composer]"):
        node.decompose()
    uncorroborated, uncorroborated_summary = open_guitar.parse_maikstrings_directory(str(soup))
    assert uncorroborated_summary["composer_attribution_confirmed"] is False
    assert all(row["composer_en"] == "" for row in uncorroborated)
    assert all(row["metadata"]["attribution_role"] == "source_unspecified" for row in uncorroborated)
    assert all(".nt-c source directory credit" in row["metadata"]["source_attribution_note"] for row in uncorroborated)

    mismatched = html.replace(b"30 sheets", b"29 sheets", 1)
    rows_mismatch, mismatch_summary = open_guitar.parse_maikstrings_directory(mismatched)
    assert mismatch_summary["composer_attribution_confirmed"] is False
    assert all(row["composer_en"] == "" for row in rows_mismatch)


def test_maikstrings_id_is_exact_locator_digest_not_download_path():
    locator = "/noten/Gitarrennoten/Adelita%20-%20Francisco.pdf"
    ident = open_guitar.maikstrings_record_id(locator)
    assert ident == "pdf:" + hashlib.sha256(locator.encode("utf-8")).hexdigest()
    assert "/noten/" not in ident and "Adelita" not in ident
    rows, _ = open_guitar.parse_maikstrings_directory(maikstrings_html(1).replace(b"112 sheets", b"1 sheet"))
    assert rows[0]["metadata"]["native_record_locator"] == "/noten/Gitarrennoten/0.pdf"
    assert rows[0]["id"].startswith("maikstrings:pdf:")


def test_maikstrings_requires_complete_count_and_rejects_duplicate_or_off_host_asset():
    with pytest.raises(ValueError, match="parsed 1 guitar links but directory declares 112"):
        open_guitar.parse_maikstrings_directory(
            maikstrings_html(112).replace(b"112 sheets", b"112 sheets", 1).replace(
                b'<a class="nt-link"', b'<aside class="nt-link"', 111
            )
        )
    duplicate = (b'<h1>Classical Guitar Sheet Music</h1><p>2 sheets</p>'
                 b'<a class="nt-link" href="/noten/Gitarrennoten/a.pdf"><span class="nt-t">A</span><span class="nt-p">1 page</span></a>'
                 b'<a class="nt-link" href="/noten/Gitarrennoten/a.pdf"><span class="nt-t">B</span><span class="nt-p">1 page</span></a>')
    with pytest.raises(ValueError, match="repeats a PDF locator"):
        open_guitar.parse_maikstrings_directory(duplicate)
    off_host = b'<h1>Classical Guitar Sheet Music</h1><p>1 sheet</p><a class="nt-link" href="https://outside.invalid/a.pdf"><span class="nt-t">A</span><span class="nt-p">1 page</span></a>'
    with pytest.raises(ValueError, match="parsed 0 guitar links but directory declares 1"):
        open_guitar.parse_maikstrings_directory(off_host)


def test_registry_proposals_separate_private_acquisition_from_public_redistribution():
    from catalog_sources import validate_record_source_url
    proposals = open_guitar.registry_proposals()
    assert set(proposals) == {"yawnoc", "maikstrings"}
    maik = proposals["maikstrings"]
    assert 'explicit_individual_educational_use' in maik["acquisition_settings"]["licensing"]
    assert 'public_redistribution_not_established' in maik["acquisition_settings"]["licensing"]
    assert maik["catalog"] == "sources/maikstrings/catalog.json"
    yawnoc = proposals["yawnoc"]
    assert yawnoc["catalog"] == "sources/yawnoc/catalog.json"
    assert "page_url_rules" in yawnoc and "public_page_rules" not in yawnoc
    assert len(yawnoc["page_url_rules"]) == 1
    assert "releases/tag" in yawnoc["page_url_rules"][0]["path"]
    assert "page_url_rules" in maik
    validate_record_source_url(
        "https://github.com/yawnoc/guitar/releases/tag/lagrima-v1.2.2",
        "yawnoc", "lagrima", [yawnoc])
    with pytest.raises(ValueError, match="unapproved yawnoc source page path"):
        validate_record_source_url(
            "https://github.com/yawnoc/guitar/blob/" + "a" * 40 + "/lagrima/lagrima.ly",
            "yawnoc", "lagrima", [yawnoc])


class FakeClient:
    def __init__(self, root, source_id, hosts, delay=0.8):
        self.root = Path(root)
        self.source_id = source_id
        self.hosts = hosts
        self.delay = delay
        self.path = self.root / "sources" / source_id
        self.path.mkdir(parents=True, exist_ok=True)
        self.state = {"started_at": "2026-10-26T00:00:00+00:00", "failures": []}
        self.calls = []
        self.files = {}

    def get(self, url):
        self.calls.append(url)
        if url != open_guitar.MAIK_DIRECTORY:
            raise AssertionError(f"adapter attempted a non-directory request: {url}")
        body = maikstrings_html()
        return body, {"sha256": hashlib.sha256(body).hexdigest(), "fetched_at": "2026-10-26T00:00:00+00:00",
                      "headers": {"Last-Modified": "Fri, 02 Oct 2026 10:49:28 GMT", "ETag": '"fixture"'}}

    def write_json(self, name, value):
        self.files[name] = value
        path = self.path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")


def test_discover_maikstrings_does_not_request_any_pdf(monkeypatch, tmp_path):
    instances = []

    def fake_factory(*args, **kwargs):
        instance = FakeClient(*args, **kwargs)
        instances.append(instance)
        return instance

    monkeypatch.setattr(open_guitar, "DiscoveryClient", fake_factory)
    report = open_guitar.discover_maikstrings(tmp_path)
    client = instances[0]
    assert client.calls == [open_guitar.MAIK_DIRECTORY]
    assert report["source_record_count"] == report["pending_pdf_count"] == 112
    assert report["restricted_pdf_count"] == 0
    assert report["pdf_downloads_attempted"] is False
    output = client.path
    identity = json.loads((output / "identity_map.json").read_text())
    catalog = json.loads((output / "catalog.json").read_text())
    frozen = json.loads((output / "freeze_report.json").read_text())
    assert len(identity["entries"]) == 112
    assert catalog["works"][0]["source_url"] == open_guitar.MAIK_DIRECTORY
    assert len(frozen["record_outcomes"]) == 112
    assert frozen["pdf_downloads_attempted"] is False


def test_maikstrings_redo_preserves_existing_verified_asset_receipt(monkeypatch, tmp_path):
    from source_adapters.additional import atomic_json
    records, _ = open_guitar.parse_maikstrings_directory(maikstrings_html())
    old = records[0]
    old["assets"][0].update(status="verified", local_path="objects/sha256/abc.pdf", sha256="a" * 64)
    atomic_json(tmp_path / "sources" / "maikstrings" / "catalog.json", {"works": [old]})
    monkeypatch.setattr(open_guitar, "DiscoveryClient", lambda *a, **k: FakeClient(*a, **k))
    open_guitar.discover_maikstrings(tmp_path)
    catalog = json.loads((tmp_path / "sources/maikstrings/catalog.json").read_text())
    restored = next(row for row in catalog["works"] if row["id"] == old["id"])
    assert restored["assets"][0]["status"] == "verified"
    assert restored["assets"][0]["local_path"] == "objects/sha256/abc.pdf"
