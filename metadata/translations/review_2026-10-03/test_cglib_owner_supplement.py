import collections,json,re,unittest
from pathlib import Path
import build_cglib_owner_supplement as b

class OwnerTitleReviewTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.rows={r['id']:r for r in b.ROWS}
  cls.entries=json.loads((b.HERE/'cglib_owner_retained_supplement.json').read_text())['entries']
  cls.by={e['id']:e for e in cls.entries}
 def test_all_2757_exact_guards_and_complete_decisions(self):
  self.assertEqual(len(self.entries),2757);self.assertEqual(set(self.by),set(self.rows))
  for e in self.entries:
   r=self.rows[e['id']];self.assertEqual(e['original'],r['original']);self.assertEqual(e['original_composer'],r['composer'])
   self.assertIn(e['status'],{'reference','retained'});self.assertTrue(e['reason']);self.assertTrue(e['review_method'])
   if e['status']=='reference':
    self.assertEqual(e['display_original'],r['display_original']);self.assertRegex(e['display_zh'],r'[\u4e00-\u9fff]')
   else:
    self.assertEqual(e['zh'],b.cg.wrap(r['original']));self.assertNotIn('孤立题名',e['reason'])
 def test_balanced_title_enclosures(self):
  for e in self.entries:
   if e['status']=='reference':
    z=e['display_zh'];self.assertEqual(z.count('《'),1);self.assertEqual(z.count('》'),1);self.assertEqual(z.count('〈'),z.count('〉'));self.assertEqual(z.count('('),z.count(')'));self.assertEqual(z.count('（'),z.count('）'))
 def test_by_inside_title_and_two_titles_preserved(self):
  self.assertEqual(self.by['cglib:47742']['display_zh'],'《永远在你身边》')
  z=self.by['cglib:57953']['display_zh'];self.assertIn('Chopin',z);self.assertIn('Zimmermann',z);self.assertIn('蒂罗尔',z)
 def test_numbers_and_scoring_not_conflated(self):
  self.assertIn('原题标记1719',self.by['cglib:48028']['display_zh']);self.assertNotIn('第1719',self.by['cglib:48028']['display_zh'])
  self.assertIn('第3曲',self.by['cglib:48920']['display_zh']);self.assertNotIn('三声部',self.by['cglib:48920']['display_zh'])
  self.assertIn('六首独奏曲与六首二重奏曲',self.by['cglib:51130']['display_zh']);self.assertNotIn('分谱',self.by['cglib:51130']['display_zh'])
 def test_whole_instrument_clauses_not_false_part_suffixes(self):
  self.assertIn('七首吉他小前奏曲',self.by['cglib:56013']['display_zh']);self.assertIn('长笛或小提琴分谱',self.by['cglib:50806']['display_zh']);self.assertIn('六首吉他随想曲',self.by['cglib:56041']['display_zh'])
 def test_deterministic_rebuild_decisions(self):
  for r in b.ROWS:self.assertEqual(b.decision(r),self.by[r['id']])
if __name__=='__main__':unittest.main()
