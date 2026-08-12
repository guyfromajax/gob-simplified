#!/usr/bin/env python3
"""Backfill subscription/geek-points on one explicit database; dry-run by default."""

import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.db_migration_cli import connect_migration_target

FIELDS = {"subscription": "alpha", "geek_points": 0}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", choices=("gob-staging", "gob"), required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    connection = connect_migration_target(args.db, write=args.apply)
    users = connection.database["users"]
    query = {"$or": [{key: {"$exists": False}} for key in FIELDS]}
    count = users.count_documents(query)
    print(f"[PLAN] {args.db}.users candidates={count}")
    if args.apply:
        result = users.update_many(query, {"$set": FIELDS})
        print(f"[DONE] matched={result.matched_count} modified={result.modified_count}")
    else:
        print("[DRY RUN] No data changed.")
    connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
