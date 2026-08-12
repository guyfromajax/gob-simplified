#!/usr/bin/env python3
"""Create dated in-DB backups of gob.players and gob.recruit_sets.

Copies each source collection into a new collection named:

    players_backup_YYYYMMDD
    recruit_sets_backup_YYYYMMDD

If a same-day name already exists, a UTC time suffix is added (``_HHMMSS``)
so prior backups are never overwritten.

Read-only by default. Writes require ``--execute --confirm-db gob``.

Uses the Mongo cluster from repo-root ``.env.local`` (same cluster hosts ``gob``
and ``gob-staging``). Does not touch gob-staging.

Usage:
    .venv/bin/python scripts/backup_gob_players_and_recruit_sets.py
    .venv/bin/python scripts/backup_gob_players_and_recruit_sets.py \\
        --execute --confirm-db gob
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_DB = "gob"
SOURCES = ("players", "recruit_sets")


def _load_uri() -> str:
    values = dotenv_values(ROOT / ".env.local")
    uri = str(values.get("MONGO_URI") or "").strip()
    if not uri:
        raise SystemExit("Missing MONGO_URI in .env.local")
    return uri


def _backup_name(source: str, stamp: str, existing: set[str]) -> str:
    base = f"{source}_backup_{stamp}"
    if base not in existing:
        return base
    ts = datetime.now(timezone.utc).strftime("%H%M%S")
    candidate = f"{base}_{ts}"
    if candidate in existing:
        raise SystemExit(f"Backup name collision: {candidate}")
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Perform the copies. Default is dry-run.",
    )
    parser.add_argument(
        "--confirm-db",
        help="Required as '--confirm-db gob' when executing.",
    )
    args = parser.parse_args()

    if args.execute and args.confirm_db != PRODUCTION_DB:
        print(
            f"Refusing write: pass --confirm-db {PRODUCTION_DB} with --execute",
            file=sys.stderr,
        )
        return 2

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    client = MongoClient(_load_uri(), serverSelectionTimeoutMS=20000)
    try:
        db = client[PRODUCTION_DB]
        if db.name != PRODUCTION_DB:
            raise SystemExit(f"Refusing: opened db {db.name!r}, expected {PRODUCTION_DB!r}")

        existing = set(db.list_collection_names())
        plan: list[tuple[str, str, int]] = []
        for source in SOURCES:
            if source not in existing:
                print(f"Missing source collection: {PRODUCTION_DB}.{source}", file=sys.stderr)
                return 1
            count = db[source].count_documents({})
            if count == 0:
                print(f"Refusing empty source: {PRODUCTION_DB}.{source}", file=sys.stderr)
                return 1
            dest = _backup_name(source, stamp, existing)
            plan.append((source, dest, count))
            existing.add(dest)  # reserve within this run

        print(f"=== backup plan for {PRODUCTION_DB} (UTC date {stamp}) ===")
        for source, dest, count in plan:
            print(f"  {source} ({count} docs) → {dest}")

        if not args.execute:
            print("[DRY RUN] No collections created. Re-run with --execute --confirm-db gob")
            return 0

        for source, dest, count in plan:
            print(f"Copying {PRODUCTION_DB}.{source} → {PRODUCTION_DB}.{dest} ...")
            db[source].aggregate([{"$match": {}}, {"$out": dest}])
            backed = db[dest].count_documents({})
            if backed != count:
                print(
                    f"Count mismatch for {dest}: source={count} backup={backed}",
                    file=sys.stderr,
                )
                return 1
            print(f"  OK {backed} docs → {PRODUCTION_DB}.{dest}")

        print("Done.")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
