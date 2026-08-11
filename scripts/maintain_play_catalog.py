#!/usr/bin/env python3
"""Perform narrow, explicit maintenance on one universal play catalog.

The current operation removes only root ``game_stats`` and ``season_stats`` fields;
team-owned play copies retain their mutable statistics. Dry-run is the default.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from BackEnd.script_db import PRODUCTION_DB, ScriptDatabaseError, connect_script_database
from scripts.publish_universal_data import _validate_backup_root, _write_backup

LEGACY_ROOT_STATS = ("game_stats", "season_stats")


def remove_universal_stats(collection, *, apply: bool) -> dict[str, int]:
    counts = {
        field: collection.count_documents({field: {"$exists": True}})
        for field in LEGACY_ROOT_STATS
    }
    counts["documents"] = collection.count_documents({
        "$or": [{field: {"$exists": True}} for field in LEGACY_ROOT_STATS]
    })
    if apply and counts["documents"]:
        collection.update_many(
            {"$or": [{field: {"$exists": True}} for field in LEGACY_ROOT_STATS]},
            {"$unset": {field: "" for field in LEGACY_ROOT_STATS}},
        )
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, choices=["gob-staging", "gob"])
    parser.add_argument("--remove-universal-stats", action="store_true", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-db")
    parser.add_argument("--backup-dir", type=Path)
    args = parser.parse_args()

    pristine = dict(os.environ)
    connection = connect_script_database(
        target=args.db,
        access="write" if args.apply else "read",
        destructive=args.apply and args.db == PRODUCTION_DB,
        confirm_db=args.confirm_db,
        pristine_env=pristine,
        repo_root=ROOT,
    )
    try:
        if args.apply:
            backup_root = _validate_backup_root(args.backup_dir)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            run_dir = backup_root / f"{args.db}-before-play-catalog-maintenance-{stamp}"
            run_dir.mkdir(mode=0o700)
            backup = _write_backup(run_dir, "plays", list(connection.database.plays.find({})))
            print(f"[BACKUP] plays: {backup}")
        counts = remove_universal_stats(connection.database.plays, apply=args.apply)
        mode = "CLEANED" if args.apply else "DRY RUN"
        print(
            f"[{mode}] documents={counts['documents']} game_stats={counts['game_stats']} "
            f"season_stats={counts['season_stats']}"
        )
        return 0
    finally:
        connection.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ScriptDatabaseError as exc:
        print(f"Refusing unsafe database operation: {exc}", file=sys.stderr)
        raise SystemExit(2)
