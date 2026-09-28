#!/usr/bin/env python
"""Render the offline master index from completed category directories."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


MIXED_CATEGORY_LOOKUP: dict[str, dict] = {}
MIXED_FAMILY_ORDER = {
    "strings": 100,
    "woodwinds": 110,
    "brass": 120,
    "keyboard_reed": 130,
    "plucked": 140,
    "percussion": 150,
    "mixed_chamber": 160,
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def valid_pdf(path: Path, expected_size: int | None = None) -> bool:
    if not path.is_file() or path.stat().st_size < 5:
        return False
    with path.open("rb") as handle:
        if handle.read(5) != b"%PDF-":
            return False
    return not expected_size or path.stat().st_size == expected_size


def record_expected_size(record: dict) -> int | None:
    return record.get("download_expected_size") or record.get("expected_size")


def category_info(name: str) -> dict:
    mixed = MIXED_CATEGORY_LOOKUP.get(name)
    if mixed:
        family_key = mixed["display_group"]
        return {
            "zh": mixed["name_zh"],
            "family": mixed["family_zh"],
            "sort": (
                MIXED_FAMILY_ORDER.get(family_key, 199),
                name.casefold().endswith("(arr)"),
                name.casefold(),
            ),
        }
    arrangement = name.casefold().endswith("(arr)")
    kind = "改编" if arrangement else "原作"
    regular = re.fullmatch(r"For (?:(\d+) guitars?|guitar)(?: \(arr\))?", name, re.IGNORECASE)
    if regular:
        count = int(regular.group(1)) if regular.group(1) else 1
        if count == 1:
            family = "独奏吉他"
        elif count == 2:
            family = "吉他二重奏"
        elif count == 3:
            family = "吉他三重奏"
        elif count == 4:
            family = "吉他四重奏"
        else:
            family = "多把吉他"
        return {"zh": f"{count}把吉他·{kind}", "family": family, "sort": (count, 0, arrangement, name.casefold())}

    extended = re.fullmatch(r"For (\d+)[ -]string guitar(?: \(arr\))?", name, re.IGNORECASE)
    if extended:
        strings = int(extended.group(1))
        return {
            "zh": f"{strings}弦吉他·{kind}",
            "family": "扩展弦制独奏",
            "sort": (1, 1, strings, arrangement, name.casefold()),
        }

    flexible = re.fullmatch(r"For (\d+) and (\d+) guitars(?: \(arr\))?", name, re.IGNORECASE)
    if flexible:
        low, high = map(int, flexible.groups())
        return {
            "zh": f"{low}或{high}把吉他·{kind}",
            "family": "灵活编制",
            "sort": (low, 2, high, arrangement, name.casefold()),
        }

    if re.fullmatch(r"For guitar ensemble(?: \(arr\))?", name, re.IGNORECASE):
        return {"zh": f"吉他合奏·{kind}", "family": "吉他合奏与乐团", "sort": (90, 0, arrangement, name.casefold())}
    if re.fullmatch(r"For guitar orchestra(?: \(arr\))?", name, re.IGNORECASE):
        return {"zh": f"吉他乐团·{kind}", "family": "吉他合奏与乐团", "sort": (91, 0, arrangement, name.casefold())}
    return {"zh": "纯吉他分类", "family": "其他分类", "sort": (99, 0, arrangement, name.casefold())}


def category_sort_key(name: str) -> tuple:
    return category_info(name)["sort"]


def category_zh(name: str) -> str:
    return category_info(name)["zh"]


def render(root: Path) -> dict:
    # Keep the production CLI stable while sharing the public presentation.
    from render_offline_site import render as render_offline

    return render_offline(root)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    print(json.dumps(render(args.root), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
