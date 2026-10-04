import json,re,sys,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE))
import build_dga_10000_supplement as d
class ReviewTests(unittest.TestCase):
    def test_full_scope_guards_and_statuses(self):
        rows=json.loads(d.INPUT.read_text())+json.loads(d.EXTRA_INPUT.read_text())
        entries=json.loads((HERE/'dga_10000_supplement.json').read_text())['entries']
        self.assertEqual(len(entries),1632);self.assertEqual(len({x['id'] for x in entries}),1632)
        for r,e in zip(rows,entries):
            self.assertEqual((e['id'],e['original'],e['original_composer'],e['display_original']),(r['id'],r['original'],r['composer'],r['display_original']))
            self.assertIn(e['status'],('reference','retained'));self.assertTrue(e['reason']);self.assertTrue(e['review_method'])
            for url in e['source_refs']:self.assertTrue(url.startswith('https://'))
            if e['status']=='retained':self.assertEqual(e['zh'],d.cg.wrap(r['original']));self.assertFalse(e['display_zh'])
            else:
                self.assertRegex(e['display_zh'],r'[\u3400-\u9fff]')
                for a,b in [('《','》'),('〈','〉'),('（','）'),('(',')'),('[',']')]:self.assertEqual(e['display_zh'].count(a),e['display_zh'].count(b),(e['id'],e['display_zh']))
    def test_heading_clause_order_and_source_role(self):
        self.assertEqual(d.semantic("LE PRINTEMPS ÉTERNEL NOCTURNE A DEUX VOIX ÉGALES")[0],'永恒的春天——同声二部夜曲')
        self.assertEqual(d.semantic('Air de la Ruse d\'Amour')[0],'〈爱情的计谋〉中的曲调')
        self.assertEqual(d.semantic('No. 5 CENDRILLON Duo Chanté par Mme. Duret')[0],'第5号：灰姑娘二重奏')
    def test_author_in_source_field_is_never_composer_inference(self):
        row={'id':'dga:99999','original':'CENDRILLON Duo Chanté par Mme. Duret','composer':'','display_original':'CENDRILLON Duo','primary_candidates':[['CENDRILLON Duo','complete_display_title']]}
        e=d.decision(row);self.assertEqual(e['original_composer'],'');self.assertIn('二重唱',e['display_zh']);self.assertNotIn('Duret',e['display_zh'])
    def test_damaged_marks_and_real_course_editions(self):
        entries={x['id']:x for x in json.loads((HERE/'dga_10000_supplement.json').read_text())['entries']}
        self.assertNotIn('[',entries['dga:11726']['display_zh'])
        self.assertIn('第一课程第二卷',entries['dga:10540']['display_zh'])
        self.assertIn('第二课程第二卷',entries['dga:10541']['display_zh'])
        self.assertEqual(entries['dga:11258']['status'],'retained')
if __name__=='__main__':unittest.main()
