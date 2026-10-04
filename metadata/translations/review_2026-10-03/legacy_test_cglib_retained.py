"""Music-semantic regressions for the independent retained-title re-review."""
import json
import re
import unittest
from pathlib import Path
from legacy_validate_decisions import errors

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
SRC=json.loads((ROOT/'work/title-review/2026-10-03/cglib-retained-pass/legacy.json').read_text())['entries'][:2200]
CORPUS={r['id']:r for r in json.loads((ROOT/'work/title-review/2026-10-03/cglib.json').read_text())}
ENTRIES=json.loads((HERE/'cglib_retained_legacy_supplement.json').read_text())['entries']


class CglibRetainedReview(unittest.TestCase):
    def test_full_exact_source_display_and_numbers(self):
        self.assertEqual(len(ENTRIES),2200)
        self.assertEqual([r['id'] for r in SRC],[e['id'] for e in ENTRIES])
        self.assertFalse(errors([CORPUS[r['id']] for r in SRC],ENTRIES))

    def test_study_is_not_scientific_research(self):
        self.assertIn('练习曲',ENTRIES[817]['zh'])
        self.assertNotIn('研究',ENTRIES[817]['zh'])
        self.assertIn('如歌曲',ENTRIES[1709]['zh'])

    def test_song_bwv_does_not_replace_literal_source_incipit(self):
        self.assertIn('让我们欢喜跳跃',ENTRIES[499]['zh'])
        self.assertIn('BWV140',ENTRIES[499]['zh'])
        self.assertIn('未凭BWV编号替换',ENTRIES[499]['reason'])

    def test_author_roles_not_merged(self):
        self.assertEqual(ENTRIES[1274]['original_composer'],'Gounod. Charles')
        self.assertIn('Franz Schubert',ENTRIES[1274]['original'])
        self.assertIn('角色或归属冲突',ENTRIES[1274]['reason'])
        self.assertEqual(ENTRIES[1979]['original_composer'],'Llobet. Miguel Soles')

    def test_optional_guitar_and_or_instruments(self):
        self.assertIn('第2吉他可选',ENTRIES[83]['zh'])
        self.assertIn('小提琴或长笛',ENTRIES[1762]['zh'])
        self.assertIn('（原标二重奏）',ENTRIES[803]['zh'])

    def test_movement_count_layers_and_manuscript_markers(self):
        self.assertIn('第1音乐会组曲，第3首',ENTRIES[1634]['zh'])
        self.assertIn('第4首：马祖卡',ENTRIES[1634]['zh'])
        self.assertIn('作品2a2',ENTRIES[1714]['zh'])
        self.assertIn('作品24第1—2号：第1号',ENTRIES[1539]['zh'])

    def test_ambiguous_pure_short_names_retained_exact(self):
        for i in (28,33,72,189,333,1050,1512,1806,1826,2184):
            self.assertEqual(ENTRIES[i]['status'],'retained')
            self.assertEqual(ENTRIES[i]['zh'],SRC[i]['original'])
            self.assertTrue(ENTRIES[i]['reason'])

    def test_old_music_false_friends(self):
        self.assertIn('集锦曲',ENTRIES[3]['zh'])
        self.assertIn('中提琴',ENTRIES[1258]['zh'])
        self.assertIn('六弦组',ENTRIES[1592]['zh'])
        self.assertIn('琶音',ENTRIES[671]['zh'])
        self.assertIn('施蒂里亚',ENTRIES[156]['zh'])

    def test_title_marks_counts_and_no_artificial_han(self):
        for e in ENTRIES:
            if e['status']=='reference':self.assertRegex(e['display_zh'],r'[\u3400-\u9fff]')
        self.assertEqual(ENTRIES[1333]['status'],'retained')

    def test_external_music_context_is_reference_not_official_chinese(self):
        for i in (138,272,1916,2120):
            self.assertEqual(ENTRIES[i]['status'],'reference')
            self.assertTrue(ENTRIES[i]['source_refs'])
        self.assertIn('霍罗波',ENTRIES[1916]['zh'])


if __name__=='__main__':unittest.main()
