from __future__ import annotations

import hashlib
import json
import re
import runpy
import shutil
from pathlib import Path

import pytest

from tests.basic_helpers import ROOT, write_json, write_minimal_pdf
from tests.test_public_site import make_library
from catalog_payload import unpack_payload


def manifest_record(root: Path, category: str, relative: str = "scores/作者/作品/Complete Score.pdf") -> dict:
    path = write_minimal_pdf(root / category / relative)
    return {"work_id": "42", "relative_path": relative, "filename": path.name,
            "description": "Complete Score", "expected_size": path.stat().st_size,
            "sha1_imslp": hashlib.sha1(path.read_bytes()).hexdigest()}


def offline_library(root: Path) -> None:
    make_library(root)
    for category in ["For guitar", "For guitar, violin (arr)"]:
        record = manifest_record(root, category)
        write_json(root / category / "metadata/score_manifest.json", [record])
        (root / category / "index.html").write_text("category", encoding="utf-8")


def render(root: Path) -> tuple[dict, str, dict]:
    result = runpy.run_path(str(ROOT / "scripts/render_master_index.py"))["render"](root)
    html = (root / "index.html").read_text(encoding="utf-8")
    match = re.search(r'<script type="application/json" id="offline-data">(.*?)</script>', html)
    assert match, "Offline data must be embedded so file:// works without fetch"
    return result, html, unpack_payload(json.loads(match[1]))


def test_offline_home_reuses_public_layout_and_search_with_embedded_data(tmp_path: Path) -> None:
    offline_library(tmp_path)
    result, html, payload = render(tmp_path)
    assert result["categories"] == 2
    assert result["unique_works"] == 1
    assert result["downloaded"] == 2
    for identity in ["catalog-title", "search", "category-directory", "results", "back-to-categories"]:
        assert f'id="{identity}"' in html
    for name in ["site.css", "search.js", "app.js"]:
        assert f'public_site/assets/{name}' in html
    assert 'src="scripts/assets/offline-catalog.js"' in html
    scripts = re.findall(r'<script src="([^"]+)"', html)
    app_sources = [src for src in scripts if src.split("?", 1)[0] == "public_site/assets/app.js"]
    assert len(app_sources) == 1
    assert scripts.count("scripts/assets/offline-catalog.js") == 1
    assert scripts.index("scripts/assets/offline-catalog.js") < scripts.index(app_sources[0])
    # Cache-version queries must survive without losing the offline adapter.
    public_app = re.search(r'<script src="assets/app\.js([^"]*)"', (ROOT / "public_site/index.html").read_text())
    assert public_app and app_sources[0] == "public_site/assets/app.js" + public_app[1]
    assert 'id="results" class="results" aria-busy="true" hidden' in html
    assert "离线版" in html
    assert len(payload["data"]["works"]) == 1
    work = payload["data"]["works"][0]
    assert work["category_ids"] == [0, 1]
    assert len(work["local_editions"]) == 2
    assert work["local_editions"][0]["files"][0]["href"].startswith('For%20guitar/scores/')
    assert payload["aliases"] == json.loads((ROOT / "public_site/data/search-aliases.json").read_text())


@pytest.mark.parametrize("fault", ["missing", "html", "broken_pdf", "size", "sha1", "traversal", "symlink"])
def test_offline_links_exclude_unavailable_or_untrusted_scores(tmp_path: Path, fault: str) -> None:
    offline_library(tmp_path)
    category = tmp_path / "For guitar"
    path = category / "metadata/score_manifest.json"
    records = json.loads(path.read_text())
    row = records[0]
    score = category / row["relative_path"]
    if fault == "missing":
        score.unlink()
    elif fault in {"html", "broken_pdf"}:
        score.write_bytes(b"<html>Bot Check</html>" if fault == "html" else b"%PDF-1.4\n%%EOF\n")
        row["expected_size"] = score.stat().st_size
        row["sha1_imslp"] = hashlib.sha1(score.read_bytes()).hexdigest()
    elif fault == "size":
        row["expected_size"] += 1
    elif fault == "sha1":
        row["sha1_imslp"] = "0" * 40
    elif fault == "traversal":
        row["relative_path"] = "../For guitar, violin (arr)/" + row["relative_path"]
    elif fault == "symlink":
        score.unlink()
        outside = write_minimal_pdf(tmp_path.parent / f"{tmp_path.name}-outside.pdf")
        score.symlink_to(outside)
    write_json(path, records)
    _, _, payload = render(tmp_path)
    editions = payload["data"]["works"][0]["local_editions"]
    assert editions[0]["files"] == []
    assert editions[0]["unavailable_count"] == 1
    assert len(editions[1]["files"]) == 1


def test_offline_index_keeps_all_parts_and_effective_source_revision(tmp_path: Path) -> None:
    offline_library(tmp_path)
    records = [manifest_record(tmp_path, "For guitar", f"scores/part {i}.pdf") for i in range(12)]
    records[0]["download_expected_size"] = records[0]["expected_size"]
    records[0]["download_sha1"] = records[0]["sha1_imslp"]
    records[0]["expected_size"] = 1
    records[0]["sha1_imslp"] = "0" * 40
    write_json(tmp_path / "For guitar/metadata/score_manifest.json", records)
    _, _, payload = render(tmp_path)
    assert len(payload["data"]["works"][0]["local_editions"][0]["files"]) == 12


def test_offline_pdf_validation_uses_contents_not_filename_extension(tmp_path: Path) -> None:
    offline_library(tmp_path)
    record = manifest_record(tmp_path, "For guitar", "scores/long_original_name_truncated_3b284133")
    write_json(tmp_path / "For guitar/metadata/score_manifest.json", [record])
    _, _, payload = render(tmp_path)
    assert len(payload["data"]["works"][0]["local_editions"][0]["files"]) == 1


@pytest.mark.skipif(not shutil.which("pdfinfo"), reason="optional Poppler compatibility reader")
def test_offline_supports_valid_pdf_with_null_encryption_dictionary(tmp_path: Path) -> None:
    offline_library(tmp_path)
    record = manifest_record(tmp_path, "For guitar")
    path = tmp_path / "For guitar" / record["relative_path"]
    path.write_bytes(path.read_bytes().replace(b"trailer\n<<", b"trailer\n<<\n/Encrypt null"))
    record["expected_size"] = path.stat().st_size
    record["sha1_imslp"] = hashlib.sha1(path.read_bytes()).hexdigest()
    write_json(tmp_path / "For guitar/metadata/score_manifest.json", [record])
    _, _, payload = render(tmp_path)
    assert len(payload["data"]["works"][0]["local_editions"][0]["files"]) == 1


def test_offline_payload_cannot_close_its_script_element(tmp_path: Path) -> None:
    offline_library(tmp_path)
    for category in ["For guitar", "For guitar, violin (arr)"]:
        path = tmp_path / category / "metadata/catalog.json"
        works = json.loads(path.read_text())
        works[0]["title_en"] = "</script><script>alert(1)</script>"
        write_json(path, works)
    _, html, payload = render(tmp_path)
    assert "</script><script>alert(1)" not in html
    assert payload["data"]["works"][0]["title_en"] == "</script><script>alert(1)</script>"


def test_offline_generation_preserves_previous_entry_and_does_not_write_public_data(tmp_path: Path) -> None:
    offline_library(tmp_path)
    (tmp_path / "index.html").write_text("previous offline library")
    public = write_json(tmp_path / "public_site/data/catalog.json", {"unchanged": True})
    render(tmp_path)
    assert any(path.read_text() == "previous offline library" for path in (tmp_path / "backups/offline-ui").glob("*.html"))
    assert json.loads(public.read_text()) == {"unchanged": True}


def test_reviewed_non_target_membership_keeps_file_but_excludes_link(tmp_path: Path) -> None:
    offline_library(tmp_path)
    manifest = json.loads((tmp_path / "For guitar/metadata/score_manifest.json").read_text())
    row = manifest[0]
    write_json(tmp_path / "config/score_exclusions.json", {"schema_version": 1, "entries": [{
        "category": "For guitar", "work_id": "42", "filename": row["filename"], "reason": "额外低音乐器",
    }]})
    result, _, payload = render(tmp_path)
    edition = payload["data"]["works"][0]["local_editions"][0]
    assert edition["files"] == []
    assert edition["excluded_count"] == 1
    assert result["excluded_memberships"] == 1
    assert "local_href" not in payload["data"]["categories"][0]
    assert (tmp_path / "For guitar" / row["relative_path"]).is_file()
