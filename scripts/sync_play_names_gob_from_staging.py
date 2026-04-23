#!/usr/bin/env python3
"""
Sync play `name` in production `gob.plays` from `gob-staging.plays`, matching documents
by shared **`_id`** (ObjectId is the same in both databases).

Only documents with **play_type == "set_play"** are considered. Motion plays are omitted.

Default: dry-run only (prints planned updates). Use --apply to write.

Connection (same cluster is typical):
  - MONGO_URI: must reach both databases (default DB in URI path is ignored; script uses names below).
  - Optional MONGO_URI_STAGING / MONGO_URI_PRODUCTION if staging and prod use different clusters.

Databases:
  - Staging: gob-staging
  - Production: gob

Usage:
  python scripts/sync_play_names_gob_from_staging.py
  python scripts/sync_play_names_gob_from_staging.py --apply
"""

from __future__ import annotations

import argparse
import os
import sys

try:
    from dotenv import load_dotenv

    load_dotenv()
    load_dotenv(".env.local")
except ImportError:
    pass

try:
    from pymongo import MongoClient
except ImportError:
    print("❌ Install pymongo: pip install pymongo", file=sys.stderr)
    sys.exit(1)

STAGING_DB = "gob-staging"
PROD_DB = "gob"
COLLECTION = "plays"

# Motion plays lack comparable successful skeletons; only set plays are synced.
PLAY_QUERY = {"play_type": "set_play"}


def _load_production_env():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    prod_env = os.path.join(repo_root, ".env.production")
    if os.path.exists(prod_env):
        try:
            from dotenv import load_dotenv

            load_dotenv(prod_env)
        except ImportError:
            pass


def get_client(uri: str) -> MongoClient:
    return MongoClient(uri, serverSelectionTimeoutMS=8000)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync play names from gob-staging to gob.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Perform updates (default is dry-run).",
    )
    parser.add_argument(
        "--production-env",
        action="store_true",
        help="Load .env.production before reading URIs (optional).",
    )
    args = parser.parse_args()

    if args.production_env:
        _load_production_env()

    staging_uri = os.environ.get("MONGO_URI_STAGING") or os.environ.get("MONGO_URI")
    prod_uri = (
        os.environ.get("MONGO_URI_PRODUCTION")
        or os.environ.get("MONGO_URI_PROD")
        or os.environ.get("MONGO_URI")
    )

    if not staging_uri:
        print("❌ Set MONGO_URI or MONGO_URI_STAGING for staging.", file=sys.stderr)
        sys.exit(1)
    if not prod_uri:
        print("❌ Set MONGO_URI or MONGO_URI_PRODUCTION for production.", file=sys.stderr)
        sys.exit(1)

    c_staging = get_client(staging_uri)
    c_prod = get_client(prod_uri) if prod_uri != staging_uri else c_staging

    try:
        c_staging.admin.command("ping")
        if c_prod is not c_staging:
            c_prod.admin.command("ping")
    except Exception as e:
        print(f"❌ MongoDB ping failed: {e}", file=sys.stderr)
        sys.exit(1)

    staging_coll = c_staging[STAGING_DB][COLLECTION]
    prod_coll = c_prod[PROD_DB][COLLECTION]

    staging_total = staging_coll.count_documents(PLAY_QUERY)
    prod_total = prod_coll.count_documents(PLAY_QUERY)
    print(f"Scope: play_type='set_play' — staging: {staging_total} doc(s), prod: {prod_total} doc(s)")

    staging_plays = list(staging_coll.find(PLAY_QUERY, {"_id": 1, "name": 1}))
    name_by_id: dict = {doc["_id"]: doc.get("name") for doc in staging_plays}
    print(f"Staging set_play docs (by _id): {len(name_by_id)}")

    prod_plays = list(prod_coll.find(PLAY_QUERY, {"_id": 1, "name": 1}))
    planned = []
    prod_no_staging = 0

    for doc in prod_plays:
        _id = doc["_id"]
        if _id not in name_by_id:
            prod_no_staging += 1
            print(
                f"⚠️  No staging set_play with same _id: prod _id={_id} name={doc.get('name')!r}",
                file=sys.stderr,
            )
            continue
        staging_name = name_by_id[_id]
        old_name = doc.get("name")
        if old_name == staging_name:
            continue
        planned.append(
            {
                "_id": _id,
                "old_name": old_name,
                "new_name": staging_name,
            }
        )

    print(f"Production plays scanned: {len(prod_plays)}")
    print(f"Updates needed (name differs): {len(planned)}")
    for row in planned:
        print(f"  _id={row['_id']}")
        print(f"    {row['old_name']!r}  →  {row['new_name']!r}")

    if prod_no_staging:
        print(f"Note: {prod_no_staging} prod doc(s) had no staging set_play with matching _id.")

    if not args.apply:
        print("\nDry-run only. Re-run with --apply to write to gob.plays.")
        return

    if not planned:
        print("Nothing to apply.")
        return

    for row in planned:
        result = prod_coll.update_one(
            {"_id": row["_id"]},
            {"$set": {"name": row["new_name"]}},
        )
        if result.modified_count != 1:
            print(
                f"⚠️  Expected 1 modified for _id={row['_id']}, got {result.modified_count}",
                file=sys.stderr,
            )
    print(f"✅ Applied {len(planned)} update(s) to {PROD_DB}.{COLLECTION}.")


if __name__ == "__main__":
    main()
