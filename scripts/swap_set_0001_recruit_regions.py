#!/usr/bin/env python3
"""Swap two set_0001 recruit Home Regions in gob and gob-staging.

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

from pymongo import MongoClient


ROOT = Path(__file__).resolve().parents[1]
DATABASES = ("gob", "gob-staging")
COLLECTION = "recruit_sets"
SET_ID = "set_0001"
CHANGES = {
    "Willie Caldwell": ("C", "A"),
    "Leslie Kim": ("A", "C"),
}


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, value = text.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_mongo_uri() -> str:
    load_env_file(ROOT / ".env.local")
    load_env_file(ROOT / ".env")
    uri = os.environ.get("MONGO_URI")
    if not uri:
        raise RuntimeError("MONGO_URI not found in environment, .env.local, or .env")
    return uri


def inspect_database(client: MongoClient, db_name: str) -> tuple[object, dict[str, str]]:
    collection = client[db_name][COLLECTION]
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


def apply_database(client: MongoClient, db_name: str, doc_id: object) -> None:
    collection = client[db_name][COLLECTION]
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
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Verify and report; do not write")
    mode.add_argument("--apply", action="store_true", help="Apply both region changes")
    args = parser.parse_args()

    client = MongoClient(load_mongo_uri(), serverSelectionTimeoutMS=15000)
    client.admin.command("ping")

    inspected: dict[str, tuple[object, dict[str, str]]] = {}
    for db_name in DATABASES:
        doc_id, regions = inspect_database(client, db_name)
        inspected[db_name] = (doc_id, regions)
        print(f"[before] {db_name}.{COLLECTION} {SET_ID}")
        for name, current in regions.items():
            print(f"  {name}: {current} -> {CHANGES[name][1]}")

    if args.dry_run:
        print("[dry-run] Validation passed; no changes made.")
        return 0

    for db_name in DATABASES:
        apply_database(client, db_name, inspected[db_name][0])

    for db_name in DATABASES:
        _, regions = inspect_database(client, db_name)
        print(f"[after] {db_name}.{COLLECTION} {SET_ID}")
        for name, current in regions.items():
            desired = CHANGES[name][1]
            print(f"  {name}: {current}")
            if current != desired:
                raise RuntimeError(
                    f"{db_name}.{COLLECTION}: verification failed for {name!r}; "
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
