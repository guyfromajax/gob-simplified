#!/usr/bin/env python3
"""
Add scouting_report field to all documents in the universal players collection.

Usage:
  PYTHONPATH=. python scripts/add_scouting_report_to_players.py
  PYTHONPATH=. python scripts/add_scouting_report_to_players.py --apply
  PYTHONPATH=. python scripts/add_scouting_report_to_players.py --apply --db production --confirm-production-write
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.db_migration_cli import connect_migration_target

DB_NAME_STAGING = "gob-staging"
DB_NAME_PRODUCTION = "gob"
COLLECTION = "players"

PETER_GREGORY_REPORT = (
    "Peter Gregory profiles as a polished, score-first combo swingman whose game is built on "
    "shotmaking and elite touch from the free throw line. He scores comfortably at all three "
    "levels and is dangerous both off the catch and off the bounce, with the agility and "
    "ball-handling chops to create his own looks. He's best deployed at the two, where his "
    "perimeter defense holds up against quicker wings. The concerns are real, though: he's "
    'undersized at 6\'0" with a thin frame, and his conditioning is a genuine red flag that caps '
    "the minutes load he can carry. A high-floor offensive piece who must answer durability questions."
)

EMPTY_REPORT = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write changes (default: dry-run)")
    parser.add_argument(
        "--db",
        choices=["staging", "production"],
        default="staging",
        help="Target database (default: staging)",
    )
    parser.add_argument(
        "--confirm-production-write",
        action="store_true",
        help="Required with --apply --db production",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_name = DB_NAME_STAGING if args.db == "staging" else DB_NAME_PRODUCTION
    connection = connect_migration_target(args.db, write=args.apply)
    collection = connection.database[COLLECTION]

    total = collection.count_documents({})
    missing = collection.count_documents({"scouting_report": {"$exists": False}})
    already_set = total - missing

    peter = collection.find_one(
        {
            "first_name": {"$regex": r"^Peter$", "$options": "i"},
            "last_name": {"$regex": r"^Gregory$", "$options": "i"},
        },
        {"_id": 1, "first_name": 1, "last_name": 1, "team": 1, "scouting_report": 1},
    )

    print(f"Target: {db_name}.{COLLECTION}")
    print(f"Total players: {total}")
    print(f"Missing scouting_report: {missing}")
    print(f"Already have scouting_report: {already_set}")
    if peter:
        print(
            f"Peter Gregory: _id={peter['_id']} team={peter.get('team', '?')} "
            f"current_report_len={len(peter.get('scouting_report') or '')}"
        )
    else:
        print("WARNING: Peter Gregory not found — only empty reports would be set")

    if not args.apply:
        print("Dry-run only. Re-run with --apply to update documents.")
        return 0

    result = collection.update_many({}, {"$set": {"scouting_report": EMPTY_REPORT}})
    print(f"Set empty scouting_report on {result.modified_count} player(s)")

    if peter:
        peter_result = collection.update_one(
            {"_id": peter["_id"]},
            {"$set": {"scouting_report": PETER_GREGORY_REPORT}},
        )
        if peter_result.modified_count:
            print(f"Set Peter Gregory scouting report ({len(PETER_GREGORY_REPORT)} chars)")
        else:
            print("Peter Gregory scouting report already matched target value")

    with_report = collection.count_documents({"scouting_report": {"$exists": True}})
    peter_after = collection.find_one({"_id": peter["_id"]}, {"scouting_report": 1}) if peter else None
    empty_count = collection.count_documents({"scouting_report": ""})
    populated_count = collection.count_documents(
        {"scouting_report": {"$exists": True, "$ne": ""}}
    )

    print(f"Players with scouting_report field: {with_report}/{total}")
    print(f"Empty reports: {empty_count}")
    print(f"Populated reports: {populated_count}")
    if peter_after:
        preview = (peter_after.get("scouting_report") or "")[:80]
        print(f"Peter Gregory preview: {preview}...")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
