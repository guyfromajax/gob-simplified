#!/usr/bin/env python3
"""
Backfill strategy_settings.alterations on franchise_team_data (FTD) documents.

Default value: 2 (Normal). Does not modify games or tournament documents.

Usage:
  python scripts/backfill_ftd_strategy_alterations.py --dry-run
  python scripts/backfill_ftd_strategy_alterations.py --db gob-staging
  python scripts/backfill_ftd_strategy_alterations.py --db gob
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VALUE = 2


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _load_mongo_uri() -> str:
    _load_env_file(ROOT / ".env.local")
    _load_env_file(ROOT / ".env")
    uri = os.environ.get("MONGO_URI")
    if not uri:
        raise RuntimeError("MONGO_URI not found in environment/.env files")
    return uri


def backfill_ftd_alterations(*, db_name: str, dry_run: bool) -> dict[str, int]:
    uri = _load_mongo_uri()
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    collection = client[db_name]["franchise_team_data"]

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
        "--dry-run",
        action="store_true",
        help="Report changes without writing",
    )
    args = parser.parse_args()

    mode = "DRY RUN" if args.dry_run else "WRITE"
    print(f"[{mode}] backfill FTD strategy_settings.alterations on db={args.db!r} default={DEFAULT_VALUE}")
    stats = backfill_ftd_alterations(db_name=args.db, dry_run=args.dry_run)
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
