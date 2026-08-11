#!/usr/bin/env python3
"""Swap selected universal-team prestige values in one explicit database.

Usage:
  .venv/bin/python scripts/swap_universal_team_prestige.py --dry-run
  .venv/bin/python scripts/swap_universal_team_prestige.py --apply
"""

from __future__ import annotations

import argparse
import difflib
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.db_migration_cli import connect_migration_target
COLLECTION = "teams"
TEAM_PAIRS = (
    ("Monroe-Hayes", "D1 Institute"),
    ("St Peters", "Amariabi International"),
    ("Reardon-Mayes", "Ann Arbor"),
    ("Mobile", "Quigley Catholic"),
    ("Knoxville", "Austin"),
    ("Gainesville", "Columbus"),
    ("Cupertino", "Pacific All-Stars"),
    ("Chambless Global", "Berkley"),
    ("Crimson County", "Burroughs"),
    ("IDA", "Sacred Heart"),
    ("River's Edge", "Cardinal Conor"),
    ("Bayou District", "GP Prep School"),
)


def inspect_database(database, db_name: str) -> dict[str, dict[str, Any]]:
    names = [name for pair in TEAM_PAIRS for name in pair]
    docs = list(
        database[COLLECTION].find(
            {"name": {"$in": names}},
            {"name": 1, "prestige": 1},
        )
    )
    by_name: dict[str, list[dict[str, Any]]] = {name: [] for name in names}
    for doc in docs:
        if doc.get("name") in by_name:
            by_name[doc["name"]].append(doc)

    validated: dict[str, dict[str, Any]] = {}
    for name in names:
        matches = by_name[name]
        if len(matches) != 1:
            suggestions = difflib.get_close_matches(
                name,
                database[COLLECTION].distinct("name"),
                n=3,
                cutoff=0.5,
            )
            raise RuntimeError(
                f"{db_name}.{COLLECTION}: expected exactly one team named {name!r}; "
                f"found {len(matches)}; closest names: {suggestions}"
            )
        prestige = matches[0].get("prestige")
        if isinstance(prestige, bool) or not isinstance(prestige, (int, float)):
            raise RuntimeError(
                f"{db_name}.{COLLECTION}: {name!r} has non-numeric prestige {prestige!r}"
            )
        validated[name] = matches[0]
    return validated


def apply_database(
    database,
    db_name: str,
    teams: dict[str, dict[str, Any]],
    session: Any,
) -> None:
    collection = database[COLLECTION]
    for left_name, right_name in TEAM_PAIRS:
        left = teams[left_name]
        right = teams[right_name]
        left_result = collection.update_one(
            {"_id": left["_id"], "prestige": left["prestige"]},
            {"$set": {"prestige": right["prestige"]}},
            session=session,
        )
        right_result = collection.update_one(
            {"_id": right["_id"], "prestige": right["prestige"]},
            {"$set": {"prestige": left["prestige"]}},
            session=session,
        )
        if left_result.matched_count != 1 or right_result.matched_count != 1:
            raise RuntimeError(
                f"{db_name}.{COLLECTION}: guarded update failed for "
                f"{left_name!r} <=> {right_name!r}"
            )


def print_plan(db_name: str, teams: dict[str, dict[str, Any]]) -> None:
    print(f"[{db_name}.{COLLECTION}]")
    for left_name, right_name in TEAM_PAIRS:
        left = teams[left_name]["prestige"]
        right = teams[right_name]["prestige"]
        print(f"  {left_name}: {left} -> {right}; {right_name}: {right} -> {left}")


def verify_database(
    database,
    db_name: str,
    before: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    after = inspect_database(database, db_name)
    for left_name, right_name in TEAM_PAIRS:
        if after[left_name]["prestige"] != before[right_name]["prestige"]:
            raise RuntimeError(f"{db_name}.{COLLECTION}: verification failed for {left_name!r}")
        if after[right_name]["prestige"] != before[left_name]["prestige"]:
            raise RuntimeError(f"{db_name}.{COLLECTION}: verification failed for {right_name!r}")
    return after


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", choices=("gob-staging", "gob"), required=True)
    parser.add_argument("--apply", action="store_true", help="Apply all prestige swaps")
    args = parser.parse_args()

    connection = connect_migration_target(args.db, write=args.apply)
    database = connection.database

    before = inspect_database(database, args.db)
    print("[before / planned swaps]")
    print_plan(args.db, before)

    if not args.apply:
        print("[dry-run] Validation passed; no changes made.")
        return 0

    with connection.client.start_session() as session:
        with session.start_transaction():
            apply_database(database, args.db, before, session)

    print("[after]")
    after = verify_database(database, args.db, before)
    print_plan(args.db, after)

    print("[done] Both databases verified.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
