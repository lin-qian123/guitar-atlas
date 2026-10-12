#!/usr/bin/env python
"""Import the approved frozen PDMX PDF archive into the unified offline library.

Only the fixed Zenodo PDF archive endpoint is permitted. MuseScore and LibreScore
services are never requested. Cached mode makes no network requests.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from source_adapters.pdmx_assets import acquire, consolidate_prefix, download_parallel_archive, initialize_pending_journal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--cached-archive", action="store_true")
    mode.add_argument("--acquire-archive", action="store_true")
    mode.add_argument("--initialize-pending", action="store_true")
    mode.add_argument("--parallel-archive", action="store_true")
    mode.add_argument("--consolidate-prefix", action="store_true")
    parser.add_argument("--batch-size", type=int, default=25)
    args = parser.parse_args()
    if args.consolidate_prefix:
        print(json.dumps(consolidate_prefix(args.root), ensure_ascii=False, indent=2))
        return 0
    if args.parallel_archive:
        download_parallel_archive(args.root)
    report = (initialize_pending_journal(args.root) if args.initialize_pending else
              acquire(args.root, cached_archive=args.cached_archive or args.parallel_archive, batch_size=args.batch_size))
    print(json.dumps({key: report[key] for key in ("status", "counts", "archive_counts", "fresh_verified_prior_records",
                                                "catalog_committed", "snapshot_unchanged", "translation_bytes_unchanged") if key in report},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
