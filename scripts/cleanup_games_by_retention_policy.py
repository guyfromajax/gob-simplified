#!/usr/bin/env python3
"""
Clean up games collection documents using the retention policy.

Policy implemented:
- gob-staging: delete all docs from games.
- gob: keep only games linked to an active franchise/tournament doc.
  - Delete games missing mode (legacy docs).
  - Keep mode=franchise only when franchise_id exists in franchises._id.
  - Keep mode=tournament only when tournament_id exists in tournaments._id.
  - Delete all other modes (including single).

Safety:
- Dry-run by default.
- Requires --yes to actually delete.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any


def load_env_files() -> None:
    try:
        from dotenv import load_dotenv  # type: ignore
    except ImportError:
        return

    repo_root = Path(__file__).resolve().parent.parent
    for filename in (".env.production", ".env.local", ".env"):
        env_path = repo_root / filename
        if env_path.exists():
            load_dotenv(env_path, override=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cleanup games docs by retention policy")
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Execute deletions. Without this flag, script is dry-run.",
    )
    parser.add_argument(
        "--only-db",
        choices=["gob", "gob-staging"],
        default=None,
        help="Run against one DB only. Default runs both gob and gob-staging.",
    )
    return parser.parse_args()


def get_mongo_uri_for_db(db_name: str) -> str:
    if db_name == "gob":
        uri = os.environ.get("MONGO_URI_PRODUCTION") or os.environ.get("MONGO_URI")
    else:
        uri = os.environ.get("MONGO_URI")

    if not uri:
        if db_name == "gob":
            msg = "Missing MONGO_URI_PRODUCTION/MONGO_URI for gob."
        else:
            msg = "Missing MONGO_URI for gob-staging."
        print(f"❌ {msg}", file=sys.stderr)
        sys.exit(1)
    return uri


def _normalize_id(value: Any) -> str | None:
    if value is None:
        return None
    return str(value).strip()


def analyze_gob(db) -> tuple[list[tuple[Any, str]], dict[str, int], int]:
    franchises_active = {
        str(doc["_id"]) for doc in db["franchises"].find({}, {"_id": 1})
    }
    tournaments_active = {
        str(doc["_id"]) for doc in db["tournaments"].find({}, {"_id": 1})
    }

    to_delete: list[tuple[Any, str]] = []
    reason_counts: dict[str, int] = {}
    total = 0

    cursor = db["games"].find(
        {},
        {
            "_id": 1,
            "mode": 1,
            "franchise_id": 1,
            "tournament_id": 1,
        },
    )
    for game in cursor:
        total += 1
        gid = game.get("_id")
        mode = game.get("mode")
        franchise_id = _normalize_id(game.get("franchise_id"))
        tournament_id = _normalize_id(game.get("tournament_id"))

        reason: str | None = None
        if not mode:
            reason = "missing_mode"
        elif mode == "franchise":
            if not franchise_id or franchise_id not in franchises_active:
                reason = "orphan_franchise"
        elif mode == "tournament":
            if not tournament_id or tournament_id not in tournaments_active:
                reason = "orphan_tournament"
        else:
            reason = f"non_retained_mode:{mode}"

        if reason:
            to_delete.append((gid, reason))
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

    return to_delete, reason_counts, total


def delete_ids(coll, ids: list[Any], chunk_size: int = 1000) -> int:
    deleted = 0
    for i in range(0, len(ids), chunk_size):
        chunk = ids[i : i + chunk_size]
        result = coll.delete_many({"_id": {"$in": chunk}})
        deleted += result.deleted_count
    return deleted


def run_for_db(client, db_name: str, execute: bool) -> None:
    db = client[db_name]
    games = db["games"]
    games_total = games.count_documents({})

    print(f"\n=== {db_name} ===")
    print(f"games total: {games_total}")

    if db_name == "gob-staging":
        to_delete_count = games_total
        print("policy: delete all games docs in gob-staging")
        if not execute:
            print(f"dry-run: would delete {to_delete_count}")
            return
        result = games.delete_many({})
        print(f"deleted: {result.deleted_count}")
        return

    to_delete, reason_counts, total_scanned = analyze_gob(db)
    to_delete_ids = [gid for gid, _ in to_delete]
    keep_count = total_scanned - len(to_delete_ids)

    print(f"scanned: {total_scanned}")
    print(f"keep: {keep_count}")
    print(f"delete: {len(to_delete_ids)}")
    if reason_counts:
        print("delete reasons:")
        for reason in sorted(reason_counts.keys()):
            print(f"  - {reason}: {reason_counts[reason]}")

    if not execute:
        print("dry-run: no deletions executed")
        return

    deleted = delete_ids(games, to_delete_ids)
    print(f"deleted: {deleted}")


def main() -> None:
    args = parse_args()
    load_env_files()

    try:
        from pymongo import MongoClient
    except ImportError:
        print("❌ pymongo not installed. Run: pip install pymongo", file=sys.stderr)
        sys.exit(1)

    target_dbs = [args.only_db] if args.only_db else ["gob-staging", "gob"]

    for db_name in target_dbs:
        uri = get_mongo_uri_for_db(db_name)
        client = MongoClient(uri, serverSelectionTimeoutMS=8000)
        try:
            client.admin.command("ping")
        except Exception as exc:
            print(f"❌ Could not connect to MongoDB for {db_name}: {exc}", file=sys.stderr)
            sys.exit(1)
        run_for_db(client, db_name, execute=args.yes)

    print("\nDone.")


if __name__ == "__main__":
    main()
