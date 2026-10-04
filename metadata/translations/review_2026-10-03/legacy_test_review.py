"""Focused regressions for complete-title review and source preservation."""
import copy,json,unittest
from pathlib import Path
from legacy_build_decisions import decision,wrapped,rossini
from legacy_closed_review import outer
from legacy_validate_decisions import errors,balanced,number_values
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]

def row(original,zh,composer='Test, Full Name'):
    return dict(id='test:1',source_id='test',original=original,composer=composer,zh=zh,status='reference',basis='fixture',reason='fixture',display_original=original,display_zh=zh)

class CompleteTitleReviewTests(unittest.TestCase):
    def test_separate_inner_titles_survive_wrapping(self):
        title='〈少女的祈祷〉与〈纯洁如雪〉'
        self.assertEqual(outer(title),title)
        self.assertEqual(wrapped(title),'《'+title+'》')
        self.assertTrue(balanced(wrapped(title)))
        self.assertEqual(outer('《〈武装的人〉弥撒中的〈赞美颂〉》'),'〈武装的人〉弥撒中的〈赞美颂〉')

    def test_guards_reject_different_source_text(self):
        r=row('Study','《练习曲》');e=decision(r)
        changed=copy.deepcopy(e);changed['original_composer']='Another Person'
        self.assertIn(('source guard','test:1'),errors([r],[changed]))

    def test_number_and_key_omissions_are_detected(self):
        r=row('3 Etudes in A minor, Op.12','《3首A小调练习曲，作品12》');e=decision(r)
        e['zh']='《3首B小调练习曲》'
        failures=errors([r],[e])
        self.assertTrue(any(f[0]=='number preservation' for f in failures))
        self.assertTrue(any(f[0]=='key preservation' for f in failures))

    def test_names_do_not_consume_music_forms_or_comma_instruments(self):
        examples=[('Study','《练习曲》'),('Minueto in A minor','《A小调小步舞曲》'),('Trio for Violin, Viola and Guitar','《小提琴、中提琴与吉他三重奏》')]
        for original,expected in examples:
            with self.subTest(original=original):self.assertEqual(decision(row(original,expected))['zh'],expected)

    def test_conventional_name_needs_complete_attribution(self):
        self.assertEqual(decision(row('Julia Florida','《朱莉娅·佛罗里达》','Barrios Mangoré, Agustín'))['zh'],'《花样的朱莉娅》')
        other=decision(row('Julia Florida','《朱莉娅·佛罗里达》','Other, Composer'))
        self.assertEqual((other['status'],other['zh']),('retained','Julia Florida'))

    def test_rossiniana_opus_guard_and_roman_movement(self):
        r=row('Op. 119 Rossiniana No. 1 III. (Maestoso)','《罗斯尼亚纳》','Mauro Giuliani')
        self.assertEqual(rossini(r)['zh'],'罗西尼主题幻想曲第1号，作品119，III：庄严地')
        self.assertIsNone(rossini(row('Rossiniana No.1, Op.131','《罗斯尼亚纳》','Munier, Carlo')))

    def test_ambiguous_title_is_retained_verbatim(self):
        r=row('Bribes No.1','《贿赂一号》','Cooper, Valiha Nicéphore');e=decision(r)
        self.assertEqual(e['status'],'retained');self.assertEqual(e['zh'],r['original'])
        self.assertTrue('法语' in e['reason'] or '歧义' in e['reason'])

    def test_numeric_audit_understands_double_instrument_and_meter(self):
        self.assertFalse(number_values('Trio for 2 Guitars, Op.2')-number_values('《双吉他三重奏，作品2》',True))
        self.assertFalse(number_values('Amusement in 2/4')-number_values('《二四拍消遣曲》',True))
        self.assertEqual(number_values('I puritani'),{})

    def test_frozen_corpus_has_all_guarded_decisions(self):
        rows=sum((json.loads((ROOT/'work/title-review/2026-10-03'/f'{s}.json').read_text()) for s in ('imslp','classclef')),[])
        entries=json.loads((HERE/'legacy_decisions.json').read_text())['entries']
        self.assertEqual(len(entries),18133);self.assertEqual(errors(rows,entries),[])

if __name__=='__main__':unittest.main()
