import json,re,unittest
from pathlib import Path
import build_cglib_archive_owner_tail_supplement as b
class TailTitleReviewTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.entries=json.loads((b.HERE/'cglib_retained_archive_owner_tail_supplement.json').read_text())['entries'];cls.by={e['id']:e for e in cls.entries};cls.rows={r['id']:r for r in b.ROWS}
 def test_600_full_original_attribution_display_guards(self):
  self.assertEqual(len(self.entries),600);self.assertEqual(set(self.by),set(self.rows))
  for e in self.entries:
   r=self.rows[e['id']];self.assertEqual(e['original'],r['original']);self.assertEqual(e['original_composer'],r['composer']);self.assertEqual(e['display_original'],r['display_original']);self.assertTrue(e['reason']);self.assertTrue(e['source_refs'])
   self.assertIn(e['status'],{'reference','retained'})
 def test_balanced_reference_titles_and_no_machine(self):
  for e in self.entries:
   z=e['display_zh'];self.assertEqual(z.count('《'),1);self.assertEqual(z.count('》'),1);self.assertEqual(z.count('〈'),z.count('〉'));self.assertEqual(z.count('（'),z.count('）'))
   if e['status']=='reference':self.assertRegex(z,'[\u4e00-\u9fff]')
   else:self.assertEqual(e['zh'],b.marked(self.rows[e['id']]['original']))
 def test_source_authorship_and_arranger_not_swapped(self):
  self.assertEqual(self.by['cglib:21332']['original_composer'],'Foden. William')
  self.assertIn('J.H. Payne',self.by['cglib:21332']['original']);self.assertIn('Wm. Foden',self.by['cglib:21332']['display_zh'])
  self.assertIn('William Fōden',self.by['cglib:21356']['original']);self.assertIn('六重唱',self.by['cglib:21356']['display_zh'])
  self.assertIn('J. C. Kirchner',self.by['cglib:21364']['original']);self.assertIn('Auguste Bartels',self.by['cglib:21365']['original'])
 def test_numbered_themes_and_source_number_units(self):
  self.assertIn('第1主题',self.by['cglib:19860']['display_zh']);self.assertIn('第2主题',self.by['cglib:19860']['display_zh']);self.assertIn('第1号',self.by['cglib:20066']['display_zh']);self.assertIn('第2号',self.by['cglib:20066']['display_zh'])
  self.assertIn('1876年12月4日',self.by['cglib:2106']['display_zh']);self.assertIn('六弦或七弦',self.by['cglib:21289']['display_zh'])
 def test_terms_and_repeated_source_notes_are_clean(self):
  self.assertIn('嘲鸫',self.by['cglib:21340']['display_zh']);self.assertIn('琉特琴',self.by['cglib:21296']['display_zh']);self.assertIn('轮舞',self.by['cglib:20029']['display_zh'])
  for i in ['21311','21366']:self.assertNotIn('重复',self.by['cglib:'+i]['display_zh']);self.assertIn('重复',self.by['cglib:'+i]['reason'])
if __name__=='__main__':unittest.main()
