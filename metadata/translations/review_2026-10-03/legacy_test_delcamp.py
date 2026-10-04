"""Regression checks for music meaning and preservation, not dictionary output."""
import json
import re
import unittest
from pathlib import Path
from legacy_validate_decisions import balanced, number_values

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ROWS = json.loads((ROOT/'work/title-review/2026-10-03/legacy-review/delcamp-review-input.json').read_text())
ENTRIES = json.loads((HERE/'root_delcamp_supplement.json').read_text())['entries']
BYID = {e['id']: e for e in ENTRIES}


def row(i):
    return BYID[ROWS[i]['id']]


class DelcampSupplement(unittest.TestCase):
    def test_complete_sparse_pool_and_exact_guards(self):
        self.assertEqual(len(ENTRIES), 540)
        source = {r['id']: r for r in ROWS}
        for e in ENTRIES:
            r = source[e['id']]
            self.assertEqual((e['original'], e['original_composer'], e['display_original']), (r['original'], r['composer'], r['display_original']))
            self.assertEqual(e['status'], 'reference')
            self.assertTrue(balanced(e['zh']) and balanced(e['display_zh']))
            self.assertRegex(e['display_zh'], r'[\u3400-\u9fff]')
            self.assertFalse(number_values(r['original'])-number_values(e['zh'], True), e['id'])

    def test_author_source_conflict_does_not_rewrite_identity(self):
        self.assertEqual(row(404)['original_composer'], 'Tomaso Giovanni Albinoni')
        self.assertEqual(row(525)['original_composer'], 'Francesco Canova da Milano')
        self.assertIn('署名冲突', row(404)['reason'])
        self.assertIn('不更改来源署名', row(525)['reason'])

    def test_old_alfabeto_not_modern_key(self):
        for i in (341,342,343,344,345):
            self.assertIn('和弦符号', row(i)['zh'])
            self.assertNotRegex(row(i)['zh'], r'[EOD]大调')

    def test_third_string_tuning_not_piece_number(self):
        self.assertIn('第3弦=F#', row(422)['zh'])
        self.assertIn('第3弦=G', row(423)['zh'])
        self.assertIn('帕凡舞曲第4号', row(598)['zh'])

    def test_tutorial_names_do_not_become_composer(self):
        self.assertEqual(row(0)['original_composer'], '')
        self.assertIn('教程', row(0)['zh'])
        self.assertNotIn('学校', row(0)['zh'])

    def test_source_differing_rossini_number_layers_preserved(self):
        self.assertIn('第1号，作品122', row(574)['zh'])
        self.assertIn('第2号，作品123', row(575)['zh'])
        self.assertIn('第6号，作品124，第I册', row(576)['zh'])

    def test_source_notes_outside_main_title(self):
        self.assertIn('629', row(306)['zh'])
        self.assertNotRegex(row(306)['display_zh'], '629|73|Mo')
        self.assertNotIn('来源附署名', row(514)['display_zh'])
        self.assertIn('Elisabetta', row(552)['display_zh'])
        self.assertIn('塞维利亚', row(552)['zh'])

    def test_true_unknown_names_remain_unmodified(self):
        for i in (41,201,222):
            self.assertNotIn(ROWS[i]['id'], BYID)

    def test_sinfonia_does_not_imply_modern_symphony(self):
        self.assertIn('Sinfonia', row(445)['zh'])
        self.assertNotIn('交响曲', row(445)['zh'])


if __name__ == '__main__':
    unittest.main()
