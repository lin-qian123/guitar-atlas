"""Semantic preservation regressions for the independently reviewed 357 titles."""
import copy
import unittest
from legacy_build_cglib_archive_tail import build
from legacy_validate_decisions import errors


class ArchiveTailReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows,cls.entries,_=build()

    def test_exact_source_attribution_display_guards(self):
        self.assertEqual(357,len(self.entries))
        self.assertEqual([],errors(self.rows,self.entries))
        changed=copy.deepcopy(self.entries)
        changed[75]['original_composer']='Moretti. Luigi'
        self.assertIn(('source guard','cglib:21629'),errors(self.rows,changed))

    def test_opera_collection_and_source_credit_are_distinct(self):
        r=self.entries[0]
        self.assertIn('歌剧主题集第3号',r['display_zh'])
        self.assertNotIn('评论',r['zh'])
        self.assertIn('贝利尼音乐',r['zh'])
        self.assertNotIn('贝利尼音乐',r['display_zh'])
        self.assertEqual('Mertz. Johann Kaspar',r['original_composer'])

    def test_flower_and_sequel_with_two_work_markings(self):
        self.assertIn('夜紫罗兰',self.entries[31]['zh'])
        r=self.entries[72]
        for s in ['矢车菊','夜紫罗兰','续集','吉他','作品5']:
            self.assertIn(s,r['display_zh'])
        self.assertIn('第5部作品',r['zh'])
        self.assertNotIn('第5部作品',r['display_zh'])
        self.assertEqual('reference',r['status'])
        self.assertGreaterEqual(len(r['source_refs']),3)

    def test_courses_not_strings_and_instrument_key_not_work_key(self):
        self.assertIn('六弦',self.entries[74]['display_zh'])
        self.assertIn('六组弦',self.entries[75]['display_zh'])
        self.assertNotIn('六弦',self.entries[75]['display_zh'])
        self.assertIn('C调单簧管',self.entries[88]['zh'])
        self.assertNotIn('C大调',self.entries[88]['zh'])
        self.assertIn('C调与E调',self.entries[256]['zh'])
        self.assertNotIn('大调',self.entries[256]['zh'])

    def test_source_variants_not_restored_from_catalogue_memory(self):
        self.assertIn('Troi',self.entries[206]['zh'])
        self.assertNotIn('3首',self.entries[206]['zh'])
        self.assertIn('作品34',self.entries[112]['zh'])
        self.assertIn('sic',self.entries[112]['zh'])
        self.assertIn('Ragozy',self.entries[204]['zh'])
        self.assertIn('Hujnady',self.entries[204]['zh'])
        self.assertIn('Schuman吉他',self.entries[106]['display_zh'])
        self.assertNotIn('舒曼',self.entries[106]['display_zh'])

    def test_arrangement_parts_not_new_concerto_identity(self):
        r=self.entries[355]
        self.assertIn('第1协奏曲',r['display_zh'])
        self.assertIn('钢琴声部',r['display_zh'])
        self.assertNotIn('第1钢琴协奏曲',r['display_zh'])
        self.assertIn('A. Diabelli',r['zh'])
        self.assertNotIn('A. Diabelli',r['display_zh'])
        for s in ['作品36','钢琴伴奏','钢琴声部']:
            self.assertIn(s,self.entries[356]['display_zh'])

    def test_movement_keys_accidentals_and_individual_numbers(self):
        for i,key in [(148,'降E大调'),(149,'G小调'),(150,'D大调'),
                      (157,'降A大调'),(158,'升C小调'),(160,'降E大调')]:
            self.assertIn(key,self.entries[i]['display_zh'])
        for no in [6,7,20]:
            self.assertIn(f'第{no}号',self.entries[146]['display_zh'])
        self.assertEqual(2,self.entries[139]['display_zh'].count('第2号'))
        self.assertIn('广板',self.entries[149]['display_zh'])
        self.assertIn('绵延的柔板',self.entries[158]['display_zh'])

    def test_total_and_selected_item_numbers_not_collapsed(self):
        for i,item in [(285,1),(286,2)]:
            self.assertIn('2首奏鸣曲',self.entries[i]['zh'])
            self.assertIn(f'{item}.',self.entries[i]['zh'])
        r=self.entries[263]['zh']
        for s in ['3首协奏三重奏','作品18第2号','低音声部']:
            self.assertIn(s,r)
        self.assertIn('作品46',self.entries[306]['zh'])
        self.assertIn('作品364',self.entries[306]['zh'])

    def test_ambiguous_robin_and_unexpanded_book_fields(self):
        r=self.entries[68]
        self.assertEqual('retained',r['status'])
        self.assertEqual('Robin',r['zh'])
        self.assertEqual('Robin',r['display_zh'])
        self.assertIn('人名',r['reason'])
        self.assertIn('知更鸟',r['reason'])
        self.assertIn('violone',self.entries[209]['display_zh'])
        self.assertIn('Total',self.entries[216]['zh'])
        self.assertNotIn('Total',self.entries[216]['display_zh'])
        self.assertIn('1888',self.entries[235]['zh'])
        self.assertNotIn('1888',self.entries[235]['display_zh'])

    def test_open_phrase_translation_and_music_study(self):
        for i in [185,188]:
            self.assertIn('当我清晨起床',self.entries[i]['display_zh'])
        self.assertIn('练习与乐趣',self.entries[304]['zh'])
        self.assertIn('练习曲',self.entries[307]['zh'])
        self.assertNotIn('研究',self.entries[307]['zh'])
        self.assertIn('忠贞之死',self.entries[329]['zh'])


if __name__=='__main__':unittest.main()
