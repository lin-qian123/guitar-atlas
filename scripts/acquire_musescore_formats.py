#!/usr/bin/env python
"""Import frozen PDMX MXL/MIDI exports and retain existing PDF/source evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from source_adapters.pdmx_formats import acquire, download_parallel_archive, initialize_pending_journal, rebalance_ranges


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument("--format",choices=["MUSICXML","MIDI","mxl","midi","mid"],required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--cached-archive",action="store_true")
    mode.add_argument("--parallel-archive",action="store_true")
    mode.add_argument("--initialize-pending",action="store_true")
    mode.add_argument("--rebalance-ranges",action="store_true")
    parser.add_argument("--batch-size",type=int,default=25)
    args = parser.parse_args()
    asset_format = "MUSICXML" if args.format in {"MUSICXML","mxl"} else "MIDI"
    if args.rebalance_ranges:
        print(json.dumps(rebalance_ranges(args.root,asset_format=asset_format),ensure_ascii=False,indent=2))
        return 0
    if args.parallel_archive:
        download_parallel_archive(args.root,asset_format=asset_format)
    report = initialize_pending_journal(args.root,asset_format=asset_format) if args.initialize_pending else acquire(
        args.root,asset_format=asset_format,cached_archive=True,batch_size=args.batch_size)
    print(json.dumps({key:report[key] for key in ("format","status","counts","archive_counts","catalog_committed",
                      "snapshot_unchanged","translation_bytes_unchanged") if key in report},ensure_ascii=False,indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
