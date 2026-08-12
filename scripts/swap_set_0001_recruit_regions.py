#!/usr/bin/env python3
"""Swap two set_0001 recruit Home Regions in one explicit database.

The migration is deliberately narrow and idempotent:

* Willie Caldwell: C -> A
* Leslie Kim: A -> C

It refuses to write unless each database has exactly one set_0001 document,
each name occurs exactly once, and every current value is either the expected
pre-migration value or the desired post-migration value.

Usage:
  .venv/bin/python scripts/swap_set_0001_recruit_regions.py --dry-run
  .venv/bin/python scripts/swap_set_0001_recruit_regions.py --apply
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.db_migration_cli import connect_migration_target
COLLECTION = "recruit_sets"
SET_ID = "set_0001"
CHANGES = {
    "Willie Caldwell": ("C", "A"),
    "Leslie Kim": ("A", "C"),
}


def inspect_database(database, db_name: str) -> tuple[object, dict[str, str]]:
    collection = database[COLLECTION]
    docs = list(
        collection.find(
            {"set_id": SET_ID},
            {"set_id": 1, "recruits.name": 1, "recruits.Home Region": 1},
        )
    )
    if len(docs) != 1:
        raise RuntimeError(
            f"{db_name}.{COLLECTION}: expected exactly one {SET_ID} document; found {len(docs)}"
        )

    doc = docs[0]
    regions: dict[str, str] = {}
    for name, (expected_before, desired_after) in CHANGES.items():
        matches = [r for r in doc.get("recruits", []) if r.get("name") == name]
        if len(matches) != 1:
            raise RuntimeError(
                f"{db_name}.{COLLECTION}: expected exactly one recruit named {name!r}; "
                f"found {len(matches)}"
            )
        current = matches[0].get("Home Region")
        if current not in (expected_before, desired_after):
            raise RuntimeError(
                f"{db_name}.{COLLECTION}: {name!r} has unexpected Home Region "
                f"{current!r}; expected {expected_before!r} or {desired_after!r}"
            )
        regions[name] = current
    return doc["_id"], regions


def apply_database(database, db_name: str, doc_id: object) -> None:
    collection = database[COLLECTION]
    result = collection.update_one(
        {"_id": doc_id, "set_id": SET_ID},
        {
            "$set": {
                "recruits.$[willie].Home Region": CHANGES["Willie Caldwell"][1],
                "recruits.$[leslie].Home Region": CHANGES["Leslie Kim"][1],
            }
        },
        array_filters=[
            {"willie.name": "Willie Caldwell"},
            {"leslie.name": "Leslie Kim"},
        ],
    )
    if result.matched_count != 1:
        raise RuntimeError(
            f"{db_name}.{COLLECTION}: update matched {result.matched_count} documents"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", choices=("gob-staging", "gob"), required=True)
    parser.add_argument("--apply", action="store_true", help="Apply region changes")
    args = parser.parse_args()

    connection = connect_migration_target(args.db, write=args.apply)
    database = connection.database

    doc_id, regions = inspect_database(database, args.db)
    print(f"[before] {args.db}.{COLLECTION} {SET_ID}")
    for name, current in regions.items():
        print(f"  {name}: {current} -> {CHANGES[name][1]}")

    if not args.apply:
        print("[dry-run] Validation passed; no changes made.")
        return 0

    apply_database(database, args.db, doc_id)

    _, regions = inspect_database(database, args.db)
    print(f"[after] {args.db}.{COLLECTION} {SET_ID}")
    for name, current in regions.items():
        desired = CHANGES[name][1]
        print(f"  {name}: {current}")
        if current != desired:
            raise RuntimeError(
                f"{args.db}.{COLLECTION}: verification failed for {name!r}; "
                f"expected {desired!r}, found {current!r}"
            )

    print("[done] Both databases verified.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
