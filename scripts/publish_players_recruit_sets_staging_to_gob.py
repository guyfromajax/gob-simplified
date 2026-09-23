#!/usr/bin/env python3
"""Replace gob.players and gob.recruit_sets with gob-staging copies.

For each collection:
  1. Read all docs from gob-staging
  2. Insert into a temporary collection on gob
  3. Verify counts (and _id sets)
  4. Atomically rename over the live collection (dropTarget=True)

Dry-run is the default. Writes require process-level ``GOB_DB_ACCESS=write``
and ``--execute --confirm-db gob``.

Staging is independently resolved from repo-root ``.env.local``. Does not
modify gob-staging. Prefer running ``backup_gob_players_and_recruit_sets.py``
first.

Usage:
    GOB_DB_ACCESS=read .venv/bin/python scripts/publish_players_recruit_sets_staging_to_gob.py
    GOB_DB_ACCESS=write .venv/bin/python scripts/publish_players_recruit_sets_staging_to_gob.py \\
        --execute --confirm-db gob
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from BackEnd.script_db import (  # noqa: E402
    PRODUCTION_DB,
    STAGING_DB,
    ScriptDatabaseError,
    connect_script_database,
)

COLLECTIONS = ("players", "recruit_sets")


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

    pristine = dict(os.environ)
    production = connect_script_database(
        target=PRODUCTION_DB,
        access="write" if args.execute else "read",
        destructive=args.execute,
        confirm_db=args.confirm_db,
        pristine_env=pristine,
        repo_root=ROOT,
    )
    staging = connect_script_database(
        target=STAGING_DB,
        access="read",
        pristine_env=pristine,
        repo_root=ROOT,
        force_local_staging=True,
    )
    try:
        if production.database.name != PRODUCTION_DB or staging.database.name != STAGING_DB:
            raise SystemExit("Database name mismatch — aborting")

        print(f"=== publish {STAGING_DB} → {PRODUCTION_DB}: {', '.join(COLLECTIONS)} ===")
        for name in COLLECTIONS:
            src_n = staging.database[name].count_documents({})
            dst_n = production.database[name].count_documents({})
            print(f"  {name}: staging={src_n} gob={dst_n}")
            if src_n == 0:
                print(f"Refusing empty source: {STAGING_DB}.{name}", file=sys.stderr)
                return 1

        if not args.execute:
            print("[DRY RUN] No production data changed.")
            print("Re-run with --execute --confirm-db gob after confirming backups exist.")
            return 0

        for name in COLLECTIONS:
            _publish_one(production.database, staging.database, name)

        print("Done.")
        return 0
    finally:
        production.close()
        staging.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ScriptDatabaseError as exc:
        print(f"Refusing unsafe database operation: {exc}", file=sys.stderr)
        raise SystemExit(2)
