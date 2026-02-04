#!/usr/bin/env python3
"""
Delete all documents from the tournaments collection in gob-staging or gob (production).

⚠️  DESTRUCTIVE: This cannot be undone.

Usage:
  Staging (default): uses MONGO_URI from .env / .env.local, database gob-staging.
    python scripts/delete_all_tournaments_staging.py
    python scripts/delete_all_tournaments_staging.py --yes

  Production (gob): uses .env.production or MONGO_URI_PRODUCTION, database gob.
    python scripts/delete_all_tournaments_staging.py --db gob
    python scripts/delete_all_tournaments_staging.py --db gob --yes
"""

import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
    load_dotenv(".env.local")
except ImportError:
    pass

COLLECTION_NAME = "tournaments"


def _load_production_env():
    _repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    _prod = os.path.join(_repo_root, ".env.production")
    if os.path.exists(_prod):
        try:
            from dotenv import load_dotenv
            load_dotenv(_prod)
        except ImportError:
            pass


def main():
    use_production = "--db" in sys.argv
    db_name = "gob"
    if use_production:
        idx = sys.argv.index("--db")
        if idx + 1 < len(sys.argv):
            db_name = sys.argv[idx + 1].strip()
        if db_name != "gob":
            print("❌ For production wipe use: --db gob", file=sys.stderr)
            sys.exit(1)
        _load_production_env()
        mongo_uri = os.environ.get("MONGO_URI_PRODUCTION") or os.environ.get("MONGO_URI")
    else:
        db_name = "gob-staging"
        mongo_uri = os.environ.get("MONGO_URI")

    if not mongo_uri:
        if use_production:
            print("❌ MONGO_URI_PRODUCTION / MONGO_URI not set. Use .env.production or set MONGO_URI_PRODUCTION.", file=sys.stderr)
        else:
            print("❌ MONGO_URI not set. Set it in .env or .env.local.", file=sys.stderr)
        sys.exit(1)

    try:
        from pymongo import MongoClient
    except ImportError:
        print("❌ pymongo not installed. pip install pymongo", file=sys.stderr)
        sys.exit(1)

    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    db = client[db_name]
    coll = db[COLLECTION_NAME]

    try:
        client.admin.command("ping")
    except Exception as e:
        print(f"❌ Cannot connect to MongoDB: {e}", file=sys.stderr)
        sys.exit(1)

    count = coll.count_documents({})
    if count == 0:
        print(f"✅ {db_name}.{COLLECTION_NAME} is already empty.")
        return

    if "--yes" not in sys.argv and "-y" not in sys.argv:
        print(f"⚠️  About to delete {count} document(s) from {db_name}.{COLLECTION_NAME}.")
        if db_name == "gob":
            print("   ⚠️  This is the PRODUCTION database.")
        print("   This cannot be undone. Run with --yes to confirm.")
        sys.exit(0)

    result = coll.delete_many({})
    print(f"✅ Deleted {result.deleted_count} document(s) from {db_name}.{COLLECTION_NAME}.")


if __name__ == "__main__":
    main()
