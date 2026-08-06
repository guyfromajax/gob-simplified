#!/usr/bin/env python3
"""Swap selected universal-team prestige values in gob and gob-staging.

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

from pymongo import MongoClient


ROOT = Path(__file__).resolve().parents[1]
DATABASES = ("gob", "gob-staging")
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


def inspect_database(client: MongoClient, db_name: str) -> dict[str, dict[str, Any]]:
    names = [name for pair in TEAM_PAIRS for name in pair]
    docs = list(
        client[db_name][COLLECTION].find(
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
                client[db_name][COLLECTION].distinct("name"),
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
    client: MongoClient,
    db_name: str,
    teams: dict[str, dict[str, Any]],
    session: Any,
) -> None:
    collection = client[db_name][COLLECTION]
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
    client: MongoClient,
    db_name: str,
    before: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    after = inspect_database(client, db_name)
    for left_name, right_name in TEAM_PAIRS:
        if after[left_name]["prestige"] != before[right_name]["prestige"]:
            raise RuntimeError(f"{db_name}.{COLLECTION}: verification failed for {left_name!r}")
        if after[right_name]["prestige"] != before[left_name]["prestige"]:
            raise RuntimeError(f"{db_name}.{COLLECTION}: verification failed for {right_name!r}")
    return after


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Validate and report without writing")
    mode.add_argument("--apply", action="store_true", help="Apply all prestige swaps")
    args = parser.parse_args()

    client = MongoClient(load_mongo_uri(), serverSelectionTimeoutMS=15000)
    client.admin.command("ping")

    before = {db_name: inspect_database(client, db_name) for db_name in DATABASES}
    print("[before / planned swaps]")
    for db_name in DATABASES:
        print_plan(db_name, before[db_name])

    if args.dry_run:
        print("[dry-run] Validation passed; no changes made.")
        return 0

    with client.start_session() as session:
        with session.start_transaction():
            for db_name in DATABASES:
                apply_database(client, db_name, before[db_name], session)

    print("[after]")
    for db_name in DATABASES:
        after = verify_database(client, db_name, before[db_name])
        print_plan(db_name, after)

    print("[done] Both databases verified.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
