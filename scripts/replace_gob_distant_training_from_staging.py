#!/usr/bin/env python3
"""
Replace gob.distant_training with gob-staging.distant_training.

Safety:
- Reads from gob-staging.distant_training
- Writes only to gob.distant_training
- Creates a local JSON backup of gob.distant_training before replacement
- Supports --dry-run to inspect counts without writes
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from bson import json_util
from pymongo import MongoClient


ROOT = Path(__file__).resolve().parents[1]
SRC_DB = "gob-staging"
DST_DB = "gob"
COLLECTION = "distant_training"


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def load_mongo_uri() -> str:
    load_env_file(ROOT / ".env.local")
    load_env_file(ROOT / ".env")
    uri = os.environ.get("MONGO_URI")
    if not uri:
        raise RuntimeError("MONGO_URI not found in environment/.env files")
    return uri


def pull_docs(coll) -> list[dict[str, Any]]:
    return [dict(doc) for doc in coll.find({})]


def write_backup(backup_dir: Path, docs: list[dict[str, Any]]) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    path = backup_dir / f"{COLLECTION}.json"
    path.write_text(json_util.dumps(docs, indent=2), encoding="utf-8")
    return path


def replace_collection(dest_coll, src_docs: list[dict[str, Any]]) -> tuple[int, int]:
    deleted = dest_coll.delete_many({}).deleted_count
    inserted = 0
    if src_docs:
        inserted = len(dest_coll.insert_many(src_docs).inserted_ids)
    return deleted, inserted


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replace gob.distant_training with gob-staging.distant_training."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Show counts only, no writes.")
    mode.add_argument("--apply", action="store_true", help="Back up and replace collection.")
    args = parser.parse_args()

    uri = load_mongo_uri()
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)

    src_coll = client[SRC_DB][COLLECTION]
    dst_coll = client[DST_DB][COLLECTION]

    src_docs = pull_docs(src_coll)
    dst_docs = pull_docs(dst_coll)
    print(
        f"[plan] {COLLECTION}: {SRC_DB} has {len(src_docs)} doc(s), "
        f"{DST_DB} currently has {len(dst_docs)} doc(s)"
    )

    if args.dry_run:
        print("[dry-run] No changes made")
        return 0

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = ROOT / "tmp" / "mongo-backups" / f"{DST_DB}-{COLLECTION}-before-staging-sync-{timestamp}"
    print(f"[backup] Writing pre-replacement backup to {backup_dir}")
    backup_path = write_backup(backup_dir, dst_docs)
    print(f"[backup] wrote {backup_path}")

    deleted, inserted = replace_collection(dst_coll, src_docs)
    final_count = dst_coll.count_documents({})
    print(
        f"[apply] {COLLECTION}: deleted={deleted}, inserted={inserted}, "
        f"{DST_DB} now has {final_count} doc(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
