#!/usr/bin/env python3
"""
Rename Jett Scheller to Jett Wood in gob-staging.players.

This updates only the universal players collection in the staging database.

Usage:
  python scripts/rename_jett_scheller_to_jett_wood_staging.py
  python scripts/rename_jett_scheller_to_jett_wood_staging.py --apply
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


def _load_env(filepath: Path) -> None:
    if not filepath.exists():
        return
    for line in filepath.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


for env_path in (ROOT / ".env.local", ROOT / ".env"):
    _load_env(env_path)

from pymongo import MongoClient  # noqa: E402


DB_NAME = "gob-staging"
COLLECTION = "players"
OLD_FIRST = "Jett"
OLD_LAST = "Scheller"
OLD_FULL = "Jett Scheller"
NEW_FIRST = "Jett"
NEW_LAST = "Wood"
NEW_FULL = "Jett Wood"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write the rename")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    uri = os.environ.get("MONGO_URI")
    if not uri:
        print("MONGO_URI not set", file=sys.stderr)
        return 1

    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    collection = client[DB_NAME][COLLECTION]

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
    raise SystemExit(main())
