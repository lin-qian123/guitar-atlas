"""Actual-file recall supplements append exact IDs without replacing evidence."""
from copy import deepcopy

import pytest

from augment_pdmx_metadata_scope import append_candidates


def inputs():
    old = {"123": {"metadata": {"original": "verbatim"}, "csv": {"original": "verbatim"}}}
    snapshot = {"status": "complete", "records": deepcopy(old)}
    selected = {"456": {"metadata_member": "metadata/4/456.json", "csv_line": 2,
                         "csv": {"metadata": "./metadata/4/456.json"}}}
    metadata = {"complete": True, "records": {"456": {"raw": "Guitar"}}, "member_paths": {"456": "metadata/4/456.json"}}
    return old, snapshot, selected, metadata


def test_only_new_requested_native_record_is_appended():
    old, snapshot, selected, metadata = inputs()
    result, added = append_candidates(snapshot, selected, metadata)
    assert added == ["456"]
    assert result["records"]["123"] == old["123"]
    assert result["records"]["456"]["metadata"] == {"raw": "Guitar"}
    assert result["records"]["456"]["csv"]["metadata"] == "./metadata/4/456.json"


@pytest.mark.parametrize("mutation", ["changed_csv", "changed_member", "extra_record", "incomplete", "old_record"])
def test_stale_extra_or_existing_evidence_is_never_replaced(mutation):
    _, snapshot, selected, metadata = inputs()
    if mutation == "changed_csv": selected["456"]["csv"]["metadata"] = "./metadata/4/999.json"
    elif mutation == "changed_member": metadata["member_paths"]["456"] = "metadata/5/456.json"
    elif mutation == "extra_record": metadata["records"]["999"] = {}
    elif mutation == "incomplete": metadata["complete"] = False
    else: snapshot["records"]["456"] = {"preserved": True}
    before = deepcopy(snapshot)
    with pytest.raises(ValueError): append_candidates(snapshot, selected, metadata)
    assert snapshot == before
