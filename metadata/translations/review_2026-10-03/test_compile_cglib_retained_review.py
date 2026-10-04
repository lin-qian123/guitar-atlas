"""Display titles must bind to the current full review corpus."""
import copy
import unittest

import compile_cglib_retained_review as compiler


class DisplayGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = compiler.current_cglib_corpus()
        cls.entries = compiler.read(compiler.ASSET)['entries']
        cls.root_entries = compiler.read(compiler.HERE / 'cglib_retained_root_supplement.json')['entries']

    def test_all_canonical_rows_against_current_full_corpus(self):
        self.assertEqual(len(self.entries), 16544)
        for entry in self.entries:
            compiler.guard(entry, self.corpus)

    def test_root557_display_titles_have_current_source_guard(self):
        self.assertEqual(len(self.root_entries), 557)
        for entry in self.root_entries:
            self.assertIn('display_zh', entry)
            self.assertEqual(entry['display_original'], self.corpus[entry['id']]['display_original'])
            compiler.guard(entry, self.corpus)

    def test_missing_guard_with_translated_display_title_is_rejected(self):
        entry = copy.deepcopy(self.root_entries[0])
        entry.pop('display_original')
        with self.assertRaisesRegex(AssertionError, 'display'):
            compiler.guard(entry, self.corpus)

    def test_stale_display_guard_is_rejected(self):
        entry = copy.deepcopy(self.root_entries[0])
        entry['display_original'] += ' changed'
        with self.assertRaisesRegex(AssertionError, 'display'):
            compiler.guard(entry, self.corpus)

    def test_empty_or_nonstring_display_text_is_rejected(self):
        for text in ('', '  ', None, 7):
            with self.subTest(text=text):
                entry = copy.deepcopy(self.root_entries[0])
                entry['display_zh'] = text
                with self.assertRaisesRegex(AssertionError, 'display text'):
                    compiler.guard(entry, self.corpus)

    def test_title_or_attribution_drift_remains_rejected(self):
        for field, error in (('original', 'original'), ('original_composer', 'composer')):
            entry = copy.deepcopy(self.root_entries[0])
            entry[field] += ' changed'
            with self.assertRaisesRegex(AssertionError, error):
                compiler.guard(entry, self.corpus)

    def test_absent_display_title_keeps_full_original_guard(self):
        entry = copy.deepcopy(self.root_entries[0])
        entry.pop('display_zh')
        entry.pop('display_original')
        compiler.guard(entry, self.corpus)


if __name__ == '__main__':
    unittest.main()
