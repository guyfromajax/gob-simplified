#!/usr/bin/env python3
"""
Backfill strategy_settings.alterations on franchise_team_data (FTD) documents.

Default value: 2 (Normal). Does not modify games or tournament documents.

Usage:
  python scripts/backfill_ftd_strategy_alterations.py --db gob-staging
  python scripts/backfill_ftd_strategy_alterations.py --db gob-staging --apply
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.db_migration_cli import connect_migration_target
DEFAULT_VALUE = 2


def backfill_ftd_alterations(*, db_name: str, dry_run: bool) -> dict[str, int]:
    connection = connect_migration_target(db_name, write=not dry_run)
    collection = connection.database["franchise_team_data"]

    stats = {
        "total_docs": 0,
        "already_has_alterations": 0,
        "would_update": 0,
        "updated": 0,
        "missing_strategy_settings": 0,
    }

    for doc in collection.find({}, {"strategy_settings": 1, "franchise_id": 1, "team_id": 1}):
        stats["total_docs"] += 1
        ss = doc.get("strategy_settings")
        if not isinstance(ss, dict):
            stats["missing_strategy_settings"] += 1

        if isinstance(ss, dict) and "alterations" in ss:
            stats["already_has_alterations"] += 1
            continue

        stats["would_update"] += 1
        if dry_run:
            print(
                f"  [dry-run] would set strategy_settings.alterations={DEFAULT_VALUE} "
                f"franchise_id={doc.get('franchise_id')} team_id={doc.get('team_id')}"
            )
            continue

        collection.update_one(
            {"_id": doc["_id"]},
            {"$set": {"strategy_settings.alterations": DEFAULT_VALUE}},
        )
        stats["updated"] += 1

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill FTD strategy_settings.alterations")
    parser.add_argument(
        "--db",
        default="gob-staging",
        choices=("gob-staging", "gob"),
        help="Target database (default: gob-staging)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes; default is dry-run",
    )
    args = parser.parse_args()

    dry_run = not args.apply
    mode = "DRY RUN" if dry_run else "WRITE"
    print(f"[{mode}] backfill FTD strategy_settings.alterations on db={args.db!r} default={DEFAULT_VALUE}")
    stats = backfill_ftd_alterations(db_name=args.db, dry_run=dry_run)
    print(
        f"total_docs={stats['total_docs']} "
        f"already_has_alterations={stats['already_has_alterations']} "
        f"missing_strategy_settings={stats['missing_strategy_settings']} "
        f"would_update={stats['would_update']} "
        f"updated={stats['updated']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
