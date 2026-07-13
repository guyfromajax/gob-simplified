#!/usr/bin/env python3
"""
Back up gob.players to gob.players_backup, then replace gob.players with gob-staging.players.

This script is intentionally players-only:
1. Reads gob.players and writes an exact copy to gob.players_backup.
2. Reads gob-staging.players and replaces gob.players with those documents.

Usage:
  .venv/bin/python scripts/sync_gob_players_from_staging_with_backup.py --dry-run
  .venv/bin/python scripts/sync_gob_players_from_staging_with_backup.py --apply
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from pymongo import MongoClient


ROOT = Path(__file__).resolve().parents[1]
SRC_DB = "gob-staging"
DST_DB = "gob"
PLAYERS_COLLECTION = "players"
BACKUP_COLLECTION = "players_backup"


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


def pull_docs(collection) -> list[dict[str, Any]]:
    return [dict(doc) for doc in collection.find({})]


def replace_collection(collection, docs: list[dict[str, Any]]) -> tuple[int, int]:
    deleted = collection.delete_many({}).deleted_count
    inserted = 0
    if docs:
        inserted = len(collection.insert_many(docs, ordered=False).inserted_ids)
    return deleted, inserted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Show counts only; no writes.")
    mode.add_argument("--apply", action="store_true", help="Back up and replace gob.players.")
    args = parser.parse_args()

    client = MongoClient(load_mongo_uri(), serverSelectionTimeoutMS=10000)
    src_players = client[SRC_DB][PLAYERS_COLLECTION]
    dst_players = client[DST_DB][PLAYERS_COLLECTION]
    backup_players = client[DST_DB][BACKUP_COLLECTION]

    staging_docs = pull_docs(src_players)
    gob_docs = pull_docs(dst_players)
    existing_backup_count = backup_players.count_documents({})

    print(f"[plan] {SRC_DB}.{PLAYERS_COLLECTION}: {len(staging_docs)} doc(s)")
    print(f"[plan] {DST_DB}.{PLAYERS_COLLECTION}: {len(gob_docs)} doc(s)")
    print(f"[plan] {DST_DB}.{BACKUP_COLLECTION}: {existing_backup_count} existing doc(s)")

    if not staging_docs:
        print(f"Refusing to continue: {SRC_DB}.{PLAYERS_COLLECTION} is empty.", file=sys.stderr)
        return 1
    if not gob_docs:
        print(f"Refusing to continue: {DST_DB}.{PLAYERS_COLLECTION} is empty.", file=sys.stderr)
        return 1

    if args.dry_run:
        print("[dry-run] No changes made.")
        return 0

    print(f"[backup] Replacing {DST_DB}.{BACKUP_COLLECTION} with current {DST_DB}.{PLAYERS_COLLECTION}")
    backup_deleted, backup_inserted = replace_collection(backup_players, gob_docs)
    backup_final = backup_players.count_documents({})
    print(
        f"[backup] deleted={backup_deleted}, inserted={backup_inserted}, "
        f"final_count={backup_final}"
    )
    if backup_final != len(gob_docs):
        print(
            f"Backup count mismatch: expected {len(gob_docs)}, got {backup_final}. "
            "Aborting before replacing gob.players.",
            file=sys.stderr,
        )
        return 1

    print(f"[apply] Replacing {DST_DB}.{PLAYERS_COLLECTION} with {SRC_DB}.{PLAYERS_COLLECTION}")
    players_deleted, players_inserted = replace_collection(dst_players, staging_docs)
    players_final = dst_players.count_documents({})
    print(
        f"[apply] deleted={players_deleted}, inserted={players_inserted}, "
        f"final_count={players_final}"
    )
    if players_final != len(staging_docs):
        print(
            f"Final count mismatch: expected {len(staging_docs)}, got {players_final}.",
            file=sys.stderr,
        )
        return 1

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
