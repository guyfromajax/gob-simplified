#!/usr/bin/env python3
"""
Copy the exact contents of gob-staging.recruit_sets into gob.recruit_sets.

Same MONGO_URI cluster, two databases (matches other staging↔gob sync scripts).

Steps on --apply:
1. Read every document from gob-staging.recruit_sets.
2. Delete all documents in gob.recruit_sets.
3. Insert the staging documents into gob.recruit_sets (same _ids and fields).

Usage:
  .venv/bin/python scripts/copy_recruit_sets_staging_to_gob.py --dry-run
  .venv/bin/python scripts/copy_recruit_sets_staging_to_gob.py --apply
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
COLLECTION = "recruit_sets"


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
    mode.add_argument("--apply", action="store_true", help="Replace gob.recruit_sets with staging.")
    args = parser.parse_args()

    client = MongoClient(load_mongo_uri(), serverSelectionTimeoutMS=15000)
    client.admin.command("ping")

    src = client[SRC_DB][COLLECTION]
    dst = client[DST_DB][COLLECTION]

    staging_docs = pull_docs(src)
    gob_docs = pull_docs(dst)

    print(f"[plan] {SRC_DB}.{COLLECTION}: {len(staging_docs)} doc(s)")
    print(f"[plan] {DST_DB}.{COLLECTION}: {len(gob_docs)} doc(s) (will be replaced)")
    if staging_docs:
        sample_ids = [d.get("set_id") or d.get("_id") for d in staging_docs[:5]]
        print(f"[plan] staging sample set_id/_id: {sample_ids}")

    if not staging_docs:
        print(f"Refusing to continue: {SRC_DB}.{COLLECTION} is empty.", file=sys.stderr)
        return 1

    if args.dry_run:
        print("[dry-run] No changes made.")
        return 0

    print(f"[apply] Replacing {DST_DB}.{COLLECTION} with {SRC_DB}.{COLLECTION}…")
    deleted, inserted = replace_collection(dst, staging_docs)
    final_count = dst.count_documents({})
    print(f"[apply] deleted={deleted} inserted={inserted} final_count={final_count}")

    if final_count != len(staging_docs):
        print(
            f"ERROR: final count {final_count} != staging count {len(staging_docs)}",
            file=sys.stderr,
        )
        return 1

    print("[done] gob.recruit_sets matches gob-staging.recruit_sets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
