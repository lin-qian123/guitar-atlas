"""Regressions for bibliography/music false friends and source guards."""
import json,re,unittest
from pathlib import Path
from legacy_validate_decisions import balanced,number_values
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
ROWS=json.loads((ROOT/'work/title-review/2026-10-03/archive-review/legacy-archive-tail-531.json').read_text())
ENTRIES=json.loads((HERE/'legacy_dga_tail_supplement.json').read_text())['entries']
BYID={e['id']:e for e in ENTRIES}

class DgaCompleteTitleTests(unittest.TestCase):
    def test_all_exact_source_and_display_guards(self):
        self.assertEqual(len(ENTRIES),531);self.assertEqual(len(BYID),531)
        for r,e in zip(ROWS,ENTRIES):
            self.assertEqual((e['id'],e['original'],e['original_composer'],e['display_original']),(r['id'],r['original'],r['composer'],r['display_original']))
            self.assertEqual(e['status'],'reference');self.assertTrue(e['reason']);self.assertTrue(e['basis'])

    def test_numeric_identifiers_and_balanced_title_marks(self):
        for r,e in zip(ROWS,ENTRIES):
            with self.subTest(id=e['id']):
                self.assertFalse(number_values(r['original'])-number_values(e['zh'],True))
                self.assertTrue(balanced(e['zh']));self.assertTrue(balanced(e['display_zh']))

    def test_ensemble_count_is_separate_from_work_count(self):
        for native_id in ('16379','16380','16381','19763'):
            e=BYID['dga:'+native_id];self.assertIn('3首',e['display_zh']);self.assertIn('四重奏',e['display_zh']);self.assertNotIn('三重奏',e['display_zh'])
        self.assertIn('第3号',BYID['dga:15183']['zh']);self.assertIn('二重奏',BYID['dga:15183']['zh'])

    def test_clef_is_not_a_key(self):
        found=0
        for e in ENTRIES:
            if re.search(r'Ch\.?\.?\s*(?:di|Di)\s+Sol|Chiave di Sol',e['original']):
                found+=1;self.assertIn('高音谱号',e['display_zh']);self.assertNotIn('G大调',e['display_zh'])
        self.assertGreater(found,30)

    def test_opera_sinfonia_does_not_change_independent_sinfonia(self):
        for native in ('15149','15156','15173'):self.assertIn('序曲',BYID['dga:'+native]['display_zh'])
        self.assertIn('Sinfonia',BYID['dga:15216']['display_zh']);self.assertNotIn('交响曲',BYID['dga:15216']['display_zh'])
        self.assertIn('Sinfonia',BYID['dga:15228']['display_zh'])

    def test_abbreviations_and_credits_are_not_title_words(self):
        for e in ENTRIES:
            self.assertNotRegex(e['display_zh'],r'百花香|花香|婴儿|只读存储器|骑兵|格林童话|法国吉他禁忌')
        self.assertIn('集锦曲',BYID['dga:4077']['zh'])

    def test_optional_instrument_is_explicit(self):
        self.assertIn('第2曼陀林声部可选',BYID['dga:18488']['zh'])
        self.assertIn('第2声部可选',BYID['dga:16814']['zh'])
        self.assertIn('无歌者时可由小提琴代奏',BYID['dga:19736']['zh'])

    def test_uncertain_source_characters_are_not_invented(self):
        self.assertIn('quarte libri',BYID['dga:17633']['original'])
        self.assertNotIn('4册',BYID['dga:17633']['display_zh'])
        self.assertIn('sda. ed.',BYID['dga:19519']['original'])
        self.assertNotIn('第2版',BYID['dga:19519']['display_zh'])
        self.assertIn('[Caprice]',BYID['dga:15174']['original'])

if __name__=='__main__':unittest.main()
