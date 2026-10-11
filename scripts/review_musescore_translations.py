#!/usr/bin/env python
"""Append guarded MuseScore display references without rebuilding other sources.

Only the accepted normalized catalog is reviewed. Existing exact title/full-name
references and the complete music-title grammar can supply Chinese display text.
Unknown names and titles retain their native wording; no machine service, source
discovery, file acquisition or cross-source identity relationship is performed.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from acquire_source_assets import atomic_json
from catalog_display import musescore_display_text, project_title, strip_authority_dates
from catalog_translations import HAN, checked_entry, display_source_title, wrap_display_title
from review_source_translations import TERMS
from title_translation_quality import terminology_grammar


ASSETS = ("source_titles_zh.json", "musicians_zh.json", "categories_zh.json")
SUPPORTED = {"reference", "reviewed"}
ATTRIBUTION_LABELS = {
    "Traditional": "传统音乐", "Trad.": "传统音乐", "Anonymous": "佚名",
    "Anon.": "佚名", "Various composers": "多位作曲家",
}
PARENTHESIZED_DATES = re.compile(r"\s*\(\s*\d{3,4}\s*[-–—]\s*(?:\d{3,4}|\?{1,2})?\s*\)\s*$")
ROLE_WORDS = {"arr", "arranged", "arranger", "edited", "editor", "transcribed", "transcriber",
              "composed", "composer", "by", "adapted", "performed", "performer"}


def full_name_key(original: str, *, musescore: bool = False) -> tuple[str, ...] | None:
    """A complete-name spelling reference, never a person or work identity key."""
    if musescore:
        original = musescore_display_text(original)
    text = PARENTHESIZED_DATES.sub("", strip_authority_dates(original)).strip()
    if (not text or not re.fullmatch(r"[\w\s,.'’\-]+", text)
            or any(character in text for character in "0123456789_")):
        return None
    folded = unicodedata.normalize("NFKD", text).casefold()
    folded = "".join(character for character in folded if not unicodedata.combining(character))
    words = re.findall(r"[^\W\d_]+", folded)
    if len(words) < 2 or any(len(word) < 2 or word in ROLE_WORDS for word in words):
        return None
    return tuple(sorted(words))


def attribution_key(original: str, *, musescore: bool = False) -> tuple[str, ...] | None:
    if musescore:
        original = musescore_display_text(original)
    if not original:
        return ("absent_source_attribution",)
    if original in ATTRIBUTION_LABELS:
        return ("source_attribution_label", original)
    return full_name_key(original)


def primary_title(original: str, source: str, composer: str) -> str:
    # Match the shared translation stage's order: the exact raw guard is kept,
    # while its already-supported display cleanup precedes title projection.
    return project_title(display_source_title(original), source, composer).title


def polish_complete_grammar(original: str, translated: str) -> str:
    """Reorder one complete guitar-lesson construction, preserving all digits."""
    match = re.fullmatch(r"(\d+)首课题为\s*(\d+)\s*吉他(，作品[\dA-Za-z/.:\-]+)?", translated)
    if match:
        polished = f"{match[1]}首吉他课题（{match[2]}把吉他）" + (match[3] or "")
        if Counter(re.findall(r"\d+", original)) == Counter(re.findall(r"\d+", polished)):
            return polished
    return translated


def entry(original: str, zh: str, status: str, basis: str, reason: str) -> dict:
    return {"original": original, "zh": zh, "status": status, "basis": basis, "reason": reason}


def load_document(path: Path, *, optional: bool = False) -> dict:
    if optional and not path.exists():
        return {"schema_version": 1, "entries": {}}
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema_version") != 1:
        raise ValueError(f"invalid review document: {path.name}")
    return document


def reference_indexes(root: Path, documents: dict) -> tuple[dict, dict, dict, dict]:
    """Build spelling references from supported assets with their exact guards."""
    names, titles = defaultdict(lambda: defaultdict(list)), defaultdict(lambda: defaultdict(list))
    for source, group in documents[ASSETS[1]]["entries"].items():
        if source == "musescore":
            continue
        for original, row in group.items():
            if row.get("status") not in SUPPORTED:
                continue
            zh, _ = checked_entry(row, original, f"{source}: {original}")
            key = full_name_key(original)
            if key is not None:
                names[key][strip_authority_dates(zh)].append(f"musicians_zh.json:{source}:{original}")
    composer_path = root / "metadata/translations/composer_overrides_reviewed_zh.json"
    if composer_path.exists():
        for original, zh in load_document(composer_path)["entries"].items():
            key = full_name_key(original)
            if key is not None and isinstance(zh, str) and HAN.search(zh):
                names[key][strip_authority_dates(zh)].append(f"composer_overrides_reviewed_zh.json:{original}")

    def add_title(source: str, identity: str, row: dict, *, imslp: bool = False) -> None:
        if imslp:
            if row.get("retention_reason") or not row.get("basis") or not row.get("reason"):
                return
            original, zh = row.get("title_en"), row.get("title_zh")
        else:
            if row.get("status") not in SUPPORTED:
                return
            original = row.get("original")
            zh, _ = checked_entry(row, original, identity)
        composer = row.get("original_composer")
        if not isinstance(original, str) or not isinstance(composer, str) or not isinstance(zh, str) or not HAN.search(zh):
            return
        key = attribution_key(composer)
        if key is None:
            return
        reference = f"{'title_overrides_reviewed_zh.json' if imslp else 'classclef_titles_zh.json' if source == 'classclef' else ASSETS[0]}:{identity}"
        projection = primary_title(original, source, composer)
        if display_source_title(original) == projection:
            titles[(original, key)][wrap_display_title(zh)].append(reference)
        if "display_zh" in row:
            if row.get("display_original") != projection:
                raise ValueError(f"reference display original drift: {identity}")
            display = row["display_zh"]
            if isinstance(display, str) and HAN.search(display):
                titles[(projection, key)][wrap_display_title(display)].append(reference)

    for identity, row in documents[ASSETS[0]]["entries"].items():
        if not identity.startswith("musescore:"):
            add_title(identity.split(":", 1)[0], identity, row)
    classclef_path = root / "metadata/translations/classclef_titles_zh.json"
    if classclef_path.exists():
        for identity, row in load_document(classclef_path)["entries"].items():
            add_title("classclef", identity, row)
    imslp_path = root / "metadata/translations/title_overrides_reviewed_zh.json"
    if imslp_path.exists():
        for row in load_document(imslp_path)["entries"]:
            add_title("imslp", str(row["work_id"]), row, imslp=True)

    terms, category_terms = dict(TERMS), {}
    terminology_path = root / "metadata/translations/expansion_terminology_zh.json"
    if terminology_path.exists():
        for row in load_document(terminology_path)["entries"]:
            if row.get("status") not in SUPPORTED or (row.get("sources") and "musescore" not in row["sources"]):
                continue
            if not isinstance(row.get("original"), str) or not isinstance(row.get("zh"), str) or not HAN.search(row["zh"]):
                continue
            if row["context"] in {"title_term", "key_signature"}:
                terms[row["original"].casefold()] = row["zh"]
            elif row["context"] == "source_category":
                category_terms[row["original"]] = row["zh"]
    return names, titles, terms, category_terms


def validate_catalog(catalog: dict) -> tuple[dict, dict]:
    if catalog.get("schema_version") != 1 or catalog.get("source_id") != "musescore":
        raise ValueError("review requires the accepted MuseScore catalog")
    works, categories = {}, {}
    for category in catalog["categories"]:
        identity = str(category["id"])
        if identity in categories or not isinstance(category.get("name"), str) or not category["name"].strip():
            raise ValueError("invalid or duplicate MuseScore category")
        categories[identity] = category
    for work in catalog["works"]:
        identity = work["id"]
        if not re.fullmatch(r"musescore:[1-9]\d*", identity) or identity in works:
            raise ValueError("invalid or duplicate MuseScore record identity")
        if not isinstance(work.get("title_en"), str) or not work["title_en"].strip() or not isinstance(work.get("composer_en"), str):
            raise ValueError("missing native MuseScore title or attribution field")
        memberships = [str(value) for value in work["category_ids"]]
        if not memberships or len(memberships) != len(set(memberships)) or not set(memberships).issubset(categories):
            raise ValueError("invalid MuseScore category memberships")
        works[identity] = work
    if not works:
        raise ValueError("refusing a translation review of an empty MuseScore catalog")
    return works, categories


def validate_existing(documents: dict, works: dict, categories: dict) -> None:
    """Reject changed native inputs instead of replacing an earlier decision."""
    for identity, row in documents[ASSETS[0]]["entries"].items():
        if not identity.startswith("musescore:"):
            continue
        if identity not in works:
            raise ValueError(f"MuseScore title absent from accepted catalog: {identity}")
        work = works[identity]
        checked_entry(row, work["title_en"], identity)
        if row.get("original_composer") != work["composer_en"]:
            raise ValueError(f"MuseScore attribution drift: {identity}")
        if row.get("display_original") != primary_title(work["title_en"], "musescore", work["composer_en"]):
            raise ValueError(f"MuseScore display original drift: {identity}")
        if row["status"] not in {*SUPPORTED, "retained"} or not isinstance(row.get("display_zh"), str) or not row["display_zh"].strip():
            raise ValueError(f"unresolved MuseScore title decision: {identity}")
    names = {work["composer_en"] for work in works.values()}
    for original, row in documents[ASSETS[1]]["entries"].get("musescore", {}).items():
        if original not in names:
            raise ValueError(f"MuseScore attribution absent from accepted catalog: {original}")
        checked_entry(row, original, f"musescore: {original}")
        if row["status"] not in {*SUPPORTED, "retained", "not_applicable"}:
            raise ValueError(f"unresolved MuseScore attribution: {original}")
    for identity, row in documents[ASSETS[2]]["entries"].get("musescore", {}).items():
        if identity not in categories:
            raise ValueError(f"MuseScore category absent from accepted catalog: {identity}")
        checked_entry(row, categories[identity]["name"], f"musescore category {identity}")
        if row["status"] not in {*SUPPORTED, "retained"}:
            raise ValueError(f"unresolved MuseScore category: {identity}")


def review_missing_entries(root: Path, documents: dict, works: dict, source_categories: dict) -> tuple[dict, dict]:
    """Review missing decisions only; existing decision objects are preserved."""
    names, title_refs, terms, category_terms = reference_indexes(root, documents)
    proposed = copy.deepcopy(documents)
    title_entries = proposed[ASSETS[0]]["entries"]
    musicians = proposed[ASSETS[1]]["entries"].setdefault("musescore", {})
    categories = proposed[ASSETS[2]]["entries"].setdefault("musescore", {})
    added = {"title": 0, "composer": 0, "category": 0}
    for original in sorted({work["composer_en"] for work in works.values()}):
        if original in musicians:
            continue
        display_name = musescore_display_text(original)
        key = full_name_key(original, musescore=True)
        candidates = names.get(key, {}) if key is not None else {}
        if not original:
            decision = entry("", "", "not_applicable", "absent_source_attribution", "本条来源元数据没有作曲者署名；不由上传者或标题补猜。")
        elif display_name in ATTRIBUTION_LABELS:
            decision = entry(original, ATTRIBUTION_LABELS[display_name], "reference", "exact_source_attribution_label", "仅翻译来源给出的署名标签，不推断具体音乐家身份。")
        elif len(candidates) == 1:
            zh, references = next(iter(candidates.items()))
            decision = entry(original, zh, "reference", "existing_checked_full_name_reference", "去除明确的末尾生卒年后，完整姓名各词与既有已核署名对应；仅复用译名，不建立人物或作品同一性。")
            decision["reference_entries"] = sorted(set(references))
        else:
            reason = ("来源署名本身包含中文；保留其原文，未新增中文姓名或把来源文字升级为规范人名核定。" if HAN.search(display_name)
                      else "既有资产对该完整署名给出不同中文对应，本条来源元数据未附可消除歧义的中文依据；保留原始署名。" if candidates
                      else "本条来源元数据未附可靠中文姓名依据；缩写、昵称、单独姓氏或含责任说明的署名不能扩展为另一完整姓名，保留原文。")
            decision = entry(original, display_name, "retained", "exact_source_attribution_preservation", reason)
        musicians[original] = decision
        added["composer"] += 1
    for identity, category in source_categories.items():
        if identity in categories:
            continue
        original = category["name"]
        zh = category_terms.get(original) or terminology_grammar(original, terms)
        categories[identity] = entry(original, zh or original, "reference" if zh else "retained",
            "checked_source_category_terms" if zh else "exact_source_category_preservation",
            "仅翻译已接受目录的明确栏目文字，不由栏目名推断单条编制、许可或原作属性。" if zh
            else "本条目录名称没有已核中文对应；保留来源栏目原文供对照。")
        added["category"] += 1
    for identity, work in works.items():
        if identity in title_entries:
            continue
        original, composer = work["title_en"], work["composer_en"]
        primary = primary_title(original, "musescore", composer)
        candidates = title_refs.get((primary, attribution_key(composer, musescore=True)), {})
        if len(candidates) == 1:
            zh, references = next(iter(candidates.items()))
            status, basis = "reference", "existing_exact_title_full_attribution_reference"
            reason = "完整显示原题及来源完整署名与既有已核译文对应；仅复用标题译法，不建立跨网站作品或版本关系。"
        elif (zh := terminology_grammar(primary, terms, composer)):
            zh = polish_complete_grammar(primary, zh)
            references = []
            status, basis = "reference", "complete_musical_title_grammar"
            reason = "完整显示原题通过既有音乐体裁、调性与编号词法；中文为参考译法，真实编号、题内括号和原始责任转录保留。"
        else:
            zh, references = primary, []
            status, basis = "retained", "exact_native_primary_title_preservation"
            reason = ("来源显示原题本身包含中文或多语文本；保留完整来源原题及真实编号，不凭中文字符认定已核规范中文题名。" if HAN.search(primary)
                      else "既有资产对该原题与完整署名给出不同译文，本条来源元数据未附可消除歧义的中文依据，保留原题。" if candidates
                      else "本条来源元数据未附可靠中文题名依据，完整曲题也不能由受限音乐词法覆盖；专名或题意未获确认，保留原题和真实编号。")
        decision = entry(original, wrap_display_title(zh), status, basis, reason)
        decision.update(original_composer=composer, display_original=primary,
                        display_zh=wrap_display_title(zh), reference_entries=sorted(set(references)))
        title_entries[identity] = decision
        added["title"] += 1
    validate_existing(proposed, works, source_categories)
    return proposed, added


def build(root: Path, *, apply: bool = False) -> dict:
    root = root.resolve()
    catalog_path = root / "sources/musescore/catalog.json"
    catalog_bytes = catalog_path.read_bytes()
    catalog = json.loads(catalog_bytes)
    works, source_categories = validate_catalog(catalog)
    paths = {name: root / "metadata/translations" / name for name in ASSETS}
    before_bytes = {name: path.read_bytes() if path.exists() else None for name, path in paths.items()}
    documents = {name: load_document(path, optional=True) for name, path in paths.items()}
    for name, document in documents.items():
        if not isinstance(document.get("entries"), dict):
            raise ValueError(f"invalid translation asset: {name}")
    validate_existing(documents, works, source_categories)
    proposed, added = review_missing_entries(root, documents, works, source_categories)
    title_entries = proposed[ASSETS[0]]["entries"]
    musicians = proposed[ASSETS[1]]["entries"]["musescore"]
    categories = proposed[ASSETS[2]]["entries"]["musescore"]
    report = {"schema_version": 1, "source_id": "musescore", "applied": apply,
              "reviewed_at": datetime.now(timezone.utc).isoformat(), "records": len(works),
              "catalog_sha256": hashlib.sha256(catalog_bytes).hexdigest(), "new_entries": added,
              "title_status_counts": dict(Counter(title_entries[identity]["status"] for identity in works)),
              "composer_status_counts": dict(Counter(musicians[work["composer_en"]]["status"] for work in works.values())),
              "unique_composer_status_counts": dict(Counter(row["status"] for row in musicians.values())),
              "category_status_counts": dict(Counter(row["status"] for row in categories.values())),
              "other_source_entries_unchanged": True,
              "scope": "Accepted MuseScore/PDMX records only; display references, no new source access or identity relationships"}
    report_path = root / "sources/musescore/translation-review.json"
    if report_path.exists():
        preceding_report = load_document(report_path)
        if preceding_report.get("source_id") != "musescore":
            raise ValueError("preceding translation receipt belongs to another source")
        # Append-only continuation must not discard the final responsibility
        # correction ledger or its independent old-source parity evidence.
        for key in ("preservation_verification", "responsibility_reconciliation", "attribution_label_review"):
            if key in preceding_report:
                report[key] = copy.deepcopy(preceding_report[key])
    if apply:
        if catalog_path.read_bytes() != catalog_bytes or any(
            (path.read_bytes() if path.exists() else None) != before_bytes[name] for name, path in paths.items()
        ):
            raise ValueError("catalog or translation assets changed during review")
        for name, path in paths.items():
            if proposed[name] != documents[name]:
                atomic_json(path, proposed[name])
        atomic_json(report_path, report)
    return report


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def protected_projection(name: str, document: dict) -> tuple[dict, dict]:
    header = {key: value for key, value in document.items() if key != "entries"}
    entries = {key: value for key, value in document["entries"].items()
               if not (key.startswith("musescore:") if name == ASSETS[0] else key == "musescore")}
    return header, entries


def reconcile_responsibilities(root: Path, *, catalog_sha256: str, apply: bool = False) -> dict:
    """Re-review an exact frozen responsibility correction inside MuseScore only.

    Native record IDs/titles, preceding display guards, the frozen PDMX raw
    attribution and the adapter's explicit responsibility result must all agree.
    This is an explicit corrective operation; ordinary append review continues
    to reject attribution drift. Prior decisions are retained in the same receipt.
    """
    from source_adapters.musescore import _composer

    root = root.resolve()
    catalog_path = root / "sources/musescore/catalog.json"
    catalog_bytes = catalog_path.read_bytes()
    if hashlib.sha256(catalog_bytes).hexdigest() != catalog_sha256:
        raise ValueError("responsibility correction catalog checksum drift")
    works, source_categories = validate_catalog(json.loads(catalog_bytes))
    paths = {name: root / "metadata/translations" / name for name in ASSETS}
    before_bytes = {name: path.read_bytes() for name, path in paths.items()}
    documents = {name: load_document(path) for name, path in paths.items()}
    titles = {identity: row for identity, row in documents[ASSETS[0]]["entries"].items()
              if identity.startswith("musescore:")}
    if set(titles) != set(works):
        raise ValueError("responsibility correction requires unchanged complete MuseScore identities")
    if set(documents[ASSETS[2]]["entries"].get("musescore", {})) != set(source_categories):
        raise ValueError("responsibility correction category identities drift")
    preceding_works = {identity: {**work, "composer_en": titles[identity].get("original_composer")}
                       for identity, work in works.items()}
    if any(not isinstance(work["composer_en"], str) for work in preceding_works.values()):
        raise ValueError("missing preceding MuseScore attribution guard")
    validate_existing(documents, preceding_works, source_categories)
    report_path = root / "sources/musescore/translation-review.json"
    report_bytes = report_path.read_bytes()
    report = json.loads(report_bytes)
    if (report.get("schema_version") != 1 or report.get("source_id") != "musescore"
            or report.get("records") != len(works) or not report.get("applied")):
        raise ValueError("responsibility correction requires the preceding applied review receipt")
    frozen_path = root / "sources/musescore/pdmx/selected-metadata.json"
    frozen_bytes = frozen_path.read_bytes()
    frozen = json.loads(frozen_bytes)
    if frozen.get("schema_version") != 1 or frozen.get("complete") is not True:
        raise ValueError("responsibility correction requires complete frozen PDMX metadata")
    changed, evidence = {}, {}
    for identity, work in works.items():
        native_id = identity.split(":", 1)[1]
        score = frozen.get("records", {}).get(native_id, {}).get("data", {}).get("score", {})
        metadata = work.get("metadata", {})
        raw = score.get("composer_name")
        if (str(score.get("id")) != native_id or score.get("title") != work["title_en"]
                or metadata.get("source_title") != work["title_en"]
                or metadata.get("source_composer_attribution") != (raw or "")):
            raise ValueError(f"frozen native title or attribution drift: {identity}")
        composer, role, note, fields = _composer(raw)
        if (composer != work["composer_en"] or role != metadata.get("attribution_role")
                or note != metadata.get("source_attribution_note")
                or any(metadata.get(key) != value for key, value in fields.items())):
            raise ValueError(f"adapter responsibility result drift: {identity}")
        preceding = titles[identity]
        new_primary = primary_title(work["title_en"], "musescore", work["composer_en"])
        if preceding["original_composer"] != composer:
            changed[identity] = preceding
            evidence[identity] = {"source_composer_attribution": raw or "", "attribution_role": role,
                                  "source_attribution_note": note, "responsibility_fields": fields,
                                  "after_display_original": new_primary}
        elif preceding["display_original"] != new_primary:
            raise ValueError(f"unrelated display original drift: {identity}")
    if not changed:
        validate_existing(documents, works, source_categories)
        return {**report, "applied": apply, "new_entries": {"title": 0, "composer": 0, "category": 0}}
    working = copy.deepcopy(documents)
    for identity in changed:
        del working[ASSETS[0]]["entries"][identity]
    actual_names = {work["composer_en"] for work in works.values()}
    retired = {}
    musicians = working[ASSETS[1]]["entries"]["musescore"]
    for original in sorted(set(musicians) - actual_names):
        retired[original] = {"decision": musicians.pop(original),
                             "record_ids": sorted(identity for identity, row in titles.items()
                                                  if row["original_composer"] == original),
                             "reason": "修正明确责任说明后，该完整文本已不再是任何已接受条目的作曲字段；原决策留在本回执，不作为作曲译名继续使用。"}
    proposed, added = review_missing_entries(root, working, works, source_categories)
    preservation = {}
    for name in ASSETS:
        before_header, before_other = protected_projection(name, documents[name])
        after_header, after_other = protected_projection(name, proposed[name])
        if before_header != after_header or before_other != after_other:
            raise ValueError(f"protected source entries or asset header changed: {name}")
        baseline = report.get("preservation_verification", {}).get("prior_assets", {}).get(name, {})
        if (baseline.get("prior_entries_sha256")
                and baseline["prior_entries_sha256"] != canonical_sha256(before_other)):
            raise ValueError(f"preceding other-source preservation evidence drift: {name}")
        preservation[name] = {"asset_header_unchanged": True, "other_source_entries_unchanged": True,
                              "asset_header_sha256": canonical_sha256(before_header),
                              "other_source_entries_sha256": canonical_sha256(before_other),
                              "other_source_entry_count": (len(before_other) if name == ASSETS[0]
                                                           else sum(len(group) for group in before_other.values()))}
    after_titles = proposed[ASSETS[0]]["entries"]
    untouched = {identity: row for identity, row in titles.items() if identity not in changed}
    after_musicians = proposed[ASSETS[1]]["entries"]["musescore"]
    old_musicians = documents[ASSETS[1]]["entries"]["musescore"]
    if (any(after_titles[identity] != row for identity, row in untouched.items())
            or any(after_musicians[original] != row for original, row in old_musicians.items() if original not in retired)
            or proposed[ASSETS[2]] != documents[ASSETS[2]]):
        raise ValueError("unaffected MuseScore translation decision changed")
    stage = {"reviewed_at": datetime.now(timezone.utc).isoformat(),
             "before_catalog_sha256": report["catalog_sha256"], "after_catalog_sha256": catalog_sha256,
             "frozen_metadata_sha256": hashlib.sha256(frozen_bytes).hexdigest(),
             "changed_title_count": len(changed), "unaffected_title_count": len(untouched),
             "retained_musician_count": len(old_musicians) - len(retired),
             "unaffected_title_decisions_unchanged": True, "retained_musician_decisions_unchanged": True,
             "native_titles_and_record_identities_unchanged": True, "category_decisions_unchanged": True,
             "reason": "限定 MuseScore/PDMX 已接受目录：按原始责任转录及已修正 adapter 分开作曲、改编、抄谱、编辑或未核责任；不由未标角色的名字猜作曲者。",
             "decisions": {identity: {"before": row, "after": after_titles[identity],
                                        "before_composer_decision": old_musicians[row["original_composer"]],
                                        "after_composer_decision": after_musicians[works[identity]["composer_en"]],
                                        "reason": "原题不变；修正来源责任字段后重新核对完整署名与主标题边界，旧中文依据不得跨新作曲上下文沿用。",
                                        "source_evidence": evidence[identity]}
                           for identity, row in changed.items()},
             "retired_musician_entries": retired,
             "added_musician_entries": {original: row for original, row in after_musicians.items()
                                         if original not in old_musicians},
             "preservation": preservation}
    report = copy.deepcopy(report)
    report.setdefault("responsibility_reconciliation", []).append(stage)
    report.update(applied=apply, reviewed_at=stage["reviewed_at"], catalog_sha256=catalog_sha256,
                  new_entries={"title": 0, "composer": added["composer"], "category": 0},
                  title_status_counts=dict(Counter(after_titles[identity]["status"] for identity in works)),
                  composer_status_counts=dict(Counter(after_musicians[work["composer_en"]]["status"] for work in works.values())),
                  unique_composer_status_counts=dict(Counter(row["status"] for row in after_musicians.values())))
    if apply:
        if (catalog_path.read_bytes() != catalog_bytes or report_path.read_bytes() != report_bytes
                or frozen_path.read_bytes() != frozen_bytes
                or any(path.read_bytes() != before_bytes[name] for name, path in paths.items())):
            raise ValueError("catalog, frozen metadata or translation assets changed during responsibility review")
        for name, path in paths.items():
            if proposed[name] != documents[name]:
                atomic_json(path, proposed[name])
        atomic_json(report_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--apply", action="store_true", help="Append reviewed MuseScore entries; default is a non-writing preview.")
    parser.add_argument("--reconcile-responsibilities", action="store_true", help="Re-review exact frozen MuseScore responsibility corrections only.")
    parser.add_argument("--catalog-sha256", help="Required exact accepted-catalog guard for responsibility reconciliation.")
    arguments = parser.parse_args()
    if arguments.reconcile_responsibilities:
        if not arguments.catalog_sha256:
            parser.error("--reconcile-responsibilities requires --catalog-sha256")
        report = reconcile_responsibilities(arguments.root, catalog_sha256=arguments.catalog_sha256, apply=arguments.apply)
    else:
        report = build(arguments.root, apply=arguments.apply)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
