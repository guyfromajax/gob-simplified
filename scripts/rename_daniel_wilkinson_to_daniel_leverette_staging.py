#!/usr/bin/env python3
"""
Rename Daniel Wilkinson to Daniel Leverette in gob-staging.players.

This updates only the universal players collection in the staging database.

Usage:
  python scripts/rename_daniel_wilkinson_to_daniel_leverette_staging.py
  python scripts/rename_daniel_wilkinson_to_daniel_leverette_staging.py --apply
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from BackEnd.script_db import STAGING_DB, ScriptDatabaseError, connect_script_database  # noqa: E402


DB_NAME = STAGING_DB
COLLECTION = "players"
OLD_FIRST = "Daniel"
OLD_LAST = "Wilkinson"
OLD_FULL = "Daniel Wilkinson"
NEW_FIRST = "Daniel"
NEW_LAST = "Leverette"
NEW_FULL = "Daniel Leverette"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write the rename")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    connection = connect_script_database(
        target=DB_NAME,
        access="write" if args.apply else "read",
        pristine_env=dict(os.environ),
        repo_root=ROOT,
    )
    collection = connection.database[COLLECTION]

    query = {
        "$or": [
            {"name": OLD_FULL},
            {"full_name": OLD_FULL},
            {"first_name": OLD_FIRST, "last_name": OLD_LAST},
        ]
    }
    docs = list(
        collection.find(
            query,
            {
                "_id": 1,
                "player_id": 1,
                "name": 1,
                "full_name": 1,
                "first_name": 1,
                "last_name": 1,
                "team": 1,
            },
        )
    )

    print(f"Target: {DB_NAME}.{COLLECTION}")
    print(f"Matched {len(docs)} player document(s) for {OLD_FULL!r}")
    for doc in docs:
        print(
            " - "
            f"_id={doc.get('_id')} player_id={doc.get('player_id')} team={doc.get('team')} "
            f"name={doc.get('name')!r} full_name={doc.get('full_name')!r} "
            f"first_name={doc.get('first_name')!r} last_name={doc.get('last_name')!r}"
        )

    if not docs:
        return 1

    if not args.apply:
        print("Dry-run only. Re-run with --apply to update the document(s).")
        return 0

    modified = 0
    for doc in docs:
        update_fields: dict[str, str] = {}
        if "name" in doc:
            update_fields["name"] = NEW_FULL
        if "full_name" in doc:
            update_fields["full_name"] = NEW_FULL
        if "first_name" in doc:
            update_fields["first_name"] = NEW_FIRST
        if "last_name" in doc:
            update_fields["last_name"] = NEW_LAST

        if not update_fields:
            print(f"Skipping _id={doc.get('_id')}: no recognized name fields present")
            continue

        result = collection.update_one({"_id": doc["_id"]}, {"$set": update_fields})
        modified += result.modified_count

    verify_count = collection.count_documents(
        {
            "$or": [
                {"name": NEW_FULL},
                {"full_name": NEW_FULL},
                {"first_name": NEW_FIRST, "last_name": NEW_LAST},
            ]
        }
    )
    old_remaining = collection.count_documents(query)

    print(f"Modified {modified} player document(s).")
    print(f"Verification: new-name matches={verify_count}; old-name matches remaining={old_remaining}")
    return 0 if old_remaining == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ScriptDatabaseError as exc:
        print(f"Refusing unsafe database operation: {exc}", file=sys.stderr)
        raise SystemExit(2)
