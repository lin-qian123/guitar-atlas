"""Publishing must fail for unreviewed fields, even with populated labels."""
import json
import pytest

from audit_translations import audit
from catalog_translations import translation_summary
from tests.basic_helpers import ROOT


def test_committed_translation_audit_detects_draft_missing_and_stale_counts():
    data=json.loads((ROOT/'public_site/data/catalog.json').read_text())
    work=data['works'][0]
    # A nonempty Chinese value does not prove review.
    work['translation']['title']={'status':'machine','basis':'draft','reason':''}
    work['translation_status']='machine'
    data['translation_summary']=translation_summary(data)
    result=audit(data)
    assert not result['ready']
    assert any(r['id']==work['id'] and r['field']=='title' for r in result['pending'])
    work['translation']['title']={'status':'untranslated','basis':'','reason':''}
    work['title_zh']=''
    work['translation_status']='untranslated'
    with pytest.raises(ValueError,match='summary is stale'):
        audit(data)
    data['translation_summary']=translation_summary(data)
    assert not audit(data)['ready']
