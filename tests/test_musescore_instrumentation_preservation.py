"""Preservation guards reject attractive but stale or unrelated catalog changes."""
import copy
from pathlib import Path

import pytest

from verify_musescore_instrumentation import (
    AuditFailure, compare_public_works, compare_offline_works, check_local_link,
)


def work(identity='musescore:1'):
    return {'id':identity, 'source_id':identity.split(':')[0],
            'source_record_id':identity.split(':')[1], 'title_en':'Native title',
            'composer_en':'Native composer','source_url':'https://example.org/score/1',
            'category_ids':[7], 'formats':['MIDI','MUSICXML','PDF'],
            'translation_status':'retained','instrumentation_status':'source_declared',
            'details':{'instrumentation':'Guitar','license':'CC0','contributors':'Uploader'},
            'topic_ids':['guitar_unspecified','studies'],
            'topic_evidence':{'guitar_unspecified':'explicit_source_instrumentation','studies':'title_keyword'},
            'topic_category_ids':{'guitar_unspecified':[7],'studies':[7]}}


def reviewed(original):
    result=copy.deepcopy(original)
    result['instrumentation_status']='file_verified'
    result['details'].update(instrumentation='Guitar solo',instrumentation_zh='吉他独奏',
                             source_instrumentation='Guitar',instrumentation_review='Files checked',
                             guitar_player_count='1',ensemble_player_count='1')
    result['topic_ids']=['solo','studies']
    result['topic_evidence']={'solo':'file_crosscheck','studies':'title_keyword'}
    result['topic_category_ids']={'solo':[7],'studies':[7]}
    review={'status':'file_verified','topic_id':'solo','instrumentation':'Guitar solo',
            'instrumentation_zh':'吉他独奏','summary':'Files checked','source_difference':'',
            'guitar_player_count':1,'ensemble_player_count':1}
    return result, {original['id']:review}


def test_completed_review_changes_only_instrumentation_and_preserves_search_topics():
    before=work();after,reviews=reviewed(before)
    assert compare_public_works([before],[after],reviews)['musescore_records']==1
    after['topic_ids']=['solo']
    after['topic_evidence'].pop('studies');after['topic_category_ids'].pop('studies')
    with pytest.raises(AuditFailure,match='topic'):
        compare_public_works([before],[after],reviews)


def test_old_public_cannot_masquerade_as_new_file_review():
    before=work();_,reviews=reviewed(before)
    with pytest.raises(AuditFailure,match='review status'):
        compare_public_works([before],[before],reviews)


@pytest.mark.parametrize('field,value',[
    ('title_en','Changed title'),('source_record_id','2'),('category_ids',[8]),
    ('formats',['PDF']),('translation_status','reviewed'),
])
def test_native_identity_and_translation_fields_are_protected(field,value):
    before=work();after,reviews=reviewed(before);after[field]=value
    with pytest.raises(AuditFailure,match='protected work fields'):
        compare_public_works([before],[after],reviews)


def test_license_details_are_not_an_instrumentation_edit():
    before=work();after,reviews=reviewed(before);after['details']['license']='Other license'
    with pytest.raises(AuditFailure,match='non-instrumentation details'):
        compare_public_works([before],[after],reviews)


def test_unrelated_work_entire_record_is_protected():
    before=work('imslp:1');after=copy.deepcopy(before);after['details']['instrumentation']='Changed'
    with pytest.raises(AuditFailure,match='non-MuseScore'):
        compare_public_works([before],[after],{})


def test_every_previous_local_edition_including_midi_must_survive():
    before=work();new,reviews=reviewed(before)
    edition=[{'category_id':7,'files':[{'format':'MIDI','href':'scores/file.mid','label':'MIDI'}],
              'unavailable_count':0}]
    offline_before={**before,'local_editions':edition}
    offline_after={**new,'local_editions':copy.deepcopy(edition)}
    assert compare_offline_works([offline_before],[offline_after],[new])['local_file_members']==1
    offline_after['local_editions'][0]['files'][0]['href']='scores/other.mid'
    with pytest.raises(AuditFailure,match='local editions'):
        compare_offline_works([offline_before],[offline_after],[new])


@pytest.mark.parametrize('href',['../outside.pdf','%2e%2e/outside.pdf','https://example.org/file.pdf',
                                 '/absolute.pdf','scores/file.pdf?download=1','scores/%00.pdf'])
def test_local_link_guard_rejects_unsafe_navigation(tmp_path,href):
    with pytest.raises(AuditFailure):check_local_link(tmp_path,href,10)


def test_local_link_uses_current_manifest_byte_size(tmp_path):
    path=tmp_path/'score.pdf';path.write_bytes(b'%PDF-content')
    assert check_local_link(tmp_path,'score.pdf',len(b'%PDF-content'))['size']==12
    with pytest.raises(AuditFailure,match='byte-size'):
        check_local_link(tmp_path,'score.pdf',13)


def test_actual_part_labels_keep_duplicate_views_and_exact_original_spelling():
    before=work();after,reviews=reviewed(before)
    labels='Guitar 1；Guitar 1\n(Tablature)；〈未标名称〉'
    after['details']['file_part_labels']=labels
    reviews[before['id']]['file_part_labels']=labels
    assert compare_public_works([before],[after],reviews)['musescore_records']==1


@pytest.mark.parametrize('changed_labels',[
    None,
    'Guitar 1；〈未标名称〉',
    'Guitar 1；Guitar 1 (Tablature)；〈未标名称〉',
])
def test_actual_part_labels_cannot_be_dropped_deduplicated_or_normalized(changed_labels):
    before=work();after,reviews=reviewed(before)
    reviews[before['id']]['file_part_labels']='Guitar 1；Guitar 1\n(Tablature)；〈未标名称〉'
    if changed_labels is not None:
        after['details']['file_part_labels']=changed_labels
    with pytest.raises(AuditFailure,match='file_part_labels'):
        compare_public_works([before],[after],reviews)
