"""Read-only PDF/MXL/MIDI completion of the separately frozen expansion scope."""
from __future__ import annotations

from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import unicodedata
import zipfile

from catalog_instrumentation import _check_review, _check_asset, _PRIVATE_TEXT, per_record_guard
from review_musescore_expansion import BASE, _digest, expansion_kind, review_mxl_scope, reviewed_cases, validate_reviewed_case, bounded_results
from score_instrumentation import read_mxl_evidence, read_mxl_view_sequences, read_midi_evidence
from score_pdf_evidence import read_pdf_evidence
from score_midi_crosscheck import read_sounding_midi, crosscheck, _mxl_ports
from source_adapters.musescore import EMAIL, CONTACT_LABEL
from source_adapters.pdmx_formats import _xml, _tag


FORMATS = {"PDF": ("pdf", "pdf"), "MUSICXML": ("mxl", "mxl"), "MIDI": ("mid", "mid")}
GENERIC_TITLES = {"untitled", "untitled score", "score", "full score", "musescore", "title", "new score",
                  "partitura", "partition", "without title", "unbenannt", "未命名", "无标题", "無標題"}
TEMPO = re.compile(r"(?:allegro|allegretto|andante|andantino|moderato|adagio|largo|lento|presto|vivace)(?:\s+(?:con|molto|poco|ma|non|troppo|sostenuto|espressivo|mosso|rubato|cantabile|brio))*", re.I)


def _text(value):
    return " ".join(unicodedata.normalize("NFKC", html.unescape(value)).split()).strip()


def _title_key(value):
    return "".join(char for char in _text(value).casefold() if char.isalnum())


def _public_safe(value):
    return (isinstance(value, str) and bool(value.strip()) and len(value) <= 1800
            and not EMAIL.search(value) and not CONTACT_LABEL.search(value) and not _PRIVATE_TEXT.search(value)
            and not any(ord(char) < 32 and char not in "\n\t" for char in value))


def public_part_labels(mxl_evidence):
    labels, omitted = [], 0
    for part in mxl_evidence["parts"]:
        raw = part.get("name", "")
        value = " ".join(raw.split()) if isinstance(raw, str) else ""
        if not value:
            labels.append("〈未标名称〉")
        elif _public_safe(value):
            labels.append(value)
        else:
            omitted += 1
            labels.append("〈原标注含联系或定位信息，公共页省略〉")
    joined = "；".join(labels)
    if len(joined) > 1800:
        return {"text": "分部原标注较长，完整转录保留于文件核验记录。", "omitted_private_labels": omitted,
                "long_label_list_omitted": True}
    return {"text": joined, "omitted_private_labels": omitted, "long_label_list_omitted": False}


def read_mxl_title_evidence(path, evidence):
    with zipfile.ZipFile(path) as archive:
        root = _xml(archive.read(evidence["validation"]["score_member"]), "MXL title evidence")
    work_titles, movement_titles, credits = [], [], []
    for node in root:
        tag = _tag(node)
        if tag == "work":
            for item in node:
                if _tag(item) == "work-title":
                    work_titles.append("".join(item.itertext()))
        elif tag == "movement-title":
            movement_titles.append("".join(node.itertext()))
        elif tag == "credit":
            kinds = ["".join(item.itertext()) for item in node if _tag(item) == "credit-type"]
            for item in node:
                if _tag(item) == "credit-words":
                    credits.append({"types": kinds, "text": "".join(item.itertext()), "attributes": dict(item.attrib), "page": node.get("page")})
    return {"work_titles": work_titles, "movement_titles": movement_titles, "credits": credits,
            "file_sha256": evidence["file_sha256"],
            "boundary": "Internal MusicXML headings may be stale template text and do not alone establish a PDF/native-title conflict."}


def _pdf_headings(pdf):
    pages = pdf.get("page_evidence", [])
    if not pages:
        return {"titles": [], "candidates": [], "confidence": "unavailable"}
    first = pages[0]
    width, height = first.get("size", [600, 800])
    span = first.get("geometry", {}).get("first_system_span")
    cutoff = min(height * .28, span[0] - 8) if span else height * .24
    candidates = []
    for row in first.get("text_lines", []):
        value, box = _text(row.get("text", "")), row.get("bbox")
        if not value or not box or box[1] >= cutoff or box[3] <= 0:
            continue
        if not any(char.isalpha() for char in value) or len(value) > 600:
            continue
        if re.search(r"copyright|all rights reserved", value, re.I):
            continue
        if expansion_kind(value) or TEMPO.fullmatch(value) or re.fullmatch(r"(?:arr(?:anged)?\.?|transcribed|edited|music|composed|by)\b.*", value, re.I):
            continue
        if _text(value).casefold() in GENERIC_TITLES or re.fullmatch(r"[\d\W]+", value):
            continue
        center = (box[0] + box[2]) / 2
        if not width * .15 <= center <= width * .85:
            continue
        candidates.append({"text": value, "bbox": box, "height": box[3] - box[1],
                           "public_text_safe": _public_safe(value)})
    if not candidates:
        return {"titles": [], "candidates": [], "confidence": "unavailable"}
    maximum = max(row["height"] for row in candidates)
    selected = sorted([row for row in candidates if row["height"] >= maximum * .84], key=lambda row: (row["bbox"][1], row["bbox"][0]))[:4]
    return {"titles": list(dict.fromkeys(row["text"] for row in selected)), "candidates": candidates,
            "confidence": "printed_header_geometry", "boundary": "Header selection is evidence extraction, not authoritative work-name certification."}


def review_file_title(source_title, mxl_titles, pdf):
    """Keep exact printed headings and distinguish conflict from absent evidence."""
    headings = _pdf_headings(pdf)
    actual = headings["titles"]
    mxl_actual = [value for value in mxl_titles.get("work_titles", []) + mxl_titles.get("movement_titles", []) if isinstance(value, str) and value.strip()]
    mxl_actual.extend(row["text"] for row in mxl_titles.get("credits", []) if "title" in row.get("types", []) and row.get("text", "").strip())
    keys = [_title_key(value) for value in actual]
    joined = _title_key(" ".join(actual))
    source = _title_key(source_title)
    notes = []
    if not actual:
        status = "insufficient_file_title"
    elif source in keys or source == joined:
        status = "consistent"
    elif source and any(len(key) >= 8 and (key in source or source in key) for key in keys + [joined]):
        status = "compatible_title_variant"
    else:
        status = "identity_conflict"
    if actual and mxl_actual and not any(_title_key(value) in keys + [joined] for value in mxl_actual):
        notes.append("MXL_internal_title_differs_from_printed_PDF")
    return {"status": status, "source_title": source_title, "actual_pdf_titles": actual,
            "actual_mxl_titles": list(dict.fromkeys(mxl_actual)), "pdf_heading_evidence": headings,
            "notes": notes, "boundary": "Frozen native ID/locators are preserved; a conflicting title is never silently relabelled or asserted to be the same composition."}


def review_midi_name_correspondence(classification, playback):
    roles = {row["part_id"]: row for row in classification["roles"]}
    observations, conflicts = [], []
    for group in playback["sounding_groups"]:
        names = group.get("track_names", [])
        named = {expansion_kind(value) for value in names if isinstance(value, str) and value.strip()}
        named.discard(None)
        expected = {roles[identity]["kind"] for identity in group.get("MXL_part_ids", []) if identity in roles}
        # A percussion kit can have an instrument/sound name per patch.
        named = {"percussion" if value in {"drumset", "glockenspiel", "marimba", "xylophone", "cajon", "bongos", "cymbal", "bass_drum", "snare_drum", "triangle", "tambourine", "castanets", "wood_blocks", "congas"} else value for value in named}
        expected = {"percussion" if value in {"drumset", "glockenspiel", "marimba", "xylophone", "cajon", "bongos", "cymbal", "bass_drum", "snare_drum", "triangle", "tambourine", "castanets", "wood_blocks", "congas"} else value for value in expected}
        issue = bool(named and expected and not named <= expected)
        row = {"track_names": names, "named_kinds": sorted(named), "MXL_part_ids": group.get("MXL_part_ids", []),
               "MXL_role_kinds": sorted(expected), "status": "conflict" if issue else "consistent"}
        observations.append(row)
        if issue:
            conflicts.append(row)
    return {"status": "unresolved_conflict" if conflicts else "consistent", "observations": observations, "conflicts": conflicts,
            "boundary": "Track names and note-on programs are checked separately; track counts never establish performers."}


def _require_full_native_guard(case, work):
    if case.get("native_record_sha256") != per_record_guard(work):
        raise ValueError("exact label explanation requires a complete native record guard")


def _used_instrument_name(part):
    declarations = part.get("score_instruments", [])
    used = set(part.get("used_instrument_ids", []))
    notes = part.get("note_count", 0)
    explicit_notes = sum(part.get("note_instrument_counts", {}).values())
    if notes <= 0 or (len(declarations) > 1 and explicit_notes != notes):
        raise ValueError("MIDI instrument-name correction requires unambiguous actual note assignment")
    if len(declarations) == 1 and not used:
        used = {declarations[0]["id"]}
    selected = [row for row in declarations if row["id"] in used]
    if len(selected) != 1 or used != {selected[0]["id"]}:
        raise ValueError("MIDI instrument-name correction requires one actual used declaration")
    name = selected[0].get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("MIDI instrument-name correction requires its literal original name")
    return name


def _apply_midi_name_corrections(case, work, mxl, classification, automatic, *, midi_sha256, pdf_sha256, instrument_names):
    """Explain only exact inherited names for explicitly corrected actual parts.

    This does not change the MIDI playback crosscheck, role kinds, raw names, or
    any unrelated name conflict. A requested but unmatched correction is stale.
    """
    key = "midi_instrument_name_corrections" if instrument_names else "midi_part_name_corrections"
    if case is None or key not in case:
        return deepcopy(automatic)
    validate_reviewed_case(case, work, mxl)
    if instrument_names:
        _require_full_native_guard(case, work)
    identities = case[key]
    if (not isinstance(identities, list) or not identities
            or any(not isinstance(identity, str) or not identity for identity in identities)
            or len(identities) != len(set(identities))):
        raise ValueError("MIDI part-name corrections require unique explicit part IDs")
    for key, actual in (("midi_sha256", midi_sha256), ("pdf_sha256", pdf_sha256)):
        if (not isinstance(case.get(key), str) or not re.fullmatch(r"[0-9a-f]{64}", case[key])
                or case[key] != actual):
            raise ValueError("MIDI part-name correction exact byte guard mismatch: " + key)
    parts = {part["part_id"]: part for part in mxl["parts"]}
    roles = {role["part_id"]: role for role in classification["roles"]}
    if len(parts) != len(mxl["parts"]) or len(roles) != len(classification["roles"]):
        raise ValueError("MIDI part-name correction has ambiguous actual part identities")
    original_names = {}
    for identity in identities:
        decision = case.get("part_decisions", {}).get(identity, {})
        role = roles.get(identity, {})
        if (identity not in parts or not isinstance(parts[identity].get("name"), str)
                or not parts[identity]["name"].strip() or decision.get("resolved") is not True
                or not decision.get("kind") or decision["kind"] == "unknown"
                or role.get("kind") != decision["kind"] or role.get("sounding") is not True
                or decision.get("role_active") is False):
            raise ValueError("MIDI part-name correction lacks an exact resolved active role: " + identity)
        original_names[identity] = _used_instrument_name(parts[identity]) if instrument_names else parts[identity]["name"]
    result, matched = deepcopy(automatic), set()
    targets = set(identities)
    for row in result["observations"]:
        relevant = set(row["MXL_part_ids"]) & targets
        if not relevant:
            continue
        identity = next(iter(relevant))
        names = row["track_names"]
        if (row["MXL_part_ids"] != [identity] or not isinstance(names, list) or not names
                or any(not isinstance(value, str) or not value.strip()
                       or value != original_names[identity] for value in names)
                or row["status"] != "conflict"):
            raise ValueError("MIDI part-name correction does not match an exact inherited-name conflict: " + identity)
        original = deepcopy(row)
        row.update(status="explained_inherited_instrument_name" if instrument_names else "explained_inherited_template_name", automatic_observation=original,
            correction_basis="exact_reviewed_part_and_MIDI_PDF_bytes",
            corrected_part_id=identity, corrected_kind=roles[identity]["kind"])
        matched.add(identity)
    if matched != targets:
        raise ValueError("MIDI part-name correction contains an unmatched part ID")
    result["conflicts"] = [row for row in result["observations"] if row["status"] == "conflict"]
    result.update(status="unresolved_conflict" if result["conflicts"] else "explained_name_difference",
        automatic_review=deepcopy(automatic.get("automatic_review", automatic)), review_basis="exact_guarded_semantic_review",
        review_note=case["note"], review_references=deepcopy(case["basis"]),
        midi_sha256=midi_sha256, pdf_sha256=pdf_sha256)
    return result


def apply_midi_part_name_corrections(case, work, mxl, classification, automatic, *, midi_sha256, pdf_sha256):
    return _apply_midi_name_corrections(case, work, mxl, classification, automatic,
        midi_sha256=midi_sha256, pdf_sha256=pdf_sha256, instrument_names=False)


def apply_midi_instrument_name_corrections(case, work, mxl, classification, automatic, *, midi_sha256, pdf_sha256):
    return _apply_midi_name_corrections(case, work, mxl, classification, automatic,
        midi_sha256=midi_sha256, pdf_sha256=pdf_sha256, instrument_names=True)


def _fresh_attack_correspondences(case, mxl, *, mxl_path, midi_path, midi_sha256):
    declarations = case.get("midi_attack_correspondence_review", [])
    if not declarations:
        if "midi_attack_correspondence_review" in case:
            raise ValueError("empty MIDI attack correspondence review")
        return {}
    if not isinstance(declarations, list) or mxl_path is None or midi_path is None:
        raise ValueError("MIDI attack correspondence requires actual guarded files")
    from score_mxl_playback_correspondence import match_pitched_attacks
    proofs = {}
    for row in declarations:
        if (not isinstance(row, dict) or set(row) != {"part_id", "track_index", "track_name", "proof_sha256"}
                or not isinstance(row["part_id"], str) or row["part_id"] in proofs
                or type(row["track_index"]) is not int or row["track_index"] < 0
                or not isinstance(row["track_name"], str) or not row["track_name"].strip()
                or not re.fullmatch(r"[0-9a-f]{64}", str(row["proof_sha256"]))):
            raise ValueError("invalid exact MIDI attack correspondence declaration")
        proof = match_pitched_attacks(mxl_path, midi_path, part_id=row["part_id"],
            track_index=row["track_index"], track_name=row["track_name"])
        digest = hashlib.sha256(json.dumps(proof, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        if (proof["mxl_sha256"] != mxl["file_sha256"] or proof["midi_sha256"] != midi_sha256
                or proof["status"] != "complete" or proof["unmatched_attacks"] != 0
                or digest != row["proof_sha256"]):
            raise ValueError("fresh MIDI attack correspondence differs from exact reviewed proof")
        proofs[row["part_id"]] = proof
    return proofs


def apply_midi_channel_collision_review(case, work, mxl, classification, automatic, *, midi_sha256, pdf_sha256,
                                      mxl_path=None, midi_path=None):
    """Explain a guarded export defect without claiming repaired playback.

    Only complete, exact conflicting groups can be explained. A distinct named
    track must actually issue the program on the affected shared port/channel;
    the target's total note-ons must equal its complete notation note count, or
    a separately guarded fresh match must explain every attack through explicit
    repeats, ties and printed trills. No source MIDI bytes are changed.
    """
    key = "midi_channel_collision_review"
    if case is None or key not in case:
        return deepcopy(automatic)
    validate_reviewed_case(case, work, mxl)
    _require_full_native_guard(case, work)
    if (case.get("pdf_sha256") != pdf_sha256 or case.get("midi_sha256") != midi_sha256
            or any(not re.fullmatch(r"[0-9a-f]{64}", str(value)) for value in (pdf_sha256, midi_sha256))):
        raise ValueError("MIDI channel collision exact file guard mismatch")
    decisions = case[key]
    def group_digest(group):
        return hashlib.sha256(json.dumps(group, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    if (not isinstance(decisions, list) or not decisions
            or any(not isinstance(row, dict) or set(row) not in (
                       {"part_id", "origin_part_id", "group_sha256"},
                       {"part_id", "origin_part_id", "group_sha256", "origin_track_names"})
                   or any(not isinstance(row.get(field), str) or not row[field] for field in ("part_id", "origin_part_id"))
                   or not re.fullmatch(r"[0-9a-f]{64}", str(row.get("group_sha256", ""))) for row in decisions)):
        raise ValueError("MIDI channel collision requires exact unique group decisions")
    targets = {row["group_sha256"]: row for row in decisions}
    conflicts = automatic.get("conflicts", [])
    if (len(targets) != len(decisions) or automatic.get("status") != "unresolved_conflict"
            or len(conflicts) != len(targets) or {group_digest(row) for row in conflicts} != set(targets)):
        raise ValueError("MIDI collision decisions do not cover exact current conflicts")
    parts = {row["part_id"]: row for row in mxl["parts"]}
    roles = {row["part_id"]: row for row in classification["roles"]}
    groups = automatic["sounding_groups"]
    attack_proofs = _fresh_attack_correspondences(case, mxl, mxl_path=mxl_path, midi_path=midi_path,
        midi_sha256=midi_sha256)
    if not set(attack_proofs) <= {row["part_id"] for row in decisions}:
        raise ValueError("MIDI attack proof does not target a reviewed channel conflict")
    for group in conflicts:
        decision = targets[group_digest(group)]
        target, source = decision["part_id"], decision["origin_part_id"]
        if (target == source or target not in parts or source not in parts
                or any(roles.get(identity, {}).get("sounding") is not True
                       or roles[identity].get("kind") in {None, "unknown"} for identity in (target, source))
                or group not in groups or group.get("MXL_part_ids") != [target]
                or group.get("matching_basis") != "exact_track_name_and_MXL_channel"
                or not group.get("track_names") or any(name.strip() != parts[target]["name"].strip() for name in group["track_names"])
                or group.get("channel_1based") == 10 or group.get("program_0based") in group.get("MXL_programs", [])
                or type(group.get("note_on_count")) is not int or group["note_on_count"] <= 0):
            raise ValueError("MIDI collision lacks one exact corresponding named role")
        target_groups = [row for row in groups if target in row.get("MXL_part_ids", [])]
        count = parts[target].get("note_count")
        if target in attack_proofs:
            proof = attack_proofs[target]
            if (proof["track_index"] != group.get("track")
                    or group.get("track_names") != [proof["track_name"]]
                    or any(row.get("track") != proof["track_index"] for row in target_groups)):
                raise ValueError("MIDI attack proof does not cover the exact target track")
            count = proof["midi_attacks_matched"]
        if (any(row.get("MXL_part_ids") != [target] for row in target_groups)
                or sum(row["note_on_count"] for row in target_groups) != count):
            raise ValueError("MIDI collision notation/target note counts differ")
        origins = group.get("program_origin_tracks", [])
        if len(origins) != 1:
            raise ValueError("MIDI collision requires one actual program origin")
        origin = origins[0]
        origin_groups = [row for row in groups if row.get("track") == origin.get("track")]
        expected_origin_names = [parts[source]["name"]]
        if "origin_track_names" in decision:
            expected_origin_names = decision["origin_track_names"]
            source_decision = case.get("part_decisions", {}).get(source, {})
            if (target not in attack_proofs or not isinstance(expected_origin_names, list)
                    or len(expected_origin_names) != 1 or not isinstance(expected_origin_names[0], str)
                    or not expected_origin_names[0].strip() or source_decision.get("resolved") is not True
                    or source_decision.get("kind") != roles[source]["kind"]):
                raise ValueError("exact differing origin track name requires a resolved role and attack proof")
        if (origin.get("track") == group.get("track") or not origin_groups
                or any(row.get("MXL_part_ids") != [source] for row in origin_groups)
                or any(origin.get(field) != group.get(field) for field in ("port", "channel_1based", "program_0based"))
                or not origin.get("track_names")
                or (origin.get("track_names") != expected_origin_names if "origin_track_names" in decision
                    else any(name.strip() != parts[source]["name"].strip() for name in origin["track_names"]))):
            raise ValueError("MIDI collision program origin does not bind a distinct actual role")
    result = deepcopy(automatic)
    for row in result["sounding_groups"]:
        if group_digest(row) in targets:
            original = deepcopy(row)
            row.update(status="explained_channel_collision", automatic_observation=original,
                reason="exact_reviewed_cross_track_channel_setup_export_defect")
    result.update(status="explained_playback_export_defect", conflicts=[], automatic_review=deepcopy(automatic),
        review_basis="exact_native_PDF_MXL_MIDI_and_complete_conflict_groups", review_note=case["note"],
        review_references=deepcopy(case["basis"]), midi_sha256=midi_sha256, pdf_sha256=pdf_sha256)
    if attack_proofs:
        result["complete_target_attack_correspondences"] = attack_proofs
    return result


def review_pdf_instrument_labels(classification, pdf):
    known = {row["kind"] for row in classification["roles"]}
    observations, conflicts = [], []
    for item in pdf.get("first_system_instrument_labels", []):
        kind = expansion_kind(item.get("text", ""))
        issue = bool(kind and kind not in known)
        row = {**item, "kind": kind, "status": "unrepresented_named_instrument" if issue else "consistent" if kind else "untyped_label"}
        observations.append(row)
        if issue:
            conflicts.append(row)
    return {"status": "unresolved_conflict" if conflicts else "consistent", "observations": observations, "conflicts": conflicts,
            "boundary": "Missing printed labels or staff geometry do not establish missing players; all-rest MXL placeholders are still represented in this comparison."}


def apply_pdf_noninstrument_labels(case, work, mxl, automatic, *, pdf_sha256):
    if case is None or "pdf_noninstrument_labels" not in case:
        return deepcopy(automatic)
    validate_reviewed_case(case, work, mxl)
    _require_full_native_guard(case, work)
    if (not isinstance(case.get("pdf_sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", case["pdf_sha256"]) or case["pdf_sha256"] != pdf_sha256):
        raise ValueError("PDF lyric explanation exact byte guard mismatch")
    labels = case["pdf_noninstrument_labels"]
    if not isinstance(labels, list) or not labels:
        raise ValueError("PDF lyric explanation requires explicit nonempty labels")
    seen, result = set(), deepcopy(automatic)
    for label in labels:
        if (not isinstance(label, dict) or set(label) != {"text", "bbox", "note"}
                or not isinstance(label["text"], str) or not label["text"].strip()
                or not isinstance(label["note"], str) or not label["note"].strip()
                or not isinstance(label["bbox"], list) or len(label["bbox"]) != 4
                or any(type(value) not in (int, float) or not math.isfinite(value) for value in label["bbox"])):
            raise ValueError("PDF lyric explanation requires literal text, exact geometry and a note")
        identity = (label["text"], tuple(label["bbox"]))
        if identity in seen:
            raise ValueError("duplicate PDF lyric explanation")
        seen.add(identity)
        matches = [row for row in result["observations"] if row.get("text") == label["text"] and row.get("bbox") == label["bbox"]]
        if (len(matches) != 1 or matches[0].get("status") != "unrepresented_named_instrument"
                or matches[0] not in automatic["conflicts"]):
            raise ValueError("PDF lyric explanation does not match one actual instrument conflict")
        row = matches[0]
        original = deepcopy(row)
        row.update(status="explained_lyric_text", automatic_observation=original, explanation_note=label["note"])
    result["conflicts"] = [row for row in result["observations"] if row["status"] == "unrepresented_named_instrument"]
    result.update(status="unresolved_conflict" if result["conflicts"] else "explained_noninstrument_text",
        automatic_review=deepcopy(automatic), review_basis="exact_guarded_semantic_review",
        review_note=case["note"], review_references=deepcopy(case["basis"]), pdf_sha256=pdf_sha256)
    return result


def make_projection(work, classification, mxl_evidence, title_review, asset_guards, *, playback=None):
    export_defect = playback is not None and playback.get("status") == "explained_playback_export_defect"
    uncertain = classification["status"] != "mxl_scope_verified" or title_review["status"] == "identity_conflict" or export_defect
    review = {key: deepcopy(classification.get(key)) for key in (
        "instrumentation", "instrumentation_zh", "topic_id", "guitar_player_count", "ensemble_player_count")}
    review["status"] = "file_reviewed_uncertain" if uncertain else "file_verified"
    review["summary"] = ("MXL记谱、PDF谱面及MIDI播放声明均已核对；演奏人数或记谱视图关系仍有具体边界，未强定人数。" if classification["status"] != "mxl_scope_verified" else
                         "MXL记谱角色与PDF、MIDI交叉核对；标准谱／TAB及播放音轨分别处理。")
    if classification.get("omitted_empty_parts"):
        review["summary"] += f" {len(classification['omitted_empty_parts'])}条空置或已确认辅助层未额外计人数。"
    if any(part.get("lyric_count", 0) for part in mxl_evidence["parts"]):
        review["summary"] += " 谱面歌词字段已保留，未据此另加歌者人数。"
    if export_defect:
        review["summary"] += " MIDI导出存在已核明的共享通道音色设置冲突，播放音色可能受合并顺序影响；谱面编制按PDF与MXL保留，原MIDI未作修复。"
    case = classification.get("reviewed_case")
    if isinstance(case, dict) and case.get("part_decisions"):
        note = case.get("public_note")
        if note is not None and note != "":
            if not _public_safe(note):
                raise ValueError("invalid public instrumentation review note")
            review["summary"] += " " + note
    labels = public_part_labels(mxl_evidence)
    review["file_part_labels"] = labels["text"]
    if labels["omitted_private_labels"]:
        review["summary"] += " 部分分部原标注含联系或定位信息，公共页省略，私有证据完整保留。"
    review["source_difference"] = "实际文件补全编制，原始来源声明保留。" if work.get("metadata", {}).get("instrumentation") != review["instrumentation"] else ""
    if title_review["status"] == "identity_conflict":
        safe_titles = [value for value in title_review["actual_pdf_titles"] if _public_safe(value)]
        if safe_titles:
            joined = " / ".join(safe_titles)
            if _public_safe(joined):
                review["file_title"] = joined
        review["file_identity_note"] = "实际PDF谱题与来源题名不一致；来源原题保留，未确认是同一作品。"
        if len(safe_titles) != len(title_review["actual_pdf_titles"]):
            review["file_identity_note"] += " 实际谱题含联系或定位信息，公共页省略，完整证据保留于私有核验记录。"
        review["summary"] += " 实际谱题与来源题名的关联存在冲突。"
        if review["topic_id"] in {"solo", "duo", "trio", "quartet", "guitar_ensemble"}:
            review["topic_id"] = "guitar_unspecified"
    if review["status"] == "file_reviewed_uncertain" and review["topic_id"] in {"solo", "duo", "trio", "quartet", "guitar_ensemble"}:
        review["topic_id"] = "guitar_unspecified"
        review["guitar_player_count"], review["ensemble_player_count"] = None, None
    guarded = deepcopy(work)
    guarded.setdefault("metadata", {})["scope_status"] = "accepted_actual_file_review"
    _check_review(guarded, review)
    return {**{key: work[key] for key in ("id", "title_en", "composer_en", "source_url")},
            "assets": deepcopy(asset_guards), "review": review}


def apply_identity_review(case, work, mxl, pdf_sha256, automatic):
    if case is None:
        return deepcopy(automatic)
    validate_reviewed_case(case, work, mxl)
    if case.get("pdf_sha256") is not None and case["pdf_sha256"] != pdf_sha256:
        raise ValueError("exact semantic PDF identity guard mismatch")
    override = case.get("identity_review_override")
    if override is None:
        return deepcopy(automatic)
    statuses = {"consistent", "compatible_title_variant", "insufficient_file_title", "identity_conflict"}
    if not isinstance(override, dict) or override.get("status") not in statuses:
        raise ValueError("invalid exact file-title semantic decision")
    actual = override.get("actual_pdf_titles", override.get("actual_file_titles", automatic["actual_pdf_titles"]))
    if not isinstance(actual, list) or any(not isinstance(value, str) or not value.strip() for value in actual):
        raise ValueError("actual reviewed file titles must be literal strings")
    return {**deepcopy(automatic), "status": override["status"], "actual_pdf_titles": deepcopy(actual),
            "automatic_review": deepcopy(automatic), "review_basis": "exact_guarded_semantic_review",
            "review_note": case["note"], "review_references": deepcopy(case["basis"])}


def _guard_format(root, asset, label):
    extension = FORMATS[label][1]
    if (not isinstance(asset, dict) or asset.get("format") != label or asset.get("status") != "verified"
            or type(asset.get("size")) is not int or asset["size"] <= 0
            or not isinstance(asset.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", asset["sha256"])):
        raise ValueError("verified actual format asset required: " + label)
    expected = f"sources/musescore/objects/{asset['sha256']}.{extension}"
    if asset.get("local_path") != expected:
        raise ValueError("unexpected verified object path")
    path = root / expected
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ValueError("actual file path escapes library")
    if _digest(path) != {"sha256": asset["sha256"], "size": asset["size"]}:
        raise ValueError("actual file digest/size disagrees: " + label)
    return path


def validate_extraction_journal(journal, label, *, plan_ids, accepted_ids, plan_sha256, configuration_sha256):
    """Allow exact accepted-only or all-plan private extraction scopes, never a partial superset."""
    plan_ids, accepted_ids = set(plan_ids), set(accepted_ids)
    scope_ids = journal.get("scope_ids")
    records = journal.get("records")
    if (not accepted_ids <= plan_ids or not isinstance(scope_ids, list)
            or any(not isinstance(identity, str) for identity in scope_ids)
            or len(scope_ids) != len(set(scope_ids)) or not isinstance(records, dict)):
        raise ValueError("format extraction scope/plan incomplete: " + label)
    actual_ids = set(scope_ids)
    allowed_scopes = [plan_ids] if label == "MUSICXML" else [accepted_ids, plan_ids]
    if (journal.get("status") != "complete" or journal.get("plan_sha256") != plan_sha256
            or journal.get("format") != label or journal.get("configuration_sha256") != configuration_sha256
            or actual_ids not in allowed_scopes or set(records) != actual_ids):
        raise ValueError("format extraction scope/plan incomplete: " + label)


def _review_final_record(job):
    root, identity, work, acquired, scope_record, config_files, case = job
    unavailable = {label: row for label, row in acquired.items() if row.get("status") != "verified"}
    if unavailable:
        return {"status": "pending", "reason": "missing_verified_format", "formats": unavailable}
    assets = {label: row["asset"] for label, row in acquired.items()}
    paths = {label: _guard_format(root, asset, label) for label, asset in assets.items()}
    guards = {label: {key: asset[key] for key in ("sha256", "size")} for label, asset in assets.items()}
    for label, asset in assets.items():
        code = FORMATS[label][0]
        locator = work["metadata"]["pdmx_csv_transcription"][code]
        expected_member = locator[2:] if locator.startswith("./") else locator
        if asset.get("archive_member") != expected_member or asset.get("archive_sha256") != config_files[code + ".tar.gz"]["sha256"]:
            raise ValueError("actual file publication/native locator guard differs: " + identity + "/" + label)
    if scope_record.get("asset_guard") != assets["MUSICXML"]:
        raise ValueError("MXL scope asset snapshot changed")
    try:
        mxl = read_mxl_evidence(paths["MUSICXML"])
        if mxl != scope_record["mxl_evidence"]:
            raise ValueError("actual MXL evidence changed")
        has_tab = any(row.get("sign") == "TAB" for part in mxl["parts"] for row in part.get("clefs", []))
        sequences = read_mxl_view_sequences(paths["MUSICXML"]) if has_tab else None
        if case is not None:
            validate_reviewed_case(case, work, mxl)
            if case.get("pdf_sha256") is not None and case["pdf_sha256"] != assets["PDF"]["sha256"]:
                raise ValueError("semantic review PDF byte guard mismatch")
        actual_scope = review_mxl_scope(mxl, sequences, source_record=work, reviewed_case=case)
        if actual_scope != {key: scope_record[key] for key in ("status", "reason", "classification")}:
            raise ValueError("actual MXL scope decision changed")
        pdf = read_pdf_evidence(paths["PDF"])
        midi_notation = read_midi_evidence(paths["MIDI"])
        midi = read_sounding_midi(paths["MIDI"])
        playback = crosscheck(mxl, midi, ports=_mxl_ports(paths["MUSICXML"], mxl), source_instrumentation=work["metadata"]["instrumentation"])
        playback = apply_midi_channel_collision_review(case, work, mxl, actual_scope["classification"], playback,
            midi_sha256=assets["MIDI"]["sha256"], pdf_sha256=assets["PDF"]["sha256"],
            mxl_path=paths["MUSICXML"], midi_path=paths["MIDI"])
        automatic_names = review_midi_name_correspondence(actual_scope["classification"], playback)
        names = apply_midi_part_name_corrections(case, work, mxl, actual_scope["classification"], automatic_names,
            midi_sha256=assets["MIDI"]["sha256"], pdf_sha256=assets["PDF"]["sha256"])
        names = apply_midi_instrument_name_corrections(case, work, mxl, actual_scope["classification"], names,
            midi_sha256=assets["MIDI"]["sha256"], pdf_sha256=assets["PDF"]["sha256"])
        automatic_pdf_labels = review_pdf_instrument_labels(actual_scope["classification"], pdf)
        pdf_labels = apply_pdf_noninstrument_labels(case, work, mxl, automatic_pdf_labels, pdf_sha256=assets["PDF"]["sha256"])
        mxl_titles = read_mxl_title_evidence(paths["MUSICXML"], mxl)
        automatic_title = review_file_title(work["title_en"], mxl_titles, pdf)
        title_review = apply_identity_review(case, work, mxl, assets["PDF"]["sha256"], automatic_title)
        private = {"scope_classification": actual_scope["classification"], "pdf_evidence": pdf,
                   "mxl_title_evidence": mxl_titles, "file_title_review": title_review,
                   "midi_note_evidence": midi_notation, "sounding_midi_evidence": midi,
                   "midi_crosscheck": playback, "midi_name_review": names,
                   "pdf_instrument_review": pdf_labels, "asset_guards": deepcopy(assets)}
        if playback["status"] == "unresolved_conflict" or names["status"] == "unresolved_conflict":
            return {"status": "pending", "reason": "unresolved_midi_correspondence", **private}
        if pdf_labels["status"] == "unresolved_conflict":
            return {"status": "pending", "reason": "unresolved_pdf_instrument_correspondence", **private}
        projection = make_projection(work, actual_scope["classification"], mxl, title_review, guards, playback=playback)
        native = deepcopy(work)
        native["assets"] = list(assets.values())
        native["metadata"]["scope_status"] = "accepted_actual_file_review"
        for label in FORMATS:
            _check_asset(root, native, label, guards[label])
        return {"status": "accepted", "reason": "three_format_review_complete", "projection": projection, **private}
    except (ValueError, RuntimeError, OSError) as error:
        return {"status": "pending", "reason": "cross_format_review_failed", "error": str(error), "asset_guards": deepcopy(assets)}


def review_final(root, *, workers=4):
    if type(workers) is not int or not 1 <= workers <= 4:
        raise ValueError("final workers must be between 1 and 4")
    root = Path(root).resolve()
    input_paths = {"plan": root / BASE / "plan.json", "scope_review": root / BASE / "scope-review.json",
                   "configuration": root / "config/musescore_pdmx_expansion.json"}
    input_paths.update({label: root / BASE / (code + "-extraction.json") for label, (code, _) in FORMATS.items()})
    raw_inputs = {name: path.read_bytes() for name, path in input_paths.items()}
    values = {name: json.loads(raw) for name, raw in raw_inputs.items()}
    plan, scope, config = values["plan"], values["scope_review"], values["configuration"]
    cases, case_guard = reviewed_cases(root)
    if plan.get("status") != "prepared" or scope.get("status") != "complete" or scope.get("review_stage") != "mxl_scope_only":
        raise ValueError("complete frozen scope and prepared native plan required")
    plan_sha = hashlib.sha256(raw_inputs["plan"]).hexdigest()
    if plan.get("configuration_sha256") != hashlib.sha256(raw_inputs["configuration"]).hexdigest():
        raise ValueError("final review configuration differs from prepared plan")
    if scope.get("inputs", {}).get("plan", {}).get("sha256") != plan_sha:
        raise ValueError("scope no longer belongs to the native plan")
    if scope.get("inputs", {}).get("mxl_extraction", {}).get("sha256") != hashlib.sha256(raw_inputs["MUSICXML"]).hexdigest():
        raise ValueError("scope MXL extraction input changed")
    if scope.get("inputs", {}).get("reviewed_cases") != case_guard:
        raise ValueError("semantic review asset changed; rerun actual-MXL scope review")
    for name, guard in scope["inputs"]["methods"].items():
        if _digest(root / name) != guard:
            raise ValueError("scope method changed before final review: " + name)
    works = {work["id"]: work for work in plan["works"]}
    accepted_ids = set(scope["accepted_ids"])
    if len(works) != len(plan["works"]) or not accepted_ids <= set(works):
        raise ValueError("scope native identities changed")
    if not set(cases) <= set(works):
        raise ValueError("semantic reviewed identity is outside the expansion plan")
    for label in FORMATS:
        validate_extraction_journal(values[label], label, plan_ids=works, accepted_ids=accepted_ids,
            plan_sha256=plan_sha, configuration_sha256=plan["configuration_sha256"])
    methods = ["scripts/review_musescore_expansion_final.py", "scripts/review_musescore_expansion.py",
               "scripts/score_instrumentation.py", "scripts/score_pdf_evidence.py", "scripts/score_midi_crosscheck.py",
               "scripts/review_musescore_instrumentation.py", "scripts/source_adapters/pdmx_formats.py",
               "scripts/catalog_instrumentation.py", "scripts/score_mxl_playback_correspondence.py"]
    method_guards = {name: _digest(root / name) for name in methods}
    identities = sorted(accepted_ids, key=lambda value: int(value.split(":")[1]))
    jobs = ((root, identity, works[identity], {label: values[label]["records"][identity] for label in FORMATS},
             scope["records"][identity], config["files"], cases.get(identity)) for identity in identities)
    records = {}
    if workers == 1:
        for index, job in enumerate(jobs):
            records[identities[index]] = _review_final_record(job)
            if len(records) % 50 == 0:
                print(json.dumps({"cross_format_reviewed": len(records), "total": len(accepted_ids)}), flush=True)
    else:
        with ProcessPoolExecutor(max_workers=workers, mp_context=get_context("spawn")) as executor:
            for index, row in bounded_results(executor, _review_final_record, jobs, limit=workers * 2):
                records[identities[index]] = row
                if len(records) % 50 == 0:
                    print(json.dumps({"cross_format_reviewed": len(records), "total": len(accepted_ids)}), flush=True)
    records = {identity: records[identity] for identity in identities}
    projections = [row["projection"] for row in records.values() if row["status"] == "accepted"]
    if any(path.read_bytes() != raw_inputs[name] for name, path in input_paths.items()):
        raise ValueError("final review input changed while reading files")
    if any(_digest(root / name) != guard for name, guard in method_guards.items()):
        raise ValueError("final review method changed while reading files")
    if reviewed_cases(root)[1] != case_guard:
        raise ValueError("exact semantic review asset changed during final review")
    report = {"schema_version": 1, "status": "complete", "review_stage": "actual_pdf_mxl_midi",
              "checked_at": datetime.now(timezone.utc).isoformat(), "works": projections, "records": records,
              "inputs": {name: {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)} for name, raw in raw_inputs.items()},
              "methods": method_guards,
              "reviewed_cases": case_guard,
              "summary": {"scope_accepted": len(accepted_ids), "new_three_format_records": len(projections),
                          "statuses": dict(Counter(row["status"] for row in records.values())),
                          "reasons": dict(Counter(row["reason"] for row in records.values())),
                          "topics": dict(Counter(row["review"]["topic_id"] for row in projections)),
                          "review_statuses": dict(Counter(row["review"]["status"] for row in projections)),
                          "file_title_statuses": dict(Counter(row["file_title_review"]["status"] for row in records.values() if "file_title_review" in row))},
              "limitations": ["Notation roles are not software tracks/staves/program counts.",
                              "Structural checks and playback correspondence do not certify note-for-note import fidelity or acoustic performance.",
                              "Conflicting printed titles retain native source identities and visible uncertainty; absent file headings are recorded separately."]}
    destination = root / BASE / "final-review.json"
    temporary = destination.with_name(destination.name + ".part")
    if destination.is_symlink() or temporary.is_symlink():
        raise ValueError("final review destination cannot be a symlink")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, destination)
    return report
