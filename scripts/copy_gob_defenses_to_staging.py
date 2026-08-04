#!/usr/bin/env python3
"""Replace gob-staging.defenses with an exact copy of gob.defenses.

Source credentials come from ``.env`` and target credentials from
``.env.local``. The script hard-checks the database names, never writes to the
source, stages the copied documents in a temporary target collection, verifies
them, and then atomically renames that collection over ``defenses``.

Usage:
  .venv/bin/python scripts/copy_gob_defenses_to_staging.py
  .venv/bin/python scripts/copy_gob_defenses_to_staging.py --execute
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from pymongo import MongoClient


SOURCE_DB = "gob"
TARGET_DB = "gob-staging"
COLLECTION = "defenses"
TEMP_COLLECTION = "defenses__copy_from_gob_tmp"


def load_env_var(path: Path, key: str) -> str | None:
    if not path.exists():
        return None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() == key:
            return value.strip().strip('"').strip("'")
    return None


def docs_by_id(collection) -> dict[Any, dict[str, Any]]:
    return {doc["_id"]: doc for doc in collection.find({})}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replace gob-staging.defenses with an exact copy of gob.defenses."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Perform the replacement. Without this flag, only show the plan.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    source_uri = load_env_var(repo_root / ".env", "MONGO_URI")
    target_uri = load_env_var(repo_root / ".env.local", "MONGO_URI")
    if not source_uri:
        print("Refusing: .env has no MONGO_URI for source gob.", file=sys.stderr)
        return 1
    if not target_uri:
        print("Refusing: .env.local has no MONGO_URI for target gob-staging.", file=sys.stderr)
        return 1

    source_client = MongoClient(source_uri, serverSelectionTimeoutMS=10000)
    target_client = MongoClient(target_uri, serverSelectionTimeoutMS=10000)
    source_db = source_client.get_default_database()
    target_db = target_client.get_default_database()
    if source_db.name != SOURCE_DB:
        print(
            f"Refusing: source database is {source_db.name!r}, expected {SOURCE_DB!r}.",
            file=sys.stderr,
        )
        return 1
    if target_db.name != TARGET_DB:
        print(
            f"Refusing: target database is {target_db.name!r}, expected {TARGET_DB!r}.",
            file=sys.stderr,
        )
        return 1

    source_client.admin.command("ping")
    target_client.admin.command("ping")
    source_docs = list(source_db[COLLECTION].find({}))
    target_count = target_db[COLLECTION].count_documents({})
    print(f"Source {SOURCE_DB}.{COLLECTION}: {len(source_docs)} document(s), read-only")
    print(f"Target {TARGET_DB}.{COLLECTION}: {target_count} document(s), will be replaced")
    if not source_docs:
        print("Refusing to replace the target from an empty source collection.", file=sys.stderr)
        return 1
    if not args.execute:
        print("DRY RUN — no writes performed. Pass --execute to copy.")
        return 0

    temp = target_db[TEMP_COLLECTION]
    temp.drop()
    temp.insert_many(source_docs, ordered=True)
    staged_docs = docs_by_id(temp)
    expected_docs = {doc["_id"]: doc for doc in source_docs}
    if staged_docs != expected_docs:
        temp.drop()
        print("Verification failed before replacement; target defenses was not changed.", file=sys.stderr)
        return 1

    temp.rename(COLLECTION, dropTarget=True)
    copied_docs = docs_by_id(target_db[COLLECTION])
    if copied_docs != expected_docs:
        print("Post-copy verification failed.", file=sys.stderr)
        return 1

    print(
        f"Copied and verified {len(copied_docs)} document(s): "
        f"{SOURCE_DB}.{COLLECTION} -> {TARGET_DB}.{COLLECTION}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
