"""Pure identity validation for append-only PDMX actual-file review.

This route intentionally does not decide whether a record belongs in the guitar
library. It preserves native declarations and returns a pending record for a
separate review of the publication files. No network or filesystem I/O occurs.
The historical adapter and its frozen 924 records are not changed.
"""
from __future__ import annotations

from copy import deepcopy
import re

from audit_pdmx_scope import metadata_identity_evidence
from catalog_display import musescore_display_text
from source_adapters.musescore import (
    EMAIL, LICENSES, _composer, _csv, _id, _instrumentation, _true, csv_serialization,
)


def _exact_boolean(value, expected: bool) -> bool:
    return value is expected or (isinstance(value, str) and value == str(expected))


def validate_candidate(csv_row, metadata) -> tuple[dict | None, str, dict]:
    """Return a native-preserving pending record, rejection reason and evidence.

    A successful result establishes historical row/identity/license consistency
    only. GM programs, a guitar word, lyrics elements and source instrument
    labels never establish actual guitar scope or performer counts here.
    """
    evidence = {"schema_version": 1, "route": "pdmx_append_actual_file_review",
                "status": "rejected", "scope_status": "pending_actual_file_review"}

    def reject(reason):
        evidence["reason"] = reason
        return None, reason, evidence

    if not isinstance(csv_row, dict) or not isinstance(metadata, dict):
        return reject("invalid_metadata_shape")
    data, mirror = metadata.get("data"), metadata.get("score")
    if not isinstance(data, dict) or not isinstance(data.get("score"), dict) or not isinstance(mirror, dict):
        return reject("missing_source_score")
    score = data["score"]
    if metadata.get("status_code") != 200:
        return reject("unsuccessful_metadata_snapshot")
    native_id = _id(score.get("id"))
    match = re.fullmatch(r"\./metadata/[0-9]+/([1-9][0-9]*)\.json", _csv(csv_row.get("metadata")))
    evidence["native_identity"] = {
        "csv_metadata_locator": deepcopy(csv_row.get("metadata")),
        "source_id": deepcopy(score.get("id")), "mirror_id": deepcopy(mirror.get("id")),
    }
    if not native_id or not match or match[1] != native_id or _id(mirror.get("id")) != native_id:
        return reject("native_id_mismatch")
    title, raw_composer = score.get("title"), score.get("composer_name")
    if not isinstance(title, str) or not title.strip():
        return reject("missing_source_title")
    if raw_composer is not None and not isinstance(raw_composer, str):
        return reject("invalid_source_composer")
    identity = metadata_identity_evidence(metadata)
    evidence["identity"] = identity
    if not identity["title"]["equivalent"]:
        return reject("metadata_title_mismatch")
    if csv_serialization(title) != _csv(csv_row.get("title")):
        return reject("csv_title_mismatch")
    if csv_serialization(raw_composer) != _csv(csv_row.get("composer_name")):
        return reject("csv_composer_mismatch")
    if EMAIL.search(title) or re.search(r"https?://", title, re.I):
        return reject("private_contact_or_url_in_title")
    user = score.get("user")
    if not isinstance(user, dict) or not _id(user.get("id")):
        return reject("missing_source_uploader_identity")
    if not identity["pages"]["source_url_valid"]:
        return reject("invalid_source_url")
    if not identity["pages"]["equivalent"]:
        return reject("source_url_mismatch")
    if not identity["uploader_ids_agree"]:
        return reject("uploader_identity_mismatch")
    evidence["license"] = {"csv_license": deepcopy(csv_row.get("license")),
                           "source_license": deepcopy(score.get("license")),
                           "csv_license_url": deepcopy(csv_row.get("license_url")),
                           "source_license_url": deepcopy(data.get("license_url")),
                           "license_conflict": deepcopy(csv_row.get("license_conflict")),
                           "no_license_conflict_subset": deepcopy(csv_row.get("subset:no_license_conflict")),
                           "all_valid_subset": deepcopy(csv_row.get("subset:all_valid"))}
    if (not _exact_boolean(csv_row.get("license_conflict"), False)
            or not _exact_boolean(csv_row.get("subset:no_license_conflict"), True)):
        return reject("license_conflict")
    if not _exact_boolean(csv_row.get("subset:all_valid"), True):
        return reject("invalid_publication_subset")
    license_id = score.get("license")
    if not isinstance(license_id, str) or license_id not in LICENSES or _csv(csv_row.get("license")) != license_id:
        return reject("license_mismatch")
    license_url = data.get("license_url")
    if license_url != _csv(csv_row.get("license_url")):
        return reject("license_url_mismatch")
    if license_url != LICENSES[license_id][0]:
        return reject("unsupported_license_url")
    evidence["access"] = {
        "source_flags": {name: deepcopy(score.get(name)) for name in ("is_private", "is_draft", "is_official", "is_blocked")},
        "mirror_flags": {name: deepcopy(mirror.get(name)) for name in ("isPublic", "isBlocked")},
        "data_flags": {name: deepcopy(data.get(name)) for name in ("hidden", "is_blocked", "score_blocked_by_country")},
        "is_download_limited": deepcopy(data.get("is_download_limited")),
        "has_paywall": deepcopy(csv_row.get("has_paywall")), "paywall": deepcopy(data.get("paywall")),
    }
    for name in ("is_private", "is_draft", "is_official", "is_blocked"):
        if _true(score.get(name)):
            return reject(name)
    if mirror.get("isPublic") is False or _true(mirror.get("isBlocked")):
        return reject("private_or_blocked_snapshot")
    if any(_true(data.get(name)) for name in ("hidden", "is_blocked", "score_blocked_by_country")):
        return reject("restricted_snapshot")
    paywall, access_restrictions = data.get("paywall"), []
    if _true(data.get("is_download_limited")):
        access_restrictions.append("download_limit")
    if _true(csv_row.get("has_paywall")) or (isinstance(paywall, dict) and _true(paywall.get("has_instant_paywall"))):
        access_restrictions.append("paywall")
    evidence["lyrics"] = {"has_lyrics": deepcopy(csv_row.get("has_lyrics")),
                          "n_lyrics": deepcopy(csv_row.get("n_lyrics")),
                          "review_required": _true(csv_row.get("has_lyrics")) or _csv(csv_row.get("n_lyrics")) != "0"}
    instrument_score = dict(score)
    if isinstance(mirror.get("partNames"), list):
        native_parts = score.get("parts_names", [])
        if isinstance(native_parts, list):
            instrument_score["parts_names"] = list(native_parts) + mirror["partNames"]
    source_scope, source_reason = _instrumentation(instrument_score, title)
    evidence["source_instrumentation_outcome"] = source_reason
    evidence["source_instrumentation_declaration"] = deepcopy(source_scope)
    evidence["source_parts_names"] = deepcopy(score.get("parts_names"))
    evidence["mirror_parts_names"] = deepcopy(mirror.get("partNames"))
    evidence["scope_basis"] = "pending_actual_file_review"
    scope = deepcopy(source_scope) if source_scope is not None else {
        "instrumentation": "Guitar-related source declaration; file scope pending",
        "instrumentation_note": "Source declarations are retained; actual file scope remains pending.",
    }
    scope.update(guitar_player_count=None, instrumentation_basis="pending_actual_file_review", scope_status="pending_review")
    composer, role, responsibility_note, responsibility_fields = _composer(raw_composer)
    uploader = user.get("name")
    contributor = ("上传者：" + musescore_display_text(uploader) if isinstance(uploader, str) and uploader.strip()
                   and not EMAIL.search(uploader) and not re.search(r"https?://", uploader, re.I) else "")
    formats = sorted(label for field, label in (("pdf", "PDF"), ("mxl", "MUSICXML"), ("mid", "MIDI")) if _csv(csv_row.get(field)))
    normalized = {
        "id": "musescore:" + native_id, "title_en": title, "composer_en": composer,
        "source_url": score["url"], "category_ids": ["guitar"], "formats": formats,
        "resource_type": "score", "instrumentation_status": "unspecified",
        "assets": [{"format": label, "status": "metadata_only"} for label in formats],
        "metadata": {**scope, **responsibility_fields, "license": LICENSES[license_id][1], "license_url": license_url,
                     "source_license": license_id, "source_composer_attribution": raw_composer or "",
                     "source_title": title, "source_instruments": deepcopy(score.get("instruments", [])),
                     "source_instrumentations": deepcopy(score.get("instrumentations", [])),
                     "source_parts_names": deepcopy(score.get("parts_names", [])),
                     "source_parts": score.get("parts"), "source_uploader": deepcopy(user),
                     "pdmx_csv_transcription": deepcopy(csv_row),
                     "source_edition": "PDMX v9 · MuseScore 历史目录",
                     "collection": "PDMX v9 无许可冲突子集",
                     "availability": "来源页面现状未核；实际文件编制待核，尚无本地谱文件。",
                     "license_note": "按 PDMX 逐条历史许可和无冲突标记整理；实际文件范围与获取结果另核。",
                     "source_attribution_note": responsibility_note, "attribution_role": role,
                     "original_arrangement_status": "unspecified", "contributors": contributor,
                     "acquisition_status": "metadata_only", "detail_status": "historical_snapshot",
                     "historical_file_access_restrictions": access_restrictions},
    }
    if access_restrictions:
        normalized["metadata"]["availability"] += "源站历史文件访问受限。"
    if type(score.get("pages_count")) is int and score["pages_count"] > 0:
        normalized["metadata"]["pages"] = score["pages_count"]
    encoding_notes = []
    key = score.get("keysig")
    if isinstance(key, str) and key and not EMAIL.search(key) and not re.search(r"https?://", key, re.I):
        normalized["metadata"]["source_key"] = key
        normalized["metadata"]["key"] = musescore_display_text(key)
        if normalized["metadata"]["key"] != key:
            encoding_notes.append("来源调性显示按完整 UTF-8 字节序列从 Latin-1 错解可逆还原；原始转录保留私有档案。")
    if contributor and contributor != "上传者：" + uploader:
        encoding_notes.append("上传者名称显示按完整 UTF-8 字节序列从 Latin-1 错解可逆还原；来源上传者原文与原生身份保留私有档案。")
    if encoding_notes:
        normalized["metadata"]["text_quality_note"] = "；".join(encoding_notes)
    evidence.update(status="identity_license_access_validated", reason="pending_actual_file_review")
    return normalized, "pending_actual_file_review", evidence
