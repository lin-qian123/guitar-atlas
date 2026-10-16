from copy import deepcopy

import pytest

from verify_library_classification import compare_classified_public
from verify_musescore_instrumentation import AuditFailure


def _pair(*, topic="solo", evidence="approved_source_category", topic_mapping=None,
          topic_category_names=None, family="pure"):
    topic_category_names = topic_category_names or {
        "22": "For 7-string guitar (arr)",
        "26": "For guitar (arr)",
    }
    topic_mapping = topic_mapping or {topic: ["26"]}
    categories = [{"id": cid, "source_id": "imslp", "name": name, "family": family}
                  for cid, name in topic_category_names.items()]
    previous = {
        "id": "imslp:8410",
        "source_id": "imslp",
        "source_record_id": "8410",
        "title_en": "Reviewed work",
        "category_ids": ["22", "26"],
        "details": {"instrumentation": "Guitar"},
        "topic_ids": [topic],
        "topic_evidence": {topic: evidence},
        "topic_category_ids": topic_mapping,
        "local_editions": [{"category_id": "22", "files": []}],
    }
    before = {"categories": categories, "works": [previous]}
    after = deepcopy(before)
    return before, after


def test_existing_solo_adds_only_approved_seven_string_category_membership():
    before, after = _pair()
    after["works"][0]["topic_category_ids"]["solo"] = ["22", "26"]

    result = compare_classified_public(before, after, {})

    assert result["approved_category_membership_repairs"] == 1
    assert after["works"][0]["topic_ids"] == ["solo"]
    assert after["works"][0]["topic_category_ids"] == {"solo": ["22", "26"]}


def test_numeric_twelve_guitar_category_adds_ensemble_and_replaces_only_fallback():
    before, after = _pair(
        topic="unspecified",
        evidence="no_exact_instrumentation_evidence",
        topic_mapping={"unspecified": ["12"]},
        topic_category_names={"12": "For 12 guitars (arr)"},
    )
    before["works"][0]["category_ids"] = ["12"]
    before["categories"][0]["family"] = "pure"
    after = deepcopy(before)
    after["works"][0].update(
        topic_ids=["guitar_ensemble"],
        topic_evidence={"guitar_ensemble": "approved_source_category"},
        topic_category_ids={"guitar_ensemble": ["12"]},
    )

    result = compare_classified_public(before, after, {})

    assert result["approved_category_membership_repairs"] == 1
    assert after["works"][0]["topic_ids"] == ["guitar_ensemble"]


def test_unreviewed_membership_changes_and_nonpure_numeric_labels_fail_closed():
    before, after = _pair(topic_category_names={"22": "For 7-string guitar", "26": "For guitar"},
                          family="mixed")
    after["works"][0]["topic_category_ids"]["solo"] = ["22", "26"]

    with pytest.raises(AuditFailure, match="unreviewed public field changed"):
        compare_classified_public(before, after, {})


def test_unreviewed_mapping_entry_fails_closed():
    before, after = _pair(topic_category_names={"26": "For guitar (arr)"})
    before["works"][0]["category_ids"] = ["26"]
    after = deepcopy(before)
    after["works"][0]["topic_category_ids"]["solo"] = ["26", "999"]

    with pytest.raises(AuditFailure, match="unreviewed public field changed"):
        compare_classified_public(before, after, {})
