#!/usr/bin/env python3
"""Remove three verified orphan franchise sidecar groups from gob-staging.

Dry-run is the default. Execution requires both ``--execute`` and
``--confirm-db gob-staging``. The cleanup aborts if the observed records differ from
the reviewed snapshot or if any owning franchise, game, or signed-image reference
exists.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from bson import ObjectId

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from BackEnd.script_db import (  # noqa: E402
    STAGING_DB,
    ScriptDatabaseError,
    connect_script_database,
)


EXPECTED_COUNTS = {
    "69a6f5461e6b3c1fcf09fae3": {
        "franchise_team_data": 128,
        "franchise_players_data": 1,
        "franchise_recruits_data": 40,
    },
    "69d6e092b0b0b0977ff2ede6": {
        "franchise_team_data": 128,
        "franchise_players_data": 1536,
        "franchise_recruits_data": 300,
    },
    "69a6f54e1e6b3c1fcf09fb0d": {
        "franchise_team_data": 8,
        "franchise_players_data": 1,
        "franchise_recruits_data": 40,
    },
}


def _query(collection_name: str, franchise_id: str) -> dict:
    value = ObjectId(franchise_id) if collection_name == "franchise_team_data" else franchise_id
    return {"franchise_id": value}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Delete the verified records.")
    parser.add_argument("--confirm-db", help="Required exact database confirmation for execution.")
    args = parser.parse_args()

    connection = connect_script_database(
        target=STAGING_DB,
        access="write" if args.execute else "read",
        destructive=args.execute,
        confirm_db=args.confirm_db,
        pristine_env=dict(os.environ),
        repo_root=ROOT,
    )
    db = connection.database
    try:
        observed: dict[str, dict[str, int]] = {}
        for franchise_id, expected in EXPECTED_COUNTS.items():
            owner_count = db.franchises.count_documents({"_id": ObjectId(franchise_id)})
            game_count = db.games.count_documents({"franchise_id": franchise_id})
            image_refs = db.franchise_players_data.count_documents(
                {
                    "franchise_id": franchise_id,
                    "meta.image_id": {"$exists": True, "$ne": None},
                }
            )
            counts = {
                name: db[name].count_documents(_query(name, franchise_id))
                for name in expected
            }
            observed[franchise_id] = counts
            print(
                f"[PLAN] franchise_id={franchise_id} owner={owner_count} games={game_count} "
                f"signed_image_refs={image_refs} counts={counts}"
            )
            if owner_count or game_count or image_refs:
                raise ScriptDatabaseError(
                    f"Refusing cleanup for {franchise_id}: owner, game, or image references exist"
                )
            if counts != expected:
                raise ScriptDatabaseError(
                    f"Refusing cleanup for {franchise_id}: expected {expected}, observed {counts}"
                )

        if not args.execute:
            print("[DRY RUN] Verified 3 orphan groups and 2,182 sidecar documents; no data changed.")
            return 0

        deleted = {name: 0 for name in next(iter(EXPECTED_COUNTS.values()))}
        for franchise_id, counts in observed.items():
            for name in counts:
                result = db[name].delete_many(_query(name, franchise_id))
                deleted[name] += result.deleted_count

        expected_totals = {
            name: sum(group[name] for group in EXPECTED_COUNTS.values())
            for name in deleted
        }
        if deleted != expected_totals:
            raise RuntimeError(f"Deletion count mismatch: expected {expected_totals}, deleted {deleted}")

        remaining = sum(
            db[name].count_documents(_query(name, franchise_id))
            for franchise_id in EXPECTED_COUNTS
            for name in deleted
        )
        if remaining:
            raise RuntimeError(f"Cleanup verification failed: remaining={remaining}")

        print(f"[DONE] deleted={deleted} total={sum(deleted.values())} remaining=0")
        return 0
    finally:
        connection.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ScriptDatabaseError as exc:
        print(f"Refusing unsafe database operation: {exc}", file=sys.stderr)
        raise SystemExit(2)
