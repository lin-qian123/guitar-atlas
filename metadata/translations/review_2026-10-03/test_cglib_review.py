"""Regression checks for full music clauses and exact CGLIB review guards."""
import importlib.util
import json
import re
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
spec = importlib.util.spec_from_file_location('cglib_review_rules', HERE / 'cglib_semantic_rules.py')
rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules)


class CompleteMusicClauses(unittest.TestCase):
    def test_piece_count_is_not_instrument_count(self):
        self.assertEqual(rules.semantic_title('3 Guitar pieces'), '3首吉他乐曲')
        self.assertEqual(rules.semantic_title('3 lute pieces'), '3首鲁特琴乐曲')

    def test_counted_duos_preserve_destination(self):
        result = rules.semantic_title('Op.244 Deux Duos pour Guitare et Violon')
        self.assertEqual(result, '作品244：二首二重奏（为吉他与小提琴而作）')
        self.assertEqual(rules.semantic_title('6 Duos'), '6首二重奏')

    def test_plurals_do_not_become_roman_numbered_parts(self):
        result = rules.semantic_title('Polka per 2 mandolini, mandola e chitarra')
        self.assertEqual(result, '波尔卡（为2把曼陀林、曼多拉琴与吉他而作）')
        self.assertNotIn('第i声部', result)

    def test_parts_are_separate_from_instruments(self):
        result = rules.semantic_title('Habanera para dos guitarras Guitar 1a')
        self.assertIn('（为双吉他而作）', result)
        self.assertIn('吉他第1声部', result)
        self.assertNotIn('双吉他与吉他', result)

    def test_counted_guitars(self):
        self.assertEqual(rules.semantic_title('Sonata for two guitars'), '奏鸣曲（为双吉他而作）')
        self.assertEqual(rules.semantic_title('7 string guitar'), '7弦吉他')

    def test_trio_requires_a_minute_clause(self):
        self.assertEqual(rules.semantic_title('Trio'), '三重奏')
        self.assertEqual(rules.semantic_title('Minuet and Trio'), '小步舞曲与三声中部')

    def test_key_order_and_tempo_qualifier(self):
        self.assertEqual(rules.semantic_title('Poco Allegretto in A'), 'A调稍小快板')
        self.assertEqual(rules.semantic_title('Allegretto in A'), 'A调小快板')
        self.assertEqual(rules.semantic_title('Gavotta in D major'), 'D大调加沃特舞曲')
        self.assertEqual(rules.semantic_title('Nocturne Es-dur No.2'), '降E大调夜曲第2号')
        self.assertEqual(rules.semantic_title('Minueto No.1 in A minor'), 'A小调小步舞曲第1号')

    def test_nocturne_is_not_a_number_marker(self):
        self.assertEqual(rules.semantic_title('Nocturne No.2'), '夜曲第2号')

    def test_opus_colon_is_work_number(self):
        self.assertEqual(rules.semantic_title('Sonata Op: 22'), '奏鸣曲作品22')
        self.assertIsNone(rules.semantic_title('Op.3-2Wedding March'))

    def test_catalogue_and_literal_variant_are_preserved(self):
        self.assertIn('BWV1008', rules.semantic_title('BWV1008 Menuet 1'))
        self.assertEqual(rules.semantic_title('Allegro de Sonate, Op.17 a'), '奏鸣曲快板乐章，作品17（原题标记：a）')
        self.assertEqual(rules.semantic_title('1103-14 Estudio'), '1103-14 练习曲')
        self.assertEqual(rules.semantic_title('K147 Sonata'), 'K147 奏鸣曲')
        self.assertEqual(rules.semantic_title('Minueto a'), '小步舞曲（原题标记：a）')
        self.assertEqual(rules.semantic_title('Op.9 Variations brillantes pour la guitare ou deux guitares'), '作品9：华丽变奏曲（为吉他或二把吉他而作）')

    def test_unknown_prose_does_not_pass_as_complete_grammar(self):
        self.assertIsNone(rules.semantic_title('Op.12 A book of apparently mysterious memories'))
        self.assertIsNone(rules.semantic_title('Sinfonia'))

    def test_ambiguous_b_key_is_not_guessed(self):
        self.assertIsNone(rules.semantic_title('Sonate B-dur'))
        self.assertIsNone(rules.semantic_title('Sonate H-moll'))


class FrozenPartitionGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = json.loads((ROOT / 'work/title-review/2026-10-03/cglib.json').read_text())
        cls.asset = json.loads((HERE / 'cglib_decisions.json').read_text())

    def test_complete_scope_and_exact_identity(self):
        self.assertEqual(self.asset['schema_version'], 1)
        entries = self.asset['entries']
        self.assertEqual(len(entries), 16544)
        self.assertEqual(len({x['id'] for x in entries}), len(entries))
        for before, after in zip(self.corpus, entries):
            self.assertEqual((after['id'], after['original'], after['original_composer']),
                             (before['id'], before['original'], before['composer']))

    def test_semantic_decision_and_evidence_on_every_row(self):
        for row in self.asset['entries']:
            self.assertIn(row['status'], {'reference', 'reviewed', 'retained'})
            self.assertTrue(row['reason'])
            self.assertTrue(row['reviewer'])
            self.assertTrue(row['review_method'])
            self.assertEqual(row['zh'].count('《'), 1)
            self.assertEqual(row['zh'].count('》'), 1)
            if row['status'] != 'retained':
                self.assertRegex(row['zh'], '[\u3400-\u9fff]')
            if row['status'] == 'reviewed':
                self.assertTrue(row['source_refs'])
            for url in row['source_refs']:
                self.assertTrue(url.startswith('https://'))

    def test_retained_title_is_full_original(self):
        for row in self.asset['entries']:
            if row['status'] == 'retained':
                original = row['original']
                if original.startswith('《') and original.endswith('》'):
                    original = original[1:-1]
                self.assertEqual(row['zh'], '《' + original.replace('《', '〈').replace('》', '〉') + '》')


if __name__ == '__main__':
    unittest.main()
