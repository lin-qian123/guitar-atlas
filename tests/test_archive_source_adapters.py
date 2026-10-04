"""Check provenance-sensitive adapter boundaries without contacting sources."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from source_adapters import boije, dga, rism


class BoijeAdapterTests(unittest.TestCase):
    def test_native_shelfmark_merges_components_but_keeps_original_attributions(self):
        category = {"id": "index:a", "name": "A", "kind": "unspecified", "source_url": boije.HOMEPAGE + "boijes-samling-a/"}
        rows = boije.page_rows('<table><tr><td>Albert, H.</td><td><a href="https://urn.kb.se/resolve?urn=urn:test">Scherzo.</a></td><td>Boije 965:15</td></tr><tr><td>Smith, X.</td><td><a href="https://urn.kb.se/resolve?urn=urn:test">Andante.</a></td><td>Boije 965:15</td></tr></table>', category)
        catalog = boije.normalize([category], rows, {})
        self.assertEqual(len(catalog["works"]), 1)
        self.assertEqual(catalog["works"][0]["id"], "boije:965:15")
        self.assertEqual(catalog["works"][0]["metadata"]["component_count"], 2)
        self.assertEqual(len(catalog["works"][0]["assets"]), 1)
        self.assertEqual(catalog["works"][0]["instrumentation_status"], "unknown")

    def test_explicit_scoring_exclusions_do_not_reject_operatic_theme(self):
        self.assertIsNone(boije.exclusion_reason("Fantaisie sur des motifs de l'opéra La Muette de Portici."))
        self.assertIsNone(boije.exclusion_reason("Orgelfuge. Arr. von J. K. Mertz."))
        self.assertIsNotNone(boije.exclusion_reason("Arion. Sammlung auserlesener Gesangstücke."))
        self.assertIsNotNone(boije.exclusion_reason("Douze pièces pour guitare ou lyre."))

    def test_non_native_numbers_and_unapproved_asset_hosts_fail(self):
        category = {"id": "a", "source_url": boije.HOMEPAGE}
        self.assertEqual(boije.page_rows('<table><tr><td>X</td><td>Title</td><td>123</td></tr></table>', category), [])
        with self.assertRaises(ValueError):
            boije.page_rows('<table><tr><td>X</td><td><a href="https://malicious.invalid/f.pdf">Title</a></td><td>Boije 1</td></tr></table>', category)

    def test_native_range_and_bracketed_shelfmarks_are_preserved(self):
        category = {"id": "a", "source_url": boije.HOMEPAGE}
        rows = boije.page_rows('<table><tr><td><a href="https://urn.kb.se/resolve?urn=urn:test">Collection</a></td><td>Boije 1055-1056</td></tr><tr><td>Mertz</td><td>Opern-Revue</td><td>[Boije 386]</td></tr></table>', category)
        self.assertEqual([row["native_id"] for row in rows], ["1055-1056", "386"])
        self.assertEqual(rows[0]["composer"], "")


class RismAdapterTests(unittest.TestCase):
    def test_keyword_label_is_not_verified_scoring(self):
        item = {"id": "https://rism.online/sources/123", "label": {"en": ["Guitar book; source label"]},
                "summary": {"sourceComposer": {"value": {"none": ["Unknown, A."]}}}}
        row = rism.normalize_record(item)
        self.assertEqual(row["instrumentation_status"], "unknown")
        self.assertFalse(row["metadata"]["resource_metadata_complete"])
        self.assertEqual(row["metadata"]["title_basis"], "resource_label")
        self.assertEqual(row["assets"], [])

    def test_detail_scoring_and_authority_provenance_survive(self):
        item = {"id": "https://rism.online/sources/123", "label": {"en": ["Index title"]}}
        detail = {"id": item["id"], "creator": {"role": {"label": {"en": ["Composer/Author"]}}, "relatedTo": {"id": "https://rism.online/people/20", "label": {"none": ["Sor, Fernando"]}}},
                  "contents": {"summary": [{"label": {"en": ["Standardized title"]}, "value": {"none": ["Study"]}},
                                            {"label": {"en": ["Total scoring"]}, "value": {"none": ["guit (1)"]}}]},
                  "partOf": {"items": [{"relatedTo": {"id": "https://rism.online/sources/12", "label": {"none": ["Collection"]}}}]}}
        row = rism.normalize_record(item, detail)
        self.assertEqual(row["title_en"], "Study")
        self.assertEqual(row["metadata"]["instrumentation"], "guit (1)")
        self.assertEqual(row["instrumentation_status"], "source_declared")
        self.assertIn("rism:12", row["metadata"]["related_source_ids"])
        self.assertTrue(any(r["id"] == "https://rism.online/people/20" for r in row["metadata"]["authority_relations"]))
        self.assertEqual(next(r["role"] for r in row["metadata"]["authority_relations"] if r["id"].endswith("people/20")), "Composer/Author")

    def test_external_diamm_identity_does_not_collide_with_rism_source_ids(self):
        item = {"id": "https://rism.online/external/diamm/source/1010", "label": {"en": ["[No title]; Manuscript copy"]}}
        row = rism.normalize_record(item)
        self.assertEqual(row["id"], "rism:external/diamm/source/1010")
        self.assertEqual(row["metadata"]["external_record_provider"], "DIAMM")
        detailed = rism.normalize_record(item, {"id": item["id"], "contents": {}})
        self.assertEqual(detailed["title_en"], "[No title]; Manuscript copy")
        self.assertEqual(detailed["metadata"]["title_basis"], "search_index_label")

    def test_sru_marc_fields_authorities_and_format_are_retained(self):
        item = {"id": "https://rism.online/sources/123", "label": {"en": ["Search label"]}, "flags": {}}
        xml = '''<root xmlns:marc="http://www.loc.gov/MARC21/slim"><marc:record>
        <marc:controlfield tag="001">123</marc:controlfield>
        <marc:datafield tag="100"><marc:subfield code="a">Sor, Fernando</marc:subfield><marc:subfield code="0">20</marc:subfield></marc:datafield>
        <marc:datafield tag="240"><marc:subfield code="a">Study</marc:subfield></marc:datafield>
        <marc:datafield tag="594"><marc:subfield code="b">guit</marc:subfield><marc:subfield code="c">1</marc:subfield></marc:datafield>
        <marc:datafield tag="852"><marc:subfield code="c">Mus.ms. 1</marc:subfield><marc:subfield code="e">Library</marc:subfield><marc:subfield code="x">30</marc:subfield></marc:datafield>
        </marc:record></root>'''
        details = rism.parse_sru(xml, {item["id"]: item}, "https://muscat.rism.info/sru/sources?query=id=123")
        row = rism.normalize_record(item, details[item["id"]])
        self.assertEqual(row["title_en"], "Study")
        self.assertEqual(row["metadata"]["total_scoring"], "guit (1)")
        self.assertEqual(row["metadata"]["institution"], "Library")
        self.assertEqual(row["metadata"]["metadata_format"], "MARCXML")
        self.assertEqual(len(row["metadata"]["source_marc_fields"]), 4)
        with self.assertRaises(ValueError):
            rism.parse_sru(xml, {}, "https://muscat.rism.info/sru/sources?query=id=124")

    def test_rism_declared_scoring_exclusions_preserve_unknown_and_chamber(self):
        def row(scoring):
            return {"metadata": {"total_scoring": scoring}}
        self.assertIsNotNone(rism.exclusion_reason(row("B (1); guit (1)")))
        self.assertIsNotNone(rism.exclusion_reason(row("V, fl, pf, guit")))
        self.assertIsNotNone(rism.exclusion_reason(row("guit (pf) (1)")))
        self.assertIsNotNone(rism.exclusion_reason(row("vl (1)")))
        self.assertIsNone(rism.exclusion_reason(row("no indication")))
        self.assertIsNone(rism.exclusion_reason(row("fl (1); vl (1); guit (1)")))
        self.assertIsNone(rism.exclusion_reason(row("guit (1)")))

    def test_child_titles_and_scoring_do_not_replace_parent_fields(self):
        item = {"id": "https://rism.online/sources/123", "label": {"en": ["Parent search label"]}}
        detail = {"id": item["id"], "contents": {"summary": [
            {"label": {"en": ["Standardized title"]}, "value": {"none": ["Guitar collection"]}},
            {"label": {"en": ["Total scoring"]}, "value": {"none": ["guit (1)"]}}]},
            "sourceItems": {"items": [{"id": "https://rism.online/sources/124", "summary": [
                {"label": {"en": ["Standardized title"]}, "value": {"none": ["Separate child"]}},
                {"label": {"en": ["Total scoring"]}, "value": {"none": ["V (1); guit (1)"]}}]}]}}
        row = rism.normalize_record(item, detail)
        self.assertEqual(row["title_en"], "Guitar collection")
        self.assertEqual(row["metadata"]["total_scoring"], "guit (1)")
        self.assertIsNone(rism.exclusion_reason(row))
        self.assertEqual(row["metadata"]["related_source_relations"][0]["target_id"], "rism:124")


class DgaAdapterTests(unittest.TestCase):
    def test_boije_relationship_uses_siglum_and_exact_native_shelfmark(self):
        raw = {"id": 1260, "title": "Study", "author": "Sor", "source": "S:Skma", "source_call": "Boije 465", "publisher": "Original Press", "digital_file": "http://example.invalid/score.pdf"}
        row = dga.normalize_record(raw, {"name": "Music Library", "country": "Sweden"})
        self.assertEqual(row["metadata"]["related_source_ids"], ["boije:465"])
        self.assertEqual(row["metadata"]["source_fields"], raw)
        self.assertEqual(row["source_url"], dga.HOMEPAGE)
        self.assertEqual(row["assets"], [])
        self.assertEqual(row["instrumentation_status"], "unknown")
        self.assertEqual(dga.normalize_record({**raw, "source": "D:Mbs"})["metadata"]["related_source_ids"], [])

    def test_pagination_overlap_fails_instead_of_duplicate_counting(self):
        raw = {"id": 1, "title": "X", "source": "S:Skma"}
        with self.assertRaises(ValueError):
            dga.normalize([raw, raw], [{"source": "S:Skma", "record_count": 2}], {})

    def test_vocal_scoring_is_excluded_but_periodical_text_is_reference(self):
        vocal = {"id": 1, "title": "Song", "source": "US:BAu", "instruments": "piano and voice; guitar, banjo"}
        article = {"id": 2, "title": "Guitar interview", "source": "", "contents": "<h1>ETUDE</h1><p>Article text</p>"}
        catalog = dga.normalize([vocal, article], [], {})
        self.assertEqual(len(catalog["excluded_entries"]), 1)
        self.assertEqual(catalog["works"][0]["resource_type"], "reference")
        self.assertEqual(catalog["summary"]["raw_discovery_records"], 2)


if __name__ == "__main__":
    unittest.main()
