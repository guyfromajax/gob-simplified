#!/usr/bin/env python3
"""Replace gob.players and gob.recruit_sets with gob-staging copies.

For each collection:
  1. Read all docs from gob-staging
  2. Insert into a temporary collection on gob
  3. Verify counts (and _id sets)
  4. Atomically rename over the live collection (dropTarget=True)

Dry-run is the default. Writes require ``--execute --confirm-db gob``.

Uses the Mongo cluster from repo-root ``.env.local``. Does not modify
gob-staging. Prefer running ``backup_gob_players_and_recruit_sets.py`` first.

Usage:
    .venv/bin/python scripts/publish_players_recruit_sets_staging_to_gob.py
    .venv/bin/python scripts/publish_players_recruit_sets_staging_to_gob.py \\
        --execute --confirm-db gob
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_DB = "gob"
STAGING_DB = "gob-staging"
COLLECTIONS = ("players", "recruit_sets")


def _load_uri() -> str:
    values = dotenv_values(ROOT / ".env.local")
    uri = str(values.get("MONGO_URI") or "").strip()
    if not uri:
        raise SystemExit("Missing MONGO_URI in .env.local")
    return uri


def _ids(docs: list[dict[str, Any]]) -> set[Any]:
    return {doc["_id"] for doc in docs}


def _publish_one(prod_db, staging_db, name: str) -> None:
    source_docs = list(staging_db[name].find({}))
    if not source_docs:
        raise SystemExit(f"Refusing empty source: {STAGING_DB}.{name}")

    dest_before = prod_db[name].count_documents({})
    print(
        f"[PLAN] {name}: {STAGING_DB}={len(source_docs)} → "
        f"{PRODUCTION_DB}={dest_before} (will replace)"
    )

    temp_name = f"{name}__publish_tmp"
    if temp_name in prod_db.list_collection_names():
        prod_db[temp_name].drop()

    temp = prod_db[temp_name]
    try:
        temp.insert_many(source_docs, ordered=True)
        temp_count = temp.count_documents({})
        if temp_count != len(source_docs):
            raise RuntimeError(
                f"Temp count mismatch for {name}: expected {len(source_docs)} got {temp_count}"
            )
        if _ids(list(temp.find({}, {"_id": 1}))) != _ids(source_docs):
            raise RuntimeError(f"_id set mismatch in temporary {name} copy")

        temp.rename(name, dropTarget=True)
        final = list(prod_db[name].find({}))
        if len(final) != len(source_docs) or _ids(final) != _ids(source_docs):
            raise RuntimeError(f"Post-rename verification failed for {name}")
        print(f"[PUBLISHED] {PRODUCTION_DB}.{name}: {len(source_docs)} docs verified")
    except Exception:
        if temp_name in prod_db.list_collection_names():
            prod_db[temp_name].drop()
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Replace production collections. Default is dry-run.",
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

    client = MongoClient(_load_uri(), serverSelectionTimeoutMS=30000)
    try:
        staging = client[STAGING_DB]
        production = client[PRODUCTION_DB]
        if production.name != PRODUCTION_DB or staging.name != STAGING_DB:
            raise SystemExit("Database name mismatch — aborting")

        print(f"=== publish {STAGING_DB} → {PRODUCTION_DB}: {', '.join(COLLECTIONS)} ===")
        for name in COLLECTIONS:
            src_n = staging[name].count_documents({})
            dst_n = production[name].count_documents({})
            print(f"  {name}: staging={src_n} gob={dst_n}")
            if src_n == 0:
                print(f"Refusing empty source: {STAGING_DB}.{name}", file=sys.stderr)
                return 1

        if not args.execute:
            print("[DRY RUN] No production data changed.")
            print("Re-run with --execute --confirm-db gob after confirming backups exist.")
            return 0

        for name in COLLECTIONS:
            _publish_one(production, staging, name)

        print("Done.")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
