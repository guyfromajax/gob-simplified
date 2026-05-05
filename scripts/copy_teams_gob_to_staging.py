#!/usr/bin/env python3
"""
One-shot recovery: copy all docs from gob.teams (production, READ-ONLY) into
gob-staging.teams.

SAFETY CONTRACT — read this carefully before running:

- Source MongoClient is opened from .env's MONGO_URI (gob / production).
- Target MongoClient is opened from .env.local's MONGO_URI (gob-staging).
- Hard assertions: source DB name == "gob", target DB name == "gob-staging",
  source URI != target URI. The script exits non-zero if any of these fail —
  it will refuse to run, not "best effort."
- Operations against the source ("gob"): ONLY ``.find({})`` (a read). The
  word ``delete``, ``drop``, ``update``, ``insert``, ``replace`` does not
  appear anywhere in this script targeting the source client. Production
  gob is untouched.
- Operations against the target ("gob-staging"): drop the ``teams``
  collection, then ``insert_many`` the docs read from gob. No other target
  collection is read or written.
- Default mode is dry-run (no writes). Pass ``--execute`` to actually copy.

Usage:
  python3 scripts/copy_teams_gob_to_staging.py            # dry run
  python3 scripts/copy_teams_gob_to_staging.py --execute  # actually copy
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pymongo import MongoClient


def load_env_var(env_path: Path, key: str) -> str | None:
    if not env_path.exists():
        return None
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() == key:
            return v.strip().strip('"').strip("'")
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Copy gob.teams -> gob-staging.teams (read-only against gob)."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually perform the copy. Without this flag, only prints what would happen.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    source_uri = load_env_var(repo_root / ".env", "MONGO_URI")
    target_uri = load_env_var(repo_root / ".env.local", "MONGO_URI")

    if not source_uri:
        print("❌ Could not read MONGO_URI from .env (source = gob).", file=sys.stderr)
        return 1
    if not target_uri:
        print("❌ Could not read MONGO_URI from .env.local (target = gob-staging).", file=sys.stderr)
        return 1
    if source_uri == target_uri:
        print("❌ Refusing to run: source and target URIs are identical.", file=sys.stderr)
        return 1

    source_client = MongoClient(source_uri)
    target_client = MongoClient(target_uri)
    source_db = source_client.get_default_database()
    target_db = target_client.get_default_database()

    if source_db.name != "gob":
        print(
            f"❌ Refusing to run: source DB name is {source_db.name!r}, expected 'gob'.",
            file=sys.stderr,
        )
        return 1
    if target_db.name != "gob-staging":
        print(
            f"❌ Refusing to run: target DB name is {target_db.name!r}, expected 'gob-staging'.",
            file=sys.stderr,
        )
        return 1

    print(f"Source: {source_db.name} (READ-ONLY)")
    print(f"Target: {target_db.name}")
    print()

    source_count = source_db.teams.count_documents({})
    target_count_before = target_db.teams.count_documents({})
    print(f"  gob.teams         has {source_count} docs (will be read)")
    print(f"  gob-staging.teams has {target_count_before} docs (will be DROPPED before insert)")
    print()

    if not args.execute:
        print("DRY RUN — no writes performed. Pass --execute to actually copy.")
        return 0

    # Read every doc from production gob.teams (read-only).
    docs = list(source_db.teams.find({}))
    print(f"Read {len(docs)} docs from gob.teams.")

    # Drop the TARGET teams collection only. Source ('gob') is never touched.
    target_db.teams.drop()
    print("Dropped gob-staging.teams.")

    # Insert the read docs into the target collection.
    if docs:
        target_db.teams.insert_many(docs)
    target_count_after = target_db.teams.count_documents({})
    print(f"Inserted into gob-staging.teams. Final target count: {target_count_after}")

    if target_count_after != source_count:
        print(
            f"⚠️  Count mismatch: source had {source_count}, target now has {target_count_after}.",
            file=sys.stderr,
        )
        return 1
    print("✅ Done. Production gob was not modified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
