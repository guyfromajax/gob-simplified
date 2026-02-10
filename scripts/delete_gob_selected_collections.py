#!/usr/bin/env python3
"""
Delete all documents from selected collections in the gob database.

Target database:
  - gob (production)

Target collections:
  - franchises
  - games
  - tournaments
  - franchise_team_data
  - franchise_players_data
  - franchise_recruits_data

Safety:
  - Prints pre-delete counts
  - Requires --yes to actually delete
  - Refuses to run against non-gob database

Usage:
  python scripts/delete_gob_selected_collections.py
  python scripts/delete_gob_selected_collections.py --yes
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


TARGET_DB = "gob"
TARGET_COLLECTIONS = [
    "franchises",
    "games",
    "tournaments",
    "franchise_team_data",
    "franchise_players_data",
    "franchise_recruits_data",
]


def load_env_files() -> None:
    """Load env files in priority order, if python-dotenv is available."""
    try:
        from dotenv import load_dotenv  # type: ignore
    except ImportError:
        return

    repo_root = Path(__file__).resolve().parent.parent
    for filename in (".env.production", ".env.local", ".env"):
        env_path = repo_root / filename
        if env_path.exists():
            load_dotenv(env_path, override=False)


def get_mongo_uri() -> str:
    uri = os.environ.get("MONGO_URI_PRODUCTION") or os.environ.get("MONGO_URI")
    if not uri:
        print(
            "❌ Missing Mongo URI. Set MONGO_URI_PRODUCTION or MONGO_URI (or add .env.production/.env.local/.env).",
            file=sys.stderr,
        )
        sys.exit(1)
    return uri


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Delete selected collections from gob database")
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Actually perform deletion (without this flag, script is dry-run).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_env_files()

    try:
        from pymongo import MongoClient
    except ImportError:
        print("❌ pymongo not installed. Run: pip install pymongo", file=sys.stderr)
        sys.exit(1)

    mongo_uri = get_mongo_uri()
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=8000)

    try:
        client.admin.command("ping")
    except Exception as exc:
        print(f"❌ Could not connect to MongoDB: {exc}", file=sys.stderr)
        sys.exit(1)

    db = client[TARGET_DB]

    print(f"📊 Database: {TARGET_DB}")
    print("📋 Target collections:")
    for name in TARGET_COLLECTIONS:
        print(f"  - {name}")

    counts: dict[str, int] = {}
    total = 0
    for coll_name in TARGET_COLLECTIONS:
        count = db[coll_name].count_documents({})
        counts[coll_name] = count
        total += count

    print("\n📈 Current document counts:")
    for coll_name in TARGET_COLLECTIONS:
        print(f"  - {coll_name}: {counts[coll_name]}")
    print(f"  Total: {total}")

    if not args.yes:
        print("\n⚠️ Dry run only. No data deleted.")
        print("Run with --yes to delete all documents from the collections above.")
        return

    print("\n🗑️ Deleting documents...")
    deleted_total = 0
    for coll_name in TARGET_COLLECTIONS:
        result = db[coll_name].delete_many({})
        deleted_total += result.deleted_count
        print(f"  ✅ {coll_name}: deleted {result.deleted_count}")

    print(f"\n✅ Done. Deleted {deleted_total} documents from {TARGET_DB}.")


if __name__ == "__main__":
    main()
