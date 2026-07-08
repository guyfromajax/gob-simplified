#!/usr/bin/env python3
"""
Create a full copy of gob-staging.players → gob-staging.players_backup.

Use before comp attribute rewrites. Does NOT read or write the gob database.

Restore (manual):
  mongosh ... --eval "
    use('gob-staging');
    db.players_backup.aggregate([{ \$match: {} }, { \$out: 'players' }]);
  "

Or re-run a dedicated restore script.

Run from repo root:
  .venv/bin/python scripts/backup_gob_staging_players.py
  .venv/bin/python scripts/backup_gob_staging_players.py --replace   # overwrite existing backup
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


def _load_env(filepath: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if filepath.exists():
        for line in filepath.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


for p in [ROOT / ".env.local", ROOT / ".env"]:
    for k, v in _load_env(p).items():
        os.environ.setdefault(k, v)

from pymongo import MongoClient

DB_NAME = "gob-staging"
SOURCE_COLLECTION = "players"
BACKUP_COLLECTION = "players_backup"
META_COLLECTION = "players_backup_meta"


def main() -> int:
    parser = argparse.ArgumentParser(description="Backup gob-staging.players collection")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Overwrite existing players_backup collection",
    )
    args = parser.parse_args()

    uri = os.environ.get("MONGO_URI")
    if not uri:
        print("MONGO_URI not set", file=sys.stderr)
        return 1

    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    db = client[DB_NAME]

    if DB_NAME != "gob-staging":
        print(f"Refusing: expected DB gob-staging, got {DB_NAME!r}", file=sys.stderr)
        return 1

    source = db[SOURCE_COLLECTION]
    backup = db[BACKUP_COLLECTION]

    source_count = source.count_documents({})
    if source_count == 0:
        print(f"No documents in {DB_NAME}.{SOURCE_COLLECTION}", file=sys.stderr)
        return 1

    existing_backup = backup.count_documents({})
    if existing_backup and not args.replace:
        print(
            f"{DB_NAME}.{BACKUP_COLLECTION} already has {existing_backup} docs. "
            "Pass --replace to overwrite.",
            file=sys.stderr,
        )
        return 1

    print(f"Backing up {DB_NAME}.{SOURCE_COLLECTION} ({source_count} docs) "
          f"→ {BACKUP_COLLECTION} ...")

    # Exact copy via $out (replaces destination collection contents)
    source.aggregate([{"$match": {}}, {"$out": BACKUP_COLLECTION}])

    backup_count = backup.count_documents({})
    if backup_count != source_count:
        print(
            f"Count mismatch: source={source_count}, backup={backup_count}",
            file=sys.stderr,
        )
        return 1

    meta = {
        "_id": "latest",
        "source_db": DB_NAME,
        "source_collection": SOURCE_COLLECTION,
        "backup_collection": BACKUP_COLLECTION,
        "document_count": backup_count,
        "created_at": datetime.now(timezone.utc),
    }
    db[META_COLLECTION].replace_one({"_id": "latest"}, meta, upsert=True)

    print(f"Done. {backup_count} documents copied to {DB_NAME}.{BACKUP_COLLECTION}")
    print(f"Metadata written to {DB_NAME}.{META_COLLECTION}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
