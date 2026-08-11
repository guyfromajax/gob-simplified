#!/usr/bin/env python3
"""
Mark alpha_otps as sent=true for codes listed in used_otp_codes.md.

Usage:
  PYTHONPATH=. python scripts/sync_sent_otps_from_markdown.py
  PYTHONPATH=. python scripts/sync_sent_otps_from_markdown.py --apply
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.db_migration_cli import connect_migration_target

from BackEnd.utils.used_otp_codes_markdown import parse_used_otp_codes_from_file

DB_NAME_STAGING = "gob-staging"
DB_NAME_PRODUCTION = "gob"
COLLECTION = "alpha_otps"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write changes (default: dry-run)")
    parser.add_argument(
        "--db",
        choices=["staging", "production"],
        default="staging",
        help="Target database (default: staging)",
    )
    parser.add_argument(
        "--confirm-production-write",
        action="store_true",
        help="Required with --apply --db production",
    )
    parser.add_argument(
        "--markdown",
        type=Path,
        default=None,
        help="Path to used_otp_codes.md (default: projects/used_otp_codes.md)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_name = DB_NAME_STAGING if args.db == "staging" else DB_NAME_PRODUCTION
    codes = parse_used_otp_codes_from_file(args.markdown)
    print(f"Parsed {len(codes)} codes from markdown")

    connection = connect_migration_target(args.db, write=args.apply)
    collection = connection.database[COLLECTION]

    matched = 0
    updated = 0
    missing = 0
    now = datetime.now(timezone.utc)

    for code in codes:
        doc = collection.find_one({"otp_code": code}, {"otp_code": 1, "sent": 1})
        if not doc:
            missing += 1
            print(f"  missing in DB: {code}")
            continue
        matched += 1
        if doc.get("sent") is True:
            continue
        if args.apply:
            collection.update_one(
                {"otp_code": code},
                {"$set": {"sent": True, "synced_from_markdown_at": now}},
            )
        updated += 1

    print(f"Target: {db_name}.{COLLECTION}")
    print(f"Matched in DB: {matched}")
    print(f"Would mark sent (not already sent): {updated}")
    print(f"Not found in DB: {missing}")

    if not args.apply:
        print("Dry-run only. Re-run with --apply to update documents.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
