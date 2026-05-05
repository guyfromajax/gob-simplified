#!/usr/bin/env python3
"""
One-shot recovery: copy all docs from gob.teams (production, READ-ONLY) into
gob-staging.teams via UPSERT — no drops, no deletes.

SAFETY CONTRACT — read carefully before running:

- Source MongoClient is opened from .env's MONGO_URI (gob / production).
- Target MongoClient is opened from .env.local's MONGO_URI (gob-staging).
- Hard assertions: source DB name == "gob", target DB name == "gob-staging",
  source URI != target URI. Script exits non-zero if any of these fail —
  refuses to run, not "best effort."
- Operations against the source ("gob"): ONLY ``.find({})`` (a read).
  ``delete``, ``drop``, ``update``, ``insert``, ``replace`` do NOT appear
  anywhere in this script targeting the source client.
- Operations against the target ("gob-staging"): ONLY ``.update_one(...,
  upsert=True)`` per source doc, keyed by source ``_id``. NO ``drop``, NO
  ``delete_many``, NO ``delete_one``. Existing docs in target that are not
  in source remain untouched.
- Default mode is dry-run (no writes). Pass ``--execute`` to actually upsert.

Usage:
  python3 scripts/upsert_teams_gob_to_staging.py            # dry run
  python3 scripts/upsert_teams_gob_to_staging.py --execute  # actually upsert
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
        description="Upsert gob.teams -> gob-staging.teams (read-only against gob, no drops)."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually perform the upsert. Without this flag, only prints what would happen.",
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
    print(f"Target: {target_db.name} (UPSERT only — no drops, no deletes)")
    print()

    source_count = source_db.teams.count_documents({})
    target_count_before = target_db.teams.count_documents({})
    print(f"  gob.teams         has {source_count} docs (will be read)")
    print(f"  gob-staging.teams has {target_count_before} docs (will be upserted into; nothing deleted)")
    print()

    if not args.execute:
        print("DRY RUN — no writes performed. Pass --execute to actually upsert.")
        return 0

    docs = list(source_db.teams.find({}))
    print(f"Read {len(docs)} docs from gob.teams.")

    upserted = 0
    matched = 0
    for doc in docs:
        _id = doc.get("_id")
        if _id is None:
            continue
        update_fields = {k: v for k, v in doc.items() if k != "_id"}
        result = target_db.teams.update_one(
            {"_id": _id},
            {"$set": update_fields},
            upsert=True,
        )
        if result.upserted_id is not None:
            upserted += 1
        elif result.matched_count:
            matched += 1

    target_count_after = target_db.teams.count_documents({})
    print(f"Upserted {upserted} new doc(s); updated {matched} existing doc(s).")
    print(f"Final gob-staging.teams count: {target_count_after} (was {target_count_before}).")
    print("✅ Done. Production gob was not modified. No deletes performed in target.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
