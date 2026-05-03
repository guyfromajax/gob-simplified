#!/usr/bin/env python3
"""
Repair EOS bracket slots that still have ``winner: null`` when ``results.{week}`` (or ``games``)
already has the outcome. Default is dry-run; pass ``--apply`` to write.

Examples:
  .venv/bin/python scripts/repair_franchise_eos_bracket_from_results.py --franchise-id 69f77f5ae1f16161c4ebb5e8
  .venv/bin/python scripts/repair_franchise_eos_bracket_from_results.py --franchise-id ID --weeks 27,28 --apply
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bson import ObjectId  # noqa: E402
from bson.errors import InvalidId  # noqa: E402

from BackEnd.db import db  # noqa: E402
from BackEnd.tournament import franchise_tournament as ft  # noqa: E402
from BackEnd.utils.repair_franchise_eos_bracket import repair_franchise_eos_bracket_from_results  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--franchise-id",
        action="append",
        dest="franchise_ids",
        required=True,
        help="Franchise ObjectId hex (repeat flag for multiple)",
    )
    parser.add_argument(
        "--weeks",
        type=str,
        default="",
        help=f"Comma-separated EOS weeks (default: all {','.join(str(w) for w in ft.EOS_WEEKS)})",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist changes to Mongo (omit for dry-run)",
    )
    args = parser.parse_args()

    if args.weeks.strip():
        try:
            weeks = tuple(int(x.strip()) for x in args.weeks.split(",") if x.strip())
        except ValueError:
            print("Invalid --weeks (use integers like 27,28)", file=sys.stderr)
            return 2
    else:
        weeks = None

    dry_run = not args.apply
    exit_code = 0

    for raw in args.franchise_ids:
        raw = str(raw).strip()
        try:
            fid = ObjectId(raw)
        except InvalidId:
            print(f"Invalid franchise id: {raw}", file=sys.stderr)
            exit_code = 1
            continue

        doc = db.franchises.find_one({"_id": fid})
        if not doc:
            print(f"Not found: {raw}", file=sys.stderr)
            exit_code = 1
            continue

        report = repair_franchise_eos_bracket_from_results(
            doc,
            mongo_db=db,
            weeks=weeks,
            dry_run=dry_run,
        )
        print(json.dumps(report, indent=2, default=str))

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
