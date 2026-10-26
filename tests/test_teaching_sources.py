import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.source_adapters.teaching import (
    CLASSROOM_DIRECTORIES,
    CLASSROOM_ID,
    DEREK_DIRECTORY,
    DEREK_ID,
    parse_derekhasted,
    parse_guitarclassroom_page,
    registry_proposals,
    _apply_acquisition_policy,
    _locator_record_id,
    _write_discovery,
)


def _anchor(name: str, label: str) -> str:
    return f'<a href="/storage/{name}.pdf">{label}</a>'


class DerekHastedParserTests(unittest.TestCase):
    def page(self):
        sections = []
        for group, count in (("2", 7), ("3", 7), ("4", 8), ("24", 1)):
            sections.append(f"<h2>{group} Guitars</h2>")
            for index in range(count):
                slug = f"piece-{group}-{index}"
                title = "Sonata (Composer Name)" if group == "2" and index == 0 else f"Piece {slug}"
                sections.append(f"<p>{_anchor(slug, title)}</p>")
        return "<h1>Free Guitar Ensemble Sheet Music</h1>" + "".join(sections)

    def test_native_identity_roles_and_declared_instrumentation_boundary(self):
        parsed = parse_derekhasted(self.page())
        self.assertEqual(23, len(parsed["works"]))
        by_old_slug = {work["metadata"]["former_unpublished_slug"]: work for work in parsed["works"]}
        composer = by_old_slug["piece-2-0"]
        expected_id = "derekhasted:pdf:" + hashlib.sha256(b"/storage/piece-2-0.pdf").hexdigest()
        self.assertEqual(expected_id, composer["id"])
        self.assertEqual("/storage/piece-2-0.pdf", composer["metadata"]["original_source_locator"])
        self.assertEqual("Composer Name", composer["composer_en"])
        self.assertEqual(DEREK_DIRECTORY, composer["source_url"])
        self.assertEqual("pending", composer["assets"][0]["status"])
        self.assertEqual("offered_free_personal_download", composer["assets"][0]["acquisition_permission"])
        self.assertEqual("2 guitars", composer["metadata"]["instrumentation"])
        self.assertEqual(2, composer["metadata"]["player_count"])
        self.assertEqual("source_declared", composer["metadata"]["player_count_status"])
        flexible = by_old_slug["piece-24-0"]
        self.assertIsNone(flexible["metadata"]["player_count"])
        self.assertEqual("guitar ensemble", flexible["metadata"]["instrumentation"])
        self.assertEqual("variable_unknown", flexible["metadata"]["player_count_status"])
        self.assertEqual(23, parsed["unique_locator_count"])
        self.assertEqual(24, parsed["scope_correction"]["earlier_manual_estimate"])

    def test_locator_hash_preserves_percent_encoding_and_case(self):
        lower = "/free/Score%2bA.pdf"
        upper = "/free/Score%2BA.pdf"
        self.assertEqual("pdf:" + hashlib.sha256(lower.encode()).hexdigest(), _locator_record_id(lower))
        self.assertEqual("pdf:" + hashlib.sha256(upper.encode()).hexdigest(), _locator_record_id(upper))
        self.assertNotEqual(_locator_record_id(lower), _locator_record_id(upper))

    def test_unrecognized_heading_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "confirmed free ensemble directory"):
            parse_derekhasted("<h1>Not the score directory</h1>")


def _card(title: str, *links: tuple[str, str]) -> str:
    contents = "".join(f'<div class="component"><a href="/storage/{slug}.pdf">{label}</a></div>'
                        for slug, label in links)
    return (f'<div class="accordion-item"><div class="accordion-item-title">{title}</div>'
            f'<div class="accordion-item-body">{contents}</div></div>')


class GuitarClassroomParserTests(unittest.TestCase):
    def ensemble_page(self):
        return """<html><head><title>Free Guitar Ensemble Sheet Music - The Guitar Classroom</title></head>
        <body><h1>Free Guitar Ensemble Sheet Music</h1>
        <h2>Intermediate – Advanced Quartets</h2>
        """ + _card("Bella (2016)", ("bella", "Score &amp; Parts"),
                       ("bella__w-tabs_", "Parts w-Tabs")) + _card(
            "Ave Maria (F. Schubert)", ("ave-maria", "Ave Maria"),
            ("ave-maria-first-position", "1st Position Version")) + """
        <h2>GUITAR QUARTET and STRINGS</h2>
        """ + _card("Mama's Lullaby (2017) Guitar Quartet &amp; Violin (or cello)",
                       ("mamas-lullaby", "Score &amp; Parts")) + _card(
            "Music for a Loonie (2018) Guitar Ensemble &amp; String Symphony",
            ("loonie-score", "Score"), ("loonie-guitar-parts", "Guitar Parts"),
            ("loonie-string-parts", "String Parts")) + """
        <h2>South American Duets &amp; Trios</h2>
        """ + _card("South American Duets &amp; Trios", ("chanson", "Chanson Indienne"),
            ("cholita-duet", "Cholita (Duet)"), ("cholita-trio", "Cholita (Trio)")) + """
        <div><a href="/storage/pricing-guide.pdf">Pricing &amp; Licensing Info</a></div>
        </body></html>"""

    def test_parts_bundle_versions_and_mixed_guitar_strings(self):
        parsed = parse_guitarclassroom_page(
            self.ensemble_page(), CLASSROOM_DIRECTORIES["guitar_ensemble"], "guitar_ensemble")
        by_old_slug = {row["metadata"]["former_unpublished_slug"]: row for row in parsed["works"]}
        bella = by_old_slug["bella"]
        expected_id = "guitarclassroom:pdf:" + hashlib.sha256(b"/storage/bella.pdf").hexdigest()
        self.assertEqual(expected_id, bella["id"])
        self.assertEqual("/storage/bella.pdf", bella["metadata"]["original_source_locator"])
        self.assertEqual(["/storage/bella.pdf", "/storage/bella__w-tabs_.pdf"],
                         bella["metadata"]["original_source_locators"])
        self.assertEqual(2, len(bella["assets"]))
        self.assertEqual(2, len(bella["metadata"]["native_record_locators"]))
        self.assertEqual(CLASSROOM_DIRECTORIES["guitar_ensemble"], bella["source_url"])
        self.assertTrue(all(asset["status"] == "pending" for asset in bella["assets"]))
        self.assertEqual("explicit_individual_noncommercial_use", bella["assets"][0]["acquisition_permission"])

        # Same work name with two source-labelled versions has two distinct
        # native locator identities; title similarity does not merge them.
        self.assertIn("ave-maria", by_old_slug)
        self.assertIn("ave-maria-first-position", by_old_slug)
        self.assertEqual(by_old_slug["ave-maria"]["title_en"], by_old_slug["ave-maria-first-position"]["title_en"])

        loonie = by_old_slug["loonie-score"]
        self.assertEqual(3, len(loonie["assets"]))
        self.assertEqual("guitar and strings", loonie["metadata"]["instrumentation"])
        self.assertIsNone(loonie["metadata"]["player_count"])
        self.assertIn("String Symphony", loonie["metadata"]["source_attribution_note"])
        self.assertTrue(loonie["metadata"]["description"])
        mama = by_old_slug["mamas-lullaby"]
        self.assertIn("guitar and strings", mama["metadata"]["instrumentation"])
        self.assertEqual("", mama["composer_en"])
        self.assertEqual("guitar and strings", mama["metadata"]["instrumentation"])
        self.assertIsNone(mama["metadata"]["player_count"])
        self.assertIn("Violin", mama["metadata"]["source_attribution_note"])

        geography = parse_guitarclassroom_page(
            self.ensemble_page().replace("</body>", _card("Scarborough Fair (England)",
                ("scarborough", "Scarborough Fair")) + "</body>"),
            CLASSROOM_DIRECTORIES["guitar_ensemble"], "guitar_ensemble")
        scarborough = next(row for row in geography["works"]
                           if row["metadata"]["former_unpublished_slug"] == "scarborough")
        self.assertEqual("", scarborough["composer_en"])

        self.assertEqual(1, len(parsed["excluded"]))
        self.assertIn("not a score", parsed["excluded"][0]["reason"])
        self.assertEqual(8, len(parsed["works"]))
        by_id = {row["metadata"]["former_unpublished_slug"]: row for row in parsed["works"]}
        self.assertEqual(("2 guitars", 2, "source_declared"), (
            by_id["cholita-duet"]["metadata"]["instrumentation"],
            by_id["cholita-duet"]["metadata"]["player_count"],
            by_id["cholita-duet"]["metadata"]["player_count_status"]))
        self.assertEqual(("3 guitars", 3), (
            by_id["cholita-trio"]["metadata"]["instrumentation"],
            by_id["cholita-trio"]["metadata"]["player_count"]))
        self.assertEqual("guitar ensemble", by_id["chanson"]["metadata"]["instrumentation"])
        self.assertIsNone(by_id["chanson"]["metadata"]["player_count"])
        self.assertEqual(12, parsed["raw_pdf_link_count"])

    def test_locator_hash_preserves_percent_encoding_and_case(self):
        html = ("<html><head><title>Classical Guitar - The Guitar Classroom</title></head><body>"
                + _card("First Version", ("Score%2bA", "PDF"))
                + _card("Second Version", ("Score%2BA", "PDF")) + "</body></html>")
        parsed = parse_guitarclassroom_page(html, CLASSROOM_DIRECTORIES["classical"], "classical")
        rows = {row["title_en"]: row for row in parsed["works"]}
        self.assertEqual("guitarclassroom:pdf:" + hashlib.sha256(b"/storage/Score%2bA.pdf").hexdigest(),
                         rows["First Version"]["id"])
        self.assertEqual("guitarclassroom:pdf:" + hashlib.sha256(b"/storage/Score%2BA.pdf").hexdigest(),
                         rows["Second Version"]["id"])
        self.assertNotEqual(rows["First Version"]["id"], rows["Second Version"]["id"])

    def test_classical_directory_and_wrong_url_guard(self):
        html = "<html><head><title>Classical Guitar - The Guitar Classroom</title></head>" + _card(
            "A Study", ("study", "PDF")) + _card(
            "The Complete Advanced Classical Guitar Book", ("classical-guitar-book", "I AGREE")) + "</html>"
        parsed = parse_guitarclassroom_page(html, CLASSROOM_DIRECTORIES["classical"], "classical")
        row = next(row for row in parsed["works"]
                   if row["metadata"]["former_unpublished_slug"] == "study")
        self.assertEqual(CLASSROOM_DIRECTORIES["classical"], row["source_url"])
        book = next(row for row in parsed["works"]
                    if row["metadata"]["former_unpublished_slug"] == "classical-guitar-book")
        self.assertEqual("The Complete Advanced Classical Guitar Book", book["title_en"])
        self.assertEqual("reference", book["resource_type"])
        with self.assertRaisesRegex(ValueError, "outside the frozen directory scope"):
            parse_guitarclassroom_page(html, "https://www.theguitarclassroom.com/other", "classical")


class RegistryProposalTests(unittest.TestCase):
    def test_proposals_are_metadata_only_and_only_human_directory_pages_are_public(self):
        proposals = registry_proposals()
        self.assertEqual({DEREK_ID, CLASSROOM_ID}, set(proposals))
        for source_id, proposal in proposals.items():
            self.assertTrue(proposal["metadata_only"])
            self.assertEqual("discovery_only", proposal["metadata_only_phase"])
            self.assertEqual(proposal["allowed_hosts"], proposal["asset_hosts"])
            self.assertGreaterEqual(proposal["acquisition_settings"]["delay"], 1)
            self.assertEqual("personal_offline_only", proposal["acquisition_settings"]["scope"])
            self.assertTrue(all(rule["human_page"] for rule in proposal["page_url_rules"]))
            self.assertNotIn("pdf", proposal["homepage"].casefold())
        self.assertEqual("not_confirmed", proposals[DEREK_ID]["acquisition_settings"]["public_redistribution"])
        self.assertEqual("prohibited_by_source", proposals[CLASSROOM_ID]["acquisition_settings"]["public_redistribution"])

    def test_new_discovery_client_counts_cached_successful_listing_pages_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = {
                "schema_version": 1, "source_id": CLASSROOM_ID,
                "started_at": "2026-10-27T00:00:00+00:00", "failures": [],
                "requests": {
                    CLASSROOM_DIRECTORIES["classical"]: {"status": 200},
                    CLASSROOM_DIRECTORIES["guitar_ensemble"]: {"status": 200},
                    "https://www.theguitarclassroom.com/classical-guitar": {"status": 404},
                },
            }
            state_path = root / "sources" / CLASSROOM_ID / "discovery_state.json"
            state_path.parent.mkdir(parents=True)
            state_path.write_text(json.dumps(state), encoding="utf-8")

            summary = _write_discovery(
                root, CLASSROOM_ID, "The Guitar Classroom", "https://www.theguitarclassroom.com/",
                "test scope", [], [], {"source_link_count": 0},
                {"excluded": [], "pending": []},
            )
            catalog = json.loads((root / "sources" / CLASSROOM_ID / "catalog.json").read_text())
            snapshot = catalog["snapshot"]
            self.assertEqual(2, summary["listing_page_count"])
            self.assertEqual(2, snapshot["page_count"])
            self.assertEqual(2, snapshot["listing_page_count"])
            self.assertIn("exact configured directory URLs", snapshot["page_count_method"])

    def test_proposals_distinguish_discovery_metadata_from_offline_use(self):
        proposals = registry_proposals()
        derek = proposals[DEREK_ID]
        classroom = proposals[CLASSROOM_ID]
        for proposal in (derek, classroom):
            self.assertTrue(proposal["metadata_only"])
            self.assertEqual("discovery_only", proposal["metadata_only_phase"])
            self.assertEqual("personal_offline_only", proposal["acquisition_settings"]["scope"])

        self.assertEqual("not_confirmed", derek["acquisition_settings"]["public_redistribution"])
        self.assertIn("free personal download", derek["file_acquisition_note"])
        self.assertEqual("prohibited_by_source", classroom["acquisition_settings"]["public_redistribution"])
        self.assertIn("download/printing", classroom["file_acquisition_note"])
        self.assertIn("prohibit public reposting", classroom["file_acquisition_note"])

    def test_private_offline_policy_preserves_receipts_and_never_grants_public_reposting(self):
        catalog = {"works": [{"assets": [
            {"status": "restricted", "local_path": None},
            {"status": "verified", "local_path": "sources/objects/sha256/abc.pdf", "sha256": "abc"},
            {"status": "failed", "attempts": 1, "last_error": "HTTP 403"},
        ]}]}
        counts = _apply_acquisition_policy(catalog, CLASSROOM_ID)
        assets = catalog["works"][0]["assets"]
        self.assertEqual(["pending", "verified", "failed"], [row["status"] for row in assets])
        self.assertEqual("abc", assets[1]["sha256"])
        self.assertEqual("HTTP 403", assets[2]["last_error"])
        self.assertEqual({"pending": 1, "verified": 1, "failed": 1}, counts)
        self.assertTrue(all(row["acquisition_permission"] == "explicit_individual_noncommercial_use" for row in assets))
        self.assertTrue(all(row["license_status"] == "personal_use_only_no_public_redistribution" for row in assets))


if __name__ == "__main__":
    unittest.main()
